"""Automated proposals and pre-screens of the new full-investigation criteria on
plausible phrasings beyond the key's examples: true positives written the way models
write, and the false positives and negatives increment A's real submissions taught us
to expect (wording bound to the wrong clause, negations, generic vocabulary shared with
other topics, a requirement mistaken for a recommendation)."""

from __future__ import annotations

import pytest
from fi_grading_support import finding, grade, row, submission


def _one(statement: str, status: str = "reported") -> dict:
    return submission([finding("F1", statement, status, [("S08", "L120-L127")])])


AUTOMATED = [
    # T04.02 rail protection threshold and response
    (
        "T04.02",
        "ORR reports that the Class 700/717 protection operated within 200 ms of frequency falling to 49.0 Hz, a design behaviour Siemens programmed.",
        "reported",
        1,
    ),
    (
        "T04.02",
        "The Thameslink trains are designed to trip their traction drives below 49 Hz within 0.2 s (ORR).",
        "reported",
        1,
    ),
    # Ofgem's 200 MW at 49 Hz is net of demand "such as trains": not the rail threshold
    (
        "T04.02",
        "Some embedded generators' 49 Hz protection operated, net of trains disconnecting.",
        "reported",
        0,
    ),
    ("T04.02", "The Class 700 trains tripped at 48.8 Hz.", "reported", 0),
    # T10.02 counts, in lists and with negated driver wording
    (
        "T10.02a",
        "ORR: 29 trains locked out (22 permanent, 7 temporary).",
        "reported",
        1,
    ),
    (
        "T10.02b",
        "ORR: 29 trains locked out (22 permanent, 7 temporary).",
        "reported",
        1,
    ),
    (
        "T10.02c",
        "ORR: 29 trains locked out (22 permanent, 7 temporary).",
        "reported",
        1,
    ),
    (
        "T10.02b",
        "22 of the 29 locked-out trains could not be reset by drivers and needed a technician.",
        "reported",
        1,
    ),
    (
        "T10.02c",
        "22 of the 29 locked-out trains could not be reset by drivers and needed a technician.",
        "reported",
        0,
    ),
    (
        "T10.02c",
        "Seven trains were recovered by driver reset and did not need a technician.",
        "reported",
        1,
    ),
    ("T10.02b", "22 trains were reset by their drivers.", "reported", 0),
    # T10.03 stranded and the Class 387s
    (
        "T10.03a",
        "31 trains were stranded: the 29 Class 700/717 lock-outs plus two Class 387s trapped behind them.",
        "reported",
        1,
    ),
    (
        "T10.03b",
        "31 trains were stranded: the 29 Class 700/717 lock-outs plus two Class 387s trapped behind them.",
        "reported",
        1,
    ),
    (
        "T10.03b",
        "Two Class 387 units were trapped behind failed Class 700s; no Class 387 suffered a shutdown itself.",
        "reported",
        1,
    ),
    # T10.04 versions, either order
    (
        "T10.04",
        "Units on TCMS 3.27.x could only be recovered by a technician with a laptop, whereas those on 3.25.x were recovered by the driver's battery reset.",
        "reported",
        1,
    ),
    (
        "T10.04",
        "Software 3.27 removed the drivers' ability to clear a permanent lock-out; 3.25 units went into a temporary lock-out.",
        "reported",
        1,
    ),
    # T10.05 rail service counts
    (
        "T10.05a",
        "Network Rail's daily report (ORR Table 1) gives 371 cancellations and 220 part-cancellations.",
        "reported",
        1,
    ),
    (
        "T10.05b",
        "ORR's Table 1 totals 14428 delay minutes, while the ESO reports 873 trains delayed.",
        "reported",
        1,
    ),
    # T11 essential services
    (
        "T11.01a",
        "Northern Powergrid's LFDD disconnected Newcastle International Airport for 18 minutes.",
        "reported",
        1,
    ),
    (
        "T11.01b",
        "Ipswich Hospital was not disconnected by LFDD: its own protection operated (UKPN).",
        "reported",
        1,
    ),
    ("T11.01b", "Ipswich Hospital lost power through LFDD stage 1.", "reported", 0),
    (
        "T11.02",
        "On Merseyrail's Wirral line, rectifiers tripped when SP Energy Networks' LFDD cut the local supply, causing 428 minutes of delay.",
        "reported",
        1,
    ),
    # T14.03 early reconnection: real phrasing of increment A's runs
    (
        "T14.03",
        "UKPN's Eastern and South Eastern networks reconnected sites without ESO instruction, contrary to OC6.6.4 as Ofgem cites it.",
        "reported",
        1,
    ),
    (
        "T14.03",
        "EPN and SPN restored customers before being instructed by the ESO, although DNOs may only restore LFDD demand on the ESO's instruction.",
        "reported",
        1,
    ),
    (
        "T14.03",
        "UK Power Networks reconnected some demand early, without ESO instruction.",
        "reported",
        0.5,
    ),
    (
        "T14.03",
        "SP Distribution reconnected customers without informing the ESO.",
        "reported",
        0,
    ),
    # the requirement alone is not the observation
    (
        "T14.03",
        "DNOs are not permitted to restore LFDD demand without the ESO's instruction.",
        "reported",
        0,
    ),
    # T15 communications
    (
        "T15.01a",
        "The ESO control room first spoke to BEIS at 16:41 UTC.",
        "reported",
        1,
    ),
    ("T15.01a", "The ESO updated BEIS at 18:09.", "reported", 0),
    (
        "T15.01b",
        "ESO's first public statement went out on Twitter at 18:27.",
        "reported",
        1,
    ),
    (
        "T15.02",
        "ESO's report gives 17:51 in section 6.2 but 18:00 in section 7 for the first call to Ofgem.",
        "reported",
        1,
    ),
    (
        "T15.03",
        "Hornsea did not inform the ESO when it lost 737 MW and then restarted two modules without coordinating with the ESO.",
        "reported",
        1,
    ),
]


