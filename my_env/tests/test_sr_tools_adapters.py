"""The nine Karotte tool adapters under the system-response profile (and the MVP one)."""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

import pytest
from incident_helpers import make_bundle, make_config
from karotte import ToolConfigWriter
from karotte import tool_base as karotte_tool_base
from karotte.mcp_servers.discover_tools import discover_tools
from sr_helpers import SR_TOOLS, make_sr_bundle, sr_config, sr_submission

from environment.incident.episode import read_state
from environment.tasks.gb_2019_electrical_disturbance import (
    IncidentToolConfig,
    make_episode,
)
from environment.tasks.gb_2019_system_response import SystemResponseToolConfig
from environment.tasks.gb_2019_system_response.prompt import (
    TOOL_DESCRIPTIONS,
    tool_description,
)

MVP_TOOLS = ("list_documents", "request_document", "run_python", "submit_findings")
NEW_TOOLS = tuple(t for t in SR_TOOLS if t not in MVP_TOOLS)
TEXT = {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}


def _write_configs(tmp_path: Path, monkeypatch, config) -> None:
    configs_dir = tmp_path / "tool_configs"
    monkeypatch.setattr(karotte_tool_base, "CONFIGS_DIR", configs_dir)
    writer = ToolConfigWriter(configs_dir)
    for name in SR_TOOLS:
        writer.write(name, config)
    make_episode(config).reset()


@pytest.fixture
def configured(tmp_path: Path, monkeypatch) -> SystemResponseToolConfig:
    bundle = make_sr_bundle(tmp_path / "src")
    config = SystemResponseToolConfig(**sr_config(tmp_path, bundle).model_dump())
    _write_configs(tmp_path, monkeypatch, config)
    return config


def _classes():
    modules = discover_tools(list(SR_TOOLS))
    return {name: getattr(modules[name], name) for name in SR_TOOLS}


def _server():
    from fastmcp import FastMCP

    server = FastMCP("sr-test")
    for name, cls in _classes().items():
        server.tool(cls().__call__, name=name)
    return server


def _listed(server):
    from fastmcp import Client

    async def go():
        async with Client(server) as client:
            return {t.name: t for t in await client.list_tools()}

    return asyncio.run(go())


def test_discover_tools_validates_all_nine_modules():
    modules = discover_tools(list(SR_TOOLS))
    assert sorted(modules) == sorted(SR_TOOLS)
    for name, module in modules.items():
        cls = getattr(module, name)
        assert cls.__name__ == name and cls.config_schema is IncidentToolConfig
        assert cls.__call__.__doc__
    for name in NEW_TOOLS:
        # class-level descriptions of the new tools are the profile's defaults
        assert _classes()[name].__call__.__doc__ == tool_description(name)


def test_profile_descriptions_and_schemas(configured):
    tools = _listed(_server())
    assert sorted(tools) == sorted(SR_TOOLS)
    for name, tool in tools.items():
        doc = " ".join(tool.description.split())
        assert tool.description == tool_description(name, configured)
        assert "of your 150 tool calls" in doc, name
        assert "argument name this tool does not accept" in doc, name
        assert "is not counted" in doc, name
        assert not tool.inputSchema.get("required"), name  # all optional
    props = {name: tool.inputSchema["properties"] for name, tool in tools.items()}
    assert props["request_document"] == {
        "doc_id": TEXT,
        "party": TEXT,
        "description": TEXT,
    }
    assert props["query_frequency"]["resolution_s"] == {
        "anyOf": [{"type": "number"}, {"type": "null"}],
        "default": None,
    }
    assert set(props["query_frequency"]) == {"start", "end", "resolution_s", "cursor"}
    assert set(props["query_asset_log"]) == {
        "asset_id",
        "start",
        "end",
        "signal",
        "cursor",
    }
    assert set(props["query_control_log"]) == {"room", "start", "end", "cursor"}
    assert set(props["interview_witness"]) == {"persona_id", "question"}
    assert set(props["request_data_return"]) == {"party", "data_type"}
    assert props["run_python"] == {"code": TEXT}


def test_configured_limits_reach_the_descriptions(tmp_path: Path, monkeypatch):
    bundle = make_sr_bundle(tmp_path / "src")
    config = SystemResponseToolConfig(
        **sr_config(
            tmp_path, bundle, max_tool_calls=40, log_page_size=25, python_timeout_s=12
        ).model_dump()
    )
    _write_configs(tmp_path, monkeypatch, config)
    tools = _listed(_server())
    assert "of your 40 tool calls" in tools["query_asset_log"].description
    assert "Up to 25 rows" in " ".join(tools["query_asset_log"].description.split())
    assert "at most 12 seconds" in " ".join(tools["run_python"].description.split())


