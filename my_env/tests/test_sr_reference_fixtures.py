"""The system-response grading fixtures (tests/fixtures/sr/submissions), built by
``tests/fixtures/sr/build_sr_fixtures.py`` from the reference submission: validation of
every fixture and the automated outcomes the grader gives them (no judge, no human)."""

from __future__ import annotations

import copy
import json
from functools import cache
from pathlib import Path

import pytest
from sr_grading_support import catalogue, grade, row

from environment import fake_model
from environment.incident.submission import validate_submission

SUBMISSIONS = Path(__file__).resolve().parent / "fixtures" / "sr" / "submissions"
VALID = ("correct", "uncited", "incorrect", "uncertain", "incomplete")
INVALID = {
    "invalid_record_wrong_evidence": [
        ("findings[7].citations[6].locator", "belongs to evidence S01, not R03")
    ],
    "invalid_unknown_record": [
        ("findings[9].citations[5].locator", "no asset-log event 'S03-SOE-E77'"),
        ("findings[23].citations[14].locator", "no control-log entry 'S07-E99'"),
        ("findings[27].citations[7].locator", "no witness response 'S09-ORS-99'"),
    ],
    "invalid_malformed_record_locator": [
        ("findings[0].citations[3].locator", "malformed asset-log event locator"),
        ("findings[24].citations[5].locator", "malformed control-log entry locator"),
    ],
    "invalid_line_locator_on_witness": [
        ("findings[31].citations[2].locator", "S09 has no document text or time series")
    ],
    "invalid_series_out_of_range": [
        ("findings[56].citations[3].locator", "is outside the R07 series")
    ],
    "invalid_data_return_out_of_range": [
        ("findings[46].citations[2].locator", "S06 has 120 lines; L999 is out of range")
    ],
    "invalid_unknown_evidence": [
        ("findings[29].citations[6].evidence_id", "unknown evidence_id 'S02'")
    ],
    "invalid_summary_601_words": [("report.executive_summary", "has 601 words")],
    "invalid_unknown_ref": [("report.sections[0].body", "references [F99]")],
}


def load(name: str) -> dict:
    return json.loads((SUBMISSIONS / f"{name}.json").read_text(encoding="utf-8"))


@cache
def graded(name: str) -> dict:
    return grade(load(name))


def test_fixture_set_is_complete():
    names = {p.stem for p in SUBMISSIONS.glob("*.json")}
    assert names == set(VALID) | set(INVALID)


def test_correct_is_the_reference_submission():
    assert (SUBMISSIONS / "correct.json").read_bytes() == (
        fake_model.SR_REFERENCE_SUBMISSION.read_bytes()
    )


def test_uncited_is_the_reference_without_citations():
    expected = copy.deepcopy(fake_model.sr_reference_submission())
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
    assert all(r["content"]["auto_proposal"] == 1 for r in rep["criteria"])
    assert all(r["evidence_support"]["auto_proposal"] == 1 for r in rep["criteria"])


def test_uncited_keeps_content_but_loses_evidence():
    rep = graded("uncited")
    assert all(r["content"]["auto_proposal"] == 1 for r in rep["criteria"])
    for r in rep["criteria"]:
        ev = r["evidence_support"]
        assert ev["value"] == 0 and ev["source"] == "auto", (r["criterion_id"], ev)
    assert len(rep["flags"]["uncited_findings"]) == len(load("uncited")["findings"])


def test_uncertain_satisfies_nothing_and_asserts_nothing():
    rep = graded("uncertain")
    assert all(r["content"]["auto_proposal"] == 0 for r in rep["criteria"])
    for cid in ("T03.01", "T03.02", "T03.03", "T04.01"):
        assert row(rep, cid)["content"]["value"] == 0
    assert rep["severe_flags"] == [] and rep["flags"]["accounting_traps"] == []


def test_incomplete_covers_only_the_initiating_event_and_frequency():
    rep = graded("incomplete")
    full = {
        r["criterion_id"] for r in rep["criteria"] if r["content"]["auto_proposal"] == 1
    }
    assert {"T01.01", "T01.02", "T01.03a", "T01.03b", "T01.04"} <= full
    assert {"T03.01", "T03.02", "T03.03", "T04.01", "T04.03"} <= full
    assert {cid[:3] for cid in full} <= {"T01", "T03", "T04", "T16"}
    for cid in ("T02.05a", "T09.02a", "T12.01a", "T07.01", "T17.03"):
        assert row(rep, cid)["content"]["auto_proposal"] == 0


def test_incorrect_trips_the_accounting_checks():
    rep = graded("incorrect")
    flagged = rep["flags"]["accounting_traps"]
    traps = {(t["type"], t.get("figure_id"), t["finding_id"]) for t in flagged}
    for expected in (
        ("mismatched", "GEN_OFG_1990", "X02"),  # 1,990 MW given as ESO's Table 2 total
        ("misattributed", "LFDD_931", "X03"),  # 931 MW attributed to Ofgem
        ("misattributed", "LFDD_OFG_892", "X04"),  # 892 MW attributed to the DNOs
        ("misattributed", "RESP_SECONDARY_1338", "X07"),
        ("misattributed", "INERTIA_ESO_219632", "X08"),
    ):
        assert expected in traps, (expected, traps)
    overlap = {
        (t["finding_id"], t["group"]) for t in flagged if t["type"] == "overlap_sum"
    }
    assert overlap == {
        ("X05", "lom_total_with_its_components"),  # 500 MW summed with 150 + 350 MW
        ("X05", "dg_loss_alternatives"),  # 462 and 500 MW estimate the same losses
        ("X06", "eso_total_mixed_with_other_bases"),  # 1,878 MW + net 200 + 550 MW
    }
    caps = {c["id"] for r in rep["criteria"] for c in r["layers"]["caps"]}
    assert {
        "ofgem_1990_on_wrong_basis",
        "overlapping_dg_estimates_summed",
        "eso_total_mixed_with_other_bases",
        "secondary_on_wrong_account",
    } <= caps
    assert row(rep, "T08.05")["content"]["auto_proposal"] == 0


def test_incorrect_raises_the_severe_flags_and_contradictions():
    rep = graded("incorrect")
    severe = {(f["flag_id"], f["finding_id"]) for f in rep["severe_flags"]}
    assert ("SF1", "X09") in severe  # invented Little Barford root cause
    assert ("SF2", "X10") in severe  # invented control-log entry S07-E14
    caps = {c["id"]: c for r in rep["criteria"] for c in r["layers"]["caps"]}
    assert {"other_trip_as_initiator", "drc_as_cause", "gt1b_automatic"} <= set(caps)
    for cid in ("T07.04", "T07.05", "T17.01"):
        assert any(
            c["kind"] == "severe_suspected" for c in row(rep, cid)["layers"]["caps"]
        )


def test_incorrect_frequency_values_score_zero_automatically():
    rep = graded("incorrect")
    for cid in ("T03.01", "T03.02", "T04.01"):
        content = row(rep, cid)["content"]
        assert content["source"] == "auto" and content["value"] == 0, (cid, content)
