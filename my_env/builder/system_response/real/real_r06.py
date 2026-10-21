"""R06 — frequency response holding and delivery; balancing actions.

Builder-only. Reported tables transcribed from the ESO technical report (Table 3, Table 5 with
its text) and its appendices (Appendix M questions 16 and 17; Appendix I Table 1, the modelled
imbalance time series). Real Elexon extracts: bid-offer acceptances (BOALF) with acceptance
times 15:40-16:45 UTC, balancing services volumes (QAS) and system prices / net imbalance
volume (DISEBSP). Each BOALF acceptance also becomes an ESO-ENCC control-log row.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from real_common import (
    EVENT_DATE,
    TextDoc,
    csv_bytes,
    data_ref,
    doc_quote_ref,
    iso_z,
    parse_utc,
    pdf_ref,
    require,
    settlement_period_bounds_utc,
    table_ref,
    tagged,
    wrap,
)
from real_docbuild import Artifact, DocBuild
from real_sources import BOALF_SPS, ELEXON_ATTRIBUTION, SOURCES

DOC_ID = "R06"
TITLE = "Frequency response holding, delivery and balancing actions, 9 August 2019"
ROOM = "ESO-ENCC"
WINDOW_UTC = (
    "2019-08-09T15:40:00Z",
    "2019-08-09T16:45:00Z",
)  # inclusive, acceptanceTime

TAB3 = "ESO-p21-tab3.csv"
TAB5 = "ESO-p25-tab5.csv"
Q16 = "APP-p81-tbl-q16-response-holding.csv"
Q17 = "APP-p82-tbl-q17-response-delivered.csv"
APPI = "APP-p62-tbl1-modelled-imbalance.csv"

F_TABLES = "R06_report_tables_response_holding_delivery.csv"
F_IMBALANCE = "R06_appendix_i_table1_modelled_imbalance.csv"
F_BOALF = "R06_elexon_boalf_acceptances_20190809_1540-1645Z.csv"
F_QAS = "R06_elexon_qas_balancing_services_volume_20190809.csv"
F_DISEBSP = "R06_elexon_disebsp_system_prices_niv_20190809.csv"

BOALF_FIELDS = [
    "acceptanceNumber",
    "acceptanceTime",
    "bmUnit",
    "nationalGridBmUnit",
    "settlementDate",
    "settlementPeriodFrom",
    "settlementPeriodTo",
    "timeFrom",
    "levelFrom",
    "timeTo",
    "levelTo",
    "soFlag",
    "storFlag",
    "deemedBoFlag",
    "rrFlag",
]
QAS_FIELDS = [
    "dataset",
    "settlementDate",
    "settlementPeriod",
    "bmUnit",
    "nationalGridBmUnit",
    "bmUnitApplicableBalancingServicesVolume",
]


def p(label: str, text: str) -> list[str]:
    return wrap(text, first=f"{label:<3}", indent="    ")


def cont(text: str) -> list[str]:
    return wrap(text, first="    ", indent="    ")


# ---------------------------------------------------------------------------------------------
# Real data
# ---------------------------------------------------------------------------------------------


def boalf_records(inputs) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Unique BOALF level records with acceptanceTime in the window (all SP32-38 queries)."""
    unique: dict[str, dict[str, Any]] = {}
    raw_count = 0
    for sp in BOALF_SPS:
        data = inputs.real_json(f"elexon_boalf_sp{sp}")["data"]
        raw_count += len(data)
        for rec in data:
            require(
                set(rec) == set(BOALF_FIELDS), f"BOALF fields changed: {sorted(rec)}"
            )
            unique.setdefault(json.dumps(rec, sort_keys=True), rec)
    recs = [
        r
        for r in unique.values()
        if WINDOW_UTC[0] <= r["acceptanceTime"] <= WINDOW_UTC[1]
    ]
    recs.sort(
        key=lambda r: (
            r["acceptanceTime"],
            r["bmUnit"],
            r["acceptanceNumber"],
            r["timeFrom"],
        )
    )
    segments = defaultdict(list)
    for rec in recs:
        segments[(rec["bmUnit"], rec["acceptanceNumber"])].append(rec)
    for key, segs in segments.items():
        require(
            len({s["acceptanceTime"] for s in segs}) == 1,
            f"acceptance time differs {key}",
        )
        times = [(s["timeFrom"], s["timeTo"]) for s in segs]
        require(len(times) == len(set(times)), f"duplicate level segment {key}")
    stats = {
        "raw_records": raw_count,
        "unique_records": len(unique),
        "window_records": len(recs),
        "acceptances": len(segments),
        "bm_units": len({r["bmUnit"] for r in recs}),
    }
    return recs, stats


