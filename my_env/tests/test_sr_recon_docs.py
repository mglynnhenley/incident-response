"""Reconstruction track: documents of the system-response bundle (no builder inputs needed).

Covers the copies of MVP bundle 1.1.0, the decision-19 S01, the new records (R08, R10, S05,
S06, S07, S12): text conventions, STATUS labels, value tags, provenance coverage, kept source
conflicts, incomplete fields kept incomplete, and absence of answer leakage.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

ENV_ROOT = Path(__file__).resolve().parents[1]
INCIDENT = ENV_ROOT / "src" / "environment" / "incident"
MVP = INCIDENT / "bundle"
SR = INCIDENT / "bundles" / "system_response"
PROVENANCE = json.loads(
    (INCIDENT / "private" / "system_response" / "provenance_recon.json").read_text(
        "utf-8"
    )
)
META = json.loads(
    (ENV_ROOT / "builder" / "system_response" / "recon" / "documents.json").read_text(
        "utf-8"
    )
)
DOCS = ["R01", "R03", "R08", "R10", "S01", "S03", "S04", "S05", "S06", "S07", "S12"]
NEW = ["R08", "R10", "S05", "S06", "S07", "S12"]
COPIED = ["R01", "R03", "S03", "S04"]
SYNTH = "STATUS: SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE."
LABELS = {
    "R08": "STATUS: RECONSTRUCTED FOR EVALUATION FROM PUBLISHED RECORDS — NOT AN ORIGINAL SYSTEM "
    "EXPORT.",
    "R10": "STATUS: RECONSTRUCTION OF REQUIREMENTS DESCRIBED IN PUBLISHED REPORTS — NOT CODE OR "
    "STANDARD TEXT.",
    "S05": SYNTH,
    "S06": SYNTH,
    "S07": SYNTH,
    "S12": SYNTH,
}
TAGS = {"measured", "reported", "estimated", "modelled", "digitised", "illustrative"}
LANDMARKS = ("48.787", "49.083", "50.001")


def text(doc_id: str) -> str:
    return (SR / doc_id / f"{doc_id}.txt").read_text("utf-8")


def lines(doc_id: str) -> list[str]:
    return text(doc_id).split("\n")[:-1]


def flat(doc_id: str) -> str:
    return " ".join(text(doc_id).split())


def ranges(doc_id: str, method: str | None = None) -> set[int]:
    out: set[int] = set()
    for segment in PROVENANCE["documents"][doc_id]["segments"]:
        if method is None or segment["extraction_method"] == method:
            a, b = (int(x) for x in segment["lines"][1:].split("-L"))
            out.update(range(a, b + 1))
    return out


# --------------------------------------------------------------------------- copies


@pytest.mark.parametrize("doc_id", COPIED)
def test_copies_are_byte_identical_to_mvp(doc_id: str) -> None:
    rel = f"{doc_id}/{doc_id}.txt"
    assert (SR / rel).read_bytes() == (MVP / rel).read_bytes()


def test_r01_csv_is_byte_identical_to_mvp() -> None:
    rel = "R01/frequency_2019-08-09_1640-1745_BST.csv"
    assert (SR / rel).read_bytes() == (MVP / rel).read_bytes()


def test_mvp_bundle_untouched() -> None:
    manifest = json.loads((MVP / "manifest.json").read_text("utf-8"))
    assert manifest["bundle_version"] == "1.1.0"
    for doc in manifest["documents"]:
        for rel, digest in doc["sha256"].items():
            assert hashlib.sha256((MVP / rel).read_bytes()).hexdigest() == digest


def test_s01_differs_from_mvp_only_by_decision_19_clock_line() -> None:
    old = (MVP / "S01" / "S01.txt").read_text("utf-8").split("\n")
    new = lines("S01")
    index = next(i for i, x in enumerate(old) if x.startswith("Clock reference:"))
    assert old[:index] == new[:index]
    assert old[index + 1 : -1] == new[index + 2 :]
    clock = " ".join(new[index : index + 2])
    assert "rendered in UTC with an explicit Z suffix" in clock
    assert "published timeline uses local time" in clock
    assert "except one passage, written 15.52" in clock
    assert "UTC is inferred" not in text("S01")
    assert "UTC+01:00" not in text("S01") and "BST" not in text("S01")


# --------------------------------------------------------------------------- conventions


@pytest.mark.parametrize("doc_id", DOCS)
def test_layout(doc_id: str) -> None:
    raw = (SR / doc_id / f"{doc_id}.txt").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw and b"\t" not in raw
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    for number, line in enumerate(lines(doc_id), 1):
        assert len(line) <= 110, f"{doc_id} L{number}"
        assert line == line.rstrip(), f"{doc_id} L{number}"


@pytest.mark.parametrize("doc_id", NEW)
def test_header_block(doc_id: str) -> None:
    head = lines(doc_id)[: lines(doc_id).index("")]
    meta = next(d for d in META["documents"] if d["doc_id"] == doc_id)
    assert head[0] == f"DOCUMENT {doc_id} — {meta['title']}"
    joined = " ".join(head)
    for prefix in (
        "Owner/originator:",
        "Record type:",
        "Clock reference:",
        "Value-status legend:",
    ):
        assert any(x.startswith(prefix) for x in head), prefix
    assert LABELS[doc_id] in joined


@pytest.mark.parametrize("doc_id", NEW)
def test_value_tags(doc_id: str) -> None:
    framing = ranges(doc_id, "framing")
    head = lines(doc_id).index("")
    quantity = re.compile(
        r"(?<![\w.])[~>+-]?\d[\d,.]*\s?(?:MW|MVAr|kV|kA|ms|Hz|%|GW|GVAs|seconds?|minutes?)(?!\w)"
        r"|\b\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
    )
    tag = re.compile(r"\[(?:%s)\]" % "|".join(sorted(TAGS)))  # noqa: UP031
    for number, line in enumerate(lines(doc_id), 1):
        for word in re.findall(r"\[([a-z]+)\]", line):
            assert word in TAGS, f"{doc_id} L{number}: [{word}]"
        assert not re.match(r"\s+\[(?:%s)\]" % "|".join(sorted(TAGS)), line)  # noqa: UP031
        if number > head and number not in framing and quantity.search(line):
            assert tag.search(line), f"{doc_id} L{number}: {line!r}"


@pytest.mark.parametrize("doc_id", DOCS)
def test_no_frequency_landmarks(doc_id: str) -> None:
    for value in LANDMARKS:
        assert value not in text(doc_id)


@pytest.mark.parametrize("doc_id", DOCS)
def test_provenance_covers_every_line_once(doc_id: str) -> None:
    entry = PROVENANCE["documents"][doc_id]
    raw = (SR / entry["text_file"]).read_bytes()
    assert entry["text_sha256"] == hashlib.sha256(raw).hexdigest()
    counts = [0] * (len(lines(doc_id)) + 1)
    for segment in entry["segments"]:
        a, b = (int(x) for x in segment["lines"][1:].split("-L"))
        for n in range(a, b + 1):
            counts[n] += 1
        if segment["extraction_method"] == "framing":
            assert segment["value_status"] == "framing" and segment["sources"] == []
        else:
            assert segment["sources"], segment["lines"]
            for ref in segment["sources"]:
                assert ref.get("quote") or ref.get("script")
    for n, line in enumerate(lines(doc_id), 1):
        if line.strip():
            assert counts[n] == 1, f"{doc_id} L{n} covered {counts[n]} times"


def test_documents_metadata_matches_files() -> None:
    assert [d["doc_id"] for d in META["documents"]] == DOCS
    for doc in META["documents"]:
        for artifact in doc["artifacts"]:
            path = SR / artifact["file"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
        title = doc["title"].casefold()
        for word in (
            "cause",
            "trip",
            "deload",
            "de-load",
            "lightning",
            "discrepancy",
            "minimum",
        ):
            assert word not in title, (doc["doc_id"], word)


# --------------------------------------------------------------------------- content


def test_s05_keeps_blank_fields_and_both_tables() -> None:
    t = flat("S05")
    assert (
        "D10 Western Power Distribution (WPD) | South West | not given | 110,273" in t
    )
    assert (
        "D01 Scottish Hydro Electric Power Distribution (SHEPD) | not given | 0 MW" in t
    )
    assert "| 160 MW [reported] | 187,427" in t and "| 190 MW [reported] | 187,427" in t
    assert (
        "D15 Totals | 931 MW [reported]" in t and "F15 Total | 973 MW [reported]" in t
    )
    assert "892 MW [reported] of net demand" in t
    assert "+/-0.01 Hz [reported] tolerance setting" in t
    # Early reconnection appears only as Ofgem reports it; no enforcement outcome.
    assert "Eastern Power Networks plc and South Eastern Power Networks plc" in t
    for phrase in ("£", "redress", "voluntary payment", "penalty", "fine"):
        assert phrase not in t.casefold()


def test_s06_attributes_each_estimate_with_basis_in_its_own_words() -> None:
    t = flat("S06")
    assert "combined total of 462 MW [reported]" in t
    assert (
        "unable to determine whether a specific generator tripped due to RoCoF or Vector Shift"
        in t
    )
    for value in (
        "approximately 150 MW [estimated]",
        "approximately 350 MW [estimated]",
        "430 MW [modelled]",
        "1,300 MW [estimated]",
        "1,500 MW [estimated]",
        "at least 500 MW [estimated]",
        "in excess of 200 MW [reported]",
        "approximately 550 MW [estimated]",
        "approximately 500 MW [estimated] of embedded generation was lost in the incident",
        "581 MW [modelled]",
    ):
        assert value in t, value
    assert "No estimate below is a direct measurement" in t
    # Each source's own timing or stage words are inside its entry.
    for words in (
        "at the time of the circuit trip",
        "in the first second after the fault",
        "when system frequency reached 49 Hz [reported]",
        "when the LFDD scheme was triggered",
        "during the event, approximately 500 MW [estimated]",
        "lost in the incident",
        "across the event",
    ):
        assert words in t, words


def test_s06_lists_estimates_by_source_without_builder_stages() -> None:
    """Issue: builder stage headings did T08's separation and overlap for the agent."""
    t = flat("S06")
    for builder_words in (
        "Stage A",
        "Stage B",
        "Stage C",
        "Stage D",
        "Whole event",
        "A and B together",
        "BY STAGE",
        "grouped by the stage",
    ):
        assert builder_words not in t, builder_words
    part3 = t[t.index("PART 3") :]
    headings = [
        "ESO technical report dated 6 September 2019",
        "ESO answers to E3C questions",
        "E3C interim report (October 2019)",
        "Ofgem report dated 3 January 2020",
        "E3C final report (January 2020)",
    ]
    positions = [part3.index(h) for h in headings]
    assert positions == sorted(positions)
    ids = re.findall(r"(?<= )E(\d+) ", part3)
    assert [int(i) for i in ids] == list(range(1, 24))
    # The provenance marks only headings as framing; every entry has sources.
    segments = PROVENANCE["documents"]["S06"]["segments"]
    framing = [s for s in segments if s["value_status"] == "framing"]
    assert all(not s["sources"] for s in framing)
    assert not any(
        re.search(r"Stage [A-D]\b|Stage heading", s["content"]) for s in segments
    )


