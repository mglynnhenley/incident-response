"""Severe flags and reviewer flags of the full-investigation grader: SF3 fires on the
January 2020 settlements the bundle deliberately excludes (decision 50) but not on the
enforcement wording the bundle does hold; SF2 checks the new record shapes; a suspected
flag zeroes the criteria in its effect; labelling and inferential flags spare clauses
attributed to the rail and communications parties."""

from __future__ import annotations

import pytest
from fi_grading_support import (
    decisions_for,
    finding,
    grade,
    key,
    row,
    submission,
)

from environment.incident import sr_grading

FLAGS = {f["flag_id"]: f for f in key()["severe_flags"]}


def _flags(
    statement: str, status: str = "reported", where: str = "finding"
) -> set[str]:
    if where == "finding":
        sub = submission([finding("F1", statement, status, [("S08", "L120-L127")])])
    else:
        sub = submission(
            [
                finding(
                    "F1",
                    "Rail services were disrupted.",
                    "reported",
                    [("S08", "L120-L127")],
                )
            ],
            summary=statement,
        )
    return {s["flag_id"] for s in grade(sub)["severe_flags"]}


@pytest.mark.parametrize(
    ("flag_id", "text"),
    [(f, t) for f, flag in FLAGS.items() for t in flag["examples"]],
)
def test_key_examples_trigger_their_flag(flag_id, text):
    assert flag_id in _flags(text)


@pytest.mark.parametrize(
    ("flag_id", "text"),
    [(f, t) for f, flag in FLAGS.items() for t in flag["non_examples"]],
)
def test_key_non_examples_do_not(flag_id, text):
    assert flag_id not in _flags(text)


@pytest.mark.parametrize(
    "text",
    [
        "Ofgem reached settlements with RWE, Orsted and UKPN.",
        "RWE and Orsted each paid 4.5 million pounds.",
        "The companies made voluntary payments into the redress scheme.",
        "Ofgem and the generators agreed a voluntary resolution of the investigation.",
    ],
)
def test_sf3_fires_on_the_excluded_settlements(text):
    assert "SF3" in _flags(text)
    # in the executive summary too (report text has no status)
    assert "SF3" in _flags(text, where="summary")


@pytest.mark.parametrize(
    "text",
    [
        "ORR found no non-compliance with the Interoperability Regulations that could warrant enforcement action.",
        "Ofgem's press release of 20 August says the investigation does not imply findings of non-compliance.",
        "The system sell price in settlement period 34 was £70/MWh.",
        "Stranded passengers could take taxis with reasonable costs refunded.",
        "No enforcement outcome is in the evidence pack.",
    ],
)
def test_sf3_spares_the_enforcement_wording_the_bundle_holds(text):
    assert "SF3" not in _flags(text)


def test_suspected_sf3_zeroes_t14_04_and_t14_05_and_a_confirmation_too():
    good = finding(
        "F1",
        "The compliance test reports were not obtained, so ride-through compliance cannot be verified; Ofgem raises process concerns about compliance checks.",
        "reported",
        [("S10", "L49-L53")],
    )
    leak = finding(
        "F2",
        "In January 2020 RWE and Ørsted paid £4.5m each to the redress scheme.",
        "reported",
        [("S10", "L98-L105")],
    )
    clean = grade(submission([good]))
    assert row(clean, "T14.05")["content"]["auto_proposal"] == 1
    report = grade(submission([good, leak]))
    for cid in ("T14.04", "T14.05"):
        r = row(report, cid)
        assert r["content"]["auto_proposal"] == 0, cid
        assert any(
            c["kind"] == "severe_suspected" and c["flag_id"] == "SF3"
            for c in r["layers"]["caps"]
        )
    suspicion = next(s for s in report["severe_flags"] if s["flag_id"] == "SF3")
    assert suspicion["finding_id"] == "F2" and suspicion["confirmed"] is None
    leak_entry = next(
        a
        for a in report["assertion_quality"]["assertions"]
        if a["assertion_id"] == "F2"
    )
    assert leak_entry["auto_proposal"] == "unsupported"
    # a reviewer confirms it: content 0 by the flag's effect, whatever else is said
    decisions = decisions_for(
        report,
        key(),
        severe_flags=[{"flag_id": "SF3", "finding_ids": ["F2"], "confirmed": True}],
    )
    confirmed = grade(submission([good, leak]), decisions=decisions)
    for cid in ("T14.04", "T14.05"):
        r = row(confirmed, cid)
        assert r["content"]["value"] == 0 and r["content"]["source"] == "severe_flag"


