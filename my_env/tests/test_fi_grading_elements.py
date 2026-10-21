"""The element types the full-investigation key adds (environment.incident.fi_elements):
counts bound to their clause (with the lessons of increment A's real submissions: a
candidate is never silently scored 0, a structured quantity that describes something
else falls back to the statement, another account's figure needs its source), the
executive summary, report sections and the word limit."""

from __future__ import annotations

import pytest
from fi_grading_support import auto, finding, grade, row, submission

from environment.incident import fi_elements as fe
from environment.incident.grading import normalise


def _counts(text: str, **kw) -> list[int]:
    return [v for v, _, _ in fe.count_mentions(normalise(text), **kw)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("29 trains were locked out", [29]),
        ("twenty-nine trains", [29]),
        ("Twenty two needed a technician", [22]),
        ("seven were reset", [7]),
        ("14,428 delay minutes", [14428]),
        ("two Class 387 trains", [2]),
        # labels, versions, times, dates, decimals, units and years are not counts
        ("Class 700 and Class 717 units", []),
        ("software 3.25.x and version 3.27", []),
        ("at 16:53 BST", []),
        ("on 9 August 2019", []),
        ("48.8 Hz within 200 ms", []),
        ("428 minutes of delay", []),
        ("Stage 1 of LFDD", []),
        ("incident 224904", []),  # an identifier labelled as such
        ("about 22-30 trains", []),
    ],
)
def test_count_mentions(text, expected):
    assert _counts(text) == expected


def test_allowed_units_count():
    assert _counts("428 minutes of delay", allow_units=["minutes?"]) == [428]


@pytest.mark.parametrize(
    ("text", "start_word", "clause"),
    [
        (
            "ORR reports that 29 Class 700 and 717 trains were locked out by their protection.",
            "29",
            "orr reports that 29 class 700 and 717 trains were locked out by their protection.",
        ),
        (
            "22 needed a technician and 7 were reset by drivers.",
            "7",
            "7 were reset by drivers.",
        ),
        (
            "Of the 29 trains locked out, 22 needed a technician on site.",
            "22",
            "22 needed a technician on site.",
        ),
    ],
)
def test_count_clause(text, start_word, clause):
    norm = normalise(text)
    assert fe.count_clause(norm, norm.index(start_word)).strip() == clause


def _f(statement, status="reported", **extra):
    return finding("F1", statement, status, [("S08", "L120-L127")], **extra)


def test_count_credit_needs_the_wording_in_the_clause():
    report = grade(submission([_f("ORR counts 29 Class 700/717 trains locked out.")]))
    assert auto(report, "T10.02a") == 1
    # 29 stated, but its clause is about something else: a candidate for a human
    report = grade(
        submission(
            [_f("Twenty-nine trains were affected, of which most were locked out.")]
        )
    )
    r = row(report, "T10.02a")
    assert r["content"]["auto_proposal"] == 1  # "affected" is lock-out wording
    report = grade(
        submission([_f("There were 29 of them; ORR says they were locked out.")])
    )
    r = row(report, "T10.02a")
    assert r["content"]["auto_proposal"] == 0
    assert "not credited automatically" in r["content"]["basis"]


def test_count_in_the_report_only_goes_to_a_human():
    report = grade(
        submission(
            [_f("Rail services were disrupted.")],
            "ORR: 22 trains were permanently locked out and needed a technician.",
        )
    )
    r = row(report, "T10.02b")
    assert r["content"]["auto_proposal"] == 0
    assert "only in the report text" in r["content"]["basis"]


def test_alternative_count_needs_its_source():
    gtr = grade(submission([_f("GTR says 27 units were recovered by Battery Reset.")]))
    assert auto(gtr, "T10.02c") == 0.5
    bare = grade(submission([_f("27 units were recovered by Battery Reset.")]))
    r = row(bare, "T10.02c")
    assert r["content"]["auto_proposal"] == 0
    detail = r["auto_checks"]["elements"][0]["detail"]
    assert detail["alternative_without_source"][0]["value"] == 27


def test_count_with_the_other_meaning_is_not_credited():
    report = grade(submission([_f("7 trains needed a technician with a laptop.")]))
    r = row(report, "T10.02c")
    assert r["content"]["auto_proposal"] == 0
    assert r["auto_checks"]["elements"][0]["detail"]["wrong_meaning"]
    report = grade(submission([_f("There were 14,428 trains delayed.")]))
    assert auto(report, "T10.05b") == 0


