"""Provenance segment specs for the documents this track adds or changes.

Each spec is an ordered list of segments; ``start`` is the unique line prefix where a segment
begins (see ``recon_common.resolve_segments``). Every non-framing segment cites verbatim quotes that
``verify_recon.py`` finds on the stated PDF page (after the MVP normalisation), and every number
on a sourced line of these documents must occur in the segment's quotes or source section
labels, unless listed in the segment's ``allow_numbers`` with the reason in ``transformation``.

R01, R03, S03 and S04 reuse the MVP specs unchanged (byte-identical copies). S01 reuses the MVP
spec with the decision-19 clock segment. R08's spec is generated with its text (recon_r08.py).
"""

from __future__ import annotations

import copy
from typing import Any

from recon_common import cat_src, frame, mvp_build, seg, src

# --------------------------------------------------------------------------- section labels

ESO_EXEC = "Executive Summary (clock basis: local time)"
ESO_22 = "2.2 ESO Roles and Responsibilities – Principles of Managing Frequency"
ESO_25 = "2.5 DNO Roles and Responsibilities"
ESO_32 = "3.2 Summary of the Event"
ESO_T1 = "3.3 Detailed Timeline, Table 1 – Timeline of Events"
ESO_T2 = "3.3, Table 2 – Table of cumulative infeed losses"
ESO_F2 = "3.4, Figure 2 – Annotated Frequency Trace of the Event"
ESO_42EG = "4.2 Generation Performance – Embedded Generation"
ESO_42LB = "4.2 Generation Performance – Little Barford"
ESO_42FN2 = "4.2 / 4.4, footnote 2"
ESO_43 = "4.3 Demand disconnection and restoration"
ESO_44 = "4.4 Frequency Response"
ESO_T3 = "4.4, Table 3 - Frequency response holding"
ESO_T4 = (
    "4.4, Table 4 – Comparison of system conditions between 1st July and 9th August"
)
ESO_T6 = "5.1 Distribution Demand, Table 6 - DNO customers affected by LFDD relays"
ESO_61 = "6.1 Operational Communications"
ESO_T7 = "6.1, Table 7 – DNO Areas Communication times"
ESO_7 = "section 7, Report Findings"
ESO_8 = "section 8, Conclusions and Next Steps – Embedded Generation"
ESO_GL = "9 Glossary of Terms"
APP_H = "Appendix H – Managing Frequency with Statutory Limits"
APP_I = "Appendix I – Simulation of the 09 August Event"
APP_M = "Appendix M – ESO E3C Questions and Answers (data available to the ESO on 28 August 2019)"
OFG_24 = "Ofgem section 2, Summary of the event"
OFG_25 = "Ofgem section 2, Consequences of the event, 2.5"
OFG_B4 = "Ofgem Box 4: SQSS"
OFG_ESO = "Ofgem section 3, The ESO, key findings"
OFG_DG = "Ofgem section 3, Distributed generation"
OFG_DNO = "Ofgem section 3, DNOs"
E3C_I = "E3C interim report (October 2019)"
E3C_F = "E3C final report (January 2020)"

CLOCK_SRC = src("ESO", 3, ESO_EXEC, "At 4:52pm on 09 August 2019")
APP_M_DATE = src(
    "APP",
    70,
    APP_M,
    "These answers are all based on the data available to the ESO on 28 August 2019.",
)


def allow(segment: dict[str, Any], *numbers: str) -> dict[str, Any]:
    segment["allow_numbers"] = list(numbers)
    return segment


def clock_seg(
    content: str, extra: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return allow(
        seg(
            "Clock reference:",
            content,
            "reported",
            "paraphrase",
            [CLOCK_SRC] + (extra or []),
            "The sources print local clock times without a zone; read as BST because ESO dates "
            "the event at 4:52pm local time. The offset +01:00 is the BST definition, not a value "
            "taken from the sources.",
        ),
        "01:00",
    )


HEADER = "Header: title, originator, record type, STATUS label"
LEGEND = "Value-status legend"

# --------------------------------------------------------------------------- S01 (decision 19)

S01_CLOCK_LINES = (
    "Clock reference: this reconstructed log is rendered in UTC with an explicit Z suffix. The operator's",
    "published timeline uses local time (16:52:33:490, 16:52:33:728) except one passage, written 15.52.",
)
S01_MVP_CLOCK_LINE = (
    "Clock reference: UTC, explicit Z suffix; BST = UTC+01:00 (the operator labels no clock; UTC is "
    "inferred)."
)

APP_D = mvp_build.APP_D


def s01_spec() -> dict[str, Any]:
    spec = copy.deepcopy(mvp_build.DOCUMENT_SPECS["S01"])
    replaced = False
    for index, segment in enumerate(spec["segments"]):
        if segment["start"] == "Clock reference:":
            spec["segments"][index] = seg(
                "Clock reference:",
                "Clock basis (decision 19): this log is rendered in UTC (Z); the operator's "
                "published timeline uses local time except one passage written 15.52",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        40,
                        APP_D + ", Description of events",
                        "At 16:52 on the 9 August 2019",
                    ),
                    src(
                        "APP",
                        40,
                        APP_D + ", Description of events",
                        "phase to Earth short circuit at exactly 16:52:33:490",
                    ),
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "(16:52:33:728 to 16:52:33:835)",
                    ),
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "began de-loading turbines at 15.52.33.728 and completed the de-load at "
                        "15.52.33.835",
                    ),
                    CLOCK_SRC,
                ],
                "Decision 19: the operator's report prints local clock times (16:52...) almost "
                "everywhere and writes 15.52.33.xxx in one sentence only; ESO dates the same "
                "event at 4:52pm local time. The log rendering in UTC is a choice of this "
                "reconstruction and is stated as such; no BST conversion is given.",
            )
            replaced = True
    if not replaced:
        raise SystemExit("S01: MVP spec has no 'Clock reference:' segment")
    old_clock = (
        "BST "
        "times are written in UTC (Z). The operator report labels no clock: it writes the same instants "
        "as 16:52:33:xxx and, once, as 15.52.33.xxx; the one-hour difference is read as BST and "
        "UTC, and the S01 clock line states that this is an inference. "
    )
    old_basis = (
        "Since bundle 1.1.0 the record gives one clock-basis line (BST = UTC+01:00) and no "
        "per-entry UTC/BST equivalences"
    )
    if old_clock not in spec["construction"] or old_basis not in spec["construction"]:
        raise SystemExit("S01: MVP construction text changed; update s01_spec()")
    spec["construction"] = (
        spec["construction"]
        .replace(
            "BST "
            "times are written in UTC (Z). The operator report labels no clock: it writes the same instants "
            "as 16:52:33:xxx and, once, as 15.52.33.xxx; the one-hour difference is read as BST and "
            "UTC, and the S01 clock line states that this is an inference. ",
            "local "
            "times are written in UTC (Z). Decision 19 (system-response bundle only): the clock line "
            "states that this reconstructed log is rendered in UTC and that the operator's published "
            "timeline uses local time (16:52:33:xxx) except one passage written 15.52.33.xxx; it "
            "gives no BST conversion. ",
        )
        .replace(
            "Since bundle 1.1.0 the record gives one clock-basis line (BST = UTC+01:00) and no "
            "per-entry UTC/BST equivalences",
            "Since MVP bundle 1.1.0 the record gives no per-entry UTC/BST equivalences",
        )
    )
    return spec


# --------------------------------------------------------------------------- S07

S07_T7_QUOTES = [
    src(
        "ESO",
        29,
        ESO_T7,
        "SSE SPED ENW NPG North East NPG Yorkshire UKPN SPN UKPN EPN UKPN LPN WPD South West WPD "
        "South Wales WPD West Midland WPD East Midland",
    ),
    src(
        "ESO",
        29,
        ESO_T7,
        "When was ESO informed demand loss 17:01 17:01 17:01 17:01 17:01 17:04 17:04 16:58 16:56 "
        "17:02 16:57",
    ),
    src(
        "ESO",
        29,
        ESO_T7,
        "When did ESO instruct restoration 17:06 17:13 17:10 17:08 17:10 17:13 17:14 16:58 17:08 "
        "17:05 17:16",
    ),
    src(
        "ESO",
        29,
        ESO_T7,
        "When did restoration complete 17:07 17:17 17:17 17:18 17:12 17:37 17:30",
    ),
    cat_src(
        "CAT-ESOT7",
        "WPD South West",
        "informed_and_instructed_cell_merged_across",
        "WPD South West+WPD South Wales",
        ESO_T7 + " (merged cells read from the page image)",
    ),
    cat_src(
        "CAT-ESOT7",
        "UKPN SPN",
        "complete_cell_merged_across",
        "UKPN SPN+EPN+LPN",
        ESO_T7 + " (merged cells read from the page image)",
    ),
    cat_src(
        "CAT-ESOT7",
        "WPD East Midland",
        "complete_cell_merged_across",
        "WPD SW+S Wales+W Midland+E Midland",
        ESO_T7 + " (merged cells read from the page image)",
    ),
]

S07_Q33_QUOTES = [
    src(
        "APP",
        87,
        APP_M + ", answer 33",
        "SSE SPED ENW NPG North East NPG Yorkshire UKPN SPN UKPN EPN UKPN LPN WPD SW WPD South "
        "Wales WPD West Midland WPD East Midland",
    ),
    src(
        "APP",
        87,
        APP_M + ", answer 33",
        "When was ESO informed of LFDD 17:00 17:01 17:01 17:01 17:01 17:04 17:04 Approx 17:00 "
        "16:56 17:05",
    ),
    src(
        "APP",
        87,
        APP_M + ", answer 33",
        "instruct restoration 17:06 17:13 17:11 17:08 17:11 17:12 17:14 Approx 17:00 17:07 17:18 "
        "17.19",
    ),
    src(
        "APP",
        87,
        APP_M + ", answer 33",
        "restoration complete 17:07 17:17 17:17 17:18 17:12 Approx. 17:40 17:30",
    ),
    src(
        "APP",
        87,
        APP_M + ", answer 33",
        "restoration complete 18:30 17:36 18:30 18:18 18:22 18:34 18:33 18:34 18:30",
    ),
    cat_src(
        "CAT-APPQ33",
        "UKPN SPN",
        "merged_cell_note",
        "restoration_complete cell merged across UKPN SPN/EPN/LPN",
        APP_M + ", answer 33 (merged and blank cells read from the page image)",
    ),
    cat_src(
        "CAT-APPQ33",
        "WPD SW",
        "merged_cell_note",
        "informed_of_lfdd and instruct_restoration merged across WPD SW/South Wales; "
        "restoration_complete and informed_restoration_complete merged across all four WPD areas",
        APP_M + ", answer 33 (merged and blank cells read from the page image)",
    ),
    cat_src(
        "CAT-APPQ33",
        "WPD West Midland",
        "merged_cell_note",
        "informed_of_lfdd cell blank in source",
        APP_M + ", answer 33 (merged and blank cells read from the page image)",
    ),
    cat_src(
        "CAT-APPQ33",
        "WPD East Midland",
        "merged_cell_note",
        "'17.19' printed with a dot in source",
        APP_M + ", answer 33 (merged and blank cells read from the page image)",
    ),
]


def _t1(
    start: str, quote: str, page: int = 12, content: str | None = None
) -> dict[str, Any]:
    return seg(
        start,
        content or f"ESO Table 1 entry {start.strip()}",
        "reported",
        "transcription",
        [src("ESO", page, ESO_T1, quote)],
        "Time and wording as printed in ESO Table 1; spaces inserted between values and units; "
        "values tagged [reported].",
    )


