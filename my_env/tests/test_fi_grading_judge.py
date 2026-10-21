"""Judge proposals on full-investigation reports (increment A's merge semantics, mocked
judges only, no paid calls): the judge sets values only for judge criteria; suspected
severe flags and accounting traps bound its value; contradiction rules of a judge
criterion are reviewer flags, not caps; a human signs off; outputs are bound to this
key and bundle; the judge sees no report passages or reviewer notes; and the existing
judge track can judge a full-investigation submission end to end."""

from __future__ import annotations

import json
import re

import pytest
from fi_grading_support import (
    catalogue,
    criteria,
    decisions_for,
    finding,
    grade,
    judge_output,
    key,
    row,
    submission,
)

from environment.incident import fi_grading, sr_grading


def _sub() -> dict:
    return submission(
        [
            finding(
                "F1",
                "Contributing factor: loss-of-mains protection on embedded generation tripped about 500 MW, and the DNOs had no real-time visibility of distributed generation.",
                "reported",
                [("S06", "L32-L35")],
            ),
            finding(
                "F2",
                "ORR reports 29 Class 700/717 trains locked out.",
                "reported",
                [("S08", "L120-L127")],
            ),
            finding(
                "F3",
                "Thameslink's Class 700 trains stopped when their traction supply was lost in the power cut.",
                "inferred",
                [("S08", "L86-L89")],
            ),
            finding(
                "F4",
                "In January 2020 RWE and Ørsted paid £4.5m each to the redress scheme.",
                "reported",
                [("S10", "L98-L105")],
            ),
        ],
        "Findings [F1] [F2] [F3] [F4].",
    )


@pytest.fixture(scope="module")
def report():
    return grade(_sub())


def test_judge_sets_values_only_for_judge_criteria(report):
    judged = fi_grading.merge_judge_proposals(
        report,
        judge_output(
            report,
            criteria={
                "T13.01": {
                    "content": 1,
                    "evidence_support": 1,
                    "finding_ids": ["F1"],
                    "rationale": "F1",
                },
                "T10.02a": {"content": 0, "rationale": "the judge disagrees"},
            },
        ),
    )
    t1301 = row(judged, "T13.01")
    assert t1301["content"]["value"] == 1 and t1301["content"]["source"] == "judge"
    t1002a = row(judged, "T10.02a")
    assert t1002a["content"]["source"] == "pending"
    assert t1002a["content"]["auto_proposal"] == 1
    assert t1002a["judge_note"]["ignored"] is True
    assert judged["judge"]["criteria_applied"] == ["T13.01"]
    assert judged["grade_schema"] == fi_grading.GRADE_SCHEMA
    assert judged["status"] == "provisional"
    assert any("judge proposals" in r for r in judged["provisional_reasons"])


def test_suspected_sf3_caps_the_judges_value(report):
    assert any(s["flag_id"] == "SF3" for s in report["severe_flags"])
    judged = fi_grading.merge_judge_proposals(
        report,
        judge_output(
            report, criteria={"T14.05": {"content": 1, "finding_ids": ["F4"]}}
        ),
    )
    r = row(judged, "T14.05")
    assert r["content"]["judge_proposal"] == 1
    assert r["content"]["value"] == 0 and r["content"]["source"] == "judge"
    assert "capped" in r["content"]["basis"]
    # accept_judge cannot sign off a capped proposal
    decisions = decisions_for(
        report, key(), criteria={"T14.05": {"accept_judge": True}}
    )
    signed = fi_grading.grade_submission(
        _sub(),
        catalogue(),
        key(),
        decisions=decisions,
        judge_output=judge_output(
            report, criteria={"T14.05": {"content": 1, "finding_ids": ["F4"]}}
        ),
    )
    r = row(signed, "T14.05")
    assert r["content"]["source"] == "pending" and r["content"].get(
        "accept_judge_refused"
    )


def test_contradiction_of_a_judge_criterion_does_not_cap_the_judge(report):
    caps = row(report, "T10.01")["layers"]["caps"]
    assert any(c["kind"] == "contradiction" and c["binding"] is False for c in caps)
    judged = fi_grading.merge_judge_proposals(
        report,
        judge_output(
            report, criteria={"T10.01": {"content": 0.5, "finding_ids": ["F3"]}}
        ),
    )
    r = row(judged, "T10.01")
    assert r["content"]["value"] == 0.5 and r["content"]["source"] == "judge"
    assert "pre-screen flag" in r["content"]["basis"]
    assert any(
        f["criterion_id"] == "T10.01"
        for f in judged["flags"]["prescreen_contradictions"]
    )


def test_judge_evidence_on_spans_never_obtained_is_decided_zero():
    sub = _sub()
    trace = {
        "retrieved": ["S08"],
        "records": {},
        "document_routes": {"S08": ["request_document"]},
    }
    rep = fi_grading.grade_submission(sub, catalogue(), key(), trace)
    judged = fi_grading.merge_judge_proposals(
        rep,
        judge_output(
            rep,
            criteria={
                "T13.01": {
                    "content": 1,
                    "evidence_support": 1,
                    "finding_ids": ["F1"],
                    "supporting_spans": [
                        {
                            "evidence_id": "S06",
                            "locator": "L32-L35",
                            "quote": "half-hourly",
                        }
                    ],
                }
            },
        ),
    )
    ev = row(judged, "T13.01")["evidence_support"]
    assert ev["value"] == 0 and ev["source"] == "auto"


