"""Pre-screens of the system-response key on realistic phrasing (review round 1):
contradiction rules tie the subject to the causal or failure wording and do not fire on
correct statements; for judge criteria they are flags for the reviewer, never caps on
the judge's value; auto_assisted_human pre-screens read table-style lists, labelled
time ranges and the first DNO's completion report as the key intends; severe-flag
heuristics leave real prices and labelled document lines alone."""

from __future__ import annotations

import pytest
from sr_grading_support import (
    decisions_for,
    finding,
    grade,
    judge_output,
    key,
    row,
    submission,
)

from environment.incident import sr_grading


def one(text: str, status: str = "reported", cites=(("S12", "L16-L24"),)) -> dict:
    return grade(submission([finding("F1", text, status, list(cites))]))


def contradictions(report: dict, cid: str) -> list[str]:
    return [c["id"] for c in row(report, cid)["auto_checks"]["contradictions"]]


CORRECT = [
    (
        "T05.03",
        "All DNO demand was restored by 17:37 BST, but train services took hours longer "
        "to recover.",
    ),
    (
        "T16.03",
        "The Killingholme–Keadby planned outage only made a power-quality monitor "
        "unavailable; separately, the Hornsea internal outage configuration (one SGT and "
        "one OTSUA circuit) contributed to the de-load according to the operator.",
    ),
    (
        "T16.03",
        "Hornsea One, which connects to the transmission system at Killingholme, had an "
        "internal outage configuration (one SGT and one OTSUA circuit out) that "
        "contributed to the de-load according to the operator.",
    ),
    (
        "T16.02",
        "Main protection at both ends operated correctly; the circuit breakers opened in "
        "70 and 74 ms, so incorrect protection operation can be excluded.",
    ),
    (
        "T17.03",
        "A further reduction of about 100 MW followed at 16:53:10, 37 s after the "
        "Hornsea de-load; ESO's modelling represents it as a slight reduction in output "
        "across the fleet.",
    ),
    (
        "T17.03",
        "The unexplained 100 MW reduction is spread across the fleet in ESO's modelling "
        "rather than to Hornsea or Little Barford.",
    ),
    (
        "T06.05",
        "Ørsted's first view blamed the DRC; its final report says the de-load was due "
        "to an insufficiently damped resonance in the turbine controllers.",
    ),
    (
        "T06.01",
        "Ørsted's first view blamed the DRC; its final report says the de-load was due "
        "to an insufficiently damped resonance in the turbine controllers.",
    ),
    (
        "T12.04",
        "Further losses of GT1A (210 MW) and about 200 MW net at 49 Hz while all "
        "response was already deployed led to LFDD; response under-delivery (Ofgem: "
        "primary 17%, secondary 14%) was a secondary factor.",
    ),
]

WRONG = [
    ("T05.03", "Rail services recovered at 17:37 when demand was restored."),
    ("T05.03", "By 17:37 all services had recovered."),
    (
        "T16.03",
        "The Killingholme–Keadby outage weakened the grid and caused the Hornsea "
        "de-load.",
    ),
    (
        "T16.03",
        "The planned outage of the Killingholme-Keadby circuit contributed to the "
        "Hornsea de-load.",
    ),
    (
        "T16.02",
        "Slow main protection at Wymondley failed to clear the fault quickly, causing "
        "the generator trips.",
    ),
    ("T16.02", "The circuit breakers at Eaton Socon were too slow to clear the fault."),
    (
        "T17.03",
        "The 100 MW reduction at 16:53:10 was caused by Dinorwig reducing output.",
    ),
    ("T17.03", "The 100 MW reduction came from Hornsea."),
    ("T06.05", "The Hornsea de-load was caused by the Dynamic Reactive Compensator."),
    ("T06.05", "The DRC was the root cause of the Hornsea de-load."),
    ("T12.04", "Under-delivery of frequency response caused the LFDD."),
    ("T12.04", "LFDD was caused by the response shortfall."),
]


@pytest.mark.parametrize(("cid", "text"), CORRECT)
def test_contradiction_rules_do_not_fire_on_correct_statements(cid, text):
    report = one(text)
    assert contradictions(report, cid) == [], cid
    assert report["assertion_quality"]["assertions"][0]["auto_proposal"] != (
        "contradicted"
    )


