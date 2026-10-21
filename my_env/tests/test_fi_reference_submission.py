"""The full-investigation reference submission (tasks/gb_2019_full_investigation/reference).

It must be a complete, correct and fully cited v3 submission for T01-T20: valid on the
real bundle, every criterion of the key at full content and evidence (automated values for
the R01 landmarks, proposals and judge pre-screens elsewhere), every figure on its own
accounting basis, no reviewer flag or severe flag, uncertainties labelled, an executive
summary of at most 600 words, no enforcement outcome and no unverified legal obligation,
and every number it computes reproducible from the bundle's records. Built by
``.context/fi_reference_builder/build_reference.py`` from increment A's reference
(re-cited to the evidence this investigation obtains) plus the new topics.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import pytest
from fi_grading_support import catalogue, grade, key, row

from environment import fake_model, fake_model_fi
from environment.incident.episode import FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET
from environment.incident.frequency import load_series, reference_landmarks
from environment.incident.paths import FULL_INVESTIGATION_BUNDLE_DIR
from environment.incident.sr_grading import resolve_text
from environment.incident.submission import (
    MAX_FINDINGS,
    extract_references,
    validate_submission,
    word_count,
)
from environment.tasks.gb_2019_full_investigation.prompt import SECTION_HEADINGS

REFERENCE = fake_model_fi.FI_REFERENCE_SUBMISSION
BUNDLE = FULL_INVESTIGATION_BUNDLE_DIR
BST = timezone(timedelta(hours=1))


@lru_cache(maxsize=1)
def reference() -> dict:
    return json.loads(REFERENCE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def report() -> dict:
    return grade(reference())


def findings() -> dict[str, dict]:
    return {f["finding_id"]: f for f in reference()["findings"]}


def all_text() -> str:
    sub = reference()
    parts = [sub["report"]["executive_summary"]]
    parts += [s["heading"] + "\n" + s["body"] for s in sub["report"]["sections"]]
    for f in sub["findings"]:
        parts.append(f["statement"])
        parts.append(f.get("derivation") or "")
        parts.append((f.get("quantity") or {}).get("basis") or "")
    return "\n".join(parts)


def section(heading: str) -> str:
    return next(
        s["body"] for s in reference()["report"]["sections"] if s["heading"] == heading
    )


def cited_text(fid: str) -> list[str]:
    return [
        " ".join(resolve_text(catalogue(), c["evidence_id"], c["locator"]).split())
        for c in findings()[fid]["citations"]
    ]


# -- the file ------------------------------------------------------------------------------
def test_file_is_canonical_json():
    text = REFERENCE.read_text(encoding="utf-8")
    assert (
        text
        == json.dumps(reference(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )


def test_valid_on_the_full_investigation_bundle():
    result = validate_submission(reference(), catalogue())
    assert result.ok, result.errors
    assert len(reference()["findings"]) <= MAX_FINDINGS


def test_report_has_the_deliverable_sections_in_order():
    headings = [s["heading"] for s in reference()["report"]["sections"]]
    assert tuple(headings) == SECTION_HEADINGS


def test_executive_summary_is_within_600_words():
    words = word_count(reference()["report"]["executive_summary"])
    assert 400 <= words <= 600, words


def test_submission_leaves_room_in_the_output_budget():
    """A model writing this submission spends roughly one token per four characters
    (about one per two of its JSON-escaped form); the reference must fit in half the
    output budget so that a real investigation of this depth is possible within it."""
    compact = json.dumps(reference(), ensure_ascii=False, separators=(",", ":"))
    assert len(compact) / 4 < FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET / 2
    assert len(compact) / 2.2 < FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET


def test_every_finding_is_referenced_and_cited():
    sub = reference()
    texts = [sub["report"]["executive_summary"]]
    texts += [s["body"] for s in sub["report"]["sections"]]
    referenced = {ref for text in texts for ref in extract_references(text)}
    assert referenced == set(findings())
    for f in sub["findings"]:
        assert f["citations"], f["finding_id"]


def test_increment_a_findings_are_reused_except_those_on_unread_evidence():
    sr = {f["finding_id"] for f in fake_model.sr_reference_submission()["findings"]}
    ours = set(findings())
    assert sr - ours == {"F45", "F46", "F47", "F78", "F93"}  # R02, R05 and R07 checks
    new = ours - sr
    assert all(int(fid[1:]) >= 100 for fid in new)
    for f in reference()["findings"]:
        for c in f["citations"]:
            assert c["evidence_id"] not in ("R02", "R04", "R05", "R07", "R08"), (
                f["finding_id"],
                c,
            )


# Source figures and facts a new finding states, each found in the text of one of its own
# citations (handoff rule: derived numerical claims cite every input).
STATED_IN_CITATIONS = [
    ("F100", "within 200 ms"),
    ("F100", "minimum frequency of 49.0 Hz"),
    ("F100", "EN 50163"),
    ("F100", "48.983"),
    ("F101", "no identified OLE AC voltage supply interruption"),
    ("F101", "operated continually"),
    ("F101", "vast majority of the railway"),
    ("F101", "below 49 Hz [reported]"),
    ("F102", "lock-out of 29 [reported] trains"),
    ("F102", "22 [reported] trains were permanently locked out"),
    ("F102", "7 [reported]"),
    ("F103", "31 [reported] trains were stranded"),
    ("F103", "Two Class 387 trains"),
    ("F104", "3.25.x"),
    ("F104", "3.27.x"),
    ("F104", "3.27 or above"),
    ("F106", "above 49.5 Hz"),
    ("F107", "TOTAL | 371 [reported] | 220 [reported]"),
    ("F108", "873 [reported]"),
    ("F108", "14428 [reported]"),
    ("F109", "circa 60 [estimated]"),
    ("F109", "27 [reported]"),
    ("F109", "28 [reported]"),
    ("F109", "17 [reported]"),
    ("F109", "18 [reported]"),
    ("F109", "23 [reported]"),
    ("F111", "GTR CL700 UNITS FAULT"),
    ("F111", "reason XK"),
    ("F120", "18 minutes [reported]"),
    ("F120", "Protected Site"),
    ("F121", "14 seconds [reported]"),
    ("F121", "breaker serving outpatient"),
    ("F122", "428 minutes [reported]"),
    ("F122", "ROCK FERRY : BIRKENHEAD CENTRAL"),
    ("F123", "3,000 [estimated]"),
    ("F123", "c.180 [estimated]"),
    ("F124", "took a few weeks"),
    ("F130", "2014"),
    ("F134", "below 49 Hz [reported]"),
    ("F134", "48.5 Hz [reported]"),
    ("F134", "software version 3.27"),
    ("F134", "too few technicians"),
    ("F132", "90% [reported]"),
    ("F132", "17% [reported]"),
    ("F132", "14% [reported]"),
    ("F132", "one Secured Event"),
    ("F140", "90% [reported]"),
    ("F140", "0.5 seconds [reported]"),
    ("F142", "without being told to do so by the ESO"),
    ("F145", "List of outstanding tests"),
    ("F150", "17:41hrs"),
    ("F150", "17:40"),
    ("F151", "17:51hrs"),
    ("F151", "just after 18:00hrs"),
    ("F152", "FRIDAY 18:27"),
    ("F152", "17:27:46.703Z"),
    ("F153", "17:10hrs"),
    ("F153", "17.09"),
    ("F154", "737 MW [reported]"),
    ("F155", "did not affect the speed"),
    ("F156", "publishTime 2019-08-09T16:54:44Z"),
    ("F156", "Under Investigation"),
    ("F156", "normal 735.0 MW"),
    ("F160", "Energy Incident Reporting"),
    ("F160", "not permitted to restore"),
    # increment A's findings re-cited without R02, R05, R07, R08
    ("F81", "1022"),
    ("F82", "1338 MW"),
    ("F86", "219632"),
    ("F30", "16:58 – 17:16"),
    ("F30", "WPD East Midland: 16:57 [reported] | 17:16 [reported]"),
]


@pytest.mark.parametrize(("fid", "text"), STATED_IN_CITATIONS)
def test_stated_source_figures_are_in_the_findings_own_citations(fid, text):
    assert any(text in t for t in cited_text(fid)), (fid, text)


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
        "F145",
        "F161",
    }
    assert {fid for fid, f in by.items() if f["status"] == "inferred"} >= {
        "F125",
        "F135",
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
    assert "BST (UTC+01:00)" in reference()["report"]["executive_summary"]
    assert "All times BST (UTC+01:00)" in section("Chronology")


# -- grading: every criterion at full content and evidence ---------------------------------
def test_every_criterion_is_satisfied_with_keyed_evidence():
    rep = report()
    assert len(rep["criteria"]) == len(key()["criteria"]) == 106
    for r in rep["criteria"]:
        content, evidence = r["content"], r["evidence_support"]
        assert content["auto_proposal"] == 1, (r["criterion_id"], r["layers"]["auto"])
        assert evidence["auto_proposal"] == 1, (r["criterion_id"], evidence)
        assert not r["layers"]["caps"], (r["criterion_id"], r["layers"]["caps"])
    assert {r["task"] for r in rep["criteria"]} == {f"T{i:02d}" for i in range(1, 21)}


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
    assert flags["executive_summary"] == {
        "words": word_count(reference()["report"]["executive_summary"]),
        "limit": 600,
        "within_limit": True,
    }
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
    assert {1878.0, 1481.0} <= {a["stated"] for a in sums.values()}
    by_figure: dict[str, set[str]] = {}
    for m in acc["mentions"]:
        by_figure.setdefault(m["figure_id"], set()).add(m["classification"])
    for figure in (
        "GEN_ESO_1878",
        "GEN_OFG_1990",
        "LFDD_931",
        "LFDD_OFG_892",
        "LFDD_E3CI_973",
        "RESP_PRIMARY_1022",
        "RESP_SECONDARY_1314",
        "RESP_SECONDARY_1338",
        "INERTIA_ESO_210",
        "INERTIA_ESO_219632",
        "DG_TOTAL_1300_1500",
    ):
        assert by_figure.get(figure, set()) & {"attributed", "defined"}, figure


# -- what the reference must not say ------------------------------------------------------
def test_no_enforcement_outcome_is_stated():
    """Decision 50: the January 2020 settlements are not in the evidence; the reference
    says the evidence holds no outcome, and names no amount, payment or penalty."""
    text = all_text()
    for pattern in (
        r"£",
        r"\b4\.5 ?m",
        r"\b1\.5 ?m",
        r"\b10\.5",
        r"redress",
        r"\bfined\b",
        r"voluntary (?:payment|resolution)",
        r"formal legal determination",
        r"\bpaid\b",
    ):
        assert not re.search(pattern, text, re.I), pattern
    assert (
        "the evidence holds no enforcement outcome"
        in (reference()["report"]["executive_summary"])
    )
    assert (
        "contains no settlement, penalty or legal finding"
        in (findings()["F145"]["statement"])
    )


def test_no_unverified_legal_obligation_is_relied_on():
    """Handoff T19: no ESQCR duties or Grid Code OC7/OC10 obligations."""
    text = all_text()
    assert not re.search(r"\besqcr\b|\boc ?7\b|\boc ?10\b", text, re.I)


def test_discrepancies_are_kept_with_their_sources():
    by = findings()
    assert "17:51" in by["F151"]["statement"] and "18:00" in by["F151"]["statement"]
    summary = reference()["report"]["executive_summary"]
    assert "17:51 (18:00 in its own findings)" in summary
    f109 = by["F109"]["statement"]
    for fragment in ("ORR gives 29", "GTR's review counts circa 60", "17 technicians"):
        assert fragment in f109
    assert "873 trains delayed" in by["F108"]["statement"]
    assert "14,428 delay minutes" in by["F108"]["statement"]


def test_recommendations_name_an_owner_and_a_verification_and_cite_findings():
    items = [
        line
        for line in section("Recommendations").splitlines()
        if re.match(r"\d+\.", line)
    ]
    assert len(items) == 6
    assert items[0].startswith("1. First priority, rail recovery")
    for item in items:
        assert re.search(r"\bshould\b", item), item
        assert "verified by" in item, item
        assert len(extract_references(item)) >= 2, item


def test_evidence_requests_name_a_party_and_specific_records():
    items = [
        line
        for line in section("Further evidence requests").splitlines()
        if re.match(r"\d+\.", line)
    ]
    assert len(items) == 7
    for item in items:
        assert re.search(r"should supply", item), item
        assert extract_references(item), item


def test_summary_puts_actions_in_priority_order_and_keeps_unknowns_open():
    summary = reference()["report"]["executive_summary"]
    order = [summary.index(w) for w in ("first,", "second,", "third,", "fourth,")]
    assert order == sorted(order)
    assert "Priority actions, in order" in summary
    assert "Still unknown" in summary and "[F53, F54, F90, F91]" in summary


# -- reproducible from the bundle --------------------------------------------------------
def test_frequency_findings_match_the_r01_series():
    lm = reference_landmarks(
        load_series(BUNDLE / "R01" / "frequency_2019-08-09_1640-1745_BST.csv")
    )
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
    assert "between 16:53:40 and 16:53:41 BST" in by["F100"]["statement"]


def _orr_table() -> list[tuple[str, int, int, int]]:
    rows = []
    for line in (BUNDLE / "S08" / "S08.txt").read_text("utf-8").splitlines():
        m = re.match(
            r"T\d\s+(.+?) \| (\d+) \[reported\] \| (\d+) \[reported\] \| (\d+)", line
        )
        if m:
            rows.append((m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))))
    return rows


def test_rail_totals_are_the_sums_of_orr_table_1():
    rows = _orr_table()
    routes, total = rows[:-1], rows[-1]
    assert len(routes) == 8 and total[0] == "TOTAL"
    sums = tuple(sum(r[i] for r in routes) for i in (1, 2, 3))
    assert sums == total[1:] == (371, 220, 14428)
    by = findings()
    assert "371 trains cancelled and 220 part-cancelled" in by["F107"]["statement"]
    assert "14,428 delay minutes across the eight routes" in by["F108"]["statement"]


def test_lfdd_tables_sum_to_the_reported_totals():
    text = (BUNDLE / "S05" / "S05.txt").read_text("utf-8")

    def total(prefix: str) -> int:
        part = re.findall(rf"^{prefix}(?:0[1-9]|1[0-4])\s.*?\| (\d+) MW", text, re.M)
        return sum(int(v) for v in part)

    assert total("D") == 931 and total("F") == 973
    assert "42 MW" in findings()["F73"]["derivation"]


def test_little_barford_and_utc_times_follow_from_the_records():
    t0 = datetime(2019, 8, 9, 16, 52, 34, tzinfo=BST).timestamp()
    by = findings()
    for fid, offset in (("F11", 1.185), ("F12", 57.620), ("F13", 84.613)):
        assert datetime.fromisoformat(
            by[fid]["event_time"]
        ).timestamp() == pytest.approx(t0 + offset)
    remit = datetime(2019, 8, 9, 16, 54, 44, tzinfo=UTC).astimezone(BST)
    assert remit.strftime("%H:%M:%S") in by["F156"]["statement"]
    post = datetime(2019, 8, 9, 17, 27, 46, tzinfo=UTC).astimezone(BST)
    assert post.strftime("%H:%M:%S") in by["F152"]["statement"]


def test_builder_reproduces_the_installed_reference():
    """``.context/fi_reference_builder/build_reference.py --check`` (builder-only; skipped
    when the builder directory is not present)."""
    builder = (
        Path(__file__).resolve().parents[2]
        / ".context"
        / "fi_reference_builder"
        / "build_reference.py"
    )
    if not builder.exists():
        pytest.skip("reference builder not present")
    result = subprocess.run(
        [sys.executable, str(builder), "--check"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "identical"
