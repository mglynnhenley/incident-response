"""R09 — external communications records, 9-20 August 2019.

Builder-only. What the record holds, by part:

* A-C (transcriptions and quotations, each checked on its PDF page): ESO's published accounts of
  its contacts with government and the regulator (technical report section 6.2 and section 7;
  Appendix M answers of 28 August 2019) — both the 17:51 and the 18:00 times of the first Ofgem
  contact are kept, as published; accounts of external communications by the ESO, DNOs and rail
  companies (ESO section 6.3 with Table 8, section 6.4, Appendix M Q35, the E3C interim and final
  reports, Ofgem paragraph 3.23); calls to the DNOs' 105 helpline (ESO Table 9, E3C interim).
* D (real Elexon data): REMIT unavailability messages for Hornsea One and Little Barford, every
  revision held, with publication times (UTC).
* E (organisational public posts and web statements, not openly licensed): time decoded from the
  post identifier or as displayed/titled, organisation, channel and a short gist written for this
  record — never the text; no handles, no personal names, no replies to members of the public.
* F (Open Government Licence): Ofgem and GOV.UK publications of 12-20 August 2019, quoted.

Excluded (private provenance): Ofgem's January 2020 enforcement settlements and the GOV.UK
release that reports them (decision 50); personal accounts; replies to members of the public.
Rows: ESO-COMMS control-log entries (every timed ESO communication in A-C and E) and REMIT
asset-log events on HORNSEA-ONE and LITTLE-BARFORD.
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from typing import Any

from fi_docbuild import LABEL_REAL_AND_TABLES, Artifact, FiDocBuild
from fi_real_common import (
    BST,
    BUILDER,
    FiInputs,
    TextDoc,
    bst_to_utc,
    csv_bytes,
    data_ref,
    gist_ref,
    normalise,
    pdf_ref,
    post_time,
    quote_ref,
    require,
    table_ref,
    tagged,
    utc_z,
    wrap,
)
from fi_sources import ELEXON_ATTRIBUTION, SOURCES
from real_r07 import DNO_POSTS

BST_OFFSET = BST

DOC_ID = "R09"
TITLE = "External communications records, 9-20 August 2019"
ROOM_ID = "ESO-COMMS"
F_REMIT = "R09_elexon_remit_messages_hornsea_one_little_barford.csv"
F_TAB8 = "R09_eso_table8_external_communications.csv"
F_TAB9 = "R09_eso_table9_calls_to_dnos.csv"
F_PUBLIC = "R09_public_posts_and_statements_gists.csv"
TAB8 = "ESO-p30-tab8.csv"
TAB9 = "ESO-p32-tab9.csv"
REMIT_UNITS = {
    "T_HOWAO-1": "HORNSEA-ONE",
    "T_HOWAO-2": "HORNSEA-ONE",
    "T_HOWAO-3": "HORNSEA-ONE",
    "T_LBAR-1": "LITTLE-BARFORD",
}
REMIT_FIELDS = [
    "publishTime",
    "assetId",
    "mrid",
    "revisionNumber",
    "id",
    "participantId",
    "messageHeading",
    "eventType",
    "unavailabilityType",
    "eventStatus",
    "eventStartTime",
    "eventEndTime",
    "normalCapacity",
    "availableCapacity",
    "unavailableCapacity",
    "cause",
    "relatedInformation",
    "fuelType",
    "affectedUnit",
    "createdTime",
    "outageProfile",
]

REPORT_CLOCK = (
    "time as printed in {source} (no clock labelled; the reports give event times in local "
    "time, read as BST, UTC+01:00)"
)


def p(label: str, text: str) -> list[str]:
    return wrap(text, first=f"{label:<4}", indent="    ")


def cont(text: str) -> list[str]:
    return wrap(text, first="    ", indent="    ")


def q(text: str) -> list[str]:
    """A quotation line (wrapped, tagged [reported])."""
    return tagged(f'"{text}"', "reported", first="    ", indent="      ")


# ---------------------------------------------------------------------------------------------
# Parts A-C: report quotations
# ---------------------------------------------------------------------------------------------

ESO_62 = [
    "The first communication between the ESO control room and BEIS was at 17:41hrs.",
    "At this point the event was generally understood, demand restoration was in progress and "
    "further disturbances were considered unlikely.",
    "The first communication with Ofgem was made at 17:51hrs with further communication at "
    "18:17hrs and 18:45hrs and then throughout the weekend.",
    "Further updates to BEIS from the ESO control room were made at 18:09hrs, 19:29hrs and "
    "19:38hrs respectively.",
]
ESO_7 = [
    "The ESO contacted BEIS at 17:40 and Ofgem at 18:00.",
    "The initial media statement by the ESO issued at 18:27 with a subsequent statement at "
    "20:06 and a video from the Head of National Control being posted at 20:11.",
]
APP_M = (
    "These answers are all based on the data available to the ESO on 28 August 2019."
)
APP_Q34 = [
    "There appeared to be delays in escalations to Ofgem & BEIS after LFDD was initiated? Are "
    "there any lessons to be learnt?",
    "At 17:10hrs, the ENCC Power System Manager (PSM) reported the incident to the Head of "
    "National Control, ESO.",
    "The 1st communication between ENCC PSM and BEIS was at 17:41hrs.",
    "The 1st communication with Ofgem was made just after 18:00hrs with the Director of "
    "Operations, ESO.",
    "Further updates to BEIS from the PSM were made at 18:09hrs, 19:29hrs and 19:38hrs "
    "respectively.",
    "Current ESO procedure outlines that following an event of loss of supply, a clear "
    "communication to Ofgem & BEIS is essential.",
    "The communication is recommended to be initiated as soon as possible, and this procedure "
    "is in line with the ‘Energy Incident Reporting’ requirement set by Ofgem dated in December "
    "2017.",
    "It is important in all cases that resolution of the incident remains the primary "
    "objective.",
]
ESO_63 = [
    "The first ESO external communication was issued at 18:27hrs on 9 August.",
    "Table 8 provides the timeline of external communication with media and wider industry.",
]
ESO_64 = [
    "In the ~90 minutes immediately following the initial fault on the network (starting at "
    "17.09hrs) statements were issued by some DNOs and rail companies stating that the loss of "
    "power and subsequent disruption was the result of a National Grid fault.",
    "These statements were issued ahead of any communication by the ESO and without engagement "
    "or coordination with the ESO communications team.",
    "These public-facing communications did not impact the speed with which the incident was "
    "resolved but did drive a large volume of media queries to the ESO.",
]
APP_Q35 = [
    "What issues did you encounter with the public-facing communications by industry, notably "
    "in terms of the content and timelines for the messaging?",
    "The initial communications from some DNOs and rail companies said that the incident had "
    "been caused by a National Grid fault.",
    "These communications were issued very shortly after the event (from 5.09pm onwards).",
    "The ESO prepared an external communication seeking to give reassurance to the public which "
    "was issued at 18:27 once it was established that the DNOs had reconnected all customers.",
    "The initial statements from some parts of the industry were issued before our statement "
    "and without any co-ordination with our comms team.",
]
E3CI_14 = [
    "DNOs led local public communications during the event and the ESO did not publish public "
    "statements until after the disruption, meaning that energy partners (such as generators) "
    "were not directly informed.",
    "In parallel with social media, DNOs reached out to customers via text message alert "
    "services and telephone services between 17:02 and 18:30.",
    "Updates from the ESO followed the first set of restorations and were not publicly "
    "released until 18:27 via Twitter.",
]
E3CI_15 = (
    "The Secretary of State for Business, Energy and Industrial Strategy later announced via "
    "Twitter (10th August) and GOV.UK (14th August) that the government was to commission the "
    "Energy Emergencies Executive Committee to provide an interim and extended report into the "
    "power disruptions."
)
E3C_20 = [
    "The first public announcement from ESO was issued at 18:27, which was following the event "
    "and once the system had stabilised.",
    "By this time, many DNOs had used twitter to provide area updates that were widely "
    "circulated.",
]
E3C_21 = (
    "However, electricity generators received no communication during the events of 9 August "
    "that would have made them aware of the system condition."
)
OFG_323_P29 = [
    "We have also found issues with Hornsea 1’s communication with the ESO.",
    "Hornsea 1 did not notify the ESO directly when the wind farm deloaded by 737MW.",
    "The wind farm then began its process of starting up two of its modules (temporarily) "
    "without",
]
OFG_323_P30 = (
    "any coordination with the ESO whilst the ESO was attempting to respond to the generation "
    "losses it was aware of."
)
ESO_105 = [
    "Electricity customers across GB can dial the ‘105’ customer helpline to get emergency help "
    "and advice, free of charge on mobile and landline phones.",
    "Analysis of the volume of calls to the 105 helpline provides a useful indicator of the "
    "scale of customer impact across the DNOs and the timeframe for disruption to power "
    "supplies with calls dropping off dramatically post 6pm.",
]
E3CI_105 = (
    "Between 16:00 and 18:00 on 9th August, the ESO Technical Report states that 39,568 calls "
    "were made to the 105 Single Emergency Number, a facility introduced since the Christmas "
    "2013 event and managed by the ENA on behalf of members."
)
TAB8_CAPTION = "Table 8 – Timeline of external communications"
TAB9_CAPTION = "Table 9 - Calls received by the 6 largest DNOs, during the period 4pm to 7pm on 9th August"

#: Personal names in ESO Table 8 are replaced by the role in square brackets (roles are given in
#: the same report: section 7 names the video's speaker as the Head of National Control).
NAME_REDACTIONS = {
    "Julian Leslie": "[the Head of National Control]",
    "Minister of State Kwasi Kwarteng MP": "Minister of State [name omitted]",
    "Minister of State Kwasi Kwarteng": "Minister of State [name omitted]",
}
PERSONAL_NAMES = (
    "Julian Leslie",
    "Kwasi Kwarteng",
    "Andrea Leadsom",
    "Jonathan Brearley",
)


def redact(text: str) -> str:
    for name, role in NAME_REDACTIONS.items():
        text = text.replace(name, role)
    require(
        not any(n in text for n in PERSONAL_NAMES), f"personal name left in {text!r}"
    )
    return text


def _check_cells(inputs: FiInputs, cells: list[str], pages: list[int]) -> list[int]:
    """Each printed cell must occur on one of ``pages``; returns the page of each cell."""
    found = []
    for cell in cells:
        compact = re.sub(r"\s+", "", normalise(cell))
        hit = None
        for page in pages:
            if compact in re.sub(r"\s+", "", normalise(inputs.page("ESO", page))):
                hit = page
                break
        require(hit is not None, f"Table cell {cell!r} not on ESO pages {pages}")
        found.append(hit)
    return found


def table8(inputs: FiInputs) -> tuple[list[dict[str, str]], dict[str, Any]]:
    rows = inputs.catalogue_rows(TAB8)
    require(len(rows) == 11, f"ESO Table 8 rows: {len(rows)}")
    out = []
    cells: list[str] = []
    for row in rows:
        heading = row["day_heading_printed_plus_date"]
        printed_day = heading if heading.startswith("W/C") else heading.split()[0]
        cells += [printed_day, row["time_printed"], row["event_verbatim"]]
        if row["distribution_verbatim"]:
            cells.append(row["distribution_verbatim"])
        out.append(
            {
                "day_as_printed": printed_day,
                "time_as_printed": row["time_printed"],
                "event": redact(row["event_verbatim"]),
                "distribution": row["distribution_verbatim"],
                "pdf_page": row["pdf_page"],
            }
        )
    pages = _check_cells(inputs, [c for c in cells if c.strip()], [30, 31])
    ref = pdf_ref(
        inputs,
        "ESO",
        30,
        "6.3 External Communications with Media and Wider Industry, Table 8 – Timeline of "
        "external communications (continues on PDF page 31)",
        None,
    )
    ref.update(
        kind="report_table",
        catalogue_artifact="ESO-p30-tab8",
        catalogue_extract=f"extracted/{TAB8}",
        catalogue_extract_sha256=inputs.catalogue_sha256(TAB8),
        cells_checked_on_page=len(pages),
        cell_pages=sorted(set(pages)),
        redaction="personal names replaced by the role in square brackets: "
        + "; ".join(sorted(set(NAME_REDACTIONS.values()))),
    )
    return out, ref


def table9(inputs: FiInputs) -> tuple[list[list[str]], dict[str, Any]]:
    rows = inputs.catalogue_rows(TAB9)
    require(
        len(rows) == 3 and all(r["row_sum_check"] == "ok" for r in rows), "ESO Table 9"
    )
    cols = ["SSEPD", "ENW", "SPEN", "NPG", "UKPN", "WPD", "TOTAL"]
    out = [[r["time_row_printed"], *(r[c] for c in cols)] for r in rows]
    ref = table_ref(
        inputs,
        "ESO",
        32,
        "6.4 Call volumes to DNO's, Table 9 - Calls received by the 6 largest DNOs, during the "
        "period 4pm to 7pm on 9th August",
        "ESO-p32-tab9",
        TAB9,
        ["DNO", "TIME", *cols, *(c for row in out for c in row)],
    )
    return [["TIME", *cols], *out], ref


# ---------------------------------------------------------------------------------------------
# Part D: REMIT
# ---------------------------------------------------------------------------------------------


def remit_messages(inputs: FiInputs) -> list[dict[str, Any]]:
    rows = []
    for key in ("elexon_remit_details_1", "elexon_remit_details_2"):
        data = inputs.real_json(key)["data"]
        for rec in data:
            if rec["assetId"] in REMIT_UNITS:
                rows.append({**rec, "_source": key})
    ids = [r["id"] for r in rows]
    require(len(ids) == len(set(ids)), "duplicate REMIT message IDs")
    keys = [(r["mrid"], r["revisionNumber"]) for r in rows]
    require(len(keys) == len(set(keys)), "duplicate REMIT revisions")
    rows.sort(
        key=lambda r: (r["assetId"], r["publishTime"], r["mrid"], r["revisionNumber"])
    )
    require(
        len(rows) == 46, f"REMIT messages for the selected units: {len(rows)} != 46"
    )
    return rows


def _num(value: Any) -> str:
    return f"{float(value):.1f}"


def _related(text: str | None) -> str:
    """Participant free text on one line: line breaks and <br> shown as ' / '."""
    if not text:
        return "(none)"
    parts = re.split(r"<br>|\r?\n", text)
    return " / ".join(part.strip() for part in parts if part.strip()) or "(none)"


def remit_line(rec: dict[str, Any]) -> str:
    return (
        f"publishTime {rec['publishTime']} | {rec['assetId']} | message {rec['mrid']} revision "
        f"{rec['revisionNumber']} | participant {rec['participantId']} | "
        f"'{rec['messageHeading']}' | {rec['unavailabilityType']} {rec['eventType'].lower()} | "
        f"status {rec['eventStatus']} | event {rec['eventStartTime']} to {rec['eventEndTime']} | "
        f"normal {_num(rec['normalCapacity'])} MW, available {_num(rec['availableCapacity'])} MW, "
        f"unavailable {_num(rec['unavailableCapacity'])} MW | cause '{rec['cause']}' | related "
        f"information: '{_related(rec.get('relatedInformation'))}'"
    )


def remit_event_id(rec: dict[str, Any]) -> str:
    """The asset-log event ID of a REMIT revision (last digits of the message ID)."""
    return f"R09-REMIT-{rec['mrid'].rsplit('-', 1)[-1]}-r{rec['revisionNumber']}"


def remit_index_line(rec: dict[str, Any]) -> str:
    """One entry of the Part D index (the remaining fields are in the CSV and the rows)."""
    return (
        f"{remit_event_id(rec)} | publishTime {rec['publishTime']} | "
        f"{rec['unavailabilityType']} | status {rec['eventStatus']} | event "
        f"{rec['eventStartTime']} to {rec['eventEndTime']} | available "
        f"{_num(rec['availableCapacity'])} MW"
    )


#: The asset-log signal of a unit's REMIT rows. The value is the capacity a message declares
#: for its own event window, not the unit's capacity at the publication time (the row index).
REMIT_SIGNAL = "{unit} REMIT declared available capacity for event window MW"
#: Statuses of revisions that no longer declare anything (withdrawn or closed messages).
REMIT_VOID_STATUSES = frozenset({"Dismissed", "Inactive"})


def remit_signal(unit: str) -> str:
    return REMIT_SIGNAL.format(unit=unit)


def remit_value(rec: dict[str, Any]) -> float | None:
    """The row's numeric value: the declared available capacity, only for an active revision
    published inside its own event window. A withdrawn (Dismissed) or closed (Inactive)
    revision, or one published before or after its event window, has no value at the row's
    index time (null); its declared figures stay in the row text and the CSV."""
    if rec["eventStatus"] in REMIT_VOID_STATUSES:
        return None
    start, published, end = (
        datetime.fromisoformat(rec[k])
        for k in ("eventStartTime", "publishTime", "eventEndTime")
    )
    if not start <= published <= end:
        return None
    return float(rec["availableCapacity"])


# ---------------------------------------------------------------------------------------------
# Part E: organisational public posts and web statements (gists)
# ---------------------------------------------------------------------------------------------

GIST_0630 = (
    "two generators had a problem that cut power in some parts of the UK; resolved, with the "
    "system back to normal; anyone still affected should get in touch with their local network "
    "operator."
)
GIST_1955 = (
    "updated statement in three posts (the third post's text is not recoverable from the "
    "archive): in an unexpected, unusual event two generators connected to the transmission "
    "system were lost and system frequency fell; the ESO says its plans worked as designed, "
    "cutting off a limited part of demand."
)
GIST_2000 = (
    "an unexpected, unusual event in which two generators connected to the transmission system "
    "were lost and frequency fell; the ESO's plans worked as designed by cutting off a limited "
    "part of demand, which lets the system protect itself and allows quick restoration; reports "
    "that DNOs had restored all demand by 18:30 and that the system was operating normally."
)
GIST_2011 = (
    "a video in which the ESO manager in charge of national control explains further (video "
    "not held)."
)
GIST_1008_CORE = (
    "the ESO does not itself generate electricity, and the root cause did not lie with the ESO's "
    "system; it describes a rare event in which two big generating units, a gas plant and an "
    "offshore wind farm, were lost almost at the same moment (time given as 16.54); other "
    "generators raised output, but not enough, so a backup protection scheme disconnected "
    "selected demand; the DNOs were given the all clear within 15 minutes; reports that DNOs "
    "had reconnected all demand by 17.40."
)
GIST_1930 = (
    "fourth statement: says the industry must understand both the cause and why the power cut "
    "disrupted services so widely, especially transport; welcomes the government's commissioning "
    "of the E3C review and promises to work with it; says the ESO had begun reviewing its own "
    "response internally and was working with Ofgem, local networks and the generators involved."
)
GIST_1308 = (
    "statement on frequency: rejects media reports of earlier near misses or early warnings of "
    "similar incidents; calls the event highly unusual and unprecedented in ten years; says "
    "that until that Friday the system had stayed within the safe frequency limits agreed with "
    "Ofgem; interim findings to be reported to Ofgem that week."
)
GIST_1608 = (
    "confirms that the ESO had delivered its interim report on the event to Ofgem before 6pm "
    "that day, the regulator's deadline; the final report would follow by 6 September; "
    "describes the government's E3C inquiry as a separate, parallel process."
)
GIST_1908 = (
    "announces publication of the ESO's interim technical report; the final report to Ofgem is "
    "due on Friday 6 September."
)


def _post(post_id: int, organisation: str, gist: str, capture: str) -> dict[str, Any]:
    return {
        "kind": "posts",
        "post_ids": [post_id],
        "organisation": organisation,
        "channel": "public social-media post",
        "gist": gist,
        "capture": capture,
    }


TL = "Thameslink (Govia Thameslink Railway)"
LNER = "London North Eastern Railway (LNER)"
NRE = "National Rail Enquiries"
ESO = "National Grid ESO"
WB = "https://web.archive.org/web"
TL_THREAD = (
    f"{WB}/20200829180220/https://twitter.com/TLRailUK/status/1159859425559154688"
)
LNER_THREAD = f"{WB}/20190810100619/https://twitter.com/LNER/status/1159875966426124288"
ESO_1008_THREAD = (
    f"{WB}/20190811085158/https://twitter.com/ng_eso/status/1160091711185571840"
    "?ref_src=twsrc%5Etfw"
)

ITEMS: list[dict[str, Any]] = [
    {
        "kind": "page",
        "source": "nre_incident_228430",
        "organisation": NRE,
        "channel": "service disruption web page (incident 228430)",
        "displayed": [
            "Incident created 09/08/2019 16:50",
            "Last updated 09/08/2019 18:49",
        ],
        "capture_utc": "2019-08-09T17:56:38Z",
        "index_bst": ("2019-08-09", "16:50"),
        "uncertainty_s": 60,
        "recorded": "page displays 'Incident created 09/08/2019 16:50' and 'Last updated "
        "09/08/2019 18:49' (Internet Archive capture 2019-08-09T17:56:38Z)",
        "clock_basis": "times as displayed on the page (no zone shown); index reads the "
        "creation time as BST, UTC+01:00",
        "gist": "disruption notice for all Thameslink and Great Northern routes, with knock-on "
        "effects for East Midlands Trains at St Pancras and LNER at King's Cross; attributes the "
        "stoppage to a 'UK Power Network' failure across much of London and south-east England, "
        "which left trains unable to draw power, most of them stationary; Thameslink trains "
        "running only on the Brighton-Blackfriars/London Bridge section; services liable to "
        "cancellation, delay or revision for the rest of the day.",
    },
    _post(
        1159859425559154688,
        TL,
        "cites an electricity supply failure: services anywhere on its network might be delayed "
        "or cancelled; more information promised.",
        f"{WB}/20200829180220/https://twitter.com/TLRailUK/status/1159859425559154688"
        "?ref_src=twsrc%5Etfw",
    ),
    _post(
        1159863037517598720,
        TL,
        "trains standing still between Farringdon and Bedford, with knock-on effects for "
        "services across its network.",
        f"{WB}/20240802190205/https://twitter.com/TLRailUK/status/1159863037517598720"
        "?ref_src=twsrc%5Etfw",
    ),
    _post(
        1159866619641892864,
        TL,
        "attributes the stoppage to a failure of the power network over much of London and "
        "south-east England, which stopped its Farringdon-Bedford trains drawing power, leaving "
        "most at a standstill; the post links to a DNO's post.",
        f"{WB}/20220728215944/https://twitter.com/TLRailUK/status/1159866619641892864",
    ),
    _post(
        1159869804980973569,
        NRE,
        "power supply problems disrupting many train services; some station information "
        "screens also affected.",
        f"{WB}/20221206020335/https://twitter.com/nationalrailenq/status/1159869804980973569",
    ),
    _post(
        1159871893962416128,
        TL,
        "services only running on the Brighton-Blackfriars/London Bridge section; gathering "
        "information and working to get every service moving.",
        f"{WB}/20220328205934/https://twitter.com/TLRailUK/status/1159871893962416128",
    ),
    _post(
        1159875966426124288,
        LNER,
        "citing a major electricity supply failure, King's Cross services in both directions "
        "suspended; customers told not to travel; Friday tickets valid on Saturday.",
        LNER_THREAD,
    ),
    {
        **_post(1159878953596792833, ESO, GIST_0630, ""),
        "capture": f"{WB}/20191011021532/https://twitter.com/ng_eso/status/1159878953596792833",
        "eso": True,
    },
    {
        "kind": "web",
        "source": "neso_statement_0908_1830",
        "organisation": ESO,
        "channel": "website statement",
        "title": "Power Cut Statement - 9 August, 6.30pm",
        "page_date": "9 Aug 2019",
        "index_bst": ("2019-08-09", "18:30"),
        "uncertainty_s": 300,
        "gist": f"a spokesperson says {GIST_0630}",
        "eso": True,
    },
    _post(
        1159884719284203520,
        TL,
        "advises against travel: no service can be run and there is no estimate yet of when "
        "services will return.",
        TL_THREAD,
    ),
    _post(
        1159884743976083457,
        LNER,
        "King's Cross closed, with no services running to or from London; customers advised to "
        "put off travel until the next day.",
        LNER_THREAD,
    ),
    _post(
        1159885729905938432,
        NRE,
        "London King's Cross station closed to the public to prevent overcrowding; LNER and "
        "Hull Trains Friday tickets valid on Saturday.",
        f"{WB}/20211204122828/https://twitter.com/nationalrailenq/status/1159885729905938432"
        "?s=20",
    ),
    _post(
        1159888608083488769,
        TL,
        "passengers on stopped trains told to stay on board while trains are restarted; if that "
        "takes too long, specialist staff will come to the train to help.",
        TL_THREAD,
    ),
    _post(
        1159891801370759174,
        NRE,
        "Grand Central advising against journeys to or from King's Cross that evening; warns of "
        "knock-on disruption to services the next day.",
        f"{WB}/20250123140337/https://twitter.com/nationalrailenq/status/1159891801370759174",
    ),
    {
        "kind": "posts",
        "post_ids": [1159900904516136961, 1159900906407845889, 1159900908148449280],
        "organisation": ESO,
        "channel": "public social-media posts (thread of three)",
        "gist": GIST_1955,
        "capture": f"{WB}/20190810232631/https://twitter.com/ng_eso/status/1159900904516136961"
        "?ref_src=twsrc%5Etfw",
        "eso": True,
    },
    {
        "kind": "web",
        "source": "neso_statement_0908_2000",
        "organisation": ESO,
        "channel": "website statement",
        "title": "Power Cut Statement - 9 August, 8pm",
        "page_date": "9 Aug 2019",
        "index_bst": ("2019-08-09", "20:00"),
        "uncertainty_s": 300,
        "gist": GIST_2000,
        "eso": True,
    },
    {
        **_post(1159904985976594432, ESO, GIST_2011, ""),
        "capture": f"{WB}/20190810164428/https://twitter.com/ng_eso/status/1159904985976594432",
        "eso": True,
    },
    _post(
        1159910960657772544,
        LNER,
        "expects a rescue engine to clear a failed train from the main line so that King's "
        "Cross services can resume; station still closed; travel advice unchanged.",
        LNER_THREAD,
    ),
    _post(
        1159912641827082240,
        TL,
        "stranded passengers without other options may take taxis, with reasonable costs "
        "refunded on receipt.",
        TL_THREAD,
    ),
    _post(
        1159921617604108290,
        TL,
        "no service north of London for the remainder of the day after the electricity supply "
        "failure; advice not to travel stands.",
        TL_THREAD,
    ),
    _post(
        1159927293931864064,
        LNER,
        "the failed train has been moved and the southbound lines reopened; London-bound "
        "services departing, with congestion slowing recovery.",
        LNER_THREAD,
    ),
    _post(
        1159937290111717376,
        LNER,
        "the failed train has failed again; its passengers will be moved to another train before "
        "the London-bound line can reopen.",
        LNER_THREAD,
    ),
    _post(
        1159952501048844288,
        TL,
        "no more services that day; disruption expected to last until about noon the next day.",
        TL_THREAD,
    ),
    _post(
        1160047064480387077,
        TL,
        "services would stay disrupted that day because trains and crews had been left out of "
        "position; passengers advised to allow extra time and plan ahead.",
        TL_THREAD,
    ),
    {
        "kind": "posts",
        "post_ids": [
            1160091702910246912,
            1160091704617263104,
            1160091706643111939,
            1160091707964370944,
            1160091709432311808,
            1160091711185571840,
        ],
        "organisation": ESO,
        "channel": "public social-media posts (thread of six)",
        "gist": f"third statement, in six posts: {GIST_1008_CORE}",
        "capture": ESO_1008_THREAD,
        "eso": True,
    },
    {
        "kind": "web",
        "source": "neso_statement_1008_0830",
        "organisation": ESO,
        "channel": "website statement",
        "title": "Power Cut Statement - 10 August, 8.30am",
        "page_date": "10 Aug 2019",
        "index_bst": ("2019-08-10", "08:30"),
        "uncertainty_s": 300,
        "gist": f"third statement: {GIST_1008_CORE}",
        "eso": True,
    },
    _post(
        1160101138043154432,
        TL,
        "services getting back to normal after the previous day's electricity supply failure; "
        "passengers advised to allow extra time.",
        TL_THREAD,
    ),
    {
        "kind": "page",
        "source": "nre_today_20190810",
        "organisation": NRE,
        "channel": "service disruption web page ('today')",
        "displayed": [
            "Incident created 09/08/2019 16:50",
            "Last updated 10/08/2019 16:51",
        ],
        "capture_utc": "2019-08-10T19:05:51Z",
        "index_bst": ("2019-08-10", "16:51"),
        "uncertainty_s": 60,
        "recorded": "page displays 'Incident created 09/08/2019 16:50' and 'Last updated "
        "10/08/2019 16:51' (Internet Archive capture 2019-08-10T19:05:51Z)",
        "clock_basis": "times as displayed on the page (no zone shown); index reads the "
        "last-updated time as BST, UTC+01:00",
        "gist": "next-day notice: after Friday's disruption, trains and crews ended the day out "
        "of position, so more cancellations were expected from crew shortages, mainly on routes "
        "from Moorgate and King's Cross; Thameslink no longer affected by Friday's power "
        "problems; again attributes the cause to a 'UK Power Network' failure across London "
        "and south-east England, which it says also affected airports.",
    },
    {
        "kind": "web",
        "source": "neso_statement_1008_1930",
        "organisation": ESO,
        "channel": "website statement",
        "title": "Power Cut Statement - 10 August, 7.30pm",
        "page_date": "10 Aug 2019",
        "index_bst": ("2019-08-10", "19:30"),
        "uncertainty_s": 300,
        "gist": GIST_1930,
        "eso": True,
    },
    {
        "kind": "web",
        "source": "neso_statement_1308",
        "organisation": ESO,
        "channel": "website statement",
        "title": "Power Cut Statement on Frequency - 13 August",
        "page_date": "13 Aug 2019",
        "index_bst": ("2019-08-13", "12:00"),
        "uncertainty_s": 43200,
        "gist": GIST_1308,
        "eso": True,
    },
    {
        "kind": "web",
        "source": "neso_statement_1608",
        "organisation": ESO,
        "channel": "website statement",
        "title": "National Grid ESO confirms submission of interim technical report into the "
        "power outages of 9th August, to Ofgem",
        "page_date": "16 Aug 2019",
        "index_bst": ("2019-08-16", "12:00"),
        "uncertainty_s": 43200,
        "gist": GIST_1608,
        "eso": True,
    },
    {
        "kind": "web",
        "source": "neso_statement_1908",
        "organisation": ESO,
        "channel": "website statement",
        "title": "Interim technical report into the power outages of Friday 9 August",
        "page_date": "19 Aug 2019",
        "index_bst": ("2019-08-19", "12:00"),
        "uncertainty_s": 43200,
        "gist": GIST_1908,
        "eso": True,
    },
]
# The six DNO posts of increment A's R07 Part D (same organisations, gists and captures).
for _dno in DNO_POSTS:
    ITEMS.append(
        {
            **_post(
                _dno["post_id"],
                _dno["organisation"],
                _dno["summary"].removeprefix("gist: "),
                _dno["archive_url"],
            ),
            "from_r07": True,
        }
    )


def item_index(item: dict[str, Any]) -> tuple[datetime, float, str]:
    """(index instant UTC, uncertainty s, recorded time text) of a Part E item."""
    if item["kind"] == "posts":
        times = [post_time(pid) for pid in item["post_ids"]]
        first, last = min(times), max(times)
        if len(times) == 1:
            recorded = f"post identifier decodes to {utc_z(first, ms=True)}"
        else:
            recorded = f"post identifiers decode to {utc_z(first, ms=True)} - {utc_z(last, ms=True)}"
        return first, max(1.0, (last - first).total_seconds()), recorded
    day, clock = item["index_bst"]
    when = bst_to_utc(day, clock)
    if item["kind"] == "web":
        if item["uncertainty_s"] >= 43200:
            recorded = f"page date '{item['page_date']}' (no time shown)"
        else:
            recorded = f"page title '{item['title']}'; page date '{item['page_date']}'"
        return when, float(item["uncertainty_s"]), recorded
    return when, float(item["uncertainty_s"]), item["recorded"]


def item_when_text(item: dict[str, Any]) -> str:
    if item["kind"] == "posts":
        times = [post_time(pid).replace(microsecond=0) for pid in item["post_ids"]]
        if len(times) == 1:
            return utc_z(times[0])
        return f"{utc_z(min(times))} to {utc_z(max(times))}"
    if item["kind"] == "web":
        if item["uncertainty_s"] >= 43200:
            return f"page dated {item['page_date']}"
        return f"page titled '{item['title']}', dated {item['page_date']}"
    return item["recorded"]


def item_time_columns(item: dict[str, Any]) -> tuple[str, str]:
    """(time_basis, time_utc) of a Part E item for the CSV. time_utc is filled only where the
    time is a UTC instant decoded from a post identifier (the first post of a thread); page
    times are local or dates only and are not converted."""
    if item["kind"] == "posts":
        first = min(post_time(pid) for pid in item["post_ids"]).replace(microsecond=0)
        if len(item["post_ids"]) == 1:
            return "decoded from the post identifier (UTC)", utc_z(first)
        return (
            "decoded from the post identifiers (UTC); time_utc is the thread's first post",
            utc_z(first),
        )
    if item["kind"] == "web":
        if item["uncertainty_s"] >= 43200:
            return "page date only (no time shown)", ""
        return "time in the page title (UK local time); page date as shown", ""
    return (
        "page-displayed times (no zone shown) with the Internet Archive capture time (UTC)",
        "",
    )


def _post_texts(inputs: FiInputs) -> dict[str, dict[str, str]] | None:
    emb = inputs.optional_real_bytes("comms_posts_embedded")
    idx = inputs.optional_real_bytes("comms_posts_index")
    if emb is None or idx is None:
        return None
    out: dict[str, dict[str, str]] = {}
    for row in csv.DictReader(io.StringIO(idx.decode("utf-8"))):
        out[row["tweet_id"]] = {
            "text": row["best_text"],
            "capture": row["wayback_capture"],
            "account_type": "organisation",
        }
    for row in csv.DictReader(io.StringIO(emb.decode("utf-8"))):
        if row["tweet_id"] == "redacted":
            continue
        entry = out.setdefault(row["tweet_id"], {"text": "", "capture": ""})
        if row["text"].strip():
            entry["text"] = row["text"]
        entry["found_in"] = row["found_in"]
        entry["account_type"] = row["account_type"]
    return out


def _timeline(inputs: FiInputs) -> dict[str, str] | None:
    """post ID -> UK local time in the derived communications timeline (when held)."""
    raw = inputs.optional_real_bytes("comms_timeline")
    if raw is None:
        return None
    out = {}
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
        match = re.search(r"/status/(\d+)", row["source_url"])
        if match and row["channel"] == "Twitter":
            out[match.group(1)] = row["time_uk_local"]
    return out


def _captures(entry: dict[str, str]) -> list[str]:
    """Wayback URLs that hold a post: its own capture and the capture it was found in."""
    out = [entry["capture"]] if entry.get("capture") else []
    found = entry.get("found_in", "")
    match = re.fullmatch(r"wayback_(\d{14})_([A-Za-z0-9_]+)_(\d+)\.html", found)
    if match:
        stamp, account, post_id = match.groups()
        out.append(f"{WB}/{stamp}/https://twitter.com/{account}/status/{post_id}")
    return out


def _check_item(
    inputs: FiInputs, item: dict[str, Any], texts, timeline: dict[str, str] | None
) -> dict[str, Any]:
    """Verify an item against the held sources; return its gist provenance reference."""
    if item["kind"] == "posts":
        cross = []
        for pid in item["post_ids"]:
            local = (post_time(pid) + BST_OFFSET).strftime("%Y-%m-%d %H:%M:%S")
            if timeline is not None and str(pid) in timeline:
                require(
                    timeline[str(pid)] == local, f"post {pid}: timeline time differs"
                )
            cross.append(
                {
                    "source_id": "comms_timeline",
                    "post_id": str(pid),
                    "uk_local_time_from_identifier": local,
                    "rule": "when the post has its own row in the timeline, that row's time must "
                    "equal the decoded time (checked when the timeline is held)",
                }
            )
        original = None
        if texts is not None:
            parts = []
            for pid in item["post_ids"]:
                entry = texts.get(str(pid))
                require(entry is not None, f"post {pid} not in the archived-post data")
                require(
                    entry.get("account_type") == "organisation",
                    f"post {pid} not organisational",
                )
                parts.append(entry["text"])
            original = "\n".join(parts)
            require(original.strip(), f"posts {item['post_ids']}: no text held")
            accepted = _captures(texts[str(item["post_ids"][0])])
            require(
                any(item["capture"].split("?")[0] == c.split("?")[0] for c in accepted),
                f"post {item['post_ids'][0]}: capture {item['capture']} not in {accepted}",
            )
        key = "comms_posts_embedded"
        return gist_ref(
            inputs,
            key,
            item["gist"],
            original=original if original is not None else "",
            post_ids=[str(x) for x in item["post_ids"]],
            decoded_utc=[utc_z(post_time(x), ms=True) for x in item["post_ids"]],
            archive_url=item["capture"],
            note="time decoded from the post identifier; gist written for this record from "
            "the archived post text (not openly licensed; not reproduced)",
            timeline_cross_check=cross,
        )
    key = item["source"]
    if item["kind"] == "page":
        for shown in item["displayed"]:
            inputs.check_text_quote(key, shown)
        return gist_ref(
            inputs, key, item["gist"], original=None, displayed=item["displayed"]
        )
    inputs.check_text_quote(key, item["title"])
    inputs.check_text_quote(key, item["page_date"])
    return gist_ref(inputs, key, item["gist"], original=None, title=item["title"])


# ---------------------------------------------------------------------------------------------
# Part F: Ofgem and GOV.UK (Open Government Licence)
# ---------------------------------------------------------------------------------------------

OFGEM_0812 = [
    "Ofgem has written to the National Grid Electricity System Operator requesting an urgent "
    "interim report into the incident on 9 August 2019 to be provided to Ofgem by Friday 16 "
    "August.",
    "A final, detailed technical report must be provided to Ofgem by Friday 6 September.",
]
BEIS_0814 = [
    "National Grid has said power cuts had “nothing to do with changes in wind speed or the "
    "variability of wind”",
    "The government today (14 August 2019) set out the scope of its review into the actions of "
    "the National Grid Electricity System Operator after Friday’s power cuts.",
    "The committee met for the first time on Monday (12 August) and will provide a report on "
    "initial findings within 5 weeks to the Secretary of State for Business, Energy and "
    "Industrial Strategy.",
    "It will then submit a comprehensive report within 12 weeks.",
    "This review will complement the investigation being undertaken by energy regulator Ofgem "
    "into how the electricity operator responded in line with its licence conditions and "
    "system security standards.",
]
GOVUK_REVIEW = [
    "On Friday 9 August 2019 a power disruption resulted from the operation of Low Frequency "
    "Demand Disconnection relays on the Great Britain power system at about 4:54 pm.",
    "Though demand was fully restored within 90 minutes, the secondary impacts continued to be "
    "felt for much of the day.",
]
OFGEM_0820 = [
    "Ofgem has launched an investigation into the power cuts of Friday 9 August, following an "
    "initial report from National Grid Electricity System Operator (NGESO).",
    "It will also seek to establish whether any of the parties involved – National Grid ESO, "
    "National Grid Electricity Transmission, 12* distribution network operators in England and "
    "Wales, as well as generators RWE Generation (Little Barford Power station) and Orsted "
    "(Hornsea) - breached their licence conditions.",
    "Ofgem is liaising with the rail regulator (Office of Rail and Road) and will be engaging "
    "with the rail authorities to understand better why the drop in frequency on the energy "
    "network led to disruption for passengers.",
    "The opening of this investigation does not imply that Ofgem has made any findings about "
    "non-compliance for any of the companies mentioned at this early stage of the "
    "investigation.",
]
#: Terms that must not appear in the agent-visible record (decision 50 leakage guard).
FORBIDDEN = re.compile(
    r"£|\b(?:4\.5|10\.5|1\.5) ?m(?:illion)?\b|voluntary payment|redress|penalt|\bfined\b"
    r"|settlement",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------------


def _report_clock(source: str) -> str:
    return REPORT_CLOCK.format(source=source)


def _row(
    entry_id: str,
    recorded: str,
    clock_basis: str,
    when: datetime,
    uncertainty: float,
    frm: str | None,
    to: str | None,
    channel: str,
    text: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "kind": "control",
        "entry_id": entry_id,
        "evidence_id": DOC_ID,
        "room_id": ROOM_ID,
        "recorded_time": recorded,
        "clock_basis": clock_basis,
        "index_time_utc": utc_z(when, ms=when.microsecond != 0),
        "index_uncertainty_s": uncertainty,
        "from": frm,
        "to": to,
        "channel": channel,
        "text": text,
        "value_status": "reported",
        "provenance": provenance,
    }


def build(inputs: FiInputs) -> FiDocBuild:
    doc = TextDoc(DOC_ID)
    build = FiDocBuild(
        doc_id=DOC_ID,
        title=TITLE,
        owner="National Grid ESO (technical report, appendices and public statements); Energy "
        "Emergencies Executive Committee (interim and final reports); Ofgem (report and press "
        "releases); BEIS (GOV.UK); Elexon (REMIT data); DNOs, train operators and National Rail "
        "Enquiries (public posts and pages; gists written for this record)",
        category="communications_records",
        record_type="report transcriptions and quotations on communications with government, "
        "the regulator, the media and the public; real Elexon REMIT messages; times and short "
        "builder-written gists of organisational public posts and web statements; Ofgem and "
        "GOV.UK publications quoted",
        construction="",
        text=doc,
        label=LABEL_REAL_AND_TABLES,
        status_scope="Nothing in Parts A-D and F is synthesised. Part E is not a transcription: "
        "for each organisational post or web statement it gives the time (decoded, displayed "
        "or titled) and a short gist written for this record; the text is not reproduced. "
        "Personal names are replaced by roles in square brackets.",
        party_aliases=[
            "system operator",
            "National Grid ESO",
            "Elexon",
            "DNO",
            "regulator",
        ],
    )
    build.header(
        "National Grid ESO; Energy Emergencies Executive Committee (E3C); Ofgem; Department for "
        "Business, Energy and Industrial Strategy (BEIS, GOV.UK); Elexon Limited (BMRS / "
        "Insights REMIT data written by market participants); distribution network operators, "
        "train operators and National Rail Enquiries (public posts and web pages)",
        wrap(
            "Clock reference: report times are printed without a zone; the reports give event "
            "times in local time (BST, UTC+01:00). Elexon REMIT times are UTC (Z); the "
            "participants' free text may state BST. Post times in Part E are UTC, decoded from "
            "the post identifiers; web statements carry a date and, for some, a time in the "
            "page title (UK local time); archived web pages show times without a zone. GOV.UK "
            "times carry explicit offsets."
        ),
    )
    rows: list[dict[str, Any]] = []

    # ---- Part A ------------------------------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part A heading",
        "PART A — ESO ACCOUNTS OF ITS CONTACTS WITH GOVERNMENT AND THE REGULATOR (quoted as "
        "printed)",
    )
    seg = doc.segment(
        "A1 ESO technical report section 6.2",
        "reported",
        "quotation",
        [
            pdf_ref(
                inputs, "ESO", 30, "6.2 Engagement with government and the regulator", s
            )
            for s in ESO_62
        ],
    )
    doc.add(
        seg,
        *p(
            "A1",
            "National Grid ESO, Technical Report on the events of 9 August 2019 (6 September "
            "2019), section 6.2 'Engagement with government and the regulator', quoted:",
        ),
        *(line for s in ESO_62 for line in q(s)),
    )
    eso62_clock = _report_clock("the ESO technical report, section 6.2")
    for n, (clock, to, what, quote) in enumerate(
        [
            (
                "17:41hrs",
                "BEIS",
                "first communication between the ESO control room and BEIS",
                ESO_62[0],
            ),
            ("17:51hrs", "Ofgem", "first communication with Ofgem", ESO_62[2]),
            ("18:17hrs", "Ofgem", "further communication with Ofgem", ESO_62[2]),
            ("18:45hrs", "Ofgem", "further communication with Ofgem", ESO_62[2]),
            (
                "18:09hrs",
                "BEIS",
                "further update to BEIS from the ESO control room",
                ESO_62[3],
            ),
            (
                "19:29hrs",
                "BEIS",
                "further update to BEIS from the ESO control room",
                ESO_62[3],
            ),
            (
                "19:38hrs",
                "BEIS",
                "further update to BEIS from the ESO control room",
                ESO_62[3],
            ),
        ],
        1,
    ):
        rows.append(
            _row(
                f"R09-A1-{n}",
                clock,
                eso62_clock,
                bst_to_utc("2019-08-09", clock[:5]),
                60,
                "ESO control room",
                to,
                "contact (means not stated)",
                f"ESO technical report, section 6.2: {what} at {clock} [reported]. Quoted: "
                f'"{quote}"',
                {
                    "segment": "A1",
                    "sources": [pdf_ref(inputs, "ESO", 30, "6.2", quote)],
                },
            )
        )

    seg = doc.segment(
        "A2 ESO technical report section 7 (communications finding)",
        "reported",
        "quotation",
        [pdf_ref(inputs, "ESO", 33, "7. Report Findings", s) for s in ESO_7],
    )
    doc.add(
        seg,
        *p(
            "A2",
            "Same report, section 7 'Report Findings', the bullet on communications, quoted:",
        ),
        *(line for s in ESO_7 for line in q(s)),
    )
    eso7_clock = _report_clock("the ESO technical report, section 7")
    for n, (clock, to, channel, what) in enumerate(
        [
            ("17:40", "BEIS", "contact (means not stated)", "ESO contacted BEIS"),
            ("18:00", "Ofgem", "contact (means not stated)", "ESO contacted Ofgem"),
            ("18:27", "media", "media statement", "initial media statement by the ESO"),
            ("20:06", "media", "media statement", "subsequent statement"),
            (
                "20:11",
                "public",
                "video",
                "video from the Head of National Control posted",
            ),
        ],
        1,
    ):
        rows.append(
            _row(
                f"R09-A2-{n}",
                clock,
                eso7_clock,
                bst_to_utc("2019-08-09", clock),
                60,
                "ESO",
                to,
                channel,
                f"ESO technical report, section 7: {what} at {clock} [reported]. Quoted: "
                f'"{" ".join(ESO_7)}"',
                {
                    "segment": "A2",
                    "sources": [pdf_ref(inputs, "ESO", 33, "7", s) for s in ESO_7],
                },
            )
        )

    seg = doc.segment(
        "A3 ESO appendices, Appendix M answers to E3C questions (Q34)",
        "reported",
        "quotation",
        [
            pdf_ref(
                inputs, "APP", 70, "Appendix M – ESO E3C Questions and Answers", APP_M
            )
        ]
        + [pdf_ref(inputs, "APP", 88, "Appendix M, question 34", s) for s in APP_Q34],
    )
    doc.add(
        seg,
        *p(
            "A3",
            "Appendices to the ESO technical report, Appendix M 'ESO E3C Questions and "
            f'Answers\'. Its introduction states: "{APP_M}" Question 34 (asked by the E3C) and '
            "the ESO's answer, quoted:",
        ),
        *(line for s in APP_Q34 for line in q(s)),
    )
    app_clock = _report_clock(
        "Appendix M of the ESO appendices (answers of 28 August 2019)"
    )
    for n, (clock, frm, to, what, uncertainty, index_clock) in enumerate(
        [
            (
                "17:10hrs",
                "ENCC Power System Manager",
                "Head of National Control, ESO",
                "incident reported",
                60,
                "17:10",
            ),
            (
                "17:41hrs",
                "ENCC Power System Manager",
                "BEIS",
                "1st communication with BEIS",
                60,
                "17:41",
            ),
            (
                "just after 18:00hrs",
                "Director of Operations, ESO",
                "Ofgem",
                "1st communication with Ofgem",
                300,
                "18:00",
            ),
            (
                "18:09hrs",
                "ENCC Power System Manager",
                "BEIS",
                "further update to BEIS",
                60,
                "18:09",
            ),
            (
                "19:29hrs",
                "ENCC Power System Manager",
                "BEIS",
                "further update to BEIS",
                60,
                "19:29",
            ),
            (
                "19:38hrs",
                "ENCC Power System Manager",
                "BEIS",
                "further update to BEIS",
                60,
                "19:38",
            ),
        ],
        1,
    ):
        when = bst_to_utc("2019-08-09", index_clock)
        clock_basis = app_clock
        if clock.startswith("just after"):
            clock_basis += (
                "; 'just after 18:00' is indexed at 18:00 BST with a 5-minute window"
            )
        rows.append(
            _row(
                f"R09-A3-{n}",
                clock,
                clock_basis,
                when,
                uncertainty,
                frm,
                to,
                "contact (means not stated)",
                f"ESO answer to E3C question 34 (Appendix M): {what} — {clock} [reported].",
                {
                    "segment": "A3",
                    "sources": [pdf_ref(inputs, "APP", 88, "Q34", APP_Q34[min(n, 4)])],
                },
            )
        )

    # ---- Part B ------------------------------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part B heading",
        "PART B — ACCOUNTS OF EXTERNAL COMMUNICATIONS BY THE ESO AND OTHERS (quoted or "
        "transcribed as printed)",
    )
    t8_rows, t8_ref = table8(inputs)
    seg = doc.segment(
        "B1 ESO section 6.3 and Table 8 (timeline of external communications)",
        "reported",
        "transcription",
        [
            pdf_ref(
                inputs,
                "ESO",
                30,
                "6.3 External Communications with Media and Wider Industry",
                s,
            )
            for s in ESO_63
        ]
        + [t8_ref, pdf_ref(inputs, "ESO", 31, "6.3 Table 8 caption", TAB8_CAPTION)],
        "Table 8 rows as printed (day heading, time, event, distribution); personal names "
        "replaced by the role in square brackets.",
    )
    doc.add(
        seg,
        *p(
            "B1",
            "ESO technical report, section 6.3 'External Communications with Media and Wider "
            "Industry', quoted:",
        ),
        *(line for s in ESO_63 for line in q(s)),
        *cont(
            f'"{TAB8_CAPTION}" (day heading | time | event | distribution), as printed; '
            "personal names replaced by the role in square brackets:"
        ),
        *(
            line
            for r in t8_rows
            for line in tagged(
                f"{r['day_as_printed']} | {r['time_as_printed'] or '(no time)'} | {r['event']} | "
                f"{r['distribution'] or '(blank)'}",
                "reported",
                first="    ",
                indent="      ",
            )
        ),
    )
    t8_days = {"FRIDAY": "2019-08-09", "SATURDAY": "2019-08-10", "SUNDAY": "2019-08-11"}
    for n, r in enumerate(t8_rows, 1):
        day = t8_days.get(r["day_as_printed"])
        clock = r["time_as_printed"]
        if day is None or not clock:
            continue  # week-commencing entry without a time: in the document only
        if "–" in clock:
            start, end = (x.strip() for x in clock.split("–"))
            t0, t1 = bst_to_utc(day, start), bst_to_utc(day, end)
            when = t0 + (t1 - t0) / 2
            uncertainty = (t1 - t0).total_seconds() / 2
        else:
            when, uncertainty = bst_to_utc(day, clock), 60
        rows.append(
            _row(
                f"R09-B1-T8-{n}",
                f"{r['day_as_printed']} {clock}",
                _report_clock("ESO technical report Table 8")
                + "; the day heading gives the date (Friday 9, Saturday 10, Sunday 11 August)",
                when,
                uncertainty,
                "ESO",
                None,
                "external communication (ESO Table 8)",
                f"ESO Table 8: {r['day_as_printed']} {clock} — {r['event']} Distribution: "
                f"{r['distribution'] or '(blank)'} [reported]",
                {"segment": "B1", "sources": [t8_ref], "table_row": n},
            )
        )

    seg = doc.segment(
        "B2 ESO section 6.4 (media statements by others)",
        "reported",
        "quotation",
        [
            pdf_ref(
                inputs, "ESO", 31, "6.4 Communications by industry and consumers", s
            )
            for s in ESO_64
        ],
    )
    doc.add(
        seg,
        *p(
            "B2",
            "ESO technical report, section 6.4 'Communications by industry and consumers', "
            "'Media statements by others', quoted:",
        ),
        *(line for s in ESO_64 for line in q(s)),
    )
    seg = doc.segment(
        "B3 ESO appendices, Appendix M question 35",
        "reported",
        "quotation",
        [pdf_ref(inputs, "APP", 88, "Appendix M, question 35", s) for s in APP_Q35],
    )
    doc.add(
        seg,
        *p(
            "B3",
            "ESO appendices, Appendix M, question 35 and the ESO's answer, quoted:",
        ),
        *(line for s in APP_Q35 for line in q(s)),
    )
    rows.append(
        _row(
            "R09-B3-1",
            "18:27",
            app_clock,
            bst_to_utc("2019-08-09", "18:27"),
            60,
            "ESO",
            "public",
            "external communication",
            "ESO answer to E3C question 35 (Appendix M): external communication seeking to "
            "reassure the public issued at 18:27 [reported].",
            {
                "segment": "B3",
                "sources": [pdf_ref(inputs, "APP", 88, "Q35", APP_Q35[3])],
            },
        )
    )
    seg = doc.segment(
        "B4 E3C interim report (communications, post-event announcement)",
        "reported",
        "quotation",
        [pdf_ref(inputs, "E3C-I", 14, "communications", s) for s in E3CI_14]
        + [pdf_ref(inputs, "E3C-I", 15, "Post-event", E3CI_15)],
    )
    doc.add(
        seg,
        *p(
            "B4",
            "Energy Emergencies Executive Committee, GB power system disruption - 9 August 2019, "
            "interim report (cover dated September 2019), quoted:",
        ),
        *(line for s in [*E3CI_14, E3CI_15] for line in q(s)),
    )
    rows.append(
        _row(
            "R09-B4-1",
            "18:27",
            _report_clock("the E3C interim report"),
            bst_to_utc("2019-08-09", "18:27"),
            60,
            "ESO",
            "public",
            "social media",
            "E3C interim report: updates from the ESO not publicly released until 18:27 via "
            "Twitter [reported].",
            {
                "segment": "B4",
                "sources": [pdf_ref(inputs, "E3C-I", 14, "communications", E3CI_14[2])],
            },
        )
    )
    seg = doc.segment(
        "B5 E3C final report section 5 (communication channels)",
        "reported",
        "quotation",
        [pdf_ref(inputs, "E3C", 20, "5. Communication channels", s) for s in E3C_20]
        + [pdf_ref(inputs, "E3C", 21, "5. Communication channels", E3C_21)],
    )
    doc.add(
        seg,
        *p(
            "B5",
            "Energy Emergencies Executive Committee, GB power system disruption on 9 August "
            "2019: Final report (January 2020), section 5 'Communication channels', quoted:",
        ),
        *(line for s in [*E3C_20, E3C_21] for line in q(s)),
    )
    rows.append(
        _row(
            "R09-B5-1",
            "18:27",
            _report_clock("the E3C final report"),
            bst_to_utc("2019-08-09", "18:27"),
            60,
            "ESO",
            "public",
            "public announcement",
            "E3C final report: first public announcement from ESO issued at 18:27 [reported].",
            {"segment": "B5", "sources": [pdf_ref(inputs, "E3C", 20, "5", E3C_20[0])]},
        )
    )
    ofg_323 = " ".join([*OFG_323_P29, OFG_323_P30])
    seg = doc.segment(
        "B6 Ofgem report paragraph 3.23 (Hornsea 1 communication with the ESO)",
        "reported",
        "quotation",
        [pdf_ref(inputs, "OFG", 29, "paragraph 3.23", s) for s in OFG_323_P29]
        + [pdf_ref(inputs, "OFG", 30, "paragraph 3.23 (continued)", OFG_323_P30)],
    )
    doc.add(
        seg,
        *p(
            "B6",
            "Ofgem, 9 August 2019 power outage report (3 January 2020), paragraph 3.23, quoted:",
        ),
        *q(ofg_323),
    )

    # ---- Part C ------------------------------------------------------------------------------
    doc.blank()
    doc.frame("Part C heading", "PART C — CALLS TO THE DNOs' 105 HELPLINE (as printed)")
    t9, t9_ref = table9(inputs)
    seg = doc.segment(
        "C1 ESO section 6.4 call volumes and Table 9",
        "reported",
        "transcription",
        [pdf_ref(inputs, "ESO", 31, "6.4 Call volumes to DNO's", s) for s in ESO_105]
        + [t9_ref, pdf_ref(inputs, "ESO", 32, "Table 9 caption", TAB9_CAPTION)],
        "Table 9 cells as printed (thousands separators kept).",
    )
    doc.add(
        seg,
        *p("C1", "ESO technical report, section 6.4, 'Call volumes to DNO's', quoted:"),
        *(line for s in ESO_105 for line in q(s)),
        *cont(f'"{TAB9_CAPTION}", as printed (row label TIME, columns by DNO):'),
        *(
            line
            for row in t9
            for line in (
                [f"    {' | '.join(row)}"]
                if row[0] == "TIME"
                else tagged(" | ".join(row), "reported")
            )
        ),
    )
    seg = doc.segment(
        "C2 E3C interim report on 105 calls",
        "reported",
        "quotation",
        [pdf_ref(inputs, "E3C-I", 14, "communications", E3CI_105)],
    )
    doc.add(seg, *p("C2", "E3C interim report, quoted:"), *q(E3CI_105))

    # ---- Part D: REMIT -----------------------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part D heading",
        "PART D — ELEXON REMIT MESSAGES FOR HORNSEA ONE AND LITTLE BARFORD (real extract)",
    )
    remit = remit_messages(inputs)
    units = list(REMIT_UNITS)
    types = sorted({r["eventType"] for r in remit})
    require(len(types) == 1, f"REMIT event types: {types}")
    event_types = f"every revision has event type '{types[0]}'"
    # One segment for Part D: the source description, the pointer to the full fields and the
    # index of revisions (one entry per revision; every field stays in the CSV and the rows).
    seg = doc.segment(
        "D REMIT source description and index of revisions",
        "reported",
        "script",
        [
            data_ref(
                key,
                "messages of the four units: message IDs "
                + ", ".join(str(r["id"]) for r in remit if r["_source"] == key),
            )
            for key in ("elexon_remit_details_1", "elexon_remit_details_2")
        ],
        "Index of revisions: event ID, publishTime, unavailability and event type, status, "
        "event window and available capacity, values unchanged; every other field is in the "
        "CSV and in the asset-log rows.",
    )
    lines = [
        *p(
            "D1",
            "Source: Elexon Insights REMIT messages (endpoint /remit, retrieved by message ID on "
            f"2026-10-20). Licence: Elexon BMRS open data licence. {ELEXON_ATTRIBUTION} Message "
            "content is written by the market participant. Selection: every message revision "
            f"held for BM units {', '.join(units[:3])} (Hornsea One) and {units[3]} (Little "
            f"Barford main unit); this selection has {len(remit)} revisions. A gap in a "
            "message's revision numbers means that revision was not retrieved, not that it does "
            "not exist. Times are UTC; capacities in MW.",
        ),
        *cont(
            f"Every field of every revision is in file {F_REMIT} (participant, message heading, "
            "unavailability and event type, status, event start and end, normal, available and "
            "unavailable capacity, cause, the participant's free text and the outage profile) "
            "and in the asset logs of HORNSEA-ONE and LITTLE-BARFORD (query_asset_log), where "
            "each revision is one row citing R09 with the event ID given below (line breaks in "
            "the free text are shown there as ' / '). Index of "
            "revisions, per unit in order of publishTime: event ID | publishTime | "
            f"unavailability type ({event_types}) | status | event start to end | available "
            "capacity."
        ),
    ]
    for unit in units:
        unit_rows = [r for r in remit if r["assetId"] == unit]
        lines.append(f"    {unit} ({len(unit_rows)} revisions):")
        for rec in unit_rows:
            lines += tagged(
                remit_index_line(rec), "reported", first="      ", indent="        "
            )
    doc.add(seg, *lines)
    for unit in units:
        for rec in (r for r in remit if r["assetId"] == unit):
            build.asset_rows.append(
                {
                    "kind": "asset",
                    "event_id": remit_event_id(rec),
                    "evidence_id": DOC_ID,
                    "asset_id": REMIT_UNITS[unit],
                    "recorded_time": f"publishTime {rec['publishTime']}",
                    "clock_basis": "UTC (Elexon REMIT publishTime with Z); the message's event "
                    "times are UTC; participant free text may state BST",
                    "index_time_utc": rec["publishTime"],
                    "index_uncertainty_s": 0,
                    "signal": remit_signal(unit),
                    "value": remit_value(rec),
                    "unit": "MW",
                    "text": f"REMIT message published: {remit_line(rec)}.",
                    "value_status": "reported",
                    "provenance": {
                        "source_id": rec["_source"],
                        "file": SOURCES[rec["_source"]]["rel"],
                        "sha256": SOURCES[rec["_source"]]["sha256"],
                        "record": {k: v for k, v in rec.items() if k != "_source"},
                    },
                }
            )

    # ---- Part E: public posts and web statements ---------------------------------------------
    doc.blank()
    seg = doc.segment("Part E heading and method", "framing", "framing", [])
    doc.add(
        seg,
        "PART E — ORGANISATIONAL PUBLIC POSTS AND WEB STATEMENTS, 9-19 AUGUST 2019 (times real;",
        "gists written for this record, not the text)",
        *wrap(
            "Organisational posts on a public social-media platform and organisations' web "
            "pages, located in Internet Archive captures or on the publishers' sites. A post "
            "time is decoded from the post identifier (milliseconds since 1970-01-01T00:00:00Z "
            "= (identifier >> 22) + 1288834974657) and shown in UTC to the second; a web "
            "statement is dated as the page shows, with the time in its title where it has "
            "one; an archived page shows its own displayed times. The text is the publisher's "
            "copyright (not an open licence) and is neither reproduced nor closely "
            "paraphrased: each entry gives the time, the organisation, the channel and a short "
            "gist written for this record, whose [reported] tag marks what the organisation "
            "said, not its words. Replies to members of the public, personal accounts, handles "
            "and personal names are not included."
        ),
    )
    texts = _post_texts(inputs)
    timeline = _timeline(inputs)
    ordered = sorted(ITEMS, key=lambda it: (item_index(it)[0], it["organisation"]))
    public_rows = []
    for n, item in enumerate(ordered, 1):
        ref = _check_item(inputs, item, texts, timeline)
        when, uncertainty, recorded = item_index(item)
        label = f"E{n}"
        seg = doc.segment(
            f"{label} {item['organisation']} {item['channel']}",
            "reported",
            "paraphrase",
            [ref],
        )
        line = (
            f"{item_when_text(item)} | {item['organisation']} | {item['channel']} | gist: "
            f"{item['gist']}"
        )
        doc.add(seg, *tagged(line, "reported", first=f"{label:<4}", indent="    "))
        public_rows.append(
            [
                label,
                item_when_text(item),
                *item_time_columns(item),
                item["organisation"],
                item["channel"],
                item["gist"],
            ]
        )
        if item.get("eso"):
            if item["kind"] == "posts":
                clock_basis = "UTC decoded from the post identifier(s)"
            elif item["uncertainty_s"] >= 43200:
                clock_basis = (
                    "page date only (no time shown); indexed at 12:00 BST with a "
                )
                clock_basis += "12-hour window"
            else:
                clock_basis = (
                    "time in the page title (UK local time, BST); 5-minute window"
                )
            rows.append(
                _row(
                    f"R09-{label}",
                    recorded,
                    clock_basis,
                    when,
                    uncertainty,
                    "ESO",
                    "public",
                    item["channel"],
                    f"{item['organisation']} {item['channel']}: gist written for this record "
                    f"(text not reproduced): {item['gist']} [reported]",
                    {"segment": label, "sources": [ref]},
                )
            )

    # ---- Part F: Ofgem and GOV.UK --------------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part F heading",
        "PART F — REGULATOR AND GOVERNMENT PUBLICATIONS, 12-20 AUGUST 2019 (quoted; Open "
        "Government Licence)",
    )
    for label, key, intro, quotes in (
        (
            "F1",
            "ofgem_pr_20190812",
            "Ofgem press release 'Ofgem sets timeline for National Grid ESO report following UK "
            "power failures', publication date 12 August 2019, quoted:",
            OFGEM_0812,
        ),
        (
            "F2",
            "govuk_beis_20190814",
            "BEIS press release on GOV.UK 'Business Secretary sets out scope of investigation "
            "into power cuts', first published 2019-08-14T11:15:35+01:00, quoted:",
            BEIS_0814,
        ),
        (
            "F3",
            "govuk_review_collection",
            "GOV.UK publication page 'Great Britain power system disruption review', first "
            "published 2019-08-14T11:15:00+01:00; the page's history records updates on "
            "2019-10-04 (interim report published) and 2020-01-03 (final review report "
            "published), and the record does not show which update introduced which sentence. "
            "Page text as retrieved on 2026-10-20, quoted:",
            GOVUK_REVIEW,
        ),
        (
            "F4",
            "ofgem_pr_20190820",
            "Ofgem press release 'Ofgem launches investigation into power cuts', publication "
            "date 20 August 2019, quoted:",
            OFGEM_0820,
        ),
    ):
        seg = doc.segment(
            f"{label} {SOURCES[key]['title']}",
            "reported",
            "quotation",
            [quote_ref(inputs, key, "quoted sentence", s) for s in quotes],
        )
        doc.add(seg, *p(label, intro), *(line for s in quotes for line in q(s)))
    for key, dated in (
        ("ofgem_pr_20190812", "12 August 2019"),
        ("ofgem_pr_20190820", "20 August 2019"),
    ):
        inputs.check_text_quote(key, dated)

    doc.blank()
    doc.frame(
        "Part G: what the record does not contain",
        "PART G — NOTES",
        *p(
            "G1",
            "This record holds no ESO control-room communication log or call recordings, and no "
            "text of the public posts or web statements in Part E.",
        ),
    )

    text = "\n".join(doc.lines)
    hit = FORBIDDEN.search(text)
    require(
        hit is None, f"R09 contains an excluded term: {hit.group(0) if hit else ''!r}"
    )

    build.construction = (
        "Parts A-C quote and transcribe the ESO technical report (sections 6.2-6.4 and 7, "
        "Tables 8 and 9), Appendix M of its appendices, the E3C interim and final reports and "
        "Ofgem paragraph 3.23, every quotation and table cell checked on the stated PDF page "
        "(personal names in Table 8 replaced by roles). Part D indexes every held revision of "
        "the REMIT messages of T_HOWAO-1/2/3 and T_LBAR-1 (real Elexon data, unchanged; all "
        "fields in the CSV and the asset-log rows). Part E "
        "gives, for organisational posts and web statements, the decoded or displayed time and "
        "a gist written for this record (no gist shares more than three consecutive words with "
        "its source; not openly licensed). Part F quotes Ofgem and GOV.UK publications of "
        "12-20 August 2019 (Open Government Licence). Ofgem's January 2020 enforcement "
        "settlements are excluded."
    )
    build.control_rows.extend(rows)

    # ---- Artifacts -----------------------------------------------------------------------------
    build.add_artifact(
        Artifact(
            name=F_REMIT,
            media_type="text/csv",
            description="Elexon REMIT message revisions for T_HOWAO-1/2/3 and T_LBAR-1 (Part "
            "D), all fields as published (outageProfile as compact JSON).",
            data=csv_bytes(
                REMIT_FIELDS,
                [
                    [
                        (
                            json.dumps(rec[f], separators=(",", ":"))
                            if f in rec
                            else None
                        )
                        if f == "outageProfile"
                        else rec.get(f)
                        for f in REMIT_FIELDS
                    ]
                    for rec in remit
                ],
            ),
            provenance={
                "extraction_method": "script",
                "builder": BUILDER,
                "inputs": [
                    {
                        "source_id": k,
                        "file": SOURCES[k]["rel"],
                        "sha256": SOURCES[k]["sha256"],
                    }
                    for k in ("elexon_remit_details_1", "elexon_remit_details_2")
                ],
                "transformation": "records of the four units, sorted by unit, publishTime, "
                "message and revision; values unchanged",
            },
        )
    )
    build.add_artifact(
        Artifact(
            name=F_TAB8,
            media_type="text/csv",
            description="ESO technical report Table 8 (timeline of external communications) as "
            "printed; personal names replaced by roles in square brackets.",
            data=csv_bytes(
                [
                    "day_as_printed",
                    "time_as_printed",
                    "event_as_printed",
                    "distribution_as_printed",
                ],
                [
                    [
                        r["day_as_printed"],
                        r["time_as_printed"],
                        r["event"],
                        r["distribution"],
                    ]
                    for r in t8_rows
                ],
            ),
            provenance={
                "extraction_method": "transcription",
                "builder": BUILDER,
                "inputs": [{"catalogue_extract": f"extracted/{TAB8}"}],
                "transformation": "cells as printed; personal names replaced by roles",
            },
        )
    )
    build.add_artifact(
        Artifact(
            name=F_TAB9,
            media_type="text/csv",
            description="ESO technical report Table 9 (calls received by the six largest DNOs, "
            "4pm to 7pm on 9 August) as printed.",
            data=csv_bytes(t9[0], t9[1:]),
            provenance={
                "extraction_method": "transcription",
                "builder": BUILDER,
                "inputs": [{"catalogue_extract": f"extracted/{TAB9}"}],
                "transformation": "cells as printed (thousands separators kept)",
            },
        )
    )
    build.add_artifact(
        Artifact(
            name=F_PUBLIC,
            media_type="text/csv",
            description="Part E: organisational public posts and web statements — label, time "
            "(decoded UTC, displayed or titled), the basis of that time, the decoded UTC instant "
            "of posts (empty for web pages, whose times are local or dates only), organisation, "
            "channel and a gist written for this record (no post or page text).",
            data=csv_bytes(
                [
                    "label",
                    "time",
                    "time_basis",
                    "time_utc",
                    "organisation",
                    "channel",
                    "gist_written_for_this_record",
                ],
                public_rows,
            ),
            provenance={
                "extraction_method": "paraphrase",
                "builder": BUILDER,
                "inputs": [
                    {"source_id": "comms_posts_embedded"},
                    {"source_id": "comms_posts_index"},
                    *(
                        {"source_id": it["source"]}
                        for it in ITEMS
                        if it["kind"] != "posts"
                    ),
                ],
                "transformation": "times decoded or as displayed; gists written for this "
                "record; no post or page text",
            },
        )
    )
    return build


REMIT_CLOCK_NOTE = (
    "R09 rows — recorded_time is the Elexon REMIT publishTime (UTC); the index is the "
    "publication time, not the event time. The value is the available capacity the message "
    "declares for its event window, given only for an active revision published inside that "
    "window; it is null for a Dismissed or Inactive revision and for a message published before "
    "or after its event window (the declared figures stay in the row text)."
)
ASSET_LOG_CONTRIB = [
    {
        "asset_id": "HORNSEA-ONE",
        "signals": [remit_signal(u) for u in ("T_HOWAO-1", "T_HOWAO-2", "T_HOWAO-3")],
        "evidence_ids": [DOC_ID],
        "clock_note_proposal": REMIT_CLOCK_NOTE,
        "source_note_proposal": "R09: Elexon REMIT messages (real extracts; Elexon BMRS open data "
        "licence, attribution required; message content written by the market participant).",
    },
    {
        "asset_id": "LITTLE-BARFORD",
        "signals": [remit_signal("T_LBAR-1")],
        "evidence_ids": [DOC_ID],
        "clock_note_proposal": REMIT_CLOCK_NOTE,
        "source_note_proposal": "R09: Elexon REMIT messages (real extracts; Elexon BMRS open data "
        "licence, attribution required; message content written by the market participant).",
    },
]
CONTROL_LOG_CONTRIB = [
    {
        "room_id": ROOM_ID,
        "title_proposal": "ESO communications: contacts with government and the regulator, "
        "media statements and public posts (published accounts and public records)",
        "owner_proposal": "National Grid ESO (published reports and public statements); E3C "
        "(reports)",
        "evidence_ids": [DOC_ID],
        "clock_note_proposal": "R09 rows — times as printed in the reports (no clock labelled; "
        "read as BST, UTC+01:00), as titled or dated on ESO web statements (UK local time), or "
        "decoded in UTC from post identifiers; each row states its basis.",
        "source_note_proposal": "R09: one entry per timed ESO communication in the published "
        "accounts (ESO report sections 6.2, 6.3/Table 8 and 7; Appendix M; E3C reports) and per "
        "ESO public post or web statement (gists written for this record).",
    }
]
