"""The system-response reference submission (tasks/gb_2019_system_response/reference).

It must be a complete, correct and fully cited v3 submission for T01-T09, T12, T16 and
T17: valid on the real bundle, every criterion of the key at full content and evidence
(automated values for the R01 landmarks, proposals and judge pre-screens elsewhere), every
figure on its own accounting basis, no reviewer flag, and every number it computes
reproducible from the bundle's real data.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from functools import lru_cache

import pandas as pd
import pytest
from sr_grading_support import catalogue, grade, key, row

from environment import fake_model
from environment.incident.episode import OUTPUT_TOKEN_BUDGET
from environment.incident.frequency import load_series, reference_landmarks
from environment.incident.paths import SYSTEM_RESPONSE_BUNDLE_DIR
from environment.incident.submission import extract_references, validate_submission

REFERENCE = fake_model.SR_REFERENCE_SUBMISSION
BUNDLE = SYSTEM_RESPONSE_BUNDLE_DIR
TASKS = (
    "T01",
    "T02",
    "T03",
    "T04",
    "T05",
    "T06",
    "T07",
    "T08",
    "T09",
    "T12",
    "T16",
    "T17",
)


@lru_cache(maxsize=1)
def reference() -> dict:
    return json.loads(REFERENCE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def report() -> dict:
    return grade(reference())


def findings() -> dict[str, dict]:
    return {f["finding_id"]: f for f in reference()["findings"]}


# -- the file ------------------------------------------------------------------------------
def test_file_is_canonical_json():
    text = REFERENCE.read_text(encoding="utf-8")
    assert (
        text
        == json.dumps(reference(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )


def test_valid_on_the_system_response_bundle():
    result = validate_submission(reference(), catalogue())
    assert result.ok, result.errors
    words = reference()["report"]["executive_summary"].split()
    assert 300 <= len(words) <= 600
    assert len(reference()["findings"]) <= 200


def test_submission_leaves_room_in_the_output_budget():
    """A model writing this submission spends roughly one token per four characters; the
    reference must fit in half the output budget so that a real investigation of this
    depth is possible within it."""
    compact = json.dumps(reference(), ensure_ascii=False, separators=(",", ":"))
    assert len(compact) / 4 < OUTPUT_TOKEN_BUDGET / 2


def test_every_finding_is_referenced_and_cited():
    sub = reference()
    texts = [sub["report"]["executive_summary"]]
    texts += [s["body"] for s in sub["report"]["sections"]]
    referenced = {ref for text in texts for ref in extract_references(text)}
    assert referenced == set(findings())
    for f in sub["findings"]:
        assert f["citations"], f["finding_id"]


# Source figures and facts a finding states, each found in the text of one of its own
# citations (handoff rule: derived numerical claims cite every input).
STATED_IN_CITATIONS = [
    ("F30", "Table 7"),
    ("F30", "WPD East Midland: 16:57 [reported] | 17:16 [reported]"),
    ("F30", "C24 17:20 [reported] NGESO -> WPD East Midland"),
    ("F30", "Instruction to restore all demand"),
    ("F42", "insufficiently damped electrical resonance"),
    ("F42", "reacted incorrectly to voltage fluctuations"),
    ("F47", "37.474 MWh"),
    ("F47", "178.708 MWh"),
    ("F47", "34.425 MWh"),
    ("F47", "7.459 MWh"),
    ("F47", "T_HOWAO-1 | HORNSEA_1A"),
    ("F60", "350-430 MW"),
    ("F60", "581 MW"),
    ("F65", "430 MW"),
    ("F65", "581 MW"),
    ("F75", "3.2% of national transmission demand"),
    ("F76", "48.787"),
    ("F90", "462 MW"),
    ("F90", "1,300 MW"),
    ("F93", "641 MW"),
]


@pytest.mark.parametrize(("fid", "text"), STATED_IN_CITATIONS)
def test_stated_source_figures_are_in_the_findings_own_citations(fid, text):
    from environment.incident.sr_grading import resolve_text

    cited = [
        resolve_text(catalogue(), c["evidence_id"], c["locator"])
        for c in findings()[fid]["citations"]
    ]
    assert any(text in t for t in cited), (fid, text)


def test_resonance_is_not_attributed_to_ofgem():
    """Ofgem's findings (S01 C1) name an instability, not a resonance: the resonance
    explanation is the operator's, restated by the ESO (S01 B3)."""
    for f in reference()["findings"]:
        statement = f["statement"]
        assert "restated by the ESO and Ofgem" not in statement, f["finding_id"]
    assert "without naming a resonance" in findings()["F42"]["statement"]
    summary = reference()["report"]["executive_summary"]
    assert "[F75, F77]" in summary and "[F75, F76, F77, F78]" not in summary