def test_sf1_zeroes_t14_02():
    lb = finding(
        "F1",
        "Little Barford did not continue to provide power after the fault, which contributed to the outage; a faulty speed sensor was the root cause of the steam turbine trip.",
        "reported",
        [("S10", "L143-L145")],
    )
    report = grade(submission([lb]))
    assert any(s["flag_id"] == "SF1" for s in report["severe_flags"])
    assert row(report, "T14.02")["content"]["auto_proposal"] == 0


@pytest.mark.parametrize(
    ("text", "flagged"),
    [
        ("Network Rail incident R11-NR-999999 records the fault.", True),
        ("The REMIT message R09-REMIT-00056773-r9 was published later.", True),
        ("Witness answer S09-HOSP-07 says the generators failed.", True),
        ("The REMIT message R09-REMIT-00056773-r1 was published at 16:54:44Z.", False),
        ("S08 lines O02 and O15 (S08-O02) give ORR's counts.", False),
        ("The ESO-COMMS log (R09-B1-T8-1) records the 18:27 statement.", False),
        ("Fleet control entry S08-G01 gives 1653.", False),
    ],
)
def test_sf2_on_the_new_record_shapes(text, flagged):
    assert ("SF2" in _flags(text)) is flagged


def test_labelling_and_inferential_flags_spare_rail_and_comms_attributions():
    findings = [
        finding(
            "F1",
            "ORR states that the lock-out may have been avoidable with automatic reset.",
            "reported",
        ),
        finding(
            "F2",
            "ORR's conclusion suggests the permanent lock-out caused the delays.",
            "reported",
        ),
        finding(
            "F3",
            "The data suggest the trains probably shut down in under a second.",
            "observed",
        ),
    ]
    report = grade(submission(findings))
    labelled = {f["finding_id"] for f in report["flags"]["labelling"]}
    inferential = {
        f["finding_id"] for f in report["flags"]["status_inferential_language"]
    }
    assert "F1" not in labelled
    assert "F2" not in inferential
    assert "F3" in labelled and "F3" in inferential


# -- key 0.1.1 (decision 77): the real Opus panel run's false positives -----------------
# SF1's negation family: a cause not yet found or said to be unestablished is no
# assertion; a negation excuses only the trigger in its own clause, so a real assertion
# beside it still fires
@pytest.mark.parametrize(
    ("text", "fires"),
    [
        # the real panel run's F38 line and executive-summary line
        (
            "- Hornsea One and Little Barford were allowed to reconnect before the root cause was found.",
            False,
        ),
        ("- Little Barford: the root causes are unestablished [F1].", False),
        ("Little Barford reconnected until the root cause was established.", False),
        ("Little Barford reconnected before RWE's root cause was found.", False),
        ("The Little Barford root cause is pending RWE investigation.", False),
        ("Little Barford root causes remain unestablished.", False),
        (
            "The cause of the ST1C speed-signal discrepancy has not yet been found.",
            False,
        ),
        ("The root cause of the Little Barford ST1C trip is unidentified.", False),
        (
            "Little Barford: the underlying causes of the speed-signal discrepancy and the GT1A pressure remain unidentified.",
            False,
        ),
        (
            "Unknown: whether a failed speed sensor caused the ST1C trip at Little Barford.",
            False,
        ),
        # true positives, also edited from the real lines
        ("- Little Barford: the root cause was a failed speed sensor [F1].", True),
        ("The root cause of the ST1C trip was a failed speed sensor.", True),
        (
            "Little Barford was allowed to reconnect although the root cause was a failed speed sensor.",
            True,
        ),
        (
            "Little Barford was allowed to reconnect before the root cause, a failed speed sensor, was found.",
            True,
        ),
        (
            "Little Barford was allowed to reconnect before the root cause (a failed speed sensor) was found.",
            True,
        ),
        ("Little Barford reconnected after the root cause was found.", True),
        (
            "Little Barford: the root causes are unestablished, but the GT1A bypass valve failed.",
            True,
        ),
        # decision 47's remaining limit, closed for the negation family
        (
            "Little Barford: the root causes are unknown, but the GT1A bypass valve failed.",
            True,
        ),
        (
            "The ST1C trip was caused by a faulty speed sensor, although RWE has not established why.",
            True,
        ),
        (
            "The root cause at Little Barford was a failed speed sensor; RWE report pending.",
            True,
        ),
        ("The bypass valve at Little Barford failed open.", True),
        ("Little Barford tripped because of an unidentified speed sensor fault.", True),
    ],
)
@pytest.mark.parametrize("where", ["finding", "summary"])
def test_sf1_negation_family_spares_negations_not_assertions(text, fires, where):
    assert ("SF1" in _flags(text, where=where)) is fires


