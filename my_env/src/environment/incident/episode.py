"""The investigation episode: configuration, ledger, envelopes and rendering.

Every tool call goes through :meth:`Episode.call`:

1. the evidence and scratch directories are created/repaired and checked (``lstat``:
   real directories, never symlinks; evidence root-owned 0555 in the container) and the
   catalogue is verified — before ANY handler runs;
2. ``seq += 1`` and ``request_id = "req-%03d" % seq``;
3. a frozen episode answers ``EPISODE_CLOSED`` (recorded, not counted);
4. an exhausted budget answers ``BUDGET_EXCEEDED`` (recorded, not counted, and
   ``state.budget_exhausted`` is set);
5. otherwise ``calls_used += 1`` (also for invalid calls); arguments that cannot be
   recorded faithfully (text that is not valid Unicode, nesting deeper than
   ``MAX_ARGUMENT_DEPTH``) are answered ``INVALID_ARGUMENT`` before any handler runs,
   and otherwise the handler runs;
6. the trace record is appended to ``trace.jsonl`` and ``state.json`` is replaced
   atomically; the envelope and its deterministic rendering are returned. Once the
   call is counted it is always recorded: a result that cannot be serialised is
   replaced by an ``INTERNAL_ERROR`` envelope rather than escaping unrecorded.

The rendering (:func:`render`) is a pure function of the envelope: a compact JSON header
(the envelope without bulky fields) followed by a body (numbered document lines, the
Python output, frequency samples, log rows or a witness response). It contains no
timestamps or durations, so deterministic tools replay byte-for-byte.

The tool set follows the bundle: an MVP (version 1) bundle serves the four MVP tools
(:data:`TOOL_NAMES`) exactly as before; a manifest-v2 bundle serves
:data:`SYSTEM_RESPONSE_TOOL_NAMES`, adding ``query_frequency``, ``query_asset_log``,
``query_control_log``, ``interview_witness`` and ``request_data_return`` and letting
``request_document`` take ``party`` + ``description`` instead of ``doc_id``.

The envelope the model sees is always valid Unicode (lone surrogates, e.g. from
undecodable filenames, are shown as ``\\udcXX`` escapes); trace lines that would
otherwise not encode fall back to ASCII-escaped JSON, which round-trips exactly.

This module must not import ``karotte``.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
import shutil
import stat
import sys
import threading
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from environment.incident.catalogue import (
    Catalogue,
    CatalogueError,
    CursorError,
    Document,
    render_numbered,
    split_lines,
)
from environment.incident.locators import LocatorError, parse_iso_instant
from environment.incident.logs import (
    ASSET_COLUMNS,
    CONTROL_COLUMNS,
    render_rows,
    select_rows,
)
from environment.incident.matching import match_documents, min_description_coverage
from environment.incident.pagination import decode_cursor, encode_cursor, query_digest
from environment.incident.paths import DEFAULT_BUNDLE_DIR
from environment.incident.python_runner import (
    Cleanup,
    Launcher,
    NetworkMode,
    PythonRunner,
)
from environment.incident.submission import validate_submission

__all__ = [
    "TOOL_NAMES",
    "SYSTEM_RESPONSE_TOOL_NAMES",
    "ERROR_CODES",
    "CallResult",
    "Episode",
    "EpisodeConfig",
    "EpisodeError",
    "EpisodeState",
    "HandlerOutcome",
    "build_transcript_summary",
    "classify_outcome",
    "error_obj",
    "read_config_snapshot",
    "read_state",
    "read_trace",
    "render",
    "sha256_text",
    "submission_is_valid",
    "summarize_transcript",
]

TOOL_NAMES = ("list_documents", "request_document", "run_python", "submit_findings")
SYSTEM_RESPONSE_TOOL_NAMES = (
    "list_documents",
    "request_document",
    "query_frequency",
    "query_asset_log",
    "query_control_log",
    "interview_witness",
    "request_data_return",
    "run_python",
    "submit_findings",
)
ERROR_CODES = (
    "INVALID_ARGUMENT",
    "UNKNOWN_ID",
    "BUDGET_EXCEEDED",
    "EPISODE_CLOSED",
    "VALIDATION_FAILED",
    "PYTHON_ERROR",
    "TIMEOUT",
    "RESOURCE_LIMIT",
    "INTERNAL_ERROR",
    # manifest-v2 tools
    "AMBIGUOUS_REQUEST",
    "NOT_HELD",
    "REFUSED",
    "OUT_OF_RANGE",
)
STATE_SCHEMA = 1
STATE_FILE = "state.json"
TRACE_FILE = "trace.jsonl"
SUBMISSION_FILE = "submission.json"
GRADE_FILE = "grade.json"
CONFIG_FILE = "episode_config.json"
LOCK_FILE = ".lock"

OUTPUT_TOKEN_BUDGET = 30_000
# The widened system-response task: 30k bound the two most thorough live runs on
# reasoning tokens alone (decisions 35-36), so it gets its own, larger budget.
SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET = 80_000
# The full investigation (increment B) starts from the widened task's 80k (decision 36);
# a constant of its own so either task can change without touching the other.
FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET = 80_000
CONTEXT_CAP_TOKENS = 200_000
MAX_ARGUMENT_DEPTH = 64
_MAX_ARGUMENT_PROBLEMS = 20

ACCEPTED_MESSAGE = (
    "Submission accepted and frozen. The investigation is now closed: end your turn "
    "without any further tool calls (they would be refused)."
)


class EpisodeError(Exception):
    """The episode's own files are unusable (fail closed)."""


class UnsafePathError(EpisodeError):
    """An episode directory is not what it must be and could not be repaired."""


class EpisodeConfig(BaseModel):
    """Everything the core needs; the Karotte task writes one for all of its tools.

    ``tool_profile`` selects the agent-facing tool descriptions and schemas of the
    Karotte adapters (``"mvp"``: the four MVP tools, unchanged; ``"system_response"``:
    the nine tools of the widened task). The core's behaviour follows the bundle.
    """

    episode_dir: Path
    evidence_dir: Path
    scratch_dir: Path
    bundle_dir: Path = DEFAULT_BUNDLE_DIR
    max_tool_calls: int = Field(default=50, ge=1)
    python_timeout_s: float = Field(default=30.0, gt=0)
    python_memory_bytes: int = Field(default=1 << 30, gt=0)
    python_file_size_bytes: int = Field(default=64 << 20, gt=0)
    python_executable: str = Field(default_factory=lambda: sys.executable)
    max_output_chars: int = Field(default=20_000, ge=100)
    max_code_chars: int = Field(default=100_000, ge=1)
    exec_summary_word_limit: int = Field(default=600, ge=1)
    variant_id: str = "baseline"
    student_uid: int | None = None
    list_page_size: int = Field(default=50, ge=1)
    tool_profile: Literal["mvp", "system_response"] = "mvp"
    frequency_page_size: int = Field(default=1000, ge=1, le=1000)
    log_page_size: int = Field(default=200, ge=1, le=200)
    max_question_chars: int = Field(default=2000, ge=1)
    max_request_chars: int = Field(default=500, ge=1)

    def budgets(self) -> dict[str, Any]:
        budgets: dict[str, Any] = {
            "max_tool_calls": self.max_tool_calls,
            "python_timeout_s": self.python_timeout_s,
            "python_memory_bytes": self.python_memory_bytes,
            "max_output_chars": self.max_output_chars,
            "exec_summary_word_limit": self.exec_summary_word_limit,
            "output_token_budget": OUTPUT_TOKEN_BUDGET,
            "context_cap_tokens": CONTEXT_CAP_TOKENS,
        }
        if self.tool_profile == "system_response":
            budgets["frequency_page_size"] = self.frequency_page_size
            budgets["log_page_size"] = self.log_page_size
        return budgets


