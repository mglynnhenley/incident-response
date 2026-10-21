"""Verify the integrated full-investigation bundle: every track's checks plus global checks.

Builder-only. Track checks run each track's own verification as a subprocess (they read
``.context`` through ``GB_REAL_DATA_DIR``, ``GB_CATALOGUE_DIR``, ``GB_HANDOFF_DIR`` and
``GB_TEXT_DIR``):

- increment A: ``builder/system_response/build_bundle.py --check`` (the frozen source of
  every copied file is itself consistent);
- real: ``real/fi_build_real.py --check`` and ``real/fi_sync_raw.py --check``;
- recon: ``recon/build_fi_recon.py --check`` and ``recon/verify_fi_recon.py``;
- integration: the recorded basis quotes of this step (the real-data sourcing log) and
  ``build_bundle.py`` rebuilt in memory and compared byte for byte.

Global checks (:func:`global_checks`, also run by ``tests/test_fi_bundle.py``; no
``.context`` needed):

- increment A's global checks, applied to this bundle (``builder/system_response/
  verify_bundle.py``): the runtime catalogue loads and re-verifies the bundle; every file
  is listed with its sha256 (no unlisted, hidden, symlinked, PDF/HTML/image/archive
  files) and the merged provenance pins the same hashes; every document's provenance
  covers each non-blank line exactly once; every log row and witness block has private
  provenance; record IDs are unique; every not-held return has a recorded basis;
- no private field or builder/local path in any agent-visible file (both increments'
  private and builder paths, the builder's input variables);
- no landmark answer in metadata (titles, owners, labels, descriptions, aliases,
  keywords, signals, log notes, witness roles and topics, data-return types and
  messages, file names): increment A's landmarks plus those of T04.02, T10, T11, T14 and
  T15, and the frequency landmarks nowhere but the R01 series;
- decisions 50-51 in every agent-visible file: no enforcement-settlement wording, no
  social-media handle except the ESO's organisational account printed in ESO Table 8,
  no personal name of the sources;
- inheritance: increment A's documents (R10 apart), files, manifest entries, log rows,
  witness cards and data returns are present unchanged with the same IDs, and the full
  R10 keeps A's R10 (lines and provenance segments) as its prefix.

    uv run --frozen python builder/full_investigation/verify_bundle.py [--skip-tracks]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

FI_BUILDER_DIR = Path(__file__).resolve().parent
ENV_ROOT = FI_BUILDER_DIR.parents[1]
SR_BUILDER_DIR = ENV_ROOT / "builder" / "system_response"


def _load_module(name: str, path: Path) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fb = _load_module("fi_build_bundle", FI_BUILDER_DIR / "build_bundle.py")
# Increment A's verifier, read-only (it imports A's build_bundle by its own name).
srv = _load_module("sr_verify_bundle", SR_BUILDER_DIR / "verify_bundle.py")

SRC_DIR = ENV_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

Report = srv.Report
bundle_files = srv.bundle_files
manifest_files = srv.manifest_files
load_manifest = srv.load_manifest

PRIVATE_TEXT = (
    *srv.PRIVATE_TEXT,
    "private/full_investigation",
    "builder/full_investigation",
    "provenance_real",
    "provenance_recon",
    "GB_REAL_DATA_DIR",
    "GB_HANDOFF_DIR",
    "GB_CATALOGUE_DIR",
    "GB_TEXT_DIR",
    "consequences/raw",
)
R01_SERIES = srv.R01_SERIES
FREQUENCY_LANDMARKS = srv.FREQUENCY_LANDMARKS

# Landmark answers of increment B's topics (T04.02 rail threshold, T10 rail impact, T11
# essential services, T14 compliance, T15 communications): numbers, instants and finding
# wording. Metadata identifies records and names subjects; it must never state these.
_FI_LANDMARK_NUMBERS = (
    "3.25",
    "3.27",
    "371",
    "14,428",
    "14428",
    "39,568",
    "39568",
)
_FI_LANDMARK_TIMES = (
    "17:51",
    "16:51",
    "18:00",
    "17:18",
    "16:18",
    "16:20",
    "17:54:44",
    "16:54:44",
    "18:27",
    "17:27",
    "17:41",
    "16:41",
)
FI_LANDMARK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    *(
        (value, re.compile(rf"(?<![\d.,]){re.escape(value)}(?![\d]|[.,]\d)"))
        for value in (*_FI_LANDMARK_NUMBERS, *_FI_LANDMARK_TIMES)
    ),
    ("200 ms", re.compile(r"(?<![\d.])200\s?(?:ms|milliseconds)\b")),
    ("lock-out count", re.compile(r"\b(?:29|31|22|23|30)\s+(?:units|trains)\b", re.I)),
)
FI_LANDMARK_PHRASES = (
    # T10: the lock-out distinction and its recovery behaviour
    "temporary lock",
    "permanent lock",
    "temporary and permanent",
    "locked out",
    "trapped",
    "stranded",
    # T11: hospital and airport mechanisms
    "own protection",
    "own system",
    # T14: compliance findings
    "without instruction",
    "without an instruction",
    "early reconnection",
    "breach",
    "non-complian",
    "noncomplian",
    "did not comply",
    "failed to comply",
    # T15 / decision 50: outcomes
    "enforcement",
    "voluntary payment",
    "redress",
    "penalt",
)

# Decision 50: Ofgem's January 2020 enforcement settlements (voluntary payments to the
# redress scheme), in every agent-visible file. "Settlement" in Elexon's sense (periods,
# dates, runs, system prices) is not a settlement of enforcement. ORR's own conclusion
# that it found nothing warranting enforcement action (S08) is evidence, not an outcome
# of the excluded settlements, so the word "enforcement" alone is checked only in
# metadata (FI_LANDMARK_PHRASES).
ENFORCEMENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"£"),
    re.compile(r"\b(?:4\.5|10\.5|1\.5|1\.45|0\.05)\s?m(?:illion)?\b", re.I),
    re.compile(r"voluntary (?:payment|redress)", re.I),
    re.compile(r"redress scheme", re.I),
    re.compile(r"\bpenalt", re.I),
    re.compile(r"\bfined\b", re.I),
    re.compile(
        r"\bsettlements?\b(?!\s*(?:/|periods?\b|system\b|dates?\b|data\b|runs?\b))",
        re.I,
    ),
)
# Decision 51: no handles, no personal names. The only account handle allowed is the
# ESO's organisational account as printed in ESO Table 8 (R09).
HANDLE = re.compile(r"(?<![\w.])@[A-Za-z_][A-Za-z0-9_]{1,}")
ALLOWED_HANDLES = frozenset({"@NG_ESO"})
HANDLE_SUBSTRINGS = (
    "UKPowerNetworks",
    "wpduk",
    "ElectricityNW",
    "TLRailUK",
    "nationalrailenq",
    "NCLairport",
    "andrealeadsom",
    "beisgovuk",
    "public_user",
    "twitter.com/",
    "x.com/",
)
PERSONAL_NAMES = (
    "Julian Leslie",
    "Kwasi Kwarteng",
    "Kwarteng",
    "Andrea Leadsom",
    "Leadsom",
    "Jonathan Brearley",
    "Neill Moloney",
    "Moloney",
    "Simon Wilde",
    "Bousso",
    "Fenton",
    "MacIver",
    "Aaron",
    "Fiona",
)
# Place names that contain a listed surname (Network Rail STANOX locations in R11).
_PLACE_PREFIXES = {"Fenton": "church "}
_NAME_PATTERNS = tuple(
    (
        name,
        re.compile(
            (
                rf"(?<!{re.escape(_PLACE_PREFIXES[name])})"
                if name in _PLACE_PREFIXES
                else ""
            )
            + rf"\b{re.escape(name)}\b",
            re.I,
        ),
    )
    for name in PERSONAL_NAMES
)
TEXT_SUFFIXES = (".txt", ".csv", ".json", ".jsonl")


# --------------------------------------------------------------------------- helpers


def landmark_hits(text: str) -> list[str]:
    """Increment A's landmark hits plus increment B's."""
    hits = srv.landmark_hits(text)
    hits += [name for name, pattern in FI_LANDMARK_PATTERNS if pattern.search(text)]
    folded = text.casefold()
    hits += [phrase for phrase in FI_LANDMARK_PHRASES if phrase in folded]
    return hits


def metadata_texts(
    bundle: Path, manifest: Mapping[str, Any]
) -> Iterator[tuple[str, str]]:
    return srv.metadata_texts(bundle, manifest)


def visible_texts(bundle: Path) -> Iterator[tuple[str, str]]:
    for path in bundle_files(bundle):
        if path.is_symlink() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        yield path.relative_to(bundle).as_posix(), path.read_text(encoding="utf-8")


def enforcement_hits(text: str) -> list[str]:
    return [m.group(0) for p in ENFORCEMENT_PATTERNS for m in p.finditer(text)]


def handle_hits(text: str) -> list[str]:
    hits = sorted(set(HANDLE.findall(text)) - ALLOWED_HANDLES)
    hits += [s for s in HANDLE_SUBSTRINGS if s in text]
    return hits


def name_hits(text: str) -> list[str]:
    return [name for name, pattern in _NAME_PATTERNS if pattern.search(text)]


# --------------------------------------------------------------------------- global checks


def check_private_fields(bundle: Path, report: Report) -> None:
    for name, text in visible_texts(bundle):
        for marker in PRIVATE_TEXT:
            if marker in text:
                report.fail(f"{name}: contains private/builder text {marker!r}")
        if name == "manifest.json" or name.startswith(("logs/", "witnesses/")):
            objects = (
                [json.loads(line) for line in text.split("\n")[:-1]]
                if name.endswith(".jsonl")
                else [json.loads(text)]
            )
            for obj in objects:
                bad = sorted(set(srv._walk_keys(obj)) & srv.PRIVATE_KEYS)
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
    for name, text in visible_texts(bundle):
        if name == R01_SERIES:
            continue
        for value in FREQUENCY_LANDMARKS:
            if value in text:
                report.fail(f"{name}: states frequency landmark {value}")
    return hits


def check_exclusions(bundle: Path, report: Report) -> None:
    """Decisions 50 and 51 over every agent-visible file."""
    for name, text in visible_texts(bundle):
        found = enforcement_hits(text)
        if found:
            report.fail(f"{name}: enforcement-settlement wording {sorted(set(found))}")
        handles = handle_hits(text)
        if handles:
            report.fail(f"{name}: social-media handle(s) {handles}")
        names = name_hits(text)
        if names:
            report.fail(f"{name}: personal name(s) {names}")
        report.count("files scanned for exclusions")


NOT_HELD_PREFIX = "Not held in this evidence pack: "
# A not-held answer says the item was not obtained, plus its recorded basis; it never
# claims that a record does not exist or was never published (increment A's rule).
NONEXISTENCE_CLAIMS = (
    "were not published",
    "was not published",
    "is not published",
    "is published",
    "does not exist",
    "do not exist",
    "never existed",
    "no such record",
)


def check_return_wording(manifest: Mapping[str, Any], report: Report) -> None:
    for entry in manifest["data_returns"]:
        if entry["status"] == "available":
            continue
        where = f"data return {entry['party']}/{entry['data_type']}"
        message = entry.get("message", "")
        if not message.startswith(NOT_HELD_PREFIX):
            report.fail(f"{where}: message does not open with {NOT_HELD_PREFIX!r}")
        claims = [c for c in NONEXISTENCE_CLAIMS if c in message.casefold()]
        if claims:
            report.fail(f"{where}: message claims non-existence {claims}")
        report.count("not-held messages checked")


def check_leakage_detectors(provenance: Mapping[str, Any], report: Report) -> None:
    """The private detectors exist and match the excluded passages they describe."""
    detectors = provenance.get("leakage_detectors", {})
    patterns = [re.compile(p, re.I) for p in detectors.get("detector_patterns", [])]
    passages = detectors.get("recon_passages", [])
    if not patterns or not passages or not detectors.get("leakage_markers"):
        report.fail("private provenance has no enforcement-outcome leakage detectors")
        return
    for passage in passages:
        if not any(p.search(passage["quote"]) for p in patterns):
            report.fail(
                f"no detector matches excluded passage {passage['quote'][:60]!r}"
            )
    for marker in detectors["leakage_markers"]:
        if not enforcement_hits(marker):
            report.fail(f"leakage marker {marker!r} escapes the visible-file scan")
    report.count("leakage detectors checked", len(passages))


def _rows(bundle: Path, file: str) -> list[dict[str, Any]]:
    text = (bundle / file).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.split("\n")[:-1]]


def check_inheritance(
    bundle: Path,
    manifest: Mapping[str, Any],
    provenance: Mapping[str, Any],
    report: Report,
    sr_bundle: Path = fb.SR_BUNDLE_DIR,
    sr_provenance_path: Path = fb.SR_PROVENANCE_PATH,
) -> None:
    """Increment A's evidence is present unchanged, with the same IDs."""
    sr_manifest = load_manifest(sr_bundle)
    sr_provenance = json.loads(sr_provenance_path.read_text(encoding="utf-8"))
    docs = {d["doc_id"]: d for d in manifest["documents"]}
    if manifest["categories"][: len(sr_manifest["categories"])] != list(
        sr_manifest["categories"]
    ):
        report.fail("increment A's categories are not kept in order")
    for doc in sr_manifest["documents"]:
        doc_id = doc["doc_id"]
        mine = docs.get(doc_id)
        if mine is None:
            report.fail(f"increment A document {doc_id} is missing")
            continue
        if doc_id in fb.REPLACED:
            sr_text = (sr_bundle / doc["text_file"]).read_bytes()
            fi_text = (bundle / mine["text_file"]).read_bytes()
            if not fi_text.startswith(sr_text) or mine["text_file"] != doc["text_file"]:
                report.fail(f"{doc_id}: the full edition does not keep A's text")
            old = sr_provenance["documents"][doc_id]["segments"]
            new = provenance["documents"][doc_id]["segments"]
            if new[: len(old)] != old:
                report.fail(f"{doc_id}: A's provenance segments are not kept")
            for key in ("category", "label", "date", "text_file"):
                if mine[key] != doc[key]:
                    report.fail(f"{doc_id}: {key} differs from increment A")
            report.count("replaced documents keeping A's prefix")
            continue
        if mine != doc:
            report.fail(f"{doc_id}: manifest entry differs from increment A")
        for name, digest in doc["sha256"].items():
            path = bundle / name
            if (
                not path.is_file()
                or path.read_bytes() != (sr_bundle / name).read_bytes()
            ):
                report.fail(f"{name}: not a byte-identical copy of increment A's file")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                report.fail(f"{name}: sha256 differs from increment A's manifest")
            else:
                report.count("increment A files copied unchanged")
        if provenance["documents"].get(doc_id, {}).get("segments") != sr_provenance[
            "documents"
        ][doc_id].get("segments"):
            report.fail(f"{doc_id}: provenance segments differ from increment A")
    for section, id_key, ref_kind, record_key in (
        ("asset_logs", "asset_id", "event", "event_id"),
        ("control_logs", "room_id", "entry", "entry_id"),
    ):
        mine = {e[id_key]: e for e in manifest[section]}
        for entry in sr_manifest[section]:
            log = mine.get(entry[id_key])
            if log is None or log["file"] != entry["file"]:
                report.fail(f"increment A log {entry[id_key]} is missing")
                continue
            ours = _rows(bundle, log["file"])
            theirs = _rows(sr_bundle, entry["file"])
            old_ids = set(entry["evidence_ids"])
            if [r for r in ours if r["evidence_id"] in old_ids] != theirs:
                report.fail(f"{entry['file']}: increment A rows changed or reordered")
            else:
                report.count("increment A log rows kept", len(theirs))
            if not set(entry["signals"] if "signals" in entry else []) <= set(
                log.get("signals", [])
            ):
                report.fail(f"{entry['file']}: increment A signals dropped")
            for row in theirs:
                ref = f"{ref_kind}:{row[record_key]}"
                a_prov = sr_provenance["rows"][ref]["provenance"]
                if provenance["rows"].get(ref, {}).get("provenance") != a_prov:
                    report.fail(f"{ref}: provenance differs from increment A")
    witnesses = {w["persona_id"]: w for w in manifest["witnesses"]}
    for entry in sr_manifest["witnesses"]:
        if witnesses.get(entry["persona_id"]) != entry:
            report.fail(f"witness {entry['persona_id']}: entry differs from A")
        elif (bundle / entry["file"]).read_bytes() != (
            sr_bundle / entry["file"]
        ).read_bytes():
            report.fail(f"witness {entry['persona_id']}: card differs from A")
        else:
            report.count("increment A witness cards copied unchanged")
        a_blocks = sr_provenance["witnesses"][entry["persona_id"]]["blocks"]
        fi_blocks = provenance["witnesses"].get(entry["persona_id"], {}).get("blocks")
        if fi_blocks != a_blocks:
            report.fail(f"witness {entry['persona_id']}: block provenance differs")
    returns = {(e["party"], e["data_type"]): e for e in manifest["data_returns"]}
    for entry in sr_manifest["data_returns"]:
        if returns.get((entry["party"], entry["data_type"])) != entry:
            report.fail(f"data return {entry['party']}/{entry['data_type']} changed")
        else:
            report.count("increment A data returns kept")


