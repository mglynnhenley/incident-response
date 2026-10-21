"""The Karotte task: discovery, instructions, hooks, and EpisodeJudge outcomes."""

from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path

import pytest
from incident_helpers import make_bundle, make_config, transcript_for, valid_submission
from karotte import EvaluationRunConfig
from karotte import tool_base as karotte_tool_base

import environment
import environment.tasks.gb_2019_electrical_disturbance as task_module
from environment.incident.episode import Episode
from environment.tasks.gb_2019_electrical_disturbance import (
    BRIEF,
    GB2019ElectricalDisturbanceTask,
    IncidentToolConfig,
)
from environment.tasks.gb_2019_electrical_disturbance.judge import EpisodeJudge
from environment.tasks.gb_2019_electrical_disturbance.prompt import build_instructions

PLAN_BRIEF = (
    "Investigate the electrical disturbance on 9 August 2019. Establish the initiating "
    "event, reconstruct the generation-trip and frequency sequence, and distinguish "
    "supported explanations from unresolved causes. Support your findings with the "
    "available evidence."
)


@pytest.fixture
def run_config(tmp_path: Path) -> EvaluationRunConfig:
    return EvaluationRunConfig(
        run_id="t",
        task_id="gb-2019-electrical-disturbance",
        model="fake",
        use_fake_model=True,
        transcript_file=str(tmp_path / "out" / "transcript.json"),
        step_context_window_limit=200_000,
        on_step_context_window_limit="score",
    )


@pytest.fixture
def config(tmp_path: Path) -> IncidentToolConfig:
    bundle = make_bundle(tmp_path / "src")
    return IncidentToolConfig(**make_config(tmp_path, bundle).model_dump())


@pytest.fixture
def task(run_config, config, monkeypatch) -> GB2019ElectricalDisturbanceTask:
    t = GB2019ElectricalDisturbanceTask(run_config)
    monkeypatch.setattr(
        GB2019ElectricalDisturbanceTask, "episode_config", lambda self: config
    )
    monkeypatch.setattr(
        task_module.InvestigationStep, "episode_config", property(lambda self: config)
    )
    return t


def test_task_is_discovered():
    ids = [cls.id for cls in environment.get_tasks()]
    assert "gb-2019-electrical-disturbance" in ids
    assert "example-task" in ids


def test_task_shape(run_config):
    t = GB2019ElectricalDisturbanceTask(run_config)
    assert t.id == "gb-2019-electrical-disturbance"
    assert t.tools == [
        "list_documents",
        "request_document",
        "run_python",
        "submit_findings",
    ]
    assert len(t.steps) == 1
    assert t.system_prompt


def test_instructions_contain_the_plan_brief_verbatim(run_config):
    assert BRIEF == PLAN_BRIEF
    text = GB2019ElectricalDisturbanceTask(run_config).steps[0].instructions
    assert PLAN_BRIEF in text
    for needle in [
        "reconstructions",
        "STATUS",
        "list_documents",
        "request_document",
        "run_python",
        "submit_findings",
        "At most 50 tool calls",
        "30 seconds",
        "1 GiB",
        "200,000 tokens",
        "30,000 tokens",
        "at most 600 words",
        "`L12` or `L12-L18`",
        "time:<ISO-8601",
        "rows:<a>-<b>",
        "hypothesis",
        "first valid",
    ]:
        assert needle in text, needle


def test_skeleton_is_valid_json_without_answers(run_config):
    text = GB2019ElectricalDisturbanceTask(run_config).steps[0].instructions
    block = re.search(r"```json\n(.*?)\n```", text, re.S).group(1)
    skeleton = json.loads(block)
    assert skeleton["schema_version"] == "3.0" and skeleton["variant_id"] == "baseline"
    finding = skeleton["findings"][0]
    assert finding["quantity"]["value"] == 0
    assert finding["event_time"].startswith("<")
    # no incident facts, sites, times or quantities leak through the prompt
    for leak in [
        "48.7",
        "49.0",
        "16:5",
        "15:5",
        "737",
        "244",
        "Hornsea",
        "Barford",
        "Eaton",
        "Wymondley",
        "lightning",
        "MW",
    ]:
        assert leak not in text, leak


