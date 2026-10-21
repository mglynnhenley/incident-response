"""R07 — demand disconnection and restoration records.

Builder-only. Real Elexon extracts: the demand control instruction (DCI) record and the 5-minute
system demand summary. Reported material: ESO Table 6 and the ESO section 4.3 sentence (931 MW,
DNO returns as of 13 August 2019), the E3C interim report Table 1 (per DNO area, total 973 MW)
and Ofgem's net figure (892 MW). Public DNO posts about restoration appear only as post time
(decoded from the post identifier) plus a short gist written for this exercise: post text is
the account holders' copyright and is neither reproduced nor closely paraphrased; no handles or
personal names are given.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import timedelta
from typing import Any

from real_common import (
    TextDoc,
    csv_bytes,
    data_ref,
    doc_quote_ref,
    iso_z,
    parse_utc,
    pdf_ref,
    require,
    snowflake_utc,
    table_ref,
    tagged,
    wrap,
)
from real_docbuild import Artifact, DocBuild
from real_sources import ELEXON_ATTRIBUTION, SOURCES

DOC_ID = "R07"
TITLE = "Demand disconnection and restoration records, 9 August 2019"
TAB6 = "ESO-p26-tab6.csv"
E3CI = "E3C-I-p11-tab1.csv"
F_DCI = "R07_elexon_dci_201908.csv"
F_DEMAND = "R07_elexon_demand_outturn_summary_5min_20190809.csv"
F_TABLES = "R07_reported_lfdd_by_dno.csv"
F_POSTS = "R07_dno_public_posts_summaries.csv"
DCI_FIELDS = [
    "mRID",
    "revisionNumber",
    "publishTime",
    "publishingPeriodCommencingTime",
    "affectedDso",
    "demandControlId",
    "instructionSequence",
    "demandControlEventFlag",
    "timeFrom",
    "timeTo",
    "volume",
    "systemManagementActionFlag",
    "amendmentFlag",
]

#: Organisational posts about supply restoration, chosen from the consequences communications
#: timeline (top-level posts by DNO accounts only; replies to members of the public excluded).
#: Each "summary" is a short gist written for this exercise: organisation, decoded time and
#: the gist only. The post text is not openly licensed and is neither reproduced nor
#: closely paraphrased (``check_posts`` refuses a gist sharing four consecutive words with
#: its post).
DNO_POSTS = (
    {
        "post_id": 1159858936037748736,
        "organisation": "UK Power Networks (UKPN)",
        "summary": "gist: power cut over a wide part of the South East, including London; cause "
        "placed, as its belief at the time, on a failure in National Grid's system.",
        "archive_url": "https://web.archive.org/web/20190809171937/https://twitter.com/"
        "UKPowerNetworks/status/1159858936037748736",
    },
    {
        "post_id": 1159860575188508672,
        "organisation": "Western Power Distribution (WPD)",
        "summary": "gist: serious national-level electricity incident; restoration of affected "
        "customers had begun.",
        "archive_url": "https://web.archive.org/web/20201104081128/https://twitter.com/wpduk/"
        "status/1159860575188508672?ref_src=twsrc%5Etfw",
    },
    {
        "post_id": 1159868068614553600,
        "organisation": "Electricity North West (ENWL)",
        "summary": "gist: several outages in its region, attributed to a National Grid fault; "
        "supplies expected to be back on.",
        "archive_url": "https://web.archive.org/web/20220120093007/https://twitter.com/"
        "ElectricityNW/status/1159868068614553600",
    },
    {
        "post_id": 1159868588607639552,
        "organisation": "Western Power Distribution (WPD)",
        "summary": "gist: progress figure, 90% of affected customers back on supply; restoration "
        "of the remainder continuing.",
        "archive_url": "https://web.archive.org/web/20250825063922/https://twitter.com/wpduk/"
        "status/1159868588607639552",
    },
    {
        "post_id": 1159877477533138945,
        "organisation": "Western Power Distribution (WPD)",
        "summary": "gist: restoration complete for every customer it had lost in the national "
        "incident.",
        "archive_url": "https://web.archive.org/web/20210926182026/https://twitter.com/wpduk/"
        "status/1159877477533138945",
    },
    {
        "post_id": 1159882018148278274,
        "organisation": "UK Power Networks (UKPN)",
        "summary": "gist: follow-up; cause attributed to a national transmission network issue; "
        "all supplies in its London and South East area believed back on.",
        "archive_url": "https://web.archive.org/web/20220205235758/https://twitter.com/"
        "UKPowerNetworks/status/1159882018148278274",
    },
)


def p(label: str, text: str) -> list[str]:
    return wrap(text, first=f"{label:<3}", indent="    ")


def cont(text: str) -> list[str]:
    return wrap(text, first="    ", indent="    ")


def thousands(value: str) -> str:
    return f"{int(value):,}" if value.strip() else ""


def dci_record(inputs) -> dict[str, Any]:
    data = inputs.real_json("elexon_dci")["data"]
    require(len(data) == 1, f"DCI records for August 2019: {len(data)} != 1")
    rec = data[0]
    require(list(rec) == DCI_FIELDS, f"DCI fields changed: {list(rec)}")
    require(
        rec["volume"] == 931.0 and rec["timeFrom"] == "2019-08-09T15:54:00Z",
        "DCI values",
    )
    return rec


def demand_summary(inputs) -> list[dict[str, Any]]:
    data = inputs.real_json("elexon_demand_summary")
    data = sorted(data, key=lambda r: r["startTime"])
    require(len(data) == 61, f"demand summary rows {len(data)} != 61")
    for prev, cur in zip(data, data[1:], strict=False):
        require(
            parse_utc(cur["startTime"]) - parse_utc(prev["startTime"])
            == timedelta(minutes=5),
            "demand summary spacing",
        )
    require({r["recordType"] for r in data} == {"VD"}, "recordType values changed")
    return data


#: A gist may share at most this many consecutive words with its post.
GIST_MAX_SHARED = 3


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9%]+", text.casefold())


def shared_word_runs(gist: str, post: str, limit: int) -> list[str]:
    """Runs of more than ``limit`` consecutive words that ``gist`` shares with ``post``."""
    words, source = _words(gist), " " + " ".join(_words(post)) + " "
    n = limit + 1
    return [
        " ".join(words[i : i + n])
        for i in range(len(words) - n + 1)
        if " " + " ".join(words[i : i + n]) + " " in source
    ]


def check_posts(inputs) -> None:
    """Cross-check post IDs, organisations and decoded times against the comms timeline."""
    raw = inputs.optional_real_bytes("consequences_comms_timeline")
    if raw is None:
        return
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    for post in DNO_POSTS:
        pid = str(post["post_id"])
        match = [
            r for r in rows if pid in r["local_file"] and r["channel"] == "Twitter"
        ]
        require(len(match) == 1, f"post {pid} not uniquely in the comms timeline")
        local = (snowflake_utc(post["post_id"]) + timedelta(hours=1)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        require(
            match[0]["time_uk_local"] == local,
            f"post {pid}: decoded time {local} differs",
        )
        require(
            match[0]["source_url"] == post["archive_url"],
            f"post {pid}: archive URL differs",
        )
        shared = shared_word_runs(post["summary"], match[0]["summary"], GIST_MAX_SHARED)
        require(not shared, f"post {pid}: the gist tracks the post wording {shared}")


def build(inputs) -> DocBuild:
    doc = TextDoc(DOC_ID)
    build = DocBuild(
        doc_id=DOC_ID,
        title=TITLE,
        owner="Elexon (BMRS data); National Grid ESO, E3C and Ofgem (report tables); DNO public "
        "posts (short gists written for this record)",
        category="distribution_records",
        record_type="real Elexon extracts (demand control instruction record, 5-minute demand "
        "summary) with transcribed report tables of demand disconnected by DNO area and short "
        "builder-written gists of public DNO posts",
        construction="",
        text=doc,
        status_scope="Nothing in Parts A-C is synthesised. Part D is not a transcription: it "
        "gives, for each public DNO post, the decoded post time and a short gist written for "
        "this record; the post text is not reproduced.",
    )
    build.header(
        "Elexon Limited (BMRS / Insights API; demand control data from the system operator); "
        "National Grid ESO (technical report of 6 September 2019); Energy Emergencies "
        "Executive Committee (E3C interim report); Ofgem (report of 3 January 2020); public "
        "posts by distribution network operators (DNOs)",
        wrap(
            "Clock reference: Elexon timestamps are UTC (ISO-8601 with Z). Report tables print "
            "times without a zone; the reports give event times in local time (BST, UTC+01:00). "
            "Post times in Part D are UTC, decoded from the post identifiers."
        ),
    )
    dci = dci_record(inputs)
    demand = demand_summary(inputs)
    check_posts(inputs)

    # ---- Part A: DCI ------------------------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part A heading",
        "PART A — ELEXON DEMAND CONTROL INSTRUCTION RECORD (real extract)",
    )
    seg = doc.segment(
        "A1 DCI query and record, field by field",
        "reported",
        "script",
        [
            data_ref(
                "elexon_dci", "the single record returned for August 2019, all fields"
            ),
            doc_quote_ref(
                inputs,
                "elexon_api_docs",
                "/system/demand-control-instructions description",
                "This endpoint provides demand control instruction data, filtered by the time "
                "range of the instruction.",
            ),
        ],
        "JSON fields listed one per line, values unchanged (null shown as null).",
    )
    doc.add(
        seg,
        *p(
            "A1",
            "Source: Elexon endpoint /system/demand-control-instructions queried for "
            "2019-08-01T00:00:00Z to 2019-08-31T00:00:00Z; retrieved 2026-10-20. Licence: Elexon "
            f"BMRS open data licence. {ELEXON_ATTRIBUTION} Publisher's description: "
            '"This endpoint provides demand control instruction data, filtered by the time '
            'range of the instruction."',
        ),
        *cont(
            "The query returned exactly one record. Its fields, as published (times UTC) "
            "[reported]:"
        ),
        *(
            f"    {name}: {'null' if dci[name] is None else dci[name]!s} [reported]"
            for name in DCI_FIELDS
        ),
        *cont(
            "The response defines neither the flag codes nor the unit of volume. The same record "
            f"is in file {F_DCI}.",
        ),
    )

    # ---- Part B: 5-minute demand summary -----------------------------------------------------
    doc.blank()
    doc.frame(
        "Part B heading",
        "PART B — ELEXON 5-MINUTE SYSTEM DEMAND SUMMARY (real extract)",
    )
    seg = doc.segment(
        "B1 Demand summary file description with the publisher's caveat",
        "measured",
        "script",
        [
            data_ref("elexon_demand_summary", "all 61 records 14:00Z-19:00Z"),
            doc_quote_ref(
                inputs,
                "elexon_api_docs",
                "/demand/outturn/summary summary",
                "System demand summary (FUELINST)",
            ),
            doc_quote_ref(
                inputs,
                "elexon_api_docs",
                "/demand/outturn/summary description",
                "This endpoint provides a down-sampled data summary intended for visualisation "
                "purposes.",
            ),
        ],
    )
    doc.add(
        seg,
        *p(
            "B1",
            f"File {F_DEMAND} [measured] — 5-minute system demand summary, 14:00 to 19:00 UTC "
            "on 9 August 2019.",
        ),
        *cont(
            "Source: Elexon endpoint /demand/outturn/summary with resolution=minute, from "
            "2019-08-09T14:00:00Z to 2019-08-09T19:00:00Z; retrieved 2026-10-20. Licence as A1.",
        ),
        *cont(
            f"Rows: {len(demand)} (every record returned), one per startTime from "
            f"{demand[0]['startTime']} to {demand[-1]['startTime']} at 5-minute steps. Columns: "
            "recordType (VD in every row; not defined in the response), startTime (UTC), demand "
            "(MW).",
        ),
        *cont(
            'The publisher titles the endpoint "System demand summary (FUELINST)" and warns: '
            '"This endpoint provides a down-sampled data summary intended for visualisation '
            'purposes." The calculation is not documented in the response; the series is not a '
            "metered measurement of disconnected demand.",
        ),
        *cont(
            "This file is the time series of R07: cite rows as row:<n> or times as "
            "time:<ISO-8601> (UTC), within 2019-08-09T14:00:00Z to 2019-08-09T19:00:00Z.",
        ),
    )

    # ---- Part C: reported LFDD tables -------------------------------------------------------
    tab6 = inputs.catalogue_rows(TAB6)
    e3ci = inputs.catalogue_rows(E3CI)
    require(
        len(tab6) == 15 and tab6[-1]["reporting_dno"] == "Totals", "ESO Table 6 rows"
    )
    require(
        len(e3ci) == 15 and e3ci[-1]["reporting_dno"] == "Total", "E3C-I Table 1 rows"
    )
    doc.blank()
    doc.frame(
        "Part C heading",
        "PART C — DEMAND DISCONNECTED BY LFDD, AS REPORTED (transcribed as printed)",
        *wrap(
            "LFDD is low frequency demand disconnection. Times in these tables are printed "
            "without a zone; the reports give event times in local time (BST, UTC+01:00). A "
            "blank printed cell is shown as (blank)."
        ),
    )
    eso_text = [
        "Table 7 summarises the customer impact in terms of total demand lost, customers "
        "affected and final restoration time.",
        "The information is based on DNO reported data as of 13 August 2019 at 12:00.",
        "The total loss of demand, due to LFDD relay operation was 1,152,878 customers or 931MW, "
        "which represents 3.2% of national transmission demand at the time of the event (29GW).",
    ]
    t6_rows = [
        (
            r["reporting_dno"],
            r["area"],
            r["mw_disconnected_by_lfdd"],
            thousands(r["customers_affected"]),
            r["final_restoration_time_printed"],
        )
        for r in tab6
    ]
    seg = doc.segment(
        "C1 ESO Table 6 (DNO customers affected by LFDD relays) with the section 5.1 text",
        "reported",
        "transcription",
        [
            table_ref(
                inputs,
                "ESO",
                26,
                "5.1 Distribution Demand, Table 6 - DNO customers "
                "affected by LFDD relays",
                "ESO-p26-tab6",
                TAB6,
                [c for row in t6_rows for c in row],
            ),
            *(
                pdf_ref(inputs, "ESO", 26, "5.1 Distribution Demand", q)
                for q in eso_text
            ),
            pdf_ref(
                inputs,
                "ESO",
                26,
                "Table 6 caption",
                "Table 6 - DNO customers affected by LFDD relays",
            ),
        ],
        "Customer counts printed with thousands separators as in the report.",
    )
    doc.add(
        seg,
        *p(
            "C1",
            "National Grid ESO, Technical Report on the events of 9 August 2019 (published "
            '6 September 2019), section 5.1 "Distribution Demand". Text printed with the table, '
            "quoted:",
        ),
        *(line for q in eso_text for line in tagged(f'"{q}"', "reported")),
        '    "Table 6 - DNO customers affected by LFDD relays" (Reporting DNO | area | MW of '
        "disconnected demand by",
        "    LFDD | Customers Affected | Final Restoration Time of Demand), as printed:",
        *(
            line
            for row in t6_rows
            for line in tagged(
                " | ".join(c or "(blank)" for c in row), "reported", indent="      "
            )
        ),
    )
    eso_43 = (
        "The DNO’s have indicated that 931MW (3.2%) of demand was automatically disconnected by "
        "the operation of the LFDD scheme."
    )
    seg = doc.segment(
        "C2 ESO section 4.3 sentence on the LFDD volume",
        "reported",
        "quotation",
        [
            pdf_ref(
                inputs, "ESO", 21, "4.3 Demand disconnection and restoration", eso_43
            )
        ],
    )
    doc.add(
        seg,
        *p(
            "C2",
            'Same report, section 4.3 "Demand disconnection and restoration", quoted:',
        ),
        *tagged(f'"{eso_43.replace("’", chr(39))}"', "reported"),
    )
    e3_rows = [
        (
            r["reporting_dno"],
            r["licence_area"],
            r["mw_disconnected_by_lfdd"],
            thousands(r["customers_affected"]),
            r["final_restoration_time_printed"],
        )
        for r in e3ci
    ]
    caption = "Table 1 Low Frequency Demand Disconnection reported by DNO area."
    seg = doc.segment(
        "C3 E3C interim report Table 1 (LFDD reported by DNO area)",
        "reported",
        "transcription",
        [
            table_ref(
                inputs,
                "E3C-I",
                11,
                "Table 1 Low Frequency Demand Disconnection reported by DNO area",
                "E3C-I-p11-tab1",
                E3CI,
                [c for row in e3_rows for c in row],
            ),
            pdf_ref(inputs, "E3C-I", 11, "Table 1 caption", caption),
        ],
        "Customer counts printed with thousands separators as in the report.",
    )
    doc.add(
        seg,
        *p(
            "C3",
            "Energy Emergencies Executive Committee (E3C), GB power system disruption - 9 August "
            '2019, interim report (cover dated September 2019), "'
            + caption
            + '" (Reporting '
            "DNO | License Area | MW of disconnected demand by LFDD | Customers Affected | Final "
            "Restoration Time of Demand), as printed:",
        ),
        *(
            line
            for row in e3_rows
            for line in tagged(
                " | ".join(c or "(blank)" for c in row), "reported", indent="      "
            )
        ),
    )
    ofg = [
        (
            19,
            "2.4.12",
            "892MW of net demand was disconnected in total from the local "
            "distribution networks.",
        ),
        (
            19,
            "2.5",
            "In total, 892MW of net demand was disconnected from the local distribution "
            "networks as a result of LFDD, representing approximately 4% of national demand and "
            "affecting 1.15 million customers.",
        ),
    ]
    seg = doc.segment(
        "C4 Ofgem report paragraphs 2.4.12 and 2.5 (892 MW net demand)",
        "reported",
        "quotation",
        [pdf_ref(inputs, "OFG", page, f"paragraph {para}", q) for page, para, q in ofg],
    )
    doc.add(
        seg,
        *p(
            "C4",
            "Ofgem, 9 August 2019 power outage report (published 3 January 2020), quoted:",
        ),
        *(
            line
            for _, para, q in ofg
            for line in tagged(f'paragraph {para}: "{q}"', "reported")
        ),
    )

    # ---- Part D: DNO public posts -----------------------------------------------------------
    doc.blank()
    seg = doc.segment(
        "Part D heading and method (post identifiers decoded to UTC; builder-written gists)",
        "framing",
        "framing",
        [],
    )
    doc.add(
        seg,
        "PART D — PUBLIC POSTS BY DNOs ABOUT SUPPLY RESTORATION (post times decoded; gists written for",
        "this record, not post text)",
        *wrap(
            "Organisational posts on a public social-media platform, located in Internet Archive "
            "captures. The post time is decoded from each post identifier (milliseconds since "
            "1970-01-01T00:00:00Z = (identifier >> 22) + 1288834974657) and shown in UTC to the "
            "second. The post text is the account holder's copyright (not an open licence) and "
            "is neither reproduced nor closely paraphrased: each entry gives only the "
            "organisation, the decoded time and a short gist written for this record, whose "
            "[reported] tag marks what the organisation reported, not its words. No account "
            "handles or personal names are given."
        ),
    )
    post_rows = []
    for n, post in enumerate(DNO_POSTS, 1):
        when = snowflake_utc(post["post_id"])
        stamp = iso_z(when.replace(microsecond=0))
        seg = doc.segment(
            f"D{n} DNO post gist, {post['organisation']}",
            "reported",
            "paraphrase",
            [
                {
                    "kind": "public_post",
                    "source_id": "consequences_comms_timeline",
                    "post_id": str(post["post_id"]),
                    "decoded_utc": when.isoformat().replace("+00:00", "Z"),
                    "archive_url": post["archive_url"],
                    "quote": None,
                    "note": "time decoded from the post identifier; gist written for this "
                    "exercise from the archived post (text neither reproduced nor closely "
                    "paraphrased: not openly licensed)",
                }
            ],
        )
        doc.add(
            seg,
            *tagged(
                f"{stamp} | {post['organisation']} | {post['summary']}",
                "reported",
                first=f"{f'D{n}':<3}",
            ),
        )
        post_rows.append([stamp, post["organisation"], post["summary"]])

    doc.blank()
    doc.frame(
        "Part E: what the record does not contain",
        "PART E — NOTES",
        *p(
            "E1",
            "This record holds no DNO operational logs, feeder-level disconnection or "
            "reconnection times, or distributed-generation data.",
        ),
    )

    build.construction = (
        "Parts A-B copy Elexon DCI and 5-minute demand summary records (hash-checked) without "
        "changing values. Part C transcribes ESO Table 6, the E3C interim Table 1 and quotes ESO "
        "sections 4.3/5.1 and Ofgem 2.4.12/2.5, every cell and quotation checked on the stated PDF "
        "page; customer counts are printed with the reports' thousands separators. Part D gives, "
        "for six top-level DNO posts in the consequences communications timeline, the time "
        "decoded from the post identifier and a short gist written for this exercise (post text "
        "neither reproduced nor closely paraphrased: no gist shares more than "
        f"{GIST_MAX_SHARED} consecutive words with its post; not openly licensed). The STATUS "
        "line scopes 'nothing synthesised' to Parts A-C. No value is synthesised."
    )

    # ---- Artifacts ----------------------------------------------------------------------------
    build.add_artifact(
        Artifact(
            name=F_DCI,
            media_type="text/csv",
            description="Elexon demand control instruction (DCI) record for August 2019 (one "
            "record), all fields.",
            data=csv_bytes(DCI_FIELDS, [[dci[f] for f in DCI_FIELDS]]),
            provenance={
                "extraction_method": "script",
                "builder": "builder/system_response/real/build_real.py",
                "inputs": [
                    {
                        "source_id": "elexon_dci",
                        "file": SOURCES["elexon_dci"]["rel"],
                        "sha256": SOURCES["elexon_dci"]["sha256"],
                    }
                ],
                "transformation": "single JSON record to one CSV row; values unchanged",
            },
        )
    )
    build.add_artifact(
        Artifact(
            name=F_DEMAND,
            media_type="text/csv",
            description="Elexon 5-minute system demand summary (MW), 14:00-19:00 UTC on "
            "9 August 2019; columns recordType, startTime (UTC), demand (MW).",
            data=csv_bytes(
                ["recordType", "startTime", "demand"],
                [[r["recordType"], r["startTime"], r["demand"]] for r in demand],
            ),
            timeseries={
                "time_column": "startTime",
                "value_column": "demand",
                "unit": "MW",
                "first": demand[0]["startTime"],
                "last": demand[-1]["startTime"],
                "rows": len(demand),
                "interval_s": 300,
            },
            provenance={
                "extraction_method": "script",
                "builder": "builder/system_response/real/build_real.py",
                "inputs": [
                    {
                        "source_id": "elexon_demand_summary",
                        "file": SOURCES["elexon_demand_summary"]["rel"],
                        "sha256": SOURCES["elexon_demand_summary"]["sha256"],
                    }
                ],
                "transformation": "records to CSV rows sorted by startTime; values unchanged",
            },
        )
    )
    table_rows = [["ESO technical report Table 6", *row] for row in t6_rows] + [
        ["E3C interim report Table 1", *row] for row in e3_rows
    ]
    build.add_artifact(
        Artifact(
            name=F_TABLES,
            media_type="text/csv",
            description="Per-DNO LFDD tables as printed: ESO technical report Table 6 and E3C "
            "interim report Table 1 (Part C).",
            data=csv_bytes(
                [
                    "table",
                    "reporting_dno",
                    "area_as_printed",
                    "mw_disconnected_by_lfdd_as_printed",
                    "customers_affected_as_printed",
                    "final_restoration_time_as_printed",
                ],
                table_rows,
            ),
            provenance={
                "extraction_method": "transcription",
                "builder": "builder/system_response/real/build_real.py",
                "inputs": [
                    {"catalogue_extract": f"extracted/{TAB6}"},
                    {"catalogue_extract": f"extracted/{E3CI}"},
                ],
                "transformation": "cells as printed (customer counts with thousands separators); "
                "empty cell where the report prints none",
            },
        )
    )
    build.add_artifact(
        Artifact(
            name=F_POSTS,
            media_type="text/csv",
            description="Public DNO posts about restoration (Part D): post time in UTC decoded "
            "from the post identifier, organisation, and a short gist written for this record "
            "(not the post text).",
            data=csv_bytes(
                ["post_time_utc", "organisation", "gist_written_for_this_record"],
                post_rows,
            ),
            provenance={
                "extraction_method": "paraphrase",
                "builder": "builder/system_response/real/build_real.py",
                "inputs": [
                    {
                        "source_id": "consequences_comms_timeline",
                        "post_ids": [str(p_["post_id"]) for p_ in DNO_POSTS],
                    }
                ],
                "transformation": "time from post identifier; gists written for this "
                "exercise; no post text",
            },
        )
    )
    return build