S07_SPEC: dict[str, Any] = {
    "construction": (
        "Synthesised control-room log for the ESO control room (ENCC). Part 1 restates the "
        "operational rows of ESO Table 1 (technical report, 6 September 2019) whose source column "
        "reads ESO, plus the closing row sourced to the DNOs; Table 1 rows sourced to NGET, Ørsted, "
        "RWE, MeteoGroup or the DNOs' LFDD entry, the RWE/ESO GT1A row and ESO's embedded-generation "
        "estimate rows are not reproduced here (they belong to other records). Part 2 restates the "
        "section 6.1 key timestamps; Part 3 the Table 7 per-area times, with merged cells marked as "
        "printed (merges read from the page image via the catalogue parse). Part 4 is ESO's earlier "
        "account in its answers to E3C questions (Appendix M; data available on 28 August 2019), "
        "kept alongside so that differing times stay visible. Part 5 holds ESO's own post-event "
        "assessments. Untimed actions keep no time. BOALF acceptances are not transcribed; the "
        "real Elexon BOALF data (R06) are carried as separate control-log entries of the same "
        "room, and so are the Appendix J call-diagram rows (R08), so the room's log covers Table 1, "
        "Appendix J and the earlier ESO account without duplicating either record."
    ),
    "segments": [
        frame("DOCUMENT S07", HEADER),
        clock_seg(
            "Clock basis: ESO prints local clock times; read as BST; precision as printed",
            [
                src("APP", 87, APP_M + ", answer 33", "Approx 17:00 16:56 17:05"),
            ],
        ),
        frame("Value-status legend:", LEGEND),
        frame(
            "Balancing Mechanism acceptances",
            "Pointer: BOALF acceptances (R06) and Appendix J calls (R08) are separate entries",
        ),
        frame("PART 1", "Part heading (selection rule for Table 1 rows)"),
        _t1(
            "E01  ",
            "16:52:26 Frequency at 50.0Hz, ESO securing for a loss of power infeed of 1000MW",
        ),
        _t1("E02  ", "16:52:34 Frequency response initiates."),
        _t1(
            "E03  ",
            "16:52:44 Frequency Response has delivered at least 650MW of power to stabilise the "
            "frequency.",
        ),
        _t1(
            "E04  ",
            "16:52:58 Frequency drop is arrested at 49.1Hz due to the delivery of frequency "
            "response products",
        ),
        _t1(
            "E05  ",
            "16:52 Contracted response service from Low Frequency Gas Turbines initiated",
        ),
        _t1(
            "E06  ",
            "16:53:04 Frequency Response has delivered 900MW of power to stabilise the frequency",
        ),
        _t1(
            "E07  ",
            "Since 16:53 Short Term Operating Reserve (STOR) units were instructed; overall amount "
            "400MW",
        ),
        _t1(
            "E08  ",
            "16:53:18 Frequency recovers to 49.2Hz, due to the continued delivery of frequency "
            "response",
        ),
        _t1(
            "E09  ",
            "16:53:31 All frequency response is being delivered at this point attempting to "
            "restore the frequency to operational limits.",
            page=13,
        ),
        _t1(
            "E10  ",
            "16:54:20 Control room initiate instructions to generation to restore the system "
            "frequency and response levels to stabilise the system",
            page=13,
        ),
        _t1(
            "E11  ",
            "16:57:15 Frequency returns to 50Hz following over 1,000MW of response and a further "
            "1240MW of control room actions to restore frequency and stabilise the situation",
            page=13,
        ),
        _t1(
            "E12  ",
            "16:58 – 17:16 ESO progressively instructs the DNO’s that they can commence demand "
            "restoration",
            page=13,
        ),
        _t1(
            "E13  ",
            "17:37 All DNO’s have confirmed that demand restoration has been completed DNO’s",
            page=13,
        ),
        frame("PART 2", "Part heading"),
        seg(
            "K1   ",
            "Section 6.1: first report of demand disconnection",
            "reported",
            "paraphrase",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "[16:56] First report of demand disconnection from DNO was received by the ESO "
                    "control room.",
                ),
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "Reports continued to arrive with number of customers and load lost. Enquires "
                    "were received about when demand restoration could begin.",
                ),
            ],
        ),
        seg(
            "K2   ",
            "Section 6.1: restoration instructions 16:58 to 17:16",
            "reported",
            "paraphrase",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "[16:58 to 17:16] Demand restoration instruction to DNOs was initiated by the "
                    "ESO control room. The demand was instructed to restore in a progressive manner.",
                )
            ],
        ),
        seg(
            "K3   ",
            "Section 6.1: first SIR request",
            "reported",
            "paraphrase",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "[17:23] The first Significant Incident Report (SIR) request (Grid Code OC7 and "
                    "OC10) was received from DNOs requesting information about the event.",
                )
            ],
        ),
        seg(
            "K4   ",
            "Section 6.1: NGET control room informed",
            "reported",
            "transcription",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "[17:32] ESO control room informed NGET control room that DNOs had started "
                    "restoration.",
                )
            ],
        ),
        seg(
            "K5   ",
            "Section 6.1: first DNO report of full restoration",
            "reported",
            "paraphrase",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "[17:34] First DNO report was received that their demand had been fully "
                    "restored.",
                )
            ],
        ),
        seg(
            "K6   ",
            "Section 6.1: last DNO restoration report",
            "reported",
            "paraphrase",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "[18:34 and beyond] Last report from DNO informing their demand restoration was "
                    "received. Demand and lost customer figures continued to be supplied by DNOs.",
                )
            ],
        ),
        frame("PART 3", "Part heading and column legend"),
        seg(
            "T01  ",
            "Table 7 per-area times, merged cells marked",
            "reported",
            "layout",
            S07_T7_QUOTES,
            "One row per printed DNO area column; a value printed once across merged columns is "
            "given at the first area and marked 'shared cell' (merges from the page image).",
        ),
        seg(
            "PART 4",
            "Part heading: ESO answers to E3C, data available on 28 August 2019",
            "reported",
            "paraphrase",
            [APP_M_DATE],
        ),
        seg(
            "M1   ",
            "Answer 33 narrative timestamps",
            "reported",
            "paraphrase",
            [
                src(
                    "APP",
                    87,
                    APP_M + ", answer 33",
                    "At 16:56hrs, first report of demand disconnection from DNO was received by "
                    "ENCC.",
                ),
                src(
                    "APP",
                    87,
                    APP_M + ", answer 33",
                    "At 17:00hrs, the first demand restoration instruction was initiated.",
                ),
                src(
                    "APP",
                    87,
                    APP_M + ", answer 33",
                    "The last restoration instruction was sent to WPD East Midland at 17:19hrs. The "
                    "demand was instructed back in a progressive manner.",
                ),
                src(
                    "APP",
                    87,
                    APP_M + ", answer 33",
                    "At 17:22hrs, ENCC informed TNCC that all DNOs had started demand restoration.",
                ),
                src(
                    "APP",
                    87,
                    APP_M + ", answer 33",
                    "At 17:36hrs, first DNO reported their demand restoration was completed. Last "
                    "demand restoration report was received by ENCC at 18:34hrs.",
                ),
            ],
            "Each sentence split into a timed entry; 'hrs' suffix dropped.",
        ),
        seg(
            "Answer 33 table",
            "Answer 33 per-area table, merged and blank cells marked",
            "reported",
            "layout",
            S07_Q33_QUOTES,
            "One row per printed DNO area column; merged values given once and marked 'shared "
            "cell'; the blank WPD West Midland cell and the '17.19' form kept as printed.",
        ),
        frame("Answer 20 (untimed)", "Heading for answer 20"),
        seg(
            "R1   ",
            "Answer 20: 1,240 MW of actions and services used",
            "reported",
            "paraphrase",
            [
                src(
                    "APP",
                    83,
                    APP_M + ", answer 20",
                    "1,240 MW of actions were taken by the ESO to restore frequency to operational "
                    "limits, using the following services:",
                ),
                src(
                    "APP",
                    83,
                    APP_M + ", answer 20",
                    "Short Term Operating Reserve Rapid Start Balancing Mechanism Actions Fast "
                    "Reserve (from BM and non-BM providers).",
                ),
            ],
        ),
        seg(
            "R2   ",
            "Answer 20: automatic services and trigger frequencies",
            "reported",
            "paraphrase",
            [
                src(
                    "APP",
                    83,
                    APP_M + ", answer 20",
                    "static Low Frequency initiated Firm Frequency Responses (FFR) which is designed "
                    "to be triggered at 49.7Hz, EWIC and Moyle interconnectors being initiated at "
                    "49.6Hz and a service contracted with Gas Turbines which was initiated at 49.6Hz "
                    "and 49.5Hz respectively, depending on the agreement between NGESO and the "
                    "providers.",
                )
            ],
        ),
        seg(
            "R3   ",
            "Answer 20: manual actions",
            "reported",
            "paraphrase",
            [
                src(
                    "APP",
                    83,
                    APP_M + ", answer 20",
                    "rapid start service being instructed to one Dinorwig unit, instructions to "
                    "another Dinorwig Unit and two Ffestiniog units from a synchronising position to "
                    "generating and an additional distribution connected diesel generator.",
                ),
                src(
                    "APP",
                    83,
                    APP_M + ", answer 20",
                    "400MW of short term operational reserve was also instructed.",
                ),
            ],
        ),
        seg(
            "R4   ",
            "Answer 20: Coryton South and Carrington",
            "reported",
            "transcription",
            [
                src(
                    "APP",
                    83,
                    APP_M + ", answer 20",
                    "To cover the enduring loss of generation at Little Barford and Hornsea One, "
                    "Coryton South and Carrington were both instructed by NGESO.",
                )
            ],
        ),
        frame("PART 5", "Part heading"),
        frame("Annotation A", "Annotation source heading"),
        seg(
            "A1   ",
            "Section 6.1: communication commenced within 2 minutes",
            "reported",
            "transcription",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "ESO control room commenced communication with DNOs and NGET control room within "
                    "2 minutes of the initial fault.",
                )
            ],
        ),
        seg(
            "A2   ",
            "Section 6.1: earliest and last restoration per post-event analysis",
            "reported",
            "transcription",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "Post-event analysis indicated the earliest restoration was completed at 17:07 "
                    "and the last customers were reconnected at 17:37.",
                )
            ],
        ),
        seg(
            "A3   ",
            "Section 6.1: communications assessment",
            "reported",
            "paraphrase",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "Operational communications were generally efficient and effective during the "
                    "demand restoration process and in the demand loss and restoration reporting "
                    "process. ESO control room experienced no communication issues with customers or "
                    "with communication systems.",
                )
            ],
        ),
        seg(
            "A4   ",
            "Section 6.1: DNOs calling NGET control room",
            "reported",
            "paraphrase",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "Whilst some DNOs incorrectly called the NGET control room, NGET control room "
                    "correctly referred DNO’s to the ESO, with no impact on the restoration process.",
                )
            ],
        ),
        seg(
            "A5   ",
            "Section 6.1: permission and phraseology",
            "reported",
            "transcription",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "Indications are that DNOs did ask specific permission from the ESO control room "
                    "to restore demand. While verbal instructions to DNOs to restore demand did not "
                    "follow agreed phraseology, they were clear and understood.",
                )
            ],
        ),
    ],
}

# --------------------------------------------------------------------------- S05

ESO_T6_QUOTES = [
    src(
        "ESO",
        26,
        ESO_T6,
        "Reporting DNO MW of disconnected demand by LFDD Customers Affected Final Restoration Time "
        "of Demand Scottish Hydro Electric Power Distribution (SHEPD) 0 Scottish Power (SP) 22 "
        "23,117 16:59",
    ),
    src(
        "ESO",
        26,
        ESO_T6,
        "Northern Power Grid (NPG) North East 76 93,081 17:18 Yorkshire 14 10,571 17:12 "
        "Electricity North Limited (ENW) 52 56,613 17:17 SP Manweb 130 74,938 17:15",
    ),
    src(
        "ESO",
        26,
        ESO_T6,
        "Western Power Distribution (WPD) East Midlands 122 150,445 17:25 West Midlands 160 "
        "187,427 17:37 South Wales 36 29,060 17:11 South West 110,273 17:22",
    ),
    src(
        "ESO",
        26,
        ESO_T6,
        "UK Power Networks (UKPN) Eastern 69 79,390 16:56 London 174 239,861 17:37 Southern 69 "
        "81,358 17:15 Scottish Electric Power Distribution (SEPD) 7 16,744 17:07 Totals 931 "
        "1,152,878 17:37",
    ),
]
E3CI_T1_QUOTES = [
    src(
        "E3C-I",
        11,
        E3C_I + ", Table 1",
        "Scottish Hydro Electric Power Distribution (SHEPD) - 0 0 - Scottish Power (SP) 22 23,117 "
        "16:59 Northern PowerGrid (NPG) North East 76 93,081 17:18 Yorkshire 14 10,571 17:12",
    ),
    src(
        "E3C-I",
        11,
        E3C_I + ", Table 1",
        "Electricity North Limited (ENW) - 52 56,613 17:17 SP Manweb - 130 74,938 17:15 Western "
        "Power Distribution (WPD) East Midlands 122 150,445 17:25 West Midlands 190 187,427 17:37",
    ),
    src(
        "E3C-I",
        11,
        E3C_I + ", Table 1",
        "South Wales 36 29,060 17:11 South West 12 110,273 17:22 UK Power Networks (UKPN) Eastern "
        "69 79,390 16:56 London 174 239,861 17:37 Southern 69 81,358 17:15",
    ),
    src(
        "E3C-I",
        11,
        E3C_I + ", Table 1",
        "Southern Electric Power Distribution (SEPD) - 7 16,744 17:07 Total 973 1,152,878 17:37",
    ),
]

