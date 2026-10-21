"""Task gb-2019-full-investigation (increment B): discovery, instructions, hooks, judge,
image checks and a full run through Karotte.

Everything runs on the synthetic bundle from ``fi_helpers``; the real
``bundles/full_investigation`` bundle and ``private/full_investigation`` are never
loaded (they are built separately and may not exist yet).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shlex
import subprocess
import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fi_helpers import FI_BUNDLE_ID, fi_config, fi_submission, make_fi_bundle
from incident_helpers import transcript_for
from karotte import EvaluationRunConfig, ProtectedStore, ToolConfigWriter
from karotte import evaluation_runner as runner_module
from karotte import tool_base as karotte_tool_base
from karotte.agents import FakeSource, MessageLoopAgent
from karotte.mcp_servers.mcp_server import McpServer
from karotte.schemas.chat import ChatCompletionMessageToolCall, Function, Message
from karotte.schemas.transcript import ScoringEvent, TaskCompletedEvent
from sr_helpers import SR_TOOLS

import environment
import environment.tasks.gb_2019_full_investigation as task_module
from environment import incident_checks
from environment.incident import paths
from environment.incident.catalogue import Catalogue, CatalogueError
from environment.incident.episode import (
    CONTEXT_CAP_TOKENS,
    FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET,
    OUTPUT_TOKEN_BUDGET,
    SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET,
    Episode,
    EpisodeConfig,
    read_state,
    read_trace,
)
from environment.incident.replay import replay_episode
from environment.tasks.gb_2019_full_investigation import (
    BRIEF,
    FullInvestigationStep,
    FullInvestigationToolConfig,
    GB2019FullInvestigationTask,
)
from environment.tasks.gb_2019_full_investigation.judge import (
    GRADING_MODULE,
    FullInvestigationJudge,
)
from environment.tasks.gb_2019_full_investigation.prompt import (
    REPORT_EXPECTATIONS,
    REPORT_SECTIONS,
    SECTION_HEADINGS,
)
from environment.tasks.gb_2019_system_response import prompt as sr_prompt

TASK_ID = "gb-2019-full-investigation"
SR_TASK_ID = "gb-2019-system-response"
MVP_TASK_ID = "gb-2019-electrical-disturbance"
PILOT_SECTIONS = (
    "Executive summary",
    "Chronology",
    "Findings",
    "Consequences",
    "Uncertainties",
    "Recommendations",
    "Further evidence requests",
)
ALL_TOPICS = tuple(f"T{n:02d}" for n in range(1, 21))
INCREMENT_A_BRIEF_CLAUSES = (
    "Investigate the electrical disturbance on 9 August 2019",
    "Establish what happened and when, quantify the generation lost and the demand "
    "disconnected on the bases the records use, explain how frequency was contained "
    "and recovered",
    "distinguish supported explanations from unresolved causes",
    "Support your findings with the available evidence.",
)


def _run_config(tmp_path: Path, **extra) -> EvaluationRunConfig:
    return EvaluationRunConfig(
        run_id="fi",
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
def config(tmp_path: Path) -> FullInvestigationToolConfig:
    bundle = make_fi_bundle(tmp_path / "src")
    return FullInvestigationToolConfig(**fi_config(tmp_path, bundle).model_dump())


@pytest.fixture
def task(run_config, config, monkeypatch) -> GB2019FullInvestigationTask:
    monkeypatch.setattr(
        GB2019FullInvestigationTask, "episode_config", lambda self: config
    )
    monkeypatch.setattr(
        FullInvestigationStep, "episode_config", property(lambda self: config)
    )
    return GB2019FullInvestigationTask(run_config)


@pytest.fixture
def no_grader(monkeypatch):
    """Grading as it is until ``fi_grading`` is built: the module cannot be imported."""
    monkeypatch.setitem(sys.modules, GRADING_MODULE, None)


def _instructions(run_config) -> str:
    return GB2019FullInvestigationTask(run_config).steps[0].instructions


def _flat(text: str) -> str:
    return " ".join(text.split())


# -- discovery and shape -----------------------------------------------------------------
def test_task_is_discovered_once_alongside_the_frozen_tasks():
    ids = [cls.id for cls in environment.get_tasks()]
    assert ids.count(TASK_ID) == 1
    assert ids.count(SR_TASK_ID) == 1 and ids.count(MVP_TASK_ID) == 1


def test_task_shape(run_config):
    t = GB2019FullInvestigationTask(run_config)
    assert t.id == TASK_ID and t.tools == list(SR_TOOLS)
    assert len(t.steps) == 1 and t.system_prompt
    assert isinstance(t.steps[0], FullInvestigationStep)
    assert isinstance(t.steps[0].judge, FullInvestigationJudge)


def test_paths_name_a_third_bundle_and_private_dir():
    assert (
        paths.FULL_INVESTIGATION_BUNDLE_DIR == paths.BUNDLES_DIR / "full_investigation"
    )
    assert (
        paths.FULL_INVESTIGATION_PRIVATE_DIR
        == paths.DEFAULT_PRIVATE_DIR / "full_investigation"
    )
    assert paths.FULL_INVESTIGATION_BUNDLE_DIR not in (
        paths.DEFAULT_BUNDLE_DIR,
        paths.SYSTEM_RESPONSE_BUNDLE_DIR,
    )
    assert task_module.KEY_CANDIDATES == (
        paths.FULL_INVESTIGATION_PRIVATE_DIR / "answer_key.json",
    )


def test_default_configuration_points_at_the_full_investigation_bundle():
    cfg = FullInvestigationToolConfig()
    assert cfg.bundle_dir == paths.FULL_INVESTIGATION_BUNDLE_DIR
    assert cfg.max_tool_calls == 150 and cfg.tool_profile == "system_response"
    assert cfg.python_timeout_s == 30 and cfg.python_memory_bytes == 1 << 30
    assert cfg.frequency_page_size == 1000 and cfg.log_page_size == 200
    assert cfg.list_page_size == 50 and cfg.exec_summary_word_limit == 600
    assert cfg.variant_id == "baseline"


def test_frozen_tasks_keep_their_bundles_budgets_and_graders():
    from environment.tasks.gb_2019_electrical_disturbance import (
        IncidentToolConfig,
    )
    from environment.tasks.gb_2019_electrical_disturbance.judge import (
        GRADING_MODULE as MVP_GRADING,
    )
    from environment.tasks.gb_2019_system_response import SystemResponseToolConfig
    from environment.tasks.gb_2019_system_response.judge import (
        GRADING_MODULE as SR_GRADING,
    )

    assert IncidentToolConfig().bundle_dir == paths.DEFAULT_BUNDLE_DIR
    assert SystemResponseToolConfig().bundle_dir == paths.SYSTEM_RESPONSE_BUNDLE_DIR
    assert MVP_GRADING == "environment.incident.grading"
    assert SR_GRADING == "environment.incident.sr_grading"
    assert GRADING_MODULE == "environment.incident.fi_grading"
    assert OUTPUT_TOKEN_BUDGET == 30_000
    assert SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET == 80_000
    assert FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET == 80_000
    assert CONTEXT_CAP_TOKENS == 200_000


def test_nothing_loads_the_bundle_without_a_hook(run_config, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("the bundle must not be loaded here")

    monkeypatch.setattr(Catalogue, "load", classmethod(refuse))
    t = GB2019FullInvestigationTask(run_config)
    assert t.tools and t.steps[0].instructions and t.steps[0].judge


def test_importing_the_task_loads_no_bundle():
    code = (
        "import environment.incident.catalogue as c\n"
        "def refuse(*a, **k):\n"
        "    raise SystemExit('a bundle was loaded at import time')\n"
        "c.Catalogue.load = classmethod(refuse)\n"
        "import environment.tasks.gb_2019_full_investigation as m\n"
        "import environment.tasks.gb_2019_full_investigation.judge\n"
        "import environment.incident_checks\n"
        "print(m.TASK_ID)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == TASK_ID


# -- instructions ---------------------------------------------------------------------------
def test_brief_broadens_increment_a_to_the_whole_incident(run_config):
    for clause in INCREMENT_A_BRIEF_CLAUSES:
        assert clause in BRIEF, clause
    for scope in (
        "its consequences",
        "recovery of affected services",
        "rail",
        "essential services",
        "communications",
        "factors that contributed",
        "compliance concerns",
        "recommend actions",
        "further evidence requests",
    ):
        assert scope in BRIEF, scope
    assert BRIEF in _instructions(run_config)


def test_instructions_state_budgets_tools_and_rules(run_config):
    text = _instructions(run_config)
    flat = _flat(text)
    for needle in [
        "STATUS",
        "real published data extracts",
        "digitised",
        "[modelled]",
        "index_time_utc",
        "retrospective investigation",
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
        "in pages of up to 50",
        "at most 200 findings",
        "assessed for accuracy",
        "evidence support",
        "handling of uncertainty",
        "not a legal or regulatory determination",
    ]:
        assert needle in flat or needle in text, needle
    for tool in SR_TOOLS:
        assert f"`{tool}(" in text, tool


def test_instructions_date_notice_and_evidence_size(run_config):
    """The catalogue date is the incident date, not the sources' (every document is listed
    with the incident date); the agent is told what reaching the context cap does and how
    large the evidence is, since reading everything does not fit (decision 53)."""
    from environment.tasks.gb_2019_full_investigation import prompt

    flat = _flat(_instructions(run_config))
    assert "every document is listed with its date" not in flat
    assert (
        "The date the catalogue lists for a document is the date of the incident it "
        "covers, not the date of its sources: each record names its sources and, where "
        "it uses them, their dates." in flat
    )
    assert (
        "A run that reaches the context cap ends at once and, without a frozen "
        "submission, is recorded as incomplete." in flat
    )
    assert (
        f"about {prompt.EVIDENCE_DOCUMENT_CHARS:,} characters of numbered text" in flat
    )
    assert f"about {prompt.EVIDENCE_LOG_CHARS:,} characters of rows" in flat
    assert "does not fit in the context cap" in flat
    # Together the documents and logs exceed the cap even at 4 characters per token.
    total = prompt.EVIDENCE_DOCUMENT_CHARS + prompt.EVIDENCE_LOG_CHARS
    assert total / 4 > CONTEXT_CAP_TOKENS


def test_report_sections_follow_the_pilot_plan(run_config):
    assert REPORT_SECTIONS == PILOT_SECTIONS
    assert SECTION_HEADINGS == PILOT_SECTIONS[1:]
    text = _instructions(run_config)
    flat = _flat(text)
    listed = ", ".join(f'"{heading}"' for heading in SECTION_HEADINGS)
    assert f"`report.sections` with the headings {listed}, in that order" in flat
    assert "an executive summary of at most 600 words (`report.executive_summary`)" in (
        flat
    )
    skeleton = json.loads(re.search(r"```json\n(.*?)\n```", text, re.S).group(1))
    assert [s["heading"] for s in skeleton["report"]["sections"]] == list(
        SECTION_HEADINGS
    )
    assert all(s["body"].startswith("<") for s in skeleton["report"]["sections"])
    assert skeleton["report"]["executive_summary"].startswith("<at most 600 words")


def test_the_skeleton_sections_are_a_valid_report_shape(config):
    """The skeleton's report part, with placeholders filled, passes validation."""
    ep = Episode(config)
    ep.reset()
    sub = fi_submission()
    sub["report"]["sections"] = [
        {"heading": heading, "body": "See [F01]."} for heading in SECTION_HEADINGS
    ]
    assert ep.submit_findings(sub).ok