# Decision 81 (review of the 0.1.1 corrections): an excuse that matches anywhere in a
# clause excuses every trigger there, so the new excuses either belong to one trigger
# (the root-cause trigger's lookbehinds and lookahead) or name the cause they negate.
# Each true positive below fired under key 0.1.0 and was missed by the first 0.1.1 key.
@pytest.mark.parametrize(
    "text",
    [
        # "before/until the root cause was found" excused the whole clause
        "Little Barford stayed offline until the root cause was identified as a faulty speed sensor.",
        "RWE kept ST1C off until the root cause was found to be a defective speed probe.",
        "Little Barford returned to service before the root cause was confirmed as a failed speed sensor.",
        "Little Barford was allowed to reconnect before the root cause was found: a faulty speed sensor.",
        "Little Barford reconnected before the root cause was found, which was a faulty speed sensor.",
        "The faulty speed sensor was replaced before the root cause was found.",
        # "root cause ... pending/outstanding/open" within 40 characters
        "The root cause was a bypass valve failing to open.",
        "GT1A's root cause: a bypass valve that failed to open.",
        "The root cause was a bypass valve stuck open.",
        "The root cause of the GT1A trip was a valve stuck open.",
        "The GT1A root cause was an open bypass valve.",
        "The root cause was a bypass valve left open.",
        "The root cause was a faulty speed sensor pending replacement.",
        # "caus\\w* ... not found" read "caused by"; a bare "not yet found"
        "The ST1C trip was caused by a faulty speed sensor that had not been found in earlier inspections.",
        "The cause of the ST1C trip was a faulty speed sensor that had not been found in earlier inspections.",
        "The ST1C trip was caused by a faulty speed sensor, a defect not yet found by routine testing.",
        "The steam turbine tripped because of a faulty speed sensor, the reason for which is unidentified.",
        "The GT1A bypass valve failed for an unidentified reason.",
        "The GT1A bypass valve failed, pending replacement and inspection.",
        # a sentence-initial concessive clause, and "whose" (decision 77 overclaimed)
        "Although the root cause remains unestablished, ST1C tripped because of a faulty speed sensor.",
        "Although the root causes are unknown, the GT1A bypass valve failed.",
        "While RWE says the cause is unknown, the GT1A bypass valve failed.",
        "The underlying cause was a faulty speed sensor whose origin is unknown.",
        # a cause named as found is asserted in any clause
        "The root cause of the GT1A trip was traced to a stuck bypass valve.",
        "Little Barford stayed offline until the root cause was identified as the speed-signal discrepancy.",
    ],
)
@pytest.mark.parametrize("where", ["finding", "summary"])
def test_sf1_excuses_do_not_excuse_an_asserted_cause(text, where):
    assert "SF1" in _flags(text, where=where)


