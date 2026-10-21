"""Grading synthetic system-response episodes on the real bundle: every retrieval route
(documents, data returns, the frequency query, asset and control-room logs, witness
responses), citations never obtained, incomplete runs, the task's judge hook and the
command line."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from incident_helpers import transcript_for
from sr_grading_support import (
    catalogue,
    episode_config,
    finding,
    key,
    oracle_submission,
    row,
    run_calls,
    submission,
)

from environment.incident import sr_grading
from environment.incident.catalogue import Catalogue
from environment.incident.episode import GRADE_FILE, read_state
from environment.incident.grading import GradingError
from environment.incident.paths import DEFAULT_BUNDLE_DIR
from environment.tasks.gb_2019_system_response import SystemResponseToolConfig
from environment.tasks.gb_2019_system_response.judge import SystemResponseJudge

ROUTES = [
    ("request_document", {"doc_id": "R03"}),
    (
        "request_data_return",
        {"party": "DNO", "data_type": "lfdd_disconnection_and_restoration_returns"},
    ),
    (
        "query_frequency",
        {"start": "2019-08-09T16:52:30+01:00", "end": "2019-08-09T16:58:00+01:00"},
    ),
    (
        "query_asset_log",
        {
            "asset_id": "LITTLE-BARFORD",
            "start": "2019-08-09T15:52:00Z",
            "end": "2019-08-09T15:55:00Z",
        },
    ),
    (
        "query_control_log",
        {
            "room": "ESO-ENCC",
            "start": "2019-08-09T15:58:00Z",
            "end": "2019-08-09T16:40:00Z",
        },
    ),
    (
        "interview_witness",
        {
            "persona_id": "eso-control-engineer",
            "question": "When were restoration instructions given to restore demand?",
        },
    ),
]


def _keys(obj) -> set[str]:
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in _keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in _keys(v)}
    return set()


def route_submission() -> dict:
    return submission(
        [
            finding(
                "F1",
                "A lightning strike caused a single-phase (blue) to earth fault on one Eaton Socon–Wymondley 400 kV circuit at 16:52:33.490 BST.",
                "reported",
                [("R03", "L36-L37"), ("R03", "event:R03-C1")],
            ),
            finding(
                "F2",
                "The DNOs reported to ESO that LFDD relays disconnected 931 MW of demand (3.2% of 29 GW).",
                "reported",
                [("S05", "L35")],
            ),
            finding(
                "F3",
                "The ESO progressively instructed the DNOs to restore demand from 16:58 to 17:16 BST.",
                "reported",
                [("S07", "entry:S07-E12"), ("S09", "response:S09-ESO-05")],
            ),
            finding(
                "F4",
                "The minimum 1-s sample was 48.787 Hz at 16:53:49 BST.",
                "observed",
                [("R01", "row:830")],
                quantity={"value": 48.787, "unit": "Hz", "basis": "R01 sample"},
                event_time="2019-08-09T16:53:49+01:00",
            ),
            finding(
                "F5",
                "Gas turbine GT1A tripped from 210 MW at T + 57.620 s.",
                "reported",
                [("S03", "event:S03-SOE-E7"), ("S12", "L23")],
            ),
            finding(
                "F6",
                "Embedded-generation returns: all DNOs together reported 462 MW lost.",
                "reported",
                [("S06", "L20-L21")],
            ),
        ],
        report="Findings [F1] [F2] [F3] [F4] [F5] [F6].",
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


def test_trace_info_records_every_route(routed):
    config, _ = routed
    info = sr_grading.trace_info_from_episode(config.episode_dir)
    assert info["retrieved"] == ["R03", "S05", "R01"]
    assert info["document_routes"] == {
        "R03": ["request_document"],
        "S05": ["request_data_return"],
        "R01": ["query_frequency"],
    }
    assert info["records"]["event:S03-SOE-E7"]["tool"] == "query_asset_log"
    assert info["records"]["entry:S07-E12"]["tool"] == "query_control_log"
    assert info["records"]["response:S09-ESO-05"]["tool"] == "interview_witness"
    assert info["records"]["response:S09-ESO-05"]["evidence_id"] == "S09"
    assert info["frequency_rows_seen"] == [[751, 1080]]
    assert info["r01_analysed_with_python"] is False


def test_citations_are_checked_against_every_route(routed):
    config, _ = routed
    report = sr_grading.grade_episode(config.episode_dir)
    by = {(c["finding_id"], c["locator"]): c for c in report["citations"]}
    assert by[("F1", "L36-L37")]["retrieval_routes"] == ["request_document"]
    # the record restates R03, which was retrieved as a document; the record itself
    # was never returned by the asset-log tool
    assert by[("F1", "event:R03-C1")]["retrieval_routes"] == ["document"]
    assert by[("F2", "L35")]["retrieval_routes"] == ["request_data_return"]
    assert by[("F3", "entry:S07-E12")]["retrieval_routes"] == ["query_control_log"]
    assert by[("F3", "response:S09-ESO-05")]["retrieval_routes"] == [
        "interview_witness"
    ]
    assert by[("F4", "row:830")]["retrieval_routes"] == ["query_frequency"]
    assert by[("F5", "event:S03-SOE-E7")]["retrieval_routes"] == ["query_asset_log"]
    # S12 was never obtained (and S06 is a data return that was never asked for)
    assert by[("F5", "L23")]["retrieved_during_episode"] is False
    assert by[("F6", "L20-L21")]["retrieved_during_episode"] is False
    assert report["flags"]["cited_but_never_retrieved"] == ["S06 L20-L21", "S12 L23"]
    assert report["flags"]["cited_but_never_retrieved_findings"] == ["F5", "F6"]
    assert report["flags"]["records_cited_via_document_only"] == ["R03 event:R03-C1"]
    assert "T05.01a" in by[("F3", "entry:S07-E12")]["targets_keyed_evidence_of"]


def test_grade_episode_report_structure(routed):
    config, _ = routed
    report = sr_grading.grade_episode(config.episode_dir)
    assert report["grade_schema"] == sr_grading.GRADE_SCHEMA
    assert report["run"]["outcome"] == "complete"
    assert report["bundle"]["matches_key"] and report["bundle"]["matches_episode"]
    assert report["tasks"] == [d["dimension_id"] for d in key()["dimensions"]]
    assert report["status"] == "provisional"
    assert any("pending_domain_review" in r for r in report["provisional_reasons"])
    t0302 = row(report, "T03.02")
    assert t0302["content"] == {**t0302["content"], "value": 1.0, "source": "auto"}
    assert (
        t0302["evidence_support"]["source"] == "auto"
        and t0302["evidence_support"]["value"] == 1
    )
    assert "query_frequency" in t0302["evidence_support"]["basis"]
    for cid in ("T01.01", "T05.01a", "T05.01b", "T09.02a"):
        r = row(report, cid)
        assert (
            r["content"]["auto_proposal"] == 1 and r["content"]["source"] == "pending"
        )
        assert r["evidence_support"]["auto_proposal"] == 1
    t0203a = row(report, "T02.03a")
    assert t0203a["content"]["auto_proposal"] == 1
    # the keyed span it cites (S12 L23) was never obtained; the SOE record it also
    # cites was returned but is not keyed for the 210 MW
    assert t0203a["evidence_support"]["auto_proposal"] == 0
    assert "never obtained" in t0203a["evidence_support"]["basis"]
    coverage = report["content_coverage"]["by_task"]["T05"]
    assert coverage["by_source"]["pending"] == 4
    assert coverage["auto_proposals"]["T05.01a"] == 1
    assert "no task total" in report["content_coverage"]["note"]
    assert not _keys(report) & {"score", "total_score", "overall_score", "pass", "rank"}
    assertions = report["assertion_quality"]["assertions"]
    assert {a["dimension"] for a in assertions} <= set(report["tasks"]) | {"unassigned"}
    assert report["assertion_quality"]["by_task"]["T03"]["by_source"]["pending"] >= 1


def test_record_cited_without_any_route_is_never_retrieved(tmp_path: Path):
    config = episode_config(tmp_path)
    sub = submission(
        [
            finding(
                "F1",
                "GT1B was tripped manually by the operators because of excessive steam pressure.",
                "reported",
                [("S03", "event:S03-SOE-E8"), ("S09", "response:S09-RWE-05")],
            )
        ]
    )
    run_calls(config, [("submit_findings", {"submission": sub})])
    report = sr_grading.grade_episode(config.episode_dir)
    checks = report["citations"]
    assert [c["retrieved_during_episode"] for c in checks] == [False, False]
    t0703 = row(report, "T07.03")
    assert t0703["content"]["auto_proposal"] == 1
    assert t0703["evidence_support"]["auto_proposal"] == 0
    assert "never obtained" in t0703["evidence_support"]["basis"]


def test_r01_landmark_without_analysis_or_samples_needs_a_human(tmp_path: Path):
    config = episode_config(tmp_path)
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
    calls = [
        ("request_document", {"doc_id": "R01"}),
        ("submit_findings", {"submission": sub}),
    ]
    run_calls(config, calls)
    report = sr_grading.grade_episode(config.episode_dir)
    ev = row(report, "T03.02")["evidence_support"]
    assert ev["source"] == "pending" and ev["auto_proposal"] == 1
    assert "neither analysed with run_python" in ev["basis"]


def test_python_analysis_of_r01_settles_landmark_evidence(tmp_path: Path):
    config = episode_config(tmp_path)
    code = (
        "import os, pandas as pd\n"
        "df = pd.read_csv(os.path.join(os.environ['EVIDENCE_DIR'], 'R01', "
        "'frequency_2019-08-09_1640-1745_BST.csv'))\n"
        "print(df['frequency_hz'].min())\n"
    )
    sub = submission(
        [
            finding(
                "F1",
                "Frequency fell below 49 Hz for 33 s (strictly below, zero-order hold).",
                "observed",
                [("R01", "time:2019-08-09T16:53:40+01:00/2019-08-09T16:54:14+01:00")],
                quantity={
                    "value": 33,
                    "unit": "s",
                    "basis": "count of samples strictly below 49 Hz",
                },
                derivation="count of 1-s samples strictly below 49.0 Hz",
            )
        ]
    )
    calls = [
        ("request_document", {"doc_id": "R01"}),
        ("run_python", {"code": code}),
        ("submit_findings", {"submission": sub}),
    ]
    results = run_calls(config, calls)
    assert results[1][2].envelope["ok"], results[1][2].envelope
    report = sr_grading.grade_episode(config.episode_dir)
    assert report["trace"]["r01_analysed_with_python"] is True
    t0401 = row(report, "T04.01")
    assert t0401["content"]["source"] == "auto" and t0401["content"]["value"] == 1
    assert (
        t0401["evidence_support"]["source"] == "auto"
        and t0401["evidence_support"]["value"] == 1
    )


def test_incomplete_run_has_no_content_measures(tmp_path: Path):
    config = episode_config(tmp_path)
    run_calls(config, [("request_document", {"doc_id": "R03"})])
    report = sr_grading.grade_episode(config.episode_dir)
    assert report["run"]["outcome"] != "complete"
    assert report["criteria"] == [] and report["content_coverage"] is None
    assert report["status"] == "provisional"
    template = sr_grading.review_template(config.episode_dir)
    assert template["criteria"] == {} and template["binding"] is None


def test_episode_must_be_graded_on_its_own_bundle(routed):
    config, _ = routed
    with pytest.raises(GradingError, match="bundle"):
        sr_grading.grade_episode(
            config.episode_dir, catalogue=Catalogue.load(DEFAULT_BUNDLE_DIR)
        )


def test_tampered_submission_is_noted(routed):
    config, _ = routed
    path = Path(config.episode_dir) / "submission.json"
    data = json.loads(path.read_text())
    data["findings"][0]["statement"] += " Edited."
    path.write_text(json.dumps(data))
    # without a transcript the ledger alone rejects the edited file
    assert sr_grading.grade_episode(config.episode_dir)["run"]["outcome"] != "complete"
    # a judge summary that calls the run complete still gets the integrity note
    report = sr_grading.grade_episode(config.episode_dir, {"outcome": "complete"})
    assert (
        "submission.json does not match the sha256 in state.json"
        in report["provisional_reasons"]
    )


def test_task_judge_runs_the_system_response_grader(tmp_path: Path):
    config = SystemResponseToolConfig(**episode_config(tmp_path).model_dump())
    sub = oracle_submission()
    calls = ROUTES + [("submit_findings", {"submission": sub})]
    results = run_calls(config, calls)
    assert results[-1][2].envelope["ok"], results[-1][2].envelope["error"]
    scoring = SystemResponseJudge(config).evaluate(transcript_for(results))
    assert scoring.score == 1.0
    grading = scoring.metadata["grading"]
    assert grading["status"] == "graded", grading
    grade = grading["grade"]
    assert grade["grade_schema"] == sr_grading.GRADE_SCHEMA
    assert grade["run"]["outcome"] == "complete"
    on_disk = json.loads((Path(config.episode_dir) / GRADE_FILE).read_text())
    assert (
        on_disk["submission"]["sha256"]
        == read_state(config.episode_dir).submission_sha256
    )
    assert all(r["content"]["auto_proposal"] == 1 for r in grade["criteria"])


def test_review_template_from_an_episode(routed):
    config, _ = routed
    template = sr_grading.review_template(config.episode_dir)
    assert template["decisions_schema"] == sr_grading.DECISIONS_SCHEMA
    assert template["binding"]["bundle_sha256"] == catalogue().bundle_sha256
    assert set(template["criteria"]) == {c["criterion_id"] for c in key()["criteria"]}
    entry = template["criteria"]["T09.02a"]
    assert entry["accept_judge"] is False and entry["finding_ids"] == ["F2"]
    assert entry["_context"]["accounting_basis"] == "LFDD_931"
    assert set(template["explanation_quality"]["by_dimension"]) == set(
        d["dimension_id"] for d in key()["dimensions"]
    )
    assert set(template["assertions"]) == {"F1", "F2", "F3", "F4", "F5", "F6"}


def test_command_line(routed, tmp_path: Path):
    config, _ = routed
    out = tmp_path / "grade.json"
    assert sr_grading.main(["grade", str(config.episode_dir), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["grade_schema"] == sr_grading.GRADE_SCHEMA
    tpl = tmp_path / "tpl.json"
    assert (
        sr_grading.main(["review-template", str(config.episode_dir), "--out", str(tpl)])
        == 0
    )
    assert (
        json.loads(tpl.read_text())["decisions_schema"] == sr_grading.DECISIONS_SCHEMA
    )
    missing = str(tmp_path / "missing.json")
    assert (
        sr_grading.main(["grade", str(config.episode_dir), "--decisions", missing]) == 1
    )
    assert sr_grading.main(["grade", str(config.episode_dir), "--judge", missing]) == 1


def test_an_episode_on_another_v2_bundle_is_graded_without_crashing(tmp_path: Path):
    """The task's judge may run on the synthetic test bundle: the key's locators do
    not apply there, so everything stays provisional, but grading never fails."""
    from sr_helpers import make_sr_bundle, sr_config, sr_submission

    bundle = make_sr_bundle(tmp_path / "src")
    config = sr_config(tmp_path, bundle)
    calls = [
        (
            "query_frequency",
            {"start": "2019-08-09T16:52:00+01:00", "end": "2019-08-09T16:53:00+01:00"},
        ),
        ("submit_findings", {"submission": sr_submission()}),
    ]
    results = run_calls(config, calls)
    assert results[-1][2].envelope["ok"]
    report = sr_grading.grade_episode(config.episode_dir)
    assert report["bundle"]["matches_key"] is False
    assert any("another bundle" in r for r in report["provisional_reasons"])
    assert len(report["criteria"]) == len(key()["criteria"])
    scoring = SystemResponseJudge(
        SystemResponseToolConfig(**config.model_dump())
    ).evaluate(transcript_for(results))
    assert scoring.metadata["grading"]["status"] == "graded"
