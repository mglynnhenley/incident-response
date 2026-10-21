"""Per-topic scoping of judge requests (decision 52), the full investigation's rubric
and config, and the judge track's dispatch to the full-investigation grader.

A scoped request carries only its topic's findings in full, the report text that refers
to them, their cited spans and the topic's keyed spans, plus every other finding by ID,
status and opening words. Checked here on a synthetic full-investigation submission
(increment A's real Opus submission plus the key's examples for the new topics), the
full-investigation oracle and increment A's six real runs. Mocked judges only: no model
is called.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import fi_grading_support as fi
import pytest
from judge_scope_support import (
    FI_CONFIG,
    RUN_MODEL,
    SR_LIVE,
    chars,
    fi_config,
    fi_report,
    fi_submission,
    sr_base_report,
    sr_catalogue,
    sr_key,
    sr_runs,
    sr_text,
    synthetic_fi_submission,
)
from sr_judge_support import FakeJudge, Request, default_response

from environment.incident import fi_grading
from environment.incident import grading as mvp
from environment.incident.judge import (
    TASK_CONFIG_DEFAULTS,
    TOPIC_PROMPT_VERSION,
    JudgeConfig,
    JudgeConfigError,
    JudgeScope,
    build_units,
    judge_episode,
    judge_submission,
    judge_submission_file,
    load_config,
    load_rubric,
    plan_submission,
    prompt_template_sha256,
    resolve_scope,
    task_for_key,
)
from environment.incident.judge import scope as topic_scope
from environment.incident.judge.__main__ import main as judge_cli
from environment.incident.judge.runner import _prepare
from environment.incident.paths import (
    FULL_INVESTIGATION_PRIVATE_DIR,
    SYSTEM_RESPONSE_PRIVATE_DIR,
)

FI_TASK = "gb-2019-full-investigation"
# increment A's list (test_sr_judge_prompt) plus the scope's own selection labels,
# which are recorded in the judge output and never shown to the judge
INTERNALS = re.compile(
    r"live runs?|gb2019-v2|gb2019-live|\bD[1-4]\.(?:\d|N)|\bMVP\b|pre-?screen|"
    r"conventions\.|reviewer_note|automated (?:cap|trap|check)|\bsr30k|\bsr80k|"
    r"keyed_citation|report_reference|all_findings|dimensions_matched",
    re.I,
)
MODEL_WORDS = re.compile(r"claude|anthropic|opus|sonnet|haiku", re.I)


def _build(sub, report, key, catalogue, config, run_model=RUN_MODEL):
    parsed, _ = mvp._as_submission(sub, catalogue)
    return build_units(
        parsed,
        report,
        key,
        catalogue,
        config,
        load_rubric(config.rubric_path()),
        blind_terms=[run_model],
    )


def _whole(config: JudgeConfig) -> JudgeConfig:
    return config.model_copy(update={"scope": JudgeScope()})


def _view(unit) -> dict:
    user = unit.messages[1]["content"]
    return json.loads(user.split("<submission>\n", 1)[1].split("\n</submission>", 1)[0])


def _span_ids(unit, prefix: str) -> set[str]:
    return set(re.findall(rf'<span id="({prefix}\d+)"', unit.messages[1]["content"]))


@pytest.fixture(scope="module")
def synthetic():
    sub = synthetic_fi_submission()
    report = fi_report("synthetic")
    inputs = _build(sub, report, fi.key(), fi.catalogue(), fi_config())
    return sub, report, inputs


@pytest.fixture(scope="module")
def units(synthetic):
    return {u.unit_id: u for u in synthetic[2].units}


# -- configuration and opt-in -------------------------------------------------------------
def test_the_fi_example_config_spells_out_the_task_defaults():
    config = load_config(FI_CONFIG)
    assert config == load_config(task=FI_TASK)
    assert config.scope.mode == "topic" and config.scope.all_findings_tasks == ["T17"]
    assert config.rubric_path() == FULL_INVESTIGATION_PRIVATE_DIR / "judge_rubric_v1.md"
    assert config.public()["scope"] == config.scope.public()
    raw = json.loads(FI_CONFIG.read_text())
    assert not any("key" in k.lower() and not k.startswith("_") for k in raw)
    assert "sk-" not in FI_CONFIG.read_text()
    # every other setting is increment A's default
    assert (
        config.model_copy(
            update={
                "scope": None,
                "rubric_file": JudgeConfig().rubric_file,
                "app_title": JudgeConfig().app_title,
            }
        )
        == JudgeConfig()
    )
    assert TASK_CONFIG_DEFAULTS["gb-2019-system-response"] == {}


def test_the_fi_rubric():
    rubric = load_rubric(fi_config().rubric_path())
    assert (rubric.rubric_id, rubric.version) == ("gb2019-fi-judge-rubric", "1.0.0")
    assert rubric.key_id == fi.key()["key_id"]
    sr_rubric = load_rubric(JudgeConfig().rubric_path())
    assert sr_rubric.key_id == sr_key()["key_id"] and sr_rubric.sha256 != rubric.sha256
    text = rubric.text
    for term in ("other_findings", "excerpt", "[…]", "whole", "enforcement outcome"):
        assert term in text, term
    assert not INTERNALS.search(text), INTERNALS.search(text).group(0)
    # general rules only: no expected values, times or amounts of this event
    assert not re.search(
        r"\d{1,2}:\d{2}|\d,\d{3}|£|\b\d+(?:\.\d+)? ?(?:MW|Hz|m)\b", text
    )


def test_rubric_paths(tmp_path: Path):
    assert (
        JudgeConfig().rubric_path()
        == SYSTEM_RESPONSE_PRIVATE_DIR / "judge_rubric_v1.md"
    )
    nested = JudgeConfig(rubric_file="full_investigation/judge_rubric_v1.md")
    assert nested.rubric_path() == FULL_INVESTIGATION_PRIVATE_DIR / "judge_rubric_v1.md"
    absolute = tmp_path / "r.md"
    assert JudgeConfig(rubric_file=str(absolute)).rubric_path() == absolute


def test_a_key_or_a_config_opts_in():
    key = copy.deepcopy(sr_key())
    assert resolve_scope(JudgeConfig(), key).mode == "submission"
    key["judge"]["scope"] = {"mode": "topic", "title_chars": 60}
    scope = resolve_scope(JudgeConfig(), key)
    assert scope.mode == "topic" and scope.title_chars == 60
    key["judge"]["scope"] = "topic"
    assert resolve_scope(JudgeConfig(), key).scoped
    # the config wins over the key
    assert resolve_scope(JudgeConfig(scope=JudgeScope()), key).mode == "submission"
    key["judge"]["scope"] = {"mode": "everything"}
    with pytest.raises(JudgeConfigError, match="judge.scope"):
        resolve_scope(JudgeConfig(), key)
    with pytest.raises(JudgeConfigError, match="unknown task"):
        load_config(task="gb-2019-nothing")
    with pytest.raises(JudgeConfigError):
        load_config(scope={"mode": "topic", "unknown": 1})


def test_a_key_scope_scopes_increment_a_requests_too():
    """The scoping is not tied to the full investigation: a key that opts in gets
    scoped requests (increment A's key does not; see test_judge_scope_parity)."""
    key = copy.deepcopy(sr_key())
    key["judge"]["scope"] = {"mode": "topic"}
    run = "sr80k-haiku45-001"
    inputs = _build(
        sr_text(run), sr_base_report(run), key, sr_catalogue(), JudgeConfig()
    )
    assert inputs.scope is not None and all(u.scope == "topic" for u in inputs.units)
    unassigned = next(u for u in inputs.units if u.unit_id == "UNASSIGNED")
    assert unassigned.criterion_ids == []
    assert set(unassigned.shown_finding_ids) == set(unassigned.finding_ids)


# -- what a scoped request shows ------------------------------------------------------------
def test_each_unit_shows_its_findings_in_full_and_lists_the_others(synthetic):
    sub, report, inputs = synthetic
    order = [f["finding_id"] for f in sub["findings"]]
    statuses = {f["finding_id"]: f["status"] for f in sub["findings"]}
    routed = {}
    for a in report["assertion_quality"]["assertions"]:
        routed.setdefault(a["dimension"], set()).add(a["assertion_id"])
    title_chars = fi_config().scope.title_chars
    for unit in inputs.units:
        view = _view(unit)
        shown = [f["finding_id"] for f in view["findings"]]
        assert shown == unit.shown_finding_ids
        assert shown == [f for f in order if f in shown]
        others = [f for f in order if f not in shown]
        assert [g.split(" ", 1)[0] for g in view["other_findings"]] == others
        for gist, fid in zip(view["other_findings"], others, strict=True):
            prefix = f"{fid} ({statuses[fid]}): "
            assert gist.startswith(prefix)
            assert len(gist) - len(prefix) <= title_chars + 2
        assert set(unit.finding_ids) <= set(shown)
        assert routed.get(unit.unit_id, set()) <= set(shown), unit.unit_id
        assert set(unit.selection) == set(shown)
        assert {r for why in unit.selection.values() for r in why} <= set(
            topic_scope.REASONS
        )
    t10 = next(u for u in inputs.units if u.unit_id == "T10")
    assert len(t10.shown_finding_ids) < len(order) / 2


def test_cited_spans_are_those_of_the_units_own_findings(synthetic):
    _, _, inputs = synthetic
    every_cited = {s for s in inputs.index.spans if s.startswith("C")}
    for unit in inputs.units:
        own = [f for f, why in unit.selection.items() if why != ["all_findings"]]
        expected = {
            s.span_id
            for s in inputs.index.spans.values()
            if s.span_id.startswith("C") and set(s.cited_by) & set(own)
        } | {s for s in unit.keyed_span_ids if s.startswith("C")}
        assert _span_ids(unit, "C") == set(unit.cited_span_ids) == expected
        assert _span_ids(unit, "K") == {
            s for s in unit.keyed_span_ids if s.startswith("K")
        }
        assert inputs.index.shown_in(unit) == set(unit.cited_span_ids) | set(
            unit.keyed_span_ids
        )
        if unit.unit_id != "T17":
            assert len(unit.cited_span_ids) < len(every_cited)


def test_report_text_is_what_refers_to_the_units_findings(synthetic):
    sub, _, inputs = synthetic
    sentences = topic_scope.report_sentences(sub, inputs.finding_ids)
    for unit in inputs.units:
        if unit.unit_id == "T17":
            continue
        own = {f for f, why in unit.selection.items() if why != ["all_findings"]}
        shown_text = "\n".join(p["text"] for p in _view(unit)["report"])
        for items in sentences.values():
            for item in items:
                if set(item.refs) & own:
                    assert item.text in shown_text, (unit.unit_id, item.text)
        # an excerpt holds sentences that refer to the unit's findings, or to none
        for part, plan_part in zip(
            _view(unit)["report"], _parts_of(sub, _view(unit)), strict=True
        ):
            if part["shown"] != "excerpt":
                continue
            for item in sentences[plan_part]:
                if item.text in part["text"] and item.refs:
                    assert set(item.refs) & own, (unit.unit_id, item.text)


def _parts_of(sub, view) -> list[int]:
    """The report part index (-1: executive summary) of each shown part."""
    headings = [s["heading"] for s in sub["report"]["sections"]]
    return [
        topic_scope.SUMMARY_PART
        if p["part"] == "executive_summary"
        else headings.index(p["heading"])
        for p in view["report"]
    ]


def test_parts_a_topic_reads_whole_and_the_cross_cutting_register(synthetic, units):
    sub, _, inputs = synthetic

    def parts(unit):
        return {p.get("heading", "SUMMARY"): p["shown"] for p in _view(unit)["report"]}

    assert parts(units["T20"])["SUMMARY"] == "whole"
    assert parts(units["T18"])["Recommendations"] == "whole"
    assert parts(units["T10"])["SUMMARY"] == "excerpt"
    t17 = units["T17"]
    assert t17.shown_finding_ids == inputs.finding_ids
    assert _view(t17)["other_findings"] == []
    assert set(parts(t17).values()) == {"whole"}
    assert "report_parts_not_shown" not in _view(t17)
    # every finding in full, but only the cited spans of its own findings
    assert len(t17.cited_span_ids) < sum(
        1 for s in inputs.index.spans if s.startswith("C")
    )
    assert any(why == ["all_findings"] for why in t17.selection.values())
    # findings shown without their spans: their citations point at no span
    shown_spans = set(t17.cited_span_ids)
    nulls = 0
    for f in _view(t17)["findings"]:
        for c in f["citations"]:
            assert c["span"] is None or c["span"] in shown_spans
            nulls += c["span"] is None
    assert nulls > 0


def test_scoped_requests_are_much_smaller(synthetic):
    sub, report, inputs = synthetic
    whole = _build(sub, report, fi.key(), fi.catalogue(), _whole(fi_config()))
    assert all(u.scope is None for u in whole.units)
    assert [u.unit_id for u in whole.units] == [u.unit_id for u in inputs.units]
    assert chars(inputs.units) < 0.5 * chars(whole.units)
    scope = fi_config().scope
    totals = [0, 0]
    for run in sr_runs():
        args = (sr_text(run), sr_base_report(run), sr_key(), sr_catalogue())
        full = chars(_build(*args, JudgeConfig()).units)
        scoped = chars(_build(*args, JudgeConfig(scope=scope)).units)
        assert scoped < 0.65 * full, run
        totals[0] += full
        totals[1] += scoped
    assert totals[1] < 0.6 * totals[0]


def test_findings_the_real_judge_credited_are_shown_in_full():
    """Recall on real output: every finding gpt-6.1-sol credited for a criterion in
    increment A's three judged runs (whole-submission requests) is shown in full in that
    criterion's scoped request, except one context finding of one partial credit.
    Opus T12.03 (0.5): F25 (LFDD at 48.8 Hz) stands beside F08, F10 and F14, which are
    shown; F25 is listed by its opening words. (F14, the first frequency minimum where
    the fall was arrested, is shown since the error screen added sentence-level
    vocabulary: its second sentence ranks T12; 298 of 300 before, 299 now.)"""
    tasks = {c["criterion_id"]: c["task"] for c in sr_key()["criteria"]}
    scope = fi_config().scope
    missing = {}
    credited = 0
    for run, meta in sr_runs().items():
        if not meta["judged"]:
            continue
        inputs = _build(
            sr_text(run),
            sr_base_report(run),
            sr_key(),
            sr_catalogue(),
            JudgeConfig(scope=scope),
            meta["model"],
        )
        shown = {u.unit_id: set(u.shown_finding_ids) for u in inputs.units}
        recorded = json.loads((SR_LIVE / run / "judge_output.json").read_text())
        for cid, entry in recorded["criteria"].items():
            for fid in entry["finding_ids"]:
                credited += 1
                if fid not in shown.get(tasks[cid], set()):
                    missing.setdefault(run, []).append((cid, fid))
    assert credited == 300
    assert missing == {"sr80k-opus55-001": [("T12.03", "F25")]}


def test_scoped_requests_name_no_internals_and_no_model():
    sub = synthetic_fi_submission()
    sub["findings"][0]["statement"] += " (Checked by Claude Opus 5.5.)"
    sub["report"]["executive_summary"] = (
        "Written by claude-opus-5.5 (Anthropic). " + sub["report"]["executive_summary"]
    )
    report = fi_grading.grade_submission(sub, fi.catalogue(), fi.key())
    inputs = _build(sub, report, fi.key(), fi.catalogue(), fi_config())
    assert inputs.redactions >= 3
    for unit in inputs.units:
        for message in unit.messages:
            text = message["content"]
            assert not MODEL_WORDS.search(text), (
                unit.unit_id,
                MODEL_WORDS.search(text),
            )
            match = INTERNALS.search(text)
            assert match is None, (unit.unit_id, message["role"], match.group(0))
    assert any("[model]" in u.messages[1]["content"] for u in inputs.units)


def test_scoping_is_deterministic(synthetic, units):
    sub, report, _ = synthetic
    again = _build(sub, report, fi.key(), fi.catalogue(), fi_config())
    assert {u.unit_id: u.messages_sha256 for u in again.units} == {
        k: u.messages_sha256 for k, u in units.items()
    }


# -- cache keys and versions ----------------------------------------------------------------
def test_the_scope_is_part_of_the_cache_key():
    sub, report = fi_submission("synthetic"), fi_report("synthetic")
    args = (sub, report, fi.key(), fi.catalogue())
    scoped = _prepare(*args, fi_config(), RUN_MODEL, None)
    whole = _prepare(*args, _whole(fi_config()), RUN_MODEL, None)
    assert scoped.template_sha == prompt_template_sha256(fi_config().scope)
    assert whole.template_sha == prompt_template_sha256()
    assert scoped.template_sha != whole.template_sha
    unit = scoped.inputs.units[0]
    assert scoped.material(unit)["scope"] == fi_config().scope.public()
    assert "scope" not in whole.material(whole.inputs.units[0])
    narrower = fi_config().model_copy(
        update={"scope": fi_config().scope.model_copy(update={"title_chars": 60})}
    )
    other = _prepare(*args, narrower, RUN_MODEL, None)
    assert other.template_sha != scoped.template_sha
    assert other.material(other.inputs.units[0]) != scoped.material(unit)


# -- the runner with a mocked judge ----------------------------------------------------------
@pytest.fixture(scope="module")
def judged(synthetic):
    sub, report, _ = synthetic
    fake = FakeJudge()
    result = judge_submission(
        sub,
        report,
        key=fi.key(),
        catalogue=fi.catalogue(),
        config=fi_config(),
        run_model=RUN_MODEL,
        client=fake,
    )
    return fake, result


def test_a_scoped_full_investigation_through_a_mocked_judge(synthetic, judged):
    sub, report, inputs = synthetic
    fake, result = judged
    out = result.judge_output
    assert out["complete"] is True and out["span_checks"]["rejected"] == 0
    assert out["prompt_version"] == TOPIC_PROMPT_VERSION
    assert out["scope"] == fi_config().scope.public()
    assert out["rubric_id"] == "gb2019-fi-judge-rubric"
    assert "warnings" not in result.run_log
    assert len(fake.calls) == len(inputs.units) == 20
    factual = [
        f["finding_id"]
        for f in sub["findings"]
        if f["status"] in ("observed", "reported", "inferred")
    ]
    assert sorted(f for r in fake.calls for f in r.findings) == sorted(factual)
    shown = {u.unit_id: u.shown_finding_ids for u in inputs.units}
    for record in out["units"]:
        assert record["scope"]["findings_shown"] == shown[record["unit_id"]]
        assert set(record["scope"]["selection"]) == set(shown[record["unit_id"]])
    # the mocked judge read the scoped submission: only the unit's findings in full
    for req in fake.calls:
        assert [f["finding_id"] for f in req.submission["findings"]] == shown[
            req.unit_id
        ]
    merged = fi_grading.merge_judge_proposals(report, out)
    assert merged["judge"]["criteria_applied"]
    assert set(merged["judge"]["criteria_applied"]) <= set(
        fi.key()["judge"]["criteria"]
    )
    assert merged["status"] == "provisional"


def test_evidence_resting_on_a_listed_only_finding_is_withheld(synthetic):
    sub, report, inputs = synthetic
    t10 = next(u for u in inputs.units if u.unit_id == "T10")
    listed = next(
        f["finding_id"]
        for f in sub["findings"]
        if f["finding_id"] not in t10.shown_finding_ids and f["citations"]
    )
    hidden_span = next(
        s
        for s in inputs.index.spans.values()
        if listed in s.cited_by and s.span_id not in t10.cited_span_ids
    )
    cid = t10.criterion_ids[0]

    def respond(req: Request):
        reply = default_response(req)
        if req.unit_id != "T10":
            return reply
        keyed = next(s for s in req.spans if s.startswith("K"))
        for entry in reply["criteria"]:
            if entry["criterion_id"] != cid:
                continue
            entry.update(
                content=1,
                evidence_support=1,
                finding_ids=[listed],
                supporting_spans=[
                    {
                        "evidence_id": "x",
                        "locator": keyed,
                        "quote": req.first_line(keyed),
                    },
                    {
                        "evidence_id": hidden_span.evidence_id,
                        "locator": hidden_span.locator,
                        "quote": hidden_span.shown_text[:60],
                    },
                ],
            )
        return reply

    result = judge_submission(
        sub,
        report,
        key=fi.key(),
        catalogue=fi.catalogue(),
        config=fi_config(),
        run_model=RUN_MODEL,
        client=FakeJudge(respond=respond),
    )
    entry = result.judge_output["criteria"][cid]
    assert entry["evidence_support"] is None and entry["judge_evidence_support"] == 1
    assert any("cross-reference list" in i for i in entry["issues"])
    # the span cited only by the listed finding was never shown: dropped
    assert entry["rejected_spans"] and entry["rejected_spans"][0]["reason"]
    assert result.judge_output["span_checks"]["rejected"] >= 1


def test_a_report_assertion_quoted_from_an_excerpt_is_verified(synthetic):
    sub, report, inputs = synthetic

    def respond(req: Request):
        reply = default_response(req)
        if req.unit_id == "T10":
            part = next(p for p in req.submission["report"] if p["shown"] == "excerpt")
            sentence = [
                s.strip()
                for s in part["text"].split(topic_scope.EXCERPT_GAP)
                if len(s.split()) > 4
            ][0]
            reply["report_assertions"] = [
                {
                    "text": sentence,
                    "verdict": "unsupported",
                    "spans": [],
                    "rationale": "no span shown",
                    "confidence": "medium",
                }
            ]
        return reply

    result = judge_submission(
        sub,
        report,
        key=fi.key(),
        catalogue=fi.catalogue(),
        config=fi_config(),
        run_model=RUN_MODEL,
        client=FakeJudge(respond=respond),
    )
    found = [
        a for k, a in result.judge_output["assertions"].items() if k.startswith("J-T10")
    ]
    assert len(found) == 1 and found[0]["location"].startswith("report.")


def test_dry_run_reports_the_scope_and_its_size(synthetic):
    sub, report, _ = synthetic
    args = dict(key=fi.key(), catalogue=fi.catalogue(), run_model=RUN_MODEL)
    scoped = plan_submission(sub, report, config=fi_config(), **args)
    whole = plan_submission(sub, report, config=_whole(fi_config()), **args)
    assert scoped["scope"]["mode"] == "topic" and "scope" not in whole
    assert all("findings_shown" in u for u in scoped["units"])
    assert (
        scoped["approx_input_tokens_all_units"] == scoped["approx_input_tokens_to_send"]
    )
    assert (
        scoped["approx_input_tokens_to_send"]
        < 0.5 * whole["approx_input_tokens_to_send"]
    )
    # a full-investigation key with increment A's rubric is recorded, not refused
    mixed = plan_submission(sub, report, config=JudgeConfig(), **args)
    assert any("written for key" in w for w in mixed["warnings"])


# -- the judge track serves the full investigation ------------------------------------------
def test_the_task_follows_the_key():
    assert task_for_key(fi.key()).grader is fi_grading
    assert task_for_key(sr_key()).task_id == "gb-2019-system-response"
    assert task_for_key(None).task_id == "gb-2019-system-response"


@pytest.fixture
def fi_episode(tmp_path: Path):
    config = fi.episode_config(tmp_path)
    sub = fi.submission(
        [
            fi.finding(
                "F1",
                "ORR reports 29 Class 700/717 trains locked out: 22 needed a "
                "technician and 7 were restored by driver reset.",
                "reported",
                [("S08", "L120-L127")],
            ),
            fi.finding(
                "F2",
                "Newcastle Airport was disconnected by Northern Powergrid's LFDD.",
                "reported",
                [("S11", "L78-L81")],
            ),
        ],
        "Rail [F1]. Airport [F2].",
        summary="Rail and essential services [F1, F2].",
    )
    results = fi.run_calls(
        config,
        [
            ("request_document", {"doc_id": "S08"}),
            ("request_document", {"doc_id": "S11"}),
            ("submit_findings", {"submission": sub}),
        ],
    )
    assert all(r.envelope["ok"] for _, _, r in results)
    return config.episode_dir


def test_judge_episode_grades_a_full_investigation_with_its_grader(
    fi_episode, tmp_path
):
    run = judge_episode(
        fi_episode,
        config=fi_config(),
        run_model=RUN_MODEL,
        task=FI_TASK,
        client=FakeJudge(),
        out_dir=tmp_path / "judge",
    )
    assert run.status == "judged"
    assert run.report["grade_schema"] == fi_grading.GRADE_SCHEMA
    assert run.report["judge"]["criteria_applied"]
    assert run.judge_output["scope"]["mode"] == "topic"
    graded = json.loads((tmp_path / "judge" / "grade.json").read_text())
    assert graded["task_id"] == FI_TASK
    # the key alone selects the task as well
    plan = judge_episode(
        fi_episode,
        config=fi_config(),
        run_model=RUN_MODEL,
        key=fi.key(),
        dry_run=True,
        out_dir=tmp_path / "plan",
    )
    assert plan.status == "dry_run" and plan.run_log["scope"]["mode"] == "topic"


def test_judge_submission_file_and_the_command_line(tmp_path, capsys):
    path = tmp_path / "submission.json"
    path.write_text(json.dumps(synthetic_fi_submission()), encoding="utf-8")
    run = judge_submission_file(
        path,
        config=fi_config(),
        out_dir=tmp_path / "out",
        run_model=RUN_MODEL,
        task=FI_TASK,
        dry_run=True,
    )
    assert (
        run.status == "dry_run"
        and run.report["grade_schema"] == fi_grading.GRADE_SCHEMA
    )
    assert len(run.run_log["units"]) == 20
    status = judge_cli(
        ["prompt", str(path), "--task", FI_TASK, "--run-model", RUN_MODEL]
    )
    assert status == 0
    listing = json.loads(capsys.readouterr().out)
    assert len(listing) == 20 and all("findings_shown" in u for u in listing)
    status = judge_cli(
        [
            "prompt",
            str(path),
            "--task",
            FI_TASK,
            "--run-model",
            RUN_MODEL,
            "--unit",
            "T10",
        ]
    )
    assert status == 0
    printed = capsys.readouterr().out
    assert "Scope of this request: unit T10 only." in printed
    assert "gb2019-fi-judge-rubric" in printed
    # increment A's default is untouched: no scope note without the task
    sr_path = tmp_path / "sr.json"
    sr_path.write_text(sr_text("sr80k-haiku45-001"), encoding="utf-8")
    assert judge_cli(["prompt", str(sr_path), "--run-model", RUN_MODEL]) == 0
    assert "findings_shown" not in capsys.readouterr().out


# -- the selection helpers ------------------------------------------------------------------
def test_tokens():
    found = topic_scope.tokens(
        "ORR: Class 700/717 lock-outs at 16:53, 1,878 MW and 49.083 Hz at Ørsted's site"
    )
    assert {
        "orr",
        "class",
        "700",
        "717",
        "lock",
        "outs",
        "16:53",
        "1878",
        "49.083",
    } <= found
    assert "orsted" in found and "and" not in found and "at" not in found
    assert topic_scope.tokens("transmission transmitted") == {"transmi"}


def test_excerpts_mark_gaps_and_keep_lines():
    sub = fi.submission(
        [fi.finding("F1", "x"), fi.finding("F2", "y")],
        "One [F1]. Two.\nThree [F2]. Four.",
    )
    sentences = topic_scope.report_sentences(sub, ["F1", "F2"])
    body = sentences[0]
    assert [s.refs for s in body] == [("F1",), (), ("F2",), ()]
    assert topic_scope._excerpt(body, {0, 2}) == "One [F1]. […] Three [F2]. […]"
    assert topic_scope._excerpt(body, {1, 2}) == "[…] Two.\nThree [F2]. […]"
    assert topic_scope._excerpt(body, {3}) == "[…] Four."
    unknown = topic_scope.report_sentences(
        fi.submission([fi.finding("F1", "x")], "A [F1, F9]."), ["F1"]
    )
    assert unknown[0][0].refs == ("F1",)


def test_finding_gist_cuts_at_a_word():
    f = {"finding_id": "F7", "status": "reported", "statement": "word " * 40}
    gist = topic_scope.finding_gist(f, 30)
    assert gist.startswith("F7 (reported): word") and gist.endswith(" …")
    assert len(gist) <= len("F7 (reported): ") + 32
    short = {"finding_id": "F8", "status": "unknown", "statement": "Short."}
    assert topic_scope.finding_gist(short, 30) == "F8 (unknown): Short."


def test_vocabulary_ranking():
    vocab = topic_scope.Vocabulary(
        tasks={
            "T1": frozenset({"rail", "train"}),
            "T2": frozenset({"rail", "train"}),
            "T3": frozenset({"hospita"}),
        },
        idf={"rail": 1.0, "train": 1.0, "hospita": 3.0},
    )
    assert vocab.best("rail train hospital", 2, 0) == ["T3", "T1"]
    assert vocab.best("rail train", 3, 2.5) == []
    assert vocab.best("rail", 0, 0) == []
    built = topic_scope.build_vocabulary(fi.key())
    assert set(built.tasks) == {d["dimension_id"] for d in fi.key()["dimensions"]}
    assert "technic" in built.tasks["T10"] and built.idf["technic"] > 1


def test_keys_load_by_their_schema(tmp_path: Path):
    from environment.incident.grading import GradingError
    from environment.incident.judge.tasks import load_key

    fi_path = FULL_INVESTIGATION_PRIVATE_DIR / "answer_key.json"
    sr_path = SYSTEM_RESPONSE_PRIVATE_DIR / "answer_key.json"
    assert load_key(fi_path)["key_id"] == fi.key()["key_id"]
    assert load_key(sr_path)["key_id"] == sr_key()["key_id"]
    assert load_key(None, FI_TASK)["key_id"] == fi.key()["key_id"]
    assert load_key()["key_id"] == sr_key()["key_id"]
    with pytest.raises(GradingError, match="not a gb2019-fi-answer-key"):
        load_key(sr_path, FI_TASK)
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    with pytest.raises(GradingError, match="cannot load"):
        load_key(bad)


def test_the_command_line_dry_runs_a_full_investigation_episode(fi_episode, capsys):
    status = judge_cli(
        [
            "run",
            str(fi_episode),
            "--task",
            FI_TASK,
            "--run-model",
            RUN_MODEL,
            "--dry-run",
        ]
    )
    assert status == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["status"] == "dry_run" and plan["scope"]["mode"] == "topic"
    assert plan["rubric_version"] == "1.0.0" and "warnings" not in plan
    assert {u["unit_id"] for u in plan["units"]} >= {"T10", "T11", "T17"}
    assert not (fi_episode / "judge").exists()  # a dry run writes nothing
