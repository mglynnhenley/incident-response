"""R02 — system conditions: real Elexon/NESO extracts plus ESO inertia/holding tables.

Builder-only. Produces the R02 text note, its CSV artifacts and the asset-log rows for the BM
units of Hornsea One (T_HOWAO-1/2/3) and Little Barford (T_LBAR-1, T_LBAR-1G): metered B1610
volumes per settlement period and Maximum Export Limit (MEL) records.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
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
    wrap,
)
from real_docbuild import Artifact, DocBuild
from real_sources import B1610_UNITS, ELEXON_ATTRIBUTION, MEL_UNITS, SOURCES

DOC_ID = "R02"
TITLE = "System conditions data, 9 August 2019"
FUELS = (
    "BIOMASS",
    "CCGT",
    "COAL",
    "INTEW",
    "INTFR",
    "INTIRL",
    "INTNED",
    "INTNEM",
    "NPSHYD",
    "NUCLEAR",
    "OCGT",
    "OIL",
    "OTHER",
    "PS",
    "WIND",
)
ASSET_OF_UNIT = {
    "T_HOWAO-1": "HORNSEA-ONE",
    "T_HOWAO-2": "HORNSEA-ONE",
    "T_HOWAO-3": "HORNSEA-ONE",
    "T_LBAR-1": "LITTLE-BARFORD",
    "T_LBAR-1G": "LITTLE-BARFORD",
}
EXCERPT_PERIODS = range(30, 41)
NESO_DATES = ("08-AUG-2019", "09-AUG-2019", "10-AUG-2019")
INERTIA_DATES = ("2019-08-08", "2019-08-09", "2019-08-10")

F_FUELINST = "R02_elexon_fuelinst_5min_20190809.csv"
F_FUELHH = "R02_elexon_fuelhh_halfhour_20190809.csv"
F_INDO = "R02_elexon_indo_itsdo_20190809.csv"
F_NESO_DEMAND = "R02_neso_historic_demand_20190808-10.csv"
F_INERTIA = "R02_neso_inertia_20190808-10.csv"
F_LOLP = "R02_elexon_lolpdrm_20190809.csv"
F_BMU = "R02_elexon_bm_unit_reference.csv"
F_B1610 = "R02_elexon_b1610_selected_units_20190809.csv"
F_MELS = "R02_elexon_mels_selected_units_20190809.csv"
F_TABLES = "R02_eso_inertia_and_conditions_tables.csv"


def p(label: str, text: str) -> list[str]:
    return wrap(text, first=f"{label:<3}", indent="    ")


def cont(text: str) -> list[str]:
    return wrap(text, first="    ", indent="    ")


# ---------------------------------------------------------------------------------------------
# Real-data extracts
# ---------------------------------------------------------------------------------------------


def _wide(records: list[dict[str, Any]], key: str) -> list[list[Any]]:
    groups: dict[str, dict[str, Any]] = defaultdict(dict)
    meta: dict[str, tuple[Any, ...]] = {}
    for rec in records:
        stamp = rec[key]
        fuel = rec["fuelType"]
        require(fuel not in groups[stamp], f"duplicate {fuel} at {stamp}")
        groups[stamp][fuel] = rec["generation"]
        info = (
            rec["startTime"],
            rec["publishTime"],
            rec["settlementDate"],
            rec["settlementPeriod"],
        )
        require(
            meta.setdefault(stamp, info) == info, f"inconsistent metadata at {stamp}"
        )
    rows = []
    for stamp in sorted(groups):
        require(set(groups[stamp]) == set(FUELS), f"fuel set differs at {stamp}")
        rows.append([*meta[stamp], *(groups[stamp][f] for f in FUELS)])
    return rows


def fuelinst_rows(inputs) -> list[list[Any]]:
    rows = _wide(inputs.real_json("elexon_fuelinst")["data"], "startTime")
    require(len(rows) == 61, f"FUELINST rows {len(rows)} != 61")
    require(
        rows[0][1] == "2019-08-09T14:00:00Z" and rows[-1][1] == "2019-08-09T19:00:00Z",
        "pub",
    )
    for row in rows:
        start = parse_utc(row[0])
        sp_start, sp_end = settlement_period_bounds_utc(EVENT_DATE, row[3])
        require(
            row[2] == "2019-08-09" and sp_start <= start < sp_end,
            f"SP mismatch {row[:4]}",
        )
    return rows


#: FUELHH quirk kept as published: the period-48 row of settlement date 2019-08-09 carries the
#: startTime of the previous day's period 48.
FUELHH_ODD_PERIODS = {48: "2019-08-08T22:30:00Z"}


def fuelhh_rows(inputs) -> list[list[Any]]:
    rows = _wide(inputs.real_json("elexon_fuelhh")["data"], "settlementPeriod")
    require(
        len(rows) == 48 and [r[3] for r in rows] == list(range(1, 49)), "FUELHH periods"
    )
    for row in rows:
        sp_start, _ = settlement_period_bounds_utc(EVENT_DATE, row[3])
        expected = FUELHH_ODD_PERIODS.get(row[3], iso_z(sp_start))
        require(row[0] == expected, f"FUELHH startTime/SP pattern changed {row[:4]}")
    return rows


def check_fuelhh_caveat(inst: list[list[Any]], half: list[list[Any]]) -> list[int]:
    """Periods whose FUELHH WIND equals the mean of five (not six) FUELINST rows."""
    wind = 4 + FUELS.index("WIND")
    by_start = {row[0]: row[wind] for row in inst}
    five_only = []
    six = 0
    for row in half:
        start, _ = settlement_period_bounds_utc(EVENT_DATE, row[3])
        stamps = [iso_z(start + timedelta(minutes=5 * i)) for i in range(6)]
        if not all(s in by_start for s in stamps):
            continue
        mean6 = sum(by_start[s] for s in stamps) / 6
        mean5 = sum(by_start[s] for s in stamps[:5]) / 5
        if abs(row[wind] - mean5) < 1 and abs(row[wind] - mean6) >= 1:
            five_only.append(row[3])
        elif abs(row[wind] - mean6) < 1:
            six += 1
    require(
        bool(five_only) and six > 0,
        "FUELHH averaging caveat no longer holds; revise R02",
    )
    return five_only


def indo_rows(inputs) -> list[list[Any]]:
    data = inputs.real_json("elexon_indo_itsdo")["data"]
    fields = [
        "publishTime",
        "startTime",
        "settlementDate",
        "settlementPeriod",
        "initialDemandOutturn",
        "initialTransmissionSystemDemandOutturn",
    ]
    rows = [
        [r[f] for f in fields]
        for r in sorted(data, key=lambda r: r["settlementPeriod"])
    ]
    require(
        len(rows) == 48 and [r[3] for r in rows] == list(range(1, 49)), "INDO periods"
    )
    for row in rows:
        sp_start, sp_end = settlement_period_bounds_utc(EVENT_DATE, row[3])
        require(
            parse_utc(row[1]) == sp_start and parse_utc(row[0]) == sp_end, f"INDO {row}"
        )
    return [fields, *rows]


def _select_lines(raw: bytes, keep) -> tuple[bytes, list[str]]:
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    selected = [lines[0]] + [line for line in lines[1:] if keep(line)]
    return "".join(selected).encode("utf-8"), [line.rstrip("\r\n") for line in selected]


def neso_demand(inputs) -> tuple[bytes, list[str]]:
    data, lines = _select_lines(
        inputs.real_bytes("neso_historic_demand"),
        lambda line: line.split(",")[0] in NESO_DATES,
    )
    require(len(lines) == 1 + 144, f"NESO demand rows {len(lines) - 1} != 144")
    require(
        lines[0].startswith("SETTLEMENT_DATE,SETTLEMENT_PERIOD,ND,TSD,"), "NESO header"
    )
    return data, lines


def neso_inertia(inputs) -> tuple[bytes, list[str]]:
    data, lines = _select_lines(
        inputs.real_bytes("neso_inertia"),
        lambda line: line.split(",")[0] in INERTIA_DATES,
    )
    require(len(lines) == 1 + 144, f"inertia rows {len(lines) - 1} != 144")
    require(
        lines[0] == '"Settlement Date","Settlement Period","Outturn Inertia",'
        '"Market Provided Inertia"',
        "inertia header",
    )
    return data, lines


def lolp_rows(inputs) -> list[list[Any]]:
    fields = [
        "publishTime",
        "publishingPeriodCommencingTime",
        "startTime",
        "settlementDate",
        "settlementPeriod",
        "forecastHorizon",
        "lossOfLoadProbability",
        "deratedMargin",
    ]
    data = [
        r
        for r in inputs.real_json("elexon_lolpdrm")["data"]
        if r["settlementDate"] == "2019-08-09"
    ]
    data.sort(key=lambda r: (r["settlementPeriod"], r["forecastHorizon"]))
    require(len(data) == 240, f"LOLPDRM rows {len(data)} != 240")
    return [fields, *([r[f] for f in fields] for r in data)]


def bmu_rows(inputs) -> list[list[Any]]:
    data = inputs.real_json("elexon_ref_bmunits")
    selected = [r for r in data if r.get("elexonBmUnit") in MEL_UNITS]
    selected.sort(key=lambda r: r["elexonBmUnit"])
    require(
        [r["elexonBmUnit"] for r in selected] == sorted(MEL_UNITS),
        "BM unit reference rows",
    )
    fields = list(selected[0].keys())
    require(all(list(r.keys()) == fields for r in selected), "BM unit fields differ")
    return [fields, *([r[f] for f in fields] for r in selected)]


B1610_FIELDS = [
    "dataset",
    "psrType",
    "bmUnit",
    "nationalGridBmUnitId",
    "settlementDate",
    "settlementPeriod",
    "halfHourEndTime",
    "settlementRunType",
    "quantity",
]


def b1610_records(inputs) -> list[tuple[str, int, dict[str, Any]]]:
    """(source key, index in the source file, record) for settlement date 9 Aug, 4 units x 48."""
    out = []
    for unit in B1610_UNITS:
        key = f"elexon_b1610_{unit}"
        data = inputs.real_json(key)
        recs = [
            (i, r) for i, r in enumerate(data) if r["settlementDate"] == "2019-08-09"
        ]
        require(
            sorted(r["settlementPeriod"] for _, r in recs) == list(range(1, 49)), unit
        )
        for index, rec in sorted(recs, key=lambda item: item[1]["settlementPeriod"]):
            require(
                rec["bmUnit"] == unit and rec["settlementRunType"] == "DF",
                f"{unit} {rec}",
            )
            _, sp_end = settlement_period_bounds_utc(
                EVENT_DATE, rec["settlementPeriod"]
            )
            require(
                parse_utc(rec["halfHourEndTime"]) == sp_end, f"halfHourEndTime {rec}"
            )
            out.append((key, index, rec))
    return out


MEL_FIELDS = [
    "dataset",
    "settlementDate",
    "settlementPeriod",
    "timeFrom",
    "timeTo",
    "levelFrom",
    "levelTo",
    "nationalGridBmUnit",
    "bmUnit",
]


def mel_records(inputs) -> list[tuple[str, int, dict[str, Any]]]:
    out = []
    for unit in MEL_UNITS:
        key = f"elexon_physical_{unit}"
        data = inputs.real_json(key)["data"]
        recs = [
            (i, r)
            for i, r in enumerate(data)
            if r["dataset"] == "MELS" and r["settlementDate"] == "2019-08-09"
        ]
        recs.sort(key=lambda item: (item[1]["timeFrom"], item[1]["timeTo"]))
        require(len(recs) >= 48, f"{unit}: only {len(recs)} MEL records")
        for index, rec in recs:
            require(rec["bmUnit"] == unit, f"{unit} {rec}")
            sp_start, sp_end = settlement_period_bounds_utc(
                EVENT_DATE, rec["settlementPeriod"]
            )
            t0, t1 = parse_utc(rec["timeFrom"]), parse_utc(rec["timeTo"])
            require(
                sp_start <= t0 <= t1 <= sp_end, f"MEL record outside its period {rec}"
            )
            out.append((key, index, rec))
    return out


# ---------------------------------------------------------------------------------------------
# Asset-log rows
# ---------------------------------------------------------------------------------------------

SP_CLOCK = (
    "Elexon settlement period on the UK local clock (BST, UTC+01:00, on this date); "
    "halfHourEndTime is UTC written without a zone designator"
)
MEL_CLOCK = "UTC (Elexon timeFrom/timeTo with Z), minute resolution"


def b1610_row(key: str, index: int, rec: dict[str, Any]) -> dict[str, Any]:
    unit, period = rec["bmUnit"], rec["settlementPeriod"]
    start, end = settlement_period_bounds_utc(EVENT_DATE, period)
    mid = start + (end - start) / 2
    return {
        "kind": "asset",
        "event_id": f"R02-B1610-{unit}-20190809-SP{period:02d}",
        "evidence_id": DOC_ID,
        "asset_id": ASSET_OF_UNIT[unit],
        "recorded_time": f"settlementDate {rec['settlementDate']}, settlementPeriod {period} "
        f"(halfHourEndTime {rec['halfHourEndTime']})",
        "clock_basis": SP_CLOCK,
        "index_time_utc": iso_z(mid),
        "index_uncertainty_s": 900,
        "signal": f"{unit} B1610 MWh",
        "value": rec["quantity"],
        "unit": "MWh",
        "text": f"Metered volume of BM unit {unit} for the settlement period: "
        f"{rec['quantity']!r} MWh (settlementRunType {rec['settlementRunType']}). The value is "
        "energy over the whole 30-minute settlement period; the index time is the middle of "
        "that period and the uncertainty is half its length.",
        "value_status": "measured",
        "provenance": {
            "source_id": key,
            "file": SOURCES[key]["rel"],
            "sha256": SOURCES[key]["sha256"],
            "url": SOURCES[key]["url"],
            "record_index": index,
            "record": {k: rec[k] for k in B1610_FIELDS},
        },
    }


def mel_row(key: str, index: int, rec: dict[str, Any]) -> dict[str, Any]:
    unit = rec["bmUnit"]
    t0 = parse_utc(rec["timeFrom"])
    return {
        "kind": "asset",
        "event_id": f"R02-MELS-{unit}-{t0.strftime('%Y%m%dT%H%MZ')}",
        "evidence_id": DOC_ID,
        "asset_id": ASSET_OF_UNIT[unit],
        "recorded_time": f"timeFrom {rec['timeFrom']} to timeTo {rec['timeTo']}",
        "clock_basis": MEL_CLOCK,
        "index_time_utc": iso_z(t0),
        "index_uncertainty_s": 0,
        "signal": f"{unit} MEL MW",
        "value": rec["levelFrom"],
        "unit": "MW",
        "text": f"Maximum Export Limit record for BM unit {unit}: {rec['levelFrom']} MW at "
        f"{rec['timeFrom']} to {rec['levelTo']} MW at {rec['timeTo']} (settlementDate "
        f"{rec['settlementDate']}, settlementPeriod {rec['settlementPeriod']}). The value field "
        "is the level at timeFrom.",
        "value_status": "reported",
        "provenance": {
            "source_id": key,
            "file": SOURCES[key]["rel"],
            "sha256": SOURCES[key]["sha256"],
            "url": SOURCES[key]["url"],
            "record_index": index,
            "record": {k: rec[k] for k in MEL_FIELDS},
        },
    }


# ---------------------------------------------------------------------------------------------
# Report tables (ESO Table 4; Appendix M Q42, first two rows)
# ---------------------------------------------------------------------------------------------

TAB4 = "ESO-p23-tab4.csv"
Q42 = "APP-p90-tbl-q42-inertia.csv"


def report_tables(inputs) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    tab4 = inputs.catalogue_rows(TAB4)
    require(
        [r["parameter"] for r in tab4]
        == ["Demand", "Inertia", "Largest planned loss", "Frequency Response Holding"],
        "ESO Table 4 rows changed",
    )
    q42 = inputs.catalogue_rows(Q42)[:2]
    require(
        [r["timestamp_as_printed"] for r in q42] == ["11:00", "16:52"],
        "Q42 rows changed",
    )
    return tab4, q42


# ---------------------------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------------------------


def build(inputs) -> DocBuild:
    doc = TextDoc(DOC_ID)
    build = DocBuild(
        doc_id=DOC_ID,
        title=TITLE,
        owner="Elexon (BMRS data) and NESO (open data portal); National Grid ESO (report tables)",
        category="measurement_data",
        record_type="real public dataset extracts (CSV files) with two published report tables "
        "and this metadata note",
        construction="",
        text=doc,
    )
    build.header(
        "Elexon Limited (BMRS / Insights API data, much of it supplied by the system operator); "
        "National Energy System Operator (NESO) open data portal; National Grid ESO "
        "(technical report tables)",
        wrap(
            "Clock reference: stated for each file and table below. Elexon timestamps are UTC "
            "(ISO-8601 with Z). Elexon and NESO settlement periods are numbered on the UK local "
            "clock: period 1 starts at 00:00 local time and each period lasts 30 minutes. UK "
            "local time on 9 August 2019 was BST (UTC+01:00)."
        ),
    )

    inst = fuelinst_rows(inputs)
    half = fuelhh_rows(inputs)
    five_only = check_fuelhh_caveat(inst, half)
    indo = indo_rows(inputs)
    demand_bytes, demand_lines = neso_demand(inputs)
    inertia_bytes, inertia_lines = neso_inertia(inputs)
    demand_meta = inputs.real_json("neso_demand_resource")
    inertia_meta = inputs.real_json("neso_inertia_resource")
    require(
        demand_meta["name"] == "Historic Demand Data 2019",
        "NESO demand resource record",
    )
    require(
        inertia_meta["name"] == "GB System Inertia - 2019-2020", "NESO inertia resource"
    )
    lolp = lolp_rows(inputs)
    bmu = bmu_rows(inputs)
    b1610 = b1610_records(inputs)
    mels = mel_records(inputs)
    tab4, q42 = report_tables(inputs)

    doc.blank()
    doc.frame(
        "Part A: how to use the record (files, citation)",
        "PART A — HOW TO USE THIS RECORD",
        *p(
            "A1",
            "The CSV files described in Part B are delivered with this note; after retrieval they "
            "are in $EVIDENCE_DIR/R02/. Dataset values are copied without rounding, unit "
            "conversion, interpolation or gap filling. CSV conventions for files built from the "
            "publishers' JSON: comma-separated, UTF-8, LF line endings, one header row; numbers as "
            "published; true/false for JSON booleans; an empty cell for JSON null. The two NESO "
            "files keep the publisher's own lines byte for byte (CRLF line endings).",
        ),
        *p(
            "A2",
            "Unit-level metered volumes (B8) and Maximum Export Limit records (B9) are also "
            "available through query_asset_log for assets HORNSEA-ONE and LITTLE-BARFORD; each "
            "row there has an event ID and cites R02.",
        ),
        *p(
            "A3",
            "Cite this note with L<n> or L<a>-L<b> (line numbers shown on retrieval).",
        ),
    )

    # ---- Part B: file descriptions ---------------------------------------------------------
    doc.blank()
    doc.frame("Part B heading", "PART B — PUBLIC DATASET EXTRACTS (one block per file)")

    k = "elexon_fuelinst"
    seg = doc.segment(
        "B1 FUELINST file description, selection, columns, clock, caveats",
        "measured",
        "script",
        [
            data_ref(k, "all 61 publishTime rows 14:00Z-19:00Z, pivoted by fuelType"),
            doc_quote_ref(
                inputs,
                "elexon_api_docs",
                "/datasets/FUELINST description",
                "average MW values over 5 minutes for each category",
            ),
        ],
        "API rows (one per fuel type and startTime) pivoted to one row per startTime; values "
        "unchanged.",
    )
    doc.add(
        seg,
        *p(
            "B1",
            f"File {F_FUELINST} [measured] — generation outturn by fuel type, 5-minute values.",
        ),
        *cont(
            "Source: Elexon BMRS dataset FUELINST, Elexon Insights API endpoint /datasets/FUELINST "
            "queried with publishDateTimeFrom=2019-08-09T14:00:00Z and "
            "publishDateTimeTo=2019-08-09T19:00:00Z; retrieved 2026-10-20. Publisher: Elexon "
            f"Limited. Licence: Elexon BMRS open data licence. {ELEXON_ATTRIBUTION}",
        ),
        *cont(
            f"Rows: {len(inst)} (every row returned), one per startTime from "
            f"{inst[0][0]} to {inst[-1][0]}. The API returns one record per fuel type; the "
            "file has one column per fuel type instead. No totals are added.",
        ),
        *cont(
            "Columns: startTime, publishTime (UTC); settlementDate, settlementPeriod (UK local "
            "clock); "
            + ", ".join(FUELS)
            + " (MW). INT* codes are interconnectors; PS is pumped "
            "storage; NPSHYD is non-pumped-storage hydro (publisher's fuel-type codes).",
        ),
        *cont(
            'Publisher\'s description: "average MW values over 5 minutes for each category". '
            "The data do not say whether startTime is the start of the averaging interval, so "
            "treat the time of each FUELINST value as uncertain by up to 5 minutes. Embedded "
            "(distribution-connected) generation is not included.",
        ),
    )

    k = "elexon_fuelhh"
    seg = doc.segment(
        "B2 FUELHH file description and averaging caveat",
        "measured",
        "script",
        [
            data_ref(k, "all 48 settlement periods of 2019-08-09, pivoted by fuelType"),
            data_ref(
                "elexon_fuelinst",
                "averaging check: FUELHH WIND equals the mean of the first five FUELINST rows "
                f"in settlement periods {five_only} and the mean of all six in others",
            ),
            doc_quote_ref(
                inputs,
                "elexon_api_docs",
                "/datasets/FUELHH description",
                "average MW values over 30 minutes for each category",
            ),
        ],
        "Pivoted as B1. The caveat is the builder's check of FUELHH against FUELINST.",
    )
    doc.add(
        seg,
        *p(
            "B2",
            f"File {F_FUELHH} [measured] — generation outturn by fuel type, half-hourly.",
        ),
        *cont(
            "Source: Elexon BMRS dataset FUELHH, endpoint /datasets/FUELHH queried for "
            "settlementDate 2019-08-09; retrieved 2026-10-20. Licence as B1.",
        ),
        *cont(
            f"Rows: {len(half)}, settlement periods 1-48 of 2019-08-09, in period order. Columns "
            "as B1; startTime is the UTC start of the settlement period, except that the "
            "publisher dates the period-48 row 2019-08-08T22:30:00Z (kept as published). "
            'Publisher\'s description: "average MW values over 30 minutes for each category".',
        ),
        *cont(
            "Caveat: on this date the FUELHH value of some settlement periods equals the mean of "
            "only the first five of the six FUELINST values in that period, not of all six. Do "
            "not use FUELHH to time changes within a half hour or to check FUELINST.",
        ),
    )

    k = "elexon_indo_itsdo"
    seg = doc.segment(
        "B3 INDO/ITSDO file description",
        "measured",
        "script",
        [
            data_ref(k, "48 settlement periods of 2019-08-09, fields as published"),
            doc_quote_ref(
                inputs,
                "elexon_api_docs",
                "/demand/outturn description",
                "measures the half-hour average MW demand metered by the Transmission Company "
                "based on its operational metering",
            ),
            doc_quote_ref(
                inputs,
                "elexon_api_docs",
                "/demand/outturn description",
                "takes into account transmission losses but does not include station "
                "transformer load, pumped storage demand or interconnector demand",
            ),
        ],
    )
    doc.add(
        seg,
        *p("B3", f"File {F_INDO} [measured] — initial demand outturn, half-hourly."),
        *cont(
            "Source: Elexon endpoint /demand/outturn queried for settlementDate 2019-08-09; "
            "retrieved 2026-10-20. Licence as B1.",
        ),
        *cont(
            f"Rows: {len(indo) - 1}, settlement periods 1-48. Columns: "
            + ", ".join(indo[0])
            + ". "
            "startTime is the UTC start of the period and publishTime its end (UTC); values MW.",
        ),
        *cont(
            "Publisher's description: INDO \"measures the half-hour average MW demand metered by "
            'the Transmission Company based on its operational metering"; INDO "takes into '
            "account transmission losses but does not include station transformer load, pumped "
            'storage demand or interconnector demand", while ITSDO includes them.',
        ),
    )

    k = "neso_historic_demand"
    seg = doc.segment(
        "B4 NESO historic demand file description incl. modelled embedded generation",
        "measured",
        "script",
        [
            data_ref(
                k,
                "header and the 144 lines dated 08/09/10-AUG-2019, copied byte for byte",
            ),
            data_ref("neso_demand_resource", "fields created and last_modified"),
            doc_quote_ref(
                inputs,
                "neso_demand_faq_docx",
                "FAQ answer on averaging",
                "All values are an average over the half hour.",
            ),
            doc_quote_ref(
                inputs,
                "neso_demand_faq_docx",
                "FAQ answer on time basis",
                "All times are UK time and for the half hour beginning.",
            ),
            doc_quote_ref(
                inputs,
                "neso_embedded_definition_docx",
                "definition of embedded",
                "The true output of these generators is not known so an estimate is provided "
                "based on NESO's best model.",
            ),
        ],
        "Rows selected by date; no value changed.",
    )
    header_cols = demand_lines[0].split(",")
    doc.add(
        seg,
        *p(
            "B4",
            f"File {F_NESO_DEMAND} [measured] — NESO historic demand data, half-hourly, "
            "8-10 August 2019; its embedded generation columns are [modelled].",
        ),
        *cont(
            "Source: NESO open data portal, Historic Demand Data 2019 (demanddata_2019.csv); "
            "retrieved 2026-10-20. Licence: NESO Open Data Licence v1.0. Supported by National "
            "Energy SO Open Data.",
        ),
        *cont(
            f"Rows: {len(demand_lines) - 1} (48 per day for 08-AUG-2019, 09-AUG-2019 and "
            "10-AUG-2019), copied from the publisher's file byte for byte with its header line. "
            "Columns: " + ", ".join(header_cols) + " (MW).",
        ),
        *cont(
            'Publisher\'s documentation: "All values are an average over the half hour." and '
            '"All times are UK time and for the half hour beginning." SETTLEMENT_DATE is '
            "written DD-MON-YYYY.",
        ),
        *cont(
            "EMBEDDED_WIND_GENERATION and EMBEDDED_SOLAR_GENERATION are model estimates "
            '[modelled]: "The true output of these generators is not known so an estimate is '
            "provided based on NESO's best model.\"",
        ),
        *cont(
            f"The publisher's resource record gives created {demand_meta['created'][:10]} and "
            f"last modified {demand_meta['last_modified'][:10]}; the copy used here was "
            "downloaded on 2026-10-20, and its values may differ from those available in 2019.",
        ),
    )

    k = "neso_inertia"
    seg = doc.segment(
        "B5 NESO inertia file description (model estimate)",
        "modelled",
        "script",
        [
            data_ref(
                k,
                "header and the 144 lines dated 2019-08-08/09/10, copied byte for byte",
            ),
            data_ref(
                "neso_inertia_resource",
                "fields description and created",
                quote=inertia_meta["description"].strip(),
            ),
        ],
        "Rows selected by date; no value changed.",
    )
    doc.add(
        seg,
        *p(
            "B5",
            f"File {F_INERTIA} [modelled] — NESO system inertia estimates, half-hourly, 8-10 August 2019.",
        ),
        *cont(
            "Source: NESO open data portal, GB System Inertia 2019-2020 (inertia.csv); retrieved "
            "2026-10-20. Licence as B4.",
        ),
        *cont(
            f"Rows: {len(inertia_lines) - 1} (48 per day), copied byte for byte with the header "
            "line. Columns: Settlement Date (YYYY-MM-DD), Settlement Period (UK local clock), "
            "Outturn Inertia, Market Provided Inertia. The file does not state a unit.",
        ),
        *cont(
            f'Publisher\'s resource description: "{inertia_meta["description"].strip()}" The '
            f"resource record gives created {inertia_meta['created'][:10]}.",
        ),
    )

    k = "elexon_lolpdrm"
    seg = doc.segment(
        "B6 LOLPDRM file description",
        "modelled",
        "script",
        [
            data_ref(
                k, "240 rows with settlementDate 2019-08-09 (5 horizons x 48 periods)"
            ),
            doc_quote_ref(
                inputs,
                "elexon_api_docs",
                "/forecast/system/loss-of-load description",
                "the returned value is the forecast received that number of hours before the "
                "start of the settlement period",
            ),
        ],
    )
    doc.add(
        seg,
        *p(
            "B6",
            f"File {F_LOLP} [modelled] — loss-of-load probability and de-rated margin forecasts.",
        ),
        *cont(
            "Source: Elexon endpoint /forecast/system/loss-of-load (LOLPDRM) for 9 August 2019; "
            "retrieved 2026-10-20. Licence as B1.",
        ),
        *cont(
            f"Rows: {len(lolp) - 1} (settlementDate 2019-08-09, forecast horizons 1, 2, 4, 8 and "
            "12 hours for each of 48 periods). Columns: "
            + ", ".join(lolp[0])
            + ". Times are "
            'UTC; deratedMargin in MW. For horizons of 1-8 hours "the returned value is the '
            'forecast received that number of hours before the start of the settlement period". '
            "These are forecasts made before each period, not outturn.",
        ),
    )

    k = "elexon_ref_bmunits"
    seg = doc.segment(
        "B7 BM unit reference file description (2026 registration snapshot)",
        "reported",
        "script",
        [
            data_ref(
                k, "records with elexonBmUnit in T_HOWAO-1/2/3, T_LBAR-1, T_LBAR-1G"
            )
        ],
    )
    doc.add(
        seg,
        *p(
            "B7",
            f"File {F_BMU} [reported] — Elexon BM unit reference data for five units.",
        ),
        *cont(
            "Source: Elexon endpoint /reference/bmunits/all; retrieved 2026-10-20. Licence as B1. "
            f"Rows: {len(bmu) - 1} (all fields of the five units listed in C4)."
        ),
        *cont(
            "Caveat: this is the publisher's registration data as served in 2026, not a copy of "
            "the register in force in August 2019; names and capacities may have changed since.",
        ),
    )

    seg = doc.segment(
        "B8 B1610 file description",
        "measured",
        "script",
        [
            *(
                data_ref(
                    f"elexon_b1610_{u}", "48 records with settlementDate 2019-08-09"
                )
                for u in B1610_UNITS
            ),
            doc_quote_ref(
                inputs,
                "elexon_api_docs",
                "/datasets/B1610/stream description",
                "The generation output returned by this endpoint is the metered volume and not "
                "the instantaneous power output",
            ),
        ],
    )
    doc.add(
        seg,
        *p(
            "B8",
            f"File {F_B1610} [measured] — metered generation per BM unit per settlement "
            "period (B1610).",
        ),
        *cont(
            "Source: Elexon endpoint /datasets/B1610/stream, one query per unit for "
            "2019-08-08T23:00:00Z to 2019-08-09T23:00:00Z; retrieved 2026-10-20. Licence as B1.",
        ),
        *cont(
            f"Rows: {len(b1610)} (units " + ", ".join(B1610_UNITS) + "; settlementDate "
            "2019-08-09, periods 1-48; the record for the next settlement date returned by the "
            "same query is not included). Columns: " + ", ".join(B1610_FIELDS) + ".",
        ),
        *cont(
            'quantity is energy in MWh over the settlement period. Publisher: "The generation '
            "output returned by this endpoint is the metered volume and not the instantaneous "
            'power output". halfHourEndTime is the UTC end of the period written without a zone '
            "designator. Every row has settlementRunType DF.",
        ),
    )

    seg = doc.segment(
        "B9 MELS file description; note on PN availability",
        "reported",
        "script",
        [
            *(
                data_ref(
                    f"elexon_physical_{u}",
                    "MELS records with settlementDate 2019-08-09",
                )
                for u in MEL_UNITS
            ),
        ],
    )
    doc.add(
        seg,
        *p(
            "B9",
            f"File {F_MELS} [reported] — Maximum Export Limit (MEL) records for five BM units.",
        ),
        *cont(
            "Source: Elexon endpoint /balancing/physical, one query per unit for "
            "2019-08-08T23:00:00Z to 2019-08-09T23:00:00Z; retrieved 2026-10-20. Licence as B1.",
        ),
        *cont(
            f"Rows: {len(mels)} MELS records with settlementDate 2019-08-09 for units "
            + ", ".join(MEL_UNITS)
            + ". Columns: "
            + ", ".join(MEL_FIELDS)
            + ". Each record is a "
            "level from levelFrom (MW) at timeFrom to levelTo (MW) at timeTo; times UTC, minute "
            "resolution. MELs are limits declared by the unit's operator, not output.",
        ),
        *cont(
            "The same queries returned physical notification (PN) records only for settlement "
            "periods 1-4 of 9 August and none for later periods; this record holds no PN data.",
        ),
    )
    _check_pn_gap(inputs)

    # ---- Part C: verbatim excerpts and reference rows ----------------------------------------
    doc.blank()
    doc.frame(
        "Part C heading",
        "PART C — FILE EXCERPTS (verbatim lines from the files in Part B)",
    )
    indo_lines = csv_bytes(indo[0], indo[1:]).decode().splitlines()
    seg = doc.segment(
        "C1 INDO/ITSDO verbatim lines, settlement periods 30-40",
        "measured",
        "script",
        [data_ref("elexon_indo_itsdo", "settlement periods 30-40 of 2019-08-09")],
    )
    doc.add(
        seg,
        *p(
            "C1",
            f"{F_INDO}, rows for settlement periods 30-40 (header omitted; column order as in "
            "B3) [measured]:",
        ),
        *(f"    {line}" for line in indo_lines[30:41]),
    )
    rows_9 = [
        line
        for line in demand_lines[1:]
        if line.startswith("09-AUG-2019,")
        and int(line.split(",")[1]) in EXCERPT_PERIODS
    ]
    seg = doc.segment(
        "C2 NESO demand verbatim lines, 9 Aug settlement periods 30-40",
        "measured",
        "script",
        [data_ref("neso_historic_demand", "09-AUG-2019 settlement periods 30-40")],
    )
    doc.add(
        seg,
        *p(
            "C2",
            f"{F_NESO_DEMAND}, rows for 09-AUG-2019 settlement periods 30-40 (header omitted; "
            "column order as in B4; embedded generation columns [modelled], others [measured]):",
        ),
        *(f"    {line}" for line in rows_9),
    )
    inertia_9 = [
        line
        for line in inertia_lines[1:]
        if line.startswith("2019-08-09,") and int(line.split(",")[1]) in EXCERPT_PERIODS
    ]
    seg = doc.segment(
        "C3 NESO inertia verbatim lines, 9 Aug settlement periods 30-40",
        "modelled",
        "script",
        [data_ref("neso_inertia", "2019-08-09 settlement periods 30-40")],
    )
    doc.add(
        seg,
        f"C3  {F_INERTIA}, header and the rows for 2019-08-09 periods 30-40 [modelled]:",
        f"    {inertia_lines[0]}",
        *(f"    {line}" for line in inertia_9),
    )
    for rows, name in ((rows_9, "C2"), (inertia_9, "C3")):
        require(len(rows) == len(EXCERPT_PERIODS), f"{name} excerpt rows")
    seg = doc.segment(
        "C4 Reference fields of the five BM units",
        "reported",
        "script",
        [
            data_ref(
                "elexon_ref_bmunits",
                "fields elexonBmUnit, bmUnitName, fuelType, "
                "leadPartyName, generationCapacity",
            )
        ],
    )
    fields = bmu[0]
    col = {name: fields.index(name) for name in fields}
    doc.add(
        seg,
        "C4  Selected fields of the five BM units in B7 (elexonBmUnit | bmUnitName | fuelType | "
        "leadPartyName |",
        "    generationCapacity in MW) [reported]:",
        *(
            "    "
            + " | ".join(
                str(r[col[n]])
                for n in (
                    "elexonBmUnit",
                    "bmUnitName",
                    "fuelType",
                    "leadPartyName",
                    "generationCapacity",
                )
            )
            + " [reported]"
            for r in bmu[1:]
        ),
    )

    # ---- Part D: report tables ----------------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part D heading and clock note",
        "PART D — PUBLISHED REPORT TABLES (transcribed as printed)",
        *wrap(
            "Times in these tables are printed without a zone; the reports give event times in "
            "local time (BST, UTC+01:00)."
        ),
    )
    t4_cells = ["01 July", "09 August"] + [
        x
        for r in tab4
        for x in (r["parameter"], r["2019-07-01_printed"], r["2019-08-09_printed"])
    ]
    seg = doc.segment(
        "D1 ESO Table 4 (comparison of system conditions, 1 July vs 9 August) with context",
        "reported",
        "transcription",
        [
            table_ref(
                inputs,
                "ESO",
                23,
                "4.4 Frequency Response, 3. Comparison with historical days, Table 4",
                "ESO-p23-tab4",
                TAB4,
                t4_cells,
            ),
            pdf_ref(
                inputs,
                "ESO",
                23,
                "4.4 Frequency Response, 3. Comparison with historical days",
                "On 1st July at 08:27 the NEMO interconnector tripped while importing 1,000MW "
                "from Belgium to GB resulting in an instantaneous loss of 1,000MW on the system.",
            ),
            pdf_ref(
                inputs,
                "ESO",
                23,
                "Table 4 caption",
                "Table 4 – Comparison of system conditions between 1st July and 9th August",
            ),
        ],
    )
    width = max(len(r["parameter"]) for r in tab4)
    doc.add(
        seg,
        *p(
            "D1",
            "National Grid ESO, Technical Report on the events of 9 August 2019 (published "
            '6 September 2019), section 4.4, "Table 4 – Comparison of system conditions between '
            '1st July and 9th August". Columns as printed: 01 July | 09 August.',
        ),
        *(
            f"    {r['parameter']:<{width}} | {r['2019-07-01_printed']:<9} | "
            f"{r['2019-08-09_printed']:<9} [reported]"
            for r in tab4
        ),
        "    Context printed before the table (quoted):",
        '    "On 1st July at 08:27 the NEMO interconnector tripped while importing 1,000MW '
        "[reported]",
        '    from Belgium to GB resulting in an instantaneous loss of 1,000MW on the system." '
        "[reported]",
    )
    q_cells = [
        x
        for r in q42
        for x in (r["timestamp_as_printed"], r["system_condition"], r["inertia_mva_s"])
    ]
    seg = doc.segment(
        "D2 Appendix M Q42 inertia estimate: method sentences and the two pre-event rows",
        "estimated",
        "transcription",
        [
            table_ref(
                inputs,
                "APP",
                90,
                "Appendix M, question 42, table (first two of eight rows)",
                "APP-p90-tbl-q42-inertia",
                Q42,
                q_cells,
            ),
            pdf_ref(
                inputs,
                "APP",
                90,
                "Appendix M, question 42",
                "What was the level of system inertia (in VAs) six hour period prior to, during "
                "and after the event?",
            ),
            pdf_ref(
                inputs,
                "APP",
                90,
                "Appendix M, answer 42",
                "The ESO does not currently measure system inertia directly but instead "
                "estimates it using a model.",
            ),
            pdf_ref(
                inputs,
                "APP",
                90,
                "Appendix M, answer 42",
                "The inertia estimate is derived from the forecasted demand level, embedded "
                "solar and wind to continuously estimate the system inertia and the largest loss "
                "that needs to be secured in real-time operations.",
            ),
        ],
        "Rows 1-2 of the 8-row table; the remaining rows are not reproduced in R02.",
    )
    doc.add(
        seg,
        *p(
            "D2",
            "Appendices to the ESO technical report, Appendix M (ESO answers to questions from "
            'the Energy Emergencies Executive Committee), question 42 as printed: "What was the '
            "level of system inertia (in VAs) six hour period prior to, during and after the "
            'event?"',
        ),
        *cont(
            'Answer (quoted, first two sentences): "The ESO does not currently measure system '
            "inertia directly but instead estimates it using a model. The inertia estimate is "
            "derived from the forecasted demand level, embedded solar and wind to continuously "
            "estimate the system inertia and the largest loss that needs to be secured in "
            'real-time operations."',
        ),
        "    First two of the eight table rows (Timestamp (hr:min:sec) | System Condition | "
        "Inertia (MVA.s)):",
        *(
            f"    {r['timestamp_as_printed']} | {r['system_condition']} | {r['inertia_mva_s']} "
            "[estimated]"
            for r in q42
        ),
    )

    build.construction = (
        "Real public datasets copied by builder/system_response/real/build_real.py from "
        "GB_REAL_DATA_DIR (hash-checked); JSON records written to CSV without changing values; "
        "NESO CSV lines copied byte for byte. Part D transcribes ESO Table 4 and the first two "
        "rows of Appendix M Q42 from the source catalogue extracts, every printed cell checked "
        "on the stated PDF page. No value is synthesised. Asset rows: B1610 per unit per "
        "settlement period and MELS records, written to builder/system_response/rows/"
        "real_r02_asset.jsonl."
    )

    # ---- Artifacts ----------------------------------------------------------------------------
    def art(name: str, desc: str, data: bytes, keys: list[str], detail: str) -> None:
        build.add_artifact(
            Artifact(
                name=name,
                media_type="text/csv",
                description=desc,
                data=data,
                provenance={
                    "extraction_method": "script",
                    "builder": "builder/system_response/real/build_real.py",
                    "inputs": [
                        {
                            "source_id": key,
                            "file": SOURCES[key]["rel"],
                            "sha256": SOURCES[key]["sha256"],
                        }
                        for key in keys
                    ],
                    "transformation": detail,
                },
            )
        )

    art(
        F_FUELINST,
        "Elexon FUELINST generation by fuel type, 5-minute MW, publishTime 14:00Z-19:00Z on "
        "9 August 2019; one column per fuel type.",
        csv_bytes(
            ["startTime", "publishTime", "settlementDate", "settlementPeriod", *FUELS],
            inst,
        ),
        ["elexon_fuelinst"],
        "pivot fuelType rows to columns; sort by startTime",
    )
    art(
        F_FUELHH,
        "Elexon FUELHH generation by fuel type, half-hourly MW, settlement date 9 August 2019.",
        csv_bytes(
            ["startTime", "publishTime", "settlementDate", "settlementPeriod", *FUELS],
            half,
        ),
        ["elexon_fuelhh"],
        "pivot fuelType rows to columns; sort by startTime",
    )
    art(
        F_INDO,
        "Elexon initial demand outturn (INDO) and transmission system demand outturn (ITSDO), "
        "half-hourly MW, settlement date 9 August 2019.",
        csv_bytes(indo[0], indo[1:]),
        ["elexon_indo_itsdo"],
        "fields as published; sort by settlementPeriod",
    )
    art(
        F_NESO_DEMAND,
        "NESO historic demand data (ND, TSD, embedded wind and solar estimates and other "
        "columns), half-hourly, 8-10 August 2019; publisher's lines unchanged.",
        demand_bytes,
        ["neso_historic_demand"],
        "header plus lines dated 08/09/10-AUG-2019, byte for byte",
    )
    art(
        F_INERTIA,
        "NESO system inertia estimates (outturn and market-provided; the file states no "
        "unit), half-hourly, 8-10 August 2019; publisher's lines unchanged.",
        inertia_bytes,
        ["neso_inertia"],
        "header plus lines dated 2019-08-08/09/10, byte for byte",
    )
    art(
        F_LOLP,
        "Elexon LOLPDRM loss-of-load probability and de-rated margin forecasts by horizon, "
        "settlement date 9 August 2019.",
        csv_bytes(lolp[0], lolp[1:]),
        ["elexon_lolpdrm"],
        "rows with settlementDate 2019-08-09; sort by settlementPeriod, forecastHorizon",
    )
    art(
        F_BMU,
        "Elexon BM unit reference data (2026 registration snapshot) for T_HOWAO-1, T_HOWAO-2, "
        "T_HOWAO-3, T_LBAR-1 and T_LBAR-1G.",
        csv_bytes(bmu[0], bmu[1:]),
        ["elexon_ref_bmunits"],
        "filter five units; all fields in API order; sort by elexonBmUnit",
    )
    art(
        F_B1610,
        "Elexon B1610 metered volumes (MWh per settlement period) for T_HOWAO-1, T_HOWAO-2, "
        "T_HOWAO-3 and T_LBAR-1, settlement date 9 August 2019.",
        csv_bytes(B1610_FIELDS, [[r[f] for f in B1610_FIELDS] for _, _, r in b1610]),
        [f"elexon_b1610_{u}" for u in B1610_UNITS],
        "settlementDate 2019-08-09 records; sort by unit, settlementPeriod",
    )
    art(
        F_MELS,
        "Elexon Maximum Export Limit (MELS) records for T_HOWAO-1, T_HOWAO-2, T_HOWAO-3, "
        "T_LBAR-1 and T_LBAR-1G, settlement date 9 August 2019.",
        csv_bytes(MEL_FIELDS, [[r[f] for f in MEL_FIELDS] for _, _, r in mels]),
        [f"elexon_physical_{u}" for u in MEL_UNITS],
        "dataset MELS, settlementDate 2019-08-09; sort by unit, timeFrom, timeTo",
    )
    table_rows = (
        [
            [
                "ESO technical report Table 4",
                r["parameter"],
                "01 July",
                r["2019-07-01_printed"],
            ]
            for r in tab4
        ]
        + [
            [
                "ESO technical report Table 4",
                r["parameter"],
                "09 August",
                r["2019-08-09_printed"],
            ]
            for r in tab4
        ]
        + [
            [
                "Appendix M Q42 table",
                r["system_condition"],
                r["timestamp_as_printed"],
                r["inertia_mva_s"] + " MVA.s",
            ]
            for r in q42
        ]
    )
    build.add_artifact(
        Artifact(
            name=F_TABLES,
            media_type="text/csv",
            description="Report tables of Part D as printed (ESO Table 4; first two rows of "
            "Appendix M Q42), one printed cell per row.",
            data=csv_bytes(
                ["table", "row_label", "column_label", "value_as_printed"], table_rows
            ),
            provenance={
                "extraction_method": "transcription",
                "builder": "builder/system_response/real/build_real.py",
                "inputs": [
                    {"catalogue_extract": f"extracted/{TAB4}"},
                    {"catalogue_extract": f"extracted/{Q42}"},
                ],
                "transformation": "cells as printed; Q42 values given the printed column unit",
            },
        )
    )

    # ---- Asset rows -------------------------------------------------------------------------
    build.asset_rows = [b1610_row(*r) for r in b1610] + [mel_row(*r) for r in mels]
    ids = [r["event_id"] for r in build.asset_rows]
    require(len(ids) == len(set(ids)), "duplicate R02 event IDs")
    return build


def _check_pn_gap(inputs) -> None:
    """B9 says PN records exist only for settlement periods 1-4 of 9 August in every unit file."""
    for unit in MEL_UNITS:
        data = inputs.real_json(f"elexon_physical_{unit}")["data"]
        periods = sorted(
            r["settlementPeriod"]
            for r in data
            if r["dataset"] == "PN" and r["settlementDate"] == "2019-08-09"
        )
        require(
            periods == [1, 2, 3, 4], f"{unit}: PN periods {periods} != [1, 2, 3, 4]"
        )


#: Asset-log registry contributions (merged by the integration step).
ASSET_LOG_CONTRIB = [
    {
        "asset_id": "HORNSEA-ONE",
        "evidence_ids": [DOC_ID],
        "signals": [f"{u} B1610 MWh" for u in B1610_UNITS if u.startswith("T_HOWAO")]
        + [f"{u} MEL MW" for u in MEL_UNITS if u.startswith("T_HOWAO")],
        "clock_note": "B1610 rows: Elexon settlement period (UK local clock; BST on 9 August "
        "2019), indexed at the middle of the period +/- 900 s. MEL rows: UTC timeFrom, minute "
        "resolution.",
        "source_note": "Elexon BMRS B1610 and MELS data (real extracts; see R02).",
    },
    {
        "asset_id": "LITTLE-BARFORD",
        "evidence_ids": [DOC_ID],
        "signals": [f"{u} B1610 MWh" for u in B1610_UNITS if u.startswith("T_LBAR")]
        + [f"{u} MEL MW" for u in MEL_UNITS if u.startswith("T_LBAR")],
        "clock_note": "B1610 rows: Elexon settlement period (UK local clock; BST on 9 August "
        "2019), indexed at the middle of the period +/- 900 s. MEL rows: UTC timeFrom, minute "
        "resolution.",
        "source_note": "Elexon BMRS B1610 and MELS data (real extracts; see R02).",
    },
]
