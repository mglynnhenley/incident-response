"""Accounting-basis checks: a figure is credited only on the basis, stage and
definition of the record it comes from (1,878 vs at least 1,990 MW; 931 vs 892 vs 973
MW; 1,314 vs 1,338 MW; 210 GVA.s vs 219,632 MVA.s; distributed-generation estimates),
derived sums are checked within 1 MW, and overlapping estimates must not be summed."""

from __future__ import annotations

import pytest
from sr_grading_support import finding, grade, judge_output, key, row, submission

from environment.incident import sr_accounting, sr_grading

ACCOUNTING = key()["accounting"]


def classify(
    text: str, status: str = "reported", **extra
) -> list[tuple[str, str, str | None]]:
    sub = submission([finding("F1", text, status, **extra)])
    result = sr_accounting.analyse(sub, [], ACCOUNTING)
    return [(m.figure_id, m.classification, m.bound_source) for m in result.mentions]


def traps(text: str, status: str = "reported", **extra) -> list[dict]:
    sub = submission([finding("F1", text, status, **extra)])
    return sr_accounting.analyse(sub, [], ACCOUNTING).traps


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "ESO's six-component total is 1,878 MW, while Ofgem's at least 1,990 MW is at "
            "a different stage (after GT1A and the 49 Hz reduction).",
            {("GEN_ESO_1878", "attributed"), ("GEN_OFG_1990", "attributed")},
        ),
        (
            "Total generation lost was 1,990 MW according to ESO's Table 2.",
            {("GEN_OFG_1990", "mismatched")},
        ),
        (
            "ESO's total generation lost was 1,990 MW.",
            {("GEN_OFG_1990", "misattributed")},
        ),
        (
            "Ofgem puts the total generation lost at 1,878 MW.",
            {("GEN_ESO_1878", "misattributed")},
        ),
        (
            "1,878 MW of generation was lost, according to ESO.",
            {("GEN_ESO_1878", "attributed")},
        ),
        (
            "Total generation lost through the event was 1.878 GW.",
            {("GEN_ESO_1878", "defined")},
        ),
        ("Total generation lost was 1,878 MW.", {("GEN_ESO_1878", "unattributed")}),
        (
            "The DNOs reported 931 MW, whereas 892 MW is Ofgem's net demand figure.",
            {("LFDD_931", "attributed"), ("LFDD_OFG_892", "attributed")},
        ),
        (
            "LFDD disconnected 931 MW (ESO) or 892 MW (Ofgem, net).",
            {("LFDD_931", "attributed"), ("LFDD_OFG_892", "attributed")},
        ),
        (
            "931 MW of net demand was disconnected by LFDD.",
            {("LFDD_931", "mismatched")},
        ),
        (
            "Ofgem reports that 931 MW of demand was disconnected.",
            {("LFDD_931", "misattributed")},
        ),
        (
            "The DNO returns total 892 MW of demand disconnected.",
            {("LFDD_OFG_892", "misattributed")},
        ),
        (
            "The E3C interim report gives 973 MW of demand disconnected by LFDD.",
            {("LFDD_E3CI_973", "attributed")},
        ),
        (
            "Secondary response held was 1,338 MW (ESO Table 3).",
            {("RESP_SECONDARY_1338", "misattributed")},
        ),
        (
            "ESO's technical report (Table 3) gives 1,314 MW of secondary response, but "
            "ESO's earlier answers to the E3C (Q16, 28 August data) gave 1,338 MW.",
            {
                ("RESP_SECONDARY_1314", "attributed"),
                ("RESP_SECONDARY_1338", "attributed"),
            },
        ),
        (
            "Inertia was 219,632 MVA.s immediately before the trip (ESO answer 42).",
            {("INERTIA_ESO_219632", "attributed")},
        ),
        (
            "Table 4 gives inertia of 219.6 GVA.s.",
            {("INERTIA_ESO_219632", "misattributed")},
        ),
        (
            "Inertia was 210 GVA.s (ESO's answer 42 to the E3C).",
            {("INERTIA_ESO_210", "misattributed")},
        ),
        (
            "ESO's Table 4 gives system inertia of 210 GVA.s.",
            {("INERTIA_ESO_210", "attributed")},
        ),
        (
            "Ofgem estimates 350-430 MW tripped on RoCoF; ESO's estimate was 350 MW.",
            {("DG_ROCOF_350_430", "attributed"), ("DG_ROCOF_350", "attributed")},
        ),
        (
            "The net demand reduction at LFDD was only 350 MW because about 550 MW of "
            "embedded generation also tripped (Ofgem).",
            {("LFDD_NET_350", "attributed"), ("DG_LFDD_550", "attributed")},
        ),
        (
            "The gross loss of embedded generation at 49 Hz was 200 MW.",
            {("DG_49HZ_200", "mismatched")},
        ),
        (
            "ESO measured 1,300-1,500 MW of distributed generation lost.",
            {("DG_TOTAL_1300_1500", "mismatched")},
        ),
    ],
)
def test_figure_classification(text, expected):
    got = {(f, c) for f, c, _ in classify(text)}
    assert got == expected, classify(text)


def test_range_endpoints_are_not_point_figures():
    got = classify(
        "Ofgem estimates 1,300-1,500 MW of distributed generation lost in total."
    )
    assert [(f, c) for f, c, _ in got] == [("DG_TOTAL_1300_1500", "attributed")]