S05_SPEC: dict[str, Any] = {
    "construction": (
        "Synthesised per-area DNO LFDD returns. Part 1 restates ESO Table 6 (DNO reported data as "
        "of 13 August 2019 at 12:00) row by row and Part 2 the E3C interim report's Table 1; both "
        "are kept in full rather than reconciled, so their differences (WPD West Midlands 160 vs "
        "190 MW; WPD South West blank vs 12 MW; totals 931 vs 973 MW) stay for the reader to find. "
        "Cells left empty in a table are written 'not given'; dashes are kept. Part 3 restates "
        "statements attributed to DNOs (ESO Table 1 LFDD row; ESO 4.3; E3C interim relay "
        "observations; E3C final 4.0%). Part 4 holds attributed post-event assessments by ESO, "
        "Ofgem and the E3C, including Ofgem's 892 MW net figure and its account of the EPN/SPN "
        "reconnection without ESO instruction, stated only as Ofgem reports it. Ofgem's "
        "enforcement outcomes are deliberately not included (increment B)."
    ),
    "segments": [
        frame("DOCUMENT S05", HEADER),
        clock_seg(
            "Clock basis: restoration times hh:mm unlabelled, read as BST",
            [
                src(
                    "ESO",
                    13,
                    ESO_T1,
                    "16:53:49.398 Frequency breaches 48.8Hz trigger level",
                )
            ],
        ),
        frame("Value-status legend:", LEGEND + " and blank-cell convention"),
        seg(
            "PART 1",
            "Part heading: ESO Table 6 and its data date",
            "reported",
            "paraphrase",
            [
                src(
                    "ESO",
                    26,
                    "5.1 Distribution Demand",
                    "The information is based on DNO reported data as of 13 August 2019 at 12:00.",
                ),
                src(
                    "ESO", 26, ESO_T6, "Table 6 - DNO customers affected by LFDD relays"
                ),
            ],
        ),
        frame("Columns:", "Column legend"),
        seg(
            "D01  ",
            "ESO Table 6 rows as printed (blank cells 'not given')",
            "reported",
            "layout",
            ESO_T6_QUOTES,
            "One row per printed table row; empty cells written 'not given'; units added (MW).",
        ),
        seg(
            "PART 2",
            "Part heading: E3C interim report Table 1",
            "reported",
            "paraphrase",
            [
                src(
                    "E3C-I",
                    11,
                    E3C_I + ", Table 1",
                    "Table 1 Low Frequency Demand Disconnection reported by DNO area.",
                )
            ],
        ),
        seg(
            "F01  ",
            "E3C interim Table 1 rows as printed (dashes kept)",
            "reported",
            "layout",
            E3CI_T1_QUOTES,
            "One row per printed table row; dashes kept; empty cells written 'not given'.",
        ),
        frame("PART 3", "Part heading"),
        seg(
            "G1   ",
            "ESO Table 1 LFDD row (source column DNOs)",
            "reported",
            "transcription",
            [
                src(
                    "ESO",
                    13,
                    ESO_T1,
                    "16:53:49.398 Frequency breaches 48.8Hz trigger level resulting in LFDD. 931MW "
                    "of demand is automatically disconnected. DNOs",
                )
            ],
        ),
        seg(
            "G2   ",
            "ESO 4.3: DNOs indicated 931 MW (3.2%)",
            "reported",
            "transcription",
            [
                src(
                    "ESO",
                    21,
                    ESO_43,
                    "The DNO’s have indicated that 931MW (3.2%) of demand was automatically "
                    "disconnected by the operation of the LFDD scheme.",
                )
            ],
        ),
        seg(
            "G3   ",
            "E3C interim: stage 1 schemes that did not trigger; tolerance",
            "reported",
            "paraphrase",
            [
                src(
                    "E3C-I",
                    11,
                    E3C_I,
                    "Post event, two DNOs reported that a number of LFDD stage 1 schemes did not "
                    "trigger, and therefore did not disconnect demand.",
                ),
                src(
                    "E3C-I",
                    11,
                    E3C_I,
                    "the system frequency did not stay at 48.8Hz long enough to trigger the "
                    "operation of all LFDD schemes",
                ),
                src(
                    "E3C-I",
                    11,
                    E3C_I,
                    "the +/-0.01Hz tolerance setting on the LFDD schemes which meant that when the "
                    "system frequency fell to 48.792Hz, not all schemes were triggered.",
                ),
            ],
        ),
        seg(
            "G4   ",
            "E3C interim: Scotland disconnections, incorrect settings",
            "reported",
            "paraphrase",
            [
                src(
                    "E3C-I",
                    11,
                    E3C_I,
                    "Additionally, disconnections were also experienced in Scotland where LFDD Stage "
                    "1 schemes are meant to be triggered when the system frequency falls to 48.5Hz. "
                    "It has been confirmed that this was due to incorrect LFDD settings that have "
                    "subsequently been corrected.",
                )
            ],
        ),
        seg(
            "G5   ",
            "E3C final: DNOs indicated 4.0%",
            "reported",
            "paraphrase",
            [
                src(
                    "E3C",
                    16,
                    E3C_F + ", section 3",
                    "the DNOs have indicated that 4.0% of demand was actually disconnected equating "
                    "to over 1 million customers",
                )
            ],
        ),
        frame("PART 4", "Part heading"),
        frame("Annotation A", "Annotation source heading"),
        seg(
            "A1   ",
            "ESO 4.3: LFDD worked largely as expected",
            "reported",
            "paraphrase",
            [
                src(
                    "ESO",
                    21,
                    ESO_43,
                    "The LFDD process worked largely as expected. While the process provided "
                    "slightly lower than 5% of demand this did not materially impact the function of "
                    "the LFDD in returning the frequency to normal operational parameters.",
                )
            ],
        ),
        frame("Annotation B", "Annotation source heading"),
        seg(
            "B1   ",
            "Ofgem 2.4.12: stage 1 and 892 MW net",
            "reported",
            "paraphrase",
            [
                src(
                    "OFG",
                    19,
                    OFG_24 + ", 2.4.12",
                    "System frequency continued to fall, dropping below 48.8Hz. This triggered DNOs "
                    "to disconnect approximately 5% of demand",
                ),
                src(
                    "OFG",
                    19,
                    OFG_24 + ", 2.4.12",
                    "‘Stage 1 of Low Frequency Demand Disconnection (LFDD)’. 892MW of net demand was "
                    "disconnected in total from the local distribution networks.",
                ),
            ],
        ),
        seg(
            "B2   ",
            "Ofgem 2.5: 892 MW, ~4%, 1.15 million customers",
            "reported",
            "paraphrase",
            [
                src(
                    "OFG",
                    19,
                    OFG_25,
                    "In total, 892MW of net demand was disconnected from the local distribution "
                    "networks as a result of LFDD, representing approximately 4% of national demand "
                    "and affecting 1.15 million customers.",
                )
            ],
        ),
        seg(
            "B3   ",
            "Ofgem 3.39: estimated 4% on average",
            "estimated",
            "paraphrase",
            [
                src(
                    "OFG",
                    34,
                    OFG_DNO + ", 3.39",
                    "On average, the DNOs disconnected an estimated 4% of demand as measured prior to "
                    "the event, and some disconnected significantly less than 5%.",
                )
            ],
        ),
        seg(
            "B4   ",
            "Ofgem 3.40: relay specification and DG disconnection explanations",
            "reported",
            "paraphrase",
            [
                src(
                    "OFG",
                    34,
                    OFG_DNO + ", 3.40",
                    "The principal cause appears to be the technical specification of some LFDD "
                    "relays which prevented them from activating. These relays would have activated "
                    "if the frequency had dropped marginally lower and the Grid Code permits this "
                    "margin of error. Another cause may have been the disconnection of significant "
                    "volumes of distributed generation as part of the LFDD operation which lowered "
                    "the net demand reduction.",
                )
            ],
        ),
        seg(
            "B5   ",
            "Ofgem 3.36: DG providing response/reserve disconnected via LFDD",
            "reported",
            "paraphrase",
            [
                src(
                    "OFG",
                    33,
                    OFG_DNO + ", 3.36",
                    "some DNOs disconnected distributed generation via LFDD that was providing either",
                ),
                src(
                    "OFG",
                    34,
                    OFG_DNO + ", 3.36",
                    "frequency response or reserve services.",
                ),
            ],
        ),
        seg(
            "B6   ",
            "Ofgem 3.43: EPN/SPN reconnection without ESO instruction (as Ofgem reports it)",
            "reported",
            "paraphrase",
            [
                src(
                    "OFG",
                    35,
                    OFG_DNO + ", 3.43",
                    "Eastern Power Networks plc and South Eastern Power Networks plc (both owned by "
                    "UK Power Networks) reconnected sites without being told to do so by the ESO, "
                    "and acknowledge that they do not appear to have technically met the "
                    "requirements of the Grid Code",
                ),
                src(
                    "OFG",
                    35,
                    OFG_DNO + ", 3.43",
                    "These instances were caused by the configuration of the DNOs’ operational "
                    "systems.",
                ),
                src(
                    "OFG",
                    35,
                    OFG_DNO + ", footnote 29",
                    "29 Grid Code Operation Code 6.6.4",
                ),
            ],
        ),
        seg(
            "B7   ",
            "Ofgem 3.44: SP Distribution 22 MW",
            "reported",
            "paraphrase",
            [
                src(
                    "OFG",
                    36,
                    OFG_DNO + ", 3.44",
                    "SP Distribution erroneously disconnected 22MW in Scotland when system frequency "
                    "fell below 48.8Hz and reconnected customers without informing the ESO.",
                ),
                src(
                    "OFG",
                    36,
                    OFG_DNO + ", 3.44",
                    "The demand disconnection occurred due to an incorrect setting in the DNO’s LFDD "
                    "equipment.",
                ),
            ],
        ),
        frame("Annotation C", "Annotation source heading"),
        seg(
            "C1   ",
            "E3C final: approximately 900 MW",
            "reported",
            "paraphrase",
            [
                src(
                    "E3C",
                    9,
                    E3C_F,
                    "stage one (of nine) of the automatic protection system known as Low Frequency "
                    "Demand Disconnection (LFDD) was triggered, which had the effect of disconnecting "
                    "approximately 900MW of demand",
                ),
                src(
                    "E3C",
                    9,
                    E3C_F,
                    "This was shared out across the different DNOs in England & Wales.",
                ),
            ],
        ),
        seg(
            "C2   ",
            "E3C final: reasons for less than 5%",
            "reported",
            "paraphrase",
            [
                src(
                    "E3C",
                    16,
                    E3C_F + ", section 3",
                    "This action should have resulted in around 5% of national electricity demand "
                    "being disconnected, however the DNOs have indicated that 4.0% of demand was "
                    "actually disconnected",
                ),
                src(
                    "E3C",
                    16,
                    E3C_F + ", section 3",
                    "The 5% demand figure is based on forecasted peak demand during an average cold "
                    "spell.",
                ),
                src(
                    "E3C",
                    16,
                    E3C_F + ", section 3",
                    "The frequency did not drop below 48.8 Hz for long enough to trigger the relays "
                    "to operate",
                ),
                src(
                    "E3C",
                    16,
                    E3C_F + ", section 3",
                    "The growth of embedded generation connected to the distribution network.",
                ),
            ],
        ),
    ],
}

# --------------------------------------------------------------------------- S06

ESO_R4_49HZ = src(
    "ESO",
    21,
    ESO_42EG,
    "A number of embedded generators and demand customers have advised that their protection "
    "operated when the frequency reached 49Hz and as such they were disconnected from the system.",
)
ESO_V2 = src(
    "ESO",
    21,
    ESO_42EG,
    "Post-event Power System studies undertaken by the ESO have indicated that, for an event such "
    "as this, a loss of embedded generation on Vector Shift protection of approximately 150MW "
    "would be expected.",
)


def _est(
    start: str, content: str, status: str, sources: list[dict[str, Any]]
) -> dict[str, Any]:
    return seg(start, content, status, "paraphrase", sources)