def test_instructions_list_report_expectations_without_answers(run_config):
    text = " ".join(
        GB2019ElectricalDisturbanceTask(run_config).steps[0].instructions.split()
    )
    start = text.index("# Report expectations")
    assert text.index(PLAN_BRIEF) < start < text.index("# Evidence")
    section = text[start : text.index("# Evidence")]
    for needle in [
        "initiating event",
        "how it was cleared",
        "whether the protection performed as required",
        "chronology",
        "clock basis",
        "the clock that record uses",
        "any conversion you applied",
        "loss of generation",
        "megawatts",
        "timing",
        "measured frequency record",
        "each minimum",
        "recovery to 50 Hz",
        "time below 49 Hz",
        "how you computed",
        "sampling",
        "mechanism that is established",
        "remains unexplained",
        "status",
    ]:
        assert needle in section, needle
    # the threshold convention is the agent's choice: no counting rule is given
    for convention in [
        "strictly",
        "at or below",
        "or equal",
        "zero-order",
        "hold",
        "interpolat",
        "inclusive",
        "count",
    ]:
        assert convention not in section, convention
    for convention in ["strictly", "at or below", "zero-order", "interpolat"]:
        assert convention not in text, convention
    # deliverables only: no clocks, requirements, sites, causes or values of the answer
    for answer in [
        "UTC + 1",
        "UTC+1",
        "+01:00",
        "BST",
        "datum",
        "80 ms",
        "as designed",
        "lightning",
        "Hornsea",
        "Little Barford",
        "Wymondley",
        "Eaton Socon",
    ]:
        assert answer not in section, answer
    assert not re.search(r"\bms\b", section)
    assert not re.search(r"\d", section.replace("50 Hz", "").replace("49 Hz", ""))


def test_instructions_follow_budgets():
    text = build_instructions(
        max_tool_calls=12, python_timeout_s=5, exec_summary_word_limit=99
    )
    assert (
        "At most 12 tool calls" in text
        and "5 seconds" in text
        and "at most 99 words" in text
    )


def test_configure_tools_writes_one_config_per_tool(
    task, config, tmp_path, monkeypatch
):
    configs_dir = tmp_path / "tool_configs"
    monkeypatch.setattr(karotte_tool_base, "CONFIGS_DIR", configs_dir)
    task.configure_tools()
    files = sorted(p.name for p in configs_dir.glob("*.json"))
    assert files == [
        "list_documents.json",
        "request_document.json",
        "run_python.json",
        "submit_findings.json",
    ]
    for path in configs_dir.glob("*.json"):
        assert IncidentToolConfig.model_validate_json(path.read_text()) == config


def test_pre_hook_resets_and_reports_metadata(task, config):
    config.scratch_dir.mkdir(parents=True, exist_ok=True)
    (config.scratch_dir / "old.txt").write_text("stale")
    meta = task.pre_hook()
    assert meta["task_id"] == "gb-2019-electrical-disturbance"
    assert meta["bundle_version"] == "1.0.0-test" and len(meta["bundle_sha256"]) == 64
    assert meta["budgets"]["max_tool_calls"] == 50
    assert meta["budgets"]["output_token_budget"] == 30_000
    assert meta["budgets"]["context_cap_tokens"] == 200_000
    assert not (config.scratch_dir / "old.txt").exists()
    assert (config.episode_dir / "state.json").exists()
    json.dumps(meta)  # serialisable for the transcript


def test_pre_scoring_hook_saves_the_episode(task, config, monkeypatch):
    saved, killed = [], []
    monkeypatch.setattr(
        task_module, "save_artifact", lambda cfg, path: saved.append(path)
    )
    monkeypatch.setattr(task_module, "kill_processes", lambda uid: killed.append(uid))
    task.pre_hook()
    task.steps[0].pre_scoring_hook()
    assert saved == [config.episode_dir]
    assert killed == []  # not containerized here


# -- judge -------------------------------------------------------------------------
@pytest.fixture
def episode(config) -> Episode:
    ep = Episode(config)
    ep.reset()
    return ep


@pytest.fixture(autouse=True)
def no_grading(monkeypatch):
    """Judge tests default to 'grading not installed' unless they install a fake."""
    monkeypatch.setitem(sys.modules, "environment.incident.grading", None)


def _judge(config, run_config, **kwargs) -> EpisodeJudge:
    return EpisodeJudge(config, run_config, **kwargs)