def test_report_expectations_cover_every_topic(run_config):
    tagged = " ".join(tag for tag, _ in REPORT_EXPECTATIONS).split()
    for topic in ALL_TOPICS:
        assert topic in tagged, topic
    text = _instructions(run_config)
    flat = _flat(text)
    for _, item in REPORT_EXPECTATIONS:
        assert _flat(item) in flat
    assert not re.search(r"\bT\d\d\b", text)  # builder tags are not shown


def test_increment_a_expectations_are_kept_word_for_word():
    """Every increment-A item is kept; only the chronology now runs to the recovery of
    affected services."""
    ours = {_flat(item).rstrip(";.") for _, item in REPORT_EXPECTATIONS}
    for tag, item in sr_prompt.REPORT_EXPECTATIONS:
        text = _flat(item).rstrip(";.")
        if tag == "T02 T05":
            text = text.replace(
                "the restoration of disconnected demand,",
                "the restoration of disconnected demand and the recovery of affected "
                "services,",
            )
        assert text in ours, tag


def test_tool_descriptions_are_increment_a_s(config):
    """Same nine tools under the same profile: the descriptions the agent sees are
    increment A's, with this task's limits."""
    assert sorted(sr_prompt.TOOL_DESCRIPTIONS) == sorted(SR_TOOLS)
    for name in SR_TOOLS:
        text = sr_prompt.tool_description(name, config)
        assert "of your 150 tool calls" in text and "$" not in text, name


