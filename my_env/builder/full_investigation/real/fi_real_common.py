"""Shared helpers of the full-investigation real-data builders (R09, R11, R12).

Builder-only and deterministic. This module reuses increment A's real-data machinery
(``builder/system_response/real/real_common.py``: line-by-line documents with exact segment
provenance, wrapping, value tags, report-quote and table-cell verification) and adds what the
consequences sources need:

* its own source registry (``fi_sources.SOURCES``) and raw mirror
  (``builder/full_investigation/raw``), with ``extract`` mirrors for the two Network Rail files
  the standard library cannot read (glossary workbook, explanation PDF);
* quotation checks against HTML pages, GOV.UK Content API JSON and plain-text extracts;
* the gist rule for text that is not openly licensed (posts, web pages): a gist written for this
  record may share at most three consecutive words with its source (increment A, R07 Part D).

Inputs are read from ``GB_REAL_DATA_DIR`` / ``GB_CATALOGUE_DIR`` / ``GB_HANDOFF_DIR`` /
``GB_TEXT_DIR`` exactly as in increment A.
"""

from __future__ import annotations

import gzip
import html
import io
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

HERE = Path(__file__).resolve().parent
ENV_ROOT = HERE.parents[2]
SR_REAL_DIR = ENV_ROOT / "builder" / "system_response" / "real"
if str(SR_REAL_DIR) not in sys.path:
    sys.path.insert(0, str(SR_REAL_DIR))

import real_common  # noqa: E402  (increment A, frozen; reused, never modified)
from real_common import (  # noqa: E402,F401  (re-exported for the document builders)
    BST,
    QUANTITY,
    TAG,
    BuildError,
    TextDoc,
    catalogue_dir,
    csv_bytes,
    handoff_dir,
    iso_z,
    json_bytes,
    jsonl_bytes,
    normalise,
    pdf_ref,
    real_data_dir,
    require,
    sha256_bytes,
    snowflake_utc,
    table_ref,
    tagged,
    text_dir,
    wrap,
)
from real_r07 import GIST_MAX_SHARED, shared_word_runs  # noqa: E402,F401

FI_BUILDER_DIR = ENV_ROOT / "builder" / "full_investigation"
RAW_MIRROR_DIR = FI_BUILDER_DIR / "raw"
RAW_MANIFEST_PATH = RAW_MIRROR_DIR / "RAW_MANIFEST.json"
BUNDLE_REL = Path("src/environment/incident/bundles/full_investigation")
PRIVATE_REL = Path("src/environment/incident/private/full_investigation")
ROWS_REL = Path("builder/full_investigation/rows")
REAL_REL = Path("builder/full_investigation/real")
BUILDER = "builder/full_investigation/real/fi_build_real.py"

#: Report sources (per-page text in GB_TEXT_DIR) used by R09.
REPORTS = {
    "ESO": {
        "title": "National Grid ESO, Technical Report on the events of 9 August 2019",
        "published": "2019-09-06",
        "licence": "National Grid ESO document hosted by Ofgem; not an open licence "
        "(builder-only)",
    },
    "APP": {
        "title": "Appendices to the ESO Technical Report on the events of 9 August 2019",
        "published": "2019-09-06 (Appendix M answers based on data available to the ESO on "
        "28 August 2019)",
        "licence": "National Grid ESO document hosted by Ofgem, includes third-party "
        "material; not an open licence (builder-only)",
    },
    "OFG": {
        "title": "Ofgem, 9 August 2019 power outage report",
        "published": "2020-01-03",
        "licence": "Open Government Licence v3.0 with exclusions (builder-only copy)",
    },
    "E3C-I": {
        "title": "Energy Emergencies Executive Committee, GB power system disruption - "
        "9 August 2019, interim report",
        "published": "cover dated September 2019; publisher file name dated 2019-10-03",
        "licence": "Open Government Licence v3.0 with exclusions (builder-only copy)",
    },
    "E3C": {
        "title": "Energy Emergencies Executive Committee, GB power system disruption on "
        "9 August 2019: Final report",
        "published": "January 2020 (GOV.UK records publication on 2020-01-03)",
        "licence": "Open Government Licence v3.0 with exclusions (builder-only copy)",
    },
}


def mirror_manifest() -> dict[str, dict[str, Any]]:
    """rel -> entry of the committed mirror manifest (empty before the first sync)."""
    if not RAW_MANIFEST_PATH.is_file():
        return {}
    data = json.loads(RAW_MANIFEST_PATH.read_text(encoding="utf-8"))
    return {entry["rel"]: entry for entry in data["files"]}