@pytest.mark.parametrize(
    ("cid", "statement", "status", "want"),
    AUTOMATED,
    ids=[f"{c}-{i}" for i, (c, *_) in enumerate(AUTOMATED)],
)
def test_automated_proposals(cid, statement, status, want):
    r = row(grade(_one(statement, status)), cid)
    assert r["content"]["auto_proposal"] == want, r["content"]["basis"]


def _f(i: int, statement: str, status: str = "reported") -> dict:
    return finding(f"F{i}", statement, status, [("S08", "L120-L127")])


JUDGED = [
    (
        "T10.05c",
        [
            _f(
                1,
                "ORR counts 29 trains locked out, whereas GTR's review gives circa 60 units affected.",
            )
        ],
        {},
        1,
    ),
    (
        "T10.05c",
        [_f(1, "Approximately 60 trains shut down; 30 needed a technician.")],
        {},
        0,
    ),
    (
        "T10.01",
        [
            _f(
                1,
                "GTR's Class 700 and 717 units shut down on their own protection even though the OLE supply was never interrupted.",
            )
        ],
        {},
        1,
    ),
    (
        "T10.01",
        [
            _f(
                1,
                "The trains stopped because traction power was lost in the power cut.",
                "inferred",
            )
        ],
        {},
        0,
    ),
    (
        "T11.03",
        [
            _f(
                1,
                "Water: about 3,000 customers lost pressure when booster pumps failed to switch to back-up power (E3C). An oil refinery's own systems detected the frequency drop and shut it down; restart took weeks (E3C).",
            )
        ],
        {},
        1,
    ),
    (
        "T11.03",
        [_f(1, "The Stanlow refinery flared after LFDD disconnected it on 9 August.")],
        {},
        0,
    ),
    (
        "T11.03",
        [
            _f(
                1,
                "A trade item about flaring at Stanlow is dated 12 September 2019, a different event, and is not a 9 August impact.",
            ),
            _f(
                2,
                "Water booster pumps failed to switch to back-up power, affecting 3,000 customers (E3C).",
            ),
        ],
        {},
        0.5,
    ),
    (
        "T14.01",
        [
            _f(
                1,
                "Hornsea One failed the fault ride-through requirement (output back to 90% within 0.5 s) and accepted it did not meet the requirement to damp voltage oscillations.",
            )
        ],
        {},
        1,
    ),
    # the contribution without the requirement is the expectation's partial (key
    # 0.1.1, decision 77: the judge gave both real runs 0.5 for this)
    (
        "T14.02",
        [
            _f(
                1,
                "Little Barford did not continue to provide power after the fault, which contributed to the outage (Ofgem); the root cause of its trips has not been established.",
            )
        ],
        {},
        0.5,
    ),
    (
        "T14.02",
        [
            _f(
                1,
                "Little Barford did not continue to provide power after the fault, against the fault ride-through requirement, which contributed to the outage (Ofgem); the root cause of its trips has not been established.",
            )
        ],
        {},
        1,
    ),
    # a requirement named before Little Barford in an action is not its requirement
    # (the real panel run's summary)
    (
        "T14.02",
        [
            _f(
                1,
                "RWE acknowledged its role by not continuing to provide power after the fault; the root causes remain unresolved.",
            )
        ],
        {
            "summary": "Priorities: independent verification of generator fault ride-through, and root-cause closure at Little Barford [F1]."
        },
        0.5,
    ),
    (
        "T14.02",
        [
            _f(
                1,
                "The ride-through requirement was not met by Little Barford, which contributed to the outage; the root causes remain unresolved.",
            )
        ],
        {},
        1,
    ),
    (
        "T14.04",
        [
            _f(
                1,
                "Ofgem's concerns about the ESO's compliance processes (self-certification, no independent verification) are process concerns; Hornsea acknowledged it did not meet the ride-through requirement; no legal determination or enforcement outcome is in the evidence.",
            )
        ],
        {},
        1,
    ),
    (
        "T14.04",
        [_f(1, "Ofgem ruled that Hornsea breached its licence.", "inferred")],
        {},
        0,
    ),
    # "restoration process ... ESO" is not a compliance-process concern (real run)
    (
        "T14.04",
        [
            _f(
                1,
                "Operational communications during the demand restoration process were efficient and the ESO control room had no failures.",
            )
        ],
        {},
        0,
    ),
    (
        "T14.05",
        [
            _f(
                1,
                "The compliance test reports and simulation studies were not obtained, so ride-through compliance cannot be verified.",
            )
        ],
        {},
        1,
    ),
    # Ofgem's finding of no breach is not missing proof (the real runs' F38); records
    # not held and tests outstanding are the partial (key 0.1.1, decision 77)
    (
        "T14.05",
        [_f(1, "Ofgem found no evidence that the ESO breached the Grid Code.")],
        {},
        0,
    ),
    (
        "T14.05",
        [
            _f(
                1,
                "Ofgem found no evidence that the ESO breached the Grid Code. Plant instrumentation and control records are not held.",
            )
        ],
        {},
        0.5,
    ),
    (
        "T14.05",
        [_f(1, "Hornsea One was still on interim notices, with tests outstanding.")],
        {},
        0.5,
    ),
    (
        "T14.05",
        [
            _f(
                1,
                "There is no evidence of independent Grid Code compliance testing for Hornsea One or Little Barford.",
            )
        ],
        {},
        1,
    ),
    # "dno reports" is not "no reports" (real run)
    (
        "T14.05",
        [
            _f(
                1,
                "This is supported by the Grid Code requirements and by all DNO reports.",
            )
        ],
        {},
        0,
    ),
    # full also needs the 17:10 internal escalation (the expectation's full; key 0.1.1,
    # decision 77: the real panel run, judged 0.5)
    (
        "T15.01c",
        [
            _f(
                1,
                "DNO and rail operator statements blaming National Grid were posted from 17:09, before any ESO statement; the ESO contacted BEIS at 17:41 and Ofgem at 17:51 or 18:00.",
            )
        ],
        {},
        0.5,
    ),
    (
        "T15.01c",
        [
            _f(
                1,
                "DNO and rail operator statements blaming National Grid were posted from 17:09, before any ESO statement; the ENCC reported to the Head of National Control at 17:10; the ESO contacted BEIS at 17:41 and Ofgem at 17:51 or 18:00.",
            )
        ],
        {},
        1,
    ),
    # "whether escalation was delayed" is not the escalation
    (
        "T15.01c",
        [
            _f(
                1,
                "DNO and rail operator statements blaming National Grid were posted from 17:09, before any ESO statement; the ESO contacted BEIS at 17:41 and Ofgem at 17:51 or 18:00. The E3C asked whether escalation was delayed.",
            )
        ],
        {},
        0.5,
    ),
    (
        "T15.04",
        [
            _f(
                1,
                "DNOs and train operators attributed the outage to a National Grid fault before the ESO said anything, and the ESO's first public statement was delayed to 18:27; these did not affect the speed of restoration.",
            )
        ],
        {},
        1,
    ),
    (
        "T15.04",
        [_f(1, "Poor communication caused the power cut to spread.", "inferred")],
        {},
        0,
    ),
    # a reconnection "before ESO was informed" is not a communications issue (real run)
    (
        "T15.04",
        [
            _f(
                1,
                "UKPN Eastern restored at 16:56, before ESO was informed or instructed.",
            )
        ],
        {},
        0,
    ),
    (
        "T19.01",
        [_f(1, "x")],
        {
            "sections": [
                {
                    "heading": "Further evidence requests",
                    "body": "RWE should supply the ST1C speed-signal logs [F1]. GTR should provide TCMS event logs [F1].",
                }
            ]
        },
        1,
    ),
    (
        "T19.01",
        [_f(1, "x")],
        {
            "sections": [
                {"heading": "Next steps", "body": "More analysis is needed [F1]."}
            ]
        },
        0,
    ),
    # ESO's own data request to the DNOs (S06) is not an evidence request by the agent
    (
        "T19.01",
        [
            _f(
                1,
                "After the event ESO requested data from all DNOs on embedded generation lost.",
            )
        ],
        {},
        0,
    ),
    (
        "T19.02",
        [
            _f(
                1,
                "After LFDD the DNOs must notify the ESO and may restore only on its instruction (ESO 2.5); ESO procedure requires a prompt communication to Ofgem and BEIS (Energy Incident Reporting).",
            )
        ],
        {},
        1,
    ),
    (
        "T19.02",
        [_f(1, "ESQCR required DNOs to notify BEIS of the outage.", "inferred")],
        {},
        0.5,
    ),
    (
        "T19.02",
        [
            _f(
                1,
                "ESQCR and OC7 obligations are not in the evidence and were not verified, so they are not relied on; the DNOs must notify the ESO after LFDD (ESO 2.5).",
            )
        ],
        {},
        1,
    ),
    (
        "T18.03",
        [_f(1, "x")],
        {
            "sections": [
                {
                    "heading": "Recommendations",
                    "body": "The ESO should review the SQSS for simultaneous losses [F1].",
                }
            ]
        },
        1,
    ),
    (
        "T18.06",
        [_f(1, "x")],
        {
            "sections": [
                {
                    "heading": "Recommendations",
                    "body": "Owner: Siemens and GTR. Install the recovery patch on all units; verified by a fleet test reported to ORR by March [F1].",
                }
            ]
        },
        1,
    ),
    (
        "T20.05",
        [_f(1, "x")],
        {
            "summary": "Priority actions: the train software patch first, then a compliance-testing review [F1]."
        },
        1,
    ),
    (
        "T20.05",
        [_f(1, "x")],
        {"summary": "The first DNO restored supply at 16:56 [F1]."},
        0,
    ),
    (
        "T20.04",
        [_f(1, "x")],
        {
            "summary": "ESO puts generation lost at 1,878 MW; Ofgem gives at least 1,990 MW [F1]."
        },
        1,
    ),
    (
        "T20.03",
        [_f(1, "x")],
        {
            "summary": "Contributing factors included distributed-generation protection; the Little Barford root causes remain unknown [F1]."
        },
        1,
    ),
    # T13.05: "setting" and generating "units" are not rail vocabulary (real run)
    (
        "T13.05",
        [
            _f(
                1,
                "The peak rate of change was above the 0.125 Hz/s RoCoF protection setting used by some distributed generators; the Little Barford units tripped.",
            )
        ],
        {},
        0,
    ),
]


