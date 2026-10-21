"""End to end: the system-response fake scenarios through the episode core, the task's
judge and the system-response grader, on the real bundle, then replayed.

The fake model's tool calls are sent through ``Episode.call`` in a temporary episode that
uses the shipped ``bundles/system_response`` bundle and the local Python (development
mode). ``SystemResponseJudge`` classifies the outcome and runs
``environment.incident.sr_grading.grade_episode``; the trace is replayed (deterministic
calls byte for byte, Python re-run). One test drives the reference scenario through
Karotte's real EvaluationRunner and MCP server. No model or judge is called.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from incident_helpers import transcript_for
from karotte import EvaluationRunConfig, ProtectedStore, ToolConfigWriter
from karotte import evaluation_runner as runner_module
from karotte import tool_base as karotte_tool_base
from karotte.agents import FakeSource, MessageLoopAgent
from karotte.mcp_servers.mcp_server import McpServer
from karotte.schemas import HttpMcpServerConfig
from karotte.schemas.transcript import ScoringEvent

import environment.tasks.gb_2019_system_response as task_module
from environment import fake_model
from environment.incident import sr_grading
from environment.incident.episode import (
    GRADE_FILE,
    Episode,
    read_state,
    read_trace,
)
from environment.incident.frequency import load_series, reference_landmarks
from environment.incident.paths import SYSTEM_RESPONSE_BUNDLE_DIR
from environment.incident.replay import replay_episode
from environment.tasks.gb_2019_system_response import (
    GB2019SystemResponseTask,
    SystemResponseToolConfig,
)
from environment.tasks.gb_2019_system_response.judge import SystemResponseJudge

CSV = SYSTEM_RESPONSE_BUNDLE_DIR / "R01" / "frequency_2019-08-09_1640-1745_BST.csv"
NOT_HELD = {
    ("METEOGROUP", "lightning_stroke_records"),
    ("DNO", "real_time_distributed_generation_telemetry"),
}


def run_config(scenario: str, root: Path) -> EvaluationRunConfig:
    return EvaluationRunConfig(
        run_id="sr-e2e",
        task_id=fake_model.SR_TASK_ID,
        model="fake",
        model_api_key="k",
        use_fake_model=True,
        save_artifacts=False,
        mcp_server_config=HttpMcpServerConfig(host="0.0.0.0", port=8080),
        transcript_file=str(root / "out" / "transcript.json"),
        step_context_window_limit=200_000,
        on_step_context_window_limit="score",
        step_time_limit_seconds=600,
        on_step_time_limit="score",
        extra_config={"fake_scenario": scenario},
    )


def tool_config(root: Path) -> SystemResponseToolConfig:
    return SystemResponseToolConfig(
        episode_dir=root / "root_data" / "episode",
        evidence_dir=root / "workdir" / "evidence",
        scratch_dir=root / "workdir" / "scratch",
        python_executable=sys.executable,
        python_timeout_s=120,
    )


def drive(scenario: str, root: Path, *, skip_sandbox_probes: bool = False):
    """Send a scenario's tool calls through the ledger and judge the episode. The
    isolation scenario's first two ``run_python`` probes (network, background process)
    are skipped locally: they are container checks."""
    config = tool_config(root)
    episode = Episode(config)
    episode.reset()
    messages = fake_model.get_messages(run_config(scenario, root))
    calls = []
    for index, message in enumerate(messages):
        for tool_call in message.tool_calls or []:
            args = json.loads(tool_call.function.arguments)
            if (
                skip_sandbox_probes
                and tool_call.function.name == "run_python"
                and index < 2
            ):
                continue
            calls.append(
                (
                    tool_call.function.name,
                    args,
                    episode.call(tool_call.function.name, args),
                )
            )
    final = messages[-1]
    assert not final.tool_calls
    scoring = SystemResponseJudge(config).evaluate(
        transcript_for(calls, final_text=final.content)
    )
    return config, calls, scoring


@pytest.fixture(scope="module")
def reference_run(tmp_path_factory):
    return drive("reference", tmp_path_factory.mktemp("sr-reference"))


def _full(row: dict) -> bool:
    content, evidence = row["content"], row["evidence_support"]
    return (content["value"] == 1 or content["auto_proposal"] == 1) and (
        evidence["value"] == 1 or evidence["auto_proposal"] == 1
    )


# -- reference -----------------------------------------------------------------------------
def test_reference_run_is_complete_and_within_budget(reference_run):
    config, calls, scoring = reference_run
    for name, args, result in calls:
        if (
            name == "request_data_return"
            and (args["party"], args["data_type"]) in NOT_HELD
        ):
            assert result.error_code == "NOT_HELD"
        else:
            assert result.ok, (name, args, result.envelope["error"])
    assert scoring.score == 1.0
    meta = scoring.metadata
    assert meta["outcome"] == "complete" and meta["incomplete_reason"] is None
    summary = meta["transcript_summary"]
    assert summary["ledger_discrepancy"]["difference"] == 0
    state = read_state(config.episode_dir)
    assert state.frozen and state.calls_used == len(calls) <= 60
    assert state.invalid_submission_attempts == 0


def test_reference_python_reproduces_the_landmarks(reference_run):
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
    cross = python[1]["python"]["stdout"]
    assert "six-component sum 1878 MW" in cross
    assert "T_LBAR-1: SP33 663.4 MW -> SP35 -9.6 MW" in cross


def test_reference_is_graded_at_full_coverage_with_every_route(reference_run):
    config, _, scoring = reference_run
    grading = scoring.metadata["grading"]
    assert grading["status"] == "graded"
    grade = grading["grade"]
    on_disk = json.loads(
        (Path(config.episode_dir) / GRADE_FILE).read_text(encoding="utf-8")
    )
    assert on_disk == grade
    assert grade["grade_schema"] == sr_grading.GRADE_SCHEMA
    assert grade["run"]["outcome"] == "complete"
    assert grade["bundle"]["matches_key"] and grade["bundle"]["matches_episode"]
    assert grade["status"] == "provisional"
    assert len(grade["criteria"]) == 60
    assert [r["criterion_id"] for r in grade["criteria"] if not _full(r)] == []
    for cid in ("T03.01", "T03.02", "T03.03", "T04.01"):
        row = next(r for r in grade["criteria"] if r["criterion_id"] == cid)
        assert row["content"]["source"] == "auto" and row["content"]["value"] == 1
        assert row["evidence_support"]["source"] == "auto"
        assert "R01 analysed with run_python" in row["evidence_support"]["basis"]
    trace = grade["trace"]
    assert trace["r01_analysed_with_python"] is True
    assert trace["document_routes"]["S05"] == ["request_data_return"]
    assert trace["document_routes"]["S06"] == ["request_data_return"]
    assert trace["document_routes"]["S07"] == ["request_document"]  # by description
    assert set(trace["records_by_kind"]) == {"event", "entry", "response"}
    routes = {route for c in grade["citations"] for route in c["retrieval_routes"]}
    assert routes == {
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
    ):
        assert not flags[name], (name, flags[name])
    assert grade["severe_flags"] == []


def test_reference_replays_byte_for_byte(reference_run):
    config, calls, _ = reference_run
    report = replay_episode(config.episode_dir, bundle_dir=SYSTEM_RESPONSE_BUNDLE_DIR)
    assert report.ok, report.summary_text()
    deterministic = [i for i in report.items if i.tool != "run_python"]
    assert len(deterministic) == len(calls) - 2
    assert all(i.status == "match" for i in deterministic)
    rerun = replay_episode(
        config.episode_dir, bundle_dir=SYSTEM_RESPONSE_BUNDLE_DIR, rerun_python=True
    )
    assert rerun.ok, rerun.summary_text()
    assert [i.status for i in rerun.items if i.tool == "run_python"] == [
        "rerun_match",
        "rerun_match",
    ]


def test_reference_grade_from_the_command_line(reference_run, tmp_path: Path):
    config, _, scoring = reference_run
    out = tmp_path / "grade.json"
    assert sr_grading.main(["grade", str(config.episode_dir), "--out", str(out)]) == 0
    cli = json.loads(out.read_text(encoding="utf-8"))
    assert (
        cli["content_coverage"]
        == scoring.metadata["grading"]["grade"]["content_coverage"]
    )
    template = sr_grading.review_template(config.episode_dir)
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
    assert any("belongs to evidence S07, not R08" in d["message"] for d in details)
    state = read_state(config.episode_dir)
    assert state.frozen and state.invalid_submission_attempts == 1
    assert state.calls_used == len(calls)
    assert scoring.score == 1.0 and scoring.metadata["outcome"] == "complete"
    ref_state = read_state(reference_run[0].episode_dir)
    assert state.submission_sha256 == ref_state.submission_sha256
    grade = scoring.metadata["grading"]["grade"]
    assert [r["criterion_id"] for r in grade["criteria"] if not _full(r)] == []
    assert replay_episode(config.episode_dir, bundle_dir=SYSTEM_RESPONSE_BUNDLE_DIR).ok


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
    assert replay_episode(config.episode_dir, bundle_dir=SYSTEM_RESPONSE_BUNDLE_DIR).ok


# -- isolation probe (local: tool probes and the materialisation probe) ----------------------
def test_isolation_probe_run_locally(tmp_path: Path):
    config, calls, scoring = drive(
        "isolation_probe", tmp_path, skip_sandbox_probes=True
    )
    expected = {
        json.dumps([tool, args], sort_keys=True): outcome
        for tool, args, outcome in fake_model.SR_TOOL_PROBES
    }
    for name, args, result in calls:
        outcome = expected.get(json.dumps([name, args], sort_keys=True))
        if outcome is None:
            assert result.ok, (name, args, result.envelope["error"])
        elif outcome == "no_answer":
            assert result.envelope["evidence_ids"] == []
        else:
            assert result.error_code == outcome, (name, args)
    # 28 hostile calls: 21 UNKNOWN_ID, 2 INVALID_ARGUMENT, and the five injected witness
    # questions answered with topic choices (3 AMBIGUOUS_REQUEST) or "not known" (2)
    hostile = [
        r
        for name, args, r in calls
        if json.dumps([name, args], sort_keys=True) in expected
    ]
    assert len(hostile) == len(fake_model.SR_TOOL_PROBES) == 28
    assert Counter(r.error_code or "ok" for r in hostile) == {
        "UNKNOWN_ID": 21,
        "INVALID_ARGUMENT": 2,
        "AMBIGUOUS_REQUEST": 3,
        "ok": 2,
    }
    probe = [r for name, _, r in calls if name == "run_python"]
    assert len(probe) == 1
    stdout = probe[0].envelope["data"]["stdout"]
    for line in (
        "PASS materialised_only_obtained: evidence holds ['R01', 'R03', 'S05']",
        "PASS unrequested_data_return_S06_absent",
        "PASS no_log_files_materialised",
        "PASS no_witness_cards_materialised",
        "INFO obtained_document_readable: R03 readable",
    ):
        assert line in stdout, stdout
    evidence = sorted(p.name for p in Path(config.evidence_dir).iterdir())
    assert evidence == sorted(fake_model.SR_PROBE_OBTAINED)
    assert scoring.score == 1.0  # the inconclusive submission is valid
    grade = scoring.metadata["grading"]["grade"]
    assert all(r["content"]["auto_proposal"] == 0 for r in grade["criteria"])
    assert grade["severe_flags"] == []


# -- through Karotte's runner and MCP server -------------------------------------------------
@pytest.fixture
def karotte_harness(tmp_path: Path, monkeypatch):
    configs_dir = tmp_path / "tool_configs"
    monkeypatch.setattr(karotte_tool_base, "CONFIGS_DIR", configs_dir)
    monkeypatch.setattr(
        runner_module, "ToolConfigWriter", lambda: ToolConfigWriter(configs_dir)
    )
    monkeypatch.setattr(
        runner_module, "ProtectedStore", lambda: ProtectedStore(tmp_path / "protected")
    )
    config = tool_config(tmp_path)
    monkeypatch.setattr(GB2019SystemResponseTask, "episode_config", lambda self: config)
    monkeypatch.setattr(
        task_module.SystemResponseStep, "episode_config", property(lambda self: config)
    )
    return config


def test_reference_scenario_through_karotte_runner(tmp_path: Path, karotte_harness):
    config = karotte_harness
    rc = run_config("reference", tmp_path)
    task = GB2019SystemResponseTask(rc)
    runner = runner_module.EvaluationRunner(rc, task)
    runner._agent = MessageLoopAgent(FakeSource(fake_model.get_messages(rc)))
    mcp = McpServer("sr-fake-e2e")

    @asynccontextmanager
    async def connect():
        from fastmcp import Client

        async with Client(mcp.server) as client:
            yield client

    runner._connect_to_mcp_server = connect

    async def go():
        return [event async for event in runner.run()]

    events = asyncio.run(go())
    scoring = [e for e in events if isinstance(e, ScoringEvent)][0].scoring
    assert scoring.score == 1.0, scoring.metadata.get("incomplete_reason")
    summary = scoring.metadata["transcript_summary"]
    n_calls = len([1 for m in fake_model.get_messages(rc) if m.tool_calls])
    assert summary["tool_calls_episode_tools"] == n_calls
    assert summary["ledger_discrepancy"]["difference"] == 0
    grade = scoring.metadata["grading"]["grade"]
    assert grade["run"]["transcript_available"] is True
    assert [r["criterion_id"] for r in grade["criteria"] if not _full(r)] == []
    assert (Path(config.episode_dir) / GRADE_FILE).exists()
    assert replay_episode(config.episode_dir, bundle_dir=SYSTEM_RESPONSE_BUNDLE_DIR).ok
