"""Integrated system-response bundle (manifest v2): build, global checks and the real tools.

Unlike the tools track's tests (synthetic bundle), these load the real
``bundles/system_response`` bundle written by ``builder/system_response/build_bundle.py``.
They need no ``.context`` input: the integration step reads only the track outputs.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from environment.incident.catalogue import Catalogue, CatalogueError
from environment.incident.episode import Episode, EpisodeConfig
from environment.incident.paths import (
    DEFAULT_BUNDLE_DIR,
    SYSTEM_RESPONSE_BUNDLE_DIR,
    SYSTEM_RESPONSE_PRIVATE_DIR,
)
from environment.incident.replay import replay_episode

ENV_ROOT = Path(__file__).resolve().parents[1]
SR_BUILDER = ENV_ROOT / "builder" / "system_response"
sys.path.insert(0, str(SR_BUILDER))

import build_bundle as bb  # noqa: E402
import verify_bundle as vb  # noqa: E402

MANIFEST = json.loads((SYSTEM_RESPONSE_BUNDLE_DIR / "manifest.json").read_text("utf-8"))
PROVENANCE = json.loads(
    (SYSTEM_RESPONSE_PRIVATE_DIR / "provenance.json").read_text("utf-8")
)
DOC_IDS = [
    "R01",
    "R02",
    "R03",
    "R04",
    "R05",
    "R06",
    "R07",
    "R08",
    "R10",
    "S01",
    "S03",
    "S04",
    "S05",
    "S06",
    "S07",
    "S12",
]
# The settlement day 9 August 2019 (BST) starts at 2019-08-08T23:00Z.
DAY = {"start": "2019-08-08T22:00:00Z", "end": "2019-08-10T00:00:00Z"}


def _fragment_rows() -> list[dict[str, Any]]:
    rows = []
    for name in sorted(bb.ROW_FRAGMENTS):
        for line in (bb.ROWS_DIR / name).read_text("utf-8").splitlines():
            rows.append(json.loads(line))
    return rows


def _log_rows(entry: dict[str, Any]) -> list[dict[str, Any]]:
    text = (SYSTEM_RESPONSE_BUNDLE_DIR / entry["file"]).read_text("utf-8")
    return [json.loads(line) for line in text.splitlines()]


def _copy_bundle(tmp_path: Path) -> tuple[Path, Path]:
    bundle = tmp_path / "bundle"
    shutil.copytree(SYSTEM_RESPONSE_BUNDLE_DIR, bundle)
    provenance = tmp_path / "provenance.json"
    shutil.copy(SYSTEM_RESPONSE_PRIVATE_DIR / "provenance.json", provenance)
    return bundle, provenance


def _config(tmp_path: Path, **extra: Any) -> EpisodeConfig:
    return EpisodeConfig(
        episode_dir=tmp_path / "root_data" / "episode",
        evidence_dir=tmp_path / "workdir" / "evidence",
        scratch_dir=tmp_path / "workdir" / "scratch",
        bundle_dir=SYSTEM_RESPONSE_BUNDLE_DIR,
        python_executable=sys.executable,
        python_timeout_s=20,
        max_tool_calls=150,
        tool_profile="system_response",
        **extra,
    )


# -- build ---------------------------------------------------------------------------------
def test_integration_build_is_byte_identical_and_deterministic():
    first = bb.build()
    assert first == bb.build()
    for path, data in first.items():
        assert path.read_bytes() == data, bb.rel(path)
    assert bb.owned_stale_files(first) == []


def test_global_checks_pass():
    report = vb.global_checks()
    assert report.ok, "\n".join(report.failures)
    assert report.counts["files hashed"] == len(vb.manifest_files(MANIFEST))
    assert report.counts["documents with full provenance coverage"] == len(DOC_IDS)
    assert report.counts["witness blocks with provenance"] == 48


def test_bundle_stats():
    stats = vb.bundle_stats()
    assert stats["bundle"] == f"{bb.BUNDLE_ID} {bb.BUNDLE_VERSION}"
    assert stats["documents"] == 16 and stats["listed_documents"] == 14
    assert stats["asset_logs"] == {
        "ESW-400": 8,
        "HORNSEA-ONE": 312,
        "LITTLE-BARFORD": 180,
    }
    assert stats["control_logs"] == {"ESO-ENCC": 277}
    assert sum(stats["witnesses"].values()) == 48 and len(stats["witnesses"]) == 5
    assert stats["data_returns"] == {"available": 9, "not_held": 8}


# -- manifest --------------------------------------------------------------------------------
def test_manifest_v2_shape():
    assert MANIFEST["manifest_version"] == 2
    assert list(MANIFEST) == [
        "manifest_version",
        "bundle_id",
        "bundle_version",
        "categories",
        "documents",
        "asset_logs",
        "control_logs",
        "witnesses",
        "data_returns",
    ]
    assert [d["doc_id"] for d in MANIFEST["documents"]] == DOC_IDS
    assert MANIFEST["categories"] == list(bb.CATEGORY_ORDER)
    for doc in MANIFEST["documents"]:
        assert doc["category"] == bb.CATEGORIES[doc["doc_id"]]
        assert doc["date"] == "2019-08-09"
        assert doc["label"] and doc["owner"] and doc["title"]
        assert set(doc["sha256"]) == {a["file"] for a in doc["artifacts"]}
    access = {d["doc_id"]: d.get("access", "catalogue") for d in MANIFEST["documents"]}
    assert [k for k, v in access.items() if v == "data_return"] == ["S05", "S06"]
    series = [
        (d["doc_id"], a["file"])
        for d in MANIFEST["documents"]
        for a in d["artifacts"]
        if a.get("timeseries")
    ]
    assert series == [
        ("R01", "R01/frequency_2019-08-09_1640-1745_BST.csv"),
        ("R07", "R07/R07_elexon_demand_outturn_summary_5min_20190809.csv"),
    ]


def test_mvp_documents_keep_their_mvp_metadata():
    mvp = json.loads((DEFAULT_BUNDLE_DIR / "manifest.json").read_text("utf-8"))
    ours = {d["doc_id"]: d for d in MANIFEST["documents"]}
    for doc in mvp["documents"]:
        mine = ours[doc["doc_id"]]
        for key in ("title", "owner", "date", "category", "text_file"):
            if doc["doc_id"] == "S01" and key not in ("title", "owner"):
                continue
            assert mine[key] == doc[key], (doc["doc_id"], key)
        if doc["doc_id"] != "S01":  # S01 carries the decision-19 clock line
            assert mine["sha256"] == doc["sha256"]


def test_every_log_and_card_entry_is_complete():
    for entry in MANIFEST["asset_logs"] + MANIFEST["control_logs"]:
        for key in ("title", "owner", "clock_note", "status", "source_note", "sha256"):
            assert entry[key], (entry["file"], key)
        assert entry["status"].startswith("STATUS: ")
        for eid in entry["evidence_ids"]:
            assert f"{eid} rows —" in entry["clock_note"]
            assert f"{eid}:" in entry["source_note"]
    for entry in MANIFEST["asset_logs"]:
        rows = _log_rows(entry)
        assert sorted({r["signal"] for r in rows}) == sorted(entry["signals"])
    real_logs = [
        e
        for e in MANIFEST["asset_logs"] + MANIFEST["control_logs"]
        if {"R02", "R06"} & set(e["evidence_ids"])
    ]
    assert real_logs
    for entry in real_logs:
        assert "Elexon BMRS open data licence" in entry["source_note"]
        assert "UTC" in entry["clock_note"]
    assert {w["evidence_id"] for w in MANIFEST["witnesses"]} == {"S09"}


# -- rows and cards ----------------------------------------------------------------------------
def test_every_fragment_row_appears_once_without_private_fields():
    fragment = {
        (r["kind"], r.get("event_id") or r.get("entry_id")): r for r in _fragment_rows()
    }
    merged = {}
    for section, kind, key in (
        ("asset_logs", "asset", "event_id"),
        ("control_logs", "control", "entry_id"),
    ):
        for entry in MANIFEST[section]:
            for row in _log_rows(entry):
                assert (kind, row[key]) not in merged
                merged[(kind, row[key])] = row
    assert set(merged) == set(fragment)
    for ident, row in merged.items():
        source = fragment[ident]
        assert row == {
            k: v for k, v in source.items() if k not in ("kind", "provenance")
        }
        ref = f"{'event' if ident[0] == 'asset' else 'entry'}:{ident[1]}"
        assert PROVENANCE["rows"][ref]["provenance"] == source["provenance"]


def test_rows_are_ordered_by_index_instant_then_id():
    for entry in MANIFEST["asset_logs"] + MANIFEST["control_logs"]:
        rows = _log_rows(entry)
        key = "event_id" if "asset_id" in entry else "entry_id"
        order = [(bb.parse_utc(r["index_time_utc"]), r[key]) for r in rows]
        assert order == sorted(order), entry["file"]
        text = (SYSTEM_RESPONSE_BUNDLE_DIR / entry["file"]).read_text("utf-8")
        for line, row in zip(text.splitlines(), rows, strict=True):
            assert line == json.dumps(row, ensure_ascii=False, sort_keys=True)


def test_witness_copies_are_the_source_cards_without_provenance():
    for entry in MANIFEST["witnesses"]:
        visible = json.loads((SYSTEM_RESPONSE_BUNDLE_DIR / entry["file"]).read_text())
        source = json.loads(
            (bb.WITNESS_SOURCE_DIR / f"{entry['persona_id']}.json").read_text()
        )
        assert visible["blocks"] == [
            {k: v for k, v in b.items() if k != "provenance"} for b in source["blocks"]
        ]
        assert {k: v for k, v in visible.items() if k != "blocks"} == {
            k: v for k, v in source.items() if k != "blocks"
        }
        private = PROVENANCE["witnesses"][entry["persona_id"]]["blocks"]
        for block in source["blocks"]:
            assert private[block["response_id"]]["sources"] == block["provenance"]


def test_provenance_merges_every_part():
    assert set(PROVENANCE["parts"]) == {"real", "digitise", "recon"}
    for part in PROVENANCE["parts"].values():
        data = (ENV_ROOT / part["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == part["sha256"]
    tracks = Counter(doc["track"] for doc in PROVENANCE["documents"].values())
    assert tracks == {"recon": 11, "real": 4, "digitise": 1}
    for source in ("ESO", "APP"):
        assert set(PROVENANCE["sources"][source]["parts"]) == {
            "real",
            "digitise",
            "recon",
        }
    assert len(PROVENANCE["data_returns"]["not_held_basis"]) == 8


# -- the runtime serves the real bundle ----------------------------------------------------------
def test_runtime_catalogue_loads_the_real_bundle():
    catalogue = Catalogue.load(SYSTEM_RESPONSE_BUNDLE_DIR)
    catalogue.verify()
    assert catalogue.is_v2 and catalogue.bundle_id == bb.BUNDLE_ID
    assert catalogue.listed_ids() == [d for d in DOC_IDS if d not in ("S05", "S06")]
    sources = catalogue.sources
    assert sorted(sources.asset_logs) == ["ESW-400", "HORNSEA-ONE", "LITTLE-BARFORD"]
    assert sorted(sources.control_logs) == ["ESO-ENCC"]
    assert len(sources.witnesses) == 5 and len(sources.data_returns) == 17
    assert len(sources.frequency) == 3900
    assert "S09" in catalogue.citable_ids()


def test_every_tool_on_the_real_bundle_and_replay(tmp_path: Path):
    ep = Episode(_config(tmp_path))
    meta = ep.reset()
    assert meta["manifest_version"] == 2 and len(meta["tool_names"]) == 9

    listing = ep.call("list_documents", {}).envelope
    assert listing["ok"]
    assert [d["doc_id"] for d in listing["data"]["documents"]] == [
        d for d in DOC_IDS if d not in ("S05", "S06")
    ]
    assert len(listing["data"]["data_returns"]) == 17

    by_party = ep.call(
        "request_document", {"party": "ESO", "description": "control room log"}
    ).envelope
    assert by_party["ok"] and by_party["evidence_ids"] == ["S07"]
    assert ep.call("request_document", {"doc_id": "S05"}).error_code == "UNKNOWN_ID"

    freq = ep.call(
        "query_frequency",
        {"start": "2019-08-09T16:53:49+01:00", "end": "2019-08-09T16:53:50+01:00"},
    ).envelope
    assert freq["ok"] and freq["evidence_ids"] == ["R01"]

    soe = ep.call(
        "query_asset_log",
        {"asset_id": "LITTLE-BARFORD", "signal": "sequence-of-events entry", **DAY},
    ).envelope
    assert soe["ok"] and soe["data"]["total_rows"] == 9
    hornsea = ep.call("query_asset_log", {"asset_id": "HORNSEA-ONE", **DAY}).envelope
    assert hornsea["data"]["total_rows"] == 312 and hornsea["next_cursor"]
    second = ep.call(
        "query_asset_log",
        {"asset_id": "HORNSEA-ONE", **DAY, "cursor": hornsea["next_cursor"]},
    ).envelope
    assert second["data"]["returned"] == 112 and second["next_cursor"] is None

    room = ep.call("query_control_log", {"room": "ESO-ENCC", **DAY}).envelope
    assert room["ok"] and room["evidence_ids"] == ["R06", "R08", "S07"]

    answer = ep.call(
        "interview_witness",
        {"persona_id": "eso-control-engineer", "question": "securing"},
    ).envelope
    assert answer["ok"] and answer["data"]["response_id"] == "S09-ESO-01"

    returned = ep.call(
        "request_data_return",
        {"party": "DNO", "data_type": "lfdd_disconnection_and_restoration_returns"},
    ).envelope
    assert returned["ok"] and returned["evidence_ids"] == ["S05"]
    refused = ep.call(
        "request_data_return",
        {"party": "METEOGROUP", "data_type": "lightning_stroke_records"},
    )
    assert refused.error_code == "NOT_HELD"

    event_id = soe["data"]["rows"][0]["event_id"]
    entry = next(r for r in room["data"]["rows"] if r["evidence_id"] == "R06")
    submission = {
        "schema_version": "3.0",
        "variant_id": "baseline",
        "report": {
            "executive_summary": "Integration smoke test [F01].",
            "sections": [{"heading": "Records", "body": "See [F01]."}],
        },
        "findings": [
            {
                "finding_id": "F01",
                "statement": "Integration smoke test of every citation kind.",
                "status": "reported",
                "citations": [
                    {"evidence_id": "S03", "locator": f"event:{event_id}"},
                    {"evidence_id": "R06", "locator": f"entry:{entry['entry_id']}"},
                    {"evidence_id": "S09", "locator": "response:S09-ESO-01"},
                    {"evidence_id": "R01", "locator": "time:2019-08-09T16:53:49+01:00"},
                    {"evidence_id": "S07", "locator": "L1-L4"},
                ],
            }
        ],
    }
    wrong = json.loads(json.dumps(submission))
    wrong["findings"][0]["citations"][0]["evidence_id"] = "R02"
    assert ep.call("submit_findings", {"submission": wrong}).error_code == (
        "VALIDATION_FAILED"
    )
    accepted = ep.call("submit_findings", {"submission": submission}).envelope
    assert accepted["ok"], accepted["error"]

    report = replay_episode(ep.config.episode_dir)
    assert report.ok, report.summary_text()


def test_task_pre_hook_loads_the_real_bundle(tmp_path: Path, monkeypatch):
    from karotte import EvaluationRunConfig

    import environment.tasks.gb_2019_system_response as task_module

    cfg = task_module.SystemResponseToolConfig(
        **_config(tmp_path).model_dump(exclude={"bundle_dir"})
    )
    assert cfg.bundle_dir == SYSTEM_RESPONSE_BUNDLE_DIR
    monkeypatch.setattr(
        task_module.GB2019SystemResponseTask, "episode_config", lambda self: cfg
    )
    run = EvaluationRunConfig(
        run_id="sr-bundle",
        task_id=task_module.TASK_ID,
        model="fake",
        use_fake_model=True,
        transcript_file=str(tmp_path / "out" / "transcript.json"),
    )
    meta = task_module.GB2019SystemResponseTask(run).pre_hook()
    manifest_sha = hashlib.sha256(
        (SYSTEM_RESPONSE_BUNDLE_DIR / "manifest.json").read_bytes()
    ).hexdigest()
    assert meta["manifest_version"] == 2
    assert meta["bundle_version"] == bb.BUNDLE_VERSION
    assert meta["bundle_sha256"] == manifest_sha == PROVENANCE["manifest_sha256"]


# -- the checks catch problems -------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("fault inception (blue phase to earth)", ["blue phase", "phase to earth"]),
        ("sequence of events: GT1B manual shutdown command", ["manual shutdown"]),
        ("about 931 MW of demand", ["931"]),
        ("1,878 MW", ["1,878"]),
        ("stage at 48.8 Hz", ["48.8"]),
        ("16:53:49 BST", ["16:53:49"]),
        ("time below 49 Hz was 33 s", ["33 s"]),
        ("turbine_speed_sensor_data", ["speed_sensor"]),
    ],
)
def test_landmark_patterns_flag_answers(text: str, expected: list[str]):
    assert vb.landmark_hits(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "System frequency record, 9 August 2019, 16:40-17:45 BST",
        "Weather observations, warnings and lightning records, 9 August 2019",
        "acceptanceTime 15:40-16:45 UTC",
        "settlement periods 9310 and 48.85 and 2931",
        "T_HOWAO-2 B1610 MWh",
    ],
)
def test_landmark_patterns_leave_neutral_metadata(text: str):
    assert vb.landmark_hits(text) == []


def test_tampered_or_unlisted_files_are_reported(tmp_path: Path):
    bundle, provenance = _copy_bundle(tmp_path)
    log = bundle / "logs" / "assets" / "ESW-400.jsonl"
    log.write_text(log.read_text("utf-8").replace("event", "evnt", 1), "utf-8")
    (bundle / "R05" / "notes.txt").write_text("stray\n", "utf-8")
    (bundle / "R05" / "chart.png").write_bytes(b"\x89PNG")
    report = vb.Report()
    manifest = vb.load_manifest(bundle)
    vb.check_files(bundle, manifest, json.loads(provenance.read_text()), report)
    text = "\n".join(report.failures)
    assert "logs/assets/ESW-400.jsonl: sha256 differs" in text
    assert "R05/notes.txt: not listed in the manifest" in text
    assert "R05/chart.png: file type not allowed" in text
    with pytest.raises(CatalogueError, match="sha256 mismatch"):
        Catalogue.load(bundle)


def test_private_fields_and_paths_are_reported(tmp_path: Path):
    bundle, _ = _copy_bundle(tmp_path)
    card = bundle / "witnesses" / "eso-control-engineer.json"
    data = json.loads(card.read_text("utf-8"))
    data["blocks"][0]["provenance"] = [{"source_id": "ESO", "quote": "x"}]
    card.write_text(json.dumps(data), "utf-8")
    text = bundle / "R10" / "R10.txt"
    text.write_text(text.read_text("utf-8") + "see .context/handoff\n", "utf-8")
    report = vb.Report()
    vb.check_private_fields(bundle, vb.load_manifest(bundle), report)
    joined = "\n".join(report.failures)
    assert "witnesses/eso-control-engineer.json: private field(s)" in joined
    assert "R10/R10.txt: contains private/builder text '.context'" in joined


def test_landmarks_in_metadata_are_reported(tmp_path: Path):
    bundle, _ = _copy_bundle(tmp_path)
    manifest = vb.load_manifest(bundle)
    manifest["documents"][2]["title"] = "Lightning strike caused the circuit trip"
    manifest["asset_logs"][0]["signals"].append("fault inception (blue phase to earth)")
    manifest["data_returns"][0]["message"] = "931 MW disconnected"
    report = vb.Report()
    hits = vb.check_landmarks(bundle, manifest, report)
    assert len(hits) == 3, hits
    (bundle / "S12" / "S12.txt").write_text("minimum 48.787 Hz\n", "utf-8")
    report = vb.Report()
    vb.check_landmarks(bundle, vb.load_manifest(bundle), report)
    assert any("S12/S12.txt: states frequency landmark" in f for f in report.failures)


def test_missing_row_or_block_provenance_is_reported(tmp_path: Path):
    bundle, provenance_path = _copy_bundle(tmp_path)
    provenance = json.loads(provenance_path.read_text("utf-8"))
    ref = next(iter(provenance["rows"]))
    del provenance["rows"][ref]
    persona = next(iter(provenance["witnesses"]))
    block = next(iter(provenance["witnesses"][persona]["blocks"]))
    provenance["witnesses"][persona]["blocks"][block]["sources"] = []
    report = vb.Report()
    vb.check_records(bundle, vb.load_manifest(bundle), provenance, report)
    joined = "\n".join(report.failures)
    assert f"no matching private provenance for {ref}" in joined
    assert f"witness block {block}: no private provenance" in joined


def test_document_coverage_gaps_are_reported(tmp_path: Path):
    bundle, provenance_path = _copy_bundle(tmp_path)
    provenance = json.loads(provenance_path.read_text("utf-8"))
    provenance["documents"]["R07"]["segments"].pop()
    report = vb.Report()
    vb.check_documents(bundle, vb.load_manifest(bundle), provenance, report)
    assert any("R07 L" in f and "covered by 0" in f for f in report.failures)


# -- review fixes ---------------------------------------------------------------------------
def test_witness_topics_and_outcome_signal_names_are_landmark_checked(tmp_path: Path):
    bundle, _ = _copy_bundle(tmp_path)
    manifest = vb.load_manifest(bundle)
    # outcome wording once used in the ESW-400 signal names
    manifest["asset_logs"][0]["signals"].append(
        "Wymondley Main end opens (main protection operating time)"
    )
    entry = manifest["witnesses"][0]
    card_path = bundle / entry["file"]
    card = json.loads(card_path.read_text("utf-8"))
    card["blocks"][0]["topics"].append("resonance")
    card_path.write_text(json.dumps(card), "utf-8")
    hits = vb.check_landmarks(bundle, manifest, vb.Report())
    assert any("signal" in h and "end opens" in h for h in hits), hits
    assert any("topic" in h and "resonan" in h for h in hits), hits


def test_esw_signal_names_state_no_outcome():
    (esw,) = [e for e in MANIFEST["asset_logs"] if e["asset_id"] == "ESW-400"]
    assert esw["signals"] == [
        "event",
        "current (Wymondley Main end, RMS)",
        "current (Eaton Socon end, RMS)",
        "voltage change",
        "protection timing (Wymondley Main end)",
        "protection timing (Eaton Socon end)",
    ]
    rows = {r["event_id"]: r for r in _log_rows(esw)}
    # The outcome wording stays in the row text, which restates R03.
    assert "Wymondley Main end opens to clear the fault" in rows["R03-C5"]["text"]


def test_one_elexon_attribution_everywhere():
    """Issue: the manifest said 'database right 2019' while R02, R06 and R07 say 2026."""
    import re

    real = json.loads(
        (SYSTEM_RESPONSE_PRIVATE_DIR / "provenance_real.json").read_text("utf-8")
    )
    attributions = {
        entry["attribution"]
        for source_id, entry in real["sources"].items()
        if source_id.startswith("elexon_") and entry.get("attribution")
    }
    assert len(attributions) == 1
    (attribution,) = attributions
    years = set()
    for path in [SYSTEM_RESPONSE_BUNDLE_DIR / "manifest.json"] + sorted(
        SYSTEM_RESPONSE_BUNDLE_DIR.glob("R0*/R0*.txt")
    ):
        flat = " ".join(path.read_text("utf-8").split())
        years |= set(
            re.findall(r"Elexon Limited copyright and database right (\d{4})", flat)
        )
    assert years == set(re.findall(r"\d{4}", attribution))
    for entry in MANIFEST["asset_logs"] + MANIFEST["control_logs"]:
        if any(e in ("R02", "R06") for e in entry["evidence_ids"]):
            assert attribution in entry["source_note"], entry.get("asset_id")


def test_real_log_terms_come_from_the_source_records():
    rows = {name: [] for name in bb.ROW_FRAGMENTS}
    for name in bb.ROW_FRAGMENTS:
        for line in (bb.ROWS_DIR / name).read_text("utf-8").splitlines():
            rows[name].append(json.loads(line))
    real = json.loads(
        (SYSTEM_RESPONSE_PRIVATE_DIR / "provenance_real.json").read_text("utf-8")
    )
    terms = bb.real_source_terms(rows, real["sources"])
    assert set(terms) == {
        ("asset", "HORNSEA-ONE"),
        ("asset", "LITTLE-BARFORD"),
        ("control", "ESO-ENCC"),
    }
    broken = json.loads(json.dumps(real["sources"]))
    first = next(k for k in broken if k.startswith("elexon_boalf"))
    broken[first]["attribution"] = "Contains BMRS data (c) Elexon 1999."
    with pytest.raises(bb.BuildError, match="different licence/attribution"):
        bb.real_source_terms(rows, broken)


def test_qas_description_matches_the_file():
    (r06,) = [d for d in MANIFEST["documents"] if d["doc_id"] == "R06"]
    (qas,) = [a for a in r06["artifacts"] if "qas" in a["file"]]
    rows = (
        (SYSTEM_RESPONSE_BUNDLE_DIR / qas["file"]).read_text("utf-8").splitlines()[1:]
    )
    assert "non-zero" not in qas["description"]
    assert f"(every record returned; {len(rows)} rows)" in qas["description"]
    assert any(row.endswith(",0.0") for row in rows)  # zero volumes are kept


def test_not_held_messages_claim_only_absence_from_this_pack():
    basis = {
        (b["party"], b["data_type"]): b
        for b in PROVENANCE["data_returns"]["not_held_basis"]
    }
    for entry in MANIFEST["data_returns"]:
        if entry["status"] == "available":
            continue
        message = entry["message"]
        assert message.startswith("Not held in this evidence pack: "), message
        assert "were not published" not in message
        assert "half-hourly at most" not in message
        assert (entry["party"], entry["data_type"]) in basis
    by_key = {
        (e["party"], e["data_type"]): e["message"] for e in MANIFEST["data_returns"]
    }
    telemetry = by_key[("DNO", "real_time_distributed_generation_telemetry")]
    assert "Ofgem states that most DNOs only record generation volumes half-hourly" in (
        telemetry
    )
    feeder = by_key[("DNO", "feeder_level_lfdd_relay_logs")]
    assert "no published feeder- or relay-level LFDD log was obtained" in feeder


def test_r07_part_d_is_labelled_builder_written():
    lines = (
        (SYSTEM_RESPONSE_BUNDLE_DIR / "R07" / "R07.txt").read_text("utf-8").split("\n")
    )
    header = " ".join(lines[: lines.index("")])
    assert "Nothing in this record is synthesised" not in header
    assert "Nothing in Parts A-C is synthesised." in header
    assert "Part D is not a transcription" in header
    body = " ".join(lines)
    assert "gists written for this record, not post text" in body
    gists = [x for x in lines if x.startswith("D") and "| gist: " in x]
    assert len(gists) == 6


def test_r10_d9_restates_eso_on_its_own():
    flat = " ".join(
        (SYSTEM_RESPONSE_BUNDLE_DIR / "R10" / "R10.txt").read_text().split()
    )
    d9 = flat[flat.index("D9 ") : flat.index("D10 ")]
    assert "ESO 2.5: Grid Code OC6.6 describes the automatic LFDD scheme" in d9
    assert "Ofgem" not in d9 and "6.6.4" not in d9
