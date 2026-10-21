"""Every example of the full-investigation key, graded: the automated proposal equals
the example's ``content`` (automated criteria) or ``prescreen`` (judge criteria). The
oracle built from the first positive examples reaches 1 on every criterion with evidence
support; an empty submission reaches 0; uncited correct answers get no evidence support
(at most half credit under the handoff's contribution rule)."""

from __future__ import annotations

import copy

import pytest
from fi_grading_support import (
    criteria,
    example_submission,
    finding,
    grade,
    key,
    oracle_submission,
    row,
    submission,
)

from environment.incident.submission import word_count

EXAMPLES = [
    (c["criterion_id"], kind, i, ex)
    for c in key()["criteria"]
    for kind in ("positive", "negative")
    for i, ex in enumerate(c["examples"][kind])
    if (ex.get("prescreen") if c["assessment_mode"] == "judge" else ex.get("content"))
    is not None
]


@pytest.mark.parametrize(
    ("cid", "kind", "index", "example"),
    EXAMPLES,
    ids=[f"{c}-{k}{i}" for c, k, i, _ in EXAMPLES],
)
def test_key_example_is_graded_as_the_key_says(cid, kind, index, example):
    crit = criteria()[cid]
    want = (
        example.get("prescreen")
        if crit["assessment_mode"] == "judge"
        else example.get("content")
    )
    report = grade(example_submission(crit, example))
    r = row(report, cid)
    assert r["content"]["auto_proposal"] == want, r["content"]["basis"]
    if kind == "positive" and want == 1:
        # the finding that earns the credit is matched, so its citation is checked
        assert r["matched_finding_ids"] or crit["auto"]["elements"][0]["type"] in (
            "summary_words",
        )


def test_every_new_criterion_has_a_full_positive_and_a_lower_negative():
    for cid in key()["new_criteria"]:
        crit = criteria()[cid]
        field = "prescreen" if crit["assessment_mode"] == "judge" else "content"
        assert any(ex.get(field) == 1 for ex in crit["examples"]["positive"]), cid
        assert all(
            ex.get(field) is not None and ex[field] < 1
            for ex in crit["examples"]["negative"]
        ), cid


@pytest.fixture(scope="module")
def oracle_report():
    return grade(oracle_submission())


def test_oracle_reaches_one_on_every_criterion(oracle_report):
    sub = oracle_submission()
    assert word_count(sub["report"]["executive_summary"]) <= 600
    for r in oracle_report["criteria"]:
        assert r["content"]["auto_proposal"] == 1, (
            r["criterion_id"],
            r["content"]["basis"],
        )
        assert r["evidence_support"]["auto_proposal"] == 1, (
            r["criterion_id"],
            r["evidence_support"]["basis"],
        )
    assert oracle_report["severe_flags"] == []
    assert oracle_report["flags"]["accounting_traps"] == []
    assert oracle_report["flags"]["executive_summary"]["within_limit"] is True


def test_oracle_report_shape(oracle_report):
    assert oracle_report["grade_schema"] == "gb2019-fi-grade/1"
    assert oracle_report["task_id"] == "gb-2019-full-investigation"
    assert oracle_report["tasks"] == [f"T{i:02d}" for i in range(1, 21)]
    assert oracle_report["status"] == "provisional"
    assert oracle_report["builds_on"]["grader"] == "environment.incident.sr_grading"
    coverage = oracle_report["content_coverage"]["by_task"]
    assert set(coverage) == set(oracle_report["tasks"])
    assert coverage["T10"]["criteria"] == 10
    assert "no task total" in oracle_report["content_coverage"]["note"]


def test_empty_submission_reaches_zero():
    sub = submission([finding("F1", "Nothing was established.", "unknown")])
    report = grade(sub)
    for r in report["criteria"]:
        assert r["content"]["auto_proposal"] == 0, r["criterion_id"]


def test_uncited_correct_answers_get_no_evidence_support():
    sub = copy.deepcopy(oracle_submission())
    for f in sub["findings"]:
        f["citations"] = []
    report = grade(sub)
    for r in report["criteria"]:
        assert r["content"]["auto_proposal"] == 1, r["criterion_id"]
        if r["matched_finding_ids"]:
            ev = r["evidence_support"]
            assert ev["auto_proposal"] == 0 and ev["source"] in (
                "auto",
                "not_applicable",
            ), (
                r["criterion_id"],
                ev,
            )
    assert len(report["flags"]["uncited_findings"]) == len(sub["findings"])