def test_a_source_named_for_another_figure_is_not_borrowed():
    got = classify(
        "The ~500 MW loss-of-mains estimate already includes the 150 MW vector-shift "
        "and 350 MW RoCoF estimates, and the DNOs' 462 MW is a different basis."
    )
    by_figure = {f: (c, s) for f, c, s in got}
    assert by_figure["DG_ROCOF_350"][1] is None and by_figure["DG_VS_150"][1] is None
    assert by_figure["DG_DNO_462"] == ("attributed", "dno")


def test_quantity_basis_names_the_source():
    got = classify(
        "Total generation lost was 1,878 MW.",
        quantity={
            "value": 1878,
            "unit": "MW",
            "basis": "ESO Table 2 cumulative infeed loss",
        },
    )
    assert ("GEN_ESO_1878", "attributed", "eso_final") in got


def test_component_sum_defines_the_eso_total():
    got = classify(
        "Total generation lost was 1,878 MW.",
        derivation="244 + 737 + 150 + 350 + 210 + 187 = 1878",
    )
    assert any(f == "GEN_ESO_1878" and c == "defined" for f, c, _ in got)


@pytest.mark.parametrize(
    ("text", "group"),
    [
        ("Total DG loss = 462 + 500 = 962 MW.", "dg_loss_alternatives"),
        (
            "Embedded generation lost: 150 + 350 + 500 = 1,000 MW.",
            "lom_total_with_its_components",
        ),
        ("RoCoF losses: 350 + 430 = 780 MW.", "rocof_alternatives"),
        (
            "Total generation lost: 1,878 MW + 200 MW = 2,078 MW.",
            "eso_total_mixed_with_other_bases",
        ),
        (
            "Distributed generation: 1,300 + 550 = 1,850 MW.",
            "ofgem_dg_total_with_its_stages",
        ),
    ],
)
def test_overlapping_estimates_summed_are_trapped(text, group):
    found = [t for t in traps(text) if t["type"] == "overlap_sum"]
    assert [t["group"] for t in found] == [group]


@pytest.mark.parametrize(
    "text",
    [
        "Embedded generation lost on loss of mains: 150 + 350 = 500 MW.",
        "ESO's total: 244 + 737 + 150 + 350 + 210 + 187 = 1,878 MW.",
        "Hornsea lost 799 - 62 = 737 MW.",
    ],
)
def test_reconciling_sums_are_not_trapped(text):
    assert traps(text) == []


def test_arithmetic_is_checked_within_1_mw():
    sub = submission(
        [finding("F1", "Little Barford lost 244 + 210 + 187 = 651 MW.", "inferred")]
    )
    result = sr_accounting.analyse(sub, [], ACCOUNTING)
    assert [a.ok for a in result.arithmetic] == [False]
    assert [t["type"] for t in result.traps] == ["arithmetic"]
    ok = sr_accounting.analyse(
        submission(
            [finding("F1", "Little Barford lost 244 + 210 + 187 = 641 MW.", "inferred")]
        ),
        [],
        ACCOUNTING,
    )
    assert [a.ok for a in ok.arithmetic] == [True] and ok.traps == []


def test_times_dates_and_ranges_are_not_expressions():
    sub = submission(
        [
            finding(
                "F1",
                "Between 16:52:33 - 16:53:49 on 2019-08-09 the losses were 1,300-1,500 MW "
                "and frequency fell 49.995 - 48.787 Hz.",
            )
        ]
    )
    assert sr_accounting.analyse(sub, [], ACCOUNTING).arithmetic == []


# -- criteria built on the figures ------------------------------------------------------------
def test_ofgem_1990_substituted_for_the_eso_total_scores_zero():
    report = grade(
        submission(
            [
                finding(
                    "F1",
                    "ESO's total generation lost was 1,990 MW.",
                    "reported",
                    [("S12", "L16-L24")],
                ),
            ]
        )
    )
    assert row(report, "T02.05a")["content"]["auto_proposal"] == 0
    t0206 = row(report, "T02.06")
    assert t0206["content"]["auto_proposal"] == 0
    assert any(c["id"] == "ofgem_1990_on_wrong_basis" for c in t0206["layers"]["caps"])
    assert [t["figure_id"] for t in report["flags"]["accounting_traps"]] == [
        "GEN_OFG_1990"
    ]
    assertion = report["assertion_quality"]["assertions"][0]
    assert assertion["auto_proposal"] == "contradicted"


def test_both_totals_on_their_bases():
    report = grade(
        submission(
            [
                finding(
                    "F1",
                    "ESO's Table 2 total of 1,878 MW includes GT1B after LFDD began.",
                    "reported",
                    [("S12", "L16-L24")],
                ),
                finding(
                    "F2",
                    "Ofgem gives a cumulative loss of at least 1,990 MW at a different stage, after GT1A and a further net reduction of 200 MW at 49 Hz.",
                    "reported",
                    [("S12", "L39-L42")],
                ),
            ]
        )
    )
    assert row(report, "T02.05a")["content"]["auto_proposal"] == 1
    assert row(report, "T02.05b")["content"]["auto_proposal"] == 1
    assert row(report, "T02.06")["content"]["auto_proposal"] == 1
    assert report["flags"]["accounting_traps"] == []