@pytest.mark.parametrize(("cid", "text"), WRONG)
def test_contradiction_rules_still_fire_on_the_error(cid, text):
    assert contradictions(one(text), cid), cid


def test_judge_criterion_contradiction_flags_the_reviewer_but_does_not_cap_the_judge():
    report = one("The Hornsea de-load was caused by the Dynamic Reactive Compensator.")
    t = row(report, "T06.05")
    assert t["content"]["auto_proposal"] == 0  # the pre-screen still applies it
    (cap,) = t["layers"]["caps"]
    assert cap["kind"] == "contradiction" and cap["binding"] is False
    flags = report["flags"]["prescreen_contradictions"]
    assert {(f["criterion_id"], f["id"]) for f in flags} == {
        ("T06.01", "drc_as_cause"),
        ("T06.05", "drc_as_cause"),
    }
    merged = sr_grading.merge_judge_proposals(
        report,
        judge_output(
            report,
            criteria={
                "T06.05": {"content": 1, "finding_ids": ["F1"], "rationale": "x"}
            },
        ),
    )
    t = row(merged, "T06.05")
    assert t["content"]["value"] == 1 and t["content"]["source"] == "judge"
    assert "pre-screen flag(s) for the reviewer" in t["content"]["basis"]
    assert "drc_as_cause" in t["content"]["basis"]
    # contradictions of criteria the judge does not decide stay binding caps
    gt1b = one("GT1B tripped automatically on its protection.")
    assert all(c.get("binding", True) for c in row(gt1b, "T07.03")["layers"]["caps"])


def test_accept_judge_cannot_sign_off_a_capped_proposal():
    sub = submission(
        [
            finding(
                "F1",
                "ESO's total generation lost was at least 1,990 MW.",
                "reported",
                [("S12", "L39-L42")],
            )
        ]
    )
    first = grade(sub)
    jo = judge_output(
        first,
        criteria={"T02.06": {"content": 1, "finding_ids": ["F1"], "rationale": "fine"}},
    )
    signed = grade(
        sub,
        decisions=decisions_for(
            first, key(), criteria={"T02.06": {"accept_judge": True}}
        ),
        judge_output=jo,
    )
    t = row(signed, "T02.06")
    assert t["content"]["value"] is None and t["content"]["source"] == "pending"
    assert t["content"]["accept_judge_refused"] is True
    assert "give an explicit content value" in t["content"]["basis"]
    assert "capped to 0" in t["content"]["basis"]
    assert any("cannot sign off capped" in r for r in signed["provisional_reasons"])
    explicit = grade(
        sub,
        decisions=decisions_for(first, key(), criteria={"T02.06": {"content": 0.5}}),
        judge_output=jo,
    )
    assert row(explicit, "T02.06")["content"] == {
        **row(explicit, "T02.06")["content"],
        "value": 0.5,
        "source": "human",
    }


def test_numeric_contradiction_bounds_the_judge_assertion_verdict():
    sub = submission(
        [
            finding(
                "F1",
                "The event minimum frequency in R01 was 48.70 Hz at 16:53:49 BST.",
                "observed",
                [("R01", "row:830")],
                quantity={"value": 48.70, "unit": "Hz", "basis": "R01 minimum"},
                event_time="2019-08-09T16:53:49+01:00",
            )
        ]
    )
    first = grade(sub)
    assert row(first, "T03.02")["content"]["value"] == 0
    entry = first["assertion_quality"]["assertions"][0]
    assert entry["auto_proposal"] == "contradicted"
    assert entry["layers"]["auto_numeric"]["verdict"] == "contradicted"
    jo = judge_output(first, assertions={"F1": {"verdict": "supported"}})
    merged = sr_grading.merge_judge_proposals(first, jo)
    entry = merged["assertion_quality"]["assertions"][0]
    assert entry["verdict"] is None and entry["source"] == "pending"
    assert entry["conflict"]["judge_verdict"] == "supported"
    assert entry["conflict"]["auto_numeric_verdict"] == "contradicted"
    assert merged["assertion_quality"]["by_task"]["T03"]["precision"] is None
    assert [c["assertion_id"] for c in merged["flags"]["assertion_conflicts"]] == ["F1"]
    assert any(
        "conflict with automated numeric" in r for r in merged["provisional_reasons"]
    )
    # a sign-off of the judge's verdict is refused too; an explicit verdict decides
    refused = grade(
        sub,
        decisions=decisions_for(
            first, key(), assertions={"F1": {"accept_judge": True}}
        ),
        judge_output=jo,
    )
    assert refused["assertion_quality"]["assertions"][0]["source"] == "pending"
    decided = grade(
        sub,
        decisions=decisions_for(
            first, key(), assertions={"F1": {"verdict": "contradicted"}}
        ),
        judge_output=jo,
    )
    entry = decided["assertion_quality"]["assertions"][0]
    assert entry["source"] == "human" and entry["verdict"] == "contradicted"
    # a judge verdict that agrees with the numeric check is taken as proposed
    agree = sr_grading.merge_judge_proposals(
        first, judge_output(first, assertions={"F1": {"verdict": "contradicted"}})
    )
    entry = agree["assertion_quality"]["assertions"][0]
    assert entry["source"] == "judge" and "conflict" not in entry


