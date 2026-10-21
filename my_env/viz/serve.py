#!/usr/bin/env python3
"""Serve the agent-world replay UI and a local episode's append-only trace."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import threading
import webbrowser
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from urllib.parse import parse_qs, urlsplit

ENV_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = ENV_DIR / "out"
HTML_FILE = Path(__file__).with_name("agent_world.html")
DEFAULT_EPISODE_DIR = ENV_DIR / "root_data" / "episode"
INCIDENT_DIR = ENV_DIR / "src" / "environment" / "incident"
# The three evidence bundles a run can cite: the MVP, the system response and the full
# investigation. Answer keys, provenance and checklists live in private/ beside them;
# the evidence endpoint reads only files a bundle manifest lists, never private/.
BUNDLE_DIRS = (
    INCIDENT_DIR / "bundle",
    INCIDENT_DIR / "bundles" / "system_response",
    INCIDENT_DIR / "bundles" / "full_investigation",
)
PRIVATE_DIR_NAME = "private"
PRIVATE_DIRS = (INCIDENT_DIR / PRIVATE_DIR_NAME,)


def is_private(path: Path) -> bool:
    """Inside the grader's private directory (answer keys, provenance, checklists)."""
    resolved = path.resolve()
    return resolved.name == PRIVATE_DIR_NAME or any(
        resolved.is_relative_to(private.resolve()) for private in PRIVATE_DIRS
    )


def resolve_output_file(out_dir: Path, requested: str) -> Path:
    """Resolve symlinks before checking containment; never expose other files."""
    root = out_dir.resolve()
    relative = Path(requested)
    if relative.is_absolute():
        raise PermissionError("The path must be relative to out/.")
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise PermissionError("The requested file is outside out/.")
    if not path.is_file():
        raise FileNotFoundError("The requested file does not exist.")
    return path


def read_json(path: Path):
    """A file may not exist yet or may be midway through a producer's write."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None


# The run list carries a compact grade: system-response grades run to ~600 KB each and
# full-investigation grades to ~2 MB. Flags stay whole: they hold the counts the viewer
# shows, including the full investigation's executive-summary word count.
GRADE_SUMMARY_KEYS = (
    "grade_schema",
    "grader_version",
    "task_id",
    "status",
    "provisional_reasons",
    "interpretation",
    "measures_note",
    "flags",
    "severe_flags",
    "key",
    "run",
    "submission",
)


def summarize_grade(grade) -> dict | None:
    """Keep what the viewer shows: status, flags, and how many criteria and
    assertions each decision source (auto, judge, human, pending) holds."""
    if not isinstance(grade, dict):
        return None
    summary = {key: grade[key] for key in GRADE_SUMMARY_KEYS if key in grade}
    for section in ("content_coverage", "evidence_support"):
        value = grade.get(section)
        if not isinstance(value, dict):
            continue
        groups = value.get("by_task") or value.get("by_dimension") or {}
        sources: dict = {}
        for group in groups.values() if isinstance(groups, dict) else ():
            if isinstance(group, dict) and isinstance(group.get("sources"), dict):
                sources.update(group["sources"])
        summary[section] = {"sources": sources}
    quality = grade.get("assertion_quality")
    if isinstance(quality, dict):
        summary["assertion_quality"] = {
            "counts": quality.get("counts_all_tasks")
            or quality.get("counts_all_dimensions")
        }
    judge = grade.get("judge")
    if isinstance(judge, dict):
        summary["judge"] = {
            "judge_model": judge.get("judge_model"),
            "rubric_version": judge.get("rubric_version"),
            "note": judge.get("note"),
            "criteria_applied": len(judge.get("criteria_applied") or []),
            "severe_flag_suggestions": len(judge.get("severe_flag_suggestions") or []),
        }
    elif "judge" in grade:
        summary["judge"] = None
    return summary


def read_output_json(root: Path, path: Path):
    """Read a JSON artifact only if it resolves inside out/."""
    try:
        resolved = resolve_output_file(root, path.relative_to(root).as_posix())
    except (OSError, ValueError):
        return None, None
    data = read_json(resolved)
    return data, resolved.relative_to(root).as_posix() if data is not None else None


# Parsed summaries of large artifacts (a full-investigation grade is about 1.2 MB),
# kept while the file is unchanged so the compare page does not re-parse every grade.
_SUMMARY_CACHE: dict[tuple, object] = {}
_SUMMARY_CACHE_LIMIT = 512


def cached_summary(path: Path, kind: str, build):
    """``build(data)`` for the JSON file at ``path``, cached by its size and mtime."""
    try:
        info = path.stat()
    except OSError:
        return None
    key = (kind, str(path), info.st_mtime_ns, info.st_size)
    if key in _SUMMARY_CACHE:
        return _SUMMARY_CACHE[key]
    value = build(read_json(path))
    if len(_SUMMARY_CACHE) >= _SUMMARY_CACHE_LIMIT:
        _SUMMARY_CACHE.clear()
    _SUMMARY_CACHE[key] = value
    return value


def _number(value):
    return (
        value
        if isinstance(value, int | float) and not isinstance(value, bool)
        else None
    )


def _first(*values):
    return next((value for value in values if value is not None), None)


def transcript_metrics(transcript: dict) -> dict:
    """Calls, peak context, output tokens and the recorded outcome of one run.

    The scoring record's transcript summary is preferred; older transcripts fall back
    to counting their own events. Budgets come from the task metadata."""
    events = [e for e in transcript.get("events") or [] if isinstance(e, dict)]
    pre = next(
        (e for e in events if e.get("type") == "task_pre_hook_completed"), {}
    ).get("metadata")
    pre = pre if isinstance(pre, dict) else {}
    budgets = pre.get("budgets") if isinstance(pre.get("budgets"), dict) else {}
    scoring = next((e for e in events if e.get("type") == "scoring"), {}).get("scoring")
    metadata = scoring.get("metadata") if isinstance(scoring, dict) else None
    metadata = metadata if isinstance(metadata, dict) else {}
    summary = metadata.get("transcript_summary")
    summary = summary if isinstance(summary, dict) else {}
    usage = [e for e in events if e.get("type") == "token_usage"]
    inputs = [_number(e.get("input_tokens")) for e in usage]
    outputs = [_number(e.get("output_tokens")) for e in usage]
    calls = sum(1 for e in events if e.get("type") == "tool_call_completed")
    summary_budgets = (
        summary.get("budgets") if isinstance(summary.get("budgets"), dict) else {}
    )
    return {
        "outcome": metadata.get("outcome"),
        "incomplete_reason": metadata.get("incomplete_reason"),
        "tool_calls": _first(
            _number(summary.get("tool_calls_episode_tools")),
            calls if events else None,
        ),
        "tool_calls_limit": _first(
            _number(budgets.get("max_tool_calls")),
            _number(budgets.get("tool_calls_limit")),
            _number(summary_budgets.get("tool_calls_limit")),
        ),
        "peak_input_tokens": _first(
            _number(summary.get("max_input_tokens")),
            max((v for v in inputs if v is not None), default=None),
        ),
        "context_cap_tokens": _first(
            _number(budgets.get("context_cap_tokens")),
            _number(summary_budgets.get("context_cap_tokens")),
        ),
        "output_tokens": _first(
            _number(summary.get("output_tokens_total")),
            sum(v for v in outputs if v is not None) if usage else None,
        ),
        "output_token_budget": _first(
            _number(budgets.get("output_token_budget")),
            _number(summary_budgets.get("output_token_budget")),
        ),
    }


def transcript_bundle(transcript: dict) -> dict | None:
    """The evidence bundle a transcript's task metadata names."""
    for event in transcript.get("events") or []:
        if isinstance(event, dict) and event.get("type") == "task_pre_hook_completed":
            meta = event.get("metadata")
            if isinstance(meta, dict) and meta.get("bundle_id"):
                return {
                    "bundle_id": meta.get("bundle_id"),
                    "bundle_version": meta.get("bundle_version"),
                    "bundle_sha256": meta.get("bundle_sha256"),
                }
    return None


