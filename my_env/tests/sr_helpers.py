"""Shared helpers for the system-response (manifest v2) tool and task tests.

Builds a small SYNTHETIC v2 bundle in a temporary directory. Nothing here is evidence:
IDs follow the real numbering and naming conventions, but every title, owner, value and
text is a placeholder. The real ``bundles/system_response`` bundle is never loaded by
these tests.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from environment.incident.episode import EpisodeConfig

SERIES_START = datetime(2019, 8, 9, 15, 40, tzinfo=UTC)  # 16:40 BST
SERIES_ROWS = 1500
BST = "+01:00"
SR_TOOLS = (
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

# doc_id -> (category, title, owner, lines, extra manifest fields)
DOCS: dict[str, tuple[str, str, str, int, dict[str, Any]]] = {
    "R01": (
        "measurement_data",
        "Synthetic frequency record",
        "Synthetic System Operator (SO)",
        10,
        {},
    ),
    "R03": (
        "network_records",
        "Synthetic transmission protection record",
        "Synthetic Transmission Owner (TO)",
        20,
        {},
    ),
    "R07": (
        "demand_records",
        "Synthetic demand disconnection record",
        "Synthetic System Operator (SO)",
        15,
        {},
    ),
    "S05": (
        "network_records",
        "Synthetic relay and reconnection returns",
        "Synthetic DNO A",
        12,
        {"access": "data_return"},
    ),
    "S06": (
        "generator_records",
        "Synthetic distributed generation returns",
        "Synthetic distribution network operators",
        12,
        {"keywords": ["embedded generation"]},
    ),
    "S12": (
        "engineering_analysis",
        "Synthetic engineering analysis records",
        "Synthetic System Operator (SO)",
        18,
        {"party_aliases": ["the system operator"]},
    ),
}
CSV_NAME = "frequency.csv"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def series_csv(rows: int = SERIES_ROWS) -> str:
    lines = ["timestamp,frequency_hz"]
    for i in range(rows):
        when = (SERIES_START + timedelta(seconds=i)).astimezone(
            datetime.fromisoformat("2019-08-09T00:00:00+01:00").tzinfo
        )
        value = 50.0 - 0.001 * (i % 700)
        lines.append(f"{when.isoformat()},{value:.3f}")
    return "\n".join(lines) + "\n"


def doc_text(doc_id: str, title: str, n_lines: int) -> str:
    lines = [
        f"DOCUMENT {doc_id} — {title}",
        "STATUS: SYNTHETIC TEST FIXTURE - NOT EVIDENCE",
    ]
    lines += [f"{doc_id} placeholder line {i}" for i in range(3, n_lines + 1)]
    return "\n".join(lines) + "\n"


def _utc(seconds_after_1540: float) -> str:
    when = SERIES_START + timedelta(seconds=seconds_after_1540)
    text = when.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return text


def asset_rows() -> dict[str, list[dict[str, Any]]]:
    esw = []
    for i, (offset, signal, value, text) in enumerate(
        [
            (753.49, "protection operation", None, "Synthetic fault inception"),
            (753.56, "protection operation", 70, "Synthetic clearance at end A"),
            (753.564, "protection operation", 74, "Synthetic clearance at end B"),
            (773.5, "circuit state", "closed", "Synthetic reclose"),
            (2000.0, "circuit state", "closed", None),
        ],
        1,
    ):
        esw.append(
            {
                "event_id": f"ESW-{i:04d}",
                "evidence_id": "R03",
                "asset_id": "ESW-400",
                "recorded_time": f"T+{offset:.3f} s",
                "clock_basis": "synthetic relay clock (BST, UTC+01:00)",
                "index_time_utc": _utc(offset),
                "index_uncertainty_s": 0.5,
                "signal": signal,
                "value": value,
                "unit": "ms" if isinstance(value, int) else None,
                "text": text,
                "value_status": "reported",
            }
        )
    plant = []
    for signal, evidence_id, unit_no in (
        ("T_PLANT-1 B1610 MWh", "R02", 1),
        ("T_PLANT-2 B1610 MWh", "R05", 2),
    ):
        for i in range(230):
            plant.append(
                {
                    "event_id": f"PLANT-{unit_no}-{i:04d}",
                    "evidence_id": evidence_id,
                    "asset_id": "PLANT-A",
                    "recorded_time": f"SP{30 + i // 60} row {i}",
                    "clock_basis": "settlement period (UK local clock)",
                    "index_time_utc": _utc(10.0 * i),
                    "index_uncertainty_s": 900,
                    "signal": signal,
                    "value": round(100.0 + unit_no + i * 0.5, 3),
                    "unit": "MWh",
                    "text": None,
                    "value_status": "measured",
                }
            )
    dno = [
        {
            "event_id": "DNO-A-0001",
            "evidence_id": "S05",
            "asset_id": "DNO-A",
            "recorded_time": "16:53:49",
            "clock_basis": "BST (UTC+01:00)",
            "index_time_utc": _utc(829.0),
            "index_uncertainty_s": 1,
            "signal": "demand disconnected",
            "value": 12.5,
            "unit": "MW",
            "text": "Synthetic relay stage 1",
            "value_status": "reported",
        }
    ]
    return {"ESW-400": esw, "PLANT-A": plant, "DNO-A": dno}


def control_rows() -> dict[str, list[dict[str, Any]]]:
    so = []
    for i, (offset, evidence_id, sender, receiver, channel, text) in enumerate(
        [
            (760.0, "S07", "SO", "TO", "phone", "Synthetic call one"),
            (1080.0, "R08", "SO", "DNO A", "phone", "Synthetic call | with a bar"),
            (1080.0, "R08", "SO", "DNO B", None, "Synthetic call\nwith a break"),
            (1500.0, "S07", None, None, "log", "  Synthetic padded entry"),
            (2100.0, "S07", "SO", "DNO A", "phone", "Synthetic restoration call"),
            (3600.0, "R08", "SO", "all", "email", "Synthetic late entry"),
        ],
        1,
    ):
        so.append(
            {
                "entry_id": f"SO-{i:03d}",
                "evidence_id": evidence_id,
                "room_id": "SO-CONTROL",
                "recorded_time": f"synthetic minute {int(offset // 60)}",
                "clock_basis": "BST (UTC+01:00), minute resolution",
                "index_time_utc": _utc(offset),
                "index_uncertainty_s": 60,
                "from": sender,
                "to": receiver,
                "channel": channel,
                "text": text,
                "value_status": "reported",
            }
        )
    dno = [
        {
            "entry_id": "DNO-A-E1",
            "evidence_id": "S05",
            "room_id": "DNO-A",
            "recorded_time": "17:10",
            "clock_basis": "BST (UTC+01:00)",
            "index_time_utc": _utc(1800.0),
            "index_uncertainty_s": 60,
            "from": "DNO A",
            "to": "SO",
            "channel": "phone",
            "text": "Synthetic reconnection report",
            "value_status": "reported",
        }
    ]
    return {"SO-CONTROL": so, "DNO-A": dno}


def witness_cards() -> dict[str, dict[str, Any]]:
    return {
        "so-engineer": {
            "persona_id": "so-engineer",
            "role": "System operator control engineer",
            "organisation": "Synthetic System Operator",
            "evidence_id": "S09",
            "unknown_response": "Not known: that is outside what I can speak to.",
            "blocks": [
                {
                    "response_id": "S09-SO-01",
                    "topics": ["frequency containment", "response holding"],
                    "response_text": "Synthetic answer about containment.",
                },
                {
                    "response_id": "S09-SO-02",
                    "topics": ["demand restoration", "restoration instructions"],
                    "response_text": "Synthetic answer about restoration.",
                },
                {
                    "response_id": "S09-SO-03",
                    "topics": ["frequency recovery", "restoration timing"],
                    "response_text": "Synthetic answer about recovery.",
                },
            ],
        },
        "dno-engineer": {
            "persona_id": "dno-engineer",
            "role": "DNO control engineer",
            "organisation": "Synthetic DNO A",
            "evidence_id": "S09",
            "unknown_response": "Not held by me.",
            "status": "STATUS: SYNTHETIC TEST CARD - NOT EVIDENCE",
            "blocks": [
                {
                    "response_id": "S09-DNO-01",
                    "topics": ["relay operation"],
                    "response_text": "Synthetic answer about relays.",
                }
            ],
        },
    }


def data_returns() -> list[dict[str, Any]]:
    return [
        {
            "party": "Synthetic DNO A",
            "data_type": "relay returns",
            "status": "available",
            "evidence_id": "S05",
            "message": "Returned as held; the return is incomplete.",
        },
        {
            "party": "Synthetic DNO A",
            "data_type": "relay timing logs",
            "status": "not_held",
            "message": "Per-relay timing logs are not held.",
        },
        {
            "party": "Synthetic Generator B",
            "data_type": "control system logs",
            "status": "refused",
            "message": "Refused: the operator declined to supply raw control logs.",
        },
    ]


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows
    )


def make_sr_bundle(
    root: Path,
    *,
    version: str = "2.0.0-test",
    mutate: Callable[[dict[str, Any], Path], None] | None = None,
) -> Path:
    """Write the synthetic v2 bundle under ``root/bundle`` and return its path.

    ``mutate(manifest, bundle)`` may edit the manifest (and files) before hashing.
    """
    bundle = root / "bundle"
    documents = []
    for doc_id, (category, title, owner, n_lines, extra) in DOCS.items():
        (bundle / doc_id).mkdir(parents=True)
        text_rel = f"{doc_id}/{doc_id}.txt"
        (bundle / text_rel).write_text(
            doc_text(doc_id, title, n_lines), encoding="utf-8"
        )
        artifacts: list[dict[str, Any]] = [
            {"file": text_rel, "media_type": "text/plain", "description": "Text."}
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
                        "first": "2019-08-09T16:40:00+01:00",
                        "last": (SERIES_START + timedelta(seconds=SERIES_ROWS - 1))
                        .astimezone(
                            datetime.fromisoformat("2019-08-09T00:00:00+01:00").tzinfo
                        )
                        .isoformat(),
                        "rows": SERIES_ROWS,
                        "interval_s": 1,
                    },
                }
            )
        documents.append(
            {
                "doc_id": doc_id,
                "title": title,
                "owner": owner,
                "date": "2019-08-09",
                "category": category,
                "text_file": text_rel,
                "artifacts": artifacts,
                "sha256": {},
                **extra,
            }
        )

    asset_meta = {
        "ESW-400": ("Synthetic circuit log", "Synthetic TO", ["R03"]),
        "PLANT-A": (
            "Synthetic plant metering",
            "Synthetic settlement body",
            ["R02", "R05"],
        ),
        "DNO-A": ("Synthetic DNO group log", "Synthetic DNO A", ["S05"]),
    }
    signals = {
        "ESW-400": ["protection operation", "circuit state"],
        "PLANT-A": ["T_PLANT-1 B1610 MWh", "T_PLANT-2 B1610 MWh"],
        "DNO-A": ["demand disconnected"],
    }
    asset_logs = []
    for asset_id, rows in asset_rows().items():
        rel = f"logs/assets/{asset_id}.jsonl"
        (bundle / rel).parent.mkdir(parents=True, exist_ok=True)
        (bundle / rel).write_text(_jsonl(rows), encoding="utf-8")
        title, owner, evidence_ids = asset_meta[asset_id]
        asset_logs.append(
            {
                "asset_id": asset_id,
                "title": title,
                "owner": owner,
                "signals": signals[asset_id],
                "clock_note": "Synthetic clock note.",
                "evidence_ids": evidence_ids,
                "file": rel,
                "sha256": "",
                "status": "STATUS: SYNTHETIC TEST LOG - NOT EVIDENCE",
            }
        )
    control_meta = {
        "SO-CONTROL": ("Synthetic control room log", "Synthetic SO", ["S07", "R08"]),
        "DNO-A": ("Synthetic DNO control log", "Synthetic DNO A", ["S05"]),
    }
    control_logs = []
    for room_id, rows in control_rows().items():
        rel = f"logs/control/{room_id}.jsonl"
        (bundle / rel).parent.mkdir(parents=True, exist_ok=True)
        (bundle / rel).write_text(_jsonl(rows), encoding="utf-8")
        title, owner, evidence_ids = control_meta[room_id]
        control_logs.append(
            {
                "room_id": room_id,
                "title": title,
                "owner": owner,
                "evidence_ids": evidence_ids,
                "file": rel,
                "sha256": "",
            }
        )
    witnesses = []
    for persona_id, card in witness_cards().items():
        rel = f"witnesses/{persona_id}.json"
        (bundle / rel).parent.mkdir(parents=True, exist_ok=True)
        (bundle / rel).write_text(
            json.dumps(card, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        witnesses.append(
            {
                "persona_id": persona_id,
                "role": card["role"],
                "organisation": card["organisation"],
                "evidence_id": card["evidence_id"],
                "file": rel,
                "sha256": "",
            }
        )
    manifest: dict[str, Any] = {
        "manifest_version": 2,
        "bundle_id": "synthetic-system-response",
        "bundle_version": version,
        "documents": documents,
        "asset_logs": asset_logs,
        "control_logs": control_logs,
        "witnesses": witnesses,
        "data_returns": data_returns(),
    }
    if mutate is not None:
        mutate(manifest, bundle)
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2))
    rehash(bundle)
    return bundle


def rehash(bundle: Path) -> None:
    """Recompute every hash in the manifest (after an intended edit)."""
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text())
    for doc in manifest["documents"]:
        doc["sha256"] = {
            a["file"]: sha256((bundle / a["file"]).read_bytes())
            for a in doc["artifacts"]
        }
    for section in ("asset_logs", "control_logs", "witnesses"):
        for entry in manifest.get(section, []):
            target = bundle / entry["file"]
            if target.is_file():
                entry["sha256"] = sha256(target.read_bytes())
    path.write_text(json.dumps(manifest, indent=2))


def edit_manifest(bundle: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text())
    mutate(manifest)
    path.write_text(json.dumps(manifest, indent=2))


def sr_config(root: Path, bundle: Path, **overrides: Any) -> EpisodeConfig:
    values: dict[str, Any] = dict(
        episode_dir=root / "root_data" / "episode",
        evidence_dir=root / "workdir" / "evidence",
        scratch_dir=root / "workdir" / "scratch",
        bundle_dir=bundle,
        python_executable=sys.executable,
        python_timeout_s=20,
        max_tool_calls=150,
        tool_profile="system_response",
    )
    values.update(overrides)
    return EpisodeConfig(**values)


def sr_submission(**overrides: Any) -> dict[str, Any]:
    submission: dict[str, Any] = {
        "schema_version": "3.0",
        "variant_id": "baseline",
        "report": {
            "executive_summary": "Synthetic summary referring to [F01] and [F02].",
            "sections": [{"heading": "Chronology", "body": "See [F01, F02, F03]."}],
        },
        "findings": [
            {
                "finding_id": "F01",
                "statement": "Synthetic event statement.",
                "status": "reported",
                "citations": [
                    {"evidence_id": "R03", "locator": "event:ESW-0001"},
                    {"evidence_id": "R03", "locator": "L3-L4"},
                ],
            },
            {
                "finding_id": "F02",
                "statement": "Synthetic control-room statement.",
                "status": "reported",
                "citations": [
                    {"evidence_id": "S07", "locator": "entry:SO-001"},
                    {"evidence_id": "S09", "locator": "response:S09-SO-02"},
                ],
            },
            {
                "finding_id": "F03",
                "statement": "Synthetic frequency statement.",
                "status": "observed",
                "citations": [
                    {
                        "evidence_id": "R01",
                        "locator": "time:2019-08-09T16:52:00+01:00/2019-08-09T16:53:00+01:00",
                    }
                ],
            },
        ],
    }
    submission.update(overrides)
    return submission
