"""Regression tests from the six real system-response submissions (decision 40 in
docs/DECISIONS.md; review round 2, key 0.1.1, grader 0.1.1).

The fixtures in ``tests/fixtures/sr_live`` are copied byte for byte from the two live
panels (see its README): the 80k panel (complete, judged by gpt-6.1-sol with key 0.1.0)
and the 30k panel (Opus and Sonnet incomplete on the output budget, Haiku complete; not
judged; graded here diagnostically with ``grade_submission`` and the episode's trace).

Every flag and cap that key/grader 0.1.0 raised on these runs was read against the
submission text. Confirmed false positives, now corrected:

* accounting source binding: Ofgem's figures in "Ofgem: >1,130 MW ..., about 1,500 MW
  ..., and at least 1,990 MW ..." (sonnet 80k F17; sonnet 30k F11) bound to ESO through
  the quantity basis of another number; "Ofgem's final report" / "the Ofgem final report"
  read as ESO's final report (haiku 80k F33 and its report); the 150 MW of "ESO estimate
  from the DNO data plus the 150 MW" bound to the DNOs (sonnet 30k F09); "ESO's earlier
  E3C answer" bound to the E3C (opus 30k F16); structured quantities "mismatched" by
  wording about other figures anywhere in the statement (sonnet 80k F12, F27; opus 30k
  F12; sonnet 30k F19);
* SF1 on the trip mechanism ("speed sensors after fault clearance", sonnet 80k F08),
  which also zeroed T07.01 and capped T07.04, T07.05 and T17.01;
* pre-screens that credited the wrong text (T08.04/T17.02 "cause ... unknown" about
  Little Barford; T12.03 Hornsea's "insufficiently damped ... response"; T02.06 Ofgem's
  892 MW net demand; T09.04 a denominator as non-equivalence; T06.02 without saying which
  side behaved as expected) or missed the expectation's alternatives (T05.03 demand
  scoped to DNO demand; T09.03 a labelled hypothesis; T05.01b the end of an instruction
  window whose start is the finding's event time);
* labelling flags on measurement caveats and reported hypotheses, and inferential flags
  on a source's simulation "suggests" and a passive "was attributed to".

True positives still fire: the remaining labelling and inferential flags, and the
mutations of the real texts at the end of this file.

An independent check of round 2 (same key and grader version, nothing released in
between; docs/DECISIONS.md, "SR grader corrections from real submissions") found
binding rules that crossed clauses (a reporting-verb list running past ", whereas" or
", and <new clause>", a later figure's source borrowed through "below"), a bare "final
report" read as ESO's, an SF1 sensor trigger that missed plain assertions, and
pre-screens that missed real text (T12.03 "with all response delivered", T08.05 "differ
by stage" and a total written as its parts, T09.04 "peak forecast demand", T12.02's
exceedance in the report). Its mutations of the real texts are asserted below.
"""

from __future__ import annotations

import copy
import functools
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from environment.incident import grading as mvp
from environment.incident import sr_grading
from environment.incident.catalogue import Catalogue
from environment.incident.judge.config import load_config
from environment.incident.judge.prompt import build_units, load_rubric
from environment.incident.paths import SYSTEM_RESPONSE_BUNDLE_DIR

ENV_ROOT = Path(__file__).resolve().parents[1]
LIVE = ENV_ROOT / "tests" / "fixtures" / "sr_live"
MANIFEST = json.loads((LIVE / "runs.json").read_text(encoding="utf-8"))
RUNS = {run["run_id"]: run for run in MANIFEST["runs"]}
JUDGED = sorted(r for r, run in RUNS.items() if run["judged"])
KEY = sr_grading.load_key()
CAT = Catalogue.load(SYSTEM_RESPONSE_BUNDLE_DIR)


