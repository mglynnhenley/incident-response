"""Grading full-investigation episodes on the real bundle: the new retrieval routes
(rail and compliance documents, data returns, the ESO-COMMS and Network Rail control
logs, REMIT asset-log rows, the new witnesses), incomplete runs, the bundle binding,
this task's decisions schema, the review template, the command line and the task's
judge hook (completion-only score; the grade is stored)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fi_grading_support import (
    catalogue,
    decisions_for,
    episode_config,
    finding,
    key,
    oracle_submission,
    row,
    run_calls,
    submission,
)
from incident_helpers import transcript_for

from environment.incident import fi_grading, sr_grading
from environment.incident.catalogue import Catalogue
from environment.incident.episode import GRADE_FILE, read_state
from environment.incident.grading import DecisionsError, GradingError
from environment.incident.paths import SYSTEM_RESPONSE_BUNDLE_DIR
from environment.tasks.gb_2019_full_investigation import FullInvestigationToolConfig
from environment.tasks.gb_2019_full_investigation.judge import FullInvestigationJudge

ROUTES = [
    ("request_document", {"doc_id": "S08"}),
    (
        "request_data_return",
        {"party": "ESO", "data_type": "generator_compliance_process_records"},
    ),
    (
        "query_control_log",
        {
            "room": "ESO-COMMS",
            "start": "2019-08-09T16:00:00Z",
            "end": "2019-08-09T17:30:00Z",
        },
    ),
    (
        "query_control_log",
        {
            "room": "NETWORK-RAIL-CONTROL",
            "start": "2019-08-09T15:50:00Z",
            "end": "2019-08-09T16:10:00Z",
        },
    ),
    (
        "query_asset_log",
        {
            "asset_id": "LITTLE-BARFORD",
            "start": "2019-08-09T16:50:00Z",
            "end": "2019-08-09T17:00:00Z",
        },
    ),
    (
        "interview_witness",
        {
            "persona_id": "gtr-fleet-engineer",
            "question": "Which TCMS software versions were the units on?",
        },
    ),
]


def route_submission() -> dict:
    return submission(
        [
            finding(
                "F1",
                "ORR reports 29 Class 700/717 trains locked out: 22 needed a technician and 7 were restored by driver reset.",
                "reported",
                [("S08", "L120-L127")],
            ),
            finding(
                "F2",
                "Units on 3.25 were recovered by driver Battery Reset; units on 3.27 needed a technician (GTR).",
                "reported",
                [("S09", "response:S09-GTR-05")],
            ),
            finding(
                "F3",
                "The ESO's records disagree on its first contact with Ofgem: 17:51 (section 6.2) and 18:00 (section 7).",
                "reported",
                [("R09", "entry:R09-A1-2"), ("R09", "entry:R09-A2-2")],
            ),
            finding(
                "F4",
                "Ofgem found that the ESO relied on self-certification for Hornsea's compliance; its compliance checks do not appear sufficiently robust.",
                "reported",
                [("S10", "L98-L105")],
            ),
            finding(
                "F5",
                "Network Rail recorded GTR Class 700 unit faults at Finsbury Park.",
                "reported",
                [("R11", "entry:R11-NR-224904")],
            ),
            finding(
                "F6",
                "Little Barford's REMIT message was published at 16:54:44 UTC.",
                "reported",
                [("R09", "event:R09-REMIT-00056773-r1")],
            ),
            finding(
                "F7",
                "Newcastle Airport was disconnected by Northern Powergrid's LFDD.",
                "reported",
                [("S11", "L78-L81")],
            ),
            finding(
                "F8",
                "Network Rail attributed a power failure at Acton Wells to National Grid.",
                "reported",
                [("R11", "entry:R11-NR-225486")],
            ),
        ],
        "Findings [F1] [F2] [F3] [F4] [F5] [F6] [F7] [F8].",
        summary="Rail and communications findings [F1, F3].",
    )


@pytest.fixture
def routed(tmp_path: Path):
    config = episode_config(tmp_path)
    calls = ROUTES + [("submit_findings", {"submission": route_submission()})]
    results = run_calls(config, calls)
    assert all(r.envelope["ok"] for _, _, r in results), [
        (t, r.envelope["error"]) for t, _, r in results if not r.envelope["ok"]
    ]
    return config, results


def test_trace_info_records_the_new_routes(routed):
    config, _ = routed
    info = fi_grading.trace_info_from_episode(config.episode_dir)
    assert info["document_routes"] == {
        "S08": ["request_document"],
        "S10": ["request_data_return"],
    }
    assert info["records"]["entry:R09-A1-2"]["tool"] == "query_control_log"
    assert info["records"]["entry:R11-NR-224861"]["evidence_id"] == "R11"
    assert info["records"]["event:R09-REMIT-00056773-r1"]["tool"] == "query_asset_log"
    assert info["records"]["response:S09-GTR-05"]["tool"] == "interview_witness"


def test_citations_are_checked_against_the_new_routes(routed):
    config, _ = routed
    report = fi_grading.grade_episode(config.episode_dir)
    by = {(c["finding_id"], c["locator"]): c for c in report["citations"]}
    assert by[("F1", "L120-L127")]["retrieval_routes"] == ["request_document"]
    assert by[("F2", "response:S09-GTR-05")]["retrieval_routes"] == [
        "interview_witness"
    ]
    assert by[("F3", "entry:R09-A1-2")]["retrieval_routes"] == ["query_control_log"]
    assert by[("F4", "L98-L105")]["retrieval_routes"] == ["request_data_return"]
    assert by[("F6", "event:R09-REMIT-00056773-r1")]["retrieval_routes"] == [
        "query_asset_log"
    ]
    # R11-NR-224904 (17:02 local, 16:02Z) was in the window queried; R11-NR-225486
    # (21:25 local) was not
    assert by[("F5", "entry:R11-NR-224904")]["retrieval_routes"] == [
        "query_control_log"
    ]
    assert by[("F8", "entry:R11-NR-225486")]["retrieved_during_episode"] is False
    # S11 was never obtained
    assert by[("F7", "L78-L81")]["retrieved_during_episode"] is False
    assert report["flags"]["cited_but_never_retrieved_findings"] == ["F7", "F8"]
    assert "T15.02" in by[("F3", "entry:R09-A1-2")]["targets_keyed_evidence_of"]


def test_grade_episode_report_structure(routed):
    config, _ = routed
    report = fi_grading.grade_episode(config.episode_dir)
    assert report["grade_schema"] == fi_grading.GRADE_SCHEMA
    assert report["grader_version"] == fi_grading.GRADER_VERSION
    assert report["task_id"] == "gb-2019-full-investigation"
    assert report["run"]["outcome"] == "complete"
    assert report["bundle"]["matches_key"] and report["bundle"]["matches_episode"]
    assert report["tasks"] == [d["dimension_id"] for d in key()["dimensions"]]
    assert report["status"] == "provisional"
    assert any("pending_domain_review" in r for r in report["provisional_reasons"])
    assert report["flags"]["executive_summary"]["within_limit"] is True
    for cid in ("T10.02a", "T10.02b", "T10.02c", "T10.04", "T15.02"):
        r = row(report, cid)
        assert r["content"]["auto_proposal"] == 1, (cid, r["content"]["basis"])
        assert r["content"]["source"] == "pending"
        assert r["evidence_support"]["auto_proposal"] == 1, cid
    # the cited S11 span was never obtained: no evidence support
    t1101a = row(report, "T11.01a")
    assert t1101a["content"]["auto_proposal"] == 1
    assert t1101a["evidence_support"]["auto_proposal"] == 0
    # judge criteria wait for the judge
    assert row(report, "T13.02")["content"]["source"] == "pending"
    assert "awaiting the judge" in row(report, "T13.02")["content"]["basis"]


def test_incomplete_run_has_no_content_measures(tmp_path: Path):
    config = episode_config(tmp_path)
    run_calls(config, [("request_document", {"doc_id": "S08"})])
    report = fi_grading.grade_episode(config.episode_dir)
    assert report["run"]["outcome"] != "complete"
    assert report["grade_schema"] == fi_grading.GRADE_SCHEMA
    assert report["criteria"] == [] and report["content_coverage"] is None
    assert report["status"] == "provisional"
    template = fi_grading.review_template(config.episode_dir)
    assert template["criteria"] == {} and template["binding"] is None
    assert template["decisions_schema"] == fi_grading.DECISIONS_SCHEMA


def test_episode_must_be_graded_on_its_own_bundle(routed):
    config, _ = routed
    with pytest.raises(GradingError, match="bundle"):
        fi_grading.grade_episode(
            config.episode_dir, catalogue=Catalogue.load(SYSTEM_RESPONSE_BUNDLE_DIR)
        )


def test_decisions_use_this_tasks_schema(routed):
    config, _ = routed
    report = fi_grading.grade_episode(config.episode_dir)
    decisions = decisions_for(
        report,
        key(),
        criteria={
            "T10.02a": {"content": 1, "evidence_support": 1, "finding_ids": ["F1"]}
        },
    )
    decided = fi_grading.grade_episode(config.episode_dir, decisions=decisions)
    r = row(decided, "T10.02a")
    assert r["content"]["value"] == 1 and r["content"]["source"] == "human"
    wrong = {**decisions, "decisions_schema": sr_grading.DECISIONS_SCHEMA}
    with pytest.raises(DecisionsError, match="gb2019-fi-grading-decisions/1"):
        fi_grading.grade_episode(config.episode_dir, decisions=wrong)
    # decisions bound to increment A's key do not apply here
    other = decisions_for(report, sr_grading.load_key())
    with pytest.raises(DecisionsError):
        fi_grading.grade_episode(config.episode_dir, decisions=other)


def test_review_template_from_an_episode(routed):
    config, _ = routed
    template = fi_grading.review_template(config.episode_dir)
    assert template["decisions_schema"] == fi_grading.DECISIONS_SCHEMA
    assert template["binding"]["bundle_sha256"] == catalogue().bundle_sha256
    assert template["binding"]["key_sha256"] == fi_grading.key_sha256(key())
    assert set(template["criteria"]) == {c["criterion_id"] for c in key()["criteria"]}
    entry = template["criteria"]["T10.02a"]
    assert entry["accept_judge"] is False and entry["finding_ids"] == ["F1"]
    assert set(template["explanation_quality"]["by_dimension"]) == {
        d["dimension_id"] for d in key()["dimensions"]
    }
    # a filled-in template is accepted as decisions
    template["reviewer"], template["date"] = "test reviewer", "2026-10-20"
    graded = fi_grading.grade_episode(config.episode_dir, decisions=template)
    assert graded["decisions"]["reviewer"] == "test reviewer"


def test_command_line(routed, tmp_path: Path):
    config, _ = routed
    out = tmp_path / "grade.json"
    assert fi_grading.main(["grade", str(config.episode_dir), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["grade_schema"] == fi_grading.GRADE_SCHEMA
    tpl = tmp_path / "tpl.json"
    assert (
        fi_grading.main(["review-template", str(config.episode_dir), "--out", str(tpl)])
        == 0
    )
    assert (
        json.loads(tpl.read_text())["decisions_schema"] == fi_grading.DECISIONS_SCHEMA
    )
    sub = tmp_path / "submission.json"
    sub.write_text(json.dumps(route_submission()))
    out2 = tmp_path / "grade2.json"
    assert fi_grading.main(["grade-submission", str(sub), "--out", str(out2)]) == 0
    assert json.loads(out2.read_text())["trace"] is None
    missing = str(tmp_path / "missing.json")
    assert (
        fi_grading.main(["grade", str(config.episode_dir), "--decisions", missing]) == 1
    )


def test_task_judge_runs_the_full_investigation_grader(tmp_path: Path):
    config = FullInvestigationToolConfig(**episode_config(tmp_path).model_dump())
    sub = oracle_submission()
    calls = ROUTES + [("submit_findings", {"submission": sub})]
    results = run_calls(config, calls)
    assert results[-1][2].envelope["ok"], results[-1][2].envelope["error"]
    scoring = FullInvestigationJudge(config).evaluate(transcript_for(results))
    assert scoring.score == 1.0
    grading = scoring.metadata["grading"]
    assert grading["status"] == "graded", grading
    grade = grading["grade"]
    assert grade["grade_schema"] == fi_grading.GRADE_SCHEMA
    assert grade["run"]["outcome"] == "complete"
    assert grade["run"]["budgets"]["output_token_budget"] == 80_000
    on_disk = json.loads((Path(config.episode_dir) / GRADE_FILE).read_text())
    assert (
        on_disk["submission"]["sha256"]
        == read_state(config.episode_dir).submission_sha256
    )
    assert all(r["content"]["auto_proposal"] == 1 for r in grade["criteria"])
    assert len(grade["criteria"]) == len(key()["criteria"])


def test_an_episode_on_a_synthetic_bundle_is_graded_without_crashing(tmp_path: Path):
    """The task's judge may run on the synthetic test bundle: the key's locators do
    not apply there, so everything stays provisional, but grading never fails."""
    from fi_helpers import fi_config, fi_submission, make_fi_bundle

    bundle = make_fi_bundle(tmp_path / "src")
    config = fi_config(tmp_path, bundle)
    results = run_calls(config, [("submit_findings", {"submission": fi_submission()})])
    assert results[-1][2].envelope["ok"], results[-1][2].envelope["error"]
    report = fi_grading.grade_episode(config.episode_dir)
    assert report["bundle"]["matches_key"] is False
    assert any("another bundle" in r for r in report["provisional_reasons"])
    assert len(report["criteria"]) == len(key()["criteria"])
    scoring = FullInvestigationJudge(
        FullInvestigationToolConfig(**config.model_dump())
    ).evaluate(transcript_for(results))
    assert scoring.metadata["grading"]["status"] == "graded"
