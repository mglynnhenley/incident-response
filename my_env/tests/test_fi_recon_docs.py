"""Full-investigation reconstruction track: S08, S10, S11 and the full R10 (no builder inputs).

Covers text conventions, STATUS labels, value tags, provenance coverage, the frozen R10 prefix,
source conflicts kept and attributed (never reconciled or pointed out), no invented mechanisms,
and the exclusions: Ofgem's enforcement outcomes (decision 50), named individuals and handles
(decision 51), ESQCR and OC7/OC10 obligations in R10 (handoff T19).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

ENV_ROOT = Path(__file__).resolve().parents[1]
INCIDENT = ENV_ROOT / "src" / "environment" / "incident"
FI = INCIDENT / "bundles" / "full_investigation"
SR = INCIDENT / "bundles" / "system_response"
PROVENANCE = json.loads(
    (INCIDENT / "private" / "full_investigation" / "provenance_recon.json").read_text(
        "utf-8"
    )
)
SR_PROVENANCE = json.loads(
    (INCIDENT / "private" / "system_response" / "provenance_recon.json").read_text(
        "utf-8"
    )
)
META = json.loads(
    (
        ENV_ROOT / "builder" / "full_investigation" / "recon" / "documents.json"
    ).read_text("utf-8")
)
DOCS = ["R10", "S08", "S10", "S11"]
SYNTH = "STATUS: SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE."
LABELS = {
    "R10": "STATUS: RECONSTRUCTION OF REQUIREMENTS DESCRIBED IN PUBLISHED REPORTS — NOT CODE OR "
    "STANDARD TEXT.",
    "S08": SYNTH,
    "S10": SYNTH,
    "S11": SYNTH,
}
TAGS = {"measured", "reported", "estimated", "modelled", "digitised", "illustrative"}
LANDMARKS = ("48.787", "49.083", "50.001")
ENFORCEMENT = re.compile(
    r"£|\b(?:4\.5|1\.5|1\.45|0\.05|10\.5)\s*m\b|voluntary payment|redress|penalt|\bfined?\b",
    re.I,
)


def text(doc_id: str) -> str:
    return (FI / doc_id / f"{doc_id}.txt").read_text("utf-8")


def lines(doc_id: str) -> list[str]:
    return text(doc_id).split("\n")[:-1]


def flat(doc_id: str) -> str:
    return " ".join(text(doc_id).split())


def item(doc_id: str, label: str) -> str:
    rows = lines(doc_id)
    (first,) = [i for i, line in enumerate(rows) if line.startswith(label + " ")]
    last = first
    while last + 1 < len(rows) and rows[last + 1].startswith(" "):
        last += 1
    return " ".join(" ".join(rows[first : last + 1]).split())


# --------------------------------------------------------------------------- conventions


@pytest.mark.parametrize("doc_id", DOCS)
def test_text_conventions_and_label(doc_id: str) -> None:
    data = (FI / doc_id / f"{doc_id}.txt").read_bytes()
    assert b"\r" not in data and b"\t" not in data and data.endswith(b"\n")
    rows = lines(doc_id)
    assert rows[0].startswith(f"DOCUMENT {doc_id} — ")
    assert LABELS[doc_id] in " ".join(rows[:12])
    for number, row in enumerate(rows, 1):
        assert len(row) <= 110 and row == row.rstrip(), f"{doc_id} L{number}"
        assert set(re.findall(r"\[([a-z]+)\]", row)) <= TAGS, f"{doc_id} L{number}"
        assert not re.match(r"\s+\[[a-z]+\]", row), f"{doc_id} L{number}: split tag"
    for value in LANDMARKS:
        assert value not in text(doc_id)


@pytest.mark.parametrize("doc_id", DOCS)
def test_every_line_covered_once_and_hash_pinned(doc_id: str) -> None:
    entry = PROVENANCE["documents"][doc_id]
    data = (FI / doc_id / f"{doc_id}.txt").read_bytes()
    assert entry["text_sha256"] == hashlib.sha256(data).hexdigest()
    rows = lines(doc_id)
    covered = [0] * (len(rows) + 1)
    for segment in entry["segments"]:
        a, b = (int(x) for x in segment["lines"][1:].split("-L"))
        for n in range(a, b + 1):
            covered[n] += 1
        if segment["extraction_method"] != "framing":
            assert segment["sources"], segment["lines"]
    for n, row in enumerate(rows, 1):
        assert covered[n] <= 1, f"{doc_id} L{n} covered twice"
        if row.strip():
            assert covered[n] == 1, f"{doc_id} L{n} not covered"


def test_documents_meta_hashes_match_bundle() -> None:
    for doc in META["documents"]:
        for artifact in doc["artifacts"]:
            data = (FI / artifact["file"]).read_bytes()
            assert artifact["sha256"] == hashlib.sha256(data).hexdigest()
    assert sorted(d["doc_id"] for d in META["documents"]) == DOCS


# --------------------------------------------------------------------------- R10


def test_r10_keeps_increment_a_lines_and_segments() -> None:
    fi = (FI / "R10" / "R10.txt").read_bytes().split(b"\n")
    sr = (SR / "R10" / "R10.txt").read_bytes().split(b"\n")[:-1]
    assert len(sr) == 133
    assert fi[:133] == sr
    old = SR_PROVENANCE["documents"]["R10"]["segments"]
    assert PROVENANCE["documents"]["R10"]["segments"][: len(old)] == old


def test_r10_adds_sections_f_to_k_without_legal_clause_duties() -> None:
    added = "\n".join(lines("R10")[133:])
    for heading in (
        "SECTION F",
        "SECTION G",
        "SECTION H",
        "SECTION I",
        "SECTION J",
        "SECTION K",
    ):
        assert heading in added
    flat_added = " ".join(added.split())
    assert "90% [reported] within 0.5 seconds [reported]" in flat_added
    assert "dampens or limits swings" in flat_added
    assert "Operation Code 6.6.4" in flat_added
    assert "Energy Incident Reporting" in flat_added
    for banned in (
        "ESQCR",
        "Electricity Safety, Quality and Continuity",
        "OC7",
        "OC10",
    ):
        assert banned not in added


# --------------------------------------------------------------------------- S08


def test_s08_keeps_each_sources_counts_attributed() -> None:
    assert "circa 60 [estimated] units" in item("S08", "G04")
    assert "27 [reported] of the affected units were recovered" in item("S08", "G08")
    assert "the 28 [reported] units recovered by the driver" in item("S08", "G20")
    assert "17 [reported] technicians" in item("S08", "G10")
    assert "18 [reported] technicians" in item("S08", "O08")
    o02 = item("S08", "O02")
    for fragment in (
        "31 [reported] trains were stranded",
        "lock-out of 29 [reported] trains",
        "22 [reported] trains were permanently locked out",
        "7 [reported] trains were restored through driver reset",
        "Two Class 387 trains were also trapped",
        "from 30 [reported] trains",
    ):
        assert fragment in o02
    assert "23 [reported] trains were evacuated without incident" in item("S08", "O20")
    assert "30 [reported] trains running the upgraded software" in item("S08", "O21")
    assert "half were restarted" in item("S08", "E02")
    assert "873 [reported] trains delayed" in item("S08", "E05")
    assert "T9   TOTAL | 371 [reported] | 220 [reported] | 14428 [reported]" in lines(
        "S08"
    )


def test_s08_states_threshold_and_200_ms_as_reported_design_facts() -> None:
    o14 = item("S08", "O14")
    assert "minimum frequency of 49.0 Hz [reported]" in o14
    assert "operated as designed" in o14 and "within 200 ms [reported]" in o14
    assert "version 3.25.x went into a temporary lock-out" in item("S08", "O15")
    assert "3.27.x went into permanent lock-out" in item("S08", "O15")
    assert "below 49 Hz [reported] for 16 seconds [reported]" in item("S08", "G01")
    assert "approximately 33 seconds [estimated]" in item("S08", "O03")


def test_s08_route_table_rows_sum_to_printed_totals() -> None:
    rows = [line for line in lines("S08") if re.match(r"^T[1-8]   ", line)]
    values = [
        [int(v) for v in re.findall(r"\| (\d+) \[reported\]", row)] for row in rows
    ]
    assert [sum(col) for col in zip(*values, strict=True)] == [371, 220, 14428]


def test_s08_does_not_point_out_or_reconcile_conflicts() -> None:
    body = flat("S08").casefold()
    for word in (
        "inconsisten",
        "conflict",
        "discrepan",
        "reconcil",
        "in total 51",
        "differs",
    ):
        assert word not in body


# --------------------------------------------------------------------------- S10


def test_s10_has_compliance_record_and_regulator_findings() -> None:
    body = flat("S10")
    assert "export on an interim basis" in body
    assert "remaining unit permitted to export up to 20% [reported]" in body
    assert "L3 Hornsea M1 70% [reported] Frequency test" in body
    assert "17.012019" in body
    assert (
        "We are not aware of concerns regarding the compliance testing process." in body
    )
    assert "relied significantly on self-certification" in body
    assert (
        "do not appear to have technically met the requirements of the Grid Code"
        in body
    )
    assert "root cause of the discrepancy has not been established" in body
    assert "preliminary view" in body


def test_s10_excludes_enforcement_outcomes() -> None:
    for doc_id in DOCS:
        assert not ENFORCEMENT.search(text(doc_id)), doc_id
    assert "Section 4" not in flat("S10")
    excluded = PROVENANCE["excluded_from_agent_evidence"]
    assert any("£4.5m" in p["quote"] for p in excluded["passages"])
    assert any("£1.45m" in p["quote"] for p in excluded["passages"])


def test_s10_takes_nothing_from_ofgem_section_4() -> None:
    """Ofgem section 4 ('Compliance, voluntary action and enforcement') is excluded whole
    (decision 50): its 4.4 'no formal legal determination' was about agreeing the voluntary
    resolution, so restating it without that clause would misstate it as a general point."""
    body = flat("S10")
    for phrase in (
        "Ofgem 4.4",
        "formal legal determination",
        "different interpretations",
        "voluntary resolution",
        "extent of any breaches",
    ):
        assert phrase not in body, phrase
    assert not any(line.startswith("G06") for line in lines("S10"))
    cited = {
        ref["section"]
        for seg in PROVENANCE["documents"]["S10"]["segments"]
        for ref in seg.get("sources", [])
        if ref.get("source_id") == "OFG"
    }
    assert not any(section.startswith("Section 4") for section in cited), cited
    detectors = PROVENANCE["excluded_from_agent_evidence"]["detector_patterns"]
    for pattern in ("voluntary resolution", "formal legal determination"):
        assert pattern in detectors
        for doc_id in DOCS:
            assert not re.search(pattern, text(doc_id), re.I), (doc_id, pattern)


# --------------------------------------------------------------------------- S11


def test_s11_distinguishes_lfdd_from_own_protection_without_linking_sites() -> None:
    assert "Ipswich Hospital internal protection operated" in item("S11", "H01")
    assert "not part of its LFDD protection zone" in item("S11", "H02")
    assert "disconnected as a result of the LFDD operation" in item("S11", "A01")
    assert (
        "18 minutes [reported] between 16:53 [reported] and 17:11 [reported]"
        in item("S11", "A02")
    )
    assert "after 17 minutes [reported]" in item("S11", "A05")
    h04 = item("S11", "H04")
    assert "11 [reported] generators" in h04 and "Ipswich" not in h04
    assert "Wirral" in item("S11", "P04") and "428 minutes [reported]" in item(
        "S11", "P04"
    )
    assert "no track supplies were lost" in item("S11", "P01")


def test_s11_refinery_and_water_keep_source_mechanisms_only() -> None:
    f01, f02 = item("S11", "F01"), item("S11", "F02")
    assert "detected a drop in frequency" in f01 and "internal safety systems" in f02
    for doc_line in (f01, f02, item("S11", "W01"), item("S11", "W02")):
        assert "Stanlow" not in doc_line
    x02 = item("S11", "X02")
    assert "12 September 2019" in x02 and "Stanlow" in x02
    assert "9 August" not in x02 and "different" not in x02.casefold()


def test_no_named_individuals_or_handles() -> None:
    for doc_id in DOCS:
        body = text(doc_id)
        assert not re.search(r"(?<![\w.])@[A-Za-z0-9_]{2,}", body), doc_id
        for name in ("Julian Leslie", "Kwarteng", "Moloney", "Simon Wilde", "Bousso"):
            assert name not in body, (doc_id, name)