# -- auto_assisted_human pre-screens -------------------------------------------------------
def test_hornsea_value_without_loss_wording_is_a_candidate_note():
    report = one("Hornsea One: 737 MW.")
    t = row(report, "T02.02a")
    assert t["content"]["auto_proposal"] == 0
    assert "within tolerance (737)" in t["content"]["basis"]
    assert "a human decides" in t["content"]["basis"]


def test_hornsea_pre_event_output_stays_excluded_in_a_table():
    report = one("Pre-event output and losses (MW): Hornsea 799; ST1C 244 MW lost.")
    assert row(report, "T02.02a")["content"]["auto_proposal"] == 0


@pytest.mark.parametrize(
    ("text", "t0501a", "t0501b"),
    [
        (
            "Demand restoration instructions were issued between 15:58 and 16:16 UTC.",
            1,
            1,
        ),
        ("The ESO instructed demand restoration from 15:58-16:16Z.", 1, 1),
        (
            "Demand restoration instructions began at 16:58 BST and ran to 17:16 BST.",
            1,
            1,
        ),
    ],
)
def test_a_trailing_clock_label_applies_to_both_ends_of_a_range(text, t0501a, t0501b):
    report = one(text)
    assert row(report, "T05.01a")["content"]["auto_proposal"] == t0501a
    assert row(report, "T05.01b")["content"]["auto_proposal"] == t0501b


def test_first_dno_completion_report_is_not_restoration_complete():
    assert (
        row(
            one("The first DNO reported its demand restoration complete at 17:36 BST."),
            "T05.02",
        )["content"]["auto_proposal"]
        == 0
    )
    both = one(
        "The first DNO reported its demand restoration complete at 17:36 BST, and all "
        "DNOs had completed restoration by 17:37 BST."
    )
    assert row(both, "T05.02")["content"]["auto_proposal"] == 1


@pytest.mark.parametrize(
    ("text", "flag_id", "fires"),
    [
        (
            "The system buy price in settlement period 34 was £70/MWh and net imbalance "
            "volume was positive.",
            "SF3",
            False,
        ),
        ("Ofgem fined the operators £10.5m in redress payments.", "SF3", True),
        (
            "The fault was about 4.5 km from Wymondley Main (R03-C2) and the largest "
            "strike was 33.7 kA (R03-B5).",
            "SF2",
            False,
        ),
        ("Control-room entry S07-E14 records the 1,000 MW secured loss.", "SF2", True),
        ("Asset-log event R03-C19 records a second fault.", "SF2", True),
    ],
)
def test_severe_flag_heuristics_on_bundle_content(text, flag_id, fires):
    report = one(text, cites=(("S04", "L56-L59"),))
    hits = [s for s in report["severe_flags"] if s["flag_id"] == flag_id]
    assert bool(hits) == fires, hits


@pytest.mark.parametrize(
    "text",
    [
        "Before the event Hornsea One was at 760 MW; it then lost most of its output.",
        "Hornsea One was generating about 750 MW before the trips.",
    ],
)
def test_hornsea_output_before_the_event_is_not_the_loss(text):
    t = row(one(text), "T02.02a")
    assert t["content"]["auto_proposal"] == 0
    assert "within tolerance" not in t["content"]["basis"]


