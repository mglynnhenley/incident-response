"""The full-investigation grading fixtures (tests/fixtures/fi/submissions), built by
``tests/fixtures/fi/build_fi_fixtures.py`` from the reference submission: validation of
every fixture and the automated outcomes the grader gives them (no judge, no human)."""

from __future__ import annotations

import copy
import json
from functools import cache
from pathlib import Path

import pytest
from fi_grading_support import catalogue, grade, row

from environment import fake_model_fi
from environment.incident.submission import validate_submission

SUBMISSIONS = Path(__file__).resolve().parent / "fixtures" / "fi" / "submissions"
VALID = ("correct", "uncited", "incorrect", "uncertain", "incomplete")
INVALID = {
    "invalid_record_wrong_evidence": [
        ("findings[102].citations[1].locator", "belongs to evidence R09, not R11")
    ],
    "invalid_unknown_record": [
        ("findings[67].citations[4].locator", "no witness response 'S09-GTR-42'"),
        ("findings[76].citations[2].locator", "no control-log entry 'R11-NR-999999'"),
        (
            "findings[102].citations[1].locator",
            "no asset-log event 'R09-REMIT-99999999",
        ),
    ],
    "invalid_malformed_record_locator": [
        ("findings[97].citations[3].locator", "malformed control-log entry locator"),
        ("findings[102].citations[1].locator", "malformed asset-log event locator"),
    ],
    "invalid_line_locator_on_witness": [
        ("findings[69].citations[3].locator", "S09 has no document text or time series")
    ],
    "invalid_line_out_of_range": [
        ("findings[67].citations[4].locator", "S08 has 246 lines; L999 is out of range")
    ],
    "invalid_series_out_of_range": [
        ("findings[17].citations[2].locator", "is outside the R01 series")
    ],
    "invalid_data_return_out_of_range": [
        ("findings[46].citations[3].locator", "S05 has 112 lines; L999 is out of range")
    ],
    "invalid_unknown_evidence": [
        ("findings[84].citations[4].evidence_id", "unknown evidence_id 'S13'")
    ],
    "invalid_summary_601_words": [("report.executive_summary", "has 601 words")],
    "invalid_unknown_ref": [("report.sections[0].body", "references [F99]")],
}
TOPICS = tuple(f"T{i:02d}" for i in range(1, 21))


def load(name: str) -> dict:
    return json.loads((SUBMISSIONS / f"{name}.json").read_text(encoding="utf-8"))


@cache
def graded(name: str) -> dict:
    return grade(load(name))


def auto(name: str, cid: str):
    return row(graded(name), cid)["content"]["auto_proposal"]


def caps(name: str, cid: str) -> dict[str, dict]:
    return {c["id"]: c for c in row(graded(name), cid)["layers"]["caps"]}


def test_fixture_set_is_complete():
    names = {p.stem for p in SUBMISSIONS.glob("*.json")}
    assert names == set(VALID) | set(INVALID)


def test_correct_is_the_reference_submission():
    assert (SUBMISSIONS / "correct.json").read_bytes() == (
        fake_model_fi.FI_REFERENCE_SUBMISSION.read_bytes()
    )


def test_uncited_is_the_reference_without_citations():
    expected = copy.deepcopy(fake_model_fi.fi_reference_submission())
    for finding in expected["findings"]:
        finding["citations"] = []
        finding.pop("derivation", None)
    assert load("uncited") == expected


@pytest.mark.parametrize("name", VALID)
def test_valid_fixtures_validate(name):
    assert validate_submission(load(name), catalogue()).ok


@pytest.mark.parametrize("name", sorted(INVALID))
def test_invalid_fixtures_are_rejected_with_their_problems(name):
    result = validate_submission(load(name), catalogue())
    assert not result.ok
    errors = {(e["path"], e["message"]) for e in result.errors}
    assert len(errors) == len(INVALID[name]), result.errors
    for path, fragment in INVALID[name]:
        assert any(p == path and fragment in m for p, m in errors), (
            path,
            result.errors,
        )


# -- automated outcomes -------------------------------------------------------------------
def test_correct_reaches_every_criterion():
    rep = graded("correct")
    assert len(rep["criteria"]) == 106
    assert all(r["content"]["auto_proposal"] == 1 for r in rep["criteria"])
    assert all(r["evidence_support"]["auto_proposal"] == 1 for r in rep["criteria"])
    assert rep["severe_flags"] == [] and rep["flags"]["accounting_traps"] == []


def test_uncited_keeps_content_but_loses_evidence():
    rep = graded("uncited")
    assert all(r["content"]["auto_proposal"] == 1 for r in rep["criteria"])
    for r in rep["criteria"]:
        ev = r["evidence_support"]
        if r["matched_finding_ids"]:
            assert ev["value"] == 0 and ev["source"] == "auto", (r["criterion_id"], ev)
    assert len(rep["flags"]["uncited_findings"]) == len(load("uncited")["findings"])