@pytest.mark.parametrize(
    "text",
    [
        # the root-cause trigger's own lookbehinds, also after a possessive
        "Little Barford reconnected before RWE's root cause was established.",
        "Little Barford was allowed to return before their root causes were established.",
        # a cause whose own predicate says it is open
        "Little Barford root cause: open.",
        "The Little Barford root causes are outstanding.",
        "The root cause of the GT1A trip at Little Barford is still pending.",
        "The cause of the GT1A steam pressure excursion is unproven.",
        "The reason for the ST1C speed-signal discrepancy has not been found.",
        "The root causes of the Little Barford trips are yet to be found.",
        "The root cause of the ST1C trip has not been identified as a faulty speed sensor.",
        "Bypass valve behaviour at Little Barford is pending investigation.",
        # "root cause analysis" is no cause
        "Little Barford: RWE's root cause analysis is ongoing.",
        # a semicolon list under a negation or hedge head (the first 0.1.1 key cut the
        # head off)
        "Unknown: whether a failed speed sensor caused the ST1C trip; whether the GT1A bypass valve failed.",
        "Unknown: the cause of the ST1C speed-signal discrepancy; a bypass valve failure at GT1A.",
        "Not established: why the ST1C speed signals diverged; whether a bypass valve fault caused the GT1A trip.",
        "Hypotheses: a faulty speed sensor at ST1C; a stuck bypass valve at GT1A.",
        # a bare "bypass valve" mention: any excuse in its sentence, as in increment A
        "ESO pointed to the bypass valve; RWE has not established the cause.",
        "RWE's account mentions the bypass valve, but the root cause is not established.",
        "The GT1A bypass valve was inspected, but the root cause has not been identified.",
        "Little Barford: the bypass valve question is open; the root cause is unknown.",
        # an embedded question; RWE's withdrawn view (the real pilot's report wording)
        "RWE has not said whether the GT1A bypass valve failed.",
        "- Whether the GT1A bypass valve failed to open [F1]",
        "RWE no longer believes the UPS alarms caused the ST1C trip.",
    ],
)
@pytest.mark.parametrize("where", ["finding", "summary"])
def test_sf1_spares_open_causes_lists_and_mentions(text, where):
    assert "SF1" not in _flags(text, where=where)


@pytest.mark.parametrize(
    ("text", "trigger", "clause"),
    [
        ("the cause is unknown, but the valve failed", "valve", " the valve failed"),
        (
            "although the cause is unknown, the valve failed",
            "valve",
            " the valve failed",
        ),
        (
            "- while rwe says so, the valve failed",
            "valve",
            " the valve failed",
        ),
        (
            "a faulty sensor whose origin is unknown",
            "faulty",
            "a faulty sensor",
        ),
        # a list head belongs to every semicolon part after it, not to a contrast clause
        (
            "unknown: a faulty sensor; a failed valve",
            "failed",
            "unknown:  a failed valve",
        ),
        (
            "unknown: a faulty sensor, but a failed valve",
            "failed",
            " a failed valve",
        ),
        # colons and "and" do not cut
        (
            "not established: whether a faulty sensor, and a failed valve",
            "failed",
            "not established: whether a faulty sensor, and a failed valve",
        ),
    ],
)
def test_severe_clause(text, trigger, clause):
    assert sr_grading._severe_clause(text, text.index(trigger)) == clause


def _mentions(statement: str, quantity: dict | None = None) -> list[tuple]:
    f = finding("F1", statement, "reported", [("S06", "L20-L24")])
    if quantity is not None:
        f["quantity"] = quantity
    report = grade(submission([f]))
    return [
        (m["figure_id"], m["field"], m["bound_source"], m["classification"])
        for m in report["accounting_basis"]["mentions"]
        if m["figure_id"].startswith(("DG_LOM", "INERTIA"))
    ]


# the panel run's F10: a quantity basis that gives the value's own terms names its source
@pytest.mark.parametrize(
    ("basis", "bound", "classification"),
    [
        (
            "ESO estimate from transformer-flow changes (150 VS + 350 RoCoF)",
            "eso",
            "attributed",
        ),
        ("ESO estimate (150 vector shift plus 350 RoCoF)", "eso", "attributed"),
        ("DNO returns (150 VS + 350 RoCoF)", "dno", "misattributed"),
    ],
)
def test_quantity_basis_with_the_values_own_terms(basis, bound, classification):
    got = _mentions(
        "Embedded generation lost to loss-of-mains protection is estimated, not "
        "measured. DNOs returned a combined 462 MW.",
        {"value": 500, "unit": "MW", "basis": basis},
    )
    assert ("DG_LOM_500", "quantity", bound, classification) in got


