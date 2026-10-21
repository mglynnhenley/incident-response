"""Integrate the full-investigation evidence bundle (manifest v2) from its inputs.

Builder-only and deterministic: the same inputs give byte-identical outputs (no clock, no
randomness, sorted iteration everywhere). Like increment A's integration step it reads no
``.context`` input, only files that already exist in the environment:

- increment A's frozen bundle ``bundles/system_response`` (manifest, documents, logs,
  witness cards) and its merged private provenance ``private/system_response/
  provenance.json``. Every file is hash-checked against that manifest, and the
  provenance must pin the same manifest and file hashes;
- the real-data track: manifest fragment ``real/documents_real.json`` (R09, R11, R12),
  row fragments ``rows/real_*.jsonl`` and ``private/full_investigation/
  provenance_real.json``;
- the reconstruction track: manifest fragment ``recon/documents.json`` (S08, S10, S11,
  the full-investigation R10, five witness cards, the GTR-FLEET-CONTROL room), row
  fragment ``rows/recon_s08.jsonl``, the data-return additions ``rows/data_returns.json``,
  the agent-visible cards it wrote to ``bundles/full_investigation/witnesses/`` and
  ``private/full_investigation/provenance_recon.json``.

It writes:

- byte-identical copies of increment A's documents (same IDs, same files; R10 is replaced
  by the reconstruction track's edition, whose lines 1-133 are A's R10 unchanged) and of
  A's five witness cards;
- ``logs/assets/<asset_id>.jsonl`` and ``logs/control/<room_id>.jsonl``: A's rows
  unchanged plus the new rows (REMIT messages on HORNSEA-ONE and LITTLE-BARFORD; the new
  rooms ESO-COMMS, NETWORK-RAIL-CONTROL and GTR-FLEET-CONTROL), keys sorted, rows
  stable-sorted by (index instant, record ID) exactly as increment A, so a log without
  new rows is byte-identical to A's;
- ``manifest.json``: manifest v2 with A's entries unchanged except where this bundle adds
  records (log notes, signals, statuses), plus the new documents, rooms, witnesses and
  data returns (neutral titles; categories, aliases and log metadata owned here);
- ``private/full_investigation/provenance.json``: the merged provenance (A's documents,
  rows, witness blocks, sources and data-return bases carried over; the tracks' parts
  merged; leakage detectors for decision 50; every file hash).

Any inconsistency (stale hash, unknown evidence ID, duplicate record ID, missing
provenance, a copied file that differs from A's manifest) stops the build.

    uv run --frozen python builder/full_investigation/build_bundle.py          # write
    uv run --frozen python builder/full_investigation/build_bundle.py --check  # compare
    uv run --frozen python builder/full_investigation/verify_bundle.py         # all checks
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

FI_BUILDER_DIR = Path(__file__).resolve().parent
ENV_ROOT = FI_BUILDER_DIR.parents[1]
SR_BUILDER_DIR = ENV_ROOT / "builder" / "system_response"


def _load_module(name: str, path: Path) -> ModuleType:
    """Import ``path`` under ``name`` (both builders have a ``build_bundle.py``)."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Increment A's integration step, read-only: row schemas, value statuses, serialisation
# and the log-note format, so rows copied from A serialise to exactly A's bytes.
sr = _load_module("sr_build_bundle", SR_BUILDER_DIR / "build_bundle.py")

INCIDENT_DIR = ENV_ROOT / "src" / "environment" / "incident"
BUNDLE_DIR = INCIDENT_DIR / "bundles" / "full_investigation"
PRIVATE_DIR = INCIDENT_DIR / "private" / "full_investigation"
SR_BUNDLE_DIR = INCIDENT_DIR / "bundles" / "system_response"
SR_PROVENANCE_PATH = INCIDENT_DIR / "private" / "system_response" / "provenance.json"
ROWS_DIR = FI_BUILDER_DIR / "rows"
DATA_RETURNS_FRAGMENT = ROWS_DIR / "data_returns.json"
MANIFEST_PATH = BUNDLE_DIR / "manifest.json"
PROVENANCE_PATH = PRIVATE_DIR / "provenance.json"
ASSET_LOG_DIR = sr.ASSET_LOG_DIR
CONTROL_LOG_DIR = sr.CONTROL_LOG_DIR
WITNESS_DIR = sr.WITNESS_DIR

GENERATED_BY = "builder/full_investigation/build_bundle.py"
VERIFIED_BY = "builder/full_investigation/verify_bundle.py"
BUNDLE_ID = "gb-2019-08-09-full-investigation"
BUNDLE_VERSION = "0.1.0"
SR_TRACK = "system_response"  # provenance track prefix of everything copied from A

FRAGMENTS: dict[str, Path] = {
    "real": FI_BUILDER_DIR / "real" / "documents_real.json",
    "recon": FI_BUILDER_DIR / "recon" / "documents.json",
}
PROVENANCE_PARTS: dict[str, Path] = {
    "real": PRIVATE_DIR / "provenance_real.json",
    "recon": PRIVATE_DIR / "provenance_recon.json",
}
# Row fragment -> owning track. Every *.jsonl in rows/ must be listed here.
ROW_FRAGMENTS: dict[str, str] = {
    "real_r09_asset.jsonl": "real",
    "real_r09_control.jsonl": "real",
    "real_r11_control.jsonl": "real",
    "recon_s08.jsonl": "recon",
}
# Increment A documents replaced in this bundle by a track's edition (same ID).
REPLACED: dict[str, str] = {"R10": "recon"}
# Increment A's data-return-only documents; no new document is data-return-only.
DATA_RETURN_ONLY = ("S05", "S06")

# --------------------------------------------------------------------------- catalogue metadata

# Increment A's categories (in A's order) are kept; the tracks' proposals are merged into
# four neutral categories (rail_records -> transport_records; essential_service_records
# and essential_services_records -> essential_services).
NEW_CATEGORY_ORDER = (
    "transport_records",
    "essential_services",
    "communications_records",
    "compliance_records",
)
NEW_CATEGORIES: dict[str, str] = {
    "R09": "communications_records",
    "R11": "transport_records",
    "R12": "essential_services",
    "S08": "transport_records",
    "S10": "compliance_records",
    "S11": "essential_services",
}
# Free-text request help (request_document party and description matching); never
# answers. Proposals of the tracks, reviewed for neutrality.
PARTY_ALIASES: dict[str, tuple[str, ...]] = {
    "R09": ("system operator", "National Grid ESO", "Elexon", "DNO", "regulator"),
    "R10": ("system operator", "regulator"),
    "R11": (
        "Network Rail",
        "rail",
        "ORR",
        "Office of Rail and Road",
        "train operator",
    ),
    "R12": ("hospital", "airport", "essential services", "NHS trust"),
    "S08": ("train operator", "GTR", "rail regulator"),
    "S10": ("system operator", "regulator"),
    "S11": ("system operator", "regulator", "E3C"),
}
# No document carries manifest ``keywords``: the agent never sees them, and the task's
# request_document description (increment A's, frozen) says a described request is matched
# on the title. Without keywords a described request matches only what the agent can read
# in the catalogue (ID and title).
KEYWORDS: dict[str, tuple[str, ...]] = {}

