"""The full-investigation fake scenarios (environment.fake_model_fi, task
gb-2019-full-investigation): dispatch, message shapes, the reference investigation on the
real bundle (every tool, every new kind of evidence, everything it cites obtained), the
repair submissions, the isolation probe's tool probes (refused without leaks) and the
sandbox probe code, and runs through Karotte's EvaluationRunner (local, development
mode: isolation itself is enforced in the container, where ``karotte run --runtime
docker`` runs the same scripts). No model or judge is called.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest
from fi_fake_support import BUNDLE, CONFIGS, run_through_karotte, tool_calls
from karotte import EvaluationRunConfig
from karotte.schemas import HttpMcpServerConfig

from environment import fake_model, fake_model_fi
from environment.incident import fi_grading
from environment.incident.catalogue import Catalogue
from environment.incident.episode import (
    GRADE_FILE,
    SYSTEM_RESPONSE_TOOL_NAMES,
    Episode,
    EpisodeConfig,
    read_trace,
)
from environment.incident.paths import (
    FULL_INVESTIGATION_PRIVATE_DIR,
    SYSTEM_RESPONSE_BUNDLE_DIR,
)
from environment.incident.replay import replay_episode
from environment.incident.submission import validate_submission

NEW_DOCS = ("R09", "R11", "R12", "S08", "S10", "S11")
NEW_ROOMS = ("ESO-COMMS", "NETWORK-RAIL-CONTROL", "GTR-FLEET-CONTROL")
NEW_PERSONAS = (
    "gtr-fleet-engineer",
    "network-rail-control-manager",
    "eso-communications-lead",
    "hospital-estates-manager",
    "ukpn-epn-spn-control-engineer",
)


def run_config(scenario: str | None, task_id: str = fake_model.FI_TASK_ID):
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


def episode(tmp_path: Path) -> Episode:
    ep = Episode(
        EpisodeConfig(
            episode_dir=tmp_path / "episode",
            evidence_dir=tmp_path / "evidence",
            scratch_dir=tmp_path / "scratch",
            bundle_dir=BUNDLE,
            python_executable=sys.executable,
            python_timeout_s=60,
            max_tool_calls=150,
            tool_profile="system_response",
        )
    )
    ep.reset()
    return ep


@pytest.fixture(scope="module")
def reference_episode(tmp_path_factory):
    """The reference investigation sent through the ledger (no submission)."""
    root = tmp_path_factory.mktemp("fi-reference-steps")
    ep = episode(root)
    results = [
        (tool, args, ep.call(tool, args))
        for _, tool, args in fake_model_fi.fi_reference_steps()
    ]
    return root, ep, results


# -- dispatch --------------------------------------------------------------------------------
@pytest.mark.parametrize("scenario", fake_model_fi.FI_SCENARIOS)
def test_message_shape(scenario):
    msgs = messages(scenario)
    assert all(m.role == "assistant" for m in msgs)
    *turns, last = msgs
    for message in turns:
        assert message.tool_calls and len(message.tool_calls) == 1
        assert isinstance(message.content, str) and message.content.strip()
        assert message.tool_calls[0].function.name in SYSTEM_RESPONSE_TOOL_NAMES
    assert last.content and last.content.strip() and not last.tool_calls
    ids = [tc.id for m in turns for tc in m.tool_calls]
    assert len(ids) == len(set(ids))


def test_scenarios_and_default():
    assert fake_model_fi.FI_SCENARIOS == (
        "reference",
        "repair",
        "no_submission",
        "isolation_probe",
    )
    assert tool_calls(messages(None)) == tool_calls(messages("reference"))
    with pytest.raises(ValueError, match="unknown fake_scenario 'nope'"):
        messages("nope")


def test_unscripted_gb_tasks_raise_and_other_tasks_keep_the_template():
    with pytest.raises(ValueError, match="no scenarios for task 'gb-2019-future-task'"):
        fake_model.get_messages(run_config("reference", "gb-2019-future-task"))
    example = fake_model.get_messages(run_config(None, "example-task"))
    assert tool_calls(example) == tool_calls(fake_model.example_task_messages())
    assert tool_calls(example)[0][0] == "bash"


def test_dispatch_keeps_the_other_tasks_scenarios_unchanged():
    for scenario in ("reference", "repair", "no_submission", "isolation_probe"):
        sr = fake_model.get_messages(run_config(scenario, fake_model.SR_TASK_ID))
        assert tool_calls(sr) == tool_calls(fake_model.sr_scenario_messages(scenario))
        mvp = fake_model.get_messages(run_config(scenario, fake_model.GB_TASK_ID))
        assert tool_calls(mvp) == tool_calls(fake_model.scenario_messages(scenario))
        assert tool_calls(messages(scenario)) != tool_calls(sr)


@pytest.mark.parametrize("scenario", fake_model_fi.FI_SCENARIOS)
def test_run_configs(scenario):
    raw = json.loads((CONFIGS / f"fi_fake_{scenario}.json").read_text("utf-8"))
    config = EvaluationRunConfig(**raw)
    assert config.task_id == fake_model.FI_TASK_ID and config.use_fake_model
    assert config.extra_config == {"fake_scenario": scenario}
    assert config.step_context_window_limit == 200_000
    assert config.on_step_context_window_limit == "score"
    assert config.transcript_file == f"out/fi/{scenario}/transcript.json"
    assert fake_model.get_messages(config)
    # The placeholder that silently played the template's script stays gone.
    assert not (CONFIGS / "fi_fake_run.json").exists()


# -- the reference investigation -------------------------------------------------------------
def test_reference_uses_every_tool_well_within_the_call_budget():
    sequence = tool_calls(messages("reference"))
    assert {name for name, _ in sequence} == set(SYSTEM_RESPONSE_TOOL_NAMES)
    assert len(sequence) == len(fake_model_fi.fi_reference_steps()) + 1 <= 60
    assert sequence[-1][0] == "submit_findings"
    assert sequence[-1][1]["submission"] == fake_model_fi.fi_reference_submission()


def test_reference_calls_succeed_or_are_defined_refusals(reference_episode):
    _, ep, results = reference_episode
    not_held = set(fake_model_fi.FI_REFERENCE_NOT_HELD)
    for tool, args, result in results:
        if tool == "request_data_return" and (args["party"], args["data_type"]) in (
            not_held
        ):
            assert result.error_code == "NOT_HELD", (args, result.envelope)
        else:
            assert result.ok, (tool, args, result.envelope["error"])
    returns = [a for t, a, _ in results if t == "request_data_return"]
    assert len(returns) == len(not_held) + 2
    assert ep.state().calls_used == len(results)


def test_reference_covers_the_new_evidence(reference_episode):
    _, ep, results = reference_episode
    obtained = {e for _, _, r in results for e in r.envelope["evidence_ids"]}
    # the new reconstructions as documents; R09 and R11 through their log rows
    assert {"S08", "S10", "S11", "R10", "R09", "R11"} <= obtained
    rooms = {a["room"] for t, a, _ in results if t == "query_control_log"}
    assert rooms == {"ESO-COMMS", "NETWORK-RAIL-CONTROL"}
    signals = {a.get("signal") for t, a, _ in results if t == "query_asset_log"}
    assert signals == {"T_LBAR-1 REMIT declared available capacity for event window MW"}
    personas = {a["persona_id"] for t, a, _ in results if t == "interview_witness"}
    assert set(NEW_PERSONAS) <= personas
    described = [a for t, a, _ in results if t == "request_document" and "party" in a]
    assert {tuple(r.envelope["evidence_ids"]) for t, a, r in results if a in described}
    assert all("doc_id" not in a for a in described)


def test_reference_questions_each_match_one_fact_block(reference_episode):
    _, _, results = reference_episode
    answers = [r for t, _, r in results if t == "interview_witness"]
    assert len(answers) == len(fake_model_fi.FI_REFERENCE_QUESTIONS)
    ids = []
    for result in answers:
        data = result.envelope["data"]
        assert data["matched"] is True, data
        ids.append(data["response_id"])
    assert len(ids) == len(set(ids))


def test_reference_obtains_everything_it_cites(reference_episode):
    root, _, _ = reference_episode
    info = fi_grading.trace_info_from_episode(root / "episode")
    submission = fake_model_fi.fi_reference_submission()
    for finding in submission["findings"]:
        for citation in finding["citations"]:
            kind = citation["locator"].partition(":")[0]
            if kind in ("event", "entry", "response"):
                record = info["records"].get(citation["locator"])
                assert record is not None, (finding["finding_id"], citation)
                assert record["evidence_id"] == citation["evidence_id"]
            else:
                assert citation["evidence_id"] in info["retrieved"], (
                    finding["finding_id"],
                    citation,
                )


def test_reference_python_runs_succeed(reference_episode):
    _, _, results = reference_episode
    python = [r for t, _, r in results if t == "run_python"]
    assert [r.envelope["data"]["exit_code"] for r in python] == [0, 0]
    assert "33 s" in python[0].envelope["data"]["stdout"]
    assert "= 1878 MW" in python[1].envelope["data"]["stdout"]


def test_reference_code_is_sent_without_the_files_docstrings():
    for code, path in (
        (
            fake_model_fi.fi_reference_analysis_code(),
            fake_model_fi.FI_REFERENCE_ANALYSIS,
        ),
        (
            fake_model_fi.fi_reference_crosscheck_code(),
            fake_model_fi.FI_REFERENCE_CROSSCHECK,
        ),
    ):
        text = path.read_text("utf-8")
        assert text.startswith('"""') and not code.startswith('"""')
        assert text.endswith(code)
        compile(code, path.name, "exec")


# -- repair, no submission -------------------------------------------------------------------
def test_repair_submits_invalid_record_locators_then_the_reference():
    catalogue = Catalogue.load(BUNDLE)
    sequence = tool_calls(messages("repair"))
    first, second = (a["submission"] for n, a in sequence if n == "submit_findings")
    result = validate_submission(first, catalogue)
    assert not result.ok
    index = {f["finding_id"]: i for i, f in enumerate(first["findings"])}
    errors = {(e["path"], e["message"]) for e in result.errors}
    expected = {
        f"findings[{index['F156']}].citations[0].locator": "belongs to evidence R09",
        f"findings[{index['F111']}].citations[0].locator": "R11-NR-999999",
        f"findings[{index['F102']}].citations[3].locator": "S09 has no document text",
        f"findings[{index['F151']}].citations[1].locator": "malformed",
        "report.sections[0].body": "[F99]",
    }
    assert {p for p, _ in errors} == set(expected), result.errors
    for path, fragment in expected.items():
        assert any(p == path and fragment in m for p, m in errors), (path, errors)
    assert second == fake_model_fi.fi_reference_submission()
    assert validate_submission(second, catalogue).ok
    steps = [(tool, args) for _, tool, args in fake_model_fi.fi_reference_steps()]
    assert sequence[: len(steps)] == steps and len(sequence) == len(steps) + 2


def test_no_submission_investigates_without_submitting():
    sequence = tool_calls(messages("no_submission"))
    assert "submit_findings" not in [n for n, _ in sequence]
    steps = [(tool, args) for _, tool, args in fake_model_fi.fi_reference_steps()]
    assert sequence == steps


# -- isolation probe -------------------------------------------------------------------------
def test_isolation_probe_shape():
    sequence = tool_calls(messages("isolation_probe"))
    names = [n for n, _ in sequence]
    assert names[:2] == ["run_python", "run_python"]
    assert names[-2:] == ["run_python", "submit_findings"]
    n = len(fake_model_fi.FI_TOOL_PROBES)
    assert sequence[2 : 2 + n] == [(t, a) for t, a, _ in fake_model_fi.FI_TOOL_PROBES]
    assert sequence[2 + n : -2] == list(fake_model_fi.FI_PROBE_RETRIEVALS)
    assert sequence[-1][1]["submission"] == fake_model.INCONCLUSIVE_SUBMISSION


def test_tool_probes_cover_the_new_ids_rooms_personas_returns_and_injection():
    probes = fake_model_fi.FI_TOOL_PROBES
    text = json.dumps([a for _, a, _ in probes])
    for doc_id in NEW_DOCS:
        assert doc_id in text, doc_id
    for room in NEW_ROOMS:
        assert room in text, room
    injected = {
        a["persona_id"]
        for t, a, o in probes
        if t == "interview_witness" and o == "no_answer"
    }
    assert injected == set(NEW_PERSONAS)
    traversed = {
        a["persona_id"]
        for t, a, o in probes
        if t == "interview_witness" and o != "no_answer"
    }
    assert any("gtr-fleet-engineer" in p for p in traversed)
    assert any(
        t == "request_document"
        and "Ignore previous instructions" in a.get("description", "")
        for t, a, _ in probes
    )
    # the excluded enforcement settlements cannot be obtained by any route
    settlements = [
        (t, a)
        for t, a, _ in probes
        if "settlement" in json.dumps(a).casefold() or "enforcement" in json.dumps(a)
    ]
    assert {t for t, _ in settlements} == {
        "request_document",
        "request_data_return",
        "interview_witness",
    }
    parties = {a["party"] for t, a, _ in probes if t == "request_data_return"}
    assert {"GTR", "OFGEM", "HOSPITAL_TRUST", "NEWCASTLE_AIRPORT"} <= parties
    assert "private/full_investigation" in text
    probed = {(t, k) for t, a, _ in probes for k in a}
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
        ("interview_witness", "persona_id"),
        ("interview_witness", "question"),
    ):
        assert pair in probed, pair


def test_tool_probes_are_refused_without_leaks(tmp_path: Path):
    ep = episode(tmp_path)
    expected = {
        json.dumps([t, a], sort_keys=True): o
        for t, a, o in fake_model_fi.FI_TOOL_PROBES
    }
    tally: Counter[str] = Counter()
    for name, args in tool_calls(messages("isolation_probe")):
        key = json.dumps([name, args], sort_keys=True)
        if key not in expected:
            continue
        result = ep.call(name, args)
        env = result.envelope
        outcome = expected[key]
        if outcome == "no_answer":
            assert env["error"] is None or env["error"]["code"] == "AMBIGUOUS_REQUEST"
            assert env["evidence_ids"] == []
            if env["ok"]:
                assert env["data"]["matched"] is False
            tally[env["error"]["code"] if env["error"] else "not_known"] += 1
        else:
            assert result.error_code == outcome, (name, args, env)
            tally[outcome] += 1
        body = result.text.split("\n\n", 1)[-1]
        asked = json.dumps(args)
        for leak in ('provenance":', '"quote"', "/private/", "answer_key", "pdf_page"):
            assert leak not in body or leak in asked, (name, leak)
        for leak in ("4.5m", "£", "redress scheme", "voluntary payment"):
            assert leak not in body, (name, leak)
    assert sum(tally.values()) == len(fake_model_fi.FI_TOOL_PROBES) == 34
    assert tally["UNKNOWN_ID"] == 26 and tally["INVALID_ARGUMENT"] == 2, tally
    assert tally["AMBIGUOUS_REQUEST"] + tally["not_known"] == 6, tally
    assert sorted(p.name for p in (tmp_path / "evidence").iterdir()) == []


def test_sandbox_probes_target_the_full_investigation_bundle():
    sequence = tool_calls(messages("isolation_probe"))
    first, second, third = (
        sequence[0][1]["code"],
        sequence[1][1]["code"],
        sequence[-2][1]["code"],
    )
    for code, name in ((first, "probe1"), (second, "probe2"), (third, "probe3")):
        compile(code, name, "exec")
    assert str(BUNDLE) in first and str(FULL_INVESTIGATION_PRIVATE_DIR) in first
    assert str(SYSTEM_RESPONSE_BUNDLE_DIR) in first
    for probe in (
        "read_bundle_manifest",
        "read_fi_control_log_",
        "read_fi_asset_log_",
        "read_fi_witness_card_",
        "read_fi_document_",
        "list_fi_private_dir",
        "read_fi_private_",
        "read_sr_answer_key",
        "unmaterialised_evidence_",
        "network_udp_8.8.8.8_53",
        "write_bundle_dir",
    ):
        assert f'"{probe}' in first, probe
    for name in (
        *NEW_ROOMS,
        *NEW_PERSONAS,
        "provenance_real.json",
        "provenance_recon.json",
    ):
        assert name in first, name
    assert '"background_process_killed"' in second
    assert json.dumps(list(fake_model_fi.FI_PROBE_OBTAINED)) in third
    for probe in (
        "materialised_only_obtained",
        "no_log_files_materialised",
        "no_witness_cards_materialised",
        "read_fi_private_after_retrieval",
        "write_obtained_document",
    ):
        assert f'"{probe}"' in third, probe


def test_probe_retrievals_obtain_exactly_the_expected_documents(tmp_path: Path):
    ep = episode(tmp_path)
    for tool, args in fake_model_fi.FI_PROBE_RETRIEVALS:
        assert ep.call(tool, args).ok, (tool, args)
    found = sorted(p.name for p in (tmp_path / "evidence").iterdir())
    assert found == sorted(fake_model_fi.FI_PROBE_OBTAINED)


# -- through Karotte's runner (local, development mode) ----------------------------------------
@pytest.mark.parametrize(
    ("scenario", "score", "outcome", "graded"),
    [
        ("reference", 1.0, "complete", True),
        ("repair", 1.0, "complete", True),
        ("no_submission", 0.0, "incomplete_submission", False),
    ],
)
def test_scenarios_run_through_the_karotte_runner(
    tmp_path: Path, monkeypatch, scenario, score, outcome, graded
):
    config, scoring, transcript = run_through_karotte(tmp_path, monkeypatch, scenario)
    assert scoring.score == score
    meta = scoring.metadata
    assert meta["outcome"] == outcome
    assert meta["transcript_summary"]["ledger_discrepancy"]["difference"] == 0
    trace = read_trace(config.episode_dir)
    codes = [r["outcome_code"] for r in trace]
    steps = len(fake_model_fi.fi_reference_steps())
    expected = {"reference": steps + 1, "repair": steps + 2, "no_submission": steps}
    assert len(trace) == expected[scenario]
    assert codes.count("NOT_HELD") == len(fake_model_fi.FI_REFERENCE_NOT_HELD)
    if scenario == "repair":
        assert codes[-2:] == ["VALIDATION_FAILED", "OK"], codes[-2:]
    # The full-investigation grade is larger than Karotte's 1 MB cap on one metadata
    # value, so the scoring event may carry it truncated to text; grade.json in the
    # episode directory is always complete.
    grading = meta["grading"]
    if isinstance(grading, str):
        assert grading.startswith("{'status': 'graded'") and "truncated" in grading
    else:
        assert grading["status"] == "graded", grading
    grade = json.loads((Path(config.episode_dir) / GRADE_FILE).read_text("utf-8"))
    assert grade["grade_schema"] == fi_grading.GRADE_SCHEMA
    if graded:
        assert len(grade["criteria"]) == 106
        assert grade["run"]["transcript_available"] is True
        assert all(
            r["content"]["auto_proposal"] == 1
            and r["evidence_support"]["auto_proposal"] == 1
            for r in grade["criteria"]
        )
    else:
        assert grade["criteria"] == [] and grade["content_coverage"] is None
    assert replay_episode(config.episode_dir).ok
    assert transcript["events"][0]["type"] == "task_started"