def test_lfdd_931_and_892_need_their_definitions():
    good = grade(
        submission(
            [
                finding(
                    "F1",
                    "The DNOs reported to ESO that 931 MW of demand was disconnected by LFDD relays.",
                    "reported",
                    [("S05", "L35")],
                ),
                finding(
                    "F2",
                    "Ofgem gives 892 MW of net demand disconnected.",
                    "reported",
                    [("S05", "L83-L87")],
                ),
            ]
        )
    )
    assert row(good, "T09.02a")["content"]["auto_proposal"] == 1
    assert row(good, "T09.02b")["content"]["auto_proposal"] == 1
    assert row(good, "T09.02a")["evidence_support"]["auto_proposal"] == 1
    swapped = grade(
        submission(
            [
                finding(
                    "F1",
                    "Ofgem reports 931 MW of demand disconnected, and the DNO returns give 892 MW.",
                    "reported",
                    [("S05", "L35")],
                )
            ]
        )
    )
    assert row(swapped, "T09.02a")["content"]["auto_proposal"] == 0
    assert row(swapped, "T09.02b")["content"]["auto_proposal"] == 0
    assert {t["figure_id"] for t in swapped["flags"]["accounting_traps"]} == {
        "LFDD_931",
        "LFDD_OFG_892",
    }


def test_secondary_response_on_the_wrong_account_is_capped():
    report = grade(
        submission(
            [
                finding(
                    "F1",
                    "Table 3 shows 1,338 MW of secondary response held within 30 s.",
                    "reported",
                    [("R06", "L31")],
                )
            ]
        )
    )
    t = row(report, "T12.01c")
    assert t["content"]["auto_proposal"] == 0
    assert any(c["id"] == "secondary_on_wrong_account" for c in t["layers"]["caps"])


def test_inertia_on_its_basis():
    for text, want in (
        ("ESO's Table 4 gives system inertia of 210 GVA.s.", 1),
        (
            "ESO's answer 42 (Appendix M) estimated inertia immediately before the trip at 219,632 MVA.s.",
            1,
        ),
        ("Table 4 gives inertia of 219.6 GVA.s.", 0),
        ("System inertia was about 210 GVA.s.", 0.5),
    ):
        report = grade(
            submission([finding("F1", text, "reported", [("S12", "L112-L113")])])
        )
        assert row(report, "T12.05")["content"]["auto_proposal"] == want, text


def test_overlapping_dg_sum_caps_the_judge_criterion():
    report = grade(
        submission(
            [
                finding(
                    "F1",
                    "These estimates overlap and use different bases, but in total distributed generation lost was 150 + 350 + 500 = 1,000 MW.",
                    "inferred",
                    [("S06", "L62-L63")],
                )
            ]
        )
    )
    t = row(report, "T08.05")
    assert t["content"]["auto_proposal"] == 0
    assert any(
        c["id"] == "overlapping_dg_estimates_summed" for c in t["layers"]["caps"]
    )


def test_report_only_figures_are_noted_not_credited():
    report = grade(
        submission(
            [
                finding(
                    "F1",
                    "Generation was lost in several steps.",
                    "reported",
                    [("S12", "L16-L24")],
                )
            ],
            report="ESO's Table 2 gives a total of 1,878 MW.",
        )
    )
    t = row(report, "T02.05a")
    assert t["content"]["auto_proposal"] == 0
    assert "only in the report" in t["content"]["basis"]
    mention = report["accounting_basis"]["mentions"][0]
    assert mention["figure_id"] == "GEN_ESO_1878" and mention["finding_id"] is None


def test_hypothesis_status_does_not_earn_a_figure():
    report = grade(
        submission(
            [
                finding(
                    "F1",
                    "ESO's Table 2 total may be 1,878 MW.",
                    "hypothesis",
                    [("S12", "L16-L24")],
                )
            ]
        )
    )
    assert row(report, "T02.05a")["content"]["auto_proposal"] == 0


def test_figures_without_a_unit_go_to_a_human():
    report = grade(
        submission(
            [
                finding(
                    "F1",
                    "Losses (MW): Hornsea 737, ST1C 244, vector shift ~150 (est.), RoCoF "
                    "~350 (est.), GT1A 210, GT1B 187; total 1878.",
                    "reported",
                    [("S12", "L16-L24")],
                )
            ]
        )
    )
    for cid in ("T02.01a", "T02.01b", "T02.05a"):
        t = row(report, cid)
        assert t["content"]["auto_proposal"] == 0
        assert "without a unit in F1" in t["content"]["basis"]
        assert "a human decides" in t["content"]["basis"]
    bare = [m for m in report["accounting_basis"]["mentions"] if m["via"] == "bare"]
    assert {m["figure_id"] for m in bare} >= {
        "DG_VS_150",
        "DG_ROCOF_350",
        "GEN_ESO_1878",
    }
    assert report["flags"]["accounting_traps"] == []