# Log metadata owned here. Clock notes describe how times are written, never what
# happened; ``real_terms`` appends the licence/attribution sentence taken from the real
# track's source records (only when every cited source states the same terms).
ASSET_LOG_UPDATES: dict[str, dict[str, Any]] = {
    "HORNSEA-ONE": {
        "title": "Hornsea One offshore wind farm: event log entries, BM unit data, "
        "REMIT messages and chart readings",
        "owner": "Ørsted (event log); Elexon (BM unit data; publication of the "
        "participant's REMIT messages); National Grid ESO (published report charts)",
        "new": {
            "R09": {
                "source": "Elexon REMIT unavailability messages, every revision held "
                "(real extracts; see R09); message content is written by the market "
                "participant.",
                "real_terms": True,
            },
        },
    },
    "LITTLE-BARFORD": {
        "title": "Little Barford power station: sequence-of-events entries, BM unit "
        "data and REMIT messages",
        "owner": "RWE Generation (sequence of events); Elexon (BM unit data; "
        "publication of the participant's REMIT messages)",
        "new": {
            "R09": {
                "source": "Elexon REMIT unavailability messages, every revision held "
                "(real extracts; see R09); message content is written by the market "
                "participant.",
                "real_terms": True,
            },
        },
    },
}
NEW_CONTROL_LOGS: dict[str, dict[str, Any]] = {
    "ESO-COMMS": {
        "title": "ESO communications: contacts with government and the regulator, "
        "media statements and public posts (published accounts and public records)",
        "owner": "National Grid ESO (published reports and public statements); E3C "
        "(reports)",
        "new": {
            "R09": {
                "source": "rows restate R09's timed ESO communications: contacts and "
                "statements in the published accounts (ESO technical report and "
                "appendices, E3C reports) and ESO public posts and web statements "
                "(gists written for this record; no post or statement text).",
                "real_terms": False,
            },
        },
    },
    "GTR-FLEET-CONTROL": {
        "title": "GTR fleet control: technical-review entries with a printed clock time",
        "owner": "Govia Thameslink Railway (technical review dated 3 September 2019)",
        "new": {"S08": {}},
    },
    "NETWORK-RAIL-CONTROL": {
        "title": "Network Rail: delay-attribution incident records (TRUST), 9 August "
        "2019",
        "owner": "Network Rail (historic delay attribution data)",
        "new": {
            "R11": {
                "source": "one entry per selected Network Rail incident, with its "
                "incident-level columns as published (real extracts; see R11).",
                "real_terms": True,
            },
        },
    },
}
# The tracks' data-return proposals are adopted except for these messages: a not-held
# answer says only that the item is not held in this pack and was not obtained, plus
# its recorded basis (increment A's rule), never that it does not exist or was never
# published, and states no finding (verify_bundle.py checks both).
DATA_RETURN_MESSAGES: dict[tuple[str, str], str] = {
    (
        "ESO",
        "control_room_communications_log",
    ): "Not held in this evidence pack: no ESO control-room message log or call "
    "recording was obtained; the available records are the published accounts of the "
    "ESO's communications.",
    # The recon proposal also restated Ofgem's cause of the EPN/SPN reconnections and
    # singled those areas out (a T14 finding in metadata); the basis is unchanged.
    (
        "UKPN",
        "reconnection_switching_records",
    ): "Not held in this evidence pack: no UK Power Networks switching or "
    "operational-system record for 9 August 2019 was obtained (its open data portal "
    "refused access).",
}
# Recorded bases for not-held answers proposed without one (checked against the
# real-data sourcing log by verify_bundle.py when GB_REAL_DATA_DIR is available).
REAL_DATA_LOG = {
    "source_id": "REAL-DATA-LOG",
    "file": "REAL_DATA.md",
    "root": "GB_REAL_DATA_DIR",
    "sha256": "37b29516d91ac447b5ed2b8f3bd7928add63a4bf7adb8437cd6aacdb6d291824",
    "title": "Real-data sourcing log (builder-only)",
}
EXTRA_NOT_HELD_BASIS: list[dict[str, Any]] = [
    {
        "party": "ESO",
        "data_type": "control_room_communications_log",
        "basis": [
            {
                "source_id": "REAL-DATA-LOG",
                "file": "REAL_DATA.md",
                "section": "4. Per-topic real data, T15 communications (gap list)",
                "quote": "Gap: tweet text for Newcastle Airport; ESO control-room "
                "messages; SYSWARN not in Insights for 2019.",
            }
        ],
        "track": "integration",
    }
]
# The real track's party descriptions for its proposals (the recon fragment describes
# the others); kept in private provenance only.
REAL_PARTY_DESCRIPTIONS = {
    "ELEXON": "Elexon (BMRS and REMIT data publisher)",
}

PART_SECTIONS = {
    "real": ("documents", "sources", "rows"),
    "recon": (
        "documents",
        "sources",
        "witnesses",
        "row_fragments",
        "data_returns",
    ),
}
_NOTE_EID = r"[A-Z]\d{2}"


class BuildError(Exception):
    """An input is inconsistent; nothing is written."""


sha256_bytes = sr.sha256_bytes
dumps_pretty = sr.dumps_pretty
dumps_sorted = sr.dumps_sorted
dumps_jsonl = sr.dumps_jsonl


def parse_utc(text: str) -> Any:
    try:
        return sr.parse_utc(text)
    except (sr.BuildError, ValueError) as exc:
        raise BuildError(str(exc)) from None


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BuildError(f"{rel(path)}: {exc}") from None


def rel(path: Path) -> str:
    return path.relative_to(ENV_ROOT).as_posix()


def status_label(text: str) -> str:
    try:
        return sr.status_label(text)
    except sr.BuildError as exc:
        raise BuildError(str(exc)) from None


def record_id(row: Mapping[str, Any]) -> str:
    return str(row.get("event_id") or row.get("entry_id"))


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (parse_utc(r["index_time_utc"]), record_id(r)))


# --------------------------------------------------------------------------- increment A


