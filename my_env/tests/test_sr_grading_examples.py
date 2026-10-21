"""The key's positive and negative examples behave as the key says, the severe-flag
examples fire (and the non-examples do not), and an oracle built from the positive
examples earns every automated proposal."""

from __future__ import annotations

import pytest
from sr_grading_support import (
    catalogue,
    example_submission,
    finding,
    grade,
    key,
    oracle_submission,
    row,
    submission,
)

KEY = key()
EXAMPLES = [
    (crit["criterion_id"], kind, i, ex)
    for crit in KEY["criteria"]
    for kind in ("positive", "negative")
    for i, ex in enumerate(crit["examples"][kind])
    if (
        ex.get("prescreen") if crit["assessment_mode"] == "judge" else ex.get("content")
    )
    is not None
]
BY_ID = {c["criterion_id"]: c for c in KEY["criteria"]}


@pytest.mark.parametrize(
    ("cid", "kind", "index", "example"),
    EXAMPLES,
    ids=[f"{c}-{k}-{i}" for c, k, i, _ in EXAMPLES],
)
def test_key_examples_agree_with_the_automated_proposal(cid, kind, index, example):
    """auto_numeric and auto_assisted_human examples: the automated proposal is the
    example's content. judge examples: the automated pre-screen is its 'prescreen'
    (the content is the value the judge and reviewer should reach)."""
    crit = BY_ID[cid]
    report = grade(example_submission(crit, example))
    got = row(report, cid)["content"]["auto_proposal"]
    want = (
        example["prescreen"]
        if crit["assessment_mode"] == "judge"
        else example["content"]
    )
    assert got == want, (
        cid,
        example.get("statement") or example.get("findings"),
        row(report, cid)["content"]["basis"],
    )


def test_every_criterion_has_checked_positive_and_negative_examples():
    checked = {(c, k) for c, k, _, _ in EXAMPLES}
    for cid in BY_ID:
        assert (cid, "positive") in checked and (cid, "negative") in checked, cid
    for crit in KEY["criteria"]:
        if crit["assessment_mode"] == "judge":
            for kind in ("positive", "negative"):
                for ex in crit["examples"][kind]:
                    assert ex.get("content") in (0, 0.5, 1, None)


FLAG_CASES = [
    (flag["flag_id"], text, fires)
    for flag in KEY["severe_flags"]
    for fires, texts in ((True, flag["examples"]), (False, flag["non_examples"]))
    for text in texts
]


@pytest.mark.parametrize(("flag_id", "text", "fires"), FLAG_CASES)
def test_severe_flag_examples(flag_id, text, fires):
    report = grade(submission([finding("F1", text, "reported", [("S04", "L56-L59")])]))
    hits = [s for s in report["severe_flags"] if s["flag_id"] == flag_id]
    assert bool(hits) == fires, (flag_id, text, hits)
    if fires:
        assert all(h["confirmed"] is None and h["source"] == "pending" for h in hits)
        assert any(
            a["auto_proposal"] == "unsupported"
            for a in report["assertion_quality"]["assertions"]
        )


def test_severe_flag_in_report_text_is_located():
    report = grade(
        submission(
            [
                finding(
                    "F1",
                    "Little Barford lost three units.",
                    "reported",
                    [("S03", "L34-L37")],
                )
            ],
            report="Ofgem fined the operators £10.5m in redress payments.",
        )
    )
    hits = [s for s in report["severe_flags"] if s["flag_id"] == "SF3"]
    assert hits and hits[0]["location"].startswith("report.sections")
    assert hits[0]["finding_id"] is None


def test_oracle_earns_every_automated_proposal():
    report = grade(oracle_submission())
    low = {
        r["criterion_id"]: (r["content"]["auto_proposal"], r["content"]["basis"])
        for r in report["criteria"]
        if r["content"]["auto_proposal"] != 1
    }
    assert low == {}
    assert report["flags"]["accounting_traps"] == []
    assert report["severe_flags"] == []
    # auto_numeric criteria are decided; everything else waits for a judge or a human
    decided = {
        r["criterion_id"]
        for r in report["criteria"]
        if r["content"]["source"] == "auto"
    }
    assert decided == {"T03.02"} | (decided & {"T03.01", "T03.03", "T04.01"})
    assert report["status"] == "provisional"
    assert "no pass threshold" in report["interpretation"].lower()


def test_oracle_evidence_proposals_target_keyed_spans():
    report = grade(oracle_submission())
    for r in report["criteria"]:
        if r["assessment_mode"] in ("auto_numeric",):
            continue
        assert r["evidence_support"]["auto_proposal"] == 1, (
            r["criterion_id"],
            r["evidence_support"],
        )


def test_examples_cite_resolvable_evidence():
    cat = catalogue()
    for crit in KEY["criteria"]:
        keyed = crit["visible_evidence"][0]
        target = cat.citation_target(keyed["evidence_id"])
        assert target is not None, crit["criterion_id"]


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("The S02 modelling note shows the controllers were unstable.", "S02"),
        ("Control-room entry S07-E14 records the secured loss.", "S07-E14"),
        ("Witness answer S09-ESO-99 says so.", "S09-ESO-99"),
    ],
)
def test_invented_records_are_flagged(text, match):
    report = grade(submission([finding("F1", text, "reported", [("S07", "L16-L17")])]))
    hits = [s for s in report["severe_flags"] if s["flag_id"] == "SF2"]
    assert [h["match"] for h in hits] == [match]


@pytest.mark.parametrize(
    "text",
    [
        "S03-E7 and S03 E9 give the GT1A and GT1B breaker feedback offsets.",
        "Records R01-R10 and S01-S12 were reviewed; S09 holds the witness answers.",
        "Entry R06-BOALF-T_GRAI-6-60050 and event R03-C5 were cited.",
    ],
)
def test_real_or_label_like_references_are_not_flagged(text):
    report = grade(submission([finding("F1", text, "reported", [("S07", "L16-L17")])]))
    assert [s for s in report["severe_flags"] if s["flag_id"] == "SF2"] == []
