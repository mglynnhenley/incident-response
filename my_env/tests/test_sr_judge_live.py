"""The judge pipeline on real model output (the live MVP submissions, which cite
documents the system-response bundle also holds) and on the key's oracle, with a
mocked client: every request builds, blinds and verifies, every factual finding is
classified exactly once, and the merge accepts the result."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sr_grading_support import catalogue, key, oracle_submission
from sr_judge_support import FakeJudge

from environment.incident import sr_grading
from environment.incident.judge import JudgeConfig, judge_submission

LIVE = Path(__file__).resolve().parent / "fixtures" / "live"
SUBMISSIONS = sorted(LIVE.glob("gb2019-v2-*.submission.json"))
RUN_MODELS = {
    "opus55": "openrouter/anthropic/claude-opus-5.5",
    "sonnet55": "openrouter/anthropic/claude-sonnet-5.5",
    "haiku45": "openrouter/anthropic/claude-haiku-4.5",
}


def _judge(sub, run_model):
    report = sr_grading.grade_submission(sub, catalogue(), key())
    fake = FakeJudge()
    result = judge_submission(
        sub,
        report,
        key=key(),
        catalogue=catalogue(),
        config=JudgeConfig(),
        run_model=run_model,
        client=fake,
    )
    return report, fake, result


@pytest.mark.parametrize(
    "path", SUBMISSIONS, ids=[p.name.split(".")[0] for p in SUBMISSIONS]
)
def test_live_submissions_go_through_the_judge(path):
    sub = json.loads(path.read_text(encoding="utf-8"))
    run_model = next(m for k, m in RUN_MODELS.items() if k in path.name)
    report, fake, result = _judge(sub, run_model)
    jo = result.judge_output
    assert jo["complete"] is True
    factual = [
        f["finding_id"]
        for f in sub["findings"]
        if f["status"] in ("observed", "reported", "inferred")
    ]
    classified = [f for r in fake.calls for f in r.findings]
    assert sorted(classified) == sorted(factual)
    assert set(jo["assertions"]) == set(factual)
    # the fake quotes only text it was shown: nothing is rejected
    assert jo["span_checks"]["rejected"] == 0
    assert jo["span_checks"]["verified"] > 0
    sent = json.dumps([c.payload for c in fake.calls]).lower()
    for word in ("claude", "anthropic", "opus", "sonnet", "haiku"):
        assert word not in sent
    merged = sr_grading.merge_judge_proposals(report, jo)
    assert sorted(merged["judge"]["criteria_applied"]) == sorted(
        key()["judge"]["criteria"]
    )
    assert merged["status"] == "provisional"
    # the judge never decides numeric criteria
    for r in merged["criteria"]:
        if r["assessment_mode"] == "auto_numeric":
            assert r["layers"]["judge"] is None
            assert r["content"]["source"] != "judge"


def test_oracle_through_the_judge():
    sub = oracle_submission()
    report, fake, result = _judge(sub, RUN_MODELS["opus55"])
    jo = result.judge_output
    assert jo["complete"] is True and jo["span_checks"]["rejected"] == 0
    assert len(fake.calls) == len(result.inputs.units) == 12
    merged = sr_grading.merge_judge_proposals(report, jo)
    by_source = {}
    for r in merged["criteria"]:
        by_source.setdefault(r["content"]["source"], set()).add(r["assessment_mode"])
    assert by_source["judge"] == {"judge"}
    assert "auto_numeric" not in by_source.get("judge", set())