def test_statuses_label_hypotheses_and_unknowns():
    by = findings()
    assert {fid for fid, f in by.items() if f["status"] == "hypothesis"} == {
        "F54",
        "F55",
        "F56",
    }
    assert {fid for fid, f in by.items() if f["status"] == "unknown"} == {
        "F53",
        "F90",
        "F91",
    }
    assert {by[fid]["status"] for fid in ("F20", "F21", "F22", "F23", "F24")} == {
        "observed"
    }


def test_times_carry_explicit_bst_offsets():
    for f in reference()["findings"]:
        if "event_time" in f:
            assert f["event_time"].endswith("+01:00"), f["finding_id"]
            assert datetime.fromisoformat(f["event_time"]).date().isoformat() == (
                "2019-08-09"
            )
    summary = reference()["report"]["executive_summary"]
    assert "BST (UTC+01:00)" in summary


# -- grading: every criterion at full content and evidence ---------------------------------
def test_every_criterion_is_satisfied_with_keyed_evidence():
    rep = report()
    assert len(rep["criteria"]) == len(key()["criteria"]) == 60
    for r in rep["criteria"]:
        content, evidence = r["content"], r["evidence_support"]
        assert content["auto_proposal"] == 1, (r["criterion_id"], r["layers"]["auto"])
        assert evidence["auto_proposal"] == 1, (r["criterion_id"], evidence)
        assert not r["layers"]["caps"], (r["criterion_id"], r["layers"]["caps"])
    covered = {r["task"] for r in rep["criteria"]}
    assert covered == set(TASKS)


@pytest.mark.parametrize("cid", ["T03.01", "T03.02", "T03.03", "T04.01"])
def test_r01_landmarks_are_decided_automatically(cid):
    r = row(report(), cid)
    assert r["content"]["source"] == "auto" and r["content"]["value"] == 1


def test_no_reviewer_flags_and_no_severe_flags():
    rep = report()
    flags = rep["flags"]
    for name in (
        "uncited_findings",
        "uncited_factual_findings",
        "unresolvable_citations",
        "suspected_severe_assertions",
        "labelling",
        "status_inferential_language",
        "accounting_traps",
        "conflicting_values",
        "findings_not_referenced_in_report",
    ):
        assert not flags[name], (name, flags[name])
    assert rep["severe_flags"] == []


def test_figures_are_on_their_own_bases():
    acc = report()["accounting_basis"]
    wrong = [
        m
        for m in acc["mentions"]
        if m["classification"] in ("misattributed", "mismatched")
    ]
    assert wrong == []
    assert acc["traps"] == []
    sums = {a["expression"]: a for a in acc["arithmetic"]}
    assert all(a["within_1_mw"] for a in sums.values())
    stated = {a["stated"] for a in sums.values()}
    assert {737.0, 1878.0, 1481.0} <= stated
    by_figure: dict[str, set[str]] = {}
    for m in acc["mentions"]:
        by_figure.setdefault(m["figure_id"], set()).add(m["classification"])
    for figure in (
        "GEN_ESO_1878",
        "GEN_OFG_1990",
        "LFDD_931",
        "LFDD_OFG_892",
        "LFDD_E3CI_973",
        "RESP_SECONDARY_1314",
        "RESP_SECONDARY_1338",
        "INERTIA_ESO_210",
        "INERTIA_ESO_219632",
        "DG_TOTAL_1300_1500",
    ):
        assert "attributed" in by_figure.get(figure, set()), figure


