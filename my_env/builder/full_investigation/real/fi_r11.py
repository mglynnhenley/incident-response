"""R11 — rail performance records (Network Rail delay attribution; ORR periodic statistics).

Builder-only. Real open-licensed data only (Open Government Licence): Network Rail's historic
delay-attribution file for railway period 2019-20 P5 (one record per train per delay or
cancellation event), its glossary and explanation document, and three ORR periodic tables.

Selection (stated in the record, no judgement about relevance): every record of every incident
that started on 9 August 2019 and either carries incident reason XK or has responsible manager
METR. Values are copied unchanged; the record computes no totals (the agent does) other than
the size of the selection, which it states untagged as a count made for this record. Incidents
also become NETWORK-RAIL-CONTROL control-log rows (one per incident).
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from datetime import date, timedelta
from typing import Any

from fi_docbuild import LABEL_REAL, Artifact, FiDocBuild
from fi_real_common import (
    BUILDER,
    FiInputs,
    TextDoc,
    bst_to_utc,
    csv_bytes,
    data_ref,
    extract_quote_ref,
    gz_text,
    require,
    tagged,
    utc_z,
    wrap,
    xlsx_sheets,
)
from fi_sources import NR_ATTRIBUTION, ORR_ATTRIBUTION, SOURCES

DOC_ID = "R11"
TITLE = (
    "Rail performance records, 9 August 2019: delay attribution and periodic statistics"
)
ROOM_ID = "NETWORK-RAIL-CONTROL"
DAY_PREFIX = "09/08/2019"
SELECT_REASON = "XK"
SELECT_MANAGER = "METR"

F_EVENTS = "R11_networkrail_delay_records_selected_incidents.csv"
F_INCIDENTS = "R11_networkrail_incidents_selected.csv"
F_CODES = "R11_networkrail_glossary_codes_used.csv"
F_ORR_3124 = "R11_orr_table3124_trains_planned_and_cancellations_P03-P07.csv"
F_ORR_3157A = "R11_orr_table3157a_severely_disrupted_days_great_britain.csv"
F_ORR_3157B = "R11_orr_table3157b_severely_disrupted_days_by_sub_operator.csv"

#: Network Rail columns kept for the per-record file (names and values as published).
EVENT_COLS = [
    "incident_number",
    "origin_departure_date",
    "trust_train_id",
    "toc_code",
    "unit_class",
    "traction_type",
    "applicable_timetable_flag",
    "planned_origin_location_code",
    "planned_origin_gbtt_datetime",
    "planned_dest_location_code",
    "planned_dest_gbtt_datetime",
    "event_type",
    "start_stanox",
    "end_stanox",
    "event_datetime",
    "pfpi_minutes",
    "non_pfpi_minutes",
    "react_reason",
]
#: Incident-level columns (constant within an incident; checked).
INCIDENT_COLS = [
    "incident_number",
    "incident_create_date",
    "incident_start_datetime",
    "incident_end_datetime",
    "section_code",
    "nr_location_manager",
    "resp_manager",
    "incident_reason",
    "attribution_status",
    "incident_equipment",
    "incident_description",
    "incident_resp_train",
    "financial_year_period",
]
NR_HEADER_LEN = 40

GLOSSARY_SHEETS = {
    "event": "Performance Event Code",
    "reason": "Incident Reason",
    "react": "Reactionary Reason Code",
    "manager": "Responsible Manager",
    "operator": "Operator Name",
    "stanox": "Stanox Codes",
    "periods": "Period Dates",
}


# ---------------------------------------------------------------------------------------------
# Network Rail records
# ---------------------------------------------------------------------------------------------


def selected(row: dict[str, str]) -> bool:
    return row["incident_start_datetime"].startswith(DAY_PREFIX) and (
        row["incident_reason"] == SELECT_REASON or row["resp_manager"] == SELECT_MANAGER
    )


def nr_rows(inputs: FiInputs) -> tuple[list[str], list[dict[str, str]]]:
    """Header and the selected records, in file order."""
    text = gz_text(inputs.real_bytes("nr_delays_p05"))
    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = list(reader.fieldnames or [])
    require(
        len(header) == NR_HEADER_LEN, f"Network Rail header has {len(header)} columns"
    )
    require(
        set(EVENT_COLS + INCIDENT_COLS) <= set(header), "Network Rail columns changed"
    )
    rows = [row for row in reader if selected(row)]
    require(len(rows) > 0, "no Network Rail records selected")
    return header, rows


def slice_lines(data: bytes) -> bytes:
    """The raw-mirror slice: header plus the selected lines, unchanged (used by fi_sync_raw)."""
    text = gz_text(data)
    lines = text.splitlines(keepends=True)
    header = next(csv.reader([lines[0]]))
    keep = [lines[0]]
    for line in lines[1:]:
        values = next(csv.reader([line]))
        if selected(dict(zip(header, values, strict=True))):
            keep.append(line)
    return "".join(keep).encode("utf-8")


def incidents_of(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_number: dict[str, dict[str, str]] = {}
    for row in rows:
        fields = {c: row[c] for c in INCIDENT_COLS}
        known = by_number.setdefault(row["incident_number"], fields)
        require(
            known == fields, f"incident {row['incident_number']}: fields differ by row"
        )
    return sorted(
        by_number.values(),
        key=lambda i: (nr_datetime(i["incident_start_datetime"]), i["incident_number"]),
    )


def nr_datetime(text: str) -> tuple[str, str]:
    """'dd/mm/yyyy HH:MM' -> ('YYYY-MM-DD', 'HH:MM')."""
    day, clock = text.split(" ")
    dd, mm, yyyy = day.split("/")
    return f"{yyyy}-{mm}-{dd}", clock


# ---------------------------------------------------------------------------------------------
# Glossary (workbook from .context, or the mirror extract)
# ---------------------------------------------------------------------------------------------


def glossary(inputs: FiInputs) -> dict[str, list[dict[str, str]]]:
    data = inputs.real_bytes("nr_glossary")
    if data[:2] == b"PK":
        sheets = xlsx_sheets(data)
        return {name: sheets[name] for name in GLOSSARY_SHEETS.values()}
    extract = json.loads(data.decode("utf-8"))
    require(set(extract) == set(GLOSSARY_SHEETS.values()), "glossary extract sheets")
    return extract


def needed_codes(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    incidents = incidents_of(rows)
    stanox = set()
    for row in rows:
        for col in (
            "start_stanox",
            "end_stanox",
            "planned_origin_location_code",
            "planned_dest_location_code",
        ):
            if row[col]:
                stanox.add(row[col])
    for inc in incidents:
        stanox.update(x for x in inc["section_code"].split(":") if x)
    return {
        "reason": {i["incident_reason"] for i in incidents},
        "react": {r["react_reason"] for r in rows if r["react_reason"]},
        "manager": {i["resp_manager"] for i in incidents},
        "operator": {r["toc_code"] for r in rows if r["toc_code"]},
        "stanox": stanox,
    }


def select_glossary(
    sheets: dict[str, list[dict[str, str]]], needed: dict[str, set[str]]
) -> dict[str, list[dict[str, str]]]:
    """The glossary rows R11 uses (idempotent: applying it to its own output changes nothing)."""
    key_column = {
        "reason": "B",
        "react": "A",
        "manager": "A",
        "operator": "A",
        "stanox": "A",
    }
    out: dict[str, list[dict[str, str]]] = {}
    for kind, sheet in GLOSSARY_SHEETS.items():
        rows = sheets[sheet]
        if kind in ("event", "periods"):
            out[sheet] = rows
            continue
        column = key_column[kind]
        out[sheet] = [rows[0]] + [r for r in rows[1:] if r.get(column) in needed[kind]]
    return out


def glossary_tables(
    sheets: dict[str, list[dict[str, str]]], needed: dict[str, set[str]]
) -> dict[str, dict[str, dict[str, str]]]:
    used = select_glossary(sheets, needed)
    tables: dict[str, dict[str, dict[str, str]]] = {}
    tables["event"] = {
        r["A"]: {"group": r.get("B", ""), "name": r.get("C", "")}
        for r in used["Performance Event Code"][1:]
        if r.get("A") and r.get("B")
    }
    tables["reason"] = {
        r["B"]: {
            "name": r.get("C", ""),
            "description": r.get("E", ""),
            "category": r.get("D", ""),
        }
        for r in used["Incident Reason"][1:]
    }
    tables["react"] = {
        r["A"]: {"name": r.get("C", ""), "description": r.get("B", "")}
        for r in used["Reactionary Reason Code"][1:]
    }
    tables["manager"] = {
        r["A"]: {
            "name": r.get("B", "").strip(),
            "organisation": r.get("D", "").strip(),
        }
        for r in used["Responsible Manager"][1:]
    }
    tables["operator"] = {
        r["A"]: {"name": r.get("B", "")} for r in used["Operator Name"][1:]
    }
    tables["stanox"] = {
        r["A"]: {"name": r.get("B", ""), "crs": r.get("C", ""), "route": r.get("D", "")}
        for r in used["Stanox Codes"][1:]
    }
    return tables


def period_end_dates(
    sheets: dict[str, list[dict[str, str]]], year: str
) -> dict[int, date]:
    rows = sheets["Period Dates"]
    year_col = next(
        (c for r in rows for c, v in r.items() if v == f"YEAR {year}"), None
    )
    require(year_col is not None, f"no period dates for {year}")
    start = ord(year_col) - ord("A")
    block = [chr(ord("A") + start + k) for k in range(5)]
    labels = next(r for r in rows if any(r.get(c) == "Date" for c in block))
    date_col = next(c for c in block if labels.get(c) == "Date")
    out = {}
    for row in rows:
        name = row.get("A", "")
        if name.startswith("Period ") and row.get(date_col, "").isdigit():
            out[int(name.split()[1])] = date(1899, 12, 30) + timedelta(
                days=int(row[date_col])
            )
    return out


def glossary_extract(inputs: FiInputs) -> bytes:
    """The mirror extract of the glossary (used by fi_sync_raw)."""
    _, rows = nr_rows(inputs)
    data = inputs.real_bytes("nr_glossary")
    require(
        data[:2] == b"PK", "the glossary extract is made from the original workbook"
    )
    sheets = xlsx_sheets(data)
    used = select_glossary(
        {name: sheets[name] for name in GLOSSARY_SHEETS.values()}, needed_codes(rows)
    )
    return (
        json.dumps(used, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    ).encode()


# ---------------------------------------------------------------------------------------------
# ORR tables
# ---------------------------------------------------------------------------------------------


def orr_rows(inputs: FiInputs, key: str) -> tuple[bytes, list[dict[str, str]]]:
    data = inputs.real_bytes(key)
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")))
    require(len(rows) > 0, f"{key}: no rows")
    return data, rows


# ---------------------------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------------------------

#: Network Rail explanation document: quotations used in Part A (checked against the extract).
EXPLANATION_QUOTES = {
    "pss": "The file attached is a standard data extract from our Performance System Strategy "
    "(PSS) database",
    "attributed": "The information within the file contains all “attributed” delays to "
    "passenger train services in line with the guidance in the Delay Attribution Guide.",
    "summing": "The data contains both delay and cancellation events (denoted by the "
    "performance event code) and a user should be careful when summing delay minutes (pfpi "
    "minutes) to exclude cancellation events.",
    "investigated": "It is possible that the detailed reasons for some of the delays in this "
    "file are still being investigated and until this is complete the responsibility for the "
    "delay is still not finalised (see attribution status).",
    "remapped": "Delay data is remapped to reflect the franchise mapping at the time of the "
    "data extraction (in this case May 2021).",
    "trainid": "trainids are unique within a railway period but not within a year",
    "unvalidated": "Train schedule type / traction type/ trailing load / unit class – these "
    "aren’t mandated or validated fields within PSS",
    "incident_number": "Incident number – the TRUST DA incident number (not unique without "
    "the create date)",
    "create_date": "Incident create date – the date the incident was entered into the system",
    "start_end": "Incident start/end date – the date the system has the incident live (this "
    "is not the length of the incident on the ground)",
    "resp": "Responsible Manager – who within the industry is responsible for the delay – all "
    "delays have responsibility for performance improvement purposes",
    "reason": "Incident Reason – the Delay Attribution Guide cause code for the incident",
    "equipment": "Incident equipment – internal free form information",
    "description": "Incident description – short description of the incident for internal use",
    "react": "If no code the delay is primary (ie the delay is at the site of the incident) if "
    "reactionary the delay is a later consequence of that incident",
    "event_code": "A and M denote delays, C, D, O, P, S and F are cancellations … C – is a "
    "full cancelletion, D is a diversion, F is a failure to stop, S is a scheduled "
    "cancellation and O/P are part cancellations",
    "stanox": "Start/end stanox – the location of the delay (not the incident)",
    "event_time": "Event Datetime – the time the train encountered the delay",
    "pfpi": "Pfpi minutes – the size of the delay …. Note if the train is cancelled "
    "(performance event code) a deemed delay minute is generated for internal usage in these "
    "circumstances the train hasn’t been delayed and including this delay in any calculation of "
    "delay is misleading.",
    "applicable": "Applicable timetable flag – if N the train is not in official performance "
    "records as it is a short term replacement of a train plan – normally a reinstatement of "
    "part of a cancelled service",
}


def p(label: str, text: str) -> list[str]:
    return wrap(text, first=f"{label:<4}", indent="    ")


def cont(text: str) -> list[str]:
    return wrap(text, first="    ", indent="    ")


def _code_name(table: dict[str, dict[str, str]], code: str, field: str = "name") -> str:
    entry = table.get(code)
    return (
        entry[field]
        if entry and entry.get(field)
        else "(not in the glossary edition held)"
    )


def _section_names(section: str, stanox: dict[str, dict[str, str]]) -> str:
    return " : ".join(_code_name(stanox, x) for x in section.split(":") if x)


def build(inputs: FiInputs) -> FiDocBuild:
    doc = TextDoc(DOC_ID)
    build = FiDocBuild(
        doc_id=DOC_ID,
        title=TITLE,
        owner="Network Rail (delay attribution records and glossary); Office of Rail and Road "
        "(periodic statistics)",
        category="transport_records",
        record_type="real Network Rail delay-attribution records for selected incidents of "
        "9 August 2019 with the publisher's code glossary, and ORR periodic tables of trains "
        "planned, cancellations and severely disrupted days",
        construction="",
        text=doc,
        label=LABEL_REAL,
        status_scope="Nothing in this record is synthesised; it computes no totals other "
        "than the size of the selection described in Part A.",
        party_aliases=[
            "Network Rail",
            "rail",
            "ORR",
            "Office of Rail and Road",
            "train operator",
        ],
    )
    header, rows = nr_rows(inputs)
    incidents = incidents_of(rows)
    sheets = glossary(inputs)
    tables = glossary_tables(sheets, needed_codes(rows))
    periods = period_end_dates(sheets, "2019/20")
    require(periods.get(5) == date(2019, 8, 17), "period 5 end date")
    require(set(r["financial_year_period"] for r in rows) == {"2019/20_P05"}, "period")

    build.header(
        "Network Rail Infrastructure Ltd (historic delay attribution data, PSS extract; "
        "glossary; explanation document); Office of Rail and Road (data portal periodic tables, "
        "source Network Rail)",
        wrap(
            "Clock reference: Network Rail date-times are written dd/mm/yyyy HH:MM (dates "
            "dd-Mon-yy); the file and its explanation document state no time zone. ORR tables "
            "are by railway period (four-week periods; Part B gives Network Rail's period end "
            "dates)."
        ),
    )

    # ---- Part A ------------------------------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part A heading",
        "PART A — NETWORK RAIL DELAY ATTRIBUTION RECORDS, RAILWAY PERIOD 2019-20 P5 (real "
        "extract)",
    )
    spec = SOURCES["nr_delays_p05"]
    seg = doc.segment(
        "A1 Source, licence, selection rule and file description",
        "reported",
        "script",
        [
            data_ref("nr_delays_p05", "header and selected records"),
            extract_quote_ref(
                inputs, "nr_explanation", "opening paragraph", EXPLANATION_QUOTES["pss"]
            ),
            extract_quote_ref(
                inputs,
                "nr_explanation",
                "opening paragraph",
                EXPLANATION_QUOTES["attributed"],
            ),
        ],
        "Records selected by rule; columns selected; values unchanged.",
    )
    by_reason = Counter(i["incident_reason"] for i in incidents)
    by_manager = Counter(
        i["incident_number"] for i in incidents if i["resp_manager"] == SELECT_MANAGER
    )
    doc.add(
        seg,
        *p(
            "A1",
            "Source: Network Rail, 'All delays 2019-20 P5' historic delay attribution file "
            f"({spec['url']}; zip entry dated 2020-03-26); retrieved 2026-10-20. Licence: Open "
            f"Government Licence v3.0. {NR_ATTRIBUTION} Network Rail describes the file: "
            f'"{EXPLANATION_QUOTES["pss"]}"; "{EXPLANATION_QUOTES["attributed"]}"',
        ),
        *cont(
            "Selection made for this record: every record of every incident whose "
            "incident_start_datetime falls on 09/08/2019 and whose incident_reason is "
            f"{SELECT_REASON} or whose resp_manager is {SELECT_MANAGER} (codes decoded in Part "
            f"B). Size of this selection: {len(incidents)} incidents ({by_reason[SELECT_REASON]} "
            f"with reason {SELECT_REASON}; {len(by_manager)} with responsible manager "
            f"{SELECT_MANAGER}) and {len(rows)} records, counted for this record. No other "
            "incident of the period is included.",
        ),
        *cont(
            f"File {F_EVENTS} [reported]: one row per record (one train, one delay or "
            f"cancellation event), in the publisher's order, {len(EVENT_COLS)} of the "
            f"{len(header)} published columns: {', '.join(EVENT_COLS)}. File {F_INCIDENTS} "
            "[reported]: one row per "
            f"incident with the incident-level columns ({', '.join(INCIDENT_COLS)}), which "
            "are the same on every record of an incident. Values are as published (blank "
            "where the publisher's cell is blank).",
        ),
    )
    seg = doc.segment(
        "A2 Publisher's explanation of the columns (quotations)",
        "reported",
        "quotation",
        [
            extract_quote_ref(inputs, "nr_explanation", f"column note {key}", quote)
            for key, quote in EXPLANATION_QUOTES.items()
            if key not in ("pss", "attributed")
        ],
    )
    doc.add(
        seg,
        *p(
            "A2",
            "Network Rail, 'Explanation document: Historic attributed delays' (May 2021), "
            "quoted:",
        ),
        *(
            line
            for key, quote in EXPLANATION_QUOTES.items()
            if key not in ("pss", "attributed")
            for line in wrap(f'"{quote}"', first="    ", indent="      ")
        ),
    )
    doc.blank()
    doc.frame(
        "A3 incident list heading",
        *p(
            "A3",
            "Incidents included, as recorded (one entry per incident, ordered by "
            "incident_start_datetime; names of codes from the glossary in Part B):",
        ),
    )
    stanox = tables["stanox"]
    for n, inc in enumerate(incidents, 1):
        seg = doc.segment(
            f"A3.{n} incident {inc['incident_number']}",
            "reported",
            "script",
            [data_ref("nr_delays_p05", f"incident {inc['incident_number']} fields")],
            "Incident-level fields as recorded; code names looked up in the glossary.",
        )
        reason = inc["incident_reason"]
        manager = inc["resp_manager"]
        lines = tagged(
            f"incident {inc['incident_number']} | created {inc['incident_create_date']} | "
            f"start {inc['incident_start_datetime']} | end {inc['incident_end_datetime']} | "
            f"reason {reason} ({_code_name(tables['reason'], reason)}) | resp_manager "
            f"{manager} ({_code_name(tables['manager'], manager)}) | section "
            f"{inc['section_code']} ({_section_names(inc['section_code'], stanox)}) | "
            f"description '{inc['incident_description'].strip()}' | equipment "
            f"'{inc['incident_equipment'].strip() or '(blank)'}' | responsible train "
            f"'{inc['incident_resp_train'] or '(blank)'}' | {inc['attribution_status'].strip()}",
            "reported",
            first=f"{f'A3.{n}':<6}",
            indent="      ",
        )
        doc.add(seg, *lines)
        start_day, start_clock = nr_datetime(inc["incident_start_datetime"])
        index = bst_to_utc(start_day, start_clock)
        org = (tables["manager"].get(manager) or {}).get("organisation") or manager
        build.control_rows.append(
            {
                "kind": "control",
                "entry_id": f"R11-NR-{inc['incident_number']}",
                "evidence_id": DOC_ID,
                "room_id": ROOM_ID,
                "recorded_time": f"incident_start_datetime {inc['incident_start_datetime']} "
                f"(incident_create_date {inc['incident_create_date']})",
                "clock_basis": "dd/mm/yyyy HH:MM as held in Network Rail's PSS extract; no "
                "time zone is stated by the publisher; the index reads it as UK local time "
                "(BST, UTC+01:00). The publisher describes incident start/end as the time the "
                "system has the incident live, not its length on the ground.",
                "index_time_utc": utc_z(index),
                "index_uncertainty_s": 60,
                "from": "Network Rail (TRUST delay attribution)",
                "to": f"responsible manager {manager} ({org})",
                "channel": "TRUST delay-attribution incident record",
                "text": " ".join(lines).replace("  ", " ").strip(),
                "value_status": "reported",
                "provenance": {
                    "source_id": "nr_delays_p05",
                    "file": SOURCES["nr_delays_p05"]["rel"],
                    "sha256": SOURCES["nr_delays_p05"]["sha256"],
                    "incident": inc,
                    "glossary": {
                        "source_id": "nr_glossary",
                        "reason": tables["reason"].get(reason),
                        "manager": tables["manager"].get(manager),
                    },
                    "doc_lines_segment": f"A3.{n}",
                },
            }
        )

    # ---- Part B: glossary ----------------------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part B heading",
        "PART B — CODES USED, FROM NETWORK RAIL'S HISTORIC DELAY ATTRIBUTION GLOSSARY (real "
        "extract)",
    )
    seg = doc.segment(
        "B1 Glossary source and performance event codes",
        "reported",
        "script",
        [data_ref("nr_glossary", "sheet Performance Event Code (all rows)")],
        "Rows copied; cell text unchanged.",
    )
    doc.add(
        seg,
        *p(
            "B1",
            "Source: Network Rail 'Historic Delay Attribution Glossary' workbook (August 2021 "
            "edition, published with the historic delay files; Open Government Licence; "
            "(c) Copyright Network Rail 2021). It is a later edition than the 2019 records; a "
            "code missing from it is marked '(not in the glossary edition held)'. File "
            f"{F_CODES} lists every code of these records with its glossary entry, including "
            "STANOX location codes.",
        ),
        *cont("Performance event codes (event_type), as listed:"),
        *(
            f"    {code} | {entry['group']} | {entry['name']} [reported]"
            for code, entry in sorted(tables["event"].items())
        ),
    )
    seg = doc.segment(
        "B2 Incident reason, reactionary reason, responsible manager and operator codes",
        "reported",
        "script",
        [
            data_ref(
                "nr_glossary",
                "sheets Incident Reason, Reactionary Reason Code, Responsible Manager, "
                "Operator Name (rows of the codes used)",
            )
        ],
        "Rows of the codes occurring in the selected records; cell text unchanged.",
    )
    needed = needed_codes(rows)
    lines: list[str] = []
    for code in sorted(needed["reason"]):
        entry = tables["reason"].get(code, {})
        lines += tagged(
            f"incident_reason {code} | {entry.get('name', '')} | "
            f"{entry.get('description', '(not in the glossary edition held)')}",
            "reported",
        )
    for code in sorted(needed["react"]):
        entry = tables["react"].get(code, {})
        lines += tagged(
            f"react_reason {code} | {entry.get('name', '')} | "
            f"{entry.get('description', '(not in the glossary edition held)')}",
            "reported",
        )
    for code in sorted(needed["manager"]):
        entry = tables["manager"].get(code, {})
        lines += tagged(
            f"resp_manager {code} | {entry.get('name', '(not in the glossary edition held)')}"
            f" | {entry.get('organisation', '')}",
            "reported",
        )
    for code in sorted(needed["operator"]):
        lines += tagged(
            f"toc_code {code} | {_code_name(tables['operator'], code)}", "reported"
        )
    doc.add(seg, *p("B2", "Other codes of these records, as listed:"), *lines)
    seg = doc.segment(
        "B3 Railway period end dates 2019/20",
        "reported",
        "script",
        [data_ref("nr_glossary", "sheet Period Dates, YEAR 2019/20 Date column")],
        "Spreadsheet date serials converted to calendar dates (1899-12-30 epoch).",
    )
    doc.add(
        seg,
        *p(
            "B3",
            "Network Rail period end dates, year 2019/20 (sheet 'Period Dates'): "
            + "; ".join(
                f"Period {n} ends {periods[n].isoformat()}" for n in range(3, 8)
            )
            + " [reported].",
        ),
    )

    # ---- Part C: ORR ---------------------------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part C heading",
        "PART C — ORR PERIODIC PASSENGER PERFORMANCE STATISTICS (real extract)",
    )
    t3124, r3124 = orr_rows(inputs, "orr_3124")
    t3157a, r3157a = orr_rows(inputs, "orr_3157a")
    t3157b, r3157b = orr_rows(inputs, "orr_3157b")
    cols3124 = list(r3124[0])
    seg = doc.segment(
        "C1 ORR Table 3124 description and Great Britain / GTR rows",
        "reported",
        "script",
        [
            data_ref(
                "orr_3124",
                "all rows; Great Britain and Greater Thameslink Railway listed",
            )
        ],
        "Rows copied; values unchanged.",
    )
    shown = [
        r
        for r in r3124
        if r["national or operator"] in ("Great Britain", "Greater Thameslink Railway")
    ]
    doc.add(
        seg,
        *p(
            "C1",
            f"Source: {SOURCES['orr_3124']['title']} (ORR data portal, passenger rail performance); "
            f"retrieved 2026-10-20. Licence: Open Government Licence v3.0. {ORR_ATTRIBUTION} "
            f"File {F_ORR_3124} holds all {len(r3124)} rows as retrieved (columns: "
            f"{'; '.join(cols3124)}). Periods are railway four-week periods; the table is not "
            "by day. Rows for Great Britain and Greater Thameslink Railway, as published "
            "(time period | trains planned | part cancelled | full cancelled | cancellation "
            "number | periodic cancellations percentage):",
        ),
        *(
            line
            for r in shown
            for line in tagged(
                f"{r['time period']} | {r['national or operator']} | "
                f"{r['number of trains planned']} | {r['number of trains part cancelled']} | "
                f"{r['number of trains full cancelled']} | {r['cancellation number']} | "
                f"{r['periodic cancellations percentage']}",
                "reported",
                first="    ",
                indent="      ",
            )
        ),
    )
    seg = doc.segment(
        "C2 ORR Tables 3157a and 3157b",
        "reported",
        "script",
        [
            data_ref("orr_3157a", "all rows"),
            data_ref("orr_3157b", "all rows; 2019-20 Period 05 rows listed"),
        ],
        "Rows copied; values unchanged.",
    )
    p05 = [r for r in r3157b if r["Time Period"] == "Apr 2019 to Mar 2020 (Period 05)"]
    doc.add(
        seg,
        *p(
            "C2",
            f"Source: {SOURCES['orr_3157a']['title']} and {SOURCES['orr_3157b']['title']} "
            "(ORR data portal; Open Government Licence v3.0). Files "
            f"{F_ORR_3157A} ({len(r3157a)} rows) and {F_ORR_3157B} ({len(r3157b)} rows) hold "
            "the rows as retrieved. Table 3157a (time period | operator | number of severely "
            "disrupted days):",
        ),
        *(
            f"    {r['Time Period']} | {r['Operator']} | {r['Number of severely disrupted days']}"
            " [reported]"
            for r in r3157a
        ),
        *cont(
            "Table 3157b rows for Apr 2019 to Mar 2020 (Period 05) (operator | sub operator | "
            "number of severely disrupted days):"
        ),
        *(
            f"    {r['Operator']} | {r['Sub operator']} | "
            f"{r['Number of severely disrupted days']} [reported]"
            for r in p05
        ),
    )

    # ---- Part D: notes -------------------------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part D: what the record does not contain",
        "PART D — NOTES",
        *p(
            "D1",
            "This record holds no train running (signalling or timetable performance) data, "
            "no on-train or fleet records, and no records of incidents outside the selection "
            "rule in A1.",
        ),
    )

    build.construction = (
        "Part A copies, for every incident starting on 09/08/2019 with incident reason XK or "
        "responsible manager METR, all of its Network Rail records (18 of 40 columns per record; "
        "13 incident-level columns per incident, checked constant within each incident) and "
        "quotes the publisher's explanation document (checked against the committed text "
        "extract). Part B copies the glossary rows of the codes used (event codes in full). Part "
        "C copies three ORR periodic tables. No totals or other derived values are computed."
    )
    build.notes = {
        "selection": {
            "rule": f"incident_start_datetime on {DAY_PREFIX} and (incident_reason == "
            f"{SELECT_REASON} or resp_manager == {SELECT_MANAGER})",
            "incidents": len(incidents),
            "records": len(rows),
        },
    }

    # ---- Artifacts -----------------------------------------------------------------------------
    nr_input = [
        {
            "source_id": "nr_delays_p05",
            "file": SOURCES["nr_delays_p05"]["rel"],
            "sha256": SOURCES["nr_delays_p05"]["sha256"],
        }
    ]
    build.add_artifact(
        Artifact(
            name=F_EVENTS,
            media_type="text/csv",
            description="Network Rail delay-attribution records of the selected incidents "
            "(one row per train per delay or cancellation event; publisher's column names "
            "and values).",
            data=csv_bytes(EVENT_COLS, [[r[c] for c in EVENT_COLS] for r in rows]),
            provenance={
                "extraction_method": "script",
                "builder": BUILDER,
                "inputs": nr_input,
                "transformation": "rows selected by rule (A1), 18 columns kept, file order "
                "kept, values unchanged",
            },
        )
    )
    build.add_artifact(
        Artifact(
            name=F_INCIDENTS,
            media_type="text/csv",
            description="One row per selected Network Rail incident with its incident-level "
            "columns as published.",
            data=csv_bytes(
                INCIDENT_COLS, [[i[c] for c in INCIDENT_COLS] for i in incidents]
            ),
            provenance={
                "extraction_method": "script",
                "builder": BUILDER,
                "inputs": nr_input,
                "transformation": "incident-level columns of the selected records, one row per "
                "incident (checked identical on every record), sorted by start time then number",
            },
        )
    )
    code_rows: list[list[str]] = []
    for code, entry in sorted(tables["event"].items()):
        code_rows.append(["event_type", code, entry["name"], entry["group"]])
    for kind, column in (
        ("reason", "incident_reason"),
        ("react", "react_reason"),
        ("manager", "resp_manager"),
        ("operator", "toc_code"),
        ("stanox", "stanox"),
    ):
        for code in sorted(needed[kind]):
            entry = tables[kind].get(code)
            if entry is None:
                code_rows.append(
                    [column, code, "(not in the glossary edition held)", ""]
                )
                continue
            if kind == "reason":
                extra = f"{entry['category']} | {entry['description']}"
            elif kind == "react":
                extra = entry["description"]
            elif kind == "manager":
                extra = entry["organisation"]
            elif kind == "stanox":
                extra = f"CRS {entry['crs'] or '(blank)'} | route {entry['route']}"
            else:
                extra = ""
            code_rows.append([column, code, entry["name"], extra])
    build.add_artifact(
        Artifact(
            name=F_CODES,
            media_type="text/csv",
            description="Glossary entries (Network Rail, August 2021 edition) of every code "
            "in the selected records: event types, incident and reactionary reasons, "
            "responsible managers, operators and STANOX locations.",
            data=csv_bytes(["code_type", "code", "name", "details"], code_rows),
            provenance={
                "extraction_method": "script",
                "builder": BUILDER,
                "inputs": [
                    {
                        "source_id": "nr_glossary",
                        "file": SOURCES["nr_glossary"]["rel"],
                        "sha256": SOURCES["nr_glossary"]["sha256"],
                    }
                ],
                "transformation": "glossary rows of the codes used; cell text unchanged "
                "(responsible manager names stripped of trailing spaces)",
            },
        )
    )
    for name, key, data in (
        (F_ORR_3124, "orr_3124", t3124),
        (F_ORR_3157A, "orr_3157a", t3157a),
        (F_ORR_3157B, "orr_3157b", t3157b),
    ):
        build.add_artifact(
            Artifact(
                name=name,
                media_type="text/csv",
                description=f"{SOURCES[key]['title']}: all rows as retrieved.",
                data=data,
                provenance={
                    "extraction_method": "script",
                    "builder": BUILDER,
                    "inputs": [
                        {
                            "source_id": key,
                            "file": SOURCES[key]["rel"],
                            "sha256": SOURCES[key]["sha256"],
                        }
                    ],
                    "transformation": "byte-identical copy",
                },
            )
        )
    return build


CONTROL_LOG_CONTRIB: list[dict[str, Any]] = [
    {
        "room_id": ROOM_ID,
        "title_proposal": "Network Rail: TRUST delay-attribution incident records, 9 August 2019",
        "owner_proposal": "Network Rail (historic delay attribution data)",
        "evidence_ids": [DOC_ID],
        "clock_note_proposal": "R11 rows — incident_start_datetime as held in Network Rail's PSS "
        "extract (dd/mm/yyyy HH:MM, no zone stated by the publisher; read as BST, UTC+01:00, "
        "for the index).",
        "source_note_proposal": "R11: one entry per selected Network Rail incident (real "
        "extract; Open Government Licence).",
    }
]