def rebound(judge: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """The judge output (produced with key 0.1.0) bound to the graded key. Allowed
    because key 0.1.1 changed no judge-visible content (checked below through the
    request messages), so the proposals are what the judge would propose now."""
    out = copy.deepcopy(judge)
    out["binding"] = {
        "submission_sha256": report["submission"]["sha256"],
        "key_version": report["key"]["key_version"],
        "key_sha256": report["key"]["key_sha256"],
        "bundle_sha256": report["bundle"]["bundle_sha256"],
    }
    return out


def summary(run_id: str) -> dict[str, Any]:
    return json.loads((LIVE / run_id / "run_summary.json").read_text(encoding="utf-8"))


def submission_text(run_id: str) -> str:
    return (LIVE / run_id / "submission.json").read_text(encoding="utf-8")


@functools.cache
def trace_info(run_id: str) -> dict[str, Any]:
    return sr_grading.trace_info_from_episode(LIVE / run_id)


@functools.cache
def base(run_id: str) -> dict[str, Any]:
    """The automated grade the judge track starts from (no judge layer)."""
    return sr_grading.grade_episode(
        LIVE / run_id, summary(run_id), key=KEY, catalogue=CAT
    )


@functools.cache
def graded(run_id: str) -> dict[str, Any]:
    """The 80k runs with their judge output merged; the 30k runs diagnostically."""
    if RUNS[run_id]["judged"]:
        judge = json.loads(
            (LIVE / run_id / "judge_output.json").read_text(encoding="utf-8")
        )
        return sr_grading.grade_episode(
            LIVE / run_id,
            summary(run_id),
            key=KEY,
            catalogue=CAT,
            judge_output=rebound(judge, base(run_id)),
        )
    return sr_grading.grade_submission(
        submission_text(run_id), CAT, KEY, trace_info(run_id)
    )


def rows(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["criterion_id"]: c for c in report["criteria"]}


def mentions(report: dict[str, Any], location: str) -> list[tuple]:
    return [
        (m["figure_id"], m["field"], m["bound_source"], m["classification"])
        for m in report["accounting_basis"]["mentions"]
        if m["location"] == location
    ]


def best_available(row: dict[str, Any]) -> float | None:
    """Decided values, judge proposals for judge-mode criteria (after caps), else the
    automated pre-screen or proposal."""
    content = row["content"]
    if content["source"] in ("auto", "human", "severe_flag", "judge"):
        return content["value"]
    return content["auto_proposal"]


# -- the fixtures are the real runs --------------------------------------------------------
@pytest.mark.parametrize("run_id", sorted(RUNS))
def test_fixtures_are_the_real_runs(run_id):
    run = RUNS[run_id]
    for name, digest in run["files"].items():
        data = (LIVE / run_id / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, name
    state = json.loads((LIVE / run_id / "state.json").read_text(encoding="utf-8"))
    assert state["submission_sha256"] == run["submission_sha256"]
    assert graded(run_id)["submission"]["sha256"] == run["submission_sha256"]
    assert run["bundle_sha256"] == CAT.bundle_sha256 == KEY["bundle"]["bundle_sha256"]
    if run["judged"]:
        assert run["judge_binding"]["key_version"] == "0.1.0"
        assert run["judge_binding"]["submission_sha256"] == run["submission_sha256"]


def test_manifest_records_the_key_and_grader_it_was_graded_with():
    assert MANIFEST["graded_with"] == {
        "key_version": KEY["key_version"],
        "key_sha256": sr_grading.key_sha256(KEY),
        "grader_version": sr_grading.GRADER_VERSION,
    }


@pytest.mark.parametrize(
    ("run_id", "outcome"),
    [
        ("sr80k-opus55-001", "complete"),
        ("sr80k-sonnet55-001", "complete"),
        ("sr80k-haiku45-001", "complete"),
        ("sr30k-opus55-001", "incomplete_submission"),
        ("sr30k-sonnet55-001", "incomplete_submission"),
        ("sr30k-haiku45-001", "complete"),
    ],
)
def test_run_outcomes_under_their_own_budgets(run_id, outcome):
    report = base(run_id)
    assert report["run"]["outcome"] == outcome == RUNS[run_id]["outcome"]
    if outcome != "complete":
        assert report["run"]["incomplete_reason"] == "output_token_budget_exhausted"
        assert report["criteria"] == []  # no measures for incomplete runs


@pytest.mark.parametrize("run_id", JUDGED)
def test_the_judge_saw_the_same_criteria_under_the_revised_key(run_id):
    """Key 0.1.1 changed no judge-visible text: a unit's request differs only where a
    finding is now classified under another task (the automated task assignment
    changed with the corrected pre-screens and severe flag)."""
    config = load_config(None)
    sub, _ = mvp._as_submission(submission_text(run_id), CAT)
    inputs = build_units(
        sub,
        base(run_id),
        KEY,
        CAT,
        config,
        load_rubric(config.rubric_path()),
        blind_terms=[RUNS[run_id]["model"]],
    )
    judge = json.loads((LIVE / run_id / "judge_output.json").read_text())
    recorded = {u["unit_id"]: u for u in judge["units"]}
    assert {u.unit_id for u in inputs.units} <= set(recorded)
    changed = []
    for unit in inputs.units:
        then = recorded[unit.unit_id]
        assert unit.criterion_ids == then["criteria"], unit.unit_id
        if unit.messages_sha256 != then["messages_sha256"]:
            assert unit.finding_ids != then["findings_classified"], unit.unit_id
            changed.append(unit.unit_id)
    assert (
        changed
        == {
            "sr80k-opus55-001": [],
            # F11 ("ESO estimate: 150 vector shift + 350 RoCoF" for 500 MW) now meets
            # the T08.05 pre-screen, so it is classified under T08
            "sr80k-sonnet55-001": ["T02", "T07", "T08", "T17"],
            "sr80k-haiku45-001": ["T02", "T09"],
        }[run_id]
    )


# -- confirmed false positives are gone ------------------------------------------------------
@pytest.mark.parametrize("run_id", sorted(RUNS))
def test_no_false_accounting_traps_severe_flags_or_caps(run_id):
    report = graded(run_id)
    assert report["flags"]["accounting_traps"] == []
    assert report["severe_flags"] == []  # SF1 (sonnet 80k F08) was the only one
    assert [
        (r["criterion_id"], c["id"])
        for r in report["criteria"]
        for c in r["layers"]["caps"]
    ] == []


@pytest.mark.parametrize(
    ("run_id", "location", "expected"),
    [
        (
            "sr80k-sonnet55-001",
            "F17",
            {
                ("GEN_1131", "statement", "ofgem", "attributed"),
                ("GEN_OFG_1500", "statement", "ofgem", "attributed"),
                ("GEN_OFG_1990", "statement", "ofgem", "attributed"),
            },
        ),
        (
            "sr80k-sonnet55-001",
            "F27",
            {
                ("LFDD_931", "statement", "eso_final", "attributed"),
                ("LFDD_OFG_892", "statement", "ofgem", "attributed"),
                ("LFDD_931", "quantity", "eso_final", "attributed"),
            },
        ),
        (
            "sr80k-sonnet55-001",
            "F12",
            {("DG_49HZ_200", "quantity", "eso", "attributed")},
        ),
        (
            "sr80k-haiku45-001",
            "F33",
            {
                ("LFDD_OFG_892", "statement", "ofgem", "attributed"),
                ("LFDD_OFG_892", "quantity", "ofgem", "attributed"),
            },
        ),
        (
            "sr80k-haiku45-001",
            "report.sections[4].body",
            {
                ("LFDD_931", "report", "eso_final", "attributed"),
                ("LFDD_E3CI_973", "report", "e3c_interim", "attributed"),
                ("LFDD_OFG_892", "report", "ofgem", "attributed"),
            },
        ),
        (
            "sr30k-opus55-001",
            "F12",
            {("GEN_ESO_1878", "quantity", "eso", "attributed")},
        ),
        (
            "sr30k-opus55-001",
            "F16",
            {
                ("RESP_SECONDARY_1314", "statement", "eso_final", "attributed"),
                ("RESP_SECONDARY_1338", "statement", "eso_earlier", "attributed"),
            },
        ),
        (
            "sr30k-sonnet55-001",
            "F09",
            {("DG_VS_150", "statement", "eso", "attributed")},
        ),
        (
            "sr30k-sonnet55-001",
            "F11",
            {
                ("GEN_OFG_1500", "statement", "ofgem", "attributed"),
                ("GEN_OFG_1990", "statement", "ofgem", "attributed"),
            },
        ),
        (
            "sr30k-sonnet55-001",
            "F19",
            {("LFDD_931", "quantity", "eso_final", "attributed")},
        ),
    ],
)
def test_figures_are_bound_to_their_nearest_attribution(run_id, location, expected):
    assert expected <= set(mentions(graded(run_id), location))


def test_sf1_no_longer_fires_on_the_speed_sensor_mechanism():
    report = graded("sr80k-sonnet55-001")
    by_id = rows(report)
    # T07.01 credits the mechanism F08 states; the judge's values are no longer capped
    assert by_id["T07.01"]["content"]["auto_proposal"] == 1
    for cid, value in (("T07.04", 0.5), ("T07.05", 1), ("T17.01", 0.5)):
        assert by_id[cid]["content"]["source"] == "judge"
        assert by_id[cid]["content"]["value"] == by_id[cid]["content"]["judge_proposal"]
        assert by_id[cid]["content"]["value"] == value, cid


# -- corrected criterion outcomes ----------------------------------------------------------
# criterion: (automated proposal or pre-screen, value shown: judge proposal or None)
EXPECTED: dict[str, dict[str, tuple[float, float | None]]] = {
    "sr80k-opus55-001": {
        "T05.01b": (1, None),  # was 0: the end of the 16:58-17:16 window (F31)
        "T05.03": (1, 1),  # was 0.5: restoration scoped to DNO demand (F34)
        "T08.04": (0.5, 0.5),  # was 1 via Little Barford "cause ... unknown"
        "T09.03": (1, 1),  # was 0.5: F39 is labelled hypothesis
        "T09.04": (0.5, 0.5),  # was 1: "3.2% of 29 GW" is not non-equivalence
        "T12.02": (1, None),  # was 0.5: "well beyond the secured level" (report)
        "T12.03": (0.5, 0.5),  # was 1 via Hornsea's "insufficiently damped"
        "T17.03": (1, 0.5),  # disagreement kept: the summary puts 100 MW at 49 Hz
    },
    "sr80k-sonnet55-001": {
        "T02.06": (1, 1),  # was 0: F17 misattribution (cap zero)
        "T07.01": (1, None),  # was 0: F08 was suspected SF1
        "T07.04": (0.5, 0.5),  # was 0 (SF1)
        "T07.05": (1, 1),  # was 0 (SF1)
        "T09.04": (0.5, 0.5),
        "T12.02": (1, None),  # was 0.5: F17 misattribution (cap half)
        "T12.03": (0.5, 0.5),
        "T17.01": (0.5, 0.5),  # was 0 (SF1)
    },
    "sr80k-haiku45-001": {
        "T02.06": (0, 0),  # was 0.5 via Ofgem's 892 MW net demand
        "T05.01b": (1, None),  # was 0 (F37, event_time 16:58)
        "T05.03": (0.5, 1),  # disagreement kept (borderline: judge decides)
        "T06.01": (0.5, 1),  # disagreement kept (borderline: judge decides)
        "T06.02": (0.5, 0.5),  # was 1: which side behaved as expected not said
        "T08.04": (0, 0),
        "T09.02b": (1, None),  # 892 MW attributed to Ofgem (was a misattribution flag)
        "T09.04": (0, 0),
        "T12.03": (0.5, 0.5),
        "T17.02": (0, 0),
    },
    "sr30k-opus55-001": {
        "T02.06": (1, None),  # was 0: F12 quantity "mismatched" (cap zero)
        "T08.04": (1, None),  # the RoCoF/vector-shift split depends on modelling
        "T08.05": (1, None),  # was 0: F14 "differ by stage", F10 500 = 150 + 350
        "T09.04": (0.5, None),
        "T12.01c": (0.5, None),  # no longer capped (F16), still no 30 s band
        "T12.03": (0.5, None),
    },
    "sr30k-sonnet55-001": {
        "T02.06": (1, None),  # was 0: F11 misattribution (cap zero)
        "T05.01b": (1, None),  # was 0 (F21, event_time 17:37)
        "T08.05": (1, None),  # was 0: F09's basis gives 500 as 150 + 350
        # was 0.5 via "29 GW", then 0: F20 "the 5% is based on peak forecast demand"
        # (still equated with 3.2%, so not full)
        "T09.04": (0.5, None),
        "T12.02": (1, None),  # was 0.5 (cap)
        "T12.03": (1, None),  # F16 "with all response delivered at 16:53:31"
    },
    "sr30k-haiku45-001": {
        "T02.06": (0, None),
        "T03.01": (0, None),  # genuine omission: 49.1 Hz at 16:52:58 is ESO's prose
        "T08.04": (0.5, None),  # "no ... embedded generation telemetry"
        "T09.04": (0.5, None),
        "T12.03": (0.5, None),
        "T17.02": (0, None),
    },
}


@pytest.mark.parametrize(
    ("run_id", "cid"), [(r, c) for r in EXPECTED for c in EXPECTED[r]]
)
def test_corrected_criterion_outcomes(run_id, cid):
    auto, shown = EXPECTED[run_id][cid]
    row = rows(graded(run_id))[cid]
    assert row["content"]["auto_proposal"] == auto, row["layers"]["auto"]["basis"]
    if shown is not None:
        assert row["content"]["source"] == "judge"
        assert row["content"]["value"] == shown


@pytest.mark.parametrize(
    ("run_id", "disagreements"),
    [
        ("sr80k-opus55-001", ["T17.03"]),
        ("sr80k-sonnet55-001", []),
        ("sr80k-haiku45-001", ["T05.03", "T06.01"]),
    ],
)
def test_remaining_judge_prescreen_disagreements(run_id, disagreements):
    """Before: opus 6, sonnet 6, haiku 8. The rest were pre-screen errors."""
    got = [
        r["criterion_id"]
        for r in graded(run_id)["criteria"]
        if r["assessment_mode"] == "judge"
        and r["content"]["judge_proposal"] is not None
        and r["content"]["judge_proposal"] != r["content"]["auto_proposal"]
    ]
    assert got == disagreements


@pytest.mark.parametrize(
    ("run_id", "counts"),
    [
        # key/grader 0.1.0, then round 2, then its verification
        ("sr80k-opus55-001", (49, 9, 2)),  # 47/10/3, 48/10/2
        ("sr80k-sonnet55-001", (52, 8, 0)),  # 48/7/5, 52/8/0
        ("sr80k-haiku45-001", (29, 10, 21)),  # 28/10/22, 29/10/21
        ("sr30k-opus55-001", (52, 7, 1)),  # 52/5/3, 51/7/2
        ("sr30k-sonnet55-001", (54, 6, 0)),  # 50/7/3, 52/6/2
        ("sr30k-haiku45-001", (27, 13, 20)),  # 29/13/18, 27/13/20
    ],
)
def test_best_available_content_counts(run_id, counts):
    values = Counter(best_available(r) for r in graded(run_id)["criteria"])
    assert (values[1], values[0.5], values[0]) == counts


# -- flags: true positives kept, false positives gone -----------------------------------
@pytest.mark.parametrize(
    ("run_id", "labelling", "inferential"),
    [
        (
            "sr80k-opus55-001",
            [],
            ["F35"],
        ),  # F44/F45 reported hypotheses; F09 simulation
        ("sr80k-sonnet55-001", ["F12", "F23"], ["F19", "F23"]),  # F08/F18/F33; F11
        ("sr80k-haiku45-001", [], []),
        ("sr30k-opus55-001", [], ["F03"]),
        ("sr30k-sonnet55-001", [], ["F02", "F04", "F29"]),  # F14/F24; F09
        ("sr30k-haiku45-001", [], ["F15"]),  # F12 passive attribution; F30 DNO posts
    ],
)
def test_labelling_and_inferential_flags(run_id, labelling, inferential):
    flags = graded(run_id)["flags"]
    assert [f["finding_id"] for f in flags["labelling"]] == labelling
    assert [
        f["finding_id"] for f in flags["status_inferential_language"]
    ] == inferential


# -- true positives still fire on the real texts -------------------------------------------
def mutated(run_id: str, fid: str, old: str, new: str, field: str = "statement"):
    sub = json.loads(submission_text(run_id))
    finding = next(f for f in sub["findings"] if f["finding_id"] == fid)
    if field == "quantity.basis":
        assert old in finding["quantity"]["basis"]
        finding["quantity"]["basis"] = finding["quantity"]["basis"].replace(old, new)
    else:
        assert old in finding[field]
        finding[field] = finding[field].replace(old, new)
    return sr_grading.grade_submission(sub, CAT, KEY, trace_info(run_id))


def test_ofgem_figures_given_as_esos_still_trap():
    report = mutated("sr80k-sonnet55-001", "F17", "Ofgem: >1,130 MW", "ESO: >1,130 MW")
    found = {(t["type"], t["figure_id"]) for t in report["flags"]["accounting_traps"]}
    assert found == {
        ("misattributed", "GEN_OFG_1500"),
        ("misattributed", "GEN_OFG_1990"),
    }
    caps = {c["id"] for c in rows(report)["T02.06"]["layers"]["caps"]}
    assert caps == {"ofgem_1990_on_wrong_basis"}
    assert rows(report)["T02.06"]["content"]["auto_proposal"] == 0


def test_ofgem_892_given_as_esos_final_report_still_traps():
    report = mutated(
        "sr80k-haiku45-001", "F33", "Ofgem's final report", "ESO's final report"
    )
    traps = [
        (t["type"], t["figure_id"], t["bound_source"])
        for t in report["flags"]["accounting_traps"]
    ]
    assert ("misattributed", "LFDD_OFG_892", "eso_final") in traps


def test_secondary_holding_on_the_other_account_still_caps():
    report = mutated(
        "sr30k-opus55-001",
        "F16",
        "ESO's earlier E3C answer gives 1,338 MW",
        "ESO's Table 3 gives 1,338 MW",
    )
    caps = {c["id"] for c in rows(report)["T12.01c"]["layers"]["caps"]}
    assert caps == {"secondary_on_wrong_account"}


def test_vector_shift_estimate_given_as_the_dnos_still_traps():
    report = mutated(
        "sr30k-sonnet55-001",
        "F09",
        "about 150 MW on vector shift (ESO estimate,",
        "about 150 MW on vector shift (DNO returns,",
    )
    traps = {(t["type"], t["figure_id"]) for t in report["flags"]["accounting_traps"]}
    assert ("misattributed", "DG_VS_150") in traps


def test_a_quantity_basis_on_the_wrong_definition_still_traps():
    report = mutated(
        "sr80k-sonnet55-001",
        "F27",
        "ESO Table 6 sum of DNO areas (gross, reported)",
        "Ofgem net demand",
        field="quantity.basis",
    )
    assert (
        "LFDD_931",
        "quantity",
        "ofgem",
        "mismatched",
    ) in mentions(report, "F27")


def test_an_asserted_little_barford_root_cause_still_raises_sf1():
    report = mutated(
        "sr80k-sonnet55-001",
        "F08",
        "exceeding the control-system tolerance.",
        "exceeding the control-system tolerance. The root cause was a failed speed "
        "sensor.",
    )
    assert [(s["flag_id"], s["finding_id"]) for s in report["severe_flags"]] == [
        ("SF1", "F08")
    ]
    by_id = rows(report)
    for cid in ("T07.04", "T07.05", "T17.01"):
        assert by_id[cid]["content"]["auto_proposal"] == 0, cid
        assert any(
            c["kind"] == "severe_suspected" for c in by_id[cid]["layers"]["caps"]
        )


# -- verification of round 2: mutations of the real texts -----------------------------------
OPUS_F12 = "Ofgem gives more than 1,130 MW within about 1 s"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        # a correct clause after ", whereas" is not inside Ofgem's list
        (
            "and at least 1,990 MW after GT1A plus the 200 MW at 49 Hz.",
            "and at least 1,990 MW after GT1A plus the 200 MW at 49 Hz, whereas 1,878 MW "
            "is the six-component cumulative total through GT1B.",
        ),
        (
            "and at least 1,990 MW after GT1A plus the 200 MW at 49 Hz.",
            "and at least 1,990 MW after GT1A plus the 200 MW at 49 Hz, and 1,878 MW is "
            "the cumulative total through GT1B.",
        ),
        # Ofgem's own final report, in natural phrasings
        (
            OPUS_F12,
            "Ofgem, in its final report, gives more than 1,130 MW within about 1 s",
        ),
        (
            OPUS_F12,
            "In its final report Ofgem gives more than 1,130 MW within about 1 s",
        ),
        (
            OPUS_F12,
            "Ofgem's January 2020 final report gives more than 1,130 MW within about 1 s",
        ),
    ],
)
def test_correct_rewordings_of_a_real_text_do_not_trap(old, new):
    report = mutated("sr80k-opus55-001", "F12", old, new)
    assert report["flags"]["accounting_traps"] == []
    t0206 = rows(report)["T02.06"]
    assert t0206["layers"]["caps"] == []
    assert t0206["content"]["auto_proposal"] == 1


