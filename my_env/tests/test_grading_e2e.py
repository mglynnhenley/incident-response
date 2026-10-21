"""End to end: fake-agent scenarios through the episode core, the judge and grading.

The fake model's tool calls are parsed and sent through ``Episode.call`` in a temporary
episode that uses the real evidence bundle and the local Python (development mode). The
EpisodeJudge then classifies the outcome and runs ``grade_episode``; the trace is
replayed. One test also drives the reference scenario through Karotte's real
EvaluationRunner and MCP server.
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from incident_helpers import make_bundle, transcript_for
from karotte import EvaluationRunConfig, ProtectedStore, ToolConfigWriter
from karotte import evaluation_runner as runner_module
from karotte import tool_base as karotte_tool_base
from karotte.agents import FakeSource, MessageLoopAgent
from karotte.mcp_servers.mcp_server import McpServer
from karotte.schemas import HttpMcpServerConfig
from karotte.schemas.transcript import ScoringEvent

import environment.tasks.gb_2019_electrical_disturbance as task_module
from environment import fake_model
from environment.incident import cli, grading
from environment.incident.catalogue import Catalogue
from environment.incident.episode import (
    GRADE_FILE,
    Episode,
    EpisodeConfig,
    read_state,
    read_trace,
)
from environment.incident.frequency import load_series, reference_landmarks
from environment.incident.paths import DEFAULT_BUNDLE_DIR
from environment.incident.replay import replay_episode
from environment.tasks.gb_2019_electrical_disturbance import (
    GB2019ElectricalDisturbanceTask,
    IncidentToolConfig,
)
from environment.tasks.gb_2019_electrical_disturbance.judge import EpisodeJudge

CSV = DEFAULT_BUNDLE_DIR / "R01" / "frequency_2019-08-09_1640-1745_BST.csv"


def run_config(scenario: str, tmp_path: Path) -> EvaluationRunConfig:
    return EvaluationRunConfig(
        run_id="e2e",
        task_id="gb-2019-electrical-disturbance",
        model="fake",
        model_api_key="k",
        use_fake_model=True,
        save_artifacts=False,
        mcp_server_config=HttpMcpServerConfig(host="0.0.0.0", port=8080),
        transcript_file=str(tmp_path / "out" / "transcript.json"),
        step_context_window_limit=200_000,
        on_step_context_window_limit="score",
        step_time_limit_seconds=600,
        on_step_time_limit="score",
        extra_config={"fake_scenario": scenario},
    )


def episode_config(tmp_path: Path) -> EpisodeConfig:
    return EpisodeConfig(
        episode_dir=tmp_path / "root_data" / "episode",
        evidence_dir=tmp_path / "workdir" / "evidence",
        scratch_dir=tmp_path / "workdir" / "scratch",
        bundle_dir=DEFAULT_BUNDLE_DIR,
        python_executable=sys.executable,
        python_timeout_s=120,
    )


def drive(scenario: str, tmp_path: Path):
    """Run a scenario's tool calls through the ledger and judge the episode."""
    config = episode_config(tmp_path)
    episode = Episode(config)
    episode.reset()
    messages = fake_model.get_messages(run_config(scenario, tmp_path))
    calls = []
    for message in messages:
        for tool_call in message.tool_calls or []:
            args = json.loads(tool_call.function.arguments)
            calls.append(
                (
                    tool_call.function.name,
                    args,
                    episode.call(tool_call.function.name, args),
                )
            )
    final = messages[-1]
    assert not final.tool_calls
    transcript = transcript_for(calls, final_text=final.content)
    scoring = EpisodeJudge(config).evaluate(transcript)
    return config, calls, scoring


@pytest.fixture(scope="module")
def landmarks() -> dict:
    return reference_landmarks(load_series(CSV))


