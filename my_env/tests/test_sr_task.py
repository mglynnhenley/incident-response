"""Task gb-2019-system-response: discovery, instructions, hooks, judge and a full run.

Everything runs on the synthetic v2 bundle from ``sr_helpers``; the real
``bundles/system_response`` bundle is never loaded.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from incident_helpers import transcript_for
from karotte import EvaluationRunConfig, ProtectedStore, ToolConfigWriter
from karotte import evaluation_runner as runner_module
from karotte import tool_base as karotte_tool_base
from karotte.agents import FakeSource, MessageLoopAgent
from karotte.mcp_servers.mcp_server import McpServer
from karotte.schemas.chat import ChatCompletionMessageToolCall, Function, Message
from karotte.schemas.transcript import ScoringEvent, TaskCompletedEvent
from sr_helpers import SR_TOOLS, make_sr_bundle, sr_config, sr_submission

import environment
import environment.tasks.gb_2019_system_response as task_module
from environment.incident.catalogue import Catalogue, CatalogueError
from environment.incident.episode import Episode, read_state, read_trace
from environment.incident.paths import SYSTEM_RESPONSE_BUNDLE_DIR
from environment.incident.replay import replay_episode
from environment.tasks.gb_2019_system_response import (
    BRIEF,
    GB2019SystemResponseTask,
    SystemResponseStep,
    SystemResponseToolConfig,
)
from environment.tasks.gb_2019_system_response.judge import (
    GRADING_MODULE,
    SystemResponseJudge,
)
from environment.tasks.gb_2019_system_response.prompt import REPORT_EXPECTATIONS

CONTRACT_BRIEF = (
    "Investigate the electrical disturbance on 9 August 2019 and the power system's "
    "response, from the initiating event to the restoration of disconnected demand. "
    "Establish what happened and when, quantify the generation lost and the demand "
    "disconnected on the bases the records use, explain how frequency was contained "
    "and recovered, and distinguish supported explanations from unresolved causes. "
    "Support your findings with the available evidence."
)
TASK_ID = "gb-2019-system-response"


def _run_config(tmp_path: Path, **extra) -> EvaluationRunConfig:
    return EvaluationRunConfig(
        run_id="sr",
        task_id=TASK_ID,
        model="fake",
        use_fake_model=True,
        transcript_file=str(tmp_path / "out" / "transcript.json"),
        step_context_window_limit=200_000,
        on_step_context_window_limit="score",
        **extra,
    )


@pytest.fixture
def run_config(tmp_path: Path) -> EvaluationRunConfig:
    return _run_config(tmp_path)


@pytest.fixture
def config(tmp_path: Path) -> SystemResponseToolConfig:
    bundle = make_sr_bundle(tmp_path / "src")
    return SystemResponseToolConfig(**sr_config(tmp_path, bundle).model_dump())


@pytest.fixture
def task(run_config, config, monkeypatch) -> GB2019SystemResponseTask:
    monkeypatch.setattr(GB2019SystemResponseTask, "episode_config", lambda self: config)
    monkeypatch.setattr(
        SystemResponseStep, "episode_config", property(lambda self: config)
    )
    return GB2019SystemResponseTask(run_config)


def _instructions(run_config) -> str:
    return GB2019SystemResponseTask(run_config).steps[0].instructions


# -- discovery and shape -----------------------------------------------------------------
def test_task_is_discovered_once_alongside_the_mvp():
    ids = [cls.id for cls in environment.get_tasks()]
    assert ids.count(TASK_ID) == 1
    assert ids.count("gb-2019-electrical-disturbance") == 1


def test_task_shape(run_config):
    t = GB2019SystemResponseTask(run_config)
    assert t.id == TASK_ID and t.tools == list(SR_TOOLS)
    assert len(t.steps) == 1 and t.system_prompt


def test_default_configuration_points_at_the_v2_bundle():
    cfg = SystemResponseToolConfig()
    assert cfg.bundle_dir == SYSTEM_RESPONSE_BUNDLE_DIR
    assert cfg.max_tool_calls == 150 and cfg.tool_profile == "system_response"
    assert cfg.python_timeout_s == 30 and cfg.python_memory_bytes == 1 << 30
    assert cfg.frequency_page_size == 1000 and cfg.log_page_size == 200


def test_nothing_loads_the_bundle_without_a_hook(run_config, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("the bundle must not be loaded here")

    monkeypatch.setattr(Catalogue, "load", classmethod(refuse))
    t = GB2019SystemResponseTask(run_config)
    assert t.tools and t.steps[0].instructions and t.steps[0].judge


# -- instructions ---------------------------------------------------------------------------
def test_instructions_contain_the_contract_brief_verbatim(run_config):
    assert BRIEF == CONTRACT_BRIEF
    text = _instructions(run_config)
    assert CONTRACT_BRIEF in text
    for needle in [
        "STATUS",
        "real published data extracts",
        "digitised",
        "[modelled]",
        "index_time_utc",
        "At most 150 tool calls",
        "30 seconds",
        "1 GiB",
        "200,000 tokens",
        "80,000 tokens",
        "at most 600 words",
        "`L12` or `L12-L18`",
        "time:<ISO-8601",
        "rows:<a>-<b>",
        "`event:<event_id>`",
        "`entry:<entry_id>`",
        "`response:<response_id>`",
        "hypothesis",
        "first valid",
        "argument name the tool does not accept",
        "up to 1000 samples",
        "up to 200 per call",
    ]:
        assert needle in " ".join(text.split()) or needle in text, needle
    for tool in SR_TOOLS:
        assert f"`{tool}(" in text, tool


def test_report_expectations_cover_the_increment_topics(run_config):
    tagged = " ".join(tag for tag, _ in REPORT_EXPECTATIONS).split()
    for topic in (
        "T01",
        "T02",
        "T03",
        "T04",
        "T05",
        "T06",
        "T07",
        "T08",
        "T09",
        "T12",
        "T16",
        "T17",
    ):
        assert topic in tagged, topic
    for deferred in ("T10", "T11", "T13", "T14", "T15", "T18", "T19", "T20"):
        assert deferred not in tagged
    text = " ".join(_instructions(run_config).split())
    for _, item in REPORT_EXPECTATIONS:
        assert " ".join(item.split()) in text
    assert "T01" not in text  # builder tags are not shown to the agent


def test_instructions_leak_no_answers(run_config):
    text = _instructions(run_config)
    block = re.search(r"```json\n(.*?)\n```", text, re.S).group(1)
    skeleton = json.loads(block)
    assert skeleton["schema_version"] == "3.0" and skeleton["variant_id"] == "baseline"
    assert skeleton["findings"][0]["event_time"].startswith("<")
    for leak in [
        "48.7",
        "48.8",
        "49.0",
        "16:5",
        "15:5",
        "17:37",
        "737",
        "244",
        "1878",
        "1,878",
        "1990",
        "931",
        "892",
        "1000 MW",
        "Hornsea",
        "Barford",
        "Eaton",
        "Wymondley",
        "lightning",
        "MW",
        "ESO",
        "Ofgem",
        "RoCoF",
        "vector shift",
        "48.8",
        "5 %",
        "inertia of",
    ]:
        assert leak not in text, leak


# -- hooks ---------------------------------------------------------------------------------
def test_configure_tools_writes_the_profile_for_all_nine(task, tmp_path, monkeypatch):
    configs_dir = tmp_path / "tool_configs"
    monkeypatch.setattr(karotte_tool_base, "CONFIGS_DIR", configs_dir)
    task.configure_tools()
    files = sorted(p.name for p in configs_dir.glob("*.json"))
    assert files == sorted(f"{name}.json" for name in SR_TOOLS)
    for path in configs_dir.glob("*.json"):
        written = json.loads(path.read_text())
        assert written["tool_profile"] == "system_response"
        assert written["max_tool_calls"] == 150


def test_pre_hook_resets_and_reports(task, config):
    Episode(config).reset()
    Episode(config).list_documents()
    meta = task.pre_hook()
    assert meta["task_id"] == TASK_ID and meta["manifest_version"] == 2
    assert meta["tool_names"] == list(SR_TOOLS)
    assert meta["budgets"]["max_tool_calls"] == 150
    assert meta["budgets"]["output_token_budget"] == 80_000
    assert meta["budgets"]["context_cap_tokens"] == 200_000
    assert read_state(config.episode_dir).calls_used == 0


def test_pre_hook_fails_closed_on_a_tampered_bundle(task, config):
    log = Path(config.bundle_dir) / "logs" / "assets" / "ESW-400.jsonl"
    log.write_text(log.read_text().replace("Synthetic", "Altered"))
    with pytest.raises(CatalogueError, match="sha256 mismatch"):
        task.pre_hook()


def test_pre_hook_reports_key_metadata(task, monkeypatch, tmp_path):
    key = tmp_path / "answer_key.json"
    key.write_text(
        json.dumps({"version": "0.1.0", "review_status": "pending_domain_review"})
    )
    monkeypatch.setattr(task_module, "KEY_CANDIDATES", (tmp_path / "missing.json", key))
    meta = task.pre_hook()
    assert meta["key_version"] == "0.1.0"
    assert meta["review_status"] == "pending_domain_review"


# -- judge ---------------------------------------------------------------------------------
def test_complete_run_scores_one_and_grading_is_unavailable(
    config, run_config, monkeypatch
):
    monkeypatch.setitem(sys.modules, GRADING_MODULE, None)
    ep = Episode(config)
    ep.reset()
    calls = [
        (
            "query_frequency",
            {"start": "2019-08-09T16:52:00+01:00", "end": "2019-08-09T16:53:00+01:00"},
        ),
        (
            "interview_witness",
            {"persona_id": "so-engineer", "question": "demand restoration"},
        ),
        ("submit_findings", {"submission": sr_submission()}),
    ]
    transcript = transcript_for([(t, a, ep.call(t, a)) for t, a in calls])
    scoring = SystemResponseJudge(config, run_config).evaluate(transcript)
    assert scoring.score == 1.0 and scoring.metadata["outcome"] == "complete"
    summary = scoring.metadata["transcript_summary"]
    assert summary["tool_calls_episode_tools"] == 3
    assert summary["ledger_discrepancy"]["difference"] == 0
    assert summary["budgets"]["tool_calls_limit"] == 150
    assert scoring.metadata["grading"]["status"] in ("unavailable", "error")
    assert "Completion only" in scoring.metadata["score_semantics"]


def test_judge_uses_the_system_response_grader_only(config, run_config, monkeypatch):
    seen = {}

    def grade_episode(episode_dir, summary):
        seen["dir"] = Path(episode_dir)
        return {"grader": "sr", "outcome": summary["outcome"]}

    def mvp_grader(*args, **kwargs):
        raise AssertionError("the MVP grader must not grade this task")

    monkeypatch.setitem(
        sys.modules, GRADING_MODULE, types.SimpleNamespace(grade_episode=grade_episode)
    )
    monkeypatch.setitem(
        sys.modules,
        "environment.incident.grading",
        types.SimpleNamespace(grade_episode=mvp_grader),
    )
    ep = Episode(config)
    ep.reset()
    sub = ep.submit_findings(sr_submission())
    scoring = SystemResponseJudge(config, run_config).evaluate(
        transcript_for([("submit_findings", {"submission": sr_submission()}, sub)])
    )
    grading = scoring.metadata["grading"]
    assert grading["status"] == "graded" and grading["grade"]["grader"] == "sr"
    assert seen["dir"] == Path(config.episode_dir)
    assert (
        json.loads((Path(config.episode_dir) / "grade.json").read_text())["grader"]
        == "sr"
    )


def test_no_submission_is_incomplete(config, run_config, monkeypatch):
    monkeypatch.setitem(sys.modules, GRADING_MODULE, None)
    ep = Episode(config)
    ep.reset()
    result = ep.list_documents()
    scoring = SystemResponseJudge(config, run_config).evaluate(
        transcript_for([("list_documents", {}, result)])
    )
    assert scoring.score == 0.0
    assert scoring.metadata["incomplete_reason"] == "final_message_without_submission"


# -- a full run through Karotte -------------------------------------------------------------
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


def test_run_through_karotte_runner(tmp_path: Path, config, monkeypatch):
    configs_dir = tmp_path / "tool_configs"
    monkeypatch.setattr(karotte_tool_base, "CONFIGS_DIR", configs_dir)
    monkeypatch.setattr(
        runner_module, "ToolConfigWriter", lambda: ToolConfigWriter(configs_dir)
    )
    monkeypatch.setattr(
        runner_module, "ProtectedStore", lambda: ProtectedStore(tmp_path / "protected")
    )
    monkeypatch.setitem(sys.modules, GRADING_MODULE, None)
    monkeypatch.setattr(GB2019SystemResponseTask, "episode_config", lambda self: config)
    monkeypatch.setattr(
        SystemResponseStep, "episode_config", property(lambda self: config)
    )
    day = {"start": "2019-08-09T00:00:00Z", "end": "2019-08-10T00:00:00Z"}
    code = (
        "import os, pandas as pd\n"
        "df = pd.read_csv(os.path.join(os.environ['EVIDENCE_DIR'], 'R01', 'frequency.csv'))\n"
        "print(len(df), df['frequency_hz'].min())\n"
    )
    messages = [
        _call(1, "list_documents", {}),
        _call(
            2,
            "request_document",
            {"party": "System Operator", "description": "demand disconnection"},
        ),
        _call(
            3,
            "query_frequency",
            {"start": "2019-08-09T16:52:00+01:00", "end": "2019-08-09T16:54:00+01:00"},
        ),
        _call(4, "query_asset_log", {"asset_id": "ESW-400", **day}),
        _call(5, "query_control_log", {"room": "SO-CONTROL", **day}),
        _call(
            6,
            "interview_witness",
            {"persona_id": "so-engineer", "question": "How was demand restored?"},
        ),
        _call(
            7,
            "request_data_return",
            {"party": "Synthetic DNO A", "data_type": "relay returns"},
        ),
        _call(8, "run_python", {"code": code}),
        _call(9, "submit_findings", {"submission": sr_submission()}),
        Message(role="assistant", content="Submitted; ending my turn."),
    ]
    run_config = _run_config(
        tmp_path,
        save_artifacts=False,
        step_time_limit_seconds=600,
        on_step_time_limit="score",
    )
    task = GB2019SystemResponseTask(run_config)
    runner = runner_module.EvaluationRunner(run_config, task)
    runner._agent = MessageLoopAgent(FakeSource(messages))
    mcp = McpServer("sr-integration")

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
    assert completed and completed[-1].status == "passed", [
        getattr(e, "message", "") for e in events if type(e).__name__ == "ErrorEvent"
    ]
    scoring = [e for e in events if isinstance(e, ScoringEvent)][0].scoring
    assert scoring.score == 1.0
    summary = scoring.metadata["transcript_summary"]
    assert summary["tool_calls_episode_tools"] == 9
    assert summary["ledger_discrepancy"]["difference"] == 0

    trace = read_trace(config.episode_dir)
    assert [r["outcome_code"] for r in trace] == ["OK"] * 9
    assert trace[7]["python"]["stdout"].startswith("1500 ")
    tool_messages = [m for m in runner.transcript.messages if m.role == "tool"]
    for message, record in zip(tool_messages, trace, strict=True):
        text = message.content[0]["text"]
        assert (
            record["rendered_text_sha256"] == hashlib.sha256(text.encode()).hexdigest()
        )

    registered = {t["function"]["name"]: t["function"] for t in runner.tools}
    assert sorted(registered) == sorted(SR_TOOLS)
    assert set(registered["request_document"]["parameters"]["properties"]) == {
        "doc_id",
        "party",
        "description",
    }
    assert "of your 150 tool calls" in registered["list_documents"]["description"]
    assert replay_episode(config.episode_dir).ok


def test_output_budget_is_task_specific():
    """The widened task allows 80k output tokens; the frozen MVP keeps 30k."""
    from environment.incident.episode import (
        OUTPUT_TOKEN_BUDGET,
        SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET,
        EpisodeConfig,
    )
    from environment.tasks.gb_2019_electrical_disturbance.judge import EpisodeJudge
    from environment.tasks.gb_2019_system_response.judge import SystemResponseJudge

    cfg = EpisodeConfig(
        episode_dir="/tmp/e", evidence_dir="/tmp/v", scratch_dir="/tmp/s"
    )
    assert OUTPUT_TOKEN_BUDGET == 30_000
    assert SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET == 80_000
    assert EpisodeJudge(cfg).output_token_budget == 30_000
    assert SystemResponseJudge(cfg).output_token_budget == 80_000
