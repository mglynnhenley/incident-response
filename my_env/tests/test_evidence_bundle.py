"""Evidence bundle checks: manifest, text conventions, provenance coverage, R01 data.

These tests need no PDFs or handoff files. Checks that compare against builder-only material
(extracted PDF text, handoff CSV, handoff source manifest) skip when that material is absent.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ENV_ROOT = Path(__file__).resolve().parents[1]
INCIDENT_DIR = ENV_ROOT / "src" / "environment" / "incident"
BUNDLE_DIR = INCIDENT_DIR / "bundle"
PRIVATE_DIR = INCIDENT_DIR / "private"
BUILDER_DIR = ENV_ROOT / "builder"
HANDOFF_DIR = Path(
    os.environ.get(
        "GB_HANDOFF_DIR",
        str(ENV_ROOT.parent / ".context" / "handoff" / "GB_power_cut_handoff"),
    )
)
TEXT_DIR = Path(os.environ.get("GB_TEXT_DIR", str(HANDOFF_DIR.parent / "text")))

DOC_IDS = ["R01", "R03", "S01", "S03", "S04"]
TAGGED_DOCS = ["R03", "S01", "S03", "S04"]
SYNTHESISED = ["S01", "S03", "S04"]
CATEGORIES = {
    "R01": "measurement_data",
    "R03": "network_records",
    "S01": "generator_records",
    "S03": "generator_records",
    "S04": "personnel_accounts",
}
SYNTH_STATUS = (
    "STATUS: SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE. Reconstructed from published "
    "investigation material for this exercise; wording, layout and record structure are "
    "reconstructions."
)
R03_STATUS = "STATUS: RECONSTRUCTED FOR EVALUATION FROM PUBLISHED RECORDS — NOT AN ORIGINAL SYSTEM EXPORT."
LABELS = {
    "R01": "REAL MEASURED DATA EXTRACT",
    "R03": "RECONSTRUCTED FOR EVALUATION FROM PUBLISHED RECORDS — NOT AN ORIGINAL SYSTEM EXPORT",
    "S01": "SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE",
    "S03": "SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE",
    "S04": "SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE",
}
ALLOWED_TAGS = {"measured", "reported", "estimated", "illustrative"}
TAG = re.compile(r"\[(measured|reported|estimated|illustrative)\]")
BRACKET_WORD = re.compile(r"\[([a-z]+)\]")
QUANTITY = re.compile(
    r"(?<![\w.])[~>]?\d[\d,.]*\s?"
    r"(?:MW|MVAr|MVAR|kV|kA|ms|s|Hz|%|km|GW|seconds?|minutes?|mins?|hours?)(?!\w)"
    r"|\b\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
)
LANDMARK_STRINGS = ("48.787", "49.083", "50.001")
CSV_NAME = "frequency_2019-08-09_1640-1745_BST.csv"
BST = timedelta(hours=1)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


MANIFEST = _load_json(BUNDLE_DIR / "manifest.json")
PROVENANCE = _load_json(PRIVATE_DIR / "provenance.json")
DOCS = {doc["doc_id"]: doc for doc in MANIFEST["documents"]}


def _text(doc_id: str) -> str:
    return (BUNDLE_DIR / DOCS[doc_id]["text_file"]).read_text(encoding="utf-8")


def _lines(doc_id: str) -> list[str]:
    lines = _text(doc_id).split("\n")
    assert lines[-1] == ""
    return lines[:-1]


def _header(doc_id: str) -> list[str]:
    lines = _lines(doc_id)
    return lines[: lines.index("")]


def _range(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"L(\d+)-L(\d+)", value)
    assert match, value
    return int(match.group(1)), int(match.group(2))


def _framing_lines(doc_id: str) -> set[int]:
    framing: set[int] = set()
    for segment in PROVENANCE["documents"][doc_id]["segments"]:
        if segment["extraction_method"] == "framing":
            start, end = _range(segment["lines"])
            framing.update(range(start, end + 1))
    return framing


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _csv_rows() -> list[tuple[datetime, float]]:
    text = (BUNDLE_DIR / "R01" / CSV_NAME).read_text(encoding="utf-8")
    reader = csv.reader(io.StringIO(text))
    assert next(reader) == ["timestamp", "frequency_hz"]
    return [(datetime.fromisoformat(stamp), float(value)) for stamp, value in reader]


def _bst(hms: str) -> datetime:
    return datetime.fromisoformat(f"2019-08-09T{hms}+01:00")


# --------------------------------------------------------------------------- manifest


class TestManifest:
    def test_top_level(self) -> None:
        assert MANIFEST["bundle_id"] == "gb-2019-08-09-electrical-mvp"
        assert MANIFEST["bundle_version"] == "1.1.0"
        assert [doc["doc_id"] for doc in MANIFEST["documents"]] == DOC_IDS

    @pytest.mark.parametrize("doc_id", DOC_IDS)
    def test_document_entry(self, doc_id: str) -> None:
        doc = DOCS[doc_id]
        assert set(doc) == {
            "doc_id",
            "title",
            "owner",
            "date",
            "category",
            "text_file",
            "artifacts",
            "sha256",
        }
        assert doc["category"] == CATEGORIES[doc_id]
        assert doc["date"] == "2019-08-09"
        assert doc["title"] and doc["owner"]
        assert doc["text_file"] == f"{doc_id}/{doc_id}.txt"
        files = [artifact["file"] for artifact in doc["artifacts"]]
        assert doc["text_file"] in files
        assert set(doc["sha256"]) == set(files)
        for artifact in doc["artifacts"]:
            assert artifact["file"].startswith(f"{doc_id}/")
            assert artifact["media_type"] in {"text/plain", "text/csv"}
            assert artifact["description"]
            assert doc["sha256"][artifact["file"]] == _sha256(
                BUNDLE_DIR / artifact["file"]
            )

    def test_only_r01_has_timeseries(self) -> None:
        series = [
            (doc["doc_id"], artifact)
            for doc in MANIFEST["documents"]
            for artifact in doc["artifacts"]
            if "timeseries" in artifact
        ]
        assert len(series) == 1
        doc_id, artifact = series[0]
        assert doc_id == "R01"
        assert artifact["file"] == f"R01/{CSV_NAME}"
        assert artifact["media_type"] == "text/csv"
        assert artifact["timeseries"] == {
            "time_column": "timestamp",
            "value_column": "frequency_hz",
            "unit": "Hz",
            "first": "2019-08-09T16:40:00+01:00",
            "last": "2019-08-09T17:44:59+01:00",
            "rows": 3900,
            "interval_s": 1,
        }

    def test_no_stray_bundle_files(self) -> None:
        listed = {a["file"] for doc in MANIFEST["documents"] for a in doc["artifacts"]}
        on_disk = {
            str(path.relative_to(BUNDLE_DIR))
            for path in BUNDLE_DIR.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        }
        assert on_disk == listed

    @pytest.mark.parametrize("doc_id", DOC_IDS)
    def test_titles_are_neutral(self, doc_id: str) -> None:
        title = DOCS[doc_id]["title"].casefold()
        for word in (
            "cause",
            "trip",
            "deload",
            "de-load",
            "lightning",
            "discrepancy",
            "minimum",
        ):
            assert word not in title

    def test_no_pdfs_or_spec_in_package(self) -> None:
        package = ENV_ROOT / "src"
        assert not list(package.rglob("*.pdf"))
        assert not list(package.rglob("*.zip"))
        assert not list(package.rglob("IMPLEMENTATION_SPEC*"))


# --------------------------------------------------------------------------- text conventions


class TestTextConventions:
    @pytest.mark.parametrize("doc_id", DOC_IDS)
    def test_encoding_and_layout(self, doc_id: str) -> None:
        raw = (BUNDLE_DIR / DOCS[doc_id]["text_file"]).read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8")
        assert "\r" not in text and "\t" not in text
        assert text.endswith("\n") and not text.endswith("\n\n")
        for number, line in enumerate(_lines(doc_id), start=1):
            assert len(line) <= 110, f"{doc_id} L{number} is {len(line)} chars"
            assert line == line.rstrip(), f"{doc_id} L{number} has trailing whitespace"
        assert 40 <= len(_lines(doc_id)) <= 120

    @pytest.mark.parametrize("doc_id", DOC_IDS)
    def test_header_block(self, doc_id: str) -> None:
        header = _header(doc_id)
        assert header[0] == f"DOCUMENT {doc_id} — {DOCS[doc_id]['title']}"
        for prefix in (
            "Owner/originator:",
            "Record type:",
            "STATUS:",
            "Clock reference:",
            "Value-status legend:",
        ):
            assert any(line.startswith(prefix) for line in header), prefix
        clock = " ".join(
            header[next(i for i, x in enumerate(header) if x.startswith("Clock")) :]
        )
        assert "+01:00" in clock

    @pytest.mark.parametrize("doc_id", SYNTHESISED)
    def test_synthesised_status_label(self, doc_id: str) -> None:
        assert SYNTH_STATUS in " ".join(_header(doc_id))

    def test_r03_status_label(self) -> None:
        assert R03_STATUS in _header("R03")

    def test_r01_status_label(self) -> None:
        header = " ".join(_header("R01"))
        assert "STATUS: REAL MEASURED DATA EXTRACT" in header
        assert "unchanged" in header

    @pytest.mark.parametrize("doc_id", TAGGED_DOCS)
    def test_numeric_lines_carry_value_status_tags(self, doc_id: str) -> None:
        # The header block defines the clock basis and legend (example times are not values).
        skip = _framing_lines(doc_id) | set(range(1, len(_header(doc_id)) + 1))
        for number, line in enumerate(_lines(doc_id), start=1):
            if number in skip:
                continue
            if QUANTITY.search(line):
                assert TAG.search(line), (
                    f"{doc_id} L{number} has a value but no tag: {line!r}"
                )
            assert not re.match(r"\s+\[", line), (
                f"{doc_id} L{number}: tag split from its value"
            )

    @pytest.mark.parametrize("doc_id", TAGGED_DOCS)
    def test_only_known_tags_and_no_illustrative_values(self, doc_id: str) -> None:
        header_len = len(_header(doc_id))
        for number, line in enumerate(_lines(doc_id), start=1):
            for word in BRACKET_WORD.findall(line):
                assert word in ALLOWED_TAGS, f"{doc_id} L{number}: unknown tag [{word}]"
            if number > header_len:
                assert "[illustrative]" not in line, f"{doc_id} L{number}"

    @pytest.mark.parametrize("doc_id", TAGGED_DOCS)
    def test_framing_lines_hold_no_quantities(self, doc_id: str) -> None:
        unit_value = re.compile(r"\d\s?(?:MW|MVAr|kV|kA|ms|Hz|km)\b")
        for number in _framing_lines(doc_id):
            assert not unit_value.search(_lines(doc_id)[number - 1]), (
                f"{doc_id} L{number}"
            )

    @pytest.mark.parametrize("doc_id", DOC_IDS)
    def test_no_frequency_landmarks_in_text(self, doc_id: str) -> None:
        text = _text(doc_id)
        for value in LANDMARK_STRINGS:
            assert value not in text

    def test_no_frequency_landmarks_in_manifest(self) -> None:
        text = (BUNDLE_DIR / "manifest.json").read_text(encoding="utf-8")
        for value in LANDMARK_STRINGS:
            assert value not in text

    @pytest.mark.parametrize(
        ("doc_id", "forbidden"),
        [
            (
                "R01",
                [
                    "minim",
                    "nadir",
                    "lowest",
                    "recover",
                    "LFDD",
                    "below 49",
                    "48.8",
                    "49.1",
                    "Hornsea",
                    "Little Barford",
                    "lightning",
                    "trip",
                ],
            ),
            (
                "R03",
                [
                    "Hornsea",
                    "Little Barford",
                    "LFDD",
                    "demand disconnection",
                    "Hz",
                    "RWE",
                ],
            ),
            (
                "S01",
                ["Little Barford", "LFDD", "Hz", "RWE", "Eaton Socon", "Wymondley"],
            ),
            ("S03", ["Hornsea", "LFDD", "Hz", "Ørsted", "Orsted"]),
            ("S04", ["Hornsea", "LFDD", "Hz", "Ørsted", "Orsted"]),
        ],
    )
    def test_no_cross_document_leakage(self, doc_id: str, forbidden: list[str]) -> None:
        text = _text(doc_id).casefold()
        for term in forbidden:
            assert term.casefold() not in text, f"{doc_id} mentions {term!r}"

    def test_synthesised_records_separate_annotations_from_raw_entries(self) -> None:
        assert "POST-EVENT ANNOTATIONS" in _text("S01")
        assert "dated 5 September 2019" in _text("S01")
        assert "POST-EVENT ANNOTATIONS" in _text("S03")
        assert "dated 30 August 2019" in _text("S03")
        assert "POST-EVENT ANNOTATIONS" in _text("S04")
        assert "dated 30 August 2019" in _text("S04")
        assert "dated 3 January 2020" in _text("S04")
        assert "POST-EVENT ASSESSMENTS" in _text("R03")

    def test_s04_keeps_root_causes_unestablished_in_source_wording(self) -> None:
        text = " ".join(_text("S04").split())
        assert (
            "The root cause of the discrepancy in the speed sensors has not been established."
            in text
        )
        assert (
            "The root cause of these high pressure conditions has not been established."
            in text
        )
        assert (
            "For reasons presently unknown a high-pressure excursion occurred on GT1A"
            in text
        )
        assert "RWE's hypothesis is that the UPS' have initiated a changeover" in text
        assert (
            "it is our preliminary view that the steam turbine's anomalous speed readings"
            in text
        )

    def test_s04_statements_follow_source_order(self) -> None:
        text = " ".join(_text("S04").split())
        narrative = text.index("PART 1 — SHIFT NARRATIVE")
        part2 = text.index("PART 2 — POST-EVENT ANNOTATIONS")
        operator = text.index("Annotation A — operator report", part2)
        regulator = text.index("Annotation B — regulator report", part2)
        assert narrative < part2 < operator < regulator
        # RWE preliminary findings (30 Aug 2019): UPS, then steam turbine, then gas turbines.
        ups = text.index("RWE's hypothesis is", operator)
        steam = text.index("Our investigations have confirmed", operator)
        gas = text.index("For reasons presently unknown", operator)
        assert ups < steam < gas < regulator
        # Ofgem (3 Jan 2020): 3.28 before 3.29; the preliminary view comes last.
        established = text.index("We have established", regulator)
        pressure = text.index("these high pressure conditions", regulator)
        view = text.index("preliminary view", regulator)
        assert established < pressure < view

    def test_s04_narrative_is_chronological(self) -> None:
        lines = _lines("S04")
        order = [
            next(i for i, x in enumerate(lines) if x.startswith(f"N{n}  "))
            for n in range(1, 9)
        ]
        assert order == sorted(order)
        alarms = " ".join(lines[order[1] : order[2]])
        assert "general" in alarms and "UPS -B-" in alarms
        assert "244 MW" in " ".join(lines[order[2] : order[3]])

    @pytest.mark.parametrize("doc_id", TAGGED_DOCS)
    def test_no_builder_conveniences_or_epistemic_labels(self, doc_id: str) -> None:
        text = " ".join(_text(doc_id).split())
        for phrase in (
            "Derived BST",
            "Intervals derived",
            "Intervals computed",
            "derived check",
            "arithmetic check",
            "799 MW - 62 MW",
            "Not established",
            "Not known",
            "Known (",
            "Established (",
            "Still a hypothesis",
            "explicitly a view",
            "not an established finding",
            "hypothesis (not",
            "Compiler's note (not a record)",
            "Mechanism:",
            "Planned:",
            "INVESTIGATION STATUS ADDENDUM",
        ):
            assert phrase not in text, f"{doc_id} contains {phrase!r}"

    def test_s01_gives_no_bst_equivalences_or_computed_loss(self) -> None:
        text = _text("S01")
        clock = [x for x in _lines("S01") if "UTC+01:00" in x]
        assert len(clock) == 1 and clock[0].startswith("Clock reference:")
        assert not re.search(r"\b16[:.]\d\d", text)
        assert "BST" not in text.replace(clock[0], "")
        assert "737" not in text

    def test_s03_gives_raw_offsets_only(self) -> None:
        text = _text("S03")
        body = "\n".join(_lines("S03")[len(_header("S03")) :])
        assert "[estimated]" not in body
        assert not re.search(r"\b16:5[2-4]:\d\d\.\d", text)
        assert text.count("16:52:34") == 1
        for value in ("56.435", "26.993", "27.314", "244 + 210 + 187"):
            assert value not in text
        for offset in ("+1.185 s", "+56.583 s", "+57.620 s", "+83.897 s", "+84.613 s"):
            assert f"{offset} [reported]" in text
        assert "U4  Total loss at the station: 641 MW [reported]" in text

    def test_s03_datum_uncertainty_retained(self) -> None:
        text = _text("S03")
        flat = " ".join(text.split())
        assert "T = 16:52:34 +/- 0.5 s [reported] without stating a clock basis" in flat
        assert "it is read here as BST (UTC+01:00)" in flat
        assert (
            "further work is needed to align T with the datum used by the system operator"
            in flat
        )
        # Since bundle 1.1.0 no absolute T + offset times are given; the reader derives them.
        assert "+01:00 [estimated]" not in text
        assert "(derived)" not in text
        legend = " ".join(" ".join(_header("S03")).split())
        assert "[measured], [estimated] and [illustrative] not used" in legend

    def test_inferred_clock_bases_are_labelled_as_inferences(self) -> None:
        s01 = " ".join(" ".join(_header("S01")).split())
        assert "BST = UTC+01:00 (the operator labels no clock; UTC is inferred)" in s01
        assert "operator's own report gives some times in this UTC form" not in s01
        assert "time as given in the operator's report" not in _text("S01")

    def test_r03_clock_line_states_the_bst_inference(self) -> None:
        header = " ".join(" ".join(_header("R03")).split())
        assert (
            "The sources do not label the clock of the B3 and section C times; they are read as "
            "BST because the ESO report dates this event at 4:52pm" in header
        )
        assert (
            'such anchor (B2, section E) are marked "clock basis not stated"' in header
        )
        lines = _lines("R03")
        assert any(
            x.startswith("SECTION C") and "(times read as BST, +01:00)" in x
            for x in lines
        )

    def test_r03_other_trips_keep_both_published_times_without_offset(self) -> None:
        lines = _lines("R03")
        start = next(i for i, x in enumerate(lines) if x.startswith("SECTION E"))
        end = next(i for i, x in enumerate(lines) if x.startswith("SECTION F"))
        section = " ".join(" ".join(lines[start:end]).split())
        assert "clock basis not stated" in section
        assert "+01:00" not in section
        for stamp in ("16:50:44", "16:43:25", "16:43:54", "14:23:00", "14:23:32"):
            assert f"{stamp} [reported]" in section
        # Since bundle 1.1.0 no compiler's note points out the conflicting times.
        assert "Compiler's note" not in section
        assert "do not resolve the difference" not in section

    def test_r03_section_d_holds_no_assessments(self) -> None:
        lines = _lines("R03")
        start = next(i for i, x in enumerate(lines) if x.startswith("SECTION D"))
        end = next(i for i, x in enumerate(lines) if x.startswith("SECTION E"))
        section = " ".join(lines[start:end]).casefold()
        for phrase in (
            "most likely",
            "fault ride through",
            "sqss",
            "within",
            "limit",
            "complian",
        ):
            assert phrase not in section, phrase

    def test_s01_log_entries_hold_no_interpretation(self) -> None:
        lines = _lines("S01")
        start = next(i for i, x in enumerate(lines) if x.startswith("PART 2"))
        notes = next(i for i, x in enumerate(lines) if x.startswith("Compiler's notes"))
        log = " ".join(lines[start:notes]).casefold()
        for phrase in (
            "caused by",
            "damped",
            "not published",
            "derived",
            "overcurrent",
            "depresses",
            "result of",
        ):
            assert phrase not in log, phrase
        assert "not log content" in lines[notes]

    def test_s01_log_times_claim_no_unpublished_precision(self) -> None:
        lines = _lines("S01")
        dip = next(x for x in lines if "Unbalanced voltage dip" in x)
        assert dip.startswith("15:52:33.490Z [estimated]")
        row_700 = next(
            i for i, x in enumerate(lines) if x.startswith("15:52:33.700Z [reported]")
        )
        assert "20 kV" not in " ".join(lines[row_700 : row_700 + 2])
        bracket = next(x for x in lines if x.startswith("15:52:33.700Z-.835Z"))
        assert (
            bracket.startswith("15:52:33.700Z-.835Z [estimated]") and "34 kV" in bracket
        )
        row_728 = next(x for x in lines if x.startswith("15:52:33.728Z"))
        assert row_728.endswith("Hornsea 1B and Hornsea 1C begin de-loading turbines.")
        assert any(x.startswith("(c) ") for x in lines)
        assert not any(x.startswith("(d) ") for x in lines)

    def test_s04_alarm_entry_states_alarms_without_hypothesis(self) -> None:
        lines = _lines("S04")
        n2 = next(i for i, x in enumerate(lines) if x.startswith("N2  "))
        entry = " ".join(" ".join(lines[n2 : n2 + 2]).split()).casefold()
        assert "general fault alarms" in entry
        assert "hypothes" not in entry and "battery" not in entry
        assert "RWE's hypothesis is" in _text("S04")


# --------------------------------------------------------------------------- provenance


class TestProvenance:
    def test_top_level(self) -> None:
        assert PROVENANCE["bundle_version"] == MANIFEST["bundle_version"]
        assert sorted(PROVENANCE["documents"]) == sorted(DOC_IDS)
        for source_id in ("ESO", "APP", "OFG", "NESO-F"):
            assert source_id in PROVENANCE["sources"]

    def test_source_hashes_match_private_source_manifest(self) -> None:
        entries = {e["id"]: e for e in _load_json(PRIVATE_DIR / "source_manifest.json")}
        assert len(entries) == 7
        for source_id, source in PROVENANCE["sources"].items():
            if source["kind"] in ("pdf", "archive"):
                assert source["sha256"] == entries[source_id]["sha256"]
                assert source["file"] == entries[source_id]["file"]

    @pytest.mark.parametrize("doc_id", DOC_IDS)
    def test_label_and_text_hash(self, doc_id: str) -> None:
        entry = PROVENANCE["documents"][doc_id]
        assert entry["label"] == LABELS[doc_id]
        assert entry["text_sha256"] == _sha256(BUNDLE_DIR / DOCS[doc_id]["text_file"])
        assert entry["construction"]

    @pytest.mark.parametrize("doc_id", DOC_IDS)
    def test_segments_cover_every_non_blank_line_once(self, doc_id: str) -> None:
        lines = _lines(doc_id)
        covered = [0] * (len(lines) + 1)
        for segment in PROVENANCE["documents"][doc_id]["segments"]:
            start, end = _range(segment["lines"])
            assert 1 <= start <= end <= len(lines)
            for number in range(start, end + 1):
                covered[number] += 1
        for number, line in enumerate(lines, start=1):
            if line.strip():
                assert covered[number] == 1, (
                    f"{doc_id} L{number} covered {covered[number]}x"
                )
            else:
                assert covered[number] <= 1

    @pytest.mark.parametrize("doc_id", DOC_IDS)
    def test_segment_sources(self, doc_id: str) -> None:
        sources = PROVENANCE["sources"]
        for segment in PROVENANCE["documents"][doc_id]["segments"]:
            assert segment["content"]
            if segment["extraction_method"] == "framing":
                assert segment["value_status"] == "framing"
                assert segment["sources"] == []
                continue
            assert segment["sources"], segment["lines"]
            for ref in segment["sources"]:
                source = sources[ref["source_id"]]
                if source["kind"] == "archive":
                    assert (ENV_ROOT / ref["script"]).is_file()
                    continue
                assert len(ref["quote"].split()) >= 3, ref
                if source["kind"] == "pdf":
                    assert isinstance(ref["pdf_page"], int) and ref["pdf_page"] >= 1
                    assert ref["section"]

    def test_r01_csv_provenance_is_script(self) -> None:
        artifact = PROVENANCE["documents"]["R01"]["artifacts"][f"R01/{CSV_NAME}"]
        assert artifact["extraction_method"] == "script"
        assert artifact["script"] == "builder/build_r01.py"
        assert artifact["sha256"] == _sha256(BUNDLE_DIR / "R01" / CSV_NAME)
        assert (BUILDER_DIR / "build_r01.py").is_file()

    @pytest.mark.skipif(
        not TEXT_DIR.is_dir(), reason="builder-only extracted PDF text not present"
    )
    def test_quotes_found_on_stated_pages(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "verify_provenance", BUILDER_DIR / "verify_provenance.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report = module.Report()
        checker = module.QuoteChecker(HANDOFF_DIR, TEXT_DIR, PROVENANCE, "off")
        for doc_id in DOC_IDS:
            for segment in PROVENANCE["documents"][doc_id]["segments"]:
                for ref in segment["sources"]:
                    if PROVENANCE["sources"][ref["source_id"]]["kind"] == "pdf":
                        checker.check(f"{doc_id} {segment['lines']}", ref, report)
        assert report.failures == []
        assert report.counts.get("quotes verified on page (extracted text)", 0) > 100

    @pytest.mark.skipif(
        not HANDOFF_DIR.is_dir(), reason="builder-only handoff not present"
    )
    def test_private_source_manifest_is_exact_copy(self) -> None:
        handoff = (HANDOFF_DIR / "source_manifest.json").read_bytes()
        assert (PRIVATE_DIR / "source_manifest.json").read_bytes() == handoff


# --------------------------------------------------------------------------- R01 data


class TestR01Data:
    def test_csv_bytes(self) -> None:
        raw = (BUNDLE_DIR / "R01" / CSV_NAME).read_bytes()
        assert raw.startswith(b"timestamp,frequency_hz\r\n")
        assert raw.endswith(b"\r\n")
        assert raw.count(b"\r\n") == 3901

    @pytest.mark.skipif(
        not HANDOFF_DIR.is_dir(), reason="builder-only handoff not present"
    )
    def test_csv_identical_to_handoff(self) -> None:
        handoff_csv = HANDOFF_DIR / "data" / CSV_NAME
        assert (BUNDLE_DIR / "R01" / CSV_NAME).read_bytes() == handoff_csv.read_bytes()

    def test_structure(self) -> None:
        rows = _csv_rows()
        assert len(rows) == 3900
        assert rows[0][0] == _bst("16:40:00")
        assert rows[-1][0] == _bst("17:44:59")
        assert all(stamp.utcoffset() == BST for stamp, _ in rows)
        assert len({stamp for stamp, _ in rows}) == 3900
        for (earlier, _), (later, _) in zip(rows, rows[1:]):
            assert later - earlier == timedelta(seconds=1)
        assert all(45.0 < value < 55.0 for _, value in rows)

    def test_timestamps_are_iso_with_explicit_offset(self) -> None:
        text = (BUNDLE_DIR / "R01" / CSV_NAME).read_text(encoding="utf-8")
        stamps = [line.split(",")[0] for line in text.splitlines()[1:]]
        pattern = re.compile(r"^2019-08-09T\d{2}:\d{2}:\d{2}\+01:00$")
        assert all(pattern.match(stamp) for stamp in stamps)

    def test_landmarks_reproduced(self) -> None:
        rows = _csv_rows()

        def window(start: str, end: str) -> list[tuple[datetime, float]]:
            return [(t, v) for t, v in rows if _bst(start) <= t < _bst(end)]

        first = min(window("16:52:45", "16:53:10"), key=lambda item: item[1])
        assert first == (_bst("16:52:59"), 49.083)
        event_min = min(window("16:53:20", "16:54:30"), key=lambda item: item[1])
        assert event_min == (_bst("16:53:49"), 48.787)
        assert event_min[1] == min(value for _, value in rows)
        recovered = next((t, v) for t, v in rows if t > event_min[0] and v >= 50.0)
        assert recovered == (_bst("16:57:16"), 50.001)

    def test_below_49_hz_duration_zero_order_hold(self) -> None:
        rows = _csv_rows()
        below = [
            (t, v)
            for t, v in rows
            if _bst("16:52:30") <= t < _bst("16:58:00") and v < 49.0
        ]
        assert len(below) == 33
        assert below[0][0] == _bst("16:53:41")
        assert below[-1][0] == _bst("16:54:13")
        stamps = [t for t, _ in below]
        assert all(b - a == timedelta(seconds=1) for a, b in zip(stamps, stamps[1:]))
        # zero-order hold: each 1-s sample holds until the next sample -> 33 s below threshold
        assert (stamps[-1] + timedelta(seconds=1) - stamps[0]).total_seconds() == 33.0
        # strictly below: no samples sit exactly on the threshold in the window edges
        assert all(v < 49.0 for _, v in below)

    def test_r01_text_matches_csv(self) -> None:
        text = _text("R01")
        csv_lines = (
            (BUNDLE_DIR / "R01" / CSV_NAME).read_text(encoding="utf-8").splitlines()
        )
        quoted = [
            line
            for line in text.splitlines()
            if re.match(r"^2019-08-09T[\d:]+\+01:00,", line)
        ]
        assert quoted == csv_lines[1:6]
        assert "timestamp,frequency_hz" in text
        assert "3900" in text
        assert (
            "2019-08-09T16:40:00+01:00" in text and "2019-08-09T17:44:59+01:00" in text
        )
        assert "14 February 2020" in text
        assert "1 second" in text and "hertz (Hz)" in text