def global_checks(
    bundle: Path = fb.BUNDLE_DIR, provenance_path: Path = fb.PROVENANCE_PATH
) -> Report:
    report = Report()
    manifest = load_manifest(bundle)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    srv.check_catalogue(bundle, report)
    srv.check_files(bundle, manifest, provenance, report)
    srv.check_documents(bundle, manifest, provenance, report)
    srv.check_records(bundle, manifest, provenance, report)
    check_private_fields(bundle, report)
    check_landmarks(bundle, manifest, report)
    check_exclusions(bundle, report)
    check_return_wording(manifest, report)
    check_leakage_detectors(provenance, report)
    check_inheritance(bundle, manifest, provenance, report)
    return report


def bundle_stats(bundle: Path = fb.BUNDLE_DIR) -> dict[str, Any]:
    stats = srv.bundle_stats(bundle)
    manifest = load_manifest(bundle)
    stats["categories"] = {
        category: [
            d["doc_id"] for d in manifest["documents"] if d["category"] == category
        ]
        for category in manifest["categories"]
    }
    stats["witness_blocks"] = sum(stats["witnesses"].values())
    stats["log_rows"] = sum(stats["asset_logs"].values()) + sum(
        stats["control_logs"].values()
    )
    return stats


# --------------------------------------------------------------------------- track checks


