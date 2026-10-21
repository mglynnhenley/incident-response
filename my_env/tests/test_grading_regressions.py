"""Regression tests for reviewed grading defects (automated checks, decisions merge)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from karotte import EvaluationRunConfig
from karotte.schemas import HttpMcpServerConfig

from environment import fake_model
from environment.incident.catalogue import Catalogue
from environment.incident.grading import (
    DecisionsError,
    GradingError,
    grade_submission,
    key_sha256,
    load_key,
    review_template,
)
from environment.incident.paths import DEFAULT_BUNDLE_DIR

ENV_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ENV_ROOT / "tests" / "fixtures"
REFERENCE = (
    ENV_ROOT
    / "src/environment/tasks/gb_2019_electrical_disturbance/reference/reference_submission.json"
)
CATALOGUE = Catalogue.load(DEFAULT_BUNDLE_DIR)
KEY = load_key()
ALL_RETRIEVED = {"available": True, "retrieved": ["R01", "R03", "S01", "S03", "S04"]}
R01_EVENT = [
    {
        "evidence_id": "R01",
        "locator": "time:2019-08-09T16:52:30+01:00/2019-08-09T16:58:00+01:00",
    }
]


def submission(findings: list[dict], summary: str = "Summary.", sections=None):
    return {
        "schema_version": "3.0",
        "variant_id": "baseline",
        "report": {"executive_summary": summary, "sections": sections or []},
        "findings": findings,
    }


def finding(fid: str, statement: str, status: str = "observed", **extra) -> dict:
    return {
        "finding_id": fid,
        "statement": statement,
        "status": status,
        "citations": extra.pop("citations", R01_EVENT),
        **extra,
    }


def rows(report: dict) -> dict[str, dict]:
    return {c["criterion_id"]: c for c in report["criteria"]}


def reference() -> dict:
    return json.loads(REFERENCE.read_text(encoding="utf-8"))


def reviewed_key() -> dict:
    key = copy.deepcopy(KEY)
    key["review"]["status"] = "reviewed"
    key["review_status"] = "reviewed"
    return key


def filled_template(sub: dict, key: dict, **overrides) -> dict:
    """A review template with every pending value decided as the automated proposal
    (content 1 where there is no proposal), assertions supported, explanation noted."""
    template = review_template(sub, key=key, catalogue=CATALOGUE)
    template.update(reviewer="test reviewer", date="2026-10-19")
    for entry in template["criteria"].values():
        auto = entry["_context"]["auto_content"]
        if auto["source"] == "pending":
            entry["content"] = (
                auto["auto_proposal"] if auto["auto_proposal"] is not None else 1
            )
        ev = entry["_context"]["auto_evidence_support"]
        if ev["source"] == "pending":
            entry["evidence_support"] = 1
    for entry in template["assertions"].values():
        entry["verdict"] = "supported"
    template["explanation_quality"] = {"notes": "clear account", "by_dimension": {}}
    template.update(overrides)
    return template


# -- 1. D3 values in statements and qualified units --------------------------------------
STATEMENT_ONLY = [
    finding(
        "F1",
        "First post-fault minimum 49.083 Hz at 16:52:59 BST.",
        event_time="2019-08-09T16:52:59+01:00",
    ),
    finding("F2", "Event minimum 48.787 Hz at 16:53:49 BST."),
    finding(
        "F3", "First sample >= 50 Hz after the minimum: 50.001 Hz at 16:57:16 BST."
    ),
    finding(
        "F4",
        "Frequency was strictly below 49 Hz for 33 s (16:53:41-16:54:13 BST).",
        derivation="count of R01 samples below 49 Hz x 1 s",
    ),
]


def test_d3_values_written_only_in_the_statement_are_scored():
    report = grade_submission(
        submission(STATEMENT_ONLY), CATALOGUE, KEY, ALL_RETRIEVED, None
    )
    r = rows(report)
    for cid in ("D3.1", "D3.2", "D3.3", "D3.4"):
        assert r[cid]["content"]["value"] == 1.0, (cid, r[cid]["content"]["basis"])
        assert r[cid]["content"]["source"] == "auto"
        assert r[cid]["evidence_support"]["value"] == 1, cid
        assert r[cid]["auto_checks"]["candidates"][0]["value_source"] == "statement"


@pytest.mark.parametrize(
    ("unit", "value", "cid"),
    [
        ("Hz (1-s sample)", 48.787, "D3.2"),
        ("hz ", 48.787, "D3.2"),
        ("Hertz", 48.787, "D3.2"),
        ("mHz", 48787, "D3.2"),
        ("s (zero-order hold)", 33, "D3.4"),
        ("seconds below 49 Hz", 33, "D3.4"),
        ("samples", 33, "D3.4"),  # unreadable unit: the statement's "33 s" is used
    ],
)
def test_qualified_units_are_read(unit, value, cid):
    duration = cid == "D3.4"
    f = finding(
        "F1",
        "Strictly below 49 Hz for 33 s, 16:53:41-16:54:13 BST."
        if duration
        else "Event minimum 48.787 Hz at 16:53:49 BST.",
        quantity={"value": value, "unit": unit, "basis": "measured"},
        event_time="2019-08-09T16:53:41+01:00"
        if duration
        else "2019-08-09T16:53:49+01:00",
        derivation="from R01",
    )
    row = rows(grade_submission(submission([f]), CATALOGUE, KEY, ALL_RETRIEVED))[cid]
    assert row["content"]["value"] == 1.0 and row["content"]["source"] == "auto", row[
        "content"
    ]["basis"]


def test_unreadable_quantity_unit_goes_to_a_human():
    f = finding(
        "F1",
        "Strictly below 49 Hz from 16:53:41 to 16:54:13 BST.",
        quantity={"value": 33, "unit": "samples", "basis": "count"},
    )
    report = grade_submission(submission([f]), CATALOGUE, KEY, ALL_RETRIEVED)
    row = rows(report)["D3.4"]
    assert row["content"]["source"] == "pending" and row["content"]["value"] is None
    assert "needs human review" in row["content"]["basis"]
    assert "D3.4" in [n["criterion_id"] for n in report["flags"]["needs_human_review"]]


def test_wrong_statement_value_is_pending_not_failed_or_contradicted():
    f = finding("F1", "The frequency fell to 48.8 Hz at 16:53:49 BST.")
    report = grade_submission(submission([f]), CATALOGUE, KEY, ALL_RETRIEVED)
    row = rows(report)["D3.2"]
    assert row["content"]["source"] == "pending"
    assert row["content"]["auto_proposal"] == 0.0
    assert "D3.2" in [n["criterion_id"] for n in report["flags"]["needs_human_review"]]
    assertion = report["assertion_quality"]["assertions"][0]
    assert assertion["auto_proposal"] is None  # prose values are not judged


def test_structured_wrong_quantity_is_still_decided():
    report = grade_submission(
        json.loads((FIXTURES / "submissions" / "incorrect.json").read_text()),
        CATALOGUE,
        KEY,
    )
    for cid in ("D3.1", "D3.2", "D3.3", "D3.4"):
        row = rows(report)[cid]
        assert row["content"]["value"] == 0 and row["content"]["source"] == "auto"


def test_threshold_in_prose_does_not_create_conflicts_in_the_reference():
    report = grade_submission(reference(), CATALOGUE, KEY)
    assert report["flags"]["conflicting_values"] == []


# -- 2. D3.4 selector -----------------------------------------------------------------
@pytest.mark.parametrize(
    "threshold", ["49Hz", "49 Hz", "49.0Hz", "49.000 Hz", "49-Hz", "49 hertz"]
)
def test_d34_selector_accepts_threshold_spellings(threshold):
    f = finding(
        "F1",
        f"Frequency was strictly below {threshold} for 33 s (16:53:41-16:54:13 BST).",
        citations=[{"evidence_id": "R01", "locator": "rows:822-854"}],
        quantity={"value": 33, "unit": "s", "basis": "zero-order hold"},
        derivation="count of samples below 49 Hz",
    )
    row = rows(grade_submission(submission([f]), CATALOGUE, KEY, ALL_RETRIEVED))["D3.4"]
    assert row["content"]["value"] == 1.0 and row["content"]["source"] == "auto"
    assert row["evidence_support"]["value"] == 1


@pytest.mark.parametrize("other", ["49.083 Hz", "149 Hz", "16:52:33.490"])
def test_d34_selector_rejects_other_numbers(other):
    f = finding(
        "F1",
        f"Something lasted 33 s around {other}.",
        quantity={"value": 33, "unit": "s", "basis": "x"},
    )
    row = rows(grade_submission(submission([f]), CATALOGUE, KEY))["D3.4"]
    assert row["matched_finding_ids"] == []


# -- 3. SF1 only on asserted root causes ------------------------------------------------
SF1_NON_EXAMPLES = [
    "A physical inspection of the Little Barford bypass system during the forthcoming "
    "outage in September 2019 was planned to help determine the root cause of the "
    "pressure excursions.",
    "The root cause of the ST1C speed-signal discrepancy has yet to be established.",
    "The root cause of the ST1C speed-signal discrepancy remains under investigation.",
    "The root cause of the ST1C speed-signal discrepancy is still under investigation.",
    "Little Barford: the operator's review of hardware, software, fault handling and "
    "diagnostic coverage for the steam turbine, aimed at finding the root cause, was "
    "still ongoing.",
    "Ofgem states that the root cause of the discrepancy in the speed sensors has not "
    "been established.",
]
SF1_EXAMPLES = [
    "The root cause of the ST1C trip was a faulty speed sensor.",
    "GT1A tripped because the steam bypass valve failed to open.",
    "A failed speed probe was the underlying cause of the ST1C trip.",
]


def _sf1(report: dict) -> list:
    return [
        s
        for s in report["flags"]["suspected_severe_assertions"]
        if s["flag_id"] == "SF1"
    ]


@pytest.mark.parametrize("where", ["finding", "report"])
@pytest.mark.parametrize("sentence", SF1_NON_EXAMPLES)
def test_sf1_does_not_fire_when_the_cause_is_kept_open(sentence, where):
    sub = reference()
    if where == "finding":
        sub["findings"].append(
            finding(
                "FX",
                sentence,
                status="reported",
                citations=[{"evidence_id": "S03", "locator": "L53-L54"}],
            )
        )
    else:
        sub["report"]["sections"].append({"heading": "Note", "body": sentence})
    report = grade_submission(sub, CATALOGUE, KEY)
    assert _sf1(report) == []
    assert rows(report)["D4.4"]["content"]["auto_proposal"] == 1.0


@pytest.mark.parametrize("sentence", SF1_EXAMPLES)
def test_sf1_still_fires_on_asserted_root_causes(sentence):
    sub = reference()
    sub["findings"].append(
        finding(
            "FX",
            sentence,
            status="reported",
            citations=[{"evidence_id": "S04", "locator": "L56-L63"}],
        )
    )
    report = grade_submission(sub, CATALOGUE, KEY)
    assert [s["location"] for s in _sf1(report)] == ["FX"]
    assert rows(report)["D4.4"]["content"]["auto_proposal"] == 0.0


@pytest.mark.parametrize("flag_id", ["SF1", "SF3"])
def test_key_severe_flag_examples_and_non_examples(flag_id):
    flag = next(f for f in KEY["severe_flags"] if f["flag_id"] == flag_id)
    for kind, expected in (("examples", [flag_id]), ("non_examples", [])):
        for sentence in flag.get(kind, []):
            f = finding(
                "X1",
                sentence,
                status="reported",
                citations=[{"evidence_id": "S04", "locator": "L56-L63"}],
            )
            report = grade_submission(submission([f]), CATALOGUE, KEY)
            hits = [
                s["flag_id"]
                for s in report["flags"]["suspected_severe_assertions"]
                if s["flag_id"] == flag_id and s["location"] == "X1"
            ]
            assert hits == expected, (kind, sentence)


# -- 4. confirmed severe flags have effects and are checked ------------------------------
def _incorrect() -> dict:
    return json.loads((FIXTURES / "submissions" / "incorrect.json").read_text())


def test_confirmed_flag_with_supported_verdict_is_rejected():
    key = reviewed_key()
    sub = _incorrect()
    template = filled_template(sub, key)
    for entry in template["severe_flags"]:
        entry["confirmed"] = True
    with pytest.raises(DecisionsError, match="assertions.I30.verdict is 'supported'"):
        grade_submission(sub, CATALOGUE, key, ALL_RETRIEVED, template)


def test_confirmed_sf1_with_d44_credit_is_rejected():
    key = reviewed_key()
    sub = _incorrect()
    template = filled_template(sub, key)
    for entry in template["severe_flags"]:
        entry["confirmed"] = True
    for fid in ("I30", "I31"):
        template["assertions"][fid]["verdict"] = "unsupported"
    template["criteria"]["D4.4"]["content"] = 1
    with pytest.raises(DecisionsError, match="criteria.D4.4.content is 1"):
        grade_submission(sub, CATALOGUE, key, ALL_RETRIEVED, template)


def test_confirmed_flag_applies_its_effect():
    key = reviewed_key()
    sub = _incorrect()
    template = filled_template(sub, key)
    for entry in template["severe_flags"]:
        entry["confirmed"] = True
    for fid in ("I30", "I31"):
        template["assertions"][fid]["verdict"] = None  # left to the flag's effect
    template["criteria"]["D4.4"]["content"] = None
    report = grade_submission(sub, CATALOGUE, key, ALL_RETRIEVED, template)
    row = rows(report)["D4.4"]
    assert row["content"]["value"] == 0 and row["content"]["source"] == "severe_flag"
    assert row["evidence_support"]["source"] == "not_applicable"
    assertions = {
        a["assertion_id"]: a for a in report["assertion_quality"]["assertions"]
    }
    for fid in ("I30", "I31"):
        assert assertions[fid]["verdict"] == "unsupported"
        assert assertions[fid]["source"] == "severe_flag"
        assert assertions[fid]["confirmed_severe_flags"] == ["SF1"]
    counts = report["assertion_quality"]["counts_all_dimensions"]
    assert counts["pending"] == 0 and counts["unsupported"] >= 2
    assert report["content_coverage"]["by_dimension"]["D4"]["pending"] == 0
    assert report["status"] == "final", report["provisional_reasons"]


def test_rejected_flag_has_no_effect():
    key = reviewed_key()
    sub = _incorrect()
    template = filled_template(sub, key)
    for entry in template["severe_flags"]:
        entry["confirmed"] = False
    report = grade_submission(sub, CATALOGUE, key, ALL_RETRIEVED, template)
    assertions = {
        a["assertion_id"]: a for a in report["assertion_quality"]["assertions"]
    }
    assert assertions["I30"]["source"] == "human"
    assert rows(report)["D4.4"]["content"]["source"] == "human"


# -- 5. explanation quality must be reviewed ---------------------------------------------
def test_untouched_or_missing_explanation_keeps_the_grade_provisional():
    key = reviewed_key()
    sub = reference()
    template = filled_template(sub, key)
    report = grade_submission(sub, CATALOGUE, key, ALL_RETRIEVED, template)
    assert report["status"] == "final", report["provisional_reasons"]
    assert report["explanation_quality"]["source"] == "human"
    for explanation in (
        {"notes": "", "by_dimension": {"D1": "", "D2": "", "D3": "", "D4": ""}},
        {"notes": None, "by_dimension": {"D1": None, "D2": None, "D3": None}},
        {"notes": "   ", "by_dimension": {"D1": "ok", "D2": "ok", "D3": "ok"}},
        None,
    ):
        d = copy.deepcopy(template)
        if explanation is None:
            del d["explanation_quality"]
        else:
            d["explanation_quality"] = explanation
        report = grade_submission(sub, CATALOGUE, key, ALL_RETRIEVED, d)
        assert report["status"] == "provisional", explanation
        assert report["explanation_quality"]["source"] == "pending"
        assert any(
            "explanation quality not reviewed" in r
            for r in report["provisional_reasons"]
        )
    d = copy.deepcopy(template)
    d["explanation_quality"] = {
        "notes": None,
        "by_dimension": {dim: "reviewed" for dim in ("D1", "D2", "D3", "D4")},
    }
    report = grade_submission(sub, CATALOGUE, key, ALL_RETRIEVED, d)
    assert report["status"] == "final" and report["explanation_quality"]["source"] == (
        "human"
    )


# -- 6. crediting a criterion the matcher missed -----------------------------------------
UNMATCHED_D34 = finding(
    "F1",
    "The frequency stayed under the lower statutory limit for 33 s "
    "(16:53:41-16:54:13 BST).",
    citations=[{"evidence_id": "R01", "locator": "rows:822-854"}],
    quantity={"value": 33, "unit": "s", "basis": "zero-order hold"},
    derivation="count of R01 samples below the limit x 1 s",
)


def _credit_d34(finding_ids):
    key = reviewed_key()
    sub = submission([UNMATCHED_D34], summary="See [F1].")
    template = filled_template(sub, key)
    assert template["criteria"]["D3.4"]["_context"]["auto_content"]["value"] == 0
    template["criteria"]["D3.4"].update(
        content=1, evidence_support=None, finding_ids=finding_ids
    )
    report = grade_submission(sub, CATALOGUE, key, {**ALL_RETRIEVED}, template)
    return report, rows(report)["D3.4"]


def test_credited_content_without_match_leaves_evidence_pending():
    report, row = _credit_d34([])
    assert row["content"] == {**row["content"], "value": 1, "source": "human"}
    assert row["evidence_support"]["source"] == "pending"
    assert report["status"] == "provisional"
    assert "1 criteria await human decisions" in report["provisional_reasons"]


def test_credited_content_checks_the_reviewers_findings():
    report, row = _credit_d34(["F1"])
    assert row["evidence_support"]["value"] == 1
    assert row["evidence_support"]["source"] == "auto"
    assert "reviewer's finding_ids" in row["evidence_support"]["basis"]
    assert report["status"] == "final", report["provisional_reasons"]


# -- 7. values and times bound to their entity ---------------------------------------------
def _proposals(statement: str, status: str = "reported", **extra) -> dict:
    f = finding(
        "F1",
        statement,
        status=status,
        citations=[{"evidence_id": "R03", "locator": "L36-L37"}],
        **extra,
    )
    return {
        cid: row["content"]["auto_proposal"]
        for cid, row in rows(grade_submission(submission([f]), CATALOGUE, KEY)).items()
    }


def test_swapped_unit_values_do_not_get_full_credit():
    p = _proposals(
        "GT1A (187 MW) tripped at 16:53:58 BST and GT1B (210 MW) tripped at 16:53:31 BST."
    )
    assert p["D2.3"] == 0.5 and p["D2.4"] == 0.5
    p = _proposals(
        "GT1A (210 MW) tripped at 16:53:31 BST and GT1B (187 MW) tripped at 16:53:58 BST."
    )
    assert p["D2.3"] == 0.5 and p["D2.4"] == 0.5  # right, but no datum uncertainty
    p = _proposals(
        "GT1A (210 MW) tripped at 16:53:31.6 BST and GT1B (187 MW) tripped at "
        "16:53:58.6 BST (times T + offset, T = 16:52:34 ± 0.5 s)."
    )
    assert p["D2.3"] == 1.0 and p["D2.4"] == 1.0


def test_circuit_name_is_not_an_end_name():
    swapped = _proposals(
        "On the Eaton Socon–Wymondley circuit the Wymondley end cleared in 74 ms and "
        "the Eaton Socon end in 70 ms, within 80 ms."
    )
    right = _proposals(
        "On the Eaton Socon–Wymondley circuit the Wymondley end cleared in 70 ms and "
        "the Eaton Socon end in 74 ms, within 80 ms."
    )
    assert swapped["D1.3"] == 0.5 and right["D1.3"] == 1.0
    assert (
        _proposals(
            "Main protection cleared the Eaton Socon–Wymondley fault in 70 ms and 74 ms, "
            "within the 80 ms requirement."
        )["D1.3"]
        == 0.5  # values not tied to an end: generic clearance only
    )


@pytest.mark.parametrize(
    "statement",
    [
        "Hornsea One was generating 799 MW at 16:52:33.531 BST.",
        "Hornsea One's declared export capability was 800 MW; at 16:52:34 BST it was "
        "operating normally.",
        "Hornsea One's active power fell from 799 MW at 16:52:33.531 BST.",
    ],
)
def test_hornsea_pre_event_output_is_not_the_deload(statement):
    assert _proposals(statement)["D2.1"] == 0.0


def test_hornsea_deload_wordings_are_credited():
    assert (
        _proposals(
            "Hornsea One de-loaded by 737 MW between 16:52:33.728 and 16:52:33.835 BST."
        )["D2.1"]
        == 1.0
    )
    assert (
        _proposals(
            "Hornsea One de-loaded from 799 MW to 62 MW at 16:52:33.728 BST.",
        )["D2.1"]
        == 1.0
    )


def test_reference_proposals_are_unchanged_by_binding():
    report = grade_submission(reference(), CATALOGUE, KEY)
    for cid, row in rows(report).items():
        assert row["content"]["auto_proposal"] == 1.0, (cid, row["content"]["basis"])


# -- 8. contradiction rules ----------------------------------------------------------------
BASE = finding(
    "F0",
    "A lightning strike caused a single-phase (blue) to earth fault on one Eaton "
    "Socon–Wymondley 400 kV circuit at 16:52:33.490 BST.",
    status="reported",
    citations=[{"evidence_id": "R03", "locator": "L36-L37"}],
    event_time="2019-08-09T16:52:33.490+01:00",
)


@pytest.mark.parametrize(
    ("statement", "cids", "cite"),
    [
        (
            "The Blyth–Eccles–Stella West trip at 16:50:44 is excluded as the initiator "
            "because it closed without power losses.",
            ("D1.1", "D1.N"),
            "R03:L73-L77",
        ),
        (
            "The earlier Blyth–Eccles–Stella West lightning trip (16:50:44) is discounted "
            "as a trigger; it closed again without losses.",
            ("D1.1", "D1.N"),
            "R03:L73-L77",
        ),
        (
            "GT1A tripped automatically on high steam-bypass pressure; about 27 s later "
            "operating staff tripped GT1B because of excessive steam pressure.",
            ("D2.4", "D4.3"),
            "S04:L50-L52",
        ),
        (
            "Hornsea began de-loading 238 ms after fault inception and the de-load "
            "completed 107 ms after it began; ST1C tripped within about 1 s of the fault.",
            ("D2.5",),
            "S01:L40-L43",
        ),
        (
            "GT1A tripped automatically. GT1B was tripped by the operators about 27 s "
            "later.",
            ("D2.4", "D4.3"),
            "S04:L50-L52",
        ),
    ],
)
def test_correct_wording_is_not_a_contradiction(statement, cids, cite):
    doc, loc = cite.split(":")
    f = finding(
        "F1",
        statement,
        status="inferred",
        citations=[{"evidence_id": doc, "locator": loc}],
    )
    report = grade_submission(submission([BASE, f]), CATALOGUE, KEY)
    for cid in cids:
        assert rows(report)[cid]["auto_checks"]["contradictions"] == [], cid
    assertions = {
        a["assertion_id"]: a for a in report["assertion_quality"]["assertions"]
    }
    assert assertions["F1"]["auto_proposal"] != "contradicted"


def test_operator_trip_counts_as_manual_for_d43():
    f = finding(
        "F1",
        "GT1A tripped automatically on high steam-bypass pressure; about 27 s later "
        "operating staff tripped GT1B because of excessive steam pressure.",
        status="reported",
        citations=[{"evidence_id": "S04", "locator": "L50-L52"}],
    )
    row = rows(grade_submission(submission([f]), CATALOGUE, KEY))["D4.3"]
    assert row["content"]["auto_proposal"] == 1.0


@pytest.mark.parametrize(
    "statement",
    [
        "Hornsea de-loaded 425 ms before ST1C tripped.",
        "ST1C tripped 0.4 s after Hornsea began to de-load.",
        "Hornsea preceded the ST1C trip by 400 ms.",
    ],
)
def test_subsecond_order_between_units_is_still_flagged(statement):
    f = finding(
        "F1",
        statement,
        status="observed",
        citations=[{"evidence_id": "S01", "locator": "L40-L43"}],
    )
    row = rows(grade_submission(submission([f]), CATALOGUE, KEY))["D2.5"]
    assert [c["id"] for c in row["auto_checks"]["contradictions"]] == [
        "subsecond_order_asserted"
    ]


# -- 9. D4.4 needs explicit uncertainty ---------------------------------------------------
def test_hypotheses_naming_causes_do_not_earn_d44():
    findings = [
        finding(
            "H1",
            "A faulty speed sensor may have caused the ST1C trip.",
            status="hypothesis",
            citations=[{"evidence_id": "S04", "locator": "L56-L59"}],
        ),
        finding(
            "H2",
            "A stuck bypass valve may have caused the GT1A high pressure.",
            status="hypothesis",
            citations=[{"evidence_id": "S04", "locator": "L60-L63"}],
        ),
    ]
    row = rows(grade_submission(submission(findings), CATALOGUE, KEY))["D4.4"]
    assert row["content"]["auto_proposal"] == 0.0
    findings[0]["statement"] = (
        "Why the speed signals disagreed is not established; a faulty sensor is one "
        "possibility."
    )
    row = rows(grade_submission(submission(findings), CATALOGUE, KEY))["D4.4"]
    assert row["content"]["auto_proposal"] == 0.5


# -- 10. evidence proposals need a primary, specific citation -------------------------------
INITIATOR = (
    "A lightning strike caused a single-phase (blue) to earth fault on one Eaton "
    "Socon–Wymondley 400 kV circuit at 16:52:33.490 BST."
)


@pytest.mark.parametrize(
    ("locator", "fragment"),
    [
        ("L7-L9", "context spans"),
        ("L1-L107", "much larger"),
        ("L20-L60", "much larger"),
    ],
)
def test_context_or_broad_citations_are_not_proposed_as_support(locator, fragment):
    f = finding(
        "F1",
        INITIATOR,
        status="reported",
        citations=[{"evidence_id": "R03", "locator": locator}],
    )
    r = rows(grade_submission(submission([f]), CATALOGUE, KEY))
    for cid in ("D1.1", "D1.2"):
        ev = r[cid]["evidence_support"]
        assert ev["auto_proposal"] is None and ev["source"] == "pending", cid
    assert fragment in r["D1.2"]["evidence_support"]["basis"]


def test_specific_primary_citation_is_proposed_as_support():
    f = finding(
        "F1",
        INITIATOR,
        status="reported",
        citations=[{"evidence_id": "R03", "locator": "L34-L39"}],
    )
    r = rows(grade_submission(submission([f]), CATALOGUE, KEY))
    assert r["D1.1"]["evidence_support"]["auto_proposal"] == 1
    assert r["D1.2"]["evidence_support"]["auto_proposal"] == 1


def test_every_criterion_has_a_primary_visible_evidence_span():
    for crit in KEY["criteria"]:
        roles = [v["role"] for v in crit["visible_evidence"]]
        assert set(roles) <= {"primary", "context"}, crit["criterion_id"]
        assert "primary" in roles, crit["criterion_id"]


# -- 11. D3 evidence needs the calculation ------------------------------------------------------
def test_derived_duration_without_derivation_needs_review():
    f = finding(
        "F1",
        "Strictly below 49 Hz for 33 s (16:53:41-16:54:13 BST).",
        citations=[{"evidence_id": "R01", "locator": "rows:1-3900"}],
        quantity={"value": 33, "unit": "s", "basis": "zero-order hold"},
    )
    report = grade_submission(submission([f]), CATALOGUE, KEY, ALL_RETRIEVED)
    ev = rows(report)["D3.4"]["evidence_support"]
    assert ev["source"] == "pending" and ev["auto_proposal"] == 1
    assert "no derivation" in ev["basis"]


def test_r01_not_analysed_in_the_episode_needs_review():
    trace = {**ALL_RETRIEVED, "r01_analysed_with_python": False}
    report = grade_submission(reference(), CATALOGUE, KEY, trace)
    for cid in ("D3.1", "D3.2", "D3.3", "D3.4"):
        ev = rows(report)[cid]["evidence_support"]
        assert ev["source"] == "pending", cid
        assert "never analysed with run_python" in ev["basis"]
        assert rows(report)[cid]["content"]["source"] == "auto"  # content unaffected
    trace["r01_analysed_with_python"] = True
    report = grade_submission(reference(), CATALOGUE, KEY, trace)
    assert all(
        rows(report)[cid]["evidence_support"]["source"] == "auto"
        for cid in ("D3.1", "D3.2", "D3.3", "D3.4")
    )


# -- 12. binding ----------------------------------------------------------------------------------
def test_template_binding_carries_key_and_bundle_hashes():
    template = review_template(reference(), key=KEY, catalogue=CATALOGUE)
    assert template["binding"]["key_sha256"] == key_sha256(KEY)
    assert template["binding"]["bundle_sha256"] == CATALOGUE.bundle_sha256


# -- 13. fake model for the example task ----------------------------------------------------------
def _config(task_id: str) -> EvaluationRunConfig:
    return EvaluationRunConfig(
        run_id="t",
        task_id=task_id,
        model="fake",
        model_api_key="k",
        mcp_server_config=HttpMcpServerConfig(host="0.0.0.0", port=8080),
        transcript_file="transcript.json",
    )


def test_fake_model_plays_the_template_script_for_the_example_task():
    messages = fake_model.get_messages(_config("example-task"))
    names = [tc.function.name for m in messages for tc in (m.tool_calls or [])]
    assert names == ["bash"]
    assert messages[0].content.startswith("path: ") and not messages[0].tool_calls
    command = json.loads(messages[1].tool_calls[0].function.arguments)["command"]
    assert "python_version.txt" in command
    assert messages[-1].content == "Done." and not messages[-1].tool_calls
    gb = fake_model.get_messages(_config("gb-2019-electrical-disturbance"))
    assert gb[0].tool_calls[0].function.name == "list_documents"


# -- 14. SF3 ---------------------------------------------------------------------------------------
def test_sf3_ignores_the_word_fine():
    sub = reference()
    sub["report"]["sections"].append(
        {
            "heading": "Limits",
            "body": "One-second samples are too coarse for fine timing of threshold "
            "crossings. The trips fell in one settlement period.",
        }
    )
    report = grade_submission(sub, CATALOGUE, KEY)
    assert report["flags"]["suspected_severe_assertions"] == []
    sub["report"]["sections"][-1]["body"] += " The operators paid £10.5m in redress."
    report = grade_submission(sub, CATALOGUE, KEY)
    assert [s["flag_id"] for s in report["flags"]["suspected_severe_assertions"]] == [
        "SF3"
    ]


# -- 15. key 0.3.0: observed/reported findings worded as inferences (review flag only) -----
LIVE_RUN_F14 = (
    "Frequency fell from 49.995 Hz at 16:52:33 to 49.921 Hz at 16:52:34 and 49.77 Hz at "
    "16:52:35. The largest 1 s fall was 0.151 Hz, consistent with about 981 MW "
    "(737 + 244) lost in about 1.2 s."
)


def _inferential(report: dict) -> dict[str, list[str]]:
    return {
        item["finding_id"]: item["terms"]
        for item in report["flags"]["status_inferential_language"]
    }


def test_live_run_f14_inference_under_observed_is_flagged_but_not_scored():
    """Live run 001, finding F14: an MW inference from a frequency slope, labelled
    observed. The flag proposes a status review; it changes no grade."""
    base = grade_submission(reference(), CATALOGUE, KEY, ALL_RETRIEVED)
    sub = reference()
    sub["findings"].append(
        finding(
            "F14X",
            LIVE_RUN_F14,
            status="observed",
            citations=[{"evidence_id": "R01", "locator": "rows:754-756"}],
            quantity={
                "value": 0.151,
                "unit": "Hz/s",
                "basis": "largest 1 s difference",
            },
            event_time="2019-08-09T16:52:35+01:00",
        )
    )
    report = grade_submission(sub, CATALOGUE, KEY, ALL_RETRIEVED)
    assert _inferential(report) == {"F14X": ["consistent with"]}
    item = report["flags"]["status_inferential_language"][0]
    assert item["status"] == "observed" and "not scored" in item["issue"]
    assert report["content_coverage"] == base["content_coverage"]
    assert report["evidence_support"] == base["evidence_support"]
    assertion = next(
        a
        for a in report["assertion_quality"]["assertions"]
        if a["assertion_id"] == "F14X"
    )
    assert assertion["auto_proposal"] is None and assertion["source"] == "pending"
    template = review_template(sub, key=KEY, catalogue=CATALOGUE)
    assert (
        template["_context"]["flags"]["status_inferential_language"]
        == (report["flags"]["status_inferential_language"])
    )


@pytest.mark.parametrize(
    ("statement", "status", "expected"),
    [
        (LIVE_RUN_F14, "inferred", []),
        (LIVE_RUN_F14, "hypothesis", []),
        (
            "The Hornsea de-load is attributed to the turbine controllers.",
            "reported",
            ["attributed to"],
        ),
        (
            "The second fall therefore came from the GT1A trip, which suggests the "
            "response was exhausted.",
            "reported",
            ["suggests", "therefore"],
        ),
        (
            'NGET: "As such we can be confident that a lightning strike was the cause of '
            "the fault\"; Ofgem: “the evidence suggests NGET's transmission assets "
            "performed as expected”.",
            "reported",
            [],  # inferential wording inside the records' quoted words
        ),
        ("Hornsea One de-loaded from 799 MW to 62 MW.", "reported", []),
    ],
)
def test_inferential_wording_flag(statement, status, expected):
    f = finding(
        "F1",
        statement,
        status=status,
        citations=[{"evidence_id": "R03", "locator": "L89-L90"}],
    )
    report = grade_submission(submission([f]), CATALOGUE, KEY)
    assert sorted(_inferential(report).get("F1", [])) == sorted(expected)


def test_inferential_flag_defaults_when_the_key_has_no_patterns():
    key = copy.deepcopy(KEY)
    del key["conventions"]["inferential_patterns"]
    f = finding("F1", LIVE_RUN_F14, status="observed")
    report = grade_submission(submission([f]), CATALOGUE, key)
    assert _inferential(report) == {"F1": ["consistent with"]}


def test_reference_has_no_inferential_or_hedge_flags():
    flags = grade_submission(reference(), CATALOGUE, KEY)["flags"]
    assert flags["status_inferential_language"] == [] and flags["labelling"] == []


# -- 16. key 0.3.0: Little Barford times are derived (T + offset) with the datum --------------
def _proposals_of(findings: list[dict]) -> dict:
    return {
        cid: row["content"]["auto_proposal"]
        for cid, row in rows(
            grade_submission(submission(findings), CATALOGUE, KEY)
        ).items()
    }


S03_CITE = [{"evidence_id": "S03", "locator": "L21-L29"}]


def test_soe_times_need_the_datum_uncertainty_somewhere():
    trip = finding(
        "F1",
        "ST1C tripped with 244 MW at about 16:52:35.2 BST (T + 1.185 s).",
        status="reported",
        citations=S03_CITE,
    )
    assert _proposals_of([trip])["D2.2"] == 0.5
    datum = finding(
        "F2",
        "Little Barford SOE times are offsets from T = 16:52:34 ± 0.5 s, read as BST.",
        status="reported",
        citations=[{"evidence_id": "S03", "locator": "L6-L9"}],
    )
    assert _proposals_of([trip, datum])["D2.2"] == 1.0


@pytest.mark.parametrize(
    "spelling",
    [
        "± 0.5 s",
        "+/- 0.5 s",
        "+/-0.5 s",
        "plus or minus half a second",
        "datum uncertainty",
    ],
)
def test_datum_uncertainty_spellings(spelling):
    f = finding(
        "F1",
        f"GT1A tripped with 210 MW at about 16:53:31.6 BST (SOE datum T, {spelling}).",
        status="reported",
        citations=S03_CITE,
    )
    assert _proposals_of([f])["D2.3"] == 1.0


def test_soe_offset_without_a_clock_time_is_values_only():
    f = finding(
        "F1",
        "GT1A (210 MW) tripped at T + 57.620 s (T = 16:52:34 ± 0.5 s).",
        status="reported",
        citations=S03_CITE,
    )
    assert _proposals_of([f])["D2.3"] == 0.5


def test_hornsea_utc_reading_needs_its_clock_label():
    unlabelled = finding(
        "F1",
        "Hornsea One de-loaded from 799 MW to 62 MW at 15:52:33.728.",
        status="reported",
        citations=[{"evidence_id": "S01", "locator": "L40-L43"}],
    )
    assert _proposals_of([unlabelled])["D2.1"] == 0.5
    labelled = copy.deepcopy(unlabelled)
    labelled["statement"] = (
        "Hornsea One de-loaded from 799 MW to 62 MW at 15:52:33.728Z (UTC)."
    )
    assert _proposals_of([labelled])["D2.1"] == 1.0
    converted = copy.deepcopy(unlabelled)
    converted["statement"] = (
        "Hornsea One de-loaded from 799 MW to 62 MW at 16:52:33.728 BST (log UTC + 1 h)."
    )
    assert _proposals_of([converted])["D2.1"] == 1.0


# -- 17. key 0.3.0: D2.5 needs both clock bases and no fine Hornsea/ST1C order ---------------
GROUPS = finding(
    "F1",
    "Hornsea and ST1C were lost within about 2 s of the fault, GT1A around a minute "
    "later and GT1B about 27 s after GT1A.",
    status="inferred",
    citations=S03_CITE,
)
CLOCKS = finding(
    "F2",
    "Clock bases: the Hornsea log (S01) is UTC, so BST = UTC + 1 h; the Little Barford "
    "SOE gives offsets from T = 16:52:34 ± 0.5 s.",
    status="reported",
    citations=[{"evidence_id": "S01", "locator": "L6"}],
)


def test_d25_grouping_needs_both_clock_bases():
    assert _proposals_of([GROUPS])["D2.5"] == 0.5
    assert _proposals_of([GROUPS, CLOCKS])["D2.5"] == 1.0
    only_hornsea = copy.deepcopy(CLOCKS)
    only_hornsea["statement"] = "The Hornsea log (S01) is UTC, so BST = UTC + 1 h."
    assert _proposals_of([GROUPS, only_hornsea])["D2.5"] == 0.5


@pytest.mark.parametrize(
    ("statement", "capped"),
    [
        ("Hornsea de-loaded 1.457 s before ST1C tripped.", True),
        ("ST1C's breaker opened 1.46 s after Hornsea began to de-load.", True),
        ("Hornsea, at 16:52:33.728 BST, de-loaded 0.5 s before ST1C.", True),
        ("Hornsea de-loaded 1.457 s before ST1C tripped (± 0.5 s datum).", False),
        ("ST1C tripped about 1.4 s after Hornsea began to de-load.", False),
        ("ST1C tripped within about 2 s of Hornsea.", False),
    ],
)
def test_d25_fine_order_between_units_is_capped(statement, capped):
    f = finding(
        "F3",
        statement,
        status="inferred",
        citations=[{"evidence_id": "S01", "locator": "L40-L43"}],
    )
    row = rows(grade_submission(submission([GROUPS, CLOCKS, f]), CATALOGUE, KEY))[
        "D2.5"
    ]
    hits = [c["id"] for c in row["auto_checks"]["contradictions"]]
    assert hits == (["subsecond_order_asserted"] if capped else []), statement
    assert row["content"]["auto_proposal"] == (0.5 if capped else 1.0)


# -- 18. key 0.3.0: D3.5 needs the stated duration convention ----------------------------------
LIMIT = finding(
    "F1",
    "R01 is a 1-s series; crossing instants between samples cannot be resolved.",
    status="unknown",
    citations=[{"evidence_id": "R01", "locator": "L22-L23"}],
)


@pytest.mark.parametrize(
    "convention",
    [
        "The 33 s counts the samples strictly below 49 Hz.",
        "Samples at or below 49 Hz were counted: 34 s.",
        "Each sample was held until the next (zero-order hold) below 49 Hz.",
        "Linear interpolation between samples gives about 33.96 s below 49 Hz.",
    ],
)
def test_d35_convention_is_required_for_full_credit(convention):
    assert _proposals_of([LIMIT])["D3.5"] == 0.5
    f = finding("F2", convention, status="observed", derivation="run_python on R01")
    assert _proposals_of([LIMIT, f])["D3.5"] == 1.0


@pytest.mark.parametrize(
    ("statement", "capped"),
    [
        ("The R01 frequency data show it crossed 49 Hz at 16:53:40.6.", True),
        (
            "By linear interpolation of the R01 frequency data, it crossed 49 Hz at "
            "about 16:53:40.0.",
            False,
        ),
    ],
)
def test_d35_subsecond_crossing_claims(statement, capped):
    convention = finding(
        "F2", "The 33 s counts the samples strictly below 49 Hz.", status="observed"
    )
    f = finding("F3", statement, status="observed")
    row = rows(grade_submission(submission([LIMIT, convention, f]), CATALOGUE, KEY))[
        "D3.5"
    ]
    assert row["content"]["auto_proposal"] == (0.5 if capped else 1.0)


# -- 19. key 0.3.0: D4.4 needs the agent's own unknown/hypothesis label ------------------------
OPEN_CAUSES = (
    "The root causes of the ST1C speed-signal discrepancy and of the steam bypass "
    "pressure excursions have not been established."
)


@pytest.mark.parametrize(
    ("status", "expected"),
    [("unknown", 1.0), ("hypothesis", 1.0), ("reported", 0.5), ("inferred", 0.5)],
)
def test_d44_open_causes_need_a_labelled_status(status, expected):
    f = finding(
        "F1",
        OPEN_CAUSES,
        status=status,
        citations=[{"evidence_id": "S04", "locator": "L56-L63"}],
    )
    assert _proposals_of([f])["D4.4"] == expected


def test_transmission_fault_asserted_as_speed_cause_is_sf1():
    sub = reference()
    sub["findings"].append(
        finding(
            "FX",
            "The ST1C speed-signal discrepancy was caused by the transmission network "
            "fault.",
            status="reported",
            citations=[{"evidence_id": "S04", "locator": "L64-L66"}],
        )
    )
    report = grade_submission(sub, CATALOGUE, KEY)
    assert [s["location"] for s in _sf1(report)] == ["FX"]
    assert rows(report)["D4.4"]["content"]["auto_proposal"] == 0.0
    sub["findings"][-1]["status"] = "hypothesis"
    report = grade_submission(sub, CATALOGUE, KEY)
    assert _sf1(report) == []
    assert rows(report)["D4.4"]["content"]["auto_proposal"] == 1.0


# -- 20. method elements read derivation, quantity basis and the report ---------------------
def _drop_little_barford_datum(text: str) -> str:
    """The reference text without any ± 0.5 s / datum wording."""
    for old, new in (
        (", each ± 0.5 s", ""),
        (" (± 0.5 s datum)", ""),
        (" ± 0.5 s", ""),
        ("datum", "reference"),
    ):
        text = text.replace(old, new)
    return text


def _ref_without_datum_in_findings() -> dict:
    sub = reference()
    for f in sub["findings"]:
        f["statement"] = _drop_little_barford_datum(f["statement"])
        if f.get("derivation"):
            f["derivation"] = _drop_little_barford_datum(f["derivation"])
    return sub


def _strip_report(sub: dict, fn) -> dict:
    sub["report"]["executive_summary"] = fn(sub["report"]["executive_summary"])
    for section in sub["report"]["sections"]:
        section["body"] = fn(section["body"])
    return sub


def _ref_proposals(sub: dict) -> dict:
    return {
        cid: row["content"]["auto_proposal"]
        for cid, row in rows(grade_submission(sub, CATALOGUE, KEY)).items()
    }


def test_datum_uncertainty_only_in_derivation_earns_full_d22_to_d24():
    """Review probe 1: Little Barford clock times in the statements, the ± 0.5 s datum
    only in each finding's derivation (the method field)."""
    sub = _strip_report(_ref_without_datum_in_findings(), _drop_little_barford_datum)
    assert {c: _ref_proposals(sub)[c] for c in ("D2.2", "D2.3", "D2.4")} == {
        "D2.2": 0.5,
        "D2.3": 0.5,
        "D2.4": 0.5,
    }
    by = {f["finding_id"]: f for f in sub["findings"]}
    for fid in ("F11", "F12", "F13"):
        by[fid]["derivation"] = (
            "T = 16:52:34 ± 0.5 s (S03 datum, read as BST); " + by[fid]["derivation"]
        )
    proposals = _ref_proposals(sub)
    assert [proposals[c] for c in ("D2.2", "D2.3", "D2.4")] == [1.0, 1.0, 1.0]