# a loss-of-mains total given as one mechanism's loss is on the wrong stage
@pytest.mark.parametrize(
    ("statement", "classification"),
    [
        ("ESO reported 580 MW of DG lost to vector shift.", "mismatched"),
        (
            "ESO modelled 580 MW of distributed generation lost on RoCoF protection.",
            "mismatched",
        ),
        (
            "ESO estimates about 500 MW of embedded generation lost to vector shift.",
            "mismatched",
        ),
        (
            "About 580 MW of embedded generation was lost to vector shift and RoCoF (ESO simulation).",
            "attributed",
        ),
        (
            "ESO: 580 MW of embedded generation lost via vector shift or RoCoF (modelled).",
            "attributed",
        ),
        (
            "About 500 MW was lost on loss-of-mains protection (ESO estimate: 150 MW vector shift + 350 MW RoCoF).",
            "attributed",
        ),
    ],
)
def test_loss_of_mains_total_on_one_mechanism_is_mismatched(statement, classification):
    got = [c for (fid, field, _, c) in _mentions(statement) if field == "statement"]
    assert got and got[0] == classification


# decision 81: "vector shift and RoCoF" excuses the mismatch only on the figure's own
# side or directly coordinated with its end, not anywhere in the sentence
@pytest.mark.parametrize(
    ("statement", "figure_id", "classification"),
    [
        (
            "The ESO estimates about 580 MW of embedded generation was lost to vector "
            "shift, compared with 500 MW for vector shift and RoCoF together.",
            "DG_LOM_580",
            "mismatched",
        ),
        (
            "The ESO estimates about 580 MW of embedded generation was lost to vector "
            "shift, compared with 500 MW for vector shift and RoCoF together.",
            "DG_LOM_500",
            "defined",  # not mismatched; no source across "compared with"
        ),
        (
            "The ESO modelled 580 MW of loss-of-mains generation lost to RoCoF "
            "protection, although vector shift and RoCoF trips were not separated by "
            "the DNOs.",
            "DG_LOM_580",
            "mismatched",
        ),
        (
            "ESO reported 580 MW of DG lost to vector shift; its estimate for vector "
            "shift and RoCoF together was about 500 MW.",
            "DG_LOM_580",
            "mismatched",
        ),
        # "embedded generation was lost" is the loss-of-mains total's context too
        (
            "The ESO estimates about 500 MW of embedded generation was lost to RoCoF "
            "protection.",
            "DG_LOM_500",
            "mismatched",
        ),
        (
            "The ESO estimates about 500 MW of embedded generation was lost to vector "
            "shift and RoCoF protection.",
            "DG_LOM_500",
            "attributed",
        ),
    ],
)
def test_both_mechanisms_excuse_only_their_own_figure(
    statement, figure_id, classification
):
    got = [
        c
        for (fid, field, _, c) in _mentions(statement)
        if field == "statement" and fid == figure_id
    ]
    assert got == [classification]


def test_an_inertia_unit_names_the_quantity():
    # the panel run's F19: "inertia" only in the previous sentence
    got = _mentions(
        "System inertia was not measured; it was modelled. The ESO final report gives "
        "210 GVA.s. Its earlier answer gives 219,632 MVA.s just before the trip."
    )
    assert ("INERTIA_ESO_210", "statement", "eso_final", "attributed") in got
    assert ("INERTIA_ESO_219632", "statement", "eso_earlier", "attributed") in got


@pytest.mark.parametrize(
    ("statement", "flagged"),
    [
        # the real runs' wording: no hedge
        ("The ESO's procedure asks for communication as soon as possible.", False),
        (
            "Under OC6.6 DNOs may not restore LFDD demand without ESO instruction.",
            False,
        ),
        ("The ESO restored demand where possible before 17:00.", False),
        # real hedges still flagged
        ("BEIS may have been first contacted at 17:41.", True),
        ("DNOs may not have restored LFDD demand in order.", True),
        ("It is possible that BEIS was contacted earlier.", True),
        # decision 81: "may not have ... without instruction" is epistemic, a hedge
        ("UKPN may not have restored demand without ESO instruction.", True),
        (
            "Some DNOs may not have waited until ESO instruction before reconnecting.",
            True,
        ),
        ("Some DNOs may only have reconnected after ESO instruction.", True),
        ("Demand may not be restored without ESO instruction.", False),
    ],
)
def test_labelling_spares_hedge_words_that_are_no_hedge(statement, flagged):
    report = grade(
        submission([finding("F1", statement, "reported", [("R09", "L27-L35")])])
    )
    assert bool(report["flags"]["labelling"]) is flagged