def test_complete_run_scores_one(episode, config, run_config):
    calls = [
        ("list_documents", {}, episode.list_documents()),
        ("request_document", {"doc_id": "R03"}, episode.request_document("R03")),
        (
            "submit_findings",
            {"submission": valid_submission()},
            episode.submit_findings(valid_submission()),
        ),
    ]
    scoring = _judge(config, run_config).evaluate(transcript_for(calls))
    assert scoring.score == 1.0 and scoring.continue_task
    meta = scoring.metadata
    assert meta["outcome"] == "complete" and meta["incomplete_reason"] is None
    assert "NOT a quality score" in meta["score_semantics"]
    summary = meta["transcript_summary"]
    assert summary["tool_calls_episode_tools"] == 3
    assert summary["ledger_discrepancy"]["difference"] == 0
    assert summary["output_tokens_total"] == 400
    assert summary["output_tokens_before_freeze"] == 300
    assert summary["last_input_tokens"] == 1000
    assert summary["submission_valid"] is True
    assert meta["grading"]["status"] == "unavailable"


def test_final_message_without_submission(episode, config, run_config):
    calls = [("list_documents", {}, episode.list_documents())]
    scoring = _judge(config, run_config).evaluate(
        transcript_for(calls, final_text="I am done.")
    )
    assert scoring.score == 0.0 and not scoring.continue_task
    assert scoring.metadata["outcome"] == "incomplete_submission"
    assert scoring.metadata["incomplete_reason"] == "final_message_without_submission"
    assert (
        scoring.metadata["transcript_summary"]["final_message_excerpt"] == "I am done."
    )


def test_invalid_submission_only_is_incomplete(episode, config, run_config):
    bad = valid_submission(schema_version="2.0")
    calls = [("submit_findings", {"submission": bad}, episode.submit_findings(bad))]
    scoring = _judge(config, run_config).evaluate(transcript_for(calls))
    assert scoring.score == 0.0
    assert scoring.metadata["incomplete_reason"] == "final_message_without_submission"


def test_tool_budget_exhausted(tmp_path, run_config):
    config = IncidentToolConfig(
        **make_config(
            tmp_path, make_bundle(tmp_path / "b"), max_tool_calls=2
        ).model_dump()
    )
    ep = Episode(config)
    ep.reset()
    calls = [
        ("list_documents", {}, ep.list_documents()),
        ("list_documents", {}, ep.list_documents()),
        ("list_documents", {}, ep.list_documents()),  # BUDGET_EXCEEDED
    ]
    scoring = _judge(config, run_config).evaluate(
        transcript_for(calls, final_text="Out of calls.")
    )
    assert scoring.score == 0.0
    assert scoring.metadata["incomplete_reason"] == "tool_budget_exhausted"
    assert scoring.metadata["incomplete_reasons"] == [
        "tool_budget_exhausted",
        "final_message_without_submission",
    ]


def test_context_cap_reached(episode, config, run_config):
    calls = [
        ("list_documents", {}, episode.list_documents()),
        ("request_document", {"doc_id": "R01"}, episode.request_document("R01")),
    ]
    transcript = transcript_for(
        calls, final_text=None, usage=[(150_000, 50), (200_500, 50)]
    )
    scoring = _judge(config, run_config).evaluate(transcript)
    assert scoring.metadata["incomplete_reason"] == "context_cap_reached"
    assert scoring.metadata["transcript_summary"]["context_cap_reached"] is True


def test_time_limit(episode, config, run_config):
    calls = [("list_documents", {}, episode.list_documents())]
    scoring = _judge(config, run_config).evaluate(
        transcript_for(calls, final_text=None)
    )
    assert scoring.metadata["incomplete_reason"] == "time_limit"


def test_output_token_budget_before_submission(episode, config, run_config):
    calls = [
        ("list_documents", {}, episode.list_documents()),
        (
            "submit_findings",
            {"submission": valid_submission()},
            episode.submit_findings(valid_submission()),
        ),
    ]
    transcript = transcript_for(
        calls, usage=[(1000, 29_000), (2000, 2_000), (2100, 10)]
    )
    scoring = _judge(config, run_config).evaluate(transcript)
    assert scoring.score == 0.0
    assert scoring.metadata["incomplete_reason"] == "output_token_budget_exhausted"
    assert (
        scoring.metadata["transcript_summary"]["output_tokens_before_freeze"] == 31_000
    )


def test_output_tokens_after_submission_do_not_matter(episode, config, run_config):
    calls = [
        (
            "submit_findings",
            {"submission": valid_submission()},
            episode.submit_findings(valid_submission()),
        ),
    ]
    transcript = transcript_for(calls, usage=[(1000, 500), (1200, 40_000)])
    scoring = _judge(config, run_config).evaluate(transcript)
    assert scoring.score == 1.0
    assert (
        scoring.metadata["transcript_summary"]["output_token_budget_exceeded"] is True
    )


