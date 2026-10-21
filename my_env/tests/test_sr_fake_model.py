"""The system-response fake scenarios (environment.fake_model, task gb-2019-system-response).

Message shapes and scripts of ``reference``, ``repair``, ``no_submission`` and
``isolation_probe``; the tool probes of the isolation scenario sent through a local
episode on the shipped bundle (each refused, or answered without a fact block); the two
``run_python`` sandbox probes are only compiled here (isolation is enforced in the
container, where ``karotte`` runs them). The MVP scenarios are covered by
``test_grading_fake_model.py``; here only their separation from this task is checked.
End-to-end runs are in ``test_sr_fake_e2e.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from karotte import EvaluationRunConfig
from karotte.schemas import HttpMcpServerConfig
from sr_grading_support import catalogue

from environment import fake_model
from environment.incident.episode import (
    SYSTEM_RESPONSE_TOOL_NAMES,
    Episode,
    EpisodeConfig,
)
from environment.incident.paths import (
    SYSTEM_RESPONSE_BUNDLE_DIR,
    SYSTEM_RESPONSE_PRIVATE_DIR,
)
from environment.incident.submission import validate_submission

CONFIGS = Path(__file__).resolve().parents[1] / "configs"


def run_config(
    scenario: str | None, task_id: str = fake_model.SR_TASK_ID
) -> EvaluationRunConfig:
    return EvaluationRunConfig(
        run_id="t",
        task_id=task_id,
        model="fake",
        model_api_key="k",
        mcp_server_config=HttpMcpServerConfig(host="0.0.0.0", port=8080),
        transcript_file="transcript.json",
        extra_config=None if scenario is None else {"fake_scenario": scenario},
    )


def messages(scenario: str | None):
    return fake_model.get_messages(run_config(scenario))


def calls(msgs) -> list[tuple[str, dict]]:
    return [
        (tc.function.name, json.loads(tc.function.arguments))
        for m in msgs
        for tc in (m.tool_calls or [])
    ]


def submissions(msgs) -> list[dict]:
    return [
        args["submission"] for name, args in calls(msgs) if name == "submit_findings"
    ]


# -- every scenario ----------------------------------------------------------------------
@pytest.mark.parametrize("scenario", fake_model.SR_SCENARIOS)
def test_message_shape(scenario):
    msgs = messages(scenario)
    assert all(m.role == "assistant" for m in msgs)
    *turns, last = msgs
    for message in turns:
        assert message.tool_calls and len(message.tool_calls) == 1
        assert isinstance(message.content, str) and message.content.strip()
        assert message.tool_calls[0].function.name in SYSTEM_RESPONSE_TOOL_NAMES
    assert (
        isinstance(last.content, str) and last.content.strip() and not last.tool_calls
    )
    ids = [tc.id for m in turns for tc in m.tool_calls]
    assert len(ids) == len(set(ids))


def test_scenarios_and_default():
    assert fake_model.SR_SCENARIOS == (
        "reference",
        "repair",
        "no_submission",
        "isolation_probe",
    )
    assert calls(messages(None)) == calls(messages("reference"))


def test_unknown_scenario_is_an_error():
    with pytest.raises(
        ValueError, match="unknown fake_scenario 'nope' for gb-2019-system-response"
    ):
        messages("nope")


def test_dispatch_keeps_the_mvp_scenarios_separate():
    for scenario in ("reference", "repair", "no_submission", "isolation_probe"):
        mvp = calls(
            fake_model.get_messages(run_config(scenario, fake_model.GB_TASK_ID))
        )
        assert mvp == calls(fake_model.scenario_messages(scenario))
        assert mvp != calls(messages(scenario))
    mvp_ref = calls(
        fake_model.get_messages(run_config("reference", fake_model.GB_TASK_ID))
    )
    assert len(mvp_ref) == 8
    assert mvp_ref[-1][1]["submission"] == fake_model.reference_submission()
    assert fake_model.reference_submission() != fake_model.sr_reference_submission()


@pytest.mark.parametrize(
    "name,scenario",
    [
        ("sr_fake_run.json", "reference"),
        ("sr_fake_repair.json", "repair"),
        ("sr_fake_no_submission.json", "no_submission"),
        ("sr_fake_isolation_probe.json", "isolation_probe"),
    ],
)
def test_run_configs(name, scenario):
    raw = json.loads((CONFIGS / name).read_text(encoding="utf-8"))
    config = EvaluationRunConfig(**raw)
    assert config.task_id == fake_model.SR_TASK_ID and config.use_fake_model
    assert config.extra_config == {"fake_scenario": scenario}
    assert config.step_context_window_limit == 200_000
    assert config.transcript_file.startswith("out/sr/")
    assert fake_model.get_messages(config)


# -- reference -----------------------------------------------------------------------------
def test_reference_uses_every_tool_well_within_budget():
    sequence = calls(messages("reference"))
    names = [name for name, _ in sequence]
    assert set(names) == set(SYSTEM_RESPONSE_TOOL_NAMES)
    assert len(sequence) <= 60  # budget 150
    assert names[0] == "list_documents" and names[-1] == "submit_findings"
    assert names.count("submit_findings") == 1
    assert sequence[-1][1]["submission"] == fake_model.sr_reference_submission()
    codes = [args["code"] for name, args in sequence if name == "run_python"]
    assert codes == [
        fake_model.sr_reference_analysis_code(),
        fake_model.sr_reference_crosscheck_code(),
    ]
    # the frequency record is queried before the analysis that reads its CSV
    assert names.index("query_frequency") < names.index("run_python")
    described = [a for n, a in sequence if n == "request_document" and "party" in a]
    assert described and all("doc_id" not in a for a in described)


def test_reference_obtains_everything_it_cites(tmp_path: Path):
    """Every document the reference submission cites is obtained, and every record it
    cites (event, entry, response) is returned, by a call of the reference script (the
    Python runs and the submission are left out here; see test_sr_fake_e2e.py)."""
    from environment.incident import sr_grading

    episode = Episode(
        EpisodeConfig(
            episode_dir=tmp_path / "episode",
            evidence_dir=tmp_path / "evidence",
            scratch_dir=tmp_path / "scratch",
            bundle_dir=SYSTEM_RESPONSE_BUNDLE_DIR,
            max_tool_calls=150,
            tool_profile="system_response",
        )
    )
    episode.reset()
    for name, args in calls(messages("reference")):
        if name in ("run_python", "submit_findings"):
            continue
        result = episode.call(name, args)
        assert result.ok or result.error_code == "NOT_HELD", (
            name,
            args,
            result.envelope,
        )
    info = sr_grading.trace_info_from_episode(tmp_path / "episode")
    cited = [
        c
        for f in fake_model.sr_reference_submission()["findings"]
        for c in f["citations"]
    ]
    records = {
        c["locator"]
        for c in cited
        if c["locator"].split(":")[0] in ("event", "entry", "response")
    }
    documents = {c["evidence_id"] for c in cited if c["locator"] not in records}
    assert records <= set(info["records"]), sorted(records - set(info["records"]))
    for locator in records:
        evidence = next(c["evidence_id"] for c in cited if c["locator"] == locator)
        assert info["records"][locator]["evidence_id"] == evidence, locator
    assert documents <= set(info["retrieved"]), sorted(
        documents - set(info["retrieved"])
    )
    assert info["document_routes"]["S05"] == ["request_data_return"]
    assert info["document_routes"]["S06"] == ["request_data_return"]
    assert "query_frequency" in info["document_routes"]["R01"]


def test_reference_questions_each_match_one_fact_block():
    witnesses = catalogue().sources.witnesses
    asked = [a for n, a in calls(messages("reference")) if n == "interview_witness"]
    assert len(asked) == len(fake_model.SR_REFERENCE_QUESTIONS) == 20
    answered = set()
    for args in asked:
        card = witnesses[args["persona_id"]]
        match = card.interview(args["question"])
        assert match.kind == "match", args
        answered.add(card.blocks[match.blocks[0]].response_id)
    cited = {
        c["locator"].split(":", 1)[1]
        for f in fake_model.sr_reference_submission()["findings"]
        for c in f["citations"]
        if c["locator"].startswith("response:")
    }
    assert cited <= answered
    assert {p for p, _ in fake_model.SR_REFERENCE_QUESTIONS} == set(witnesses)


def test_reference_includes_defined_refusals():
    returns = catalogue().sources.data_returns
    asked = [a for n, a in calls(messages("reference")) if n == "request_data_return"]
    statuses = {
        (a["party"], a["data_type"]): returns.lookup(a["party"], a["data_type"]).status
        for a in asked
    }
    assert statuses[("METEOGROUP", "lightning_stroke_records")] == "not_held"
    assert statuses[("DNO", "real_time_distributed_generation_telemetry")] == "not_held"
    assert sorted(s for s in statuses.values() if s == "available") == ["available"] * 2


# -- repair and no_submission ------------------------------------------------------------
def test_repair_submits_invalid_record_locators_then_the_reference():
    msgs = messages("repair")
    first, second = submissions(msgs)
    result = validate_submission(first, catalogue())
    assert not result.ok
    index = {f["finding_id"]: i for i, f in enumerate(first["findings"])}
    assert {e["path"] for e in result.errors} == {
        f"findings[{index['F01']}].citations[1].locator",  # event: without an ID
        f"findings[{index['F12']}].citations[2].locator",  # unknown asset-log event
        f"findings[{index['F30']}].citations[2].locator",  # S07 entry under R08
        f"findings[{index['F40']}].citations[4].locator",  # a witness response by line
        "report.sections[0].body",  # [F99]
    }
    assert second == fake_model.sr_reference_submission()
    assert validate_submission(second, catalogue()).ok
    reference = calls(messages("reference"))
    assert calls(msgs)[: len(reference) - 1] == reference[:-1]


def test_no_submission_investigates_without_submitting():
    sequence = calls(messages("no_submission"))
    assert "submit_findings" not in [n for n, _ in sequence]
    assert sequence == calls(messages("reference"))[:-1]


# -- isolation probe -----------------------------------------------------------------------
def test_isolation_probe_shape():
    sequence = calls(messages("isolation_probe"))
    names = [name for name, _ in sequence]
    assert names[:2] == ["run_python", "run_python"]  # before any retrieval
    assert names[-2:] == ["run_python", "submit_findings"]
    n_probes = len(fake_model.SR_TOOL_PROBES)
    assert [(n, a) for n, a in sequence[2 : 2 + n_probes]] == [
        (tool, args) for tool, args, _ in fake_model.SR_TOOL_PROBES
    ]
    retrievals = sequence[2 + n_probes : -2]
    assert retrievals == list(fake_model.SR_PROBE_RETRIEVALS)
    for tool in (
        "request_document",
        "query_asset_log",
        "query_control_log",
        "interview_witness",
        "request_data_return",
        "query_frequency",
    ):
        assert tool in names, tool
    submission = sequence[-1][1]["submission"]
    assert submission == fake_model.INCONCLUSIVE_SUBMISSION


def test_tool_probes_cover_every_identifying_argument():
    probed = {
        (tool, name) for tool, args, _ in fake_model.SR_TOOL_PROBES for name in args
    }
    for pair in (
        ("request_document", "doc_id"),
        ("request_document", "party"),
        ("request_document", "description"),
        ("request_data_return", "party"),
        ("request_data_return", "data_type"),
        ("query_asset_log", "asset_id"),
        ("query_asset_log", "signal"),
        ("query_control_log", "room"),
        ("query_control_log", "cursor"),
        ("query_frequency", "start"),
        ("interview_witness", "persona_id"),
        ("interview_witness", "question"),
    ):
        assert pair in probed, pair
    injections = [
        a
        for t, a, o in fake_model.SR_TOOL_PROBES
        if t == "interview_witness" and o == "no_answer"
    ]
    assert len(injections) >= 4


def test_sandbox_probes_target_the_system_response_bundle():
    sequence = calls(messages("isolation_probe"))
    first, second, third = (
        sequence[0][1]["code"],
        sequence[1][1]["code"],
        sequence[-2][1]["code"],
    )
    for code, name in ((first, "probe1"), (second, "probe2"), (third, "probe3")):
        compile(code, name, "exec")
    assert str(SYSTEM_RESPONSE_BUNDLE_DIR) in first
    assert str(SYSTEM_RESPONSE_PRIVATE_DIR) in first
    for probe in (
        "read_bundle_manifest",
        "read_provenance",
        "read_sr_asset_log",
        "read_sr_control_log",
        "list_sr_control_logs",
        "read_sr_witness_card",
        "read_sr_rwe_witness_card",
        "read_sr_unlisted_document",
        "read_sr_data_return_S05",
        "read_sr_r05_calibration",
        "list_sr_private_dir",
        "read_sr_private_",
        "read_mvp_answer_key",
        "unmaterialised_evidence_",
        "network_connect_1.1.1.1_443",
        "network_connect_api.neso.energy_443",
        "network_udp_8.8.8.8_53",
        "dns_resolve",
        "write_bundle_dir",
    ):
        assert f'"{probe}' in first, probe
    for name in ("answer_key.json", "provenance_recon.json", "provenance_R05.json"):
        assert name in first
    assert '"background_process_killed"' in second
    for probe in (
        "materialised_only_obtained",
        "unrequested_data_return_S06_absent",
        "no_log_files_materialised",
        "no_witness_cards_materialised",
        "read_sr_bundle_S06_after_retrieval",
        "read_sr_private_after_retrieval",
        "write_obtained_document",
    ):
        assert f'"{probe}"' in third, probe
    assert json.dumps(list(fake_model.SR_PROBE_OBTAINED)) in third


def test_tool_probes_are_refused_without_leaks(tmp_path: Path):
    episode = Episode(
        EpisodeConfig(
            episode_dir=tmp_path / "episode",
            evidence_dir=tmp_path / "evidence",
            scratch_dir=tmp_path / "scratch",
            bundle_dir=SYSTEM_RESPONSE_BUNDLE_DIR,
            max_tool_calls=150,
            tool_profile="system_response",
        )
    )
    episode.reset()
    expected = {
        json.dumps([tool, args], sort_keys=True): outcome
        for tool, args, outcome in fake_model.SR_TOOL_PROBES
    }
    seen = 0
    for name, args in calls(messages("isolation_probe")):
        if name in ("run_python", "submit_findings"):
            continue
        key = json.dumps([name, args], sort_keys=True)
        if key not in expected:  # the legitimate retrievals
            assert (name, args) in fake_model.SR_PROBE_RETRIEVALS
            continue
        result = episode.call(name, args)
        env = result.envelope
        outcome = expected[key]
        seen += 1
        if outcome == "no_answer":
            assert env["error"] is None or env["error"]["code"] == "AMBIGUOUS_REQUEST"
            assert env["evidence_ids"] == []
            if env["ok"]:
                assert env["data"]["matched"] is False
        else:
            assert result.error_code == outcome, (name, args, env)
        body = result.text.split("\n\n", 1)[-1]
        asked = json.dumps(args)
        for leak in ('provenance":', '"quote"', "/private/", "answer_key", "pdf_page"):
            # an echo of the probe's own argument is not a leak
            assert leak not in body or leak in asked, (name, leak)
    assert seen == len(fake_model.SR_TOOL_PROBES)
    assert sorted(p.name for p in (tmp_path / "evidence").iterdir()) == []