def test_datum_uncertainty_only_in_the_report_earns_full_d22_to_d24():
    """Review probe 4: ± 0.5 s kept in the report prose, removed from every finding."""
    sub = _ref_without_datum_in_findings()
    report = grade_submission(sub, CATALOGUE, KEY)
    for cid in ("D2.2", "D2.3", "D2.4"):
        row = rows(report)[cid]
        assert row["content"]["auto_proposal"] == 1.0, cid
        element = next(
            e for e in row["auto_checks"]["elements"] if e["id"] == "datum_uncertainty"
        )
        assert element["finding_ids"] == [] and element["finding_id"] is None
        assert element["detail"]["report_locations"] == [
            "report.executive_summary",
            "report.sections[1].body",  # the trip table's SOE rows
            "report.sections[4].body",  # the clock bases in "Evidence and limitations"
        ]
    # report text is matched sentence by sentence: a unit named in one sentence and the
    # ± 0.5 s in another does not count
    sub = _strip_report(sub, _drop_little_barford_datum)
    sub["report"]["sections"].append(
        {
            "heading": "Clocks",
            "body": "Little Barford times are T + offset. That clock is ± 0.5 s.",
        }
    )
    assert _ref_proposals(sub)["D2.2"] == 0.5
    sub["report"]["sections"][-1]["body"] = (
        "Little Barford times are T + offset, ± 0.5 s."
    )
    assert _ref_proposals(sub)["D2.2"] == 1.0