def real_data_dir() -> Path:
    default = ENV_ROOT.parent / ".context" / "real_data"
    return Path(os.environ.get("GB_REAL_DATA_DIR", default))


def check_basis_quotes(report: Report) -> None:
    """The integration step's own recorded bases quote the real-data sourcing log."""
    log = real_data_dir() / fb.REAL_DATA_LOG["file"]
    if not log.is_file():
        print(f"  basis quotes: skipped ({log} not available)")
        return
    data = log.read_bytes()
    if hashlib.sha256(data).hexdigest() != fb.REAL_DATA_LOG["sha256"]:
        report.fail(f"{log.name}: sha256 differs from the pinned sourcing log")
    text = " ".join(data.decode("utf-8").replace("*", "").split())
    for item in fb.EXTRA_NOT_HELD_BASIS:
        for ref in item["basis"]:
            if " ".join(ref["quote"].split()) not in text:
                report.fail(f"basis quote not in {log.name}: {ref['quote'][:60]!r}")
            else:
                report.count("integration basis quotes verified")


def track_commands() -> list[tuple[str, list[str]]]:
    py = [sys.executable]
    fi = "builder/full_investigation"
    return [
        (
            "system-response integration --check",
            [*py, "builder/system_response/build_bundle.py", "--check"],
        ),
        ("real build --check", [*py, f"{fi}/real/fi_build_real.py", "--check"]),
        ("real raw mirror --check", [*py, f"{fi}/real/fi_sync_raw.py", "--check"]),
        ("recon build --check", [*py, f"{fi}/recon/build_fi_recon.py", "--check"]),
        ("recon verify", [*py, f"{fi}/recon/verify_fi_recon.py"]),
    ]


def run_track_checks(report: Report) -> None:
    for name, command in track_commands():
        result = subprocess.run(
            command, cwd=ENV_ROOT, capture_output=True, text=True, check=False
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
    check_basis_quotes(report)


def check_rebuild(report: Report) -> None:
    try:
        outputs = fb.build()
    except (fb.BuildError, fb.sr.BuildError) as exc:
        report.fail(f"integration build fails: {exc}")
        return
    for path, data in outputs.items():
        if not path.is_file() or path.read_bytes() != data:
            report.fail(f"{fb.rel(path)} differs from a fresh integration build")
    for path in fb.owned_stale_files(outputs):
        report.fail(f"{fb.rel(path)} would not be written by a fresh build")
    if outputs != fb.build():
        report.fail("two integration builds differ")
    report.count("integration outputs identical to a fresh build", len(outputs))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--skip-tracks", action="store_true", help="run only the integration checks"
    )
    args = parser.parse_args(argv)
    report = Report()
    if not args.skip_tracks:
        run_track_checks(report)
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
    print("OK: full-investigation bundle verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
