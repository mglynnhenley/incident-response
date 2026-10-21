"""Verify the approved agent bundle against its private provenance and the builder sources.

Builder-only tool (excluded from the image). Checks, in order:

1. Sources: every file in the handoff ``source_manifest.json`` exists with the recorded sha256;
   ``private/source_manifest.json`` is an exact copy; provenance source hashes agree.
2. Bundle manifest: schema, fixed categories, text_file listed as an artifact, only R01 has a
   time series, sha256 recorded for every artifact and matching the files, no stray files.
3. Provenance: bundle version, labels, text hashes, segment line ranges (in range, no overlap,
   every non-blank line covered), framing rules, and every verbatim quote found (after
   normalisation) on the stated PDF page of the stated source. Quotes are checked against the
   per-page extracted text files and, when PyMuPDF is importable, against the PDFs themselves.
4. R01: the bundle CSV is rebuilt from the NESO archive and compared byte-for-byte (see
   build_r01.py); the sample rows quoted in R01.txt are the first rows of the CSV.
5. Leakage: no document text states the frequency landmarks.

Prints a report and exits non-zero on any failure.

Usage (from the environment root)::

    uv run --frozen python builder/verify_provenance.py
    uv run --no-project --with pymupdf python builder/verify_provenance.py --pdf on

Environment: GB_HANDOFF_DIR (handoff root) and GB_TEXT_DIR (extracted per-page text) override
the defaults ``<workspace>/.context/handoff/GB_power_cut_handoff`` and ``.../handoff/text``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

ENV_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ENV_ROOT.parent
INCIDENT_DIR = ENV_ROOT / "src" / "environment" / "incident"
BUNDLE_DIR = INCIDENT_DIR / "bundle"
PRIVATE_DIR = INCIDENT_DIR / "private"
MANIFEST_PATH = BUNDLE_DIR / "manifest.json"
PROVENANCE_PATH = PRIVATE_DIR / "provenance.json"
PRIVATE_SOURCE_MANIFEST = PRIVATE_DIR / "source_manifest.json"
DEFAULT_HANDOFF_DIR = WORKSPACE_ROOT / ".context" / "handoff" / "GB_power_cut_handoff"

CATEGORIES = {
    "R01": "measurement_data",
    "R03": "network_records",
    "S01": "generator_records",
    "S03": "generator_records",
    "S04": "personnel_accounts",
}
LABELS = {
    "R01": "REAL MEASURED DATA EXTRACT",
    "R03": "RECONSTRUCTED FOR EVALUATION FROM PUBLISHED RECORDS — NOT AN ORIGINAL SYSTEM EXPORT",
    "S01": "SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE",
    "S03": "SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE",
    "S04": "SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE",
}
VALUE_STATUSES = {
    "measured",
    "reported",
    "estimated",
    "illustrative",
    "derived",
    "framing",
}
EXTRACTION_METHODS = {
    "transcription",
    "paraphrase",
    "arithmetic",
    "layout",
    "framing",
    "script",
}
FORBIDDEN_LANDMARKS = ("48.787", "49.083", "50.001")
LINE_RANGE = re.compile(r"^L(\d+)(?:-L?(\d+))?$")
MIN_QUOTE_WORDS = 3

_DASHES = "‐‑‒–—―−﹘﹣－"
_DOUBLE_QUOTES = "“”„‟″«»"
_SINGLE_QUOTES = "‘’‚‛′´`"
_TRANSLATE = {ord(c): "-" for c in _DASHES}
_TRANSLATE.update({ord(c): '"' for c in _DOUBLE_QUOTES})
_TRANSLATE.update({ord(c): "'" for c in _SINGLE_QUOTES})
_TRANSLATE[0x00AD] = None  # soft hyphen


def normalise(text: str) -> str:
    """Casefold, unify dashes/quotes/apostrophes, drop soft hyphens, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATE).casefold()
    return re.sub(r"\s+", " ", text).strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def handoff_dir() -> Path:
    return Path(os.environ.get("GB_HANDOFF_DIR", str(DEFAULT_HANDOFF_DIR))).resolve()