# The compare page needs every run's values per criterion, not the 1.2 MB grade: this
# projection keeps the grade's own schema (so the viewer reads it with the same code as
# a full grade) and only the fields that decide a value and its source.
_SLIM_VALUE_KEYS = ("value", "source", "auto_proposal", "judge_proposal")
_SLIM_ASSERTION_KEYS = (
    "assertion_id",
    "dimension",
    "kind",
    "source",
    "verdict",
    "auto_proposal",
    "judge_proposal",
)


def topic_hint(title) -> str:
    """A topic's first criterion title, shortened: the grade names no topics."""
    text = " ".join(str(title or "").split())
    return text if len(text) <= 70 else text[:69].rstrip() + "…"


def slim_grade(grade) -> dict | None:
    if not isinstance(grade, dict):
        return None

    def value_of(field):
        field = field if isinstance(field, dict) else {}
        return {k: field[k] for k in _SLIM_VALUE_KEYS if field.get(k) is not None}

    def picked(value, keys):
        value = value if isinstance(value, dict) else {}
        return {k: value[k] for k in keys if value.get(k) is not None}

    slim = {
        k: grade[k]
        for k in ("grade_schema", "grader_version", "task_id", "status")
        if k in grade
    }
    if grade.get("measures_note"):
        slim["measures_note"] = grade["measures_note"]
    tasks = grade.get("tasks")
    if isinstance(tasks, list) and all(isinstance(t, str) for t in tasks):
        slim["tasks"] = tasks
    slim["key"] = picked(grade.get("key"), ("key_id", "key_version", "review_status"))
    run = grade.get("run") if isinstance(grade.get("run"), dict) else {}
    slim["run"] = picked(run, ("outcome", "incomplete_reason", "budgets", "tokens"))
    criteria, hints = [], {}
    for criterion in grade.get("criteria") or []:
        if not isinstance(criterion, dict):
            continue
        item = picked(
            criterion, ("criterion_id", "task", "dimension", "assessment_mode")
        )
        item["content"] = value_of(criterion.get("content"))
        item["evidence_support"] = value_of(criterion.get("evidence_support"))
        criteria.append(item)
        topic = criterion.get("task") or criterion.get("dimension")
        if topic and topic not in hints:
            hints[topic] = topic_hint(criterion.get("title"))
    slim["criteria"] = criteria
    slim["topic_hints"] = hints
    quality = grade.get("assertion_quality")
    if isinstance(quality, dict):
        slim["assertion_quality"] = {
            "assertions": [
                picked(a, _SLIM_ASSERTION_KEYS)
                for a in quality.get("assertions") or []
                if isinstance(a, dict)
            ]
        }
    if isinstance(grade.get("judge"), dict):
        slim["judge"] = picked(grade["judge"], ("judge_model", "rubric_version"))
    return slim


