"""End to end: the full-investigation fake scenarios through the episode core, the task's
judge and ``environment.incident.fi_grading``, on the shipped bundle, then replayed.

The fake model's tool calls are sent through ``Episode.call`` in a temporary episode that
uses ``bundles/full_investigation`` and the local Python (development mode).
``FullInvestigationJudge`` classifies the outcome and runs ``fi_grading.grade_episode``;
the trace is replayed (deterministic calls byte for byte, Python re-run). The runs through
Karotte's runner and MCP server are in ``test_fi_fake_model.py``. No model or judge is
called.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from fi_fake_support import BUNDLE, drive

from environment import fake_model_fi
from environment.incident import fi_grading
from environment.incident.episode import GRADE_FILE, read_state, read_trace
from environment.incident.frequency import load_series, reference_landmarks
from environment.incident.replay import replay_episode

CSV = BUNDLE / "R01" / "frequency_2019-08-09_1640-1745_BST.csv"


@pytest.fixture(scope="module")
def reference_run(tmp_path_factory):
    return drive("reference", tmp_path_factory.mktemp("fi-reference"))


def _full(row: dict) -> bool:
    content, evidence = row["content"], row["evidence_support"]
    return (content["value"] == 1 or content["auto_proposal"] == 1) and (
        evidence["value"] == 1 or evidence["auto_proposal"] == 1
    )


# -- reference -------------------------------------------------------------------------------
def test_reference_run_is_complete_and_within_budget(reference_run):
    config, calls, scoring = reference_run
    not_held = set(fake_model_fi.FI_REFERENCE_NOT_HELD)
    for name, args, result in calls:
        if name == "request_data_return" and (args["party"], args["data_type"]) in (
            not_held
        ):
            assert result.error_code == "NOT_HELD"
        else:
            assert result.ok, (name, args, result.envelope["error"])
    assert scoring.score == 1.0
    meta = scoring.metadata
    assert meta["outcome"] == "complete" and meta["incomplete_reason"] is None
    summary = meta["transcript_summary"]
    assert summary["ledger_discrepancy"]["difference"] == 0
    assert summary["budgets"]["output_token_budget"] == 80_000
    state = read_state(config.episode_dir)
    assert state.frozen and state.calls_used == len(calls) <= 60
    assert state.invalid_submission_attempts == 0


def test_reference_python_reproduces_the_landmarks_and_sums(reference_run):
    config, _, _ = reference_run
    python = [r for r in read_trace(config.episode_dir) if r["tool"] == "run_python"]
    assert [r["python"]["exit_code"] for r in python] == [0, 0]
    stdout = python[0]["python"]["stdout"]
    lm = reference_landmarks(load_series(CSV))
    for name in (
        "first_local_minimum",
        "event_minimum",
        "first_at_or_above_50_after_minimum",
    ):
        assert f"{lm[name]['value_hz']:.3f} Hz at {lm[name]['time']}" in stdout
    assert "time below 49 Hz (zero-order hold, 1-s samples): 33 s" in stdout
    assert "first fall below 49 Hz lies between 16:53:40" in stdout
    cross = python[1]["python"]["stdout"]
    assert "= 1878 MW; printed cumulative 1878 MW" in cross
    assert "371 cancelled, 220 part-cancelled, 14428 delay minutes" in cross
    assert "locked out 29 + 2 Class 387 = 31 (stranded 31)" in cross


def test_reference_is_graded_at_full_coverage_with_every_route(reference_run):
    config, _, scoring = reference_run
    grading = scoring.metadata["grading"]
    assert grading["status"] == "graded"
    grade = grading["grade"]
    on_disk = json.loads(
        (Path(config.episode_dir) / GRADE_FILE).read_text(encoding="utf-8")
    )
    assert on_disk == grade
    assert grade["grade_schema"] == fi_grading.GRADE_SCHEMA
    assert grade["task_id"] == "gb-2019-full-investigation"
    assert grade["run"]["outcome"] == "complete"
    assert grade["bundle"]["matches_key"] and grade["bundle"]["matches_episode"]
    assert grade["status"] == "provisional"
    assert len(grade["criteria"]) == 106
    assert [r["criterion_id"] for r in grade["criteria"] if not _full(r)] == []
    for cid in ("T03.01", "T03.02", "T03.03", "T04.01"):
        row = next(r for r in grade["criteria"] if r["criterion_id"] == cid)
        assert row["content"]["source"] == "auto" and row["content"]["value"] == 1
        assert "R01 analysed with run_python" in row["evidence_support"]["basis"]
    trace = grade["trace"]
    assert trace["r01_analysed_with_python"] is True
    routes = trace["document_routes"]
    assert routes["S05"] == routes["S06"] == ["request_data_return"]
    assert routes["S07"] == routes["S12"] == ["request_document"]  # by description
    assert "query_frequency" in routes["R01"]
    assert set(trace["records_by_kind"]) == {"event", "entry", "response"}
    cited_routes = {
        route for c in grade["citations"] for route in c["retrieval_routes"]
    }
    assert cited_routes == {
        "request_document",
        "request_data_return",
        "query_frequency",
        "query_asset_log",
        "query_control_log",
        "interview_witness",
    }
    assert all(c["retrieved_during_episode"] for c in grade["citations"])
    flags = grade["flags"]
    for name in (
        "cited_but_never_retrieved",
        "records_cited_via_document_only",
        "unresolvable_citations",
        "suspected_severe_assertions",
        "accounting_traps",
        "conflicting_values",
        "labelling",
        "status_inferential_language",
        "findings_not_referenced_in_report",
        "uncited_findings",
    ):
        assert not flags[name], (name, flags[name])
    assert flags["executive_summary"]["within_limit"] is True
    assert grade["severe_flags"] == []


def test_reference_replays_byte_for_byte(reference_run):
    config, calls, _ = reference_run
    report = replay_episode(config.episode_dir, bundle_dir=BUNDLE)
    assert report.ok, report.summary_text()
    deterministic = [i for i in report.items if i.tool != "run_python"]
    assert len(deterministic) == len(calls) - 2
    assert all(i.status == "match" for i in deterministic)
    rerun = replay_episode(config.episode_dir, bundle_dir=BUNDLE, rerun_python=True)
    assert rerun.ok, rerun.summary_text()
    assert [i.status for i in rerun.items if i.tool == "run_python"] == [
        "rerun_match",
        "rerun_match",
    ]


def test_reference_grade_from_the_command_line(reference_run, tmp_path: Path):
    config, _, scoring = reference_run
    out = tmp_path / "grade.json"
    assert fi_grading.main(["grade", str(config.episode_dir), "--out", str(out)]) == 0
    cli = json.loads(out.read_text(encoding="utf-8"))
    assert (
        cli["content_coverage"]
        == scoring.metadata["grading"]["grade"]["content_coverage"]
    )
    template = fi_grading.review_template(config.episode_dir)
    assert template["decisions_schema"] == fi_grading.DECISIONS_SCHEMA
    assert template["binding"]["submission_sha256"] == (
        read_state(config.episode_dir).submission_sha256
    )
    assert set(template["criteria"]) == {r["criterion_id"] for r in cli["criteria"]}


# -- repair, no submission ---------------------------------------------------------------
def test_repair_run_freezes_the_reference_after_one_rejection(
    tmp_path: Path, reference_run
):
    config, calls, scoring = drive("repair", tmp_path)
    submits = [result for name, _, result in calls if name == "submit_findings"]
    assert [r.error_code for r in submits] == ["VALIDATION_FAILED", None]
    details = submits[0].envelope["error"]["details"]
    assert len(details) == 5
    assert any("belongs to evidence R09, not R11" in d["message"] for d in details)
    state = read_state(config.episode_dir)
    assert state.frozen and state.invalid_submission_attempts == 1
    assert state.calls_used == len(calls)
    assert scoring.score == 1.0 and scoring.metadata["outcome"] == "complete"
    ref_state = read_state(reference_run[0].episode_dir)
    assert state.submission_sha256 == ref_state.submission_sha256
    grade = scoring.metadata["grading"]["grade"]
    assert [r["criterion_id"] for r in grade["criteria"] if not _full(r)] == []
    assert replay_episode(config.episode_dir, bundle_dir=BUNDLE).ok


def test_no_submission_run_is_incomplete(tmp_path: Path):
    config, calls, scoring = drive("no_submission", tmp_path)
    assert "submit_findings" not in [name for name, _, _ in calls]
    assert scoring.score == 0.0
    meta = scoring.metadata
    assert meta["outcome"] == "incomplete_submission"
    assert meta["incomplete_reason"] == "final_message_without_submission"
    grade = meta["grading"]["grade"]
    assert grade["run"]["outcome"] == "incomplete_submission"
    assert grade["criteria"] == [] and grade["content_coverage"] is None
    assert grade["grade_schema"] == fi_grading.GRADE_SCHEMA
    assert replay_episode(config.episode_dir, bundle_dir=BUNDLE).ok


# -- isolation probe (local: tool probes and the materialisation probe) ------------------------
def test_isolation_probe_run_locally(tmp_path: Path):
    config, calls, scoring = drive(
        "isolation_probe", tmp_path, skip_sandbox_probes=True
    )
    expected = {
        json.dumps([tool, args], sort_keys=True): outcome
        for tool, args, outcome in fake_model_fi.FI_TOOL_PROBES
    }
    for name, args, result in calls:
        outcome = expected.get(json.dumps([name, args], sort_keys=True))
        if outcome is None:
            assert result.ok, (name, args, result.envelope["error"])
        elif outcome == "no_answer":
            assert result.envelope["evidence_ids"] == []
        else:
            assert result.error_code == outcome, (name, args)
    hostile = [
        r
        for name, args, r in calls
        if json.dumps([name, args], sort_keys=True) in expected
    ]
    assert len(hostile) == len(fake_model_fi.FI_TOOL_PROBES) == 34
    tally = Counter(r.error_code or "ok" for r in hostile)
    assert tally["UNKNOWN_ID"] == 26 and tally["INVALID_ARGUMENT"] == 2, tally
    assert tally["AMBIGUOUS_REQUEST"] + tally["ok"] == 6, tally
    probe = [r for name, _, r in calls if name == "run_python"]
    assert len(probe) == 1
    stdout = probe[0].envelope["data"]["stdout"]
    for line in (
        "PASS materialised_only_obtained: evidence holds ['R12', 'S08']",
        "PASS no_log_files_materialised",
        "PASS no_witness_cards_materialised",
        "INFO obtained_document_readable: R12 readable",
    ):
        assert line in stdout, stdout
    for doc in ("S10", "R09", "R11", "S11"):
        assert f"PASS unrequested_document_absent_{doc}" in stdout
    evidence = sorted(p.name for p in Path(config.evidence_dir).iterdir())
    assert evidence == sorted(fake_model_fi.FI_PROBE_OBTAINED)
    assert scoring.score == 1.0  # the inconclusive submission is valid
    grade = scoring.metadata["grading"]["grade"]
    assert all(r["content"]["auto_proposal"] == 0 for r in grade["criteria"])
    assert grade["severe_flags"] == []
