"""Shared paths, sources and helpers for the full-investigation reconstruction track.

Builder-only (excluded from the image). This track adds to the full-investigation bundle the
reconstructed records S08 (rail fleet), S10 (compliance process) and S11 (essential services),
the full R10 (report-derived requirements; increment A's R10 lines 1-133 unchanged, Sections
F-K appended), five S09 witness cards, the GTR fleet-control row fragment and the data-return
registry additions. Everything else in the bundle is copied from the system-response bundle by
the integration step.

Inputs are read from the workspace ``.context`` tree through environment variables, as in
increment A (``builder/system_response/recon/recon_common.py``):

- ``GB_HANDOFF_DIR``: handoff root (``source_manifest.json``; the six report PDFs' hashes)
- ``GB_TEXT_DIR``: per-page extracted PDF text ``{ESO,APP,OFG,E3C,E3C-I,ORR}.txt``
- ``GB_CATALOGUE_DIR``: source catalogue (ESO Table 7 extract, sha256 pinned)
- ``GB_REAL_DATA_DIR``: real-data folder (``real_data_manifest.json`` and the two raw web
  pages behind the S11 index entries; never copied into the environment)

Provenance conventions are increment A's: a document is an ordered list of segments, each
starting at the unique line that begins with its ``start`` anchor; every non-blank line is in
exactly one segment; every non-framing segment cites verbatim quotes checked on the stated PDF
page (or in a pinned catalogue row/field, real-data manifest field or pinned raw file); every
number on a sourced line occurs in the segment's quotes or section labels or is listed in
``allow_numbers`` with the reason in ``transformation``.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

RECON_DIR = Path(__file__).resolve().parent
FI_BUILDER_DIR = RECON_DIR.parent
BUILDER_DIR = FI_BUILDER_DIR.parent
ENV_ROOT = BUILDER_DIR.parent
WORKSPACE_ROOT = ENV_ROOT.parent
INCIDENT_DIR = ENV_ROOT / "src" / "environment" / "incident"
SR_BUNDLE_DIR = INCIDENT_DIR / "bundles" / "system_response"
SR_PRIVATE_DIR = INCIDENT_DIR / "private" / "system_response"
SR_RECON_DIR = BUILDER_DIR / "system_response" / "recon"
SR_ROWS_DIR = BUILDER_DIR / "system_response" / "rows"
FI_BUNDLE_DIR = INCIDENT_DIR / "bundles" / "full_investigation"
FI_PRIVATE_DIR = INCIDENT_DIR / "private" / "full_investigation"
FI_ROWS_DIR = FI_BUILDER_DIR / "rows"
TEXT_SRC_DIR = RECON_DIR / "text"
WITNESS_DIR = FI_BUNDLE_DIR / "witnesses"
PROVENANCE_PATH = FI_PRIVATE_DIR / "provenance_recon.json"
DATA_RETURNS_PATH = FI_ROWS_DIR / "data_returns.json"
DOCUMENTS_META_PATH = RECON_DIR / "documents.json"
ROW_FRAGMENT = "recon_s08.jsonl"

if str(BUILDER_DIR) not in sys.path:
    sys.path.insert(0, str(BUILDER_DIR))

import build_provenance as mvp_build  # noqa: E402
import verify_provenance as mvp_verify  # noqa: E402

normalise = mvp_verify.normalise
load_page_texts = mvp_verify.load_page_texts
parse_line_range = mvp_verify.parse_line_range
resolve_segments = mvp_build.resolve_segments

TRACK = "recon"
GENERATED_BY = "builder/full_investigation/recon/build_fi_recon.py"
VERIFIED_BY = "builder/full_investigation/recon/verify_fi_recon.py"

# Documents this track writes into the full-investigation bundle.
AUTHORED_DOCS = (
    "S08",
    "S10",
    "S11",
)  # from builder/full_investigation/recon/text/*.src.txt
R10_DOC = "R10"  # system-response R10 (frozen) + Sections F-K
ALL_DOCS = ("R10", "S08", "S10", "S11")
R10_FROZEN_LINES = 133
R10_FROZEN_SHA256 = "f5fdfb27096e593d29be15374928b7e2811b29894f086b3d11e67a92a6a50195"

SYNTH_LABEL = "SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE"
REQ_LABEL = "RECONSTRUCTION OF REQUIREMENTS DESCRIBED IN PUBLISHED REPORTS — NOT CODE OR STANDARD TEXT"
LABELS = {"R10": REQ_LABEL, "S08": SYNTH_LABEL, "S10": SYNTH_LABEL, "S11": SYNTH_LABEL}
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
    "index_entry",
)

# Printed page = PDF page + offset (ORR and the E3C reports print the PDF page number).
PRINTED_OFFSET = {"ESO": 1, "OFG": 0, "E3C": 0, "E3C-I": 0, "ORR": 0}
PDF_SOURCES = ("ESO", "APP", "OFG", "E3C", "E3C-I", "ORR")
SOURCE_TITLES = {
    "ESO": (
        "National Grid ESO, Technical Report on the events of 9 August 2019",
        "2019-09-06",
    ),
    "APP": (
        "Appendices to the ESO Technical Report on the events of 9 August 2019 (Appendix D Ørsted "
        "report; F GTR technical review dated 2019-09-03; G compliance testing for Hornsea and "
        "Little Barford; M ESO answers to E3C questions, data available on 2019-08-28)",
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
    "ORR": (
        "Office of Rail and Road, Report following railway power disruption on 9th August 2019",
        "2020-01-03",
    ),
}

# Catalogue extracts: increment A's pinned set (ESO Table 7, Appendix M answer 33, E3C Table 1 and
# the Appendix J call diagram), reused unchanged.
if str(SR_RECON_DIR) not in sys.path:
    sys.path.insert(0, str(SR_RECON_DIR))

import recon_common as sr_recon_common  # noqa: E402

CATALOGUE_EXTRACTS: dict[str, dict[str, Any]] = dict(sr_recon_common.CATALOGUE_EXTRACTS)

REAL_DATA_MANIFEST_SHA256 = (
    "5ae03bec654fb84d1a23da3a59581957bbe314125745776c299d0d00c17adffd"
)
# Raw web pages behind the S11 index entries. Not openly licensed: used only to verify that the
# entries' facts are on the page and that no more than three consecutive words are shared.
REAL_FILES = {
    "RAW-ESNEFT": {
        "file": "consequences/raw/docs/esneft_p8309.html",
        "sha256": "02701761f49099fd6f1fc124c61773d7bfc3204d6591f5ce51df1fc13fdccf0d",
        "dataset_id": "esneft_ipswich_hospital_statement",
        "publisher": "East Suffolk and North Essex NHS Foundation Trust",
        "url": "https://www.esneft.nhs.uk/major-power-cut-across-parts-of-england-and-wales/",
        "licence": "(c) ESNEFT website; no open licence stated",
        "statement_start": "Yesterday evening the major power cut",
        "statement_end": "reassured throughout the evening.",
    },
    "RAW-STANLOW": {
        "file": "consequences/raw/docs/"
        "hydrocarbonprocessing_2019-09-12_stanlow_power_cut_DIFFERENT_EVENT.html",
        "sha256": "b8fb9c1bd628b610a06db2096bc557d3ca37bea410c9083a9f51aff87c507803",
        "dataset_id": "stanlow_12sep2019_power_cut_article",
        "publisher": "Hydrocarbon Processing (Reuters)",
        "url": "https://www.hydrocarbonprocessing.com/news/2019/09/"
        "massive-flare-at-refinery-caused-by-power-cut",
        "licence": "(c) Gulf Energy Information / Reuters; copying and distribution prohibited "
        "without permission",
        "statement_start": "Massive flare at refinery caused by power cut 9/12/2019",
        "statement_end": "It was unclear how long the outage would last.",
    },
}

# Ofgem's January 2020 enforcement outcomes (decision 50): never agent-visible. These phrases are
# the leakage detectors checked over every file this track writes into the bundle.
EXCLUDED_PATTERNS = (
    r"£\s*\d",
    r"\b4\.5\s*m\b",
    r"\b1\.45\s*m\b",
    r"\b0\.05\s*m\b",
    r"\b1\.5\s*m\b",
    r"\b10\.5\s*m\b",
    r"voluntary (?:payment|redress)",
    r"redress scheme",
    r"\bsettlements?\b(?!\s+periods?)",
    r"\bpenalt",
    r"\bfined?\b",
    r"voluntary resolution",
    r"formal legal determination",
)


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
    """Canonical pretty JSON used for the private and builder JSON files of this track."""
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def dumps_card(obj: Any) -> bytes:
    """Agent-visible witness card bytes, as the system-response integration writes them."""
    return (
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def dumps_jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows
    )


def text_lines(data: bytes) -> list[str]:
    lines = data.decode("utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


# --------------------------------------------------------------------------- source refs


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


def real_src(dataset_id: str, field: str, quote: str) -> dict[str, Any]:
    return {
        "source_id": "REAL-DATA-MANIFEST",
        "dataset_id": dataset_id,
        "field": field,
        "quote": quote,
    }


def raw_src(raw_id: str, quote: str, section: str) -> dict[str, Any]:
    meta = REAL_FILES[raw_id]
    return {
        "source_id": raw_id,
        "file": meta["file"],
        "sha256": meta["sha256"],
        "section": section,
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


def allow(segment: dict[str, Any], *numbers: str) -> dict[str, Any]:
    segment["allow_numbers"] = list(numbers)
    return segment


# --------------------------------------------------------------------------- raw web text


def html_text(data: bytes) -> str:
    """Visible text of a saved web page (scripts and styles dropped, entities decoded)."""
    text = data.decode("utf-8", errors="replace")
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def statement_text(raw_id: str) -> str:
    """The indexed statement/article text inside the saved page (normalised)."""
    meta = REAL_FILES[raw_id]
    full = normalise(html_text((real_data_dir() / meta["file"]).read_bytes()))
    start = full.find(normalise(meta["statement_start"]))
    end = full.find(normalise(meta["statement_end"]), start)
    if start < 0 or end < 0:
        raise SystemExit(f"{raw_id}: statement boundaries not found in the saved page")
    return full[start : end + len(normalise(meta["statement_end"]))]


def word_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalise(text))


def shared_runs(a: str, b: str, n: int = 4) -> list[str]:
    """Runs of ``n`` consecutive word tokens that occur in both texts."""
    ta, tb = word_tokens(a), word_tokens(b)
    grams_b = {tuple(tb[i : i + n]) for i in range(len(tb) - n + 1)}
    return sorted(
        {
            " ".join(ta[i : i + n])
            for i in range(len(ta) - n + 1)
            if tuple(ta[i : i + n]) in grams_b
        }
    )


# --------------------------------------------------------------------------- number checks

_NUMBER = re.compile(r"(?<![A-Za-z0-9])\d(?:[\d,]*\d)?(?:[.:]\d+)*")


def numbers_in(text: str) -> set[str]:
    """Numeric tokens with thousands separators removed ("1,481" -> "1481").

    Tokens glued to letters on the left (item labels such as G01, Q33, OC7) are ignored.
    """
    found = set()
    for match in _NUMBER.finditer(normalise(text)):
        token = match.group(0)
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", token):
            token = token.replace(",", "")
        for part in re.split(r",", token):
            if part.isdigit():
                part = str(int(part))
            if part:
                found.add(part)
    return found


def strip_tags(text: str) -> str:
    return re.sub(r"\[(?:{})\]".format("|".join(TAGS)), " ", text)