def test_instructions_leak_no_answers(run_config):
    text = _instructions(run_config)
    block = re.search(r"```json\n(.*?)\n```", text, re.S).group(1)
    skeleton = json.loads(block)
    assert skeleton["schema_version"] == "3.0" and skeleton["variant_id"] == "baseline"
    assert skeleton["findings"][0]["event_time"].startswith("<")
    increment_a = [
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
        "5 %",
        "inertia of",
    ]
    increment_b = [
        # rail
        "Class",
        "700",
        "717",
        "387",
        "Thameslink",
        "Govia",
        "GTR",
        "Network Rail",
        "Siemens",
        "3.25",
        "3.27",
        "lockout",
        "technician",
        "driver",
        "reset",
        "200 ms",
        "stranded",
        "traction",
        "cancel",
        "delay minutes",
        # essential services
        "Newcastle",
        "Ipswich",
        "Wirral",
        "Merseyrail",
        "Stanlow",
        "airport",
        "Airport",
        "hospital",
        "Hospital",
        "water",
        "refinery",
        # communications
        "17:51",
        "18:00",
        "18:27",
        "17:18",
        "17:20",
        "17:54",
        "REMIT",
        "Elexon",
        "COBR",
        "BEIS",
        "Twitter",
        "tweet",
        "@",
        "million",
        # compliance and enforcement
        "£",
        "4.5",
        "1.5",
        "10.5",
        "settlement",
        "penalt",
        "redress",
        "ESQCR",
        "OC7",
        "OC10",
        "Grid Code",
        "Distribution Code",
        "SQSS",
        "ride-through",
        "ride through",
        "damping",
        "interim notification",
        "EPN",
        "SPN",
        "UKPN",
        "UK Power Networks",
        "Ørsted",
        "Orsted",
        "RWE",
        "E3C",
        "ORR",
    ]
    for leak in increment_a + increment_b:
        assert leak not in text, leak


