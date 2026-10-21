"""R08: operational call record, generated from the catalogue transcription of ESO Appendix J.

Appendix J (APP PDF pages 64-65) prints four summary bullets as text and a raster swimlane
diagram of calls. The bullets are quoted from the page text; the diagram rows come from the
source catalogue's transcription (``extracted/APP-p65-fig-operational-calls.csv``, sha256
pinned in ``recon_common.CATALOGUE_EXTRACTS``). Every generated row is checked against its CSV row:
printed time, arrow direction, lane(s) and, where the diagram prints one, the annotation text.

The record keeps the diagram's own content only: arrows as drawn, annotation boxes as printed
(boxes without an arrow of their own and side boxes beside a block of rows are listed
separately rather than attached to a row), and the cataloguer's lane-reading doubts as
compiler's notes.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from recon_common import (
    CATALOGUE_EXTRACTS,
    cat_src,
    catalogue_dir,
    frame,
    seg,
    sha256_bytes,
    src,
)

EXTRACT = "CAT-APPJ"
APP_J = "Appendix J – Operational Calls between ESO Control Room, DNOs and NGET Control Room"
APP_J_FIG = APP_J + ", call diagram (raster; catalogue transcription)"

# Diagram lane label -> printed short name used in R08 and the party/room ID used in rows.
LANES: dict[str, tuple[str, str]] = {
    "NGESO": ("NGESO", "ESO-ENCC"),
    "NGET": ("NGET", "NGET-TNCC"),
    "SSE": ("SSE", "DNO-SSE"),
    "SPED": ("SPED", "DNO-SPED"),
    "ENW": ("ENW", "DNO-ENW"),
    "NPG North East": ("NPG North East", "DNO-NPG-NE"),
    "NPG Yorkshire": ("NPG Yorkshire", "DNO-NPG-YORKS"),
    "UKPN SPN": ("UKPN SPN", "DNO-UKPN-SPN"),
    "UKPN EPN": ("UKPN EPN", "DNO-UKPN-EPN"),
    "UKPN LPN": ("UKPN LPN", "DNO-UKPN-LPN"),
    "WPD South West": ("WPD South West", "DNO-WPD-SW"),
    "WPD South Wales": ("WPD South Wales", "DNO-WPD-SWALES"),
    "WPD West Midland": ("WPD West Midland", "DNO-WPD-WMID"),
    "WPD East Midland": ("WPD East Midland", "DNO-WPD-EMID"),
    "Scotland (SP)": ("Scotland (SP)", "SCOT-SP"),
    "Scotland (SHETL)": ("Scotland (SHETL)", "SCOT-SHETL"),
}

# Annotation boxes attached to an arrow: seq -> printed text (must equal the CSV field).
ARROW_BOXES: dict[str, str] = {
    "1": "Confirmation of trip and DAR of Eaton Socon - Wymondley",
    "2": "WPD East Midlands reports loss of demand on low frequency relays. Similar losses in "
    "the West Midlands",
    "3": "Call to SHETL. Discussion of system event.",
    "4": "First of a number of calls from TNCC reporting that DNOs have lost supply.",
    "5": "UPKN LPN reports loss of supply on low frequency relays. Instructed to start "
    "restoration.",
    "6": "Multiple simultaneous calls to the ENCC from TNCC (different desks). SSE and ENW are "
    "off supplies. LF losses at SPED, ENW, NPGN, NPGY. PSM provides brief to TNCC.",
    "9": "SSE reports loss of demand on LF.",
    "11": "SP reports loss at Cockenzie.",
    "28": "TNCC informed that all DNOs are restoring.",
    "31": "Briefing to TNCC.",
    "41": "TNCC informed that all demand has been restored.",
}
# Rows printed inside the box drawn for another row.
SHARED_BOX = {"7": "6", "8": "6"}
# Boxes not attached to an arrow of their own (seq whose CSV row carries the text).
FREE_BOXES: list[dict[str, str]] = [
    {
        "label": "X1",
        "seq": "10",
        "where": "between rows C09 and C10, with no arrow of its own",
        "text": "WPD phones PSM. Call ended as ESO desk is calling on another line.",
    },
]
# Side boxes printed beside a block of rows (seq whose CSV row carries the text).
SIDE_BOXES: list[dict[str, str]] = [
    {
        "label": "X2",
        "seq": "13",
        "where": "beside rows C13 to C27",
        "text": "Instruction to restore all demand.",
    },
    {
        "label": "X3",
        "seq": "29",
        "where": "beside rows C29 to C40",
        "text": "Checking all DNOs have restored. Collection of initial numbers.",
    },
    {
        "label": "X4",
        "seq": "42",
        "where": "beside rows C42 and C43",
        "text": "Checking for demand lost figures.",
    },
]

SUMMARY = [
    (
        "N1",
        "17:04",
        "By 17:04 [reported], demand disconnection on individual DNO areas were all communicated "
        "to the ESO control room.",
        "By 17:04hrs, demand disconnection on individual DNO areas were all communicated to the "
        "ESO control room.",
    ),
    (
        "N2",
        "17:05",
        "At 17:05 [reported], demand restoration instruction commenced from ESO control room to "
        "DNOs.",
        "At 17:05hrs, demand restoration instruction commenced from ESO control room to DNOs.",
    ),
    (
        "N3",
        "17:16",
        "By 17:16 [reported], demand restoration instructions were all initiated to DNOs.",
        "By 17:16hrs, demand restoration instructions were all initiated to DNOs.",
    ),
    (
        "N4",
        "17:34",
        "Since 17:34 [reported], communications commenced to check restoration status and "
        "collate initial numbers.",
        "Since 17:34hrs, communications commenced to check restoration status and collate "
        "initial numbers.",
    ),
]

HEADER = [
    "DOCUMENT R08 — Operational call record between control rooms, 9 August 2019",
    "Owner/originator: National Grid ESO (diagram of calls between the ESO control room, NGET, DNO and",
    "Scottish control rooms, published as Appendix J to the ESO technical report dated 6 September 2019)",
    "Record type: row-by-row transcription of a published call diagram, with its printed summary notes",
    "STATUS: RECONSTRUCTED FOR EVALUATION FROM PUBLISHED RECORDS — NOT AN ORIGINAL SYSTEM EXPORT.",
    "Rows are transcribed from a diagram published by ESO; layout and wording are reconstructions.",
    "Clock reference: hh:mm as printed on the diagram, which labels no clock; read as BST (UTC+01:00)",
    "because ESO dates the event at 4:52pm. Rows sharing a printed minute keep the diagram's order.",
    "Value-status legend: [reported] time or text as printed by ESO; [measured], [estimated],",
    "[modelled], [digitised] and [illustrative] not used.",
    "Lanes as printed: NGESO = ESO control room; NGET = NGET control room (TNCC); DNO areas as labelled;",
    "Scotland (SP) and Scotland (SHETL). Arrows are listed from the end without an arrowhead to the end",
    "with one; the diagram does not say who placed each call. Annotation text is quoted as printed.",
]


def load_rows() -> tuple[dict[str, dict[str, str]], str]:
    meta = CATALOGUE_EXTRACTS[EXTRACT]
    path = catalogue_dir() / meta["file"]
    data = path.read_bytes()
    digest = sha256_bytes(data)
    if digest != meta["sha256"]:
        raise SystemExit(
            f"{path}: sha256 {digest} differs from pinned {meta['sha256']}"
        )
    reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
    rows = {row["seq"]: row for row in reader}
    return rows, digest


def _lanes(row: dict[str, str]) -> list[str]:
    lanes = [part.strip() for part in row["counterparty_lanes_all"].split("|")]
    for lane in lanes:
        if lane not in LANES:
            raise SystemExit(f"R08 seq {row['seq']}: unknown lane {lane!r}")
    return lanes


def _direction(row: dict[str, str]) -> tuple[list[str], list[str]]:
    lanes = _lanes(row)
    if row["direction"] == "to NGESO":
        return lanes, ["NGESO"]
    if row["direction"] == "from NGESO":
        return ["NGESO"], lanes
    raise SystemExit(f"R08 seq {row['seq']}: direction {row['direction']!r}")


def _wrap(prefix: str, text: str, indent: str = "     ", width: int = 110) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = prefix
    for word in words:
        candidate = f"{current} {word}" if current.strip() else f"{current}{word}"
        if len(candidate) > width and current.strip():
            lines.append(current)
            current = f"{indent}{word}"
        else:
            current = candidate
    lines.append(current)
    return lines


def call_label(seq: str) -> str:
    return f"C{int(seq):02d}"


def build_r08() -> tuple[
    str, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]
]:
    """Return (text, segment specs, call records, extract info)."""
    rows, digest = load_rows()
    lines: list[str] = list(HEADER) + [""]
    specs: list[dict[str, Any]] = [
        frame("DOCUMENT R08", "Header: title, originator, record type, STATUS label"),
        seg(
            "Clock reference:",
            "Clock basis: hh:mm as printed, unlabelled, read as BST",
            "reported",
            "paraphrase",
            [
                src(
                    "ESO",
                    3,
                    "Executive Summary (clock basis: local time)",
                    "At 4:52pm on 09 August 2019",
                ),
                src(
                    "APP",
                    65,
                    APP_J,
                    "By 17:04hrs, demand disconnection on individual DNO areas",
                ),
            ],
            "The diagram's time column prints hh:mm without a zone; read as BST because ESO dates "
            "the event at 4:52pm and the summary bullets on the same page use the same clock. "
            "The offset +01:00 is the BST definition, not a value taken from the sources.",
        ),
        frame("Value-status legend:", "Value-status legend"),
        frame("Lanes as printed:", "Lane names and reading conventions"),
    ]
    specs[1]["allow_numbers"] = ["01:00"]

    lines.append(
        "PART 1 — SUMMARY NOTES PRINTED WITH THE DIAGRAM (Appendix J, page text)"
    )
    specs.append(frame("PART 1", "Part heading"))
    records: list[dict[str, Any]] = []
    for label, hhmm, text, quote in SUMMARY:
        lines.extend(_wrap(f"{label}  ", text))
        specs.append(
            seg(
                f"{label}  ",
                f"Appendix J summary note {label}",
                "reported",
                "transcription",
                [src("APP", 65, APP_J, quote)],
                "'hrs' suffix dropped; time tagged [reported].",
            )
        )
        records.append({"label": label, "kind": "summary", "time": hhmm, "text": text})
    lines.append("")

    lines.append(
        "PART 2 — CALLS AS DRAWN (label, printed time, arrow from -> to, annotation box as printed)"
    )
    specs.append(frame("PART 2", "Part heading"))
    for seq in sorted(rows, key=int):
        row = rows[seq]
        label = call_label(seq)
        froms, tos = _direction(row)
        arrow = f"{'; '.join(LANES[x][0] for x in froms)} -> {'; '.join(LANES[x][0] for x in tos)}"
        hhmm = row["time_label_hhmm"]
        if seq in ARROW_BOXES:
            note = f'box: "{ARROW_BOXES[seq]}"'
        elif seq in SHARED_BOX:
            note = f"inside the box printed for {call_label(SHARED_BOX[seq])}"
        else:
            note = "no box of its own"
        if len(tos) > 1 or len(froms) > 1:
            note = "one arrow with arrowheads in each lane named; " + note
        lines.extend(_wrap(f"{label}  {hhmm} [reported]  {arrow};", note))
        sources = [
            cat_src(EXTRACT, seq, "time_label_hhmm", hhmm, APP_J_FIG),
            cat_src(EXTRACT, seq, "direction", row["direction"], APP_J_FIG),
            cat_src(
                EXTRACT,
                seq,
                "counterparty_lanes_all",
                row["counterparty_lanes_all"],
                APP_J_FIG,
            ),
        ]
        if seq in ARROW_BOXES:
            sources.append(
                cat_src(EXTRACT, seq, "annotation_text", ARROW_BOXES[seq], APP_J_FIG)
            )
        specs.append(
            seg(
                f"{label}  ",
                f"Diagram arrow seq {seq}",
                "reported",
                "transcription",
                sources,
                "Catalogue row rendered as label, printed time, arrow 'from -> to' (direction 'to "
                "NGESO' = lane -> NGESO) and the box text where the diagram prints one.",
            )
        )
        records.append(
            {
                "label": label,
                "kind": "call",
                "seq": seq,
                "time": hhmm,
                "from": [LANES[x][1] for x in froms],
                "to": [LANES[x][1] for x in tos],
                "arrow": arrow,
                "box": ARROW_BOXES.get(seq),
                "shared_box": call_label(SHARED_BOX[seq])
                if seq in SHARED_BOX
                else None,
            }
        )
    lines.append("")

    lines.append("PART 3 — BOXES NOT ATTACHED TO A SINGLE ARROW")
    specs.append(frame("PART 3", "Part heading"))
    for box in FREE_BOXES + SIDE_BOXES:
        text = f'Box printed {box["where"]}: "{box["text"]}"'
        lines.extend(_wrap(f"{box['label']}  ", text))
        specs.append(
            seg(
                f"{box['label']}  ",
                f"Diagram box ({box['where']})",
                "reported",
                "transcription",
                [
                    cat_src(
                        EXTRACT, box["seq"], "annotation_text", box["text"], APP_J_FIG
                    )
                ],
                "Box text quoted as printed; its position on the diagram is described, not "
                "interpreted.",
            )
        )
    lines.append("")

    lines.append(
        "Compiler's notes (added for this reconstruction; not diagram content)"
    )
    specs.append(frame("Compiler's notes", "Compiler's notes heading"))
    notes = [
        (
            "(a)",
            "C05: 'UPKN' is printed as shown. C11: the arrow is drawn from NGESO to Scotland (SP) "
            "while its box reads 'SP reports loss at Cockenzie.'",
            [
                cat_src(
                    EXTRACT,
                    "5",
                    "transcription_note",
                    "'UPKN' typo as printed",
                    APP_J_FIG,
                ),
                cat_src(
                    EXTRACT,
                    "11",
                    "transcription_note",
                    "arrow drawn NGESO->SP although the label says SP reports; recorded as drawn",
                    APP_J_FIG,
                ),
            ],
        ),
        (
            "(b)",
            "The lane at the arrow end is read with less certainty for C02, C10, C29, C30 and C37 "
            "(the arrow ends near a lane boundary or the reading rests on box position).",
            [
                cat_src(
                    EXTRACT, s, "lane_confidence", rows[s]["lane_confidence"], APP_J_FIG
                )
                for s in ("2", "10", "29", "30", "37")
            ],
        ),
        (
            "(c)",
            "C02: the box text is printed between rows C01 and C02, on the right of the diagram, "
            "and is listed with C02, the arrow from that lane.",
            [
                cat_src(
                    EXTRACT,
                    "2",
                    "transcription_note",
                    "annotation box drawn between 16:54 and 16:57 rows on the right; associated "
                    "with the 16:57 inbound arrow from WPD East Midland lane",
                    APP_J_FIG,
                )
            ],
        ),
    ]
    for label, text, sources in notes:
        lines.extend(_wrap(f"{label} ", text, indent="    "))
        specs.append(
            seg(
                f"{label} ",
                f"Compiler's note {label}",
                "reported",
                "paraphrase",
                sources,
                "Transcription caveats recorded by the catalogue, restated.",
            )
        )
    for rowlabel, row in rows.items():
        if row["lane_confidence"] not in {"high", "medium", "low"}:
            raise SystemExit(
                f"R08 seq {rowlabel}: lane_confidence {row['lane_confidence']!r}"
            )
    for check in ("2", "10", "29", "30", "37"):
        if rows[check]["lane_confidence"] == "high":
            raise SystemExit(f"R08 seq {check}: expected a non-high lane confidence")
    for seq, row in rows.items():
        if row["lane_confidence"] != "high" and seq not in {
            "2",
            "10",
            "29",
            "30",
            "37",
        }:
            raise SystemExit(
                f"R08 seq {seq}: lane confidence not reflected in note (b)"
            )

    text = "\n".join(lines) + "\n"
    info = {
        "extract_id": EXTRACT,
        "file": CATALOGUE_EXTRACTS[EXTRACT]["file"],
        "sha256": digest,
        "rows": len(rows),
    }
    return text, specs, records, info


def write_r08(
    target: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    text, specs, records, info = build_r08()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))
    return specs, records, info