# -- wording between two figures belongs to one of them (review round 1) ------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Generation lost: ESO's 1,878 MW (Table 2, including GT1B) vs Ofgem's at "
            "least 1,990 MW after GT1A.",
            {("GEN_ESO_1878", "attributed"), ("GEN_OFG_1990", "attributed")},
        ),
        (
            "Ofgem's at least 1,990 MW before LFDD versus ESO's 1,878 MW total including "
            "GT1B.",
            {("GEN_OFG_1990", "attributed"), ("GEN_ESO_1878", "attributed")},
        ),
        (
            "Ofgem compares the 892 MW of net demand with ESO's 931 MW.",
            {("LFDD_OFG_892", "attributed"), ("LFDD_931", "attributed")},
        ),
        (
            "Demand disconnected by LFDD: 892 MW net (Ofgem) vs 931 MW (ESO, DNO "
            "returns).",
            {("LFDD_OFG_892", "attributed"), ("LFDD_931", "attributed")},
        ),
        (
            "ESO reports 931 MW of demand disconnected by LFDD (net reduction seen by the "
            "transmission system only about 350 MW).",
            {("LFDD_931", "attributed"), ("LFDD_NET_350", "attributed")},
        ),
        (
            "Inertia was 219,632 MVA.s in ESO's answer 42 vs 210 GVA.s in Table 4.",
            {("INERTIA_ESO_219632", "attributed"), ("INERTIA_ESO_210", "attributed")},
        ),
        (
            "Secondary response held was 1,314 MW in ESO's Table 3 rather than the "
            "1,338 MW in its earlier answers to the E3C.",
            {
                ("RESP_SECONDARY_1314", "attributed"),
                ("RESP_SECONDARY_1338", "attributed"),
            },
        ),
        (
            "More than 1,130 MW was lost within about one second (Ofgem).",
            {("GEN_1131", "attributed")},
        ),
    ],
)
def test_contrasted_figures_keep_their_own_wording(text, expected):
    """A contrast ("vs", "versus", "rather than"), a weak connective ("with", "or"),
    an unclosed parenthesis or a possessive source splits the wording between two
    figures: one figure's qualifier or source is not applied to the other."""
    got = {(f, c) for f, c, _ in classify(text)}
    assert got == expected, classify(text)
    assert traps(text) == []


def test_a_source_across_a_contrast_is_not_borrowed():
    got = classify(
        "Total generation lost was 1,878 MW versus the figure given by Ofgem."
    )
    assert got == [("GEN_ESO_1878", "unattributed", None)]
    # "secured against" is not a contrast
    assert classify("The ESO secured against a loss of 1,000 MW.") == [
        ("SEC_LOSS_1000", "attributed", "eso")
    ]


def test_contrasted_figures_earn_their_criteria_and_survive_the_judge_merge():
    report = grade(
        submission(
            [
                finding(
                    "F1",
                    "Ofgem's at least 1,990 MW before LFDD versus ESO's 1,878 MW total "
                    "including GT1B.",
                    "reported",
                    [("S12", "L16-L24"), ("S12", "L39-L42")],
                ),
                finding(
                    "F2",
                    "Demand disconnected by LFDD: 892 MW net (Ofgem) vs 931 MW (ESO, DNO "
                    "returns).",
                    "reported",
                    [("S05", "L35"), ("S05", "L83-L87")],
                ),
            ]
        )
    )
    assert report["flags"]["accounting_traps"] == []
    assert row(report, "T02.05a")["content"]["auto_proposal"] == 1
    assert row(report, "T09.02a")["content"]["auto_proposal"] == 1
    assert row(report, "T09.02b")["content"]["auto_proposal"] == 1
    assert row(report, "T02.06")["layers"]["caps"] == []
    merged = sr_grading.merge_judge_proposals(
        report,
        judge_output(
            report,
            criteria={
                "T02.06": {"content": 1, "finding_ids": ["F1"], "rationale": "ok"}
            },
        ),
    )
    assert row(merged, "T02.06")["content"]["value"] == 1
    assert {a["auto_proposal"] for a in merged["assertion_quality"]["assertions"]} == {
        None
    }


# -- overlap traps bind terms to figures (review round 1) ---------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Ofgem's cumulative figures: around 1,500 MW after the RoCoF trips, then 1,500 + "
        "100 + 210 + 200 = 2,010 MW before rounding to its at least 1,990 MW.",
        "Ofgem's at least 1,990 MW ... 1,481 + 100 + 210 + 200 = 1,991 MW, i.e. ESO's "
        "cumulative loss at 16:52:34 plus the unexplained 100 MW, GT1A and the 200 MW "
        "net reduction at 49 Hz.",
        "Ofgem's staging: 1,131 + 350 + 100 + 210 + 200 = 1,991 MW.",
        "Cumulative loss: 1,481 MW + 550 MW at LFDD = 2,031 MW.",
    ],
)
def test_staging_sums_are_not_overlap_traps(text):
    """A stage subtotal plus later-stage losses is how Ofgem builds its at least 1,990
    MW (OFG 2.4.5-2.4.11); 1,500 identified as Ofgem's cumulative loss is not the upper
    end of its distributed-generation total."""
    assert [t for t in traps(text) if t["type"] == "overlap_sum"] == []
    report = grade(submission([finding("F1", text, "inferred", [("S12", "L16-L24")])]))
    for cid in ("T02.06", "T08.03", "T08.05"):
        assert not [
            c for c in row(report, cid)["layers"]["caps"] if c["kind"] == "accounting"
        ], cid
    assert report["assertion_quality"]["assertions"][0]["auto_proposal"] is None


def test_overlap_groups_still_trap_without_identifying_wording():
    assert [
        t["group"]
        for t in traps("Distributed generation lost: 1,500 + 100 = 1,600 MW.")
        if t["type"] == "overlap_sum"
    ] == ["ofgem_dg_total_with_its_stages"]
    # without distributed-generation wording the DG-total group is not tested
    assert traps("Ofgem: 1,500 + 100 = 1,600 MW.") == []
    assert [t["group"] for t in traps("ESO's 1,878 + 1,500 = 3,378 MW lost.")] == [
        "eso_total_mixed_with_other_bases"
    ]