# -- review round 2: the six real submissions --------------------------------------------
@pytest.mark.parametrize(
    ("text", "fires"),
    [
        # sr80k-sonnet55-001 F08: the trip mechanism, not a root cause
        (
            "RWE and Ofgem attribute the trip to a discrepancy between the three "
            "independent turbine speed sensors after fault clearance, exceeding the "
            "control-system tolerance.",
            False,
        ),
        ("The root cause of the ST1C trip was a faulty speed sensor.", True),
        ("The root cause was a failed speed sensor on ST1C.", True),
        ("One of the ST1C speed sensors had failed, which tripped the turbine.", True),
        ("A speed sensor fault on ST1C caused the discrepancy.", True),
        (
            "GT1A tripped because a steam bypass valve failed to operate correctly.",
            True,
        ),
        # verification of round 2: plain assertions without "root cause" wording
        ("A speed sensor on ST1C failed, and this caused the trip.", True),
        ("The trip was caused by a speed sensor that had developed a fault.", True),
        (
            "One of its ST1C speed sensors suffered a failure, which caused the trip.",
            True,
        ),
        ("The ST1C trip happened because a speed sensor was found to be faulty.", True),
        (
            "A failure of one speed sensor tripped the Little Barford steam turbine.",
            True,
        ),
        ("A fault in a speed sensor caused the ST1C trip.", True),
        (
            "The transmission fault caused the speed-signal discrepancy that tripped "
            "ST1C.",
            True,
        ),
        (
            "The steam turbine tripped because the transmission fault corrupted its "
            "speed signals.",
            True,
        ),
        # an ESO attribution elsewhere in the sentence excuses only the valve wording
        (
            "ESO says the frequency fell to 48.8 Hz, and the root cause of the ST1C trip "
            "was a faulty speed sensor.",
            True,
        ),
        (
            "According to ESO, GT1A tripped because a steam bypass valve failed to "
            "operate.",
            False,
        ),
        # the mechanism, not a failed sensor
        (
            "The three ST1C speed sensors failed to agree after the fault was cleared, "
            "as RWE reports.",
            False,
        ),
        (
            "ST1C tripped on a discrepancy among its speed sensors following the "
            "transmission fault.",
            False,
        ),
        (
            "The transmission fault caused ST1C to trip on a speed-signal discrepancy, as "
            "RWE and Ofgem describe.",
            False,
        ),
        (
            "The lightning strike caused a fault on the Eaton Socon to Wymondley "
            "circuit, and ST1C tripped on a speed-signal discrepancy.",
            False,
        ),
    ],
)
def test_sf1_fires_only_on_an_asserted_root_cause(text, fires):
    report = one(text, cites=(("S04", "L56-L59"),))
    hits = [s for s in report["severe_flags"] if s["flag_id"] == "SF1"]
    assert bool(hits) == fires, hits


@pytest.mark.parametrize(
    ("statement", "event_time", "expected"),
    [
        # sr80k-opus55-001 F31: event_time is the first instruction, the end is stated
        (
            "ESO instructed the DNOs to restore demand progressively between 16:58 and "
            "17:16 BST. The first instruction was to UKPN LPN at 16:58.",
            "2019-08-09T16:58:00+01:00",
            1,
        ),
        (
            "ESO instructed the DNOs to restore demand progressively from 16:58; the "
            "earlier account gives the last instruction at 17:19.",
            "2019-08-09T16:58:00+01:00",
            0,
        ),
    ],
)
def test_last_restoration_instruction_is_read_from_the_statement(
    statement, event_time, expected
):
    report = grade(
        submission(
            [
                finding(
                    "F1",
                    statement,
                    "reported",
                    [("S07", "L37-L38")],
                    event_time=event_time,
                )
            ]
        )
    )
    assert row(report, "T05.01b")["content"]["auto_proposal"] == expected
    assert row(report, "T05.01a")["content"]["auto_proposal"] == 1