def test_reference_scenario_end_to_end(tmp_path: Path, landmarks):
    config, calls, scoring = drive("reference", tmp_path)
    assert [result.ok for _, _, result in calls] == [True] * len(calls)
    assert scoring.score == 1.0
    meta = scoring.metadata
    assert meta["outcome"] == "complete" and meta["incomplete_reason"] is None
    assert meta["transcript_summary"]["ledger_discrepancy"]["difference"] == 0

    # the reference analysis, run through run_python, reproduces the landmarks and 33 s
    trace = read_trace(config.episode_dir)
    python = [r for r in trace if r["tool"] == "run_python"]
    assert len(python) == 1 and python[0]["python"]["exit_code"] == 0
    stdout = python[0]["python"]["stdout"]
    for key in (
        "first_local_minimum",
        "event_minimum",
        "first_at_or_above_50_after_minimum",
    ):
        lm = landmarks[key]
        assert f"{lm['value_hz']:.3f} Hz at {lm['time']}" in stdout
    assert "time below 49 Hz (zero-order hold, 1-s samples): 33 s" in stdout
    assert landmarks["below_49"]["covered_below_s"] == 33

    # grading ran inside the judge and wrote grade.json
    grading = meta["grading"]
    assert grading["status"] == "graded"
    grade = grading["grade"]
    on_disk = json.loads((config.episode_dir / GRADE_FILE).read_text(encoding="utf-8"))
    assert on_disk == grade
    assert grade["run"]["outcome"] == "complete"
    assert grade["status"] == "provisional"
    assert grade["trace"]["retrieved"] == ["R01", "R03", "S01", "S03", "S04"]
    assert grade["trace"]["r01_analysed_with_python"] is True
    rows = {c["criterion_id"]: c for c in grade["criteria"]}
    for cid in ("D3.1", "D3.2", "D3.3", "D3.4"):
        assert (
            rows[cid]["content"]["value"] == 1
            and rows[cid]["content"]["source"] == "auto"
        )
        assert rows[cid]["evidence_support"]["value"] == 1
        assert "retrieval not checked" not in rows[cid]["evidence_support"]["basis"]
    assert all(c["retrieved_during_episode"] for c in grade["citations"])
    assert grade["flags"]["cited_but_never_retrieved"] == []

    # replay: deterministic calls are byte-equivalent; Python re-runs identically
    report = replay_episode(config.episode_dir, bundle_dir=DEFAULT_BUNDLE_DIR)
    assert report.ok, report.summary_text()
    statuses = {item.tool: item.status for item in report.items}
    assert statuses["run_python"] == "recorded"
    assert all(i.status == "match" for i in report.items if i.tool != "run_python")
    rerun = replay_episode(
        config.episode_dir, bundle_dir=DEFAULT_BUNDLE_DIR, rerun_python=True
    )
    assert rerun.ok and [i.status for i in rerun.items if i.tool == "run_python"] == [
        "rerun_match"
    ]

    # the runtime CLI uses the grading module for grade and review-template
    out = tmp_path / "grade_cli.json"
    assert cli.main(["grade", str(config.episode_dir), "--out", str(out)]) == 0
    cli_grade = json.loads(out.read_text(encoding="utf-8"))
    assert cli_grade["run"]["outcome"] == "complete"
    assert cli_grade["content_coverage"] == grade["content_coverage"]
    template = tmp_path / "template.json"
    assert (
        cli.main(["review-template", str(config.episode_dir), "--out", str(template)])
        == 0
    )
    binding = json.loads(template.read_text(encoding="utf-8"))["binding"]
    assert (
        binding["submission_sha256"] == read_state(config.episode_dir).submission_sha256
    )


def test_repair_scenario_end_to_end(tmp_path: Path):
    config, calls, scoring = drive("repair", tmp_path)
    submits = [result for name, _, result in calls if name == "submit_findings"]
    assert [r.error_code for r in submits] == ["VALIDATION_FAILED", None]
    state = read_state(config.episode_dir)
    assert state.frozen and state.invalid_submission_attempts == 1
    assert state.calls_used == len(calls)
    assert scoring.score == 1.0 and scoring.metadata["outcome"] == "complete"
    grade = scoring.metadata["grading"]["grade"]
    reference = fake_model.reference_submission()
    assert grade["submission"]["findings"] == len(reference["findings"])
    assert replay_episode(config.episode_dir, bundle_dir=DEFAULT_BUNDLE_DIR).ok


def test_no_submission_scenario_is_incomplete(tmp_path: Path):
    config, calls, scoring = drive("no_submission", tmp_path)
    assert scoring.score == 0.0
    meta = scoring.metadata
    assert meta["outcome"] == "incomplete_submission"
    assert meta["incomplete_reason"] == "final_message_without_submission"
    grade = meta["grading"]["grade"]
    assert grade["run"]["outcome"] == "incomplete_submission"
    assert grade["run"]["incomplete_reason"] == "final_message_without_submission"
    assert grade["content_coverage"] is None and grade["evidence_support"] is None
    assert grade["assertion_quality"] is None and grade["criteria"] == []
    assert "incomplete runs" in grade["measures_note"]
    assert replay_episode(config.episode_dir, bundle_dir=DEFAULT_BUNDLE_DIR).ok


