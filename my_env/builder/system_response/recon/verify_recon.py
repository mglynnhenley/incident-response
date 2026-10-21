"""Verify the reconstruction track's outputs against their sources (builder-only).

Checks, in order (non-zero exit on any failure):

1. Inputs: the handoff PDFs match ``source_manifest.json``; catalogue extracts, their page
   images and the real-data manifest match their pinned sha256.
2. Freshness and determinism: a fresh in-memory build is byte-identical to every file on disk.
3. Copies: R01 (text and CSV), R03, S03 and S04 are byte-identical to MVP bundle 1.1.0; S01
   differs from the MVP only by the decision-19 clock line.
4. Documents: text conventions (UTF-8, LF, no tabs, <= 110 chars, no trailing blanks, value
   tags from the vocabulary and never split from their value, quantities tagged on sourced
   lines of new documents, STATUS label, no frequency landmarks); provenance coverage (every
   non-blank line in exactly one segment; framing rules); every quote found on its stated PDF
   page (and in the PDF itself with ``--pdf on``) or in its catalogue row and field; the
   number rule for R08, R10, S05, S06, S07 and S12.
5. Rows: schema, IDs, UTC index format, value statuses, room/asset IDs, the cited document
   lines, text restating those lines, and index times recomputed from the recorded times.
6. Witness cards: schema, STATUS, unique response IDs, distinct topics (each block's first topic
   selects that block under the runtime matcher when importable), quotes and the number rule.
7. Data-return registry: schema, evidence IDs, and the basis of every ``not_held`` message.

    uv run --frozen python builder/system_response/recon/verify_recon.py
    uv run --no-project --with pymupdf python builder/system_response/recon/verify_recon.py --pdf on
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_recon  # noqa: E402
import recon_doc_specs  # noqa: E402
import recon_rows  # noqa: E402
from recon_common import (  # noqa: E402
    ALL_DOCS,
    CATALOGUE_EXTRACTS,
    COPIED_DOCS,
    DATA_RETURNS_PATH,
    ENV_ROOT,
    EXTRACTION_METHODS,
    LABELS,
    MVP_BUNDLE_DIR,
    NEW_DOCS,
    PDF_SOURCES,
    PROVENANCE_PATH,
    ROWS_DIR,
    SR_BUNDLE_DIR,
    TAGS,
    VALUE_STATUSES,
    WITNESS_DIR,
    WITNESS_EVIDENCE_ID,
    WITNESS_LABEL,
    catalogue_dir,
    handoff_dir,
    load_page_texts,
    normalise,
    numbers_in,
    parse_line_range,
    real_data_dir,
    sha256_bytes,
    sha256_file,
    strip_tags,
    text_dir,
    text_lines,
)

LANDMARKS = ("48.787", "49.083", "50.001")
TAG_RE = re.compile(r"\[([a-z]+)\]")
TAG_ANY = re.compile(r"\[(?:{})\]".format("|".join(TAGS)))
QUANTITY = re.compile(
    r"(?<![\w.])[~>+-]?\d[\d,.]*\s?"
    r"(?:MW|MVAr|MVAR|kV|kA|ms|s|Hz|%|km|GW|GVAs|MVA\.s|seconds?|minutes?|mins?|hours?)(?!\w)"
    r"|\b\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
)
ASSET_KEYS = {
    "event_id",
    "evidence_id",
    "asset_id",
    "recorded_time",
    "clock_basis",
    "index_time_utc",
    "index_uncertainty_s",
    "signal",
    "value",
    "unit",
    "text",
    "value_status",
    "kind",
    "provenance",
}
CONTROL_KEYS = {
    "entry_id",
    "evidence_id",
    "room_id",
    "recorded_time",
    "clock_basis",
    "index_time_utc",
    "index_uncertainty_s",
    "from",
    "to",
    "channel",
    "text",
    "value_status",
    "kind",
    "provenance",
}
ASSET_IDS = {"ESW-400", "HORNSEA-ONE", "LITTLE-BARFORD"}
ROOM_IDS = {"ESO-ENCC"}
PARTY_RE = re.compile(r"^(ESO-ENCC|NGET-TNCC|DNOS|DNO-[A-Z0-9-]+|SCOT-SP|SCOT-SHETL)$")
RECORD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
NAME_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
UTC_RE = re.compile(r"^2019-08-09T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
FUZZY_FIELDS = {"annotation_text", "transcription_note", "merged_cell_note"}


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.counts: dict[str, int] = {}

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def count(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n


# --------------------------------------------------------------------------- quotes


class Quotes:
    def __init__(self, pdf_mode: str) -> None:
        self.pages = {
            s: {
                n: normalise(t)
                for n, t in load_page_texts(text_dir() / f"{s}.txt", s).items()
            }
            for s in PDF_SOURCES
        }
        self.catalogue: dict[str, dict[str, dict[str, str]]] = {}
        for extract_id, meta in CATALOGUE_EXTRACTS.items():
            data = (catalogue_dir() / meta["file"]).read_bytes()
            reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
            self.catalogue[extract_id] = {row[meta["key"]]: row for row in reader}
        manifest = json.loads(
            (real_data_dir() / "real_data_manifest.json").read_text("utf-8")
        )
        self.real = {r["dataset_id"]: r for r in manifest["records"]}
        self.fitz = None
        self.pdfs: dict[str, Any] = {}
        if pdf_mode != "off":
            try:
                import fitz  # type: ignore[import-not-found]

                self.fitz = fitz
            except ImportError:
                if pdf_mode == "on":
                    raise SystemExit("--pdf on requested but PyMuPDF is not importable")

    def _pdf_text(self, source_id: str, page: int) -> str | None:
        if self.fitz is None:
            return None
        if source_id not in self.pdfs:
            manifest = json.loads(
                (handoff_dir() / "source_manifest.json").read_text("utf-8")
            )
            entry = next(e for e in manifest if e["id"] == source_id)
            self.pdfs[source_id] = self.fitz.open(str(handoff_dir() / entry["file"]))
        doc = self.pdfs[source_id]
        return normalise(doc[page - 1].get_text()) if 1 <= page <= len(doc) else ""

    def check(self, where: str, ref: dict[str, Any], report: Report) -> None:
        source_id = ref.get("source_id")
        quote = ref.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            report.fail(f"{where}: empty quote")
            return
        if source_id in PDF_SOURCES:
            if len(quote.split()) < 3:
                report.fail(f"{where}: quote shorter than 3 words: {quote!r}")
                return
            page = ref.get("pdf_page")
            needle = normalise(quote)
            if needle not in self.pages[source_id].get(page, ""):
                found = [n for n, t in self.pages[source_id].items() if needle in t]
                report.fail(
                    f"{where}: quote not on {source_id} p{page} (found {found}): {quote!r}"
                )
                return
            report.count("PDF quotes verified on page (extracted text)")
            pdf_text = self._pdf_text(source_id, page)
            if pdf_text is not None:
                if needle not in pdf_text:
                    report.fail(
                        f"{where}: quote not on {source_id} p{page} (PyMuPDF): {quote!r}"
                    )
                else:
                    report.count("PDF quotes verified on page (PyMuPDF)")
        elif source_id in CATALOGUE_EXTRACTS:
            meta = CATALOGUE_EXTRACTS[source_id]
            (key,) = ref["row"].values()
            row = self.catalogue[source_id].get(key)
            field = ref.get("field")
            if row is None or field not in row:
                report.fail(
                    f"{where}: no row {key!r} / field {field!r} in {meta['file']}"
                )
                return
            value = row[field]
            ok = (
                normalise(quote) in normalise(value)
                if field in FUZZY_FIELDS
                else normalise(quote) == normalise(value)
            )
            if not ok:
                report.fail(
                    f"{where}: {meta['file']} row {key} {field}={value!r}, quote {quote!r}"
                )
                return
            report.count("catalogue fields verified")
        elif source_id == "REAL-DATA-MANIFEST":
            record = self.real.get(ref.get("dataset_id"))
            if record is None or normalise(quote) not in normalise(
                str(record.get(ref["field"]))
            ):
                report.fail(
                    f"{where}: real-data manifest {ref.get('dataset_id')} lacks {quote!r}"
                )
                return
            report.count("real-data manifest fields verified")
        else:
            report.fail(f"{where}: unknown source_id {source_id!r}")


def check_numbers(
    where: str,
    text: str,
    sources: list[dict[str, Any]],
    allowed: list[str],
    report: Report,
) -> None:
    pool: set[str] = set(allowed)
    for ref in sources:
        pool |= numbers_in(ref.get("quote") or "")
        pool |= numbers_in(ref.get("section") or "")
    text = re.sub(r"\b(?:PART|Part|SECTION|Section) [0-9A-Z]\b", " ", text)
    missing = sorted(numbers_in(strip_tags(text)) - pool)
    if missing:
        report.fail(f"{where}: numbers not found in quotes or sections: {missing}")
    else:
        report.count("number-rule checks passed")


# --------------------------------------------------------------------------- checks


def check_inputs(report: Report) -> None:
    manifest = json.loads((handoff_dir() / "source_manifest.json").read_text("utf-8"))
    for entry in manifest:
        if entry["id"] in PDF_SOURCES:
            if sha256_file(handoff_dir() / entry["file"]) != entry["sha256"]:
                report.fail(f"source {entry['id']}: sha256 mismatch")
            else:
                report.count("source PDFs hash-verified")
    for extract_id, meta in CATALOGUE_EXTRACTS.items():
        for name, digest in (
            (meta["file"], meta["sha256"]),
            (meta["image_file"], meta["image_sha256"]),
        ):
            if sha256_file(catalogue_dir() / name) != digest:
                report.fail(f"{extract_id}: {name} sha256 mismatch")
            else:
                report.count("catalogue files hash-verified")
    provenance = json.loads(PROVENANCE_PATH.read_text("utf-8"))
    real = provenance["sources"]["REAL-DATA-MANIFEST"]
    if sha256_file(real_data_dir() / real["file"]) != real["sha256"]:
        report.fail("real_data_manifest.json sha256 mismatch")


def check_fresh(report: Report) -> None:
    outputs = build_recon.build()
    for path, data in sorted(outputs.items()):
        if not path.is_file() or path.read_bytes() != data:
            report.fail(
                f"stale or missing output: {path.relative_to(ENV_ROOT)} (run build_recon.py)"
            )
        else:
            report.count("outputs identical to a fresh build")
    again = build_recon.build()
    if again != outputs:
        report.fail("two in-memory builds differ (non-deterministic build)")


def check_copies(report: Report) -> None:
    for doc_id in COPIED_DOCS:
        rel = f"{doc_id}/{doc_id}.txt"
        if (SR_BUNDLE_DIR / rel).read_bytes() != (MVP_BUNDLE_DIR / rel).read_bytes():
            report.fail(f"{rel} differs from MVP bundle 1.1.0")
    csv_rel = build_recon.R01_CSV
    if (SR_BUNDLE_DIR / csv_rel).read_bytes() != (
        MVP_BUNDLE_DIR / csv_rel
    ).read_bytes():
        report.fail("R01 CSV differs from MVP bundle 1.1.0")
    mvp = text_lines((MVP_BUNDLE_DIR / "S01" / "S01.txt").read_bytes())
    new = text_lines((SR_BUNDLE_DIR / "S01" / "S01.txt").read_bytes())
    index = mvp.index(recon_doc_specs.S01_MVP_CLOCK_LINE)
    expected = mvp[:index] + list(recon_doc_specs.S01_CLOCK_LINES) + mvp[index + 1 :]
    if new != expected:
        report.fail("S01 differs from MVP S01 by more than the decision-19 clock line")
    joined = " ".join(new)
    if "UTC+01:00" in joined or "BST =" in joined or "BST" in joined:
        report.fail("S01 gives a BST conversion")
    report.count("copied/derived documents checked", len(COPIED_DOCS) + 1)


def check_text(
    doc_id: str, data: bytes, provenance: dict[str, Any], report: Report
) -> None:
    if data.startswith(b"\xef\xbb\xbf") or b"\r" in data or b"\t" in data:
        report.fail(f"{doc_id}: BOM, CR or tab")
    text = data.decode("utf-8")
    if not text.endswith("\n") or text.endswith("\n\n"):
        report.fail(f"{doc_id}: must end with exactly one newline")
    lines = text_lines(data)
    label = LABELS[doc_id]
    header = " ".join(lines[:12])
    if f"STATUS: {label}" not in header:
        report.fail(f"{doc_id}: STATUS label {label!r} missing from header")
    if not lines[0].startswith(f"DOCUMENT {doc_id} — "):
        report.fail(f"{doc_id}: first line must be 'DOCUMENT {doc_id} — <title>'")
    for value in LANDMARKS:
        if value in text:
            report.fail(f"{doc_id}: states frequency landmark {value}")
    framing: set[int] = set()
    for segment in provenance["segments"]:
        start, end = parse_line_range(segment["lines"])
        if segment["extraction_method"] == "framing":
            framing.update(range(start, end + 1))
    header_len = lines.index("") if "" in lines else 0
    for number, line in enumerate(lines, 1):
        if len(line) > 110 or line != line.rstrip():
            report.fail(f"{doc_id} L{number}: longer than 110 chars or trailing blank")
        for word in TAG_RE.findall(line):
            if word not in TAGS:
                report.fail(f"{doc_id} L{number}: unknown tag [{word}]")
        if re.match(r"\s+\[(?:{})\]".format("|".join(TAGS)), line):
            report.fail(f"{doc_id} L{number}: value tag split from its value")
        if doc_id in NEW_DOCS and number > header_len and number not in framing:
            if QUANTITY.search(line) and not TAG_ANY.search(line):
                report.fail(
                    f"{doc_id} L{number}: quantity without a value tag: {line!r}"
                )


def check_documents(quotes: Quotes, report: Report) -> None:
    provenance = json.loads(PROVENANCE_PATH.read_text("utf-8"))
    documents = provenance["documents"]
    if sorted(documents) != sorted(ALL_DOCS):
        report.fail(f"provenance documents {sorted(documents)} != {sorted(ALL_DOCS)}")
    for doc_id in ALL_DOCS:
        entry = documents[doc_id]
        data = (SR_BUNDLE_DIR / entry["text_file"]).read_bytes()
        if entry["text_sha256"] != sha256_bytes(data):
            report.fail(f"{doc_id}: text_sha256 mismatch")
        if entry["label"] != LABELS[doc_id]:
            report.fail(f"{doc_id}: label mismatch")
        check_text(doc_id, data, entry, report)
        lines = text_lines(data)
        covered = [0] * (len(lines) + 1)
        for index, segment in enumerate(entry["segments"]):
            where = f"{doc_id} segment {index} ({segment['lines']})"
            start, end = parse_line_range(segment["lines"])
            if end > len(lines):
                report.fail(f"{where}: beyond the last line")
                continue
            for n in range(start, end + 1):
                covered[n] += 1
            method, status = segment["extraction_method"], segment["value_status"]
            if method not in EXTRACTION_METHODS:
                report.fail(f"{where}: extraction_method {method!r}")
            if status not in VALUE_STATUSES and status != "derived":
                report.fail(f"{where}: value_status {status!r}")
            if method == "framing" or status == "framing":
                if method != status or segment["sources"]:
                    report.fail(
                        f"{where}: framing needs method+status framing and no sources"
                    )
                continue
            if not segment["sources"]:
                report.fail(f"{where}: no sources")
            for ref_index, ref in enumerate(segment["sources"]):
                if ref.get("source_id") == "NESO-F":
                    if not (ENV_ROOT / ref.get("script", "")).is_file():
                        report.fail(f"{where}: NESO-F reference without builder script")
                    continue
                if ref.get("source_id") == "HANDOFF-STATUS":
                    status_text = normalise(
                        (handoff_dir() / "SOURCE_STATUS.md").read_text("utf-8")
                    )
                    if normalise(ref["quote"]) not in status_text:
                        report.fail(f"{where}: quote not in SOURCE_STATUS.md")
                    continue
                quotes.check(f"{where} source {ref_index}", ref, report)
            if doc_id in NEW_DOCS:
                text = " ".join(lines[start - 1 : end])
                check_numbers(
                    where,
                    text,
                    segment["sources"],
                    segment.get("allow_numbers", []),
                    report,
                )
        for n, line in enumerate(lines, 1):
            if line.strip() and covered[n] == 0:
                report.fail(f"{doc_id}: L{n} not covered by any segment")
            if covered[n] > 1:
                report.fail(f"{doc_id}: L{n} covered by {covered[n]} segments")
        report.count("documents with full line coverage")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def check_rows(report: Report) -> None:
    seen: set[str] = set()
    for name, doc_id in build_recon.ROW_FRAGMENTS.items():
        path = ROWS_DIR / name
        raw = path.read_text("utf-8")
        for line in raw.splitlines():
            if json.dumps(json.loads(line), ensure_ascii=False, sort_keys=True) != line:
                report.fail(f"{name}: line is not canonical sorted-key JSON")
        rows = _load_jsonl(path)
        lines = text_lines((SR_BUNDLE_DIR / doc_id / f"{doc_id}.txt").read_bytes())
        for row in rows:
            kind = row.get("kind")
            keys = ASSET_KEYS if kind == "asset" else CONTROL_KEYS
            rid = row.get("event_id") if kind == "asset" else row.get("entry_id")
            where = f"{name} {rid}"
            if set(row) != keys:
                report.fail(f"{where}: keys {sorted(set(row) ^ keys)}")
                continue
            if not RECORD_ID.match(str(rid)) or rid in seen:
                report.fail(f"{where}: bad or duplicate ID")
            seen.add(str(rid))
            if row["evidence_id"] != doc_id:
                report.fail(f"{where}: evidence_id {row['evidence_id']} != {doc_id}")
            if not UTC_RE.match(row["index_time_utc"]):
                report.fail(f"{where}: index_time_utc {row['index_time_utc']!r}")
            if (
                not isinstance(row["index_uncertainty_s"], (int, float))
                or row["index_uncertainty_s"] < 0
            ):
                report.fail(f"{where}: index_uncertainty_s")
            if (
                row["value_status"] not in VALUE_STATUSES
                or row["value_status"] == "framing"
            ):
                report.fail(f"{where}: value_status {row['value_status']!r}")
            if kind == "asset":
                if row["asset_id"] not in ASSET_IDS or not NAME_ID.match(
                    row["asset_id"]
                ):
                    report.fail(f"{where}: asset_id {row['asset_id']!r}")
                if row["value"] is not None and not isinstance(
                    row["value"], (int, float)
                ):
                    report.fail(f"{where}: value must be a number or null")
                if (row["value"] is None) != (row["unit"] is None):
                    report.fail(
                        f"{where}: value and unit must both be set or both null"
                    )
            else:
                if row["room_id"] not in ROOM_IDS:
                    report.fail(f"{where}: room_id {row['room_id']!r}")
                for key in ("from", "to"):
                    for party in filter(None, (row[key] or "").split("; ")):
                        if not PARTY_RE.match(party):
                            report.fail(f"{where}: {key} party {party!r}")
            prov = row["provenance"]
            start, end = parse_line_range(prov["doc_lines"])
            entry_text = " ".join(" ".join(lines[start - 1 : end]).split())
            if row["recorded_time"].split(" ")[0] not in entry_text and not row[
                "recorded_time"
            ].startswith(("T", "during")):
                report.fail(
                    f"{where}: recorded_time {row['recorded_time']!r} not in cited lines"
                )
            if not row["text"]:
                report.fail(f"{where}: empty text")
            elif not row["text"].startswith("ESO ") and row["text"] != entry_text:
                report.fail(f"{where}: text does not restate the cited lines")
            if not prov["sources"]:
                report.fail(f"{where}: provenance without sources")
            report.count(f"{kind} rows checked")
    # Index times recomputed from recorded times.
    for row in _load_jsonl(ROWS_DIR / "recon_s03.jsonl"):
        expected = recon_rows.utc_from_bst("16:52:34").timestamp() + row["value"]
        actual = recon_rows.datetime.fromisoformat(row["index_time_utc"]).timestamp()
        if abs(expected - actual) > 0.0005:
            report.fail(f"{row['event_id']}: index time is not T + offset")
    for name in ("recon_r03.jsonl",):
        for row in _load_jsonl(ROWS_DIR / name):
            stamp = re.search(
                r"T(\d{2}:\d{2}:\d{2}(?:\.\d+)?)\+01:00", row["recorded_time"]
            )
            if stamp:
                expected = recon_rows.iso_z(recon_rows.utc_from_bst(stamp.group(1)))
                if expected != row["index_time_utc"]:
                    report.fail(
                        f"{row['event_id']}: index {row['index_time_utc']} != {expected}"
                    )


def check_witnesses(quotes: Quotes, report: Report) -> None:
    try:
        sys.path.insert(0, str(ENV_ROOT / "src"))
        from environment.incident.matching import match_topics  # type: ignore
    except Exception:  # pragma: no cover - runtime package absent
        match_topics = None
    files = sorted(WITNESS_DIR.glob("*.json"))
    if len(files) != 5:
        report.fail(f"expected 5 witness cards, found {len(files)}")
    response_ids: set[str] = set()
    for path in files:
        card = json.loads(path.read_text("utf-8"))
        where = path.name
        expected = {
            "persona_id",
            "role",
            "organisation",
            "evidence_id",
            "status",
            "unknown_response",
            "blocks",
        }
        if set(card) != expected:
            report.fail(f"{where}: keys {sorted(set(card) ^ expected)}")
            continue
        if (
            card["evidence_id"] != WITNESS_EVIDENCE_ID
            or path.stem != card["persona_id"]
        ):
            report.fail(f"{where}: evidence_id or file name mismatch")
        if not NAME_ID.match(card["persona_id"]):
            report.fail(f"{where}: persona_id pattern")
        if card["status"] != "STATUS: " + WITNESS_LABEL:
            report.fail(f"{where}: status label")
        if "not known" not in card["unknown_response"].casefold():
            report.fail(f"{where}: unknown_response must say 'not known'")
        topics = [block["topics"] for block in card["blocks"]]
        for index, block in enumerate(card["blocks"]):
            bwhere = f"{where} {block.get('response_id')}"
            if set(block) != {"response_id", "topics", "response_text", "provenance"}:
                report.fail(f"{bwhere}: block keys")
                continue
            if (
                not RECORD_ID.match(block["response_id"])
                or block["response_id"] in response_ids
            ):
                report.fail(f"{bwhere}: bad or duplicate response_id")
            response_ids.add(block["response_id"])
            text = block["response_text"]
            for value in LANDMARKS:
                if value in text:
                    report.fail(f"{bwhere}: states frequency landmark {value}")
            for word in TAG_RE.findall(text):
                if word not in TAGS:
                    report.fail(f"{bwhere}: unknown tag [{word}]")
            if not block["provenance"]:
                report.fail(f"{bwhere}: no provenance")
            for ref_index, ref in enumerate(block["provenance"]):
                quotes.check(f"{bwhere} source {ref_index}", ref, report)
            check_numbers(bwhere, text, block["provenance"], [], report)
            if match_topics is not None:
                result = match_topics(block["topics"][0], topics)
                if result.kind != "match" or result.blocks != (index,):
                    report.fail(
                        f"{bwhere}: first topic {block['topics'][0]!r} -> {result.kind} {result.blocks}"
                    )
                else:
                    report.count("witness topics selecting their own block")
        report.count("witness cards checked")


def check_registry(quotes: Quotes, report: Report) -> None:
    import recon_returns

    registry = json.loads(DATA_RETURNS_PATH.read_text("utf-8"))
    keys = set()
    docs = set(ALL_DOCS)
    for index, entry in enumerate(registry):
        where = f"data_returns[{index}] {entry.get('party')}/{entry.get('data_type')}"
        allowed = {"party", "data_type", "status", "evidence_id", "message"}
        if not set(entry) <= allowed or not {"party", "data_type", "status"} <= set(
            entry
        ):
            report.fail(f"{where}: keys")
            continue
        key = (entry["party"].casefold(), entry["data_type"].casefold())
        if key in keys:
            report.fail(f"{where}: duplicate")
        keys.add(key)
        if entry["status"] == "available":
            if entry.get("evidence_id") not in docs:
                report.fail(
                    f"{where}: evidence_id {entry.get('evidence_id')!r} not a track document"
                )
        elif entry["status"] in ("not_held", "refused"):
            if "evidence_id" in entry or not entry.get("message"):
                report.fail(f"{where}: refusal needs a message and no evidence_id")
            basis = recon_returns.NOT_HELD_BASIS.get(
                (entry["party"], entry["data_type"])
            )
            if basis is None:
                report.fail(f"{where}: no recorded basis")
            for ref_index, ref in enumerate(basis or []):
                quotes.check(f"{where} basis {ref_index}", ref, report)
        else:
            report.fail(f"{where}: status {entry['status']!r}")
        report.count("data-return entries checked")


def run(pdf_mode: str) -> Report:
    report = Report()
    check_inputs(report)
    check_fresh(report)
    check_copies(report)
    quotes = Quotes(pdf_mode)
    check_documents(quotes, report)
    check_rows(report)
    check_witnesses(quotes, report)
    check_registry(quotes, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", choices=("auto", "on", "off"), default="auto")
    args = parser.parse_args(argv)
    report = run(args.pdf)
    for key, value in sorted(report.counts.items()):
        print(f"  {key}: {value}")
    if report.failures:
        print(f"FAILED ({len(report.failures)}):")
        for failure in report.failures:
            print(f"  - {failure}")
        return 1
    print("OK: reconstruction outputs verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
