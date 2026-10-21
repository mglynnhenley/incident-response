"""Real-data evidence of the system-response bundle (R02, R04, R06, R07): static checks.

These tests need no ``.context`` material: they check the committed outputs of
``builder/system_response/real/build_real.py`` (text notes, CSVs, row fragments, private
provenance, manifest fragment) and compare data values with the raw mirror in
``builder/system_response/raw`` (open-licensed copies of the publishers' files).
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ENV_ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ENV_ROOT / "builder" / "system_response" / "real"
RAW_DIR = ENV_ROOT / "builder" / "system_response" / "raw"
ROWS_DIR = ENV_ROOT / "builder" / "system_response" / "rows"
BUNDLE_DIR = (
    ENV_ROOT / "src" / "environment" / "incident" / "bundles" / "system_response"
)
PRIVATE_DIR = (
    ENV_ROOT / "src" / "environment" / "incident" / "private" / "system_response"
)
sys.path.insert(0, str(REAL_DIR))

DOC_IDS = ("R02", "R04", "R06", "R07")
FRAGMENT = json.loads((REAL_DIR / "documents_real.json").read_text(encoding="utf-8"))
PROVENANCE = json.loads(
    (PRIVATE_DIR / "provenance_real.json").read_text(encoding="utf-8")
)
RAW_MANIFEST = json.loads((RAW_DIR / "RAW_MANIFEST.json").read_text(encoding="utf-8"))
DOCS = {doc["doc_id"]: doc for doc in FRAGMENT["documents"]}
LABEL = "REAL DATA EXTRACTS WITH TRANSCRIBED REPORT TABLES"
VALUE_STATUSES = {
    "measured",
    "reported",
    "estimated",
    "modelled",
    "digitised",
    "illustrative",
    "framing",
}
TAG = re.compile(r"\[(measured|reported|estimated|modelled|digitised|illustrative)\]")
LOWER_BRACKET = re.compile(r"\[([a-z]+)\]")
QUANTITY = re.compile(
    r"(?<![\w.])[-+~>]?\d[\d,.]*\s?(?:MWh|MW|MVA\.s|MVAr|kV|kA|ms|Hz|%|km|GW|GVAs|GVA\.s|mm|"
    r"seconds?|minutes?|hours?)(?![\w])|\b\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
)
TAGGED_METHODS = {"transcription", "figure_transcription", "quotation", "paraphrase"}
RECORD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
ASSET_KEYS = {
    "event_id",
    "evidence_id",
    "asset_id",
    "recorded_time",
    "clock_basis",
    "index_time_utc",
    "index_uncertainty_s",
    "signal",
    "value",
    "unit",
    "text",
    "value_status",
}
CONTROL_KEYS = {
    "entry_id",
    "evidence_id",
    "room_id",
    "recorded_time",
    "clock_basis",
    "index_time_utc",
    "index_uncertainty_s",
    "from",
    "to",
    "channel",
    "text",
    "value_status",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def text_lines(doc_id: str) -> list[str]:
    return (
        (BUNDLE_DIR / doc_id / f"{doc_id}.txt")
        .read_text(encoding="utf-8")
        .split("\n")[:-1]
    )


def csv_rows(doc_id: str, name: str) -> list[dict[str, str]]:
    data = (BUNDLE_DIR / doc_id / name).read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(data)))


def jsonl(name: str) -> list[dict[str, Any]]:
    lines = (ROWS_DIR / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def raw_json(rel: str) -> Any:
    data = (RAW_DIR / rel).read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return json.loads(data.decode("utf-8"))


def seg_range(seg: dict[str, Any]) -> range:
    first, last = (int(x) for x in seg["lines"][1:].split("-L"))
    return range(first, last + 1)


# ---------------------------------------------------------------------------------------------
# Files, hashes, text conventions
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_fragment_lists_exactly_the_files_on_disk(doc_id: str) -> None:
    doc = DOCS[doc_id]
    listed = {a["file"] for a in doc["artifacts"]}
    on_disk = {
        f"{doc_id}/{p.name}" for p in (BUNDLE_DIR / doc_id).iterdir() if p.is_file()
    }
    assert listed == on_disk
    assert set(doc["sha256"]) == listed
    assert doc["text_file"] == f"{doc_id}/{doc_id}.txt"
    for rel, digest in doc["sha256"].items():
        assert sha256((BUNDLE_DIR / rel).read_bytes()) == digest, rel


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_text_conventions(doc_id: str) -> None:
    raw = (BUNDLE_DIR / doc_id / f"{doc_id}.txt").read_bytes()
    text = raw.decode("utf-8")
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert "\r" not in text and "\t" not in text
    lines = text_lines(doc_id)
    for number, line in enumerate(lines, 1):
        assert line == line.rstrip(), f"L{number} trailing whitespace"
        assert len(line) <= 110, f"L{number} has {len(line)} chars"
    assert lines[0] == f"DOCUMENT {doc_id} — {DOCS[doc_id]['title']}"
    header = "\n".join(lines[: lines.index("")])
    assert f"STATUS: {LABEL} —" in header
    assert "Clock reference:" in header and "Value-status legend:" in header
    assert DOCS[doc_id]["label"] == LABEL == PROVENANCE["documents"][doc_id]["label"]


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_value_tags(doc_id: str) -> None:
    lines = text_lines(doc_id)
    for number, line in enumerate(lines, 1):
        for word in LOWER_BRACKET.findall(line):
            assert word in VALUE_STATUSES - {"framing"}, (
                f"L{number}: unknown tag [{word}]"
            )
    for seg in PROVENANCE["documents"][doc_id]["segments"]:
        span = [lines[n - 1] for n in seg_range(seg)]
        if seg["extraction_method"] in TAGGED_METHODS:
            for n in seg_range(seg):
                line = lines[n - 1]
                if QUANTITY.search(line):
                    assert TAG.search(line), (
                        f"{doc_id} L{n}: quantity without a value tag"
                    )
        elif seg["extraction_method"] == "script":
            assert any(TAG.search(line) for line in span), (
                f"{seg['lines']}: no value tag"
            )


# ---------------------------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_provenance_covers_every_line_once(doc_id: str) -> None:
    lines = text_lines(doc_id)
    entry = PROVENANCE["documents"][doc_id]
    raw = (BUNDLE_DIR / doc_id / f"{doc_id}.txt").read_bytes()
    assert entry["text_sha256"] == sha256(raw)
    assert entry["line_count"] == len(lines)
    covered: Counter[int] = Counter()
    for seg in entry["segments"]:
        for n in seg_range(seg):
            covered[n] += 1
    for n, line in enumerate(lines, 1):
        if line.strip():
            assert covered[n] == 1, f"{doc_id} L{n} covered {covered[n]} times"
    assert all(1 <= n <= len(lines) for n in covered)


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_provenance_segment_rules(doc_id: str) -> None:
    sources = PROVENANCE["sources"]
    for seg in PROVENANCE["documents"][doc_id]["segments"]:
        assert seg["value_status"] in VALUE_STATUSES
        if seg["extraction_method"] == "framing":
            assert seg["value_status"] == "framing" and seg["sources"] == []
            continue
        assert seg["value_status"] != "framing"
        assert seg["sources"], seg["content"]
        for ref in seg["sources"]:
            assert ref["source_id"] in sources, ref
            if ref["kind"] in ("report_page", "report_table", "report_figure"):
                assert isinstance(ref["pdf_page"], int) and ref["pdf_page"] >= 1
                assert sources[ref["source_id"]]["kind"] == "pdf"
            if ref["kind"] == "report_page":
                assert ref["quote"] is None or len(ref["quote"].split()) >= 3
            if ref["kind"] == "report_table":
                assert ref["cells_checked_on_page"] > 0
                assert re.fullmatch(r"[0-9a-f]{64}", ref["catalogue_extract_sha256"])
            if ref["kind"] == "dataset":
                assert sources[ref["source_id"]]["sha256"] == ref["sha256"]


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_provenance_artifacts_match_fragment(doc_id: str) -> None:
    prov = PROVENANCE["documents"][doc_id]["artifacts"]
    listed = {a["file"] for a in DOCS[doc_id]["artifacts"]} - {f"{doc_id}/{doc_id}.txt"}
    assert set(prov) == listed
    for rel, meta in prov.items():
        data = (BUNDLE_DIR / rel).read_bytes()
        assert meta["sha256"] == sha256(data) and meta["bytes"] == len(data)
        assert meta["extraction_method"] in {"script", "transcription", "paraphrase"}


def test_dataset_sources_record_licence_url_and_hash() -> None:
    datasets = {
        k: v for k, v in PROVENANCE["sources"].items() if v["kind"] == "dataset"
    }
    assert len(datasets) >= 30
    for key, meta in datasets.items():
        for field in (
            "publisher",
            "url",
            "licence",
            "licence_text",
            "retrieved_utc",
            "file",
        ):
            assert meta.get(field), f"{key}: {field}"
        assert re.fullmatch(r"[0-9a-f]{64}", meta["sha256"]), key
        assert meta["root"] == "GB_REAL_DATA_DIR"
    for source_id in ("ESO", "APP", "OFG", "E3C-I"):
        assert PROVENANCE["sources"][source_id]["kind"] == "pdf"


def test_no_builder_only_material_or_local_paths() -> None:
    for folder in [BUNDLE_DIR / d for d in DOC_IDS] + [RAW_DIR]:
        for path in folder.rglob("*"):
            assert path.suffix.lower() not in {
                ".pdf",
                ".zip",
                ".docx",
                ".html",
                ".xlsx",
            }, path
    outputs = [p for d in DOC_IDS for p in (BUNDLE_DIR / d).iterdir()] + [
        ROWS_DIR / "real_r02_asset.jsonl",
        ROWS_DIR / "real_r06_control.jsonl",
        PRIVATE_DIR / "provenance_real.json",
        REAL_DIR / "documents_real.json",
        RAW_DIR / "RAW_MANIFEST.json",
    ]
    for path in outputs:
        assert "/Users/" not in path.read_text(encoding="utf-8"), path


def test_public_posts_reproduce_no_post_text_or_handles() -> None:
    text = "\n".join(text_lines("R07"))
    for handle in ("@", "UKPowerNetworks", "wpduk", "ElectricityNW", "twitter.com"):
        assert handle not in text
    # Summaries, not the posts' own words (two distinctive phrases of the originals).
    assert "90% of customers are now restored" not in text
    assert "We have experienced multiple power cuts" not in text


# ---------------------------------------------------------------------------------------------
# Manifest-v2 compatibility
# ---------------------------------------------------------------------------------------------


def test_fragment_documents_load_with_the_catalogue(tmp_path: Path) -> None:
    from environment.incident import catalogue

    bundle = tmp_path / "bundle"
    for doc_id in DOC_IDS:
        shutil.copytree(BUNDLE_DIR / doc_id, bundle / doc_id)
    categories = tuple({*catalogue.CATEGORIES, *(d["category"] for d in DOCS.values())})
    loaded = {
        doc_id: catalogue.Catalogue._load_document(
            bundle, DOCS[doc_id], f"documents[{doc_id}]", categories
        )
        for doc_id in DOC_IDS
    }
    series = loaded["R07"].timeseries
    assert series is not None and series.rows == 61 and series.interval_s == 300
    assert series.first == datetime.fromisoformat("2019-08-09T14:00:00+00:00")
    assert series.last == datetime.fromisoformat("2019-08-09T19:00:00+00:00")
    for doc_id in ("R02", "R04", "R06"):
        assert loaded[doc_id].timeseries is None
    for doc_id, doc in loaded.items():
        assert doc.lines == tuple(text_lines(doc_id))


def test_row_fragments_parse_as_v2_logs() -> None:
    logs = pytest.importorskip("environment.incident.logs")
    assets = jsonl("real_r02_asset.jsonl")
    for contrib in FRAGMENT["asset_logs"]:
        rows = [
            {k: v for k, v in r.items() if k not in ("kind", "provenance")}
            for r in assets
            if r["asset_id"] == contrib["asset_id"]
        ]
        data = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()
        entry = {**contrib, "title": "t", "owner": "o", "file": "x.jsonl"}
        log = logs.parse_asset_log(entry, data, sha256(data), contrib["asset_id"])
        assert len(log.rows) == len(rows) > 0
    controls = jsonl("real_r06_control.jsonl")
    (contrib,) = FRAGMENT["control_logs"]
    rows = [
        {k: v for k, v in r.items() if k not in ("kind", "provenance")}
        for r in controls
    ]
    data = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()
    entry = {**contrib, "title": "t", "owner": "o", "file": "x.jsonl"}
    log = logs.parse_control_log(entry, data, sha256(data), contrib["room_id"])
    assert len(log.rows) == 139


def test_r07_timeseries_is_regular() -> None:
    rows = csv_rows("R07", "R07_elexon_demand_outturn_summary_5min_20190809.csv")
    stamps = [
        datetime.fromisoformat(r["startTime"].replace("Z", "+00:00")) for r in rows
    ]
    assert len(stamps) == 61
    assert all(
        b - a == timedelta(minutes=5) for a, b in zip(stamps, stamps[1:], strict=False)
    )


# ---------------------------------------------------------------------------------------------
# Row fragments
# ---------------------------------------------------------------------------------------------


def test_row_fragments_schema_and_ids() -> None:
    assets = jsonl("real_r02_asset.jsonl")
    controls = jsonl("real_r06_control.jsonl")
    for name, rows, keys, id_key in (
        ("real_r02_asset.jsonl", assets, ASSET_KEYS, "event_id"),
        ("real_r06_control.jsonl", controls, CONTROL_KEYS, "entry_id"),
    ):
        raw_lines = (ROWS_DIR / name).read_text(encoding="utf-8").splitlines()
        for line, row in zip(raw_lines, rows, strict=True):
            assert line == json.dumps(row, sort_keys=True, ensure_ascii=False)
            assert set(row) == keys | {"kind", "provenance"}
            assert RECORD_ID_RE.match(row[id_key]), row[id_key]
            assert row["index_time_utc"].endswith("Z")
            datetime.fromisoformat(row["index_time_utc"].replace("Z", "+00:00"))
            assert row["index_uncertainty_s"] >= 0
            assert row["value_status"] in VALUE_STATUSES - {"framing"}
        ids = [r[id_key] for r in rows]
        assert len(ids) == len(set(ids))
    assert {r["kind"] for r in assets} == {"asset"} and {
        r["kind"] for r in controls
    } == {"control"}
    assert {r["evidence_id"] for r in assets} == {"R02"}
    assert {r["asset_id"] for r in assets} == {"HORNSEA-ONE", "LITTLE-BARFORD"}
    assert {r["evidence_id"] for r in controls} == {"R06"}
    assert {r["room_id"] for r in controls} == {"ESO-ENCC"}


def test_row_counts_and_provenance_summary() -> None:
    assets = jsonl("real_r02_asset.jsonl")
    controls = jsonl("real_r06_control.jsonl")
    counts = Counter(r["signal"] for r in assets)
    for unit in ("T_HOWAO-1", "T_HOWAO-2", "T_HOWAO-3", "T_LBAR-1"):
        assert counts[f"{unit} B1610 MWh"] == 48
    for unit in ("T_HOWAO-1", "T_HOWAO-2", "T_HOWAO-3", "T_LBAR-1G"):
        assert counts[f"{unit} MEL MW"] == 48
    assert counts["T_LBAR-1 MEL MW"] == 75
    assert len(assets) == 459 and len(controls) == 139
    summary = PROVENANCE["rows"]
    assert summary["real_r02_asset.jsonl"]["count"] == len(assets)
    assert summary["real_r02_asset.jsonl"]["by_signal"] == dict(sorted(counts.items()))
    assert summary["real_r06_control.jsonl"]["count"] == len(controls)
    for name in ("real_r02_asset.jsonl", "real_r06_control.jsonl"):
        assert summary[name]["sha256"] == sha256((ROWS_DIR / name).read_bytes())


# ---------------------------------------------------------------------------------------------
# Values against the raw mirror (publishers' files)
# ---------------------------------------------------------------------------------------------


def test_dci_record_matches_raw_file() -> None:
    raw = raw_json("elexon/raw/DCI_201908.json")["data"]
    assert len(raw) == 1
    record = raw[0]
    assert record["volume"] == 931.0
    assert (record["timeFrom"], record["timeTo"]) == (
        "2019-08-09T15:54:00Z",
        "2019-08-09T16:40:00Z",
    )
    (row,) = csv_rows("R07", "R07_elexon_dci_201908.csv")
    assert float(row["volume"]) == record["volume"]
    for key in ("mRID", "timeFrom", "timeTo", "publishTime", "demandControlEventFlag"):
        assert row[key] == record[key]
    text = "\n".join(text_lines("R07"))
    assert "volume: 931.0 [reported]" in text
    assert "timeFrom: 2019-08-09T15:54:00Z [reported]" in text


def test_b1610_rows_and_csv_match_raw_files() -> None:
    assets = {r["event_id"]: r for r in jsonl("real_r02_asset.jsonl")}
    csv_values = {
        (r["bmUnit"], int(r["settlementPeriod"])): float(r["quantity"])
        for r in csv_rows("R02", "R02_elexon_b1610_selected_units_20190809.csv")
    }
    for unit in ("T_HOWAO-1", "T_HOWAO-2", "T_HOWAO-3", "T_LBAR-1"):
        raw = raw_json(f"elexon/raw/B1610_stream_{unit}_2019-08-09.json")
        records = [r for r in raw if r["settlementDate"] == "2019-08-09"]
        assert len(records) == 48
        for rec in records:
            sp = rec["settlementPeriod"]
            row = assets[f"R02-B1610-{unit}-20190809-SP{sp:02d}"]
            assert row["value"] == rec["quantity"] and row["unit"] == "MWh"
            assert csv_values[(unit, sp)] == rec["quantity"]
            assert row["provenance"]["record"] == rec
    # Spot values quoted in the real-data sourcing log (MWh in SP34).
    assert assets["R02-B1610-T_LBAR-1-20190809-SP34"]["value"] == 256.77
    assert assets["R02-B1610-T_HOWAO-2-20190809-SP34"]["value"] == 149.34


def test_mel_rows_match_raw_files() -> None:
    mel = [r for r in jsonl("real_r02_asset.jsonl") if r["signal"].endswith("MEL MW")]
    by_unit = defaultdict(list)
    for row in mel:
        by_unit[row["signal"].split()[0]].append(row)
    for unit, rows in by_unit.items():
        raw = raw_json(f"elexon/raw/PHYSICAL_{unit}_2019-08-09.json")["data"]
        records = [
            r
            for r in raw
            if r["dataset"] == "MELS" and r["settlementDate"] == "2019-08-09"
        ]
        assert len(records) == len(rows)
        for row in rows:
            rec = row["provenance"]["record"]
            assert rec in records and row["value"] == rec["levelFrom"]
            assert row["index_time_utc"] == rec["timeFrom"]
    lbar = {r["index_time_utc"]: r for r in by_unit["T_LBAR-1"]}
    assert lbar["2019-08-09T15:57:00Z"]["value"] == 664
    assert "to 0 MW at 2019-08-09T15:58:00Z" in lbar["2019-08-09T15:57:00Z"]["text"]


def _raw_boalf() -> list[dict[str, Any]]:
    unique = {}
    for sp in range(32, 39):
        for rec in raw_json(f"elexon/raw/BOALF_all_2019-08-09_SP{sp}.json")["data"]:
            unique[json.dumps(rec, sort_keys=True)] = rec
    return [
        r
        for r in unique.values()
        if "2019-08-09T15:40:00Z" <= r["acceptanceTime"] <= "2019-08-09T16:45:00Z"
    ]


def test_boalf_csv_and_control_rows_match_raw_files() -> None:
    raw = _raw_boalf()
    rows = csv_rows("R06", "R06_elexon_boalf_acceptances_20190809_1540-1645Z.csv")
    assert len(rows) == len(raw) == 363
    key = ("bmUnit", "acceptanceNumber", "timeFrom", "timeTo")
    raw_keys = {tuple(str(r[k]) for k in key): r for r in raw}
    for row in rows:
        rec = raw_keys[tuple(row[k] for k in key)]
        assert (
            int(row["levelFrom"]) == rec["levelFrom"]
            and int(row["levelTo"]) == rec["levelTo"]
        )
        assert row["acceptanceTime"] == rec["acceptanceTime"]
    controls = {r["entry_id"]: r for r in jsonl("real_r06_control.jsonl")}
    acceptances = {(r["bmUnit"], r["acceptanceNumber"]) for r in raw}
    assert len(controls) == len(acceptances) == 139
    for unit, number in acceptances:
        entry = controls[f"R06-BOALF-{unit}-{number}"]
        segments = [
            r for r in raw if (r["bmUnit"], r["acceptanceNumber"]) == (unit, number)
        ]
        assert entry["index_time_utc"] == segments[0]["acceptanceTime"]
        for seg in segments:
            assert f"{seg['timeFrom']} {seg['levelFrom']} MW" in entry["text"]
            assert f"{seg['timeTo']} {seg['levelTo']} MW" in entry["text"]


def test_fuelinst_csv_matches_raw_file() -> None:
    raw = raw_json("elexon/raw/FUELINST_20190809_1400_1900Z.json")["data"]
    values = {(r["startTime"], r["fuelType"]): r["generation"] for r in raw}
    rows = csv_rows("R02", "R02_elexon_fuelinst_5min_20190809.csv")
    assert len(rows) == 61
    fuels = [c for c in rows[0] if c.isupper()]
    assert len(fuels) == 15 and "TOTAL" not in "".join(rows[0])
    for row in rows:
        for fuel in fuels:
            assert int(row[fuel]) == values[(row["startTime"], fuel)]


def test_neso_files_are_verbatim_lines_of_the_raw_files() -> None:
    for name, rel in (
        (
            "R02_neso_historic_demand_20190808-10.csv",
            "neso_historic_demand_2019/demanddata_2019.csv",
        ),
        (
            "R02_neso_inertia_20190808-10.csv",
            "neso_system_inertia_2019_2020/inertia.csv",
        ),
    ):
        bundle_lines = (
            (BUNDLE_DIR / "R02" / name).read_bytes().splitlines(keepends=True)
        )
        raw_lines = (
            (RAW_DIR / "neso" / "datasets" / rel).read_bytes().splitlines(keepends=True)
        )
        assert len(bundle_lines) == 145
        assert all(line in raw_lines for line in bundle_lines)
        assert bundle_lines[0] == raw_lines[0]


# ---------------------------------------------------------------------------------------------
# Raw mirror
# ---------------------------------------------------------------------------------------------


def test_raw_mirror_manifest_hashes_licences_and_layout() -> None:
    listed = set()
    for entry in RAW_MANIFEST["files"]:
        path = RAW_DIR / entry["rel"]
        data = path.read_bytes()
        assert sha256(data) == entry["mirror_sha256"], entry["rel"]
        assert entry["mode"] in {"copy", "slice"}
        if entry["mode"] == "copy":
            assert entry["mirror_sha256"] == entry["original_sha256"]
        else:
            assert entry["slice_rule"]
        for field in ("licence", "licence_text", "url", "publisher", "retrieved_utc"):
            assert entry[field], (entry["rel"], field)
        listed.add(entry["rel"])
    on_disk = {
        str(p.relative_to(RAW_DIR)) for p in RAW_DIR.rglob("*") if p.is_file()
    } - {"RAW_MANIFEST.json"}
    assert on_disk == listed
    licences = " ".join(e["licence"] for e in RAW_MANIFEST["files"])
    assert (
        "Not an open licence" not in licences and "not an open licence" not in licences
    )


def test_part_d_gists_do_not_track_the_post_wording() -> None:
    """Issue: D4 and D6 were near-verbatim paraphrases of posts that are not openly
    licensed. No gist may share more than three consecutive words with its post."""
    import csv
    import io
    import os

    import real_r07

    real_dir = Path(
        os.environ.get(
            "GB_REAL_DATA_DIR", str(ENV_ROOT.parent / ".context" / "real_data")
        )
    )
    timeline = real_dir / "consequences" / "derived" / "comms_timeline_uk_local.csv"
    if not timeline.is_file():
        pytest.skip("comms timeline not available (GB_REAL_DATA_DIR)")
    rows = list(csv.DictReader(io.StringIO(timeline.read_text("utf-8"))))
    for post in real_r07.DNO_POSTS:
        (match,) = [r for r in rows if str(post["post_id"]) in r["source_url"]]
        assert not real_r07.shared_word_runs(
            post["summary"], match["summary"], real_r07.GIST_MAX_SHARED
        ), post["post_id"]
    assert real_r07.shared_word_runs(
        "90% of customers are now restored",
        match["summary"] + " 90% of customers are now restored",
        3,
    )