# -- the attribution nearest to each figure (review round 2, real submissions) ----------
@pytest.mark.parametrize(
    ("text", "extra", "expected"),
    [
        # list scope "X: a, b, c" (sr80k-sonnet55-001 F17), not the quantity basis
        (
            "Other sources use different stages. Ofgem: >1,130 MW within about 1 s, "
            "about 1,500 MW after the RoCoF trips, and at least 1,990 MW after GT1A and "
            "the 49 Hz net loss.",
            {
                "quantity": {
                    "value": 2258,
                    "unit": "MW",
                    "basis": "my sum of ESO Appendix I Table 1 modelled rows",
                }
            },
            {
                ("GEN_1131", "attributed", "ofgem"),
                ("GEN_OFG_1500", "attributed", "ofgem"),
                ("GEN_OFG_1990", "attributed", "ofgem"),
            },
        ),
        # list items separated by semicolons keep the colon head (sr30k-sonnet55-001)
        (
            "Ofgem: more than 1,130 MW within about 1 s; about 1,500 MW after the RoCoF "
            "trips; at least 1,990 MW at 49 Hz.",
            {},
            {
                ("GEN_1131", "attributed", "ofgem"),
                ("GEN_OFG_1500", "attributed", "ofgem"),
                ("GEN_OFG_1990", "attributed", "ofgem"),
            },
        ),
        # a reporting verb heads a list too (sr80k-opus55-001 F12)
        (
            "Ofgem gives more than 1,130 MW within about 1 s, about 1,500 MW after the "
            "RoCoF trips, and at least 1,990 MW after GT1A.",
            {},
            {
                ("GEN_1131", "attributed", "ofgem"),
                ("GEN_OFG_1500", "attributed", "ofgem"),
                ("GEN_OFG_1990", "attributed", "ofgem"),
            },
        ),
        # a possessive report title is its owner's, not ESO's final report
        # (sr80k-haiku45-001 F33)
        (
            "Ofgem's final report (3 January 2020) reported 892 MW of net demand was "
            "disconnected from local distribution networks as a result of LFDD.",
            {},
            {("LFDD_OFG_892", "attributed", "ofgem")},
        ),
        (
            "The ESO technical report cites 931 MW disconnected; the E3C interim report "
            "cites 973 MW; and the Ofgem final report cites 892 MW net demand.",
            {},
            {
                ("LFDD_931", "attributed", "eso_final"),
                ("LFDD_E3CI_973", "attributed", "e3c_interim"),
                ("LFDD_OFG_892", "attributed", "ofgem"),
            },
        ),
        # a shared subject: the 150 MW is ESO's, not the DNOs' (sr30k-sonnet55-001 F09)
        (
            "About 350 MW of embedded generation tripped on RoCoF (ESO estimate from the "
            "DNO data plus the 150 MW on vector shift).",
            {},
            {
                ("DG_ROCOF_350", "attributed", "eso"),
                ("DG_VS_150", "attributed", "eso"),
            },
        ),
        # a parenthesis around a figure is its own (sr30k-opus55-001 F26); the 1,000
        # MW after "exceeded" is compared with it, not given on ESO's basis by it
        (
            "The losses before LFDD (1,481 MW on ESO's basis) exceeded both the secured "
            "1,000 MW and the primary response held.",
            {},
            {
                ("GEN_ESO_1481", "attributed", "eso"),
                ("SEC_LOSS_1000", "defined", None),
            },
        ),
        # ESO's earlier E3C answer is ESO's earlier account (sr30k-opus55-001 F16)
        (
            "ESO's earlier E3C answer gives 1,338 MW secondary.",
            {},
            {("RESP_SECONDARY_1338", "attributed", "eso_earlier")},
        ),
    ],
)
def test_figures_bind_to_the_nearest_attribution(text, extra, expected):
    got = {m for m in classify(text, **extra) if m[0] != "DG_ROCOF_430"}
    assert got >= expected, classify(text, **extra)
    assert [t for t in traps(text, **extra) if t["type"] != "overlap_sum"] == []


@pytest.mark.parametrize(
    ("text", "extra", "expected"),
    [
        (
            "ESO: about 1,500 MW after the RoCoF trips, and at least 1,990 MW after GT1A.",
            {},
            {
                ("GEN_OFG_1500", "misattributed", "eso"),
                ("GEN_OFG_1990", "misattributed", "eso"),
            },
        ),
        (
            "ESO gives about 1,500 MW after the RoCoF trips and at least 1,990 MW after "
            "GT1A.",
            {},
            {
                ("GEN_OFG_1500", "misattributed", "eso"),
                ("GEN_OFG_1990", "misattributed", "eso"),
            },
        ),
        (
            "ESO's final report (6 September 2019) reported 892 MW of net demand was "
            "disconnected by LFDD.",
            {},
            {("LFDD_OFG_892", "misattributed", "eso_final")},
        ),
        (
            "The DNOs reported 150 MW of embedded generation lost on vector shift.",
            {},
            {("DG_VS_150", "misattributed", "dno")},
        ),
        (
            "ESO's Table 3 gives 1,338 MW secondary.",
            {},
            {("RESP_SECONDARY_1338", "misattributed", "eso_final")},
        ),
        # the quantity basis still binds its own value
        (
            "LFDD disconnected 931 MW of demand.",
            {"quantity": {"value": 931, "unit": "MW", "basis": "Ofgem 931 MW net"}},
            {("LFDD_931", "mismatched", "ofgem")},
        ),
    ],
)
def test_wrong_attributions_still_trap(text, extra, expected):
    """True positives: the nearest attribution is still checked against the figure's
    sources."""
    got = set(classify(text, **extra))
    assert got >= expected, classify(text, **extra)
    assert {t["figure_id"] for t in traps(text, **extra)} >= {f for f, _, _ in expected}