def test_hornsea_clock_basis_only_in_derivation_earns_full_d25():
    """Review probe 2: Hornsea times stated in BST; the UTC log reading + 1 h only in the
    derivation."""
    sub = reference()
    by = {f["finding_id"]: f for f in sub["findings"]}
    by["F10"]["statement"] = (
        "Hornsea One was generating 799 MW before the event; its 1B and 1C phases "
        "de-loaded between 16:52:33.728 and 16:52:33.835 BST, while 1A stayed at 62 MW: "
        "a reduction of 737 MW."
    )
    by["F10"]["derivation"] = "799 MW - 62 MW = 737 MW (S01 L35, L40-L43)."
    by["F15"]["statement"] = by["F15"]["statement"].replace(", the UTC log + 1 h", "")
    by["F15"]["derivation"] = by["F15"]["derivation"].replace(
        "S01 UTC readings + 1 h", "S01 readings"
    )
    by["F16"]["statement"] = by["F16"]["statement"].split(", and the Hornsea log")[0]
    sub = _strip_report(
        sub,
        lambda t: (
            t.replace(
                "the Hornsea log is on UTC and was converted by adding one hour, and ",
                "",
            )
            .replace("operator log in UTC, + 1 h", "operator log")
            .replace("the Hornsea log in UTC (an inference stated in its header), ", "")
        ),
    )
    assert "utc" not in json.dumps(sub).lower().replace("utc+01:00", "")
    d25 = rows(grade_submission(sub, CATALOGUE, KEY))["D2.5"]
    assert d25["content"]["auto_proposal"] == 0.5
    by["F10"]["derivation"] += " S01 log time 15:52:33.728Z + 1 h = 16:52:33.728 BST."
    d25 = rows(grade_submission(sub, CATALOGUE, KEY))["D2.5"]
    assert d25["content"]["auto_proposal"] == 1.0
    element = next(
        e for e in d25["auto_checks"]["elements"] if e["id"] == "hornsea_clock_basis"
    )
    assert element["finding_ids"] == ["F10"]