def text_dir(handoff: Path) -> Path:
    return Path(os.environ.get("GB_TEXT_DIR", str(handoff.parent / "text"))).resolve()


def parse_line_range(value: str) -> tuple[int, int]:
    match = LINE_RANGE.match(value.strip())
    if not match:
        raise ValueError(f"bad line range {value!r}")
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if start < 1 or end < start:
        raise ValueError(f"bad line range {value!r}")
    return start, end


def load_page_texts(path: Path, source_id: str) -> dict[int, str]:
    """Split an extracted text file on '=== <ID> PDF page <n> ===' markers."""
    raw = path.read_text(encoding="utf-8")
    marker = re.compile(
        rf"^=== {re.escape(source_id)} PDF page (\d+) ===$", re.MULTILINE
    )
    parts = marker.split(raw)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.notes: list[str] = []
        self.counts: dict[str, int] = {}

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)

    def count(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n


# --------------------------------------------------------------------------- sources


def check_sources(
    handoff: Path, provenance: dict[str, Any], report: Report
) -> dict[str, Any]:
    manifest_path = handoff / "source_manifest.json"
    if not manifest_path.is_file():
        report.fail(f"handoff source manifest missing: {manifest_path}")
        return {}
    entries = {
        entry["id"]: entry for entry in json.loads(manifest_path.read_text("utf-8"))
    }
    for source_id, entry in entries.items():
        path = handoff / entry["file"]
        if not path.is_file():
            report.fail(f"source {source_id}: missing file {path}")
            continue
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            report.fail(
                f"source {source_id}: sha256 {actual} != manifest {entry['sha256']}"
            )
        else:
            report.count("source files hash-verified")
    if not PRIVATE_SOURCE_MANIFEST.is_file():
        report.fail("private/source_manifest.json missing")
    elif PRIVATE_SOURCE_MANIFEST.read_bytes() != manifest_path.read_bytes():
        report.fail(
            "private/source_manifest.json is not an exact copy of the handoff manifest"
        )
    for source_id, source in provenance.get("sources", {}).items():
        kind = source.get("kind")
        if kind in ("pdf", "archive"):
            entry = entries.get(source_id)
            if entry is None:
                report.fail(f"provenance source {source_id} not in source manifest")
            elif (
                source.get("sha256") != entry["sha256"]
                or source.get("file") != entry["file"]
            ):
                report.fail(
                    f"provenance source {source_id}: file/sha256 differ from manifest"
                )
        elif kind == "text":
            path = handoff / source["file"]
            if not path.is_file():
                report.fail(f"provenance source {source_id}: missing {path}")
            elif sha256_file(path) != source.get("sha256"):
                report.fail(
                    f"provenance source {source_id}: sha256 mismatch for {path}"
                )
        else:
            report.fail(f"provenance source {source_id}: unknown kind {kind!r}")
    return entries


# --------------------------------------------------------------------------- manifest


def check_manifest(manifest: dict[str, Any], report: Report) -> None:
    for key in ("bundle_id", "bundle_version", "documents"):
        if key not in manifest:
            report.fail(f"manifest: missing key {key}")
    documents = manifest.get("documents", [])
    ids = [doc.get("doc_id") for doc in documents]
    if sorted(ids) != sorted(CATEGORIES):
        report.fail(f"manifest: documents {ids} != expected {sorted(CATEGORIES)}")
    listed: set[str] = set()
    for doc in documents:
        doc_id = doc.get("doc_id")
        for key in (
            "title",
            "owner",
            "date",
            "category",
            "text_file",
            "artifacts",
            "sha256",
        ):
            if key not in doc:
                report.fail(f"manifest {doc_id}: missing {key}")
        if doc.get("category") != CATEGORIES.get(doc_id):
            report.fail(f"manifest {doc_id}: category {doc.get('category')!r}")
        files = [artifact.get("file") for artifact in doc.get("artifacts", [])]
        if doc.get("text_file") not in files:
            report.fail(f"manifest {doc_id}: text_file not listed among artifacts")
        if set(doc.get("sha256", {})) != set(files):
            report.fail(
                f"manifest {doc_id}: sha256 keys {sorted(doc.get('sha256', {}))} != artifacts"
            )
        for artifact in doc.get("artifacts", []):
            rel = artifact.get("file", "")
            listed.add(rel)
            if not rel.startswith(f"{doc_id}/") or ".." in Path(rel).parts:
                report.fail(
                    f"manifest {doc_id}: artifact path {rel!r} outside its folder"
                )
                continue
            has_series = "timeseries" in artifact
            if has_series and doc_id != "R01":
                report.fail(
                    f"manifest {doc_id}: only R01 may have a timeseries artifact"
                )
            path = BUNDLE_DIR / rel
            if not path.is_file():
                report.fail(f"manifest {doc_id}: missing artifact {rel}")
                continue
            actual = sha256_file(path)
            if doc.get("sha256", {}).get(rel) != actual:
                report.fail(f"manifest {doc_id}: sha256 mismatch for {rel}")
            else:
                report.count("bundle artifacts hash-verified")
    on_disk = {
        str(path.relative_to(BUNDLE_DIR))
        for path in BUNDLE_DIR.rglob("*")
        if path.is_file()
        and path.name != "manifest.json"
        and "__pycache__" not in path.parts
    }
    stray = sorted(on_disk - listed)
    if stray:
        report.fail(f"bundle contains files not in the manifest: {stray}")


# --------------------------------------------------------------------------- provenance


class QuoteChecker:
    def __init__(
        self, handoff: Path, texts: Path, provenance: dict[str, Any], pdf_mode: str
    ):
        self.handoff = handoff
        self.texts = texts
        self.sources = provenance.get("sources", {})
        self.page_cache: dict[str, dict[int, str]] = {}
        self.pdf_cache: dict[str, Any] = {}
        self.text_file_cache: dict[str, str] = {}
        self.fitz = None
        if pdf_mode != "off":
            try:
                import fitz  # type: ignore[import-not-found]

                self.fitz = fitz
            except ImportError:
                if pdf_mode == "on":
                    raise SystemExit(
                        "--pdf on requested but PyMuPDF (fitz) is not importable"
                    )

    def _pages(self, source_id: str) -> dict[int, str]:
        if source_id not in self.page_cache:
            path = self.texts / f"{source_id}.txt"
            pages = load_page_texts(path, source_id) if path.is_file() else {}
            self.page_cache[source_id] = {n: normalise(t) for n, t in pages.items()}
        return self.page_cache[source_id]

    def _pdf_page(self, source_id: str, page: int) -> str | None:
        if self.fitz is None:
            return None
        if source_id not in self.pdf_cache:
            path = self.handoff / self.sources[source_id]["file"]
            self.pdf_cache[source_id] = self.fitz.open(str(path))
        doc = self.pdf_cache[source_id]
        if not 1 <= page <= len(doc):
            return ""
        return normalise(doc[page - 1].get_text())

    def check(self, where: str, ref: dict[str, Any], report: Report) -> None:
        source_id = ref.get("source_id")
        source = self.sources.get(source_id)
        if source is None:
            report.fail(f"{where}: unknown source_id {source_id!r}")
            return
        kind = source.get("kind")
        quote = ref.get("quote")
        if kind == "archive":
            if not ref.get("script"):
                report.fail(f"{where}: archive source must name the builder script")
            elif not (ENV_ROOT / ref["script"]).is_file():
                report.fail(f"{where}: script {ref['script']} missing")
            else:
                report.count("script-derived source references")
            return
        if not quote or len(quote.split()) < MIN_QUOTE_WORDS:
            report.fail(
                f"{where}: quote missing or shorter than {MIN_QUOTE_WORDS} words: {quote!r}"
            )
            return
        needle = normalise(quote)
        if kind == "text":
            if source_id not in self.text_file_cache:
                path = self.handoff / source["file"]
                self.text_file_cache[source_id] = normalise(path.read_text("utf-8"))
            if needle not in self.text_file_cache[source_id]:
                report.fail(f"{where}: quote not found in {source['file']}: {quote!r}")
            else:
                report.count("quotes verified (text source)")
            return
        page = ref.get("pdf_page")
        if not isinstance(page, int):
            report.fail(f"{where}: pdf_page missing for {source_id}")
            return
        pages = self._pages(source_id)
        if not pages:
            report.fail(f"{where}: no extracted text for {source_id} in {self.texts}")
        elif needle not in pages.get(page, ""):
            elsewhere = [n for n, text in pages.items() if needle in text]
            report.fail(
                f"{where}: quote not on {source_id} PDF page {page} (found on {elsewhere}): {quote!r}"
            )
        else:
            report.count("quotes verified on page (extracted text)")
        pdf_text = self._pdf_page(source_id, page)
        if pdf_text is not None:
            if needle not in pdf_text:
                report.fail(
                    f"{where}: quote not on {source_id} PDF page {page} (PyMuPDF): {quote!r}"
                )
            else:
                report.count("quotes verified on page (PyMuPDF)")


def check_provenance(
    manifest: dict[str, Any],
    provenance: dict[str, Any],
    checker: QuoteChecker,
    report: Report,
) -> None:
    if provenance.get("bundle_version") != manifest.get("bundle_version"):
        report.fail("provenance bundle_version differs from manifest")
    documents = provenance.get("documents", {})
    for doc in manifest.get("documents", []):
        doc_id = doc["doc_id"]
        entry = documents.get(doc_id)
        if entry is None:
            report.fail(f"provenance: no entry for {doc_id}")
            continue
        if entry.get("label") != LABELS[doc_id]:
            report.fail(f"provenance {doc_id}: label {entry.get('label')!r}")
        text_path = BUNDLE_DIR / doc["text_file"]
        data = text_path.read_bytes()
        if entry.get("text_sha256") != sha256_bytes(data):
            report.fail(
                f"provenance {doc_id}: text_sha256 does not match {doc['text_file']}"
            )
        lines = data.decode("utf-8").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        label_line = next(
            (line for line in lines[:12] if line.startswith("STATUS: ")), ""
        )
        if LABELS[doc_id] not in label_line:
            report.fail(
                f"{doc_id}: STATUS line does not carry the label {LABELS[doc_id]!r}"
            )
        covered = [0] * (len(lines) + 1)
        for index, segment in enumerate(entry.get("segments", [])):
            where = f"{doc_id} segment {index} ({segment.get('lines')})"
            try:
                start, end = parse_line_range(segment.get("lines", ""))
            except ValueError as exc:
                report.fail(f"{where}: {exc}")
                continue
            if end > len(lines):
                report.fail(f"{where}: beyond last line {len(lines)}")
                continue
            for n in range(start, end + 1):
                covered[n] += 1
            status = segment.get("value_status")
            method = segment.get("extraction_method")
            if status not in VALUE_STATUSES:
                report.fail(f"{where}: value_status {status!r}")
            if method not in EXTRACTION_METHODS:
                report.fail(f"{where}: extraction_method {method!r}")
            if not segment.get("content"):
                report.fail(f"{where}: empty content description")
            sources = segment.get("sources")
            if not isinstance(sources, list):
                report.fail(f"{where}: sources must be a list")
                continue
            if method == "framing" or status == "framing":
                if method != "framing" or status != "framing" or sources:
                    report.fail(
                        f"{where}: framing segments need method+status framing, no sources"
                    )
                report.count("framing segments")
                continue
            if not sources:
                report.fail(f"{where}: non-framing segment without sources")
            for ref_index, ref in enumerate(sources):
                checker.check(f"{where} source {ref_index}", ref, report)
            report.count("sourced segments")
        for n, line in enumerate(lines, start=1):
            if line.strip() and covered[n] == 0:
                report.fail(f"{doc_id}: line L{n} not covered by any segment")
            if covered[n] > 1:
                report.fail(f"{doc_id}: line L{n} covered by {covered[n]} segments")
        report.count("documents with full line coverage")


# --------------------------------------------------------------------------- R01 + leakage


def check_r01(manifest: dict[str, Any], report: Report) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_r01  # noqa: PLC0415  (builder-local module)

    buffer = io.StringIO()
    stdout = sys.stdout
    sys.stdout = buffer
    try:
        code = build_r01.main(["--check"])
    finally:
        sys.stdout = stdout
    if code != 0:
        report.fail(
            "R01: build_r01.py --check failed (CSV not reproducible from the NESO archive)"
        )
    else:
        report.note(
            "R01: CSV rebuilt from NESO archive, byte-identical to handoff, landmarks match"
        )
    doc = next(d for d in manifest["documents"] if d["doc_id"] == "R01")
    series = next(a for a in doc["artifacts"] if "timeseries" in a)
    csv_lines = (BUNDLE_DIR / series["file"]).read_text("utf-8").splitlines()
    text = (BUNDLE_DIR / doc["text_file"]).read_text("utf-8").splitlines()
    quoted = [line for line in text if line.startswith("2019-08-09T") and "," in line]
    if "timestamp,frequency_hz" not in text or not quoted:
        report.fail("R01.txt: sample rows block missing")
    elif quoted != csv_lines[1 : 1 + len(quoted)]:
        report.fail(
            "R01.txt: quoted sample rows are not the first data rows of the CSV"
        )
    rows = list(csv.reader(io.StringIO("\n".join(csv_lines))))
    meta = series["timeseries"]
    if (
        len(rows) - 1 != meta["rows"]
        or rows[1][0] != meta["first"]
        or rows[-1][0] != meta["last"]
    ):
        report.fail("R01: manifest timeseries metadata disagrees with the CSV")


def check_leakage(manifest: dict[str, Any], report: Report) -> None:
    for doc in manifest["documents"]:
        text = (BUNDLE_DIR / doc["text_file"]).read_text("utf-8")
        for value in FORBIDDEN_LANDMARKS:
            if value in text:
                report.fail(f"{doc['doc_id']}: text states frequency landmark {value}")
    if any(value in MANIFEST_PATH.read_text("utf-8") for value in FORBIDDEN_LANDMARKS):
        report.fail("manifest.json states a frequency landmark")


def check_archive_members(
    provenance: dict[str, Any], handoff: Path, report: Report
) -> None:
    for source_id, source in provenance.get("sources", {}).items():
        member = source.get("member")
        if source.get("kind") != "archive" or not member:
            continue
        with zipfile.ZipFile(handoff / source["file"]) as archive:
            try:
                info = archive.getinfo(member)
            except KeyError:
                report.fail(f"{source_id}: archive member {member!r} missing")
                continue
        year, month, day = info.date_time[:3]
        stamp = f"{year:04d}-{month:02d}-{day:02d}"
        if source.get("member_date") and stamp != source["member_date"]:
            report.fail(
                f"{source_id}: member date {stamp} != provenance {source['member_date']}"
            )


def run(pdf_mode: str) -> Report:
    report = Report()
    handoff = handoff_dir()
    texts = text_dir(handoff)
    manifest = json.loads(MANIFEST_PATH.read_text("utf-8"))
    provenance = json.loads(PROVENANCE_PATH.read_text("utf-8"))
    check_sources(handoff, provenance, report)
    check_archive_members(provenance, handoff, report)
    check_manifest(manifest, report)
    checker = QuoteChecker(handoff, texts, provenance, pdf_mode)
    report.note(
        "PyMuPDF available: quotes also checked against PDFs"
        if checker.fitz is not None
        else "PyMuPDF not importable: quotes checked against extracted page text only"
    )
    check_provenance(manifest, provenance, checker, report)
    check_r01(manifest, report)
    check_leakage(manifest, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--pdf",
        choices=("auto", "on", "off"),
        default="auto",
        help="also check quotes against the PDFs with PyMuPDF (auto = if importable)",
    )
    args = parser.parse_args(argv)
    report = run(args.pdf)
    print(f"Handoff: {handoff_dir()}")
    for note in report.notes:
        print(f"NOTE  {note}")
    for key, value in sorted(report.counts.items()):
        print(f"OK    {key}: {value}")
    for failure in report.failures:
        print(f"FAIL  {failure}")
    status = "FAILED" if report.failures else "PASSED"
    print(f"Provenance verification {status} ({len(report.failures)} failure(s))")
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