def test_a_reporting_verb_list_ends_at_a_semicolon_and_a_contrast():
    got = {
        (f, s)
        for f, _, s in classify(
            "ESO reports 1,878 MW of generation lost through the event; at least 1,990 "
            "MW lost after GT1A is a later estimate."
        )
    }
    assert ("GEN_OFG_1990", None) in got and ("GEN_ESO_1878", "eso") in got
    got = {
        (f, s)
        for f, _, s in classify(
            "ESO gives 1,878 MW of generation lost through the event, compared with at "
            "least 1,990 MW lost after GT1A."
        )
    }
    assert ("GEN_OFG_1990", None) in got


def test_the_quantity_basis_binds_only_its_own_value():
    """A basis describes its own quantity: "my sum of ESO Appendix I rows" (2,258 MW)
    is not the source of an unattributed 1,500 MW in the statement."""
    got = classify(
        "About 1,500 MW was lost after the RoCoF trips, the cumulative figure.",
        quantity={
            "value": 2258,
            "unit": "MW",
            "basis": "my sum of ESO Appendix I Table 1 modelled rows",
        },
    )
    assert ("GEN_OFG_1500", "defined", None) in got


@pytest.mark.parametrize(
    ("statement", "quantity", "figure"),
    [
        # sr80k-sonnet55-001 F27: Ofgem's "net" is not the 931 MW's definition
        (
            "LFDD quantity by source. ESO Table 6: 931 MW (3.2% of 29 GW). Ofgem: 892 "
            "MW of 'net' demand.",
            {
                "value": 931,
                "unit": "MW",
                "basis": "ESO Table 6 sum of DNO areas (gross, reported); E3C 973 MW; "
                "Ofgem 892 MW net",
            },
            "LFDD_931",
        ),
        # sr30k-sonnet55-001 F19: other figures named without a unit
        (
            "Reported demand disconnected differs by record: ESO 931 MW, Ofgem 892 MW "
            "net.",
            {
                "value": 931,
                "unit": "MW",
                "basis": "ESO Table 6 sum of DNO-reported areas; alternatives 973 (E3C) "
                "and 892 net (Ofgem)",
            },
            "LFDD_931",
        ),
        # sr80k-sonnet55-001 F12: "gross" in a later sentence contrasts with the net
        (
            "A further net ~200 MW of generation loss occurred as frequency reached 49 "
            "Hz. The gross generation loss is probably larger.",
            {"value": 200, "unit": "MW", "basis": "net, modelled by ESO [modelled]"},
            "DG_49HZ_200",
        ),
        # sr30k-opus55-001 F12: "(before LFDD)" belongs to the 1,481 MW
        (
            "On ESO's cumulative-infeed basis the losses total 1,131 MW after vector "
            "shift, 1,481 MW after RoCoF (before LFDD), 1,691 MW after GT1A and 1,878 "
            "MW for the whole event including GT1B.",
            {
                "value": 1878,
                "unit": "MW",
                "basis": "reported, ESO cumulative infeed, whole event",
            },
            "GEN_ESO_1878",
        ),
    ],
)
def test_a_structured_quantity_reads_its_own_wording(statement, quantity, figure):
    sub = submission([finding("F1", statement, quantity=quantity)])
    result = sr_accounting.analyse(sub, [], ACCOUNTING)
    via_quantity = [
        m for m in result.mentions if m.via == "quantity" and m.figure_id == figure
    ]
    assert [m.classification for m in via_quantity] == ["attributed"], via_quantity
    assert result.traps == []


