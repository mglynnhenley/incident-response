"""Verify the full-investigation reconstruction track's outputs (builder-only).

Checks, in order (non-zero exit on any failure):

1. Inputs: the six report PDFs (incl. ORR) match ``source_manifest.json``; the catalogue
   extracts and their page images, the real-data manifest and the two saved web pages match
   their pinned sha256.
2. Freshness and determinism: a fresh in-memory build is byte-identical to every file on disk.
3. R10: lines 1-133 are byte-identical to the frozen system-response R10 and keep increment A's
   segments exactly.
4. Documents: text conventions (UTF-8, LF, no tabs, <= 110 chars, no trailing blanks, value
   tags from the vocabulary and never split from their value, quantities tagged on sourced
   lines, STATUS label, no frequency landmarks); every non-blank line in exactly one segment;
   every quote found on its stated PDF page, catalogue row/field, manifest field or saved page;
   the number rule.
5. Leakage: no Ofgem enforcement outcome (decision 50), no social-media handle and no named
   individual from the sources (roles only) in any agent-visible output; index entries share
   no run of four consecutive words with the statement or article they index.
6. Rows: schema, IDs (no clash with the system-response logs), UTC index recomputed from the
   recorded time, cited lines, text restating them.
7. Witness cards: schema, STATUS, unique persona and response IDs (none shared with the
   system-response cards), quotes and the number rule, each block's first topic selecting that
   block under the runtime matcher, the runtime card parser accepting the visible card.
8. Data-return additions: schema, no pair shared with the system-response registry, evidence
   IDs, the recorded basis of every ``not_held`` message, and the runtime registry parser
   accepting the merged registry.

    uv run --frozen python builder/full_investigation/recon/verify_fi_recon.py
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_fi_recon  # noqa: E402
import fi_returns  # noqa: E402
import fi_rows  # noqa: E402
import fi_witnesses  # noqa: E402
from fi_recon_common import (  # noqa: E402
    ALL_DOCS,
    CATALOGUE_EXTRACTS,
    DATA_RETURNS_PATH,
    ENV_ROOT,
    EXCLUDED_PATTERNS,
    EXTRACTION_METHODS,
    FI_BUNDLE_DIR,
    FI_ROWS_DIR,
    LABELS,
    PDF_SOURCES,
    PROVENANCE_PATH,
    R10_FROZEN_LINES,
    REAL_DATA_MANIFEST_SHA256,
    REAL_FILES,
    ROW_FRAGMENT,
    SR_BUNDLE_DIR,
    SR_PRIVATE_DIR,
    SR_ROWS_DIR,
    TAGS,
    VALUE_STATUSES,
    WITNESS_DIR,
    WITNESS_EVIDENCE_ID,
    WITNESS_LABEL,
    catalogue_dir,
    handoff_dir,
    html_text,
    load_page_texts,
    normalise,
    numbers_in,
    parse_line_range,
    real_data_dir,
    sha256_bytes,
    sha256_file,
    shared_runs,
    statement_text,
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
RECORD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
NAME_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
UTC_RE = re.compile(r"^2019-08-09T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
FUZZY_FIELDS = {"annotation_text", "transcription_note", "merged_cell_note"}
# Individuals named in the sources; the evidence names roles only.
PERSONAL_NAMES = (
    "Julian Leslie",
    "Kwarteng",
    "Moloney",
    "Simon Wilde",
    "Bousso",
    "Fenton",
    "MacIver",
)
HANDLE = re.compile(r"(?<![\w.])@[A-Za-z0-9_]{2,}")


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
    def __init__(self) -> None:
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
        self.raw = {
            raw_id: normalise(html_text((real_data_dir() / meta["file"]).read_bytes()))
            for raw_id, meta in REAL_FILES.items()
        }

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
            if normalise(quote) not in self.pages[source_id].get(page, ""):
                found = [
                    n for n, t in self.pages[source_id].items() if normalise(quote) in t
                ]
                report.fail(
                    f"{where}: quote not on {source_id} p{page} (found {found}): {quote!r}"
                )
                return
            report.count("PDF quotes verified on page")
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
        elif source_id in REAL_FILES:
            meta = REAL_FILES[source_id]
            if ref.get("sha256") != meta["sha256"] or ref.get("file") != meta["file"]:
                report.fail(
                    f"{where}: {source_id} file/sha256 differ from the pinned record"
                )
            if normalise(quote) not in self.raw[source_id]:
                report.fail(f"{where}: quote not on saved page {source_id}: {quote!r}")
                return
            report.count("saved-page quotes verified")
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
    if (
        sha256_file(real_data_dir() / "real_data_manifest.json")
        != REAL_DATA_MANIFEST_SHA256
    ):
        report.fail("real_data_manifest.json sha256 mismatch")
    for raw_id, meta in REAL_FILES.items():
        if sha256_file(real_data_dir() / meta["file"]) != meta["sha256"]:
            report.fail(f"{raw_id}: saved page sha256 mismatch")
        else:
            report.count("saved pages hash-verified")


def check_fresh(report: Report) -> None:
    outputs = build_fi_recon.build()
    for path, data in sorted(outputs.items()):
        if not path.is_file() or path.read_bytes() != data:
            report.fail(
                f"stale or missing output: {path.relative_to(ENV_ROOT)} (run build_fi_recon.py)"
            )
        else:
            report.count("outputs identical to a fresh build")
    if build_fi_recon.build() != outputs:
        report.fail("two in-memory builds differ (non-deterministic build)")
    expected_cards = {p.name for p in outputs if p.parent == WITNESS_DIR}
    present = {p.name for p in WITNESS_DIR.glob("*.json")}
    sr_cards = {p.name for p in (SR_BUNDLE_DIR / "witnesses").glob("*.json")}
    extra = sorted(present - expected_cards - sr_cards)
    if extra:
        report.fail(f"unexpected witness cards in the bundle: {extra}")
    for name in sorted(present & sr_cards):
        if (WITNESS_DIR / name).read_bytes() != (
            SR_BUNDLE_DIR / "witnesses" / name
        ).read_bytes():
            report.fail(
                f"inherited witness card {name} differs from the system-response copy"
            )


def check_r10(report: Report) -> None:
    fi = text_lines((FI_BUNDLE_DIR / "R10" / "R10.txt").read_bytes())
    sr = text_lines((SR_BUNDLE_DIR / "R10" / "R10.txt").read_bytes())
    if fi[:R10_FROZEN_LINES] != sr or len(sr) != R10_FROZEN_LINES:
        report.fail("R10 lines 1-133 differ from the system-response R10")
    provenance = json.loads(PROVENANCE_PATH.read_text("utf-8"))["documents"]["R10"]
    sr_prov = json.loads((SR_PRIVATE_DIR / "provenance_recon.json").read_text("utf-8"))
    old = sr_prov["documents"]["R10"]["segments"]
    if provenance["segments"][: len(old)] != old:
        report.fail("R10 segments for lines 1-133 differ from increment A's provenance")
    report.count("R10 frozen prefix checked")


def _framing_lines(segments: list[dict[str, Any]]) -> set[int]:
    out: set[int] = set()
    for segment in segments:
        if segment["extraction_method"] == "framing":
            start, end = parse_line_range(segment["lines"])
            out.update(range(start, end + 1))
    return out


def check_text(doc_id: str, data: bytes, entry: dict[str, Any], report: Report) -> None:
    if data.startswith(b"\xef\xbb\xbf") or b"\r" in data or b"\t" in data:
        report.fail(f"{doc_id}: BOM, CR or tab")
    text = data.decode("utf-8")
    if not text.endswith("\n") or text.endswith("\n\n"):
        report.fail(f"{doc_id}: must end with exactly one newline")
    lines = text_lines(data)
    if f"STATUS: {LABELS[doc_id]}" not in " ".join(lines[:12]):
        report.fail(f"{doc_id}: STATUS label missing from header")
    if not lines[0].startswith(f"DOCUMENT {doc_id} — "):
        report.fail(f"{doc_id}: first line must be 'DOCUMENT {doc_id} — <title>'")
    for value in LANDMARKS:
        if value in text:
            report.fail(f"{doc_id}: states frequency landmark {value}")
    framing = _framing_lines(entry["segments"])
    header_len = lines.index("") if "" in lines else 0
    first_new = R10_FROZEN_LINES + 1 if doc_id == "R10" else header_len + 1
    for number, line in enumerate(lines, 1):
        if len(line) > 110 or line != line.rstrip():
            report.fail(f"{doc_id} L{number}: longer than 110 chars or trailing blank")
        for word in TAG_RE.findall(line):
            if word not in TAGS:
                report.fail(f"{doc_id} L{number}: unknown tag [{word}]")
        if re.match(r"\s+\[(?:{})\]".format("|".join(TAGS)), line):
            report.fail(f"{doc_id} L{number}: value tag split from its value")
        if number >= first_new and number not in framing:
            if QUANTITY.search(line) and not TAG_ANY.search(line):
                report.fail(
                    f"{doc_id} L{number}: quantity without a value tag: {line!r}"
                )


def check_documents(quotes: Quotes, report: Report) -> None:
    documents = json.loads(PROVENANCE_PATH.read_text("utf-8"))["documents"]
    if sorted(documents) != sorted(ALL_DOCS):
        report.fail(f"provenance documents {sorted(documents)} != {sorted(ALL_DOCS)}")
    for doc_id in ALL_DOCS:
        entry = documents[doc_id]
        data = (FI_BUNDLE_DIR / entry["text_file"]).read_bytes()
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
            if status not in VALUE_STATUSES:
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
                quotes.check(f"{where} source {ref_index}", ref, report)
            check_numbers(
                where,
                " ".join(lines[start - 1 : end]),
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


def visible_texts() -> dict[str, str]:
    """Every agent-visible text this track writes (bundle files and registry messages)."""
    out = {}
    for doc_id in ALL_DOCS:
        out[f"{doc_id}.txt"] = (FI_BUNDLE_DIR / doc_id / f"{doc_id}.txt").read_text(
            "utf-8"
        )
    for card in fi_witnesses.cards():
        path = WITNESS_DIR / f"{card['persona_id']}.json"
        out[path.name] = path.read_text("utf-8")
    out[ROW_FRAGMENT] = "\n".join(
        json.loads(line)["text"]
        for line in (FI_ROWS_DIR / ROW_FRAGMENT).read_text("utf-8").splitlines()
    )
    out["data_returns.json"] = DATA_RETURNS_PATH.read_text("utf-8")
    return out


def check_leakage(report: Report) -> None:
    texts = visible_texts()
    for name, text in texts.items():
        for pattern in EXCLUDED_PATTERNS:
            hit = re.search(pattern, text, flags=re.I)
            if hit:
                report.fail(f"{name}: enforcement-outcome wording {hit.group(0)!r}")
        for person in PERSONAL_NAMES:
            if person.casefold() in text.casefold():
                report.fail(f"{name}: names an individual ({person})")
        handle = HANDLE.search(text)
        if handle:
            report.fail(f"{name}: social-media handle {handle.group(0)!r}")
    report.count("visible texts scanned for leakage", len(texts))
    s11 = text_lines((FI_BUNDLE_DIR / "S11" / "S11.txt").read_bytes())
    entries = {
        "S11 X01": ("RAW-ESNEFT", _item_text(s11, "X01  ")),
        "S11 X02": ("RAW-STANLOW", _item_text(s11, "X02  ")),
    }
    hosp = next(
        c for c in fi_witnesses.cards() if c["persona_id"] == "hospital-estates-manager"
    )
    for block in hosp["blocks"]:
        if any(ref.get("source_id") == "RAW-ESNEFT" for ref in block["provenance"]):
            entries[f"witness {block['response_id']}"] = (
                "RAW-ESNEFT",
                block["response_text"],
            )
    for where, (raw_id, text) in entries.items():
        runs = shared_runs(text, statement_text(raw_id))
        if runs:
            report.fail(f"{where}: shares runs of four words with {raw_id}: {runs}")
        else:
            report.count("index entries without copied wording")


def _item_text(lines: list[str], anchor: str) -> str:
    (first,) = [i for i, line in enumerate(lines) if line.startswith(anchor)]
    last = first
    while last + 1 < len(lines) and lines[last + 1].startswith(" "):
        last += 1
    return " ".join(" ".join(lines[first : last + 1]).split()[1:])


def check_rows(report: Report) -> None:
    raw = (FI_ROWS_DIR / ROW_FRAGMENT).read_text("utf-8")
    sr_ids: set[str] = set()
    for path in sorted(SR_ROWS_DIR.glob("*.jsonl")):
        for line in path.read_text("utf-8").splitlines():
            row = json.loads(line)
            sr_ids.add(str(row.get("entry_id") or row.get("event_id")))
    lines = text_lines((FI_BUNDLE_DIR / "S08" / "S08.txt").read_bytes())
    for line in raw.splitlines():
        if json.dumps(json.loads(line), ensure_ascii=False, sort_keys=True) != line:
            report.fail(f"{ROW_FRAGMENT}: line is not canonical sorted-key JSON")
        row = json.loads(line)
        where = f"{ROW_FRAGMENT} {row.get('entry_id')}"
        if set(row) != CONTROL_KEYS or row["kind"] != "control":
            report.fail(f"{where}: keys/kind differ from the control row schema")
            continue
        if not RECORD_ID.match(row["entry_id"]) or row["entry_id"] in sr_ids:
            report.fail(
                f"{where}: bad ID or one already used by the system-response logs"
            )
        if (
            row["evidence_id"] != "S08"
            or row["room_id"] not in build_fi_recon.CONTROL_LOGS
        ):
            report.fail(f"{where}: evidence or room not declared")
        if not UTC_RE.match(row["index_time_utc"]):
            report.fail(f"{where}: index_time_utc {row['index_time_utc']!r}")
        expected = fi_rows.iso_z(fi_rows.utc_from_bst_hhmm(row["recorded_time"]))
        if expected != row["index_time_utc"] or row["index_uncertainty_s"] != 60.0:
            report.fail(f"{where}: index time is not the recorded minute read as BST")
        if (
            row["value_status"] not in VALUE_STATUSES
            or row["value_status"] == "framing"
        ):
            report.fail(f"{where}: value_status")
        start, end = parse_line_range(row["provenance"]["doc_lines"])
        cited = " ".join(" ".join(lines[start - 1 : end]).split())
        if row["recorded_time"] not in cited:
            report.fail(f"{where}: recorded_time not in the cited lines")
        if row["text"] != cited:
            report.fail(f"{where}: text does not restate the cited lines")
        if not row["provenance"]["sources"]:
            report.fail(f"{where}: provenance without sources")
        report.count("control rows checked")


def check_witnesses(quotes: Quotes, report: Report) -> None:
    sys.path.insert(0, str(ENV_ROOT / "src"))
    from environment.incident.matching import match_topics
    from environment.incident.witness import parse_witness_card

    sr_cards = [
        json.loads(p.read_text("utf-8"))
        for p in sorted((SR_BUNDLE_DIR / "witnesses").glob("*.json"))
    ]
    sr_personas = {c["persona_id"] for c in sr_cards}
    response_ids = {b["response_id"] for c in sr_cards for b in c["blocks"]}
    cards = fi_witnesses.cards()
    if len(cards) != 5:
        report.fail(f"expected 5 new witness cards, found {len(cards)}")
    for card in cards:
        pid = card["persona_id"]
        path = WITNESS_DIR / f"{pid}.json"
        data = path.read_bytes()
        visible = json.loads(data)
        where = path.name
        if pid in sr_personas or not NAME_ID.match(pid):
            report.fail(f"{where}: persona_id clashes with increment A or is malformed")
        if visible.get("status") != "STATUS: " + WITNESS_LABEL:
            report.fail(f"{where}: status label")
        if visible.get("evidence_id") != WITNESS_EVIDENCE_ID:
            report.fail(f"{where}: evidence_id")
        if "not known" not in visible["unknown_response"].casefold():
            report.fail(f"{where}: unknown_response must say 'not known'")
        if any("provenance" in b for b in visible["blocks"]):
            report.fail(f"{where}: visible card carries provenance")
        entry = {
            k: visible[k] for k in ("persona_id", "role", "organisation", "evidence_id")
        }
        entry["file"] = f"witnesses/{pid}.json"
        parsed = parse_witness_card(entry, data, sha256_bytes(data), where)
        topics = [block["topics"] for block in card["blocks"]]
        for index, block in enumerate(card["blocks"]):
            bwhere = f"{where} {block['response_id']}"
            if block["response_id"] in response_ids or not RECORD_ID.match(
                block["response_id"]
            ):
                report.fail(f"{bwhere}: duplicate or malformed response_id")
            response_ids.add(block["response_id"])
            text = block["response_text"]
            for value in LANDMARKS:
                if value in text or any(value in t for t in block["topics"]):
                    report.fail(f"{bwhere}: states frequency landmark {value}")
            for word in TAG_RE.findall(text):
                if word not in TAGS:
                    report.fail(f"{bwhere}: unknown tag [{word}]")
            if not block["provenance"]:
                report.fail(f"{bwhere}: no provenance")
            for ref_index, ref in enumerate(block["provenance"]):
                quotes.check(f"{bwhere} source {ref_index}", ref, report)
            check_numbers(bwhere, text, block["provenance"], [], report)
            result = match_topics(block["topics"][0], topics)
            if result.kind != "match" or result.blocks != (index,):
                report.fail(
                    f"{bwhere}: first topic {block['topics'][0]!r} -> "
                    f"{result.kind} {result.blocks}"
                )
            else:
                report.count("witness topics selecting their own block")
        if len(parsed.blocks) != len(card["blocks"]):
            report.fail(f"{where}: runtime parser block count differs")
        report.count("witness cards checked")


def check_registry(quotes: Quotes, report: Report) -> None:
    sys.path.insert(0, str(ENV_ROOT / "src"))
    from environment.incident.returns import DataReturnRegistry

    additions = json.loads(DATA_RETURNS_PATH.read_text("utf-8"))
    sr_manifest = json.loads((SR_BUNDLE_DIR / "manifest.json").read_text("utf-8"))
    sr_registry = sr_manifest["data_returns"]
    sr_keys = {(e["party"].casefold(), e["data_type"].casefold()) for e in sr_registry}
    seen: set[tuple[str, str]] = set()
    for index, entry in enumerate(additions):
        where = f"data_returns[{index}] {entry.get('party')}/{entry.get('data_type')}"
        allowed = {"party", "data_type", "status", "evidence_id", "message"}
        if not set(entry) <= allowed or not {"party", "data_type", "status"} <= set(
            entry
        ):
            report.fail(f"{where}: keys")
            continue
        key = (entry["party"].casefold(), entry["data_type"].casefold())
        if key in seen or key in sr_keys:
            report.fail(
                f"{where}: duplicate or already in the system-response registry"
            )
        seen.add(key)
        if entry["party"] not in fi_returns.PARTIES:
            report.fail(f"{where}: party not described in fi_returns.PARTIES")
        if entry["status"] == "available":
            if entry.get("evidence_id") not in ALL_DOCS:
                report.fail(f"{where}: evidence_id {entry.get('evidence_id')!r}")
        elif entry["status"] == "not_held":
            if "evidence_id" in entry or not entry.get("message"):
                report.fail(f"{where}: refusal needs a message and no evidence_id")
            basis = fi_returns.NOT_HELD_BASIS.get((entry["party"], entry["data_type"]))
            if basis is None:
                report.fail(f"{where}: no recorded basis")
            for ref_index, ref in enumerate(basis or []):
                quotes.check(f"{where} basis {ref_index}", ref, report)
        else:
            report.fail(
                f"{where}: status {entry['status']!r} (no published refusal exists)"
            )
        report.count("data-return additions checked")
    doc_ids = {d["doc_id"] for d in sr_manifest["documents"]} | set(ALL_DOCS)
    merged = DataReturnRegistry.parse(sr_registry + additions, doc_ids)
    report.count("merged registry entries", len(merged))


def run() -> Report:
    report = Report()
    check_inputs(report)
    check_fresh(report)
    check_r10(report)
    quotes = Quotes()
    check_documents(quotes, report)
    check_leakage(report)
    check_rows(report)
    check_witnesses(quotes, report)
    check_registry(quotes, report)
    return report


def main() -> int:
    report = run()
    for key, value in sorted(report.counts.items()):
        print(f"  {key}: {value}")
    if report.failures:
        print(f"FAILED ({len(report.failures)}):")
        for failure in report.failures:
            print(f"  - {failure}")
        return 1
    print("OK: full-investigation reconstruction outputs verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