def test_ofgem_and_e3c_figures_are_tagged_by_their_own_wording() -> None:
    s06, s12 = flat("S06"), flat("S12")
    # Ofgem 2.4.11 and E3C final state the 200 MW as a net reduction, not as modelled.
    assert "further net reduction in generation of 200 MW [reported] at 49 Hz" in s06
    assert "further net reduction in generation of 200 MW [reported] at 49 Hz" in s12
    assert "further net reduction of 200 MW [reported]" in s06
    # Ofgem 2.4.13: the ESO reported 350 MW.
    assert "seen by the transmission system was only 350 MW [reported]" in s06
    for text_ in (s06, s12):
        for line in re.findall(r"(?:Ofgem|E3C)[^;]*?\[modelled\]", text_):
            assert "modelling" in line or "simulation" in line, line


def test_s07_references_boalf_and_keeps_differing_times() -> None:
    t = flat("S07")
    assert "Elexon BOALF, evidence R06" in t
    assert "BOALF" not in " ".join(lines("S07")[13:])
    assert "K4 17:32 [reported] ESO control room informed NGET control room" in t
    assert "M4 17:22 [reported] ENCC informed TNCC" in t
    assert "Q11 WPD West Midland: blank" in t and "17.19 [reported]" in t
    assert "shared cell: UKPN SPN, EPN, LPN" in t


