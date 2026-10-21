"""Real submissions graded with the full-investigation key: the regression discipline
of decisions 18, 27 and 40-48.

Part 1: increment A's six real submissions (tests/fixtures/sr_live), before any
full-investigation run existed.

* The 60 re-bound criteria give increment A's automated results on the real texts
  (content and evidence proposals, decided values, matched findings), and the flags,
  accounting traps and severe flags are unchanged, except the differences key 0.1.1
  (decision 77) makes and this file lists (``FI_DIFFERENCES``, ``FI_MENTIONS``).
* The new criteria's pre-screens were read against the same texts: real phrasing found
  false negatives (EPN/SPN "reconnected sites without ESO instruction") and false
  positives (Ofgem's 200 MW at 49 Hz "net of ... trains" read as the rail threshold;
  "setting" read as rail "sets"; "dno reports" as "no reports"; a requirement "DNOs
  to notify" read as a recommendation; "before ESO was informed" read as a
  communications issue), all fixed in key 0.1.0 and pinned here.

Part 2: the two real full-investigation runs (tests/fixtures/fi_live: the Opus 5.5
pilot and first panel run, both judged by gpt-6.1-sol with key 0.1.0), swept in key
0.1.1 (decision 77): every flag, cap, automated decision and judge/pre-screen
disagreement was read against the submissions and the keyed evidence.

* Confirmed false positives, gone: SF1 on the panel run's F38 ("allowed to reconnect
  before the root cause was found") and executive summary ("the root causes are
  unestablished"), which zeroed T07.04, T07.05, T14.02, T17.01, T20.03 and T20.06 (and
  excluded F38 from T14.05's credit); the 'misattributed' DG_LOM_500 trap on F10 (its
  quantity basis "ESO estimate from transformer-flow changes (150 VS + 350 RoCoF)" was
  bound to the DNOs of the next sentence); labelling flags on "as soon as possible"
  and a prohibition "may not restore ... without ESO instruction".
* Confirmed false negatives, fixed: T08.02/T08.03 (figures in F11, a finding labelled
  unknown for other causes), T10.03a ("29 trains locked out ... plus 2 trapped Class
  387s"), T12.05 (F19's inertia sentences without the word "inertia"), T02.04 ("1.16 s
  after datum T"), and pre-screens of T05.03, T06.02, T08.04, T08.05, T09.05.
* Pre-screens that over-credited, fixed to the expectation: T08.04 (a measurement
  limit), T11.03 (the refinery's recovery time alone), T14.02 (the contribution without
  the requirement), T14.05 (Ofgem's finding of no breach), T15.01c (no internal
  escalation).
* True positives still fire on edited real sentences ("the root cause was a failed
  speed sensor", "ESO reported 580 MW of DG lost to vector shift", a basis that gives
  the 500 MW to the DNOs, a real hedge), and so do those the first 0.1.1 corrections
  missed (decision 81): F38 "before the root cause was identified as a faulty speed
  sensor", the summary's "the root cause was a bypass valve that stuck open", F10's
  580 MW "lost to RoCoF protection, although vector shift and RoCoF trips were not
  separated", F39's "UKPN may not have restored demand without ESO instruction".
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
from fi_grading_support import SR_LIVE_DIR, catalogue, key, live_runs

from environment.incident import fi_grading, sr_grading
from environment.incident import grading as mvp
from environment.incident.judge import prompt
from environment.incident.judge.config import load_config, with_task_defaults
from environment.incident.judge.prompt import build_units, load_rubric

RUNS = live_runs()
REUSED = key()["reused_from"]["criteria"]
# key 0.1.1 (decision 77) differences on increment A's texts, each read: (run, criterion)
# -> what differs. The values are increment A's; only the matched findings change.
FI_DIFFERENCES = {
    # "Hornsea One 1B and 1C wind turbine generators began de-loading" (F13) is the
    # offshore side (T06.02's offshore element now reads the wind turbines)
    ("sr80k-haiku45-001", "T06.02"): {
        "matched_finding_ids": ["F11", "F12", "F13", "F14"]
    },
}
# mentions key 0.1.1 adds: an inertia unit names the quantity ("ESO's modelled estimate
# was 219,632 MVA.s immediately before the trip", sr30k-sonnet55-001 F17)
FI_MENTIONS = {
    "sr30k-sonnet55-001": [("F17", "INERTIA_ESO_219632", "statement", "eso", "defined")]
}


@pytest.fixture(scope="module")
def graded():
    sr_key, sr_cat = sr_grading.load_key(), None
    from environment.incident.catalogue import Catalogue
    from environment.incident.paths import SYSTEM_RESPONSE_BUNDLE_DIR

    sr_cat = Catalogue.load(SYSTEM_RESPONSE_BUNDLE_DIR)
    out = {}
    for run in RUNS:
        d = SR_LIVE_DIR / run
        text = (d / "submission.json").read_text(encoding="utf-8")
        trace = sr_grading.trace_info_from_episode(d)
        out[run] = (
            sr_grading.grade_submission(text, sr_cat, sr_key, trace),
            fi_grading.grade_submission(text, catalogue(), key(), trace),
        )
    return out


def test_the_six_runs_are_present():
    assert RUNS == [
        "sr30k-haiku45-001",
        "sr30k-opus55-001",
        "sr30k-sonnet55-001",
        "sr80k-haiku45-001",
        "sr80k-opus55-001",
        "sr80k-sonnet55-001",
    ]


@pytest.mark.parametrize("run", RUNS)
def test_reused_criteria_reproduce_increment_a_on_real_texts(graded, run):
    sr, fi = graded[run]
    by_sr = {r["criterion_id"]: r for r in sr["criteria"]}
    by_fi = {r["criterion_id"]: r for r in fi["criteria"]}
    for cid in REUSED:
        a, b = by_sr[cid], by_fi[cid]
        for section in ("content", "evidence_support"):
            for name in ("auto_proposal", "value", "source"):
                assert a[section][name] == b[section][name], (run, cid, section, name)
        differs = FI_DIFFERENCES.get((run, cid), {})
        assert b["matched_finding_ids"] == differs.get(
            "matched_finding_ids", a["matched_finding_ids"]
        ), (run, cid)
        assert a["layers"]["caps"] == b["layers"]["caps"], (run, cid)


@pytest.mark.parametrize("run", RUNS)
def test_flags_and_severe_flags_are_unchanged(graded, run):
    sr, fi = graded[run]
    assert fi["severe_flags"] == sr["severe_flags"] == []
    for name in (
        "accounting_traps",
        "labelling",
        "status_inferential_language",
        "uncited_findings",
        "cited_but_never_retrieved",
    ):
        assert fi["flags"][name] == sr["flags"][name], (run, name)
    extra = [
        m
        for m in fi["accounting_basis"]["mentions"]
        if m not in sr["accounting_basis"]["mentions"]
    ]
    assert [m for m in fi["accounting_basis"]["mentions"] if m not in extra] == sr[
        "accounting_basis"
    ]["mentions"]
    assert [
        (
            m["location"],
            m["figure_id"],
            m["field"],
            m["bound_source"],
            m["classification"],
        )
        for m in extra
    ] == FI_MENTIONS.get(run, [])


def _auto(report, cid):
    return next(r for r in report["criteria"] if r["criterion_id"] == cid)["content"][
        "auto_proposal"
    ]


# increment A's runs say nothing about rail, essential services or recommendations
NOTHING_TO_CREDIT = [
    "T04.02",
    "T10.01",
    "T10.02a",
    "T10.02b",
    "T10.02c",
    "T10.03a",
    "T10.03b",
    "T10.04",
    "T10.05a",
    "T10.05b",
    "T10.05c",
    "T11.01a",
    "T11.01b",
    "T11.02",
    "T11.03",
    "T13.05",
    "T15.01a",
    "T15.01b",
    "T15.02",
    "T15.03",
    "T18.01",
    "T18.02",
    "T18.03",
    "T18.04",
    "T18.05",
    "T18.06",
    "T19.01",
]


@pytest.mark.parametrize("run", RUNS)
def test_new_criteria_give_no_credit_where_the_runs_say_nothing(graded, run):
    _, fi = graded[run]
    credited = {cid: _auto(fi, cid) for cid in NOTHING_TO_CREDIT if _auto(fi, cid)}
    assert credited == {}, (run, credited)


# real phrasing the new pre-screens must read (true positives on increment A's runs)
PINNED = {
    # "UKPN's Eastern and South Eastern networks reconnected sites without ESO
    # instruction, contrary to OC6.6.4 as Ofgem cites it" (sr80k-sonnet55-001 F28)
    "T14.03": {
        "sr30k-haiku45-001": 0,
        "sr30k-opus55-001": 1,
        "sr30k-sonnet55-001": 1,
        "sr80k-haiku45-001": 0,
        "sr80k-opus55-001": 1,
        "sr80k-sonnet55-001": 1,
    },
    # only sr30k-sonnet55-001 F20 says Grid Code compliance cannot be determined
    # because the relay logs are not held; "all DNO reports" is not "no reports". Key
    # 0.1.1's partial (records not held): sr30k opus F06/F46 and sr80k opus F36/F42
    # ("instrumentation and control records", "turbine controller logs" not held),
    # sr80k sonnet F07/F15 ("controller logs were not obtained", "no ... relay logs")
    "T14.05": {
        "sr30k-haiku45-001": 0,
        "sr30k-opus55-001": 0.5,
        "sr30k-sonnet55-001": 1,
        "sr80k-haiku45-001": 0,
        "sr80k-opus55-001": 0.5,
        "sr80k-sonnet55-001": 0.5,
    },
    # every run's executive summary gives the lightning fault on the circuit
    "T20.01": {
        "sr30k-haiku45-001": 1,
        "sr30k-opus55-001": 1,
        "sr30k-sonnet55-001": 1,
        "sr80k-haiku45-001": 1,
        "sr80k-opus55-001": 1,
        "sr80k-sonnet55-001": 0.5,
    },
    # "restoration process ... ESO" is not a compliance-process concern
    "T14.04": {run: 0 for run in RUNS},
}


@pytest.mark.parametrize("cid", sorted(PINNED))
def test_pinned_prescreens_on_real_texts(graded, cid):
    got = {run: _auto(graded[run][1], cid) for run in RUNS}
    assert got == PINNED[cid]


def test_judge_outputs_of_increment_a_do_not_merge_into_full_investigation_reports(
    graded,
):
    run = "sr80k-opus55-001"
    judge = json.loads((SR_LIVE_DIR / run / "judge_output.json").read_text())
    with pytest.raises(fi_grading.JudgeOutputError, match="key"):
        fi_grading.merge_judge_proposals(graded[run][1], judge)


# ======================================================================================
# Part 2: the real full-investigation runs (tests/fixtures/fi_live; decision 77)
# ======================================================================================
FI_LIVE = Path(__file__).resolve().parent / "fixtures" / "fi_live"
FI_MANIFEST = json.loads((FI_LIVE / "runs.json").read_text(encoding="utf-8"))
FI_RUNS = {run["run_id"]: run for run in FI_MANIFEST["runs"]}
PILOT, PANEL = "fi-pilot-opus55-001", "fi-panel-opus55-001"
# sha256 of what the judge sees of key 0.1.0, the key the judge outputs were produced
# with (criterion items, severe-flag items and task titles of judge/prompt.py); key
# 0.1.1 must leave it unchanged for the outputs to be re-merged without a judge call
JUDGE_VISIBLE_SHA256 = (
    "8f338945d2ce6a5eb5438f9e6b7a673144b2b9c36550d697ad4926e2abb47531"
)


def fi_summary(run_id: str) -> dict[str, Any]:
    return json.loads((FI_LIVE / run_id / "run_summary.json").read_text("utf-8"))


def fi_text(run_id: str) -> str:
    return (FI_LIVE / run_id / "submission.json").read_text(encoding="utf-8")


def fi_judge(run_id: str) -> dict[str, Any]:
    return json.loads((FI_LIVE / run_id / "judge_output.json").read_text("utf-8"))


@functools.cache
def fi_base(run_id: str) -> dict[str, Any]:
    """The automated grade the judge track starts from (no judge layer)."""
    return fi_grading.grade_episode(FI_LIVE / run_id, fi_summary(run_id))


def fi_rebound(run_id: str) -> dict[str, Any]:
    """The judge output (key 0.1.0) bound to the installed key: allowed because no
    judge-visible key text changed (``test_the_judge_saw_the_same_key_text``)."""
    out = copy.deepcopy(fi_judge(run_id))
    report = fi_base(run_id)
    out["binding"] = {
        "submission_sha256": report["submission"]["sha256"],
        "key_version": report["key"]["key_version"],
        "key_sha256": report["key"]["key_sha256"],
        "bundle_sha256": report["bundle"]["bundle_sha256"],
    }
    return out


@functools.cache
def fi_graded(run_id: str) -> dict[str, Any]:
    """Both runs with their judge output merged (no judge is called)."""
    return fi_grading.grade_episode(
        FI_LIVE / run_id, fi_summary(run_id), judge_output=fi_rebound(run_id)
    )


def fi_rows(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["criterion_id"]: r for r in report["criteria"]}


def best_available(row: dict[str, Any]) -> float | None:
    """Decided values, judge proposals for judge-mode criteria (after caps), else the
    automated pre-screen or proposal."""
    content = row["content"]
    if content["source"] in ("auto", "human", "severe_flag", "judge"):
        return content["value"]
    return content["auto_proposal"]


def regrade(run_id: str, edit) -> dict[str, Any]:
    """The run's submission edited by ``edit(sub)`` (a mutation of the real text),
    graded with the run's trace."""
    sub = json.loads(fi_text(run_id))
    edit(sub)
    return fi_grading.grade_submission(
        json.dumps(sub),
        catalogue(),
        key(),
        sr_grading.trace_info_from_episode(FI_LIVE / run_id),
    )


