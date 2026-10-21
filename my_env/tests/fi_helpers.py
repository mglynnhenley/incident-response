"""Shared helpers for the full-investigation (increment B) task tests.

Builds a small SYNTHETIC manifest-v2 bundle in a temporary directory: increment A's
synthetic bundle (``sr_helpers.make_sr_bundle``) plus placeholder records of the kinds
increment B adds (a rail fleet record, an essential-services record, an external
communications record, a compliance-process record only obtainable as a data return, a
rail asset log, a rail control room, two more witnesses, and data returns that are
supplied, not held or refused). Nothing here is evidence: the IDs follow the real
numbering, but every title, owner, value and text is a placeholder. The real
``bundles/full_investigation`` bundle is never loaded by these tests (it is built
separately and may not exist yet).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sr_helpers import BST, _jsonl, _utc, doc_text, make_sr_bundle, sr_config

from environment.incident.episode import EpisodeConfig

FI_BUNDLE_ID = "synthetic-full-investigation"

# doc_id -> (category, title, owner, lines, extra manifest fields)
FI_DOCS: dict[str, tuple[str, str, str, int, dict[str, Any]]] = {
    "S08": (
        "rail_records",
        "Synthetic rail fleet records",
        "Synthetic Train Operator (TOC)",
        16,
        {"keywords": ["fleet", "train"]},
    ),
    "S11": (
        "essential_services",
        "Synthetic essential services records",
        "Synthetic Resilience Forum",
        14,
        {},
    ),
    "R09": (
        "communications",
        "Synthetic external communications record",
        "Synthetic System Operator (SO)",
        12,
        {"keywords": ["public statements"]},
    ),
    "S10": (
        "compliance_records",
        "Synthetic compliance process records",
        "Synthetic Regulator",
        12,
        {"access": "data_return"},
    ),
}

FI_ASSET_ROWS: dict[str, list[dict[str, Any]]] = {
    "FLEET-A": [
        {
            "event_id": f"FLEET-A-{i:04d}",
            "evidence_id": "S08",
            "asset_id": "FLEET-A",
            "recorded_time": f"16:5{3 + i}:00",
            "clock_basis": f"BST (UTC{BST})",
            "index_time_utc": _utc(800.0 + 60 * i),
            "index_uncertainty_s": 60,
            "signal": "unit state",
            "value": state,
            "unit": None,
            "text": f"Synthetic unit event {i}",
            "value_status": "reported",
        }
        for i, state in enumerate(("stopped", "reset", "moving"), 1)
    ]
}

FI_CONTROL_ROWS: dict[str, list[dict[str, Any]]] = {
    "RAIL-CONTROL": [
        {
            "entry_id": f"RAIL-{i:03d}",
            "evidence_id": evidence_id,
            "room_id": "RAIL-CONTROL",
            "recorded_time": f"synthetic minute {minute}",
            "clock_basis": f"BST (UTC{BST}), minute resolution",
            "index_time_utc": _utc(60.0 * minute),
            "index_uncertainty_s": 60,
            "from": "Rail control",
            "to": "Train operator",
            "channel": "phone",
            "text": text,
            "value_status": "reported",
        }
        for i, (minute, evidence_id, text) in enumerate(
            (
                (14, "S08", "Synthetic report of stopped units"),
                (30, "R09", "Synthetic public notice"),
            ),
            1,
        )
    ]
}

FI_WITNESSES: dict[str, dict[str, Any]] = {
    "fleet-engineer": {
        "persona_id": "fleet-engineer",
        "role": "Train operator fleet engineer",
        "organisation": "Synthetic Train Operator",
        "evidence_id": "S09",
        "unknown_response": "Not known: that is outside what I can speak to.",
        "blocks": [
            {
                "response_id": "S09-FLEET-01",
                "topics": ["unit recovery", "reset procedure"],
                "response_text": "Synthetic answer about unit recovery.",
            },
            {
                "response_id": "S09-FLEET-02",
                "topics": ["fleet software"],
                "response_text": "Synthetic answer about software.",
            },
        ],
    },
    "comms-lead": {
        "persona_id": "comms-lead",
        "role": "System operator communications lead",
        "organisation": "Synthetic System Operator",
        "evidence_id": "S09",
        "unknown_response": "Not held by me.",
        "blocks": [
            {
                "response_id": "S09-COMMS-01",
                "topics": ["public statements", "statement timing"],
                "response_text": "Synthetic answer about statements.",
            }
        ],
    },
}

FI_DATA_RETURNS: list[dict[str, Any]] = [
    {
        "party": "Synthetic Regulator",
        "data_type": "compliance process records",
        "status": "available",
        "evidence_id": "S10",
        "message": "Returned as held.",
    },
    {
        "party": "Synthetic Train Operator",
        "data_type": "train running records",
        "status": "not_held",
        "message": "Train running records are not held in this evidence pack.",
    },
    {
        "party": "Synthetic Generator B",
        "data_type": "compliance test records",
        "status": "refused",
        "message": "Refused: the operator declined to supply test records.",
    },
]


def _add_full_investigation(manifest: dict[str, Any], bundle: Path) -> None:
    """``make_sr_bundle`` mutation: increment B's placeholder records."""
    manifest["bundle_id"] = FI_BUNDLE_ID
    for doc_id, (category, title, owner, n_lines, extra) in FI_DOCS.items():
        (bundle / doc_id).mkdir(parents=True)
        text_rel = f"{doc_id}/{doc_id}.txt"
        (bundle / text_rel).write_text(
            doc_text(doc_id, title, n_lines), encoding="utf-8"
        )
        manifest["documents"].append(
            {
                "doc_id": doc_id,
                "title": title,
                "owner": owner,
                "date": "2019-08-09",
                "category": category,
                "text_file": text_rel,
                "artifacts": [
                    {
                        "file": text_rel,
                        "media_type": "text/plain",
                        "description": "Text.",
                    }
                ],
                "sha256": {},
                **extra,
            }
        )
    for asset_id, rows in FI_ASSET_ROWS.items():
        rel = f"logs/assets/{asset_id}.jsonl"
        (bundle / rel).write_text(_jsonl(rows), encoding="utf-8")
        manifest["asset_logs"].append(
            {
                "asset_id": asset_id,
                "title": "Synthetic fleet event log",
                "owner": "Synthetic Train Operator",
                "signals": ["unit state"],
                "clock_note": "Synthetic clock note.",
                "evidence_ids": ["S08"],
                "file": rel,
                "sha256": "",
            }
        )
    for room_id, rows in FI_CONTROL_ROWS.items():
        rel = f"logs/control/{room_id}.jsonl"
        (bundle / rel).write_text(_jsonl(rows), encoding="utf-8")
        manifest["control_logs"].append(
            {
                "room_id": room_id,
                "title": "Synthetic rail control log",
                "owner": "Synthetic Rail Infrastructure Manager",
                "evidence_ids": ["S08", "R09"],
                "file": rel,
                "sha256": "",
            }
        )
    for persona_id, card in FI_WITNESSES.items():
        rel = f"witnesses/{persona_id}.json"
        (bundle / rel).write_text(
            json.dumps(card, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        manifest["witnesses"].append(
            {
                "persona_id": persona_id,
                "role": card["role"],
                "organisation": card["organisation"],
                "evidence_id": card["evidence_id"],
                "file": rel,
                "sha256": "",
            }
        )
    manifest["data_returns"].extend(FI_DATA_RETURNS)


def make_fi_bundle(
    root: Path,
    *,
    version: str = "3.0.0-test",
    mutate: Callable[[dict[str, Any], Path], None] | None = None,
) -> Path:
    """Write the synthetic full-investigation bundle under ``root/bundle``; its path."""

    def build(manifest: dict[str, Any], bundle: Path) -> None:
        _add_full_investigation(manifest, bundle)
        if mutate is not None:
            mutate(manifest, bundle)

    return make_sr_bundle(root, version=version, mutate=build)


def fi_config(root: Path, bundle: Path, **overrides: Any) -> EpisodeConfig:
    """An episode configuration on ``bundle`` with the task's limits (150 calls)."""
    return sr_config(root, bundle, **overrides)


def fi_submission(**overrides: Any) -> dict[str, Any]:
    """A valid submission citing increment A's and increment B's synthetic records, with
    the pilot plan's report sections."""
    submission: dict[str, Any] = {
        "schema_version": "3.0",
        "variant_id": "baseline",
        "report": {
            "executive_summary": "Synthetic summary referring to [F01] and [F04].",
            "sections": [
                {"heading": "Chronology", "body": "See [F01, F03]."},
                {"heading": "Findings", "body": "See [F01, F02]."},
                {"heading": "Consequences", "body": "See [F04, F05]."},
                {"heading": "Uncertainties", "body": "See [F06]."},
                {"heading": "Recommendations", "body": "Act on [F04]."},
                {"heading": "Further evidence requests", "body": "Ask about [F06]."},
            ],
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
            {
                "finding_id": "F04",
                "statement": "Synthetic rail statement.",
                "status": "reported",
                "citations": [
                    {"evidence_id": "S08", "locator": "L3-L5"},
                    {"evidence_id": "S08", "locator": "event:FLEET-A-0001"},
                    {"evidence_id": "S08", "locator": "entry:RAIL-001"},
                    {"evidence_id": "S09", "locator": "response:S09-FLEET-01"},
                ],
            },
            {
                "finding_id": "F05",
                "statement": "Synthetic communications statement.",
                "status": "reported",
                "citations": [
                    {"evidence_id": "R09", "locator": "L3"},
                    {"evidence_id": "R09", "locator": "entry:RAIL-002"},
                    {"evidence_id": "S09", "locator": "response:S09-COMMS-01"},
                ],
            },
            {
                "finding_id": "F06",
                "statement": "Synthetic compliance statement.",
                "status": "unknown",
                "citations": [{"evidence_id": "S10", "locator": "L3-L4"}],
            },
        ],
    }
    submission.update(overrides)
    return submission
