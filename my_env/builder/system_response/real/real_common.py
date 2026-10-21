"""Shared helpers for the real-data evidence builders (R02, R04, R06, R07).

Builder-only (excluded from the image). Everything here is deterministic: the same inputs give
byte-identical outputs. Inputs come from three builder-only locations, each overridable by an
environment variable:

* ``GB_REAL_DATA_DIR`` - real public datasets (default ``<workspace>/.context/real_data``). The
  sparse mirror ``builder/system_response/raw`` has the same layout and may be used instead.
* ``GB_CATALOGUE_DIR`` - source catalogue with extracted report tables
  (default ``<workspace>/.context/source_catalogue``).
* ``GB_HANDOFF_DIR`` - handoff root (default ``<workspace>/.context/handoff/GB_power_cut_handoff``);
  the per-page PDF text is read from ``GB_TEXT_DIR`` (default ``<handoff>/../text``).
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ENV_ROOT = HERE.parents[2]
WORKSPACE_ROOT = ENV_ROOT.parent
SR_BUILDER_DIR = ENV_ROOT / "builder" / "system_response"
RAW_MIRROR_DIR = SR_BUILDER_DIR / "raw"
RAW_MANIFEST_PATH = RAW_MIRROR_DIR / "RAW_MANIFEST.json"
ROWS_DIR = SR_BUILDER_DIR / "rows"
BUNDLE_REL = Path("src/environment/incident/bundles/system_response")
PRIVATE_REL = Path("src/environment/incident/private/system_response")
ROWS_REL = Path("builder/system_response/rows")
REAL_REL = Path("builder/system_response/real")

sys.path.insert(0, str(ENV_ROOT / "builder"))
from verify_provenance import normalise  # noqa: E402  (same quote normalisation as the MVP)

MAX_LINE = 110
WRAP_WIDTH = 98  # leaves room for a value-status tag appended to a wrapped line
BST = timedelta(hours=1)
EVENT_DATE = date(2019, 8, 9)
VALUE_TAGS = (
    "measured",
    "reported",
    "estimated",
    "modelled",
    "digitised",
    "illustrative",
)
VALUE_STATUSES = (*VALUE_TAGS, "framing")
TAG = re.compile(r"\[(measured|reported|estimated|modelled|digitised|illustrative)\]")
#: A quantity with a unit, a percentage, or a clock time (as used by the value-tag rule).
QUANTITY = re.compile(
    r"(?<![\w.])[-+~>]?\d[\d,.]*\s?(?:MWh|MW|MVA\.s|MVAr|kV|kA|ms|Hz|%|km|GW|GVAs|GVA\.s|mm|"
    r"seconds?|minutes?|hours?)(?![\w])|\b\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
)
#: Extraction methods whose lines carry per-line value-status tags.
TAGGED_METHODS = ("transcription", "figure_transcription", "quotation", "paraphrase")
EXTRACTION_METHODS = (
    "script",  # values copied from a real dataset by the builder script
    "transcription",  # report table cells or captions copied as printed
    "figure_transcription",  # values read from a published figure image (catalogue entry)
    "quotation",  # verbatim quotation of a published sentence
    "paraphrase",  # builder wording of a published statement
    "framing",  # headers, guidance and structure written for this exercise
)


# ---------------------------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------------------------


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).resolve()


def real_data_dir() -> Path:
    return _env_path("GB_REAL_DATA_DIR", WORKSPACE_ROOT / ".context" / "real_data")


def catalogue_dir() -> Path:
    return _env_path(
        "GB_CATALOGUE_DIR", WORKSPACE_ROOT / ".context" / "source_catalogue"
    )


def handoff_dir() -> Path:
    return _env_path(
        "GB_HANDOFF_DIR",
        WORKSPACE_ROOT / ".context" / "handoff" / "GB_power_cut_handoff",
    )


def text_dir() -> Path:
    return _env_path("GB_TEXT_DIR", handoff_dir().parent / "text")


# ---------------------------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BuildError(Exception):
    """An input is missing, changed, or fails a consistency check."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def cell(value: Any) -> str:
    """Render a JSON scalar for CSV: ints and floats as Python reprs, booleans as JSON, null empty."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return value
    raise BuildError(f"unexpected cell value {value!r}")


def csv_bytes(header: list[str], rows: list[list[Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        require(
            len(row) == len(header), f"row width {len(row)} != header {len(header)}"
        )
        writer.writerow([cell(v) for v in row])
    return buffer.getvalue().encode("utf-8")


def json_bytes(obj: Any) -> bytes:
    return (
        json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    ).encode()


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows
    ).encode()


def parse_utc(text: str) -> datetime:
    """Parse an Elexon UTC timestamp ('...Z', or naive which the publisher documents as UTC)."""
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    require(value.utcoffset() == timedelta(0), f"{text!r} is not UTC")
    return value


def iso_z(when: datetime) -> str:
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def uk_local_offset(day: date) -> timedelta:
    """UK local offset from UTC on ``day``; this builder only handles BST dates in August 2019."""
    require(day.year == 2019 and day.month == 8, f"no clock rule coded for {day}")
    return BST


def settlement_period_bounds_utc(day: date, period: int) -> tuple[datetime, datetime]:
    """UTC start and end of an Elexon/NESO settlement period on the UK local clock.

    Period 1 starts at 00:00 UK local time on the settlement date; each period lasts 30 minutes.
    """
    require(1 <= period <= 50, f"settlement period {period} out of range")
    local_midnight = datetime(
        day.year, day.month, day.day, tzinfo=UTC
    ) - uk_local_offset(day)
    start = local_midnight + timedelta(minutes=30 * (period - 1))
    return start, start + timedelta(minutes=30)


# Snowflake post identifiers (public social-media posts): milliseconds since the Unix epoch.
SNOWFLAKE_EPOCH_MS = 1288834974657


def snowflake_utc(post_id: int) -> datetime:
    ms = (post_id >> 22) + SNOWFLAKE_EPOCH_MS
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=ms)


# ---------------------------------------------------------------------------------------------
# Inputs (hash-checked) and quote verification
# ---------------------------------------------------------------------------------------------


def _page_map(path: Path) -> dict[int, str]:
    pages: dict[int, str] = {}
    parts = re.split(
        r"=== (\S+) PDF page (\d+) ===\n", path.read_text(encoding="utf-8")
    )
    for index in range(1, len(parts), 3):
        pages[int(parts[index + 1])] = parts[index + 2]
    return pages


def docx_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


@dataclass
class Inputs:
    """Hash-checked access to every builder input, plus quote and cell verification."""

    real_dir: Path = field(default_factory=real_data_dir)
    cat_dir: Path = field(default_factory=catalogue_dir)
    txt_dir: Path = field(default_factory=text_dir)
    handoff: Path = field(default_factory=handoff_dir)
    _pages: dict[str, dict[int, str]] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    used: dict[str, str] = field(
        default_factory=dict
    )  # source key -> sha256 actually read

    def __post_init__(self) -> None:
        self.mirror_hashes: dict[str, str] = {}
        if RAW_MANIFEST_PATH.is_file():
            manifest = json.loads(RAW_MANIFEST_PATH.read_text(encoding="utf-8"))
            for entry in manifest["files"]:
                self.mirror_hashes[entry["rel"]] = entry["mirror_sha256"]

    # -- real data -----------------------------------------------------------------------------
    def real_bytes(self, key: str) -> bytes:
        from real_sources import (
            SOURCES,
        )  # local import: avoids a cycle at module import time

        spec = SOURCES[key]
        path = self.real_dir / spec["rel"]
        require(path.is_file(), f"missing real-data input {path} (source {key})")
        data = path.read_bytes()
        digest = sha256_bytes(data)
        allowed = {spec["sha256"], self.mirror_hashes.get(spec["rel"])}
        require(
            digest in allowed,
            f"{path}: sha256 {digest} matches neither the recorded original nor the mirror",
        )
        self.used[key] = digest
        return data

    def real_json(self, key: str) -> Any:
        data = self.real_bytes(key)
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return json.loads(data.decode("utf-8"))

    def real_text(self, key: str) -> str:
        return self.real_bytes(key).decode("utf-8")

    def optional_real_bytes(self, key: str) -> bytes | None:
        from real_sources import SOURCES

        if (self.real_dir / SOURCES[key]["rel"]).is_file():
            return self.real_bytes(key)
        note = f"{key}: not present in {self.real_dir}; quote checks skipped"
        if note not in self.skipped:
            self.skipped.append(note)
        return None

    # -- catalogue -----------------------------------------------------------------------------
    def catalogue_rows(self, name: str) -> list[dict[str, str]]:
        path = self.cat_dir / "extracted" / name
        require(path.is_file(), f"missing catalogue extract {path}")
        data = path.read_bytes()
        self.used[f"catalogue:{name}"] = sha256_bytes(data)
        return list(csv.DictReader(io.StringIO(data.decode("utf-8"))))

    def catalogue_sha256(self, name: str) -> str:
        return sha256_bytes((self.cat_dir / "extracted" / name).read_bytes())

    # -- report pages --------------------------------------------------------------------------
    def page(self, source_id: str, pdf_page: int) -> str:
        if source_id not in self._pages:
            path = self.txt_dir / f"{source_id}.txt"
            require(path.is_file(), f"missing per-page text {path}")
            self._pages[source_id] = _page_map(path)
        pages = self._pages[source_id]
        require(pdf_page in pages, f"{source_id} has no PDF page {pdf_page}")
        return pages[pdf_page]

    def check_quote(self, source_id: str, pdf_page: int, quote: str) -> None:
        require(len(quote.split()) >= 3, f"quote too short: {quote!r}")
        page = normalise(self.page(source_id, pdf_page))
        require(
            normalise(quote) in page,
            f"quote not found on {source_id} PDF page {pdf_page}: {quote!r}",
        )

    def check_cell(self, source_id: str, pdf_page: int, printed: str) -> None:
        """A table cell (as printed) must occur on the page (whitespace-insensitive)."""
        compact = re.sub(r"\s+", "", normalise(self.page(source_id, pdf_page)))
        require(
            re.sub(r"\s+", "", normalise(printed)) in compact,
            f"cell {printed!r} not found on {source_id} PDF page {pdf_page}",
        )

    def check_text_quote(self, key: str, quote: str) -> None:
        """A quote from a real-data text source (warnings page text, API docs, NESO docs)."""
        data = self.optional_real_bytes(key)
        if data is None:
            return
        if key.endswith("_docx"):
            text = docx_text(data)
        elif key == "elexon_api_docs":
            docs = json.loads(data.decode("utf-8"))
            text = "\n".join(
                str(op.get("description", "")) + "\n" + str(op.get("summary", ""))
                for path in docs["paths"].values()
                for op in path.values()
            )
        else:
            text = data.decode("utf-8")
        require(
            normalise(quote) in normalise(text),
            f"quote not found in real-data source {key}: {quote!r}",
        )


# ---------------------------------------------------------------------------------------------
# Readable documents with exact segment provenance
# ---------------------------------------------------------------------------------------------


@dataclass
class Segment:
    content: str
    value_status: str
    extraction_method: str
    sources: list[dict[str, Any]]
    transformation: str | None = None


class TextDoc:
    """A document text built line by line; each line belongs to a provenance segment."""

    def __init__(self, doc_id: str) -> None:
        self.doc_id = doc_id
        self.lines: list[str] = []
        self.keys: list[str | None] = []
        self.specs: dict[str, Segment] = {}
        self._counter = 0

    def segment(
        self,
        content: str,
        value_status: str,
        extraction_method: str,
        sources: list[dict[str, Any]],
        transformation: str | None = None,
    ) -> str:
        require(value_status in VALUE_STATUSES, f"bad value status {value_status}")
        require(
            extraction_method in EXTRACTION_METHODS, f"bad method {extraction_method}"
        )
        if extraction_method == "framing":
            require(not sources, "framing segments have no sources")
        else:
            require(bool(sources), f"segment {content!r} needs at least one source")
        self._counter += 1
        key = f"s{self._counter:03d}"
        self.specs[key] = Segment(
            content, value_status, extraction_method, sources, transformation
        )
        return key

    def frame(self, content: str, *lines: str) -> None:
        self.add(self.segment(content, "framing", "framing", []), *lines)

    def add(self, key: str, *lines: str) -> None:
        """Append lines; in report-derived segments a line stating a quantity or a clock time
        without a value-status tag gets the segment's tag appended (tags stay on the line)."""
        require(key in self.specs, f"unknown segment {key}")
        spec = self.specs[key]
        auto_tag = (
            spec.extraction_method in TAGGED_METHODS and spec.value_status in VALUE_TAGS
        )
        for line in lines:
            require("\n" not in line, f"{self.doc_id}: embedded newline in {line!r}")
            if auto_tag and QUANTITY.search(line) and not TAG.search(line):
                line = f"{line} [{spec.value_status}]"
            self.lines.append(line)
            self.keys.append(key if line.strip() else None)

    def blank(self) -> None:
        self.lines.append("")
        self.keys.append(None)

    def render(self) -> bytes:
        for number, line in enumerate(self.lines, 1):
            require("\t" not in line, f"{self.doc_id} L{number}: tab")
            require(
                line == line.rstrip(), f"{self.doc_id} L{number}: trailing whitespace"
            )
            require(
                len(line) <= MAX_LINE, f"{self.doc_id} L{number}: {len(line)} chars"
            )
        require(
            bool(self.lines) and self.lines[-1] != "", f"{self.doc_id}: trailing blank"
        )
        return ("\n".join(self.lines) + "\n").encode("utf-8")

    def segments(self) -> list[dict[str, Any]]:
        """Contiguous runs of lines with the same segment key (blank lines inside a run allowed)."""
        runs: list[tuple[str, int, int]] = []
        for index, key in enumerate(self.keys):
            if key is None:
                continue
            if runs and runs[-1][0] == key:
                runs[-1] = (key, runs[-1][1], index)
            else:
                runs.append((key, index, index))
        seen: set[str] = set()
        out = []
        for key, first, last in runs:
            require(key not in seen, f"{self.doc_id}: segment {key} is not contiguous")
            seen.add(key)
            spec = self.specs[key]
            out.append(
                {
                    "lines": f"L{first + 1}-L{last + 1}",
                    "content": spec.content,
                    "value_status": spec.value_status,
                    "extraction_method": spec.extraction_method,
                    "transformation": spec.transformation,
                    "sources": spec.sources,
                }
            )
        unused = set(self.specs) - seen
        require(not unused, f"{self.doc_id}: segments without lines: {sorted(unused)}")
        return out