# -- verification of review round 2: binding rules that crossed clauses -----------------
@pytest.mark.parametrize(
    "text",
    [
        # a reporting-verb list ends at "and" opening a new finite clause and at
        # "whereas" / "but"
        "Ofgem gives at least 1,990 MW after GT1A, whereas 1,878 MW is the "
        "six-component cumulative total through GT1B.",
        "Ofgem gives at least 1,990 MW of generation lost after GT1A, but the "
        "cumulative infeed loss through GT1B is 1,878 MW.",
        "Ofgem gives at least 1,990 MW after GT1A and the 49 Hz loss, and 1,878 MW is "
        "the cumulative total through GT1B.",
        "Ofgem reports 892 MW of net demand disconnected, and LFDD relays disconnected "
        "931 MW of demand (3.2% of 29 GW).",
        "The DNOs reported 462 MW lost, and about 150 MW of embedded generation tripped "
        "on vector shift.",
        "Ofgem says the margin was narrow, and the cumulative infeed loss was 1,878 MW "
        "through GT1B.",
        # the next figure's source is its own unless it is a shared citation
        "The 1,878 MW cumulative total sits below the at least 1,990 MW of generation "
        "lost in Ofgem's report.",
        # a source shared by coordinated figures beats a shared subject
        "The DNO returns (462 MW) cannot separate the 150 MW vector-shift and 350 MW "
        "RoCoF estimates made by ESO.",
        # a head after a figure that introduces its own figures, across a semicolon
        "Total generation lost was 1,878 MW over the event; Ofgem says the margin was "
        "narrow and gives at least 1,990 MW after GT1A.",
        # a comparison is a barrier
        "The DNOs reported 462 MW lost, close to the estimated 150 MW vector shift plus "
        "350 MW RoCoF from ESO.",
        # a closed citation parenthesis is not a shared subject
        "Generation lost: 1,878 MW (ESO) plus 1,300-1,500 MW of distributed "
        "generation, about 3,300 MW in total.",
    ],
)
def test_correct_sentences_are_not_misattribution_traps(text):
    assert [
        (t["type"], t.get("figure_id"), t.get("bound_source"))
        for t in traps(text)
        if t["type"] != "overlap_sum"
    ] == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "The DNO returns (462 MW) cannot separate the 150 MW vector-shift and 350 "
            "MW RoCoF estimates made by ESO.",
            {("DG_VS_150", "attributed", "eso"), ("DG_ROCOF_350", "attributed", "eso")},
        ),
        (
            "The DNOs returned 462 MW in total; the 150 MW vector-shift and 350 MW RoCoF "
            "figures are ESO estimates.",
            {("DG_VS_150", "attributed", "eso"), ("DG_ROCOF_350", "attributed", "eso")},
        ),
        # "a and b (Ofgem)": a citation parenthesis shared by coordinated figures
        (
            "About 1,500 MW and at least 1,990 MW (Ofgem) of cumulative generation were "
            "lost at successive stages.",
            {
                ("GEN_OFG_1500", "attributed", "ofgem"),
                ("GEN_OFG_1990", "attributed", "ofgem"),
            },
        ),
    ],
)
def test_coordinated_figures_share_a_trailing_source(text, expected):
    assert set(classify(text)) >= expected, classify(text)
    assert traps(text) == []


def test_a_stage_between_figures_is_not_a_coordination():
    """ "1,990 MW after GT1A plus the 200 MW ... (ESO's modelled net)": the source of
    the later figure is not shared across a stage."""
    got = classify(
        "At least 1,990 MW after GT1A and the 200 MW net at 49 Hz (ESO) were lost."
    )
    assert ("GEN_OFG_1990", "defined", None) in got, got


@pytest.mark.parametrize(
    ("text", "figure", "source"),
    [
        # the list continues through figures with participles ("lost", "disconnected
        # by") and an Oxford comma
        (
            "Ofgem gives 1,130 MW, 1,500 MW, and 1,878 MW of cumulative generation lost.",
            "GEN_ESO_1878",
            "ofgem",
        ),
        (
            "Ofgem gives 892 MW and 931 MW of demand disconnected by LFDD on different "
            "days.",
            "LFDD_931",
            "ofgem",
        ),
        (
            "ESO gives 931 MW gross and 892 MW net of demand disconnected.",
            "LFDD_OFG_892",
            "eso",
        ),
        # an Ofgem figure given to ESO with a coordinated trailing source
        (
            "The 1,500 MW after the RoCoF trips and the 1,990 MW after GT1A are ESO "
            "figures of cumulative generation lost.",
            "GEN_OFG_1990",
            "eso",
        ),
    ],
)
def test_misattributions_in_lists_still_trap(text, figure, source):
    found = {(t["figure_id"], t["bound_source"]) for t in traps(text)}
    assert (figure, source) in found, classify(text)


# -- verification of review round 2: a generic "final report" -----------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Ofgem, in its final report, gives at least 1,990 MW of generation lost.",
            ("GEN_OFG_1990", "attributed", "ofgem"),
        ),
        (
            "In its final report Ofgem gives at least 1,990 MW of generation lost.",
            ("GEN_OFG_1990", "attributed", "ofgem"),
        ),
        (
            "Ofgem's January 2020 final report gives at least 1,990 MW of generation "
            "lost.",
            ("GEN_OFG_1990", "attributed", "ofgem"),
        ),
        (
            "Ofgem's 3 January final report gives at least 1,990 MW of generation lost.",
            ("GEN_OFG_1990", "attributed", "ofgem"),
        ),
        (
            "Ofgem, in its final report (3 January 2020), reported 892 MW of net demand "
            "was disconnected by LFDD.",
            ("LFDD_OFG_892", "attributed", "ofgem"),
        ),
        (
            "According to the final report of the E3C, at least 2,000 MW of generation "
            "was lost.",
            ("GEN_E3C_2000", "attributed", "e3c"),
        ),
        # ESO's final report by default, and when ESO or "technical report" names it
        (
            "The final report gives 1,314 MW of secondary response held.",
            ("RESP_SECONDARY_1314", "attributed", "eso_final"),
        ),
        (
            "ESO's final report gives 1,314 MW of secondary response held.",
            ("RESP_SECONDARY_1314", "attributed", "eso_final"),
        ),
        # not across a contrast (sr30k-sonnet55-001 F27)
        (
            "Inertia: 210 GVAs (final report) vs 219,632 MVA.s (earlier answer).",
            ("INERTIA_ESO_210", "attributed", "eso_final"),
        ),
    ],
)
def test_a_generic_final_report_belongs_to_the_source_named_with_it(text, expected):
    assert expected in classify(text), classify(text)
    assert traps(text) == []