S06_SPEC: dict[str, Any] = {
    "construction": (
        "Synthesised record of the embedded (distributed) generation data available after the "
        "event. Part 1 restates ESO's description of the DNO returns to its data request (combined "
        "462 MW; no RoCoF/vector-shift split possible without generator confirmation). Part 2 "
        "restates the data limits stated by ESO and Ofgem. Part 3 lists every published estimate "
        "by source (ESO report, ESO Appendix I, ESO answers to E3C, E3C interim, Ofgem, E3C final) "
        "in the order printed, each entry carrying only that source's own timing, stage and basis "
        "words; the builder assigns no stage and draws no grouping. Estimates are not summed, "
        "reconciled or ranked; which estimates overlap or refer to the same stage (e.g. ESO's "
        "~500 MW and the 150 + 350 MW split, Ofgem's 1,300-1,500 MW whole-event bound) is left for "
        "the reader (T08). Value tags follow each source's own wording: Ofgem's and the E3C's "
        "figures are [reported] unless they call a figure an estimate or approximation, or "
        "attribute it to modelling (Ofgem footnote 31 is restated in Part 2 rather than used to "
        "retag)."
    ),
    "segments": [
        frame("DOCUMENT S06", HEADER),
        clock_seg("Clock basis: ESO prints local clock times; read as BST"),
        frame(
            "Value-status legend:",
            LEGEND + " and statement that no estimate is a measurement",
        ),
        frame("PART 1", "Part heading"),
        _est(
            "R1   ",
            "ESO request to DNOs and the reasons asked for",
            "reported",
            [
                src(
                    "ESO",
                    20,
                    ESO_42EG,
                    "Post event, ESO contacted all DNO’s and requested data related to the volume "
                    "of embedded generation that was disconnected or changed output during the power "
                    "system event on 09 August.",
                ),
                src(
                    "ESO",
                    21,
                    ESO_42EG,
                    "DNOs were asked to indicate the reason for the change of output, for example "
                    "RoCoF, Vector Shift, Active Network Management (ANM) operation.",
                ),
            ],
        ),
        _est(
            "R2   ",
            "Combined DNO return 462 MW",
            "reported",
            [
                src(
                    "ESO",
                    21,
                    ESO_42EG,
                    "All DNOs have responded to this request and indicated a combined total of 462MW "
                    "of embedded generation was lost during the event.",
                )
            ],
        ),
        _est(
            "R3   ",
            "DNO data challenges; no RoCoF/vector shift split",
            "reported",
            [
                src(
                    "ESO",
                    21,
                    ESO_42EG,
                    "In providing their analysis some DNOs noted challenges in obtaining the data "
                    "due to the way it is collected or stored and without confirmation from "
                    "generators, DNOs were unable to determine whether a specific generator tripped "
                    "due to RoCoF or Vector Shift.",
                )
            ],
        ),
        _est(
            "R4   ",
            "Protection operating at 49 Hz (reports to ESO)",
            "reported",
            [ESO_R4_49HZ],
        ),
        frame("PART 2", "Part heading"),
        _est(
            "L1   ",
            "ESO answer 10: no DG output data to ESO",
            "reported",
            [
                APP_M_DATE,
                src(
                    "APP",
                    76,
                    APP_M + ", answer 10",
                    "The majority of distribution connected generation provides no indication of "
                    "proposed output, and no actual output data to the ESO.",
                ),
            ],
        ),
        _est(
            "L2   ",
            "Ofgem 3.45: half-hourly DNO data; partial view",
            "reported",
            [
                src(
                    "OFG",
                    36,
                    OFG_DNO + ", 3.45",
                    "Most of the DNOs only record information on generation volumes on their "
                    "networks on a half-hourly basis, obscuring shorter-term events",
                ),
                src(
                    "OFG",
                    36,
                    OFG_DNO + ", 3.45",
                    "only gives a partial view of which distributed generators tripped off or "
                    "reduced output on their networks at different times in response to the fault.",
                ),
                src(
                    "OFG",
                    36,
                    OFG_DNO + ", 3.45",
                    "we cannot ascertain the resulting volumes of generation output lost at different "
                    "locations or the cause of these losses with confidence from the information "
                    "DNOs have provided",
                ),
            ],
        ),
        _est(
            "L3   ",
            "Ofgem 3.37: DG information variable or severely limited",
            "reported",
            [
                src(
                    "OFG",
                    34,
                    OFG_DNO + ", 3.37",
                    "We also found that the information DNOs collect and record on distributed "
                    "generation is variable or severely limited. As a result, the exact causes and "
                    "timeline of the incident cannot be fully established",
                )
            ],
        ),
        _est(
            "L4   ",
            "Ofgem footnote 19: no real-time DG monitoring",
            "reported",
            [
                src(
                    "OFG",
                    18,
                    OFG_24 + ", footnote 19",
                    "It has not been possibly to fully validate with the DNOs as they also do not "
                    "monitor output from distributed generators in real-time.",
                )
            ],
        ),
        _est(
            "L5   ",
            "Ofgem footnote 31: basis of Ofgem's DG figures",
            "reported",
            [
                src(
                    "OFG",
                    36,
                    OFG_DNO + ", footnote 31",
                    "We have been able to ascertain the distributed generation losses described in "
                    "section 2 based on our validation of the frequency event modelling carried out "
                    "by the ESO.",
                )
            ],
        ),
        frame("PART 3", "Part heading: estimates listed by source, not grouped"),
        frame("ESO technical report dated 6 September 2019", "Source heading"),
        _est(
            "E1   ",
            "ESO Table 1: ~150 MW vector shift at 16:52:33",
            "estimated",
            [
                src(
                    "ESO",
                    12,
                    ESO_T1,
                    "16:52:33 Approximately 150MW of embedded generation trips on vector-shift "
                    "protection",
                )
            ],
        ),
        _est(
            "E2   ",
            "ESO Table 1: ~350 MW RoCoF at 16:52:34 with cumulative bracket",
            "estimated",
            [
                src(
                    "ESO",
                    12,
                    ESO_T1,
                    "16:52:34 Approximately 350MW of embedded generation trips on RoCoF protection "
                    "[1,481MW cumulative infeed loss]",
                )
            ],
        ),
        _est(
            "E3   ",
            "ESO Figure 2 annotation: ~500 MW transformer loadings [16:52:34]",
            "estimated",
            [
                src(
                    "ESO",
                    14,
                    ESO_F2,
                    "Increase in transformer loadings (Loss Of Mains) ~500MW [16:52:34]",
                )
            ],
        ),
        _est(
            "E4   ",
            "ESO Figure 2 annotation: 200 MW @49Hz",
            "modelled",
            [src("ESO", 14, ESO_F2, "Embedded gen. loss 200 MW @49Hz")],
        ),
        _est("E5   ", "ESO 4.2: ~150 MW expected from studies", "estimated", [ESO_V2]),
        _est(
            "E6   ",
            "ESO 4.2: ~350 MW RoCoF derived from 150 MW + DNO data",
            "estimated",
            [
                ESO_V2,
                src(
                    "ESO",
                    21,
                    ESO_42EG,
                    "Therefore, based on this plus the data provided by the DNO’s, it is estimated "
                    "that approximately 350MW of embedded generation was lost due to RoCoF",
                ),
            ],
        ),
        _est(
            "E7   ",
            "ESO 4.2: protection at 49 Hz; net effect modelled as 200 MW",
            "modelled",
            [
                ESO_R4_49HZ,
                src(
                    "ESO",
                    21,
                    ESO_42EG,
                    "The net effect of this disconnection has been modelled as a 200MW loss of "
                    "generation. Protection operating at this frequency was not expected and has not "
                    "previously been observed.",
                ),
            ],
        ),
        _est(
            "E8   ",
            "ESO footnote 2: 580 MW v 500 MW",
            "modelled",
            [
                src(
                    "ESO",
                    21,
                    ESO_42FN2,
                    "ESO simulation data indicates that the overall total embedded generation loss "
                    "could be slightly higher (580MW v 500MW)",
                )
            ],
        ),
        _est(
            "E9   ",
            "ESO section 7: broadly in line with expectation",
            "reported",
            [
                src(
                    "ESO",
                    33,
                    ESO_7,
                    "Levels of embedded generation tripping due to RoCoF and vector shift were "
                    "broadly in line with what was expected.",
                )
            ],
        ),
        _est(
            "E10  ",
            "ESO section 8: ~500 MW on loss of mains during the event",
            "estimated",
            [
                src(
                    "ESO",
                    35,
                    ESO_8,
                    "During the event, approximately 500MW of embedded generation tripped on Loss of "
                    "Mains protection (vector shift and Rate of Change of Frequency).",
                )
            ],
        ),
        _est(
            "E11  ",
            "ESO Appendix I: vector shift at the time of the circuit trip",
            "estimated",
            [
                src(
                    "APP",
                    62,
                    APP_I,
                    "The loss due to Vector Shift of 150 MW is estimated to have occurred at the "
                    "time of the circuit trip as highlighted previously.",
                )
            ],
        ),
        _est(
            "E12  ",
            "ESO Appendix I: 350 MW (DNO data) vs 430 MW (simulation)",
            "modelled",
            [
                src(
                    "APP",
                    62,
                    APP_I,
                    "based on the data from DNOs, the volume of embedded generation lost through "
                    "RoCoF was 350MW while analysis of the simulation data indicates that it may be "
                    "slightly higher at 430MW.",
                )
            ],
        ),
        _est(
            "E13  ",
            "ESO Appendix I: 581 MW additional; net 350 MW",
            "modelled",
            [
                src(
                    "APP",
                    62,
                    APP_I,
                    "Our modelling indicates that an additional 581 MW of embedded generation was "
                    "also disconnected either part of the LFDD scheme or via another mechanism, "
                    "resulting in a net reduction in demand of 350 MW.",
                )
            ],
        ),
        frame("ESO answers to E3C questions", "Source heading"),
        _est(
            "E14  ",
            "ESO answer 7: ~500 MW lost in the incident, from IEMS flows; split not yet made",
            "estimated",
            [
                APP_M_DATE,
                src(
                    "APP",
                    75,
                    APP_M + ", answer 7",
                    "We estimate that approximately 500 MW of embedded generation was lost in the "
                    "incident.",
                ),
                src(
                    "APP",
                    75,
                    APP_M + ", answer 7",
                    "The volume has been estimated by analysing the changes in flows between the "
                    "Transmission Networks and the Distribution Networks using metered data gathered "
                    "from our IEMS system.",
                ),
                src(
                    "APP",
                    75,
                    APP_M + ", answer 7",
                    "We have corrected this change for the frequency characteristics of demand and "
                    "allowed for frequency response services in the distribution network.",
                ),
                src(
                    "APP",
                    75,
                    APP_M + ", answer 7",
                    "to determine whether we can a split between RoCoF and Vector Shift connected "
                    "generation",
                ),
            ],
        ),
        frame("E3C interim report", "Source heading"),
        _est(
            "E15  ",
            "E3C interim: ~600 MW at this point (LFDD or another mechanism); net 350 MW",
            "estimated",
            [
                src(
                    "E3C-I",
                    5,
                    E3C_I,
                    "However, the ESO Technical Report states that approximately 600MW of embedded "
                    "generation was also disconnected at this point, either as part of the LFDD "
                    "scheme or via another mechanism, resulting in a net reduction in demand of "
                    "350MW.",
                )
            ],
        ),
        frame("Ofgem report dated 3 January 2020", "Source heading"),
        _est(
            "E16  ",
            "Ofgem 2.4.6: RoCoF above 0.125 Hz/s; an estimated 350-430 MW",
            "estimated",
            [
                src(
                    "OFG",
                    17,
                    OFG_24 + ", 2.4.6",
                    "caused the frequency of the electricity system to fall at a rate of change of "
                    "frequency (RoCoF) above 0.125Hz/s. Some distributed generators operating",
                ),
                src(
                    "OFG",
                    18,
                    OFG_24 + ", 2.4.6",
                    "under legacy Distribution Code requirements have loss of mains protection "
                    "mechanisms triggered by RoCoF set at this rate.",
                ),
                src("OFG", 18, OFG_24 + ", 2.4.6", "As a result, an estimated 350-"),
                src(
                    "OFG",
                    18,
                    OFG_24 + ", 2.4.6",
                    "430MW of distributed generation tripped off unnecessarily, based on information "
                    "provided by the ESO",
                ),
            ],
        ),
        _est(
            "E17  ",
            "Ofgem footnote 19: basis of the ESO figure; up to 580 MW",
            "estimated",
            [
                src(
                    "OFG",
                    18,
                    OFG_24 + ", footnote 19 (to 2.4.6)",
                    "This has been inferred by the ESO from a 500MW increase in transformer loadings "
                    "at the interface with the distribution network. The ESO estimated 150MW of "
                    "vector shift distributed generation tripped and attributed the remainder to "
                    "RoCoF. Further ESO modelling suggests the total loss of distributed generation "
                    "from vector shift and RoCoF could have been up to 580MW.",
                )
            ],
        ),
        _est(
            "E18  ",
            "Ofgem 2.4.11 and footnote 20: further net reduction of 200 MW at 49 Hz",
            "reported",
            [
                src(
                    "OFG",
                    18,
                    OFG_24 + ", 2.4.11",
                    "There was a further net reduction in generation of 200MW at 49Hz",
                ),
                src(
                    "OFG",
                    18,
                    OFG_24 + ", 2.4.11",
                    "Some distributed generators tripped due to protection mechanisms set to "
                    "activate when the frequency falls to 49Hz, and this could be the cause of the "
                    "net reduction in generation observed.",
                ),
                src(
                    "OFG",
                    18,
                    OFG_24 + ", footnote 20",
                    "This figure is net of demand disconnection, such as trains and large industrial "
                    "customers we are aware of.",
                ),
            ],
        ),
        _est(
            "E19  ",
            "Ofgem 2.4.12-2.4.13: below 48.8 Hz, Stage 1 LFDD; net 350 MW; ~550 MW at this point",
            "estimated",
            [
                src(
                    "OFG",
                    19,
                    OFG_24 + ", 2.4.12",
                    "System frequency continued to fall, dropping below 48.8Hz.",
                ),
                src(
                    "OFG",
                    19,
                    OFG_24 + ", 2.4.12",
                    "known as ‘Stage 1 of Low Frequency Demand Disconnection (LFDD)’",
                ),
                src(
                    "OFG",
                    19,
                    OFG_24 + ", 2.4.13",
                    "The ESO reported that the net demand reduction seen by the transmission system "
                    "was only 350MW. This indicates that approximately 550MW of additional "
                    "distributed generation was lost at this point.",
                ),
            ],
        ),
        _est(
            "E20  ",
            "Ofgem 3.30: 1,300-1,500 MW across the event",
            "estimated",
            [
                src(
                    "OFG",
                    32,
                    OFG_DG + ", 3.30",
                    "Our lower bound for total estimated distributed generation lost across the event "
                    "is 1,300MW, and the loss could be as high as 1,500MW.",
                )
            ],
        ),
        _est(
            "E21  ",
            "Ofgem 3.31: at least 500 MW in the first second",
            "estimated",
            [
                src(
                    "OFG",
                    32,
                    OFG_DG + ", 3.31",
                    "At least 500MW of distributed generation is estimated to have been lost due to "
                    "loss of mains protection settings (RoCoF and vector shift) in the first second "
                    "after the fault.",
                ),
                src(
                    "OFG",
                    32,
                    OFG_DG + ", 3.31",
                    "some generators with capacities greater than 5MW were reported to have de-loaded "
                    "during the event and the cause of this is still to be determined precisely.",
                ),
            ],
        ),
        _est(
            "E22  ",
            "Ofgem 3.32 and footnote 27: in excess of 200 MW when frequency reached 49 Hz",
            "reported",
            [
                src(
                    "OFG",
                    32,
                    OFG_DG + ", 3.32",
                    "in excess of 200MW of distributed generation tripped off when system frequency "
                    "reached 49Hz",
                ),
                src(
                    "OFG",
                    32,
                    OFG_DG + ", footnote 27",
                    "It is possible that significantly more than 200MW of distributed generation "
                    "tripped off at this point as the modelling is net of demand that was "
                    "simultaneously disconnected such as the trains.",
                ),
            ],
        ),
        frame("E3C final report (January 2020)", "Source heading"),
        _est(
            "E23  ",
            "E3C final: five modes in E3C's order and wording; 1300-1500 MW in total",
            "estimated",
            [
                src(
                    "E3C",
                    12,
                    E3C_F + ", section 1",
                    "On 9 August, there were five significant modes of embedded generator loss.",
                ),
                src(
                    "E3C",
                    12,
                    E3C_F + ", section 1",
                    "which disconnected approximately 150MW",
                ),
                src(
                    "E3C",
                    12,
                    E3C_F + ", section 1",
                    "which disconnected between 350-430MW. The third loss was due to embedded "
                    "generation shutting down at a frequency of 49Hz; this was not expected and "
                    "resulted in a further net reduction of 200MW.",
                ),
                src(
                    "E3C",
                    12,
                    E3C_F + ", section 1",
                    "The ESO Technical Report identified that an unexpected increase in electricity "
                    "demand occurred in parallel with the loss of generation. This has been "
                    "attributed to the de-loading or tripping of 100MW of embedded generation but the "
                    "cause for this loss is unknown at present.",
                ),
                src(
                    "E3C",
                    12,
                    E3C_F + ", section 1",
                    "The final loss, as reported in the ESO Technical Report, of 550MW occurred when "
                    "the LFDD scheme was triggered. In total across the event, the loss of embedded "
                    "generation is estimated to be in the range of 1300MW to 1500MW.",
                ),
            ],
        ),
    ],
}