def test_duration_convention_only_in_quantity_basis_earns_full_d35():
    """Review probe 3: the convention stated only in the duration's quantity basis."""
    sub = reference()
    by = {f["finding_id"]: f for f in sub["findings"]}
    by["F23"]["statement"] = (
        "The frequency was below 49 Hz for 33 s, 16:53:41 to 16:54:13 BST."
    )
    by["F23"]["derivation"] = "run_python on the R01 CSV."
    by["F23"]["quantity"]["basis"] = (
        "count of 1-s samples strictly below 49 Hz (zero-order hold)"
    )
    by["F25"]["statement"] = by["F25"]["statement"].split(" The 33 s")[0]
    sub["report"] = {"executive_summary": "See the findings.", "sections": []}
    d35 = rows(grade_submission(sub, CATALOGUE, KEY))["D3.5"]
    assert d35["content"]["auto_proposal"] == 1.0, d35["content"]["basis"]
    convention = next(
        e for e in d35["auto_checks"]["elements"] if e["id"] == "convention"
    )
    assert convention["finding_ids"] == ["F23"]
    by["F23"]["quantity"]["basis"] = "R01"
    d35 = rows(grade_submission(sub, CATALOGUE, KEY))["D3.5"]
    assert d35["content"]["auto_proposal"] == 0.5