@pytest.mark.parametrize(
    ("cid", "findings", "kw", "want"),
    JUDGED,
    ids=[f"{c}-{i}" for i, (c, *_) in enumerate(JUDGED)],
)
def test_judge_prescreens(cid, findings, kw, want):
    sub = submission(
        findings, summary=kw.get("summary", "Summary."), sections=kw.get("sections")
    )
    r = row(grade(sub), cid)
    assert r["assessment_mode"] == "judge"
    assert r["content"]["auto_proposal"] == want, r["content"]["basis"]
    # a judge criterion's value waits for the judge; the pre-screen is never the value
    assert r["content"]["source"] == "pending" and r["content"]["value"] is None


def test_contradiction_of_a_judge_criterion_is_a_reviewer_flag():
    report = grade(
        _one(
            "Thameslink's Class 700 trains stopped when their traction supply was lost in the power cut.",
            "inferred",
        )
    )
    r = row(report, "T10.01")
    caps = r["layers"]["caps"]
    assert caps and all(
        c["binding"] is False for c in caps if c["kind"] == "contradiction"
    )
    flagged = report["flags"]["prescreen_contradictions"]
    assert any(f["criterion_id"] == "T10.01" for f in flagged)


def test_t05_03_transport_recovery_route():
    report = grade(
        _one(
            "Demand was restored by the DNOs between 16:58 and 17:37 while frequency had recovered at 16:57; rail disruption continued into Saturday and ORR reports full service within 24 hours."
        )
    )
    r = row(report, "T05.03")
    assert r["content"]["auto_proposal"] == 1
    assert (
        "transport_later" in r["content"]["basis"]
        or "other_services_scoped" in r["content"]["basis"]
    )
    rail_with_demand = grade(
        _one("Rail services recovered at 17:37 when demand was restored.", "inferred")
    )
    assert row(rail_with_demand, "T05.03")["content"]["auto_proposal"] == 0
