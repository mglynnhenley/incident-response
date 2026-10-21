"""The scripted fake agent's scenarios (environment.fake_model)."""

from __future__ import annotations

import json

import pytest
from karotte import EvaluationRunConfig
from karotte.schemas import HttpMcpServerConfig

from environment import fake_model
from environment.incident.catalogue import Catalogue
from environment.incident.episode import TOOL_NAMES
from environment.incident.paths import DEFAULT_BUNDLE_DIR, DEFAULT_PRIVATE_DIR
from environment.incident.submission import validate_submission

CATALOGUE = Catalogue.load(DEFAULT_BUNDLE_DIR)


def config(scenario: str | None) -> EvaluationRunConfig:
    return EvaluationRunConfig(
        run_id="t",
        task_id="gb-2019-electrical-disturbance",
        model="fake",
        model_api_key="k",
        mcp_server_config=HttpMcpServerConfig(host="0.0.0.0", port=8080),
        transcript_file="transcript.json",
        extra_config=None if scenario is None else {"fake_scenario": scenario},
    )


def calls(messages) -> list[tuple[str, dict]]:
    return [
        (tc.function.name, json.loads(tc.function.arguments))
        for m in messages
        for tc in (m.tool_calls or [])
    ]


def has_text(message) -> bool:
    return isinstance(message.content, str) and bool(message.content.strip())


@pytest.mark.parametrize("scenario", fake_model.SCENARIOS)
def test_message_shape(scenario):
    messages = fake_model.get_messages(config(scenario))
    assert all(m.role == "assistant" for m in messages)
    *turns, last = messages
    for message in turns:
        assert message.tool_calls and len(message.tool_calls) == 1
        assert has_text(message)
        assert message.tool_calls[0].function.name in TOOL_NAMES
        json.loads(message.tool_calls[0].function.arguments)
    assert has_text(last) and not last.tool_calls
    ids = [tc.id for m in turns for tc in m.tool_calls]
    assert len(ids) == len(set(ids))


def test_default_is_reference():
    assert calls(fake_model.get_messages(config(None))) == calls(
        fake_model.get_messages(config("reference"))
    )


def test_unknown_scenario_is_an_error():
    with pytest.raises(ValueError, match="unknown fake_scenario"):
        fake_model.get_messages(config("nope"))


def test_reference_scenario():
    sequence = calls(fake_model.get_messages(config("reference")))
    assert [name for name, _ in sequence] == [
        "list_documents",
        "request_document",
        "request_document",
        "request_document",
        "request_document",
        "request_document",
        "run_python",
        "submit_findings",
    ]
    assert [
        args["doc_id"] for name, args in sequence if name == "request_document"
    ] == [
        "R01",
        "R03",
        "S01",
        "S03",
        "S04",
    ]
    assert sequence[6][1]["code"] == fake_model.REFERENCE_ANALYSIS.read_text()
    submission = sequence[7][1]["submission"]
    assert submission == fake_model.reference_submission()
    assert validate_submission(submission, CATALOGUE).ok


def test_repair_scenario_submits_invalid_then_valid():
    sequence = calls(fake_model.get_messages(config("repair")))
    submissions = [
        args["submission"] for name, args in sequence if name == "submit_findings"
    ]
    assert len(submissions) == 2
    first = validate_submission(submissions[0], CATALOGUE)
    assert not first.ok
    assert {e["path"] for e in first.errors} == {
        "report.sections[0].body",
        "findings[0].citations[0].locator",
    }
    assert validate_submission(submissions[1], CATALOGUE).ok


def test_no_submission_scenario():
    sequence = calls(fake_model.get_messages(config("no_submission")))
    assert "submit_findings" not in [name for name, _ in sequence]
    assert "run_python" in [name for name, _ in sequence]


def test_isolation_probe_scenario():
    sequence = calls(fake_model.get_messages(config("isolation_probe")))
    names = [name for name, _ in sequence]
    assert names == ["run_python", "run_python", "submit_findings"]
    assert "request_document" not in names  # probes run before any retrieval
    first, second = sequence[0][1]["code"], sequence[1][1]["code"]
    compile(first, "probe1", "exec")
    compile(second, "probe2", "exec")
    for probe in (
        "read_bundle_manifest",
        "read_answer_key",
        "read_provenance",
        "list_episode_dir",
        "list_tool_configs",
        "list_protected_store",
        "evidence_empty_before_retrieval",
        "network_connect_1.1.1.1_443",
        "dns_resolve",
        "write_evidence_root",
        "write_bundle_dir",
        "write_root_data",
    ):
        assert f'"{probe}"' in first, probe
    assert '"background_process_killed"' in second
    assert str(DEFAULT_BUNDLE_DIR) in first and str(DEFAULT_PRIVATE_DIR) in first
    submission = sequence[2][1]["submission"]
    result = validate_submission(submission, CATALOGUE)
    assert result.ok and result.submission.findings == []
    assert "inconclusive" in submission["report"]["executive_summary"].lower()