def judge_summary(artifacts: Path, root: Path) -> dict | None:
    """LLM judge outputs (proposals awaiting human sign-off), when a run has them."""
    judge_dir = artifacts / "episode" / "judge"
    record, record_path = read_output_json(root, judge_dir / "judge_run.json")
    judged, judged_path = read_output_json(root, judge_dir / "grade.json")
    if not isinstance(record, dict) and not isinstance(judged, dict):
        return None
    record = record if isinstance(record, dict) else {}
    meta = judged.get("judge") if isinstance(judged, dict) else None
    meta = meta if isinstance(meta, dict) else {}
    # The request scope: "topic" (full investigation: each topic sees only its own
    # findings and spans) or "submission" (increment A); older outputs record none.
    output, _ = read_output_json(root, judge_dir / "judge_output.json")
    scope = output.get("scope") if isinstance(output, dict) else None
    return {
        "status": record.get("status"),
        "scope": scope.get("mode") if isinstance(scope, dict) else None,
        "units": record.get("units"),
        "failed_units": len(record.get("failed_units") or []),
        "errors": len(record.get("errors") or {}),
        "api_calls": record.get("api_calls"),
        "cache_hits": record.get("cache_hits"),
        "judge_model": meta.get("judge_model"),
        "rubric_version": meta.get("rubric_version"),
        "note": meta.get("note"),
        "grade": summarize_grade(judged),
        "path": judged_path,
        "run_path": record_path,
    }


def live_episode_config(episode_dir: Path) -> dict | None:
    """The episode's tool names and budgets, written before the first call."""
    snapshot = read_json(episode_dir / "episode_config.json")
    if not isinstance(snapshot, dict):
        return None
    config = snapshot.get("config") if isinstance(snapshot.get("config"), dict) else {}
    tool_names = snapshot.get("tool_names")
    return {
        "tool_names": tool_names if isinstance(tool_names, list) else None,
        "bundle_version": snapshot.get("bundle_version"),
        "budgets": {
            "tool_calls_limit": config.get("max_tool_calls"),
            "frequency_page_size": config.get("frequency_page_size"),
            "log_page_size": config.get("log_page_size"),
        },
    }


def artifact_dir(transcript_path: Path, run_id: str, out_dir: Path) -> Path | None:
    # A transcript's run ID is input data, not permission to construct a new path.
    if not run_id or Path(run_id).name != run_id:
        return None
    path = (transcript_path.parent / f"{run_id}_artifacts").resolve()
    return path if path.is_relative_to(out_dir.resolve()) else None


def discover_runs(out_dir: Path = OUT_DIR) -> list[dict]:
    """Include nested output directories, ignoring unfinished/invalid JSON files."""
    root = out_dir.resolve()
    runs = []
    for candidate in root.rglob("transcript.json"):
        try:
            path = resolve_output_file(root, candidate.relative_to(root).as_posix())
        except (OSError, ValueError):
            continue
        transcript = read_json(path)
        if not isinstance(transcript, dict) or not isinstance(
            transcript.get("events"), list
        ):
            continue
        run_id = str(transcript.get("run_id") or path.parent.name)
        events = transcript["events"]
        started = next(
            (
                event
                for event in events
                if isinstance(event, dict) and event.get("type") == "task_started"
            ),
            {},
        )
        artifacts = artifact_dir(path, run_id, root)
        grade_path = None
        grade = None
        judge = None
        submission_path = None
        bundle = transcript_bundle(transcript)
        if artifacts is not None:
            full_grade, grade_path = read_output_json(root, artifacts / "grade.json")
            grade = summarize_grade(full_grade)
            judge = judge_summary(artifacts, root)
            submission_path = output_path(
                root, artifacts / "episode" / "submission.json"
            )
            config, _ = read_output_json(
                root, artifacts / "episode" / "episode_config.json"
            )
            if isinstance(config, dict) and config.get("bundle_sha256"):
                bundle = {
                    "bundle_id": config.get("bundle_id"),
                    "bundle_version": config.get("bundle_version"),
                    "bundle_sha256": config.get("bundle_sha256"),
                }
        runs.append(
            {
                "run_id": run_id,
                "path": path.relative_to(root).as_posix(),
                "model": started.get("model"),
                "event_count": len(events),
                "task_id": started.get("task_id"),
                "timestamp": started.get("timestamp"),
                "grade": grade,
                "grade_path": grade_path,
                "judge": judge,
                "submission_path": submission_path,
                "bundle": bundle,
                "metrics": transcript_metrics(transcript),
            }
        )
    return sorted(
        runs, key=lambda run: (str(run["timestamp"] or ""), run["path"]), reverse=True
    )


