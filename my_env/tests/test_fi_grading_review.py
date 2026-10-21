"""Regressions from the review of the full-investigation grading (key 0.1.0 revised,
grader 0.1.0; decisions 65-75 in docs/DECISIONS.md). Each test pins a confirmed defect
with the probe sentence that exposed it (synthetic findings on the real bundle; no
network, no paid calls). Key examples added in the same round are graded by
``test_fi_grading_examples.py``; SF3's new non-examples by ``test_fi_grading_flags.py``.
"""

from __future__ import annotations

import copy

import pytest
from fi_grading_support import (
    auto,
    catalogue,
    decisions_for,
    finding,
    grade,
    key,
    row,
    submission,
)

from environment.incident import fi_elements as fe
from environment.incident import fi_grading, sr_grading
from environment.incident.grading import normalise

O02 = [("S08", "L120-L127")]  # ORR 1.0: 31 stranded; 29 / 22 / 7


def _f(statement, cites=O02, status="reported", fid="F1", **extra):
    return finding(fid, statement, status, list(cites), **extra)


def _basis(report, cid):
    return row(report, cid)["layers"]["auto"]["basis"]


def _evidence(report, cid):
    r = row(report, cid)
    return r["evidence_support"]["auto_proposal"], r["layers"]["auto_evidence"]["basis"]


# -- counts: clauses, bound words and notes (issue: 'and' before multi-digit counts) --------
@pytest.mark.parametrize(
    ("text", "word", "clause"),
    [
        (
            "7 were reset by their drivers and 22 needed a technician",
            "7",
            "7 were reset by their drivers and ",
        ),
        (
            "7 were reset by their drivers and 22 needed a technician",
            "22",
            "22 needed a technician",
        ),
        (
            "873 delayed trains and 14,428 delay minutes",
            "873",
            "873 delayed trains and ",
        ),
        (
            "22 needed a technician and the other 7 were reset by drivers",
            "22",
            "22 needed a technician and ",
        ),
        (
            "29 class 700 and 717 trains were locked out",
            "29",
            "29 class 700 and 717 trains were locked out",
        ),
    ],
)
def test_and_divides_before_any_count(text, word, clause):
    norm = normalise(text)
    assert fe.count_clause(norm, norm.index(word)) == clause


def test_other_meaning_is_read_only_in_the_counts_own_words():
    norm = normalise("ORR: 22 trains needed a technician and 7 were reset by drivers.")
    mentions = fe.count_mentions(norm)
    words = {v: fe.bound_words(norm, s, e, mentions) for v, s, e in mentions}
    assert "reset by drivers" not in words[22]
    assert "technician" not in words[7]


@pytest.mark.parametrize(
    ("statement", "cids"),
    [
        (
            "ORR: 7 trains were reset by their drivers and 22 needed a technician on site.",
            ["T10.02b", "T10.02c"],
        ),
        (
            "There were 873 delayed trains and 14,428 delay minutes (ESO; ORR Table 1).",
            ["T10.05b"],
        ),
        (
            "ORR: 29 trains locked out; 22 needed a technician and the other 7 were reset "
            "by drivers.",
            ["T10.02a", "T10.02b", "T10.02c"],
        ),
        (
            "ORR: 22 trains needed a technician and 7 were reset by their drivers.",
            ["T10.02b", "T10.02c"],
        ),
    ],
)
def test_neighbouring_counts_no_longer_disqualify_each_other(statement, cids):
    report = grade(submission([_f(statement)]))
    assert {cid: auto(report, cid) for cid in cids} == dict.fromkeys(cids, 1.0)


@pytest.mark.parametrize(
    ("statement", "cid", "note"),
    [
        (
            "7 trains needed a technician with a laptop.",
            "T10.02c",
            "the expected value (7) is given with wording of another meaning in F1",
        ),
        (
            "27 units were recovered by Battery Reset.",
            "T10.02c",
            "another account's value (27) is given without the source that reports it",
        ),
        (
            "ORR reports that about 60 trains were locked out.",
            "T10.02a",
            "another account's value (60) is attributed to a source that does not "
            "report it",
        ),
    ],
)
def test_a_count_scored_0_says_why_in_the_basis(statement, cid, note):
    """Decisions 18 and 27: a candidate is never silently 0."""
    report = grade(submission([_f(statement)]))
    assert auto(report, cid) == 0
    basis = _basis(report, cid)
    assert note in basis and "not credited automatically: a human decides" in basis


