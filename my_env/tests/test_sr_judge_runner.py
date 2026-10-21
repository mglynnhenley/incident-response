"""The judge run with a mocked client (no network, no paid calls): routing to units,
merging as judge proposals (never auto_numeric, auto_assisted_human ignored),
hallucinated quotes, withheld evidence and verdicts, schema failures and repair,
client errors, caching and cost accounting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sr_grading_support import catalogue, finding, key, row, submission
from sr_judge_support import (
    RUN_MODEL,
    SERVED_MODEL,
    FakeJudge,
    base_report,
    config,
    default_response,
    no_client,
    small_submission,
)

from environment.incident import sr_grading
from environment.incident.judge import (
    JudgeCache,
    JudgeConfigError,
    judge_submission,
    parse_response,
    request_payload,
    usage_cost,
)


def run(sub, client=None, cache=None, **kwargs):
    report = kwargs.pop("report", None) or base_report(sub)
    return report, judge_submission(
        sub,
        report,
        key=key(),
        catalogue=catalogue(),
        config=kwargs.pop("cfg", None) or config(),
        run_model=kwargs.pop("run_model", RUN_MODEL),
        client=client,
        cache=cache,
        **kwargs,
    )


@pytest.fixture(scope="module")
def judged():
    sub = small_submission()
    fake = FakeJudge()
    report, result = run(sub, fake)
    merged = sr_grading.merge_judge_proposals(report, result.judge_output)
    return sub, fake, report, result, merged


def test_one_request_per_unit_with_the_right_criteria(judged):
    _, fake, report, result, _ = judged
    units = {r.unit_id: r for r in fake.calls}
    modes = {c["criterion_id"]: c["assessment_mode"] for c in key()["criteria"]}
    sent = {cid for r in fake.calls for cid in r.criteria}
    assert sent == {
        c for c, m in modes.items() if m in ("judge", "auto_assisted_human")
    }
    assert not {c for c in sent if modes[c] == "auto_numeric"}
    # findings go to the unit of the task the automated grader assigned them
    dims = {
        a["assertion_id"]: a["dimension"]
        for a in report["assertion_quality"]["assertions"]
    }
    assert units["T06"].findings == ["F1"] and dims["F1"] == "T06"
    assert units["T02"].findings == ["F2"]
    # hypotheses and unknowns are never classified
    assert all("F5" not in r.findings for r in fake.calls)
    assert sorted(f for r in fake.calls for f in r.findings) == ["F1", "F2", "F3", "F4"]
    assert result.judge_output["complete"] is True
    assert result.run_log["api_calls"] == len(fake.calls) == len(result.inputs.units)


def test_requests_are_structured_and_deterministic(judged):
    _, fake, _, _, _ = judged
    payload = fake.calls[0].payload
    assert payload["model"] == "openai/gpt-6.1-sol"
    assert payload["temperature"] == 0
    rf = payload["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    assert payload["usage"] == {"include": True}
    assert payload["provider"] == {"require_parameters": True}
    assert [m["role"] for m in payload["messages"]] == ["system", "user"]
    assert payload["messages"][0]["content"].startswith("---\nrubric_id: ")
    again = request_payload(config(), payload["messages"])
    assert again == payload


def test_merge_makes_judge_proposals_only(judged):
    _, _, report, result, merged = judged
    jo = result.judge_output
    assert jo["judge_schema"] == sr_grading.JUDGE_SCHEMA
    assert jo["binding"]["submission_sha256"] == report["submission"]["sha256"]
    t0601 = row(merged, "T06.01")
    assert t0601["content"]["source"] == "judge" and t0601["content"]["value"] == 1
    assert t0601["evidence_support"]["source"] == "judge"
    # an automated cap still bounds the judge (F2 gives Ofgem's total as ESO's)
    t0206 = row(merged, "T02.06")
    assert t0206["content"]["judge_proposal"] == 1
    # (T02.06 was proposed on F1 here; the cap applies whatever the judge says)
    assert t0206["content"]["value"] == 0
    # auto_numeric criteria are never sent, never proposed
    for cid in ("T03.01", "T03.02", "T03.03", "T04.01"):
        assert cid not in jo["criteria"]
        assert row(merged, cid)["content"]["source"] in ("auto", "pending")
        assert row(merged, cid)["layers"]["judge"] is None
    # auto_assisted_human proposals are recorded for the reviewer and ignored
    ignored = {i["criterion_id"] for i in merged["judge"]["criteria_ignored"]}
    aah = {
        c["criterion_id"]
        for c in key()["criteria"]
        if c["assessment_mode"] == "auto_assisted_human"
    }
    assert ignored == aah
    assert row(merged, "T01.01")["content"]["source"] == "pending"
    assert row(merged, "T01.01")["judge_note"]["ignored"] is True
    assert merged["status"] == "provisional"
    assert any("judge proposals" in r for r in merged["provisional_reasons"])


def test_assertion_verdicts_and_their_spans(judged):
    _, _, _, result, merged = judged
    jo = result.judge_output
    assert jo["assertions"]["F1"]["verdict"] == "supported"
    span = jo["assertions"]["F1"]["supporting_spans"][0]
    assert span["evidence_id"] == "S01" and span["locator"] == "L54-L58"
    assert span["shown_in"]
    # an uncited finding the fake calls unsupported needs no span
    assert jo["assertions"]["F3"]["verdict"] == "unsupported"
    by = {a["assertion_id"]: a for a in merged["assertion_quality"]["assertions"]}
    assert by["F1"]["source"] == "judge" and by["F1"]["verdict"] == "supported"
    assert by["F5"]["source"] == "labelled_hypothesis_or_unknown"
    assert jo["span_checks"]["rejected"] == 0
    assert jo["span_checks"]["verified"] == jo["span_checks"]["returned"] > 0


def test_hallucinated_quotes_are_dropped_and_evidence_withheld():
    sub = small_submission()

    def respond(req):
        out = default_response(req)
        for c in out["criteria"]:
            if c["criterion_id"] == "T06.01":
                c["supporting_spans"] = [
                    {
                        "evidence_id": "S01",
                        "locator": "L54-L58",
                        "quote": "the DRC failed and caused the de-load",
                    },
                    {"evidence_id": "S02", "locator": "L1", "quote": "modelling note"},
                ]
        for a in out["assertions"]:
            if a["finding_id"] == "F1":
                a["spans"] = [
                    {"evidence_id": "S01", "locator": "L54", "quote": "invented words"}
                ]
        return out

    _, result = run(sub, FakeJudge(respond))
    jo = result.judge_output
    t0601 = jo["criteria"]["T06.01"]
    assert t0601["supporting_spans"] == []
    assert [r["reason"] for r in t0601["rejected_spans"]] == [
        "quote not found in any shown span",
        "no span of 'S02' was shown",
    ]
    assert t0601["evidence_support"] is None  # withheld: a human decides
    assert t0601["judge_evidence_support"] == 1
    assert any("withheld" in i for i in t0601["issues"])
    f1 = jo["assertions"]["F1"]
    assert f1["verdict"] is None and f1["judge_verdict"] == "supported"
    assert jo["span_checks"]["rejected"] == 3
    issues = [i for u in jo["units"] for i in u["issues"]]
    assert sum("hallucinated span dropped" in i for i in issues) == 3
    merged = sr_grading.merge_judge_proposals(base_report(sub), jo)
    assert row(merged, "T06.01")["evidence_support"]["source"] == "pending"
    by = {a["assertion_id"]: a for a in merged["assertion_quality"]["assertions"]}
    assert by["F1"]["source"] == "pending"


def test_evidence_needs_a_quote_from_a_span_the_credited_finding_cites():
    """A real quote from a keyed span the finding never cited does not earn 1."""
    sub = small_submission()

    def respond(req):
        out = default_response(req)
        if req.unit_id == "T06":
            cited_text = " ".join(
                req.spans[s]["text"] for s in req.spans if s.startswith("C")
            )
            keyed = next(
                s
                for s in req.spans
                if s.startswith("K") and req.first_line(s)[:80] not in cited_text
            )
            for c in out["criteria"]:
                c["supporting_spans"] = [
                    {
                        "evidence_id": req.spans[keyed]["ev"],
                        "locator": keyed,
                        "quote": req.first_line(keyed)[:80],
                    }
                ]
        return out

    _, result = run(sub, FakeJudge(respond))
    c = result.judge_output["criteria"]["T06.02"]
    assert c["supporting_spans"] and c["supporting_spans"][0]["shown_in"]
    assert all(s.startswith("K") for s in c["supporting_spans"][0]["shown_in"])
    assert c["evidence_support"] is None
    assert c["content"] == 1


def test_evidence_quoted_only_from_a_span_never_obtained_is_withheld():
    """F1 cites S06 L102-L103 (never obtained: the trace has only R01) and R01
    row:830 (obtained); a judge quoting only the S06 span does not earn evidence
    support: the runner withholds the 1, and the merge decides 0 from the citations."""
    sub = submission(
        [
            finding(
                "F1",
                "Ofgem's lower bound for distributed generation lost across the event is "
                "1,300 MW and it could be as high as 1,500 MW (estimates); the lowest "
                "R01 sample was 48.787 Hz at 16:53:49 BST.",
                "reported",
                [("S06", "L102-L103"), ("R01", "row:830")],
            )
        ]
    )
    trace_info = {
        "available": True,
        "retrieved": ["R01"],
        "document_routes": {"R01": ["query_frequency"]},
        "records": {},
        "frequency_rows_seen": [[830, 830]],
        "python_calls": [],
        "r01_analysed_with_python": False,
    }
    report = sr_grading.grade_submission(sub, catalogue(), key(), trace_info)
    fake = FakeJudge()  # quotes the first span F1 cites (S06)
    _, result = run(sub, fake, report=report)
    span = next(s for s in result.inputs.index.spans.values() if s.evidence_id == "S06")
    assert span.obtained is False and "not obtained during the episode" in span.notes
    for cid in ("T08.04", "T17.02"):
        c = result.judge_output["criteria"][cid]
        assert c["judge_evidence_support"] == 1 and c["evidence_support"] is None, cid
        assert any("not obtained during the episode" in i for i in c["issues"]), cid
    merged = sr_grading.merge_judge_proposals(report, result.judge_output)
    for cid in ("T08.04", "T17.02"):
        ev = row(merged, cid)["evidence_support"]
        assert ev["value"] == 0 and ev["source"] == "auto", (cid, ev)
        assert "never obtained" in ev["basis"], cid


def test_narrowed_and_relocated_spans_are_verified():
    sub = small_submission()

    def respond(req):
        out = default_response(req)
        for c in out["criteria"]:
            if c["criterion_id"] == "T06.01":
                c["supporting_spans"] = [
                    # a narrowed locator inside the cited L54-L58
                    {
                        "evidence_id": "S01",
                        "locator": "L56",
                        "quote": "The de-load was caused by an unexpected wind farm "
                        "control system response",
                    },
                    # right quote, wrong locator: moved to the span that has it
                    {
                        "evidence_id": "S09",
                        "locator": "response:S09-ORS-99",
                        "quote": "Our report concludes that the de-load",
                    },
                    # the span ID as locator, with a [L<n>] prefix and an ellipsis
                    {
                        "evidence_id": "S01",
                        "locator": req.cited_by("F1")[0],
                        "quote": "[L56] A1  Section ... insufficiently damped electrical "
                        "resonance",
                    },
                ]
        return out

    _, result = run(sub, FakeJudge(respond))
    c = result.judge_output["criteria"]["T06.01"]
    assert [s["locator"] for s in c["supporting_spans"]] == [
        "L56",
        "response:S09-ORS-04",
        "L54-L58",
    ]
    assert [s.get("relocated", False) for s in c["supporting_spans"]] == [
        False,
        True,
        False,
    ]
    assert c["evidence_support"] == 1
    assert result.judge_output["span_checks"]["relocated"] == 1


def test_not_factual_and_report_assertions_and_severe_suggestions():
    sub = small_submission(" The operators paid £10.5m in redress.")

    def respond(req):
        out = default_response(req)
        for a in out["assertions"]:
            if a["finding_id"] == "F4":
                a["verdict"] = "not_factual"
        if req.unit_id == "T06":
            out["report_assertions"] = [
                {
                    "text": "The DRC was cleared by the operator.",
                    "verdict": "supported",
                    "spans": [],
                    "rationale": "no quote given",
                    "confidence": "medium",
                },
                {
                    "text": "Hornsea One tripped because of a cable fault.",
                    "verdict": "contradicted",
                    "spans": [],
                    "rationale": "not in the report",
                    "confidence": "low",
                },
            ]
        out["severe_flag_suggestions"] = [
            {
                "flag_id": "SF3",
                "finding_ids": [],
                "report_quote": "The operators paid £10.5m in redress.",
                "rationale": "enforcement outcome",
            },
            {
                "flag_id": "SF9",
                "finding_ids": ["F1"],
                "report_quote": "",
                "rationale": "no such flag",
            },
        ]
        return out

    report, result = run(sub, FakeJudge(respond))
    jo = result.judge_output
    f4 = jo["assertions"]["F4"]
    assert f4["verdict"] is None and f4["judge_verdict"] == "not_factual"
    assert f4["rationale"].startswith("judge: not a factual assertion")
    j = jo["assertions"]["J-T06-1"]
    assert j["text"] == "The DRC was cleared by the operator."
    assert j["location"] == "report.sections[0].body" and j["task"] == "T06"
    assert j["verdict"] is None  # 'supported' without a quote is withheld
    assert "J-T06-2" not in jo["assertions"]  # text not in the report: dropped
    # SF3 suggested by every unit once: deduplicated
    assert [(s["flag_id"], s["locations"]) for s in jo["severe_flags"]] == [
        ("SF3", ["report.sections[0].body"])
    ]
    merged = sr_grading.merge_judge_proposals(report, jo)
    by = {a["assertion_id"]: a for a in merged["assertion_quality"]["assertions"]}
    assert by["J-T06-1"]["kind"] == "report_text"
    assert by["F4"]["source"] == "pending"
    assert merged["judge"]["severe_flag_suggestions"][0]["flag_id"] == "SF3"
    assert all(s["confirmed"] is None for s in merged["severe_flags"])


def test_unknown_ids_and_missing_entries_are_flagged_not_merged():
    sub = small_submission()

    def respond(req):
        out = default_response(req)
        if req.unit_id == "T06":
            out["criteria"] = out["criteria"][1:] + [
                {**out["criteria"][1], "rationale": "duplicate"},
                {**out["criteria"][1], "criterion_id": "T03.02"},
            ]
            out["criteria"][0]["finding_ids"] = ["F1", "F99"]
            out["assertions"].append({**out["assertions"][0], "finding_id": "F2"})
        return out

    report, result = run(sub, FakeJudge(respond))
    jo = result.judge_output
    unit = next(u for u in jo["units"] if u["unit_id"] == "T06")
    text = "\n".join(unit["issues"])
    assert "criteria not returned (left pending): T06.01" in text
    assert "criteria.T03.02: not a criterion of unit T06 (ignored)" in text
    assert "duplicate entry ignored" in text
    assert "unknown finding 'F99' ignored" in text
    assert "assertions.F2: not a finding to classify in unit T06" in text
    assert "T06.01" not in jo["criteria"] and "T03.02" not in jo["criteria"]
    assert jo["criteria"]["T06.02"]["finding_ids"] == ["F1"]
    sr_grading.merge_judge_proposals(report, jo)  # accepted by the merge


def test_schema_failure_is_repaired_once():
    sub = small_submission()
    state = {"n": 0}

    def respond(req):
        if req.unit_id == "T06" and state["n"] == 0:
            state["n"] += 1
            bad = default_response(req)
            bad["criteria"][0]["content"] = 0.75
            del bad["severe_flag_suggestions"]
            return "```json\n" + json.dumps(bad) + "\n```"
        return default_response(req)

    fake = FakeJudge(respond)
    _, result = run(sub, fake)
    t06 = [r for r in fake.calls if r.unit_id == "T06"]
    assert len(t06) == 2
    repair = t06[1].payload["messages"]
    assert [m["role"] for m in repair] == ["system", "user", "assistant", "user"]
    assert "could not be used" in repair[-1]["content"]
    assert "0.75 is not one of" in repair[-1]["content"]
    assert "missing property 'severe_flag_suggestions'" in repair[-1]["content"]
    unit = next(u for u in result.judge_output["units"] if u["unit_id"] == "T06")
    assert unit["status"] == "ok" and unit["attempts"] == 2
    assert unit["usage"]["calls"] == 2
    assert "T06.01" in result.judge_output["criteria"]


def test_schema_failure_twice_fails_the_unit_and_is_not_cached(tmp_path: Path):
    sub = small_submission()

    def respond(req):
        return "not json" if req.unit_id == "T07" else default_response(req)

    cache = JudgeCache(tmp_path)
    report, result = run(sub, FakeJudge(respond), cache)
    jo = result.judge_output
    assert jo["complete"] is False and jo["failed_units"] == ["T07"]
    unit = next(u for u in jo["units"] if u["unit_id"] == "T07")
    assert unit["status"] == "failed" and "no valid response after 2" in unit["error"]
    assert not any(c.startswith("T07.") for c in jo["criteria"])
    assert not (tmp_path / f"{unit['cache_key']}.json").exists()
    # the failed attempts still cost money
    assert result.run_log["cost_this_run"]["calls"] == len(jo["units"]) + 1
    merged = sr_grading.merge_judge_proposals(report, jo)
    assert row(merged, "T07.04")["content"]["source"] == "pending"
    # a re-run retries only the failed unit
    fake = FakeJudge()
    _, again = run(sub, fake, cache)
    assert [r.unit_id for r in fake.calls] == ["T07"]
    assert again.judge_output["complete"] is True


def test_truncated_reply_is_reported():
    sub = small_submission()
    fake = FakeJudge(lambda req: '{"criteria": [', finish_reason="length")
    _, result = run(sub, fake)
    unit = result.judge_output["units"][0]
    assert "cut off at max_output_tokens" in unit["error"]


def test_client_errors_fail_units_without_crashing():
    from environment.incident.judge import JudgeClientError

    class Broken:
        def complete(self, payload):
            raise JudgeClientError("judge API returned HTTP 503: overloaded")

    _, result = run(small_submission(), Broken())
    jo = result.judge_output
    assert jo["complete"] is False and set(jo["failed_units"]) == {
        u["unit_id"] for u in jo["units"]
    }
    assert jo["criteria"] == {} and jo["usage"]["calls"] == 0
    assert result.run_log["errors"]["T06"].startswith("judge API returned HTTP 503")


def test_cache_hits_are_free_and_reproduce_the_output(tmp_path: Path):
    sub = small_submission()
    cache = JudgeCache(tmp_path / "cache")
    first_fake = FakeJudge()
    _, first = run(sub, first_fake, cache)
    files = sorted(p.name for p in (tmp_path / "cache").iterdir())
    assert len(files) == len(first.inputs.units) == len(first_fake.calls)
    entry = json.loads((tmp_path / "cache" / files[0]).read_text())
    assert entry["key_material"]["judge_model"] == "openai/gpt-6.1-sol"
    assert entry["key_material"]["rubric_version"] == "1.0.0"
    assert set(entry["key_material"]) >= {
        "submission_sha256",
        "bundle_sha256",
        "key_sha256",
        "rubric_sha256",
        "prompt_template_sha256",
        "messages_sha256",
    }
    # a re-run never builds a client (no API key needed) and reproduces the output
    _, second = run(sub, None, cache, client_factory=no_client)
    assert second.run_log["api_calls"] == 0
    assert second.run_log["cache_hits"] == len(files)
    assert second.run_log["cost_this_run"]["cost_usd"] == 0
    dump = lambda o: json.dumps(o, sort_keys=True)  # noqa: E731
    assert dump(second.judge_output) == dump(first.judge_output)
    # cache-only with an empty cache sends nothing and fails every unit
    _, cold = run(
        sub,
        None,
        JudgeCache(tmp_path / "empty"),
        cache_only=True,
        client_factory=no_client,
    )
    assert cold.judge_output["complete"] is False
    assert all("not in the cache" in u["error"] for u in cold.judge_output["units"])


@pytest.mark.parametrize(
    "change",
    ["submission", "judge_model", "rubric", "temperature"],
)
def test_cache_misses_when_an_input_changes(tmp_path: Path, change):
    sub = small_submission()
    cache = JudgeCache(tmp_path)
    run(sub, FakeJudge(), cache)
    kwargs = {}
    if change == "submission":
        sub = small_submission(" One more sentence.")
    elif change == "judge_model":
        kwargs["cfg"] = config(judge_model="google/gemini-4-pro")
    elif change == "rubric":
        from environment.incident.judge import load_rubric
        from environment.incident.judge.prompt import Rubric

        r = load_rubric(config().rubric_path())
        kwargs["rubric"] = Rubric(r.rubric_id, "1.0.1", "f" * 64, r.text, r.path)
    else:
        kwargs["cfg"] = config(temperature=0.2)
    fake = FakeJudge()
    run(sub, fake, cache, **kwargs)
    assert len(fake.calls) > 0


def test_tampered_cache_entries_are_ignored(tmp_path: Path):
    sub = small_submission()
    cache = JudgeCache(tmp_path)
    _, first = run(sub, FakeJudge(), cache)
    path = next(tmp_path.iterdir())
    entry = json.loads(path.read_text())
    entry["key_material"]["judge_model"] = "anthropic/claude-opus-5.5"
    path.write_text(json.dumps(entry))
    fake = FakeJudge()
    run(sub, fake, cache)
    assert len(fake.calls) == 1


def test_cost_accounting(tmp_path: Path):
    sub = small_submission()

    def usage(req, chars):
        if req.unit_id == "T06":  # no provider cost: estimated from prices
            return {
                "prompt_tokens": 10_000,
                "completion_tokens": 2_000,
                "completion_tokens_details": {"reasoning_tokens": 500},
                "prompt_tokens_details": {"cached_tokens": 8_000},
            }
        return {"prompt_tokens": 1_000, "completion_tokens": 100, "cost": 0.01}

    cache = JudgeCache(tmp_path)
    _, result = run(sub, FakeJudge(usage=usage), cache)
    jo = result.judge_output
    t06 = next(u for u in jo["units"] if u["unit_id"] == "T06")
    assert t06["usage"]["cost_usd"] == pytest.approx(0.04)  # 10k*$2/M + 2k*$10/M
    assert t06["usage"]["cost_source"] == "estimated"
    assert t06["usage"]["reasoning_tokens"] == 500
    assert t06["usage"]["cached_prompt_tokens"] == 8_000
    n = len(jo["units"])
    assert jo["usage"]["calls"] == n
    assert jo["usage"]["cost_usd"] == pytest.approx(0.04 + 0.01 * (n - 1))
    assert jo["usage"]["cost_source"] == "mixed"
    assert jo["usage"]["prompt_tokens"] == 10_000 + 1_000 * (n - 1)
    assert result.run_log["cost_this_run"] == jo["usage"]
    # a cached re-run records the original cost and spends nothing
    _, again = run(sub, None, cache, client_factory=no_client)
    assert again.judge_output["usage"] == jo["usage"]
    assert again.run_log["cost_this_run"]["cost_usd"] == 0
    assert again.run_log["cost_this_run"]["calls"] == 0
    assert usage_cost({"cost": 0.5}, config()) == (0.5, "provider")
    assert usage_cost({"prompt_tokens": 1_000_000}, config()) == (2.0, "estimated")


def test_same_family_judge_is_refused_before_anything_is_sent():
    fake = FakeJudge()
    with pytest.raises(JudgeConfigError, match="evaluated model's family"):
        run(
            small_submission(),
            fake,
            cfg=config(judge_model="anthropic/claude-opus-5.5"),
        )
    assert fake.calls == []
    report, result = run(
        small_submission(),
        fake,
        cfg=config(judge_model="anthropic/claude-sonnet-5.5", allow_same_family=True),
    )
    fam = result.judge_output["family_check"]
    assert fam["same_family"] is True and fam["allow_same_family"] is True
    assert fam["run_model_family"] == "anthropic"
    assert "claude-opus" not in json.dumps(fam)


def test_report_must_belong_to_the_submission():
    from environment.incident.judge import JudgeError

    report = base_report(small_submission())
    with pytest.raises(JudgeError, match="not produced for this submission"):
        run(small_submission(" Different."), FakeJudge(), report=report)


def test_parse_response():
    good = {
        "criteria": [],
        "assertions": [],
        "report_assertions": [],
        "severe_flag_suggestions": [],
    }
    assert parse_response(json.dumps(good)) == (good, [])
    assert parse_response("Here it is:\n" + json.dumps(good) + "\nThanks")[0] == good
    assert parse_response("```json\n" + json.dumps(good) + "\n```")[0] == good
    obj, errors = parse_response(json.dumps({**good, "extra": 1}))
    assert obj is None and errors == ["$: unexpected property 'extra'"]
    assert parse_response("")[1] == ["empty response"]
    assert parse_response("[]")[1] == ["the response must be a JSON object"]
    bad = {**good, "criteria": [{"criterion_id": "T06.01", "content": True}]}
    errors = parse_response(json.dumps(bad))[1]
    assert "$.criteria[0].content: expected number" in errors
    assert any("missing property 'evidence_support'" in e for e in errors)


def test_served_model_and_binding_recorded(judged):
    _, _, report, result, _ = judged
    jo = result.judge_output
    assert jo["judge_models_served"] == [SERVED_MODEL]
    assert jo["rubric_version"] == "1.0.0" and len(jo["rubric_sha256"]) == 64
    assert jo["prompt_sha256"] == jo["prompt_template_sha256"]
    assert jo["binding"]["key_sha256"] == report["key"]["key_sha256"]
    assert jo["config"]["modes"] == ["judge", "auto_assisted_human"]


def test_concurrent_requests_give_the_same_output():
    import threading
    import time

    sub = small_submission()
    lock = threading.Lock()
    active = {"now": 0, "max": 0}

    def respond(req):
        with lock:
            active["now"] += 1
            active["max"] = max(active["max"], active["now"])
        time.sleep(0.02)
        with lock:
            active["now"] -= 1
        return default_response(req)

    made = []

    def factory():
        made.append(1)
        return FakeJudge(respond)

    _, parallel = run(sub, None, cfg=config(concurrency=3), client_factory=factory)
    _, serial = run(sub, FakeJudge(), cfg=config(concurrency=1))
    assert made == [1]  # one client for the whole submission
    assert 1 < active["max"] <= 3
    dump = lambda o: json.dumps(o, sort_keys=True)  # noqa: E731
    assert dump(parallel.judge_output) == dump(serial.judge_output)
    assert [u["unit_id"] for u in parallel.judge_output["units"]] == [
        u.unit_id for u in parallel.inputs.units
    ]


def test_low_confidence_unsupported_and_short_report_text_go_to_a_human():
    sub = small_submission()

    def respond(req):
        out = default_response(req)
        for a in out["assertions"]:
            if a["finding_id"] == "F3":
                a.update(verdict="unsupported", confidence="low")
        if req.unit_id == "T06":
            out["report_assertions"] = [
                {
                    "text": "Hornsea One",
                    "verdict": "supported",
                    "spans": [],
                    "rationale": "a name, not a claim",
                    "confidence": "high",
                },
                {
                    "text": "The DRC was cleared by the operator.",
                    "verdict": "unsupported",
                    "spans": [],
                    "rationale": "cannot see the operator's account",
                    "confidence": "low",
                },
            ]
        return out

    report, result = run(sub, FakeJudge(respond))
    jo = result.judge_output
    f3 = jo["assertions"]["F3"]
    assert f3["verdict"] is None and f3["judge_verdict"] == "unsupported"
    assert "low-confidence 'unsupported' withheld" in f3["issues"][0]
    j = jo["assertions"]["J-T06-1"]
    assert j["text"] == "The DRC was cleared by the operator." and j["verdict"] is None
    issues = next(u for u in jo["units"] if u["unit_id"] == "T06")["issues"]
    assert "report_assertions[0]: text too short to be a claim (dropped)" in issues
    merged = sr_grading.merge_judge_proposals(report, jo)
    by = {a["assertion_id"]: a for a in merged["assertion_quality"]["assertions"]}
    assert by["F3"]["source"] == "pending" and by["F3"]["judge_proposal"] is None