@pytest.mark.parametrize(
    ("report_text", "full"),
    [
        ("The Hornsea log reads 15:52:33.728Z, i.e. 16:52:33.728 BST.", True),
        (
            "The Hornsea log reads 15:52:33.728Z (e.g. the de-load start), 16:52:33.728 BST.",
            True,
        ),
        ("The Hornsea log reads 15:52:33.728Z. That is 16:52:33.728 BST.", False),
    ],
)
def test_report_sentences_do_not_end_at_abbreviations(report_text, full):
    """Live panel opus55-002: 'between 15:52:33.728Z and 15:52:33.835Z, i.e.
    16:52:33.728-.835 BST' states the Hornsea clock basis in one sentence."""
    soe = finding(
        "F2",
        "Little Barford SOE times are offsets from T = 16:52:34 ± 0.5 s.",
        status="reported",
        citations=[{"evidence_id": "S03", "locator": "L6-L9"}],
    )
    sub = submission([GROUPS, soe], summary=report_text)
    d25 = rows(grade_submission(sub, CATALOGUE, KEY))["D2.5"]
    assert d25["content"]["auto_proposal"] == (1.0 if full else 0.5)


def test_fields_do_not_widen_other_elements():
    """Elements without 'fields' (values, times, mechanism text) still read the
    statement only: a GT1B manual trip or MW value in the derivation does not count."""
    f = finding(
        "F1",
        "GT1B tripped at about 16:53:58.6 BST (T + 84.613 s; T = 16:52:34 ± 0.5 s).",
        status="inferred",
        citations=S03_CITE,
        derivation="GT1B output at trip 187 MW (S03 U3).",
    )
    assert _proposals_of([f])["D2.4"] == 0.0


