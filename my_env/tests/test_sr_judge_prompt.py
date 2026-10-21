"""What the judge sees: the blinded submission, the criterion rubric, the cited spans
and keyed spans, and nothing else (no model identity, no source-report passages or
provenance, no automated pre-screen, no auto_numeric criteria)."""

from __future__ import annotations

import json
import re

import pytest
from sr_grading_support import catalogue, key, oracle_submission
from sr_judge_support import RUN_MODEL, base_report, config, small_submission

from environment.incident import grading as mvp
from environment.incident import sr_grading
from environment.incident.judge import (
    JudgeConfigError,
    build_units,
    load_config,
    load_rubric,
    prompt_template_sha256,
)
from environment.incident.judge.prompt import Blinder

MODEL_WORDS = re.compile(
    r"claude|anthropic|opus|sonnet|haiku|gpt|openai|gemini|llama|mistral", re.I
)
ALLOWED_CRITERION_KEYS = {
    "criterion_id",
    "title",
    "handoff_text",
    "polarity",
    "expectation",
    "expected",
    "tolerances",
    "accepted_alternatives",
    "accounting_figures",
    "examples",
    "keyed_spans",
}


def build(sub, trace_info=None, cfg=None, run_model=RUN_MODEL):
    cfg = cfg or config()
    sub_dict, _ = mvp._as_submission(sub, catalogue())
    report = sr_grading.grade_submission(sub, catalogue(), key(), trace_info)
    return build_units(
        sub_dict,
        report,
        key(),
        catalogue(),
        cfg,
        load_rubric(cfg.rubric_path()),
        blind_terms=[run_model],
    )


@pytest.fixture(scope="module")
def oracle_inputs():
    return build(oracle_submission())


def _section(user: str, tag: str) -> str:
    return user.split(f"<{tag}>\n", 1)[1].split(f"\n</{tag}>", 1)[0]


def test_model_identity_is_blinded():
    sub = small_submission(
        " Written by claude-opus-5.5 via openrouter/anthropic/claude-opus-5.5; as an "
        "Opus model I am confident."
    )
    sub["findings"][0]["statement"] += " (Sonnet and GPT-5 agree.)"
    inputs = build(sub)
    assert inputs.redactions >= 6
    for unit in inputs.units:
        text = json.dumps(unit.messages, ensure_ascii=False)
        assert not MODEL_WORDS.search(text), (unit.unit_id, MODEL_WORDS.search(text))
        assert RUN_MODEL not in text and "claude-opus-5.5" not in text
        assert "[model]" in text


def test_key_examples_naming_live_runs_are_not_shown(oracle_inputs):
    t01 = next(u for u in oracle_inputs.units if u.unit_id == "T01")
    raw = json.dumps(
        next(c for c in key()["criteria"] if c["criterion_id"] == "T01.01")["examples"]
    )
    assert "opus55-002" in raw  # the key's reviewer note names the live runs ...
    user = t01.messages[1]["content"]
    assert "opus55" not in user and "sonnet55" not in user  # ... the judge never
    assert "live run" not in user and "reviewer_note" not in user  # sees the note
    assert "the cause in its own finding" in user


# Grader internals the judge must not see: other runs, MVP criterion IDs, key
# conventions, the automated pre-screen or caps (the rubric says it sees no automated
# grading and no other submissions).
INTERNALS = re.compile(
    r"live runs?|gb2019-v2|gb2019-live|\bD[1-4]\.(?:\d|N)|\bMVP\b|pre-?screen|"
    r"conventions\.|reviewer_note|automated (?:cap|trap|check)",
    re.I,
)


def test_judge_messages_name_no_grader_internals(oracle_inputs):
    for unit in oracle_inputs.units:
        for message in unit.messages:
            match = INTERNALS.search(message["content"])
            assert match is None, (unit.unit_id, message["role"], match.group(0))
    rubric = sr_grading.criterion_rubric("T07.01", key=key(), catalogue=catalogue())
    assert not INTERNALS.search(json.dumps(rubric, ensure_ascii=False))
    assert "T07.04" in rubric["expectation"]


def test_blinder_counts_and_keeps_evidence_words():
    blind = Blinder(["openrouter/anthropic/claude-haiku-4.5"])
    text = "claude-haiku-4.5 and Claude Haiku 4.5 by Anthropic; Hornsea One; ESO"
    out = blind(text)
    assert out == "[model] and [model] [model] 4.5 by [model]; Hornsea One; ESO"
    assert blind.count == 4
    assert blind.quiet("Little Barford GT1A") == "Little Barford GT1A"
    assert blind.count == 4


def test_only_rubric_fields_are_shown(oracle_inputs):
    for unit in oracle_inputs.units:
        user = unit.messages[1]["content"]
        criteria = json.loads(_section(user, "criteria"))
        assert [c["criterion_id"] for c in criteria] == unit.criterion_ids
        for c in criteria:
            assert set(c) <= ALLOWED_CRITERION_KEYS, set(c) - ALLOWED_CRITERION_KEYS
            for side in ("positive", "negative"):
                assert all("prescreen" not in ex for ex in c["examples"][side])
        for word in (
            "report_passages",
            "pdf_page",
            "printed_page",
            "prescreen",
            "auto_proposal",
            "assessment_mode",
            "matched_finding_ids",
            "provenance",
            "builder_only",
            "must_contain",
            '"full_if_any"',
            '"half_if_any"',
            '"elements"',
            '"heuristic"',
            '"trigger_any"',
        ):
            assert word not in user, (unit.unit_id, word)