def test_esos_name_on_ofgems_figures_still_traps_through_its_final_report():
    report = mutated(
        "sr80k-opus55-001",
        "F12",
        OPUS_F12,
        "In its final report ESO gives more than 1,130 MW within about 1 s",
    )
    found = {
        (t["figure_id"], t["bound_source"]) for t in report["flags"]["accounting_traps"]
    }
    assert found == {("GEN_OFG_1500", "eso_final"), ("GEN_OFG_1990", "eso_final")}
    assert rows(report)["T02.06"]["content"]["auto_proposal"] == 0


def test_ofgem_in_its_final_report_keeps_the_892_mw():
    report = mutated(
        "sr80k-haiku45-001",
        "F33",
        "Ofgem's final report (3 January 2020) reported",
        "Ofgem, in its final report (3 January 2020), reported",
    )
    assert report["flags"]["accounting_traps"] == []
    assert ("LFDD_OFG_892", "statement", "ofgem", "attributed") in mentions(
        report, "F33"
    )
    assert rows(report)["T09.02b"]["content"]["auto_proposal"] == 1


OPUS_F07 = (
    "RWE attributes the trip to a discrepancy between the turbine's speed signals after "
    "the fault was cleared."
)


@pytest.mark.parametrize(
    "assertion",
    [
        "A speed sensor on ST1C failed, and this caused the trip.",
        "The trip was caused by a speed sensor that had developed a fault.",
        "One of its speed sensors suffered a failure, which caused the trip.",
        "A failure of one speed sensor tripped the steam turbine.",
        "A fault in a speed sensor caused the ST1C trip.",
        "The transmission fault caused the speed-signal discrepancy that tripped ST1C.",
        "The transmission fault caused the speed-signal discrepancy that tripped it.",
    ],
)
def test_plainly_asserted_root_causes_raise_sf1(assertion):
    """Without "root cause" wording (the earlier regression test used it, which another
    trigger catches)."""
    report = mutated("sr80k-opus55-001", "F07", OPUS_F07, assertion)
    assert [(s["flag_id"], s["finding_id"]) for s in report["severe_flags"]] == [
        ("SF1", "F07")
    ]
    by_id = rows(report)
    for cid in ("T07.04", "T07.05", "T17.01"):
        assert by_id[cid]["content"]["auto_proposal"] == 0, cid


@pytest.mark.parametrize(
    "mechanism",
    [
        "RWE says the three speed sensors failed to agree after the fault was cleared.",
        "ST1C tripped when its speed sensors disagreed following the transmission fault.",
    ],
)
def test_the_speed_sensor_mechanism_does_not_raise_sf1(mechanism):
    report = mutated("sr80k-opus55-001", "F07", OPUS_F07, mechanism)
    assert report["severe_flags"] == []


def test_response_delivered_without_an_auxiliary_is_exhaustion():
    """sr30k-sonnet55-001 F16 paraphrases ESO's 16:53:31 entry "All frequency response
    is being delivered at this point"."""
    row = rows(graded("sr30k-sonnet55-001"))["T12.03"]
    element = next(
        e for e in row["auto_checks"]["elements"] if e["id"] == "response_exhausted"
    )
    assert element["level"] == 1 and "F16" in element["finding_ids"]


def test_the_exceedance_stated_in_the_report_counts_for_t1202():
    row = rows(graded("sr80k-opus55-001"))["T12.02"]
    element = next(
        e for e in row["auto_checks"]["elements"] if e["id"] == "exceeds_secured_report"
    )
    assert element["level"] == 1
    assert element["detail"]["report_locations"]