# -- hooks ---------------------------------------------------------------------------------
def test_configure_tools_writes_the_bundle_for_all_nine(
    task, config, tmp_path, monkeypatch
):
    configs_dir = tmp_path / "tool_configs"
    monkeypatch.setattr(karotte_tool_base, "CONFIGS_DIR", configs_dir)
    task.configure_tools()
    files = sorted(p.name for p in configs_dir.glob("*.json"))
    assert files == sorted(f"{name}.json" for name in SR_TOOLS)
    for path in configs_dir.glob("*.json"):
        written = json.loads(path.read_text())
        assert written["tool_profile"] == "system_response"
        assert written["max_tool_calls"] == 150
        assert Path(written["bundle_dir"]) == Path(config.bundle_dir)


def test_default_tool_configs_name_the_shipped_bundle(
    run_config, tmp_path, monkeypatch
):
    configs_dir = tmp_path / "tool_configs"
    monkeypatch.setattr(karotte_tool_base, "CONFIGS_DIR", configs_dir)
    GB2019FullInvestigationTask(run_config).configure_tools()
    for name in SR_TOOLS:
        written = json.loads((configs_dir / f"{name}.json").read_text())
        assert Path(written["bundle_dir"]) == paths.FULL_INVESTIGATION_BUNDLE_DIR
        assert Path(written["bundle_dir"]) != paths.SYSTEM_RESPONSE_BUNDLE_DIR


def test_pre_hook_resets_and_reports(task, config):
    Episode(config).reset()
    Episode(config).list_documents()
    meta = task.pre_hook()
    assert meta["task_id"] == TASK_ID and meta["manifest_version"] == 2
    assert meta["bundle_id"] == FI_BUNDLE_ID
    assert {"S08", "S10", "S11", "R09"} <= set(meta["documents"])
    assert meta["tool_names"] == list(SR_TOOLS)
    assert meta["budgets"]["max_tool_calls"] == 150
    assert meta["budgets"]["output_token_budget"] == 80_000
    assert meta["budgets"]["context_cap_tokens"] == 200_000
    assert read_state(config.episode_dir).calls_used == 0


def test_pre_hook_fails_closed_on_a_tampered_bundle(task, config):
    text = Path(config.bundle_dir) / "S08" / "S08.txt"
    text.write_text(text.read_text().replace("Synthetic", "Altered"))
    with pytest.raises(CatalogueError, match="sha256 mismatch"):
        task.pre_hook()


def test_pre_hook_fails_closed_without_the_bundle(run_config, tmp_path, monkeypatch):
    missing = FullInvestigationToolConfig(
        **fi_config(tmp_path, tmp_path / "no_bundle_here").model_dump()
    )
    monkeypatch.setattr(
        GB2019FullInvestigationTask, "episode_config", lambda self: missing
    )
    with pytest.raises(CatalogueError):
        GB2019FullInvestigationTask(run_config).pre_hook()


def test_pre_hook_reports_key_metadata(task, monkeypatch, tmp_path):
    key = tmp_path / "answer_key.json"
    key.write_text(
        json.dumps({"key_version": "0.1.0", "review_status": "pending_domain_review"})
    )
    monkeypatch.setattr(task_module, "KEY_CANDIDATES", (tmp_path / "missing.json", key))
    meta = task.pre_hook()
    assert meta["key_version"] == "0.1.0"
    assert meta["review_status"] == "pending_domain_review"
    assert meta["key_file"] == "answer_key.json"


