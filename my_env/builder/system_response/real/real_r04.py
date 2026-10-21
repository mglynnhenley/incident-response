"""R04 — weather observations, warnings and reported lightning records.

Builder-only. Real extracts: Iowa Environmental Mesonet METAR reports (public domain) and the
Met Office warnings page captured by the Internet Archive (OGL). Reported material: the ESO's
Appendix M answer on weather warnings and lightning risk, the Appendix A table of MeteoGroup
lightning-risk e-mails, and the values displayed in the MeteoGroup lightning screenshots printed
in the ESO report (Figure 4) and the NGET report (Appendix C, Figure 3.1.1). The MeteoGroup
detection records themselves are not public and are not part of this record.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from real_common import (
    TextDoc,
    csv_bytes,
    data_ref,
    doc_quote_ref,
    figure_ref,
    pdf_ref,
    require,
    table_ref,
    tagged,
    wrap,
)
from real_docbuild import Artifact, DocBuild
from real_sources import SOURCES

DOC_ID = "R04"
TITLE = "Weather observations, warnings and lightning records, 9 August 2019"
STATIONS = ("EGGW", "EGSC", "EGTC")
STATION_NAMES = {"EGGW": "London Luton", "EGSC": "Cambridge", "EGTC": "Cranfield"}
WINDOW = ("2019-08-09 14:50", "2019-08-09 17:20")  # inclusive, UTC ('valid' column)

F_METAR = "R04_iem_metar_EGGW_EGSC_EGTC_20190809_1450-1720Z.csv"
F_WARN = "R04_metoffice_warnings_capture_20190809T160223Z.csv"
F_LIGHT = "R04_lightning_information_as_published.csv"
LIGHTNING_FORECAST = "APP-p10-tbl-lightning-forecast.csv"
APP_P25 = "APP-p25-map-lightning-meteogroup.csv"
ESO_FIG4 = "ESO-p16-fig4.csv"


def p(label: str, text: str) -> list[str]:
    return wrap(text, first=f"{label:<3}", indent="    ")


def cont(text: str) -> list[str]:
    return wrap(text, first="    ", indent="    ")


# ---------------------------------------------------------------------------------------------
# METAR
# ---------------------------------------------------------------------------------------------


def metar_lines(inputs) -> tuple[bytes, list[dict[str, str]]]:
    raw = inputs.real_text("iem_metar")
    lines = raw.splitlines(keepends=True)
    require(lines[0].startswith("station,valid,lon,lat,metar,"), "IEM header changed")
    keep = [lines[0]]
    rows = []
    for line in lines[1:]:
        rec = next(csv.DictReader(io.StringIO(lines[0] + line)))
        if rec["station"] in STATIONS and WINDOW[0] <= rec["valid"] <= WINDOW[1]:
            keep.append(line)
            rows.append(rec)
    rows.sort(key=lambda r: (STATIONS.index(r["station"]), r["valid"]))
    require(len(rows) == 16, f"METAR rows {len(rows)} != 16")
    for rec in rows:
        group = rec["metar"].split()[1]
        day, hhmm = group[:2], group[2:6]
        require(group.endswith("Z") and day == "09", f"METAR time group {group}")
        require(
            rec["valid"][11:13] + rec["valid"][14:16] == hhmm, f"valid vs METAR {rec}"
        )
    return "".join(keep).encode("utf-8"), rows


# ---------------------------------------------------------------------------------------------
# Met Office warnings page (text extracted from the archived HTML)
# ---------------------------------------------------------------------------------------------

REGION_HEADINGS = (
    "Central, Tayside & Fife",
    "East Midlands",
    "East of England",
    "Grampian",
    "Highlands & Eilean Siar",
    "London & South East England",
    "North East England",
    "North West England",
    "Northern Ireland",
    "Orkney & Shetland",
    "SW Scotland, Lothian Borders",
    "South West England",
    "Strathclyde",
    "Wales",
    "West Midlands",
    "Yorkshire & Humber",
)


def parse_warnings(text: str) -> tuple[list[dict[str, Any]], list[str], str]:
    """The four warning detail blocks, the overview lines and the page banner."""
    lines = [line.strip() for line in text.splitlines()]
    banner = "We are experiencing issues. These warnings may be out of date."
    require(banner in lines, "warnings banner missing")
    start = lines.index("Warning overview for UK")
    end = lines.index("Warning details for UK")
    overview = []
    for i in range(start, end):
        if lines[i].startswith("Yellow - "):
            overview.append(f"{lines[i]}: {lines[i + 1]}")
    require(len(overview) == 4, f"overview warnings {overview}")
    blocks = []
    stop = lines.index("Follow warnings on Twitter")
    idx = [
        i
        for i in range(end, stop)
        if lines[i] == "yellow" and lines[i + 1] == "Yellow warning"
    ]
    for n, i in enumerate(idx):
        block_end = idx[n + 1] if n + 1 < len(idx) else stop
        b = lines[i:block_end]
        require(b[5] == "UTC+1", f"warning block layout changed: {b[:9]}")
        when_key = "Issued:" if "Issued:" in b else "Updated:"
        regions_at = b.index("Regions and local authorities affected:")
        areas: dict[str, list[str]] = {}
        current = None
        for item in b[regions_at + 1 :]:
            if not item:
                continue
            if item in REGION_HEADINGS:
                current = item
                areas[current] = []
            else:
                require(current is not None, f"local authority before a region: {item}")
                areas[current].append(item)
        blocks.append(
            {
                "type": b[2],
                "from": f"{b[3]} {b[4]}",
                "to": f"{b[6]} {b[7]}",
                "clock": b[5],
                "headline": b[b.index("Headline") + 1],
                "when_label": when_key[:-1],
                "when": b[b.index(when_key) + 1],
                "reason": b[b.index("Reason for update") + 1]
                if "Reason for update" in b
                else "",
                "details": [
                    b[j]
                    for j in range(
                        b.index("Further details", b.index(when_key)) + 1, regions_at
                    )
                    if b[j]
                    and b[j] != "Warning impact matrix"
                    and not _matrix_word(b[j])
                ],
                "regions": list(areas),
                "east": areas.get("East of England", []),
            }
        )
    require(len(blocks) == 4, f"{len(blocks)} warning blocks")
    return blocks, overview, banner


def _matrix_word(item: str) -> bool:
    return item in {
        "Very",
        "likely",
        "Unlikely",
        "Very low",
        "impact",
        "High",
        "Impact matrix guide",
    }


# ---------------------------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------------------------


def build(inputs) -> DocBuild:
    doc = TextDoc(DOC_ID)
    build = DocBuild(
        doc_id=DOC_ID,
        title=TITLE,
        owner="Iowa Environmental Mesonet (METAR archive); Met Office (warnings page); National "
        "Grid ESO and NGET (reported MeteoGroup lightning information)",
        category="measurement_data",
        record_type="real aerodrome weather reports and archived warning text (real extracts), "
        "with lightning information transcribed from published report tables and figures",
        construction="",
        text=doc,
    )
    build.header(
        "Iowa Environmental Mesonet, Iowa State University (archive of METAR reports from UK "
        "aerodromes); Met Office (UK weather warnings page, Internet Archive capture); National "
        "Grid ESO and National Grid Electricity Transmission (NGET) report material citing "
        "MeteoGroup lightning data",
        wrap(
            "Clock reference: METAR times are UTC (the DDHHMMZ group; the file's valid column is "
            'UTC). Met Office page times are labelled "UTC+1" on the page. Report tables print '
            "times without a zone; the reports give event times in local time (BST, UTC+01:00). "
            "The MeteoGroup screenshots label their times UTC."
        ),
    )
    metar_bytes, metar = metar_lines(inputs)
    warn_text = inputs.real_text("metoffice_warnings_text")
    warnings, overview, banner = parse_warnings(warn_text)

    doc.blank()
    doc.frame(
        "Part A heading",
        "PART A — AERODROME WEATHER REPORTS (METAR), REAL EXTRACT",
    )
    seg = doc.segment(
        "A1 METAR file description: source, licence, selection, columns",
        "measured",
        "script",
        [
            data_ref(
                "iem_metar", "lines for EGGW, EGSC, EGTC with valid 14:50-17:20 UTC"
            )
        ],
        "Lines selected by station and time; copied byte for byte with the header line.",
    )
    coords = {r["station"]: (r["lat"], r["lon"]) for r in metar}
    doc.add(
        seg,
        *p(
            "A1",
            f"File {F_METAR} [measured] — METAR reports from three aerodromes, 14:50 to "
            "17:20 UTC on 9 August 2019.",
        ),
        *cont(
            "Source: Iowa Environmental Mesonet (IEM), Iowa State University, ASOS/METAR archive "
            "request for 2019-08-09 12:00-20:00 UTC with times in UTC; retrieved 2026-10-20. "
            'Licence: public domain (IEM: "The materials found on this website are in the '
            'public domain and may be used freely by anyone for any lawful purpose."). Data '
            "from the Iowa Environmental Mesonet, Iowa State University.",
        ),
        *cont(
            f"Rows: {len(metar)} lines of the downloaded file, copied byte for byte with its "
            "header: every report for stations "
            + ", ".join(
                f"{s} ({STATION_NAMES[s]}; lat {coords[s][0]}, lon {coords[s][1]})"
                for s in STATIONS
            )
            + " whose valid time is 14:50 to 17:20 UTC.",
        ),
        *cont(
            "Columns: station, valid (UTC, YYYY-MM-DD HH:MM), lon, lat (degrees), metar (report "
            "text), wxcodes (present weather), tmpc (air temperature, deg C), sknt (wind speed, "
            "knots), gust (knots), p01m (precipitation, mm); M marks a missing value.",
        ),
    )
    seg = doc.segment(
        "A2 METAR report texts, verbatim",
        "measured",
        "script",
        [data_ref("iem_metar", "metar column of the selected lines")],
        "metar column of each selected line, unchanged.",
    )
    doc.add(
        seg,
        "A2  Report texts (the metar column, verbatim; every report below is [measured]):",
    )
    for station in STATIONS:
        doc.add(seg, f"    {station} ({STATION_NAMES[station]}):")
        doc.add(seg, *(f"    {r['metar']}" for r in metar if r["station"] == station))
    doc.frame(
        "A3 METAR code legend (standard report format)",
        *p(
            "A3",
            "Reading the reports (standard METAR code): DDHHMMZ is day, hour and minute UTC; "
            "AUTO marks an automated report; dddffKT or dddffGggKT is wind direction (degrees), "
            "mean speed and gust (knots), and dddVddd a varying direction; a 4-figure group is "
            "visibility in metres (9999 = 10 km or more); TS thunderstorm, RA rain, SH showers, "
            "a leading - light; RE (as in RETSRA) recent weather, observed since the previous "
            "report but not at report time; FEW, SCT and BKN are cloud amounts with base in "
            "hundreds of feet; CB cumulonimbus, TCU towering cumulus; / marks an element the "
            "automated system did not observe; nn/nn is temperature and dew point (deg C); "
            "Qnnnn is pressure (hPa).",
        ),
    )

    # ---- Part B: Met Office warnings -----------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part B heading",
        "PART B — MET OFFICE WEATHER WARNINGS PAGE, ARCHIVED COPY (REAL EXTRACT)",
    )
    seg = doc.segment(
        "B1 Warnings page capture: source, licence, banner, clock",
        "reported",
        "script",
        [
            data_ref("metoffice_warnings_text", "page banner and day tabs"),
            doc_quote_ref(inputs, "metoffice_warnings_text", "page banner", banner),
        ],
    )
    doc.add(
        seg,
        *p(
            "B1",
            "Source: Met Office UK weather warnings page (www.metoffice.gov.uk/weather/"
            "warnings-and-advice/uk-warnings) as captured by the Internet Archive at "
            "2019-08-09T16:02:23Z (capture time, UTC); text extracted from the captured page; "
            "retrieved 2026-10-20. Licence: Open Government Licence v3.0 (Crown copyright). "
            "Contains public sector information licensed under the Open Government Licence v3.0.",
        ),
        *cont(
            f'Page banner as printed: "{banner}" [reported]. The page\'s day tabs begin with '
            '"Fri 9 Aug"; validity times are labelled "UTC+1" and use "Today" and '
            '"Tomorrow" as printed. Each warning on the page lists regions and their local '
            "authorities; below, local authorities are reproduced for the East of England "
            "region only.",
        ),
    )
    seg = doc.segment(
        "B2 Warning overview as printed",
        "reported",
        "script",
        [
            doc_quote_ref(inputs, "metoffice_warnings_text", "warning overview", line)
            for line in [o.split(": ", 1)[1] for o in overview]
        ],
        "Overview lines: warning heading and its region list, as printed.",
    )
    doc.add(
        seg, "B2  Warning overview for UK, as printed (warning: regions) [reported]:"
    )
    for line in overview:
        doc.add(seg, *wrap(line, first="    ", indent="      "))
    for n, w in enumerate(warnings, 1):
        quotes = [w["headline"], w["when"]] + ([w["reason"]] if w["reason"] else [])
        seg = doc.segment(
            f"B3.{n} Warning detail block: {w['type']} {w['from']} to {w['to']}",
            "reported",
            "script",
            [
                doc_quote_ref(
                    inputs, "metoffice_warnings_text", f"warning {n} detail", q
                )
                for q in quotes
            ],
            "Fields of one warning detail block as printed; local authorities are listed for "
            "the East of England region only.",
        )
        doc.add(
            seg,
            *wrap(
                f"Yellow warning — {w['type']}: from {w['from']} to {w['to']} ({w['clock']}); "
                f"{w['when_label'].lower()} {w['when']} [reported].",
                first=f"B3.{n}",
                indent="    ",
            ),
            *cont(f'Headline: "{w["headline"]}"'),
            *(cont(f'Reason for update: "{w["reason"]}"') if w["reason"] else []),
            *cont("Regions listed: " + "; ".join(w["regions"]) + "."),
            *cont(
                "Local authorities listed under East of England: "
                + (", ".join(w["east"]) if w["east"] else "none (region not listed)")
                + "."
            ),
        )
    rain = next(
        w for w in warnings if w["type"] == "Rain" and w["from"].endswith("Today")
    )
    showers = next(
        d for d in rain["details"] if d.startswith("Once the rain has cleared")
    )
    seg = doc.segment(
        "B4 Further details of the rain warning (showers and thunderstorms sentence)",
        "reported",
        "script",
        [
            doc_quote_ref(
                inputs,
                "metoffice_warnings_text",
                "rain warning further details",
                showers,
            )
        ],
    )
    doc.add(
        seg,
        *tagged(
            f'Rain warning (B3.3), further details, quoted: "{showers}"',
            "reported",
            first="B4 ",
        ),
    )

    # ---- Part C: ESO answer on weather (Appendix M Q32) -----------------------------------
    doc.blank()
    doc.frame(
        "Part C heading",
        "PART C — ESO STATEMENT ON WARNINGS AND LIGHTNING RISK (published report, quoted)",
    )
    q32 = [
        "Weather conditions on 9th August were anticipated and were not unusual.",
        "The Met Office had issued yellow warnings of wind for the South West England and South "
        "Wales, and yellow warnings of rain for all of England and Wales.",
        "Lightning Risk 1 was in place in NW England, NE England and Midlands/Lincs.",
        "The Yellow Warning is the lowest of the 3 Met Office warnings.",
    ]
    q32_question = (
        "What is ESO policy on bad weather risk mitigations? Was the weather such on the day "
        "that actions were being considered or had been taken?"
    )
    policy = "NGESO's policy for severe weather, which was not required on the day,"
    seg = doc.segment(
        "C1 Appendix M Q32 question and answer sentences",
        "reported",
        "quotation",
        [pdf_ref(inputs, "APP", 86, "Appendix M, question 32", q32_question)]
        + [pdf_ref(inputs, "APP", 86, "Appendix M, answer 32", q) for q in q32]
        + [pdf_ref(inputs, "APP", 86, "Appendix M, answer 32", policy)],
    )
    doc.add(
        seg,
        *p(
            "C1",
            "Appendices to the ESO technical report (published 6 September 2019), Appendix M, "
            f'question 32 as printed: "{q32_question}"',
        ),
        "    Answer, quoted sentence by sentence:",
        *(line for q in q32 for line in tagged(f'"{q}"', "reported")),
        *tagged(f'"{policy} ..."', "reported"),
    )

    # ---- Part D: MeteoGroup lightning-risk e-mails (Appendix A) ---------------------------
    doc.blank()
    doc.frame(
        "Part D heading",
        "PART D — METEOGROUP LIGHTNING-RISK FORECASTS RECEIVED BY ESO (published table)",
    )
    forecast = inputs.catalogue_rows(LIGHTNING_FORECAST)
    require(
        [r["update_received_time_as_printed"] for r in forecast]
        == ["05:49", "08:02", "12:34", "16:44"],
        "lightning forecast rows changed",
    )
    intro = [
        "Lightning risk is provided on a scale of 1-5, with 5 referring to the least risk of "
        "lightning (due to the absence of the required weather conditions), and 1 the highest "
        "risk.",
        "On 9 August from 05:49hrs onwards ESO received email updates on the lightning risk from "
        "Meteogroup.",
        "East Anglia was updated to Risk 1 in the update just prior to the incident.",
    ]
    forecast_text = (
        "Rain, heavy at times, clearing northwards, but persisting in northern and eastern "
        "Scotland. A mix of sunny spells, but also some heavy and possibly thundery showers will "
        "follow on behind. Feeling warm and humid for many, but increasingly windy."
    )
    cells = [f"{r['update_received_time_as_printed']}hrs" for r in forecast] + [
        part.strip()
        for r in forecast
        for part in r["regions_level1_risk_next_24h"].split(";")
    ]
    seg = doc.segment(
        "D1 Appendix A lightning-risk table, its introduction and the day's forecast text",
        "reported",
        "transcription",
        [
            table_ref(
                inputs,
                "APP",
                10,
                "Appendix A, Lightning Forecasts from Meteogroup on 9 August "
                "2019 (Table 1)",
                "APP-p10-tbl-lightning-forecast",
                LIGHTNING_FORECAST,
                cells,
            ),
            *(
                pdf_ref(inputs, "APP", 10, "Appendix A, lightning forecasts", q)
                for q in intro
            ),
            pdf_ref(inputs, "APP", 10, "Appendix A, weather forecast", forecast_text),
            pdf_ref(
                inputs,
                "APP",
                10,
                "Appendix A, table heading",
                "Regions Forecasted with Level 1 lightning risk for the next 24 hours",
            ),
        ],
    )
    doc.add(
        seg,
        *p(
            "D1",
            "Appendices to the ESO technical report, Appendix A (system conditions prior to the "
            'incident), "Lightning Forecasts from Meteogroup on 9 August 2019". Text printed '
            "with the table, quoted:",
        ),
        *(line for q in intro for line in tagged(f'"{q}"', "reported")),
        "    Table (Time of Lightning Update Received | Regions Forecasted with Level 1 lightning "
        "risk for the",
        "    next 24 hours), as printed:",
    )
    for r in forecast:
        regions = ", ".join(
            x.strip() for x in r["regions_level1_risk_next_24h"].split(";")
        )
        doc.add(
            seg,
            *tagged(
                f"{r['update_received_time_as_printed']}hrs | {regions}",
                "reported",
                indent="      ",
            ),
        )
    doc.add(
        seg,
        *tagged(
            f'Weather forecast for the day as printed in the same appendix: "{forecast_text}"',
            "reported",
        ),
    )

    # ---- Part E: lightning screenshots ------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part E heading and not-held statement",
        "PART E — LIGHTNING DETECTIONS AS DISPLAYED IN PUBLISHED SCREENSHOTS (MeteoGroup data)",
        *wrap(
            "The MeteoGroup detection records were not available for this compilation. The "
            "values below are read from screenshots of the MeteoGroup lightning viewer printed "
            "in the published reports; they are reported values, not a data extract."
        ),
    )
    fig4 = inputs.catalogue_rows(ESO_FIG4)
    require(len(fig4) == 3, "ESO Figure 4 popup rows changed")
    fig4_caption = (
        "Figure 4 - Three simultaneous lightning strikes close to Willian Arboretum at 15:52hrs "
        "– Data Source: Meteogroup"
    )
    seg = doc.segment(
        "E1 ESO Figure 4 caption and the three strike popups (figure transcription)",
        "reported",
        "figure_transcription",
        [
            pdf_ref(
                inputs,
                "ESO",
                16,
                "4.1 Transmission System, Figure 4 caption",
                fig4_caption,
            ),
            figure_ref(
                "ESO",
                16,
                "4.1 Transmission System, Figure 4",
                "ESO-p16-fig4",
                [
                    "figures/ESO-p16-fig4.png",
                    "figures/ESO-p16-fig4_native.jpeg",
                    f"extracted/{ESO_FIG4}",
                ],
                "Popup values read from the raster image by the catalogue; the lower-left popup "
                "is hard to read at this resolution and was confirmed against the same strike "
                "in APP p25 Figure 3.1.1.",
            ),
        ],
    )
    doc.add(
        seg,
        *p(
            "E1",
            "ESO technical report, section 4.1, Figure 4, caption as printed: "
            f'"{fig4_caption}". Each of the three strike popups shown in the figure reads '
            "(Time of impact | latitude, longitude | amplitude | location accuracy | type):",
        ),
    )
    for r in fig4:
        doc.add(
            seg,
            f"    {r['time_of_impact_printed']} | {r['latitude_deg_N']} N, {r['longitude_deg_W']} W "
            f"| {r['amplitude_kA']} kA | {r['location_accuracy_km']} km | {r['type']} [reported]",
        )
    p25 = {r["field"]: r["value_as_printed"] for r in inputs.catalogue_rows(APP_P25)}
    p25_caption = (
        "Figure 3.1.1 MeteoGroup Lightning Activity Recordings in the vicinity of Letchworth "
        "Garden City."
    )
    seg = doc.segment(
        "E2 NGET Figure 3.1.1 caption, viewer settings and strike popup (figure transcription)",
        "reported",
        "figure_transcription",
        [
            pdf_ref(
                inputs,
                "APP",
                25,
                "Appendix C, 3.1.1 MeteoGroup lightning activity",
                p25_caption,
            ),
            figure_ref(
                "APP",
                25,
                "Appendix C (NGET report), Figure 3.1.1",
                "APP-p25-map-lightning-meteogroup",
                [
                    "figures/APP-p25-map-lightning-meteogroup.png",
                    f"extracted/{APP_P25}",
                ],
                "Viewer panel and popup fields read from the raster screenshot at native "
                "resolution by the catalogue.",
            ),
        ],
    )
    doc.add(
        seg,
        *p(
            "E2",
            "Appendix C of the ESO appendices (NGET technical report), Figure 3.1.1, caption as "
            f'printed: "{p25_caption}" Values displayed in the screenshot:',
        ),
        f"    Viewer settings: data source {p25['data_source_selector']}; date "
        f"{p25['date_selector']} [reported]",
        f"    Viewer time window: start {p25['start_time_selector']}, end "
        f"{p25['end_time_selector']}; the clock of the window is not shown [reported]",
        '    Panel text: "Number of impacts : '
        f'{p25["number_of_impacts_in_view"]}" [reported]',
        f"    Popup: time of impact {p25['time_of_impact']} [reported]",
        f"    Popup: position {p25['popup_coordinates']} | amplitude {p25['amplitude']} "
        "[reported]",
        f"    Popup: accuracy {p25['accuracy']} | type {p25['type']} [reported]",
    )

    build.construction = (
        "Part A copies IEM METAR lines (public domain) byte for byte; Part B parses the text the "
        "real-data pass extracted from the Internet Archive capture of the Met Office warnings "
        "page (OGL) and reproduces fields as printed; Parts C-D quote and transcribe ESO "
        "Appendix M Q32 and the Appendix A lightning-risk table (verified on the PDF page "
        "text); Part E transcribes values displayed in two published MeteoGroup screenshots "
        "(catalogue figure transcriptions). No value is synthesised."
    )

    # ---- Artifacts ----------------------------------------------------------------------------
    build.add_artifact(
        Artifact(
            name=F_METAR,
            media_type="text/csv",
            description="IEM METAR reports for EGGW, EGSC and EGTC, 14:50-17:20 UTC on 9 August "
            "2019; lines of the downloaded file unchanged.",
            data=metar_bytes,
            provenance={
                "extraction_method": "script",
                "builder": "builder/system_response/real/build_real.py",
                "inputs": [
                    {
                        "source_id": "iem_metar",
                        "file": SOURCES["iem_metar"]["rel"],
                        "sha256": SOURCES["iem_metar"]["sha256"],
                    }
                ],
                "transformation": "header plus lines for three stations, valid 14:50-17:20 UTC",
            },
        )
    )
    warn_rows = [
        [
            w["type"],
            w["from"],
            w["to"],
            w["clock"],
            w["when_label"],
            w["when"],
            w["headline"],
            "; ".join(w["regions"]),
            ", ".join(w["east"]),
        ]
        for w in warnings
    ]
    build.add_artifact(
        Artifact(
            name=F_WARN,
            media_type="text/csv",
            description="The four warning detail blocks of the Met Office UK warnings page "
            "captured 2019-08-09T16:02:23Z, fields as printed.",
            data=csv_bytes(
                [
                    "warning_type",
                    "valid_from_as_printed",
                    "valid_to_as_printed",
                    "clock_as_printed",
                    "issued_or_updated",
                    "issued_or_updated_as_printed",
                    "headline",
                    "regions_listed",
                    "east_of_england_local_authorities",
                ],
                warn_rows,
            ),
            provenance={
                "extraction_method": "script",
                "builder": "builder/system_response/real/build_real.py",
                "inputs": [
                    {
                        "source_id": "metoffice_warnings_text",
                        "file": SOURCES["metoffice_warnings_text"]["rel"],
                        "sha256": SOURCES["metoffice_warnings_text"]["sha256"],
                    }
                ],
                "transformation": "warning detail blocks parsed into one row each; text as printed",
            },
        )
    )
    light_rows: list[list[Any]] = []
    for r in forecast:
        light_rows.append(
            [
                "ESO appendices, Appendix A, lightning forecasts table",
                "update received",
                f"{r['update_received_time_as_printed']}hrs",
                ", ".join(
                    x.strip() for x in r["regions_level1_risk_next_24h"].split(";")
                ),
            ]
        )
    for n, r in enumerate(fig4, 1):
        for field_name in (
            "time_of_impact_printed",
            "latitude_deg_N",
            "longitude_deg_W",
            "amplitude_kA",
            "location_accuracy_km",
            "type",
        ):
            light_rows.append(
                [
                    f"ESO technical report, Figure 4, popup {n}",
                    field_name,
                    r[field_name],
                    "",
                ]
            )
    for field_name in (
        "data_source_selector",
        "date_selector",
        "start_time_selector",
        "end_time_selector",
        "number_of_impacts_in_view",
        "time_of_impact",
        "popup_coordinates",
        "amplitude",
        "accuracy",
        "type",
    ):
        light_rows.append(
            ["NGET report (Appendix C), Figure 3.1.1", field_name, p25[field_name], ""]
        )
    build.add_artifact(
        Artifact(
            name=F_LIGHT,
            media_type="text/csv",
            description="Lightning information as published: the Appendix A lightning-risk table "
            "and the values displayed in ESO Figure 4 and NGET Figure 3.1.1 (Parts D and E).",
            data=csv_bytes(
                ["published_in", "field", "value_as_printed", "detail"], light_rows
            ),
            provenance={
                "extraction_method": "transcription",
                "builder": "builder/system_response/real/build_real.py",
                "inputs": [
                    {"catalogue_extract": f"extracted/{LIGHTNING_FORECAST}"},
                    {"catalogue_extract": f"extracted/{ESO_FIG4}"},
                    {"catalogue_extract": f"extracted/{APP_P25}"},
                ],
                "transformation": "as printed; figure values are catalogue transcriptions of "
                "raster screenshots",
            },
        )
    )
    return build
