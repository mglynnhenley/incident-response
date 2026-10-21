"""Write ``private/provenance.json`` and copy the handoff ``source_manifest.json``.

Builder-only tool. Each bundle document is described as an ordered list of contiguous segments.
A segment starts at the first line that begins with its ``start`` anchor and runs until the line
before the next segment's anchor (trailing blank lines excluded), so line ranges follow edits to
the text automatically. Every non-framing segment cites at least one source with a verbatim quote
(checked on the stated PDF page by verify_provenance.py) or, for R01 data facts, the builder
script that derives them from the NESO archive.

    uv run --frozen python builder/build_provenance.py
    uv run --frozen python builder/verify_provenance.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_provenance import (  # noqa: E402
    BUNDLE_DIR,
    ENV_ROOT,
    LABELS,
    MANIFEST_PATH,
    PRIVATE_SOURCE_MANIFEST,
    PROVENANCE_PATH,
    handoff_dir,
    sha256_bytes,
    sha256_file,
)

BUILD_SCRIPT = "builder/build_r01.py"

# Printed page offsets: ESO printed page = PDF page + 1; Ofgem printed page = PDF page.
# The appendix PDF has no consistent printed numbering in its text layer, so APP uses null.
PRINTED_OFFSET = {"ESO": 1, "OFG": 0}

SOURCE_META: dict[str, dict[str, Any]] = {
    "ESO": {
        "kind": "pdf",
        "title": "National Grid ESO, Technical Report on the events of 9 August 2019",
        "published": "2019-09-06",
    },
    "APP": {
        "kind": "pdf",
        "title": "Appendices to the Technical Report on the events of 9 August 2019 "
        "(Appendix C NGET report; Appendix D Ørsted report dated 2019-09-05; "
        "Appendix E RWE preliminary findings dated 2019-08-30)",
        "published": "2019-09-06",
    },
    "OFG": {
        "kind": "pdf",
        "title": "Ofgem, 9 August 2019 power outage report",
        "published": "2020-01-03",
    },
    "NESO-F": {
        "kind": "archive",
        "title": "NESO system frequency data, August 2019 monthly archive",
        "published": None,
        "member": "f 2019 8.csv",
        "member_date": "2020-02-14",
        "note": "Publisher states 2019 data was corrected on 2020-02-14; archive as downloaded "
        "2026-10-20, not a preserved copy of the originally published data.",
    },
    "HANDOFF-STATUS": {
        "kind": "text",
        "file": "SOURCE_STATUS.md",
        "title": "Builder handoff source verification status (records the publisher's "
        "historical-page correction note and the offset/UTC description issue)",
        "published": None,
    },
}


def src(
    source_id: str, pdf_page: int | None, section: str, quote: str | None
) -> dict[str, Any]:
    printed = None
    if pdf_page is not None and source_id in PRINTED_OFFSET:
        printed = pdf_page + PRINTED_OFFSET[source_id]
    return {
        "source_id": source_id,
        "pdf_page": pdf_page,
        "printed_page": printed,
        "section": section,
        "quote": quote,
    }


def script_src(section: str) -> dict[str, Any]:
    ref = src("NESO-F", None, section, None)
    ref["script"] = BUILD_SCRIPT
    return ref


def seg(
    start: str,
    content: str,
    status: str,
    method: str,
    sources: list[dict[str, Any]],
    transformation: str | None = None,
) -> dict[str, Any]:
    return {
        "start": start,
        "content": content,
        "value_status": status,
        "extraction_method": method,
        "transformation": transformation,
        "sources": sources,
    }


def frame(start: str, content: str) -> dict[str, Any]:
    return seg(start, content, "framing", "framing", [])


# Section labels used repeatedly.
ESO_T1 = "3.3 Detailed Timeline, Table 1 – Timeline of Events"
ESO_T2 = "3.3, Table 2 – Table of cumulative infeed losses"
ESO_41 = "4.1 Transmission System"
ESO_42H = "4.2 Generation Performance – Hornsea"
ESO_42L = "4.2 Generation Performance – Little Barford"
APP_C = "Appendix C – NGET Technical Report"
APP_D = (
    "Appendix D – Hornsea Technical Report submitted by Ørsted (dated 5 September 2019)"
)
APP_E = "Appendix E – RWE Preliminary Findings (dated 30 August 2019)"
APP_M = "Appendix M – ESO E3C Questions and Answers (answers based on data at 28 August 2019)"
OFG_H = "Section 3, Hornsea 1 key findings (3.19-3.23)"
OFG_L = "Section 3, Little Barford (3.25-3.29)"
UTC_NOTE = (
    "Source time unlabelled in the operator report; read as BST (it matches the ESO timeline, "
    "dated 4:52pm in the ESO executive summary) and converted to UTC = BST - 1 h (written with Z)."
)

STATUS_FRAME = (
    "Header: title, originator, record type, STATUS label, clock basis, value legend"
)

DOCUMENT_SPECS: dict[str, dict[str, Any]] = {
    "R01": {
        "construction": (
            "Real measured data. builder/build_r01.py reads the NESO August 2019 archive, parses the "
            "explicit +0100 offsets, keeps [16:40:00, 17:45:00) BST (3900 rows, 1 s, no gaps or "
            "duplicates) and writes timestamp,frequency_hz rows; the output is asserted byte-identical "
            "to the handoff CSV and the handoff landmarks are reproduced. R01.txt is a metadata note "
            "only; it deliberately states no minima, recovery times, durations or event narrative."
        ),
        "artifacts": {
            "R01/frequency_2019-08-09_1640-1745_BST.csv": {
                "extraction_method": "script",
                "value_status": "measured",
                "script": BUILD_SCRIPT,
                "sources": [script_src("archive member 'f 2019 8.csv', columns dtm,f")],
                "transformation": "dtm '%Y-%m-%d %H:%M:%S %z' -> ISO-8601 (+01:00); f -> float "
                "repr (e.g. '50' -> '50.0'); slice [16:40:00, 17:45:00) BST; csv.writer (CRLF).",
                "handoff_reference": "data/frequency_2019-08-09_1640-1745_BST.csv (byte-identical)",
            }
        },
        "segments": [
            frame("DOCUMENT R01", STATUS_FRAME),
            seg(
                "SOURCE DATASET",
                "Dataset origin: publisher portal, archive and member names, columns, dtm format",
                "derived",
                "script",
                [
                    script_src(
                        "archive f-2019-8.zip, member 'f 2019 8.csv' (columns dtm,f)"
                    )
                ],
                "Names, columns and an example dtm value read from the archive by build_r01.py; "
                "portal host from the source manifest URL (api.neso.energy).",
            ),
            seg(
                "Publisher's correction note",
                "Publisher's note that 2019 data was corrected on 14 February 2020; archive caveat",
                "reported",
                "paraphrase",
                [
                    src(
                        "HANDOFF-STATUS",
                        None,
                        "Frequency verification",
                        "The historical page states that 2019 data was corrected on 14 February 2020",
                    ),
                    src(
                        "HANDOFF-STATUS",
                        None,
                        "Frequency verification",
                        "This is the currently downloaded archive, not a claim to have preserved the "
                        "originally published data.",
                    ),
                    script_src("archive member date 2020-02-14 (zip directory entry)"),
                ],
            ),
            seg(
                "EXTRACT",
                "Slice bounds, row count, 1-s interval, gap/duplicate checks, unit, number format",
                "derived",
                "script",
                [script_src("slice [16:40:00, 17:45:00) BST of 'f 2019 8.csv'")],
                "Asserted by build_r01.py: 3900 rows, first 16:40:00+01:00, last 17:44:59+01:00, "
                "strict 1 s steps; values parsed with float() so '50' is written '50.0'.",
            ),
            seg(
                "TIME BASIS",
                "Offsets parsed as supplied; UTC conversion; publisher UTC-description caveat",
                "derived",
                "script",
                [
                    script_src("dtm column carries explicit +0100 offsets"),
                    src(
                        "HANDOFF-STATUS",
                        None,
                        "Frequency verification",
                        "The source CSV has explicit +0100 offsets. These were parsed as supplied, "
                        "not treated as naive UTC.",
                    ),
                    src(
                        "HANDOFF-STATUS",
                        None,
                        "Frequency verification",
                        "NESO's generic portal prose describes UTC while the raw file includes an "
                        "offset; no additional publisher clarification has been obtained.",
                    ),
                ],
            ),
            seg(
                "FILE AND COLUMNS",
                "Artifact name, evidence-folder location, CSV format and column definitions",
                "derived",
                "script",
                [script_src("output format written by build_r01.py")],
            ),
            seg(
                "FIRST ROWS OF THE FILE",
                "Header and first five data rows of the CSV, verbatim",
                "measured",
                "script",
                [script_src("first five rows of the slice")],
                "Copied verbatim from CSV lines 1-6; verify_provenance.py re-checks them.",
            ),
            frame(
                "CITING THIS RECORD",
                "Citation help (locator grammar for rows, times, lines)",
            ),
        ],
    },
    "R03": {
        "construction": (
            "Reconstructed record. Compiled from the ESO technical report (Table 1 NGET/MeteoGroup rows "
            "and section 4.1), the NGET report in Appendix C (sections 1.1, 1.2, 2.2, 3.1-3.5, 4.1), "
            "the ESO answers to E3C questions in Appendix M (Q30) and Ofgem 3.18. Sections A-F restate "
            "published record values; ESO Table 1 times are written as ISO-8601 BST (+01:00) because "
            "the ESO executive summary dates the event at 4:52pm, while times whose clock basis no "
            "source states (section B2, section E) are kept as printed without an offset. The R03 clock "
            "line says that the B3/section C BST reading is an inference from that 4:52pm anchor and "
            "that only times without such an anchor are marked 'clock basis not stated' (the ESO "
            "4.1 time 16:50:44 for Blyth-Eccles-Stella West has no anchor and conflicts with the "
            "Appendix M time 16:43:25, so both stay unlabelled in section E). Section D "
            "keeps measured magnitudes only; interpretations and compliance judgements (NGET, ESO, "
            "Ofgem) are in section G, in the assessing party's own wording. Section E lists both "
            "published times for the Blyth-Eccles-Stella West trip, which conflict, without resolving "
            "them; since bundle 1.1.0 there is no compiler's note pointing out the conflict (readers "
            "compare the two times themselves). Generator trips, frequency landmarks and demand "
            "disconnection are deliberately excluded."
        ),
        "segments": [
            frame("DOCUMENT R03", STATUS_FRAME),
            frame("SECTION A", "Section heading"),
            seg(
                "A1  ",
                "Circuit description: 400 kV double circuit, ~35 km, end substations, tower layout",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        15,
                        ESO_41,
                        "400kV double circuit overhead line running from Eaton Socon Substation near "
                        "St Neots in Cambridgeshire, to Wymondley Main Substation near Stevenage in "
                        "Hertfordshire",
                    ),
                    src(
                        "ESO",
                        15,
                        ESO_41,
                        "Each of the double circuits is made up of 3 conductors (phases) hanging on "
                        "each side of the lattice steel towers. An earth wire is at the top of the tower.",
                    ),
                    src(
                        "APP",
                        20,
                        APP_C + ", 1.1",
                        "This circuit runs for just over 35km",
                    ),
                ],
            ),
            seg(
                "A2  ",
                "Killingholme-Keadby planned outage; PQ monitor near Killingholme unavailable",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        30,
                        APP_C + ", 3.3.2",
                        "The Power Quality Monitoring Equipment we have installed close to "
                        "Killingholme was not available at the time of fault, as it is connected to "
                        "the Killingholme – Keadby circuit which was out of service for planned "
                        "maintenance on 9th August.",
                    )
                ],
            ),
            frame("SECTION B", "Section heading"),
            seg(
                "B1  ",
                "UK lightning count for 9 August (24 h)",
                "reported",
                "transcription",
                [
                    src(
                        "ESO",
                        15,
                        ESO_41,
                        "in the 24 hours of 9 August there were 12,370 lightning strikes across "
                        "mainland UK",
                    )
                ],
            ),
            seg(
                "B2  ",
                "UK lightning count, 2 hours preceding 17:00 (clock basis not stated in source)",
                "reported",
                "transcription",
                [
                    src(
                        "ESO",
                        15,
                        ESO_41,
                        "In the 2 hours preceding 17:00hrs there were 2,106 strikes across mainland UK",
                    )
                ],
            ),
            seg(
                "B3  ",
                "Three near-simultaneous strikes at 16:52:33 BST near Willian Arboretum",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        15,
                        ESO_41,
                        "At 16:52:33hrs, three almost simultaneous lightning strikes were recorded "
                        "adjacent to the Eaton Socon – Wymondley circuit",
                    ),
                    src(
                        "ESO",
                        15,
                        ESO_41,
                        "close to Willian Arboretum, at the Wymondley end of the circuit",
                    ),
                    src(
                        "ESO",
                        12,
                        ESO_T1 + " (source: MeteoGroup)",
                        "There were three lightning strikes detected in very close proximity to the "
                        "Eaton Socon – Wymondley circuit.",
                    ),
                    src(
                        "ESO",
                        3,
                        "Executive Summary (clock basis: local time)",
                        "At 4:52pm on 09 August 2019",
                    ),
                ],
                "16:52:33hrs -> 2019-08-09T16:52:33+01:00. The ESO timeline does not label its clock; "
                "it is read as BST because the ESO executive summary dates the event at 4:52pm. ESO "
                "Figure 4 (PDF page 16) captions the same three strikes 'at 15:52hrs', one hour earlier "
                "and also unlabelled; R03 follows the section 4.1 text and Table 1 time.",
            ),
            seg(
                "B4  ",
                "Strike location uncertainty; any of the three could have hit the circuit",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        15,
                        ESO_41,
                        "The red circles show the radius of uncertainty for the location of the "
                        "direct hit. Any of the three strikes could have hit the circuit.",
                    )
                ],
            ),
            seg(
                "B5  ",
                "Largest strike current amplitude 33.7 kA",
                "reported",
                "transcription",
                [
                    src(
                        "ESO",
                        15,
                        ESO_41,
                        "The largest strike had a current amplitude of 33.7kA.",
                    )
                ],
            ),
            seg(
                "B6  ",
                "NGET overlay: strike timed with fault; fault 4.5 km from Wymondley Main",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        25,
                        APP_C + ", 3.1.1",
                        "The lightning strike overlay here shows a number of strikes close to our "
                        "overhead line circuits. One of these strikes is timed at the same time as the "
                        "fault.",
                    ),
                    src(
                        "APP",
                        25,
                        APP_C + ", 3.1.1",
                        "The activity aligns with the protection data indicating the fault was 4.5km "
                        "from Wymondley Main, just outside Letchworth Garden City.",
                    ),
                ],
            ),
            frame("SECTION C", "Section heading (clock basis restated)"),
            seg(
                "C1  ",
                "Fault inception 16:52:33.490 BST: single (blue) phase to earth, middle conductor",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        12,
                        ESO_T1 + " (source: NGET)",
                        "16:52:33.490 A single (blue) Phase to Earth fault on Eaton Socon - Wymondley "
                        "circuit",
                    ),
                    src(
                        "APP",
                        20,
                        APP_C + ", 1.1",
                        "causing an electrical fault between the middle (blue phase) conductor and "
                        "the tower which is earthed to the ground",
                    ),
                    src(
                        "ESO",
                        3,
                        "Executive Summary (clock basis: local time)",
                        "At 4:52pm on 09 August 2019",
                    ),
                ],
                "16:52:33.490 (ESO Table 1) -> 2019-08-09T16:52:33.490+01:00. Table 1 does not label "
                "its clock; it is read as BST because the ESO executive summary dates the event at "
                "4:52pm. Section C times share this basis.",
            ),
            seg(
                "C2  ",
                "Fault location ~4.5 km from Wymondley Main",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        20,
                        APP_C + ", 1.1",
                        "approximately 4.5km along the circuit from the Wymondley Main substation end",
                    ),
                    src(
                        "ESO",
                        16,
                        ESO_41,
                        "approximately 4.5km along the circuit from the Wymondley Main Substation end",
                    ),
                ],
            ),
            seg(
                "C3  ",
                "Fault infeed ~21 kA RMS (Wymondley) and ~7 kA RMS (Eaton Socon)",
                "reported",
                "transcription",
                [
                    src(
                        "ESO",
                        12,
                        ESO_T1 + " (source: NGET)",
                        "fault infeed approximately 21kA (RMS) from Wymondley and 7kA (RMS) from "
                        "Eaton Socon",
                    )
                ],
            ),
            seg(
                "C4  ",
                "Blue-phase voltage depression: estimated 50% (ESO); circa 50% for 100 ms (NGET)",
                "estimated",
                "paraphrase",
                [
                    src(
                        "ESO",
                        12,
                        ESO_T1 + " (source: NGET)",
                        "estimated 50% voltage depression on the blue phase during the fault",
                    ),
                    src(
                        "APP",
                        17,
                        APP_C + ", Executive Summary",
                        "A voltage depression of circa 50% was seen at the fault location on the blue "
                        "phase which lasted for 100ms in the vicinity of the fault.",
                    ),
                ],
            ),
            seg(
                "C5  ",
                "Wymondley end opens 16:52:33.560 BST, 70 ms after fault (main protection)",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        12,
                        ESO_T1 + " (source: NGET)",
                        "16:52:33.560 70ms after fault, Wymondley end opens to clear the fault",
                    ),
                    src(
                        "APP",
                        17,
                        APP_C + ", Executive Summary",
                        "The main protection at Wymondley Main operated in 70ms",
                    ),
                ],
                "16:52:33.560 (BST) -> 2019-08-09T16:52:33.560+01:00.",
            ),
            seg(
                "C6  ",
                "Eaton Socon end opens 16:52:33.564 BST, 74 ms after fault (main protection)",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        12,
                        ESO_T1 + " (source: NGET)",
                        "16:52:33.564 74ms after fault, Eaton Socon end opens to clear the fault",
                    ),
                    src(
                        "APP",
                        17,
                        APP_C + ", Executive Summary",
                        "the main protection at Eaton Socon operated in 74ms",
                    ),
                ],
                "16:52:33.564 (BST) -> 2019-08-09T16:52:33.564+01:00.",
            ),
            seg(
                "C7  ",
                "Grid Code CC.6.2.3.1.1 clearance times quoted by NGET (80/100/120 ms)",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        26,
                        APP_C + ", 3.2 Post Event - Protection Analysis",
                        "Grid Code Connection Condition (CC.6.2.3.1.1) require the following fault "
                        "clearance times for primary protection operation",
                    ),
                    src(
                        "APP", 26, APP_C + ", 3.2", "(i) 80ms at 400kV (400,000 volts)"
                    ),
                    src("APP", 26, APP_C + ", 3.2", "(ii) 100ms at 275kV"),
                    src("APP", 26, APP_C + ", 3.2", "(iii) 120ms at 132kV and below"),
                ],
            ),
            seg(
                "C8  ",
                "DAR re-energisation 16:52:53 BST, about 20 s after the fault",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        12,
                        ESO_T1 + " (source: NGET)",
                        "16:52:53 Eaton Socon - Wymondley circuit energised on DAR",
                    ),
                    src(
                        "APP",
                        17,
                        APP_C + ", Executive Summary",
                        "The circuit was returned to service 20 seconds later with our automatic "
                        "Delayed Auto-Reclose system",
                    ),
                ],
                "16:52:53 (BST, ESO Table 1) -> 2019-08-09T16:52:53+01:00.",
            ),
            seg(
                "C9  ",
                "DAR in service; pre-event configuration restored; no intervention needed",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        21,
                        APP_C + ", 1.2 Delayed Auto Re-Close (DAR)",
                        "the DAR system was available and in service on the Eaton Socon - Wymondley "
                        "Main circuit",
                    ),
                    src(
                        "APP",
                        21,
                        APP_C + ", 1.2",
                        "This restored the network to the same configuration seen prior to the event.",
                    ),
                    src(
                        "APP",
                        21,
                        APP_C + ", 1.2",
                        "required no further operational intervention or immediate site attendance",
                    ),
                ],
            ),
            frame(
                "SECTION D", "Section heading (measured magnitudes; assessments in G)"
            ),
            seg(
                "D1  ",
                "Ryhall 400 kV: 44% blue-phase depression, 100 ms including recovery",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        28,
                        APP_C + ", 3.3.1 Power Quality Monitoring at Ryhall 400kV",
                        "One of these monitors is located at Ryhall which is the next substation along "
                        "from Eaton Socon",
                    ),
                    src(
                        "APP",
                        28,
                        APP_C + ", 3.3.1",
                        "the 44% voltage depression on the Blue phase of the circuit experienced at "
                        "Ryhall. The duration of the event including voltage recovery is 100ms",
                    ),
                ],
            ),
            seg(
                "D2  ",
                "Later small Ryhall transient; text 'a minute', figure '2mins'; not seen at Necton",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        29,
                        APP_C + ", 3.3.1",
                        "a further small transient event which occurred at Ryhall a minute after the "
                        "fault",
                    ),
                    src(
                        "APP",
                        29,
                        APP_C + ", Figure 3.3.1c annotation",
                        "Small Disturbance 2mins after fault likely due to reactive switching.",
                    ),
                    src(
                        "APP",
                        30,
                        APP_C + ", 3.3.2",
                        "The second transient seen at Ryhall 400kV likely associated with reactive "
                        "switching did not register at Necton",
                    ),
                ],
                "Record content only (timing and non-registration); NGET's attribution to reactive "
                "compensation switching is placed in G3.",
            ),
            seg(
                "D3  ",
                "Necton 400 kV: 21% blue-phase depression, 80 ms including recovery",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        30,
                        APP_C + ", 3.3.2",
                        "Necton Substation is located in Norfolk",
                    ),
                    src(
                        "APP",
                        30,
                        APP_C + ", 3.3.2",
                        "voltage depression of 21% on the Blue phase of the circuit experienced at "
                        "Necton 400kV. The duration of the event including voltage recovery is 80ms",
                    ),
                ],
            ),
            seg(
                "D4  ",
                "ESO measurements: recovery <100 ms after de-energisation; largest dip at Wymondley",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        17,
                        ESO_41 + ", Transmission System Performance",
                        "recovering to normal less than 100ms later after the circuit is",
                    ),
                    src(
                        "ESO",
                        17,
                        ESO_41 + ", Transmission System Performance",
                        "The voltage dip is larger at locations near to the short-circuit, with the "
                        "largest dip observed at Wymondley.",
                    ),
                ],
                "Measurement description only; ESO's Fault Ride Through statement is placed in G5.",
            ),
            seg(
                "D5  ",
                "Harmonics <1% and NPS currents <=0.6% in the area of the event (magnitudes only)",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        32,
                        APP_C + ", 3.5 Harmonics and NPS Currents",
                        "system harmonics in the area of the event were compliant with these limits at "
                        "less than 1%",
                    ),
                    src(
                        "APP",
                        32,
                        APP_C + ", 3.5",
                        "the NPS levels in the area of the event were within these requirements and did "
                        "not exceed 0.6%",
                    ),
                ],
                "Magnitudes only; the limits and NGET's compliance statements are placed in G4.",
            ),
            frame(
                "SECTION E",
                "Section heading (times as printed; clock basis not stated in the sources)",
            ),
            seg(
                "E1  ",
                "Harker-Stella West 275 kV trip: ESO narrative 14:23; ESO E3C answers 14:23:00 / DAR "
                "14:23:32",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        15,
                        ESO_41,
                        "At 14:23hrs, the Harker – Stella West 275kV circuit was also tripped and "
                        "automatically returned to service. Lightning was observed active in the "
                        "vicinity. There were no adverse effects to the transmission system following "
                        "this fault.",
                    ),
                    src(
                        "APP",
                        70,
                        APP_M,
                        "Appendix M – ESO E3C Questions and Answers",
                    ),
                    src(
                        "APP",
                        85,
                        APP_M + ", Q30",
                        "At 14:23:00, the Harker – Stella West 275kV circuit tripped and was "
                        "automatically returned to service via Delayed Auto Reclose (DAR) at 14:23:32.",
                    ),
                ],
                "Times kept as printed (14:23hrs; 14:23:00 and 14:23:32); neither source states a "
                "clock basis, so no offset is written.",
            ),
            seg(
                "E2  ",
                "Blyth-Eccles-Stella West 400 kV trip: ESO narrative 16:50:44; ESO E3C answers "
                "16:43:25 / DAR 16:43:54",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        15,
                        ESO_41,
                        "At 16:50:44hrs, a lightning struck the Blyth – Eccles – Stella West 400kV "
                        "circuit near Longframlington, Northumberland. The circuit tripped and closed "
                        "with no power losses associated.",
                    ),
                    src(
                        "APP",
                        85,
                        APP_M + ", Q30",
                        "At 16:43:25, the Blyth – Eccles – Stella West 1 400kV circuit tripped and was "
                        "likewise returned to service via DAR at 16:43:54.",
                    ),
                    src(
                        "APP",
                        85,
                        APP_M + ", Q30",
                        "On both occasions, lightning was observed in the vicinity and the faults were "
                        "cleared with no adverse effects to the transmission system.",
                    ),
                ],
                "Times kept as printed (16:50:44hrs; 16:43:25 and 16:43:54); neither source states a "
                "clock basis, so no offset is written.",
            ),
            frame("SECTION F", "Section heading"),
            seg(
                "F1  ",
                "Post-event substation attendance; assets normal; no defects",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        22,
                        APP_C + ", 2.2 Other response and communications",
                        "Our operational staff were requested to attend Wymondley Main and Eaton Socon "
                        "substations to collect data from our systems including protection operating "
                        "data",
                    ),
                    src(
                        "APP",
                        22,
                        APP_C + ", 2.2",
                        "Engineers went to both sites and confirmed all assets were operating as normal "
                        "at each substation and no defects on our assets were identified.",
                    ),
                ],
            ),
            seg(
                "F2  ",
                "Overhead line visual inspection, morning of Saturday 10 August; no defects",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        22,
                        APP_C + ", 2.2",
                        "Our overhead line engineers undertook a visual inspection of the Eaton Socon – "
                        "Wymondley Main overhead line, on the morning Saturday 10th August. No "
                        "identified defects were observed.",
                    )
                ],
            ),
            frame(
                "SECTION G",
                "Section heading (separates later assessments from records)",
            ),
            seg(
                "G1  ",
                "NGET assessment: network operated as designed; within 80 ms; DAR as designed",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        1,
                        "Title page",
                        "Appendices to the Technical Report on the events of 9 August 2019 6 September "
                        "2019",
                    ),
                    src(
                        "APP",
                        17,
                        APP_C + ", Executive Summary",
                        "the electricity transmission network operated as designed and in line with "
                        "standards",
                    ),
                    src(
                        "APP",
                        17,
                        APP_C + ", Executive Summary",
                        "therefore clearing the fault within the 80ms required in the Grid Code",
                    ),
                    src(
                        "APP",
                        17,
                        APP_C + ", Executive Summary",
                        "Delayed Auto-Reclose system again operating as expected and designed",
                    ),
                ],
            ),
            seg(
                "G2  ",
                "NGET: strike timed with the fault; confident lightning caused the fault",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        25,
                        APP_C + ", 3.1.1",
                        "One of these strikes is timed at the same time as the fault. As such we can be "
                        "confident that a lightning strike was the cause of the fault.",
                    )
                ],
            ),
            seg(
                "G3  ",
                "NGET assessments: dips as expected; 20%/80 ms further away; Ryhall transient likely "
                "reactive switching",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        33,
                        APP_C + ", 4.1 Report Findings",
                        "The voltage depression and duration were as expected for this type of fault.",
                    ),
                    src(
                        "APP",
                        33,
                        APP_C + ", 4.1 Report Findings",
                        "Electrically further from the fault voltage dips of 20% were observed with "
                        "80ms duration.",
                    ),
                    src(
                        "APP",
                        29,
                        APP_C + ", 3.3.1",
                        "most likely associated with reactive compensation switching on the network "
                        "which was in response to the fault",
                    ),
                    src(
                        "APP",
                        30,
                        APP_C + ", 3.3.2",
                        "as this transient was too small to register at this location",
                    ),
                ],
            ),
            seg(
                "G4  ",
                "NGET: steady-state voltages within SQSS ±10%; harmonics within 3% (G5/4); NPS within "
                "1.5%",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        31,
                        APP_C + ", 3.4 Steady State pre-fault and post-fault voltages",
                        "voltages recorded at Wymondley Main 400kV, Eaton Socon 400kV, Keadby 400kV and "
                        "Killingholme 400kV substations",
                    ),
                    src(
                        "APP",
                        31,
                        APP_C + ", 3.4",
                        "within operational voltage limits (of ±10% 420KV – 380kV)",
                    ),
                    src(
                        "APP",
                        32,
                        APP_C + ", 3.5 Harmonics and NPS Currents",
                        "harmonics are limited to 3% by Electricity Association (EA) Engineering "
                        "Recommendation (ER) G5/4",
                    ),
                    src(
                        "APP",
                        32,
                        APP_C + ", 3.5",
                        "are limited to 1.5% by the Grid Code",
                    ),
                    src(
                        "APP",
                        32,
                        APP_C + ", 3.5",
                        "the NPS levels in the area of the event were within these requirements",
                    ),
                ],
            ),
            seg(
                "G5  ",
                "ESO: voltages stayed above the Grid Code FRT profile; back within steady state limits",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        17,
                        ESO_41 + ", Transmission System Performance",
                        "All measurements indicate voltages stayed above the Fault Ride Through "
                        "profile specified in the Grid Code and returned to within steady state limits "
                        "after the event.",
                    ),
                ],
            ),
            seg(
                "G6  ",
                "ESO: NGET confirmed strikes caused trip and reclose; protection per design/Grid Code",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        1,
                        "Title page",
                        "Technical Report on the events of 9 August 2019",
                    ),
                    src(
                        "ESO",
                        15,
                        ESO_41,
                        "NGET by analysing their protection data confirmed that these lightning strikes "
                        "were the cause of the circuit trip and reclose",
                    ),
                    src(
                        "ESO",
                        16,
                        ESO_41 + ", Transmission System protection measurements",
                        "The transmission system protection operated in line with the design and in "
                        "compliance with the Grid Code requirements on fault clearance",
                    ),
                ],
            ),
            seg(
                "G7  ",
                "Ofgem: clearance under 75 ms; voltage 390-410 kV; assets performed as expected",
                "reported",
                "paraphrase",
                [
                    src("OFG", 1, "Cover", "3 January 2020"),
                    src(
                        "OFG",
                        28,
                        "Section 3, NGET (3.18)",
                        "Evidence NGET has submitted to us shows its fault clearance times for the two "
                        "circuit breakers were under 75ms, and that the voltage remained within a range "
                        "of 390kV to 410kV following the fault.",
                    ),
                    src(
                        "OFG",
                        28,
                        "Section 3, NGET (3.18)",
                        "The evidence suggests that NGET’s transmission assets performed as expected",
                    ),
                ],
            ),
        ],
    },
    "S01": {
        "construction": (
            "Synthesised record. Event-log entries restate values and times published in the Ørsted "
            "report (APP Appendix D, Figure 3-5 descriptions) and the Ørsted rows of ESO Table 1; BST "
            "times are written in UTC (Z). The operator report labels no clock: it writes the same instants "
            "as 16:52:33:xxx and, once, as 15.52.33.xxx; the one-hour difference is read as BST and "
            "UTC, and the S01 clock line states that this is an inference. "
            "The earlier oscillation time is an estimate (event time minus the reported 10 minutes). "
            "Log entries carry no times more precise than the operator publishes: the TIP voltage dip "
            "(dated only 'at 16:52') takes the .490 end of the steady-voltage interval and is tagged "
            "[estimated], and the 20 kV collection-system voltage, which has no time of its own, is "
            "bracketed .700Z-.835Z and tagged [estimated] (notes (b) and (c)). "
            "Since bundle 1.1.0 the record gives one clock-basis line (BST = UTC+01:00) and no "
            "per-entry UTC/BST equivalences, and it no longer states the 799 - 62 MW reduction; "
            "readers convert times and compute the loss themselves. "
            "Causal statements and mechanisms (for example WTG overcurrent protection as the de-load "
            "mechanism, first established in the operator's 5 September report) appear only in the "
            "dated, attributed post-event annotations (Ørsted "
            "report 2019-09-05, ESO report 2019-09-06, Ofgem report 2020-01-03). Nothing about other "
            "generators or frequency landmarks is included."
        ),
        "segments": [
            frame("DOCUMENT S01", STATUS_FRAME),
            seg(
                "Clock reference:",
                "Single clock-basis line: UTC with Z, BST = UTC+01:00; the operator labels no clock, "
                "so the UTC reading is stated as an inference",
                "reported",
                "paraphrase",
                [
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
                    src(
                        "ESO",
                        12,
                        ESO_T1 + " (source: Orsted)",
                        "16:52:33.728 Hornsea started deloading",
                    ),
                    src(
                        "ESO",
                        3,
                        "Executive Summary (clock basis: local time)",
                        "At 4:52pm on 09 August 2019",
                    ),
                ],
                "The operator report writes the same instants as 16:52:33:xxx and once as 15.52.33.xxx, "
                "labelling neither; the BST/UTC reading rests on the one-hour difference and on the ESO "
                "timeline (16:52:33.728, dated 4:52pm local time). Only the resulting basis and the "
                "inference are stated in the record.",
            ),
            frame("Value-status legend:", "Value-status legend"),
            frame("PART 1", "Part heading"),
            seg(
                "P1  ",
                "Hornsea One location, construction status, 1.2 GW, 174 x 7 MW turbines",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        39,
                        APP_D + ", Hornsea One overview",
                        "Hornsea One is an offshore wind farm located 120 km from the Yorkshire coast "
                        "and is currently under construction offshore",
                    ),
                    src(
                        "APP",
                        39,
                        APP_D + ", Hornsea One overview",
                        "installed capacity of 1.2GW, comprising of 174 offshore wind turbines rated at "
                        "7MW each",
                    ),
                ],
            ),
            seg(
                "P2  ",
                "Three 400 MW phases (1A/1B/1C) and connection chain to Killingholme 400 kV",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        39,
                        APP_D + ", Hornsea One overview",
                        "consists of three phases, each 400MW in size",
                    ),
                    src(
                        "APP",
                        39,
                        APP_D + ", Hornsea One overview",
                        "Each phase connects into its own HVAC Collector Substation, before connecting "
                        "into a HVAC Reactive Compensation Station located offshore before connecting "
                        "into an Onshore HVAC Substation, which then subsequently connects into the "
                        "National Grid Substation at Killingholme",
                    ),
                    src(
                        "ESO",
                        18,
                        ESO_42H,
                        "connected to the main transmission system at Killingholme 400kV substation",
                    ),
                ],
            ),
            seg(
                "P3  ",
                "Two modules installed, third partial; declared capability 800 MW",
                "reported",
                "paraphrase",
                [
                    src(
                        "OFG",
                        29,
                        "Section 3, Hornsea 1 overview (3.19)",
                        "two of its modules were fully installed and the third was partially "
                        "installed; it therefore had declared a total 800MW power export capability",
                    ),
                    src("ESO", 18, ESO_42H, "had a declared capability of 800MW"),
                ],
            ),
            seg(
                "P4  ",
                "Outage configuration: one SGT and one OTSUA circuit on outage",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        20,
                        ESO_42H + " (Ørsted report as summarised by ESO)",
                        "with one SGT and one offshore transmission system user asset (OTSUA Circuit) "
                        "on outage",
                    )
                ],
            ),
            seg(
                "P5  ",
                "Hornsea 1B (circuit Z12) at 400 MW before the event",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "Figure 4 (below) depicts the offshore conditions at Hornsea 1B (circuit Z12)",
                    ),
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "Prior to the event, Hornsea 1B is operating at 400MW (maximum capacity for "
                        "that unit)",
                    ),
                ],
            ),
            frame("PART 2", "Part heading and log column header (UTC, Z suffix)"),
            seg(
                "~15:42Z",
                "Reactive power output response to a 2% voltage step, ~10 min before (description only)",
                "estimated",
                "paraphrase",
                [
                    src(
                        "APP",
                        42,
                        APP_D + ", Figure 5",
                        "Showing the reactive power output from Hornsea 10 minutes prior to the event "
                        "in response to a 2% voltage step change",
                    ),
                ],
                "Time estimated: event 15:52Z (16:52 BST) minus the reported 10 minutes -> ~15:42Z "
                "(see note (a)). The characterisation of the response (damped, no de-loading) and "
                "the fact that it was identified after the event are in annotation A5, not the log.",
            ),
            seg(
                "15:52:33.000Z-.490Z",
                "400 kV substation voltage steady at ~400 kV before the dip",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        40,
                        APP_D + ", Description of events (Figure 3)",
                        "NETS voltage in the 400kV substation initially steady at ~400kV "
                        "(16:52:33:000 to 16:52:33:490)",
                    )
                ],
                "16:52:33:000-16:52:33:490 BST -> 15:52:33.000Z-.490Z. " + UTC_NOTE,
            ),
            seg(
                "15:52:33.490Z [estimated]       Unbalanced",
                "Unbalanced voltage dip at the TIP; time [estimated], basis given in note (b)",
                "estimated",
                "paraphrase",
                [
                    src(
                        "APP",
                        38,
                        APP_D + ", Executive Summary",
                        "an unbalanced voltage dip due to an external event occurred at the interface "
                        "point where Hornsea One connects",
                    ),
                    src(
                        "APP",
                        40,
                        APP_D + ", Description of events",
                        "NETS voltage in the 400kV substation initially steady at ~400kV "
                        "(16:52:33:000 to 16:52:33:490)",
                    ),
                    src(
                        "APP",
                        37,
                        APP_D + ", Glossary of Terms",
                        "TIP – Transmission Interface Point",
                    ),
                ],
                "The operator dates the dip only 'at 16:52'; the log takes .490, the end of its "
                "steady-voltage interval and its short-circuit time, and tags it [estimated] (note (b)). "
                "16:52:33:490 -> 15:52:33.490Z. " + UTC_NOTE,
            ),
            seg(
                "15:52:33.490Z-.700Z [reported]  Reactive",
                "Reactive injection, then oscillation absorbing >300 MVAr while voltage falls to ~394 kV "
                "(source's causal 'depresses' not carried into the log)",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        40,
                        APP_D + ", Description of events",
                        "during this time (16:52:33:490 to 16:52:33:700), the Hornsea One reactive "
                        "compensation control systems initially inject reactive power (leading MVArs) "
                        "to boost NETS voltage, before a significant oscillation occurs",
                    ),
                    src(
                        "APP",
                        40,
                        APP_D + ", Description of events",
                        "absorbing reactive power (>300MVAr which depresses NETS and Hornsea One systems",
                    ),
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "voltage to ~394kV) and then injecting MVArs again",
                    ),
                ],
                "16:52:33:490-16:52:33:700 BST -> 15:52:33.490Z-.700Z. " + UTC_NOTE,
            ),
            seg(
                "15:52:33.490Z-.700Z [reported]  Active",
                "Active power 799 -> 400 -> 799 MW",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "Hornsea reduces active power from 799MW to 400MW before returning to 799MW",
                    )
                ],
                "Same interval as the preceding entry (16:52:33:490-:700 BST). "
                + UTC_NOTE,
            ),
            seg(
                "15:52:33.531Z",
                "Status at .531: generating 799 MW, absorbing 0.4 MVAr (Ørsted row of ESO Table 1)",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        12,
                        ESO_T1 + " (source: Orsted)",
                        "16:52:33.531 Hornsea was generating 799MW and absorbing 0.4MVAR",
                    )
                ],
                "16:52:33.531 BST -> 15:52:33.531Z. " + UTC_NOTE,
            ),
            seg(
                "15:52:33.700Z [reported]",
                "~0 MVAr switching then ~560 MVAr absorption at .700",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "the reactive power output reaches ~0MVAr as it rapidly switches from "
                        "injection and absorption again (16:52:33:700). Hornsea now absorbs ~560MVAr.",
                    ),
                ],
                "16:52:33:700 BST -> 15:52:33.700Z. " + UTC_NOTE,
            ),
            seg(
                "15:52:33.700Z-.835Z",
                "34 kV collection-system voltage falls rapidly to 20 kV (target 34 kV); time bracketed",
                "estimated",
                "paraphrase",
                [
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "In the wind farm 34kV collection cable system the result of this is that the "
                        "voltage rapidly reduces to 20kV (target voltage 34kV)",
                    ),
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "(16:52:33:728 to 16:52:33:835)",
                    ),
                ],
                "No separate time is published for the 20 kV voltage. It follows the .700 switch to "
                "absorption and sits in the sentence timed 16:52:33:728 to 16:52:33:835, so the log "
                "brackets it 15:52:33.700Z-.835Z and tags the bracket [estimated] (note (c)). "
                "The source's causal 'the result of this' is not carried into the log. "
                + UTC_NOTE,
            ),
            seg(
                "15:52:33.728Z",
                "De-loading of Hornsea 1B and 1C begins (mechanism left to annotation A3)",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "The protection systems at Hornsea 1B and 1C began de-loading turbines at "
                        "15.52.33.728",
                    ),
                    src(
                        "ESO",
                        12,
                        ESO_T1 + " (source: Orsted)",
                        "16:52:33.728 Hornsea started deloading",
                    ),
                ],
                "Operator writes both 16:52:33:728 and 15.52.33.728 without a clock label; read as BST and "
                "UTC (one hour apart; ESO Table 1 gives 16:52:33.728). Written 15:52:33.728Z. The "
                "overcurrent mechanism comes from the operator's 5 September report and is kept in "
                "annotation A3, not in the log entry.",
            ),
            seg(
                "15:52:33.835Z",
                "De-load complete after 107 ms; 1A remains at 62 MW; site 62 MW injecting 21 MVAr",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "completed the de-load at 15.52.33.835, 107ms later",
                    ),
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "Hornsea 1A remained in operation at 62MW active power output",
                    ),
                    src(
                        "ESO",
                        12,
                        ESO_T1 + " (source: Orsted)",
                        "16:52:33.835 Hornsea stabilised at 62MW and injecting 21 MVAR",
                    ),
                ],
                "Operator writes 15.52.33.835 and 16:52:33:835 without a clock label; ESO Table 1 gives "
                "16:52:33.835. Read as UTC/BST; written 15:52:33.835Z.",
            ),
            frame(
                "Compiler's notes on Part 2",
                "Heading separating compiler's notes from log content",
            ),
            seg(
                "(a) ~15:42Z",
                "Note (a): ~15:42Z is an estimate from the reported '10 minutes before'",
                "estimated",
                "paraphrase",
                [
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "10 minutes before, the trace shown in figure 5",
                    ),
                    src(
                        "APP",
                        42,
                        APP_D + ", Figure 5",
                        "reactive power output from Hornsea 10 minutes prior to the event",
                    ),
                ],
                "15:52Z (16:52 BST) minus 10 minutes -> ~15:42Z; no exact time is published.",
            ),
            seg(
                "(b) The operator",
                "Note (b): TIP dip timed only to the minute; the log uses .490Z, the end of the "
                "steady-voltage interval",
                "estimated",
                "paraphrase",
                [
                    src(
                        "APP",
                        38,
                        APP_D + ", Executive Summary",
                        "On 9 August 2019 at 16:52 an unbalanced voltage dip due to an external event "
                        "occurred",
                    ),
                    src(
                        "APP",
                        40,
                        APP_D + ", Description of events",
                        "NETS voltage in the 400kV substation initially steady at ~400kV "
                        "(16:52:33:000 to 16:52:33:490)",
                    ),
                ],
                "The operator dates the dip itself only 'at 16:52'; the log takes the end of the "
                "steady-voltage interval (16:52:33:490 -> 15:52:33.490Z) and tags it [estimated]. No "
                "BST time is written in the note. " + UTC_NOTE,
            ),
            seg(
                "(c) The operator gives no separate time",
                "Note (c): basis of the .700Z-.835Z bracket for the 20 kV collection-system voltage",
                "estimated",
                "paraphrase",
                [
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "rapidly switches from injection and absorption again (16:52:33:700)",
                    ),
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "the voltage rapidly reduces to 20kV (target voltage 34kV) and all WTGs on "
                        "Hornsea 1B and Hornsea 1C reduce to 0MW as a result of overcurrent protection "
                        "in the generators (16:52:33:728 to 16:52:33:835)",
                    ),
                ],
                "Bracket = operator's .700 switch time to the end of the interval it gives for that "
                "sentence (.835), written in UTC only; no separate 20 kV time is published. "
                + UTC_NOTE,
            ),
            frame("PART 3", "Part heading (separates annotations from the log)"),
            seg(
                "Annotation A",
                "Attribution header: Ørsted technical report dated 5 September 2019",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        35,
                        APP_D + ", title page",
                        "Technical Report for National Grid ESO on the events of 9 August 2019",
                    ),
                    src(
                        "APP",
                        35,
                        APP_D + ", title page",
                        "5 September 2019, submitted 1606h",
                    ),
                ],
            ),
            seg(
                "A1  ",
                "Operator conclusion on cause of de-load (verbatim)",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        43,
                        APP_D + ", Conclusion",
                        "The de-load was caused by an unexpected wind farm control system response, due "
                        "to an insufficiently damped electrical resonance in the sub-synchronous "
                        "frequency range, which was triggered by the initial event.",
                    )
                ],
            ),
            seg(
                "A2  ",
                "Initial expected reactive injection, then majority of turbines disconnected",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        38,
                        APP_D + ", Executive Summary",
                        "Initially the offshore wind farm responded as expected by injecting reactive "
                        "power into the grid",
                    ),
                    src(
                        "APP",
                        38,
                        APP_D + ", Executive Summary",
                        "in the following few hundred milli-seconds, as the wind farm active power "
                        "reduced to cope with the voltage dip and the reactive power balance in the wind "
                        "farm changed, the majority of the wind turbines in the wind farm were "
                        "disconnected by automatic protection systems",
                    ),
                ],
            ),
            seg(
                "A3  ",
                "Operator: ~20 kV at 1B while maintaining full active power leads to WTG overcurrent; "
                "WTGs de-load (protection); no builder label",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "Hornsea 1B system voltage falls to ~20kV while attempting to maintain full "
                        "active power which leads to an overcurrent of each WTG connected to Hornsea 1B "
                        "and Hornsea 1C at the time",
                    ),
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "the WTGs de-load as part of the industry standard protection system to avoid "
                        "permanent damage to the generators",
                    ),
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "all WTGs on Hornsea 1B and Hornsea 1C reduce to 0MW as a result of overcurrent "
                        "protection in the generators (16:52:33:728 to 16:52:33:835)",
                    ),
                ],
            ),
            seg(
                "A4  ",
                "Weak grid identified; disturbance from external 400 kV circuit trip; strike time unknown",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        40,
                        APP_D + ", Description of events",
                        "Hornsea One’s systems identified a weak grid and then detected an unusual "
                        "voltage disturbance which was subsequently discovered to have been caused by "
                        "the circuit trip, itself caused by a lightning strike",
                    ),
                    src(
                        "APP",
                        40,
                        APP_D + ", Description of events",
                        "a disturbance caused by a circuit trip on the external 400kV network",
                    ),
                    src(
                        "APP",
                        40,
                        APP_D + ", footnote 1",
                        "At the time of publishing Ørsted is unaware of the exact time of the lightning "
                        "strike",
                    ),
                ],
            ),
            seg(
                "A5  ",
                "Earlier oscillation identified after the event; damped response; no de-loading",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        41,
                        APP_D + ", Description of events",
                        "Subsequent to the event in question and as part of this investigation, "
                        "electrical oscillations at Hornsea One were identified occurring prior to the "
                        "event (and without causing any de-loading)",
                    ),
                    src(
                        "APP",
                        42,
                        APP_D + ", Figure 5",
                        "Showing the reactive power output from Hornsea 10 minutes prior to the event "
                        "in response to a 2% voltage step change",
                    ),
                    src(
                        "APP",
                        42,
                        APP_D + ", Description of events",
                        "In this case the response from Hornsea shows a damped oscillatory response from "
                        "the overall voltage control systems.",
                    ),
                ],
                "~15:42Z [estimated] cross-references the log entry (event time minus the reported 10 "
                "minutes).",
            ),
            seg(
                "A6  ",
                "Prior modelling/testing; oscillation potential considered; first such de-load",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        42,
                        APP_D + ", Description of events",
                        "Prior to the event, each stage of Hornsea One had been successfully modelled "
                        "and physically tested in line with all grid code requirements",
                    ),
                    src(
                        "APP",
                        42,
                        APP_D + ", Description of events",
                        "While the potential for oscillations had been considered",
                    ),
                    src(
                        "APP",
                        42,
                        APP_D + ", Description of events",
                        "this is the first time such oscillations have led to a de-load of a windfarm",
                    ),
                ],
            ),
            seg(
                "A7  ",
                "Software update on 10 August 2019, previously agreed, mitigates the behaviour",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        42,
                        APP_D + ", Description of events",
                        "The software update performed on the 10 August 2019 was previously agreed with "
                        "the manufacturer",
                    ),
                    src(
                        "APP",
                        42,
                        APP_D + ", Description of events",
                        "This software update mitigates the observed behaviour of Hornsea One",
                    ),
                ],
            ),
            seg(
                "Annotation B",
                "Attribution header: operator statements as reported by ESO (6 September 2019)",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        1,
                        "Title page",
                        "Technical Report on the events of 9 August 2019",
                    ),
                    src("ESO", 20, ESO_42H, "Orsted’s report advises the following"),
                ],
            ),
            seg(
                "B1  ",
                "DRC initially suspected; later concluded to have worked as designed",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        20,
                        ESO_42H,
                        "Initially, Orsted understood that the Dynamic Reactive Compensator (DRC) was "
                        "responsible for the rapid de-load of Hornsea-1. Orsted have since concluded "
                        "that the DRC worked as designed and was not the cause of the de-load.",
                    )
                ],
            ),
            seg(
                "B2  ",
                "Outage configuration contributory (weak internal network); network reconfigured",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        20,
                        ESO_42H,
                        "was a contributory factor as it created a weak internal network environment",
                    ),
                    src(
                        "ESO",
                        20,
                        ESO_42H,
                        "Subsequently Orsted have reviewed and reconfigured their network.",
                    ),
                ],
            ),
            seg(
                "B3  ",
                "Standard manufacturer settings; controllers reacted incorrectly (resonance)",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        20,
                        ESO_42H,
                        "The wind turbine settings were standard settings from the manufacturer.",
                    ),
                    src(
                        "ESO",
                        20,
                        ESO_42H,
                        "the turbine controllers reacted incorrectly due to an insufficiently damped "
                        "electrical resonance in the",
                    ),
                    src(
                        "ESO",
                        20,
                        ESO_42H,
                        "so that the local Hornsea voltage dropped and the turbines shut themselves down",
                    ),
                ],
            ),
            seg(
                "Annotation C",
                "Attribution header: Ofgem report dated 3 January 2020",
                "reported",
                "paraphrase",
                [src("OFG", 1, "Cover", "3 January 2020")],
            ),
            seg(
                "C1  ",
                "Onshore control as expected; offshore controllers reacted incorrectly; 2 modules shut",
                "reported",
                "paraphrase",
                [
                    src(
                        "OFG",
                        29,
                        OFG_H,
                        "the wind farm’s onshore control system operated as expected when the system "
                        "voltage dipped concurrently with the lightning strike",
                    ),
                    src(
                        "OFG",
                        29,
                        OFG_H,
                        "The offshore wind turbine controllers, however, reacted incorrectly to voltage "
                        "fluctuations on the offshore network following the fault.",
                    ),
                    src(
                        "OFG",
                        29,
                        OFG_H,
                        "The instability triggered two modules to automatically shut down.",
                    ),
                ],
            ),
            seg(
                "C2  ",
                "Stability issue ~10 minutes before without de-loading",
                "reported",
                "paraphrase",
                [
                    src(
                        "OFG",
                        29,
                        OFG_H,
                        "had occurred around ten minutes prior to the incident on 9 August but had not "
                        "caused de-loading at that time",
                    )
                ],
            ),
            seg(
                "C3  ",
                "Pre-event modelling issues at 1,200 MW not discussed with ESO; update 13 -> 10 Aug",
                "reported",
                "paraphrase",
                [
                    src(
                        "OFG",
                        29,
                        OFG_H,
                        "modelling it carried out with its equipment manufacturer prior to 9 August "
                        "suggested that there were performance issues with the voltage control system "
                        "with Hornsea 1 operating at its full planned 1,200MW capacity",
                    ),
                    src(
                        "OFG",
                        29,
                        OFG_H,
                        "These issues were not discussed with the ESO.",
                    ),
                    src(
                        "OFG",
                        29,
                        OFG_H,
                        "had planned to carry out on 13 August but implemented on 10 August",
                    ),
                ],
            ),
        ],
    },
    "S03": {
        "construction": (
            "Synthesised record. The sequence of events transcribes the RWE preliminary findings table "
            "(APP Appendix E, PDF page 45; event/offset pairing confirmed from the PDF's word positions): "
            "raw offsets from the datum T only. RWE states no clock basis for T = 16:52:34 +/- 0.5 s; "
            "the clock line says that T is read as BST (the ESO timeline lists the RWE-sourced steam "
            "turbine trip at 16:52:34) and keeps RWE's statement that T is not yet aligned with the ESO "
            "datum. Since bundle 1.1.0 the record gives no T + offset BST times, no intervals between "
            "entries and no arithmetic check of the station total; readers derive these themselves and "
            "carry the datum uncertainty. Unit outputs come from ESO Table 2; the 641 MW station total "
            "is the value published in ESO 4.2 and Ofgem 3.27. Causal statements appear only in the "
            "attributed annotation section dated 30 August 2019, in the operator's own wording and "
            "without builder labels. Nothing about other generators or frequency landmarks is included."
        ),
        "segments": [
            frame("DOCUMENT S03", STATUS_FRAME),
            seg(
                "Clock reference:",
                "Datum T = 16:52:34 +/- 0.5 s (no clock basis stated; read as BST); ESO alignment "
                "still required",
                "reported",
                "paraphrase",
                [
                    src("APP", 45, APP_E, "Time T = 16:52:34 +/- 0.5seconds"),
                    src(
                        "APP",
                        45,
                        APP_E,
                        "further investigation work is required to determine an accurate “T” datum "
                        "relative to datum used within NGESO report",
                    ),
                    src(
                        "ESO",
                        12,
                        ESO_T1 + " (source: RWE)",
                        "16:52:34 Little Barford Steam Turbine trips 244MW instantaneously.",
                    ),
                    src(
                        "ESO",
                        3,
                        "Executive Summary (clock basis: local time)",
                        "At 4:52pm on 09 August 2019",
                    ),
                ],
                "RWE writes 'Time T = 16:52:34 +/- 0.5seconds' with no clock label. It is read as BST "
                "because the ESO timeline, which the ESO executive summary dates at 4:52pm, lists the "
                "RWE-sourced steam turbine trip at 16:52:34. The S03 clock line states this reading.",
            ),
            frame(
                "Value-status legend:",
                "Value-status legend (only [reported] is used)",
            ),
            frame("PART 1", "Part heading"),
            seg(
                "S1  ",
                "Station: 740 MW CCGT, Bedfordshire, connected at Eaton Socon 400 kV",
                "reported",
                "paraphrase",
                [
                    src(
                        "OFG",
                        30,
                        OFG_L,
                        "Little Barford is a 740MW combined cycle gas turbine power station, located in "
                        "Bedfordshire",
                    ),
                    src(
                        "OFG",
                        30,
                        OFG_L,
                        "It is connected to the national transmission system at the Eaton Socon 400kV "
                        "substation.",
                    ),
                ],
            ),
            seg(
                "S2  ",
                "Units: two GTs and one ST, all operating on 9 August",
                "reported",
                "paraphrase",
                [
                    src(
                        "OFG",
                        30,
                        OFG_L,
                        "The station has two gas turbines and one steam turbine which were all "
                        "operating on 9 August.",
                    ),
                    src("ESO", 13, ESO_T2, "Little Barford ST1C 244 MW"),
                ],
            ),
            frame("PART 2", "Part heading and SOE column header"),
            seg(
                "E1  ",
                "UPS-B general fault alarm at T = 0",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        45,
                        APP_E,
                        "110v AC UPS –B- general fault alarm “T” = 0 mSec",
                    )
                ],
            ),
            seg(
                "E2  ",
                "UPS-A general fault alarm at +3 ms",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        45,
                        APP_E,
                        "110v AC UPS –A- general fault alarm +003 mSec",
                    )
                ],
            ),
            seg(
                "E3  ",
                "Initiation of ST control system shutdown at +253 ms",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        45,
                        APP_E,
                        "Initiation of ST Control System shutdown +253 mSec",
                    )
                ],
            ),
            seg(
                "E4  ",
                "ST generator breaker open command at +1.16 s",
                "reported",
                "transcription",
                [src("APP", 45, APP_E, "ST Generator Breaker Open command +1.16 Sec")],
            ),
            seg(
                "E5  ",
                "ST generator breaker open feedback at +1.185 s",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        45,
                        APP_E,
                        "ST Generator Breaker Open feedback +1.185 Sec",
                    )
                ],
            ),
            seg(
                "E6  ",
                "GT1A auto shutdown command at +56.583 s",
                "reported",
                "transcription",
                [src("APP", 45, APP_E, "GT1A Auto shutdown command +56.583 Sec")],
            ),
            seg(
                "E7  ",
                "GT1A breaker open feedback at +57.620 s",
                "reported",
                "transcription",
                [src("APP", 45, APP_E, "GT1A Breaker Open feedback +57.620 Sec")],
            ),
            seg(
                "E8  ",
                "GT1B manual shutdown command at +83.897 s",
                "reported",
                "transcription",
                [src("APP", 45, APP_E, "GT1B Manual shutdown command +83.897 Sec")],
            ),
            seg(
                "E9  ",
                "GT1B breaker open feedback at +84.613 s",
                "reported",
                "transcription",
                [src("APP", 45, APP_E, "GT1B Breaker Open feedback +84.613 Sec")],
            ),
            seg(
                "SOE note (operator)",
                "SOE system source; operator confidence in chronology",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        45,
                        APP_E,
                        "Times are recorded in the Station’s Sequence of Events system.",
                    ),
                    src(
                        "APP",
                        45,
                        APP_E,
                        "RWE have confidence in the chronology of the events",
                    ),
                ],
            ),
            frame(
                "PART 3",
                "Part heading (attributes unit outputs to the ESO technical report)",
            ),
            seg(
                "U1  ",
                "Unit outputs at trip: ST1C 244 MW, GT1A 210 MW, GT1B 187 MW",
                "reported",
                "transcription",
                [
                    src("ESO", 13, ESO_T2, "Little Barford ST1C 244 MW"),
                    src("ESO", 13, ESO_T2, "Little Barford GT1A 210 MW"),
                    src("ESO", 13, ESO_T2, "Little Barford GT1B 187 MW"),
                    src(
                        "OFG",
                        30,
                        OFG_L + " (3.27)",
                        "Little Barford’s steam turbine was generating 244MW when it tripped",
                    ),
                    src(
                        "OFG",
                        30,
                        OFG_L + " (3.27)",
                        "one of the gas turbines which was generating 210MW tripped",
                    ),
                ],
            ),
            seg(
                "U4  ",
                "Total station loss 641 MW (published value; no arithmetic shown)",
                "reported",
                "transcription",
                [
                    src(
                        "ESO",
                        20,
                        ESO_42L,
                        "In total this meant a total loss at Little Barford of 641MW.",
                    ),
                    src(
                        "OFG",
                        31,
                        OFG_L + " (3.27)",
                        "bringing the total loss of generation to 641MW",
                    ),
                ],
            ),
            frame("PART 4", "Part heading (separates annotations from SOE content)"),
            seg(
                "Annotation A",
                "Attribution header: RWE preliminary findings dated 30 August 2019",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        45,
                        APP_E,
                        "RWE Preliminary Findings Regarding the Event on 9th August 2019 30th August 2019",
                    )
                ],
            ),
            seg(
                "A1  ",
                "ST tripped on speed-signal discrepancy after fault clearance (verbatim)",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        46,
                        APP_E + ", Steam Turbine",
                        "Our investigations have confirmed that the Steam Turbine tripped due to a "
                        "discrepancy in the speed signals after the point of the Transmission System "
                        "fault clearance.",
                    )
                ],
            ),
            seg(
                "A2  ",
                "ST hardware/software/fault-handling/diagnostics investigation ongoing; NGESO data",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        46,
                        APP_E + ", Steam Turbine",
                        "A comprehensive investigation of hardware, software, fault handling and "
                        "diagnostic coverage for the conditions, that the ST was subjected to during "
                        "this rare system disturbance, is ongoing.",
                    ),
                    src(
                        "APP",
                        46,
                        APP_E + ", Steam Turbine",
                        "frequency data has been received from NGESO, relevant to Eaton Socon",
                    ),
                ],
            ),
            seg(
                "A3  ",
                "GTs went to bypass mode, the normal response",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        46,
                        APP_E + ", Gas Turbines",
                        "Upon initiation of the Steam Turbine Trip the Gas Turbines went into bypass "
                        "mode of operation, which is the normal response to allow sustained operation.",
                    )
                ],
            ),
            seg(
                "A4  ",
                "GT1A high-pressure excursion, reasons unknown, automated trip (verbatim)",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        46,
                        APP_E + ", Gas Turbines",
                        "For reasons presently unknown a high-pressure excursion occurred on GT1A "
                        "resulting in an automated trip.",
                    ),
                    src(
                        "APP",
                        46,
                        APP_E + ", Gas Turbines",
                        "Given the prevailing conditions all systems functioned as expected.",
                    ),
                ],
            ),
            seg(
                "A5  ",
                "GT1B manually tripped for excessive steam pressure (verbatim)",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        46,
                        APP_E + ", Gas Turbines",
                        "GT1B was manually tripped shortly after as a result of excessive steam "
                        "pressure.",
                    )
                ],
            ),
            seg(
                "A6  ",
                "Gas turbines: planned bypass-system inspection, September 2019 outage (verbatim)",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        46,
                        APP_E + ", Gas Turbines",
                        "A physical inspection of the bypass system is now planned during the "
                        "forthcoming outage in September 2019 to help determine the root cause of the "
                        "pressure excursions.",
                    )
                ],
            ),
            seg(
                "A7  ",
                "UPS functioned correctly; OEMs confirmed; not believed related to the trip",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        45,
                        APP_E + ", Investigation Update – UPS",
                        "all UPS’ at Site have functioned correctly to enable continuity of supply to "
                        "plant equipment",
                    ),
                    src(
                        "APP",
                        45,
                        APP_E + ", Investigation Update – UPS",
                        "Relevant OEM’s have been engaged and confirmed the units have functioned as "
                        "expected",
                    ),
                    src(
                        "APP",
                        45,
                        APP_E + ", Investigation Update – UPS",
                        "we do not now believe the UPS’ were related to the subsequent trip",
                    ),
                ],
            ),
            seg(
                "A8  ",
                "UPS: the operator's own words 'RWE's hypothesis is ...' (verbatim); supply "
                "characteristic still to be determined",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        45,
                        APP_E + ", Investigation Update – UPS",
                        "RWE’s hypothesis is that the UPS’ have initiated a changeover to battery "
                        "back-up supplies as a consequence of the system disturbance.",
                    ),
                    src(
                        "APP",
                        45,
                        APP_E + ", Investigation Update – UPS",
                        "The exact characteristic of the power supply to the UPS causing it to switch "
                        "to battery operation is still to be determined and subject to further "
                        "investigation.",
                    ),
                ],
            ),
            seg(
                "A9  ",
                "UPS: OEM resilience testing requested for the outage from 6 September 2019; prior "
                "test dates",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        45,
                        APP_E + ", Investigation Update – UPS",
                        "During a forthcoming outage, commencing 6th September 2019, we have requested "
                        "that the OEM undertakes resilience testing",
                    ),
                    src(
                        "APP",
                        45,
                        APP_E + ", Investigation Update – UPS",
                        "previously undertaken manufacturing tests (9th November 2017) and "
                        "commissioning tests (January 2018)",
                    ),
                ],
            ),
        ],
    },
    "S04": {
        "construction": (
            "Synthesised account in two parts. Part 1 is a role-level, chronological shift narrative "
            "restating only published facts (ESO 4.2 Little Barford, the RWE SOE in APP Appendix E, "
            "Ofgem 3.25-3.29); no names, conversations, readings or clock times are added and no "
            "illustrative values are used. Part 2 gives attributed post-event statements, each in its "
            "source's order: the RWE preliminary findings dated 30 August 2019 (UPS, steam turbine, gas "
            "turbines) and Ofgem 3.28-3.29 dated 3 January 2020, as verbatim quotes or close "
            "paraphrase. Since bundle 1.1.0 the account carries no builder classification (no "
            "known/not known, established/not established or hypothesis labels); the sources' own "
            "words ('RWE's hypothesis is', 'is ongoing', 'For reasons presently unknown', 'We have "
            "established', 'has not been established', 'preliminary view') carry the epistemic status. "
            "Deliberately not carried into the pack (flagged for the domain reviewer, criteria "
            "D4.3/D4.4): the ESO executive summary (PDF page 4) says the GT1A trip was 'due to high "
            "pressure in the steam bypass system following the failure of a bypass valve to operate "
            "correctly'. ESO section 4.2 (PDF page 20) and RWE (APP page 46) give the excursion's cause "
            "as 'presently unknown', and Ofgem 3.29 states that the root cause of the high pressure "
            "conditions has not been established, so the pack keeps it unknown. A submission that "
            "asserts a bypass-valve failure as established is not supported by the visible evidence."
        ),
        "segments": [
            frame("DOCUMENT S04", STATUS_FRAME),
            seg(
                "Roles:",
                "Role definitions (plant operators / operating staff)",
                "reported",
                "paraphrase",
                [
                    src(
                        "OFG",
                        31,
                        OFG_L + " (3.29)",
                        "the plant operators made the decision to manually trip the other operational "
                        "gas turbine",
                    ),
                    src(
                        "ESO",
                        20,
                        ESO_42L,
                        "was manually tripped by the RWE operational staff",
                    ),
                ],
            ),
            frame("PART 1", "Part heading and sub-heading"),
            seg(
                "N1  ",
                "Pre-disturbance plant state: 740 MW CCGT at Eaton Socon, all three units operating",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        20,
                        ESO_42L,
                        "is a 740MW CCGT connected to the transmission system at Eaton Socon 400kV "
                        "substation",
                    ),
                    src(
                        "OFG",
                        30,
                        OFG_L + " (3.25)",
                        "The station has two gas turbines and one steam turbine which were all "
                        "operating on 9 August.",
                    ),
                ],
            ),
            frame("Steam turbine trip", "Sub-heading"),
            seg(
                "N2  ",
                "UPS-B then UPS-A general fault alarms at the start of the SOE (alarms only)",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        45,
                        APP_E,
                        "110v AC UPS –B- general fault alarm “T” = 0 mSec",
                    ),
                    src(
                        "APP",
                        45,
                        APP_E,
                        "110v AC UPS –A- general fault alarm +003 mSec",
                    ),
                ],
                "Alarms only, placed first because they head the station SOE (T = 0 and +3 ms, before "
                "the ST control system shutdown at +253 ms). RWE does not link the alarms to its UPS "
                "changeover hypothesis; that statement is quoted separately in Part 2 (A2).",
            ),
            seg(
                "N3  ",
                "ST1C tripped within 1 s of the strike, generating 244 MW",
                "reported",
                "paraphrase",
                [
                    src(
                        "OFG",
                        30,
                        OFG_L + " (3.27)",
                        "Little Barford’s steam turbine was generating 244MW when it tripped, within 1 "
                        "second of the lightning strike",
                    ),
                    src(
                        "ESO",
                        20,
                        ESO_42L,
                        "Near instantaneous to the lightning strike on Eaton Socon – Wymondley line",
                    ),
                ],
            ),
            frame("Steam bypass operation", "Sub-heading"),
            seg(
                "N4  ",
                "Steam bypass mode to condenser; normal response for sustained operation",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        20,
                        ESO_42L,
                        "Normal operation of Little Barford power station following the loss of the "
                        "steam turbine is for the steam generated from the Gas Turbines to be fed "
                        "directly into the condenser in a steam bypass mode of operation.",
                    ),
                    src(
                        "APP",
                        46,
                        APP_E + ", Gas Turbines",
                        "which is the normal response to allow sustained operation",
                    ),
                ],
            ),
            seg(
                "N5  ",
                "Steam system pressure rose after the ST trip",
                "reported",
                "paraphrase",
                [
                    src(
                        "OFG",
                        31,
                        OFG_L + " (3.29)",
                        "Following the steam turbine trip, the pressure in Little Barford’s steam "
                        "system rose",
                    )
                ],
            ),
            frame("First gas turbine trip", "Sub-heading"),
            seg(
                "N6  ",
                "GT1A auto trip on high bypass pressure around a minute after the fault, 210 MW",
                "reported",
                "paraphrase",
                [
                    src(
                        "OFG",
                        30,
                        OFG_L + " (3.27)",
                        "Around a minute after the fault, one of the gas turbines which was generating "
                        "210MW tripped.",
                    ),
                    src(
                        "ESO",
                        20,
                        ESO_42L,
                        "after approximately 1 minute the first gas turbine tripped due to a "
                        "high-pressure excursion in the steam bypass system",
                    ),
                    src(
                        "ESO",
                        20,
                        ESO_42L,
                        "This trip occurred automatically and shut the gas turbine (GT1A) down.",
                    ),
                ],
            ),
            frame("Second gas turbine trip", "Sub-heading"),
            seg(
                "N7  ",
                "Pressure kept rising; operators decided to trip the other GT for safety",
                "reported",
                "paraphrase",
                [
                    src(
                        "OFG",
                        31,
                        OFG_L + " (3.29)",
                        "The steam system pressure continued to rise after this and the plant operators "
                        "made the decision to manually trip the other operational gas turbine due to "
                        "safety risks.",
                    )
                ],
            ),
            seg(
                "N8  ",
                "GT1B manually tripped ~30 s later, 187 MW; station total 641 MW",
                "reported",
                "paraphrase",
                [
                    src(
                        "ESO",
                        20,
                        ESO_42L,
                        "was manually tripped by the RWE operational staff in response to high steam "
                        "pressures around 30 seconds later",
                    ),
                    src("ESO", 13, ESO_T2, "Little Barford GT1B 187 MW"),
                    src(
                        "ESO",
                        20,
                        ESO_42L,
                        "In total this meant a total loss at Little Barford of 641MW.",
                    ),
                ],
            ),
            frame(
                "PART 2",
                "Part heading (separates attributed post-event statements from the shift narrative)",
            ),
            seg(
                "Annotation A",
                "Attribution header: RWE preliminary findings dated 30 August 2019",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        45,
                        APP_E,
                        "RWE Preliminary Findings Regarding the Event on 9th August 2019 30th August 2019",
                    )
                ],
            ),
            seg(
                "A1  ",
                "UPS: all UPS functioned correctly; operator does not now believe UPS related (verbatim)",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        45,
                        APP_E + ", Investigation Update – UPS",
                        "The investigation to date has found that all UPS’ at Site have functioned "
                        "correctly to enable continuity of supply to plant equipment.",
                    ),
                    src(
                        "APP",
                        45,
                        APP_E + ", Investigation Update – UPS",
                        "Therefore, we do not now believe the UPS’ were related to the subsequent trip.",
                    ),
                ],
                "Two verbatim sentences; the intervening OEM-confirmation sentence is omitted (it is "
                "in S03 A7).",
            ),
            seg(
                "A2  ",
                "UPS: the operator's own words 'RWE's hypothesis is ...'; characteristic still to be "
                "determined (verbatim)",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        45,
                        APP_E + ", Investigation Update – UPS",
                        "RWE’s hypothesis is that the UPS’ have initiated a changeover to battery "
                        "back-up supplies as a consequence of the system disturbance.",
                    ),
                    src(
                        "APP",
                        45,
                        APP_E + ", Investigation Update – UPS",
                        "The exact characteristic of the power supply to the UPS causing it to switch "
                        "to battery operation is still to be determined and subject to further "
                        "investigation.",
                    ),
                ],
            ),
            seg(
                "A3  ",
                "UPS: OEM resilience testing requested for the outage commencing 6 September 2019",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        45,
                        APP_E + ", Investigation Update – UPS",
                        "During a forthcoming outage, commencing 6th September 2019, we have requested "
                        "that the OEM undertakes resilience testing",
                    )
                ],
            ),
            seg(
                "A4  ",
                "Steam turbine: trip due to speed-signal discrepancy after fault clearance (verbatim); "
                "comprehensive investigation ongoing",
                "reported",
                "paraphrase",
                [
                    src(
                        "APP",
                        46,
                        APP_E + ", Steam Turbine",
                        "Our investigations have confirmed that the Steam Turbine tripped due to a "
                        "discrepancy in the speed signals after the point of the Transmission System "
                        "fault clearance.",
                    ),
                    src(
                        "APP",
                        46,
                        APP_E + ", Steam Turbine",
                        "A comprehensive investigation of hardware, software, fault handling and "
                        "diagnostic coverage for the conditions, that the ST was subjected to during "
                        "this rare system disturbance, is ongoing.",
                    ),
                ],
                "First sentence verbatim; second closely paraphrased ('the ST' written as 'the steam "
                "turbine').",
            ),
            {
                **seg(
                    "A5  ",
                    "Gas turbines: GT1A excursion 'for reasons presently unknown', automated trip; "
                    "systems functioned as expected; GT1B manual trip (verbatim)",
                    "reported",
                    "transcription",
                    [
                        src(
                            "APP",
                            46,
                            APP_E + ", Gas Turbines",
                            "For reasons presently unknown a high-pressure excursion occurred on GT1A "
                            "resulting in an automated trip. Given the prevailing conditions all "
                            "systems functioned as expected. GT1B was manually tripped shortly after "
                            "as a result of excessive steam pressure.",
                        ),
                    ],
                ),
                "review_note": (
                    "Conflicting statement not used: ESO executive summary (PDF page 4, printed page 5) "
                    "attributes the GT1A trip to 'high pressure in the steam bypass system following "
                    "the failure of a bypass valve to operate correctly'. Ofgem 3.29 (PDF page 31): "
                    "'The root cause of these high pressure conditions has not been established.' "
                    "Reviewer to decide how D4.3/D4.4 treat a submission citing a bypass-valve failure."
                ),
            },
            seg(
                "A6  ",
                "Gas turbines: planned bypass-system inspection to help determine the root cause "
                "(verbatim)",
                "reported",
                "transcription",
                [
                    src(
                        "APP",
                        46,
                        APP_E + ", Gas Turbines",
                        "A physical inspection of the bypass system is now planned during the "
                        "forthcoming outage in September 2019 to help determine the root cause of the "
                        "pressure excursions.",
                    )
                ],
            ),
            seg(
                "Annotation B",
                "Attribution header: Ofgem 9 August 2019 power outage report, dated 3 January 2020",
                "reported",
                "paraphrase",
                [
                    src("OFG", 1, "Cover", "9 August 2019 power outage report"),
                    src("OFG", 1, "Cover", "3 January 2020"),
                ],
            ),
            seg(
                "B1  ",
                "Ofgem 3.28 (verbatim): 'We have established' trip on discrepancy in three independent "
                "speed sensors; root cause 'has not been established'",
                "reported",
                "transcription",
                [
                    src(
                        "OFG",
                        31,
                        OFG_L + " (3.28)",
                        "We have established that the steam turbine tripped initially because of a "
                        "discrepancy in the three independent speed sensors on the turbine. This "
                        "discrepancy exceeded the tolerance of the control system, causing the "
                        "generator to automatically shut down. The root cause of the discrepancy in "
                        "the speed sensors has not been established.",
                    )
                ],
                "Verbatim except for the inserted value-status tag after 'three'.",
            ),
            seg(
                "B2  ",
                "Ofgem 3.29: pressure rise, automatic GT shutdown, manual trip of the other GT "
                "(paraphrase); root cause 'has not been established' (verbatim)",
                "reported",
                "paraphrase",
                [
                    src(
                        "OFG",
                        31,
                        OFG_L + " (3.29)",
                        "Following the steam turbine trip, the pressure in Little Barford’s steam "
                        "system rose and its safety systems automatically shut down one of the gas "
                        "turbines due to excessive pressure in the steam bypass.",
                    ),
                    src(
                        "OFG",
                        31,
                        OFG_L + " (3.29)",
                        "The steam system pressure continued to rise after this and the plant operators "
                        "made the decision to manually trip the other operational gas turbine due to "
                        "safety risks.",
                    ),
                    src(
                        "OFG",
                        31,
                        OFG_L + " (3.29)",
                        "The root cause of these high pressure conditions has not been established.",
                    ),
                ],
            ),
            seg(
                "B3  ",
                "Ofgem 3.29 (verbatim): the regulator's 'preliminary view' on the anomalous speed "
                "readings",
                "reported",
                "transcription",
                [
                    src(
                        "OFG",
                        31,
                        OFG_L + " (3.29)",
                        "Given the sequence of events and in absence of an established root cause, it "
                        "is our preliminary view that the steam turbine’s anomalous speed readings and "
                        "the resulting trip were due to the transmission network fault following the "
                        "lightning strike.",
                    )
                ],
            ),
        ],
    },
}


def resolve_segments(
    doc_id: str, lines: list[str], specs: list[dict[str, Any]]
) -> list[dict]:
    starts = []
    for spec in specs:
        matches = [i for i, line in enumerate(lines) if line.startswith(spec["start"])]
        if len(matches) != 1:
            raise SystemExit(
                f"{doc_id}: anchor {spec['start']!r} matched lines {matches}"
            )
        starts.append(matches[0])
    if starts != sorted(starts) or starts[0] != 0:
        raise SystemExit(
            f"{doc_id}: anchors must be in document order and start at line 1"
        )
    resolved = []
    for index, spec in enumerate(specs):
        first = starts[index]
        last = (starts[index + 1] if index + 1 < len(specs) else len(lines)) - 1
        while last > first and not lines[last].strip():
            last -= 1
        segment = {key: value for key, value in spec.items() if key != "start"}
        segment = {"lines": f"L{first + 1}-L{last + 1}", **segment}
        resolved.append(segment)
    return resolved


def build() -> dict[str, Any]:
    handoff = handoff_dir()
    entries = {
        entry["id"]: entry
        for entry in json.loads(
            (handoff / "source_manifest.json").read_text(encoding="utf-8")
        )
    }
    sources: dict[str, Any] = {}
    for source_id, meta in SOURCE_META.items():
        record = dict(meta)
        if meta["kind"] in ("pdf", "archive"):
            entry = entries[source_id]
            record.update(file=entry["file"], sha256=entry["sha256"], url=entry["url"])
            record["retrieved_date_utc"] = entry.get("retrieved_date_utc")
        else:
            record["sha256"] = sha256_file(handoff / meta["file"])
        sources[source_id] = record

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    documents: dict[str, Any] = {}
    for doc in manifest["documents"]:
        doc_id = doc["doc_id"]
        spec = DOCUMENT_SPECS[doc_id]
        data = (BUNDLE_DIR / doc["text_file"]).read_bytes()
        lines = data.decode("utf-8").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        entry: dict[str, Any] = {
            "label": LABELS[doc_id],
            "text_file": doc["text_file"],
            "text_sha256": sha256_bytes(data),
            "line_count": len(lines),
            "construction": spec["construction"],
            "segments": resolve_segments(doc_id, lines, spec["segments"]),
        }
        if "artifacts" in spec:
            artifacts = {}
            for name, meta in spec["artifacts"].items():
                artifacts[name] = {**meta, "sha256": doc["sha256"][name]}
            entry["artifacts"] = artifacts
        documents[doc_id] = entry

    return {
        "bundle_version": manifest["bundle_version"],
        "generated_by": "builder/build_provenance.py",
        "verified_by": "builder/verify_provenance.py",
        "quote_normalisation": "NFKC; casefold; unify dashes, double quotes and apostrophes; drop "
        "soft hyphens; collapse whitespace. Quotes are matched within the stated 1-based PDF page.",
        "page_numbering": "pdf_page is the 1-based PDF page index; printed_page is the number "
        "printed on that page where known (ESO = pdf_page + 1; OFG = pdf_page; APP null).",
        "sources": sources,
        "documents": documents,
    }


def main() -> int:
    provenance = build()
    PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(provenance, indent=2, ensure_ascii=False) + "\n"
    PROVENANCE_PATH.write_text(text, encoding="utf-8")
    shutil.copyfile(handoff_dir() / "source_manifest.json", PRIVATE_SOURCE_MANIFEST)
    print(f"wrote {PROVENANCE_PATH.relative_to(ENV_ROOT)}")
    print(f"copied source manifest to {PRIVATE_SOURCE_MANIFEST.relative_to(ENV_ROOT)}")
    for doc_id, entry in provenance["documents"].items():
        print(
            f"  {doc_id}: {len(entry['segments'])} segments over {entry['line_count']} lines"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