def test_no_auto_numeric_criterion_is_ever_sent(oracle_inputs):
    modes = {c["criterion_id"]: c["assessment_mode"] for c in key()["criteria"]}
    sent = [cid for u in oracle_inputs.units for cid in u.criterion_ids]
    assert sorted(sent) == sorted(
        c for c, m in modes.items() if m in ("judge", "auto_assisted_human")
    )
    assert len(sent) == len(set(sent))
    with pytest.raises(JudgeConfigError, match="never sent to the judge"):
        load_config(modes=["judge", "auto_numeric"])
    judge_only = build(oracle_submission(), cfg=config(modes=["judge"]))
    assert sorted(c for u in judge_only.units for c in u.criterion_ids) == sorted(
        key()["judge"]["criteria"]
    )


def test_keyed_spans_are_resolved_from_the_bundle(oracle_inputs):
    t06 = next(u for u in oracle_inputs.units if u.unit_id == "T06")
    user = t06.messages[1]["content"]
    keyed = _section(user, "keyed_spans")
    crit = next(c for c in key()["criteria"] if c["criterion_id"] == "T06.03")
    for ve in crit["visible_evidence"]:
        text = sr_grading.resolve_text(catalogue(), ve["evidence_id"], ve["locator"])
        first = text.split("\n")[0]
        assert first in user  # in <keyed_spans> or, if cited, in <cited_spans>
    assert 'role="primary"' in keyed
    assert "[L54] " in user  # numbered document lines


def test_shared_prefix_is_identical_across_units(oracle_inputs):
    """The rubric, submission and cited spans come first, identical for every unit,
    so providers can reuse the cached prompt prefix."""
    systems = {u.messages[0]["content"] for u in oracle_inputs.units}
    assert len(systems) == 1
    prefixes = {
        u.messages[1]["content"].split("\nUnit ", 1)[0] for u in oracle_inputs.units
    }
    assert len(prefixes) == 1
    assert next(iter(prefixes)).startswith("<submission>\n")


def test_messages_are_deterministic():
    a = build(small_submission())
    b = build(small_submission())
    assert [u.messages_sha256 for u in a.units] == [u.messages_sha256 for u in b.units]
    assert prompt_template_sha256() == prompt_template_sha256()
    c = build(small_submission(" More."))
    assert a.units[0].messages_sha256 != c.units[0].messages_sha256


def test_cited_spans_note_evidence_never_obtained():
    trace_info = {
        "available": True,
        "retrieved": ["S01"],
        "document_routes": {"S01": ["request_document"]},
        "records": {},
        "frequency_rows_seen": [],
        "python_calls": [],
        "r01_analysed_with_python": False,
    }
    inputs = build(small_submission(), trace_info=trace_info)
    user = inputs.units[0].messages[1]["content"]
    cited = _section(user, "cited_spans")
    spans = dict(re.findall(r'<span id="(C\d+)" ([^>]*)>', cited))
    by_loc = {re.search(r'locator="([^"]+)"', a).group(1): a for a in spans.values()}
    assert "note=" not in by_loc["L54-L58"]
    assert 'note="not obtained during the episode"' in by_loc["L39-L42"]
    assert 'note="not obtained during the episode"' in by_loc["response:S09-ORS-04"]
    assert 'cited_by="F1"' in by_loc["L54-L58"]
    sub = json.loads(_section(user, "submission"))
    assert sub["findings"][0]["citations"][0]["span"] == "C1"


def test_long_spans_are_truncated_with_a_note():
    sub = small_submission()
    sub["findings"][0]["citations"].append({"evidence_id": "S12", "locator": "L1-L152"})
    inputs = build(sub, cfg=config(max_span_chars=400))
    span = next(s for s in inputs.index.spans.values() if s.locator == "L1-L152")
    assert "truncated" in span.notes
    assert len(span.shown_text) <= 400
    assert "[... truncated:" in span.rendered


def test_units_route_findings_once():
    inputs = build(small_submission())
    classified = [f for u in inputs.units for f in u.finding_ids]
    assert sorted(classified) == ["F1", "F2", "F3", "F4"]
    t06 = next(u for u in inputs.units if u.unit_id == "T06")
    assert t06.report_assertion_limit == config().max_report_assertions
    flags = {f["flag_id"] for f in t06.flags}
    assert flags == {"SF2", "SF3"}  # SF1 applies to T07/T17 only
    t07 = next(u for u in inputs.units if u.unit_id == "T07")
    assert {f["flag_id"] for f in t07.flags} == {"SF1", "SF2", "SF3"}
    no_report = build(small_submission(), cfg=config(report_assertions=False))
    assert all(u.report_assertion_limit == 0 for u in no_report.units)


def test_rubric_is_versioned():
    rubric = load_rubric(config().rubric_path())
    assert rubric.rubric_id == "gb2019-sr-judge-rubric"
    assert rubric.version == "1.0.0"
    assert len(rubric.sha256) == 64
    assert rubric.path == "judge_rubric_v1.md"
    assert not MODEL_WORDS.search(rubric.text)


def test_report_must_match_submission_for_routing():
    report = base_report(small_submission())
    dims = {
        a["assertion_id"]: a["dimension"]
        for a in report["assertion_quality"]["assertions"]
    }
    assert dims["F1"] == "T06" and dims["F2"] == "T02"


def test_keyed_span_attributes_name_only_the_request_criteria(oracle_inputs):
    for unit in oracle_inputs.units:
        keyed = _section(unit.messages[1]["content"], "keyed_spans")
        for names in re.findall(r' for="([^"]+)"', keyed):
            assert set(names.split()) <= set(unit.criterion_ids), unit.unit_id
        assert len(re.findall(r'<span id="K', keyed)) == sum(
            1 for s in unit.keyed_span_ids if s.startswith("K")
        )