def test_mvp_profile_is_untouched(tmp_path: Path, monkeypatch):
    bundle = make_bundle(tmp_path / "src")
    config = IncidentToolConfig(**make_config(tmp_path, bundle).model_dump())
    assert config.tool_profile == "mvp"
    _write_configs(tmp_path, monkeypatch, config)
    classes = _classes()
    for name in MVP_TOOLS:
        instance = classes[name]()
        assert "__call__" not in vars(instance), name  # the class method is registered
        assert "50 tool calls" in instance.__call__.__doc__
    tools = _listed(_server())
    assert tools["request_document"].inputSchema["properties"] == {"doc_id": TEXT}
    for name in MVP_TOOLS:
        doc = inspect.cleandoc(classes[name].__call__.__doc__)
        assert tools[name].description == doc, name


def test_descriptions_contain_no_incident_facts():
    for name in SR_TOOLS:
        text = tool_description(name)
        for leak in (
            "Hornsea",
            "Barford",
            "Eaton",
            "Wymondley",
            "lightning",
            "48.8",
            "931",
            "1878",
            "ESO",
            "HOWAO",
            "LFDD",
        ):
            assert leak not in text, (name, leak)
    assert set(TOOL_DESCRIPTIONS) == set(SR_TOOLS)


def test_mcp_round_trip_through_the_shared_ledger(configured):
    from fastmcp import Client

    server = _server()
    day = {"start": "2019-08-09T00:00:00Z", "end": "2019-08-10T00:00:00Z"}

    async def scenario():
        async with Client(server) as client:
            calls = [
                ("list_documents", {}),
                (
                    "request_document",
                    {"party": "System Operator", "description": "demand disconnection"},
                ),
                (
                    "query_frequency",
                    {
                        "start": "2019-08-09T16:52:30+01:00",
                        "end": "2019-08-09T16:52:33+01:00",
                        "resolution_s": 1,
                    },
                ),
                ("query_asset_log", {"asset_id": "ESW-400", **day}),
                ("query_control_log", {"room": "SO-CONTROL", **day}),
                (
                    "interview_witness",
                    {"persona_id": "so-engineer", "question": "demand restoration"},
                ),
                (
                    "request_data_return",
                    {"party": "Synthetic DNO A", "data_type": "relay returns"},
                ),
                (
                    "query_frequency",
                    {
                        "start": "2019-08-09T16:52:30+01:00",
                        "end": "x",
                        "resolution_s": "1",
                    },
                ),
                ("query_asset_log", {"asset_id": ["ESW-400"], **day}),
                (
                    "interview_witness",
                    {"persona_id": "so-engineer", "question": {"q": 1}},
                ),
                ("submit_findings", {"submission": sr_submission()}),
                ("query_control_log", {"room": "SO-CONTROL", **day}),
            ]
            return [await client.call_tool_mcp(name, args) for name, args in calls]

    results = asyncio.run(scenario())
    codes = [(r.structuredContent["error"] or {}).get("code", "OK") for r in results]
    assert codes == ["OK"] * 7 + ["INVALID_ARGUMENT"] * 3 + ["OK", "EPISODE_CLOSED"]
    for used, result in enumerate(results[:-1], 1):
        assert result.structuredContent["budget"]["tool_calls_used"] == used
        assert len(result.content) == 1 and result.content[0].type == "text"
    assert results[1].structuredContent["evidence_ids"] == ["R07"]
    assert results[-2].structuredContent["data"]["status"] == "accepted_and_frozen"
    state = read_state(configured.episode_dir)
    assert state.frozen and state.calls_used == 11


def test_unknown_argument_names_are_refused_before_the_ledger(configured):
    from fastmcp import Client

    server = _server()

    async def scenario():
        async with Client(server) as client:
            return [
                await client.call_tool_mcp("query_frequency", {"from": "x"}),
                await client.call_tool_mcp("interview_witness", {"persona": "x"}),
                await client.call_tool_mcp("query_control_log", {"room_id": "x"}),
            ]

    for result in asyncio.run(scenario()):
        assert result.isError and not result.structuredContent
    assert read_state(configured.episode_dir).calls_used == 0