def test_structured_quantity_count_and_statement_fallback():
    as_count = _f(
        "ORR's count of trains locked out by their protection.",
        quantity={"value": 29, "unit": "trains", "basis": "ORR 1.0"},
    )
    assert auto(grade(submission([as_count])), "T10.02a") == 1
    # a quantity in MW describes something else: the statement is read instead
    other = _f(
        "The disturbance tripped 29 trains into lock-out.",
        quantity={"value": 737, "unit": "MW", "basis": "Hornsea"},
    )
    assert auto(grade(submission([other])), "T10.02a") == 1


def test_hypothesis_and_suspected_findings_earn_no_count_credit():
    report = grade(
        submission([_f("Perhaps 29 trains were locked out.", status="hypothesis")])
    )
    assert auto(report, "T10.02a") == 0


def test_summary_text_reads_the_executive_summary_only():
    f = finding("F1", "Lightning struck the circuit.", "reported", [("R03", "L25-L27")])
    in_summary = grade(
        submission(
            [f],
            summary="A lightning strike hit the Eaton Socon–Wymondley 400 kV circuit [F1].",
        )
    )
    r = row(in_summary, "T20.01")
    assert r["content"]["auto_proposal"] == 1 and r["matched_finding_ids"] == ["F1"]
    in_section = grade(
        submission(
            [f],
            "A lightning strike hit the Eaton Socon–Wymondley 400 kV circuit [F1].",
            summary="An event happened [F1].",
        )
    )
    assert auto(in_section, "T20.01") == 0


def test_summary_overclaim_and_word_limit():
    f = finding("F1", "x", "reported", [("S04", "L56-L59")])
    calibrated = grade(submission([f], summary="The root causes remain unknown [F1]."))
    assert auto(calibrated, "T20.06") == 1
    overclaim = grade(
        submission(
            [f], summary="The data prove the root cause was a faulty sensor [F1]."
        )
    )
    r = row(overclaim, "T20.06")
    assert r["content"]["auto_proposal"] == 0
    detail = next(
        e for e in r["auto_checks"]["elements"] if e["id"] == "summary_overclaims"
    )
    assert detail["detail"]["matching_sentences"]
    no_refs = grade(submission([f], summary="The root causes remain unknown."))
    assert auto(no_refs, "T20.06") == 0
    words = row(calibrated, "T20.06")["auto_checks"]["elements"][0]
    assert words["detail"] == {"words": 6, "max_words": 600}
    assert calibrated["flags"]["executive_summary"] == {
        "words": 6,
        "limit": 600,
        "within_limit": True,
    }


def test_section_text_needs_the_heading_and_references():
    f1 = finding(
        "F1", "Hornsea relied on self-certification.", "reported", [("S10", "L98-L105")]
    )
    f2 = finding(
        "F2", "Modelling concerns were not shared.", "reported", [("S10", "L126-L132")]
    )
    body = "The ESO should review compliance testing of complex connections [F1, F2]."
    linked = grade(
        submission([f1, f2], sections=[{"heading": "Recommendations", "body": body}])
    )
    assert auto(linked, "T18.01") == 1
    one_ref = grade(
        submission(
            [f1, f2],
            sections=[{"heading": "Recommendations", "body": body.replace(", F2", "")}],
        )
    )
    assert auto(one_ref, "T18.01") == 0.5
    wrong_heading = grade(
        submission([f1, f2], sections=[{"heading": "Findings", "body": body}])
    )
    assert auto(wrong_heading, "T18.01") == 0


def test_recommendations_stated_as_findings_count_but_requirements_do_not():
    rec = finding(
        "F1",
        "Recommendation: the ESO should strengthen compliance testing of generators.",
        "inferred",
    )
    assert auto(grade(submission([rec])), "T18.02") == 0.5
    requirement = finding(
        "F1",
        "The Grid Code requires DNOs to notify the ESO of LFDD operation.",
        "reported",
    )
    report = grade(submission([requirement]))
    for cid in ("T18.04", "T18.05", "T18.06"):
        assert auto(report, cid) == 0, cid