@pytest.mark.parametrize(
    ("element", "message"),
    [
        ({"id": "x", "type": "text", "all": [["a"]], "fields": ["notes"]}, "unknown"),
        (
            {"id": "x", "type": "value", "unit": "MW", "expected": 1, "abs_tol": 0,
             "fields": ["derivation"]},
            "only text elements",
        ),
        (
            {"id": "x", "type": "text", "all": [["a"]], "fields": ["report"],
             "statuses": ["reported"]},
            "no status",
        ),
    ],
)  # fmt: skip
def test_malformed_fields_are_rejected(element, message):
    key = copy.deepcopy(KEY)
    crit = next(c for c in key["criteria"] if c["criterion_id"] == "D2.2")
    crit["auto"]["elements"].append(element)
    with pytest.raises(GradingError, match=message):
        grade_submission(reference(), CATALOGUE, key)


# -- 21. datum uncertainty spellings beyond ± 0.5 s ------------------------------------------
@pytest.mark.parametrize(
    ("spelling", "full"),
    [
        ("± 500 ms", True),
        ("±500ms", True),
        ("+/- 500 ms", True),
        ("plus or minus 500 milliseconds", True),
        ("a half-second uncertainty in T", True),
        ("uncertain by half a second", True),
        ("an uncertainty of 0.5 s in T", True),
        ("0.5 s uncertainty in T", True),
        ("accurate to half a second", True),
        ("about half a second after its shutdown command", False),
        ("57.5 s after T, timing uncertain", False),
    ],
)
def test_datum_uncertainty_equivalent_spellings(spelling, full):
    f = finding(
        "F1",
        f"GT1A tripped with 210 MW at about 16:53:31.6 BST (T + 57.620 s, {spelling}).",
        status="inferred",
        citations=S03_CITE,
    )
    assert _proposals_of([f])["D2.3"] == (1.0 if full else 0.5), spelling