def wrap(
    text: str, width: int = WRAP_WIDTH, indent: str = "", first: str = ""
) -> list[str]:
    """Greedy word wrap; ``first`` prefixes the first line, ``indent`` the following ones."""
    words = text.split()
    lines: list[str] = []
    current = first
    for word in words:
        candidate = f"{current} {word}" if current.strip() else f"{current}{word}"
        if len(candidate) > width and current.strip():
            lines.append(current.rstrip())
            current = f"{indent}{word}"
        else:
            current = candidate
    if current.strip():
        lines.append(current.rstrip())
    for line in lines:
        require(len(line) <= width, f"cannot wrap word in {text!r}")
    return lines


def tagged(text: str, tag: str, first: str = "    ", indent: str = "    ") -> list[str]:
    """Wrap ``text`` and end its last line with the value-status tag ``[tag]``."""
    require(tag in VALUE_TAGS, f"bad tag {tag}")
    lines = wrap(text, first=first, indent=indent)
    lines[-1] = f"{lines[-1]} [{tag}]"
    return lines


# ---------------------------------------------------------------------------------------------
# Provenance source references
# ---------------------------------------------------------------------------------------------

PRINTED_OFFSET = {"ESO": 1, "OFG": 0}


def pdf_ref(
    inputs: Inputs, source_id: str, pdf_page: int, section: str, quote: str | None
) -> dict[str, Any]:
    """A report passage; a non-null quote is verified on the stated PDF page now."""
    if quote is not None:
        inputs.check_quote(source_id, pdf_page, quote)
    printed = (
        pdf_page + PRINTED_OFFSET[source_id] if source_id in PRINTED_OFFSET else None
    )
    return {
        "kind": "report_page",
        "source_id": source_id,
        "pdf_page": pdf_page,
        "printed_page": printed,
        "section": section,
        "quote": quote,
    }


