"""Merging LLM-judge proposals (mocked: no model is called) and human decisions into a
grade report: which criteria the judge may decide, automated caps, evidence
constraints, assertion verdicts, human precedence and sign-off, and the report status."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from sr_grading_support import (
    catalogue,
    decisions_for,
    finding,
    grade,
    judge_output,
    key,
    row,
    submission,
)

from environment.incident import sr_grading
from environment.incident.grading import DecisionsError


def base_submission() -> dict:
    return submission(
        [
            finding(
                "F1",
                "The offshore turbine controllers at Hornsea One reacted incorrectly to the voltage fluctuations (an insufficiently damped sub-synchronous resonance in the control system), and turbine overcurrent protection then de-loaded Hornsea 1B and 1C.",
                "reported",
                [("S01", "L56-L58"), ("S01", "L62-L64")],
            ),
            finding(
                "F2",
                "ESO's total generation lost was at least 1,990 MW.",
                "reported",
                [("S12", "L39-L42")],
            ),
            finding("F3", "Hornsea's internal network was weak.", "inferred"),
            finding(
                "F4",
                "The minimum 1-s sample was 48.787 Hz at 16:53:49 BST.",
                "observed",
                [("R01", "row:830")],
            ),
        ]
    )


@pytest.fixture(scope="module")
def report() -> dict:
    return grade(base_submission())


def test_judge_criteria_wait_for_the_judge(report):
    for r in report["criteria"]:
        if r["assessment_mode"] == "judge":
            assert r["content"]["source"] in ("pending", "severe_flag")
            assert r["content"]["judge_proposal"] is None
    assert row(report, "T06.01")["content"]["basis"].startswith("awaiting the judge")
    assert report["judge"] is None


def test_merge_applies_judge_values_to_judge_criteria_only(report):
    jo = judge_output(
        report,
        criteria={
            "T06.01": {
                "content": 1,
                "evidence_support": 1,
                "finding_ids": ["F1"],
                "rationale": "controller reaction and de-load",
            },
            "T06.03": {
                "content": 0.5,
                "finding_ids": ["F1"],
                "rationale": "resonance attributed only",
            },
            "T03.02": {"content": 0, "rationale": "should be ignored"},
            "T02.05a": {"content": 1, "rationale": "should be ignored"},
        },
    )
    merged = sr_grading.merge_judge_proposals(report, jo)
    t0601 = row(merged, "T06.01")
    assert t0601["content"]["source"] == "judge" and t0601["content"]["value"] == 1
    assert (
        t0601["evidence_support"]["source"] == "judge"
        and t0601["evidence_support"]["value"] == 1
    )
    assert t0601["evidence_support"]["auto_proposal"] == 1  # F1 cites keyed spans
    assert t0601["judge_finding_ids"] == ["F1"]
    t0603 = row(merged, "T06.03")
    assert t0603["content"] == {**t0603["content"], "value": 0.5, "source": "judge"}
    assert t0603["evidence_support"]["source"] == "pending"  # no judge evidence value
    # numeric criteria are never decided by the judge
    assert row(merged, "T03.02")["content"]["source"] == "auto"
    assert row(merged, "T03.02")["content"]["value"] == 1.0
    assert row(merged, "T02.05a")["content"]["source"] == "pending"
    ignored = {i["criterion_id"] for i in merged["judge"]["criteria_ignored"]}
    assert ignored == {"T03.02", "T02.05a"}
    assert merged["judge"]["criteria_applied"] == ["T06.01", "T06.03"]
    assert merged["status"] == "provisional"
    assert any(
        "judge proposals awaiting human sign-off" in r
        for r in merged["provisional_reasons"]
    )
    coverage = merged["content_coverage"]["by_task"]["T06"]
    assert coverage["by_source"]["judge"] == 2
    assert coverage["judge_proposed_content_sum"] == 1.5
    assert coverage["decided_content_sum"] == 0
    # the input report is untouched
    assert row(report, "T06.01")["content"]["source"] == "pending"


def test_automated_caps_bound_the_judge(report):
    """F2 substitutes Ofgem's stage total for ESO's: the T02.06 accounting cap holds
    whatever the judge proposes."""
    t0206 = row(report, "T02.06")
    assert any(c["id"] == "ofgem_1990_on_wrong_basis" for c in t0206["layers"]["caps"])
    merged = sr_grading.merge_judge_proposals(
        report,
        judge_output(
            report,
            criteria={
                "T02.06": {
                    "content": 1,
                    "finding_ids": ["F2"],
                    "rationale": "looks fine",
                }
            },
        ),
    )
    t = row(merged, "T02.06")
    assert t["content"]["value"] == 0 and t["content"]["source"] == "judge"
    assert t["content"]["judge_proposal"] == 1
    assert "capped to 0" in t["content"]["basis"]
    assert t["evidence_support"]["source"] == "not_applicable"


def test_judge_evidence_on_uncited_findings_is_decided_zero(report):
    merged = sr_grading.merge_judge_proposals(
        report,
        judge_output(
            report,
            criteria={
                "T16.03": {
                    "content": 0.5,
                    "evidence_support": 1,
                    "finding_ids": ["F3"],
                    "rationale": "weak network noted",
                }
            },
        ),
    )
    ev = row(merged, "T16.03")["evidence_support"]
    assert ev["source"] == "auto" and ev["value"] == 0
    assert "cite no evidence" in ev["basis"]


def test_judge_assertions_and_severe_suggestions(report):
    merged = sr_grading.merge_judge_proposals(
        report,
        judge_output(
            report,
            assertions={
                "F1": {
                    "verdict": "supported",
                    "task": "T06",
                    "rationale": "S01 annotations",
                },
                "F2": {"verdict": "contradicted", "rationale": "Ofgem's figure"},
                "J-1": {
                    "verdict": "unsupported",
                    "text": "The report says DG telemetry exists.",
                    "task": "T08",
                },
            },
            severe_flags=[
                {
                    "flag_id": "SF1",
                    "finding_ids": [],
                    "locations": ["report.executive_summary"],
                    "rationale": "check",
                }
            ],
        ),
    )
    by = {a["assertion_id"]: a for a in merged["assertion_quality"]["assertions"]}
    assert by["F1"]["source"] == "judge" and by["F1"]["verdict"] == "supported"
    assert (
        by["F2"]["verdict"] == "contradicted"
        and by["F2"]["auto_proposal"] == "contradicted"
    )
    assert by["F3"]["source"] == "pending"
    assert by["J-1"]["kind"] == "report_text" and by["J-1"]["dimension"] == "T08"
    tally = merged["assertion_quality"]["by_task"]["T06"]
    assert tally["by_source"]["judge"] == 1 and tally["precision_human_only"] is None
    assert "judge proposal" in tally["precision_note"]
    assert merged["judge"]["severe_flag_suggestions"][0]["flag_id"] == "SF1"
    assert all(s["detected_by"] == "heuristic" for s in merged["severe_flags"])


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda jo: jo["binding"].update(submission_sha256="0" * 64),
            "submission_sha256",
        ),
        (lambda jo: jo["binding"].update(key_sha256="x"), "key_sha256"),
        (lambda jo: jo["binding"].update(bundle_sha256="y"), "bundle_sha256"),
        (lambda jo: jo.update(judge_schema="other"), "judge_schema"),
        (lambda jo: jo.update(judge_model=""), "judge_model"),
        (
            lambda jo: jo["criteria"].update({"T99.01": {"content": 1}}),
            "unknown criterion",
        ),
        (
            lambda jo: jo["criteria"].update({"T06.01": {"content": 0.7}}),
            "content must be",
        ),
        (
            lambda jo: jo["criteria"].update(
                {"T06.01": {"content": 1, "finding_ids": ["F9"]}}
            ),
            "unknown finding",
        ),
        (
            lambda jo: jo["assertions"].update({"F1": {"verdict": "maybe"}}),
            "verdict must be",
        ),
        (
            lambda jo: jo["assertions"].update({"J-2": {"verdict": "supported"}}),
            "needs 'text'",
        ),
        (lambda jo: jo["severe_flags"].append({"flag_id": "SF9"}), "unknown flag_id"),
    ],
)
def test_malformed_or_misbound_judge_output_is_rejected(report, change, message):
    jo = judge_output(report)
    change(jo)
    with pytest.raises(sr_grading.JudgeOutputError, match=message):
        sr_grading.merge_judge_proposals(report, jo)


def test_human_decisions_take_precedence_and_sign_off_the_judge():
    sub = base_submission()
    first = grade(sub)
    jo = judge_output(
        first,
        criteria={
            "T06.01": {
                "content": 1,
                "evidence_support": 1,
                "finding_ids": ["F1"],
                "rationale": "ok",
            },
            "T06.02": {
                "content": 0.5,
                "finding_ids": ["F1"],
                "rationale": "offshore only",
            },
        },
        assertions={"F1": {"verdict": "supported"}, "F3": {"verdict": "unsupported"}},
    )
    decisions = decisions_for(
        first,
        key(),
        criteria={
            "T06.01": {"accept_judge": True, "notes": "agree"},
            "T06.02": {
                "content": 1,
                "evidence_support": 1,
                "finding_ids": ["F1"],
                "notes": "onshore implied",
            },
        },
        assertions={"F1": {"accept_judge": True}, "F3": {"verdict": "supported"}},
    )
    report = grade(sub, decisions=decisions, judge_output=jo)
    t0601 = row(report, "T06.01")
    assert t0601["content"] == {
        **t0601["content"],
        "value": 1,
        "source": "human",
        "signed_off_judge": True,
    }
    assert t0601["evidence_support"]["source"] == "human"
    t0602 = row(report, "T06.02")
    assert t0602["content"]["source"] == "human" and t0602["content"]["value"] == 1
    assert t0602["content"]["judge_proposal"] == 0.5
    by = {a["assertion_id"]: a for a in report["assertion_quality"]["assertions"]}
    assert by["F1"]["source"] == "human" and by["F1"]["signed_off_judge"]
    assert by["F3"]["source"] == "human" and by["F3"]["verdict"] == "supported"


def test_decisions_are_validated():
    first = grade(base_submission())
    bad = decisions_for(first, key(), criteria={"T06.01": {"accept_judge": "yes"}})
    with pytest.raises(DecisionsError, match="accept_judge"):
        grade(base_submission(), decisions=bad)
    wrong_schema = decisions_for(first, key())
    wrong_schema["decisions_schema"] = "gb2019-grading-decisions/1"
    with pytest.raises(DecisionsError, match="decisions_schema"):
        grade(base_submission(), decisions=wrong_schema)
    wrong_task = decisions_for(
        first, key(), explanation_quality={"by_dimension": {"D1": "x"}}
    )
    with pytest.raises(DecisionsError, match="unknown dimension"):
        grade(base_submission(), decisions=wrong_task)


def test_confirmed_severe_flag_zeroes_and_overrides_the_judge():
    sub = submission(
        [
            finding(
                "F1",
                "The root cause of the GT1A trip was a failed bypass valve.",
                "observed",
                [("S04", "L50-L52")],
            )
        ]
    )
    first = grade(sub)
    flagged = [s for s in first["severe_flags"] if s["flag_id"] == "SF1"]
    assert flagged and flagged[0]["finding_id"] == "F1"
    decisions = decisions_for(
        first,
        key(),
        criteria={"T07.04": {"accept_judge": True}},
        severe_flags=[
            {
                "flag_id": "SF1",
                "finding_ids": ["F1"],
                "confirmed": True,
                "notes": "asserted root cause",
            }
        ],
    )
    jo = judge_output(first, criteria={"T07.04": {"content": 1, "rationale": "wrong"}})
    report = grade(sub, decisions=decisions, judge_output=jo)
    for cid in ("T07.04", "T07.05", "T17.01"):
        r = row(report, cid)
        assert r["content"]["source"] == "severe_flag" and r["content"]["value"] == 0, (
            cid
        )
    assertion = report["assertion_quality"]["assertions"][0]
    assert (
        assertion["source"] == "severe_flag" and assertion["verdict"] == "unsupported"
    )


def test_rejected_severe_flag_lifts_the_judge_cap():
    sub = submission(
        [
            finding(
                "F1",
                "GT1A tripped because a steam bypass valve failed to operate correctly.",
                "reported",
                [("S12", "L148-L152")],
            )
        ]
    )
    first = grade(sub)
    assert [s["flag_id"] for s in first["severe_flags"]] == ["SF1"]
    jo = judge_output(
        first, criteria={"T07.05": {"content": 1, "rationale": "attributed view"}}
    )
    capped = sr_grading.merge_judge_proposals(first, jo)
    assert (
        row(capped, "T07.05")["content"]["value"] == 0
    )  # suspected SF1, not yet adjudicated
    decisions = decisions_for(
        first,
        key(),
        severe_flags=[
            {
                "flag_id": "SF1",
                "finding_ids": ["F1"],
                "confirmed": False,
                "notes": "ESO wording",
            }
        ],
    )
    lifted = grade(sub, decisions=decisions, judge_output=jo)
    assert row(lifted, "T07.05")["content"] == {
        **row(lifted, "T07.05")["content"],
        "value": 1,
        "source": "judge",
    }
    assert lifted["severe_flags"][0]["confirmed"] is False


def _reviewed_key() -> dict:
    reviewed = copy.deepcopy(key())
    reviewed["review"]["status"] = "reviewed"
    reviewed["review_status"] = "reviewed"
    return reviewed


def test_status_is_final_only_with_every_sign_off_and_a_reviewed_key():
    reviewed = _reviewed_key()
    sub = submission(
        [
            finding(
                "F1",
                "The minimum 1-s sample was 48.787 Hz at 16:53:49 BST.",
                "observed",
                [("R01", "row:830")],
            )
        ]
    )
    trace = {
        "retrieved": ["R01"],
        "document_routes": {"R01": ["request_document"]},
        "records": {},
        "records_by_kind": {"event": 0, "entry": 0, "response": 0},
        "frequency_rows_seen": [],
        "python_calls": [],
        "r01_analysed_with_python": True,
        "calls_used": 3,
        "frozen_at_request_id": "req-003",
    }
    first = sr_grading.grade_submission(sub, catalogue(), reviewed, trace)
    pending = [
        r["criterion_id"]
        for r in first["criteria"]
        if "pending" in (r["content"]["source"], r["evidence_support"]["source"])
    ]
    jo = judge_output(first, criteria={"T06.01": {"content": 0, "rationale": "absent"}})
    decisions = decisions_for(
        first,
        reviewed,
        criteria={
            cid: ({"accept_judge": True} if cid == "T06.01" else {"content": 0})
            for cid in pending
        },
        assertions={"F1": {"verdict": "supported"}},
    )
    final = sr_grading.grade_submission(
        sub, catalogue(), reviewed, trace, decisions, jo
    )
    assert final["status"] == "final", final["provisional_reasons"]
    assert final["provisional_reasons"] == []
    assert row(final, "T03.02")["content"]["source"] == "auto"
    # the same decisions on the pending-review key cannot be applied (bound to another key)
    with pytest.raises(DecisionsError, match="key"):
        grade(sub, decisions=decisions)
    # a builder fixture never makes a report final
    fixture = {**decisions, "builder_fixture": True}
    provisional = sr_grading.grade_submission(
        sub, catalogue(), reviewed, trace, fixture, jo
    )
    assert provisional["status"] == "provisional"
    assert any("builder fixture" in r for r in provisional["provisional_reasons"])
    # without the judge's sign-off target, T06.01 stays pending
    no_judge = sr_grading.grade_submission(sub, catalogue(), reviewed, trace, decisions)
    assert row(no_judge, "T06.01")["content"]["source"] == "pending"
    assert no_judge["status"] == "provisional"


def test_review_template_carries_judge_proposals(tmp_path: Path, report):
    jo = judge_output(
        report,
        criteria={"T06.01": {"content": 1, "finding_ids": ["F1"], "rationale": "ok"}},
    )
    path = tmp_path / "judge.json"
    path.write_text(json.dumps(jo))
    template = sr_grading.review_template(report, judge_output=path)
    entry = template["criteria"]["T06.01"]
    assert entry["_context"]["judge"]["content"] == 1
    assert entry["finding_ids"] == ["F1"] and entry["accept_judge"] is False
    assert template["_context"]["judge"]["judge_model"] == "test/mock-judge"
    assert "T02.06" in template["criteria"]
    assert template["_context"]["accounting_traps"]


def test_judge_inputs_are_rubric_and_resolved_spans_only():
    rubric = sr_grading.criterion_rubric("T09.02b", key=key(), catalogue=catalogue())
    assert rubric["assessment_mode"] == "auto_assisted_human"
    assert rubric["keyed_spans"][0]["text"].count("892") >= 1
    assert "report_passages" not in rubric and "auto" not in rubric
    judged = sr_grading.criterion_rubric("T06.02", key=key(), catalogue=catalogue())
    assert judged["assessment_mode"] == "judge" and judged["examples"]["positive"]
    spans = sr_grading.cited_spans(base_submission(), catalogue())
    assert set(spans) == {"F1", "F2", "F3", "F4"}
    assert "unexpected wind farm control system response" in spans["F1"][0]["text"]
    assert spans["F3"] == []
    assert spans["F4"][0]["text"].startswith("2019-08-09T16:53:49+01:00,48.787")


def test_merge_works_on_a_report_read_back_from_json(report):
    stored = json.loads(json.dumps(report, default=str))
    jo = judge_output(
        report,
        criteria={"T06.01": {"content": 1, "finding_ids": ["F1"], "rationale": "ok"}},
    )
    a = sr_grading.merge_judge_proposals(report, jo)
    b = sr_grading.merge_judge_proposals(stored, jo)
    assert row(a, "T06.01")["content"] == row(b, "T06.01")["content"]
    assert (
        a["status"] == b["status"]
        and a["provisional_reasons"] == b["provisional_reasons"]
    )


def test_judge_evidence_follows_the_spans_it_quotes():
    """An evidence value of 1 whose quotes come only from cited spans never obtained
    is decided 0; one whose quotes lie in no span the credited findings cite is
    withheld for a human; quotes inside an obtained cited span keep the proposal."""
    sub = submission(
        [
            finding(
                "F1",
                "Ofgem's lower bound for distributed generation lost is 1,300 MW, and "
                "it could be as high as 1,500 MW (estimates).",
                "reported",
                [("S06", "L102-L103"), ("S12", "L131-L134")],
            )
        ]
    )
    trace = {
        "retrieved": ["S12"],
        "document_routes": {"S12": ["request_document"]},
        "records": {},
        "records_by_kind": {"event": 0, "entry": 0, "response": 0},
        "frequency_rows_seen": [],
        "python_calls": [],
        "r01_analysed_with_python": False,
    }
    first = sr_grading.grade_submission(sub, catalogue(), key(), trace)

    def merged(spans):
        jo = judge_output(
            first,
            criteria={
                "T17.02": {
                    "content": 1,
                    "evidence_support": 1,
                    "finding_ids": ["F1"],
                    "supporting_spans": spans,
                    "rationale": "x",
                }
            },
        )
        return row(sr_grading.merge_judge_proposals(first, jo), "T17.02")[
            "evidence_support"
        ]

    never = merged([{"evidence_id": "S06", "locator": "L102", "quote": "1,300 MW"}])
    assert never["value"] == 0 and never["source"] == "auto"
    elsewhere = merged([{"evidence_id": "S06", "locator": "L20-L21", "quote": "462"}])
    assert elsewhere["value"] is None and elsewhere["source"] == "pending"
    obtained = merged(
        [
            {"evidence_id": "S06", "locator": "L102", "quote": "1,300 MW"},
            {"evidence_id": "S12", "locator": "L132", "quote": "estimate"},
        ]
    )
    assert obtained["value"] == 1 and obtained["source"] == "judge"