@dataclass
class EpisodeState:
    bundle_version: str
    calls_used: int = 0
    seq: int = 0
    retrieved: list[str] = field(default_factory=list)
    frozen: bool = False
    frozen_at_request_id: str | None = None
    submission_sha256: str | None = None
    budget_exhausted: bool = False
    invalid_submission_attempts: int = 0
    python_calls: int = 0
    # run_python calls after which the cleanup hook could not confirm that every
    # student process had stopped (an extension of the contract's state fields).
    cleanup_failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"schema": STATE_SCHEMA, **asdict(self)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> EpisodeState:
        if raw.get("schema") != STATE_SCHEMA:
            raise EpisodeError(f"unsupported state schema {raw.get('schema')!r}")
        try:
            state = cls(
                bundle_version=str(raw["bundle_version"]),
                calls_used=int(raw["calls_used"]),
                seq=int(raw["seq"]),
                retrieved=[str(x) for x in raw["retrieved"]],
                frozen=bool(raw["frozen"]),
                frozen_at_request_id=raw.get("frozen_at_request_id"),
                submission_sha256=raw.get("submission_sha256"),
                budget_exhausted=bool(raw["budget_exhausted"]),
                invalid_submission_attempts=int(raw["invalid_submission_attempts"]),
                python_calls=int(raw["python_calls"]),
                cleanup_failures=int(raw.get("cleanup_failures", 0)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise EpisodeError(f"corrupt episode state: {exc}") from None
        return state


@dataclass
class HandlerOutcome:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    evidence_ids: list[str] = field(default_factory=list)
    next_cursor: str | None = None
    python: dict[str, Any] | None = None
    deterministic: bool = True


@dataclass
class CallResult:
    envelope: dict[str, Any]
    text: str
    text_sha256: str
    counted: bool
    record: dict[str, Any]

    @property
    def ok(self) -> bool:
        return bool(self.envelope["ok"])

    @property
    def error_code(self) -> str | None:
        error = self.envelope.get("error")
        return error["code"] if error else None


Handler = Callable[[EpisodeState, dict[str, Any], str], HandlerOutcome]


def error_obj(
    code: str, message: str, details: list[Any] | None = None
) -> dict[str, Any]:
    assert code in ERROR_CODES, code
    return {"code": code, "message": message, "details": list(details or [])}


def _fail(code: str, message: str, details: list[Any] | None = None) -> HandlerOutcome:
    return HandlerOutcome(ok=False, data={}, error=error_obj(code, message, details))


def sha256_text(text: str) -> str:
    """SHA-256 of ``text`` as UTF-8 (a lone surrogate is hashed as its code point
    rather than raising; identical to plain UTF-8 for every valid string)."""
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def _encodable(text: str) -> bool:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _escape_text(text: str) -> str:
    return (
        text
        if _encodable(text)
        else text.encode("utf-8", "backslashreplace").decode("utf-8")
    )


def _unicode_safe(obj: Any) -> Any:
    """``obj`` with every string valid Unicode (lone surrogates escaped)."""
    if isinstance(obj, str):
        return _escape_text(obj)
    if isinstance(obj, Mapping):
        return {_unicode_safe(k): _unicode_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_unicode_safe(v) for v in obj]
    return obj


def _argument_problems(args: Mapping[str, Any]) -> list[dict[str, str]]:
    """Arguments that cannot be recorded and replayed faithfully: text that is not
    valid Unicode (lone surrogates) and nesting deeper than ``MAX_ARGUMENT_DEPTH``."""
    problems: list[dict[str, str]] = []
    stack: list[tuple[str, Any, int]] = [
        (_escape_text(str(name)), value, 1) for name, value in args.items()
    ]
    for name in args:
        if not _encodable(str(name)):
            problems.append(
                {
                    "path": _escape_text(str(name)),
                    "message": "name is not valid Unicode",
                }
            )
    while stack and len(problems) < _MAX_ARGUMENT_PROBLEMS:
        path, value, depth = stack.pop()
        if isinstance(value, str):
            if not _encodable(value):
                problems.append(
                    {
                        "path": path,
                        "message": "contains text that is not valid Unicode (a lone "
                        "surrogate code point)",
                    }
                )
            continue
        if not isinstance(value, (Mapping, list, tuple)):
            continue
        if depth >= MAX_ARGUMENT_DEPTH:
            problems.append(
                {
                    "path": path,
                    "message": f"nested more than {MAX_ARGUMENT_DEPTH} levels deep",
                }
            )
            continue
        if isinstance(value, Mapping):
            for key, item in value.items():
                key_text = str(key)
                if not _encodable(key_text):
                    problems.append(
                        {
                            "path": f"{path}.{_escape_text(key_text)}",
                            "message": "key is not valid Unicode",
                        }
                    )
                stack.append((f"{path}.{_escape_text(key_text)}", item, depth + 1))
        else:
            stack.extend(
                (f"{path}[{index}]", item, depth + 1)
                for index, item in enumerate(value)
            )
    return sorted(problems[:_MAX_ARGUMENT_PROBLEMS], key=lambda p: p["path"])


def _compact(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# -- rendering -----------------------------------------------------------------
def render(envelope: Mapping[str, Any]) -> str:
    """Deterministic text the model sees (a pure function of the envelope)."""
    header = dict(envelope)
    data = envelope.get("data") or {}
    body: str | None = None
    tool = envelope.get("tool")
    if tool in ("request_document", "request_data_return") and isinstance(
        data.get("content"), str
    ):
        header["data"] = {k: v for k, v in data.items() if k != "content"}
        lines = split_lines(data["content"])
        doc_id = data.get("doc_id", "?")
        body = (
            f"--- {doc_id} text: {len(lines)} numbered lines; cite as "
            f'{{"evidence_id": "{doc_id}", "locator": "L<a>-L<b>"}} ---\n'
            + render_numbered(lines)
        )
    elif tool == "query_frequency" and isinstance(data.get("rows"), list):
        header["data"] = {k: v for k, v in data.items() if k != "rows"}
        body = _frequency_body(data)
    elif tool in ("query_asset_log", "query_control_log") and isinstance(
        data.get("rows"), list
    ):
        header["data"] = {k: v for k, v in data.items() if k != "rows"}
        body = _log_body(tool, data)
    elif tool == "interview_witness" and isinstance(data.get("response_text"), str):
        header["data"] = {k: v for k, v in data.items() if k != "response_text"}
        body = _witness_body(data)
    elif tool == "run_python" and ("stdout" in data or "stderr" in data):
        header["data"] = {
            k: v for k, v in data.items() if k not in ("stdout", "stderr")
        }
        body = (
            _output_section("stdout", data.get("stdout") or "")
            + _output_section("stderr", data.get("stderr") or "")
        ).rstrip("\n")
    head = _compact(header)
    return head if body is None else f"{head}\n\n{body}"


def _page_span(data: Mapping[str, Any]) -> str:
    offset = int(data.get("offset") or 0)
    returned = int(data.get("returned") or 0)
    total = int(data.get("total_rows") or 0)
    if not returned:
        return f"no rows (0 of {total})"
    return f"rows {offset + 1}-{offset + returned} of {total}"


def _window_text(data: Mapping[str, Any]) -> str:
    window = data.get("window") or {}
    return f"{window.get('start')} <= time < {window.get('end')}"


def _frequency_body(data: Mapping[str, Any]) -> str:
    doc_id = data.get("doc_id", "?")
    columns = [str(c) for c in data.get("columns") or ()]
    lines = [
        f"--- {doc_id} samples, {_page_span(data)} with {_window_text(data)}; values "
        "exactly as recorded; cite as "
        f'{{"evidence_id": "{doc_id}", "locator": "time:<start>/<end>"}} or '
        '"rows:<a>-<b>" ---',
        ",".join(columns),
    ]
    lines.extend(",".join(str(cell) for cell in row) for row in data["rows"])
    return "\n".join(lines)


def _log_body(tool: str, data: Mapping[str, Any]) -> str:
    if tool == "query_asset_log":
        name, kind, ident = f"asset {data.get('asset_id')}", "event", "event_id"
        columns = ASSET_COLUMNS
    else:
        name, kind, ident = f"control room {data.get('room')}", "entry", "entry_id"
        columns = CONTROL_COLUMNS
    head = (
        f"--- {name} log, {_page_span(data)} with index time in "
        f"[{(data.get('window') or {}).get('start')}, "
        f"{(data.get('window') or {}).get('end')}); the time as recorded and its clock "
        "come first; index_time_utc (with its uncertainty) only selects rows; cite a "
        f'row as {{"evidence_id": "<its evidence_id>", "locator": "{kind}:<{ident}>"}} ---'
    )
    return head + "\n" + render_rows(data["rows"], columns)


def _witness_body(data: Mapping[str, Any]) -> str:
    response_id = data.get("response_id")
    evidence_id = data.get("evidence_id", "?")
    if response_id:
        head = (
            f"--- response {response_id} ({data.get('role')}, "
            f"{data.get('organisation')}); cite as "
            f'{{"evidence_id": "{evidence_id}", "locator": "response:{response_id}"}} ---'
        )
    else:
        head = (
            f"--- {data.get('role')}, {data.get('organisation')}: outside this witness's "
            "fact card (not citable) ---"
        )
    status = data.get("status")
    lines = [head]
    if status:
        lines.append(str(status))
    lines.append(str(data["response_text"]))
    return "\n".join(lines)


def _output_section(name: str, text: str) -> str:
    text = text or "(empty)"
    if not text.endswith("\n"):
        text += "\n"
    return f"--- {name} ---\n{text}"


# -- safe filesystem helpers ---------------------------------------------------
def _onexc_make_writable(
    func: Callable[..., Any], path: str, exc: BaseException
) -> None:
    parent = os.path.dirname(path)
    try:
        os.chmod(parent, 0o700)
        if os.path.isdir(path) and not os.path.islink(path):
            os.chmod(path, 0o700)
    except OSError:
        raise exc from None
    func(path)


def remove_tree(path: Path) -> None:
    """Remove ``path`` without following symlinks (fd-based ``rmtree``)."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    if stat.S_ISDIR(info.st_mode):
        shutil.rmtree(path, onexc=_onexc_make_writable)
    else:
        os.unlink(path)


def _ensure_real_dir(path: Path, mode: int, owner: int | None) -> None:
    """Make ``path`` a real directory with ``mode`` (and ``owner``), never following
    or keeping a symlink in its place."""
    try:
        info: os.stat_result | None = os.lstat(path)
    except FileNotFoundError:
        info = None
    if info is not None and not stat.S_ISDIR(info.st_mode):
        os.unlink(path)  # a symlink or file planted in place of the directory
        info = None
    elif info is not None and owner is not None and info.st_uid != owner:
        remove_tree(path)
        info = None
    if info is None:
        os.makedirs(path.parent, exist_ok=True)
        os.mkdir(path, 0o700)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if owner is not None:
            os.fchown(fd, owner, owner)
        os.fchmod(fd, mode)
        final = os.fstat(fd)
        if not stat.S_ISDIR(final.st_mode) or (
            owner is not None and final.st_uid != owner
        ):
            raise UnsafePathError(f"{path} is not a directory owned by uid {owner}")
    finally:
        os.close(fd)


def _atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _trace_line(record: Mapping[str, Any]) -> bytes:
    """One ``trace.jsonl`` line. Records holding a lone surrogate (e.g. a rejected
    argument) are written as ASCII-escaped JSON, which ``json.loads`` restores
    exactly, so replay sees the original arguments."""
    try:
        return (_compact(record) + "\n").encode("utf-8")
    except UnicodeEncodeError:
        text = json.dumps(record, sort_keys=True, separators=(",", ":"))
        return (text + "\n").encode("ascii")


def read_state(episode_dir: Path) -> EpisodeState | None:
    path = Path(episode_dir) / STATE_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise EpisodeError(f"cannot read {path}: {exc}") from None
    return EpisodeState.from_dict(raw)


def read_trace(episode_dir: Path) -> list[dict[str, Any]]:
    path = Path(episode_dir) / TRACE_FILE
    if not path.exists():
        return []
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise EpisodeError(
                f"{path}:{number}: corrupt trace record: {exc}"
            ) from None
    return records


# -- the episode ---------------------------------------------------------------
class Episode:
    """One investigation episode backed by files in ``config.episode_dir``.

    State lives on disk and is reloaded under a lock for every call, so several tool
    adapter instances (or processes) can share one episode.
    """

    def __init__(
        self,
        config: EpisodeConfig,
        *,
        launcher: Launcher | None = None,
        cleanup: Cleanup | None = None,
        isolated: bool = False,
        network_mode: NetworkMode = None,
        catalogue: Catalogue | None = None,
    ) -> None:
        self.config = config
        self.launcher = launcher
        self.cleanup = cleanup
        self.isolated = isolated
        self.network_mode = network_mode
        self._catalogue = catalogue
        self._thread_lock = threading.Lock()
        self._handlers: dict[str, Handler] = {
            "list_documents": self._handle_list_documents,
            "request_document": self._handle_request_document,
            "query_frequency": self._handle_query_frequency,
            "query_asset_log": self._handle_query_asset_log,
            "query_control_log": self._handle_query_control_log,
            "interview_witness": self._handle_interview_witness,
            "request_data_return": self._handle_request_data_return,
            "run_python": self._handle_run_python,
            "submit_findings": self._handle_submit_findings,
        }

    # -- paths ------------------------------------------------------------------
    @property
    def episode_dir(self) -> Path:
        return Path(self.config.episode_dir)

    @property
    def state_path(self) -> Path:
        return self.episode_dir / STATE_FILE

    @property
    def trace_path(self) -> Path:
        return self.episode_dir / TRACE_FILE

    @property
    def submission_path(self) -> Path:
        return self.episode_dir / SUBMISSION_FILE

    @property
    def grade_path(self) -> Path:
        return self.episode_dir / GRADE_FILE

    @property
    def config_path(self) -> Path:
        return self.episode_dir / CONFIG_FILE

    @property
    def _lock_path(self) -> Path:
        return self.episode_dir / LOCK_FILE

    @property
    def catalogue(self) -> Catalogue:
        if self._catalogue is None:
            self._catalogue = Catalogue.load(self.config.bundle_dir)
        return self._catalogue

    @property
    def tool_names(self) -> tuple[str, ...]:
        """The tools this episode serves (it follows the bundle's manifest version)."""
        return _tool_names_for(self.catalogue)

    @property
    def _container_mode(self) -> bool:
        """Running as root with a student to protect (the Karotte container)."""
        return self.config.student_uid is not None and os.geteuid() == 0

    # -- locking & persistence ---------------------------------------------------
    @contextmanager
    def _locked(self) -> Iterator[None]:
        with self._thread_lock:
            _ensure_real_dir(self.episode_dir, 0o700, None)
            fd = os.open(self._lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def _ensure_dirs(self) -> None:
        container = self._container_mode
        _ensure_real_dir(self.episode_dir, 0o700, None)
        _ensure_real_dir(
            Path(self.config.evidence_dir),
            0o555 if container else 0o755,
            0 if container else None,
        )
        _ensure_real_dir(
            Path(self.config.scratch_dir),
            0o700,
            self.config.student_uid if container else None,
        )

    def _config_snapshot(self, catalogue: Catalogue | None) -> dict[str, Any]:
        return {
            "config": self.config.model_dump(mode="json"),
            "bundle_id": catalogue.bundle_id if catalogue else None,
            "bundle_version": catalogue.bundle_version if catalogue else None,
            "bundle_sha256": catalogue.bundle_sha256 if catalogue else None,
            "tool_names": list(_tool_names_for(catalogue)) if catalogue else None,
            "isolated": self.isolated,
            "network_mode": self.python_runner().network_mode(),
        }

    def _load_state(self) -> EpisodeState:
        state = read_state(self.episode_dir)
        if state is not None:
            return state
        try:
            catalogue: Catalogue | None = self.catalogue
        except CatalogueError:
            catalogue = None
        _atomic_write(
            self.config_path,
            (_compact(self._config_snapshot(catalogue)) + "\n").encode("utf-8"),
        )
        return EpisodeState(
            bundle_version=catalogue.bundle_version if catalogue else "unavailable"
        )

    def _save_state(self, state: EpisodeState) -> None:
        _atomic_write(
            self.state_path,
            (json.dumps(state.to_dict(), sort_keys=True, indent=2) + "\n").encode(),
        )

    def _append_trace(self, record: dict[str, Any]) -> None:
        line = _trace_line(record)
        fd = os.open(
            self.trace_path,
            os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
        )
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)

    def state(self) -> EpisodeState:
        """Current state (fresh if the episode has not started)."""
        with self._locked():
            return self._load_state()

    def trace(self) -> list[dict[str, Any]]:
        return read_trace(self.episode_dir)

    # -- lifecycle ---------------------------------------------------------------
    def reset(self) -> dict[str, Any]:
        """Wipe and recreate the episode, evidence and scratch directories.

        Verifies the bundle first (fails closed with :class:`CatalogueError`). Returns
        metadata for the task's pre-hook.
        """
        catalogue = self.catalogue
        catalogue.verify()
        with self._locked():
            for entry in os.listdir(self.episode_dir):
                if entry != LOCK_FILE:
                    remove_tree(self.episode_dir / entry)
            remove_tree(Path(self.config.evidence_dir))
            remove_tree(Path(self.config.scratch_dir))
            self._ensure_dirs()
            _atomic_write(
                self.config_path,
                (_compact(self._config_snapshot(catalogue)) + "\n").encode("utf-8"),
            )
            self._save_state(EpisodeState(bundle_version=catalogue.bundle_version))
            _atomic_write(self.trace_path, b"")
        return {
            "bundle_id": catalogue.bundle_id,
            "bundle_version": catalogue.bundle_version,
            "bundle_sha256": catalogue.bundle_sha256,
            "manifest_version": getattr(catalogue, "manifest_version", 1),
            "tool_names": list(_tool_names_for(catalogue)),
            "documents": catalogue.ids(),
            "variant_id": self.config.variant_id,
            "budgets": self.config.budgets(),
            "isolated": self.isolated,
            "network_mode": self.python_runner().network_mode(),
        }

    # -- the ledger --------------------------------------------------------------
    def call(
        self,
        tool: str,
        args: Mapping[str, Any] | None,
        handler: Handler | None = None,
        *,
        forced_uncounted_error: Mapping[str, Any] | None = None,
    ) -> CallResult:
        """Run one tool call through the ledger (see the module docstring).

        ``forced_uncounted_error`` is for replay only: it reproduces a recorded
        pre-flight ``INTERNAL_ERROR``.
        """
        clean_args = {k: v for k, v in dict(args or {}).items() if v is not None}
        with self._locked():
            preflight: dict[str, Any] | None = None
            if forced_uncounted_error is not None:
                preflight = dict(forced_uncounted_error)
            else:
                try:
                    self._ensure_dirs()
                    _ = self.catalogue
                except CatalogueError as exc:
                    preflight = error_obj(
                        "INTERNAL_ERROR",
                        "The evidence bundle failed integrity verification; the "
                        f"environment cannot serve this call ({exc}).",
                    )
                except (OSError, EpisodeError) as exc:
                    preflight = error_obj(
                        "INTERNAL_ERROR",
                        f"The episode directories are unusable ({exc}).",
                    )
            state = self._load_state()
            state.seq += 1
            request_id = f"req-{state.seq:03d}"
            counted = False
            if preflight is not None:
                outcome = HandlerOutcome(ok=False, error=preflight)
            elif state.frozen:
                outcome = _fail(
                    "EPISODE_CLOSED",
                    "The investigation is closed: a valid submission was accepted and "
                    f"frozen at {state.frozen_at_request_id}. End your turn without "
                    "further tool calls.",
                )
            elif state.calls_used >= self.config.max_tool_calls:
                state.budget_exhausted = True
                outcome = _fail(
                    "BUDGET_EXCEEDED",
                    f"The tool-call budget of {self.config.max_tool_calls} calls is used "
                    "up; no further calls can run.",
                )
            else:
                state.calls_used += 1
                counted = True
                served = self.tool_names
                chosen = handler or (
                    self._handlers.get(tool) if tool in served else None
                )
                problems = _argument_problems(clean_args)
                if chosen is None:
                    outcome = _fail(
                        "INVALID_ARGUMENT",
                        f"unknown tool {_escape_text(tool)!r}; tools: "
                        f"{', '.join(served)}",
                    )
                elif problems:
                    if tool == "submit_findings":
                        state.invalid_submission_attempts += 1
                    outcome = _fail(
                        "INVALID_ARGUMENT",
                        "the arguments could not be accepted: "
                        + "; ".join(f"{p['path']}: {p['message']}" for p in problems),
                        problems,
                    )
                else:
                    try:
                        outcome = chosen(state, clean_args, request_id)
                    except Exception as exc:  # noqa: BLE001 - reported as INTERNAL_ERROR
                        outcome = _fail(
                            "INTERNAL_ERROR",
                            f"internal error while handling {tool}: "
                            f"{type(exc).__name__}: {exc}",
                        )
                        # Code may have run before the crash: replay must use the
                        # recording rather than execute it again.
                        outcome.deterministic = tool != "run_python"
            try:
                envelope, text, text_sha, record = self._record(
                    state, request_id, tool, clean_args, counted, outcome
                )
            except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
                # The call has happened (and may have run code): record it anyway.
                failed = _fail(
                    "INTERNAL_ERROR",
                    f"the result of this {_escape_text(tool)} call could not be "
                    f"recorded ({type(exc).__name__}); it was counted",
                )
                failed.deterministic = False
                envelope, text, text_sha, record = self._record(
                    state,
                    request_id,
                    tool,
                    {"unrecordable_arguments": sorted(map(str, clean_args))},
                    counted,
                    failed,
                )
            self._append_trace(record)
            self._save_state(state)
        return CallResult(
            envelope=envelope,
            text=text,
            text_sha256=text_sha,
            counted=counted,
            record=record,
        )

    def _record(
        self,
        state: EpisodeState,
        request_id: str,
        tool: str,
        args: dict[str, Any],
        counted: bool,
        outcome: HandlerOutcome,
    ) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
        """The envelope (valid Unicode), its rendering and hash, and the trace record."""
        envelope = _unicode_safe(
            {
                "ok": bool(outcome.ok),
                "request_id": request_id,
                "tool": tool,
                "evidence_ids": list(outcome.evidence_ids),
                "data": outcome.data,
                "error": outcome.error,
                "next_cursor": outcome.next_cursor,
                "budget": {
                    "tool_calls_used": state.calls_used,
                    "tool_calls_limit": self.config.max_tool_calls,
                    "tool_calls_remaining": max(
                        0, self.config.max_tool_calls - state.calls_used
                    ),
                },
            }
        )
        text = render(envelope)
        text_sha = sha256_text(text)
        record: dict[str, Any] = {
            "seq": state.seq,
            "request_id": request_id,
            "tool": tool,
            "args": args,
            "args_sha256": sha256_text(_compact(args)),
            "counted": counted,
            "outcome_code": envelope["error"]["code"] if envelope["error"] else "OK",
            "envelope": envelope,
            "rendered_text_sha256": text_sha,
            "deterministic": bool(outcome.deterministic),
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        if outcome.python is not None:
            record["python"] = outcome.python
        _trace_line(record)  # fail here, before anything is written
        return envelope, text, text_sha, record

    # convenience wrappers ------------------------------------------------------
    def list_documents(
        self, category: str | None = None, cursor: str | None = None
    ) -> CallResult:
        return self.call("list_documents", {"category": category, "cursor": cursor})

    def request_document(self, doc_id: str | None = None) -> CallResult:
        return self.call("request_document", {"doc_id": doc_id})

    def run_python(self, code: str | None = None) -> CallResult:
        return self.call("run_python", {"code": code})

    def submit_findings(self, submission: Any = None) -> CallResult:
        return self.call("submit_findings", {"submission": submission})

    # -- handlers ----------------------------------------------------------------
    @staticmethod
    def _unexpected(
        args: Mapping[str, Any], allowed: tuple[str, ...]
    ) -> HandlerOutcome | None:
        extra = sorted(set(args) - set(allowed))
        if not extra:
            return None
        return _fail(
            "INVALID_ARGUMENT",
            f"unexpected argument(s) {', '.join(extra)}; this tool accepts: "
            f"{', '.join(allowed)}",
            [{"path": name, "message": "unexpected argument"} for name in extra],
        )

    @staticmethod
    def _optional_str(
        args: Mapping[str, Any], name: str
    ) -> tuple[str | None, HandlerOutcome | None]:
        value = args.get(name)
        if value is None:
            return None, None
        if not isinstance(value, str):
            return None, _fail(
                "INVALID_ARGUMENT",
                f"{name} must be a string",
                [{"path": name, "message": "must be a string"}],
            )
        value = value.strip()
        return (value or None), None

    def _handle_list_documents(
        self, state: EpisodeState, args: dict[str, Any], request_id: str
    ) -> HandlerOutcome:
        if bad := self._unexpected(args, ("category", "cursor")):
            return bad
        category, bad = self._optional_str(args, "category")
        if bad:
            return bad
        cursor, bad = self._optional_str(args, "cursor")
        if bad:
            return bad
        catalogue = self.catalogue
        categories = list(catalogue.categories)
        if category is not None and category not in categories:
            return _fail(
                "INVALID_ARGUMENT",
                f"unknown category {category!r}; valid categories: {', '.join(categories)}",
                [
                    {
                        "path": "category",
                        "message": "unknown category",
                        "valid": categories,
                    }
                ],
            )
        try:
            page, next_cursor = catalogue.list_page(
                category, cursor, self.config.list_page_size
            )
        except CursorError as exc:
            return _fail(
                "INVALID_ARGUMENT", str(exc), [{"path": "cursor", "message": str(exc)}]
            )
        total = sum(
            1
            for d in catalogue
            if (category is None or d.category == category)
            and catalogue.is_listed(d.doc_id)
        )
        data: dict[str, Any] = {
            "documents": [doc.summary() for doc in page],
            "categories": categories,
            "category": category,
            "total": total,
            "page_size": self.config.list_page_size,
        }
        if catalogue.sources is not None and cursor is None:
            # Public identifiers of the other evidence routes (first page only).
            data.update(catalogue.sources.summaries())
        return HandlerOutcome(ok=True, data=data, next_cursor=next_cursor)

    def _citation_help(self, doc: Document) -> str:
        text = (
            f'Cite lines of the numbered text as {{"evidence_id": "{doc.doc_id}", '
            f'"locator": "L12"}} or "L12-L18" (1..{doc.line_count}).'
        )
        series = doc.timeseries
        if series is not None:
            text += (
                " Cite the time series as 'time:<ISO-8601 with offset>' or "
                f"'time:<start>/<end>' within {series.first.isoformat()} .. "
                f"{series.last.isoformat()}, or data rows as 'row:<n>' or "
                f"'rows:<a>-<b>' (1..{series.rows}, header excluded)."
            )
        text += (
            " In run_python the files are read-only at "
            "os.path.join(os.environ['EVIDENCE_DIR'], <path>)."
        )
        return text

    def _handle_request_document(
        self, state: EpisodeState, args: dict[str, Any], request_id: str
    ) -> HandlerOutcome:
        catalogue = self.catalogue
        if catalogue.is_v2:
            return self._handle_request_document_v2(state, args)
        if bad := self._unexpected(args, ("doc_id",)):
            return bad
        doc_id, bad = self._optional_str(args, "doc_id")
        if bad:
            return bad
        if doc_id is None:
            return _fail(
                "INVALID_ARGUMENT",
                "doc_id is required, e.g. one of: " + ", ".join(catalogue.ids()),
                [{"path": "doc_id", "message": "required"}],
            )
        doc = catalogue.get(doc_id)
        if doc is None:
            return _fail(
                "UNKNOWN_ID",
                f"no document has ID {doc_id!r}; valid IDs: {', '.join(catalogue.ids())}",
                [{"path": "doc_id", "message": "unknown ID", "valid": catalogue.ids()}],
            )
        return HandlerOutcome(
            ok=True,
            data=self._document_payload(doc, state),
            evidence_ids=[doc.doc_id],
        )

    def _document_payload(self, doc: Document, state: EpisodeState) -> dict[str, Any]:
        """Materialise ``doc``, record it as retrieved and describe it for the agent."""
        self._materialize(doc)
        if doc.doc_id not in state.retrieved:
            state.retrieved.append(doc.doc_id)
        artifacts = []
        for artifact in doc.artifacts:
            entry: dict[str, Any] = {
                "path": f"{doc.doc_id}/{artifact.name}",
                "media_type": artifact.media_type,
                "bytes": artifact.bytes,
                "sha256": artifact.sha256,
                "description": artifact.description,
            }
            if artifact.timeseries is not None:
                entry["timeseries"] = artifact.timeseries.to_dict()
            artifacts.append(entry)
        return {
            **doc.summary(),
            "text_file": f"{doc.doc_id}/{doc.text_artifact.name}",
            "line_count": doc.line_count,
            "artifacts": artifacts,
            "artifact_root": "EVIDENCE_DIR",
            "citation_help": self._citation_help(doc),
            "content": doc.text,
        }

    # -- manifest-v2 tools ---------------------------------------------------------
    def _required_str(
        self, args: Mapping[str, Any], name: str, what: str
    ) -> tuple[str | None, HandlerOutcome | None]:
        value, bad = self._optional_str(args, name)
        if bad:
            return None, bad
        if value is None:
            return None, _fail(
                "INVALID_ARGUMENT",
                f"{name} is required: {what}",
                [{"path": name, "message": "required"}],
            )
        return value, None

    def _bounded(self, name: str, value: str, limit: int) -> HandlerOutcome | None:
        if len(value) <= limit:
            return None
        return _fail(
            "INVALID_ARGUMENT",
            f"{name} is {len(value)} characters; the limit is {limit}",
            [{"path": name, "message": "too long"}],
        )

    def _window(
        self, args: Mapping[str, Any]
    ) -> tuple[datetime | None, datetime | None, HandlerOutcome | None]:
        instants: dict[str, datetime] = {}
        for name in ("start", "end"):
            text, bad = self._required_str(
                args,
                name,
                "an ISO-8601 time with an explicit UTC offset, e.g. "
                "2000-01-31T23:59:59+01:00 or 2000-01-31T22:59:59Z",
            )
            if bad:
                return None, None, bad
            assert text is not None
            try:
                instant = parse_iso_instant(text)
                # Every later comparison and conversion goes through UTC; an instant
                # whose UTC equivalent is outside year 1-9999 (e.g. 0001-01-01T00:00
                # +23:59) is refused here rather than failing inside a handler.
                instant.astimezone(UTC)
            except LocatorError as exc:
                return (
                    None,
                    None,
                    _fail(
                        "INVALID_ARGUMENT",
                        f"{name}: {exc}",
                        [{"path": name, "message": str(exc)}],
                    ),
                )
            except (OverflowError, ValueError):
                message = (
                    f"{name}: time out of range ({text!r} has no UTC equivalent "
                    "between years 1 and 9999)"
                )
                return (
                    None,
                    None,
                    _fail(
                        "INVALID_ARGUMENT",
                        message,
                        [{"path": name, "message": "time out of range"}],
                    ),
                )
            instants[name] = instant
        start, end = instants["start"], instants["end"]
        if start >= end:
            return (
                None,
                None,
                _fail(
                    "INVALID_ARGUMENT",
                    "end must be after start (the window includes start and excludes "
                    "end)",
                    [{"path": "end", "message": "not after start"}],
                ),
            )
        return start, end, None

    def _offset(
        self,
        args: Mapping[str, Any],
        tool: str,
        query: Mapping[str, Any],
        total: int,
        page_size: int,
    ) -> tuple[int, str, HandlerOutcome | None]:
        cursor, bad = self._optional_str(args, "cursor")
        digest = query_digest(query)
        if bad:
            return 0, digest, bad
        if cursor is None:
            return 0, digest, None
        try:
            offset = decode_cursor(
                cursor,
                tool,
                digest,
                self.catalogue.bundle_version,
                total,
                key=self.catalogue.bundle_sha256,
                page_size=page_size,
            )
        except CursorError as exc:
            return (
                0,
                digest,
                _fail(
                    "INVALID_ARGUMENT",
                    str(exc),
                    [{"path": "cursor", "message": str(exc)}],
                ),
            )
        return offset, digest, None

    def _handle_request_document_v2(
        self, state: EpisodeState, args: dict[str, Any]
    ) -> HandlerOutcome:
        if bad := self._unexpected(args, ("doc_id", "party", "description")):
            return bad
        values: dict[str, str | None] = {}
        for name in ("doc_id", "party", "description"):
            values[name], bad = self._optional_str(args, name)
            if bad:
                return bad
        doc_id, party, description = (
            values["doc_id"],
            values["party"],
            values["description"],
        )
        catalogue = self.catalogue
        listed = catalogue.listed_ids()
        if doc_id is not None and (party is not None or description is not None):
            return _fail(
                "INVALID_ARGUMENT",
                "give either doc_id, or party and description, not both",
                [{"path": "doc_id", "message": "combined with party/description"}],
            )
        if doc_id is not None:
            doc = catalogue.get(doc_id)
            if doc is None or not (
                catalogue.is_listed(doc_id) or doc_id in state.retrieved
            ):
                return _fail(
                    "UNKNOWN_ID",
                    f"no document has ID {doc_id!r}; valid IDs: {', '.join(listed)}",
                    [{"path": "doc_id", "message": "unknown ID", "valid": listed}],
                )
            return HandlerOutcome(
                ok=True,
                data=self._document_payload(doc, state),
                evidence_ids=[doc.doc_id],
            )
        if party is None or description is None:
            missing = "party" if party is None else "description"
            return _fail(
                "INVALID_ARGUMENT",
                "request a document either by doc_id (e.g. one of: "
                f"{', '.join(listed)}) or by party AND description; {missing} is "
                "missing",
                [{"path": missing, "message": "required"}],
            )
        for name, value in (("party", party), ("description", description)):
            if bad := self._bounded(name, value, self.config.max_request_chars):
                return bad
        sources = catalogue.sources
        assert sources is not None
        match = match_documents(
            party,
            description,
            [(d, *sources.match_text[d]) for d in listed],
        )
        matcher = {
            "matcher_version": match.version,
            "party_tokens": list(match.party_tokens),
            "description_tokens": list(match.description_tokens),
        }
        if match.selected is not None:
            doc = catalogue.get(match.selected)
            assert doc is not None
            chosen = match.candidates[0]
            payload = self._document_payload(doc, state)
            payload["matched_by"] = {
                **matcher,
                "party": party,
                "description": description,
                "description_score": chosen.description_score,
                "party_score": chosen.party_score,
            }
            return HandlerOutcome(ok=True, data=payload, evidence_ids=[doc.doc_id])
        if match.ambiguous:
            candidates = []
            for candidate in match.candidates:
                found = catalogue.get(candidate.doc_id)
                assert found is not None
                candidates.append(
                    {
                        **found.summary(),
                        "description_score": candidate.description_score,
                        "party_score": candidate.party_score,
                    }
                )
            ids = ", ".join(c["doc_id"] for c in candidates)
            return _fail(
                "AMBIGUOUS_REQUEST",
                f"the request matches {len(candidates)} documents equally ({ids}; "
                f"matcher {match.version}); nothing was retrieved. Request one of them "
                "by doc_id, or describe the document more specifically.",
                candidates,
            )
        return _fail(
            "UNKNOWN_ID",
            "no listed document matches that party and description "
            f"(matcher {match.version}: at least one party word must match a "
            "document's owner, and its ID, title or keywords must contain at least "
            f"{min_description_coverage(match.description_tokens)} of the "
            f"{len(match.description_tokens)} description words). Use "
            "list_documents to see the catalogue; asset logs, control-room logs, "
            "witnesses and data returns have their own tools.",
            [{"path": "description", "message": "no matching document", **matcher}],
        )

    def _sources(self) -> Any:
        sources = self.catalogue.sources
        assert sources is not None, "manifest-v2 tool called on a v1 bundle"
        return sources

    def _handle_query_frequency(
        self, state: EpisodeState, args: dict[str, Any], request_id: str
    ) -> HandlerOutcome:
        if bad := self._unexpected(args, ("start", "end", "resolution_s", "cursor")):
            return bad
        resolution = args.get("resolution_s", 1)
        if (
            isinstance(resolution, bool)
            or not isinstance(resolution, (int, float))
            or resolution != 1
        ):
            return _fail(
                "INVALID_ARGUMENT",
                "resolution_s must be 1: the record is served at its native 1-second "
                "sampling, without resampling, smoothing or interpolation",
                [{"path": "resolution_s", "message": "must be 1"}],
            )
        start, end, bad = self._window(args)
        if bad:
            return bad
        assert start is not None and end is not None
        catalogue = self.catalogue
        series = self._sources().frequency
        if end <= series.first or start >= series.coverage_end:
            return _fail(
                "OUT_OF_RANGE",
                f"the window {start.isoformat()} <= time < {end.isoformat()} lies outside "
                f"the frequency record, which has samples from {series.stamps[0]} to "
                f"{series.stamps[-1]} every {series.interval_s:g} s",
                [
                    {
                        "path": "start",
                        "message": "outside the record",
                        "first": series.stamps[0],
                        "last": series.stamps[-1],
                    }
                ],
            )
        lo, hi = series.window(start, end)
        total = hi - lo
        query = {
            "start": start.astimezone(UTC).isoformat(),
            "end": end.astimezone(UTC).isoformat(),
            "resolution_s": 1,
        }
        size = self.config.frequency_page_size
        offset, digest, bad = self._offset(args, "query_frequency", query, total, size)
        if bad:
            return bad
        first = lo + offset
        last = min(hi, first + size)
        rows = [[i + 1, series.stamps[i], series.values[i]] for i in range(first, last)]
        next_cursor = (
            encode_cursor(
                "query_frequency",
                digest,
                last - lo,
                catalogue.bundle_version,
                key=catalogue.bundle_sha256,
            )
            if last < hi
            else None
        )
        doc = catalogue.get(series.doc_id)
        assert doc is not None
        self._materialize(doc)
        if doc.doc_id not in state.retrieved:
            state.retrieved.append(doc.doc_id)
        return HandlerOutcome(
            ok=True,
            data={
                "doc_id": doc.doc_id,
                "title": doc.title,
                "window": {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "rule": "start inclusive, end exclusive",
                },
                "resolution_s": 1,
                "unit": series.unit,
                "columns": ["row", series.time_column, series.value_column],
                "rows": rows,
                "total_rows": total,
                "offset": offset,
                "returned": len(rows),
                "page_size": size,
                "series": {
                    "first": series.stamps[0],
                    "last": series.stamps[-1],
                    "rows": len(series),
                    "interval_s": series.interval_s,
                    "gaps": series.gaps,
                },
                "artifact_path": f"{doc.doc_id}/{series.artifact_name}",
                "artifact_root": "EVIDENCE_DIR",
                "citation_help": (
                    f'Cite samples as {{"evidence_id": "{doc.doc_id}", "locator": '
                    '"time:<ISO-8601 with offset>"} or "time:<start>/<end>", or by the '
                    "row column as 'row:<n>' or 'rows:<a>-<b>'. The whole series is "
                    "also available read-only to run_python at "
                    f"os.path.join(os.environ['EVIDENCE_DIR'], '{doc.doc_id}', "
                    f"'{series.artifact_name}')."
                ),
            },
            evidence_ids=[doc.doc_id],
            next_cursor=next_cursor,
        )

    def _query_log(
        self,
        args: dict[str, Any],
        *,
        tool: str,
        id_arg: str,
        logs: Mapping[str, Any],
        what: str,
        with_signal: bool,
    ) -> HandlerOutcome:
        allowed = (id_arg, "start", "end", *(("signal",) if with_signal else ()))
        if bad := self._unexpected(args, (*allowed, "cursor")):
            return bad
        valid = list(logs)
        log_id, bad = self._required_str(args, id_arg, f"one of: {', '.join(valid)}")
        if bad:
            return bad
        log = logs.get(log_id)
        if log is None:
            return _fail(
                "UNKNOWN_ID",
                f"no {what} has ID {log_id!r}; valid IDs: {', '.join(valid)}",
                [{"path": id_arg, "message": "unknown ID", "valid": valid}],
            )
        start, end, bad = self._window(args)
        if bad:
            return bad
        assert start is not None and end is not None
        signal = None
        if with_signal:
            asked, bad = self._optional_str(args, "signal")
            if bad:
                return bad
            if asked is not None:
                signal = log.resolve_signal(asked)
                if signal is None:
                    return _fail(
                        "UNKNOWN_ID",
                        f"asset {log_id} has no signal {asked!r}; its signals: "
                        f"{', '.join(log.signals)}",
                        [
                            {
                                "path": "signal",
                                "message": "unknown signal",
                                "valid": list(log.signals),
                            }
                        ],
                    )
        selected = select_rows(log.rows, start, end, signal)
        query = {
            id_arg: log_id,
            "start": start.astimezone(UTC).isoformat(),
            "end": end.astimezone(UTC).isoformat(),
            "signal": signal,
        }
        size = self.config.log_page_size
        offset, digest, bad = self._offset(args, tool, query, len(selected), size)
        if bad:
            return bad
        page = selected[offset : offset + size]
        end_offset = offset + len(page)
        next_cursor = (
            encode_cursor(
                tool,
                digest,
                end_offset,
                self.catalogue.bundle_version,
                key=self.catalogue.bundle_sha256,
            )
            if end_offset < len(selected)
            else None
        )
        kind, ident = ("event", "event_id") if with_signal else ("entry", "entry_id")
        coverage = (
            {
                "first_index_time_utc": log.rows[0].raw["index_time_utc"],
                "last_index_time_utc": log.rows[-1].raw["index_time_utc"],
                "rows": len(log.rows),
            }
            if log.rows
            else {"first_index_time_utc": None, "last_index_time_utc": None, "rows": 0}
        )
        data: dict[str, Any] = {
            id_arg: log_id,
            "title": log.title,
            "owner": log.owner,
            "status": log.status,
            "source_note": log.source_note,
            "clock_note": log.clock_note,
            "evidence_ids": list(log.evidence_ids),
        }
        if with_signal:
            data["signals"] = list(log.signals)
            data["signal"] = signal
        data.update(
            {
                "window": {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "rule": "index_time_utc >= start and < end",
                },
                "columns": list(ASSET_COLUMNS if with_signal else CONTROL_COLUMNS),
                "rows": [row.to_dict() for row in page],
                "total_rows": len(selected),
                "offset": offset,
                "returned": len(page),
                "page_size": size,
                "log_coverage": coverage,
                "selection_note": (
                    "recorded_time and clock_basis are the record's own time; "
                    "index_time_utc is a conversion used only to select rows, with "
                    "the stated uncertainty in seconds"
                ),
                "citation_help": (
                    f'Cite a row as {{"evidence_id": "<the row\'s evidence_id>", '
                    f'"locator": "{kind}:<{ident}>"}}.'
                ),
            }
        )
        return HandlerOutcome(
            ok=True,
            data=data,
            evidence_ids=sorted({row.evidence_id for row in page}),
            next_cursor=next_cursor,
        )

    def _handle_query_asset_log(
        self, state: EpisodeState, args: dict[str, Any], request_id: str
    ) -> HandlerOutcome:
        return self._query_log(
            args,
            tool="query_asset_log",
            id_arg="asset_id",
            logs=self._sources().asset_logs,
            what="asset log",
            with_signal=True,
        )

    def _handle_query_control_log(
        self, state: EpisodeState, args: dict[str, Any], request_id: str
    ) -> HandlerOutcome:
        return self._query_log(
            args,
            tool="query_control_log",
            id_arg="room",
            logs=self._sources().control_logs,
            what="control room",
            with_signal=False,
        )

    def _handle_interview_witness(
        self, state: EpisodeState, args: dict[str, Any], request_id: str
    ) -> HandlerOutcome:
        if bad := self._unexpected(args, ("persona_id", "question")):
            return bad
        witnesses = self._sources().witnesses
        valid = list(witnesses)
        persona_id, bad = self._required_str(
            args, "persona_id", f"one of: {', '.join(valid)}"
        )
        if bad:
            return bad
        card = witnesses.get(persona_id)
        if card is None:
            return _fail(
                "UNKNOWN_ID",
                f"no witness has persona_id {persona_id!r}; valid IDs: {', '.join(valid)}",
                [{"path": "persona_id", "message": "unknown ID", "valid": valid}],
            )
        question, bad = self._required_str(
            args, "question", "the question to put to the witness, as plain text"
        )
        if bad:
            return bad
        assert question is not None
        if bad := self._bounded("question", question, self.config.max_question_chars):
            return bad
        match = card.interview(question)
        base: dict[str, Any] = {**card.summary(), "matcher_version": match.version}
        if match.kind == "ambiguous":
            choices = [{"topics": list(card.blocks[i].topics)} for i in match.blocks]
            listing = " | ".join("; ".join(c["topics"]) for c in choices)
            more = (
                f" ({match.withheld} more equally close; ask more specifically)"
                if match.withheld
                else ""
            )
            return _fail(
                "AMBIGUOUS_REQUEST",
                "the question does not match exactly one of this witness's topics "
                f"(matcher {match.version}); nothing was answered. Ask about one "
                f"topic, for example by naming it: {listing}{more}",
                choices,
            )
        if match.kind == "match":
            block = card.blocks[match.blocks[0]]
            base.update(
                matched=True,
                response_id=block.response_id,
                topics=list(block.topics),
                status=card.status,
                response_text=block.response_text,
                citation_help=(
                    f'Cite this response as {{"evidence_id": "{card.evidence_id}", '
                    f'"locator": "response:{block.response_id}"}}.'
                ),
            )
            return HandlerOutcome(ok=True, data=base, evidence_ids=[card.evidence_id])
        base.update(
            matched=False,
            response_id=None,
            topics=[],
            status=None,
            response_text=card.unknown_response,
            citation_help="The witness's fixed answer outside their fact card; not citable.",
        )
        return HandlerOutcome(ok=True, data=base, evidence_ids=[])

    def _handle_request_data_return(
        self, state: EpisodeState, args: dict[str, Any], request_id: str
    ) -> HandlerOutcome:
        if bad := self._unexpected(args, ("party", "data_type")):
            return bad
        registry = self._sources().data_returns
        pairs = registry.summaries()
        party, bad = self._required_str(
            args, "party", "the party holding the data, as listed by list_documents"
        )
        if bad:
            return bad
        data_type, bad = self._required_str(
            args, "data_type", "the type of data return, as listed by list_documents"
        )
        if bad:
            return bad
        assert party is not None and data_type is not None
        for name, value in (("party", party), ("data_type", data_type)):
            if bad := self._bounded(name, value, self.config.max_request_chars):
                return bad
        entry = registry.lookup(party, data_type)
        if entry is None:
            types = registry.data_types_for(party)
            if types:
                message = (
                    f"{party!r} has no data return of type {data_type!r}; its data "
                    f"types: {', '.join(types)}"
                )
            else:
                message = (
                    f"no data return is registered for party {party!r}; registered "
                    f"(party / data_type): {registry.pairs_text(pairs)}"
                )
            return _fail(
                "UNKNOWN_ID",
                message,
                [{"path": "data_type" if types else "party", "valid": pairs}],
            )
        if entry.status in ("not_held", "refused"):
            return _fail(
                "NOT_HELD" if entry.status == "not_held" else "REFUSED",
                f"{entry.party} / {entry.data_type}: {entry.message}",
                [
                    {
                        "party": entry.party,
                        "data_type": entry.data_type,
                        "status": entry.status,
                    }
                ],
            )
        doc = self.catalogue.get(str(entry.evidence_id))
        assert doc is not None
        payload = self._document_payload(doc, state)
        payload.update(
            party=entry.party,
            data_type=entry.data_type,
            return_status=entry.status,
            message=entry.message,
        )
        return HandlerOutcome(ok=True, data=payload, evidence_ids=[doc.doc_id])

    def _materialize(self, doc: Document) -> None:
        """Place ``doc``'s artifacts in ``evidence_dir/<doc_id>/`` atomically and
        idempotently, re-verifying every hash (fails closed)."""
        evidence_root = Path(self.config.evidence_dir)
        container = self._container_mode
        dir_mode = 0o555 if container else 0o755
        root_fd = os.open(evidence_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if self._materialized_ok(root_fd, doc):
                return
            contents = {a.name: self.catalogue.read_artifact(a) for a in doc.artifacts}
            tmp_name = f".tmp-{doc.doc_id}-{secrets.token_hex(6)}"
            os.mkdir(tmp_name, 0o700, dir_fd=root_fd)
            tmp_fd = os.open(
                tmp_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd
            )
            try:
                for name, data in contents.items():
                    fd = os.open(
                        name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=tmp_fd,
                    )
                    try:
                        view = memoryview(data)
                        while view:
                            view = view[os.write(fd, view) :]
                        os.fsync(fd)
                        if container:
                            os.fchown(fd, 0, 0)
                        os.fchmod(fd, 0o444)
                    finally:
                        os.close(fd)
                if container:
                    os.fchown(tmp_fd, 0, 0)
                os.fchmod(tmp_fd, dir_mode)
            finally:
                os.close(tmp_fd)
            trash = None
            try:
                os.stat(doc.doc_id, dir_fd=root_fd, follow_symlinks=False)
                trash = f".trash-{doc.doc_id}-{secrets.token_hex(6)}"
                os.rename(doc.doc_id, trash, src_dir_fd=root_fd, dst_dir_fd=root_fd)
            except FileNotFoundError:
                pass
            os.rename(tmp_name, doc.doc_id, src_dir_fd=root_fd, dst_dir_fd=root_fd)
            if trash is not None:
                remove_tree(evidence_root / trash)
        finally:
            os.close(root_fd)

    def _materialized_ok(self, root_fd: int, doc: Document) -> bool:
        try:
            dir_fd = os.open(
                doc.doc_id, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd
            )
        except OSError:
            return False
        try:
            expected = {a.name: a.sha256 for a in doc.artifacts}
            if sorted(os.listdir(dir_fd)) != sorted(expected):
                return False
            for name, digest in expected.items():
                try:
                    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd)
                except OSError:
                    return False
                try:
                    info = os.fstat(fd)
                    if (
                        not stat.S_ISREG(info.st_mode)
                        or stat.S_IMODE(info.st_mode) != 0o444
                    ):
                        return False
                    hasher = hashlib.sha256()
                    while chunk := os.read(fd, 1 << 20):
                        hasher.update(chunk)
                    if hasher.hexdigest() != digest:
                        return False
                finally:
                    os.close(fd)
            return True
        finally:
            os.close(dir_fd)

    def python_runner(self) -> PythonRunner:
        return PythonRunner(
            python_executable=self.config.python_executable,
            evidence_dir=Path(self.config.evidence_dir),
            scratch_dir=Path(self.config.scratch_dir),
            timeout_s=self.config.python_timeout_s,
            memory_bytes=self.config.python_memory_bytes,
            file_size_bytes=self.config.python_file_size_bytes,
            max_output_chars=self.config.max_output_chars,
            launcher=self.launcher,
            cleanup=self.cleanup,
            isolated=self.isolated,
            network_mode=self.network_mode,
        )

    def _handle_run_python(
        self, state: EpisodeState, args: dict[str, Any], request_id: str
    ) -> HandlerOutcome:
        if bad := self._unexpected(args, ("code",)):
            return bad
        code = args.get("code")
        if code is not None and not isinstance(code, str):
            return _fail(
                "INVALID_ARGUMENT",
                "code must be a string of Python source",
                [{"path": "code", "message": "must be a string"}],
            )
        if code is None or not code.strip():
            return _fail(
                "INVALID_ARGUMENT",
                "code is required: a non-empty string of Python source",
                [{"path": "code", "message": "required"}],
            )
        if len(code) > self.config.max_code_chars:
            return _fail(
                "INVALID_ARGUMENT",
                f"code is {len(code)} characters; the limit is {self.config.max_code_chars}",
                [{"path": "code", "message": "too long"}],
            )
        state.python_calls += 1
        # After a failed cleanup, kill leftovers before touching scratch again.
        result = self.python_runner().run(code, precleanup=state.cleanup_failures > 0)
        if result.cleanup_error is not None:
            state.cleanup_failures += 1
        data: dict[str, Any] = {
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "stdout_truncated": result.stdout_truncated,
            "stderr_truncated": result.stderr_truncated,
            "files": result.files,
            "files_truncated": result.files_truncated,
            "limits": result.limits,
        }
        if result.notes:
            data["notes"] = result.notes
        error = (
            None
            if result.ok
            else error_obj(
                result.error_code or "INTERNAL_ERROR", result.error_message or ""
            )
        )
        return HandlerOutcome(
            ok=result.ok,
            data=data,
            error=error,
            deterministic=False,
            python={
                "code": code,
                "code_sha256": sha256_text(code),
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "stdout_bytes": result.stdout_bytes,
                "stderr_bytes": result.stderr_bytes,
                "duration_s": result.duration_s,
                "files": result.files,
                "notes": result.notes,
                "cleanup_error": result.cleanup_error,
            },
        )

    def _handle_submit_findings(
        self, state: EpisodeState, args: dict[str, Any], request_id: str
    ) -> HandlerOutcome:
        if bad := self._unexpected(args, ("submission",)):
            state.invalid_submission_attempts += 1
            return bad
        raw = args.get("submission")
        if raw is None:
            state.invalid_submission_attempts += 1
            return _fail(
                "INVALID_ARGUMENT",
                "submission is required: a v3 submission object (or its JSON text)",
                [{"path": "submission", "message": "required"}],
            )
        result = validate_submission(
            raw,
            self.catalogue,
            word_limit=self.config.exec_summary_word_limit,
            variant_id=self.config.variant_id,
        )
        if not result.ok:
            state.invalid_submission_attempts += 1
            remaining = max(0, self.config.max_tool_calls - state.calls_used)
            return _fail(
                "VALIDATION_FAILED",
                f"Submission rejected with {len(result.errors)} problem(s); nothing was "
                "frozen. Fix every problem listed in details and call submit_findings "
                f"again ({remaining} tool calls remain).",
                result.errors,
            )
        assert result.canonical_json is not None and result.submission is not None
        _atomic_write(self.submission_path, result.canonical_json.encode("utf-8"))
        state.frozen = True
        state.frozen_at_request_id = request_id
        state.submission_sha256 = result.sha256
        cited = sorted(
            {c.evidence_id for f in result.submission.findings for c in f.citations}
        )
        return HandlerOutcome(
            ok=True,
            data={
                "status": "accepted_and_frozen",
                "submission_sha256": result.sha256,
                "findings_count": result.findings_count,
                "message": ACCEPTED_MESSAGE,
            },
            evidence_ids=cited,
        )


def _tool_names_for(catalogue: Any) -> tuple[str, ...]:
    return (
        SYSTEM_RESPONSE_TOOL_NAMES
        if getattr(catalogue, "sources", None) is not None
        else TOOL_NAMES
    )


# -- transcript summary & outcome (pure; used by the judge and the CLI) --------
def _message_has_text(message: Mapping[str, Any]) -> bool:
    content = message.get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(
            isinstance(part, Mapping)
            and part.get("type") == "text"
            and str(part.get("text") or "").strip()
            for part in content
        )
    return False


def _result_request_id(result: Mapping[str, Any]) -> str | None:
    structured = result.get("structuredContent") or result.get("structured_content")
    if isinstance(structured, Mapping):
        value = structured.get("request_id")
        return value if isinstance(value, str) else None
    return None


def summarize_transcript(
    events: Iterable[Mapping[str, Any]],
    *,
    frozen_at_request_id: str | None = None,
    tool_names: Iterable[str] = TOOL_NAMES,
) -> dict[str, Any]:
    """Summarise transcript events given as JSON dicts (``Transcript.model_dump``)."""
    names = set(tool_names)
    calls_by_tool: Counter[str] = Counter()
    output_tokens = 0
    output_before_freeze: int | None = None
    input_tokens: list[int] = []
    estimated = False
    last_message: Mapping[str, Any] | None = None
    assistant_turns = 0
    for event in events:
        kind = event.get("type")
        if kind == "tool_call_started":
            call = event.get("tool_call") or {}
            name = (call.get("function") or {}).get("name") or "?"
            calls_by_tool[str(name)] += 1
        elif kind == "token_usage":
            output_tokens += int(event.get("output_tokens") or 0)
            input_tokens.append(int(event.get("input_tokens") or 0))
            estimated = estimated or bool(event.get("estimated"))
        elif kind == "message_added":
            message = event.get("message") or {}
            if message.get("role") in ("assistant", "user", "tool"):
                last_message = message
            if message.get("role") == "assistant":
                assistant_turns += 1
        elif kind == "tool_call_completed" and frozen_at_request_id is not None:
            result = event.get("result") or {}
            if (
                output_before_freeze is None
                and _result_request_id(result) == frozen_at_request_id
            ):
                output_before_freeze = output_tokens
    ended_with_final = bool(
        last_message is not None
        and last_message.get("role") == "assistant"
        and not last_message.get("tool_calls")
    )
    final_text = None
    if ended_with_final and last_message is not None:
        content = last_message.get("content")
        if isinstance(content, str):
            final_text = content[:2000]
        elif isinstance(content, list):
            final_text = "\n".join(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, Mapping) and part.get("type") == "text"
            )[:2000]
    return {
        "tool_calls_total": sum(calls_by_tool.values()),
        "tool_calls_episode_tools": sum(
            n for t, n in calls_by_tool.items() if t in names
        ),
        "tool_calls_by_tool": dict(sorted(calls_by_tool.items())),
        "output_tokens_total": output_tokens,
        "output_tokens_before_freeze": output_before_freeze,
        "last_input_tokens": input_tokens[-1] if input_tokens else None,
        "max_input_tokens": max(input_tokens) if input_tokens else None,
        "token_usage_events": len(input_tokens),
        "token_counts_estimated": estimated,
        "assistant_turns": assistant_turns,
        "ended_with_final_message": ended_with_final,
        "final_message_has_text": bool(
            ended_with_final
            and last_message is not None
            and _message_has_text(last_message)
        ),
        "final_message_excerpt": final_text,
    }


def classify_outcome(
    state: EpisodeState | None,
    summary: Mapping[str, Any],
    *,
    max_tool_calls: int,
    submission_valid: bool,
    output_token_budget: int = OUTPUT_TOKEN_BUDGET,
    context_cap: int = CONTEXT_CAP_TOKENS,
    transcript_available: bool = True,
) -> tuple[str, str | None, list[str]]:
    """``("complete", None, [])`` or ``("incomplete_submission", reason, reasons)``.

    ``complete`` needs a valid frozen submission made within the output-token budget.
    Reasons, in priority order: tool_budget_exhausted, context_cap_reached,
    output_token_budget_exhausted, final_message_without_submission, time_limit.
    Without a transcript the last two cannot be told apart and
    ``unknown_without_transcript`` is reported instead.
    """
    frozen = bool(state and state.frozen and submission_valid)
    if frozen:
        spent = summary.get("output_tokens_before_freeze")
        if spent is None:
            spent = summary.get("output_tokens_total") or 0
        if spent <= output_token_budget:
            return "complete", None, []
        return (
            "incomplete_submission",
            "output_token_budget_exhausted",
            ["output_token_budget_exhausted"],
        )
    reasons: list[str] = []
    if state is not None and (
        state.budget_exhausted or state.calls_used >= max_tool_calls
    ):
        reasons.append("tool_budget_exhausted")
    last_input = summary.get("last_input_tokens")
    context_hit = last_input is not None and last_input >= context_cap
    if context_hit:
        reasons.append("context_cap_reached")
    if (summary.get("output_tokens_total") or 0) > output_token_budget:
        reasons.append("output_token_budget_exhausted")
    if not transcript_available:
        if not reasons:
            reasons.append("unknown_without_transcript")
    elif summary.get("ended_with_final_message"):
        reasons.append("final_message_without_submission")
    elif not context_hit:
        # The step ended without a final assistant message and not at the context
        # cap: Karotte's step time limit stopped it.
        reasons.append("time_limit")
    return "incomplete_submission", reasons[0], reasons


def read_config_snapshot(episode_dir: Path) -> dict[str, Any] | None:
    path = Path(episode_dir) / CONFIG_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EpisodeError(f"cannot read {path}: {exc}") from None


def submission_is_valid(episode_dir: Path, state: EpisodeState | None) -> bool:
    """A frozen ``submission.json`` exists and matches the sha256 in the state."""
    if state is None or not state.frozen or not state.submission_sha256:
        return False
    path = Path(episode_dir) / SUBMISSION_FILE
    try:
        data = path.read_bytes()
    except OSError:
        return False
    return hashlib.sha256(data).hexdigest() == state.submission_sha256


def build_transcript_summary(
    episode_dir: Path,
    events: Iterable[Mapping[str, Any]] | None,
    *,
    max_tool_calls: int | None = None,
    output_token_budget: int = OUTPUT_TOKEN_BUDGET,
    context_cap: int = CONTEXT_CAP_TOKENS,
    tool_names: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Outcome, budgets and ledger/transcript figures for one episode.

    This is the ``transcript_summary`` the judge hands to grading. ``events`` are
    transcript events as JSON dicts, or ``None`` when no transcript is available.
    ``tool_names`` (the episode's tools) defaults to those recorded in the episode's
    config snapshot, else the four MVP tools.
    """
    episode_dir = Path(episode_dir)
    state = read_state(episode_dir)
    snapshot = read_config_snapshot(episode_dir) or {}
    if max_tool_calls is None:
        max_tool_calls = int((snapshot.get("config") or {}).get("max_tool_calls") or 50)
    if tool_names is None:
        recorded = snapshot.get("tool_names")
        tool_names = (
            [str(name) for name in recorded]
            if isinstance(recorded, list) and recorded
            else TOOL_NAMES
        )
    event_list = list(events) if events is not None else []
    summary = summarize_transcript(
        event_list,
        frozen_at_request_id=state.frozen_at_request_id if state else None,
        tool_names=tool_names,
    )
    valid = submission_is_valid(episode_dir, state)
    outcome, reason, reasons = classify_outcome(
        state,
        summary,
        max_tool_calls=max_tool_calls,
        submission_valid=valid,
        output_token_budget=output_token_budget,
        context_cap=context_cap,
        transcript_available=events is not None,
    )
    ledger_recorded = state.seq if state else 0
    summary.update(
        outcome=outcome,
        incomplete_reason=reason,
        incomplete_reasons=reasons,
        submission_valid=valid,
        transcript_available=events is not None,
        budgets={
            "tool_calls_limit": max_tool_calls,
            "output_token_budget": output_token_budget,
            "context_cap_tokens": context_cap,
        },
        ledger=state.to_dict() if state else None,
        ledger_discrepancy={
            "transcript_tool_calls": summary["tool_calls_episode_tools"],
            "ledger_recorded_calls": ledger_recorded,
            "difference": summary["tool_calls_episode_tools"] - ledger_recorded,
            "note": (
                "calls in the transcript that never reached the ledger (e.g. malformed "
                "JSON arguments or an argument name the tool does not accept, which "
                "the MCP layer rejects before the ledger sees the call)"
                if events is not None
                else "no transcript available"
            ),
        },
        isolation={
            "isolated": snapshot.get("isolated"),
            "network_mode": snapshot.get("network_mode"),
            "python_cleanup_failures": state.cleanup_failures if state else 0,
        },
        output_token_budget_exceeded=summary["output_tokens_total"]
        > output_token_budget,
        context_cap_reached=(summary["last_input_tokens"] or 0) >= context_cap,
        bundle_version=snapshot.get("bundle_version"),
        bundle_sha256=snapshot.get("bundle_sha256"),
    )
    return summary
