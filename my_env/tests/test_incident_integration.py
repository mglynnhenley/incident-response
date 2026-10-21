"""In-process run through Karotte's real EvaluationRunner and McpServer.

A scripted fake agent drives the four tools over an in-memory MCP connection: tool
registration (``discover_tools``), the task's ``configure_tools``/``pre_hook``, the
message loop, ``pre_scoring_hook`` and the EpisodeJudge all run for real. Karotte's
home-directory stores (tool configs, protected store) are redirected to tmp_path.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from incident_helpers import make_bundle, make_config, valid_submission
from karotte import EvaluationRunConfig, ProtectedStore, ToolConfigWriter
from karotte import evaluation_runner as runner_module
from karotte import tool_base as karotte_tool_base
from karotte.agents import FakeSource, MessageLoopAgent
from karotte.mcp_servers.mcp_server import McpServer
from karotte.schemas.chat import ChatCompletionMessageToolCall, Function, Message
from karotte.schemas.transcript import ScoringEvent, TaskCompletedEvent

import environment.tasks.gb_2019_electrical_disturbance as task_module
from environment.incident.episode import read_state, read_trace
from environment.incident.replay import replay_episode
from environment.tasks.gb_2019_electrical_disturbance import (
    GB2019ElectricalDisturbanceTask,
    IncidentToolConfig,
)


def _call(index: int, name: str, args: dict) -> Message:
    return Message(
        role="assistant",
        content=f"Step {index}.",
        tool_calls=[
            ChatCompletionMessageToolCall(
                id=f"call_{index}",
                type="function",
                function=Function(name=name, arguments=json.dumps(args)),
            )
        ],
    )


@pytest.fixture
def harness(tmp_path: Path, monkeypatch):
    configs_dir = tmp_path / "tool_configs"
    store_dir = tmp_path / "protected"
    monkeypatch.setattr(karotte_tool_base, "CONFIGS_DIR", configs_dir)
    monkeypatch.setattr(
        runner_module, "ToolConfigWriter", lambda: ToolConfigWriter(configs_dir)
    )
    monkeypatch.setattr(
        runner_module, "ProtectedStore", lambda: ProtectedStore(store_dir)
    )
    monkeypatch.setitem(sys.modules, "environment.incident.grading", None)
    bundle = make_bundle(tmp_path / "src")
    config = IncidentToolConfig(**make_config(tmp_path, bundle).model_dump())
    monkeypatch.setattr(
        GB2019ElectricalDisturbanceTask, "episode_config", lambda self: config
    )
    monkeypatch.setattr(
        task_module.InvestigationStep, "episode_config", property(lambda self: config)
    )
    return config, bundle


def _run(tmp_path: Path, messages: list[Message]):
    run_config = EvaluationRunConfig(
        run_id="integration",
        task_id="gb-2019-electrical-disturbance",
        model="fake",
        use_fake_model=True,
        save_artifacts=False,
        transcript_file=str(tmp_path / "out" / "transcript.json"),
        step_context_window_limit=200_000,
        on_step_context_window_limit="score",
        step_time_limit_seconds=600,
        on_step_time_limit="score",
    )
    task = GB2019ElectricalDisturbanceTask(run_config)
    runner = runner_module.EvaluationRunner(run_config, task)
    runner._agent = MessageLoopAgent(FakeSource(messages))
    mcp = McpServer("incident-integration")

    @asynccontextmanager
    async def connect():
        from fastmcp import Client

        async with Client(mcp.server) as client:
            yield client

    runner._connect_to_mcp_server = connect

    async def go():
        return [event async for event in runner.run()]

    return asyncio.run(go()), runner


def test_reference_style_run_completes(tmp_path: Path, harness):
    config, bundle = harness
    code = (
        "import os, pandas as pd\n"
        "df = pd.read_csv(os.path.join(os.environ['EVIDENCE_DIR'], 'R01', 'series.csv'))\n"
        "print(df['frequency_hz'].min())\n"
    )
    bad = valid_submission(variant_id="nope")
    messages = [
        _call(1, "list_documents", {}),
        _call(2, "request_document", {"doc_id": "R01"}),
        _call(3, "request_document", {"doc_id": "R03"}),
        _call(4, "run_python", {"code": code}),
        _call(5, "submit_findings", {"submission": bad}),
        _call(6, "submit_findings", {"submission": valid_submission()}),
        Message(role="assistant", content="Submitted; ending my turn."),
    ]
    events, runner = _run(tmp_path, messages)
    completed = [e for e in events if isinstance(e, TaskCompletedEvent)]
    assert completed and completed[-1].status == "passed", [
        getattr(e, "message", "") for e in events if type(e).__name__ == "ErrorEvent"
    ]
    scoring = [e for e in events if isinstance(e, ScoringEvent)][0].scoring
    assert scoring.score == 1.0
    assert scoring.metadata["outcome"] == "complete"
    summary = scoring.metadata["transcript_summary"]
    assert summary["tool_calls_episode_tools"] == 6
    assert summary["ledger_discrepancy"]["difference"] == 0

    state = read_state(config.episode_dir)
    assert (
        state.frozen
        and state.calls_used == 6
        and state.invalid_submission_attempts == 1
    )
    trace = read_trace(config.episode_dir)
    python_record = trace[3]
    assert python_record["python"]["stdout"].strip() == "49.81"

    # the model saw exactly the rendered text of each call
    tool_messages = [m for m in runner.transcript.messages if m.role == "tool"]
    assert len(tool_messages) == 6
    for message, record in zip(tool_messages, trace, strict=True):
        text = message.content[0]["text"]
        assert text.startswith('{"budget":')
        assert (
            record["rendered_text_sha256"] == hashlib.sha256(text.encode()).hexdigest()
        )

    # the registered tool schemas reached the agent with every parameter optional
    tool_names = sorted(t["function"]["name"] for t in runner.tools)
    assert tool_names == [
        "list_documents",
        "request_document",
        "run_python",
        "submit_findings",
    ]
    assert all(not t["function"]["parameters"].get("required") for t in runner.tools)

    assert replay_episode(config.episode_dir, bundle_dir=bundle).ok
    assert Path(tmp_path / "out" / "transcript.json").exists()


def test_run_without_submission_is_incomplete(tmp_path: Path, harness):
    config, _ = harness
    messages = [
        _call(1, "list_documents", {}),
        _call(2, "request_document", {"doc_id": "S04"}),
        Message(role="assistant", content="I have read enough."),
    ]
    events, _ = _run(tmp_path, messages)
    scoring = [e for e in events if isinstance(e, ScoringEvent)][0].scoring
    assert scoring.score == 0.0
    assert scoring.metadata["incomplete_reason"] == "final_message_without_submission"
    assert read_state(config.episode_dir).calls_used == 2