def table_ref(
    inputs: Inputs,
    source_id: str,
    pdf_page: int,
    section: str,
    artifact_id: str,
    extracted: str,
    cells: list[str],
) -> dict[str, Any]:
    """A transcribed report table; every printed cell is checked on the stated page now."""
    for printed in cells:
        if printed.strip():
            inputs.check_cell(source_id, pdf_page, printed)
    ref = pdf_ref(inputs, source_id, pdf_page, section, None)
    ref.update(
        kind="report_table",
        catalogue_artifact=artifact_id,
        catalogue_extract=f"extracted/{extracted}",
        catalogue_extract_sha256=inputs.catalogue_sha256(extracted),
        cells_checked_on_page=sum(1 for c in cells if c.strip()),
    )
    return ref


def figure_ref(
    source_id: str,
    pdf_page: int,
    section: str,
    artifact_id: str,
    files: list[str],
    note: str,
) -> dict[str, Any]:
    """Values read from a published figure image (not machine-checkable against page text)."""
    printed = (
        pdf_page + PRINTED_OFFSET[source_id] if source_id in PRINTED_OFFSET else None
    )
    return {
        "kind": "report_figure",
        "source_id": source_id,
        "pdf_page": pdf_page,
        "printed_page": printed,
        "section": section,
        "catalogue_artifact": artifact_id,
        "catalogue_files": files,
        "note": note,
        "quote": None,
    }


def data_ref(key: str, detail: str, quote: str | None = None) -> dict[str, Any]:
    from real_sources import SOURCES

    spec = SOURCES[key]
    ref = {
        "kind": "dataset",
        "source_id": key,
        "file": spec["rel"],
        "sha256": spec["sha256"],
        "detail": detail,
        "quote": quote,
    }
    return ref


def doc_quote_ref(inputs: Inputs, key: str, detail: str, quote: str) -> dict[str, Any]:
    inputs.check_text_quote(key, quote)
    return data_ref(key, detail, quote)
