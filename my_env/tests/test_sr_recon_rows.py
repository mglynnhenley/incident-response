"""Reconstruction track: asset/control row fragments and the data-return registry.

The fragments are parsed with the runtime's own manifest-v2 parsers after the integration
step's transformation (drop ``kind`` and ``provenance``), so a schema drift fails here first.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from environment.incident.logs import parse_asset_log, parse_control_log
from environment.incident.returns import DataReturnRegistry

ENV_ROOT = Path(__file__).resolve().parents[1]
ROWS = ENV_ROOT / "builder" / "system_response" / "rows"
SR = ENV_ROOT / "src" / "environment" / "incident" / "bundles" / "system_response"
FRAGMENTS = {
    "recon_r03.jsonl": ("R03", "asset"),
    "recon_s01.jsonl": ("S01", "asset"),
    "recon_s03.jsonl": ("S03", "asset"),
    "recon_s07.jsonl": ("S07", "control"),
    "recon_r08.jsonl": ("R08", "control"),
}
DOCS = {"R01", "R03", "R08", "R10", "S01", "S03", "S04", "S05", "S06", "S07", "S12"}


def load(name: str) -> list[dict]:
    return [json.loads(line) for line in (ROWS / name).read_text("utf-8").splitlines()]


def doc_lines(doc_id: str) -> list[str]:
    return (SR / doc_id / f"{doc_id}.txt").read_text("utf-8").split("\n")[:-1]


def agent_rows(rows: list[dict]) -> bytes:
    stripped = [
        {k: v for k, v in r.items() if k not in ("kind", "provenance")} for r in rows
    ]
    return "".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in stripped
    ).encode()


@pytest.mark.parametrize("name", sorted(FRAGMENTS))
def test_fragment_lines_are_canonical(name: str) -> None:
    for line in (ROWS / name).read_text("utf-8").splitlines():
        assert line == json.dumps(json.loads(line), ensure_ascii=False, sort_keys=True)


@pytest.mark.parametrize("name", sorted(FRAGMENTS))
def test_rows_cite_document_lines_they_restate(name: str) -> None:
    doc_id, kind = FRAGMENTS[name]
    text_lines = doc_lines(doc_id)
    for row in load(name):
        assert row["kind"] == kind and row["evidence_id"] == doc_id
        prov = row["provenance"]
        a, b = (int(x) for x in prov["doc_lines"][1:].split("-L"))
        cited = " ".join(" ".join(text_lines[a - 1 : b]).split())
        if not row["text"].startswith("ESO "):
            assert row["text"] == cited
        assert prov["sources"], row
        assert row["value_status"] in {"reported", "estimated", "measured", "modelled"}


def test_ids_unique_across_fragments() -> None:
    ids = [r.get("event_id") or r.get("entry_id") for n in FRAGMENTS for r in load(n)]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", i) for i in ids)


@pytest.mark.parametrize("asset_id", ["ESW-400", "HORNSEA-ONE", "LITTLE-BARFORD"])
def test_asset_rows_parse_with_runtime(asset_id: str) -> None:
    rows = [r for n, (d, k) in FRAGMENTS.items() if k == "asset" for r in load(n)]
    rows = [r for r in rows if r["asset_id"] == asset_id]
    assert rows
    data = agent_rows(rows)
    entry = {
        "asset_id": asset_id,
        "title": "test",
        "owner": "test",
        "signals": sorted({r["signal"] for r in rows}),
        "clock_note": "test",
        "evidence_ids": sorted({r["evidence_id"] for r in rows}),
        "file": f"logs/assets/{asset_id}.jsonl",
    }
    log = parse_asset_log(entry, data, hashlib.sha256(data).hexdigest(), "test")
    assert len(log.rows) == len(rows)


def test_control_rows_parse_with_runtime() -> None:
    rows = load("recon_s07.jsonl") + load("recon_r08.jsonl")
    data = agent_rows(rows)
    entry = {
        "room_id": "ESO-ENCC",
        "title": "test",
        "owner": "test",
        "evidence_ids": ["R08", "S07"],
        "file": "logs/control/ESO-ENCC.jsonl",
    }
    log = parse_control_log(entry, data, hashlib.sha256(data).hexdigest(), "test")
    assert len(log.rows) == len(rows)
    assert {r["room_id"] for r in rows} == {"ESO-ENCC"}


def test_s03_index_is_datum_plus_offset() -> None:
    datum = datetime(2019, 8, 9, 15, 52, 34, tzinfo=UTC)
    for row in load("recon_s03.jsonl"):
        index = datetime.fromisoformat(row["index_time_utc"].replace("Z", "+00:00"))
        assert (
            abs((index - datum - timedelta(seconds=row["value"])).total_seconds())
            < 1e-3
        )
        assert row["index_uncertainty_s"] >= 0.5
        assert row["recorded_time"].startswith("T")
        assert "16:52:34 +/- 0.5 s" in row["clock_basis"]


def test_s01_rows_keep_utc_rendering() -> None:
    for row in load("recon_s01.jsonl"):
        assert "Z" in row["recorded_time"]
        assert "local time" in row["clock_basis"]
    deload = next(r for r in load("recon_s01.jsonl") if r["event_id"] == "S01-EV09")
    assert deload["index_time_utc"] == "2019-08-09T15:52:33.728Z"


def test_r03_and_control_indices_are_bst_minus_one_hour() -> None:
    fault = next(r for r in load("recon_r03.jsonl") if r["event_id"] == "R03-C1")
    assert fault["recorded_time"] == "2019-08-09T16:52:33.490+01:00"
    assert fault["index_time_utc"] == "2019-08-09T15:52:33.490Z"
    first = next(r for r in load("recon_s07.jsonl") if r["entry_id"] == "S07-E01")
    assert (first["recorded_time"], first["index_time_utc"]) == (
        "16:52:26",
        "2019-08-09T15:52:26.000Z",
    )
    call = next(r for r in load("recon_r08.jsonl") if r["entry_id"] == "R08-C28")
    assert call["index_time_utc"] == "2019-08-09T16:32:00.000Z"
    assert (call["from"], call["to"]) == ("ESO-ENCC", "NGET-TNCC")


def test_r08_rows_cover_every_call_and_summary_note() -> None:
    rows = load("recon_r08.jsonl")
    assert len([r for r in rows if r["entry_id"].startswith("R08-C")]) == 43
    assert len([r for r in rows if r["entry_id"].startswith("R08-N")]) == 4


def test_s07_does_not_duplicate_boalf() -> None:
    for row in load("recon_s07.jsonl"):
        assert "BOALF" not in row["text"] and not row["entry_id"].startswith("R06")


# --------------------------------------------------------------------------- registry


def test_data_return_registry_parses_with_runtime() -> None:
    raw = json.loads((ROWS / "data_returns.json").read_text("utf-8"))
    registry = DataReturnRegistry.parse(raw, DOCS)
    assert len(registry) == len(raw)
    statuses = {(e["party"], e["data_type"]): e["status"] for e in raw}
    for key in (
        ("METEOGROUP", "lightning_stroke_records"),
        ("ESO", "pmu_wams_traces"),
        ("DNO", "real_time_distributed_generation_telemetry"),
        ("ELEXON", "physical_notifications_event_window"),
    ):
        assert statuses[key] == "not_held"
    available = {e["evidence_id"] for e in raw if e["status"] == "available"}
    assert {"S05", "S06", "S07", "S12", "R08"} <= available
    assert (
        registry.lookup("dno", "Embedded_Generation_Loss_Returns").evidence_id == "S06"
    )
    for entry in raw:
        if entry["status"] != "available":
            # Absence from this pack only, never a claim that the record does not exist.
            assert entry["message"].startswith("Not held in this evidence pack: ")
            assert "were not published" not in entry["message"]
