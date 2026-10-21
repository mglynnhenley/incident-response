"""Integrated full-investigation bundle (manifest v2): build, global checks, inheritance
from increment A, decisions 50-51, and the nine tools and the task on the real bundle.

Unlike the task track's tests (synthetic bundle), these load the real
``bundles/full_investigation`` bundle written by ``builder/full_investigation/
build_bundle.py``. They need no ``.context`` input: the integration step reads only
increment A's frozen bundle and the tracks' outputs. Both builders are called
``build_bundle.py``, so the modules are loaded under distinct names.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import shutil
import sys
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from karotte import EvaluationRunConfig, ProtectedStore, ToolConfigWriter
from karotte import evaluation_runner as runner_module
from karotte import tool_base as karotte_tool_base
from karotte.agents import FakeSource, MessageLoopAgent
from karotte.mcp_servers.mcp_server import McpServer
from karotte.schemas.chat import ChatCompletionMessageToolCall, Function, Message
from karotte.schemas.transcript import ScoringEvent, TaskCompletedEvent

from environment import incident_checks
from environment.incident.catalogue import Catalogue
from environment.incident.episode import Episode, EpisodeConfig, read_trace
from environment.incident.paths import (
    FULL_INVESTIGATION_BUNDLE_DIR,
    FULL_INVESTIGATION_PRIVATE_DIR,
    SYSTEM_RESPONSE_BUNDLE_DIR,
    SYSTEM_RESPONSE_PRIVATE_DIR,
)
from environment.incident.replay import replay_episode

ENV_ROOT = Path(__file__).resolve().parents[1]
FI_BUILDER = ENV_ROOT / "builder" / "full_investigation"


def _load(name: str, path: Path) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fb = _load("fi_build_bundle", FI_BUILDER / "build_bundle.py")
fv = _load("fi_verify_bundle", FI_BUILDER / "verify_bundle.py")

BUNDLE = FULL_INVESTIGATION_BUNDLE_DIR
MANIFEST = json.loads((BUNDLE / "manifest.json").read_text("utf-8"))
PROVENANCE = json.loads(
    (FULL_INVESTIGATION_PRIVATE_DIR / "provenance.json").read_text("utf-8")
)
SR_MANIFEST = json.loads(
    (SYSTEM_RESPONSE_BUNDLE_DIR / "manifest.json").read_text("utf-8")
)
SR_PROVENANCE = json.loads(
    (SYSTEM_RESPONSE_PRIVATE_DIR / "provenance.json").read_text("utf-8")
)
SR_DOC_IDS = [d["doc_id"] for d in SR_MANIFEST["documents"]]
NEW_DOC_IDS = ["R09", "R11", "R12", "S08", "S10", "S11"]
DOC_IDS = sorted(SR_DOC_IDS + NEW_DOC_IDS)
NEW_CATEGORIES = [
    "transport_records",
    "essential_services",
    "communications_records",
    "compliance_records",
]
NEW_PERSONAS = [
    "eso-communications-lead",
    "gtr-fleet-engineer",
    "hospital-estates-manager",
    "network-rail-control-manager",
    "ukpn-epn-spn-control-engineer",
]
# The settlement day 9 August 2019 (BST) starts at 2019-08-08T23:00Z.
DAY = {"start": "2019-08-08T22:00:00Z", "end": "2019-08-10T00:00:00Z"}


def _rows(bundle: Path, file: str) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in (bundle / file).read_text("utf-8").splitlines()
    ]


def _fragment_rows() -> list[dict[str, Any]]:
    rows = []
    for name in sorted(fb.ROW_FRAGMENTS):
        for line in (fb.ROWS_DIR / name).read_text("utf-8").splitlines():
            rows.append(json.loads(line))
    return rows


def _copy_bundle(tmp_path: Path) -> tuple[Path, Path]:
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    provenance = tmp_path / "provenance.json"
    shutil.copy(FULL_INVESTIGATION_PRIVATE_DIR / "provenance.json", provenance)
    return bundle, provenance


def _config(tmp_path: Path, **extra: Any) -> EpisodeConfig:
    fields: dict[str, Any] = {
        "episode_dir": tmp_path / "root_data" / "episode",
        "evidence_dir": tmp_path / "workdir" / "evidence",
        "scratch_dir": tmp_path / "workdir" / "scratch",
        "bundle_dir": BUNDLE,
        "python_executable": sys.executable,
        "python_timeout_s": 20,
        "max_tool_calls": 150,
        "tool_profile": "system_response",
    }
    return EpisodeConfig(**{**fields, **extra})


# -- build ---------------------------------------------------------------------------------
def test_integration_build_is_byte_identical_and_deterministic():
    first = fb.build()
    assert first == fb.build()
    for path, data in first.items():
        assert path.read_bytes() == data, fb.rel(path)
    assert fb.owned_stale_files(first) == []


def test_global_checks_pass():
    report = fv.global_checks()
    assert report.ok, "\n".join(report.failures)
    counts = report.counts
    assert counts["files hashed"] == len(fv.manifest_files(MANIFEST))
    assert counts["documents with full provenance coverage"] == len(DOC_IDS) == 22
    assert counts["witness blocks with provenance"] == 90
    assert counts["rows with provenance"] == 897
    sr_files = sum(len(d["sha256"]) for d in SR_MANIFEST["documents"]) - 1  # not R10
    assert counts["increment A files copied unchanged"] == sr_files
    assert counts["increment A log rows kept"] == 777
    assert counts["increment A witness cards copied unchanged"] == 5
    assert counts["increment A data returns kept"] == 17
    assert counts["replaced documents keeping A's prefix"] == 1
    assert counts["not-held messages checked"] == 19


def test_bundle_stats():
    stats = fv.bundle_stats()
    assert stats["bundle"] == f"{fb.BUNDLE_ID} {fb.BUNDLE_VERSION}"
    assert stats["documents"] == 22 and stats["listed_documents"] == 20
    assert stats["asset_logs"] == {
        "ESW-400": 8,
        "HORNSEA-ONE": 312 + 25,
        "LITTLE-BARFORD": 180 + 21,
    }
    assert stats["control_logs"] == {
        "ESO-COMMS": 42,
        "ESO-ENCC": 277,
        "GTR-FLEET-CONTROL": 1,
        "NETWORK-RAIL-CONTROL": 31,
    }
    assert len(stats["witnesses"]) == 10 and stats["witness_blocks"] == 48 + 42
    assert stats["data_returns"] == {"available": 15, "not_held": 19}
    assert stats["log_rows"] == 777 + 46 + 42 + 31 + 1


# -- manifest --------------------------------------------------------------------------------
def test_manifest_v2_shape():
    assert MANIFEST["manifest_version"] == 2
    assert list(MANIFEST) == list(SR_MANIFEST)
    assert MANIFEST["bundle_id"] == "gb-2019-08-09-full-investigation"
    assert [d["doc_id"] for d in MANIFEST["documents"]] == DOC_IDS
    assert MANIFEST["categories"] == SR_MANIFEST["categories"] + NEW_CATEGORIES
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
    assert [w["persona_id"] for w in MANIFEST["witnesses"]] == sorted(
        [w["persona_id"] for w in SR_MANIFEST["witnesses"]] + NEW_PERSONAS
    )
    assert {w["evidence_id"] for w in MANIFEST["witnesses"]} == {"S09"}


def test_new_documents_have_neutral_metadata_and_new_categories():
    docs = {d["doc_id"]: d for d in MANIFEST["documents"]}
    assert {d: docs[d]["category"] for d in NEW_DOC_IDS} == {
        "R09": "communications_records",
        "R11": "transport_records",
        "R12": "essential_services",
        "S08": "transport_records",
        "S10": "compliance_records",
        "S11": "essential_services",
    }
    labels = {d: docs[d]["label"] for d in NEW_DOC_IDS}
    assert labels["R09"] == "REAL DATA EXTRACTS WITH TRANSCRIBED REPORT TABLES"
    assert labels["R11"] == labels["R12"] == "REAL DATA EXTRACTS"
    for doc_id in ("S08", "S10", "S11"):
        assert labels[doc_id] == "SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE"
    for doc_id in NEW_DOC_IDS:
        doc = docs[doc_id]
        assert doc["party_aliases"] == list(fb.PARTY_ALIASES[doc_id])
        assert doc.get("keywords", []) == list(fb.KEYWORDS.get(doc_id, ()))
        assert "access" not in doc
        assert all(a["file"].startswith(f"{doc_id}/") for a in doc["artifacts"])
        for key in ("title", "owner", "label"):
            assert fv.landmark_hits(doc[key]) == [], (doc_id, key)


def test_described_requests_match_only_what_the_catalogue_shows(tmp_path: Path):
    """request_document's description (increment A's, frozen) says a described request is
    matched on the title. No document carries hidden manifest keywords, so words that are in
    no listed ID or title (e.g. 'REMIT', 'cancellations', 'airport') do not select one."""
    assert all("keywords" not in d for d in MANIFEST["documents"])
    assert fb.KEYWORDS == {}
    ep = Episode(_config(tmp_path))
    ep.reset()
    for party, description in (
        ("ESO", "REMIT"),
        ("Network Rail", "cancellations"),
        ("airport", "hospital"),
    ):
        result = ep.call(
            "request_document", {"party": party, "description": description}
        )
        assert result.error_code == "UNKNOWN_ID", (party, description, result.envelope)
    found = ep.call(
        "request_document",
        {"party": "Network Rail", "description": "rail performance records"},
    ).envelope
    assert found["ok"] and found["evidence_ids"] == ["R11"]


def test_increment_a_documents_cards_and_returns_are_copied_unchanged():
    docs = {d["doc_id"]: d for d in MANIFEST["documents"]}
    for doc in SR_MANIFEST["documents"]:
        if doc["doc_id"] == "R10":
            continue
        assert docs[doc["doc_id"]] == doc
        for name in doc["sha256"]:
            assert (BUNDLE / name).read_bytes() == (
                SYSTEM_RESPONSE_BUNDLE_DIR / name
            ).read_bytes()
    cards = {w["persona_id"]: w for w in MANIFEST["witnesses"]}
    for entry in SR_MANIFEST["witnesses"]:
        assert cards[entry["persona_id"]] == entry
        assert (BUNDLE / entry["file"]).read_bytes() == (
            SYSTEM_RESPONSE_BUNDLE_DIR / entry["file"]
        ).read_bytes()
    returns = {(e["party"], e["data_type"]): e for e in MANIFEST["data_returns"]}
    for entry in SR_MANIFEST["data_returns"]:
        assert returns[(entry["party"], entry["data_type"])] == entry


def test_r10_is_the_full_edition_with_increment_a_as_its_prefix():
    (r10,) = [d for d in MANIFEST["documents"] if d["doc_id"] == "R10"]
    (sr_r10,) = [d for d in SR_MANIFEST["documents"] if d["doc_id"] == "R10"]
    ours = (BUNDLE / "R10" / "R10.txt").read_bytes()
    theirs = (SYSTEM_RESPONSE_BUNDLE_DIR / "R10" / "R10.txt").read_bytes()
    assert ours.startswith(theirs) and len(ours) > len(theirs)
    for key in ("category", "label", "date", "text_file", "party_aliases"):
        assert r10[key] == sr_r10[key], key
    old = SR_PROVENANCE["documents"]["R10"]["segments"]
    assert PROVENANCE["documents"]["R10"]["segments"][: len(old)] == old
    assert PROVENANCE["documents"]["R10"]["track"] == "recon"


def test_logs_keep_increment_a_rows_and_add_only_new_evidence():
    sr_logs = {
        e.get("asset_id") or e["room_id"]: e
        for e in SR_MANIFEST["asset_logs"] + SR_MANIFEST["control_logs"]
    }
    for entry in MANIFEST["asset_logs"] + MANIFEST["control_logs"]:
        log_id = entry.get("asset_id") or entry["room_id"]
        rows = _rows(BUNDLE, entry["file"])
        if log_id not in sr_logs:
            assert {r["evidence_id"] for r in rows} <= {"R09", "R11", "S08"}
            continue
        base = sr_logs[log_id]
        theirs = _rows(SYSTEM_RESPONSE_BUNDLE_DIR, base["file"])
        kept = [r for r in rows if r["evidence_id"] in base["evidence_ids"]]
        assert kept == theirs, log_id
        added = {r["evidence_id"] for r in rows} - set(base["evidence_ids"])
        if not added:
            assert entry == base
            assert (BUNDLE / entry["file"]).read_bytes() == (
                SYSTEM_RESPONSE_BUNDLE_DIR / base["file"]
            ).read_bytes()
        else:
            assert added == {"R09"}, log_id
            assert entry["signals"][: len(base["signals"])] == base["signals"]
    unchanged = {"ESW-400", "ESO-ENCC"}
    changed = {"HORNSEA-ONE", "LITTLE-BARFORD"}
    assert unchanged | changed == set(sr_logs)


def test_every_log_entry_is_complete_and_attributed():
    for entry in MANIFEST["asset_logs"] + MANIFEST["control_logs"]:
        for key in ("title", "owner", "clock_note", "status", "source_note", "sha256"):
            assert entry[key], (entry["file"], key)
        assert entry["status"].startswith("STATUS: ")
        assert entry["clock_note"].startswith(fb.sr.LOG_HEADER_NOTE)
        for eid in entry["evidence_ids"]:
            assert f"{eid} rows —" in entry["clock_note"]
            assert f"{eid}:" in entry["source_note"]
        if "signals" in entry:
            rows = _rows(BUNDLE, entry["file"])
            assert sorted({r["signal"] for r in rows}) == sorted(entry["signals"])
    logs = {
        e.get("asset_id") or e["room_id"]: e
        for e in MANIFEST["asset_logs"] + MANIFEST["control_logs"]
    }
    elexon = "Contains BMRS data (c) Elexon Limited copyright and database right 2026."
    for log_id in ("HORNSEA-ONE", "LITTLE-BARFORD"):
        entry = logs[log_id]
        assert (
            "R09 rows — recorded_time is the Elexon REMIT publishTime (UTC)"
            in (entry["clock_note"])
        )
        assert entry["source_note"].count(elexon) == 2  # R02 and R09
        assert "REMIT" in entry["title"]
    assert "Open Government Licence v3.0" in logs["NETWORK-RAIL-CONTROL"]["source_note"]
    # ESO-COMMS restates sources under different terms: no single licence is claimed.
    assert "Rows are real public data extracts" not in logs["ESO-COMMS"]["source_note"]
    assert logs["GTR-FLEET-CONTROL"]["status"] == (
        "STATUS: SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE (rows of S08)."
    )
    assert logs["NETWORK-RAIL-CONTROL"]["status"] == (
        "STATUS: REAL DATA EXTRACTS (rows of R11)."
    )


def test_split_note_round_trips_increment_a_notes():
    for entry in SR_MANIFEST["asset_logs"] + SR_MANIFEST["control_logs"]:
        ids = entry["evidence_ids"]
        clock = fb.split_note(
            entry["clock_note"], ids, header=fb.sr.LOG_HEADER_NOTE, sep=" rows — "
        )
        source = fb.split_note(entry["source_note"], ids, header=None, sep=": ")
        assert sorted(clock) == sorted(source) == sorted(ids)
    with pytest.raises(fb.BuildError):
        fb.split_note("R02: x. S01: y.", ["R02"], header=None, sep=": ")


# -- rows and cards ----------------------------------------------------------------------------
def test_every_row_appears_once_without_private_fields():
    expected: dict[tuple[str, str], dict[str, Any]] = {}
    for section, kind, key in (
        ("asset_logs", "event", "event_id"),
        ("control_logs", "entry", "entry_id"),
    ):
        for entry in SR_MANIFEST[section]:
            for row in _rows(SYSTEM_RESPONSE_BUNDLE_DIR, entry["file"]):
                expected[(kind, row[key])] = row
    fragment = {}
    for row in _fragment_rows():
        kind = "event" if row["kind"] == "asset" else "entry"
        ident = (kind, row.get("event_id") or row.get("entry_id"))
        assert ident not in expected
        fragment[ident] = row
        expected[ident] = {
            k: v for k, v in row.items() if k not in ("kind", "provenance")
        }
    merged = {}
    for section, kind, key in (
        ("asset_logs", "event", "event_id"),
        ("control_logs", "entry", "entry_id"),
    ):
        for entry in MANIFEST[section]:
            for row in _rows(BUNDLE, entry["file"]):
                assert (kind, row[key]) not in merged
                merged[(kind, row[key])] = row
    assert merged == expected
    for (kind, ident), row in fragment.items():
        assert PROVENANCE["rows"][f"{kind}:{ident}"]["provenance"] == row["provenance"]
    for ref, private in SR_PROVENANCE["rows"].items():
        assert PROVENANCE["rows"][ref]["provenance"] == private["provenance"]
        assert PROVENANCE["rows"][ref]["track"] == f"system_response.{private['track']}"


def test_rows_are_ordered_by_index_instant_then_id():
    for entry in MANIFEST["asset_logs"] + MANIFEST["control_logs"]:
        rows = _rows(BUNDLE, entry["file"])
        key = "event_id" if "asset_id" in entry else "entry_id"
        order = [(fb.parse_utc(r["index_time_utc"]), r[key]) for r in rows]
        assert order == sorted(order), entry["file"]
        text = (BUNDLE / entry["file"]).read_text("utf-8")
        for line, row in zip(text.splitlines(), rows, strict=True):
            assert line == json.dumps(row, ensure_ascii=False, sort_keys=True)


def test_witness_cards_and_block_provenance():
    for entry in MANIFEST["witnesses"]:
        data = (BUNDLE / entry["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        card = json.loads(data)
        assert all(
            set(b) == {"response_id", "topics", "response_text"} for b in card["blocks"]
        )
        private = PROVENANCE["witnesses"][entry["persona_id"]]
        assert sorted(private["blocks"]) == sorted(
            b["response_id"] for b in card["blocks"]
        )
        for block in card["blocks"]:
            assert private["blocks"][block["response_id"]]["sources"]
            assert private["blocks"][block["response_id"]]["topics"] == block["topics"]
        expected = (
            "recon" if entry["persona_id"] in NEW_PERSONAS else "system_response.recon"
        )
        assert private["track"] == expected
    for persona_id in NEW_PERSONAS:
        topics = [
            t
            for b in json.loads(
                (BUNDLE / "witnesses" / f"{persona_id}.json").read_text()
            )["blocks"]
            for t in b["topics"]
        ]
        for topic in topics:
            assert fv.landmark_hits(topic) == [], (persona_id, topic)


def test_provenance_merges_increment_a_and_both_tracks():
    tracks = Counter(doc["track"] for doc in PROVENANCE["documents"].values())
    assert tracks == {
        "system_response.recon": 10,
        "system_response.real": 4,
        "system_response.digitise": 1,
        "real": 3,
        "recon": 4,
    }
    assert set(PROVENANCE["parts"]) == {"real", "recon"}
    for part in PROVENANCE["parts"].values():
        data = (ENV_ROOT / part["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == part["sha256"]
    inherited = PROVENANCE["inherited"]
    sr_provenance_bytes = (SYSTEM_RESPONSE_PRIVATE_DIR / "provenance.json").read_bytes()
    assert (
        inherited["provenance_sha256"]
        == hashlib.sha256(sr_provenance_bytes).hexdigest()
    )
    assert (
        inherited["manifest_sha256"]
        == hashlib.sha256(
            (SYSTEM_RESPONSE_BUNDLE_DIR / "manifest.json").read_bytes()
        ).hexdigest()
    )
    assert inherited["replaced"] == {"R10": "recon"}
    for source in ("ESO", "APP", "OFG", "E3C"):
        parts = set(PROVENANCE["sources"][source]["parts"])
        assert {"real", "recon"} <= parts, source
        assert any(p.startswith("system_response.") for p in parts), source
        assert (
            PROVENANCE["sources"][source]["sha256"]
            == (SR_PROVENANCE["sources"][source]["sha256"])
        )
    assert len(PROVENANCE["data_returns"]["not_held_basis"]) == 19
    detectors = PROVENANCE["leakage_detectors"]
    assert "£4.5m" in detectors["leakage_markers"]
    assert detectors["detector_patterns"] and detectors["recon_passages"]


def test_data_returns_merge_three_registries():
    entries = MANIFEST["data_returns"]
    assert len(entries) == 34
    assert entries == sorted(entries, key=lambda e: (e["party"], e["data_type"]))
    tracks = Counter(PROVENANCE["data_returns"]["entry_tracks"].values())
    assert tracks == {"system_response": 17, "recon": 12, "real": 5}
    available = {
        (e["party"], e["data_type"]): e["evidence_id"]
        for e in entries
        if e["status"] == "available"
    }
    for key, doc_id in {
        ("GTR", "fleet_incident_records"): "S08",
        ("ESO", "generator_compliance_process_records"): "S10",
        ("NETWORK_RAIL", "delay_attribution_records"): "R11",
        ("ELEXON", "remit_messages"): "R09",
        ("ESO", "external_communications_record"): "R09",
        ("HOSPITAL_TRUST", "public_statement"): "R12",
        ("DNO", "lfdd_disconnection_and_restoration_returns"): "S05",
        ("DNO", "embedded_generation_loss_returns"): "S06",
    }.items():
        assert available[key] == doc_id
    basis = {
        (b["party"], b["data_type"])
        for b in PROVENANCE["data_returns"]["not_held_basis"]
    }
    by_key = {(e["party"], e["data_type"]): e for e in entries}
    for entry in entries:
        if entry["status"] == "available":
            continue
        assert entry["status"] == "not_held"  # no published refusal exists
        message = entry["message"]
        assert message.startswith("Not held in this evidence pack: "), message
        for claim in fv.NONEXISTENCE_CLAIMS:
            assert claim not in message.casefold(), (entry, claim)
        assert (entry["party"], entry["data_type"]) in basis
        assert fv.landmark_hits(message) == [], message
    for (party, data_type), message in fb.DATA_RETURN_MESSAGES.items():
        assert by_key[(party, data_type)]["message"] == message
    ukpn = by_key[("UKPN", "reconnection_switching_records")]["message"]
    assert "caused by" not in ukpn and "Eastern" not in ukpn


# -- decisions 50 and 51 ---------------------------------------------------------------------------
def test_no_enforcement_settlement_handles_or_personal_names():
    report = fv.Report()
    fv.check_exclusions(BUNDLE, report)
    assert report.ok, report.failures
    assert report.counts["files scanned for exclusions"] == len(
        list(fv.visible_texts(BUNDLE))
    )
    markers = PROVENANCE["leakage_detectors"]["leakage_markers"]
    for name, text in fv.visible_texts(BUNDLE):
        for marker in markers:
            assert marker not in text, (name, marker)
    r09 = (BUNDLE / "R09" / "R09.txt").read_text("utf-8")
    assert "@NG_ESO" in r09  # the ESO's organisational account, printed in Table 8


@pytest.mark.parametrize(
    ("planted", "kind"),
    [
        ("agreed to make a voluntary payment of £4.5m", "enforcement"),
        ("a settlement with the regulator", "enforcement"),
        ("the companies were fined", "enforcement"),
        ("posted by @UKPowerNetworks", "handle"),
        ("see twitter.com/someone", "handle"),
        ("Julian Leslie said", "name"),
    ],
)
def test_exclusion_checks_catch_planted_text(tmp_path: Path, planted: str, kind: str):
    bundle, _ = _copy_bundle(tmp_path)
    path = bundle / "S11" / "S11.txt"
    path.write_text(path.read_text("utf-8") + planted + "\n", "utf-8")
    report = fv.Report()
    fv.check_exclusions(bundle, report)
    expected = {
        "enforcement": "enforcement-settlement wording",
        "handle": "social-media handle",
        "name": "personal name",
    }[kind]
    assert any(f.startswith("S11/S11.txt: " + expected) for f in report.failures)


@pytest.mark.parametrize(
    "text",
    [
        "settlement period 34 and settlement date 2019-08-09",
        "Elexon endpoint /balancing/settlement/system-prices/2019-08-09",
        "only messages generated for the latest settlement run",
        "Published on twitter @NG_ESO",
        "embedded gen. loss 200 MW @49Hz",
        "stanox,16495,CHURCH FENTON,CRS CHF",
        "could warrant enforcement action",
    ],
)
def test_exclusion_checks_leave_legitimate_text(text: str):
    assert fv.enforcement_hits(text) == []
    assert fv.handle_hits(text) == []
    assert fv.name_hits(text) == []


# -- landmarks -------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "temporary and permanent lock-out",
            {"temporary and permanent", "permanent lock"},
        ),
        ("reconnection without instruction", {"without instruction"}),
        ("software 3.25.x and 3.27.x", {"3.25", "3.27"}),
        ("first call to Ofgem at 17:51", {"17:51"}),
        ("Ofgem contacted at 18:00", {"18:00"}),
        ("trip within 200 ms", {"200 ms"}),
        ("29 units locked out", {"lock-out count", "locked out"}),
        ("its own protection operated", {"own protection"}),
        ("a voluntary payment", {"voluntary payment"}),
        ("39,568 calls", {"39,568"}),
        ("the reconnections were caused by the systems", {"caused by"}),
    ],
)
def test_fi_landmark_patterns_flag_answers(text: str, expected: set[str]):
    assert expected <= set(fv.landmark_hits(text))


@pytest.mark.parametrize(
    "text",
    [
        "Rail performance records, 9 August 2019: delay attribution and periodic statistics",
        "IEM METAR reports for EGGW, EGSC and EGTC, 14:50-17:20 UTC on 9 August 2019",
        "T_HOWAO-1 REMIT declared available capacity for event window MW",
        "lock-out types",
        "lock-out recovery",
        "reconnection timing",
        "Table 3124 - Trains planned and cancellations by operator (periodic)",
        "Essential-service public statements, 9-10 August 2019",
    ],
)
def test_fi_landmark_patterns_leave_neutral_metadata(text: str):
    assert fv.landmark_hits(text) == []


def test_landmarks_in_new_metadata_are_reported(tmp_path: Path):
    bundle, _ = _copy_bundle(tmp_path)
    manifest = fv.load_manifest(bundle)
    (r09,) = [d for d in manifest["documents"] if d["doc_id"] == "R09"]
    r09["title"] = "Communications: Ofgem first contacted at 17:51"
    ukpn = next(e for e in manifest["data_returns"] if e["party"] == "UKPN")
    ukpn["message"] += " The reconnections were caused by the operational systems."
    card_path = bundle / "witnesses" / "ukpn-epn-spn-control-engineer.json"
    card = json.loads(card_path.read_text("utf-8"))
    card["blocks"][2]["topics"].append("reconnection without instruction")
    card_path.write_text(json.dumps(card), "utf-8")
    hits = fv.check_landmarks(bundle, manifest, fv.Report())
    assert len(hits) == 3, hits
    assert any("document R09 title" in h and "17:51" in h for h in hits)
    assert any("data return UKPN" in h and "caused by" in h for h in hits)
    assert any("topic (S09-UKPN-03)" in h and "without instruction" in h for h in hits)


# -- inheritance and refusals of the build -----------------------------------------------------------
def test_inheritance_check_catches_changed_increment_a_content(tmp_path: Path):
    bundle, provenance_path = _copy_bundle(tmp_path)
    provenance = json.loads(provenance_path.read_text("utf-8"))
    (bundle / "R03" / "R03.txt").write_text("changed\n", "utf-8")
    log = bundle / "logs" / "assets" / "HORNSEA-ONE.jsonl"
    lines = log.read_text("utf-8").splitlines(keepends=True)
    first_a_row = next(i for i, x in enumerate(lines) if '"evidence_id": "S01"' in x)
    log.write_text("".join(lines[:first_a_row] + lines[first_a_row + 1 :]), "utf-8")
    card = bundle / "witnesses" / "eso-control-engineer.json"
    card.write_bytes(card.read_bytes() + b" ")
    manifest = fv.load_manifest(bundle)
    manifest["data_returns"][0]["message"] = "changed"
    report = fv.Report()
    fv.check_inheritance(bundle, manifest, provenance, report)
    joined = "\n".join(report.failures)
    assert "R03/R03.txt: not a byte-identical copy" in joined
    assert "logs/assets/HORNSEA-ONE.jsonl: increment A rows changed" in joined
    assert "witness eso-control-engineer: card differs from A" in joined
    assert f"data return {manifest['data_returns'][0]['party']}/" in joined


def test_build_refuses_inconsistent_metadata(monkeypatch):
    monkeypatch.delitem(fb.NEW_CATEGORIES, "R11")
    with pytest.raises(fb.BuildError, match="R11: no category"):
        fb.build()


def test_build_refuses_undeclared_new_evidence_on_a_log(monkeypatch):
    monkeypatch.delitem(fb.ASSET_LOG_UPDATES, "HORNSEA-ONE")
    with pytest.raises(fb.BuildError, match="HORNSEA-ONE: new evidence"):
        fb.build()


def test_build_refuses_a_message_override_for_an_unknown_return(monkeypatch):
    monkeypatch.setitem(fb.DATA_RETURN_MESSAGES, ("NOBODY", "nothing"), "x")
    with pytest.raises(fb.BuildError, match="unknown return NOBODY/nothing"):
        fb.build()


def test_build_refuses_a_not_held_return_without_basis(monkeypatch):
    monkeypatch.setattr(fb, "EXTRA_NOT_HELD_BASIS", [])
    with pytest.raises(fb.BuildError, match="control_room_communications_log"):
        fb.build()


# -- the runtime serves the real bundle ----------------------------------------------------------------
def test_runtime_catalogue_loads_the_real_bundle():
    catalogue = Catalogue.load(BUNDLE)
    catalogue.verify()
    assert catalogue.is_v2 and catalogue.bundle_id == fb.BUNDLE_ID
    assert catalogue.listed_ids() == [d for d in DOC_IDS if d not in ("S05", "S06")]
    sources = catalogue.sources
    assert sorted(sources.asset_logs) == ["ESW-400", "HORNSEA-ONE", "LITTLE-BARFORD"]
    assert sorted(sources.control_logs) == [
        "ESO-COMMS",
        "ESO-ENCC",
        "GTR-FLEET-CONTROL",
        "NETWORK-RAIL-CONTROL",
    ]
    assert len(sources.witnesses) == 10 and len(sources.data_returns) == 34
    assert len(sources.frequency) == 3900
    assert catalogue.citable_ids() == sorted(
        [d for d in DOC_IDS if d not in ("S05", "S06")] + ["S09"]
    )


def _submission(ids: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "3.0",
        "variant_id": "baseline",
        "report": {
            "executive_summary": "Integration smoke test [F01] [F02].",
            "sections": [
                {"heading": "Chronology", "body": "See [F01]."},
                {"heading": "Consequences", "body": "See [F02]."},
            ],
        },
        "findings": [
            {
                "finding_id": "F01",
                "statement": "Integration smoke test of increment A's citation kinds.",
                "status": "reported",
                "citations": [
                    {"evidence_id": "S03", "locator": f"event:{ids['soe']}"},
                    {"evidence_id": "R06", "locator": f"entry:{ids['boalf']}"},
                    {"evidence_id": "S09", "locator": "response:S09-ESO-01"},
                    {"evidence_id": "R01", "locator": "time:2019-08-09T16:53:49+01:00"},
                    {"evidence_id": "S07", "locator": "L1-L4"},
                ],
            },
            {
                "finding_id": "F02",
                "statement": "Integration smoke test of increment B's records.",
                "status": "reported",
                "citations": [
                    {"evidence_id": "R09", "locator": f"event:{ids['remit']}"},
                    {"evidence_id": "R09", "locator": "entry:R09-A1-1"},
                    {"evidence_id": "R11", "locator": f"entry:{ids['rail']}"},
                    {"evidence_id": "S08", "locator": "entry:S08-G01"},
                    {"evidence_id": "S09", "locator": "response:S09-GTR-03"},
                    {"evidence_id": "R10", "locator": "L140-L141"},
                    {"evidence_id": "S10", "locator": "L1-L4"},
                    {"evidence_id": "S11", "locator": "L1-L4"},
                    {"evidence_id": "R12", "locator": "L1-L2"},
                ],
            },
        ],
    }


def test_every_tool_on_the_real_bundle_and_replay(tmp_path: Path):
    ep = Episode(_config(tmp_path))
    meta = ep.reset()
    assert meta["manifest_version"] == 2 and len(meta["tool_names"]) == 9
    assert meta["bundle_id"] == fb.BUNDLE_ID

    listing = ep.call("list_documents", {}).envelope
    assert listing["ok"] and listing["next_cursor"] is None
    assert [d["doc_id"] for d in listing["data"]["documents"]] == [
        d for d in DOC_IDS if d not in ("S05", "S06")
    ]
    assert [r["room_id"] for r in listing["data"]["control_logs"]] == [
        "ESO-COMMS",
        "ESO-ENCC",
        "GTR-FLEET-CONTROL",
        "NETWORK-RAIL-CONTROL",
    ]
    assert len(listing["data"]["witnesses"]) == 10
    assert len(listing["data"]["data_returns"]) == 34
    rail = ep.call("list_documents", {"category": "transport_records"}).envelope
    assert [d["doc_id"] for d in rail["data"]["documents"]] == ["R11", "S08"]

    for party, description, doc_id in (
        ("Network Rail", "delay attribution records", "R11"),
        ("GTR", "rail fleet records", "S08"),
        ("system operator", "external communications records", "R09"),
        ("hospital", "essential service public statements", "R12"),
        ("ESO", "control room log", "S07"),
    ):
        found = ep.call(
            "request_document", {"party": party, "description": description}
        ).envelope
        assert found["ok"] and found["evidence_ids"] == [doc_id], (party, found)
    for doc_id in ("S10", "S11", "R10"):
        assert ep.call("request_document", {"doc_id": doc_id}).envelope["ok"]
    assert ep.call("request_document", {"doc_id": "S06"}).error_code == "UNKNOWN_ID"

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
    remit = ep.call(
        "query_asset_log",
        {
            "asset_id": "HORNSEA-ONE",
            "signal": "T_HOWAO-1 REMIT declared available capacity for event window MW",
            "start": "2019-01-01T00:00:00Z",
            "end": "2020-01-01T00:00:00Z",
        },
    ).envelope
    assert remit["ok"] and remit["evidence_ids"] == ["R09"]
    assert remit["data"]["total_rows"] == 4

    comms = ep.call("query_control_log", {"room": "ESO-COMMS", **DAY}).envelope
    assert comms["ok"] and comms["evidence_ids"] == ["R09"]
    network = ep.call(
        "query_control_log", {"room": "NETWORK-RAIL-CONTROL", **DAY}
    ).envelope
    assert network["ok"] and network["data"]["total_rows"] == 31
    gtr = ep.call("query_control_log", {"room": "GTR-FLEET-CONTROL", **DAY}).envelope
    assert [r["entry_id"] for r in gtr["data"]["rows"]] == ["S08-G01"]
    room = ep.call("query_control_log", {"room": "ESO-ENCC", **DAY}).envelope
    assert room["ok"] and room["evidence_ids"] == ["R06", "R08", "S07"]

    for persona_id, question, response_id in (
        ("eso-control-engineer", "securing", "S09-ESO-01"),
        ("gtr-fleet-engineer", "battery reset", "S09-GTR-03"),
        ("eso-communications-lead", "Ofgem contact", "S09-ESOC-02"),
        ("network-rail-control-manager", "Wirral line", "S09-NR-03"),
        ("hospital-estates-manager", "standby generators", "S09-HOSP-03"),
        ("ukpn-epn-spn-control-engineer", "reconnection", "S09-UKPN-03"),
    ):
        answer = ep.call(
            "interview_witness", {"persona_id": persona_id, "question": question}
        ).envelope
        assert answer["ok"] and answer["data"]["response_id"] == response_id
    unknown = ep.call(
        "interview_witness",
        {"persona_id": "gtr-fleet-engineer", "question": "What was the inertia?"},
    ).envelope
    assert unknown["ok"] and unknown["data"]["matched"] is False

    for party, data_type, doc_id in (
        ("DNO", "lfdd_disconnection_and_restoration_returns", "S05"),
        ("GTR", "fleet_incident_records", "S08"),
        ("ELEXON", "remit_messages", "R09"),
    ):
        returned = ep.call(
            "request_data_return", {"party": party, "data_type": data_type}
        ).envelope
        assert returned["ok"] and returned["evidence_ids"] == [doc_id]
    for party, data_type in (
        ("NETWORK_RAIL", "train_running_records"),
        ("ESO", "grid_code_compliance_test_records"),
        ("ESO", "control_room_communications_log"),
    ):
        refused = ep.call(
            "request_data_return", {"party": party, "data_type": data_type}
        )
        assert refused.error_code == "NOT_HELD"

    code = (
        "import os, pandas as pd\n"
        "root = os.environ['EVIDENCE_DIR']\n"
        "d = pd.read_csv(os.path.join(root, 'R11', "
        "'R11_networkrail_delay_records_selected_incidents.csv'))\n"
        "print(len(d), sorted(os.listdir(root)))\n"
    )
    python = ep.call("run_python", {"code": code}).envelope
    assert python["ok"], python
    stdout = python["data"]["stdout"]
    assert stdout.startswith("3234 ") and "'S05'" in stdout and "'S06'" not in stdout

    ids = {
        "soe": soe["data"]["rows"][0]["event_id"],
        "boalf": next(r for r in room["data"]["rows"] if r["evidence_id"] == "R06")[
            "entry_id"
        ],
        "remit": remit["data"]["rows"][0]["event_id"],
        "rail": network["data"]["rows"][0]["entry_id"],
    }
    submission = _submission(ids)
    wrong = json.loads(json.dumps(submission))
    wrong["findings"][1]["citations"][0]["evidence_id"] = "R02"
    assert ep.call("submit_findings", {"submission": wrong}).error_code == (
        "VALIDATION_FAILED"
    )
    accepted = ep.call("submit_findings", {"submission": submission}).envelope
    assert accepted["ok"], accepted["error"]

    report = replay_episode(ep.config.episode_dir)
    assert report.ok, report.summary_text()


def _rendered_sizes(tmp_path: Path) -> tuple[dict[str, int], int]:
    """Characters the tools return for every listed document, and for every log row when
    each log is paged over its whole record (as an agent reading everything would)."""
    from environment.incident.episode import render

    ep = Episode(_config(tmp_path, max_tool_calls=1000))
    ep.reset()
    listing = ep.call("list_documents", {}).envelope["data"]
    docs = {
        d["doc_id"]: len(
            render(ep.call("request_document", {"doc_id": d["doc_id"]}).envelope)
        )
        for d in listing["documents"]
    }
    logs = 0
    window = {"start": "2019-01-01T00:00:00Z", "end": "2020-12-31T00:00:00Z"}
    routes = [
        ("query_asset_log", {"asset_id": a["asset_id"]}) for a in listing["asset_logs"]
    ] + [("query_control_log", {"room": r["room_id"]}) for r in listing["control_logs"]]
    for tool, key in routes:
        cursor = None
        while True:
            args = {**key, **window, **({"cursor": cursor} if cursor else {})}
            envelope = ep.call(tool, args).envelope
            assert envelope["ok"], (tool, key, envelope)
            logs += len(render(envelope))
            cursor = envelope["next_cursor"]
            if not cursor:
                break
    return docs, logs


def test_stated_evidence_size_matches_the_bundle(tmp_path: Path):
    """The instructions' evidence-size figures (decision 53) are the shipped bundle's,
    within 5 %; R09 no longer repeats its REMIT rows in the text."""
    from environment.tasks.gb_2019_full_investigation import prompt

    docs, logs = _rendered_sizes(tmp_path)
    total = sum(docs.values())

    def close(stated: int, measured: int) -> bool:
        return abs(stated - measured) <= 0.05 * measured

    assert close(prompt.EVIDENCE_DOCUMENT_CHARS, total), total
    assert close(prompt.EVIDENCE_DOCUMENT_MIN_CHARS, min(docs.values())), docs
    assert close(prompt.EVIDENCE_DOCUMENT_MAX_CHARS, max(docs.values())), docs
    assert close(prompt.EVIDENCE_LOG_CHARS, logs), logs
    assert max(docs, key=docs.get) == "R09" and docs["R09"] < 50_000


def test_task_pre_hook_loads_the_real_bundle(tmp_path: Path, monkeypatch):
    import environment.tasks.gb_2019_full_investigation as task_module

    cfg = task_module.FullInvestigationToolConfig(
        **_config(tmp_path).model_dump(exclude={"bundle_dir"})
    )
    assert cfg.bundle_dir == BUNDLE
    monkeypatch.setattr(
        task_module.GB2019FullInvestigationTask, "episode_config", lambda self: cfg
    )
    run = EvaluationRunConfig(
        run_id="fi-bundle",
        task_id=task_module.TASK_ID,
        model="fake",
        use_fake_model=True,
        transcript_file=str(tmp_path / "out" / "transcript.json"),
    )
    meta = task_module.GB2019FullInvestigationTask(run).pre_hook()
    manifest_sha = hashlib.sha256((BUNDLE / "manifest.json").read_bytes()).hexdigest()
    assert meta["manifest_version"] == 2
    assert meta["bundle_id"] == fb.BUNDLE_ID
    assert meta["bundle_version"] == fb.BUNDLE_VERSION
    assert meta["bundle_sha256"] == manifest_sha == PROVENANCE["manifest_sha256"]
    assert meta["budgets"]["output_token_budget"] == 80_000


# -- the image checks' assumptions hold on the real bundle ------------------------------------------
def test_image_check_flow_runs_on_the_real_bundle(tmp_path: Path):
    """The container checks drive increment A's materialisation flow on this bundle
    (``incident_checks.full_investigation_checks``); its IDs must exist here. Locally
    run_python is not isolated, so only the flow and the targets are checked."""
    ep = Episode(_config(tmp_path))
    ep.reset()
    report = incident_checks.sr_materialisation_report(
        ep, FULL_INVESTIGATION_PRIVATE_DIR
    )
    assert report["after_reset"] == [] and report["after_queries"] == []
    assert report["obtained"] == report["after_obtaining"] == ["R01", "S05"]
    assert report["python"]["listing"] == ["R01", "S05"]
    assert all(report["python"]["readable"].values())
    targets = incident_checks.fi_unobtained_targets(
        BUNDLE, FULL_INVESTIGATION_PRIVATE_DIR, report["obtained"]
    )
    assert str(BUNDLE / "S06" / "S06.txt") in targets
    assert str(BUNDLE / "S05" / "S05.txt") not in targets
    assert str(FULL_INVESTIGATION_PRIVATE_DIR / "provenance.json") in targets
    directories, files = incident_checks.fi_protected_paths()
    for folder in (
        BUNDLE,
        BUNDLE / "logs" / "control",
        BUNDLE / "witnesses",
        BUNDLE / "R11",
    ):
        assert folder in directories, folder
    for path in (
        BUNDLE / "manifest.json",
        BUNDLE / "S05" / "S05.txt",
        BUNDLE / "S06" / "S06.txt",
        FULL_INVESTIGATION_PRIVATE_DIR / "provenance.json",
        FULL_INVESTIGATION_PRIVATE_DIR / "provenance_real.json",
        FULL_INVESTIGATION_PRIVATE_DIR / "provenance_recon.json",
    ):
        assert path in files, path
    assert incident_checks.load_full_investigation_bundle() == fb.BUNDLE_ID


# -- a full run through Karotte on the real bundle -------------------------------------------------
def _call(index: int, name: str, args: dict) -> Message:
    return Message(
        role="assistant",
        content=f"Step {index}.",
        tool_calls=[
            ChatCompletionMessageToolCall(
                id=f"call_{index}",
                type="function",
                function=Function(name=name, arguments=json.dumps(args)),
            )
        ],
    )


def test_run_through_karotte_runner_on_the_real_bundle(tmp_path: Path, monkeypatch):
    import environment.tasks.gb_2019_full_investigation as task_module
    from environment.tasks.gb_2019_full_investigation.judge import GRADING_MODULE

    monkeypatch.setitem(sys.modules, GRADING_MODULE, None)  # grading not built yet
    config = task_module.FullInvestigationToolConfig(
        **_config(tmp_path).model_dump(exclude={"bundle_dir"})
    )
    configs_dir = tmp_path / "tool_configs"
    monkeypatch.setattr(karotte_tool_base, "CONFIGS_DIR", configs_dir)
    monkeypatch.setattr(
        runner_module, "ToolConfigWriter", lambda: ToolConfigWriter(configs_dir)
    )
    monkeypatch.setattr(
        runner_module, "ProtectedStore", lambda: ProtectedStore(tmp_path / "protected")
    )
    monkeypatch.setattr(
        task_module.GB2019FullInvestigationTask, "episode_config", lambda self: config
    )
    monkeypatch.setattr(
        task_module.FullInvestigationStep,
        "episode_config",
        property(lambda self: config),
    )
    ids = {
        "soe": "S03-SOE-E1",
        "boalf": "R06-BOALF-2__BANGE001-4755",
        "remit": "R09-REMIT-00000594-r1",
        "rail": "R11-NR-224906",
    }
    lb = {"asset_id": "LITTLE-BARFORD", "signal": "sequence-of-events entry", **DAY}
    messages = [
        _call(1, "list_documents", {}),
        _call(
            2,
            "request_document",
            {"party": "Network Rail", "description": "delay attribution records"},
        ),
        _call(
            3,
            "query_frequency",
            {"start": "2019-08-09T16:52:00+01:00", "end": "2019-08-09T16:54:00+01:00"},
        ),
        _call(4, "query_asset_log", lb),
        _call(5, "query_control_log", {"room": "NETWORK-RAIL-CONTROL", **DAY}),
        _call(
            6,
            "interview_witness",
            {"persona_id": "gtr-fleet-engineer", "question": "battery reset"},
        ),
        _call(
            7,
            "request_data_return",
            {"party": "GTR", "data_type": "fleet_incident_records"},
        ),
        _call(
            8,
            "request_data_return",
            {"party": "NETWORK_RAIL", "data_type": "train_running_records"},
        ),
        _call(9, "request_document", {"doc_id": "R09"}),
        _call(10, "request_document", {"doc_id": "R10"}),
        _call(11, "request_document", {"doc_id": "S10"}),
        _call(12, "request_document", {"doc_id": "S11"}),
        _call(13, "request_document", {"doc_id": "R12"}),
        _call(14, "request_document", {"doc_id": "S07"}),
        _call(15, "query_control_log", {"room": "ESO-ENCC", **DAY}),
        _call(
            16,
            "interview_witness",
            {"persona_id": "eso-control-engineer", "question": "securing"},
        ),
        _call(
            17,
            "run_python",
            {
                "code": "import os\nprint(sorted(os.listdir(os.environ['EVIDENCE_DIR'])))"
            },
        ),
        _call(18, "submit_findings", {"submission": _submission(ids)}),
        Message(role="assistant", content="Submitted; ending my turn."),
    ]
    run_config = EvaluationRunConfig(
        run_id="fi-real",
        task_id=task_module.TASK_ID,
        model="fake",
        use_fake_model=True,
        transcript_file=str(tmp_path / "out" / "transcript.json"),
        step_context_window_limit=200_000,
        on_step_context_window_limit="score",
        save_artifacts=False,
        step_time_limit_seconds=600,
        on_step_time_limit="score",
    )
    task = task_module.GB2019FullInvestigationTask(run_config)
    runner = runner_module.EvaluationRunner(run_config, task)
    runner._agent = MessageLoopAgent(FakeSource(messages))
    mcp = McpServer("fi-real-bundle")

    @asynccontextmanager
    async def connect():
        from fastmcp import Client

        async with Client(mcp.server) as client:
            yield client

    runner._connect_to_mcp_server = connect

    async def go():
        return [event async for event in runner.run()]

    events = asyncio.run(go())
    completed = [e for e in events if isinstance(e, TaskCompletedEvent)]
    assert completed and completed[-1].status == "passed", [
        getattr(e, "message", "") for e in events if type(e).__name__ == "ErrorEvent"
    ]
    scoring = [e for e in events if isinstance(e, ScoringEvent)][0].scoring
    assert scoring.score == 1.0
    assert scoring.metadata["grading"]["status"] == "unavailable"
    summary = scoring.metadata["transcript_summary"]
    assert summary["tool_calls_episode_tools"] == 18
    assert summary["bundle_version"] == fb.BUNDLE_VERSION

    trace = read_trace(config.episode_dir)
    codes = [r["outcome_code"] for r in trace]
    assert codes == ["OK"] * 7 + ["NOT_HELD"] + ["OK"] * 10, codes
    assert trace[1]["envelope"]["evidence_ids"] == ["R11"]
    assert trace[6]["envelope"]["evidence_ids"] == ["S08"]
    stdout = trace[16]["python"]["stdout"]
    for doc_id in ("R01", "R09", "R10", "R11", "R12", "S07", "S08", "S10", "S11"):
        assert f"'{doc_id}'" in stdout
    tool_messages = [m for m in runner.transcript.messages if m.role == "tool"]
    for message, record in zip(tool_messages, trace, strict=True):
        text = message.content[0]["text"]
        assert (
            record["rendered_text_sha256"] == hashlib.sha256(text.encode()).hexdigest()
        )
    assert replay_episode(config.episode_dir).ok