def test_tampered_submission_is_not_complete(episode, config, run_config):
    calls = [
        (
            "submit_findings",
            {"submission": valid_submission()},
            episode.submit_findings(valid_submission()),
        ),
    ]
    episode.submission_path.write_text("{}")
    scoring = _judge(config, run_config).evaluate(transcript_for(calls))
    assert scoring.score == 0.0
    assert scoring.metadata["transcript_summary"]["submission_valid"] is False


def test_ledger_discrepancy_is_reported(episode, config, run_config):
    calls = [
        ("list_documents", {}, episode.list_documents()),
        ("request_document", {"doc_id": 5}, None),  # rejected before the ledger
        (
            "submit_findings",
            {"submission": valid_submission()},
            episode.submit_findings(valid_submission()),
        ),
    ]
    scoring = _judge(config, run_config).evaluate(transcript_for(calls))
    discrepancy = scoring.metadata["transcript_summary"]["ledger_discrepancy"]
    assert discrepancy == {
        "transcript_tool_calls": 3,
        "ledger_recorded_calls": 2,
        "difference": 1,
        "note": discrepancy["note"],
    }
    assert scoring.score == 1.0


def test_grading_hook_writes_grade_json(episode, config, run_config, monkeypatch):
    seen = {}
    fake = types.ModuleType("environment.incident.grading")

    def grade_episode(episode_dir, summary):
        seen["summary"] = summary
        return {
            "provisional": True,
            "content_coverage": {},
            "episode": str(episode_dir),
        }

    fake.grade_episode = grade_episode
    monkeypatch.setitem(sys.modules, "environment.incident.grading", fake)
    saved = []
    monkeypatch.setattr(
        "environment.tasks.gb_2019_electrical_disturbance.judge.save_artifact",
        lambda cfg, path: saved.append(path),
    )
    calls = [
        (
            "submit_findings",
            {"submission": valid_submission()},
            episode.submit_findings(valid_submission()),
        )
    ]
    scoring = _judge(config, run_config).evaluate(transcript_for(calls))
    grading = scoring.metadata["grading"]
    assert grading["status"] == "graded" and grading["grade"]["provisional"] is True
    grade_file = config.episode_dir / "grade.json"
    assert json.loads(grade_file.read_text())["content_coverage"] == {}
    assert saved == [grade_file]
    assert seen["summary"]["outcome"] == "complete"
    assert scoring.score == 1.0


def test_grading_errors_do_not_break_the_judge(
    episode, config, run_config, monkeypatch
):
    fake = types.ModuleType("environment.incident.grading")

    def broken(episode_dir, summary):
        raise ValueError("key not reviewed")

    fake.grade_episode = broken
    monkeypatch.setitem(sys.modules, "environment.incident.grading", fake)
    calls = [("list_documents", {}, episode.list_documents())]
    scoring = _judge(config, run_config).evaluate(transcript_for(calls))
    assert scoring.metadata["grading"] == {
        "status": "error",
        "error": "ValueError: key not reviewed",
    }
    assert scoring.score == 0.0