def test_s12_keeps_conflicts_and_the_100_mw_records() -> None:
    t = flat("S12")
    assert "210GVAs [reported]" in t and "219632 MVA.s [estimated]" in t
    assert "1338 MW [reported]" in t and "1314 MW [reported]" in t
    assert "it is unable to precisely point to the source of change" in t
    assert "16:53:40* | -200 MW [modelled]" in t and "does not define the mark" in t
    # Neutral heading: the records are listed by source; 'unexplained' is the agent's call.
    assert "SECTION C — RECORDS OF A CHANGE OF ABOUT 100 MW, BY SOURCE" in t
    assert "UNEXPLAINED" not in t.upper()
    assert "Little Barford GT1B 187 MW [reported] | 1,878 MW [reported]" in t
    assert "at least 1,990MW" in t
    assert "failure of a bypass valve to operate correctly" in t
    assert '"for reasons presently unknown"' in t


def test_r10_is_labelled_requirements_reconstruction() -> None:
    t = flat("R10")
    assert "have not been verified for this exercise" in t
    assert "Stage 1 | 48.80 Hz [reported] | E&W 5 [reported]" in t
    assert "5% [reported] of winter peak demand" in t
    assert "average cold spell" in t
    assert "1800MW" in t and "1,260 MW [reported]" in t
    for figure in ("931", "892", "1,878", "Hornsea", "Little Barford"):
        assert figure not in t


def test_r08_transcribes_every_diagram_arrow() -> None:
    t = lines("R08")
    calls = [x for x in t if re.match(r"C\d\d  \d\d:\d\d \[reported\]", x)]
    assert len(calls) == 43
    assert any(x.startswith("C28  17:32 [reported]  NGESO -> NGET") for x in t)
    assert "Hornsea" not in text("R08") and "Little Barford" not in text("R08")


@pytest.mark.parametrize(
    ("doc_id", "forbidden"),
    [
        ("R08", ["Hornsea", "Little Barford", "RoCoF"]),
        ("R10", ["Hornsea", "Little Barford", "Ørsted", "RWE"]),
        ("S05", ["Hornsea", "Little Barford", "Ørsted", "RWE"]),
        ("S06", ["Hornsea", "Little Barford", "GT1A", "ST1C"]),
    ],
)
def test_no_cross_document_leakage(doc_id: str, forbidden: list[str]) -> None:
    body = text(doc_id)
    for term in forbidden:
        assert term not in body, (doc_id, term)