def test_pre_hook_without_a_key_reports_none(task, monkeypatch, tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    monkeypatch.setattr(
        task_module, "KEY_CANDIDATES", (tmp_path / "missing.json", broken)
    )
    meta = task.pre_hook()
    assert not {"key_version", "review_status", "key_file"} & set(meta)


# -- judge ---------------------------------------------------------------------------------
def _complete_episode(config) -> tuple[Episode, list]:
    ep = Episode(config)
    ep.reset()
    calls = [
        (
            "query_frequency",
            {"start": "2019-08-09T16:52:00+01:00", "end": "2019-08-09T16:53:00+01:00"},
        ),
        (
            "request_data_return",
            {"party": "Synthetic Regulator", "data_type": "compliance process records"},
        ),
        ("submit_findings", {"submission": fi_submission()}),
    ]
    return ep, [(t, a, ep.call(t, a)) for t, a in calls]


def test_complete_run_scores_one_and_grading_is_unavailable(
    config, run_config, no_grader
):
    _, calls = _complete_episode(config)
    scoring = FullInvestigationJudge(config, run_config).evaluate(transcript_for(calls))
    assert scoring.score == 1.0 and scoring.metadata["outcome"] == "complete"
    summary = scoring.metadata["transcript_summary"]
    assert summary["tool_calls_episode_tools"] == 3
    assert summary["ledger_discrepancy"]["difference"] == 0
    assert summary["budgets"] == {
        "tool_calls_limit": 150,
        "output_token_budget": 80_000,
        "context_cap_tokens": 200_000,
    }
    grading = scoring.metadata["grading"]
    assert grading == {
        "status": "unavailable",
        "reason": f"{GRADING_MODULE} not installed",
    }
    assert not (Path(config.episode_dir) / "grade.json").exists()
    assert "Completion only" in scoring.metadata["score_semantics"]


def test_grading_module_without_grade_episode_is_unavailable(
    config, run_config, monkeypatch
):
    monkeypatch.setitem(sys.modules, GRADING_MODULE, types.SimpleNamespace())
    _, calls = _complete_episode(config)
    scoring = FullInvestigationJudge(config, run_config).evaluate(transcript_for(calls))
    assert scoring.score == 1.0
    assert scoring.metadata["grading"]["status"] == "unavailable"


def test_judge_uses_the_full_investigation_grader_only(config, run_config, monkeypatch):
    seen = {}

    def grade_episode(episode_dir, summary):
        seen["dir"] = Path(episode_dir)
        seen["budget"] = summary["budgets"]["output_token_budget"]
        return {"grader": "fi", "outcome": summary["outcome"]}

    def other_grader(*args, **kwargs):
        raise AssertionError("another task's grader must not grade this task")

    monkeypatch.setitem(
        sys.modules, GRADING_MODULE, types.SimpleNamespace(grade_episode=grade_episode)
    )
    for name in ("environment.incident.grading", "environment.incident.sr_grading"):
        monkeypatch.setitem(
            sys.modules, name, types.SimpleNamespace(grade_episode=other_grader)
        )
    _, calls = _complete_episode(config)
    scoring = FullInvestigationJudge(config, run_config).evaluate(transcript_for(calls))
    grading = scoring.metadata["grading"]
    assert grading["status"] == "graded" and grading["grade"]["grader"] == "fi"
    assert seen == {"dir": Path(config.episode_dir), "budget": 80_000}
    grade = json.loads((Path(config.episode_dir) / "grade.json").read_text())
    assert grade == {"grader": "fi", "outcome": "complete"}


def test_a_grading_error_never_changes_the_score(config, run_config, monkeypatch):
    def grade_episode(episode_dir, summary):
        raise RuntimeError("key not built yet")

    monkeypatch.setitem(
        sys.modules, GRADING_MODULE, types.SimpleNamespace(grade_episode=grade_episode)
    )
    _, calls = _complete_episode(config)
    scoring = FullInvestigationJudge(config, run_config).evaluate(transcript_for(calls))
    assert scoring.score == 1.0
    assert scoring.metadata["grading"] == {
        "status": "error",
        "error": "RuntimeError: key not built yet",
    }


def test_no_submission_is_incomplete(config, run_config, no_grader):
    ep = Episode(config)
    ep.reset()
    result = ep.list_documents()
    scoring = FullInvestigationJudge(config, run_config).evaluate(
        transcript_for([("list_documents", {}, result)])
    )
    assert scoring.score == 0.0
    assert scoring.metadata["incomplete_reason"] == "final_message_without_submission"


@pytest.mark.parametrize(
    ("output_tokens", "outcome"),
    [(79_000, "complete"), (80_000, "complete"), (80_001, "incomplete_submission")],
)
def test_the_output_budget_is_80k(
    config, run_config, no_grader, output_tokens, outcome
):
    _, calls = _complete_episode(config)
    usage = [(1000, 0), (1000, 0), (1000, output_tokens), (1000, 50)]
    scoring = FullInvestigationJudge(config, run_config).evaluate(
        transcript_for(calls, usage=usage)
    )
    assert scoring.metadata["outcome"] == outcome
    if outcome != "complete":
        assert scoring.metadata["incomplete_reason"] == "output_token_budget_exhausted"
    cfg = EpisodeConfig(
        episode_dir="/tmp/e", evidence_dir="/tmp/v", scratch_dir="/tmp/s"
    )
    assert FullInvestigationJudge(cfg).output_token_budget == 80_000


def test_the_tool_call_budget_is_150(config, run_config, no_grader):
    ep = Episode(config)
    ep.reset()
    results = [ep.list_documents() for _ in range(150)]
    assert all(r.ok for r in results)
    assert results[-1].envelope["budget"]["tool_calls_remaining"] == 0
    refused = ep.submit_findings(fi_submission())
    assert refused.error_code == "BUDGET_EXCEEDED" and not refused.counted
    calls = [("list_documents", {}, r) for r in results]
    calls.append(("submit_findings", {"submission": fi_submission()}, refused))
    scoring = FullInvestigationJudge(config, run_config).evaluate(transcript_for(calls))
    assert scoring.score == 0.0
    assert scoring.metadata["incomplete_reason"] == "tool_budget_exhausted"


# -- image checks (incident_checks) ---------------------------------------------------------
@pytest.fixture
def shipped_fi(tmp_path, monkeypatch) -> tuple[Path, Path]:
    """A synthetic full-investigation bundle and private directory in place of the
    shipped ones."""
    bundle = make_fi_bundle(tmp_path / "fi_src")
    private = tmp_path / "private" / "full_investigation"
    private.mkdir(parents=True)
    for name in ("answer_key.json", "provenance.json", "REVIEW_CHECKLIST.md"):
        (private / name).write_text("{}\n")
    (private / "judge").mkdir()
    (private / "judge" / "rubric.md").write_text("rubric\n")
    monkeypatch.setattr(paths, "FULL_INVESTIGATION_BUNDLE_DIR", bundle)
    monkeypatch.setattr(paths, "FULL_INVESTIGATION_PRIVATE_DIR", private)
    return bundle, private


def test_fi_paths_are_protected_when_present(shipped_fi):
    bundle, private = shipped_fi
    directories, files = incident_checks.protected_paths()
    for folder in (
        bundle,
        bundle / "S08",
        bundle / "S10",
        bundle / "R09",
        bundle / "logs",
        bundle / "logs" / "assets",
        bundle / "logs" / "control",
        bundle / "witnesses",
        private,
        private / "judge",
    ):
        assert folder in directories, folder
    for path in (
        bundle / "manifest.json",
        bundle / "S10" / "S10.txt",  # data-return only
        bundle / "S05" / "S05.txt",  # data-return only (increment A's)
        private / "answer_key.json",
        private / "provenance.json",
        private / "REVIEW_CHECKLIST.md",
        private / "judge" / "rubric.md",
    ):
        assert path in files, path
    for folder in ("assets", "control"):
        assert any(p.parent == bundle / "logs" / folder for p in files), folder
    assert any(p.parent == bundle / "witnesses" for p in files)
    assert len(files) == len(set(files))
    # the frozen tasks' paths are still covered
    assert paths.SYSTEM_RESPONSE_BUNDLE_DIR in directories
    assert paths.SYSTEM_RESPONSE_PRIVATE_DIR in directories
    assert paths.DEFAULT_BUNDLE_DIR in directories

    script = incident_checks.bash_check_script()
    targets = incident_checks.probe_targets()
    for path in (*directories, *files):
        assert shlex.quote(str(path)) in script, path
        assert str(path) in targets, path


def test_absent_fi_paths_are_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "FULL_INVESTIGATION_BUNDLE_DIR", tmp_path / "nope")
    monkeypatch.setattr(paths, "FULL_INVESTIGATION_PRIVATE_DIR", tmp_path / "none")
    assert incident_checks.fi_protected_paths() == ([], [])
    directories, files = incident_checks.protected_paths()
    assert all(p.exists() for p in (*directories, *files))