def test_increment_a_uses_none_of_the_added_element_types_or_notes():
    """The new notes, routing and evidence fields come only from the full
    investigation's element types; increment A's key uses none of them (its outputs
    are pinned by tests/test_sr_grading_live_runs.py and the judge parity snapshot).
    ``figure`` is increment A's own element type: the full investigation's override
    (unknown-labelled findings, decision 77) is passed only by ``fi_grading``, so
    increment A's grader keeps its built-in figure element. Nor does increment A's key
    carry the fields key 0.1.1 of the full investigation added to shared code
    (``unless_clause_any``, ``mention_triggers``, ``binding_options``,
    ``mismatch_unless_any``, ``labelling_exempt``)."""
    added = set(fi_grading.ELEMENT_TYPES) - {"figure"}
    sr_key = sr_grading.load_key()
    for crit in sr_key["criteria"]:
        auto_rules = crit.get("auto") or {}
        assert "severe_flags_zero_at" not in auto_rules, crit["criterion_id"]
        for el in auto_rules.get("elements") or []:
            assert el.get("type") not in added, crit["criterion_id"]
    for flag in sr_key["severe_flags"]:
        assert "zero_content_at" not in (flag.get("effect") or {})
        assert "unless_clause_any" not in (flag.get("heuristic") or {})
        assert "mention_triggers" not in (flag.get("heuristic") or {})
    assert "binding_options" not in sr_key["accounting"]
    assert not any("mismatch_unless_any" in f for f in sr_key["accounting"]["figures"])
    assert "labelling_exempt" not in sr_key["conventions"]
    # the full-investigation key does carry them
    fi_key = fi_grading.load_key()
    assert fi_key["accounting"]["binding_options"] == {"basis_components": True}
    assert fi_key["conventions"]["labelling_exempt"]
    sf1 = next(f for f in fi_key["severe_flags"] if f["flag_id"] == "SF1")
    assert sf1["heuristic"]["unless_clause_any"]
    assert sf1["heuristic"]["mention_triggers"]


# -- alternatives: their own sources and their own evidence --------------------------------
@pytest.mark.parametrize(
    ("statement", "cid", "want"),
    [
        ("ORR reports that about 60 trains were locked out.", "T10.02a", 0),
        ("Ofgem says 60 trains shut down.", "T10.02a", 0),
        ("About 60 trains were locked out (S08).", "T10.02a", 0),
        ("GTR's review says circa 60 units suffered a 4QC lock-out.", "T10.02a", 0.5),
        ("The ESO says approximately 60 trains shut down.", "T10.02a", 0.5),
        ("ESO reports that 28 trains were restarted by drivers.", "T10.02c", 0),
        (
            "GTR says 28 units were recovered by the drivers' Battery Reset.",
            "T10.02c",
            0.5,
        ),
        (
            "ORR's conclusion says 30 trains on the upgraded software were effectively "
            "stranded and needed a technician reset.",
            "T10.02b",
            0.5,
        ),
        ("Ofgem says 30 trains needed a technician to reset them.", "T10.02b", 0),
    ],
)
def test_alternative_counts_need_a_source_that_reports_them(statement, cid, want):
    assert auto(grade(submission([_f(statement)])), cid) == want


def test_an_alternatives_evidence_is_its_own_sources_spans():
    statement = "GTR's review says circa 60 units suffered a 4QC lock-out."
    on_orr = grade(submission([_f(statement)]))  # ORR's 29: the 60 is not there
    value, basis = _evidence(on_orr, "T10.02a")
    assert value is None and "cites only context spans" in basis
    on_gtr = grade(submission([_f(statement, [("S08", "L22-L23")])]))
    value, basis = _evidence(on_gtr, "T10.02a")
    assert value == 1 and "S08 L22-L23" in basis
    # the expected count keeps the criterion's own spans
    expected = grade(submission([_f("ORR reports 29 trains locked out.")]))
    assert _evidence(expected, "T10.02a")[0] == 1
    on_gtr_span = grade(
        submission([_f("ORR reports 29 trains locked out.", [("S08", "L22-L23")])])
    )
    assert _evidence(on_gtr_span, "T10.02a")[0] is None


