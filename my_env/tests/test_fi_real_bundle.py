"""Real-data evidence of the full-investigation bundle (R09, R11, R12): static checks.

These tests need no ``.context`` material: they check the committed outputs of
``builder/full_investigation/real/fi_build_real.py`` (text notes, CSVs, row fragments, private
provenance, manifest fragment) and compare data values with the raw mirror in
``builder/full_investigation/raw`` (open-licensed copies, slices and extracts).
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

ENV_ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ENV_ROOT / "builder" / "full_investigation" / "real"
RAW_DIR = ENV_ROOT / "builder" / "full_investigation" / "raw"
ROWS_DIR = ENV_ROOT / "builder" / "full_investigation" / "rows"
BUNDLE_DIR = (
    ENV_ROOT / "src" / "environment" / "incident" / "bundles" / "full_investigation"
)
PRIVATE_DIR = (
    ENV_ROOT / "src" / "environment" / "incident" / "private" / "full_investigation"
)

DOC_IDS = ("R09", "R11", "R12")
ROW_FILES = ("real_r09_asset.jsonl", "real_r09_control.jsonl", "real_r11_control.jsonl")
FRAGMENT = json.loads((REAL_DIR / "documents_real.json").read_text(encoding="utf-8"))
PROVENANCE = json.loads(
    (PRIVATE_DIR / "provenance_real.json").read_text(encoding="utf-8")
)
RAW_MANIFEST = json.loads((RAW_DIR / "RAW_MANIFEST.json").read_text(encoding="utf-8"))
DOCS = {doc["doc_id"]: doc for doc in FRAGMENT["documents"]}
LABELS = {
    "R09": "REAL DATA EXTRACTS WITH TRANSCRIBED REPORT TABLES",
    "R11": "REAL DATA EXTRACTS",
    "R12": "REAL DATA EXTRACTS",
}
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
#: Account handles of the archived posts and personal names in the sources (decision 51).
HANDLES = (
    "UKPowerNetworks",
    "wpduk",
    "ElectricityNW",
    "TLRailUK",
    "nationalrailenq",
    "NCLairport",
    "ng_eso",
    "andrealeadsom",
    "beisgovuk",
    "twitter.com",
    "public_user",
)
PERSONAL_NAMES = (
    "Julian Leslie",
    "Kwasi Kwarteng",
    "Andrea Leadsom",
    "Jonathan Brearley",
    "Neill Moloney",
    "Aaron",
    "Fiona",
)
#: Decision 50: no enforcement outcome may reach the agent-visible evidence.
ENFORCEMENT = re.compile(
    r"£|\b(?:4\.5|10\.5|1\.5) ?m(?:illion)?\b|voluntary payment|redress|penalt|\bfined\b"
    r"|settlement|enforcement action",
    re.IGNORECASE,
)


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
    return list(csv.DictReader(io.StringIO(data, newline="")))


def jsonl(name: str) -> list[dict[str, Any]]:
    return [
        json.loads(x)
        for x in (ROWS_DIR / name).read_text(encoding="utf-8").splitlines()
    ]


def seg_range(seg: dict[str, Any]) -> range:
    first, last = (int(x) for x in seg["lines"][1:].split("-L"))
    return range(first, last + 1)


def raw_json(rel: str) -> Any:
    return json.loads((RAW_DIR / rel).read_text(encoding="utf-8"))


def all_agent_text(doc_id: str) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8") for p in sorted((BUNDLE_DIR / doc_id).iterdir())
    )


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
    text = (BUNDLE_DIR / doc_id / f"{doc_id}.txt").read_bytes().decode("utf-8")
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert "\r" not in text and "\t" not in text
    lines = text_lines(doc_id)
    for number, line in enumerate(lines, 1):
        assert line == line.rstrip(), f"L{number} trailing whitespace"
        assert len(line) <= 110, f"L{number} has {len(line)} chars"
    assert lines[0] == f"DOCUMENT {doc_id} — {DOCS[doc_id]['title']}"
    header = "\n".join(lines[: lines.index("")])
    assert f"STATUS: {LABELS[doc_id]} —" in header
    assert "Clock reference:" in header and "Value-status legend:" in header
    assert (
        DOCS[doc_id]["label"]
        == LABELS[doc_id]
        == PROVENANCE["documents"][doc_id]["label"]
    )


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
                if QUANTITY.search(lines[n - 1]):
                    assert TAG.search(lines[n - 1]), (
                        f"{doc_id} L{n}: quantity without a tag"
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
    assert entry["text_sha256"] == sha256(
        (BUNDLE_DIR / doc_id / f"{doc_id}.txt").read_bytes()
    )
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
            if ref["kind"] in ("report_page", "report_table"):
                assert isinstance(ref["pdf_page"], int) and ref["pdf_page"] >= 1
                assert sources[ref["source_id"]]["kind"] == "pdf"
            if ref["kind"] == "report_page":
                assert ref["quote"] is None or len(ref["quote"].split()) >= 3
            if ref["kind"] == "report_table":
                assert ref["cells_checked_on_page"] > 0
                assert re.fullmatch(r"[0-9a-f]{64}", ref["catalogue_extract_sha256"])
            if ref["kind"] == "dataset":
                assert sources[ref["source_id"]]["sha256"] == ref["sha256"]
        if seg["extraction_method"] == "paraphrase":
            assert any("gist_rule" in ref for ref in seg["sources"]), seg["content"]


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_provenance_artifacts_match_fragment(doc_id: str) -> None:
    prov = PROVENANCE["documents"][doc_id]["artifacts"]
    listed = {a["file"] for a in DOCS[doc_id]["artifacts"]} - {f"{doc_id}/{doc_id}.txt"}
    assert set(prov) == listed
    for rel, meta in prov.items():
        data = (BUNDLE_DIR / rel).read_bytes()
        assert meta["sha256"] == sha256(data) and meta["bytes"] == len(data)
        assert meta["extraction_method"] in {"script", "transcription", "paraphrase"}


def test_sources_record_licence_url_and_hash() -> None:
    datasets = {
        k: v for k, v in PROVENANCE["sources"].items() if v["kind"] == "dataset"
    }
    assert len(datasets) >= 25
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
        assert meta["mirror"] in {"copy", "slice", "extract", "none"}
    for source_id in ("ESO", "APP", "OFG", "E3C-I", "E3C"):
        assert PROVENANCE["sources"][source_id]["kind"] == "pdf"


def test_evidence_id_choice_is_recorded() -> None:
    for record in (PROVENANCE, FRAGMENT):
        choice = record["evidence_id_choice"]
        assert (
            "R11" in choice and "R12" in choice and "S08" in choice and "S11" in choice
        )


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
        *(ROWS_DIR / name for name in ROW_FILES),
        PRIVATE_DIR / "provenance_real.json",
        REAL_DIR / "documents_real.json",
        RAW_DIR / "RAW_MANIFEST.json",
    ]
    for path in outputs:
        assert "/Users/" not in path.read_text(encoding="utf-8"), path


# ---------------------------------------------------------------------------------------------
# Decisions 50 and 51: no enforcement outcomes, organisational statements only
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_no_enforcement_outcome_reaches_the_evidence(doc_id: str) -> None:
    text = all_agent_text(doc_id)
    hit = ENFORCEMENT.search(text)
    assert hit is None, hit.group(0) if hit else ""
    rows = "".join((ROWS_DIR / name).read_text(encoding="utf-8") for name in ROW_FILES)
    public_rows = "\n".join(
        json.dumps({k: v for k, v in json.loads(line).items() if k != "provenance"})
        for line in rows.splitlines()
    )
    assert ENFORCEMENT.search(public_rows) is None
    excluded = json.dumps(PROVENANCE["excluded"])
    assert "2020-01-03" in excluded and "Decision 50" in excluded


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_no_handles_personal_names_or_post_text(doc_id: str) -> None:
    text = all_agent_text(doc_id)
    for handle in HANDLES:
        assert handle not in text, handle
    for name in PERSONAL_NAMES:
        assert not re.search(rf"\b{re.escape(name)}\b", text), name
    # The only '@' is the ESO's organisational account printed in ESO Table 8.
    assert set(re.findall(r"@\w+", text)) <= {"@NG_ESO"}
    # Distinctive phrases of the archived posts and pages are not reproduced.
    for phrase in (
        "90% of customers are now restored",
        "We have experienced multiple power cuts",
        "The UK Power Network has failed in the large parts",
        "Trains are currently at a stand",
        "The emergency generators at the hospital all worked",
        "the almost simultaneous loss of two large generators",
        "By 18:30 all demand was restored",
    ):
        assert phrase.lower() not in text.lower(), phrase


def test_private_outputs_carry_no_personal_names_or_post_text() -> None:
    """Decision 51 also holds for the private provenance and the row fragments."""
    for path in (
        PRIVATE_DIR / "provenance_real.json",
        REAL_DIR / "documents_real.json",
        *(ROWS_DIR / name for name in ROW_FILES),
    ):
        text = path.read_text(encoding="utf-8")
        for name in PERSONAL_NAMES[:5]:
            assert name not in text, (path.name, name)
        assert not re.search(r"public_user_\d", text), path.name
        assert "andrealeadsom" not in text, path.name


def test_stanlow_article_is_excluded_not_shipped() -> None:
    for doc_id in DOC_IDS:
        assert "Stanlow" not in all_agent_text(doc_id)
    excluded = json.dumps(PROVENANCE["excluded"])
    assert "Stanlow" in excluded and "PROHIBITED" in excluded


# ---------------------------------------------------------------------------------------------
# R09: the 17:51 vs 18:00 discrepancy, REMIT publication times, rows
# ---------------------------------------------------------------------------------------------


def test_r09_keeps_both_first_ofgem_contact_times() -> None:
    text = "\n".join(text_lines("R09"))
    assert "The first communication with Ofgem was made at 17:51hrs" in text
    assert "The ESO contacted BEIS at 17:40 and Ofgem at 18:00." in text
    assert "made just after 18:00hrs with the Director of" in text
    assert "between the ESO control room and BEIS was at 17:41hrs" in text
    rows = {r["entry_id"]: r for r in jsonl("real_r09_control.jsonl")}
    assert rows["R09-A1-2"]["index_time_utc"] == "2019-08-09T16:51:00Z"
    assert rows["R09-A1-2"]["to"] == rows["R09-A2-2"]["to"] == "Ofgem"
    assert rows["R09-A2-2"]["index_time_utc"] == "2019-08-09T17:00:00Z"
    assert rows["R09-A3-3"]["recorded_time"] == "just after 18:00hrs"
    assert rows["R09-A1-1"]["recorded_time"] == "17:41hrs"
    assert rows["R09-A2-1"]["recorded_time"] == "17:40"


def test_r09_remit_matches_the_raw_files() -> None:
    raw = [
        rec
        for name in (
            "REMIT_revision_details_selected.json",
            "REMIT_revision_details_selected_part2.json",
        )
        for rec in raw_json(f"elexon/raw/{name}")["data"]
        if rec["assetId"] in {"T_HOWAO-1", "T_HOWAO-2", "T_HOWAO-3", "T_LBAR-1"}
    ]
    rows = csv_rows("R09", "R09_elexon_remit_messages_hornsea_one_little_barford.csv")
    assert len(rows) == len(raw) == 46
    by_id = {str(r["id"]): r for r in raw}
    for row in rows:
        rec = by_id[row["id"]]
        assert row["publishTime"] == rec["publishTime"]
        assert float(row["availableCapacity"]) == rec["availableCapacity"]
        assert row["relatedInformation"] == (rec.get("relatedInformation") or "")
    events = {r["event_id"]: r for r in jsonl("real_r09_asset.jsonl")}
    assert len(events) == 46
    first = {
        "T_HOWAO-2": ("R09-REMIT-00000741-r1", "2019-08-09T16:18:00Z"),
        "T_HOWAO-3": ("R09-REMIT-00000743-r1", "2019-08-09T16:20:00Z"),
        "T_LBAR-1": ("R09-REMIT-00056773-r1", "2019-08-09T16:54:44Z"),
    }
    for unit, (event_id, published) in first.items():
        row = events[event_id]
        assert row["index_time_utc"] == published and row["recorded_time"].endswith(
            published
        )
        assert (
            row["signal"]
            == f"{unit} REMIT declared available capacity for event window MW"
        )
        assert row["value"] == 0.0 and row["value_status"] == "reported"
        assert row["provenance"]["record"]["publishTime"] == published
    assert {r["asset_id"] for r in events.values()} == {"HORNSEA-ONE", "LITTLE-BARFORD"}
    # The participants' free text stays in the rows (and the CSV), not in the text note.
    row_text = "\n".join(r["text"] for r in events.values())
    assert (
        "'trip of BMU 2.'" in row_text
        and "'trip of BMU 3. / 18:10 BST / Park is starting up.'" in row_text
    )
    text = "\n".join(text_lines("R09"))
    for event_id, published in first.values():
        assert f"{event_id} | publishTime {published} |" in text


def _remit_rows() -> list[dict[str, Any]]:
    return jsonl("real_r09_asset.jsonl")


def test_r09_remit_values_only_where_the_declaration_applies() -> None:
    """A REMIT row's numeric value is the capacity the message declares for its own event
    window: null for withdrawn (Dismissed) or closed (Inactive) revisions and for revisions
    published outside their event window, so no series shows a pre-event derate."""
    from datetime import datetime

    rows = _remit_rows()
    nulls = 0
    for row in rows:
        rec = row["provenance"]["record"]
        start, published, end = (
            datetime.fromisoformat(rec[k])
            for k in ("eventStartTime", "publishTime", "eventEndTime")
        )
        void = rec["eventStatus"] in {"Dismissed", "Inactive"}
        if void or not start <= published <= end:
            assert row["value"] is None, row["event_id"]
            nulls += 1
        else:
            assert row["value"] == float(rec["availableCapacity"]), row["event_id"]
        # The declared figures stay readable in the row text.
        assert f"available {float(rec['availableCapacity']):.1f} MW" in row["text"]
        assert row["signal"].endswith(
            "REMIT declared available capacity for event window MW"
        )
    assert 0 < nulls < len(rows)
    by_id = {r["event_id"]: r for r in rows}
    # The reviewer's cases: Little Barford's messages of the morning of 9 August (for a
    # window starting that night) and the withdrawn or closed revisions.
    for event_id in (
        "R09-REMIT-00056749-r1",
        "R09-REMIT-00056749-r2",
        "R09-REMIT-00056768-r1",
        "R09-REMIT-00056768-r2",
        "R09-REMIT-00056809-r10",
        "R09-REMIT-00000733-r2",
    ):
        assert by_id[event_id]["value"] is None, event_id
    before_event = [
        r
        for r in rows
        if r["asset_id"] == "LITTLE-BARFORD"
        and r["index_time_utc"] < "2019-08-09T15:52:33Z"
    ]
    assert before_event and all(r["value"] is None for r in before_event)
    notes = {c["asset_id"]: c for c in FRAGMENT["asset_logs"]}
    for asset_id in ("HORNSEA-ONE", "LITTLE-BARFORD"):
        note = notes[asset_id]["clock_note_proposal"]
        assert "null for a Dismissed or Inactive revision" in note
        assert "published before or after its event window" in note


def test_r09_text_indexes_remit_revisions_without_repeating_them() -> None:
    """Part D lists each revision once as a short index entry; the full fields are in the CSV
    and the asset-log rows (the text no longer repeats them: context cost)."""
    lines = text_lines("R09")
    start = next(i for i, x in enumerate(lines) if x.startswith("PART D"))
    end = next(i for i, x in enumerate(lines) if x.startswith("PART E"))
    part_d = "\n".join(lines[start:end])
    rows = _remit_rows()
    for row in rows:
        assert part_d.count(f"{row['event_id']} |") == 1, row["event_id"]
    assert "related information" not in part_d and "cause '" not in part_d
    assert "R09_elexon_remit_messages_hornsea_one_little_barford.csv" in part_d
    assert "query_asset_log" in part_d
    assert end - start < 120


def test_r09_public_post_times_are_decoded_from_identifiers() -> None:
    from datetime import UTC, datetime, timedelta

    def decode(post_id: int) -> str:
        when = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
            milliseconds=(post_id >> 22) + 1288834974657
        )
        return when.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

    text = "\n".join(text_lines("R09"))
    segments = PROVENANCE["documents"]["R09"]["segments"]
    posts = [
        ref
        for seg in segments
        if seg["extraction_method"] == "paraphrase"
        for ref in seg["sources"]
        if ref.get("post_ids")
    ]
    assert len(posts) == 29  # 27 single posts and two ESO threads (3 and 6 posts)
    for ref in posts:
        times = [decode(int(pid)) for pid in ref["post_ids"]]
        assert times[0] in text, ref["post_ids"]
        assert ref["archive_url"].startswith("https://web.archive.org/web/")
    # ESO's first post and the DNOs' first post, as decoded.
    assert "2019-08-09T17:27:46Z | National Grid ESO" in text
    assert "2019-08-09T16:08:14Z | UK Power Networks (UKPN)" in text


def test_r09_restoration_gists_keep_the_sources_upper_bounds() -> None:
    """ESO's statements say all demand was restored *by* 18:30 (8pm statement) and reconnected
    *by* 17.40 (10 August statement and thread): the gists keep the bound and never turn it into
    a point time that would conflict with other records."""
    public = csv_rows("R09", "R09_public_posts_and_statements_gists.csv")
    comms = [
        r for r in jsonl("real_r09_control.jsonl") if r["entry_id"].startswith("R09-E")
    ]
    texts = [r["gist_written_for_this_record"] for r in public] + [
        r["text"] for r in comms
    ]
    texts.append("\n".join(text_lines("R09")))
    seen = {"18:30": 0, "17.40": 0}
    for text in texts:
        flat = " ".join(text.split())
        assert "at 18:30" not in flat and "time when DNO reconnection" not in flat
        for clock in seen:
            for match in re.finditer(re.escape(clock), flat):
                before = flat[max(0, match.start() - 60) : match.start()]
                if "demand" in before:
                    assert before.endswith("by "), (
                        clock,
                        flat[match.start() - 60 :][:90],
                    )
                    seen[clock] += 1
    gists = {r["label"]: r["gist_written_for_this_record"] for r in public}
    by_1830 = [k for k, g in gists.items() if "restored all demand by 18:30" in g]
    by_1740 = [k for k, g in gists.items() if "reconnected all demand by 17.40" in g]
    assert len(by_1830) == 1 and len(by_1740) == 2, (by_1830, by_1740)
    assert seen["18:30"] >= 3 and seen["17.40"] >= 6


def test_r09_public_csv_states_each_time_basis() -> None:
    """The CSV says which clock each time uses; time_utc is filled only for decoded posts."""
    from datetime import UTC, datetime, timedelta

    rows = csv_rows("R09", "R09_public_posts_and_statements_gists.csv")
    assert list(rows[0])[:4] == ["label", "time", "time_basis", "time_utc"]
    bases = Counter(r["time_basis"] for r in rows)
    assert set(bases) == {
        "decoded from the post identifier (UTC)",
        "decoded from the post identifiers (UTC); time_utc is the thread's first post",
        "time in the page title (UK local time); page date as shown",
        "page date only (no time shown)",
        "page-displayed times (no zone shown) with the Internet Archive capture time (UTC)",
    }
    posts = {
        ref["post_ids"][0]: ref
        for seg in PROVENANCE["documents"]["R09"]["segments"]
        for ref in seg["sources"]
        if ref.get("post_ids")
    }
    decoded = set()
    for pid in posts:
        when = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
            milliseconds=(int(pid) >> 22) + 1288834974657
        )
        decoded.add(when.strftime("%Y-%m-%dT%H:%M:%SZ"))
    for row in rows:
        if row["time_basis"].startswith("decoded"):
            assert row["time_utc"] in decoded and row["time"].startswith(
                row["time_utc"]
            )
            datetime.fromisoformat(row["time_utc"])
        else:
            assert row["time_utc"] == "", row["label"]


def test_r09_reuses_the_r07_dno_gists() -> None:
    r07 = (
        ENV_ROOT
        / "src/environment/incident/bundles/system_response/R07/R07_dno_public_posts_summaries.csv"
    )
    gists = [
        r["gist_written_for_this_record"]
        for r in csv.DictReader(io.StringIO(r07.read_text()))
    ]
    public = csv_rows("R09", "R09_public_posts_and_statements_gists.csv")
    r09_gists = {r["gist_written_for_this_record"] for r in public}
    for gist in gists:
        assert gist.removeprefix("gist: ") in r09_gists


# ---------------------------------------------------------------------------------------------
# R11: Network Rail and ORR values against the mirror
# ---------------------------------------------------------------------------------------------


def _mirror_nr_rows() -> list[dict[str, str]]:
    rel = "consequences/raw/rail/networkrail_all_delays_201920_P05_slice_2019-08-09.csv.gz"
    text = gzip.decompress((RAW_DIR / rel).read_bytes()).decode("utf-8")
    return list(csv.DictReader(io.StringIO(text, newline="")))


def test_r11_records_are_the_selected_rows_unchanged() -> None:
    raw = _mirror_nr_rows()
    assert all(
        r["incident_start_datetime"].startswith("09/08/2019")
        and (r["incident_reason"] == "XK" or r["resp_manager"] == "METR")
        for r in raw
    )
    rows = csv_rows("R11", "R11_networkrail_delay_records_selected_incidents.csv")
    assert len(rows) == len(raw) == 3234
    for row, rec in zip(rows, raw, strict=True):
        assert all(row[k] == rec[k] for k in row)
    incidents = csv_rows("R11", "R11_networkrail_incidents_selected.csv")
    assert len(incidents) == 31
    numbers = {i["incident_number"] for i in incidents}
    assert {"224904", "224913", "224957", "224917", "225015", "225022"} <= numbers
    by_reason = Counter(i["incident_reason"] for i in incidents)
    assert by_reason["XK"] == 28
    assert {i["incident_number"] for i in incidents if i["resp_manager"] == "METR"} == {
        "224904",
        "224913",
        "224957",
    }
    controls = {r["entry_id"]: r for r in jsonl("real_r11_control.jsonl")}
    assert set(controls) == {f"R11-NR-{n}" for n in numbers}
    gtr = controls["R11-NR-224904"]
    assert gtr["index_time_utc"] == "2019-08-09T16:02:00Z"
    assert (
        "GTR CL700 UNITS FAULT FPK" in gtr["text"]
        and "GTR Class 700 Unit" in gtr["text"]
    )
    assert "17:02" in gtr["recorded_time"]


def test_r11_computes_no_totals() -> None:
    text = "\n".join(text_lines("R11"))
    # Delay minutes and cancellation counts are left to the investigator.
    assert (
        "7539" not in text and "7,539" not in text and "pfpi_minutes total" not in text
    )


@pytest.mark.parametrize(
    ("doc_id", "count"),
    [("R11", r"3234 records"), ("R11", r"31 incidents"), ("R09", r"46 revisions")],
)
def test_selection_sizes_are_not_tagged_as_reported(doc_id: str, count: str) -> None:
    """A count of the selection made for the record is the builder's, not a value given by a
    publisher, so it carries no [reported] tag (legend: [reported] = given by its publisher or
    by a report)."""
    text = " ".join(" ".join(text_lines(doc_id)).split())
    assert re.search(count, text), count
    assert not re.search(rf"{count}[^.;]*?\[reported\]", text), count


def test_r11_status_scopes_the_selection_count() -> None:
    header = " ".join(" ".join(text_lines("R11")[:12]).split())
    assert (
        "it computes no totals other than the size of the selection described in Part A"
        in header
    )
    assert "Size of this selection: 31 incidents" in " ".join(
        " ".join(text_lines("R11")).split()
    )


def test_r11_glossary_decodes() -> None:
    codes = {
        (r["code_type"], r["code"]): r
        for r in csv_rows("R11", "R11_networkrail_glossary_codes_used.csv")
    }
    assert codes[("incident_reason", "XK")]["name"] == "NATL GRID"
    assert codes[("incident_reason", "M8")]["name"] == "ABOVE SBAR"
    assert codes[("resp_manager", "METR")]["name"] == "GTR Class 700 Unit"
    assert codes[("toc_code", "ET")]["name"] == "GTR"
    assert codes[("event_type", "C")]["name"] == "Cancelled At Origin"
    assert codes[("stanox", "54238")]["name"] == "FINSBURY PARK"
    text = "\n".join(text_lines("R11"))
    assert "Period 5 ends 2019-08-17" in text


def test_r11_orr_tables_are_byte_copies() -> None:
    for name, rel in (
        (
            "R11_orr_table3124_trains_planned_and_cancellations_P03-P07.csv",
            "orr_3124_2019-20_P03-P07_slice.csv",
        ),
        (
            "R11_orr_table3157a_severely_disrupted_days_great_britain.csv",
            "orr_3157a_2019-20_P03-P07_slice.csv",
        ),
        (
            "R11_orr_table3157b_severely_disrupted_days_by_sub_operator.csv",
            "orr_3157b_2019-20_P03-P07_slice.csv",
        ),
    ):
        mirror = (RAW_DIR / "consequences" / "raw" / "rail" / rel).read_bytes()
        assert (BUNDLE_DIR / "R11" / name).read_bytes() == mirror
    text = "\n".join(text_lines("R11"))
    assert (
        "Apr 2019 to Mar 2020 (Period 05) | Greater Thameslink Railway | 107211 | 2938 | 5972"
        in text
    )


# ---------------------------------------------------------------------------------------------
# R12
# ---------------------------------------------------------------------------------------------


def test_r12_statement_details_and_unknown_airport_posts() -> None:
    text = "\n".join(text_lines("R12"))
    assert "2019-08-10T10:09:37+00:00" in text and "2024-10-15T08:22:50+00:00" in text
    assert (
        "2019-08-09T16:49:50Z | post 1 of 2 | identifier 1159869406102425601 | content not "
        "known" in text
    )
    assert (
        "2019-08-09T16:56:45Z | post 2 of 2 | identifier 1159871147980328960 | content not "
        "known" in text
    )
    assert "circuit breaker" in text and "X-ray" in text


def test_r12_prints_the_identifiers_its_times_are_decoded_from() -> None:
    """R12 promises the identifiers of the airport posts; the agent can check each decoded
    time from them (text and CSV)."""
    from datetime import UTC, datetime, timedelta

    def decode(post_id: int) -> str:
        when = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
            milliseconds=(post_id >> 22) + 1288834974657
        )
        return when.strftime("%Y-%m-%dT%H:%M:%SZ")

    text = "\n".join(text_lines("R12"))
    rows = csv_rows("R12", "R12_essential_service_public_statements.csv")
    posts = [r for r in rows if r["post_identifier"]]
    assert len(posts) == 2
    for row in posts:
        assert row["time_utc"] == decode(int(row["post_identifier"]))
        assert f"{row['time_utc']} | post" in text
        assert f"identifier {row['post_identifier']}" in text
    assert [
        r["post_identifier"] for r in rows if not r["time_basis"].startswith("decoded")
    ] == [""]


# ---------------------------------------------------------------------------------------------
# Manifest-v2 compatibility and rows
# ---------------------------------------------------------------------------------------------


def test_fragment_documents_load_with_the_catalogue(tmp_path: Path) -> None:
    from environment.incident import catalogue

    bundle = tmp_path / "bundle"
    for doc_id in DOC_IDS:
        shutil.copytree(BUNDLE_DIR / doc_id, bundle / doc_id)
    categories = tuple({*catalogue.CATEGORIES, *(d["category"] for d in DOCS.values())})
    for doc_id in DOC_IDS:
        loaded = catalogue.Catalogue._load_document(
            bundle, DOCS[doc_id], f"documents[{doc_id}]", categories
        )
        assert loaded.lines == tuple(text_lines(doc_id))
        assert loaded.timeseries is None


def test_row_fragments_schema_and_ids() -> None:
    for name in ROW_FILES:
        rows = jsonl(name)
        kind = "asset" if "asset" in name else "control"
        keys, id_key = (
            (ASSET_KEYS, "event_id") if kind == "asset" else (CONTROL_KEYS, "entry_id")
        )
        raw_lines = (ROWS_DIR / name).read_text(encoding="utf-8").splitlines()
        for line, row in zip(raw_lines, rows, strict=True):
            assert line == json.dumps(row, sort_keys=True, ensure_ascii=False)
            assert set(row) == keys | {"kind", "provenance"} and row["kind"] == kind
            assert RECORD_ID_RE.match(row[id_key]), row[id_key]
            assert row["index_time_utc"].endswith("Z")
            assert row["index_uncertainty_s"] >= 0
            assert row["value_status"] == "reported"
            assert row["provenance"]
        ids = [r[id_key] for r in rows]
        assert len(ids) == len(set(ids))
        summary = PROVENANCE["rows"][name]
        assert summary["count"] == len(rows)
        assert summary["sha256"] == sha256((ROWS_DIR / name).read_bytes())
    assert {r["room_id"] for r in jsonl("real_r09_control.jsonl")} == {"ESO-COMMS"}
    assert {r["room_id"] for r in jsonl("real_r11_control.jsonl")} == {
        "NETWORK-RAIL-CONTROL"
    }
    assert {r["evidence_id"] for r in jsonl("real_r11_control.jsonl")} == {"R11"}


def test_row_fragments_parse_as_v2_logs() -> None:
    logs = pytest.importorskip("environment.incident.logs")
    assets = jsonl("real_r09_asset.jsonl")
    for contrib in FRAGMENT["asset_logs"]:
        rows = [
            {k: v for k, v in r.items() if k not in ("kind", "provenance")}
            for r in assets
            if r["asset_id"] == contrib["asset_id"]
        ]
        data = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()
        entry = {
            "asset_id": contrib["asset_id"],
            "signals": contrib["signals"],
            "evidence_ids": contrib["evidence_ids"],
            "title": "t",
            "owner": "o",
            "clock_note": "c",
            "file": "x.jsonl",
        }
        log = logs.parse_asset_log(entry, data, sha256(data), contrib["asset_id"])
        assert len(log.rows) == len(rows) > 0
    controls = jsonl("real_r09_control.jsonl") + jsonl("real_r11_control.jsonl")
    for contrib in FRAGMENT["control_logs"]:
        rows = [
            {k: v for k, v in r.items() if k not in ("kind", "provenance")}
            for r in controls
            if r["room_id"] == contrib["room_id"]
        ]
        data = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()
        entry = {
            "room_id": contrib["room_id"],
            "evidence_ids": contrib["evidence_ids"],
            "title": "t",
            "owner": "o",
            "file": "x.jsonl",
        }
        log = logs.parse_control_log(entry, data, sha256(data), contrib["room_id"])
        assert len(log.rows) == len(rows) > 0


def test_row_ids_do_not_clash_with_increment_a_rows() -> None:
    ours = {
        r.get("event_id") or r.get("entry_id")
        for name in ROW_FILES
        for r in jsonl(name)
    }
    sr_rows = ENV_ROOT / "builder" / "system_response" / "rows"
    theirs = {
        json.loads(line).get("event_id") or json.loads(line).get("entry_id")
        for path in sr_rows.glob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    }
    assert not ours & theirs


# ---------------------------------------------------------------------------------------------
# Raw mirror
# ---------------------------------------------------------------------------------------------


def test_raw_mirror_manifest_hashes_licences_and_layout() -> None:
    listed = set()
    for entry in RAW_MANIFEST["files"]:
        data = (RAW_DIR / entry["rel"]).read_bytes()
        assert sha256(data) == entry["mirror_sha256"], entry["rel"]
        assert entry["mode"] in {"copy", "slice", "extract"}
        if entry["mode"] == "copy":
            assert entry["mirror_sha256"] == entry["original_sha256"]
        else:
            assert entry.get("slice_rule") or entry.get("extract_rule")
        for field in ("licence", "licence_text", "url", "publisher", "retrieved_utc"):
            assert entry[field], (entry["rel"], field)
        # Only open-licensed material is mirrored.
        assert entry["licence"].startswith(
            ("Open Government Licence", "Elexon BMRS open")
        ), entry
        listed.add(entry["rel"])
    on_disk = {str(p.relative_to(RAW_DIR)) for p in RAW_DIR.rglob("*") if p.is_file()}
    assert on_disk - {"RAW_MANIFEST.json"} == listed
