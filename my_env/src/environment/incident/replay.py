"""Replay a recorded episode trace against an evidence bundle.

The replay builds a fresh temporary episode with the recorded configuration (budgets,
variant, limits) and the given bundle, then re-issues every recorded call in order
through the same ledger:

* deterministic calls (``list_documents``, ``request_document``, ``submit_findings``,
  refusals and invalid calls) are re-executed and their ``rendered_text_sha256`` is
  compared with the recording — any difference is a mismatch;
* executed ``run_python`` calls are reported as ``recorded``: by default the recorded
  outcome is fed back through the ledger (so budgets and request IDs stay in step);
  with ``rerun_python=True`` the code is executed again and the result is reported as
  ``rerun_match`` or ``rerun_differs`` (informational only).

Every record is also checked for integrity: its stored hash must equal the hash of the
rendering of its stored envelope. Finally the replayed state and frozen submission are
compared with the recorded ones.
"""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from environment.incident.episode import (
    CONFIG_FILE,
    SUBMISSION_FILE,
    Episode,
    EpisodeConfig,
    EpisodeState,
    HandlerOutcome,
    read_state,
    read_trace,
    render,
    sha256_text,
)
from environment.incident.paths import (
    BUNDLES_DIR,
    DEFAULT_BUNDLE_DIR,
    PACKAGE_DIR,
    SYSTEM_RESPONSE_BUNDLE_DIR,
)

__all__ = [
    "ReplayItem",
    "ReplayReport",
    "replay_episode",
    "replay_records",
    "resolve_recorded_bundle",
]

_STATE_FIELDS = (
    "calls_used",
    "seq",
    "retrieved",
    "frozen",
    "frozen_at_request_id",
    "submission_sha256",
    "budget_exhausted",
    "invalid_submission_attempts",
    "python_calls",
    "cleanup_failures",
)


@dataclass
class ReplayItem:
    seq: int
    request_id: str
    tool: str
    outcome_code: str
    status: str
    recorded_sha256: str
    replayed_sha256: str | None
    integrity_ok: bool
    note: str = ""


@dataclass
class ReplayReport:
    ok: bool
    items: list[ReplayItem] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    replayed_state: dict[str, Any] | None = None

    @property
    def mismatches(self) -> list[ReplayItem]:
        return [i for i in self.items if i.status == "mismatch" or not i.integrity_ok]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "items": [asdict(item) for item in self.items],
            "problems": list(self.problems),
            "replayed_state": self.replayed_state,
            "counts": self.counts(),
        }

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.status] = counts.get(item.status, 0) + 1
        return counts

    def summary_text(self) -> str:
        lines = [
            f"replay {'OK' if self.ok else 'FAILED'}: "
            + ", ".join(f"{k}={v}" for k, v in sorted(self.counts().items()))
        ]
        for item in self.items:
            flag = "" if item.integrity_ok else "  [integrity check failed]"
            note = f"  ({item.note})" if item.note else ""
            lines.append(
                f"  {item.request_id} {item.tool:<17} {item.outcome_code:<18} "
                f"{item.status}{flag}{note}"
            )
        lines.extend(f"  problem: {p}" for p in self.problems)
        return "\n".join(lines)


def _recorded_python_handler(record: dict[str, Any]):
    envelope = record["envelope"]

    def handler(
        state: EpisodeState, args: dict[str, Any], request_id: str
    ) -> HandlerOutcome:
        state.python_calls += 1
        if (record.get("python") or {}).get("cleanup_error"):
            state.cleanup_failures += 1
        return HandlerOutcome(
            ok=bool(envelope["ok"]),
            data=envelope.get("data") or {},
            error=envelope.get("error"),
            evidence_ids=list(envelope.get("evidence_ids") or []),
            next_cursor=envelope.get("next_cursor"),
            deterministic=False,
            python=record.get("python"),
        )

    return handler


def _installed_bundles() -> list[Path]:
    """Bundle directories shipped with this package (system response first, MVP last)."""
    found = [SYSTEM_RESPONSE_BUNDLE_DIR]
    if BUNDLES_DIR.is_dir():
        found += sorted(p for p in BUNDLES_DIR.iterdir() if p.is_dir())
    found.append(DEFAULT_BUNDLE_DIR)
    return list(dict.fromkeys(found))


def _bundle_sha256(bundle: Path) -> str | None:
    from environment.incident.catalogue import Catalogue, CatalogueError

    try:
        return Catalogue.load(bundle).bundle_sha256
    except (CatalogueError, OSError, ValueError):
        return None


def resolve_recorded_bundle(recorded: str | None, recorded_sha256: str | None) -> Path:
    """The bundle to replay against when ``--bundle`` is not given.

    1. the recorded ``bundle_dir`` if it exists here;
    2. otherwise its package-relative tail (``.../environment/incident/<tail>``, e.g. a
       container path under ``/root/.venv``) mapped onto this installation;
    3. otherwise the installed bundle whose ``bundle_sha256`` equals the recorded one;
    4. otherwise the MVP bundle (the replay then reports the bundle difference).
    """
    if recorded:
        path = Path(recorded)
        if path.is_dir():
            return path
        parts = path.parts
        for index in range(len(parts) - 1, 0, -1):
            if parts[index - 1 : index + 1] == ("environment", "incident"):
                tail = Path(*parts[index + 1 :]) if index + 1 < len(parts) else None
                mapped = PACKAGE_DIR / tail if tail is not None else None
                if mapped is not None and mapped.is_dir():
                    if recorded_sha256 is None or (
                        _bundle_sha256(mapped) == recorded_sha256
                    ):
                        return mapped
                break
    if recorded_sha256:
        for candidate in _installed_bundles():
            if candidate.is_dir() and _bundle_sha256(candidate) == recorded_sha256:
                return candidate
    return DEFAULT_BUNDLE_DIR