def qas_rows(inputs) -> list[list[Any]]:
    data = inputs.real_json("elexon_qas")["data"]
    require(all(r["settlementDate"] == "2019-08-09" for r in data), "QAS date")
    data = sorted(data, key=lambda r: (r["settlementPeriod"], r["bmUnit"]))
    keys = [(r["settlementPeriod"], r["bmUnit"]) for r in data]
    require(len(keys) == len(set(keys)), "duplicate QAS rows")
    require(len(data) == 596, f"QAS rows {len(data)} != 596")
    return [[r[f] for f in QAS_FIELDS] for r in data]


def disebsp(inputs) -> tuple[list[str], list[list[Any]]]:
    data = inputs.real_json("elexon_disebsp")["data"]
    fields = list(data[0].keys())
    require(all(list(r.keys()) == fields for r in data), "DISEBSP fields differ")
    data = sorted(data, key=lambda r: r["settlementPeriod"])
    require(
        [r["settlementPeriod"] for r in data] == list(range(1, 49)), "DISEBSP periods"
    )
    for rec in data:
        start, _ = settlement_period_bounds_utc(EVENT_DATE, rec["settlementPeriod"])
        require(
            parse_utc(rec["startTime"]) == start,
            f"DISEBSP startTime {rec['startTime']}",
        )
    return fields, [[r[f] for f in fields] for r in data]