def load_increment_a() -> dict[str, Any]:
    """A's manifest, provenance and verified file bytes (fail closed)."""
    manifest_bytes = (SR_BUNDLE_DIR / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    provenance_bytes = SR_PROVENANCE_PATH.read_bytes()
    provenance = json.loads(provenance_bytes)
    if provenance.get("manifest_sha256") != sha256_bytes(manifest_bytes):
        raise BuildError("increment A provenance pins a different manifest sha256")
    pinned: dict[str, str] = {}
    for doc in manifest["documents"]:
        pinned.update(doc["sha256"])
    for section in ("asset_logs", "control_logs", "witnesses"):
        for entry in manifest[section]:
            pinned[entry["file"]] = entry["sha256"]
    if provenance.get("files") != dict(sorted(pinned.items())):
        raise BuildError("increment A provenance 'files' differ from its manifest")
    files: dict[str, bytes] = {}
    for name, digest in sorted(pinned.items()):
        path = SR_BUNDLE_DIR / name
        if path.is_symlink() or not path.is_file():
            raise BuildError(f"increment A file {name} is missing or not a file")
        data = path.read_bytes()
        if sha256_bytes(data) != digest:
            raise BuildError(f"increment A file {name} differs from A's manifest")
        files[name] = data
    access = {
        d["doc_id"] for d in manifest["documents"] if d.get("access") == "data_return"
    }
    if access != set(DATA_RETURN_ONLY):
        raise BuildError(f"increment A data-return-only documents are {sorted(access)}")
    for doc_id in REPLACED:
        if doc_id not in {d["doc_id"] for d in manifest["documents"]}:
            raise BuildError(f"replaced document {doc_id} is not in increment A")
    return {
        "manifest": manifest,
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "provenance": provenance,
        "provenance_sha256": sha256_bytes(provenance_bytes),
        "files": files,
    }


def split_note(
    text: str, evidence_ids: list[str], *, header: str | None, sep: str
) -> dict[str, str]:
    """Per-evidence parts of one of A's composed log notes (round-trip checked).

    A's clock notes are ``header + " " + " ".join(f"{eid} rows — {note}")`` and its
    source notes ``" ".join(f"{eid}: {note}")``, in evidence-ID order.
    """
    body = text
    if header is not None:
        if not text.startswith(header + " "):
            raise BuildError(f"log note does not open with A's header: {text[:60]!r}")
        body = text[len(header) + 1 :]
    pattern = re.compile(rf"(?:^| )({_NOTE_EID}){re.escape(sep)}")
    marks = list(pattern.finditer(body))
    found = [m.group(1) for m in marks]
    if found != list(evidence_ids):
        raise BuildError(f"log note parts {found} != evidence IDs {evidence_ids}")
    parts: dict[str, str] = {}
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(body)
        parts[mark.group(1)] = body[mark.end() : end]
    if join_note(parts, header=header, sep=sep) != text:
        raise BuildError("log note does not split unambiguously")
    return parts


def join_note(parts: Mapping[str, str], *, header: str | None, sep: str) -> str:
    body = " ".join(f"{eid}{sep}{parts[eid]}" for eid in sorted(parts))
    return f"{header} {body}" if header is not None else body


def status_line(evidence_ids: list[str], labels: Mapping[str, str]) -> str:
    return sr._status(evidence_ids, labels)


# --------------------------------------------------------------------------- documents


def _artifact(item: Mapping[str, Any]) -> dict[str, Any]:
    out = {
        "file": item["file"],
        "media_type": item["media_type"],
        "description": item["description"],
    }
    if item.get("timeseries") is not None:
        out["timeseries"] = item["timeseries"]
    return out


def new_document_entries(
    fragments: Mapping[str, Any], sr_docs: Mapping[str, Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Manifest entries of the tracks' documents and doc_id -> owning track."""
    owners: dict[str, str] = {}
    entries = []
    raw = [("real", doc) for doc in fragments["real"]["documents"]]
    raw += [("recon", doc) for doc in fragments["recon"]["documents"]]
    for track, doc in raw:
        doc_id = doc["doc_id"]
        if doc_id in owners:
            raise BuildError(f"{doc_id} is proposed by {owners[doc_id]} and {track}")
        owners[doc_id] = track
        if doc_id in sr_docs and REPLACED.get(doc_id) != track:
            raise BuildError(f"{track} proposes {doc_id}, an increment A document")
        if doc_id not in sr_docs and doc_id not in NEW_CATEGORIES:
            raise BuildError(f"{doc_id}: no category assigned by the integration step")
        category = (
            sr_docs[doc_id]["category"] if doc_id in sr_docs else NEW_CATEGORIES[doc_id]
        )
        artifacts = [_artifact(item) for item in doc["artifacts"]]
        hashes: dict[str, str] = {}
        for item, art in zip(doc["artifacts"], artifacts, strict=True):
            path = BUNDLE_DIR / art["file"]
            if path.is_symlink() or not path.is_file():
                raise BuildError(f"{doc_id}: {art['file']} is missing or not a file")
            if art["file"].split("/", 1)[0] != doc_id:
                raise BuildError(f"{doc_id}: {art['file']} is outside {doc_id}/")
            digest = sha256_bytes(path.read_bytes())
            claimed = (doc.get("sha256") or {}).get(art["file"], item.get("sha256"))
            if claimed is None or claimed != digest:
                raise BuildError(
                    f"{doc_id}: the {track} fragment's sha256 for {art['file']} is "
                    "missing or stale; rebuild the track"
                )
            hashes[art["file"]] = digest
        text = (BUNDLE_DIR / doc["text_file"]).read_text(encoding="utf-8")
        label = doc.get("label")
        if not label or not status_label(text).startswith(label):
            raise BuildError(f"{doc_id}: label {label!r} does not open the STATUS line")
        entry: dict[str, Any] = {
            "doc_id": doc_id,
            "title": doc["title"],
            "owner": doc["owner"],
            "date": doc["date"],
            "category": category,
            "label": label,
            "text_file": doc["text_file"],
            "artifacts": artifacts,
            "sha256": dict(sorted(hashes.items())),
        }
        if doc_id in PARTY_ALIASES:
            entry["party_aliases"] = list(PARTY_ALIASES[doc_id])
        if doc_id in KEYWORDS:
            entry["keywords"] = list(KEYWORDS[doc_id])
        entries.append(entry)
    missing = sorted((set(NEW_CATEGORIES) | set(REPLACED)) - set(owners))
    if missing:
        raise BuildError(f"no track supplies document(s) {', '.join(missing)}")
    return entries, owners


# --------------------------------------------------------------------------- rows


def load_fragment_rows(
    doc_ids: set[str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, bytes]]:
    """Rows of every new fragment (validated as A's schema) and the fragment bytes."""
    present = sorted(p.name for p in ROWS_DIR.glob("*.jsonl"))
    unknown = sorted(set(present) - set(ROW_FRAGMENTS))
    absent = sorted(set(ROW_FRAGMENTS) - set(present))
    if unknown or absent:
        raise BuildError(
            f"row fragments: unlisted {unknown or '-'}; missing {absent or '-'}"
        )
    rows: dict[str, list[dict[str, Any]]] = {}
    raw_bytes: dict[str, bytes] = {}
    for name in sorted(ROW_FRAGMENTS):
        data = (ROWS_DIR / name).read_bytes()
        raw_bytes[name] = data
        items = []
        for number, line in enumerate(data.decode("utf-8").split("\n")[:-1], 1):
            where = f"rows/{name} line {number}"
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise BuildError(f"{where}: {exc}") from None
            kind = row.get("kind")
            keys = {"asset": sr.ASSET_ROW_KEYS, "control": sr.CONTROL_ROW_KEYS}.get(
                kind
            )
            if keys is None:
                raise BuildError(f"{where}: kind {kind!r} is not asset or control")
            expected = set(keys) | set(sr.PRIVATE_ROW_KEYS)
            if set(row) != expected:
                raise BuildError(
                    f"{where}: keys differ from the {kind} row schema: "
                    f"{sorted(set(row) ^ expected)}"
                )
            if not isinstance(row["provenance"], dict) or not row["provenance"]:
                raise BuildError(f"{where}: empty provenance")
            if row["evidence_id"] not in doc_ids:
                raise BuildError(f"{where}: evidence_id {row['evidence_id']!r}")
            if row["value_status"] not in sr.VALUE_STATUSES:
                raise BuildError(f"{where}: value_status {row['value_status']!r}")
            parse_utc(row["index_time_utc"])
            items.append(row)
        if not data.endswith(b"\n") or not items:
            raise BuildError(f"rows/{name}: empty or not newline-terminated")
        rows[name] = items
    return rows, raw_bytes


def increment_a_rows(
    a: Mapping[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """A's public rows by asset and by room (from A's agent-visible log files)."""
    out: dict[str, dict[str, list[dict[str, Any]]]] = {"asset": {}, "control": {}}
    provenance = a["provenance"]["rows"]
    for section, kind, key, ref_kind in (
        ("asset_logs", "asset", "asset_id", "event"),
        ("control_logs", "control", "room_id", "entry"),
    ):
        for entry in a["manifest"][section]:
            text = a["files"][entry["file"]].decode("utf-8")
            rows = [json.loads(line) for line in text.split("\n")[:-1]]
            for row in rows:
                ref = f"{ref_kind}:{record_id(row)}"
                private = provenance.get(ref)
                if not private or private.get("log_file") != entry["file"]:
                    raise BuildError(f"increment A row {ref} has no provenance")
            out[kind][entry[key]] = rows
    return out["asset"], out["control"]


def merge_logs(
    a: Mapping[str, Any], fragment_rows: Mapping[str, list[dict[str, Any]]]
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, dict[str, Any]],
]:
    """asset_id -> rows, room_id -> rows (public fields only) and the row provenance."""
    a_assets, a_rooms = increment_a_rows(a)
    assets = {k: list(v) for k, v in a_assets.items()}
    rooms = {k: list(v) for k, v in a_rooms.items()}
    provenance: dict[str, dict[str, Any]] = {}
    for ref, private in a["provenance"]["rows"].items():
        provenance[ref] = {
            **private,
            "track": f"{SR_TRACK}.{private['track']}",
        }
    for name in sorted(fragment_rows):
        for row in fragment_rows[name]:
            public = {k: v for k, v in row.items() if k not in sr.PRIVATE_ROW_KEYS}
            if row["kind"] == "asset":
                key, log_id, target = "event", row["asset_id"], assets
                file = f"{ASSET_LOG_DIR}/{log_id}.jsonl"
            else:
                key, log_id, target = "entry", row["room_id"], rooms
                file = f"{CONTROL_LOG_DIR}/{log_id}.jsonl"
            ref = f"{key}:{record_id(row)}"
            if ref in provenance:
                raise BuildError(f"duplicate {key} ID {record_id(row)!r} ({name})")
            provenance[ref] = {
                "evidence_id": row["evidence_id"],
                "log_file": file,
                "fragment": f"builder/full_investigation/rows/{name}",
                "track": ROW_FRAGMENTS[name],
                "provenance": row["provenance"],
            }
            target.setdefault(log_id, []).append(public)
    known_assets = set(a_assets)
    known_rooms = set(a_rooms) | set(NEW_CONTROL_LOGS)
    unknown = sorted(set(assets) - known_assets) + sorted(set(rooms) - known_rooms)
    if unknown:
        raise BuildError(f"rows name logs without integration metadata: {unknown}")
    empty = sorted(set(NEW_CONTROL_LOGS) - set(rooms))
    if empty:
        raise BuildError(f"new rooms without rows: {empty}")
    return (
        {k: sort_rows(v) for k, v in sorted(assets.items())},
        {k: sort_rows(v) for k, v in sorted(rooms.items())},
        dict(sorted(provenance.items())),
    )


def real_source_terms(
    fragment_rows: Mapping[str, list[dict[str, Any]]],
    real_sources: Mapping[str, Any],
) -> dict[tuple[str, str], set[tuple[str, str]]]:
    """(kind, log ID) -> the (licence, attribution) terms of the real rows' sources."""
    out: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for name in sorted(fragment_rows):
        if ROW_FRAGMENTS[name] != "real":
            continue
        for row in fragment_rows[name]:
            key = (
                ("asset", row["asset_id"])
                if row["kind"] == "asset"
                else ("control", row["room_id"])
            )
            prov = row["provenance"]
            ids = prov.get("source_ids") or (
                [prov["source_id"]] if prov.get("source_id") else []
            )
            ids += [s["source_id"] for s in prov.get("sources", []) if "source_id" in s]
            if not ids:
                raise BuildError(f"real row {record_id(row)} cites no source_id")
            for source_id in ids:
                entry = real_sources.get(source_id)
                if not isinstance(entry, Mapping) or not entry.get("licence"):
                    raise BuildError(f"real source {source_id!r} has no licence")
                out.setdefault(key, set()).add(
                    (entry["licence"], entry.get("attribution") or "")
                )
    return out


def log_entries(
    a: Mapping[str, Any],
    assets: Mapping[str, list[dict[str, Any]]],
    rooms: Mapping[str, list[dict[str, Any]]],
    fragments: Mapping[str, Any],
    labels: Mapping[str, str],
    files: Mapping[str, bytes],
    terms: Mapping[tuple[str, str], set[tuple[str, str]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    real_assets = {e["asset_id"]: e for e in fragments["real"]["asset_logs"]}
    real_rooms = {e["room_id"]: e for e in fragments["real"]["control_logs"]}
    recon_rooms = {e["room_id"]: e for e in fragments["recon"]["control_logs"]}

    def proposal(text: str, prefix: str) -> str:
        return text[len(prefix) :] if text.startswith(prefix) else text

    def new_notes(
        kind: str, log_id: str, eid: str, spec: Mapping[str, Any]
    ) -> tuple[str, str]:
        """Clock and source note parts of a new evidence ID on a log."""
        if eid in ("R09", "R11"):
            real = (real_assets if kind == "asset" else real_rooms).get(log_id)
            if real is None or real["evidence_ids"] != [eid]:
                raise BuildError(f"{kind} log {log_id}: no real proposal for {eid}")
            clock = proposal(real["clock_note_proposal"], f"{eid} rows — ")
            source = spec["source"]
            found = terms.get((kind, log_id), set())
            if spec["real_terms"]:
                if len(found) != 1:
                    raise BuildError(
                        f"{kind} log {log_id}: {len(found)} licence terms for {eid}"
                    )
                ((licence, attribution),) = found
                if not attribution:
                    raise BuildError(f"{kind} log {log_id}: no attribution")
                source = (
                    f"{source} Rows are real public data extracts; licence: "
                    f"{licence}. {attribution}"
                )
            elif len(found) < 2:
                raise BuildError(
                    f"{kind} log {log_id}: one licence term; state it in the note"
                )
            return clock, source
        recon = recon_rooms.get(log_id)
        if recon is None or recon["evidence_ids"] != [eid]:
            raise BuildError(f"{kind} log {log_id}: no recon proposal for {eid}")
        clock, source = recon["clock_note"][eid], recon["source_note"][eid]
        # Each note part ends as a sentence (as increment A's notes do).
        return (clock if clock.endswith(".") else f"{clock}."), source

    header = sr.LOG_HEADER_NOTE
    sr_assets = {e["asset_id"]: e for e in a["manifest"]["asset_logs"]}
    sr_rooms = {e["room_id"]: e for e in a["manifest"]["control_logs"]}

    def entry_for(kind: str, log_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        id_key = "asset_id" if kind == "asset" else "room_id"
        folder = ASSET_LOG_DIR if kind == "asset" else CONTROL_LOG_DIR
        file = f"{folder}/{log_id}.jsonl"
        evidence_ids = sorted({r["evidence_id"] for r in rows})
        base = (sr_assets if kind == "asset" else sr_rooms).get(log_id)
        updates = (
            ASSET_LOG_UPDATES.get(log_id)
            if kind == "asset"
            else NEW_CONTROL_LOGS.get(log_id)
        )
        if base is not None:
            old_ids = list(base["evidence_ids"])
            clock = split_note(
                base["clock_note"], old_ids, header=header, sep=" rows — "
            )
            source = split_note(base["source_note"], old_ids, header=None, sep=": ")
            title, owner = base["title"], base["owner"]
            signals = list(base.get("signals", []))
        else:
            old_ids = []
            clock, source = {}, {}
            title = owner = ""
            signals = []
        added = [eid for eid in evidence_ids if eid not in old_ids]
        if added and updates is None:
            raise BuildError(f"{kind} log {log_id}: new evidence {added} undeclared")
        if updates is not None:
            if sorted(updates["new"]) != added:
                raise BuildError(
                    f"{kind} log {log_id}: declared {sorted(updates['new'])}, rows "
                    f"add {added}"
                )
            title, owner = updates["title"], updates["owner"]
            for eid in added:
                clock[eid], source[eid] = new_notes(
                    kind, log_id, eid, updates["new"][eid]
                )
        if kind == "asset":
            declared = list(real_assets.get(log_id, {}).get("signals", []))
            for signal in declared:
                if signal not in signals and any(r["signal"] == signal for r in rows):
                    signals.append(signal)
            for row in rows:
                if row["signal"] not in signals:
                    signals.append(row["signal"])
        entry: dict[str, Any] = {id_key: log_id, "title": title, "owner": owner}
        if kind == "asset":
            entry["signals"] = signals
            entry["clock_note"] = join_note(clock, header=header, sep=" rows — ")
            entry["evidence_ids"] = evidence_ids
        else:
            entry["evidence_ids"] = evidence_ids
            entry["clock_note"] = join_note(clock, header=header, sep=" rows — ")
        entry["status"] = status_line(evidence_ids, labels)
        entry["source_note"] = join_note(source, header=None, sep=": ")
        entry["file"] = file
        entry["sha256"] = sha256_bytes(files[file])
        if base is not None and not added:
            if entry != base:
                raise BuildError(f"{kind} log {log_id}: unchanged log entry differs")
            if files[file] != a["files"][file]:
                raise BuildError(f"{kind} log {log_id}: unchanged log file differs")
        if recon_rooms.get(log_id, {}).get("status") not in (None, entry["status"]):
            raise BuildError(f"{kind} log {log_id}: recon status proposal differs")
        return entry

    asset_entries = [entry_for("asset", k, v) for k, v in assets.items()]
    room_entries = [entry_for("control", k, v) for k, v in rooms.items()]
    return asset_entries, room_entries


# --------------------------------------------------------------------------- witnesses


def witness_entries(
    a: Mapping[str, Any], recon_fragment: Mapping[str, Any], recon_part: Mapping
) -> tuple[dict[str, bytes], list[dict[str, Any]], dict[str, Any]]:
    """Copies of A's cards, manifest entries of all cards and their block provenance."""
    copies: dict[str, bytes] = {}
    entries: list[dict[str, Any]] = []
    private: dict[str, Any] = {}
    for entry in a["manifest"]["witnesses"]:
        copies[entry["file"]] = a["files"][entry["file"]]
        entries.append(dict(entry))
        a_private = a["provenance"]["witnesses"][entry["persona_id"]]
        private[entry["persona_id"]] = {
            "track": f"{SR_TRACK}.recon",
            **a_private,
        }
    a_ids = {e["persona_id"] for e in entries}
    for proposal in recon_fragment["witnesses"]:
        persona_id = proposal["persona_id"]
        if persona_id in a_ids:
            raise BuildError(f"witness {persona_id} is already an increment A card")
        file = f"{WITNESS_DIR}/{persona_id}.json"
        if proposal["file"] != file:
            raise BuildError(f"witness {persona_id}: file {proposal['file']!r}")
        path = BUNDLE_DIR / file
        if path.is_symlink() or not path.is_file():
            raise BuildError(f"witness {persona_id}: card is missing")
        data = path.read_bytes()
        digest = sha256_bytes(data)
        if digest != proposal["sha256"]:
            raise BuildError(f"witness {persona_id}: recon fragment hash is stale")
        card = json.loads(data)
        for key in ("persona_id", "role", "organisation", "evidence_id"):
            if card.get(key) != proposal[key]:
                raise BuildError(f"witness {persona_id}: {key} differs from fragment")
        if any("provenance" in block for block in card["blocks"]):
            raise BuildError(f"witness {persona_id}: visible card carries provenance")
        part = recon_part["witnesses"].get(persona_id)
        if part is None or part.get("visible_sha256") != digest:
            raise BuildError(f"witness {persona_id}: recon provenance is stale")
        ids = [block["response_id"] for block in card["blocks"]]
        if sorted(ids) != sorted(part["blocks"]):
            raise BuildError(f"witness {persona_id}: provenance blocks differ")
        blocks = {}
        for block in card["blocks"]:
            sources = part["blocks"][block["response_id"]].get("sources")
            if not sources:
                raise BuildError(f"witness block {block['response_id']}: no sources")
            blocks[block["response_id"]] = {
                "topics": block["topics"],
                "sources": sources,
            }
        entries.append(
            {
                "persona_id": persona_id,
                "role": card["role"],
                "organisation": card["organisation"],
                "evidence_id": card["evidence_id"],
                "file": file,
                "sha256": digest,
            }
        )
        private[persona_id] = {
            "track": "recon",
            "file": file,
            "evidence_id": card["evidence_id"],
            "status": card.get("status"),
            "visible_sha256": digest,
            "blocks": blocks,
        }
    entries.sort(key=lambda e: e["persona_id"])
    return copies, entries, dict(sorted(private.items()))


# --------------------------------------------------------------------------- data returns


def _return_key(party: str, data_type: str) -> tuple[str, str]:
    return (" ".join(party.casefold().split()), " ".join(data_type.casefold().split()))


def data_return_entries(
    a: Mapping[str, Any], real_fragment: Mapping[str, Any], doc_ids: set[str]
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], str]]:
    """A's registry, the recon additions and the real proposals; entry -> track."""
    raw: list[tuple[str, Mapping[str, Any]]] = [
        (SR_TRACK, item) for item in a["manifest"]["data_returns"]
    ]
    raw += [("recon", item) for item in read_json(DATA_RETURNS_FRAGMENT)]
    raw += [("real", item) for item in real_fragment["data_returns_proposal"]]
    out: list[dict[str, Any]] = []
    tracks: dict[tuple[str, str], str] = {}
    for track, item in raw:
        key = _return_key(item["party"], item["data_type"])
        if key in tracks:
            raise BuildError(
                f"data return {item['party']}/{item['data_type']} is proposed by "
                f"{tracks[key]} and {track}"
            )
        tracks[key] = track
        entry: dict[str, Any] = {
            "party": item["party"],
            "data_type": item["data_type"],
            "status": item["status"],
        }
        if item.get("evidence_id") is not None:
            if item["evidence_id"] not in doc_ids:
                raise BuildError(f"data return names unknown {item['evidence_id']!r}")
            entry["evidence_id"] = item["evidence_id"]
        message = DATA_RETURN_MESSAGES.get(
            (item["party"], item["data_type"]), item.get("message")
        )
        if message is not None:
            entry["message"] = message
        if entry["status"] != "available" and not str(message).startswith(
            "Not held in this evidence pack: "
        ):
            raise BuildError(f"data return {key}: refusal wording")
        out.append(entry)
    for (party, data_type), _ in DATA_RETURN_MESSAGES.items():
        if _return_key(party, data_type) not in tracks:
            raise BuildError(f"message override for unknown return {party}/{data_type}")
    reachable = {e.get("evidence_id") for e in out if e["status"] == "available"}
    for doc_id in DATA_RETURN_ONLY:
        if doc_id not in reachable:
            raise BuildError(f"{doc_id} is data-return-only but no return names it")
    out.sort(key=lambda e: (e["party"], e["data_type"]))
    by_entry = {
        (e["party"], e["data_type"]): tracks[_return_key(e["party"], e["data_type"])]
        for e in out
    }
    return out, by_entry


def not_held_basis(
    a: Mapping[str, Any],
    recon_part: Mapping[str, Any],
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    basis: dict[tuple[str, str], dict[str, Any]] = {}
    for track, items in (
        (SR_TRACK, a["provenance"]["data_returns"].get("not_held_basis", [])),
        ("recon", recon_part["data_returns"].get("not_held_basis", [])),
        ("integration", EXTRA_NOT_HELD_BASIS),
    ):
        for item in items:
            key = (item["party"], item["data_type"])
            if key in basis:
                raise BuildError(f"two not-held bases for {key}")
            basis[key] = {
                "party": item["party"],
                "data_type": item["data_type"],
                "basis": item.get("basis", []),
                "track": item.get("track", track),
            }
    wanted = {
        (e["party"], e["data_type"]) for e in entries if e["status"] != "available"
    }
    missing = sorted(wanted - set(basis))
    extra = sorted(set(basis) - wanted)
    if missing or extra:
        raise BuildError(f"not-held bases: missing {missing}; without entry {extra}")
    return [basis[key] for key in sorted(basis)]


# --------------------------------------------------------------------------- provenance


def merged_sources(a: Mapping[str, Any], parts: Mapping[str, Any]) -> dict[str, Any]:
    """source_id -> {sha256?, parts: {track: entry}}; a shared ID must pin one hash."""
    out: dict[str, Any] = {}

    def add(source_id: str, track: str, entry: Any) -> None:
        slot = out.setdefault(source_id, {"parts": {}})
        digest = entry.get("sha256") if isinstance(entry, dict) else None
        if digest is not None:
            if slot.get("sha256", digest) != digest:
                raise BuildError(f"source {source_id}: tracks pin different sha256")
            slot["sha256"] = digest
        slot["parts"][track] = entry

    for source_id, merged in sorted(a["provenance"]["sources"].items()):
        for track, entry in sorted(merged["parts"].items()):
            add(source_id, f"{SR_TRACK}.{track}", entry)
    for track in sorted(parts):
        for source_id, entry in sorted(parts[track]["sources"].items()):
            add(source_id, track, entry)
    add(REAL_DATA_LOG["source_id"], "integration", dict(REAL_DATA_LOG))
    return dict(sorted(out.items()))


def merged_documents(
    a: Mapping[str, Any],
    parts: Mapping[str, Any],
    owners: Mapping[str, str],
    texts: Mapping[str, bytes],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for doc_id, doc in a["provenance"]["documents"].items():
        if doc_id in REPLACED:
            continue
        out[doc_id] = {**doc, "track": f"{SR_TRACK}.{doc['track']}"}
    for doc_id, track in owners.items():
        doc = parts[track]["documents"].get(doc_id)
        if doc is None:
            raise BuildError(f"{doc_id}: no provenance in the {track} part")
        out[doc_id] = {"track": track, **doc}
    for track, part in parts.items():
        extra = sorted(set(part["documents"]) - set(owners))
        if extra:
            raise BuildError(f"{track} provenance covers unknown documents {extra}")
    for doc_id, doc in out.items():
        if doc.get("text_sha256") != sha256_bytes(texts[doc_id]):
            raise BuildError(f"{doc_id}: provenance text_sha256 does not match")
    return dict(sorted(out.items()))


def leakage_detectors(parts: Mapping[str, Any]) -> dict[str, Any]:
    """Decision 50: enforcement outcomes kept out of the agent evidence, as detectors."""
    real = parts["real"].get("excluded", [])
    recon = parts["recon"].get("excluded_from_agent_evidence", {})
    markers = sorted({m for item in real for m in item.get("leakage_markers", [])})
    if not markers or not recon.get("detector_patterns"):
        raise BuildError("the tracks record no enforcement-outcome leakage detectors")
    return {
        "note": "Decision 50: Ofgem's January 2020 enforcement outcomes are public but "
        "excluded from every agent-visible file (verify_bundle.py scans for them). "
        "Markers and patterns below detect leakage or memorisation (severe flag SF3).",
        "leakage_markers": markers,
        "detector_patterns": list(recon["detector_patterns"]),
        "real_excluded": real,
        "recon_passages": recon.get("passages", []),
    }


def _row_fragment_hashes(
    fragments: Mapping[str, Any], parts: Mapping[str, Any]
) -> dict[str, str]:
    out = {name: info["sha256"] for name, info in parts["real"]["rows"].items()}
    for name, info in fragments["recon"]["row_fragments"].items():
        out[name] = info["sha256"]
    return out


# --------------------------------------------------------------------------- build


def build() -> dict[Path, bytes]:
    a = load_increment_a()
    sr_docs = {d["doc_id"]: d for d in a["manifest"]["documents"]}
    fragments = {track: read_json(path) for track, path in FRAGMENTS.items()}
    part_bytes = {track: path.read_bytes() for track, path in PROVENANCE_PARTS.items()}
    parts = {track: json.loads(data) for track, data in part_bytes.items()}

    outputs: dict[str, bytes] = {}
    documents: list[dict[str, Any]] = []
    for doc_id, doc in sr_docs.items():
        if doc_id in REPLACED:
            continue
        documents.append(dict(doc))
        for name in doc["sha256"]:
            outputs[name] = a["files"][name]
    new_docs, owners = new_document_entries(fragments, sr_docs)
    documents += new_docs
    documents.sort(key=lambda d: d["doc_id"])
    doc_ids = {d["doc_id"] for d in documents}
    labels = {d["doc_id"]: d["label"] for d in documents}
    texts = {
        d["doc_id"]: (
            outputs[d["text_file"]]
            if d["text_file"] in outputs
            else (BUNDLE_DIR / d["text_file"]).read_bytes()
        )
        for d in documents
    }

    fragment_rows, fragment_bytes = load_fragment_rows(doc_ids)
    pinned = _row_fragment_hashes(fragments, parts)
    for name, data in fragment_bytes.items():
        if pinned.get(name) != sha256_bytes(data):
            raise BuildError(f"rows/{name}: sha256 differs from its track's record")
    recon_rows = parts["recon"]["row_fragments"]
    for name, rows in fragment_rows.items():
        if ROW_FRAGMENTS[name] != "recon":
            continue
        recorded = recon_rows.get(name, {}).get("provenance", {})
        for row in rows:
            if recorded.get(record_id(row)) != row["provenance"]:
                raise BuildError(f"rows/{name}: {record_id(row)} provenance differs")
    assets, rooms, row_provenance = merge_logs(a, fragment_rows)
    for asset_id, rows in assets.items():
        outputs[f"{ASSET_LOG_DIR}/{asset_id}.jsonl"] = dumps_jsonl(rows)
    for room_id, rows in rooms.items():
        outputs[f"{CONTROL_LOG_DIR}/{room_id}.jsonl"] = dumps_jsonl(rows)
    asset_entries, room_entries = log_entries(
        a,
        assets,
        rooms,
        fragments,
        labels,
        outputs,
        real_source_terms(fragment_rows, parts["real"]["sources"]),
    )

    card_copies, witnesses, witness_provenance = witness_entries(
        a, fragments["recon"], parts["recon"]
    )
    outputs.update(card_copies)
    clash = sorted({w["evidence_id"] for w in witnesses} & doc_ids)
    if clash:
        raise BuildError(f"witness evidence ID(s) {clash} collide with documents")

    data_returns, return_tracks = data_return_entries(a, fragments["real"], doc_ids)
    basis = not_held_basis(a, parts["recon"], data_returns)

    categories = list(a["manifest"]["categories"]) + list(NEW_CATEGORY_ORDER)
    used = {d["category"] for d in documents}
    if used != set(categories):
        raise BuildError(f"categories in use {sorted(used)} != {categories}")
    manifest = {
        "manifest_version": 2,
        "bundle_id": BUNDLE_ID,
        "bundle_version": BUNDLE_VERSION,
        "categories": categories,
        "documents": documents,
        "asset_logs": asset_entries,
        "control_logs": room_entries,
        "witnesses": witnesses,
        "data_returns": data_returns,
    }
    manifest_bytes = dumps_pretty(manifest)
    outputs["manifest.json"] = manifest_bytes

    bundle_files: dict[str, str] = {}
    for doc in documents:
        bundle_files.update(doc["sha256"])
    for entry in (*asset_entries, *room_entries, *witnesses):
        bundle_files[entry["file"]] = entry["sha256"]

    provenance = {
        "schema": "gb-2019-full-investigation/provenance/1",
        "bundle_id": BUNDLE_ID,
        "bundle_version": BUNDLE_VERSION,
        "generated_by": GENERATED_BY,
        "verified_by": VERIFIED_BY,
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "value_statuses": list(sr.VALUE_STATUSES),
        "inherited": {
            "note": "Increment A's documents (except R10), log rows, witness cards and "
            "data returns are copied unchanged with their IDs; their provenance below is "
            "increment A's (track prefix 'system_response.'). R10 is the "
            "reconstruction track's full edition, whose lines 1-133 are A's R10.",
            "bundle": rel(SR_BUNDLE_DIR),
            "bundle_id": a["manifest"]["bundle_id"],
            "bundle_version": a["manifest"]["bundle_version"],
            "manifest_sha256": a["manifest_sha256"],
            "provenance": rel(SR_PROVENANCE_PATH),
            "provenance_sha256": a["provenance_sha256"],
            "documents": sorted(d for d in sr_docs if d not in REPLACED),
            "replaced": dict(REPLACED),
            "parts": a["provenance"]["parts"],
        },
        "parts": {
            track: {
                "file": rel(PROVENANCE_PARTS[track]),
                "sha256": sha256_bytes(part_bytes[track]),
                "generated_by": parts[track].get("generated_by"),
                "documents": sorted(parts[track]["documents"]),
                "extras": {
                    key: value
                    for key, value in sorted(parts[track].items())
                    if key not in PART_SECTIONS[track]
                },
            }
            for track in sorted(parts)
        },
        "manifest_fragments": {
            track: {"file": rel(path), "sha256": sha256_bytes(path.read_bytes())}
            for track, path in sorted(FRAGMENTS.items())
        },
        "sources": merged_sources(a, parts),
        "documents": merged_documents(a, parts, owners, texts),
        "rows": row_provenance,
        "row_fragments": {
            name: {
                "track": ROW_FRAGMENTS[name],
                "rows": len(fragment_rows[name]),
                "sha256": sha256_bytes(fragment_bytes[name]),
            }
            for name in sorted(fragment_rows)
        },
        "witnesses": witness_provenance,
        "data_returns": {
            "fragments": {
                "system_response": a["provenance"]["data_returns"].get("fragment"),
                "recon": rel(DATA_RETURNS_FRAGMENT),
                "real": rel(FRAGMENTS["real"]) + " (data_returns_proposal)",
            },
            "recon_fragment_sha256": sha256_bytes(DATA_RETURNS_FRAGMENT.read_bytes()),
            "entries": data_returns,
            "entry_tracks": {
                f"{party}/{data_type}": track
                for (party, data_type), track in sorted(return_tracks.items())
            },
            "not_held_basis": basis,
            "notes": {
                SR_TRACK: a["provenance"]["data_returns"].get("note"),
                "recon": parts["recon"]["data_returns"].get("note"),
            },
            "parties": {
                **fragments["recon"]["data_returns"].get("parties", {}),
                **REAL_PARTY_DESCRIPTIONS,
            },
            "message_overrides": {
                f"{party}/{data_type}": message
                for (party, data_type), message in sorted(DATA_RETURN_MESSAGES.items())
            },
        },
        "leakage_detectors": leakage_detectors(parts),
        "integration": {
            "categories": {d["doc_id"]: d["category"] for d in documents},
            "new_categories": list(NEW_CATEGORY_ORDER),
            "data_return_only": list(DATA_RETURN_ONLY),
            "replaced": dict(REPLACED),
            "row_order": "index_time_utc instant, then event_id/entry_id",
            "stripped_from_agent_files": ["kind", "provenance"],
            "notes": [
                "No new document is data-return-only: every new document is listed; "
                + ", ".join(
                    sorted(
                        {
                            e["evidence_id"]
                            for e in data_returns
                            if e["status"] == "available" and e["evidence_id"] in owners
                        }
                    )
                )
                + " can also be obtained through a registered data return.",
                "Stanlow (12 September 2019): R12 (real track) excludes the article; S11 "
                "(reconstruction track) carries a dated summary that shares no four "
                "consecutive words with it, labelled by its date only (contract: a "
                "known distractor that may be included, labelled by date).",
                "ESO/control_room_communications_log: the real track proposed it "
                "without a recorded basis; the basis is the real-data sourcing log's "
                "T15 gap list, and the message says only that it was not obtained.",
            ],
        },
        "files": dict(sorted(bundle_files.items())),
    }

    result = {BUNDLE_DIR / name: data for name, data in sorted(outputs.items())}
    result[PROVENANCE_PATH] = dumps_sorted(provenance)
    return result


def owned_stale_files(outputs: Mapping[Path, bytes]) -> list[Path]:
    """Files in places this step owns that a fresh build would not write.

    Owned: the log directories, the copied increment A document directories, the
    witness directory except the reconstruction track's cards, and the bundle's top
    level (only ``manifest.json`` and the document, log and witness directories)."""
    manifest = read_json(FRAGMENTS["recon"])
    recon_cards = {BUNDLE_DIR / w["file"] for w in manifest["witnesses"]}
    a_manifest = read_json(SR_BUNDLE_DIR / "manifest.json")
    copied = [
        d["doc_id"] for d in a_manifest["documents"] if d["doc_id"] not in REPLACED
    ]
    known_dirs = {d["doc_id"] for d in a_manifest["documents"]}
    known_dirs |= set(NEW_CATEGORIES) | {"logs", WITNESS_DIR}
    stale = []
    for sub in (ASSET_LOG_DIR, CONTROL_LOG_DIR, WITNESS_DIR, *copied):
        folder = BUNDLE_DIR / sub
        if folder.is_dir():
            for path in sorted(folder.iterdir()):
                if path not in outputs and path not in recon_cards:
                    stale.append(path)
    logs = BUNDLE_DIR / "logs"
    if logs.is_dir():
        for path in sorted(logs.iterdir()):
            if path.name not in ("assets", "control"):
                stale.append(path)
    if BUNDLE_DIR.is_dir():
        for path in sorted(BUNDLE_DIR.iterdir()):
            if path.name == "manifest.json" or (
                path.is_dir() and not path.is_symlink() and path.name in known_dirs
            ):
                continue
            stale.append(path)
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="compare with disk, write nothing"
    )
    args = parser.parse_args(argv)
    try:
        outputs = build()
    except (BuildError, sr.BuildError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    differ = []
    for path, data in outputs.items():
        current = path.read_bytes() if path.is_file() else None
        if current != data:
            differ.append(path)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    extra = owned_stale_files(outputs)
    if not args.check:
        for path in extra:
            if path.is_dir() and not path.is_symlink():
                raise SystemExit(f"refusing to remove directory {rel(path)}")
            path.unlink()
    for path in sorted(outputs):
        flag = "STALE " if args.check and path in differ else ""
        if flag or not args.check:
            print(f"{flag}{rel(path)}")
    for path in extra:
        print(f"{'UNEXPECTED ' if args.check else 'REMOVED '}{rel(path)}")
    if args.check and (differ or extra):
        print(f"{len(differ)} output(s) differ, {len(extra)} unexpected file(s)")
        return 1
    print(
        f"{len(outputs)} outputs; {len(differ)} {'differ' if args.check else 'written'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