# -- 22. the reference labels derived values inferred -----------------------------------------
def test_reference_labels_derived_times_and_quantities_inferred():
    """Bundle 1.1.0 states no BST clock time for S01/S03 and no 737 MW: findings that
    give them are the agent's derivations (inferred), not 'stated in a record'."""
    by = {f["finding_id"]: f for f in reference()["findings"]}
    assert {fid: by[fid]["status"] for fid in ("F10", "F11", "F12", "F13")} == {
        fid: "inferred" for fid in ("F10", "F11", "F12", "F13")
    }
    for f in by.values():
        basis = (f.get("quantity") or {}).get("basis", "")
        if f["status"] == "reported" and basis:
            assert basis.startswith("reported"), (f["finding_id"], basis)
    fixture = json.loads(
        (FIXTURES / "submissions" / "correct.json").read_text(encoding="utf-8")
    )
    assert fixture == reference()


# -- 23. inferential flag: record wording attributed to its source or quoted ------------------
@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        (
            "The ESO technical report states that all measurements indicate voltages "
            "stayed above the Fault Ride Through profile; Ofgem says the evidence "
            "suggests NGET's assets performed as expected.",
            [],
        ),
        (
            "According to R03, the fault was 4.5 km from Wymondley Main, indicating a "
            "strike near Willian.",
            [],
        ),
        (
            "The operator writes: 'Therefore, we do not now believe the UPS' were "
            "related to the trips'.",
            [],
        ),
        ("The operator's preliminary view was 'most likely' a UPS issue.", []),
        (
            "The ESO report states the trip times; the losses therefore exceeded the "
            "reserve.",
            ["therefore"],
        ),
        (
            "The ESO report's timeline is consistent with a 1 s delay.",
            ["consistent with"],
        ),
        ("The operators' records likely understate the load.", ["likely"]),
    ],
)
def test_inferential_flag_exempts_attributed_and_quoted_record_wording(
    statement, expected
):
    f = finding(
        "F1",
        statement,
        status="reported",
        citations=[{"evidence_id": "R03", "locator": "L89-L90"}],
    )
    report = grade_submission(submission([f]), CATALOGUE, KEY)
    assert sorted(_inferential(report).get("F1", [])) == sorted(expected)


def test_inferential_attribution_comes_from_the_key():
    key = copy.deepcopy(KEY)
    key["conventions"]["inferential_attribution"] = {
        "sources": ["\\bnobody\\b"],
        "verbs": ["\\bstates\\b"],
    }
    f = finding(
        "F1",
        "Ofgem states that the evidence suggests the assets performed as expected.",
        status="reported",
    )
    report = grade_submission(submission([f]), CATALOGUE, key)
    assert _inferential(report) == {"F1": ["suggests"]}