def test_data_return_only_files_tolerate_a_broken_manifest(tmp_path):
    (tmp_path / "manifest.json").write_text("{broken")
    assert incident_checks.data_return_only_files(tmp_path) == []
    (tmp_path / "manifest.json").write_text(json.dumps({"documents": "nonsense"}))
    assert incident_checks.data_return_only_files(tmp_path) == []
    assert incident_checks.data_return_only_files(tmp_path / "missing") == []


def test_fi_unobtained_targets_cover_unrequested_returns_and_private_files(shipped_fi):
    bundle, private = shipped_fi
    targets = incident_checks.fi_unobtained_targets(bundle, private, ["R01", "S05"])
    assert str(bundle / "S10" / "S10.txt") in targets
    assert str(bundle / "S05" / "S05.txt") not in targets  # obtained
    for name in ("answer_key.json", "provenance.json", "REVIEW_CHECKLIST.md"):
        assert str(private / name) in targets
    assert str(private / "judge" / "rubric.md") in targets
    code = incident_checks.private_path_probe_code(targets)
    compile(code, "probe", "exec")


def test_increment_a_runner_checks_are_unchanged(monkeypatch):
    """The full investigation's runner checks are not part of increment A's flow."""
    calls = []
    monkeypatch.setattr(
        incident_checks,
        "_episode_checks",
        lambda task_id, config_class: calls.append(task_id),
    )
    monkeypatch.setattr(
        incident_checks, "_sr_materialisation_checks", lambda: calls.append("sr")
    )
    monkeypatch.setattr(
        incident_checks,
        "full_investigation_checks",
        lambda: calls.append("must not run here"),
    )
    incident_checks._runner_checks()
    assert calls == [MVP_TASK_ID, SR_TASK_ID, "sr"]
    assert dict(incident_checks.fi_task_tool_configs()) == {
        TASK_ID: FullInvestigationToolConfig
    }