class FiInputs(real_common.Inputs):
    """Increment A's hash-checked inputs, bound to this track's registry and mirror."""

    def __post_init__(self) -> None:
        self.mirror = mirror_manifest()
        self.mirror_hashes = {rel: e["mirror_sha256"] for rel, e in self.mirror.items()}

    # -- registry-bound access ------------------------------------------------------------------
    def _spec(self, key: str) -> dict[str, Any]:
        from fi_sources import SOURCES

        require(key in SOURCES, f"unregistered source {key}")
        return SOURCES[key]

    def _locate(self, key: str) -> tuple[Path, set[str]] | None:
        """Path of the original (or of its mirror copy/slice/extract) and the accepted hashes."""
        spec = self._spec(key)
        original = self.real_dir / spec["rel"]
        if original.is_file():
            allowed = {spec["sha256"]}
            entry = self.mirror.get(spec["rel"])
            if entry is not None and entry["mode"] in ("copy", "slice"):
                allowed.add(entry["mirror_sha256"])
            return original, allowed
        extract_rel = spec.get("mirror_rel")
        if extract_rel and (self.real_dir / extract_rel).is_file():
            entry = self.mirror.get(extract_rel)
            require(
                entry is not None,
                f"{key}: extract {extract_rel} is not in the manifest",
            )
            return self.real_dir / extract_rel, {entry["mirror_sha256"]}
        return None

    def real_bytes(self, key: str) -> bytes:
        located = self._locate(key)
        spec = self._spec(key)
        require(
            located is not None, f"missing real-data input {spec['rel']} (source {key})"
        )
        path, allowed = located
        data = path.read_bytes()
        digest = sha256_bytes(data)
        require(
            digest in allowed,
            f"{path}: sha256 {digest} matches neither the recorded original nor the mirror",
        )
        self.used[key] = digest
        return data

    def is_extract(self, key: str) -> bool:
        located = self._locate(key)
        return (
            located is not None and located[0].name != Path(self._spec(key)["rel"]).name
        )

    def optional_real_bytes(self, key: str) -> bytes | None:
        if self._locate(key) is not None:
            return self.real_bytes(key)
        note = f"{key}: not present in {self.real_dir}; quote checks skipped"
        if note not in self.skipped:
            self.skipped.append(note)
        return None

    def mirror_extract_bytes(self, key: str) -> bytes:
        """The committed extract of an ``extract`` source, always read from this track's mirror.

        Used where the builder has no reader for the original format (the explanation PDF). The
        extract's hash is fixed by the mirror manifest, which also records the original's hash.
        """
        spec = self._spec(key)
        if f"{key}:extract" not in self.used:
            self.optional_real_bytes(
                key
            )  # hash-check the original (or extract) when present
        rel = spec["mirror_rel"]
        entry = self.mirror.get(rel)
        require(entry is not None, f"{key}: {rel} missing from {RAW_MANIFEST_PATH}")
        require(
            entry["original_sha256"] == spec["sha256"],
            f"{key}: the mirror extract was made from another original",
        )
        data = (RAW_MIRROR_DIR / rel).read_bytes()
        require(
            sha256_bytes(data) == entry["mirror_sha256"], f"{key}: extract hash changed"
        )
        self.used[f"{key}:extract"] = entry["mirror_sha256"]
        return data

    # -- quotations in non-PDF sources ----------------------------------------------------------
    def source_text(self, key: str) -> str | None:
        data = self.optional_real_bytes(key)
        if data is None:
            return None
        return source_text_of(key, data)

    def check_text_quote(self, key: str, quote: str) -> None:
        text = self.source_text(key)
        if text is None:
            return
        require(
            normalise(quote) in normalise(text),
            f"quote not found in source {key}: {quote!r}",
        )

    def check_gist(self, key: str, gist: str, *, original: str | None = None) -> None:
        """A gist may share at most GIST_MAX_SHARED consecutive words with its source text."""
        text = original if original is not None else self.source_text(key)
        if text is None:
            return
        shared = shared_word_runs(gist, text, GIST_MAX_SHARED)
        require(not shared, f"{key}: gist tracks the source wording {shared}: {gist!r}")


def html_text(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text)


def source_text_of(key: str, data: bytes) -> str:
    if key.startswith("govuk_"):
        doc = json.loads(data.decode("utf-8"))
        return html_text(doc["details"]["body"].encode("utf-8")) + "\n" + doc["title"]
    if data[:5] == b"<!DOC" or data.lstrip()[:1] == b"<":
        return html_text(data)
    return data.decode("utf-8")


# ---------------------------------------------------------------------------------------------
# Provenance references
# ---------------------------------------------------------------------------------------------


def data_ref(key: str, detail: str, quote: str | None = None) -> dict[str, Any]:
    from fi_sources import SOURCES

    spec = SOURCES[key]
    return {
        "kind": "dataset",
        "source_id": key,
        "file": spec["rel"],
        "sha256": spec["sha256"],
        "detail": detail,
        "quote": quote,
    }


def quote_ref(inputs: FiInputs, key: str, detail: str, quote: str) -> dict[str, Any]:
    inputs.check_text_quote(key, quote)
    return data_ref(key, detail, quote)