def test_accounting_bases_are_kept_apart_in_the_text():
    by = findings()
    assert "1,878 MW" in by["F17"]["statement"] and "Table 2" in by["F17"]["statement"]
    assert "at least 1,990 MW" in by["F18"]["statement"]
    assert "1,878" not in by["F18"]["statement"]
    assert "931 MW" in by["F71"]["statement"] and "Ofgem" not in by["F71"]["statement"]
    assert "892 MW of net demand" in by["F72"]["statement"]
    assert "973 MW" in by["F73"]["statement"]
    assert "not additive" in by["F65"]["statement"]
    # no distributed-generation total of its own: no arithmetic over DG estimates
    dg_terms = {150.0, 350.0, 430.0, 462.0, 500.0, 550.0, 580.0, 581.0, 600.0}
    for a in report()["accounting_basis"]["arithmetic"]:
        if a["stated"] not in (1878.0, 1481.0):
            assert not dg_terms & {abs(t) for t in a["terms"]}, a


# -- reproducible from the bundle --------------------------------------------------------
def test_frequency_findings_match_the_r01_series():
    csv = BUNDLE / "R01" / "frequency_2019-08-09_1640-1745_BST.csv"
    lm = reference_landmarks(load_series(csv))
    by = findings()
    for fid, name in (
        ("F20", "first_local_minimum"),
        ("F21", "event_minimum"),
        ("F22", "first_at_or_above_50_after_minimum"),
    ):
        assert by[fid]["quantity"]["value"] == pytest.approx(lm[name]["value_hz"])
        assert datetime.fromisoformat(by[fid]["event_time"]) == datetime.fromisoformat(
            lm[name]["time"]
        )
    assert by["F23"]["quantity"]["value"] == lm["below_49"]["covered_below_s"] == 33


def _b1610() -> pd.DataFrame:
    df = pd.read_csv(BUNDLE / "R02" / "R02_elexon_b1610_selected_units_20190809.csv")
    return df.pivot(index="settlementPeriod", columns="bmUnit", values="quantity") * 2


def _numbers(text: str) -> set[float]:
    return {
        float(n.replace(",", "")) for n in re.findall(r"-?\d[\d,]*(?:\.\d+)?", text)
    }


def test_unit_data_cross_checks_match_the_b1610_extract():
    mw = _b1610()
    stated = _numbers(findings()["F47"]["statement"])
    for unit, sp in (("T_HOWAO-2", 33), ("T_HOWAO-3", 33), ("T_HOWAO-1", 33)):
        assert round(mw.loc[sp, unit]) in stated, (unit, sp)
    for unit in ("T_HOWAO-2", "T_HOWAO-3", "T_HOWAO-1"):
        assert round(mw.loc[35, unit]) in stated, unit
    hornsea = mw[["T_HOWAO-1", "T_HOWAO-2", "T_HOWAO-3"]].sum(axis=1)
    assert round(hornsea[33] - hornsea[35]) == 732 and 732 in stated
    lbar = _numbers(findings()["F93"]["statement"])
    assert (
        round(mw.loc[33, "T_LBAR-1"]) in lbar and round(mw.loc[35, "T_LBAR-1"]) in lbar
    )


def test_demand_cross_check_matches_the_r07_extract():
    df = pd.read_csv(
        BUNDLE / "R07" / "R07_elexon_demand_outturn_summary_5min_20190809.csv"
    )
    window = df[
        (df["startTime"] >= "2019-08-09T15:50")
        & (df["startTime"] <= "2019-08-09T16:30")
    ]
    before = int(df.loc[df["startTime"] == "2019-08-09T15:50:00Z", "demand"].iloc[0])
    low = window.loc[window["demand"].idxmin()]
    stated = findings()["F78"]["statement"]
    assert f"{before:,} MW at 15:50 UTC" in stated
    assert f"{int(low['demand']):,} MW at {low['startTime'][11:16]} UTC" in stated
    dci = pd.read_csv(BUNDLE / "R07" / "R07_elexon_dci_201908.csv").iloc[0]
    assert dci["timeFrom"][11:16] == "15:54" and dci["timeTo"][11:16] == "16:40"
    assert "15:54-16:40 UTC" in findings()["F71"]["statement"]


def test_little_barford_times_follow_from_the_datum():
    t0 = datetime.fromisoformat("2019-08-09T16:52:34+01:00").timestamp()
    by = findings()
    for fid, offset in (("F11", 1.185), ("F12", 57.620), ("F13", 84.613)):
        assert datetime.fromisoformat(
            by[fid]["event_time"]
        ).timestamp() == pytest.approx(t0 + offset)
        assert "± 0.5 s" in by[fid]["statement"] or "± 0.5 s" in by[fid].get(
            "derivation", ""
        )
