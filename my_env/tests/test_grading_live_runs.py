"""Regression tests from real live-run submissions (decision 18 in docs/DECISIONS.md).

The five submissions in ``tests/fixtures/live`` are copied byte for byte from the live
runs (see its README): four panel runs on bundle 1.1.0 and live run 001 on bundle 1.0.0,
graded against a copy of the bundle it ran on. Grader 0.3.0 / key 0.3.0 auto-scored four
D3 landmarks 0 and proposed 0 for two D4.2 mechanisms although the answers were present:

* opus55-002 D3.3: the quantity of F20 is "283 s after the fault"; the statement and
  event_time give 50.001 Hz at 16:57:16.
* haiku45-001 D3.2: the quantity of F09 is the 1.208 Hz drop; the statement gives
  48.787 Hz at 16:53:49.
* haiku45-001 D3.3: the quantity of F11 is 207 s; the statement gives 50.0 Hz at
  16:57:16 (and the matcher had picked the pre-event average of F08).
* opus55-002 and sonnet55-001 D4.2: the speed-signal mechanism is stated in a finding
  labelled unknown (for its open root cause).

Haiku 4.5 never reported the first local minimum: its D3.1 must stay an automatic 0.

A second verification round (the ``round 2`` tests below) found that the rules still
paired a value with the reference time of an offset ("207 s after its minimum at
16:53:49"), let a structured quantity hide a correct value in its own statement,
credited timed values worded as "still below" or "not yet", credited any seconds near
"49 Hz" as the time below 49 Hz, credited mechanisms labelled hypothesis or framed as not
established, and read no value written without a unit. In the live runs this changes
only the D1.1 proposals of opus55-002 and sonnet55-001 (lightning attributed to "the
fault" in F02, the circuit in F01) and adds reviewer notes (opus55-002 D2.4/D2.5 times
given only in the report, haiku45-001 D3.5 convention).
"""

from __future__ import annotations

import copy
import functools
import hashlib
import json
from pathlib import Path

import pytest

from environment.incident.catalogue import Catalogue
from environment.incident.grading import (
    GradingError,
    _resolved_time_spans,
    grade_submission,
    load_key,
    statement_times,
)
from environment.incident.paths import DEFAULT_BUNDLE_DIR

ENV_ROOT = Path(__file__).resolve().parents[1]
LIVE = ENV_ROOT / "tests" / "fixtures" / "live"
REFERENCE = (
    ENV_ROOT
    / "src/environment/tasks/gb_2019_electrical_disturbance/reference/reference_submission.json"
)
RUNS = {
    run["run_id"]: run
    for run in json.loads((LIVE / "runs.json").read_text(encoding="utf-8"))["runs"]
}
KEY = load_key()
CATALOGUE = Catalogue.load(DEFAULT_BUNDLE_DIR)
CATALOGUES = {"1.1.0": CATALOGUE, "1.0.0": Catalogue.load(LIVE / "bundle-1.0.0")}
R01_EVENT = [
    {
        "evidence_id": "R01",
        "locator": "time:2019-08-09T16:52:30+01:00/2019-08-09T16:58:00+01:00",
    }
]


@functools.cache
def graded(run_id: str) -> dict:
    run = RUNS[run_id]
    text = (LIVE / run["file"]).read_text(encoding="utf-8")
    return grade_submission(
        text, CATALOGUES[run["bundle_version"]], KEY, run["trace_info"]
    )


def rows(report: dict) -> dict[str, dict]:
    return {c["criterion_id"]: c for c in report["criteria"]}


def element(row: dict, element_id: str) -> dict:
    return next(e for e in row["auto_checks"]["elements"] if e["id"] == element_id)


