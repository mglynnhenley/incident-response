"""Shared paths, source descriptions and helpers for the system-response reconstruction track.

Builder-only (excluded from the image). Inputs are read from the workspace ``.context`` tree
through environment variables, so the scripts can be pointed at another copy:

- ``GB_HANDOFF_DIR``: handoff root (default ``<workspace>/.context/handoff/GB_power_cut_handoff``)
- ``GB_TEXT_DIR``: per-page extracted PDF text (default ``<handoff root>/../text``)
- ``GB_CATALOGUE_DIR``: source catalogue (default ``<workspace>/.context/source_catalogue``)
- ``GB_REAL_DATA_DIR``: real-data folder (default ``<workspace>/.context/real_data``); this track
  only records it, it reads no real-data file.

The provenance approach extends ``builder/build_provenance.py``: a document is an ordered list of
segments, each starting at the unique line that begins with its ``start`` anchor; every
non-blank line is covered by exactly one segment; every non-framing segment cites at least one
verbatim quote that is checked on its stated PDF page (or, for figure transcriptions, against a
named row and field of a catalogue extract whose sha256 is pinned).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

RECON_DIR = Path(__file__).resolve().parent
SR_BUILDER_DIR = RECON_DIR.parent
BUILDER_DIR = SR_BUILDER_DIR.parent
ENV_ROOT = BUILDER_DIR.parent
WORKSPACE_ROOT = ENV_ROOT.parent
INCIDENT_DIR = ENV_ROOT / "src" / "environment" / "incident"
MVP_BUNDLE_DIR = INCIDENT_DIR / "bundle"
SR_BUNDLE_DIR = INCIDENT_DIR / "bundles" / "system_response"
SR_PRIVATE_DIR = INCIDENT_DIR / "private" / "system_response"
ROWS_DIR = SR_BUILDER_DIR / "rows"
# Source cards (blocks carry provenance); build_bundle.py writes the agent-visible copies.
WITNESS_DIR = ROWS_DIR / "witnesses"
PROVENANCE_PATH = SR_PRIVATE_DIR / "provenance_recon.json"
DATA_RETURNS_PATH = ROWS_DIR / "data_returns.json"
DOCUMENTS_META_PATH = RECON_DIR / "documents.json"

if str(BUILDER_DIR) not in sys.path:
    sys.path.insert(0, str(BUILDER_DIR))

import build_provenance as mvp_build  # noqa: E402
import verify_provenance as mvp_verify  # noqa: E402

normalise = mvp_verify.normalise
load_page_texts = mvp_verify.load_page_texts
parse_line_range = mvp_verify.parse_line_range
resolve_segments = mvp_build.resolve_segments

TRACK = "recon"
GENERATED_BY = "builder/system_response/recon/build_recon.py"
VERIFIED_BY = "builder/system_response/recon/verify_recon.py"

# Documents this track writes into the system-response bundle.
COPIED_DOCS = ("R01", "R03", "S03", "S04")  # byte-identical copies of MVP bundle 1.1.0
DERIVED_DOCS = ("S01",)  # MVP S01 with the decision-19 clock line
GENERATED_DOCS = ("R08",)  # generated from a catalogue extract
AUTHORED_DOCS = ("R10", "S05", "S06", "S07", "S12")  # hand-authored text files
ALL_DOCS = ("R01", "R03", "R08", "R10", "S01", "S03", "S04", "S05", "S06", "S07", "S12")
NEW_DOCS = GENERATED_DOCS + AUTHORED_DOCS

SYNTH_LABEL = "SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE"
RECON_LABEL = "RECONSTRUCTED FOR EVALUATION FROM PUBLISHED RECORDS — NOT AN ORIGINAL SYSTEM EXPORT"
REQ_LABEL = "RECONSTRUCTION OF REQUIREMENTS DESCRIBED IN PUBLISHED REPORTS — NOT CODE OR STANDARD TEXT"
LABELS = {
    "R01": "REAL MEASURED DATA EXTRACT",
    "R03": RECON_LABEL,
    "R08": RECON_LABEL,
    "R10": REQ_LABEL,
    "S01": SYNTH_LABEL,
    "S03": SYNTH_LABEL,
    "S04": SYNTH_LABEL,
    "S05": SYNTH_LABEL,
    "S06": SYNTH_LABEL,
    "S07": SYNTH_LABEL,
    "S12": SYNTH_LABEL,
}
WITNESS_EVIDENCE_ID = "S09"
WITNESS_LABEL = (
    "SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE. Fact card reconstructed from published "
    "investigation material; the witness is a role, not a person, and every answer is attributed "
    "to a published source passage."
)

VALUE_STATUSES = (
    "measured",
    "reported",
    "estimated",
    "modelled",
    "digitised",
    "illustrative",
    "framing",
)
TAGS = ("measured", "reported", "estimated", "modelled", "digitised", "illustrative")
EXTRACTION_METHODS = (
    "transcription",
    "paraphrase",
    "arithmetic",
    "layout",
    "framing",
    "script",
)

# Printed page = PDF page + offset (E3C reports print the PDF page number).
PRINTED_OFFSET = {"ESO": 1, "OFG": 0, "E3C": 0, "E3C-I": 0}

PDF_SOURCES = ("ESO", "APP", "OFG", "E3C", "E3C-I")
SOURCE_TITLES = {
    "ESO": (
        "National Grid ESO, Technical Report on the events of 9 August 2019",
        "2019-09-06",
    ),
    "APP": (
        "Appendices to the ESO Technical Report on the events of 9 August 2019 (Appendix C NGET "
        "report; D Ørsted report dated 2019-09-05; E RWE preliminary findings dated 2019-08-30; H "
        "frequency management; I simulation; J operational calls; M ESO answers to E3C questions, "
        "data available on 2019-08-28)",
        "2019-09-06",
    ),
    "OFG": ("Ofgem, 9 August 2019 power outage report", "2020-01-03"),
    "E3C": (
        "Energy Emergencies Executive Committee, GB power system disruption on 9 August 2019: "
        "final report",
        "2020-01",
    ),
    "E3C-I": (
        "Energy Emergencies Executive Committee, interim report into the GB power disruption",
        "2019-10-03",
    ),
}

# Figure transcriptions are verified against catalogue extracts with pinned hashes.
CATALOGUE_EXTRACTS = {
    "CAT-APPJ": {
        "file": "extracted/APP-p65-fig-operational-calls.csv",
        "sha256": "8b242003e85a5c46646dc8de1d442465240da504949a4d8291204256a2532ec9",
        "key": "seq",
        "underlying_source": "APP",
        "pdf_page": 65,
        "image_file": "figures/APP-p65-fig-operational-calls.png",
        "image_sha256": "922a0b702f607b67f7c38bc261cf7656fb17ce905adec818ec5eb138781c826b",
        "title": "Source catalogue transcription of the Appendix J operational-call diagram "
        "(raster figure, APP PDF page 65): one row per drawn arrow with printed time label, "
        "direction, lane and annotation text, plus lane-reading confidence",
    },
    "CAT-ESOT7": {
        "file": "extracted/ESO-p29-tab7.csv",
        "sha256": "394cbfa1ccb864f8f4182a46f380052888066737867708c0ecb9361b39de27c3",
        "key": "dno_area_column_printed",
        "underlying_source": "ESO",
        "pdf_page": 29,
        "image_file": "figures/ESO-p29-tab7.png",
        "image_sha256": "69f1074543cff75210381e95ed47cda496eb4dc4be8d6daf72b72ba184169892",
        "title": "Source catalogue parse of ESO Table 7 (DNO Areas Communication times), "
        "including which printed values span merged cells (read from the page image)",
    },
    "CAT-APPQ33": {
        "file": "extracted/APP-p87-tbl-q33-dno-comms.csv",
        "sha256": "1b997e44e191e4e15858645298c8705dfcb53871bf8bd9ac7e6141fa52232512",
        "key": "dno_area",
        "underlying_source": "APP",
        "pdf_page": 87,
        "image_file": "figures/APP-p87-tbl-q33-dno-comms.png",
        "image_sha256": "0a3ec2473ae4cb6d9a41ac547f38faf1dd22bf7523eea391806cec266ee67dc0",
        "title": "Source catalogue parse of the ESO answer-33 communication table (Appendix M), "
        "including merged and blank cells (read from the page image)",
    },
    "CAT-E3CT1": {
        "file": "extracted/E3C-p24-tab1.csv",
        "sha256": "b52e0820e14c6ded84d174480810450e7c181a3a89eb22e835286573cf6f1b55",
        "key": "lfdd_stage",
        "underlying_source": "E3C",
        "pdf_page": 24,
        "image_file": "figures/E3C-p24-tab1.png",
        "image_sha256": "1154fcb355375995a0527820291b7d9b6a0247213b3ee5d8386248c2082c2428",
        "title": "Source catalogue parse of E3C final report Table 1 (LFDD settings by stage), "
        "giving the transmission-area column of each value (read from the page image)",
    },
}


def handoff_dir() -> Path:
    return mvp_verify.handoff_dir()


def text_dir() -> Path:
    return mvp_verify.text_dir(handoff_dir())


def catalogue_dir() -> Path:
    default = WORKSPACE_ROOT / ".context" / "source_catalogue"
    return Path(os.environ.get("GB_CATALOGUE_DIR", str(default))).resolve()


def real_data_dir() -> Path:
    default = WORKSPACE_ROOT / ".context" / "real_data"
    return Path(os.environ.get("GB_REAL_DATA_DIR", str(default))).resolve()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def dumps_json(obj: Any) -> str:
    """Canonical pretty JSON used for every JSON file this track writes."""
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def dumps_jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows
    )


def src(source_id: str, pdf_page: int, section: str, quote: str) -> dict[str, Any]:
    printed = (
        pdf_page + PRINTED_OFFSET[source_id] if source_id in PRINTED_OFFSET else None
    )
    return {
        "source_id": source_id,
        "pdf_page": pdf_page,
        "printed_page": printed,
        "section": section,
        "quote": quote,
    }


def cat_src(
    extract_id: str, key: str, field: str, quote: str, section: str
) -> dict[str, Any]:
    meta = CATALOGUE_EXTRACTS[extract_id]
    return {
        "source_id": extract_id,
        "pdf_page": meta["pdf_page"],
        "printed_page": None,
        "underlying_source": meta["underlying_source"],
        "section": section,
        "row": {meta["key"]: key},
        "field": field,
        "quote": quote,
    }


def seg(
    start: str,
    content: str,
    status: str,
    method: str,
    sources: list[dict[str, Any]],
    transformation: str | None = None,
) -> dict[str, Any]:
    return mvp_build.seg(start, content, status, method, sources, transformation)


def frame(start: str, content: str) -> dict[str, Any]:
    return mvp_build.frame(start, content)


def text_lines(data: bytes) -> list[str]:
    lines = data.decode("utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


# --------------------------------------------------------------------------- number checks

_NUMBER = re.compile(r"(?<![A-Za-z0-9])\d(?:[\d,]*\d)?(?:[.:]\d+)*")


def numbers_in(text: str) -> set[str]:
    """Numeric tokens with thousands separators removed ("1,481" -> "1481").

    Tokens glued to letters on the left (item labels such as E01, Q33, OC7) are ignored.
    """
    found = set()
    for match in _NUMBER.finditer(normalise(text)):
        token = match.group(0)
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", token):
            token = token.replace(",", "")
        for part in re.split(r",", token):
            if part.isdigit():
                part = str(int(part))  # "09" == "9", "+003 mSec" == "+3 ms"
            if part:
                found.add(part)
    return found


def strip_tags(text: str) -> str:
    return re.sub(r"\[(?:{})\]".format("|".join(TAGS)), " ", text)