def control_rows(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_acc: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for rec in recs:
        by_acc[(rec["bmUnit"], rec["acceptanceNumber"])].append(rec)
    rows = []
    for (unit, number), segs in sorted(by_acc.items()):
        segs.sort(key=lambda s: (s["timeFrom"], s["timeTo"]))
        first = segs[0]
        points = "; ".join(
            f"{s['timeFrom']} {s['levelFrom']} MW to {s['timeTo']} {s['levelTo']} MW"
            for s in segs
        )
        flags = (
            f"soFlag {_flag(first['soFlag'])}, storFlag {_flag(first['storFlag'])}, deemedBoFlag "
            f"{_flag(first['deemedBoFlag'])}, rrFlag {_flag(first['rrFlag'])}"
        )
        for s in segs:
            require(
                (s["soFlag"], s["storFlag"], s["deemedBoFlag"], s["rrFlag"])
                == (
                    first["soFlag"],
                    first["storFlag"],
                    first["deemedBoFlag"],
                    first["rrFlag"],
                ),
                f"flags differ within acceptance {unit} {number}",
            )
        periods = sorted(
            {s["settlementPeriodFrom"] for s in segs}
            | {s["settlementPeriodTo"] for s in segs}
        )
        when = parse_utc(first["acceptanceTime"])
        rows.append(
            {
                "kind": "control",
                "entry_id": f"R06-BOALF-{unit}-{number}",
                "evidence_id": DOC_ID,
                "room_id": ROOM,
                "recorded_time": f"acceptanceTime {first['acceptanceTime']}",
                "clock_basis": "UTC (Elexon BOALF acceptanceTime with Z), minute resolution; "
                "whether the publisher rounds or truncates to the minute is not documented",
                "index_time_utc": iso_z(when),
                "index_uncertainty_s": 60,
                "from": ROOM,
                "to": f"BM unit {unit} (nationalGridBmUnit {first['nationalGridBmUnit']})",
                "channel": "Balancing Mechanism bid-offer acceptance (Elexon BOALF record)",
                "text": f"Bid-offer acceptance {number} for BM unit {unit}, settlementDate "
                f"{first['settlementDate']}, settlement periods {periods[0]}-{periods[-1]}. "
                f"Accepted levels (UTC): {points}. Flags: {flags}.",
                "value_status": "reported",
                "provenance": {
                    "source_ids": sorted(
                        k for k in SOURCES if k.startswith("elexon_boalf_sp")
                    ),
                    "dataset_id": "elexon_BOALF",
                    "selection": f"unique records with bmUnit {unit} and acceptanceNumber {number}",
                    "records": [{k: s[k] for k in BOALF_FIELDS} for s in segs],
                },
            }
        )
    return rows


def _flag(value: Any) -> str:
    if value is None:
        return "null"
    return "true" if value else "false"


# ---------------------------------------------------------------------------------------------
# Report tables
# ---------------------------------------------------------------------------------------------


def _check_rows(
    rows: list[dict[str, str]], column: str, expected: list[str], what: str
) -> None:
    require([r[column] for r in rows] == expected, f"{what} rows changed")


def build(inputs) -> DocBuild:
    doc = TextDoc(DOC_ID)
    build = DocBuild(
        doc_id=DOC_ID,
        title=TITLE,
        owner="National Grid ESO (report tables); Elexon (BMRS balancing data)",
        category="system_operator_records",
        record_type="published tables of frequency response holding, delivery and modelled "
        "imbalance (transcribed) with real Elexon balancing-data extracts (CSV files)",
        construction="",
        text=doc,
    )
    build.header(
        "National Grid ESO (technical report of 6 September 2019 and its appendices); Elexon "
        "Limited (BMRS / Insights API balancing data submitted by the system operator)",
        wrap(
            "Clock reference: report tables print times without a zone; the reports give event "
            "times in local time (BST, UTC+01:00). Elexon timestamps are UTC (ISO-8601 with Z); "
            "Elexon settlement periods are numbered on the UK local clock (period 1 starts at "
            "00:00 local time; 30-minute periods; BST on 9 August 2019)."
        ),
    )

    tab3 = inputs.catalogue_rows(TAB3)
    _check_rows(
        tab3,
        "provider_type",
        ["BM", "BM & Non-BM", "BM & Non-BM", "Non-BM", "Non-BM", "BM", ""],
        "ESO Table 3",
    )
    tab5 = inputs.catalogue_rows(TAB5)
    _check_rows(
        tab5,
        "provider_type",
        ["BM", "BM & Non-BM", "BM & Non-BM", "Non-BM", "Non-BM", "BM", ""],
        "ESO Table 5",
    )
    q16 = inputs.catalogue_rows(Q16)
    require(len(q16) == 12, "Q16 rows changed")
    q17 = inputs.catalogue_rows(Q17)
    require(len(q17) == 8, "Q17 rows changed")
    appi = inputs.catalogue_rows(APPI)
    require(
        [r["row"] for r in appi] == [str(i) for i in range(1, 10)], "App I rows changed"
    )

    doc.blank()
    doc.frame(
        "Part A heading",
        "PART A — PUBLISHED TABLES: RESPONSE HOLDING AND DELIVERY (transcribed as printed)",
    )

    # A1 ESO Table 3 ------------------------------------------------------------------------
    t3_intro = [
        "The largest secured loss on the event day was 1,000 MW.",
        "In order to keep the frequency above 49.5Hz for this level of infeed loss, the response "
        "holding was calculated and planned as below.",
    ]
    t3_cells = [
        x
        for r in tab3
        for x in (
            r["service"],
            r["provider_type"],
            r["primary_response_held_mw"],
            r["secondary_response_held_mw"],
        )
    ]
    seg = doc.segment(
        "A1 ESO Table 3 (frequency response holding) with the sentences printed before it",
        "reported",
        "transcription",
        [
            table_ref(
                inputs,
                "ESO",
                21,
                "4.4 Frequency Response, Table 3 - Frequency response holding",
                "ESO-p21-tab3",
                TAB3,
                t3_cells,
            ),
            pdf_ref(
                inputs,
                "ESO",
                21,
                "4.4 Frequency Response, Response Holding on August 9th 2019",
                " ".join(t3_intro),
            ),
            pdf_ref(
                inputs,
                "ESO",
                21,
                "Table 3 caption",
                "Table 3 - Frequency response holding",
            ),
        ],
    )
    doc.add(
        seg,
        *p(
            "A1",
            "National Grid ESO, Technical Report on the events of 9 August 2019 (published "
            '6 September 2019), section 4.4 "Response Holding on August 9th 2019". Printed '
            "before the table (quoted):",
        ),
        *(line for q in t3_intro for line in tagged(f'"{q}"', "reported")),
        '    "Table 3 - Frequency response holding" (Service | Provider type | Lower Frequency '
        "response held (MW):",
        "    Primary response | Secondary response), as printed:",
        *(
            f"    {r['service']} | {r['provider_type'] or '-'} | {r['primary_response_held_mw']} | "
            f"{r['secondary_response_held_mw']} [reported]"
            for r in tab3
        ),
    )

    # A2 ESO Table 5 and its text -------------------------------------------------------------
    t5_text = [
        "At the time of the event the amount of low frequency response being held was 1,022MW "
        "primary and 1,314MW secondary.",
        "To date, of the 1,022MW and 1,314MW of response holding, the ESO has worked with "
        "providers and used internal data to validate the performance of 91% of all primary and "
        "secondary that was being held at the time (i.e. 945MW and 1,202MW respectively).",
        "Of the validated response holding the ESO can confirm that 89% of primary (841MW) and "
        "88% of secondary (1055MW) response performed as expected and in line with its "
        "contractual obligations.",
        "Nevertheless, there was some under-performance and this is being followed-up with the "
        "specific providers.",
    ]
    t5_cells = [
        x
        for r in tab5
        for x in (
            r["service"],
            r["provider_type"],
            r["primary_cell_printed"],
            r["secondary_cell_printed"],
        )
    ]
    seg = doc.segment(
        "A2 ESO Table 5 (validated frequency response performance) with the text before it",
        "reported",
        "transcription",
        [
            table_ref(
                inputs,
                "ESO",
                25,
                "4.4 Frequency Response, Table 5 – Validated Frequency "
                "Response Performance",
                "ESO-p25-tab5",
                TAB5,
                t5_cells,
            ),
            *(
                pdf_ref(
                    inputs,
                    "ESO",
                    24,
                    "4.4 Frequency Response, Delivery of Frequency Response",
                    q,
                )
                for q in t5_text
            ),
            pdf_ref(
                inputs,
                "ESO",
                25,
                "Table 5 caption and column heading",
                "% validated low frequency response delivered at 30 seconds versus Total MW "
                "response held",
            ),
        ],
    )
    doc.add(
        seg,
        *p(
            "A2",
            'Same report, section 4.4 "Delivery of Frequency Response". Text printed before '
            "Table 5, quoted sentence by sentence:",
        ),
        *(line for q in t5_text for line in tagged(f'"{q}"', "reported")),
        *wrap(
            '"Table 5 – Validated Frequency Response Performance" (Service | Provider type | % '
            "validated low frequency response delivered at 30 seconds versus Total MW response "
            "held: Validated Primary response | Validated Secondary response), as printed:",
            first="    ",
            indent="    ",
        ),
        *(
            f"    {r['service']} | {r['provider_type'] or '-'} | {r['primary_cell_printed']} | "
            f"{r['secondary_cell_printed']} [reported]"
            for r in tab5
        ),
    )

    # A3 Appendix M Q16 -----------------------------------------------------------------------
    q16_question = (
        "What was the total capacity of all Primary and Secondary frequency response available; "
        "an hour prior to as well as during and after the time of the event; for activation by "
        "the ESO?"
    )
    q16_intro = (
        "Below is a table detailing the volumes of frequency response which was instructed by "
        "the ENCC at three time points around the event."
    )
    points = []
    for r in q16:
        key = (r["time_point_label"], r["time_as_printed"], r["largest_gen_loss_mw"])
        if key not in points:
            points.append(key)
    require(len(points) == 3, "Q16 time points")
    q16_cells = [x for pt in points for x in pt] + [
        r["secondary_as_printed"] for r in q16
    ]
    seg = doc.segment(
        "A3 Appendix M Q16 table (low-frequency response holding at 15:52, 16:52, 17:00)",
        "reported",
        "transcription",
        [
            table_ref(
                inputs,
                "APP",
                81,
                "Appendix M, question 16, table",
                "APP-p81-tbl-q16-response-holding",
                Q16,
                q16_cells,
            ),
            pdf_ref(inputs, "APP", 81, "Appendix M, question 16", q16_question),
            pdf_ref(inputs, "APP", 81, "Appendix M, answer 16", q16_intro),
            pdf_ref(
                inputs, "APP", 81, "Appendix M, answer 16", "Source of data: NED system"
            ),
        ],
        "Table layout turned into one line per time point and response type; cells as printed.",
    )
    doc.add(
        seg,
        *p(
            "A3",
            "Appendices to the ESO technical report, Appendix M (ESO answers to questions from "
            f'the Energy Emergencies Executive Committee), question 16 as printed: "{q16_question}"',
        ),
        *cont(
            f'Answer (quoted): "{q16_intro}" The table notes "Source of data: NED system".'
        ),
        "    Table as printed, one line per time point and response type (Low Frequency Holding "
        "(MW), Primary",
        "    [Secondary]):",
    )
    for label, time, loss in points:
        doc.add(seg, f"    {label} | Time {time} | Largest gen loss {loss} [reported]")
        for r in q16:
            if (r["time_point_label"], r["time_as_printed"]) == (label, time):
                kind = r["response_category"] + (
                    f" {r['response_subtype']}" if r["response_subtype"] else ""
                )
                doc.add(seg, f"      {kind}: {r['secondary_as_printed']} [reported]")

    # A4 Appendix M Q17 -----------------------------------------------------------------------
    q17_question = (
        "Was all the Primary and Secondary frequency response activated by the ESO, and when (in "
        "a timeline, prior to, during and after the event) was this done?"
    )
    q17_intro = (
        "The table below highlights the frequency response holding and the current best view "
        "of the low frequency response performance, this is subject to change."
    )
    q17_foot = [
        "*Demand varies due to frequency, as some devices such as synchronous motors use slightly "
        "less power when frequency is slightly low, and vice versa when frequency is slightly "
        "high.",
        "For 29 GW demand, this effect is approximately 350MW at 49.5 Hz.",
        "This effect is unrelated to LFDD.",
    ]
    q17_cells = [
        x
        for r in q17
        for x in (
            r["number_of_units"],
            r["holding_as_printed"],
            r["lf_delivered_within_30s_mw"],
        )
    ]
    seg = doc.segment(
        "A4 Appendix M Q17 table (holding vs delivered within 30 s) with its footnote",
        "reported",
        "transcription",
        [
            table_ref(
                inputs,
                "APP",
                82,
                "Appendix M, question 17, table",
                "APP-p82-tbl-q17-response-delivered",
                Q17,
                q17_cells,
            ),
            pdf_ref(inputs, "APP", 82, "Appendix M, question 17", q17_question),
            pdf_ref(inputs, "APP", 82, "Appendix M, answer 17", q17_intro),
            *(
                pdf_ref(inputs, "APP", 82, "Appendix M, answer 17, table footnote", q)
                for q in q17_foot
            ),
            pdf_ref(
                inputs,
                "APP",
                82,
                "Appendix M, answer 17, total row",
                "Total (Excluding demand effect*)",
            ),
        ],
        "Table layout turned into one line per row; cells as printed ('-' where printed).",
    )
    doc.add(
        seg,
        *p("A4", f'Same appendix, question 17 as printed: "{q17_question}"'),
        *cont(f'Answer (quoted): "{q17_intro}"'),
        "    Table as printed (Frequency Response Type | Number of Units | Low Frequency Holding "
        "Primary [Secondary] |",
        "    Low Frequency Delivered within 30 seconds of event):",
    )
    for r in q17:
        sub = r["trigger_or_subtype"].replace("\n", " ")
        kind = r["response_category"] + (f" {sub}" if sub else "")
        bm = f" {r['bm_nbm']}" if r["bm_nbm"] else ""
        units = r["number_of_units"] or " "
        line = (
            f"{kind}{bm} | {units.strip() or '(blank)'} | {r['holding_as_printed'] or '(blank)'} | "
            f"{r['lf_delivered_within_30s_mw'] or '(blank)'}"
        )
        doc.add(seg, *tagged(line, "reported", indent="      "))
    doc.add(
        seg,
        "    Footnote as printed:",
        *(
            line
            for q in q17_foot
            for line in wrap(f'"{q}"', first="    ", indent="    ")
        ),
    )

    # A5 Appendix I Table 1 -------------------------------------------------------------------
    appi_intro = [
        "The Frequency Simulation Engine (FSE) is used by ESO to calculate the frequency "
        "response holding required to keep frequency within limits for a given loss and set of "
        "system conditions.",
        "This gives the following inputs for a time series of imbalance",
    ]
    appi_cells = [
        x for r in appi for x in (r["time_as_printed"], r["imbalance_change_mw"])
    ]
    seg = doc.segment(
        "A5 Appendix I Table 1 (modelled imbalance time series): inputs of the ESO simulation",
        "modelled",
        "transcription",
        [
            table_ref(
                inputs,
                "APP",
                62,
                "Appendix I, Table 1 – Modelled Imbalance Time Series",
                "APP-p62-tbl1-modelled-imbalance",
                APPI,
                appi_cells,
            ),
            pdf_ref(
                inputs,
                "APP",
                61,
                "Appendix I, Simulation of Frequency Trace",
                appi_intro[0],
            ),
            pdf_ref(
                inputs, "APP", 62, "Appendix I, text before Table 1", appi_intro[1]
            ),
            pdf_ref(
                inputs,
                "APP",
                62,
                "Appendix I, Table 1 caption",
                "Table 1 – Modelled Imbalance Time Series",
            ),
        ],
        "Event names, times and MW as printed; '*' kept as printed.",
    )
    doc.add(
        seg,
        *p(
            "A5",
            "Appendices to the ESO technical report, Appendix I (simulation of the 9 August "
            "event). Quoted:",
        ),
        *(
            line
            for q in appi_intro
            for line in wrap(f'"{q}"', first="    ", indent="    ")
        ),
        '    "Table 1 – Modelled Imbalance Time Series" (Event | Time | Imbalance Change (MW)), '
        "as printed; the table",
        "    lists the imbalance inputs of the simulation [modelled]:",
        *(
            f"    {r['event']} | {r['time_as_printed']} | {r['imbalance_change_mw']} [modelled]"
            for r in appi
        ),
        '    The source marks two times with "*" and does not define the mark in the table.',
    )

    # ---- Part B: Elexon data ----------------------------------------------------------------
    recs, stats = boalf_records(inputs)
    qas = qas_rows(inputs)
    dis_fields, dis_rows = disebsp(inputs)
    doc.blank()
    doc.frame(
        "Part B heading", "PART B — BALANCING MECHANISM DATA (real extracts, Elexon)"
    )
    seg = doc.segment(
        "B1 BOALF file description: queries, deduplication, window, columns, caveats",
        "reported",
        "script",
        [
            *(
                data_ref(
                    f"elexon_boalf_sp{sp}",
                    "all records; deduplicated across the seven queries",
                )
                for sp in BOALF_SPS
            ),
            doc_quote_ref(
                inputs,
                "elexon_api_docs",
                "/balancing/acceptances/all description",
                "It returns the data valid for a single settlement period.",
            ),
        ],
        f"{stats['raw_records']} records returned by the seven queries; {stats['unique_records']} "
        f"unique; {stats['window_records']} with acceptanceTime in the window.",
    )
    doc.add(
        seg,
        *p(
            "B1",
            f"File {F_BOALF} [reported] — bid-offer acceptance level records (BOALF) with "
            "acceptance times 15:40 to 16:45 UTC inclusive.",
        ),
        *cont(
            "Source: Elexon endpoint /balancing/acceptances/all, one query per settlement period "
            "32 to 38 of 2019-08-09 (each query returns the records valid for that period); "
            "retrieved 2026-10-20. Licence: Elexon BMRS open data licence. "
            f"{ELEXON_ATTRIBUTION}",
        ),
        *cont(
            f"Selection: the {stats['raw_records']} records returned include repeats of records "
            f"spanning several periods; {stats['unique_records']} are unique, and the "
            f"{stats['window_records']} whose acceptanceTime is 2019-08-09T15:40:00Z to "
            f"16:45:00Z are kept. They belong to {stats['acceptances']} acceptances of "
            f"{stats['bm_units']} BM units. An acceptance in that window whose accepted levels "
            "lie wholly outside settlement periods 32-38 would not be in these queries.",
        ),
        *cont(
            "Columns: "
            + ", ".join(BOALF_FIELDS)
            + ". Each record is one segment of an "
            "accepted level profile: levelFrom (MW) at timeFrom to levelTo (MW) at timeTo. "
            "acceptanceTime, timeFrom and timeTo are UTC at minute resolution. soFlag, storFlag, "
            "deemedBoFlag and rrFlag are the publisher's flags (system operator, STOR, deemed "
            "bid-offer and replacement reserve flags). An acceptance is an instruction, not a "
            "measurement of what the unit delivered.",
        ),
        *cont(
            f"Each acceptance is also an entry in the control log of room {ROOM} "
            "(query_control_log); entry IDs have the form R06-BOALF-<bmUnit>-<acceptanceNumber>.",
        ),
    )
    seg = doc.segment(
        "B2 QAS file description",
        "reported",
        "script",
        [
            data_ref("elexon_qas", "all 596 records for 2019-08-09"),
            doc_quote_ref(
                inputs,
                "elexon_api_docs",
                "/datasets/QAS description",
                "represents the volume of energy (MWh) associated with the provision of "
                "Applicable Balancing Services for each relevant BM Unit and Settlement Period",
            ),
            doc_quote_ref(
                inputs,
                "elexon_api_docs",
                "/datasets/QAS description",
                "QAS can be positive or negative and is normally only provided where there is a "
                "non-zero volume.",
            ),
        ],
    )
    doc.add(
        seg,
        *p(
            "B2",
            f"File {F_QAS} [reported] — balancing services volume (QAS) per BM unit.",
        ),
        *cont(
            "Source: Elexon endpoint /datasets/QAS for settlement date 2019-08-09, periods 1-50; "
            "retrieved 2026-10-20. Licence as B1.",
        ),
        *cont(
            f"Rows: {len(qas)} (every record returned), sorted by settlementPeriod and bmUnit. "
            "Columns: "
            + ", ".join(QAS_FIELDS)
            + ". Publisher's description: the volume "
            '"represents the volume of energy (MWh) associated with the provision of Applicable '
            'Balancing Services for each relevant BM Unit and Settlement Period"; "QAS can be '
            "positive or negative and is normally only provided where there is a non-zero "
            'volume." The data do not name the balancing service.',
        ),
    )
    seg = doc.segment(
        "B3 DISEBSP file description",
        "reported",
        "script",
        [
            data_ref(
                "elexon_disebsp", "48 settlement periods of 2019-08-09, all fields"
            ),
            doc_quote_ref(
                inputs,
                "elexon_api_docs",
                "/balancing/settlement/system-prices/{settlementDate} description",
                "only messages generated for the latest settlement run are returned",
            ),
        ],
    )
    doc.add(
        seg,
        *p(
            "B3",
            f"File {F_DISEBSP} [reported] — settlement system prices and net imbalance volume "
            "(DISEBSP).",
        ),
        *cont(
            "Source: Elexon endpoint /balancing/settlement/system-prices/2019-08-09; retrieved "
            '2026-10-20. Licence as B1. Publisher: "only messages generated for the latest '
            'settlement run are returned".',
        ),
        *cont(
            f"Rows: {len(dis_rows)} (settlement periods 1-48). Columns, in the publisher's order: "
            + ", ".join(dis_fields)
            + ". startTime and createdDateTime are UTC; prices GBP/MWh; "
            "volumes MWh.",
        ),
    )
    col = {name: dis_fields.index(name) for name in dis_fields}
    sel = (
        "settlementPeriod",
        "startTime",
        "netImbalanceVolume",
        "systemSellPrice",
        "systemBuyPrice",
        "totalAcceptedOfferVolume",
        "totalAcceptedBidVolume",
    )
    seg = doc.segment(
        "B4 DISEBSP selected columns, settlement periods 30-40 (values verbatim)",
        "reported",
        "script",
        [data_ref("elexon_disebsp", "periods 30-40, seven columns")],
    )
    doc.add(
        seg,
        *p(
            "B4",
            f"{F_DISEBSP}, settlement periods 30-40, columns "
            + ", ".join(sel)
            + " (values as in the file) [reported]:",
        ),
        *(
            "    " + ",".join(_csv_cell(row[col[name]]) for name in sel)
            for row in dis_rows
            if 30 <= row[col["settlementPeriod"]] <= 40
        ),
    )

    build.construction = (
        "Part A transcribes ESO Table 3, ESO Table 5 (with the section 4.4 text), Appendix M "
        "Q16 and Q17 and Appendix I Table 1 from the source catalogue extracts; every printed "
        "cell and every quotation is checked on the stated PDF page. Part B copies Elexon BOALF "
        "(deduplicated across seven per-period queries, acceptanceTime 15:40-16:45Z), QAS "
        "(whole day) and DISEBSP (whole day) records without changing values. Control rows: one "
        "ESO-ENCC entry per acceptance in builder/system_response/rows/real_r06_control.jsonl."
    )

    # ---- Artifacts ----------------------------------------------------------------------------
    table_rows: list[list[Any]] = []
    for r in tab3:
        table_rows.append(
            [
                "ESO technical report Table 3",
                r["service"],
                r["provider_type"],
                "Primary response held (MW)",
                r["primary_response_held_mw"],
            ]
        )
        table_rows.append(
            [
                "ESO technical report Table 3",
                r["service"],
                r["provider_type"],
                "Secondary response held (MW)",
                r["secondary_response_held_mw"],
            ]
        )
    for r in tab5:
        table_rows.append(
            [
                "ESO technical report Table 5",
                r["service"],
                r["provider_type"],
                "Validated Primary response",
                r["primary_cell_printed"],
            ]
        )
        table_rows.append(
            [
                "ESO technical report Table 5",
                r["service"],
                r["provider_type"],
                "Validated Secondary response",
                r["secondary_cell_printed"],
            ]
        )
    for label, time, loss in points:
        table_rows.append(
            ["Appendix M Q16 table", f"{label} ({time})", "", "Largest gen loss", loss]
        )
    for r in q16:
        kind = r["response_category"] + (
            f" {r['response_subtype']}" if r["response_subtype"] else ""
        )
        table_rows.append(
            [
                "Appendix M Q16 table",
                f"{r['time_point_label']} ({r['time_as_printed']})",
                kind,
                "Low Frequency Holding (MW) Primary [Secondary]",
                r["secondary_as_printed"],
            ]
        )
    for r in q17:
        kind = r["response_category"] + (
            f" {r['trigger_or_subtype']}" if r["trigger_or_subtype"] else ""
        )
        for heading, key in (
            ("Number of Units", "number_of_units"),
            ("Low Frequency Holding Primary [Secondary]", "holding_as_printed"),
            (
                "Low Frequency Delivered within 30 seconds of event",
                "lf_delivered_within_30s_mw",
            ),
        ):
            table_rows.append(
                ["Appendix M Q17 table", kind, r["bm_nbm"], heading, r[key]]
            )
    build.add_artifact(
        Artifact(
            name=F_TABLES,
            media_type="text/csv",
            description="ESO Table 3, ESO Table 5 and Appendix M Q16/Q17 tables as printed, one "
            "printed cell per row (Part A1-A4).",
            data=csv_bytes(
                [
                    "table",
                    "row_label",
                    "row_detail",
                    "column_label",
                    "value_as_printed",
                ],
                table_rows,
            ),
            provenance={
                "extraction_method": "transcription",
                "builder": "builder/system_response/real/build_real.py",
                "inputs": [
                    {"catalogue_extract": f"extracted/{n}"}
                    for n in (TAB3, TAB5, Q16, Q17)
                ],
                "transformation": "cells as printed; empty cell where the source prints none",
            },
        )
    )
    build.add_artifact(
        Artifact(
            name=F_IMBALANCE,
            media_type="text/csv",
            description="Appendix I Table 1, Modelled Imbalance Time Series, as printed (event, "
            "time, imbalance change MW).",
            data=csv_bytes(
                ["event", "time_as_printed", "imbalance_change_mw_as_printed"],
                [
                    [r["event"], r["time_as_printed"], r["imbalance_change_mw"]]
                    for r in appi
                ],
            ),
            provenance={
                "extraction_method": "transcription",
                "builder": "builder/system_response/real/build_real.py",
                "inputs": [{"catalogue_extract": f"extracted/{APPI}"}],
                "transformation": "three printed columns only; the catalogue's assumed-ISO time "
                "and basis notes are not reproduced",
            },
        )
    )
    build.add_artifact(
        Artifact(
            name=F_BOALF,
            media_type="text/csv",
            description="Elexon BOALF bid-offer acceptance level records with acceptanceTime "
            "15:40-16:45 UTC on 9 August 2019 (unique records of the SP32-38 queries).",
            data=csv_bytes(BOALF_FIELDS, [[r[f] for f in BOALF_FIELDS] for r in recs]),
            provenance={
                "extraction_method": "script",
                "builder": "builder/system_response/real/build_real.py",
                "inputs": [
                    {
                        "source_id": f"elexon_boalf_sp{sp}",
                        "file": SOURCES[f"elexon_boalf_sp{sp}"]["rel"],
                        "sha256": SOURCES[f"elexon_boalf_sp{sp}"]["sha256"],
                    }
                    for sp in BOALF_SPS
                ],
                "transformation": "deduplicate identical records; keep acceptanceTime "
                "15:40:00Z-16:45:00Z inclusive; sort by acceptanceTime, bmUnit, "
                "acceptanceNumber, timeFrom",
                "counts": stats,
            },
        )
    )
    build.add_artifact(
        Artifact(
            name=F_QAS,
            media_type="text/csv",
            description="Elexon QAS balancing services volume per BM unit per settlement period, "
            f"9 August 2019 (every record returned; {len(qas)} rows).",
            data=csv_bytes(QAS_FIELDS, qas),
            provenance={
                "extraction_method": "script",
                "builder": "builder/system_response/real/build_real.py",
                "inputs": [
                    {
                        "source_id": "elexon_qas",
                        "file": SOURCES["elexon_qas"]["rel"],
                        "sha256": SOURCES["elexon_qas"]["sha256"],
                    }
                ],
                "transformation": "all records; sort by settlementPeriod, bmUnit",
            },
        )
    )
    build.add_artifact(
        Artifact(
            name=F_DISEBSP,
            media_type="text/csv",
            description="Elexon DISEBSP settlement system prices and net imbalance volume, "
            "settlement date 9 August 2019, all fields.",
            data=csv_bytes(dis_fields, dis_rows),
            provenance={
                "extraction_method": "script",
                "builder": "builder/system_response/real/build_real.py",
                "inputs": [
                    {
                        "source_id": "elexon_disebsp",
                        "file": SOURCES["elexon_disebsp"]["rel"],
                        "sha256": SOURCES["elexon_disebsp"]["sha256"],
                    }
                ],
                "transformation": "all fields in API order; sort by settlementPeriod",
            },
        )
    )
    build.control_rows = control_rows(recs)
    require(
        len(build.control_rows) == stats["acceptances"],
        "one control row per acceptance",
    )
    return build


def _csv_cell(value: Any) -> str:
    from real_common import cell

    return cell(value)


#: Control-log registry contribution (merged by the integration step).
CONTROL_LOG_CONTRIB = [
    {
        "room_id": ROOM,
        "evidence_ids": [DOC_ID],
        "source_note": "Elexon BMRS BOALF bid-offer acceptances (real extracts; see R06), one "
        "entry per acceptance with acceptanceTime 15:40-16:45 UTC on 9 August 2019.",
        "clock_note": "recorded_time is the Elexon acceptanceTime (UTC, minute resolution); "
        "index uncertainty 60 s.",
    }
]