# -- the fixtures are the live submissions --------------------------------------------
@pytest.mark.parametrize("run_id", sorted(RUNS))
def test_fixture_is_the_live_submission_on_its_own_bundle(run_id):
    run = RUNS[run_id]
    data = (LIVE / run["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == run["file_sha256"]
    catalogue = CATALOGUES[run["bundle_version"]]
    assert catalogue.bundle_version == run["bundle_version"]
    assert catalogue.bundle_sha256 == run["bundle_sha256"]
    report = graded(run_id)
    # the canonical sha256 the episode recorded in state.json when it froze
    assert report["submission"]["sha256"] == run["submission_sha256"]


def test_bundle_100_run_does_not_validate_on_the_current_bundle():
    """Why the 1.0.0 bundle is kept with the fixtures: run 001 cites lines that do not
    exist in bundle 1.1.0."""
    run = RUNS["gb2019-live-opus55-001"]
    with pytest.raises(GradingError, match="not valid"):
        grade_submission((LIVE / run["file"]).read_text(), CATALOGUE, KEY)


# -- D3 and D4 outcomes per run -----------------------------------------------------------
# (value, source) of the D3 auto-numeric criteria, and the D4.2/D4.3 proposals.
EXPECTED = {
    "gb2019-v2-opus55-002": {
        "D3.1": (1.0, "auto"),
        "D3.2": (1.0, "auto"),
        "D3.3": (1.0, "auto"),  # was 0 (quantity: 283 s after the fault)
        "D3.4": (1.0, "auto"),
        "D4.2": 1.0,  # was 0 (mechanism in F11, status unknown)
        "D4.3": 1.0,  # was 0.5 (GT1A mechanism in F12, status unknown)
    },
    "gb2019-v2-opus55-003": {
        "D3.1": (1.0, "auto"),
        "D3.2": (1.0, "auto"),
        "D3.3": (1.0, "auto"),
        "D3.4": (1.0, "auto"),
        "D4.2": 1.0,
        "D4.3": 1.0,
    },
    "gb2019-v2-sonnet55-001": {
        "D3.1": (1.0, "auto"),
        "D3.2": (1.0, "auto"),
        "D3.3": (1.0, "auto"),
        "D3.4": (1.0, "auto"),
        "D4.2": 1.0,  # was 0 (mechanism in F09, status unknown)
        "D4.3": 1.0,
    },
    "gb2019-v2-haiku45-001": {
        "D3.1": (0.0, "auto"),  # genuine omission: stays 0
        "D3.2": (1.0, "auto"),  # was 0 (quantity: the 1.208 Hz drop)
        "D3.3": (1.0, "auto"),  # was 0 (quantity: 207 s; F08 average picked)
        "D3.4": (1.0, "auto"),
        "D4.2": 1.0,
        "D4.3": 1.0,
    },
    "gb2019-live-opus55-001": {
        "D3.1": (None, "pending"),  # only the 49.08-49.27 Hz plateau: a human decides
        "D3.2": (1.0, "auto"),
        "D3.3": (1.0, "auto"),
        "D3.4": (0.0, "auto"),  # no time below 49 Hz anywhere (genuine omission)
        "D4.2": 1.0,
        "D4.3": 1.0,
    },
}


# D1.1 proposals: opus55-002 and sonnet55-001 attribute "the fault" to lightning in F02
# and give the circuit and fault type in F01 (0.5 before key 0.3.1 round 2).
D11 = {
    "gb2019-v2-opus55-002": 1.0,
    "gb2019-v2-opus55-003": 1.0,
    "gb2019-v2-sonnet55-001": 1.0,
    "gb2019-v2-haiku45-001": 1.0,
    "gb2019-live-opus55-001": 1.0,
}


@pytest.mark.parametrize("run_id", sorted(D11))
def test_live_run_d1_1_lightning_in_its_own_finding(run_id):
    row = rows(graded(run_id))["D1.1"]
    assert row["content"]["auto_proposal"] == D11[run_id], row["content"]["basis"]


def test_live_run_reviewer_notes():
    """Notes point the reviewer at what the automated proposal cannot credit; they never
    change a proposal."""
    r = rows(graded("gb2019-v2-opus55-002"))
    for cid, el in (("D2.4", "trip_time"), ("D2.5", "gt1b_group")):
        content = r[cid]["content"]
        assert content["auto_proposal"] == 0.5
        assert (
            f"only the report text gives a time within tolerance for {el}"
            in (content["basis"])
        )
        assert "16:53:58.600000" in content["basis"]
    d35 = rows(graded("gb2019-v2-haiku45-001"))["D3.5"]
    assert d35["content"]["auto_proposal"] == 1.0
    assert (
        "the convention F10 states does not reproduce the 33 s"
        in (d35["content"]["basis"])
    )
    assert d35["auto_checks"]["notes"]
    for run_id in sorted(set(RUNS) - {"gb2019-v2-haiku45-001"}):
        assert not rows(graded(run_id))["D3.5"]["auto_checks"]["notes"], run_id


@pytest.mark.parametrize("run_id", sorted(EXPECTED))
def test_live_run_d3_and_d4_outcomes(run_id):
    r = rows(graded(run_id))
    for cid, want in EXPECTED[run_id].items():
        if cid.startswith("D3"):
            got = (r[cid]["content"]["value"], r[cid]["content"]["source"])
            assert got == want, (cid, r[cid]["content"]["basis"])
        else:
            assert r[cid]["content"]["auto_proposal"] == want, (
                cid,
                r[cid]["content"]["basis"],
            )
        if r[cid]["content"]["value"] == 1.0 and cid.startswith("D3"):
            assert r[cid]["evidence_support"]["value"] == 1, cid


def test_opus55_002_recovery_is_read_from_the_statement():
    row = rows(graded("gb2019-v2-opus55-002"))["D3.3"]
    best = row["auto_checks"]["candidates"][0]
    assert row["matched_finding_ids"] == ["F20"]
    assert (best["value"], best["value_source"], best["time_ok"]) == (
        50.001,
        "statement",
        True,
    )
    assert row["evidence_support"] == {**row["evidence_support"], "value": 1}


def test_haiku_drop_and_interval_quantities_fall_back_to_the_statement():
    r = rows(graded("gb2019-v2-haiku45-001"))
    d32 = r["D3.2"]["auto_checks"]["candidates"][0]
    assert (d32["finding_id"], d32["value"], d32["value_source"]) == (
        "F09",
        48.787,
        "statement",
    )
    # the minimum is paired with its own time, the starting value with 16:52:33
    assert d32["times"] == ["2019-08-09T16:53:49+01:00"]
    d33 = r["D3.3"]["auto_checks"]["candidates"]
    assert [c["finding_id"] for c in d33] == ["F11"]  # never the F08 pre-event average
    assert (d33[0]["value"], d33[0]["time_ok"]) == (50.0, True)
    assert all(
        o["location"] != "F08" for o in r["D3.3"]["auto_checks"]["other_candidates"]
    )


def test_haiku_first_minimum_is_a_genuine_omission():
    """48.787 Hz (dated 16:53:49 elsewhere), the 49 Hz threshold and the pre-event
    statistics are not candidates for the first minimum."""
    row = rows(graded("gb2019-v2-haiku45-001"))["D3.1"]
    assert row["content"]["value"] == 0.0 and row["content"]["source"] == "auto"
    assert "no candidate value anywhere" in row["content"]["basis"]
    # the values dated outside the window are named for the reviewer
    assert "48.787 Hz at 2019-08-09T16:53:49+01:00 in F09" in row["content"]["basis"]
    assert row["auto_checks"]["candidates"] == []
    assert row["auto_checks"]["other_candidates"] == []
    assert row["evidence_support"]["source"] == "not_applicable"


@pytest.mark.parametrize(
    ("run_id", "cid", "element_id", "fid"),
    [
        ("gb2019-v2-opus55-002", "D4.2", "speed_discrepancy", "F11"),
        ("gb2019-v2-sonnet55-001", "D4.2", "speed_discrepancy", "F09"),
        ("gb2019-v2-opus55-002", "D4.3", "gt1a_pressure", "F12"),
        ("gb2019-v2-opus55-002", "D4.3", "gt1a_automatic", "F12"),
    ],
)
def test_mechanism_stated_in_an_unknown_finding_is_recognised(
    run_id, cid, element_id, fid
):
    row = rows(graded(run_id))[cid]
    el = element(row, element_id)
    assert fid in el["finding_ids"]
    assert fid in el["detail"]["other_status_finding_ids"]
    # the same finding still earns the D4.4 labelling credit
    d44 = rows(graded(run_id))["D4.4"]
    assert fid in d44["matched_finding_ids"]


def test_live_run_d4_4_is_unchanged():
    """Status still decides D4.4: sonnet labelled the pressure causes 'reported'."""
    proposals = {
        run_id: rows(graded(run_id))["D4.4"]["content"]["auto_proposal"]
        for run_id in RUNS
    }
    assert proposals == {
        "gb2019-v2-opus55-002": 1.0,
        "gb2019-v2-opus55-003": 1.0,
        "gb2019-v2-sonnet55-001": 0.5,
        "gb2019-v2-haiku45-001": 0.5,
        "gb2019-live-opus55-001": 1.0,
    }


# -- the rules, on small synthetic submissions ---------------------------------------
def submission(findings: list[dict], summary: str = "Summary.") -> dict:
    return {
        "schema_version": "3.0",
        "variant_id": "baseline",
        "report": {"executive_summary": summary, "sections": []},
        "findings": findings,
    }


def finding(fid: str, statement: str, status: str = "observed", **extra) -> dict:
    return {
        "finding_id": fid,
        "statement": statement,
        "status": status,
        "citations": extra.pop("citations", R01_EVENT),
        **extra,
    }


def grade(findings: list[dict], summary: str = "Summary.") -> dict[str, dict]:
    return rows(grade_submission(submission(findings, summary), CATALOGUE, KEY))


PRE_EVENT = finding(
    "F1",
    "Pre-disturbance system frequency was normal, averaging 50.0058 Hz.",
    quantity={
        "value": 50.0058,
        "unit": "Hz",
        "basis": "mean of the samples from 16:40:00 to 16:52:32 BST",
    },
)


def test_rule_b_a_pre_event_average_is_not_a_recovery_candidate():
    row = grade([PRE_EVENT])["D3.3"]
    assert (row["content"]["value"], row["content"]["source"]) == (0.0, "auto")
    assert "no candidate value anywhere" in row["content"]["basis"]
    recovery = finding(
        "F2",
        "Frequency recovered to 50.0 Hz at 16:57:16 BST, 207 s after the minimum.",
        quantity={"value": 207, "unit": "s", "basis": "16:57:16 minus 16:53:49"},
    )
    row = grade([PRE_EVENT, recovery])["D3.3"]
    assert (row["content"]["value"], row["matched_finding_ids"]) == (1.0, ["F2"])


def test_rule_a_value_in_the_derivation_with_the_statement_time():
    f = finding(
        "F1",
        "Frequency first returned to 50 Hz at 16:57:16 BST.",
        quantity={"value": 283, "unit": "s", "basis": "16:57:16 minus 16:52:33"},
        derivation="first R01 sample >= 50 Hz after the minimum: 50.001 Hz (row 1037)",
    )
    row = grade([f])["D3.3"]
    best = row["auto_checks"]["candidates"][0]
    assert row["content"]["value"] == 1.0
    assert (best["value"], best["value_source"]) == (50.001, "derivation")


def test_rule_a_quantity_dated_outside_the_window_falls_back_to_the_statement():
    """The quantity is the event minimum (outside the D3.1 window); the statement also
    gives the first minimum with its own time."""
    f = finding(
        "F1",
        "Frequency fell to a first minimum of 49.083 Hz at 16:52:59 BST and to the "
        "event minimum of 48.787 Hz at 16:53:49 BST.",
        quantity={"value": 48.787, "unit": "Hz", "basis": "event minimum"},
        event_time="2019-08-09T16:53:49+01:00",
    )
    r = grade([f])
    assert r["D3.1"]["content"]["value"] == 1.0
    assert r["D3.1"]["auto_checks"]["candidates"][0]["value"] == 49.083
    assert r["D3.2"]["content"]["value"] == 1.0
    assert r["D3.2"]["auto_checks"]["candidates"][0]["value_source"] == "quantity"


@pytest.mark.parametrize(
    ("where", "status"),
    [("report", None), ("finding", "unknown"), ("finding", "hypothesis")],
)
def test_rule_c_a_candidate_outside_the_credited_findings_goes_to_review(where, status):
    text = "The first minimum was 49.083 Hz at 16:52:59 BST."
    findings = [finding("F1", "The fault was cleared in 74 ms.", "reported")]
    if where == "finding":
        findings.append(finding("F2", text, status))
    row = grade(findings, summary=text if where == "report" else "Summary.")["D3.1"]
    assert row["content"]["source"] == "pending"
    assert row["content"]["auto_proposal"] == 0.0
    assert row["matched_finding_ids"] == []
    other = row["auto_checks"]["other_candidates"]
    assert [(o["value"], o["level"]) for o in other] == [(49.083, 1.0)]
    location = "report.executive_summary" if where == "report" else "F2"
    assert location in row["content"]["basis"]


@pytest.mark.parametrize(
    "statement",
    [
        "Frequency fell below 49 Hz and the 48.8 Hz LFDD stage operated.",
        "Frequency stayed above 49.5 Hz before the fault.",
        "The statutory limit is 49.5 Hz.",
    ],
)
def test_rule_c_thresholds_are_not_candidates(statement):
    r = grade([finding("F1", statement)], summary=statement)
    for cid in ("D3.1", "D3.2", "D3.3"):
        content = r[cid]["content"]
        assert (content["value"], content["source"]) == (0.0, "auto"), cid


def test_rule_c_a_value_dated_outside_the_window_elsewhere_is_not_a_candidate():
    f = finding("F1", "The event minimum was 48.787 Hz at 16:53:49 BST.")
    r = grade([f], summary="Frequency reached a minimum of 48.787 Hz.")
    assert r["D3.2"]["content"]["value"] == 1.0
    d31 = r["D3.1"]["content"]
    assert (d31["value"], d31["source"]) == (0.0, "auto")


def test_rule_c_a_structured_value_without_a_time_goes_to_review():
    f = finding(
        "F1",
        "The event minimum was 48.787 Hz.",
        quantity={"value": 48.787, "unit": "Hz", "basis": "minimum 1-s sample"},
    )
    row = grade([f])["D3.2"]
    assert row["content"]["source"] == "pending"
    assert "no time in the landmark window" in row["content"]["basis"]
    assertion = grade_submission(submission([f]), CATALOGUE, KEY)["assertion_quality"]
    assert assertion["assertions"][0]["auto_proposal"] is None


def _reference_with_duration(value: float, consistent: bool) -> dict:
    """The reference submission with the F23 duration quantity set to ``value``; with
    ``consistent`` its statement and derivation say the same (no other duration)."""
    sub = json.loads(REFERENCE.read_text(encoding="utf-8"))
    for f in sub["findings"]:
        if f["finding_id"] == "F23":
            f["quantity"]["value"] = value
            if consistent:
                f["statement"] = (
                    f"The frequency was strictly below 49 Hz for {value:g} s under a "
                    "zero-order hold (16:53:41 to 16:54:13 BST)."
                )
                f["derivation"] = "run_python on the R01 CSV: samples below 49 Hz."
    return sub


def test_rule_c_a_structured_value_clearly_wrong_stays_decided():
    """The duration quantity is 4 s off and its finding says nothing else; the report's
    33 s is pointed out, not used."""
    sub = _reference_with_duration(37, consistent=True)
    row = rows(grade_submission(sub, CATALOGUE, KEY))["D3.4"]
    assert (row["content"]["value"], row["content"]["source"]) == (0.0, "auto")
    assert "note: a value within tolerance also appears in" in row["content"]["basis"]
    assert "report.executive_summary" in row["content"]["basis"]


ST1C = "ST1C tripped when its three speed signals {} after the fault was cleared."


@pytest.mark.parametrize(
    ("statement", "status", "expected"),
    [
        (ST1C.format("disagreed"), "reported", 1.0),
        (ST1C.format("did not agree"), "reported", 1.0),
        (ST1C.format("were not in agreement"), "reported", 1.0),
        (ST1C.format("differed"), "observed", 1.0),
        (ST1C.format("were inconsistent"), "observed", 1.0),
        (ST1C.format("diverged"), "observed", 1.0),
        (
            "The steam turbine is reported to have tripped because its three speed "
            "signals disagreed after the fault was cleared. The root cause of that "
            "disagreement has not been established.",
            "unknown",
            1.0,
        ),
        (
            "Reported mechanism for the ST1C trip: a discrepancy between the three "
            "independent speed sensors exceeded the control-system tolerance after "
            "fault clearance. The root cause of the discrepancy is not established.",
            "unknown",
            1.0,
        ),
        (
            "The ST1C speed signals may have disagreed, causing the trip.",
            "hypothesis",
            0.0,
        ),
        (
            "Why the ST1C speed signals disagreed has not been established.",
            "unknown",
            0.0,
        ),
        (
            "Ofgem's preliminary view is that the ST1C speed readings and the resulting "
            "trip were due to the transmission fault.",
            "hypothesis",
            0.0,
        ),
    ],
)
def test_rule_d_speed_signal_mechanism(statement, status, expected):
    f = finding(
        "F1",
        statement,
        status,
        citations=[{"evidence_id": "S04", "locator": "L56-L59"}],
    )
    assert grade([f])["D4.2"]["content"]["auto_proposal"] == expected


@pytest.mark.parametrize(
    ("statement", "status", "expected"),
    [
        (
            "GT1A tripped automatically on high steam-bypass pressure and GT1B was "
            "tripped manually because of excessive steam pressure. The root cause of "
            "these high-pressure conditions has not been established.",
            "unknown",
            1.0,
        ),
        (
            "GT1A may have tripped automatically on high bypass pressure, and GT1B was "
            "possibly tripped manually because of steam pressure.",
            "hypothesis",
            0.0,
        ),
    ],
)
def test_rule_d_gas_turbine_mechanisms(statement, status, expected):
    f = finding(
        "F1",
        statement,
        status,
        citations=[{"evidence_id": "S04", "locator": "L56-L59"}],
    )
    assert grade([f])["D4.3"]["content"]["auto_proposal"] == expected


@pytest.mark.parametrize(
    "change",
    [
        {"statuses": None},  # nothing to widen
        {"other_statuses": {"all": "\\btrip"}},  # not a list of groups
        {"fields": ["statement", "derivation"]},  # sentences of the statement only
    ],
)
def test_malformed_other_statuses_is_rejected(change):
    key = copy.deepcopy(KEY)
    crit = next(c for c in key["criteria"] if c["criterion_id"] == "D4.2")
    el = next(e for e in crit["auto"]["elements"] if e["id"] == "speed_discrepancy")
    el.update(change)
    if el.get("statuses") is None:
        el.pop("statuses")
    with pytest.raises(GradingError, match="other_statuses"):
        grade_submission(submission([]), CATALOGUE, key)


# -- round 2: offsets, unsettled wording and hedged mechanisms (verifier cases) -------
def _d3(findings: list[dict], cid: str, summary: str = "Summary.") -> dict:
    return grade(findings, summary)[cid]


def _content(row: dict) -> tuple:
    return (row["content"]["value"], row["content"]["source"])


def _assertion(findings: list[dict], summary: str = "Summary.") -> str | None:
    report = grade_submission(submission(findings, summary), CATALOGUE, KEY)
    return report["assertion_quality"]["assertions"][0]["auto_proposal"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # a number before the relation: the reference is moved by the offset
        (
            "recovered to 50.0 Hz 207 seconds after reaching its minimum at 16:53:49",
            [("offset", "16:57:16")],
        ),
        (
            "came 26 s after fault inception at 16:52:33.490 BST",
            [("offset", "16:52:59.490000")],
        ),
        ("4 min 43 s after the fault at 16:52:33", [("offset", "16:57:16")]),
        (
            "207 seconds (3 minutes 27 seconds) after the minimum at 16:53:49",
            [("offset", "16:57:16")],
        ),
        (
            "reached 50.001 Hz 207 s after the 16:53:49 minimum",
            [("offset", "16:57:16")],
        ),
        ("16:52:33 + 26 s", [("offset", "16:52:59")]),
        ("10 s before the trip at 16:53:31", [("offset", "16:53:21")]),
        # a reference without a number only bounds the time
        ("after the minimum at 16:53:49", [("after", "16:53:49")]),
        (
            "seconds after fault inception at 16:52:33.490",
            [("after", "16:52:33.490000")],
        ),
        ("50.0 Hz before 16:52:33", [("before", "16:52:33")]),
        # written times
        ("from 16:53:41 to 16:54:13", [("at", "16:53:41"), ("at", "16:54:13")]),
        (
            "fell from 49.995 Hz at 16:52:33 to 48.787 Hz at 16:53:49",
            [("at", "16:52:33"), ("at", "16:53:49")],
        ),
        ("48.787 Hz at 16:53:49, 76 s after the fault", [("at", "16:53:49")]),
        ("after the fault, frequency was 49.083 Hz at 16:52:59", [("at", "16:52:59")]),
    ],
)
def test_round2_offset_references_are_resolved(text, expected):
    got = [
        (kind, when.astimezone(UTC_PLUS_1).time().isoformat())
        for kind, when, _, _ in _resolved_time_spans(text.lower())
    ]
    assert got == expected


UTC_PLUS_1 = __import__("datetime").timezone(__import__("datetime").timedelta(hours=1))


def test_round2_twelve_hour_clock_times():
    assert [t.isoformat() for t in statement_times("at 4:52:59 pm BST")] == [
        "2019-08-09T16:52:59+01:00"
    ]
    assert [t.isoformat() for t in statement_times("at 12:30 a.m.")] == [
        "2019-08-09T00:30:00+01:00"
    ]
    # a 24-hour time with a stray 'pm' is left as written
    assert [t.isoformat() for t in statement_times("16:52:59 pm")] == [
        "2019-08-09T16:52:59+01:00"
    ]


@pytest.mark.parametrize(
    ("statement", "quantity", "cid"),
    [
        (  # haiku F11 with the clock time removed
            "System frequency recovered to 50.0 Hz 207 seconds after reaching its "
            "minimum at 16:53:49 BST.",
            {
                "value": 207,
                "unit": "s",
                "basis": "first sample at or above 50 Hz minus the minimum time",
            },
            "D3.3",
        ),
        (
            "The first trough, 49.083 Hz, came 26 s after fault inception at "
            "16:52:33.490 BST.",
            {"value": 26, "unit": "s", "basis": "16:52:59 minus 16:52:33"},
            "D3.1",
        ),
        (
            "Frequency first returned to 50 Hz (50.001 Hz) 283 s after the fault at "
            "16:52:33 BST.",
            {"value": 283, "unit": "s", "basis": "16:57:16 minus 16:52:33"},
            "D3.3",
        ),
    ],
)
def test_round2_an_offset_from_a_written_time_dates_the_value(statement, quantity, cid):
    """Issue 1: the clock time is the reference of the offset, not the value's time."""
    row = _d3([finding("F1", statement, quantity=quantity)], cid)
    assert _content(row) == (1.0, "auto"), row["content"]["basis"]
    best = row["auto_checks"]["candidates"][0]
    assert best["time_source"] == "statement offset"


def test_round2_a_basis_reference_does_not_exclude_the_value():
    """Issue 1 (3): opus55-002 F20 without its event_time; the basis time is the fault
    time that the 283 s are counted from."""
    statement = (
        "Frequency first returned to 50 Hz (50.001 Hz) about 283 s after the fault."
    )
    for basis in (
        "seconds after fault inception at 16:52:33.490 BST",
        "seconds after fault inception",
    ):
        f = finding(
            "F1", statement, quantity={"value": 283, "unit": "s", "basis": basis}
        )
        row = _d3([f], "D3.3")
        assert _content(row) == (None, "pending"), basis
        assert "no candidate value anywhere" not in row["content"]["basis"]
        assert row["auto_checks"]["candidates"][0]["value"] == 50.001


def test_round2_a_report_offset_does_not_exclude_an_untimed_finding_value():
    """Issue 1 (4): the report dates 50.001 Hz by an offset to the minimum, so the
    finding's untimed 50.001 Hz stays a candidate."""
    f = finding("F1", "Recovery: frequency first reached 50.001 Hz after the minimum.")
    row = _d3(
        [f],
        "D3.3",
        summary="Frequency reached 50.001 Hz 207 s after the 16:53:49 minimum.",
    )
    assert _content(row) == (None, "pending")
    assert "no candidate value anywhere" not in row["content"]["basis"]
    other = row["auto_checks"]["other_candidates"][0]
    assert (other["value"], other["times"], other["level"]) == (
        50.001,
        ["2019-08-09T16:57:16+01:00"],
        1.0,
    )


def test_round2_an_offset_to_the_wrong_time_is_not_credited():
    """Issue 1 (5): 21 s after 16:53:49 is 16:54:10, not the minimum's time: a human
    decides (a prose value is never failed automatically), and no assertion is
    proposed as supported."""
    f = finding(
        "F1",
        "The minimum of 48.787 Hz occurred about 21 s after LFDD operated at "
        "16:53:49 BST.",
        quantity={"value": 21, "unit": "s", "basis": "after the LFDD trigger"},
    )
    row = _d3([f], "D3.2")
    assert _content(row) == (None, "pending")
    assert row["auto_checks"]["candidates"][0]["times"] == ["2019-08-09T16:54:10+01:00"]
    assert _assertion([f]) is None


def test_round2_a_value_dated_outside_only_by_an_offset_goes_to_review():
    """A value an offset dates outside the window is listed for the reviewer, and does
    not exclude the same value written without a time elsewhere."""
    dated = finding(
        "F2", "Frequency was 49.083 Hz 60 s after the fault at 16:52:33 BST."
    )
    row = _d3([dated], "D3.1")
    assert _content(row) == (None, "pending")
    assert row["auto_checks"]["other_candidates"][0]["outside_window"] is True
    assert "an offset dates it outside the window" in row["content"]["basis"]
    untimed = finding("F1", "The first trough was 49.083 Hz.")
    row = _d3([untimed, dated], "D3.1")
    assert _content(row) == (None, "pending")
    assert [c["finding_id"] for c in row["auto_checks"]["candidates"]] == ["F1"]


def test_round2_a_reference_without_a_number_only_bounds_the_value():
    before = finding("F1", "Frequency was 50.0 Hz before 16:52:33 BST.")
    assert _content(_d3([before], "D3.3")) == (0.0, "auto")
    after = finding(
        "F1", "Frequency recovered to 50.001 Hz after the minimum at 16:53:49 BST."
    )
    row = _d3([after], "D3.3")
    assert _content(row) == (None, "pending")
    assert row["auto_checks"]["candidates"][0]["times"] == []


@pytest.mark.parametrize(
    ("statement", "quantity", "event_time", "cid", "value"),
    [
        (  # issue 2 (1): the quantity is the LFDD threshold
            "Frequency crossed the 48.8 Hz LFDD stage-1 threshold at about 16:53:48 BST "
            "and reached its minimum of 48.787 Hz at 16:53:49 BST.",
            {"value": 48.8, "unit": "Hz", "basis": "LFDD stage 1 threshold"},
            "2019-08-09T16:53:48+01:00",
            "D3.2",
            48.787,
        ),
        (  # issue 2 (2): the quantity is the partial recovery
            "Frequency fell to a first trough of 49.083 Hz at 16:52:59 BST and had "
            "recovered to 49.17 Hz by 16:53:08 BST.",
            {"value": 49.17, "unit": "Hz", "basis": "sample at 16:53:08"},
            "2019-08-09T16:53:08+01:00",
            "D3.1",
            49.083,
        ),
    ],
)
def test_round2_a_quantity_outside_tolerance_does_not_hide_its_statement(
    statement, quantity, event_time, cid, value
):
    """Issue 2: the statement's value within tolerance is evaluated; the finding is
    inconsistent, so a human decides, and its assertion is not proposed contradicted."""
    f = finding("F1", statement, quantity=quantity, event_time=event_time)
    row = _d3([f], cid)
    assert _content(row) == (None, "pending")
    best = row["auto_checks"]["candidates"][0]
    assert (best["value"], best["value_source"], best["level_if_settled"]) == (
        value,
        "statement",
        1.0,
    )
    assert (
        f"the structured quantity of F1 ({quantity['value']} Hz)"
        in (row["content"]["basis"])
    )
    assert _assertion([f]) is None


def test_round2_a_quantity_outside_tolerance_with_its_own_prose_stays_decided():
    """The statement repeats the quantity (no better value): still an automatic 0."""
    f = finding(
        "F1",
        "Frequency was arrested at 49.1 Hz at 16:52:58.",
        "reported",
        quantity={"value": 49.1, "unit": "Hz", "basis": "ESO timeline"},
        event_time="2019-08-09T16:52:58+01:00",
    )
    assert _content(_d3([f], "D3.1")) == (0.0, "auto")
    assert _assertion([f]) == "contradicted"


def test_round2_a_duration_quantity_beside_a_correct_statement_goes_to_review():
    """The reference F23 with its quantity set to 37 s: its statement still says 33 s
    (and 34 s, 33.96 s)."""
    sub = _reference_with_duration(37, consistent=False)
    row = rows(grade_submission(sub, CATALOGUE, KEY))["D3.4"]
    assert _content(row) == (None, "pending")
    assert "the structured quantity of F23 (37 s)" in row["content"]["basis"]


def test_round2_a_seconds_quantity_worded_as_an_offset_does_not_fit_the_duration():
    """Issue 2 (3): 68 s is the offset from the fault (statement and basis), so the
    duration is read from the statement."""
    statement = (
        "Frequency first fell below 49 Hz at 16:53:41 BST, 68 s after the fault, and "
        "stayed below it for 33 s."
    )
    quantity = {
        "value": 68,
        "unit": "s",
        "basis": "16:53:41 minus 16:52:33 (after the fault)",
    }
    f = finding(
        "F1",
        statement,
        quantity=quantity,
        derivation="33 samples strictly below 49.000 Hz",
    )
    row = _d3([f], "D3.4")
    assert _content(row) == (1.0, "auto")
    assert row["auto_checks"]["candidates"][0]["value_source"] == "statement"
    assert _assertion([f]) == "supported"
    # worded as an offset in the statement only (neutral basis)
    f = finding("F1", statement, quantity={**quantity, "basis": "seconds"})
    assert _content(_d3([f], "D3.4")) == (1.0, "auto")
    # the duration only in the report: a human decides
    f = finding(
        "F1",
        "Frequency first fell below 49 Hz at 16:53:41 BST, 68 s after the fault.",
        quantity={"value": 68, "unit": "s", "basis": "16:53:41 minus 16:52:33"},
    )
    row = _d3([f], "D3.4", summary="Frequency was below 49 Hz for 33 s (33 samples).")
    assert _content(row) == (None, "pending")


@pytest.mark.parametrize(
    ("statement", "quantity"),
    [
        (
            "Frequency was still below 50 Hz at 16:57:15 BST and only first returned "
            "to 50 Hz at 16:58:30 BST.",
            {"value": 357, "unit": "s", "basis": "16:58:30 minus 16:52:33"},
        ),
        (
            "Frequency was still below 50 Hz at 16:57:15 BST and only first returned "
            "to 50 Hz at 16:58:30 BST.",
            None,
        ),
        (
            "Frequency had not returned to 50 Hz by 16:57:16 BST; it recovered at "
            "16:58:40 BST.",
            {"value": 367, "unit": "s", "basis": "after the fault"},
        ),
        ("Frequency remained near 50.0 Hz until 16:57:16 BST.", None),
    ],
)
def test_round2_a_timed_level_or_not_yet_wording_is_not_credited(statement, quantity):
    """Issue 3 (1): with a time, 'still below', 'had not returned' and 'until' make the
    value a state, not the recovery: a human decides."""
    extra = {"quantity": quantity} if quantity else {}
    f = finding("F1", statement, **extra)
    row = _d3([f], "D3.3")
    assert _content(row) == (None, "pending"), row["content"]["basis"]
    assert row["auto_checks"]["candidates"][0]["level"] == 0.0
    assert _assertion([f]) is None


@pytest.mark.parametrize(
    "statement",
    [
        "Frequency first returned to 50 Hz or above at 16:57:16 BST.",  # opus55-003 F17
        "Frequency first rose above 50 Hz at 16:57:16 BST.",
        # sonnet F17 without its event_time: the bare 50.001 does not take the time
        "Frequency first returned to 50.0 Hz at 16:57:16 BST (50.001).",
    ],
)
def test_round2_reaching_the_level_is_the_landmark(statement):
    assert _content(_d3([finding("F1", statement)], "D3.3")) == (1.0, "auto")


def test_round2_a_timed_threshold_outside_tolerance_is_not_a_candidate():
    row = _d3(
        [finding("F1", "Frequency did not fall below 49 Hz until 16:53:41 BST.")],
        "D3.2",
    )
    assert _content(row) == (0.0, "auto")
    assert "no candidate value anywhere" in row["content"]["basis"]


@pytest.mark.parametrize(
    "quantity",
    [{"value": 48.787, "unit": "Hz", "basis": "minimum"}, None],
)
def test_round2_seconds_without_duration_wording_are_not_credited(quantity):
    """Issue 3 (2): '33 s to fall to below 49 Hz' is not the time below 49 Hz."""
    extra = {"quantity": quantity} if quantity else {}
    f = finding(
        "F1",
        "After the GT1A trip, frequency took 33 s to fall from 49.27 Hz to below 49 Hz "
        "and then reached 48.787 Hz.",
        **extra,
    )
    row = _d3([f], "D3.4")
    assert _content(row) == (None, "pending")
    assert "no wording next to it makes it a duration" in row["content"]["basis"]


@pytest.mark.parametrize(
    "statement",
    [
        "Frequency was below 49 Hz for 33 s.",
        "The time below 49 Hz was 33 s.",
        "Duration below 49 Hz: 33 s (zero-order hold).",
        "Frequency spent 33 s strictly below 49 Hz.",
        "Counting the samples strictly below 49 Hz gives 33 s.",
        "The excursion below 49 Hz lasted 33 s.",
        "33 s below 49 Hz (16:53:41 to 16:54:13 BST).",
    ],
)
def test_round2_prose_durations_with_duration_wording_are_credited(statement):
    assert _content(_d3([finding("F1", statement)], "D3.4")) == (1.0, "auto")


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        (
            "Frequency fell to a first trough of 49.083 at 16:52:59 BST.",
            (None, "pending"),
        ),
        ("The first trough was 49,083 Hz at 16:52:59 BST.", (None, "pending")),
        ("First trough: f = 49.083 (Hz) at 16:52:59 BST.", (1.0, "auto")),
        ("The first trough was 49.083 Hz at 4:52:59 pm BST.", (1.0, "auto")),
        # a unitless number outside tolerance is no candidate
        ("Frequency fell to a first trough of 49.2 at 16:52:59 BST.", (0.0, "auto")),
    ],
)
def test_round2_values_without_a_unit_or_with_a_12_hour_time(statement, expected):
    """Issue 6: the answer written without a unit is a candidate for a human, never
    an automatic 0."""
    row = _d3([finding("F1", statement)], "D3.1")
    assert _content(row) == expected, row["content"]["basis"]