@pytest.fixture
def karotte_harness(tmp_path: Path, monkeypatch):
    configs_dir = tmp_path / "tool_configs"
    store_dir = tmp_path / "protected"
    monkeypatch.setattr(karotte_tool_base, "CONFIGS_DIR", configs_dir)
    monkeypatch.setattr(
        runner_module, "ToolConfigWriter", lambda: ToolConfigWriter(configs_dir)
    )
    monkeypatch.setattr(
        runner_module, "ProtectedStore", lambda: ProtectedStore(store_dir)
    )
    config = IncidentToolConfig(**episode_config(tmp_path).model_dump())
    monkeypatch.setattr(
        GB2019ElectricalDisturbanceTask, "episode_config", lambda self: config
    )
    monkeypatch.setattr(
        task_module.InvestigationStep, "episode_config", property(lambda self: config)
    )
    return config


def test_reference_scenario_through_karotte_runner(tmp_path: Path, karotte_harness):
    config = karotte_harness
    rc = run_config("reference", tmp_path)
    task = GB2019ElectricalDisturbanceTask(rc)
    runner = runner_module.EvaluationRunner(rc, task)
    runner._agent = MessageLoopAgent(FakeSource(fake_model.get_messages(rc)))
    mcp = McpServer("grading-e2e")

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
    assert scoring.metadata["transcript_summary"]["tool_calls_episode_tools"] == 8
    grade = scoring.metadata["grading"]["grade"]
    assert grade["run"]["transcript_available"] is True
    assert grade["trace"]["r01_analysed_with_python"] is True
    assert (config.episode_dir / GRADE_FILE).exists()
    d3 = grade["content_coverage"]["by_dimension"]["D3"]
    assert d3["decided_content_sum"] == 4


def test_episode_is_graded_only_against_its_recorded_bundle(tmp_path: Path, capsys):
    """An episode's citations refer to the bundle it ran on (episode_config.json): grading
    it against another bundle fails with a clear message (CLI: exit 1, no traceback),
    and ``--bundle-dir`` selects the recorded bundle."""
    config, _, _ = drive("reference", tmp_path)
    episode = config.episode_dir
    grade = grading.grade_episode(episode)
    installed = Catalogue.load(DEFAULT_BUNDLE_DIR)
    assert grade["bundle"]["matches_episode"] is True
    assert grade["bundle"]["episode_bundle_version"] == installed.bundle_version
    assert not any("bundle" in r for r in grade["provisional_reasons"])

    other_dir = make_bundle(tmp_path / "other", version="0.9.0-test")
    other = Catalogue.load(other_dir)
    with pytest.raises(grading.GradingError, match="recorded on evidence bundle"):
        grading.grade_episode(episode, catalogue=other)
    capsys.readouterr()
    assert cli.main(["grade", str(episode), "--bundle", str(other_dir)]) == 1
    assert (
        cli.main(["review-template", str(episode), "--bundle-dir", str(other_dir)]) == 1
    )
    assert grading.main(["grade", str(episode), "--bundle-dir", str(other_dir)]) == 1
    err = capsys.readouterr().err
    assert err.count("GradingError") == 3 and "Traceback" not in err
    assert "0.9.0-test" in err and installed.bundle_version in err
    # the recorded bundle passed explicitly is accepted
    out = tmp_path / "grade.json"
    args = ["grade", str(episode), "--bundle-dir", str(DEFAULT_BUNDLE_DIR)]
    assert grading.main([*args, "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["bundle"]["matches_episode"]

    # an episode recorded on a bundle that is not installed (e.g. bundle 1.0.0 runs
    # after the move to 1.1.0) is refused instead of being graded on the installed one
    snapshot_path = episode / "episode_config.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot.update(bundle_version="1.0.0", bundle_sha256="0" * 64)
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(grading.GradingError, match="bundle 1.0.0"):
        grading.grade_episode(episode)
    capsys.readouterr()
    assert cli.main(["grade", str(episode)]) == 1
    assert "Traceback" not in capsys.readouterr().err
