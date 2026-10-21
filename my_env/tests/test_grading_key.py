"""The reduced answer key: structure, bindings to report passages and visible evidence."""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from datetime import timedelta
from pathlib import Path

import pytest

from environment.incident import frequency as fq
from environment.incident.catalogue import Catalogue
from environment.incident.grading import TEXT_FIELDS, grade_submission, load_key
from environment.incident.locators import parse_and_validate, parse_iso_instant
from environment.incident.paths import DEFAULT_BUNDLE_DIR
from environment.tasks.gb_2019_electrical_disturbance.prompt import REPORT_EXPECTATIONS

ENV_ROOT = Path(__file__).resolve().parents[1]
HANDOFF_DIR = Path(
    os.environ.get(
        "GB_HANDOFF_DIR",
        str(ENV_ROOT.parent / ".context" / "handoff" / "GB_power_cut_handoff"),
    )
)
TEXT_DIR = Path(os.environ.get("GB_TEXT_DIR", str(HANDOFF_DIR.parent / "text")))
CSV_REL = "R01/frequency_2019-08-09_1640-1745_BST.csv"

KEY = load_key()
CATALOGUE = Catalogue.load(DEFAULT_BUNDLE_DIR)
CRITERIA = {c["criterion_id"]: c for c in KEY["criteria"]}
EXPECTED_IDS = [
    "D1.1", "D1.2", "D1.3", "D1.4", "D1.N",
    "D2.1", "D2.2", "D2.3", "D2.4", "D2.5",
    "D3.1", "D3.2", "D3.3", "D3.4", "D3.5",
    "D4.1", "D4.2", "D4.3", "D4.4",
]  # fmt: skip
MODES = {"auto_numeric", "auto_assisted_human", "human"}

_DASHES = "‐‑‒–—―−﹘﹣－"
_TRANSLATE = {ord(c): "-" for c in _DASHES}
_TRANSLATE.update({ord(c): '"' for c in "“”„‟″«»"})
_TRANSLATE.update({ord(c): "'" for c in "‘’‚‛′´`"})
_TRANSLATE[0x00AD] = None


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATE).casefold()
    return re.sub(r"\s+", " ", text).strip()


def test_key_identity_and_review_status():
    assert KEY["key_version"] == "0.3.1"
    assert KEY["review"]["status"] == "pending_domain_review"
    assert KEY["review_status"] == KEY["review"]["status"]
    bundle = KEY["bundle"]
    assert bundle["bundle_version"] == CATALOGUE.bundle_version
    assert bundle["bundle_sha256"] == CATALOGUE.bundle_sha256
    csv_sha = hashlib.sha256((DEFAULT_BUNDLE_DIR / CSV_REL).read_bytes()).hexdigest()
    assert bundle["r01_csv"] == {"file": CSV_REL, "sha256": csv_sha}


def test_criteria_and_dimensions():
    assert [c["criterion_id"] for c in KEY["criteria"]] == EXPECTED_IDS
    dims = {d["dimension_id"]: d["criteria"] for d in KEY["dimensions"]}
    assert sorted(dims) == ["D1", "D2", "D3", "D4"]
    assert [cid for d in sorted(dims) for cid in dims[d]] == EXPECTED_IDS
    for cid, crit in CRITERIA.items():
        assert crit["dimension"] == cid.split(".")[0]
        assert crit["assessment_mode"] in MODES, cid
        assert crit["expectation"].strip() and crit["title"].strip(), cid
        assert crit["tolerances"], cid
        assert crit["report_passages"], cid
        assert crit["visible_evidence"], cid
        assert crit["examples"]["positive"] and crit["examples"]["negative"], cid
        assert crit["polarity"] == ("negative" if cid == "D1.N" else "positive")
    assert {
        c for c, v in CRITERIA.items() if v["assessment_mode"] == "auto_numeric"
    } == {
        "D3.1",
        "D3.2",
        "D3.3",
        "D3.4",
    }