S04_CITE = [{"evidence_id": "S04", "locator": "L56-L59"}]


@pytest.mark.parametrize(
    ("statement", "status", "expected"),
    [
        (
            "The ST1C trip was caused by a discrepancy between its three speed signals. "
            "This remains a hypothesis.",
            "hypothesis",
            0.0,
        ),
        (
            "ST1C tripped because its three speed signals disagreed after the fault was "
            "cleared.",
            "hypothesis",
            0.0,
        ),
        (
            "It has not been established that ST1C tripped because its speed signals "
            "disagreed.",
            "unknown",
            0.0,
        ),
        (
            "There is no evidence that the ST1C trip was caused by a speed-signal "
            "discrepancy.",
            "unknown",
            0.0,
        ),
        (
            "It is unconfirmed that ST1C tripped on a speed-signal mismatch.",
            "unknown",
            0.0,
        ),
        (
            "RWE's early idea that ST1C tripped on a speed-signal discrepancy was later "
            "ruled out.",
            "hypothesis",
            0.0,
        ),
        (
            "RWE's early idea that ST1C tripped on a speed-signal discrepancy was later "
            "ruled out.",
            "unknown",
            0.0,
        ),
        (
            "ST1C tripped because its three speed signals disagreed. This has not been "
            "confirmed.",
            "unknown",
            0.0,
        ),
        (
            "Unknown: ST1C tripped when its three speed signals disagreed.",
            "unknown",
            0.0,
        ),
        # the open root cause, not the mechanism, is what is not established
        (
            "ST1C tripped because its three speed signals disagreed after the fault was "
            "cleared; the root cause of the disagreement has not been established.",
            "unknown",
            1.0,
        ),
        (
            "ST1C tripped because its three speed signals disagreed. It is not known "
            "why they disagreed.",
            "unknown",
            1.0,
        ),
    ],
)
def test_round2_rule_d_hedged_or_denied_speed_mechanism(statement, status, expected):
    """Issue 4: a hypothesis label, a negated or unproven mechanism, and a later
    sentence that hedges it earn no D4.2 credit."""
    f = finding("F1", statement, status, citations=S04_CITE)
    assert grade([f])["D4.2"]["content"]["auto_proposal"] == expected