# -- T10.03a ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("statement", "cites", "want"),
    [
        (
            "29 Class 700/717 trains were stranded by their lock-outs and two Class 387 "
            "trains were trapped behind them (ORR).",
            O02,
            1,
        ),
        (
            "Ofgem: 29 GTR trains became stranded, and two Class 387 trains were also "
            "trapped by them.",
            [("S08", "L222-L225")],
            1,
        ),
        (
            "Ofgem reports that 29 GTR trains became stranded.",
            [("S08", "L222-L225")],
            0.5,
        ),
        (
            "ORR's conclusion says 30 trains on the upgraded software were effectively "
            "stranded.",
            [("S08", "L214-L216")],
            0.5,
        ),
        ("29 trains were stranded.", O02, 0),
        ("GTR says 29 trains were stranded.", O02, 0),
    ],
)
def test_stranded_count_routes(statement, cites, want):
    assert auto(grade(submission([_f(statement, cites)])), "T10.03a") == want


# -- routing: summary references never outweigh a finding's own topic -----------------------
def test_a_finding_the_summary_cites_keeps_its_own_topic():
    rail = _f("ORR reports that 29 Class 700 and 717 trains were locked out.")
    lone = finding(
        "F2", "The event was widely reported.", "reported", [("R09", "L1-L3")]
    )
    report = grade(
        submission(
            [rail, lone],
            summary="Lightning struck the Eaton Socon–Wymondley 400 kV circuit; 29 "
            "trains locked out and power was restored [F1, F2].",
        )
    )
    by_id = {a["assertion_id"]: a for a in report["assertion_quality"]["assertions"]}
    assert by_id["F1"]["dimension"] == "T10"
    assert "T20" in by_id["F1"]["dimensions_matched"]  # still the summary's finding
    assert "F1" in row(report, "T20.01")["matched_finding_ids"]
    # a finding no other topic matches falls back to the summary's topic
    assert by_id["F2"]["dimension"] == "T20"


def test_a_finding_that_states_a_recommendation_routes_to_t18():
    rec = finding(
        "F1",
        "Recommendation: GTR and Siemens should deploy the software patch so that "
        "trains recover automatically after a frequency drop.",
        "inferred",
        [("S08", "L74-L76")],
    )
    report = grade(
        submission(
            [rec],
            summary="First, GTR should deploy the patch [F1].",
            sections=[
                {"heading": "Recommendations", "body": "GTR to deploy the patch [F1]."}
            ],
        )
    )
    (a,) = report["assertion_quality"]["assertions"]
    assert a["dimension"] == "T18"


# -- severe flags ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "statement",
    [
        "ORR found no non-compliance with the Interoperability Regulations warranting "
        "enforcement action.",
        "ORR did not find any non-compliance that would justify enforcement action.",
        "ORR concluded the rail lock-outs did not warrant enforcement action.",
        "Ofgem's investigation could lead to enforcement action against the generators.",
        "EPN and SPN acknowledged a technical breach of the Grid Code (Ofgem 3.43).",
    ],
)
def test_sf3_spares_records_and_conditions(statement):
    report = grade(submission([_f(statement, [("S08", "L217-L219")])]))
    assert report["severe_flags"] == []


def test_sf3_spares_a_recommendation_section_and_counts_survive():
    statement = (
        "ORR reports 29 trains locked out (22 needed a technician, 7 were reset by "
        "drivers); ORR found no non-compliance warranting enforcement action."
    )
    report = grade(
        submission(
            [_f(statement)],
            sections=[
                {
                    "heading": "Recommendations",
                    "body": "1. **Ofgem** to complete its investigation and decide on "
                    "any enforcement action [F1].",
                }
            ],
        )
    )
    assert report["severe_flags"] == []
    for cid in ("T10.02a", "T10.02b", "T10.02c"):
        assert auto(report, cid) == 1, cid
    asserted = grade(submission([_f("Ofgem took enforcement action against RWE.")]))
    assert [s["flag_id"] for s in asserted["severe_flags"]] == ["SF3"]


def test_sf1_in_the_summary_caps_the_summary_criteria_but_not_in_a_finding():
    lb = _f("Little Barford's steam turbine tripped.", [("S04", "L56-L59")])
    summary = (
        "Contributing factors were the coincident losses; the DG volumes remain "
        "unknown [F1]. The root cause of the Little Barford trip was a faulty speed "
        "sensor."
    )
    report = grade(submission([lb], summary=summary))
    assert [(s["flag_id"], s["location"]) for s in report["severe_flags"]] == [
        ("SF1", "report.executive_summary")
    ]
    for cid in ("T20.03", "T20.06"):
        caps = row(report, cid)["layers"]["caps"]
        assert [c["kind"] for c in caps] == ["severe_suspected"], cid
        assert auto(report, cid) == 0
    # the same assertion in a finding, with a calibrated summary
    flagged = _f(
        "The root cause of the Little Barford trip was a faulty speed sensor.",
        [("S04", "L56-L59")],
    )
    other = finding(
        "F2", "Little Barford tripped; causes open.", "unknown", [("S04", "L56-L59")]
    )
    calm = grade(
        submission(
            [flagged, other],
            summary="Contributing factors were the coincident losses; the root causes "
            "at Little Barford remain unknown [F2].",
        )
    )
    assert [s["location"] for s in calm["severe_flags"]] == ["F1"]
    assert auto(calm, "T20.03") == 1
    assert row(calm, "T20.03")["layers"]["caps"] == []
    assert auto(calm, "T07.04") == 0