def test_numeric_tolerances_follow_the_handoff_rules():
    for cid in ("D3.1", "D3.2", "D3.3"):
        auto = CRITERIA[cid]["auto"]
        assert auto["value"]["abs_tol"] == 0.002 and auto["time"]["tol_s"] == 1
    assert CRITERIA["D3.4"]["auto"]["value"] == {
        "expected": 33,
        "full_abs": 1,
        "half_abs": 3,
    }
    for cid in ("D2.1", "D2.2", "D2.3", "D2.4"):
        mw = next(e for e in CRITERIA[cid]["auto"]["elements"] if e["id"] == "mw")
        assert (mw["full_rel"], mw["half_rel"]) == (0.10, 0.25)
    fault = CRITERIA["D1.2"]["auto"]["elements"][0]
    assert fault["tol_s"] == 1 and fault["expected"] == "2019-08-09T16:52:33.490+01:00"


def test_d3_expected_values_come_from_the_frozen_series():
    lm = fq.reference_landmarks(fq.load_series(DEFAULT_BUNDLE_DIR / CSV_REL))
    pairs = {
        "D3.1": lm["first_local_minimum"],
        "D3.2": lm["event_minimum"],
        "D3.3": lm["first_at_or_above_50_after_minimum"],
    }
    for cid, landmark in pairs.items():
        expected = CRITERIA[cid]["expected"]
        assert expected["value_hz"] == landmark["value_hz"]
        assert expected["time"] == landmark["time"]
        assert expected["row"] == landmark["row"]
        assert CRITERIA[cid]["auto"]["value"]["expected"] == landmark["value_hz"]
        assert CRITERIA[cid]["auto"]["time"]["expected"] == landmark["time"]
    d34 = CRITERIA["D3.4"]["expected"]
    assert d34["duration_s"] == lm["below_49"]["covered_below_s"] == 33
    assert d34["first_sample"] == lm["below_49"]["first_below"][0]
    assert d34["last_sample"] == lm["below_49"]["last_below"][0]
    assert d34["missing_s"] == lm["below_49"]["missing_s"] == 0


def _page_texts(source_id: str) -> dict[int, str]:
    raw = (TEXT_DIR / f"{source_id}.txt").read_text(encoding="utf-8")
    marker = re.compile(
        rf"^=== {re.escape(source_id)} PDF page (\d+) ===$", re.MULTILINE
    )
    parts = marker.split(raw)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


PASSAGES = [
    (c["criterion_id"], i, p)
    for c in KEY["criteria"]
    for i, p in enumerate(c["report_passages"])
]


@pytest.mark.skipif(
    not TEXT_DIR.is_dir(), reason="builder-only extracted PDF text not present"
)
@pytest.mark.parametrize(
    ("cid", "index", "passage"), PASSAGES, ids=[f"{c}-{i}" for c, i, _ in PASSAGES]
)
def test_report_passage_quote_is_on_the_stated_pdf_page(cid, index, passage):
    pages = _page_texts(passage["source_id"])
    page = pages.get(passage["pdf_page"])
    assert page is not None, (
        f"{passage['source_id']} has no PDF page {passage['pdf_page']}"
    )
    assert norm(passage["quote"]) in norm(page), (cid, passage["quote"])
    assert len(passage["quote"].split()) >= 3
    if passage["source_id"] == "ESO":
        assert passage["printed_page"] == passage["pdf_page"] + 1
    elif passage["source_id"] == "APP":
        assert passage["printed_page"] is None
    assert passage["role"] in {
        "expected",
        "alternative_account",
        "conflicting_account",
        "context",
    }


def test_every_criterion_has_an_expected_or_context_passage():
    for cid, crit in CRITERIA.items():
        roles = {p["role"] for p in crit["report_passages"]}
        assert roles & {"expected", "context"}, cid


def _locator_text(doc_id: str, locator: str) -> str:
    doc = CATALOGUE.get(doc_id)
    loc = parse_and_validate(locator, doc)
    if loc.kind == "lines":
        return " ".join(doc.lines[loc.start - 1 : loc.end])
    rows = (DEFAULT_BUNDLE_DIR / CSV_REL).read_text(encoding="utf-8").splitlines()[1:]
    if loc.kind == "rows":
        return " ".join(rows[loc.start - 1 : loc.end])
    first = doc.timeseries.first
    a = int((loc.start - first).total_seconds())
    b = int((loc.end - first).total_seconds())
    return " ".join(rows[a : b + 1])