def output_path(root: Path, path: Path) -> str | None:
    """The out/-relative path of a regular file that resolves inside out/."""
    try:
        return (
            resolve_output_file(root, path.relative_to(root).as_posix())
            .relative_to(root)
            .as_posix()
        )
    except (OSError, ValueError):
        return None


def results_grade_path(run: dict) -> tuple[str | None, str | None]:
    """The grade a run's results use: the judged grade (episode/judge/grade.json)
    supersedes the run's grade.json when present."""
    judged = (run.get("judge") or {}).get("path")
    if judged:
        return judged, "judge"
    if run.get("grade_path"):
        return run["grade_path"], "run"
    return None, None


def discover_results(out_dir: Path = OUT_DIR) -> dict:
    """Compact per-run results for the compare page: outcome, calls, tokens and each
    criterion's value and source. Full grades stay behind /api/file."""
    root = out_dir.resolve()
    runs, hints = [], {}
    for run in discover_runs(out_dir):
        path, source = results_grade_path(run)
        grade = None
        if path is not None:
            try:
                grade = cached_summary(
                    resolve_output_file(root, path), "slim_grade", slim_grade
                )
            except (OSError, ValueError):
                grade = None
        if isinstance(grade, dict) and grade.get("topic_hints"):
            task_hints = hints.setdefault(run.get("task_id") or "", {})
            for topic, hint in grade["topic_hints"].items():
                task_hints.setdefault(topic, hint)
            grade = {k: v for k, v in grade.items() if k != "topic_hints"}
        runs.append(
            {
                **{
                    key: run[key]
                    for key in (
                        "run_id",
                        "path",
                        "model",
                        "task_id",
                        "timestamp",
                        "submission_path",
                        "metrics",
                    )
                },
                "grade": grade,
                "grade_path": path if grade is not None else None,
                "grade_source": source if grade is not None else None,
            }
        )
    return {"runs": runs, "topic_hints": hints}


def trace_cursor(stream: BinaryIO, offset: int) -> str:
    """Identify both a file and its consumed boundary, including in-place resets."""
    stat = os.fstat(stream.fileno())
    position = stream.tell()
    stream.seek(0)
    start = stream.read(min(offset, 256))
    stream.seek(max(0, offset - 256))
    end = stream.read(min(offset, 256))
    stream.seek(position)
    digest = hashlib.sha256(start + end).hexdigest()
    return f"{stat.st_dev}:{stat.st_ino}:{offset}:{digest}"


class LiveTail:
    def __init__(self, episode_dir: Path):
        self.episode_dir = episode_dir.resolve()
        self._last_cursor: str | None = None
        self._last_offset = 0
        self._lock = threading.Lock()

    def read(self, offset: int = 0, cursor: str | None = None) -> dict:
        if offset < 0:
            raise ValueError("offset must be a non-negative byte offset")
        with self._lock:
            return self._read(offset, cursor)

    def _read(self, offset: int, cursor: str | None) -> dict:
        result = {
            "records": [],
            "offset": 0,
            "cursor": None,
            "reset": False,
            "waiting": True,
            "state": read_json(self.episode_dir / "state.json"),
            "episode": live_episode_config(self.episode_dir),
            "episode_dir": str(self.episode_dir),
            "replay": None,
            "errors": [],
        }
        try:
            stream = (self.episode_dir / "trace.jsonl").open("rb")
        except FileNotFoundError:
            result["reset"] = offset > 0 or cursor is not None
            self._last_cursor = None
            self._last_offset = 0
            return result
        with stream:
            size = os.fstat(stream.fileno()).st_size
            previous = cursor
            if previous is None and offset == self._last_offset:
                previous = self._last_cursor
            reset = offset > size or (
                previous is not None and previous != trace_cursor(stream, offset)
            )
            if reset:
                offset = 0
            # Bound the read to this snapshot; appends will be picked up next poll.
            stream.seek(offset)
            pending = stream.read(max(0, size - offset))
            complete = pending[: pending.rfind(b"\n") + 1]
            for line in complete.splitlines():
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise ValueError("Trace records must be JSON objects.")
                    result["records"].append(record)
                except (UnicodeError, ValueError) as error:
                    # Consume a broken complete line so subsequent calls can progress.
                    result["errors"].append(f"Skipped invalid trace record: {error}")
            next_offset = offset + len(complete)
            next_cursor = trace_cursor(stream, next_offset)
            self._last_cursor = next_cursor
            self._last_offset = next_offset
            result.update(
                offset=next_offset,
                cursor=next_cursor,
                reset=reset,
                waiting=size == 0,
            )
        return result


def completed_replay(episode_dir: Path, out_dir: Path) -> dict | None:
    """Match the actual trace, so an unrelated old transcript is never offered."""
    try:
        live_trace = (episode_dir / "trace.jsonl").read_bytes()
    except OSError:
        return None
    if not live_trace or not live_trace.endswith(b"\n"):
        return None
    for run in discover_runs(out_dir):
        transcript = out_dir.resolve() / run["path"]
        artifacts = artifact_dir(transcript, run["run_id"], out_dir)
        if artifacts is None:
            continue
        try:
            candidate = resolve_output_file(
                out_dir,
                (artifacts / "episode" / "trace.jsonl")
                .relative_to(out_dir.resolve())
                .as_posix(),
            )
            if candidate.read_bytes() == live_trace:
                return run
        except (OSError, ValueError):
            continue
    return None


