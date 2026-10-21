"""The real full-investigation pilot (Opus 5.5; ``tests/fixtures/fi_live``) graded with
the installed key, pre-screens only (no judge layer; the judged grade of both real runs
is pinned in ``tests/test_fi_grading_live_runs.py``): the regression discipline of
decisions 18, 27 and 40-48 applied to the first real submission of the task
(docs/DECISIONS.md, increment B grading outcome).

Every pre-screen below 1 on the pilot was read against its text. Key 0.1.0 fixed three
false negatives: T05.02 ('Disconnected demand was restored by 17:37 BST', F25),
T10.02c ('29 locked out (22 permanent, 7 reset)', F28) and T14.02 ('RWE acknowledges
it contributed', F39). Key 0.1.1 (decision 77, after the judge's proposals) keeps
F39 as Little Barford's contribution but without the requirement, the expectation's
partial (0.5), and fixes T02.04 ("1.16 s after datum T"), T05.03, T06.02, T08.05 and
T09.05 (false negatives), T08.04 and T14.05 (credited from a measurement limit and from
Ofgem's finding of no breach). The others are genuine partial answers (e.g. T04.02: no
200 ms; T10.03b: no Class 387; T10.04: 3.27 only; T07.01-T07.03: no trip mechanism
with the trip). The summary's references no longer route domain findings to T20.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

import pytest

from environment.incident import fi_grading

PILOT = Path(__file__).resolve().parent / "fixtures" / "fi_live" / "fi-pilot-opus55-001"
RUNS = json.loads((PILOT.parent / "runs.json").read_text(encoding="utf-8"))["runs"]


@lru_cache(maxsize=1)
def report() -> dict:
    summary = json.loads((PILOT / "run_summary.json").read_text(encoding="utf-8"))
    return fi_grading.grade_episode(PILOT, summary)


def auto(cid: str):
    return next(r for r in report()["criteria"] if r["criterion_id"] == cid)["content"][
        "auto_proposal"
    ]


def test_the_fixture_files_are_the_copied_run():
    run = next(r for r in RUNS if r["run_id"] == PILOT.name)
    for name, digest in run["files"].items():
        assert hashlib.sha256((PILOT / name).read_bytes()).hexdigest() == digest, name
    state = json.loads((PILOT / "state.json").read_text(encoding="utf-8"))
    assert state["submission_sha256"] == run["submission_sha256"]
    assert report()["submission"]["sha256"] == run["submission_sha256"]
    assert report()["run"]["outcome"] == "complete"
    assert report()["bundle"]["bundle_sha256"] == run["bundle_sha256"]


@pytest.mark.parametrize(
    ("cid", "finding", "want"),
    [
        ("T05.02", "F25", 1),
        ("T10.02c", "F28", 1),
        # the contribution, but not against the requirement (key 0.1.1)
        ("T14.02", "F39", 0.5),
        ("T02.04", "F06", 1),  # "1.16 s after datum T" (key 0.1.1)
        ("T05.03", "F25", 1),  # demand restoration "separate from" other services
        ("T08.05", "F13", 1),  # "This includes about 550 MW" (key 0.1.1)
        ("T09.05", "F26", 0.5),  # "a wrong setting" (key 0.1.1)
    ],
)
def test_the_pilots_false_negatives_are_credited(cid, finding, want):
    row = next(r for r in report()["criteria"] if r["criterion_id"] == cid)
    assert row["content"]["auto_proposal"] == want, row["layers"]["auto"]["basis"]
    assert finding in row["matched_finding_ids"]


def test_pre_screen_proposals_by_mode():
    counts = Counter(
        (r["assessment_mode"], r["content"]["auto_proposal"])
        for r in report()["criteria"]
    )
    # key 0.1.0: 40/7/2 and 43/6/4; key 0.1.1 (decision 77): T02.04 0.5 -> 1;
    # judge-mode T05.03 0.5 -> 1, T06.02 0 -> 0.5, T08.04 1 -> 0.5, T08.05 0 -> 1,
    # T09.05 0 -> 0.5, T14.02 1 -> 0.5, T14.05 1 -> 0.5
    assert counts == {
        ("auto_numeric", 1.0): 4,
        ("auto_assisted_human", 1.0): 41,
        ("auto_assisted_human", 0.5): 6,
        ("auto_assisted_human", 0.0): 2,
        ("judge", 1.0): 42,
        ("judge", 0.5): 10,
        ("judge", 0.0): 1,
    }
    below = {
        r["criterion_id"]: r["content"]["auto_proposal"]
        for r in report()["criteria"]
        if r["content"]["auto_proposal"] != 1
    }
    assert below == {
        "T04.02": 0.5,
        "T06.02": 0.5,
        "T07.01": 0.0,
        "T07.02": 0.5,
        "T07.03": 0.5,
        "T08.04": 0.5,
        "T09.04": 0.0,
        "T09.05": 0.5,
        "T10.03b": 0.0,
        "T10.04": 0.5,
        "T12.01b": 0.5,
        "T12.01c": 0.5,
        "T12.03": 0.5,
        "T13.06": 0.5,
        "T14.02": 0.5,
        "T14.05": 0.5,
        "T16.01": 0.5,
        "T16.03": 0.5,
        "T18.04": 0.5,
    }


def test_no_severe_flag_trap_or_cap_on_the_pilot():
    rep = report()
    assert rep["severe_flags"] == []
    assert rep["flags"]["accounting_traps"] == []
    assert not any(
        c.get("binding", True) for r in rep["criteria"] for c in r["layers"]["caps"]
    )


def test_summary_references_do_not_route_findings_to_t20():
    assertions = {
        a["assertion_id"]: a for a in report()["assertion_quality"]["assertions"]
    }
    dims = Counter(a["dimension"] for a in assertions.values())
    assert "T20" not in dims
    for fid in ("F24", "F25", "F30"):
        assert assertions[fid]["dimension"] == "T05", fid
    for fid in ("F42", "F43", "F44", "F45"):
        assert assertions[fid]["dimension"] == "T18", fid
    # the summary's references still make them the summary criteria's findings
    t2006 = next(r for r in report()["criteria"] if r["criterion_id"] == "T20.06")
    assert len(t2006["matched_finding_ids"]) == 44  # F01-F45 but F04
    assert all("T20" in assertions[f]["dimensions_matched"] for f in ("F24", "F42"))


def test_the_recommendation_section_is_not_an_enforcement_outcome():
    sub = json.loads((PILOT / "submission.json").read_text(encoding="utf-8"))
    headings = [s["heading"] for s in sub["report"]["sections"]]
    assert "Recommendations" in headings
    assert report()["severe_flags"] == []
    # T14.05 is partial for the missing proof it identifies (records not held, tests
    # outstanding), not for an enforcement outcome: F38's "found no evidence that the
    # ESO breached the Grid Code" is no longer read as missing proof (key 0.1.1)
    assert auto("T14.04") == 1 and auto("T14.05") == 0.5