def test_a_confirmed_sf1_zeroes_the_summary_criteria_only_from_the_summary():
    lb = _f("Little Barford's steam turbine tripped.", [("S04", "L56-L59")])
    k = key()

    def confirmed(sub):
        report = grade(sub)
        flags = [
            {
                "flag_id": s["flag_id"],
                "finding_ids": [s["finding_id"]] if s["finding_id"] else [],
                "locations": [s["location"]],
                "confirmed": True,
                "notes": "confirmed",
            }
            for s in report["severe_flags"]
        ]
        decisions = decisions_for(report, copy.deepcopy(k), severe_flags=flags)
        return fi_grading.grade_submission(sub, catalogue(), k, decisions=decisions)

    in_summary = confirmed(
        submission(
            [lb],
            summary="The root cause of the Little Barford trip was a faulty speed "
            "sensor [F1].",
        )
    )
    assert row(in_summary, "T20.06")["layers"]["severe_zero"] == ["SF1"]
    assert row(in_summary, "T20.03")["layers"]["severe_zero"] == ["SF1"]
    flagged = _f(
        "The root cause of the Little Barford trip was a faulty speed sensor.",
        [("S04", "L56-L59")],
    )
    in_finding = confirmed(submission([flagged], summary="Causes remain open [F1]."))
    assert row(in_finding, "T07.04")["layers"]["severe_zero"] == ["SF1"]
    assert row(in_finding, "T20.06")["layers"]["severe_zero"] == []


# -- T19.02, T05.03, T15 ----------------------------------------------------------------------
def test_the_recorded_sir_request_is_evidence_not_an_unverified_obligation():
    sir = _f(
        "At 17:23 the DNOs sent the ESO the first Significant Incident Report request "
        "under Grid Code OC7 and OC10 (S07 K3); after LFDD the DNOs must notify the ESO "
        "and may restore demand only on its instruction (Grid Code OC6.6, R10 D9).",
        [("S07", "L48-L49"), ("R10", "L113-L116")],
    )
    report = grade(submission([sir]))
    assert auto(report, "T19.02") == 1
    assert row(report, "T19.02")["layers"]["caps"] == []
    keyed = {
        (v["evidence_id"], v["locator"])
        for v in key()["criteria"][
            [c["criterion_id"] for c in key()["criteria"]].index("T19.02")
        ]["visible_evidence"]
    }
    assert {("S07", "L48-L49"), ("S07", "entry:S07-K3")} <= keyed
    obligation = _f(
        "Under ESQCR and Grid Code OC7, the DNOs had to notify BEIS within one hour.",
        [("R10", "L113-L116")],
    )
    capped = grade(submission([obligation]))
    assert [c["id"] for c in row(capped, "T19.02")["layers"]["caps"]] == [
        "unverified_obligation"
    ]


def test_the_victoria_lines_own_recovery_is_not_a_contradiction():
    report = grade(
        submission(
            [
                _f(
                    "London Underground's Victoria line was suspended by an internal "
                    "traction issue; its trains resumed at 17:35 (ESO 5.2).",
                    [("S11", "L24-L27")],
                )
            ]
        )
    )
    assert row(report, "T05.03")["layers"]["caps"] == []
    t0503 = next(c for c in key()["criteria"] if c["criterion_id"] == "T05.03")
    assert "Victoria" not in t0503["expected"]["transport_recovery"]