EVIDENCE = [
    (c["criterion_id"], i, v)
    for c in KEY["criteria"]
    for i, v in enumerate(c["visible_evidence"])
]


@pytest.mark.parametrize(
    ("cid", "index", "item"), EVIDENCE, ids=[f"{c}-{i}" for c, i, _ in EVIDENCE]
)
def test_visible_evidence_resolves_and_contains_tokens(cid, index, item):
    assert item["evidence_id"] in CATALOGUE
    assert item["must_contain"], (cid, item)
    text = norm(_locator_text(item["evidence_id"], item["locator"]))
    for token in item["must_contain"]:
        assert norm(token) in text, (cid, item["locator"], token)


def test_all_patterns_compile():
    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in (
                    "all",
                    "none",
                    "context",
                    "context_any",
                    "trigger_any",
                    "unless_any",
                    "statement_any",
                    "uncertainty_patterns",
                    "inferential_patterns",
                    "mechanism_hedge_patterns",
                    "mechanism_negation_patterns",
                    "patterns",
                    "sources",
                    "verbs",
                ):
                    groups = v if v and isinstance(v[0], list) else [v]
                    for group in groups:
                        for pattern in group:
                            re.compile(pattern)
                else:
                    walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(KEY)


def _soe_offsets() -> dict[str, float]:
    """Raw SOE offsets (seconds after T) from S03, by event number."""
    out = {}
    for line in CATALOGUE.get("S03").lines:
        m = re.match(r"^(E\d)\s+.*?\s(T = 0 ms|\+[\d.]+ (?:ms|s)) \[reported\]$", line)
        if m:
            raw = m.group(2)
            if raw.startswith("T"):
                out[m.group(1)] = 0.0
            elif raw.endswith("ms"):
                out[m.group(1)] = float(raw[1:-3]) / 1000
            else:
                out[m.group(1)] = float(raw[1:-2])
    return out


def test_d2_expected_times_are_derived_from_the_soe_offsets():
    """Bundle 1.1.0 gives only offsets: the key's D2.2-D2.4 times are T + offset with
    T = 16:52:34 (S03), and full credit needs the datum uncertainty."""
    offsets = _soe_offsets()
    assert sorted(offsets) == [f"E{i}" for i in range(1, 10)]
    datum = fq.bst("16:52:34")
    events = {"D2.2": ("E3", "E5"), "D2.3": ("E6", "E7"), "D2.4": ("E8", "E9")}
    for cid, (first, last) in events.items():
        crit = CRITERIA[cid]
        want = [datum + timedelta(seconds=offsets[e]) for e in (first, last)]
        got = [parse_iso_instant(t) for t in crit["expected"]["expected_range"]]
        assert got == want, cid
        trip = next(e for e in crit["auto"]["elements"] if e["id"] == "trip_time")
        assert trip["expected_range"] == crit["expected"]["expected_range"]
        assert crit["auto"]["full_if_any"] == [["mw", "trip_time", "datum_uncertainty"]]
    full = CRITERIA["D2.5"]["auto"]["full_if_any"]
    assert full and all(
        {"hornsea_clock_basis", "soe_datum_basis"} <= set(group) for group in full
    )


METHOD_ELEMENTS = {
    "D2.2": ["datum_uncertainty"],
    "D2.3": ["datum_uncertainty"],
    "D2.4": ["datum_uncertainty"],
    "D2.5": ["hornsea_clock_basis", "soe_datum_basis"],
    "D3.5": ["convention", "sampling", "subsecond"],
}


def test_method_elements_read_every_method_field():
    """Method (clock bases, datum uncertainty, duration convention) may be stated in a
    statement, a derivation, a quantity basis or the report: the prompt points agents to
    derivation and quantity.basis for how values were obtained."""
    for cid, crit in CRITERIA.items():
        for element in crit.get("auto", {}).get("elements", []):
            fields = element.get("fields")
            if element["id"] in METHOD_ELEMENTS.get(cid, []):
                assert fields == list(TEXT_FIELDS), (cid, element["id"])
                assert not element.get("statuses"), (cid, element["id"])
            else:
                assert fields is None, (cid, element["id"])


