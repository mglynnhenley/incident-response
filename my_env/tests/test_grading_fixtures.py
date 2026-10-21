"""Grading of the fixture submissions: automated outcomes and validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from environment.incident.catalogue import Catalogue
from environment.incident.grading import grade_submission, load_key
from environment.incident.paths import DEFAULT_BUNDLE_DIR
from environment.incident.submission import validate_submission

ENV_ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS = ENV_ROOT / "tests" / "fixtures" / "submissions"
REFERENCE = (
    ENV_ROOT
    / "src/environment/tasks/gb_2019_electrical_disturbance/reference/reference_submission.json"
)
CATALOGUE = Catalogue.load(DEFAULT_BUNDLE_DIR)
KEY = load_key()
D3_AUTO = ("D3.1", "D3.2", "D3.3", "D3.4")


def load(name: str) -> dict:
    return json.loads((SUBMISSIONS / f"{name}.json").read_text(encoding="utf-8"))


def grade(name: str) -> dict:
    return grade_submission(load(name), CATALOGUE, KEY)


def rows(report: dict) -> dict[str, dict]:
    return {c["criterion_id"]: c for c in report["criteria"]}


def proposal(report: dict, cid: str):
    return rows(report)[cid]["content"]["auto_proposal"]


@pytest.fixture(scope="module")
def graded() -> dict[str, dict]:
    return {
        name: grade(name)
        for name in ("correct", "uncited", "incorrect", "uncertain", "incomplete")
    }


# -- the fixtures themselves ------------------------------------------------------------
def test_correct_is_the_reference_submission():
    assert (SUBMISSIONS / "correct.json").read_bytes() == REFERENCE.read_bytes()


def test_uncited_is_the_reference_without_citations():
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    expected = copy.deepcopy(reference)
    for finding in expected["findings"]:
        finding["citations"] = []
        finding.pop("derivation", None)  # a derivation requires citations
    assert load("uncited") == expected


@pytest.mark.parametrize(
    "name", ["correct", "uncited", "incorrect", "uncertain", "incomplete"]
)
def test_valid_fixtures_validate(name):
    result = validate_submission(load(name), CATALOGUE)
    assert result.ok, result.errors


INVALID = {
    "invalid_schema": [
        ("findings[0].status", "must be one of"),
        ("findings[1].citations", "required field is missing"),
        ("findings[2].confidence", "unexpected field"),
    ],
    "invalid_unknown_evidence": [
        ("findings[0].citations[0].evidence_id", "unknown evidence_id 'R04'")
    ],
    "invalid_bad_locator": [
        ("findings[0].citations[0].locator", "out of range"),
        ("findings[10].citations[0].locator", "outside the R01 series"),
        ("findings[11].citations[0].locator", "malformed line locator"),
    ],
    "invalid_summary_601_words": [("report.executive_summary", "has 601 words")],
    "invalid_duplicate_ids": [("findings[1].finding_id", "duplicate finding_id 'F01'")],
    "invalid_unknown_ref": [("report.sections[0].body", "references [F99]")],
}


@pytest.mark.parametrize("name", sorted(INVALID))
def test_invalid_fixtures_are_rejected(name):
    result = validate_submission(load(name), CATALOGUE)
    assert not result.ok and result.submission is None
    for path, fragment in INVALID[name]:
        assert any(
            e["path"] == path and fragment in e["message"] for e in result.errors
        ), (path, fragment, result.errors)


def test_summary_fixture_is_exactly_one_word_over():
    assert (
        len(load("invalid_summary_601_words")["report"]["executive_summary"].split())
        == 601
    )
    assert len(load("correct")["report"]["executive_summary"].split()) <= 600


# -- automated outcomes -----------------------------------------------------------------
def test_report_has_no_overall_score(graded):
    for report in graded.values():
        for banned in ("score", "overall_score", "pass", "passed", "rank", "ranking"):
            assert banned not in report
        assert "overall" not in report["content_coverage"]
        assert "overall" not in report["evidence_support"]
        assert report["status"] == "provisional"
        assert any("pending_domain_review" in r for r in report["provisional_reasons"])


def test_correct_all_d3_auto_pass_with_evidence(graded):
    report = graded["correct"]
    for cid in D3_AUTO:
        row = rows(report)[cid]
        assert row["content"] == {**row["content"], "value": 1.0, "source": "auto"}
        assert row["evidence_support"]["value"] == 1
        assert row["evidence_support"]["source"] == "auto"
    for cid, row in rows(report).items():
        assert row["content"]["auto_proposal"] == 1.0, cid
        assert row["evidence_support"]["auto_proposal"] == 1, cid
    flags = report["flags"]
    assert flags["uncited_findings"] == [] and flags["unresolvable_citations"] == []
    assert flags["suspected_severe_assertions"] == []
    assert flags["conflicting_values"] == [] and flags["labelling"] == []
    assert flags["status_inferential_language"] == []
    assert sorted(flags["labelled_unknowns"]) == ["F16", "F25", "F37", "F38"]
    assert sorted(flags["labelled_hypotheses"]) == ["F39", "F40"]
    assert report["bundle"]["matches_key"] is True
    coverage = report["content_coverage"]["by_dimension"]["D3"]
    assert coverage["decided"] == 4 and coverage["decided_content_sum"] == 4
    assert coverage["pending"] == 1  # D3.5 needs a human decision


def test_uncited_keeps_content_but_loses_evidence_support(graded):
    correct, uncited = graded["correct"], graded["uncited"]
    for cid, row in rows(uncited).items():
        assert row["content"]["auto_proposal"] == proposal(correct, cid), cid
        assert row["content"]["value"] == rows(correct)[cid]["content"]["value"], cid
        assert row["evidence_support"]["value"] == 0, cid
        assert row["evidence_support"]["source"] == "auto", cid
    flags = uncited["flags"]
    assert len(flags["uncited_findings"]) == len(load("uncited")["findings"])
    for dim, support in uncited["evidence_support"]["by_dimension"].items():
        assert (
            support["supported"] == 0 and support["unsupported"] == support["criteria"]
        ), dim


def test_incorrect_numeric_failures_and_flags(graded):
    report = graded["incorrect"]
    r = rows(report)
    bases = {
        "D3.1": "value off by 0.017",
        "D3.2": "value off by 0.013",
        "D3.3": "time off by 16 s",
        "D3.4": "value off by 17",
    }
    for cid, basis in bases.items():
        assert r[cid]["content"]["value"] == 0 and r[cid]["content"]["source"] == "auto"
        assert basis in r[cid]["content"]["basis"]
        assert r[cid]["evidence_support"]["source"] == "not_applicable"
    assert proposal(report, "D1.1") == 0
    assert proposal(report, "D1.N") == 0
    assert "other_trip_as_initiator" in r["D1.N"]["content"]["basis"]
    assert "reclose_as_second_initiator" in r["D1.4"]["content"]["basis"]
    assert proposal(report, "D2.1") == 0  # 400 MW and the UTC time read as BST
    assert proposal(report, "D2.2") == 1 and proposal(report, "D2.3") == 1
    assert proposal(report, "D2.4") == 0.5  # capped: GT1B called automatic
    assert proposal(report, "D4.1") == 0  # DRC asserted as the cause
    assert proposal(report, "D4.2") == 0  # the only speed statement is the severe one
    assert proposal(report, "D4.4") == 0
    severe = report["flags"]["suspected_severe_assertions"]
    assert {(s["flag_id"], s["location"]) for s in severe} >= {
        ("SF1", "I30"),
        ("SF1", "I31"),
        ("SF1", "report.executive_summary"),
    }
    assert all(s["confirmed"] is None for s in report["severe_flags"])
    proposals = {
        a["assertion_id"]: a["auto_proposal"]
        for a in report["assertion_quality"]["assertions"]
    }
    for fid in ("I01", "I02", "I13", "I20", "I21", "I22", "I23", "I32"):
        assert proposals[fid] == "contradicted", fid
    assert proposals["I30"] == proposals["I31"] == "unsupported"
    assert proposals["I11"] is None  # correct values are not judged automatically


def test_uncertain_has_coverage_gaps(graded):
    report = graded["uncertain"]
    r = rows(report)
    for cid, row in r.items():
        expected = 1.0 if cid == "D4.4" else 0.0
        assert row["content"]["auto_proposal"] == expected, cid
    for cid in D3_AUTO:
        assert "no finding reports this landmark" in r[cid]["content"]["basis"]
    quality = report["assertion_quality"]
    assert quality["counts_all_dimensions"]["labelled_hypothesis_or_unknown"] == 5
    assert quality["counts_all_dimensions"]["pending"] == 0
    for dim_quality in quality["by_dimension"].values():
        assert dim_quality["precision"] is None
        assert dim_quality["precision_note"] == "undefined: no factual assertions"
    assert report["flags"]["suspected_severe_assertions"] == []


def test_incomplete_covers_only_frequency(graded):
    report = graded["incomplete"]
    coverage = report["content_coverage"]["by_dimension"]
    assert coverage["D3"]["decided_content_sum"] == 4
    assert coverage["D3"]["content_sum_including_auto_proposals"] == 5
    for dim in ("D1", "D2", "D4"):
        assert coverage[dim]["content_sum_including_auto_proposals"] == 0, dim
        support = report["evidence_support"]["by_dimension"][dim]
        assert support["not_applicable"] == support["criteria"], dim


def test_citation_checks_listed_for_every_citation(graded):
    report = graded["correct"]
    n = sum(len(f["citations"]) for f in load("correct")["findings"])
    assert len(report["citations"]) == n
    assert all(c["resolvable"] for c in report["citations"])
    assert all(c["retrieved_during_episode"] is None for c in report["citations"])
    keyed = [c for c in report["citations"] if c["overlaps_keyed_evidence_of"]]
    assert len(keyed) >= 30


def test_alternative_evidence_needs_review_not_failure():
    sub = load("correct")
    for finding in sub["findings"]:
        if (
            finding["finding_id"] == "F02"
        ):  # D1.1 / D1.2 evidence moved to other R03 lines
            finding["citations"] = [{"evidence_id": "R03", "locator": "L1-L3"}]
        if finding["finding_id"] == "F01":
            finding["citations"] = [{"evidence_id": "R03", "locator": "L4"}]
    report = grade_submission(sub, CATALOGUE, KEY)
    row = rows(report)["D1.2"]
    assert row["evidence_support"]["source"] == "pending"
    assert row["evidence_support"]["auto_proposal"] is None
    assert "needs human review" in row["evidence_support"]["basis"]


def test_r01_citation_must_cover_the_landmark():
    sub = load("correct")
    for finding in sub["findings"]:
        if finding["finding_id"] == "F21":
            finding["citations"] = [
                {
                    "evidence_id": "R01",
                    "locator": "time:2019-08-09T16:53:20+01:00/2019-08-09T16:53:48+01:00",
                }
            ]
    row = rows(grade_submission(sub, CATALOGUE, KEY))["D3.2"]
    assert row["content"]["value"] == 1
    assert row["evidence_support"] == {
        **row["evidence_support"],
        "value": 0,
        "source": "auto",
    }
    assert "do not cover 2019-08-09T16:53:49+01:00" in row["evidence_support"]["basis"]


def test_rows_locator_and_utc_times_are_accepted():
    sub = load("correct")
    for finding in sub["findings"]:
        if finding["finding_id"] == "F20":
            finding["event_time"] = "2019-08-09T15:52:59Z"
            finding["citations"] = [{"evidence_id": "R01", "locator": "rows:775-785"}]
    row = rows(grade_submission(sub, CATALOGUE, KEY))["D3.1"]
    assert row["content"]["value"] == 1 and row["evidence_support"]["value"] == 1


def test_conflicting_landmark_values_are_flagged():
    sub = load("correct")
    sub["findings"].append(
        {
            "finding_id": "F99",
            "statement": "The frequency bottomed out at 48.8 Hz at 16:53:49.",
            "status": "reported",
            "citations": [{"evidence_id": "R01", "locator": "row:830"}],
            "quantity": {"value": 48.8, "unit": "Hz", "basis": "prose"},
            "event_time": "2019-08-09T16:53:49+01:00",
        }
    )
    report = grade_submission(sub, CATALOGUE, KEY)
    assert rows(report)["D3.2"]["content"]["value"] == 1
    assert report["flags"]["conflicting_values"] == [
        {
            "criterion_id": "D3.2",
            "finding_id": "F99",
            "value": 48.8,
            "note": "another finding in the same window gives a value outside tolerance",
        }
    ]


def test_duration_half_credit_and_strictly_below_convention():
    """Tolerance bands on the structured quantity, with a statement and derivation
    that agree with it. (A statement or derivation value within tolerance beside a
    quantity outside it goes to a human: test_grading_live_runs.)"""
    for value, expected in ((34, 1.0), (36, 0.5), (37, 0.0)):
        sub = load("correct")
        for finding in sub["findings"]:
            if finding["finding_id"] == "F23":
                finding["quantity"]["value"] = value
                finding["statement"] = (
                    f"The frequency was strictly below 49 Hz for {value} s under a "
                    "zero-order hold (16:53:41 to 16:54:13 BST)."
                )
                finding["derivation"] = (
                    "run_python on the R01 CSV: samples with frequency_hz < 49, each "
                    "held until the next."
                )
        content = rows(grade_submission(sub, CATALOGUE, KEY))["D3.4"]["content"]
        assert (content["value"], content["source"]) == (expected, "auto")


def test_report_text_severe_and_invented_record_flags():
    sub = load("correct")
    sub["report"]["sections"][3]["body"] += (
        " The R04 lightning log confirms it. The operator was fined £10m."
    )
    sub["findings"][0]["statement"] += (
        " The bypass valve failure is the root cause at Little Barford."
    )
    report = grade_submission(sub, CATALOGUE, KEY)
    flags = {
        (s["flag_id"], s["location"])
        for s in report["flags"]["suspected_severe_assertions"]
    }
    assert ("SF2", "report.sections[3].body") in flags
    assert ("SF3", "report.sections[3].body") in flags
    assert ("SF1", "F01") in flags


def test_hedged_factual_statement_is_flagged_for_labelling():
    sub = load("correct")
    sub["findings"][0]["statement"] = "The fault may have been caused by lightning."
    report = grade_submission(sub, CATALOGUE, KEY)
    assert report["flags"]["labelling"][0]["finding_id"] == "F01"