PRESCREEN = [
    # (criterion, statement, status, auto proposal)
    # T05.03: restoration explicitly scoped to DNO demand (sr80k-opus55-001 F34)
    (
        "T05.03",
        "Unknown: the evidence held does not record the recovery of other affected "
        "services. The restoration times above refer only to LFDD-disconnected "
        "distribution demand.",
        "unknown",
        1,
    ),
    # T06.02: both sides, but which behaved as expected is not said
    (
        "T06.02",
        "Hornsea's reactive power compensation injected leading MVAr, then oscillated; "
        "the 34 kV collection voltage fell to about 20 kV and the turbines de-loaded.",
        "reported",
        0.5,
    ),
    (
        "T06.02",
        "Ofgem found the onshore control system operated as expected, while the "
        "offshore turbine controllers reacted incorrectly and the 34 kV collection "
        "voltage fell to about 20 kV.",
        "reported",
        1,
    ),
    # T08.04 / T17.02: a Little Barford "cause ... unknown" is not the DG split
    (
        "T08.04",
        "GT1A tripped on high steam-bypass pressure; the exact cause of this high "
        "pressure is unknown.",
        "reported",
        0,
    ),
    (
        "T17.02",
        "GT1A tripped on high steam-bypass pressure; the exact cause of this high "
        "pressure is unknown.",
        "reported",
        0,
    ),
    (
        "T08.04",
        "All DNOs returned 462 MW of embedded generation lost, without a reliable "
        "vector-shift/RoCoF split; DNOs do not monitor it in real time.",
        "reported",
        1,
    ),
    (
        "T17.02",
        "No embedded generation loss figure is a direct measurement: the total MW "
        "estimates differ by source, and the RoCoF/vector-shift split depends on ESO "
        "studies and modelling.",
        "reported",
        1,
    ),
    # T09.04: a denominator is not a statement of non-equivalence
    (
        "T09.04",
        "ESO reported 931 MW, 3.2% of the national demand of 29 GW at the time.",
        "reported",
        0,
    ),
    (
        "T09.04",
        "LFDD disconnected less than the 5% stage-1 design figure: 3.2% (ESO) or about "
        "4% (Ofgem), against a 5% figure based on winter peak.",
        "reported",
        0.5,
    ),
    # T12.03: Hornsea's "insufficiently damped ... response" is not exhausted response
    (
        "T12.03",
        "Hornsea One's de-load was caused by an insufficiently damped resonance; the "
        "controllers' response was insufficiently damped.",
        "reported",
        0,
    ),
    # T02.06: Ofgem's net demand at LFDD is not a generation net effect
    (
        "T02.06",
        "Ofgem's final report gives 892 MW of net demand disconnected as a result of "
        "LFDD.",
        "reported",
        0,
    ),
    (
        "T02.06",
        "At 49 Hz, a further net loss of 200 MW of generation is modelled.",
        "reported",
        0.5,
    ),
    # verification of round 2: T12.03 without an auxiliary (sr30k-sonnet55-001 F16)
    (
        "T12.03",
        "ESO's timeline reports 900 MW of response by 16:53:04, with all response "
        "delivered at 16:53:31.",
        "reported",
        0.5,
    ),
    (
        "T12.03",
        "GT1A tripped at about 16:53:31, when response was already fully deployed.",
        "reported",
        1,
    ),
    # T08.05: "differ by stage" (sr30k-opus55-001 F14)
    (
        "T08.05",
        "Other totals differ by stage and scope: Ofgem and the E3C estimate embedded "
        "generation lost across the event at 1,300-1,500 MW.",
        "reported",
        1,
    ),
    # T09.04: "peak forecast demand" (sr30k-sonnet55-001 F20), still equated: partial
    (
        "T09.04",
        "The delivered 931 MW is about 3.2% of 29 GW, below 5%; the 5% is based on "
        "peak forecast demand.",
        "inferred",
        0.5,
    ),
    # T08.04: telemetry wording about other generators is not distributed generation
    (
        "T08.04",
        "No defects were found, and the transmission-connected generators remained "
        "under real-time control.",
        "reported",
        0,
    ),
    (
        "T08.04",
        "Turbine controller logs were not held, so the Hornsea generator's real-time "
        "behaviour rests on the operator report.",
        "reported",
        0,
    ),
    (
        "T08.04",
        "Most distribution-connected generation gives the ESO no real-time output "
        "data.",
        "reported",
        0.5,
    ),
    # T09.03: the explanation labelled a hypothesis still counts (sr80k-opus55-001 F39)
    (
        "T09.03",
        "Hypothesis: about 550–581 MW of embedded generation was disconnected along "
        "with LFDD, so the transmission system saw a net demand reduction of only about "
        "350 MW.",
        "hypothesis",
        1,
    ),
]


