"""Shared helpers for the incident runtime tests.

Builds a small SYNTHETIC evidence bundle in a temporary directory (the real bundle is
authored separately and is never loaded by these tests): five documents with the real
IDs and categories, neutral placeholder text, and a tiny 1-second time series.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from environment.incident.episode import CallResult, EpisodeConfig

SERIES_FIRST = "2019-08-09T16:52:30+01:00"
SERIES_LAST = "2019-08-09T16:52:49+01:00"
SERIES_ROWS = 20

# doc_id -> (category, title, number of text lines)
DOCS: dict[str, tuple[str, str, int]] = {
    "R01": ("measurement_data", "Synthetic measurement record", 12),
    "R03": ("network_records", "Synthetic network record", 30),
    "S01": ("generator_records", "Synthetic generator record A", 25),
    "S03": ("generator_records", "Synthetic generator record B", 25),
    "S04": ("personnel_accounts", "Synthetic personnel account", 20),
}
CSV_NAME = "series.csv"


def series_csv() -> str:
    lines = ["timestamp,frequency_hz"]
    for i in range(SERIES_ROWS):
        lines.append(f"2019-08-09T16:52:{30 + i:02d}+01:00,{50.0 - 0.01 * i:.3f}")
    return "\n".join(lines) + "\n"


def doc_text(doc_id: str, title: str, n_lines: int) -> str:
    lines = [
        f"DOCUMENT {doc_id} - {title}",
        "STATUS: SYNTHETIC TEST FIXTURE - NOT EVIDENCE",
    ]
    lines += [f"{doc_id} placeholder line {i}" for i in range(3, n_lines + 1)]
    return "\n".join(lines) + "\n"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_bundle(root: Path, *, version: str = "1.0.0-test") -> Path:
    """Write the synthetic bundle under ``root/bundle`` and return its path."""
    bundle = root / "bundle"
    documents = []
    for doc_id, (category, title, n_lines) in DOCS.items():
        (bundle / doc_id).mkdir(parents=True)
        text_rel = f"{doc_id}/{doc_id}.txt"
        (bundle / text_rel).write_text(
            doc_text(doc_id, title, n_lines), encoding="utf-8"
        )
        artifacts: list[dict[str, Any]] = [
            {
                "file": text_rel,
                "media_type": "text/plain",
                "description": "Record text.",
            }
        ]
        if doc_id == "R01":
            csv_rel = f"R01/{CSV_NAME}"
            (bundle / csv_rel).write_text(series_csv(), encoding="utf-8")
            artifacts.append(
                {
                    "file": csv_rel,
                    "media_type": "text/csv",
                    "description": "One-second samples.",
                    "timeseries": {
                        "time_column": "timestamp",
                        "value_column": "frequency_hz",
                        "unit": "Hz",
                        "first": SERIES_FIRST,
                        "last": SERIES_LAST,
                        "rows": SERIES_ROWS,
                        "interval_s": 1,
                    },
                }
            )
        documents.append(
            {
                "doc_id": doc_id,
                "title": title,
                "owner": f"Synthetic owner {doc_id}",
                "date": "2019-08-09",
                "category": category,
                "text_file": text_rel,
                "artifacts": artifacts,
                "sha256": {},
            }
        )
    manifest = {
        "bundle_id": "synthetic-test-bundle",
        "bundle_version": version,
        "documents": documents,
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2))
    rehash(bundle)
    return bundle


def rehash(bundle: Path) -> None:
    """Recompute every artifact hash in the manifest (after an intended edit)."""
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for doc in manifest["documents"]:
        doc["sha256"] = {
            a["file"]: sha256((bundle / a["file"]).read_bytes())
            for a in doc["artifacts"]
        }
    manifest_path.write_text(json.dumps(manifest, indent=2))


def edit_manifest(bundle: Path, mutate) -> None:
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    mutate(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2))


def make_config(root: Path, bundle: Path, **overrides: Any) -> EpisodeConfig:
    values: dict[str, Any] = dict(
        episode_dir=root / "root_data" / "episode",
        evidence_dir=root / "workdir" / "evidence",
        scratch_dir=root / "workdir" / "scratch",
        bundle_dir=bundle,
        python_executable=sys.executable,
        python_timeout_s=20,
    )
    values.update(overrides)
    return EpisodeConfig(**values)


def valid_submission(**overrides: Any) -> dict[str, Any]:
    submission: dict[str, Any] = {
        "schema_version": "3.0",
        "variant_id": "baseline",
        "report": {
            "executive_summary": "Synthetic summary referring to [F01] and [F02].",
            "sections": [{"heading": "Chronology", "body": "See [F01, F02]."}],
        },
        "findings": [
            {
                "finding_id": "F01",
                "statement": "Synthetic statement one.",
                "status": "reported",
                "citations": [{"evidence_id": "R03", "locator": "L3-L5"}],
            },
            {
                "finding_id": "F02",
                "statement": "Synthetic statement two.",
                "status": "observed",
                "citations": [
                    {
                        "evidence_id": "R01",
                        "locator": "time:2019-08-09T16:52:35+01:00/2019-08-09T16:52:40+01:00",
                    },
                    {"evidence_id": "R01", "locator": "rows:6-11"},
                ],
                "quantity": {"value": 49.95, "unit": "Hz", "basis": "synthetic"},
                "event_time": "2019-08-09T16:52:35+01:00",
                "derivation": "minimum of the cited samples",
            },
        ],
    }
    submission.update(overrides)
    return submission


# -- synthetic transcripts -------------------------------------------------------
def transcript_for(
    calls: list[tuple[str, dict[str, Any], CallResult | None]],
    *,
    final_text: str | None = "Done.",
    usage: list[tuple[int, int]] | None = None,
):
    """A Karotte ``Transcript`` with one assistant turn per tool call.

    ``calls`` are (tool name, arguments, ledger result or None when the call never
    reached the ledger). ``usage`` gives (input, output) tokens per assistant turn
    (defaults to small numbers); the final message (if any) is the last turn.
    """
    from karotte.schemas.chat import ChatCompletionMessageToolCall, Function, Message
    from karotte.schemas.transcript import (
        MessageAddedEvent,
        TokenUsageEvent,
        ToolCallCompletedEvent,
        ToolCallStartedEvent,
        Transcript,
    )
    from mcp.types import CallToolResult, TextContent

    turns = len(calls) + (1 if final_text is not None else 0)
    usage = list(usage or [(1000, 100)] * turns)
    events: list[Any] = [
        MessageAddedEvent(message=Message(role="user", content="instructions"))
    ]
    for index, (tool, args, result) in enumerate(calls):
        call = ChatCompletionMessageToolCall(
            id=f"call_{index}",
            type="function",
            function=Function(name=tool, arguments=json.dumps(args)),
        )
        events.append(
            MessageAddedEvent(
                message=Message(role="assistant", content="", tool_calls=[call])
            )
        )
        inp, out = usage[index]
        events.append(TokenUsageEvent(input_tokens=inp, output_tokens=out))
        events.append(ToolCallStartedEvent(tool_call=call))
        if result is not None:
            tool_result = CallToolResult(
                content=[TextContent(type="text", text=result.text)],
                structuredContent=result.envelope,
                isError=not result.ok,
            )
        else:
            tool_result = CallToolResult(
                content=[TextContent(type="text", text="Error: invalid arguments")],
                isError=True,
            )
        events.append(ToolCallCompletedEvent(tool_call_id=call.id, result=tool_result))
        events.append(
            MessageAddedEvent(
                message=Message(
                    role="tool",
                    content=[{"type": "text", "text": "..."}],
                    tool_call_id=call.id,
                )
            )
        )
    if final_text is not None:
        events.append(
            MessageAddedEvent(message=Message(role="assistant", content=final_text))
        )
        inp, out = usage[len(calls)]
        events.append(TokenUsageEvent(input_tokens=inp, output_tokens=out))
    return Transcript(run_id="test", events=events)