@pytest.mark.parametrize(
    ("statement", "status", "expected"),
    [
        (
            "It is not established that GT1A tripped automatically on high "
            "steam-bypass pressure.",
            "unknown",
            0.0,
        ),
        (
            "GT1A tripped automatically on high bypass pressure and GT1B was tripped "
            "manually because of excessive steam pressure. This is our working "
            "hypothesis.",
            "hypothesis",
            0.0,
        ),
        (
            "It is not known if GT1B was tripped manually or by its own protection.",
            "unknown",
            0.0,
        ),
    ],
)
def test_round2_rule_d_hedged_gas_turbine_mechanisms(statement, status, expected):
    f = finding("F1", statement, status, citations=S04_CITE)
    assert grade([f])["D4.3"]["content"]["auto_proposal"] == expected


HORNSEA = (
    "The Hornsea de-load was caused by an insufficiently damped sub-synchronous "
    "resonance in the wind farm control system, with turbine overcurrent protection "
    "de-loading 1B and 1C and the weak internal network contributing."
)


@pytest.mark.parametrize(
    ("statement", "status", "expected"),
    [
        (HORNSEA + " This is a hypothesis we could not verify.", "hypothesis", 0.0),
        (HORNSEA + " This is a hypothesis we could not verify.", "unknown", 0.0),
        (
            HORNSEA + " Why the resonance was insufficiently damped has not been "
            "established.",
            "unknown",
            1.0,
        ),
    ],
)
def test_round2_rule_d_hornsea_mechanism(statement, status, expected):
    f = finding(
        "F1",
        statement,
        status,
        citations=[{"evidence_id": "S01", "locator": "L55-L63"}],
    )
    assert grade([f])["D4.1"]["content"]["auto_proposal"] == expected