# -- evidence -------------------------------------------------------------------------
# The evidence drawer shows what a citation points at, read from the bundle the run
# used (matched by its manifest sha256). Only files a manifest lists are read, each
# checked against the manifest hash, without following links or leaving the bundle.

_EVIDENCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_EVIDENCE_BYTES = 64 * 1024 * 1024
_MAX_LOCATOR_CHARS = 200
MAX_CONTEXT = 40
MAX_SHOWN_ROWS = 400
MAX_SHOWN_LINES = 600
RECORD_KINDS = ("event", "entry", "response")
_RECORD_NAMES = {
    "event": "asset-log event",
    "entry": "control-log entry",
    "response": "witness response",
}
# The locator grammar of environment.incident.locators, restated so the server stays
# standard-library only.
_ISO = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})"
_LINES_RE = re.compile(r"^[Ll](\d{1,9})(?:\s*-\s*[Ll]?(\d{1,9}))?$")
_TIME_RE = re.compile(rf"^({_ISO})(?:\s*/\s*({_ISO}))?$")
_ROWS_RE = re.compile(r"^(\d{1,9})(?:\s*-\s*(\d{1,9}))?$")
_RECORD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


class EvidenceRefused(PermissionError):
    """A file the evidence endpoint must not read."""


class LocatorProblem(ValueError):
    """A locator that is malformed or does not fit the cited evidence."""


def _instant(text: str) -> datetime:
    value = text.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    # Python reads at most six fractional digits.
    value = re.sub(r"(\.\d{6})\d+", r"\1", value)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise LocatorProblem(f"{text!r} is not a valid date/time") from None


def parse_locator(text) -> dict:
    """``{"kind", "start", "end", "normalized"}`` or :class:`LocatorProblem`."""
    if not isinstance(text, str) or not text.strip():
        raise LocatorProblem("locator is empty")
    value = text.strip()
    if len(value) > _MAX_LOCATOR_CHARS:
        raise LocatorProblem(f"locator is longer than {_MAX_LOCATOR_CHARS} characters")
    lowered = value.lower()
    if lowered.startswith("time:"):
        match = _TIME_RE.match(value[5:].strip())
        if not match:
            raise LocatorProblem(f"malformed time locator {text!r}")
        start = _instant(match.group(1))
        end = _instant(match.group(2)) if match.group(2) else start
        if start > end:
            raise LocatorProblem(f"time locator {text!r} is reversed")
        a, b = start.astimezone(UTC).isoformat(), end.astimezone(UTC).isoformat()
        normalized = f"time:{a}" if start == end else f"time:{a}/{b}"
        return {"kind": "time", "start": start, "end": end, "normalized": normalized}
    for kind in RECORD_KINDS:
        if lowered.startswith(f"{kind}:"):
            record = value[len(kind) + 1 :].strip()
            if not _RECORD_ID_RE.match(record):
                raise LocatorProblem(
                    f"malformed {_RECORD_NAMES[kind]} locator {text!r}"
                )
            return {
                "kind": kind,
                "start": record,
                "end": record,
                "normalized": f"{kind}:{record}",
            }
    for prefix in ("rows:", "row:"):
        if lowered.startswith(prefix):
            match = _ROWS_RE.match(value[len(prefix) :].strip())
            if not match:
                raise LocatorProblem(f"malformed row locator {text!r}")
            return _span("rows", match, text)
    if lowered.startswith("l"):
        match = _LINES_RE.match(value)
        if not match:
            raise LocatorProblem(f"malformed line locator {text!r}")
        return _span("lines", match, text)
    raise LocatorProblem(f"unrecognised locator {text!r}")


def _span(kind: str, match: re.Match, text: str) -> dict:
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) is not None else start
    if start < 1:
        raise LocatorProblem(f"{text!r}: numbering starts at 1")
    if start > end:
        raise LocatorProblem(f"{text!r} is reversed")
    if kind == "lines":
        normalized = f"L{start}" if start == end else f"L{start}-L{end}"
    else:
        normalized = f"row:{start}" if start == end else f"rows:{start}-{end}"
    return {"kind": kind, "start": start, "end": end, "normalized": normalized}


