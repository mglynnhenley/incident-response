"""The four Karotte tool adapters: discovery, configuration, results and MCP schemas."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastmcp.tools.tool import ToolResult
from incident_helpers import make_bundle, make_config, valid_submission
from karotte import ToolConfigWriter
from karotte import tool_base as karotte_tool_base
from karotte.mcp_servers.discover_tools import discover_tools

from environment.incident.episode import read_state, read_trace
from environment.tasks.gb_2019_electrical_disturbance import (
    IncidentToolConfig,
    make_episode,
)

TOOLS = ["list_documents", "request_document", "run_python", "submit_findings"]


@pytest.fixture
def configured(tmp_path: Path, monkeypatch) -> IncidentToolConfig:
    configs_dir = tmp_path / "tool_configs"
    monkeypatch.setattr(karotte_tool_base, "CONFIGS_DIR", configs_dir)
    bundle = make_bundle(tmp_path / "src")
    config = IncidentToolConfig(**make_config(tmp_path, bundle).model_dump())
    writer = ToolConfigWriter(configs_dir)
    for name in TOOLS:
        writer.write(name, config)
    make_episode(config).reset()
    return config


def _tools():
    modules = discover_tools(TOOLS)
    return {name: getattr(modules[name], name) for name in TOOLS}


def test_discover_tools_validates_the_four_modules():
    modules = discover_tools(TOOLS)
    assert sorted(modules) == sorted(TOOLS)
    for name, module in modules.items():
        cls = getattr(module, name)
        assert cls.__name__ == name
        assert cls.config_schema is IncidentToolConfig
        assert "50 tool calls" in cls.__call__.__doc__


def test_tool_config_defaults_are_constructible():
    config = IncidentToolConfig()
    assert config.max_tool_calls == 50 and config.python_timeout_s == 30
    assert config.python_memory_bytes == 1 << 30 and config.max_output_chars == 20000
    assert config.exec_summary_word_limit == 600 and config.variant_id == "baseline"
    assert config.episode_dir.name == "episode"
    assert (
        config.evidence_dir.name == "evidence" and config.scratch_dir.name == "scratch"
    )


def test_adapters_load_their_written_config(configured):
    for cls in _tools().values():
        tool = cls()
        assert tool.config == configured
        assert tool._episode.isolated is False  # not containerized here


def test_adapters_share_one_ledger_and_return_tool_results(configured):
    tools = {name: cls() for name, cls in _tools().items()}

    async def scenario():
        listed = await tools["list_documents"](category=None, cursor=None)
        doc = await tools["request_document"](doc_id="R01")
        bad = await tools["request_document"](doc_id="nope")
        py = await tools["run_python"](
            code="import os\nprint(os.listdir(os.environ['EVIDENCE_DIR']))"
        )
        sub = await tools["submit_findings"](submission=valid_submission())
        closed = await tools["list_documents"]()
        return listed, doc, bad, py, sub, closed

    listed, doc, bad, py, sub, closed = asyncio.run(scenario())
    for result in (listed, doc, bad, py, sub, closed):
        assert isinstance(result, ToolResult)
        assert len(result.content) == 1 and result.content[0].type == "text"
        assert result.structured_content["request_id"].startswith("req-")
        assert result.is_error is (not result.structured_content["ok"])
    assert listed.structured_content["budget"]["tool_calls_used"] == 1
    assert doc.content[0].text.split("\n\n", 1)[1].startswith("--- R01 text")
    assert bad.structured_content["error"]["code"] == "UNKNOWN_ID" and bad.is_error
    assert py.structured_content["data"]["stdout"] == "['R01']\n"
    assert sub.structured_content["data"]["status"] == "accepted_and_frozen"
    assert closed.structured_content["error"]["code"] == "EPISODE_CLOSED"
    assert closed.structured_content["request_id"] == "req-006"


def test_submission_as_json_text(configured):
    tool = _tools()["submit_findings"]()
    result = asyncio.run(tool(submission=json.dumps(valid_submission())))
    assert result.structured_content["ok"]


def test_mcp_round_trip_and_optional_parameters(configured):
    from fastmcp import Client, FastMCP

    server = FastMCP("incident-test")
    for name, cls in _tools().items():
        server.tool(cls().__call__, name=name)

    async def scenario():
        async with Client(server) as client:
            listed = {t.name: t for t in await client.list_tools()}
            missing = await client.call_tool_mcp("request_document", {})
            ok = await client.call_tool_mcp("request_document", {"doc_id": "S04"})
            sub = await client.call_tool_mcp(
                "submit_findings", {"submission": valid_submission()}
            )
            return listed, missing, ok, sub

    listed, missing, ok, sub = asyncio.run(scenario())
    assert sorted(listed) == sorted(TOOLS)
    for tool in listed.values():
        assert not tool.inputSchema.get("required"), tool.name  # all optional
        assert tool.description
    assert set(listed["submit_findings"].inputSchema["properties"]) == {"submission"}
    # a missing argument reaches the ledger and is counted
    assert missing.structuredContent["error"]["code"] == "INVALID_ARGUMENT"
    assert missing.structuredContent["budget"]["tool_calls_used"] == 1
    assert missing.isError
    assert ok.content[0].text.startswith("{")
    assert ok.structuredContent["evidence_ids"] == ["S04"]
    assert sub.structuredContent["data"]["status"] == "accepted_and_frozen"


def _mcp_server():
    from fastmcp import FastMCP

    server = FastMCP("incident-test")
    for name, cls in _tools().items():
        server.tool(cls().__call__, name=name)
    return server


def test_mcp_schemas_are_unchanged_by_the_permissive_annotations(configured):
    from fastmcp import Client

    async def scenario():
        async with Client(_mcp_server()) as client:
            return {t.name: t.inputSchema for t in await client.list_tools()}

    schemas = asyncio.run(scenario())
    text = {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}
    assert schemas["request_document"] == {
        "additionalProperties": False,
        "properties": {"doc_id": text},
        "type": "object",
    }
    assert schemas["list_documents"]["properties"] == {"category": text, "cursor": text}
    assert schemas["run_python"]["properties"] == {"code": text}
    assert schemas["submit_findings"]["properties"]["submission"] == {
        "anyOf": [
            {"additionalProperties": True, "type": "object"},
            {"type": "string"},
            {"type": "null"},
        ],
        "default": None,
    }


def test_mcp_wrong_types_reach_the_ledger_and_are_counted(configured):
    from fastmcp import Client

    calls = [
        ("request_document", {"doc_id": 5}, "INVALID_ARGUMENT"),
        ("request_document", {"doc_id": ["R01"]}, "INVALID_ARGUMENT"),
        ("run_python", {"code": ["print(1)"]}, "INVALID_ARGUMENT"),
        ("list_documents", {"category": 3}, "INVALID_ARGUMENT"),
        ("list_documents", {"cursor": {"page": 2}}, "INVALID_ARGUMENT"),
        ("submit_findings", {"submission": [1, 2]}, "VALIDATION_FAILED"),
        ("submit_findings", {"submission": 5}, "VALIDATION_FAILED"),
    ]

    async def scenario():
        async with Client(_mcp_server()) as client:
            return [await client.call_tool_mcp(name, args) for name, args, _ in calls]

    results = asyncio.run(scenario())
    for used, ((name, _, code), result) in enumerate(zip(calls, results), 1):
        assert result.isError, name
        envelope = result.structuredContent
        assert envelope["error"]["code"] == code, (name, envelope)
        assert envelope["budget"]["tool_calls_used"] == used
        assert result.content[0].text.startswith("{")
    state = read_state(configured.episode_dir)
    assert state.calls_used == len(calls) and state.seq == len(calls)
    assert state.invalid_submission_attempts == 2
    trace = read_trace(configured.episode_dir)
    assert [r["args"] for r in trace][:2] == [{"doc_id": 5}, {"doc_id": ["R01"]}]


def test_mcp_unknown_argument_names_are_rejected_before_the_ledger(configured):
    """Documented limit: FastMCP refuses argument names a tool does not declare (tools
    cannot take **kwargs), so these calls are not counted or traced; the judge reports
    them as a ledger discrepancy and the prompt says so."""
    from fastmcp import Client

    async def scenario():
        async with Client(_mcp_server()) as client:
            return [
                await client.call_tool_mcp("request_document", {"id": "R01"}),
                await client.call_tool_mcp("run_python", {"source": "print(1)"}),
                await client.call_tool_mcp("submit_findings", {"findings": []}),
            ]

    for result in asyncio.run(scenario()):
        assert result.isError and not result.structuredContent
        assert "Unexpected keyword argument" in result.content[0].text
    state = read_state(configured.episode_dir)
    assert state.calls_used == 0 and state.seq == 0


def test_tool_descriptions_state_what_is_counted():
    for name, cls in _tools().items():
        doc = " ".join(cls.__call__.__doc__.split())
        assert "argument name this tool does not accept" in doc, name
        assert "is not counted" in doc, name