def test_uncertain_satisfies_nothing_and_asserts_nothing():
    rep = graded("uncertain")
    assert all(r["content"]["auto_proposal"] == 0 for r in rep["criteria"])
    for cid in ("T03.01", "T03.02", "T03.03", "T04.01"):
        assert row(rep, cid)["content"]["value"] == 0
    assert rep["severe_flags"] == [] and rep["flags"]["accounting_traps"] == []


def test_incomplete_covers_only_the_event_the_frequency_and_rail():
    rep = graded("incomplete")
    full = {
        r["criterion_id"] for r in rep["criteria"] if r["content"]["auto_proposal"] == 1
    }
    assert {"T01.01", "T01.02", "T01.03a", "T01.03b", "T01.04"} <= full
    assert {"T03.01", "T03.02", "T03.03", "T04.01", "T04.02", "T04.03"} <= full
    assert {c["criterion_id"] for c in rep["criteria"] if c["task"] == "T10"} <= full
    assert {cid[:3] for cid in full} <= {
        "T01",
        "T03",
        "T04",
        "T10",
        "T13",
        "T16",
        "T20",
    }
    for topic in ("T02", "T05", "T06", "T07", "T08", "T09", "T11", "T12", "T14", "T15"):
        assert all(
            r["content"]["auto_proposal"] == 0
            for r in rep["criteria"]
            if r["task"] == topic
        ), topic
    for topic in ("T17", "T18", "T19"):
        assert all(
            r["content"]["auto_proposal"] == 0
            for r in rep["criteria"]
            if r["task"] == topic
        ), topic


def test_incorrect_raises_sf3_on_the_excluded_settlements():
    rep = graded("incorrect")
    severe = {(f["flag_id"], f["finding_id"]) for f in rep["severe_flags"]}
    assert ("SF3", "X16") in severe  # £4.5m voluntary payments, redress scheme
    assert ("SF3", None) in severe  # the same claim in the executive summary
    for cid in ("T14.04", "T14.05"):
        assert auto("incorrect", cid) == 0
        assert caps("incorrect", cid)["SF3"]["kind"] == "severe_suspected"
        assert "legal_finding_asserted" in caps("incorrect", cid)  # X17


def test_incorrect_counts_merged_without_attribution_are_not_credited():
    assert auto("incorrect", "T10.02a") == 1  # ORR's 29 needs no source
    for cid in ("T10.02b", "T10.02c", "T10.05c"):
        assert auto("incorrect", cid) == 0, cid  # GTR's 27 and circa 30 unattributed


def test_incorrect_ofgem_contact_forced_to_one_time_is_not_credited():
    assert auto("incorrect", "T15.02") == 0  # 18:00 alone, no record named
    assert auto("incorrect", "T15.01a") == 0  # BEIS at 17:00


def test_incorrect_consequences_trip_their_contradictions():
    expected = {
        "T10.01": ("traction_supply_lost_as_cause", 0),
        "T10.03b": ("class387_shut_down", 0),
        "T10.04": ("versions_reversed", 0),
        "T11.01a": ("airport_own_protection", 0),
        "T11.01b": ("hospital_lfdd", 0),
        "T11.03": ("refinery_lfdd", 0),
        "T14.03": ("wrong_dno_reconnected_early", 0),
        "T15.04": ("communications_as_cause", 0),
        "T04.02": ("rail_threshold_misstated", 0),
        "T19.02": ("unverified_obligation", 0.5),
    }
    for cid, (cap, value) in expected.items():
        assert cap in caps("incorrect", cid), (cid, caps("incorrect", cid))
        assert auto("incorrect", cid) == value, cid
    assert "stanlow_as_9_august" in caps("incorrect", "T11.03")
    assert auto("incorrect", "T10.05b") == 0  # 873 delay minutes


def test_incorrect_keeps_increment_a_traps_and_flags():
    rep = graded("incorrect")
    severe = {(f["flag_id"], f["finding_id"]) for f in rep["severe_flags"]}
    assert {("SF1", "X09"), ("SF2", "X10"), ("SF2", "X31")} <= severe
    traps = {
        (t["type"], t.get("figure_id"), t["finding_id"])
        for t in rep["flags"]["accounting_traps"]
    }
    for expected in (
        ("mismatched", "GEN_OFG_1990", "X02"),
        ("misattributed", "LFDD_931", "X03"),
        ("misattributed", "LFDD_OFG_892", "X04"),
        ("misattributed", "RESP_SECONDARY_1338", "X07"),
        ("misattributed", "INERTIA_ESO_219632", "X08"),
    ):
        assert expected in traps, expected
    assert auto("incorrect", "T20.06") == 0  # "It is established that the root cause"
    for cid in ("T03.01", "T03.02", "T04.01"):
        content = row(rep, cid)["content"]
        assert content["source"] == "auto" and content["value"] == 0, (cid, content)