def _replay_config(
    snapshot: dict[str, Any] | None,
    base: Path,
    bundle_dir: Path | None,
    python_executable: str | None,
) -> EpisodeConfig:
    recorded = dict((snapshot or {}).get("config") or {})
    values = {k: v for k, v in recorded.items() if k in EpisodeConfig.model_fields}
    if bundle_dir is None:
        bundle_dir = resolve_recorded_bundle(
            values.get("bundle_dir"), (snapshot or {}).get("bundle_sha256")
        )
    values.update(
        episode_dir=base / "episode",
        evidence_dir=base / "evidence",
        scratch_dir=base / "scratch",
        bundle_dir=bundle_dir,
        student_uid=None,
        python_executable=python_executable or sys.executable,
    )
    return EpisodeConfig(**values)


def replay_records(
    records: list[dict[str, Any]],
    *,
    snapshot: dict[str, Any] | None = None,
    recorded_state: EpisodeState | None = None,
    recorded_submission: bytes | None = None,
    bundle_dir: Path | None = None,
    rerun_python: bool = False,
    python_executable: str | None = None,
    work_dir: Path | None = None,
) -> ReplayReport:
    """Replay ``records`` (trace.jsonl entries) in a fresh temporary episode."""
    report = ReplayReport(ok=True)
    with tempfile.TemporaryDirectory(prefix="incident-replay-", dir=work_dir) as tmp:
        config = _replay_config(snapshot, Path(tmp), bundle_dir, python_executable)
        episode = Episode(config)
        metadata = episode.reset()
        recorded_bundle = (snapshot or {}).get("bundle_sha256")
        if recorded_bundle and recorded_bundle != metadata["bundle_sha256"]:
            report.problems.append(
                f"bundle differs from the recorded one (recorded {recorded_bundle[:12]}..., "
                f"replay {metadata['bundle_sha256'][:12]}...)"
            )
        for expected_seq, record in enumerate(records, 1):
            envelope = record.get("envelope") or {}
            recorded_sha = str(record.get("rendered_text_sha256", ""))
            integrity_ok = sha256_text(render(envelope)) == recorded_sha
            if record.get("seq") != expected_seq:
                report.problems.append(
                    f"trace record {expected_seq} has seq {record.get('seq')!r}"
                )
            tool = str(record.get("tool"))
            args = record.get("args") or {}
            outcome_code = str(record.get("outcome_code", "?"))
            handler = None
            forced = None
            executed_python = tool == "run_python" and not record.get(
                "deterministic", True
            )
            if outcome_code == "INTERNAL_ERROR" and not record.get("counted"):
                forced = envelope.get("error")
            elif executed_python and not rerun_python:
                handler = _recorded_python_handler(record)
            result = episode.call(tool, args, handler, forced_uncounted_error=forced)
            same = result.text_sha256 == recorded_sha
            note = ""
            if executed_python:
                if rerun_python:
                    status = "rerun_match" if same else "rerun_differs"
                else:
                    status = "recorded"
                    note = "python output taken from the recording"
            else:
                status = "match" if same else "mismatch"
            if result.envelope["request_id"] != record.get("request_id"):
                note = (note + "; " if note else "") + (
                    f"request_id {result.envelope['request_id']} != "
                    f"{record.get('request_id')}"
                )
                if status == "recorded":
                    status = "mismatch"
            report.items.append(
                ReplayItem(
                    seq=int(record.get("seq") or expected_seq),
                    request_id=str(record.get("request_id")),
                    tool=tool,
                    outcome_code=outcome_code,
                    status=status,
                    recorded_sha256=recorded_sha,
                    replayed_sha256=result.text_sha256,
                    integrity_ok=integrity_ok,
                    note=note,
                )
            )
        final_state = episode.state()
        report.replayed_state = final_state.to_dict()
        if recorded_state is not None:
            for name in _STATE_FIELDS:
                ours, theirs = getattr(final_state, name), getattr(recorded_state, name)
                if ours != theirs:
                    report.problems.append(
                        f"state.{name}: replay {ours!r} != recorded {theirs!r}"
                    )
        if recorded_submission is not None:
            recorded_sha = sha256_text(recorded_submission.decode("utf-8"))
            if (
                recorded_state is not None
                and recorded_sha != recorded_state.submission_sha256
            ):
                report.problems.append(
                    "submission.json does not match the sha256 recorded in state.json"
                )
            if final_state.submission_sha256 != recorded_sha:
                report.problems.append(
                    "replayed submission sha256 differs from the recorded submission.json"
                )
        elif recorded_state is not None and recorded_state.frozen:
            report.problems.append("state says frozen but submission.json is missing")
    report.ok = not report.problems and not report.mismatches
    return report


def replay_episode(
    episode_dir: Path | str,
    *,
    bundle_dir: Path | None = None,
    rerun_python: bool = False,
    python_executable: str | None = None,
    work_dir: Path | None = None,
) -> ReplayReport:
    """Replay ``episode_dir/trace.jsonl`` and compare with the recorded state."""
    episode_dir = Path(episode_dir)
    snapshot = None
    config_path = episode_dir / CONFIG_FILE
    if config_path.exists():
        snapshot = json.loads(config_path.read_text(encoding="utf-8"))
    submission_path = episode_dir / SUBMISSION_FILE
    return replay_records(
        read_trace(episode_dir),
        snapshot=snapshot,
        recorded_state=read_state(episode_dir),
        recorded_submission=submission_path.read_bytes()
        if submission_path.exists()
        else None,
        bundle_dir=bundle_dir,
        rerun_python=rerun_python,
        python_executable=python_executable,
        work_dir=work_dir,
    )
