"""Verify the integrated system-response bundle: every track's checks plus global checks.

Builder-only. Track checks run each track's own verification as a subprocess:

- real: ``real/build_real.py --check`` and ``real/sync_raw.py --check`` (read ``.context``
  through ``GB_REAL_DATA_DIR``, ``GB_CATALOGUE_DIR``, ``GB_HANDOFF_DIR``);
- digitise: ``digitise/build_r05.py --check --no-qa`` (about 80 s; needs PyMuPDF, numpy and
  Pillow, so it runs under ``uv run --no-project --with ...``; ``--fast`` skips it);
- recon: ``recon/build_recon.py --check`` and ``recon/verify_recon.py``;
- integration: ``build_bundle.py`` rebuilt in memory and compared byte for byte.

Global checks (:func:`global_checks`, also run by ``tests/test_sr_bundle.py``):

- the bundle loads with the runtime catalogue (manifest v2, fail closed) and re-verifies;
- every file in the bundle is listed in the manifest with its sha256 (nothing unlisted, no
  symlinks, no hidden files, no PDF/ZIP/DOCX/HTML/image files), and the merged provenance
  pins the same hashes and the manifest hash;
- every document has provenance whose segments cover each non-blank line exactly once, with
  a known value status and a source for every non-framing segment; the text opens with the
  manifest label on its STATUS line;
- every log row and every witness block has non-empty private provenance (and nothing else
  does); rows are in (index instant, ID) order with sorted keys; record IDs are unique;
  every evidence ID exists;
- no private field (``provenance``, ``kind``, quotes, source pages) in agent-visible JSON, no
  builder path or local path in any agent-visible file;
- no landmark answer in metadata texts (titles, owners, labels, descriptions, signals, log
  notes, witness roles, card framing and every block's topics, data-return types and
  messages, file names), and the frequency landmarks appear nowhere but the R01 series.

    uv run --frozen python builder/system_response/verify_bundle.py [--fast] [--skip-tracks]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_bundle as bb  # noqa: E402

SRC_DIR = bb.ENV_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

SEGMENT_STATUSES = (*bb.VALUE_STATUSES, "derived")  # "derived": MVP R01 script segments
FORBIDDEN_SUFFIXES = (
    ".pdf",
    ".zip",
    ".docx",
    ".doc",
    ".html",
    ".htm",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".xlsx",
    ".gz",
)
# Keys that only private provenance may carry.
PRIVATE_KEYS = frozenset(
    {"provenance", "kind", "quote", "pdf_page", "printed_page", "source_id", "sources"}
)
# Text that must never reach an agent-visible file.
PRIVATE_TEXT = (
    "/Users/",
    "/home/",
    ".context",
    "builder_only",
    "GB_power_cut_handoff",
    "answer_key",
    "private/system_response",
    "builder/system_response",
)
FREQUENCY_LANDMARKS = ("48.787", "49.083", "50.001")
R01_SERIES = "R01/frequency_2019-08-09_1640-1745_BST.csv"

# Landmark answers of the scored topics (T01-T09, T12, T16, T17): numbers, instants and
# mechanism wording. Metadata identifies records; it must never state these.
_LANDMARK_NUMBERS = (
    "49.083",
    "48.787",
    "50.001",
    "48.8",
    "1878",
    "1,878",
    "1990",
    "1,990",
    "931",
    "892",
    "973",
    "737",
    "799",
    "244",
    "210",
    "187",
    "641",
    "1314",
    "1,314",
    "1338",
    "1,338",
    "219632",
    "219,632",
    "462",
    "1300",
    "1,300",
    "1500",
    "1,500",
    "560",
)
_LANDMARK_TIMES = (
    "16:52:33",
    "15:52:33",
    "16:52:34",
    "15:52:34",
    "16:52:53",
    "15:52:53",
    "16:52:59",
    "15:52:59",
    "16:53:31",
    "15:53:31",
    "16:53:49",
    "15:53:49",
    "16:53:58",
    "15:53:58",
    "16:57:16",
    "15:57:16",
    "16:54",
    "15:54",
    "16:58",
    "15:58",
    "17:16",
    "17:37",
    "16:37",
    "17:40",
)
LANDMARK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    *(
        (value, re.compile(rf"(?<![\d.,]){re.escape(value)}(?![\d]|[.,]\d)"))
        for value in (*_LANDMARK_NUMBERS, *_LANDMARK_TIMES)
    ),
    ("33 s", re.compile(r"(?<![\d.])33\s?(?:s|sec|seconds)\b")),
    ("70 ms", re.compile(r"(?<![\d.])70\s?ms\b")),
    ("74 ms", re.compile(r"(?<![\d.])74\s?ms\b")),
)
LANDMARK_PHRASES = (
    "blue phase",
    "blue-phase",
    "phase to earth",
    "phase-to-earth",
    "single-phase",
    "single phase",
    "sub-synchronous",
    "subsynchronous",
    "resonan",
    "oscillat",
    "overcurrent",
    "over-current",
    "de-load",
    "deload",
    "speed signal",
    "speed-signal",
    "speed sensor",
    "speed-sensor",
    "speed_sensor",
    "discrepanc",
    "bypass",
    "steam pressure",
    "manual shutdown",
    "manually",
    "manual trip",
    "auto shutdown",
    "auto-reclose",
    "auto reclose",
    "vector shift",
    "vector-shift",
    "rocof",
    "loss of mains",
    "root cause",
    "caused by",
    "due to",
    "because",
    "lightning strike",
    "weak grid",
    "weak network",
    "damping",
    "damped",
    "stage 1",
    "unexplained",
    "not established",
    "precursor",
    "earlier event",
    # outcome wording once used in ESW-400 / HORNSEA-ONE signal names
    "fault infeed",
    "end opens",
    "opens to clear",
    "main protection operating",
    "protection operating time",
    "voltage depression",
    "voltage dip",
)


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    counts: Counter[str] = field(default_factory=Counter)

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def count(self, key: str, n: int = 1) -> None:
        self.counts[key] += n

    @property
    def ok(self) -> bool:
        return not self.failures


# --------------------------------------------------------------------------- helpers


def load_manifest(bundle: Path) -> dict[str, Any]:
    return json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))


def bundle_files(bundle: Path) -> Iterator[Path]:
    for root, dirs, files in os.walk(bundle, followlinks=False):
        dirs.sort()
        for name in sorted(files):
            yield Path(root) / name
        for name in dirs:
            path = Path(root) / name
            if path.is_symlink():
                yield path


def manifest_files(manifest: Mapping[str, Any]) -> dict[str, str]:
    """Every file the manifest pins (bundle-relative path -> sha256)."""
    out: dict[str, str] = {}
    for doc in manifest["documents"]:
        out.update(doc["sha256"])
    for section in ("asset_logs", "control_logs", "witnesses"):
        for entry in manifest.get(section, []):
            digest = entry["sha256"]
            out[entry["file"]] = (
                digest if isinstance(digest, str) else digest[entry["file"]]
            )
    return out


def landmark_hits(text: str) -> list[str]:
    hits = [name for name, pattern in LANDMARK_PATTERNS if pattern.search(text)]
    folded = text.casefold()
    hits += [phrase for phrase in LANDMARK_PHRASES if phrase in folded]
    return hits


def metadata_texts(
    bundle: Path, manifest: Mapping[str, Any]
) -> Iterator[tuple[str, str]]:
    """(where, text) for every agent-visible metadata string."""
    for category in manifest.get("categories", []):
        yield "categories", category
    for doc in manifest["documents"]:
        where = f"document {doc['doc_id']}"
        for key in ("title", "owner", "label", "date"):
            yield f"{where} {key}", doc[key]
        for value in (*doc.get("party_aliases", []), *doc.get("keywords", [])):
            yield f"{where} alias/keyword", value
        for art in doc["artifacts"]:
            yield f"{where} artifact {art['file']}", art["file"]
            yield f"{where} artifact description", art["description"]
            if art.get("timeseries"):
                yield f"{where} timeseries", json.dumps(art["timeseries"])
    for entry in manifest.get("asset_logs", []):
        where = f"asset log {entry['asset_id']}"
        for key in (
            "asset_id",
            "title",
            "owner",
            "clock_note",
            "status",
            "source_note",
        ):
            if entry.get(key):
                yield f"{where} {key}", entry[key]
        for signal in entry["signals"]:
            yield f"{where} signal", signal
    for entry in manifest.get("control_logs", []):
        where = f"control log {entry['room_id']}"
        for key in ("room_id", "title", "owner", "clock_note", "status", "source_note"):
            if entry.get(key):
                yield f"{where} {key}", entry[key]
    for entry in manifest.get("witnesses", []):
        where = f"witness {entry['persona_id']}"
        for key in ("persona_id", "role", "organisation"):
            yield f"{where} {key}", entry[key]
        card = json.loads((bundle / entry["file"]).read_text(encoding="utf-8"))
        for key in ("status", "unknown_response"):
            if card.get(key):
                yield f"{where} card {key}", card[key]
        # Topics are shown as choices for an ambiguous question, before any evidence is
        # cited, so they name the subject of a block and never its finding.
        for block in card.get("blocks", []):
            for topic in block.get("topics", []):
                yield f"{where} topic ({block.get('response_id')})", topic
    for entry in manifest.get("data_returns", []):
        where = f"data return {entry['party']}/{entry['data_type']}"
        for key in ("party", "data_type", "message"):
            if entry.get(key):
                yield f"{where} {key}", entry[key]


def _walk_keys(obj: Any) -> Iterator[str]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from _walk_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_keys(item)


def _line_range(text: str) -> tuple[int, int]:
    match = re.fullmatch(r"L(\d+)(?:-L?(\d+))?", text.strip())
    if not match:
        raise ValueError(f"bad line range {text!r}")
    start = int(match.group(1))
    return start, int(match.group(2) or start)


# --------------------------------------------------------------------------- global checks


def check_catalogue(bundle: Path, report: Report) -> Any:
    from environment.incident.catalogue import Catalogue, CatalogueError

    try:
        catalogue = Catalogue.load(bundle)
        catalogue.verify()
    except CatalogueError as exc:
        report.fail(f"runtime catalogue refuses the bundle: {exc}")
        return None
    if not catalogue.is_v2:
        report.fail("bundle is not manifest v2")
    report.count("catalogue loads (manifest v2)")
    return catalogue


def check_files(
    bundle: Path,
    manifest: Mapping[str, Any],
    provenance: Mapping[str, Any],
    report: Report,
) -> None:
    pinned = manifest_files(manifest)
    seen: set[str] = set()
    for path in bundle_files(bundle):
        name = path.relative_to(bundle).as_posix()
        if path.is_symlink():
            report.fail(f"{name}: symlink in the bundle")
            continue
        if any(part.startswith(".") for part in Path(name).parts):
            report.fail(f"{name}: hidden file in the bundle")
        if name.lower().endswith(FORBIDDEN_SUFFIXES):
            report.fail(f"{name}: file type not allowed in the agent bundle")
        if name == "manifest.json":
            continue
        seen.add(name)
        if name not in pinned:
            report.fail(f"{name}: not listed in the manifest")
        elif bb.sha256_bytes(path.read_bytes()) != pinned[name]:
            report.fail(f"{name}: sha256 differs from the manifest")
        else:
            report.count("files hashed")
    for name in sorted(set(pinned) - seen):
        report.fail(f"{name}: listed in the manifest but missing")
    if provenance.get("files") != dict(sorted(pinned.items())):
        report.fail("private provenance 'files' differs from the manifest hashes")
    manifest_sha = bb.sha256_bytes((bundle / "manifest.json").read_bytes())
    if provenance.get("manifest_sha256") != manifest_sha:
        report.fail("private provenance pins a different manifest sha256")


def check_documents(
    bundle: Path,
    manifest: Mapping[str, Any],
    provenance: Mapping[str, Any],
    report: Report,
) -> None:
    docs = provenance.get("documents", {})
    if sorted(docs) != sorted(d["doc_id"] for d in manifest["documents"]):
        report.fail("provenance documents differ from the manifest documents")
    for doc in manifest["documents"]:
        doc_id = doc["doc_id"]
        data = (bundle / doc["text_file"]).read_bytes()
        text = data.decode("utf-8")
        status = next(
            (line for line in text.splitlines() if line.startswith("STATUS: ")), None
        )
        if status is None or not status[len("STATUS: ") :].startswith(doc["label"]):
            report.fail(f"{doc_id}: STATUS line does not open with the manifest label")
        prov = docs.get(doc_id)
        if prov is None:
            continue
        if prov.get("text_sha256") != bb.sha256_bytes(data):
            report.fail(f"{doc_id}: provenance text_sha256 is stale")
        lines = text.split("\n")[:-1] if text.endswith("\n") else text.split("\n")
        covered = [0] * (len(lines) + 1)
        for segment in prov.get("segments", []):
            try:
                start, end = _line_range(segment["lines"])
            except (KeyError, ValueError) as exc:
                report.fail(f"{doc_id}: {exc}")
                continue
            if not 1 <= start <= end <= len(lines):
                report.fail(f"{doc_id}: segment {segment['lines']} out of range")
                continue
            for number in range(start, end + 1):
                covered[number] += 1
            status_value = segment.get("value_status")
            if status_value not in SEGMENT_STATUSES:
                report.fail(
                    f"{doc_id} {segment['lines']}: value_status {status_value!r}"
                )
            if status_value != "framing" and not segment.get("sources"):
                report.fail(f"{doc_id} {segment['lines']}: no source")
            report.count("document segments")
        for number, line in enumerate(lines, 1):
            if line.strip() and covered[number] != 1:
                report.fail(
                    f"{doc_id} L{number}: covered by {covered[number]} segments (need 1)"
                )
        report.count("documents with full provenance coverage")


def check_records(
    bundle: Path,
    manifest: Mapping[str, Any],
    provenance: Mapping[str, Any],
    report: Report,
) -> dict[str, int]:
    doc_ids = {d["doc_id"] for d in manifest["documents"]}
    row_prov = provenance.get("rows", {})
    refs_seen: set[str] = set()
    per_log: dict[str, int] = {}
    for section, kind, id_key, keys in (
        ("asset_logs", "event", "event_id", bb.ASSET_ROW_KEYS),
        ("control_logs", "entry", "entry_id", bb.CONTROL_ROW_KEYS),
    ):
        for entry in manifest.get(section, []):
            file = entry["file"]
            raw = (bundle / file).read_text(encoding="utf-8")
            rows = []
            for number, line in enumerate(raw.split("\n")[:-1], 1):
                row = json.loads(line)
                where = f"{file} row {number}"
                if list(row) != sorted(row):
                    report.fail(f"{where}: keys are not sorted")
                if set(row) != set(keys):
                    report.fail(f"{where}: keys {sorted(set(row) ^ set(keys))}")
                if row.get("evidence_id") not in doc_ids:
                    report.fail(f"{where}: evidence_id {row.get('evidence_id')!r}")
                ref = f"{kind}:{row[id_key]}"
                if ref in refs_seen:
                    report.fail(f"{where}: duplicate {kind} ID {row[id_key]}")
                refs_seen.add(ref)
                private = row_prov.get(ref)
                if (
                    not private
                    or not private.get("provenance")
                    or private.get("log_file") != file
                    or private.get("evidence_id") != row["evidence_id"]
                ):
                    report.fail(f"{where}: no matching private provenance for {ref}")
                rows.append(row)
            order = [(bb.parse_utc(r["index_time_utc"]), r[id_key]) for r in rows]
            if order != sorted(order):
                report.fail(f"{file}: rows are not in (index instant, ID) order")
            per_log[file] = len(rows)
            report.count("rows with provenance", len(rows))
    orphans = sorted(set(row_prov) - refs_seen)
    if orphans:
        report.fail(f"private row provenance without a row: {orphans[:5]}")

    witness_prov = provenance.get("witnesses", {})
    response_ids: set[str] = set()
    evidence_ids = set(doc_ids)
    for entry in manifest.get("witnesses", []):
        card = json.loads((bundle / entry["file"]).read_text(encoding="utf-8"))
        private = witness_prov.get(entry["persona_id"], {}).get("blocks", {})
        evidence_ids.add(card["evidence_id"])
        if card["evidence_id"] in doc_ids:
            report.fail(f"witness {entry['persona_id']}: evidence ID is a document")
        if not str(card.get("status", "")).startswith("STATUS: "):
            report.fail(f"witness {entry['persona_id']}: no STATUS label")
        ids = [block["response_id"] for block in card["blocks"]]
        if sorted(ids) != sorted(private):
            report.fail(f"witness {entry['persona_id']}: provenance blocks differ")
        for block in card["blocks"]:
            rid = block["response_id"]
            if rid in response_ids:
                report.fail(f"duplicate response ID {rid}")
            response_ids.add(rid)
            if not private.get(rid, {}).get("sources"):
                report.fail(f"witness block {rid}: no private provenance")
            else:
                report.count("witness blocks with provenance")
    for item in manifest.get("data_returns", []):
        if item.get("evidence_id") and item["evidence_id"] not in doc_ids:
            report.fail(f"data return names unknown evidence {item['evidence_id']}")
    basis = {
        (b["party"], b["data_type"]): b
        for b in provenance.get("data_returns", {}).get("not_held_basis", [])
    }
    for item in manifest.get("data_returns", []):
        if (
            item["status"] != "available"
            and (item["party"], item["data_type"]) not in basis
        ):
            report.fail(
                f"data return {item['party']}/{item['data_type']}: no recorded basis"
            )
    return per_log


def check_private_fields(
    bundle: Path, manifest: Mapping[str, Any], report: Report
) -> None:
    for path in bundle_files(bundle):
        if path.is_symlink() or path.suffix.lower() not in (
            ".txt",
            ".csv",
            ".json",
            ".jsonl",
        ):
            continue
        name = path.relative_to(bundle).as_posix()
        text = path.read_text(encoding="utf-8")
        for marker in PRIVATE_TEXT:
            if marker in text:
                report.fail(f"{name}: contains private/builder text {marker!r}")
        is_record_file = name.startswith(("logs/", "witnesses/"))
        if name == "manifest.json" or is_record_file:
            objects = (
                [json.loads(line) for line in text.split("\n")[:-1]]
                if name.endswith(".jsonl")
                else [json.loads(text)]
            )
            for obj in objects:
                bad = sorted(set(_walk_keys(obj)) & PRIVATE_KEYS)
                if bad:
                    report.fail(f"{name}: private field(s) {bad}")
                    break
        report.count("agent-visible files scanned")


def check_landmarks(
    bundle: Path, manifest: Mapping[str, Any], report: Report
) -> list[str]:
    hits = []
    for where, text in metadata_texts(bundle, manifest):
        found = landmark_hits(text)
        report.count("metadata texts scanned")
        if found:
            hits.append(f"{where}: {', '.join(found)} in {text[:120]!r}")
    for message in hits:
        report.fail(f"landmark in metadata: {message}")
    for path in bundle_files(bundle):
        name = path.relative_to(bundle).as_posix()
        if name == R01_SERIES or path.is_symlink():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for value in FREQUENCY_LANDMARKS:
            if value in text:
                report.fail(f"{name}: states frequency landmark {value}")
    return hits


def global_checks(
    bundle: Path = bb.BUNDLE_DIR, provenance_path: Path = bb.PROVENANCE_PATH
) -> Report:
    report = Report()
    manifest = load_manifest(bundle)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    check_catalogue(bundle, report)
    check_files(bundle, manifest, provenance, report)
    check_documents(bundle, manifest, provenance, report)
    check_records(bundle, manifest, provenance, report)
    check_private_fields(bundle, manifest, report)
    check_landmarks(bundle, manifest, report)
    return report


def bundle_stats(bundle: Path = bb.BUNDLE_DIR) -> dict[str, Any]:
    manifest = load_manifest(bundle)

    def rows(file: str) -> int:
        return (bundle / file).read_text(encoding="utf-8").count("\n")

    return {
        "bundle": f"{manifest['bundle_id']} {manifest['bundle_version']}",
        "documents": len(manifest["documents"]),
        "listed_documents": sum(
            1 for d in manifest["documents"] if d.get("access") != "data_return"
        ),
        "artifacts": sum(len(d["artifacts"]) for d in manifest["documents"]),
        "asset_logs": {e["asset_id"]: rows(e["file"]) for e in manifest["asset_logs"]},
        "control_logs": {
            e["room_id"]: rows(e["file"]) for e in manifest["control_logs"]
        },
        "witnesses": {
            e["persona_id"]: len(
                json.loads((bundle / e["file"]).read_text(encoding="utf-8"))["blocks"]
            )
            for e in manifest["witnesses"]
        },
        "data_returns": dict(Counter(e["status"] for e in manifest["data_returns"])),
    }


# --------------------------------------------------------------------------- track checks


def track_commands(fast: bool) -> list[tuple[str, list[str]]]:
    py = [sys.executable]
    sr = "builder/system_response"
    commands = [
        ("real build --check", [*py, f"{sr}/real/build_real.py", "--check"]),
        ("real raw mirror --check", [*py, f"{sr}/real/sync_raw.py", "--check"]),
        ("recon build --check", [*py, f"{sr}/recon/build_recon.py", "--check"]),
        ("recon verify", [*py, f"{sr}/recon/verify_recon.py"]),
    ]
    if not fast:
        commands.append(
            (
                "digitise build --check",
                [
                    "uv",
                    "run",
                    "--no-project",
                    "--with",
                    "pymupdf",
                    "--with",
                    "numpy",
                    "--with",
                    "pillow",
                    "python",
                    f"{sr}/digitise/build_r05.py",
                    "--check",
                    "--no-qa",
                ],
            )
        )
    return commands


def run_track_checks(fast: bool, report: Report) -> None:
    for name, command in track_commands(fast):
        result = subprocess.run(
            command, cwd=bb.ENV_ROOT, capture_output=True, text=True, check=False
        )
        tail = (result.stdout + result.stderr).strip().splitlines()[-1:]
        status = (
            "ok" if result.returncode == 0 else f"FAILED (exit {result.returncode})"
        )
        print(f"  track check {name}: {status} {tail[0] if tail else ''}")
        if result.returncode != 0:
            report.fail(f"track check {name} failed")
        else:
            report.count("track checks passed")
    if fast:
        print("  track check digitise build --check: skipped (--fast)")


def check_rebuild(report: Report) -> None:
    try:
        outputs = bb.build()
    except bb.BuildError as exc:
        report.fail(f"integration build fails: {exc}")
        return
    for path, data in outputs.items():
        if not path.is_file() or path.read_bytes() != data:
            report.fail(f"{bb.rel(path)} differs from a fresh integration build")
    for path in bb.owned_stale_files(outputs):
        report.fail(f"{bb.rel(path)} would not be written by a fresh build")
    if outputs != bb.build():
        report.fail("two integration builds differ")
    report.count("integration outputs identical to a fresh build", len(outputs))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--fast", action="store_true", help="skip the slow digitise rebuild check"
    )
    parser.add_argument(
        "--skip-tracks", action="store_true", help="run only the integration checks"
    )
    args = parser.parse_args(argv)
    report = Report()
    if not args.skip_tracks:
        run_track_checks(args.fast, report)
    check_rebuild(report)
    glob = global_checks()
    report.failures += glob.failures
    report.counts.update(glob.counts)
    for key, value in sorted(report.counts.items()):
        print(f"  {key}: {value}")
    print(json.dumps(bundle_stats(), indent=1, ensure_ascii=False))
    if report.failures:
        for message in report.failures:
            print(f"FAIL: {message}")
        print(f"{len(report.failures)} problem(s)")
        return 1
    print("OK: system-response bundle verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