R03_CITE = [{"evidence_id": "R03", "locator": "L25-L40"}]
FAULT = finding(
    "F01",
    "A single blue-phase-to-earth fault began at 16:52:33.490 BST on one Eaton "
    "Socon–Wymondley Main 400 kV circuit.",
    "reported",
    citations=R03_CITE,
)


@pytest.mark.parametrize(
    ("lightning", "expected"),
    [
        ("NGET states that lightning caused the fault.", 1.0),
        ("NGET and ESO attribute the fault to lightning.", 1.0),
        ("The fault was caused by a lightning strike near Wymondley Main.", 1.0),
        # lightning recorded, but not attributed to the fault
        (
            "Three lightning strikes were recorded near the circuit at 16:52:33 BST.",
            0.5,
        ),
        ("Lightning tripped the Blyth–Eccles–Stella West circuit at 16:50:44.", 0.5),
    ],
)
def test_round2_d1_1_lightning_attributed_in_its_own_finding(lightning, expected):
    """Issue 5 (1)(2): the circuit and fault type in F01, lightning attributed to
    'the fault' in F02."""
    f2 = finding("F02", lightning, "reported", citations=R03_CITE)
    assert grade([FAULT, f2])["D1.1"]["content"]["auto_proposal"] == expected


def test_round2_d2_report_only_time_is_noted_not_credited():
    """Issue 5 (3): a time derived only in the report is pointed out to the reviewer;
    the finding gives only the SOE offset (decision 9: the agent derives the time)."""
    f = finding(
        "F1",
        "GT1B (187 MW) was tripped manually at T + 84.613 s (T = 16:52:34 ± 0.5 s).",
        "reported",
        citations=[{"evidence_id": "S03", "locator": "L6-L9"}],
    )
    content = grade([f], summary="GT1B (187 MW) tripped at about 16:53:58.6 BST.")[
        "D2.4"
    ]["content"]
    assert content["auto_proposal"] == 0.5
    assert (
        "only the report text gives a time within tolerance for trip_time"
        in (content["basis"])
    )
    content = grade([f])["D2.4"]["content"]
    assert content["auto_proposal"] == 0.5 and "note" not in content["basis"]