# Checklist A7: each criterion maps to an item of the brief's Report expectations.
EXPECTATION_FOR = {
    "D1.1": "the initiating event",
    "D1.2": "the initiating event",
    "D1.3": "whether the protection performed as required",
    "D1.4": "whether the protection performed as required",
    "D1.N": "the initiating event",
    "D2.1": "each loss of generation",
    "D2.2": "each loss of generation",
    "D2.3": "each loss of generation",
    "D2.4": "each loss of generation",
    "D2.5": "the clock that record uses",
    "D3.1": "each minimum",
    "D3.2": "each minimum",
    "D3.3": "the recovery to 50 Hz",
    "D3.4": "the time below 49 Hz",
    "D3.5": "the limits of the data's sampling",
    "D4.1": "the mechanism that is established",
    "D4.2": "the mechanism that is established",
    "D4.3": "the mechanism that is established",
    "D4.4": "what remains unexplained",
}


def test_every_criterion_maps_to_a_report_expectation():
    assert sorted(EXPECTATION_FOR) == sorted(CRITERIA)
    items = " ".join(" ".join(REPORT_EXPECTATIONS).split())
    for cid, phrase in EXPECTATION_FOR.items():
        assert phrase in items, (cid, phrase)


def test_d44_full_credit_needs_labelled_findings():
    auto = CRITERIA["D4.4"]["auto"]
    labelled = {e["id"]: e for e in auto["elements"] if e["id"].endswith("_labelled")}
    assert set(auto["full_if_any"][0]) == set(labelled)
    for element in labelled.values():
        assert element["statuses"] == ["unknown", "hypothesis"] and element["uncertain"]


def test_severe_flags_defined():
    flags = {f["flag_id"]: f for f in KEY["severe_flags"]}
    assert set(flags) == {"SF1", "SF2", "SF3"}
    assert "root cause" in flags["SF1"]["title"].lower()
    for flag in flags.values():
        assert (
            flag["definition"] and flag["effect_when_confirmed"] and flag["heuristic"]
        )
    assert "SF1" in CRITERIA["D4.4"]["auto"]["severe_flags_zero"]


def _example_submission(cid: str, example: dict) -> dict:
    crit = CRITERIA[cid]
    keyed = crit["visible_evidence"][0]
    finding = {
        "finding_id": "X1",
        "statement": example["statement"],
        "status": example["status"],
        "citations": [
            {"evidence_id": keyed["evidence_id"], "locator": keyed["locator"]}
        ],
    }
    if "quantity" in example:
        finding["quantity"] = {"basis": "key example", **example["quantity"]}
    if "event_time" in example:
        finding["event_time"] = example["event_time"]
    if "derivation" in example:
        finding["derivation"] = example["derivation"]
    sections = []
    if "report" in example:  # report text that goes with the finding
        sections.append({"heading": "Key example", "body": example["report"]})
    return {
        "schema_version": "3.0",
        "variant_id": "baseline",
        "report": {"executive_summary": "Key example [X1].", "sections": sections},
        "findings": [finding],
    }


EXAMPLES = [
    (cid, kind, i, ex)
    for cid, crit in CRITERIA.items()
    for kind in ("positive", "negative")
    for i, ex in enumerate(crit["examples"][kind])
    if ex.get("content") is not None
]


@pytest.mark.parametrize(
    ("cid", "kind", "index", "example"),
    EXAMPLES,
    ids=[f"{c}-{k}-{i}" for c, k, i, _ in EXAMPLES],
)
def test_key_examples_agree_with_the_automated_proposal(cid, kind, index, example):
    """Each example finding, graded on its own, gets the content the key says it should
    (single-statement examples; multi-finding context is not needed for them)."""
    report = grade_submission(_example_submission(cid, example), CATALOGUE, KEY)
    row = next(c for c in report["criteria"] if c["criterion_id"] == cid)
    assert row["content"]["auto_proposal"] == example["content"], (
        cid,
        example["statement"],
        row["content"]["basis"],
    )