# --------------------------------------------------------------------------- S12

SOURCES_LINE_NOTE = (
    "Publication dates of the ESO (6 September 2019), Ofgem (3 January 2020) and E3C (October "
    "2019; January 2020) reports come from the source manifest, not from a quoted passage."
)


def _s12(
    start: str,
    content: str,
    status: str,
    sources: list[dict[str, Any]],
    method: str = "paraphrase",
    transformation: str | None = None,
) -> dict[str, Any]:
    return seg(start, content, status, method, sources, transformation)


APP_75_500 = src(
    "APP",
    75,
    APP_M + ", answer 7",
    "We estimate that approximately 500 MW of embedded generation was lost in the incident.",
)
APP_75_SPLIT = src(
    "APP",
    75,
    APP_M + ", answer 7",
    "to determine whether we can a split between RoCoF and Vector Shift connected generation",
)
ESO_C2_350 = src(
    "ESO",
    21,
    ESO_42EG,
    "it is estimated that approximately 350MW of embedded generation was lost due to RoCoF",
)
ESO_LFDD_LARGELY = src(
    "ESO",
    21,
    ESO_43,
    "The LFDD process worked largely as expected. While the process provided slightly lower than "
    "5% of demand",
)
ESO_T4_INERTIA = src(
    "ESO",
    23,
    ESO_T4,
    "01 July 09 August Demand 28 GW 29 GW Inertia 201 GVAs 210GVAs",
)
APP_Q42_PRIOR = src(
    "APP", 90, APP_M + ", answer 42", "16:52 Immediately prior to the trip 219632"
)