@pytest.mark.parametrize(
    ("derivation", "basis", "noted"),
    [
        ("Count of 33 one-second samples at or below 49.0 Hz", "seconds", True),
        (
            "samples strictly below 49 Hz",
            "duration from first sample below 49.0 Hz to last sample below 49.0 Hz",
            False,  # strictly below reproduces 33 s
        ),
        (
            "samples below 49 Hz",
            "from first sample below 49.0 Hz to last sample below",
            True,
        ),
        ("samples strictly below 49 Hz; at or below gives 34 s", "s", False),
        # neither stated convention gives 33 s (34 s and about 33.96 s)
        ("samples at or below 49 Hz; linear interpolation gives 33.96 s", "s", True),
        ("rows 822-854", "count of samples", False),  # no convention stated
    ],
)
def test_round2_d3_5_notes_a_convention_that_does_not_reproduce_the_duration(
    derivation, basis, noted
):
    """Issue 5 (5): haiku45-001 F10 states 'at or below' and a first-to-last span for
    33 s (they give 34 s and 32 s). Never scored."""
    f = finding(
        "F1",
        "Frequency was below 49 Hz from 16:53:41 to 16:54:13 BST, a duration of 33 s.",
        quantity={"value": 33, "unit": "s", "basis": basis},
        derivation=derivation,
    )
    row = grade([f])["D3.5"]
    assert ("does not reproduce the 33 s" in row["content"]["basis"]) is noted
    assert bool(row["auto_checks"]["notes"]) is noted