def test_a_generic_final_report_still_traps_a_wrong_figure():
    found = {
        (t["figure_id"], t["bound_source"])
        for t in traps(
            "In its final report Ofgem gives a total generation loss of 1,878 MW."
        )
    }
    assert found == {("GEN_ESO_1878", "ofgem")}


# -- verification of review round 2: ranges ---------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Secondary response held was 1,314 MW in Table 3 and 1,338 MW in Appendix M.",
            {
                ("RESP_SECONDARY_1314", "attributed", "eso_final"),
                ("RESP_SECONDARY_1338", "attributed", "eso_earlier"),
            },
        ),
        (
            "System inertia was 210 GVA.s in ESO Table 4 and 219,632 MVA.s immediately "
            "before the trip in the earlier answer.",
            {
                ("INERTIA_ESO_210", "attributed", "eso_final"),
                ("INERTIA_ESO_219632", "attributed", "eso_earlier"),
            },
        ),
    ],
)
def test_two_figures_joined_by_and_are_not_a_range(text, expected):
    assert set(classify(text)) >= expected, classify(text)


def test_ranges_are_read_only_when_written_as_ranges():
    def values(text: str) -> list:
        return [n.value for n in sr_accounting._numbers(text, "MW", [(1300, 1500)])]

    assert values("between 350 and 430 mw") == [(350.0, 430.0)]
    assert values("between 350 mw and 430 mw") == [(350.0, 430.0)]
    assert values("350-430 mw") == [(350.0, 430.0)]
    assert values("1,300 mw to 1,500 mw") == [(1300.0, 1500.0)]
    assert values("rose from 1,481 mw to 1,990 mw") == [1481.0, 1990.0]
    assert values("150 mw and 350 mw") == [150.0, 350.0]
    assert values("1,022 mw and 1,314 mw") == [1022.0, 1314.0]
    assert values("table 3 and 1,338 mw") == [1338.0]
    assert values("q 16 to 1,338 mw") == [1338.0]


@pytest.mark.parametrize(
    ("text", "trap"),
    [
        (
            "Ofgem gives 1,130 MW, 1,500 MW and 1,878 MW of cumulative generation lost.",
            ("GEN_ESO_1878", "ofgem"),
        ),
        (
            "ESO's cumulative generation loss rose from 1,481 MW to 1,990 MW.",
            ("GEN_OFG_1990", "eso"),
        ),
    ],
)
def test_rising_figures_in_a_list_are_each_checked(text, trap):
    found = {(t["figure_id"], t["bound_source"]) for t in traps(text)}
    assert trap in found, classify(text)


# -- verification of review round 2: labelled and prose sums --------------------------------
@pytest.mark.parametrize(
    ("text", "group"),
    [
        (
            "Total generation lost: 1,878 MW + 200 MW net at 49 Hz = 2,078 MW.",
            "eso_total_mixed_with_other_bases",
        ),
        (
            "Total generation lost: ESO 1,878 MW + 49 Hz net 200 MW = 2,078 MW.",
            "eso_total_mixed_with_other_bases",
        ),
        (
            "Embedded generation lost: loss of mains 500 MW + vector shift 150 MW = 650 "
            "MW.",
            "lom_total_with_its_components",
        ),
        (
            "Embedded generation lost: DNO returns 462 MW + ESO 500 MW = 962 MW.",
            "dg_loss_alternatives",
        ),
        (
            "The embedded generation lost was about 500 MW on loss of mains plus 150 MW "
            "on vector shift, about 650 MW in total.",
            "lom_total_with_its_components",
        ),
        (
            "Adding the DNO's 462 MW to ESO's 500 MW estimate gives 962 MW of embedded "
            "generation lost.",
            "dg_loss_alternatives",
        ),
        (
            "Total generation lost was 1,878 MW plus the 200 MW net at 49 Hz, about "
            "2,078 MW.",
            "eso_total_mixed_with_other_bases",
        ),
    ],
)
def test_labelled_and_prose_sums_of_overlapping_terms_are_trapped(text, group):
    found = [t["group"] for t in traps(text) if t["type"] == "overlap_sum"]
    assert found == [group]


@pytest.mark.parametrize(
    "text",
    [
        "Staging: 1,481 MW plus about 100 MW plus 210 MW plus 200 MW gives about 1,991 "
        "MW of generation lost.",
        "ESO's total: Hornsea 737 MW + Little Barford 641 MW + vector shift 150 MW = "
        "1,528 MW of secured events.",
        # a prose "plus" whose result is not the sum is not a sum
        "Total generation lost was 1,878 MW plus the 200 MW net at 49 Hz, about 49 "
        "seconds after 1,481 MW.",
    ],
)
def test_labelled_and_prose_sums_that_do_not_overlap_are_not_trapped(text):
    assert traps(text) == []


def test_prose_sums_are_never_arithmetic_errors():
    sub = submission(
        [
            finding(
                "F1",
                "Loss of mains was about 500 MW plus 150 MW, about 650 MW in total.",
                "inferred",
            )
        ]
    )
    result = sr_accounting.analyse(sub, [], ACCOUNTING)
    assert result.arithmetic == []
    assert [a.terms for a in result.prose_sums] == [[500.0, 150.0]]
    assert [t["type"] for t in result.traps] == ["overlap_sum"]