def test_fi_image_checks_are_discovered_and_container_only(monkeypatch):
    import pkgutil

    from environment import incident_fi_checks

    discovered = sorted(
        info.name
        for info in pkgutil.iter_modules(environment.__path__)
        if info.name.endswith("_checks")
    )
    assert "incident_fi_checks" in discovered
    assert discovered.index("incident_checks") < discovered.index("incident_fi_checks")

    calls = []
    monkeypatch.setattr(
        incident_checks, "full_investigation_checks", lambda: calls.append("fi")
    )
    monkeypatch.delenv("KAROTTE_CONTAINERIZED", raising=False)
    incident_fi_checks.check()
    assert calls == []
    monkeypatch.setenv("KAROTTE_CONTAINERIZED", "1")
    incident_fi_checks.check()
    assert calls == ["fi"]


def test_full_investigation_checks_fail_closed_without_the_bundle(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(paths, "FULL_INVESTIGATION_BUNDLE_DIR", tmp_path / "missing")

    def must_not_run(*args, **kwargs):
        raise AssertionError("nothing may run before the bundle verifies")

    monkeypatch.setattr(incident_checks, "_episode_checks", must_not_run)
    with pytest.raises(CatalogueError):
        incident_checks.full_investigation_checks()


class _FakeResult:
    def __init__(self, report: dict) -> None:
        self.ok = True
        self.envelope = {"data": {"stdout": json.dumps(report) + "\n"}, "error": None}


@pytest.mark.parametrize(
    ("broken", "message"),
    [
        ({}, None),
        ({"after_queries": ["logs"]}, "log queries or witness answers"),
        ({"python": {"uid": 0}}, "ran as uid 0"),
        ({"python": {"denied": {"/x": "READABLE"}}}, "unobtained or private"),
        ({"write": {"results": {"unlink_file": "ALLOWED"}}}, "modify a data return"),
        ({"extra": {"/private/key": "READABLE"}}, "unobtained or private"),
    ],
)
def test_full_investigation_checks_drive_an_episode_and_assert_isolation(
    monkeypatch, broken, message
):
    import environment.tasks.gb_2019_electrical_disturbance as mvp_task

    calls = []
    good = {
        "after_reset": [],
        "after_queries": [],
        "obtained": ["R01", "S05"],
        "after_obtaining": ["R01", "S05"],
        "python": {
            "uid": 1000,
            "listing": ["R01", "S05"],
            "readable": {"S05/S05.txt": True},
            "denied": {"/x": "DENIED"},
        },
        "write": {"results": {"unlink_file": "DENIED"}},
    }
    report = {}
    for name, value in good.items():
        change = broken.get(name)
        if change is None:
            report[name] = value
        else:
            report[name] = {**value, **change} if isinstance(value, dict) else change
    extra = {"uid": 1000, "seen": broken.get("extra", {"/private/key": "DENIED"})}

    class FakeEpisode:
        def __init__(self, config):
            calls.append(("episode", Path(config.bundle_dir)))

        def reset(self):
            return {"network_mode": "namespace"}

        def run_python(self, code):
            calls.append("extra probe")
            return _FakeResult(extra)

    def fake_report(episode, private_dir):
        calls.append(("materialisation", private_dir))
        return report

    monkeypatch.setattr(
        incident_checks,
        "load_full_investigation_bundle",
        lambda: calls.append("verified") or FI_BUNDLE_ID,
    )
    monkeypatch.setattr(
        incident_checks,
        "_episode_checks",
        lambda task_id, config_class: calls.append((task_id, config_class)),
    )
    monkeypatch.setattr(incident_checks, "sr_materialisation_report", fake_report)
    monkeypatch.setattr(mvp_task, "make_episode", FakeEpisode)
    monkeypatch.setattr("environment.STUDENT_UID", 1000)
    if message is None:
        incident_checks.full_investigation_checks()
        assert calls == [
            "verified",
            (TASK_ID, FullInvestigationToolConfig),
            ("episode", paths.FULL_INVESTIGATION_BUNDLE_DIR),
            ("materialisation", paths.FULL_INVESTIGATION_PRIVATE_DIR),
            "extra probe",
        ]
    else:
        with pytest.raises(AssertionError, match=message):
            incident_checks.full_investigation_checks()


def test_load_full_investigation_bundle_verifies_it(shipped_fi):
    bundle, _ = shipped_fi
    assert incident_checks.load_full_investigation_bundle() == FI_BUNDLE_ID
    card = bundle / "witnesses" / "fleet-engineer.json"
    card.write_text(card.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(CatalogueError):
        incident_checks.load_full_investigation_bundle()


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


def test_run_through_karotte_runner(tmp_path: Path, config, monkeypatch, no_grader):
    configs_dir = tmp_path / "tool_configs"
    monkeypatch.setattr(karotte_tool_base, "CONFIGS_DIR", configs_dir)
    monkeypatch.setattr(
        runner_module, "ToolConfigWriter", lambda: ToolConfigWriter(configs_dir)
    )
    monkeypatch.setattr(
        runner_module, "ProtectedStore", lambda: ProtectedStore(tmp_path / "protected")
    )
    monkeypatch.setattr(
        GB2019FullInvestigationTask, "episode_config", lambda self: config
    )
    monkeypatch.setattr(
        FullInvestigationStep, "episode_config", property(lambda self: config)
    )
    day = {"start": "2019-08-09T00:00:00Z", "end": "2019-08-10T00:00:00Z"}
    code = (
        "import os, pandas as pd\n"
        "root = os.environ['EVIDENCE_DIR']\n"
        "df = pd.read_csv(os.path.join(root, 'R01', 'frequency.csv'))\n"
        "print(len(df), sorted(os.listdir(root)))\n"
    )
    messages = [
        _call(1, "list_documents", {}),
        _call(
            2,
            "request_document",
            {"party": "Synthetic Train Operator", "description": "rail fleet records"},
        ),
        _call(
            3,
            "query_frequency",
            {"start": "2019-08-09T16:52:00+01:00", "end": "2019-08-09T16:54:00+01:00"},
        ),
        _call(4, "query_asset_log", {"asset_id": "FLEET-A", **day}),
        _call(5, "query_control_log", {"room": "RAIL-CONTROL", **day}),
        _call(
            6,
            "interview_witness",
            {
                "persona_id": "fleet-engineer",
                "question": "What was the reset procedure for the units?",
            },
        ),
        _call(
            7,
            "request_data_return",
            {"party": "Synthetic Regulator", "data_type": "compliance process records"},
        ),
        _call(
            8,
            "request_data_return",
            {"party": "Synthetic Train Operator", "data_type": "train running records"},
        ),
        _call(9, "request_document", {"doc_id": "R09"}),
        _call(10, "request_document", {"doc_id": "R03"}),
        _call(11, "query_control_log", {"room": "SO-CONTROL", **day}),
        _call(12, "query_asset_log", {"asset_id": "ESW-400", **day}),
        _call(
            13,
            "interview_witness",
            {"persona_id": "so-engineer", "question": "How was demand restored?"},
        ),
        _call(
            14,
            "interview_witness",
            {
                "persona_id": "comms-lead",
                "question": "When were public statements made?",
            },
        ),
        _call(15, "run_python", {"code": code}),
        _call(16, "submit_findings", {"submission": fi_submission()}),
        Message(role="assistant", content="Submitted; ending my turn."),
    ]
    run_config = _run_config(
        tmp_path,
        save_artifacts=False,
        step_time_limit_seconds=600,
        on_step_time_limit="score",
    )
    task = GB2019FullInvestigationTask(run_config)
    runner = runner_module.EvaluationRunner(run_config, task)
    runner._agent = MessageLoopAgent(FakeSource(messages))
    mcp = McpServer("fi-integration")

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
    assert scoring.metadata["grading"]["status"] == "unavailable"
    summary = scoring.metadata["transcript_summary"]
    assert summary["tool_calls_episode_tools"] == 16
    assert summary["ledger_discrepancy"]["difference"] == 0
    assert summary["bundle_version"] == "3.0.0-test"

    trace = read_trace(config.episode_dir)
    codes = [r["outcome_code"] for r in trace]
    assert codes == ["OK"] * 7 + ["NOT_HELD"] + ["OK"] * 8
    assert trace[1]["envelope"]["evidence_ids"] == ["S08"]
    assert trace[6]["envelope"]["evidence_ids"] == ["S10"]
    stdout = trace[14]["python"]["stdout"]
    assert stdout.startswith("1500 ") and "'S10'" in stdout and "'S08'" in stdout
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
    for name in SR_TOOLS:
        assert registered[name]["description"] == sr_prompt.tool_description(
            name, config
        ), name
    assert "of your 150 tool calls" in registered["list_documents"]["description"]
    assert replay_episode(config.episode_dir).ok