S12_SPEC: dict[str, Any] = {
    "construction": (
        "Synthesised register of published analysis records. Section A keeps each published loss "
        "total with its own components and stage (ESO Table 2's six components to 1,878 MW; ESO "
        "Appendix H's three Secured Events 1528 MW plus ~350 MW; Ofgem's >1,130, ~1,500 and at "
        "least 1,990 MW at successive stages; E3C's ~2,100 and at least 2,000 MW) without "
        "reconciling them. Section B restates ESO's Appendix I simulation and its modelled "
        "imbalance table, every row tagged [modelled] as a model input (as in R06; asterisked "
        "times kept). Section C lists, by source and under a neutral heading, the three records "
        "of a change of about 100 MW (Ofgem 2.4.9, ESO Appendix I, E3C final); whether they "
        "describe one movement and whether it is explained is left to the reader (T17). Value "
        "tags of Ofgem and E3C figures follow their own wording. Section D restates response "
        "planning assumptions and "
        "Ofgem's delivery findings; Section E the inertia figures (ESO Table 4 210 GVAs vs ESO "
        "answer 42 219,632 MVA.s) in their printed units; Section F pairs ESO's earlier answers to "
        "E3C (data available on 28 August 2019) with the final report, and the two ESO wordings "
        "about the Little Barford GT1A trip within the final report itself."
    ),
    "segments": [
        frame("DOCUMENT S12", HEADER),
        clock_seg(
            "Clock basis: times as printed; read as BST; inertia units as printed"
        ),
        frame("Value-status legend:", LEGEND),
        allow(
            seg(
                "Sources:",
                "Sources and the 28 August 2019 data date of ESO's answers",
                "reported",
                "paraphrase",
                [APP_M_DATE],
                SOURCES_LINE_NOTE,
            ),
            "6",
            "3",
            "2020",
        ),
        frame("SECTION A", "Section heading"),
        _s12(
            "A1   ",
            "ESO Table 2 cumulative infeed losses",
            "reported",
            [
                src(
                    "ESO",
                    13,
                    ESO_T2,
                    "Generation Unit Infeed Loss Cumulative Infeed Loss Little Barford ST1C 244 MW "
                    "244 MW Hornsea Offshore Windfarm 737 MW 981 MW Estimated, Embedded generation "
                    "infeed loss due to Vector Shift Loss of Mains Protection 150 MW 1,131 MW "
                    "Estimated, Embedded generation infeed loss due to RoCoF Loss of Mains "
                    "Protection 350 MW 1,481 MW Little Barford GT1A 210 MW 1,691 MW Little Barford "
                    "GT1B 187 MW 1,878 MW",
                ),
                src("ESO", 13, ESO_T2, "Table 2 – Table of cumulative infeed losses"),
            ],
            "layout",
            "Table rows restated one per line; the 'Estimated' row prefixes kept.",
        ),
        _s12(
            "A2   ",
            "ESO footnote 1: GT1B after LFDD; total 1,878 MW",
            "reported",
            [
                src(
                    "ESO",
                    10,
                    ESO_32 + ", footnote 1",
                    "The second Gas Turbine at Little Barford tripped from 187MW after the "
                    "initiation of LFDD bringing total generation lost through the event to 1,878MW. "
                    "The effect of this second GT trip was absorbed by the action of LFDD and the "
                    "additional plant dispatched by the ENCC.",
                )
            ],
        ),
        _s12(
            "A3   ",
            "ESO Appendix H: three Secured Events, 1528 MW, plus ~350 MW RoCoF",
            "reported",
            [
                src(
                    "APP",
                    56,
                    APP_H,
                    "the events of the 09 August are considered as three separate (albeit "
                    "simultaneous) Secured Events",
                ),
                src("APP", 56, APP_H, "the loss of Hornsea (737MW);"),
                src("APP", 56, APP_H, "the loss of Little Barford (641MW); and"),
                src("APP", 56, APP_H, "the loss of vector shift generation (150MW)."),
                src(
                    "APP",
                    56,
                    APP_H,
                    "The total loss seen through the three Secured Events was significantly in "
                    "excess of the level secured for (1,000MW) at 1528MW.",
                ),
                src(
                    "APP",
                    56,
                    APP_H,
                    "In addition to the 1528MW loss, there was also approximately 350MW of embedded "
                    "generation tripped off on Rate of Change of Frequency protection.",
                ),
            ],
        ),
        _s12(
            "A4   ",
            "Ofgem 2.4.5: >1,130 MW within ~1 second",
            "reported",
            [
                src(
                    "OFG",
                    17,
                    OFG_24 + ", 2.4.5",
                    "The events above resulted in a cumulative power loss of more than 1,130MW of "
                    "generation within around 1 second of the fault.",
                )
            ],
        ),
        _s12(
            "A5   ",
            "Ofgem 2.4.6-2.4.7: ~1,500 MW; 1,000 MW held",
            "estimated",
            [
                src(
                    "OFG",
                    18,
                    OFG_24 + ", 2.4.6-2.4.7",
                    "The cumulative loss of generation at this point was around 1,500MW. The ESO has "
                    "informed us that it held sufficient frequency response and reserve for a "
                    "1,000MW generation loss.",
                )
            ],
        ),
        _s12(
            "A6   ",
            "Ofgem 2.4.10-2.4.11: at least 1,990 MW",
            "reported",
            [
                src(
                    "OFG",
                    18,
                    OFG_24 + ", 2.4.10-2.4.11, footnote 20",
                    "one of the gas turbines at Little Barford (210MW) was shut down",
                ),
                src(
                    "OFG",
                    18,
                    OFG_24 + ", 2.4.10-2.4.11, footnote 20",
                    "There was a further net reduction in generation of 200MW at 49Hz",
                ),
                src(
                    "OFG",
                    18,
                    OFG_24 + ", 2.4.10-2.4.11, footnote 20",
                    "The cumulative loss of generation at this point was at least 1,990MW.",
                ),
                src(
                    "OFG",
                    18,
                    OFG_24 + ", 2.4.10-2.4.11, footnote 20",
                    "This figure is net of demand disconnection, such as trains and large industrial "
                    "customers we are aware of.",
                ),
            ],
        ),
        _s12(
            "A7   ",
            "E3C interim: ~2,100 MW",
            "estimated",
            [
                src(
                    "E3C-I",
                    5,
                    E3C_I,
                    "the total generation lost from the affected power stations, as part of the "
                    "initial event, was in the region of 2,100MW, greater than the response held.",
                )
            ],
        ),
        _s12(
            "A8   ",
            "E3C final: at least 2,000 MW",
            "reported",
            [
                src(
                    "E3C",
                    9,
                    E3C_F,
                    "the total generation lost from the affected power stations and a number of "
                    "smaller generators, as part of the initial event, was at least 2,000MW",
                )
            ],
        ),
        frame("SECTION B", "Section heading"),
        _s12(
            "B1   ",
            "Appendix I: FSE method",
            "reported",
            [
                src(
                    "APP",
                    61,
                    APP_I,
                    "As a first stage in the modelling, FSE has been used to infer the imbalance "
                    "between supply and demand that would produce the actual frequency curve of the "
                    "event.",
                ),
                src(
                    "APP",
                    61,
                    APP_I,
                    "The green trace includes the output from the frequency response services as "
                    "they reacted to the event. Removing these from this imbalance trace gives the "
                    "solid green line in the following figure. This line represents the changes in "
                    "underlying supply and demand over time that are required to obtain the "
                    "out-turn frequency trace.",
                ),
            ],
        ),
        _s12(
            "B2   ",
            "Appendix I: not all movements explicable",
            "reported",
            [
                src(
                    "APP",
                    61,
                    APP_I,
                    "An event such as this is complex with many different things happening and so it "
                    "is unlikely that we can explain all of the movements in the imbalance.",
                )
            ],
            "transcription",
        ),
        _s12(
            "B3   ",
            "Appendix I Table 1: modelled imbalance time series (every row a model input)",
            "modelled",
            [
                src(
                    "APP",
                    62,
                    APP_I + ", Table 1",
                    "Event Time Imbalance Change (MW) Hornsea One 16:52:33.728 -737 Little Barford "
                    "ST1C 16:52:34 -244 Loss of Mains – Vector Shift 16:52:34 -150 Loss of Mains - "
                    "RoCoF 16:52:34 -430 Reduction in generator output over 30 seconds 16:53:10 -100 "
                    "Little Barford GT1A 16:53:30 -210 Net Change due to protection at 49.0 Hz "
                    "16:53:40* -200 Net demand change at 48.8 Hz 16:53:48* +350 Little Barford GT1B "
                    "16:53:58 -187 Table 1 – Modelled Imbalance Time Series",
                ),
                src(
                    "APP",
                    62,
                    APP_I,
                    "This gives the following inputs for a time series of imbalance",
                ),
            ],
            "layout",
            "Table rows restated one per line with units. The source titles the table 'Modelled "
            "Imbalance Time Series' and introduces it as the inputs of the simulation, so every "
            "row is tagged [modelled] (the same rule as R06 A5); the asterisks are kept and noted "
            "as undefined in the source.",
        ),
        _s12(
            "B4   ",
            "Appendix I: 100 MW fleet variation over 30 s",
            "modelled",
            [
                src(
                    "APP",
                    62,
                    APP_I,
                    "A 100 MW variation in underlying imbalance which can be attributed to a slight "
                    "reduction in generation output across the fleet lasting for 30 seconds is also "
                    "modelled during the return of the frequency.",
                )
            ],
        ),
        _s12(
            "B5   ",
            "ESO 4.4: simulation maps closely; inputs end 16:54",
            "reported",
            [
                src(
                    "ESO",
                    22,
                    ESO_44,
                    "Our simulation maps closely to the actual frequency trace",
                ),
                src(
                    "ESO",
                    22,
                    ESO_44,
                    "Note: Modelling inputs complete at 16:54 hence the deviation of the trace from "
                    "this point onwards.",
                ),
                src(
                    "APP",
                    63,
                    APP_I,
                    "The black line is the smoothed frequency from the event.",
                ),
            ],
        ),
        _s12(
            "B6   ",
            "ESO 4.4: two 1,000 MW simulations stay above 49.5 Hz",
            "modelled",
            [
                src(
                    "ESO",
                    23,
                    ESO_44,
                    "Two simulations have been carried out for a loss of 1,000MW using the same "
                    "inertia and demand as for the simulation of the incident.",
                ),
                src(
                    "ESO",
                    23,
                    ESO_44,
                    "using the fully available contracted volume for that period of the day",
                ),
                src(
                    "ESO",
                    23,
                    ESO_44,
                    "using the actual delivery of the contracted volume of frequency response on 09 "
                    "August",
                ),
                src(
                    "ESO",
                    23,
                    ESO_44,
                    "In both cases the frequency does not go below 49.5Hz",
                ),
            ],
        ),
        frame("SECTION C", "Section heading"),
        _s12(
            "C1   ",
            "Ofgem 2.4.9: equivalent to 100 MW over 30 s, source not identified",
            "reported",
            [
                src(
                    "OFG",
                    18,
                    OFG_24 + ", 2.4.9",
                    "There was a reduction in frequency equivalent to a 100MW reduction in "
                    "generation or increase in demand over 30 seconds. The ESO has stated that "
                    "during this time there were a number of movements in both demand and generation "
                    "but it is unable to precisely point to the source of change.",
                )
            ],
        ),
        _s12(
            "C2   ",
            "Appendix I attribution (cross-reference to B4)",
            "modelled",
            [
                src(
                    "APP",
                    62,
                    APP_I,
                    "slight reduction in generation output across the fleet",
                )
            ],
        ),
        _s12(
            "C3   ",
            "E3C final: attributed to 100 MW embedded generation, cause unknown",
            "reported",
            [
                src(
                    "E3C",
                    12,
                    E3C_F + ", section 1",
                    "The ESO Technical Report identified that an unexpected increase in electricity "
                    "demand occurred in parallel with the loss of generation. This has been "
                    "attributed to the de-loading or tripping of 100MW of embedded generation but the "
                    "cause for this loss is unknown at present.",
                )
            ],
        ),
        frame("SECTION D", "Section heading"),
        _s12(
            "D1   ",
            "Appendix H: FSE pessimistic assumptions",
            "reported",
            [
                src("APP", 57, APP_H, "The model adopts a pessimistic approach"),
                src(
                    "APP",
                    57,
                    APP_H,
                    "The starting frequency is set as 49.9Hz for low frequency response calculation, "
                    "while in real time it would be generally kept higher.",
                ),
                src(
                    "APP",
                    57,
                    APP_H,
                    "The response service is modelled in a way based on their minimum performance "
                    "requirement.",
                ),
            ],
        ),
        _s12(
            "D2   ",
            "ESO answer 18: 90% delivery assumed",
            "reported",
            [
                src(
                    "APP",
                    82,
                    APP_M + ", answer 18",
                    "Note, when calculating the volume of frequency response required to secure the "
                    "largest loss, a 90% delivery rate is assumed.",
                )
            ],
        ),
        _s12(
            "D3   ",
            "ESO answer 17 note: demand frequency effect ~350 MW at 49.5 Hz",
            "estimated",
            [
                src(
                    "APP",
                    82,
                    APP_M + ", answer 17",
                    "Demand varies due to frequency, as some devices such as synchronous motors use "
                    "slightly less power when frequency is slightly low",
                ),
                src(
                    "APP",
                    82,
                    APP_M + ", answer 17",
                    "For 29 GW demand, this effect is approximately 350MW at 49.5 Hz. This effect is "
                    "unrelated to LFDD.",
                ),
            ],
        ),
        _s12(
            "D4   ",
            "ESO 4.4: conservative assumptions; performance broadly in line",
            "reported",
            [
                src(
                    "ESO",
                    24,
                    ESO_44,
                    "In the operation of the system and provisioning of response conservative "
                    "modelling assumptions are employed to ensure there is contingency if not all "
                    "contracted response delivers. The overall response performance on 09 August was "
                    "broadly in line with these planning assumptions.",
                ),
                src(
                    "ESO",
                    24,
                    ESO_44,
                    "Nevertheless, there was some under-performance and this is being followed-up "
                    "with the specific providers.",
                ),
            ],
        ),
        _s12(
            "D5   ",
            "ESO answer 27: extra 100 MW held, since removed",
            "reported",
            [
                src(
                    "APP",
                    85,
                    APP_M + ", answer 27",
                    "In the days immediately after the event we took the prudent, defensive measure "
                    "of holding 100 MW more frequency response whilst we analysed the incident.",
                ),
                src(
                    "APP",
                    85,
                    APP_M + ", answer 27",
                    "have now removed this extra holding",
                ),
            ],
        ),
        _s12(
            "D6   ",
            "Ofgem 3.6: narrow margin; sensitivity; DG processes not robust",
            "reported",
            [
                src(
                    "OFG",
                    25,
                    OFG_ESO + ", 3.6",
                    "suggests that there was only a narrow margin for error in securing the system "
                    "against transmission-connected generator losses alone. There was also a high "
                    "level of sensitivity to small changes in key assumptions.",
                ),
                src(
                    "OFG",
                    25,
                    OFG_ESO + ", 3.6",
                    "The ESO’s internal processes for estimating the impact of distributed "
                    "generation on requirements, in",
                ),
                src(
                    "OFG",
                    26,
                    OFG_ESO + ", 3.6",
                    "particular, do not appear sufficiently robust",
                ),
            ],
        ),
        _s12(
            "D7   ",
            "Ofgem 3.9: under-delivery 17%/14%; ~25%",
            "reported",
            [
                src(
                    "OFG",
                    26,
                    OFG_ESO + ", 3.9",
                    "Primary response providers (required to deliver a response within 10s) "
                    "under-delivered by 17% and secondary response providers (required to deliver a "
                    "response within 30s) under-delivered by 14%.",
                ),
                src(
                    "OFG",
                    26,
                    OFG_ESO + ", 3.9",
                    "Mandatory response providers, and commercial Fast Frequency Response providers "
                    "of dynamic primary response",
                ),
                src(
                    "OFG",
                    26,
                    OFG_ESO + ", 3.9",
                    "performed particularly poorly, under-delivering by approximately 25% "
                    "respectively.",
                ),
            ],
        ),
        _s12(
            "D8   ",
            "Ofgem 3.12: better delivery not sufficient to prevent disconnection",
            "reported",
            [
                src(
                    "OFG",
                    27,
                    OFG_ESO + ", 3.12",
                    "We do not believe that better response and reserve delivery would have been "
                    "sufficient to prevent demand from being disconnected for this event.",
                )
            ],
        ),
        frame("SECTION E", "Section heading"),
        _s12(
            "E1   ",
            "ESO Table 4: inertia 201 vs 210 GVAs",
            "reported",
            [
                ESO_T4_INERTIA,
                src(
                    "ESO",
                    23,
                    ESO_T4,
                    "Table 4 – Comparison of system conditions between 1st July",
                ),
            ],
        ),
        _s12(
            "E2   ",
            "ESO answer 42: inertia estimated by model; table",
            "estimated",
            [
                src(
                    "APP",
                    90,
                    APP_M + ", answer 42",
                    "The ESO does not currently measure system inertia directly but instead "
                    "estimates it using a model. The inertia estimate is derived from the forecasted "
                    "demand level, embedded solar and wind",
                ),
                src(
                    "APP",
                    90,
                    APP_M + ", answer 42",
                    "Timestamp (hr:min:sec) System Condition Inertia (MVA.s) 11:00 6 hours before "
                    "the incident 201353 16:52 Immediately prior to the trip 219632 16:52:34 LBAR ST1 "
                    "trip and 500MW embedded generation loss 216885 16:52:58 LFGT service kicked in "
                    "218013 16:53:31 LBAR GT1A trip 216177 16:53:49 LFDD operated, 931MW drop "
                    "reported from DNOs 214222 16:53:58 LBAR GT1B trip 212386 16:57 Frequency "
                    "restored with additional units on 215356",
                ),
            ],
            "layout",
            "Table rows restated one per line; times tagged [reported] (as printed), inertia "
            "values tagged [estimated] because ESO states they come from a model estimate.",
        ),
        _s12(
            "E3   ",
            "Appendix H: 1 MW more infeed needs ~20 MW synchronous generation",
            "reported",
            [
                src(
                    "APP",
                    59,
                    APP_H,
                    "To increase the inertia of the system to allow 1MW more of infeed loss "
                    "generally requires adding 20 MW of synchronous generation to the system.",
                )
            ],
        ),
        _s12(
            "E4   ",
            "Ofgem 3.8: demand-inertia model from 8 events in 2016/17",
            "reported",
            [
                src(
                    "OFG",
                    26,
                    OFG_ESO + ", 3.8",
                    "the ESO used 8 sample events in 2016/17 (when demand and system inertia was "
                    "higher) to build a model which it validates against actual system events.",
                )
            ],
        ),
        frame("SECTION F", "Section heading"),
        _s12(
            "F1   ",
            "Embedded generation: earlier ~500 MW vs final 150 + 350 MW",
            "estimated",
            [APP_75_500, APP_75_SPLIT, ESO_V2, ESO_C2_350],
        ),
        _s12(
            "F2   ",
            "Loss of mains volume vs expectation: earlier and final wording",
            "reported",
            [
                src(
                    "APP",
                    72,
                    APP_M + ", answers 2 and 3",
                    "the loss was in line with our forecasts for such an event",
                ),
                src(
                    "ESO",
                    33,
                    ESO_7,
                    "were broadly in line with what was expected",
                ),
            ],
            "transcription",
        ),
        _s12(
            "F3   ",
            "LFDD: earlier 'worked as intended' vs final 'largely as expected'",
            "reported",
            [
                src(
                    "APP",
                    86,
                    APP_M + ", answer 31",
                    "Initial analysis for the Interim Report suggests that the LFDD worked as "
                    "intended.",
                ),
                ESO_LFDD_LARGELY,
            ],
            "transcription",
        ),
        _s12(
            "F4   ",
            "Restoration durations: earlier c. 15 / c. 30 minutes vs final 40 minutes",
            "reported",
            [
                src(
                    "APP",
                    72,
                    APP_M + ", answers 2 and 3",
                    "The system was returned to a stable position in c. 15 minutes and the "
                    "Distribution Network Operators then quickly restored supplies in c. 30 minutes "
                    "once the system was returned to a stable position.",
                ),
                src(
                    "ESO",
                    10,
                    ESO_32,
                    "The Distribution Network Operators quickly restored supplies within 40 minutes "
                    "once the system was in a stable and secure position.",
                ),
            ],
        ),
        _s12(
            "F5   ",
            "Secondary holding: answer 16 1338 MW vs Table 3 1314 MW",
            "reported",
            [
                src(
                    "APP",
                    81,
                    APP_M + ", answer 16",
                    "Time 15:52 16:52 17:00",
                ),
                src(
                    "APP",
                    81,
                    APP_M + ", answer 16",
                    "Total 1076[1494] 1022 [1338] 1281[1761]",
                ),
                src("ESO", 21, ESO_T3, "Total 1022 1314"),
            ],
        ),
        _s12(
            "F6   ",
            "Inertia before the event: 219632 MVA.s vs 210 GVAs",
            "reported",
            [APP_Q42_PRIOR, ESO_T4_INERTIA],
        ),
        _s12(
            "F7   ",
            "ESO report: executive summary vs section 4.2 wording on GT1A",
            "reported",
            [
                src(
                    "ESO",
                    4,
                    "Executive Summary",
                    "there was a further trip of a Gas Turbine at 210MW at Little Barford Power "
                    "Station (due to high pressure in the steam bypass system following the failure "
                    "of a bypass valve to operate correctly)",
                ),
                src(
                    "ESO",
                    20,
                    ESO_42LB,
                    "RWE have confirmed that for reasons presently unknown, after approximately 1 "
                    "minute the first gas turbine tripped due to a high-pressure excursion in the "
                    "steam bypass system.",
                ),
            ],
            "transcription",
        ),
    ],
}