@pytest.mark.parametrize(
    ("statement", "cid", "want"),
    [
        (
            "The ESO's third statement, shared with BEIS and Ofgem, said the DNOs had "
            "reconnected all demand by 17:40.",
            "T15.01a",
            0,
        ),
        ("The ESO first contacted BEIS at 17:41 BST (ESO 6.2).", "T15.01a", 1),
        ("The ESO contacted BEIS at 17:40 and Ofgem at 18:00.", "T15.01a", 1),
        (
            "The ESO's 8pm website statement said the DNOs had restored all demand by "
            "18:30.",
            "T15.01b",
            0,
        ),
        (
            "The ESO's first public statement was posted at 17:27:46Z (18:27 BST), once "
            "DNOs had reconnected customers.",
            "T15.01b",
            1,
        ),
        (
            "The ESO first contacted Ofgem at 17:51 (section 6.2); calls to the 105 line "
            "fell sharply after 18:00.",
            "T15.02",
            0.5,
        ),
        (
            "The ESO first contacted Ofgem at 17:51 (section 6.2) and delivered its "
            "interim report to Ofgem before 6pm on 16 August.",
            "T15.02",
            0.5,
        ),
    ],
)
def test_communications_times_are_read_from_their_own_clause(statement, cid, want):
    assert auto(grade(submission([_f(statement, [("R09", "L1-L3")])])), cid) == want


@pytest.mark.parametrize(
    "statement",
    [
        "At 17:41, the ESO control room first contacted BEIS.",
        "The ESO first contacted BEIS, at 17:41 BST.",
        "Demand was reconnected by 17:40, and the ESO first contacted BEIS at 17:41.",
    ],
)
def test_a_contact_time_reads_its_wording_across_commas(statement):
    """A time's clause is joined across commas with neighbouring clauses that hold no
    time of their own; a restoration phrase in the time's own clause still excludes
    it."""
    report = grade(submission([_f(statement, [("R09", "L1-L3")])]))
    assert auto(report, "T15.01a") == 1
    assert row(report, "T15.01a")["auto_checks"]["elements"][0]["detail"]["time"] == (
        "2019-08-09T17:41:00+01:00"
    )


def test_a_contact_time_without_its_wording_is_listed_for_the_reviewer():
    report = grade(
        submission(
            [
                _f(
                    "BEIS was contacted by the ESO; separately, 17:41 is the time "
                    "section 6.2 gives.",
                    [("R09", "L1-L3")],
                )
            ]
        )
    )
    assert auto(report, "T15.01a") == 0
    basis = _basis(report, "T15.01a")
    assert (
        "a time within tolerance (2019-08-09T17:41:00+01:00) is given without" in basis
    )


# -- the judge track: a full-investigation key brings its task's judge defaults ------------
def test_a_full_investigation_key_without_a_task_gets_the_tasks_judge_defaults(
    tmp_path, capsys
):
    import json

    from environment.incident.judge import (
        JudgeConfig,
        judge_submission_file,
        with_task_defaults,
    )
    from environment.incident.judge.__main__ import main as judge_main

    fi_task, sr_task = "gb-2019-full-investigation", "gb-2019-system-response"
    plain = JudgeConfig()
    fi_config = with_task_defaults(plain, fi_task)
    assert fi_config.rubric_file == "full_investigation/judge_rubric_v1.md"
    assert fi_config.scope is not None and fi_config.scope.mode == "topic"
    assert fi_config.app_title == "gb2019-fi-judge"
    # a setting the config gives explicitly is kept; increment A's config is untouched
    explicit = with_task_defaults(
        JudgeConfig(rubric_file="judge_rubric_v1.md"), fi_task
    )
    assert explicit.rubric_file == "judge_rubric_v1.md"
    assert explicit.scope.mode == "topic"
    assert with_task_defaults(plain, sr_task) is plain
    # a dry run with the key alone: the full investigation's rubric and scope
    path = tmp_path / "submission.json"
    path.write_text(
        json.dumps(submission([_f("ORR reports 29 trains locked out.")])),
        encoding="utf-8",
    )
    run = judge_submission_file(
        path,
        config=plain,
        out_dir=tmp_path / "out",
        run_model="openrouter/anthropic/claude-opus-5.5",
        key=key(),
        dry_run=True,
    )
    assert "warnings" not in run.run_log
    assert run.run_log["scope"]["mode"] == "topic"
    # the command line with --key (no --task)
    key_path = fi_grading.DEFAULT_KEY_PATH
    code = judge_main(
        [
            "run",
            str(path),
            "--key",
            str(key_path),
            "--run-model",
            "openrouter/anthropic/claude-opus-5.5",
            "--out-dir",
            str(tmp_path / "cli"),
            "--dry-run",
        ]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert "warnings" not in printed and printed["scope"]["mode"] == "topic"