def test_human_sign_off_of_a_judge_value(report):
    out = judge_output(
        report,
        criteria={
            "T13.01": {"content": 1, "evidence_support": 1, "finding_ids": ["F1"]}
        },
    )
    decisions = decisions_for(
        report, key(), criteria={"T13.01": {"accept_judge": True}}
    )
    signed = fi_grading.grade_submission(
        _sub(), catalogue(), key(), decisions=decisions, judge_output=out
    )
    r = row(signed, "T13.01")
    assert r["content"]["value"] == 1 and r["content"]["source"] == "human"
    assert r["content"]["signed_off_judge"] is True


def test_judge_output_is_bound_to_this_key_and_bundle(report):
    out = judge_output(report)
    out["binding"]["key_sha256"] = sr_grading.key_sha256(sr_grading.load_key())
    with pytest.raises(fi_grading.JudgeOutputError, match="key_sha256"):
        fi_grading.merge_judge_proposals(report, out)
    out = judge_output(report)
    out["judge_schema"] = "gb2019-fi-judge-output/1"
    with pytest.raises(fi_grading.JudgeOutputError, match="judge_schema"):
        fi_grading.merge_judge_proposals(report, out)


def test_criterion_rubric_shows_no_report_passages_or_reviewer_notes():
    for cid in key()["new_criteria"]:
        rubric = fi_grading.criterion_rubric(cid)
        text = json.dumps(rubric, ensure_ascii=False)
        assert "report_passages" not in rubric and "pdf_page" not in text
        assert "prescreen" not in text and "reviewer_note" not in text
        assert rubric["keyed_spans"] and all(
            not s["text"].startswith("(unresolvable") for s in rubric["keyed_spans"]
        )
        assert rubric["expectation"] == criteria()[cid]["expectation"]


def test_cited_spans_resolve_the_new_records():
    sub = submission(
        [
            finding(
                "F1",
                "x",
                "reported",
                [
                    ("R09", "entry:R09-A1-2"),
                    ("S09", "response:S09-GTR-05"),
                    ("R11", "entry:R11-NR-224917"),
                    ("R09", "event:R09-REMIT-00056773-r1"),
                ],
            )
        ]
    )
    spans = fi_grading.cited_spans(sub)["F1"]
    assert [("error" in s) for s in spans] == [False] * 4
    assert "17:51hrs" in spans[0]["text"]
    assert "3.27" in spans[1]["text"]
    assert "ROCK FERRY" in spans[2]["text"]


def test_the_judge_track_can_judge_a_full_investigation_submission():
    """End to end with a mocked chat client: the judge package builds its requests from
    the full-investigation key, bundle and report, and the output merges here."""
    from sr_judge_support import RUN_MODEL, FakeJudge
    from sr_judge_support import config as judge_config

    from environment.incident.judge import judge_submission

    sub = _sub()
    rep = grade(sub)
    fake = FakeJudge()
    result = judge_submission(
        sub,
        rep,
        key=key(),
        catalogue=catalogue(),
        config=judge_config(),
        run_model=RUN_MODEL,
        client=fake,
    )
    units = {c.unit_id for c in fake.calls}
    assert {"T10", "T13", "T14"} <= units
    out = result.judge_output
    assert out["binding"]["key_sha256"] == fi_grading.key_sha256(key())
    merged = fi_grading.merge_judge_proposals(rep, out)
    assert merged["judge"]["criteria_applied"]
    assert set(merged["judge"]["criteria_applied"]) <= set(key()["judge"]["criteria"])
    assert row(merged, "T14.05")["content"]["value"] == 0  # SF3 still caps


def test_judge_visible_text_names_no_runs_builders_or_prescreens():
    """As for increment A (decision 34): what the judge sees of a criterion (rubric
    without keyed spans) names no live runs, increments, builders or pre-screens."""
    pattern = re.compile(
        r"live run|increment [ab]\b|pre-?screen|\bmvp\b|sr30k|sr80k|opus|sonnet|haiku"
        r"|builder|reviewer",
        re.I,
    )
    for cid in key()["new_criteria"] + ["T04.03", "T05.03"]:
        rubric = fi_grading.criterion_rubric(cid)
        text = json.dumps(
            {k: v for k, v in rubric.items() if k != "keyed_spans"}, ensure_ascii=False
        )
        assert not pattern.search(text), (cid, pattern.search(text).group(0))


def test_the_full_investigation_key_needs_its_element_types():
    """Increment A's grader alone cannot grade this key: the added element types come
    from fi_grading (environment.incident.fi_elements)."""
    sub = _sub()
    with pytest.raises(fi_grading.GradingError, match="unknown element type"):
        sr_grading.grade_submission(sub, catalogue(), key())
    report = sr_grading.grade_submission(
        sub, catalogue(), key(), element_types=fi_grading.ELEMENT_TYPES
    )
    assert report["grade_schema"] == sr_grading.GRADE_SCHEMA  # fi_grading marks its own