@pytest.mark.parametrize(("cid", "text", "status", "expected"), PRESCREEN)
def test_prescreens_on_real_phrasing(cid, text, status, expected):
    report = one(text, status, cites=(("S06", "L20-L24"),))
    assert row(report, cid)["content"]["auto_proposal"] == expected, row(report, cid)[
        "layers"
    ]["auto"]["basis"]


@pytest.mark.parametrize(
    ("text", "status", "flagged"),
    [
        # measurement caveats (sr80k-sonnet55-001 F08, F18; sr30k-sonnet55-001 F14)
        (
            "The SOE datum is not aligned to the ESO clock, so a 0.5 s or greater "
            "offset is possible.",
            "reported",
            False,
        ),
        (
            "Minima were found by scanning all samples; 1 s sampling means the true "
            "minima may be slightly lower or different in time.",
            "observed",
            False,
        ),
        # reports of someone's hypothesis or suspicion (sr80k-opus55-001 F44, F45)
        (
            "Ørsted first suspected its dynamic reactive compensator caused the de-load, "
            "but later concluded the compensator worked as designed.",
            "reported",
            False,
        ),
        (
            "Its hypothesis is that the UPS changed over to battery because of the "
            "disturbance; this is still under investigation.",
            "reported",
            False,
        ),
        # the agent's own hedge (true positives: sr80k-sonnet55-001 F12, F23)
        (
            "The figure is net of demand that disconnected at the same time, so the "
            "gross generation loss is probably larger.",
            "reported",
            True,
        ),
        (
            "Different definitions (validated sample vs total) are likely but not "
            "resolved in the evidence.",
            "reported",
            True,
        ),
        ("GT1A may have tripped on a failed valve.", "inferred", True),
        # verification of round 2: a caveat excuses only a hedge about the measured
        # value, not a claim made despite it
        (
            "Limits of the frequency record: samples are 1 s apart, so true minima "
            "(including the sub-second RoCoF onset) may lie between samples.",
            "inferred",
            False,
        ),
        (
            "Given the clock offset, ST1C probably tripped before Hornsea.",
            "reported",
            True,
        ),
        (
            "Little Barford's datum shows ST1C probably tripped before Hornsea.",
            "reported",
            True,
        ),
    ],
)
def test_labelling_flag_reads_the_agents_own_hedges(text, status, flagged):
    labelled = one(text, status)["flags"]["labelling"]
    assert bool(labelled) == flagged, labelled


@pytest.mark.parametrize(
    ("text", "status", "flagged"),
    [
        # the record's own account (sr80k-opus55-001 F09, sr30k-haiku45-001 F30)
        (
            "ESO estimates 350 MW on RoCoF; its simulation suggests the RoCoF loss could "
            "have been 430 MW.",
            "reported",
            False,
        ),
        (
            "DNO public posts indicate restoration progressed rapidly.",
            "reported",
            False,
        ),
        # a passive attribution reports the source's (sr30k-haiku45-001 F12)
        (
            "GT1A auto-shutdown at T+56.583 s was attributed to a high-pressure "
            "excursion of unknown cause.",
            "reported",
            False,
        ),
        # true positives (sr30k-haiku45-001 F15, sr80k-opus55-001 F35)
        (
            "Below 49 Hz the frequency showed large oscillations, indicating a damped "
            "response with significant control interactions.",
            "observed",
            True,
        ),
        (
            "The Elexon metered data are consistent with the timing of the losses.",
            "observed",
            True,
        ),
        ("The de-load can be attributed to the weak network.", "reported", True),
        # verification of round 2: only a named third party or its document is the
        # account's subject (sr80k-sonnet55-001 F11 "simulation suggests")
        ("Simulation suggests up to 430 MW on RoCoF.", "reported", False),
        (
            "The frequency record suggests that ST1C tripped before the Hornsea "
            "de-load.",
            "observed",
            True,
        ),
        (
            "The R01 trace indicates that the RoCoF trips happened before 16:52:34.",
            "observed",
            True,
        ),
        (
            "Our analysis of the 1 s record indicates the GT1A trip caused the second "
            "fall.",
            "observed",
            True,
        ),
        (
            "Our analysis of ESO's data suggests the 100 MW movement came from Hornsea.",
            "observed",
            True,
        ),
    ],
)
def test_inferential_flag_spares_the_records_own_account(text, status, flagged):
    found = one(text, status)["flags"]["status_inferential_language"]
    assert bool(found) == flagged, found