# --------------------------------------------------------------------------- R10


def _r10(
    start: str, content: str, sources: list[dict[str, Any]], method: str = "paraphrase"
) -> dict[str, Any]:
    return seg(start, content, "reported", method, sources)


R10_SPEC: dict[str, Any] = {
    "construction": (
        "Reconstruction of requirements as the published reports describe them, item by item, "
        "for the LFDD, security-standard, response-product and distributed-generation questions "
        "of the system-response task. It is not code text: the handoff states that the Grid Code, "
        "SQSS and Distribution Code editions applicable on 9 August 2019 were not archived and "
        "verified, so each item names the report it restates and keeps differences between "
        "reports (e.g. infrequent infeed loss 1,260 MW in ESO 2.2 vs 1800 MW in the ESO glossary; "
        "LFDD up to 60% in Ofgem/E3C vs 'up to 40% available' in the ESO glossary). The 5% stage-1 "
        "requirement is given with its winter-peak / average-cold-spell basis exactly as Ofgem and "
        "the E3C state it."
    ),
    "segments": [
        frame("DOCUMENT R10", HEADER + " and the unverified-editions caveat"),
        frame("Clock reference:", "Clock statement (no times recorded)"),
        frame("Value-status legend:", LEGEND),
        allow(
            seg(
                "Sources:",
                "Sources and abbreviations; ESO answers' data date",
                "reported",
                "paraphrase",
                [APP_M_DATE],
                SOURCES_LINE_NOTE,
            ),
            "6",
            "3",
            "2020",
        ),
        frame("SECTION A", "Section heading"),
        _r10(
            "A1   ",
            "ESO 2.2: SQSS secured events and frequency limits",
            [
                src(
                    "ESO",
                    7,
                    ESO_22,
                    "It specifies the limits of frequency deviations for secured events, which "
                    "include loss of output from a single generating unit, Combined Cycle Gas "
                    "Turbine Module (CCGT), boiler, nuclear reactor or DC bi-pole lost as a result "
                    "of an event.",
                ),
                src(
                    "ESO",
                    7,
                    ESO_22,
                    "Normal Infeed Loss Risk: Maximum frequency deviation should not exceed 0.5Hz",
                ),
                src(
                    "ESO",
                    7,
                    ESO_22,
                    "Infrequent Infeed Loss Risk Frequency should not deviate outside the range "
                    "49.5Hz to 50.5Hz for more than 60 seconds.",
                ),
            ],
        ),
        _r10(
            "A2   ",
            "ESO 2.2: normal loss c. 1,000; infrequent 1,260 MW",
            [
                src(
                    "ESO",
                    7,
                    ESO_22,
                    "The level of the normal infeed loss actually covered depends on the "
                    "configuration of the system at the time (typically it is c. 1,000W). The "
                    "current normal infrequent infeed maximum loss risk is 1,260MW for when Sizewell "
                    "nuclear station is operating at full load.",
                )
            ],
        ),
        _r10(
            "A3   ",
            "Appendix H: normal and infrequent infeed loss definitions",
            [
                src(
                    "APP",
                    56,
                    APP_H,
                    "the maxiumim loss the system should be able to manage without the frequency "
                    "going below 49.5 Hz (e.g., an interconnector at 1,000MW)",
                ),
                src(
                    "APP",
                    56,
                    APP_H,
                    "is a higher level of infeed loss dictated by a small number of larger potential "
                    "losses (e.g., Sizewell at 1,260MW) and for the loss of which the frequency "
                    "should not go below 49.2 Hz and should recover to 49.5 Hz within one minute.",
                ),
            ],
        ),
        _r10(
            "A4   ",
            "Appendix H: N-1, single Secured Event; power infeed loss",
            [
                src(
                    "APP",
                    56,
                    APP_H,
                    "The SQSS anticipates that only one Secured Event would happen at any one time and "
                    "does not assume multiple Secured Events occurring simultaneously. In engineering "
                    "terms this is defined as N-1",
                ),
                src(
                    "APP",
                    56,
                    APP_H,
                    "The Power Infeed Loss is the amount of power infeed that can be lost in one "
                    "Secured Event.",
                ),
                src(
                    "APP",
                    56,
                    APP_H,
                    "Generally this is either a single large generator, with a single mode of "
                    "failure such as a single connection to the transmission system or could be two "
                    "or more smaller generators that are separate but are connected to the rest of "
                    "the system through an asset treated as a single Secured Event (for example a "
                    "double circuit overhead line or busbar).",
                ),
            ],
        ),
        _r10(
            "A5   ",
            "Appendix H: re-securing",
            [
                src(
                    "APP",
                    57,
                    APP_H,
                    "The SQSS also sets out that the system should be re-secured as soon as "
                    "reasonably practicable after the occurrence of a Secured Event.",
                )
            ],
        ),
        _r10(
            "A6   ",
            "ESO glossary: infrequent infeed loss upper limit 1800 MW",
            [
                src(
                    "ESO",
                    37,
                    ESO_GL,
                    "The current maximum upper limit for an infrequent infeed loss risk is 1800MW.",
                )
            ],
            "transcription",
        ),
        _r10(
            "A7   ",
            "Ofgem Box 4: 49.5 Hz or recovery within 60 s",
            [
                src(
                    "OFG",
                    23,
                    OFG_B4,
                    "Specifically, the SQSS requires frequency to stay above or equal to 49.5Hz or "
                    "that any fall below that level should be recovered within 60 seconds for such "
                    "events. The ESO is required to secure the system by holding reserves so that "
                    "the frequency limits are not breached for these events.",
                )
            ],
        ),
        _r10(
            "A8   ",
            "E3C final footnote 14",
            [
                src(
                    "E3C",
                    16,
                    "E3C final, footnote 14",
                    "The SQSS allows for a deviation below 49.5Hz provided that the frequency is "
                    "returned to 49.5Hz within 60 seconds.",
                )
            ],
        ),
        _r10(
            "A9   ",
            "Ofgem 3.2 and 3.5: ESO position on DG losses under the SQSS",
            [
                src(
                    "OFG",
                    24,
                    "Ofgem 3.2 and 3.5",
                    "The ESO does not consider it is required to secure against distributed "
                    "generation losses under the SQSS.",
                ),
                src(
                    "OFG",
                    25,
                    "Ofgem 3.2 and 3.5",
                    "The ESO follows an internal policy of only securing against both transmission-",
                ),
                src(
                    "OFG",
                    25,
                    "Ofgem 3.2 and 3.5",
                    "connected generation losses and distributed generation losses from vector shift "
                    "protection mechanisms for credible transmission network faults during periods of "
                    "increased risk to the transmission system (e.g. bad weather, lightning) or when "
                    "it considers it economic to do so.",
                ),
            ],
        ),
        frame("SECTION B", "Section heading"),
        _r10(
            "B1   ",
            "Appendix H: RoCoF 0.125 Hz/s in largest-loss securing",
            [
                src(
                    "APP",
                    57,
                    APP_H,
                    "In securing for the largest loss, the ESO also takes into account the known "
                    "protection setting historically specified in the Distribution Code for RoCoF of "
                    "0.125 Hz/s.",
                ),
                src(
                    "APP",
                    57,
                    APP_H,
                    "seeks to ensure that the system is configured in real-time such that the limit "
                    "of 0.125Hz/s is not breached for an infeed loss.",
                ),
            ],
        ),
        _r10(
            "B2   ",
            "ESO answer 11: RoCoF limit and containment limits",
            [
                src(
                    "APP",
                    78,
                    APP_M + ", answer 11",
                    "We also secure the system to within a ROCOF limit of 0.125 Hz/s for the largest "
                    "credible loss.",
                ),
                src(
                    "APP",
                    78,
                    APP_M + ", answer 11",
                    "We then schedule sufficient frequency response to ensure the largest loss is "
                    "contained to frequency limits (49.5Hz for a normal loss, 49.2 Hz for an "
                    "abnormal loss)",
                ),
            ],
        ),
        _r10(
            "B3   ",
            "Appendix H: ~2 GW on RoCoF relays",
            [
                src(
                    "APP",
                    58,
                    APP_H,
                    "Approximately 2 GW of small generators are connected to the distribution "
                    "networks via relays which disconnect the generators if the RoCoF is greater "
                    "than 0.125Hz/s.",
                )
            ],
        ),
        _r10(
            "B4   ",
            "Appendix H: ~8.5 GW on vector shift relays",
            [
                src(
                    "APP",
                    59,
                    APP_H,
                    "Approximately 8.5 GW of small generators are connected to the distribution "
                    "networks via relays which disconnect the generators if the Vector Shift angle is "
                    "greater than 6 degrees.",
                )
            ],
        ),
        _r10(
            "B5   ",
            "Appendix H: vector shift Type A and Type B",
            [
                src(
                    "APP",
                    59,
                    APP_H,
                    "transmission faults with no coincident loss of BMU infeed (e.g. an overhead "
                    "line)",
                ),
                src(
                    "APP",
                    59,
                    APP_H,
                    "transmission faults with coincident loss of BMU infeed (e.g. a generator "
                    "busbar)",
                ),
                src(
                    "APP",
                    59,
                    APP_H,
                    "The ESO actively monitors, models and forecasts the largest Type A Vector Shift "
                    "risk (e.g., associated with a fault on a transmission circuit) for each "
                    "half-hourly settlement period",
                ),
                src(
                    "APP",
                    59,
                    APP_H,
                    "Type B faults are only secured based on it being economic to do so.",
                ),
            ],
        ),
        frame("SECTION C", "Section heading"),
        _r10(
            "C1   ",
            "Appendix H: primary response timing",
            [
                src(
                    "APP",
                    58,
                    APP_H,
                    "It must be delivering it’s required output by 10 seconds following the trip "
                    "and must continue to deliver for a further 20 seconds (30 seconds total)",
                )
            ],
        ),
        _r10(
            "C2   ",
            "Appendix H: secondary response timing",
            [
                src(
                    "APP",
                    58,
                    APP_H,
                    "It must be delivering it’s required output by 30 seconds following the change "
                    "in frequency and must continue to deliver for a further 30 minutes.",
                )
            ],
        ),
        _r10(
            "C3   ",
            "Appendix H: dynamic and static",
            [
                src(
                    "APP",
                    58,
                    APP_H,
                    "Dynamic - Is a continuously provided service to manage the normal fluctuations "
                    "in the frequency.",
                ),
                src(
                    "APP",
                    58,
                    APP_H,
                    "Static - Is a service to provide frequency response when the system frequency "
                    "transgresses the low frequency relay setting on site.",
                ),
                src(
                    "APP",
                    58,
                    APP_H,
                    "These two types of service can be provided from generation and demand, BM and "
                    "Non-BM units.",
                ),
            ],
        ),
        _r10(
            "C4   ",
            "Appendix H: mandatory and commercial response",
            [
                src(
                    "APP",
                    57,
                    APP_H,
                    "Mandatory Frequency Response (MFR): This can only be provided by synchronised BM "
                    "units. The requirement for MFR is an obligation of the Grid Code.",
                ),
                src(
                    "APP",
                    57,
                    APP_H,
                    "Commercial response contracts: This is the service procured from generation or "
                    "demand, BM or Non-BM units. The providers are required to deliver the "
                    "contracted amount of response.",
                ),
            ],
        ),
        _r10(
            "C5   ",
            "ESO answer 13: FFR, MFR, EFR, static",
            [
                src(
                    "APP",
                    79,
                    APP_M + ", answer 13",
                    "Firm Frequency Response (FFR): this is tendered for on a monthly basis",
                ),
                src(
                    "APP",
                    79,
                    APP_M + ", answer 13",
                    "Mandatory Frequency Response: this has similar characteristics as FFR but is "
                    "provided as an obligation laid out in a generator’s connection agreement",
                ),
                src(
                    "APP",
                    79,
                    APP_M + ", answer 13",
                    "Enhanced Frequency Response (EFR): this is a faster form of FFR",
                ),
                src(
                    "APP",
                    79,
                    APP_M + ", answer 13",
                    "This reduces demand or increases generation when the frequency hits a trigger "
                    "limit",
                ),
            ],
        ),
        _r10(
            "C6   ",
            "ESO answer 13: reserve services",
            [
                src(
                    "APP",
                    79,
                    APP_M + ", answer 13",
                    "Short Term Operating Reserve: this service typically delivers energy within 20 "
                    "minutes or less",
                ),
                src(
                    "APP",
                    79,
                    APP_M + ", answer 13",
                    "Rapid Start: this provides access to energy in less than 2 minutes",
                ),
                src("APP", 79, APP_M + ", answer 13", "Balancing Mechanism Actions"),
            ],
        ),
        _r10(
            "C7   ",
            "Appendix H: minimum dynamic response 550 MW",
            [
                src(
                    "APP",
                    58,
                    APP_H,
                    "To ensure the quality of steady state frequency control, a minimum amount of "
                    "dynamic response must be held.",
                ),
                src(
                    "APP",
                    58,
                    APP_H,
                    "The minimum dynamic response requirement at the time of the incident was set to "
                    "550MW.",
                ),
            ],
        ),
        frame("SECTION D", "Section heading"),
        _r10(
            "D1   ",
            "ESO 4.3: disconnection below 48.8 Hz in blocks",
            [
                src(
                    "ESO",
                    21,
                    ESO_43,
                    "The Grid Code, requires each DNO to make arrangements that will enable automatic "
                    "disconnection of demand if the frequency on the transmission system drops below "
                    "48.8Hz. The amount of demand that is disconnected is in staged “Blocks” (5%, "
                    "7.5% and 10%)",
                )
            ],
        ),
        _r10(
            "D2   ",
            "E3C final Table 1: LFDD stages by area",
            [
                src(
                    "E3C",
                    24,
                    "E3C final, Table 1",
                    "Table 1: Low Frequency Demand Disconnection settings for each frequency "
                    "disconnection stages",
                ),
                src(
                    "E3C",
                    24,
                    "E3C final, Table 1",
                    "England & Wales (NGET) % of Demand disconnection in Southern Scotland (SPT) % "
                    "of Demand disconnection in Northern Scotland (SHET)",
                ),
                src(
                    "E3C",
                    24,
                    "E3C final, Table 1",
                    "Stage 1 48.80 5 Stage 2 48.75 5 Stage 3 48.70 10 Stage 4 48.60 7.5 10 Stage 5 "
                    "48.50 7.5 10 Stage 6 48.40 7.5 10 10 Stage 7 48.20 7.5 10 10 Stage 8 48.00 5 10 "
                    "10 Stage 9 47.80 5 Total % Demand N/A 60 40 40",
                ),
                cat_src(
                    "CAT-E3CT1",
                    "Stage 4",
                    "pct_demand_northern_scotland_SHET",
                    "10",
                    "E3C final, Table 1 (column placement read from the page image)",
                ),
                cat_src(
                    "CAT-E3CT1",
                    "Stage 5",
                    "pct_demand_southern_scotland_SPT",
                    "10",
                    "E3C final, Table 1 (column placement read from the page image)",
                ),
            ],
            "layout",
        ),
        _r10(
            "D3   ",
            "Ofgem 3.38: OC6, max 60% at winter demand, tolerance and delay",
            [
                src(
                    "OFG",
                    34,
                    OFG_DNO + ", 3.38",
                    "The Grid Code (Operating Code 6) requires each DNO in England and Wales to have "
                    "LFDD equipment in place to disconnect a maximum of 60% of demand (measured at "
                    "winter demand). This equipment should operate in stages to disconnect a given "
                    "percentage of supply once certain frequencies are reached. The Grid Code "
                    "requirements contain an accuracy tolerance for the frequency levels and a time "
                    "delay permitted for different LFDD equipment, depending on its installation "
                    "date.",
                )
            ],
        ),
        _r10(
            "D4   ",
            "Ofgem 3.39: 5% of winter peak demand at stage 1",
            [
                src(
                    "OFG",
                    34,
                    OFG_DNO + ", 3.39",
                    "triggered Stage 1 of the LFDD. This required 5% of winter peak demand to be "
                    "disconnected.",
                )
            ],
        ),
        _r10(
            "D5   ",
            "E3C final: 5% basis",
            [
                src(
                    "E3C",
                    16,
                    E3C_F + ", section 3",
                    "The 5% demand figure is based on forecasted peak demand during an average cold "
                    "spell.",
                )
            ],
            "transcription",
        ),
        _r10(
            "D6   ",
            "E3C interim: 5-60% through 9 stages",
            [
                src(
                    "E3C-I",
                    10,
                    E3C_I,
                    "This scheme is designed to disconnect between 5 - 60% of total peak demand "
                    "through 9 stages as the system frequency reaches certain trigger levels.",
                )
            ],
        ),
        _r10(
            "D7   ",
            "ESO glossary: 5% stages, up to 40% available",
            [
                src(
                    "ESO",
                    37,
                    ESO_GL,
                    "It is set up in agreement with the ESO by DNOs to reduce their demand in 5% "
                    "stages of total demand (up to 40% available)",
                )
            ],
        ),
        _r10(
            "D8   ",
            "Ofgem 3.44: SP Distribution threshold 48.5 Hz",
            [
                src(
                    "OFG",
                    36,
                    OFG_DNO + ", 3.44",
                    "As SP Distribution is part of the SP Transmission network area, it is not "
                    "required by the Grid Code to disconnect demand until frequency reaches 48.5Hz.",
                )
            ],
        ),
        _r10(
            "D9   ",
            "ESO 2.5 on its own: OC6.6 LFDD arrangements; notify ESO; restore only on instruction",
            [
                src(
                    "ESO",
                    8,
                    ESO_25,
                    "Grid Code OC6.6 describes the automatic LFDD scheme and the arrangements that "
                    "the DNO’s are required to make in relation to this scheme.",
                ),
                src(
                    "ESO",
                    8,
                    ESO_25,
                    "Following operation of this scheme, the DNO’s must notify ESO of its operation "
                    "and are not permitted to restore automatically disconnected demand without "
                    "instruction from National Grid ESO.",
                ),
            ],
        ),
        _r10(
            "D10  ",
            "Ofgem 3.40: DG disconnection through LFDD not regulated",
            [
                src(
                    "OFG",
                    34,
                    OFG_DNO + ", 3.40",
                    "The Grid Code does not currently regulate the disconnection",
                ),
                src(
                    "OFG",
                    35,
                    OFG_DNO + ", 3.40",
                    "of distributed generation through LFDD",
                ),
            ],
        ),
        frame("SECTION E", "Section heading"),
        _r10(
            "E1   ",
            "E3C final: loss of mains protection requirement",
            [
                src(
                    "E3C",
                    10,
                    E3C_F + ", section 1",
                    "Under the Distribution Code, embedded generators are required to install "
                    "protection systems which detect when the generator is islanded",
                ),
                src(
                    "E3C",
                    10,
                    E3C_F + ", section 1",
                    "This is predominantly achieved by either monitoring the rate of change of "
                    "frequency across the electricity system, or the change in voltage phase angle "
                    "(also known as vector shift).",
                ),
            ],
        ),
        _r10(
            "E2   ",
            "E3C final: 2014 requirements, 2018 implementation, ALoMCP 2019",
            [
                src(
                    "E3C",
                    10,
                    E3C_F + ", section 1",
                    "New requirements for embedded generators under the Distribution Code were "
                    "introduced in 2014 which required all generators with a capacity greater than "
                    "5MW, to install rate of change of frequency protection systems with specific "
                    "settings",
                ),
                src(
                    "E3C",
                    10,
                    E3C_F + ", section 1",
                    "This was implemented across all relevant sites in 2018 and the Accelerated Loss "
                    "of Mains Protection programme was initiated in 2019 to implement similar changes "
                    "across embedded generators with a capacity between 5MW – 50kW.",
                ),
            ],
        ),
        _r10(
            "E3   ",
            "Ofgem footnote 18: vector shift not permitted after 1 February 2018",
            [
                src(
                    "OFG",
                    17,
                    OFG_24 + ", footnote 18",
                    "Vector shift protection is no longer permitted for distributed generators "
                    "connected after 1 February 2018.",
                )
            ],
        ),
        _r10(
            "E4   ",
            "Ofgem 3.32: under-frequency 47 Hz for >5 MW from August 2010",
            [
                src(
                    "OFG",
                    32,
                    OFG_DG + ", 3.32",
                    "Changes were made to the Distribution Code which reduced the frequency level "
                    "triggering under frequency protections to 47Hz permitted for distributed "
                    "generators with capacities greater than 5MW from August",
                ),
                src(
                    "OFG",
                    33,
                    OFG_DG + ", 3.32",
                    "2010. It is possible that the frequency protection settings",
                ),
            ],
        ),
    ],
}

NEW_DOC_SPECS: dict[str, dict[str, Any]] = {
    "R10": R10_SPEC,
    "S05": S05_SPEC,
    "S06": S06_SPEC,
    "S07": S07_SPEC,
    "S12": S12_SPEC,
}