def raw_quote_ref(
    inputs: FiInputs, key: str, detail: str, quote: str
) -> dict[str, Any]:
    """A string checked in the raw source bytes (e.g. page metadata inside a script element)."""
    data = inputs.optional_real_bytes(key)
    if data is not None:
        require(
            quote in data.decode("utf-8", errors="replace"),
            f"string not found in the raw source {key}: {quote!r}",
        )
    ref = data_ref(key, detail, quote)
    ref["checked_against"] = "raw source text (no tag removal)"
    return ref


def extract_quote_ref(
    inputs: FiInputs, key: str, detail: str, quote: str
) -> dict[str, Any]:
    """A quotation from an ``extract`` source, checked against the committed extract."""
    text = inputs.mirror_extract_bytes(key).decode("utf-8")
    require(
        normalise(quote) in normalise(text),
        f"quote not found in the extract of {key}: {quote!r}",
    )
    ref = data_ref(key, detail, quote)
    ref["checked_against"] = "mirror extract (see the source's extract_rule)"
    return ref


def gist_ref(
    inputs: FiInputs,
    key: str,
    gist: str,
    *,
    original: str | None,
    **fields: Any,
) -> dict[str, Any]:
    """A builder-written gist of a text that is not openly licensed (checked when held)."""
    if original is not None:
        inputs.check_gist(key, gist, original=original)
    else:
        inputs.check_gist(key, gist)
    ref = data_ref(key, "gist written for this record; source text not reproduced")
    ref.update(fields)
    ref["gist_rule"] = (
        f"shares no run of more than {GIST_MAX_SHARED} consecutive words with the source text "
        "(checked when the source is held)"
    )
    return ref


# ---------------------------------------------------------------------------------------------
# Clock helpers (9-20 August 2019 are all on BST, UTC+01:00)
# ---------------------------------------------------------------------------------------------


def bst_to_utc(day: str, clock: str) -> datetime:
    """``day`` 'YYYY-MM-DD' and ``clock`` 'HH:MM[:SS]' on the UK clock (BST) -> aware UTC."""
    require(day.startswith("2019-08-"), f"no clock rule coded for {day}")
    parts = [int(x) for x in clock.split(":")]
    while len(parts) < 3:
        parts.append(0)
    local = datetime.fromisoformat(f"{day}T00:00:00").replace(tzinfo=UTC)
    return local + timedelta(hours=parts[0], minutes=parts[1], seconds=parts[2]) - BST


def utc_z(when: datetime, *, ms: bool = False) -> str:
    when = when.astimezone(UTC)
    if ms:
        return when.strftime("%Y-%m-%dT%H:%M:%S.") + f"{when.microsecond // 1000:03d}Z"
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def post_time(post_id: int) -> datetime:
    return snowflake_utc(post_id)


# ---------------------------------------------------------------------------------------------
# Minimal XLSX reader (standard library only) for the Network Rail glossary
# ---------------------------------------------------------------------------------------------

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _column(ref: str) -> str:
    match = re.match(r"[A-Z]+", ref)
    require(match is not None, f"bad cell reference {ref!r}")
    return match.group(0)


def xlsx_sheets(data: bytes) -> dict[str, list[dict[str, str]]]:
    """Every sheet as a list of {column letter: cell text} (shared and inline strings)."""
    archive = zipfile.ZipFile(io.BytesIO(data))
    shared: list[str] = []
    if "xl/sharedStrings.xml" in archive.namelist():
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        for item in root.findall("m:si", _NS):
            shared.append("".join(t.text or "" for t in item.iter(f"{{{_NS['m']}}}t")))
    rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target") for rel in rels}
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    sheets: dict[str, list[dict[str, str]]] = {}
    for sheet in workbook.iter(f"{{{_NS['m']}}}sheet"):
        target = targets[sheet.get(f"{{{_REL_NS}}}id")]
        root = ElementTree.fromstring(archive.read(f"xl/{target}"))
        rows = []
        for row in root.iter(f"{{{_NS['m']}}}row"):
            cells: dict[str, str] = {}
            for cell in row.findall("m:c", _NS):
                value = cell.find("m:v", _NS)
                if value is None:
                    inline = cell.find("m:is", _NS)
                    if inline is not None:
                        cells[_column(cell.get("r"))] = "".join(
                            t.text or "" for t in inline.iter(f"{{{_NS['m']}}}t")
                        )
                    continue
                text = value.text or ""
                cells[_column(cell.get("r"))] = (
                    shared[int(text)] if cell.get("t") == "s" else text
                )
            rows.append(cells)
        sheets[sheet.get("name")] = rows
    return sheets


def gz_text(data: bytes) -> str:
    return (gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data).decode("utf-8")


@dataclass(frozen=True)
class Post:
    """An organisational public post: identifier, organisation, gist, archive locator."""

    post_id: int
    organisation: str
    gist: str
    archive: (
        str  # Wayback URL of the capture holding the post (private provenance only)
    )

    @property
    def utc(self) -> datetime:
        return post_time(self.post_id)
