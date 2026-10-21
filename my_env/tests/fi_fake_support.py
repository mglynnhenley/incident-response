"""Shared helpers for the full-investigation fake-scenario and reference tests
(``test_fi_fake_*.py``, ``test_fi_reference_*.py``).

Everything runs on the shipped ``bundles/full_investigation`` bundle in a temporary
episode, with the local Python (development mode: isolation itself is enforced in the
container, where ``karotte run --runtime docker`` plays the same scripts). No model and
no judge is called.

* :func:`drive` sends a scenario's tool calls straight through ``Episode.call`` and judges
  the episode with the task's ``FullInvestigationJudge`` (which grades with
  ``environment.incident.fi_grading``).
* :func:`run_through_karotte` plays a scenario through Karotte's ``EvaluationRunner`` and
  MCP server, and returns the run's transcript as well.
* :func:`context_profile` estimates the input context of every model turn of a
  transcript from its characters, with the fit measured on the full-investigation pilot
  (decision 64; see :data:`PILOT_FIT`).
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from incident_helpers import transcript_for
from karotte import EvaluationRunConfig, ProtectedStore, ToolConfigWriter
from karotte import evaluation_runner as runner_module
from karotte import tool_base as karotte_tool_base
from karotte.agents import FakeSource, MessageLoopAgent
from karotte.mcp_servers.mcp_server import McpServer
from karotte.schemas import HttpMcpServerConfig
from karotte.schemas.transcript import ScoringEvent, TaskCompletedEvent

import environment.tasks.gb_2019_full_investigation as task_module
from environment import fake_model
from environment.incident.episode import Episode
from environment.incident.paths import FULL_INVESTIGATION_BUNDLE_DIR
from environment.tasks.gb_2019_full_investigation.judge import FullInvestigationJudge

ENV_ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ENV_ROOT / "configs"
BUNDLE = FULL_INVESTIGATION_BUNDLE_DIR
PILOT_TRANSCRIPT = ENV_ROOT / "out" / "fi_pilot" / "transcript.json"

#: Estimated input tokens of a model turn = a + b x characters of the conversation before
#: it (every message serialised with ``json.dumps(..., ensure_ascii=False)``, as the
#: transcript stores it). Fitted by least squares on the 24 turns of the Opus 5.5 pilot of
#: this task (``out/fi_pilot``, decision 64; provider-reported input tokens): a = 5,057
#: tokens (tool definitions and framing), b = 0.3857 tokens per character; largest
#: residual 1,666 tokens, and 175,269 reported against 174,194 estimated at its last
#: turn. ``test_fi_reference_context`` re-fits it when the pilot transcript is present.
PILOT_FIT = (5057.0, 0.3857)
CONTEXT_CAP_TOKENS = 200_000


def run_config(scenario: str, root: Path) -> EvaluationRunConfig:
    return EvaluationRunConfig(
        run_id="fi-e2e",
        task_id=fake_model.FI_TASK_ID,
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


def tool_config(root: Path) -> task_module.FullInvestigationToolConfig:
    return task_module.FullInvestigationToolConfig(
        episode_dir=root / "root_data" / "episode",
        evidence_dir=root / "workdir" / "evidence",
        scratch_dir=root / "workdir" / "scratch",
        python_executable=sys.executable,
        python_timeout_s=120,
    )


def tool_calls(messages: list[Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (tc.function.name, json.loads(tc.function.arguments))
        for m in messages
        for tc in (m.tool_calls or [])
    ]


def drive(scenario: str, root: Path, *, skip_sandbox_probes: bool = False):
    """Send a scenario's tool calls through the ledger and judge the episode. The
    isolation scenario's first two ``run_python`` probes (network, background process)
    are skipped when asked: they are container checks."""
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
    scoring = FullInvestigationJudge(config).evaluate(
        transcript_for(calls, final_text=final.content)
    )
    return config, calls, scoring


def run_through_karotte(tmp_path: Path, monkeypatch, scenario: str):
    """Play ``configs/fi_fake_<scenario>.json`` through Karotte's runner and MCP server
    in a temporary episode. Returns (tool config, scoring, transcript dict)."""
    config = tool_config(tmp_path)
    configs_dir = tmp_path / "tool_configs"
    monkeypatch.setattr(karotte_tool_base, "CONFIGS_DIR", configs_dir)
    monkeypatch.setattr(
        runner_module, "ToolConfigWriter", lambda: ToolConfigWriter(configs_dir)
    )
    monkeypatch.setattr(
        runner_module, "ProtectedStore", lambda: ProtectedStore(tmp_path / "protected")
    )
    monkeypatch.setattr(
        task_module.GB2019FullInvestigationTask, "episode_config", lambda self: config
    )
    monkeypatch.setattr(
        task_module.FullInvestigationStep,
        "episode_config",
        property(lambda self: config),
    )
    raw = json.loads((CONFIGS / f"fi_fake_{scenario}.json").read_text("utf-8"))
    transcript_file = tmp_path / "out" / "transcript.json"
    raw.update(
        transcript_file=str(transcript_file),
        save_artifacts=False,
        step_time_limit_seconds=600,
    )
    rc = EvaluationRunConfig(**raw)
    task = task_module.GB2019FullInvestigationTask(rc)
    runner = runner_module.EvaluationRunner(rc, task)
    runner._agent = MessageLoopAgent(FakeSource(fake_model.get_messages(rc)))
    mcp = McpServer(f"fi-fake-{scenario}")

    @asynccontextmanager
    async def connect():
        from fastmcp import Client

        async with Client(mcp.server) as client:
            yield client

    runner._connect_to_mcp_server = connect

    async def go():
        return [event async for event in runner.run()]

    events = asyncio.run(go())
    completed = [e for e in events if isinstance(e, TaskCompletedEvent)]
    assert completed, [getattr(e, "message", "") for e in events]
    scoring = [e for e in events if isinstance(e, ScoringEvent)][0].scoring
    transcript = json.loads(transcript_file.read_text(encoding="utf-8"))
    return config, scoring, transcript


def context_profile(
    transcript: dict[str, Any], fit: tuple[float, float] = PILOT_FIT
) -> list[dict[str, Any]]:
    """For every assistant turn of a transcript: the characters of the conversation
    before it (its input), by role, and the input tokens estimated with ``fit``."""
    messages = [
        e["message"] for e in transcript["events"] if e["type"] == "message_added"
    ]
    out = []
    for index, message in enumerate(messages):
        if message["role"] != "assistant":
            continue
        by_role: dict[str, int] = {}
        for earlier in messages[:index]:
            size = len(json.dumps(earlier, ensure_ascii=False))
            by_role[earlier["role"]] = by_role.get(earlier["role"], 0) + size
        chars = sum(by_role.values())
        out.append(
            {
                "turn": len(out) + 1,
                "chars": chars,
                "by_role": by_role,
                "estimated_tokens": round(fit[0] + fit[1] * chars),
            }
        )
    return out


def fit_pilot(transcript: dict[str, Any]) -> tuple[float, float, float]:
    """Least-squares fit (a, b, largest residual) of the provider-reported input tokens
    of each turn against the characters before it."""
    messages: list[str] = []
    points = []
    for event in transcript["events"]:
        if event["type"] == "message_added":
            messages.append(json.dumps(event["message"], ensure_ascii=False))
        elif event["type"] == "token_usage":
            # the usage event follows the assistant message the call produced
            points.append((sum(len(m) for m in messages[:-1]), event["input_tokens"]))
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    b = sum((x - mx) * (y - my) for x, y in points) / sum(
        (x - mx) ** 2 for x, _ in points
    )
    a = my - b * mx
    residual = max(abs(y - (a + b * x)) for x, y in points)
    return a, b, residual