def finding_of(sub: dict[str, Any], fid: str) -> dict[str, Any]:
    return next(f for f in sub["findings"] if f["finding_id"] == fid)


def replace_in(item: dict[str, Any], field: str, old: str, new: str) -> None:
    assert old in item[field], (field, old)
    item[field] = item[field].replace(old, new)


# -- the fixtures are the real runs -------------------------------------------------------
@pytest.mark.parametrize("run_id", sorted(FI_RUNS))
def test_fi_fixtures_are_the_real_runs(run_id):
    run = FI_RUNS[run_id]
    for name, digest in run["files"].items():
        data = (FI_LIVE / run_id / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, name
    state = json.loads((FI_LIVE / run_id / "state.json").read_text(encoding="utf-8"))
    assert state["submission_sha256"] == run["submission_sha256"]
    report = fi_graded(run_id)
    assert report["submission"]["sha256"] == run["submission_sha256"]
    assert report["run"]["outcome"] == run["outcome"] == "complete"
    assert run["bundle_sha256"] == catalogue().bundle_sha256
    assert run["bundle_sha256"] == key()["bundle"]["bundle_sha256"]
    assert run["judged"] and run["judge_binding"]["key_version"] == "0.1.0"
    assert run["judge_binding"]["submission_sha256"] == run["submission_sha256"]
    assert fi_judge(run_id)["binding"] == run["judge_binding"]


def test_fi_manifest_records_the_key_and_grader_it_was_graded_with():
    assert FI_MANIFEST["graded_with"] == {
        "key_version": key()["key_version"],
        "key_sha256": fi_grading.key_sha256(key()),
        "grader_version": fi_grading.GRADER_VERSION,
    }
    assert sorted(FI_RUNS) == [PANEL, PILOT]


def test_the_judge_outputs_need_rebinding_to_the_installed_key():
    with pytest.raises(fi_grading.JudgeOutputError, match="key"):
        fi_grading.merge_judge_proposals(fi_base(PANEL), fi_judge(PANEL))


def test_the_judge_saw_the_same_key_text():
    """Key 0.1.1 changed no judge-visible text (criteria, examples without pre-screen
    values, accounting figure descriptions, severe-flag definitions, examples and
    non-examples)."""
    k = key()
    visible = {
        "criteria": [prompt._criterion_item(c, k, []) for c in k["criteria"]],
        "flags": [prompt._flag_item(f) for f in k["severe_flags"]],
        "dims": [(d["dimension_id"], d["title"]) for d in k["dimensions"]],
    }
    digest = hashlib.sha256(
        json.dumps(visible, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    assert digest == JUDGE_VISIBLE_SHA256


@pytest.mark.parametrize(
    ("run_id", "changed"),
    [
        # F13 now classified under T08 (T08.05 reads "This includes about 550 MW"), not
        # T02; F38's "before root causes were known" is no longer an SF1 trigger for the
        # error screen, so T07 and T17 no longer show F38 or its spans
        (PILOT, ["T02", "T07", "T08", "T17"]),
        # F38 is no longer suspected of SF1: classified under T14 (not T07) and shown to
        # T02 and T05 by its own content; F15's measurement limit no longer meets T08.04;
        # F19 (inertia, now read) is classified under T12, not T13
        (PANEL, ["T02", "T05", "T07", "T08", "T12", "T13", "T14"]),
    ],
)
def test_judge_requests_differ_only_in_the_findings_they_show(run_id, changed):
    """The requests the installed key would send have the same units and criteria as
    the recorded ones; where a request differs, it is because the corrected flags and
    pre-screens route or show other findings (no criterion text changed: see
    ``test_the_judge_saw_the_same_key_text``)."""
    k = key()
    config = with_task_defaults(
        load_config(None, task=fi_grading.TASK_ID), fi_grading.TASK_ID
    )
    sub, _ = mvp._as_submission(fi_text(run_id), catalogue())
    inputs = build_units(
        sub,
        fi_base(run_id),
        k,
        catalogue(),
        config,
        load_rubric(config.rubric_path()),
        blind_terms=[FI_RUNS[run_id]["model"]],
    )
    recorded = {u["unit_id"]: u for u in fi_judge(run_id)["units"]}
    assert [u.unit_id for u in inputs.units] == list(recorded)
    got = []
    for unit in inputs.units:
        assert unit.criterion_ids == recorded[unit.unit_id]["criteria"], unit.unit_id
        if unit.messages_sha256 != recorded[unit.unit_id]["messages_sha256"]:
            got.append(unit.unit_id)
    assert got == changed


# -- the confirmed false positives are gone ---------------------------------------------------
@pytest.mark.parametrize("run_id", [PILOT, PANEL])
def test_no_severe_flag_trap_or_cap_on_the_real_runs(run_id):
    report = fi_graded(run_id)
    assert report["severe_flags"] == []
    assert report["flags"]["accounting_traps"] == []
    assert [
        (r["criterion_id"], c["id"])
        for r in report["criteria"]
        for c in r["layers"]["caps"]
        if c.get("binding", True)
    ] == []
    assert report["judge"]["severe_flag_suggestions"] == []


def test_panel_f10_500_mw_is_esos_estimate():
    """F10's quantity (500 MW, basis "ESO estimate from transformer-flow changes (150 VS
    + 350 RoCoF)") is ESO's figure; every figure of F10 is given to its own account:
    the 150 and 350 MW as estimates, the 430 MW and "about 580 MW total" as modelling
    (ESO's simulation, Ofgem footnote 19), the 462 MW to the DNOs. None is
    misattributed."""
    mentions = {
        (m["figure_id"], m["field"]): (m["bound_source"], m["classification"])
        for m in fi_graded(PANEL)["accounting_basis"]["mentions"]
        if m["location"] == "F10"
    }
    assert mentions == {
        ("DG_LOM_500", "quantity"): ("eso", "attributed"),
        ("DG_VS_150", "statement"): (None, "defined"),
        ("DG_ROCOF_350", "statement"): (None, "defined"),
        ("DG_ROCOF_430", "statement"): (None, "unattributed"),
        ("DG_LOM_580", "statement"): (None, "unattributed"),
        ("DG_DNO_462", "statement"): ("dno", "attributed"),
    }


@pytest.mark.parametrize("run_id", [PILOT, PANEL])
def test_labelling_and_inferential_flags(run_id):
    """No labelling flag: "as soon as possible" (pilot F34, panel F33) and a
    prohibition "DNOs may not restore LFDD demand without ESO instruction" (pilot F26)
    are no hedges. The inferential flags are true positives: an observed finding that
    calls the record "consistent with" RoCoF trips (pilot F09) and a reported finding
    that concludes "therefore" (panel F45)."""
    flags = fi_graded(run_id)["flags"]
    assert flags["labelling"] == []
    assert [f["finding_id"] for f in flags["status_inferential_language"]] == {
        PILOT: ["F09"],
        PANEL: ["F45"],
    }[run_id]


# -- corrected criterion outcomes -------------------------------------------------------------
# criterion: (automated proposal or pre-screen, value shown: the judge proposal for a
# judge criterion, else None); key 0.1.0's value in the comment
FI_EXPECTED: dict[str, dict[str, tuple[float, float | None]]] = {
    PANEL: {
        "T07.04": (1, 1),  # was 0: suspected SF1 (F38 and the summary)
        "T07.05": (1, 1),  # was 0: SF1
        "T17.01": (1, 1),  # was 0: SF1
        "T14.02": (0.5, 0.5),  # was 0: SF1; the contribution without the requirement
        "T20.03": (0.5, 0.5),  # was 0: SF1 in the summary
        "T20.06": (1, 1),  # was 0: SF1 in the summary
        "T08.02": (1, None),  # was 0.5: "a net 200 MW at 49 Hz" (F11, labelled unknown)
        "T08.03": (1, None),  # was 0: Ofgem's 1,300-1,500 MW (estimated) in F11
        "T10.03a": (1, None),  # was 0: "29 trains locked out ... plus 2 trapped 387s"
        "T12.05": (1, None),  # was 0.5: F19's 210 GVA.s and 219,632 MVA.s
        "T14.05": (0.5, 0.5),  # pre-screen was 0 (F38 suspected): records not held
        "T15.01c": (0.5, 0.5),  # pre-screen was 1: no 17:10 internal escalation
        "T08.04": (1, 1),  # pre-screen was 1 through F15's measurement limit; now F10
    },
    PILOT: {
        "T02.04": (1, None),  # was 0.5: "1.16 s after datum T" (F06)
        "T05.03": (1, 1),  # pre-screen was 0.5: F25 "separate from" + F30
        "T06.02": (
            0.5,
            0.5,
        ),  # pre-screen was 0: "overcurrent protection on the turbines"
        "T08.04": (0.5, 0.5),  # pre-screen was 1 through F09's measurement limit
        "T08.05": (1, 1),  # pre-screen was 0: F13 "This includes about 550 MW"
        "T09.05": (0.5, 0.5),  # pre-screen was 0: F26 "a wrong setting"
        "T14.02": (
            0.5,
            0.5,
        ),  # pre-screen was 1: "RWE acknowledges it contributed" only
        "T14.05": (
            0.5,
            0.5,
        ),  # pre-screen was 1 through "found no evidence ... breached"
        "T15.01c": (1, 1),  # F34: "reported to the Head of National Control at 17:10"
        "T07.01": (0, None),  # genuine: the speed signals never given as the mechanism
        "T10.03b": (0, None),  # genuine: no Class 387
    },
}


@pytest.mark.parametrize(
    ("run_id", "cid"), [(r, c) for r in FI_EXPECTED for c in FI_EXPECTED[r]]
)
def test_fi_corrected_criterion_outcomes(run_id, cid):
    auto, shown = FI_EXPECTED[run_id][cid]
    row = fi_rows(fi_graded(run_id))[cid]
    assert row["content"]["auto_proposal"] == auto, row["layers"]["auto"]["basis"]
    if shown is not None:
        assert row["content"]["source"] == "judge"
        assert row["content"]["value"] == shown


def test_panel_figures_in_a_finding_labelled_unknown():
    """F11 (labelled unknown for the causes of two further losses) also reports Ofgem's
    estimate and the net 200 MW, with no uncertainty in their clauses."""
    rows = fi_rows(fi_graded(PANEL))
    for cid in ("T08.02", "T08.03"):
        (element,) = rows[cid]["auto_checks"]["elements"]
        assert element["finding_ids"] == ["F11"], cid
        assert element["detail"]["from_labelled_unknown"] == ["F11"], cid


@pytest.mark.parametrize(
    ("run_id", "disagreements"),
    [
        # T09.04: "3.2% of 29 GW" is not the non-equivalence (decision 43), the judge
        #   credits it as partial: borderline, the reviewer decides
        # T11.03: the summary's "some through their own protection" covers the refinery
        #   for the pre-screen; the judge wants the refinery's own mechanism: borderline
        # T13.04: pre-screen right (F13: the ~550 MW lost when LFDD operated, leaving a
        #   net reduction of ~350 MW); the judge's T13 request did not show F13 (scope)
        # T14.01: the requirements named and acknowledged, without their terms (90%
        #   within 0.5 s): borderline (both runs)
        # T18.04: UKPN's reconnection fix as the LFDD action: the judge accepts it as an
        #   equivalent action; the pre-screen needs LFDD named: borderline
        # T20.04: the pre-screen reads one attributed figure; the judge checks every
        #   disagreement (restoration times, rail counts): judge right, no reliable
        #   pattern
        (PILOT, ["T09.04", "T11.03", "T13.04", "T14.01", "T18.04", "T20.04"]),
        # T13.05: the judge gives the pilot 1 and the panel 0.5 for the same content
        #   (3.27 lock-outs needing technicians, no technician shortage): borderline
        (PANEL, ["T13.05", "T14.01"]),
    ],
)
def test_fi_remaining_judge_prescreen_disagreements(run_id, disagreements):
    """Key 0.1.0: pilot 13, panel 10 (six of them false SF1 caps). The rest were
    pre-screen errors, fixed in key 0.1.1."""
    got = [
        r["criterion_id"]
        for r in fi_graded(run_id)["criteria"]
        if r["assessment_mode"] == "judge"
        and r["content"]["judge_proposal"] is not None
        and r["content"]["judge_proposal"] != r["content"]["auto_proposal"]
    ]
    assert got == disagreements


@pytest.mark.parametrize(
    ("run_id", "counts"),
    [
        (PILOT, (84, 20, 2)),  # key 0.1.0: 83/21/2
        (PANEL, (86, 20, 0)),  # key 0.1.0: 78/20/8
    ],
)
def test_fi_best_available_content_counts(run_id, counts):
    values = Counter(best_available(r) for r in fi_graded(run_id)["criteria"])
    assert (values[1], values[0.5], values[0]) == counts


def test_the_panels_zeros_were_grader_errors():
    """Key 0.1.0's eight zeros on the panel run: six SF1 caps (T07.04, T07.05,
    T14.02, T17.01, T20.03, T20.06) and two false negatives (T08.03, T10.03a)."""
    rows = fi_rows(fi_graded(PANEL))
    got = {
        cid: best_available(rows[cid])
        for cid in (
            "T07.04",
            "T07.05",
            "T08.03",
            "T10.03a",
            "T14.02",
            "T17.01",
            "T20.03",
            "T20.06",
        )
    }
    assert got == {
        "T07.04": 1,
        "T07.05": 1,
        "T08.03": 1,
        "T10.03a": 1,
        "T14.02": 0.5,
        "T17.01": 1,
        "T20.03": 0.5,
        "T20.06": 1,
    }


# -- true positives still fire on the real texts -----------------------------------------------
@pytest.mark.parametrize(
    "line",
    [
        "- Little Barford was allowed to reconnect although the root cause was a failed "
        "speed sensor.",
        # decision 81: the first 0.1.1 key excused these with the not-yet-found wording
        "- Hornsea One and Little Barford were allowed to reconnect before the root cause "
        "was identified as a faulty speed sensor.",
        "- Little Barford was allowed to reconnect before the root cause was found: a "
        "faulty speed sensor.",
        "- Little Barford was allowed to reconnect before the root cause was found, "
        "which was a faulty speed sensor.",
    ],
)
def test_sf1_fires_on_the_panels_f38_line_with_a_root_cause(line):
    def edit(sub):
        replace_in(
            finding_of(sub, "F38"),
            "statement",
            "- Hornsea One and Little Barford were allowed to reconnect before the root "
            "cause was found.",
            line,
        )

    report = regrade(PANEL, edit)
    assert [(s["flag_id"], s["location"]) for s in report["severe_flags"]] == [
        ("SF1", "F38")
    ]
    rows = fi_rows(report)
    for cid in ("T07.04", "T07.05", "T14.02", "T17.01"):
        assert rows[cid]["content"]["auto_proposal"] == 0, cid
    # an assertion only in a finding does not zero the summary criteria
    assert rows["T20.06"]["content"]["auto_proposal"] == 1


@pytest.mark.parametrize(
    ("line", "match"),
    [
        (
            "- Little Barford: the root cause was a failed speed sensor [F09].",
            "root cause was",
        ),
        (
            "- Little Barford: the root causes are unestablished, but the GT1A bypass "
            "valve failed [F09].",
            "valve failed",
        ),
        # decision 81: the first 0.1.1 key excused these ("open", "until ... found",
        # "not been found" and a leading "although" clause)
        (
            "- Little Barford: the root cause was a bypass valve that stuck open [F09].",
            "root cause was",
        ),
        (
            "- Little Barford: GT1A's root cause: a bypass valve that failed to open "
            "[F09].",
            "valve that failed",
        ),
        (
            "- Little Barford: ST1C stayed off until the root cause was identified as a "
            "faulty speed sensor [F09].",
            "faulty speed sensor",
        ),
        (
            "- Little Barford: the ST1C trip was caused by a faulty speed sensor that "
            "had not been found in earlier inspections [F09].",
            "faulty speed sensor",
        ),
        (
            "- Although the root cause remains unestablished, ST1C tripped because of a "
            "faulty speed sensor [F09].",
            "faulty speed sensor",
        ),
    ],
)
def test_sf1_fires_on_the_panels_summary_line_with_a_root_cause(line, match):
    def edit(sub):
        replace_in(
            sub["report"],
            "executive_summary",
            "- Little Barford: the root causes are unestablished [F09].",
            line,
        )

    report = regrade(PANEL, edit)
    assert [
        (s["flag_id"], s["location"], s["match"]) for s in report["severe_flags"]
    ] == [("SF1", "report.executive_summary", match)]
    rows = fi_rows(report)
    for cid in ("T07.04", "T20.03", "T20.06"):
        assert rows[cid]["content"]["auto_proposal"] == 0, cid


def test_traps_fire_on_the_panels_f10_with_a_wrong_stage_or_source():
    def stage(sub):
        replace_in(
            finding_of(sub, "F10"),
            "statement",
            "with modelling up to 430 MW (about 580 MW total).",
            "with modelling up to 430 MW. ESO reported 580 MW of DG lost to vector shift.",
        )

    def source(sub):
        finding_of(sub, "F10")["quantity"]["basis"] = "DNO returns (150 VS + 350 RoCoF)"

    # decision 81: both mechanisms named elsewhere in the sentence do not excuse it
    def stage_elsewhere(sub):
        replace_in(
            finding_of(sub, "F10"),
            "statement",
            "with modelling up to 430 MW (about 580 MW total).",
            "with modelling up to 430 MW. The ESO modelled 580 MW of loss-of-mains "
            "generation lost to RoCoF protection, although vector shift and RoCoF trips "
            "were not separated by the DNOs.",
        )

    for edit in (stage, stage_elsewhere):
        traps = regrade(PANEL, edit)["flags"]["accounting_traps"]
        assert [(t["type"], t["figure_id"], t["bound_source"]) for t in traps] == [
            ("mismatched", "DG_LOM_580", "eso")
        ]
    traps = regrade(PANEL, source)["flags"]["accounting_traps"]
    assert [(t["type"], t["figure_id"], t["bound_source"]) for t in traps] == [
        ("misattributed", "DG_LOM_500", "dno")
    ]


@pytest.mark.parametrize(
    ("edit_f11", "t0802", "t0803"),
    [
        # the estimate itself put in doubt: a candidate for a human, never credited
        (
            lambda f: replace_in(
                f,
                "statement",
                "Ofgem puts total distributed generation lost at 1,300–1,500 MW (estimated).",
                "It is unknown whether Ofgem's total of 1,300–1,500 MW of distributed "
                "generation lost (estimated) is right.",
            ),
            1,
            0,
        ),
        # a hypothesis never counts (T08.02 falls back to F13's 200 MW without "net")
        (lambda f: f.update(status="hypothesis"), 0.5, 0),
    ],
)
def test_figures_in_a_labelled_finding_need_an_unhedged_clause(edit_f11, t0802, t0803):
    report = regrade(PANEL, lambda sub: edit_f11(finding_of(sub, "F11")))
    rows = fi_rows(report)
    assert rows["T08.02"]["content"]["auto_proposal"] == t0802
    assert rows["T08.03"]["content"]["auto_proposal"] == t0803
    assert (
        "labelled hypothesis, or labelled unknown" in rows["T08.03"]["content"]["basis"]
    )


def test_t10_03a_needs_the_class_387s_with_the_29():
    def edit(sub):
        replace_in(
            finding_of(sub, "F27"), "statement", " plus 2 trapped Class 387s", ""
        )

    assert fi_rows(regrade(PANEL, edit))["T10.03a"]["content"]["auto_proposal"] == 0


@pytest.mark.parametrize(
    ("run_id", "fid", "old", "new"),
    [
        (
            PANEL,
            "F33",
            "BEIS was first contacted at 17:41",
            "BEIS may have been first contacted at 17:41",
        ),
        (
            PILOT,
            "F26",
            "Under OC6.6 DNOs may not restore LFDD demand without ESO instruction.",
            "DNOs may not have restored LFDD demand in order.",
        ),
        # decision 81: "may not have ... without instruction" is a hedge, not the
        # prohibition the exemption spares
        (
            PILOT,
            "F26",
            "Under OC6.6 DNOs may not restore LFDD demand without ESO instruction.",
            "UKPN may not have restored LFDD demand without ESO instruction.",
        ),
    ],
)
def test_labelling_still_flags_a_real_hedge(run_id, fid, old, new):
    report = regrade(
        run_id, lambda sub: replace_in(finding_of(sub, fid), "statement", old, new)
    )
    assert [(f["finding_id"], f["terms"]) for f in report["flags"]["labelling"]] == [
        (fid, ["may"])
    ]


def test_pilot_t14_05_full_with_the_compliance_proof_named_missing():
    def edit(sub):
        replace_in(
            finding_of(sub, "F38"),
            "statement",
            "Ofgem found no evidence that the ESO breached the Grid Code.",
            "Ofgem found no evidence that the ESO breached the Grid Code, and the "
            "compliance test reports were not obtained.",
        )

    assert fi_rows(regrade(PILOT, edit))["T14.05"]["content"]["auto_proposal"] == 1


def test_pilot_t11_03_needs_the_refinerys_own_mechanism():
    """F33's "A refinery took weeks to restore operations" gives no mechanism (its
    "internal" is the second airport's); the summary's "some through their own
    protection" names one (the remaining disagreement with the judge)."""
    rows = fi_rows(fi_base(PILOT))
    assert rows["T11.03"]["content"]["auto_proposal"] == 1

    def edit(sub):
        replace_in(
            sub["report"],
            "executive_summary",
            "some through LFDD and some through their own protection",
            "some through LFDD",
        )

    assert fi_rows(regrade(PILOT, edit))["T11.03"]["content"]["auto_proposal"] == 0.5


def test_pilot_t02_04_offset_must_fit_the_initial_group():
    def edit(sub):
        replace_in(
            finding_of(sub, "F06"),
            "statement",
            "ST1C tripped about 1.16 s after datum T",
            "ST1C tripped about 2.5 s after datum T",
        )

    assert fi_rows(regrade(PILOT, edit))["T02.04"]["content"]["auto_proposal"] == 0.5