def read_bundle_file(root: Path, relative: str, expected_sha256: str | None) -> bytes:
    """Read one file of a bundle: a plain relative path with no link anywhere along it,
    never under private/, and (when given) matching the manifest's hash."""
    if (
        not isinstance(relative, str)
        or not relative
        or "\\" in relative
        or "\x00" in relative
    ):
        raise EvidenceRefused("The bundle path is not a plain relative path.")
    rel = PurePosixPath(relative)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        raise EvidenceRefused("The bundle path must stay inside the bundle.")
    if PRIVATE_DIR_NAME in rel.parts or is_private(root):
        raise EvidenceRefused("Private grading material is never served.")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise EvidenceRefused("Linked bundle files are not followed.")
    try:
        descriptor = os.open(current, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        raise
    except OSError as error:
        raise EvidenceRefused("The bundle file could not be opened safely.") from error
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_EVIDENCE_BYTES:
            raise EvidenceRefused("Only regular bundle files are read.")
        data = stream.read()
    if not current.resolve().is_relative_to(root):
        raise EvidenceRefused("The bundle file is outside the bundle.")
    if expected_sha256 is not None and hashlib.sha256(data).hexdigest() != (
        expected_sha256
    ):
        raise EvidenceRefused("The bundle file does not match its manifest hash.")
    return data


def _text_lines(text: str) -> list[str]:
    """Lines as line locators count them (LF only), as the catalogue splits them."""
    if not text:
        return []
    return (text[:-1] if text.endswith("\n") else text).split("\n")


class EvidenceBundle:
    """One bundle: its manifest-listed files and their hashes, documents and records."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        data = read_bundle_file(self.root, "manifest.json", None)
        self.sha256 = hashlib.sha256(data).hexdigest()
        manifest = json.loads(data)
        if not isinstance(manifest, dict):
            raise ValueError("The bundle manifest is not an object.")
        self.bundle_id = str(manifest.get("bundle_id") or "")
        self.version = str(manifest.get("bundle_version") or "")
        self.manifest_version = manifest.get("manifest_version") or 1
        self.files: dict[str, str] = {}
        self.documents: dict[str, dict] = {}
        for doc in manifest.get("documents") or []:
            if not isinstance(doc, dict) or not doc.get("doc_id"):
                continue
            hashes = doc.get("sha256") if isinstance(doc.get("sha256"), dict) else {}
            self.files.update({str(k): str(v) for k, v in hashes.items()})
            self.documents[str(doc["doc_id"])] = doc
        self.sections = {}
        for section in ("asset_logs", "control_logs", "witnesses"):
            entries = [
                entry
                for entry in manifest.get(section) or []
                if isinstance(entry, dict) and entry.get("file")
            ]
            for entry in entries:
                self.files[str(entry["file"])] = str(entry.get("sha256") or "")
            self.sections[section] = entries
        self._cache: dict[str, bytes] = {}
        self._records: dict | None = None
        self._lock = threading.Lock()

    def describe(self) -> dict:
        return {
            "bundle_id": self.bundle_id,
            "bundle_version": self.version,
            "bundle_sha256": self.sha256,
        }

    def read(self, relative: str) -> bytes:
        """A manifest-listed file, checked against its manifest hash."""
        expected = self.files.get(relative)
        if not expected:
            raise EvidenceRefused("Only files listed in the bundle manifest are read.")
        with self._lock:
            if relative not in self._cache:
                self._cache[relative] = read_bundle_file(self.root, relative, expected)
            return self._cache[relative]

    def records(self) -> dict:
        """``(kind, record_id) -> (evidence_id, fields, source)`` for a v2 bundle."""
        if self._records is not None:
            return self._records
        records: dict = {}
        for kind, section, key, source_keys in (
            ("event", "asset_logs", "event_id", ("asset_id", "title", "owner")),
            ("entry", "control_logs", "entry_id", ("room_id", "title", "owner")),
        ):
            for entry in self.sections.get(section, []):
                source = {
                    k: entry.get(k) for k in (*source_keys, "status", "clock_note")
                }
                text = self.read(str(entry["file"])).decode("utf-8")
                for line in text.splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if isinstance(row, dict) and row.get(key):
                        records[(kind, str(row[key]))] = (
                            str(row.get("evidence_id") or ""),
                            row,
                            source,
                        )
        for entry in self.sections.get("witnesses", []):
            card = json.loads(self.read(str(entry["file"])).decode("utf-8"))
            if not isinstance(card, dict):
                continue
            source = {
                k: card.get(k) or entry.get(k)
                for k in ("persona_id", "role", "organisation", "status")
            }
            for block in card.get("blocks") or []:
                if isinstance(block, dict) and block.get("response_id"):
                    records[("response", str(block["response_id"]))] = (
                        str(card.get("evidence_id") or entry.get("evidence_id") or ""),
                        block,
                        source,
                    )
        self._records = records
        return records


class EvidenceLibrary:
    """The local bundles, found by the manifest sha256 a run recorded."""

    def __init__(self, bundle_dirs=BUNDLE_DIRS):
        self.bundle_dirs = tuple(Path(d) for d in bundle_dirs)
        self._loaded: dict[str, tuple[tuple, EvidenceBundle]] = {}
        self._lock = threading.Lock()

    def bundles(self) -> list[EvidenceBundle]:
        found = []
        for directory in self.bundle_dirs:
            manifest = directory / "manifest.json"
            try:
                info = manifest.lstat()
            except OSError:
                continue
            key = (info.st_mtime_ns, info.st_size, info.st_ino)
            with self._lock:
                cached = self._loaded.get(str(directory))
                if cached is None or cached[0] != key:
                    try:
                        cached = (key, EvidenceBundle(directory))
                    except (OSError, ValueError, UnicodeError):
                        continue
                    self._loaded[str(directory)] = cached
            found.append(cached[1])
        return found

    def find(self, sha256: str) -> EvidenceBundle | None:
        return next((b for b in self.bundles() if b.sha256 == sha256), None)

    def available(self) -> list[dict]:
        return [bundle.describe() for bundle in self.bundles()]


_DOC_FIELDS = ("doc_id", "title", "owner", "date", "category", "label", "access")
_RECORD_FIELDS = {
    "event": (
        "event_id",
        "recorded_time",
        "clock_basis",
        "signal",
        "value",
        "unit",
        "value_status",
        "text",
    ),
    "entry": (
        "entry_id",
        "recorded_time",
        "clock_basis",
        "from",
        "to",
        "channel",
        "value_status",
        "text",
    ),
    "response": ("response_id", "response_text"),
}


def resolve_citation(
    bundle: EvidenceBundle, evidence_id: str, locator: str, context: int = 3
) -> dict:
    """What a citation points at in ``bundle``: numbered lines (with ``context`` lines
    either side), time-series rows, or one record. A citation that does not resolve
    comes back with ``resolved`` false and the reason."""
    if not isinstance(evidence_id, str) or not _EVIDENCE_ID_RE.match(evidence_id):
        raise ValueError("evidence_id is not an evidence identifier")
    context = max(0, min(MAX_CONTEXT, int(context)))
    doc = bundle.documents.get(evidence_id)
    result = {
        "resolved": False,
        "error": None,
        "evidence_id": evidence_id,
        "locator": locator,
        "normalized": None,
        "kind": None,
        "bundle": bundle.describe(),
        "document": {k: doc[k] for k in _DOC_FIELDS if k in doc} if doc else None,
    }
    records = bundle.records() if bundle.manifest_version >= 2 else {}
    owned = any(owner == evidence_id for owner, _, _ in records.values())
    if doc is None and not owned:
        result["error"] = f"unknown evidence_id {evidence_id!r} in this bundle"
        return result
    try:
        loc = parse_locator(locator)
        result.update(kind=loc["kind"], normalized=loc["normalized"])
        if loc["kind"] in RECORD_KINDS:
            result.update(_resolve_record(records, evidence_id, loc))
        elif doc is None:
            raise LocatorProblem(
                f"{evidence_id} has no document text or time series to cite with "
                f"{loc['normalized']}"
            )
        elif loc["kind"] == "lines":
            result.update(_resolve_lines(bundle, doc, loc, context))
        else:
            result.update(_resolve_rows(bundle, doc, loc))
    except LocatorProblem as problem:
        result["error"] = str(problem)
        return result
    result["resolved"] = True
    return result


def _resolve_lines(bundle: EvidenceBundle, doc: dict, loc: dict, context: int) -> dict:
    lines = _text_lines(bundle.read(str(doc.get("text_file"))).decode("utf-8"))
    if loc["end"] > len(lines):
        raise LocatorProblem(
            f"{doc['doc_id']} has {len(lines)} lines; {loc['normalized']} is out of range"
        )
    last = min(loc["end"], loc["start"] + MAX_SHOWN_LINES - 1)
    first_shown, last_shown = (
        max(1, loc["start"] - context),
        min(len(lines), last + context),
    )
    return {
        "line_count": len(lines),
        "truncated": last < loc["end"],
        "lines": [
            {"n": n, "text": lines[n - 1], "cited": loc["start"] <= n <= loc["end"]}
            for n in range(first_shown, last_shown + 1)
        ],
    }


def _resolve_rows(bundle: EvidenceBundle, doc: dict, loc: dict) -> dict:
    artifact = next(
        (
            a
            for a in doc.get("artifacts") or []
            if isinstance(a, dict) and isinstance(a.get("timeseries"), dict)
        ),
        None,
    )
    if artifact is None:
        raise LocatorProblem(
            f"{doc['doc_id']} has no time series; cite its text with line locators"
        )
    series = artifact["timeseries"]
    text = bundle.read(str(artifact["file"])).decode("utf-8").splitlines()
    header, rows = (text[0] if text else ""), text[1:]
    if loc["kind"] == "rows":
        a, b = loc["start"] - 1, loc["end"] - 1
        if loc["end"] > len(rows):
            raise LocatorProblem(
                f"the {doc['doc_id']} series has {len(rows)} data rows; "
                f"{loc['normalized']} is out of range"
            )
    else:
        first, last = _instant(series["first"]), _instant(series["last"])
        for when in (loc["start"], loc["end"]):
            if when < first or when > last:
                raise LocatorProblem(
                    f"time {when.isoformat()} is outside the {doc['doc_id']} series "
                    f"({first.isoformat()} to {last.isoformat()}, inclusive)"
                )
        interval = float(series.get("interval_s") or 1)
        a = math.ceil((loc["start"] - first).total_seconds() / interval)
        b = math.floor((loc["end"] - first).total_seconds() / interval)
    shown = range(a, min(b, a + MAX_SHOWN_ROWS - 1) + 1)
    return {
        "file": artifact["file"],
        "header": header,
        "row_count": len(rows),
        "cited_rows": max(0, b - a + 1),
        "truncated": b - a + 1 > MAX_SHOWN_ROWS,
        "unit": series.get("unit"),
        "rows": [{"n": i + 1, "text": rows[i], "cited": True} for i in shown],
    }


def _resolve_record(records: dict, evidence_id: str, loc: dict) -> dict:
    found = records.get((loc["kind"], loc["start"]))
    name = _RECORD_NAMES[loc["kind"]]
    if found is None:
        raise LocatorProblem(f"{evidence_id} has no {name} {loc['start']!r}")
    owner, fields, source = found
    if owner != evidence_id:
        raise LocatorProblem(
            f"{name} {loc['start']!r} belongs to evidence {owner}, not {evidence_id}"
        )
    return {
        "record": {
            "kind": loc["kind"],
            "id": loc["start"],
            "fields": {
                k: fields[k] for k in _RECORD_FIELDS[loc["kind"]] if k in fields
            },
            "source": {k: v for k, v in source.items() if v is not None},
        }
    }


def make_server(
    port: int = 8765,
    *,
    out_dir: Path = OUT_DIR,
    episode_dir: Path | None = None,
    html_file: Path = HTML_FILE,
    bundle_dirs=BUNDLE_DIRS,
) -> ThreadingHTTPServer:
    root = out_dir.resolve()
    tail = LiveTail(episode_dir) if episode_dir is not None else None
    library = EvidenceLibrary(bundle_dirs)

    class Handler(BaseHTTPRequestHandler):
        def send_body(self, data: bytes, content_type: str, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, data, status: int = 200):
            self.send_body(
                json.dumps(data, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
                status,
            )

        def do_GET(self):
            url = urlsplit(self.path)
            query = parse_qs(url.query, keep_blank_values=True)
            try:
                if url.path in ("/", "/agent_world.html", "/compare", "/compare/"):
                    # The compare page is the same self-contained viewer on its own route.
                    self.send_body(html_file.read_bytes(), "text/html; charset=utf-8")
                elif url.path == "/api/results":
                    self.send_json(discover_results(root))
                elif url.path == "/api/bundles":
                    self.send_json({"bundles": library.available()})
                elif url.path == "/api/evidence":
                    sha = query.get("bundle", [""])[0]
                    evidence_id = query.get("evidence_id", [""])[0]
                    locator = query.get("locator", [""])[0]
                    if not _SHA256_RE.match(sha) or not evidence_id or not locator:
                        raise ValueError(
                            "bundle, evidence_id and locator are required."
                        )
                    bundle = library.find(sha)
                    if bundle is None:
                        self.send_json(
                            {
                                "error": "No local evidence bundle matches the bundle "
                                "this run used, so its citations cannot be shown.",
                                "bundle_sha256": sha,
                                "available": library.available(),
                            },
                            404,
                        )
                        return
                    self.send_json(
                        resolve_citation(
                            bundle,
                            evidence_id,
                            locator,
                            int(query.get("context", ["3"])[0]),
                        )
                    )
                elif url.path == "/api/config":
                    self.send_json(
                        {
                            "mode": "live" if tail else "replay",
                            "live": tail is not None,
                            "episode_dir": str(tail.episode_dir) if tail else None,
                            "poll_interval_ms": 500,
                        }
                    )
                elif url.path == "/api/runs":
                    self.send_json({"runs": discover_runs(root)})
                elif url.path == "/api/file":
                    if not query.get("path", [""])[0]:
                        raise ValueError("A path relative to out/ is required.")
                    path = resolve_output_file(root, query["path"][0])
                    self.send_body(path.read_bytes(), "application/json; charset=utf-8")
                elif url.path == "/api/live":
                    if tail is None:
                        self.send_json({"error": "Start the server with --live."}, 404)
                        return
                    result = tail.read(
                        int(query.get("offset", ["0"])[0]),
                        query.get("cursor", [None])[0],
                    )
                    result["replay"] = completed_replay(tail.episode_dir, root)
                    self.send_json(result)
                else:
                    self.send_json({"error": "Not found."}, 404)
            except PermissionError as error:
                self.send_json({"error": str(error)}, 403)
            except FileNotFoundError:
                self.send_json({"error": "File not found."}, 404)
            except (ValueError, UnicodeError):
                self.send_json({"error": "Invalid path or offset."}, 400)
            except OSError:
                self.send_json({"error": "The requested file could not be read."}, 500)

        def log_message(self, format, *args):
            # Live polling is deliberately quiet; startup prints the useful URL.
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--live",
        nargs="?",
        const=str(DEFAULT_EPISODE_DIR),
        metavar="EPISODE_DIR",
        help="Follow trace.jsonl (default: my_env/root_data/episode).",
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Do not open a browser automatically."
    )
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    episode_dir = Path(args.live).expanduser().resolve() if args.live else None
    try:
        server = make_server(args.port, episode_dir=episode_dir)
    except OSError as error:
        parser.exit(1, f"Could not start the visualiser: {error}\n")
    with server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"Agent world: {url}", flush=True)
        if episode_dir:
            print(f"Following {episode_dir / 'trace.jsonl'}", flush=True)
            print(
                "Container runs need a bind-mounted episode directory for live follow.",
                flush=True,
            )
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