# -- robustness of the judge and hooks ------------------------------------------------
class _RaisingFinder:
    """Makes ``environment.incident.grading`` fail while it is being imported."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def find_spec(self, name, path=None, target=None):
        import importlib.util

        if name != "environment.incident.grading":
            return None
        return importlib.util.spec_from_loader(name, self)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        raise self.error


@pytest.mark.parametrize(
    "error",
    [
        ValueError("bad answer key"),
        SyntaxError("invalid syntax"),
        ImportError(
            "cannot import name 'missing' from 'environment.incident.frequency'"
        ),
        ModuleNotFoundError("No module named 'scipy'", name="scipy"),
    ],
)
def test_grading_import_errors_do_not_break_the_judge(
    episode, config, run_config, monkeypatch, error
):
    monkeypatch.delitem(sys.modules, "environment.incident.grading", raising=False)
    monkeypatch.setattr(sys, "meta_path", [_RaisingFinder(error), *sys.meta_path])
    calls = [
        (
            "submit_findings",
            {"submission": valid_submission()},
            episode.submit_findings(valid_submission()),
        )
    ]
    scoring = _judge(config, run_config).evaluate(transcript_for(calls))
    assert scoring.metadata["grading"] == {
        "status": "error",
        "error": f"{type(error).__name__}: {error}",
    }
    assert scoring.score == 1.0 and scoring.metadata["outcome"] == "complete"


def test_grading_results_are_stored_as_plain_json(
    episode, config, run_config, monkeypatch
):
    fake = types.ModuleType("environment.incident.grading")
    fake.grade_episode = lambda episode_dir, summary: {"path": Path("x"), "n": {1, 2}}
    monkeypatch.setitem(sys.modules, "environment.incident.grading", fake)
    monkeypatch.setattr(
        "environment.tasks.gb_2019_electrical_disturbance.judge.save_artifact",
        lambda cfg, path: None,
    )
    calls = [("list_documents", {}, episode.list_documents())]
    grading = _judge(config, run_config).evaluate(transcript_for(calls)).metadata
    assert grading["grading"]["grade"] == {"path": "x", "n": "{1, 2}"}
    json.dumps(grading)


def test_pre_scoring_hook_saves_the_episode_when_the_kill_fails(
    task, config, monkeypatch
):
    from karotte import UnreapableCohortError

    saved = []

    def unreapable(uid):
        raise UnreapableCohortError("processes were still alive")

    monkeypatch.setattr(task_module, "is_containerized", lambda: True)
    monkeypatch.setattr(task_module, "kill_processes", unreapable)
    monkeypatch.setattr(
        task_module, "save_artifact", lambda cfg, path: saved.append(path)
    )
    task.pre_hook()
    step = task.steps[0]
    with pytest.raises(UnreapableCohortError):
        step.pre_scoring_hook()
    assert saved == [config.episode_dir]
    # Karotte scores the misbehaviour as 0 (and the episode is still saved)
    scoring = step.score(transcript_for([]), 0)
    assert scoring.score == 0.0 and "still alive" in scoring.metadata["misbehavior"]
    assert saved == [config.episode_dir, config.episode_dir]


def test_pre_scoring_hook_kill_error_wins_over_a_save_error(task, monkeypatch):
    from karotte import UnreapableCohortError

    def unreapable(uid):
        raise UnreapableCohortError("still alive")

    def broken_save(cfg, path):
        raise OSError("disk full")

    monkeypatch.setattr(task_module, "is_containerized", lambda: True)
    monkeypatch.setattr(task_module, "kill_processes", unreapable)
    monkeypatch.setattr(task_module, "save_artifact", broken_save)
    with pytest.raises(UnreapableCohortError):
        task.steps[0].pre_scoring_hook()
    monkeypatch.setattr(task_module, "kill_processes", lambda uid: None)
    with pytest.raises(OSError, match="disk full"):
        task.steps[0].pre_scoring_hook()


@pytest.mark.parametrize(
    ("namespace_usable", "needs_namespace", "mode"),
    [
        (True, False, "namespace"),
        (False, True, "namespace"),
        (False, False, "karotte_firewall"),
    ],
)
def test_container_episode_reports_its_network_mode(
    config, monkeypatch, namespace_usable, needs_namespace, mode
):
    import karotte.confinement
    import karotte.subprocess

    seen = {}

    def session(argv, *fds, disable_networking):
        seen["disable_networking"] = disable_networking
        return list(argv), None

    monkeypatch.setattr(task_module, "is_containerized", lambda: True)
    monkeypatch.setattr(
        task_module, "_network_namespace_usable", lambda exe: namespace_usable
    )
    monkeypatch.setattr(
        karotte.confinement, "network_needs_namespace", lambda: needs_namespace
    )
    monkeypatch.setattr(karotte.subprocess, "student_session_command", session)
    episode = task_module.make_episode(config)
    assert episode.isolated
    limits = episode.python_runner().limits()
    assert limits["network"] == mode
    assert ("without network access" in limits["isolation"]) is (mode == "namespace")
    episode.launcher([sys.executable, "-c", "pass"])
    assert seen["disable_networking"] is (mode == "namespace")


def test_pre_hook_and_summary_record_isolation(task, config, run_config):
    meta = task.pre_hook()
    assert meta["network_mode"] == "not_isolated" and meta["isolated"] is False
    scoring = _judge(config, run_config).evaluate(transcript_for([]))
    assert scoring.metadata["transcript_summary"]["isolation"] == {
        "isolated": False,
        "network_mode": "not_isolated",
        "python_cleanup_failures": 0,
    }


def test_instructions_say_which_calls_are_not_counted(run_config):
    text = " ".join(
        GB2019ElectricalDisturbanceTask(run_config).steps[0].instructions.split()
    )
    assert "calls with invalid argument values" in text
    assert "argument name the tool does not accept" in text and "not counted" in text
