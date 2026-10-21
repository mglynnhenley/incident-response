"""Integrate the system-response evidence bundle (manifest v2) from the track outputs.

Builder-only and deterministic: the same inputs give byte-identical outputs (no clock, no
randomness, sorted iteration everywhere). It reads only files already produced by the
track builders, so it needs no ``.context`` input:

- manifest fragments: ``real/documents_real.json`` (R02, R04, R06, R07 and the real asset
  and control log contributions), ``digitise/r05_manifest_fragment.json`` (R05) and
  ``recon/documents.json`` (R01, R03, R08, R10, S01, S03-S07, S12 and the S09 witnesses);
- row fragments ``rows/*.jsonl`` (one object per line with ``kind`` and private
  ``provenance``), the data-return registry fragment ``rows/data_returns.json`` and the
  witness source cards ``rows/witnesses/<persona_id>.json`` (blocks carry ``provenance``);
- the private provenance parts ``private/system_response/provenance_{real,R05,recon}.json``.

It writes:

- ``bundles/system_response/logs/assets/<asset_id>.jsonl`` and
  ``logs/control/<room_id>.jsonl``: the merged rows without ``kind``/``provenance``, keys
  sorted, rows stable-sorted by (index instant, record ID);
- ``bundles/system_response/witnesses/<persona_id>.json``: agent-visible cards (block
  provenance stripped);
- ``bundles/system_response/manifest.json``: manifest v2 (neutral titles, categories,
  owners, dates, labels, sha256 of every file; asset_logs, control_logs, witnesses and
  data_returns sections);
- ``private/system_response/provenance.json``: the merged provenance (documents, every row,
  every witness block, data-return bases, the parts' own validation sections, file hashes).

Metadata owned by this step (categories, log titles, owners, clock notes, status labels,
data-return-only documents) is defined below. Any inconsistency between fragments and the
files on disk (stale hash, unknown evidence ID, duplicate record ID, missing provenance) stops
the build.

    uv run --frozen python builder/system_response/build_bundle.py          # write
    uv run --frozen python builder/system_response/build_bundle.py --check  # compare only
    uv run --frozen python builder/system_response/verify_bundle.py         # all checks
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SR_BUILDER_DIR = Path(__file__).resolve().parent
ENV_ROOT = SR_BUILDER_DIR.parents[1]
INCIDENT_DIR = ENV_ROOT / "src" / "environment" / "incident"
BUNDLE_DIR = INCIDENT_DIR / "bundles" / "system_response"
PRIVATE_DIR = INCIDENT_DIR / "private" / "system_response"
ROWS_DIR = SR_BUILDER_DIR / "rows"
WITNESS_SOURCE_DIR = ROWS_DIR / "witnesses"
DATA_RETURNS_FRAGMENT = ROWS_DIR / "data_returns.json"
MANIFEST_PATH = BUNDLE_DIR / "manifest.json"
PROVENANCE_PATH = PRIVATE_DIR / "provenance.json"
ASSET_LOG_DIR = "logs/assets"
CONTROL_LOG_DIR = "logs/control"
WITNESS_DIR = "witnesses"

GENERATED_BY = "builder/system_response/build_bundle.py"
VERIFIED_BY = "builder/system_response/verify_bundle.py"
BUNDLE_ID = "gb-2019-08-09-system-response"
BUNDLE_VERSION = "0.1.0"

# Track -> manifest fragment and private provenance part.
FRAGMENTS: dict[str, Path] = {
    "real": SR_BUILDER_DIR / "real" / "documents_real.json",
    "digitise": SR_BUILDER_DIR / "digitise" / "r05_manifest_fragment.json",
    "recon": SR_BUILDER_DIR / "recon" / "documents.json",
}
PROVENANCE_PARTS: dict[str, Path] = {
    "real": PRIVATE_DIR / "provenance_real.json",
    "digitise": PRIVATE_DIR / "provenance_R05.json",
    "recon": PRIVATE_DIR / "provenance_recon.json",
}
# Row fragment -> owning track. Every *.jsonl in rows/ must be listed here.
ROW_FRAGMENTS: dict[str, str] = {
    "real_r02_asset.jsonl": "real",
    "real_r06_control.jsonl": "real",
    "r05_hornsea_traces.jsonl": "digitise",
    "recon_r03.jsonl": "recon",
    "recon_r08.jsonl": "recon",
    "recon_s01.jsonl": "recon",
    "recon_s03.jsonl": "recon",
    "recon_s07.jsonl": "recon",
}

ASSET_ROW_KEYS = (
    "asset_id",
    "clock_basis",
    "event_id",
    "evidence_id",
    "index_time_utc",
    "index_uncertainty_s",
    "recorded_time",
    "signal",
    "text",
    "unit",
    "value",
    "value_status",
)
CONTROL_ROW_KEYS = (
    "channel",
    "clock_basis",
    "entry_id",
    "evidence_id",
    "from",
    "index_time_utc",
    "index_uncertainty_s",
    "recorded_time",
    "room_id",
    "text",
    "to",
    "value_status",
)
PRIVATE_ROW_KEYS = ("kind", "provenance")
VALUE_STATUSES = (
    "measured",
    "reported",
    "estimated",
    "modelled",
    "digitised",
    "illustrative",
    "framing",
)

# --------------------------------------------------------------------------- catalogue metadata

CATEGORY_ORDER = (
    "measurement_data",
    "network_records",
    "generator_records",
    "personnel_accounts",
    "system_operator_records",
    "distribution_records",
    "requirements",
    "analysis_records",
)
# The MVP categories are kept for the MVP documents; the tracks' proposals are merged into
# four neutral categories (operational_records -> system_operator_records,
# distribution_returns -> distribution_records).
CATEGORIES: dict[str, str] = {
    "R01": "measurement_data",
    "R02": "measurement_data",
    "R03": "network_records",
    "R04": "measurement_data",
    "R05": "measurement_data",
    "R06": "system_operator_records",
    "R07": "distribution_records",
    "R08": "system_operator_records",
    "R10": "requirements",
    "S01": "generator_records",
    "S03": "generator_records",
    "S04": "personnel_accounts",
    "S05": "distribution_records",
    "S06": "distribution_records",
    "S07": "system_operator_records",
    "S12": "analysis_records",
}
# DNO returns are obtained through request_data_return (party DNO), not listed.
DATA_RETURN_ONLY = ("S05", "S06")
# Free-text request help (request_document party matching); never answers.
PARTY_ALIASES: dict[str, tuple[str, ...]] = {
    "R01": ("system operator",),
    "R02": ("system operator", "National Grid ESO"),
    "R03": ("transmission owner",),
    "R05": ("system operator", "Hornsea One operator"),
    "R06": ("system operator",),
    "R07": ("system operator", "DNO", "DNOs"),
    "R08": ("system operator",),
    "R10": ("system operator", "regulator"),
    "S01": ("wind farm operator",),
    "S03": ("power station operator",),
    "S04": ("power station operator",),
    "S07": ("system operator",),
    "S12": ("system operator", "regulator"),
}
R05_LABEL_KEY = "label"  # provenance_R05.json carries the R05 label

LOG_HEADER_NOTE = (
    "Each row gives the time as recorded and its clock basis; index_time_utc is a UTC "
    "conversion made by the bundle builder and used only to select rows, with the "
    "uncertainty in index_uncertainty_s."
)
# Per log: title, owner and, per evidence ID, the clock and source notes. Clock notes
# describe how times are written, never what happened.
ASSET_LOGS: dict[str, dict[str, Any]] = {
    "ESW-400": {
        "title": "Eaton Socon - Wymondley Main 400 kV circuit: record entries",
        "owner": "National Grid Electricity Transmission (NGET)",
        "clock": {
            "R03": "times as written in R03 (BST, UTC+01:00; the source does not label "
            "its clock).",
        },
        "source": {
            "R03": "rows restate entries of the reconstructed transmission record R03.",
        },
    },
    "HORNSEA-ONE": {
        "title": "Hornsea One offshore wind farm: event log entries, BM unit data and "
        "chart readings",
        "owner": "Ørsted (event log); Elexon (BM unit data); National Grid ESO "
        "(published report charts)",
        "clock": {
            "S01": "times rendered in UTC (Z) by the reconstructed event log; the "
            "operator's published timeline uses local time.",
            "R05": "chart times as printed (no time zone printed); the index reads them "
            "as BST, with the uncertainty stated per row.",
        },
        "source": {
            "R05": "rows restate values read from published chart images (see R05 for "
            "method and uncertainty); not original records.",
            "S01": "rows restate entries of the reconstructed event log S01.",
        },
    },
    "LITTLE-BARFORD": {
        "title": "Little Barford power station: sequence-of-events entries and BM unit "
        "data",
        "owner": "RWE Generation (sequence of events); Elexon (BM unit data)",
        "clock": {
            "S03": "offsets from the station's sequence-of-events datum T as recorded; "
            "the datum and its clock are stated in S03 and in each row's clock_basis.",
        },
        "source": {
            "S03": "rows restate entries of the reconstructed sequence-of-events record "
            "S03.",
        },
    },
}
CONTROL_LOGS: dict[str, dict[str, Any]] = {
    "ESO-ENCC": {
        "title": "ESO Electricity National Control Centre (ENCC): timeline entries, "
        "operational calls and balancing acceptances",
        "owner": "National Grid ESO (published timelines and call diagram); Elexon "
        "(BOALF data)",
        "clock": {
            "R08": "hh:mm as printed on ESO's call diagram (no clock labelled; read as "
            "BST, UTC+01:00).",
            "S07": "hh:mm[:ss] as printed in ESO's timelines (no clock labelled; read as "
            "BST, UTC+01:00).",
        },
        "source": {
            "R08": "rows restate the calls of the reconstructed call record R08.",
            "S07": "rows restate entries of the reconstructed control-room log S07.",
        },
    },
}

# --------------------------------------------------------------------------- helpers


class BuildError(Exception):
    """An input fragment is inconsistent; nothing is written."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BuildError(f"{path.relative_to(ENV_ROOT)}: {exc}") from None


def dumps_pretty(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def dumps_sorted(obj: Any, indent: int | None = 1) -> bytes:
    return (
        json.dumps(obj, ensure_ascii=False, indent=indent, sort_keys=True) + "\n"
    ).encode("utf-8")


def dumps_jsonl(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return "".join(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    ).encode("utf-8")


def parse_utc(text: str) -> datetime:
    when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if when.tzinfo is None:
        raise BuildError(f"index time {text!r} has no offset")
    return when.astimezone(UTC)


def rel(path: Path) -> str:
    return path.relative_to(ENV_ROOT).as_posix()


def status_label(text: str) -> str:
    """The STATUS label of a document text (first STATUS line, up to its first stop)."""
    for line in text.splitlines():
        if line.startswith("STATUS: "):
            return line[len("STATUS: ") :]
    raise BuildError("document text has no 'STATUS: ' line")


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


def collect_documents(
    fragments: Mapping[str, Any], parts: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Manifest document entries (sorted by doc_id) and doc_id -> owning track."""
    raw: list[tuple[str, dict[str, Any]]] = []
    for track in ("real", "recon"):
        for doc in fragments[track]["documents"]:
            raw.append((track, doc))
    raw.append(("digitise", fragments["digitise"]))
    owners: dict[str, str] = {}
    documents = []
    for track, doc in raw:
        doc_id = doc["doc_id"]
        if doc_id in owners:
            raise BuildError(
                f"{doc_id} is proposed by both {owners[doc_id]} and {track}"
            )
        owners[doc_id] = track
        if doc_id not in CATEGORIES:
            raise BuildError(f"{doc_id}: no category assigned by the integration step")
        artifacts = [_artifact(item) for item in doc["artifacts"]]
        hashes: dict[str, str] = {}
        for item, art in zip(doc["artifacts"], artifacts, strict=True):
            path = BUNDLE_DIR / art["file"]
            if path.is_symlink() or not path.is_file():
                raise BuildError(f"{doc_id}: {art['file']} is missing or not a file")
            digest = sha256_bytes(path.read_bytes())
            claimed = (doc.get("sha256") or {}).get(art["file"], item.get("sha256"))
            if claimed is not None and claimed != digest:
                raise BuildError(
                    f"{doc_id}: the {track} fragment's sha256 for {art['file']} is stale "
                    f"(fragment {claimed[:12]}..., disk {digest[:12]}...); rebuild the track"
                )
            hashes[art["file"]] = digest
        text = (BUNDLE_DIR / doc["text_file"]).read_text(encoding="utf-8")
        label = doc.get("label")
        if label is None and track == "digitise":
            label = parts["digitise"][R05_LABEL_KEY]
        if label is None or not status_label(text).startswith(label):
            raise BuildError(
                f"{doc_id}: label {label!r} does not open the text's STATUS line"
            )
        entry: dict[str, Any] = {
            "doc_id": doc_id,
            "title": doc["title"],
            "owner": doc["owner"],
            "date": doc["date"],
            "category": CATEGORIES[doc_id],
            "label": label,
            "text_file": doc["text_file"],
            "artifacts": artifacts,
            "sha256": dict(sorted(hashes.items())),
        }
        if doc_id in DATA_RETURN_ONLY:
            entry["access"] = "data_return"
        if doc_id in PARTY_ALIASES:
            entry["party_aliases"] = list(PARTY_ALIASES[doc_id])
        documents.append(entry)
    missing = sorted(set(CATEGORIES) - set(owners))
    if missing:
        raise BuildError(f"no track supplies document(s) {', '.join(missing)}")
    return sorted(documents, key=lambda d: d["doc_id"]), owners


# --------------------------------------------------------------------------- rows


def load_fragment_rows(
    doc_ids: set[str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, bytes]]:
    """Rows of every fragment (validated) and the fragment bytes."""
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
            keys = {"asset": ASSET_ROW_KEYS, "control": CONTROL_ROW_KEYS}.get(kind)
            if keys is None:
                raise BuildError(f"{where}: kind {kind!r} is not asset or control")
            expected = set(keys) | set(PRIVATE_ROW_KEYS)
            if set(row) != expected:
                raise BuildError(
                    f"{where}: keys differ from the {kind} row schema: "
                    f"{sorted(set(row) ^ expected)}"
                )
            if not isinstance(row["provenance"], dict) or not row["provenance"]:
                raise BuildError(f"{where}: empty provenance")
            if row["evidence_id"] not in doc_ids:
                raise BuildError(
                    f"{where}: evidence_id {row['evidence_id']!r} is not a document"
                )
            if row["value_status"] not in VALUE_STATUSES:
                raise BuildError(f"{where}: value_status {row['value_status']!r}")
            parse_utc(row["index_time_utc"])
            items.append(row)
        if not data.endswith(b"\n") or not items:
            raise BuildError(f"rows/{name}: empty or not newline-terminated")
        rows[name] = items
    return rows, raw_bytes


def record_id(row: Mapping[str, Any]) -> str:
    return str(row.get("event_id") or row.get("entry_id"))


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (parse_utc(r["index_time_utc"]), record_id(r)))


def merge_logs(
    fragment_rows: Mapping[str, list[dict[str, Any]]],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, dict[str, Any]],
]:
    """asset_id -> rows, room_id -> rows (public fields only) and the row provenance."""
    assets: dict[str, list[dict[str, Any]]] = {}
    rooms: dict[str, list[dict[str, Any]]] = {}
    provenance: dict[str, dict[str, Any]] = {}
    for name in sorted(fragment_rows):
        for row in fragment_rows[name]:
            kind = row["kind"]
            public = {k: v for k, v in row.items() if k not in PRIVATE_ROW_KEYS}
            if kind == "asset":
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
                "fragment": f"builder/system_response/rows/{name}",
                "track": ROW_FRAGMENTS[name],
                "provenance": row["provenance"],
            }
            target.setdefault(log_id, []).append(public)
    unknown_assets = sorted(set(assets) - set(ASSET_LOGS))
    unknown_rooms = sorted(set(rooms) - set(CONTROL_LOGS))
    if unknown_assets or unknown_rooms:
        raise BuildError(
            f"rows name logs without integration metadata: assets {unknown_assets}, "
            f"rooms {unknown_rooms}"
        )
    return (
        {k: sort_rows(v) for k, v in sorted(assets.items())},
        {k: sort_rows(v) for k, v in sorted(rooms.items())},
        dict(sorted(provenance.items())),
    )


def _ordered_signals(rows: list[dict[str, Any]], declared: list[str]) -> list[str]:
    """Signals in the fragments' declared order, then first appearance in sorted rows."""
    out = [s for s in declared if any(r["signal"] == s for r in rows)]
    for row in rows:
        if row["signal"] not in out:
            out.append(row["signal"])
    return out


def _status(evidence_ids: list[str], labels: Mapping[str, str]) -> str:
    groups: dict[str, list[str]] = {}
    for eid in evidence_ids:
        groups.setdefault(labels[eid], []).append(eid)
    if len(groups) == 1:
        (label,) = groups
        return f"STATUS: {label} (rows of {', '.join(evidence_ids)})."
    parts = [f"{', '.join(ids)}: {label}" for label, ids in groups.items()]
    return (
        "STATUS: MIXED RECORD TYPES — each row keeps the status of its evidence record. "
        + "; ".join(parts)
        + "."
    )


def real_source_terms(
    fragment_rows: Mapping[str, list[dict[str, Any]]],
    real_sources: Mapping[str, Any],
) -> dict[tuple[str, str], str]:
    """(kind, log ID) -> licence and attribution sentence for the real track's rows.

    Taken from the real track's own source records (``provenance_real.json`` sources:
    ``licence`` and ``attribution``) of every source the log's rows cite, so the
    manifest states exactly what the document texts state. A log whose rows cite
    sources with different terms, or a source without them, stops the build.
    """
    cited: dict[tuple[str, str], set[str]] = {}
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
            if not ids:
                raise BuildError(f"real row {record_id(row)} cites no source_id")
            cited.setdefault(key, set()).update(ids)
    out: dict[tuple[str, str], str] = {}
    for key, ids in sorted(cited.items()):
        terms = set()
        for source_id in sorted(ids):
            entry = real_sources.get(source_id)
            if (
                not isinstance(entry, Mapping)
                or not entry.get("licence")
                or not entry.get("attribution")
            ):
                raise BuildError(
                    f"real source {source_id!r} has no licence/attribution record"
                )
            terms.add((entry["licence"], entry["attribution"]))
        if len(terms) != 1:
            raise BuildError(
                f"{key[0]} log {key[1]}: its rows' sources state {len(terms)} different "
                "licence/attribution terms"
            )
        ((licence, attribution),) = terms
        out[key] = (
            f"Rows are real public data extracts; licence: {licence}. {attribution}"
        )
    return out


def log_entries(
    assets: Mapping[str, list[dict[str, Any]]],
    rooms: Mapping[str, list[dict[str, Any]]],
    real_fragment: Mapping[str, Any],
    labels: Mapping[str, str],
    files: Mapping[str, bytes],
    real_terms: Mapping[tuple[str, str], str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    real_assets = {e["asset_id"]: e for e in real_fragment.get("asset_logs", [])}
    real_rooms = {e["room_id"]: e for e in real_fragment.get("control_logs", [])}

    def notes(
        meta: Mapping[str, Any],
        real: Mapping[str, Any] | None,
        evidence_ids: list[str],
        key: tuple[str, str],
    ) -> tuple[str, str]:
        clock = dict(meta["clock"])
        source = dict(meta["source"])
        if real is not None:
            (eid,) = real["evidence_ids"]
            if key not in real_terms:
                raise BuildError(f"{key[0]} log {key[1]}: no real rows to attribute")
            clock[eid] = real["clock_note"]
            source[eid] = f"{real['source_note']} {real_terms[key]}"
        missing = [e for e in evidence_ids if e not in clock or e not in source]
        if missing:
            raise BuildError(f"no clock/source note for evidence {missing}")
        clock_note = (
            LOG_HEADER_NOTE
            + " "
            + " ".join(f"{eid} rows — {clock[eid]}" for eid in evidence_ids)
        )
        source_note = " ".join(f"{eid}: {source[eid]}" for eid in evidence_ids)
        return clock_note, source_note

    asset_entries = []
    for asset_id, rows in assets.items():
        meta = ASSET_LOGS[asset_id]
        real = real_assets.get(asset_id)
        evidence_ids = sorted({r["evidence_id"] for r in rows})
        clock_note, source_note = notes(meta, real, evidence_ids, ("asset", asset_id))
        file = f"{ASSET_LOG_DIR}/{asset_id}.jsonl"
        asset_entries.append(
            {
                "asset_id": asset_id,
                "title": meta["title"],
                "owner": meta["owner"],
                "signals": _ordered_signals(rows, real["signals"] if real else []),
                "clock_note": clock_note,
                "evidence_ids": evidence_ids,
                "status": _status(evidence_ids, labels),
                "source_note": source_note,
                "file": file,
                "sha256": sha256_bytes(files[file]),
            }
        )
    room_entries = []
    for room_id, rows in rooms.items():
        meta = CONTROL_LOGS[room_id]
        real = real_rooms.get(room_id)
        evidence_ids = sorted({r["evidence_id"] for r in rows})
        clock_note, source_note = notes(meta, real, evidence_ids, ("control", room_id))
        file = f"{CONTROL_LOG_DIR}/{room_id}.jsonl"
        room_entries.append(
            {
                "room_id": room_id,
                "title": meta["title"],
                "owner": meta["owner"],
                "evidence_ids": evidence_ids,
                "clock_note": clock_note,
                "status": _status(evidence_ids, labels),
                "source_note": source_note,
                "file": file,
                "sha256": sha256_bytes(files[file]),
            }
        )
    return asset_entries, room_entries


# --------------------------------------------------------------------------- witnesses


def load_witnesses(
    recon_fragment: Mapping[str, Any],
) -> tuple[dict[str, bytes], list[dict[str, Any]], dict[str, Any]]:
    """Agent-visible card bytes, manifest entries and private block provenance."""
    listed = {w["persona_id"]: w for w in recon_fragment["witnesses"]}
    present = sorted(p.stem for p in WITNESS_SOURCE_DIR.glob("*.json"))
    if present != sorted(listed):
        raise BuildError(
            f"witness source cards {present} differ from the recon fragment "
            f"{sorted(listed)}"
        )
    visible: dict[str, bytes] = {}
    entries = []
    private: dict[str, Any] = {}
    for persona_id in present:
        source_path = WITNESS_SOURCE_DIR / f"{persona_id}.json"
        source_bytes = source_path.read_bytes()
        card = json.loads(source_bytes)
        claimed = listed[persona_id].get("source_sha256_with_provenance")
        if claimed is not None and claimed != sha256_bytes(source_bytes):
            raise BuildError(f"witness {persona_id}: recon fragment hash is stale")
        if card.get("persona_id") != persona_id:
            raise BuildError(f"witness {persona_id}: persona_id mismatch")
        blocks = []
        sources = {}
        for block in card["blocks"]:
            refs = block.get("provenance")
            if not isinstance(refs, list) or not refs:
                raise BuildError(
                    f"witness {persona_id} {block.get('response_id')}: no provenance"
                )
            if set(block) != {"response_id", "topics", "response_text", "provenance"}:
                raise BuildError(f"witness {persona_id}: unexpected block keys")
            blocks.append({k: v for k, v in block.items() if k != "provenance"})
            sources[block["response_id"]] = {
                "topics": block["topics"],
                "sources": refs,
            }
        public = {k: v for k, v in card.items() if k != "blocks"}
        public["blocks"] = blocks
        file = f"{WITNESS_DIR}/{persona_id}.json"
        data = dumps_sorted(public, indent=2)
        visible[file] = data
        entries.append(
            {
                "persona_id": persona_id,
                "role": card["role"],
                "organisation": card["organisation"],
                "evidence_id": card["evidence_id"],
                "file": file,
                "sha256": sha256_bytes(data),
            }
        )
        private[persona_id] = {
            "file": file,
            "source_card": rel(source_path),
            "source_card_sha256": sha256_bytes(source_bytes),
            "evidence_id": card["evidence_id"],
            "status": card.get("status"),
            "blocks": sources,
        }
    return visible, entries, private


# --------------------------------------------------------------------------- data returns


def load_data_returns(doc_ids: set[str]) -> list[dict[str, Any]]:
    raw = read_json(DATA_RETURNS_FRAGMENT)
    out = []
    for item in raw:
        entry = {
            "party": item["party"],
            "data_type": item["data_type"],
            "status": item["status"],
        }
        if item.get("evidence_id") is not None:
            if item["evidence_id"] not in doc_ids:
                raise BuildError(f"data return names unknown {item['evidence_id']!r}")
            entry["evidence_id"] = item["evidence_id"]
        if item.get("message") is not None:
            entry["message"] = item["message"]
        out.append(entry)
    reachable = {e.get("evidence_id") for e in out if e["status"] == "available"}
    for doc_id in DATA_RETURN_ONLY:
        if doc_id not in reachable:
            raise BuildError(f"{doc_id} is data-return-only but no return names it")
    return sorted(out, key=lambda e: (e["party"], e["data_type"]))


# --------------------------------------------------------------------------- provenance


def _row_fragment_hashes(parts: Mapping[str, Any]) -> dict[str, str]:
    out = {}
    for name, info in parts["real"]["rows"].items():
        out[name] = info["sha256"]
    out[Path(parts["digitise"]["rows_fragment"]["file"]).name] = parts["digitise"][
        "rows_fragment"
    ]["sha256"]
    for name, info in parts["recon"]["row_fragments"].items():
        out[name] = info["sha256"]
    return out


def merged_sources(parts: Mapping[str, Any]) -> dict[str, Any]:
    """source_id -> {sha256?, parts: {track: entry}}; a shared ID must pin one hash."""
    out: dict[str, Any] = {}
    for track in sorted(parts):
        for source_id, entry in sorted(parts[track]["sources"].items()):
            slot = out.setdefault(source_id, {"parts": {}})
            digest = entry.get("sha256") if isinstance(entry, dict) else None
            if digest is not None:
                if slot.get("sha256", digest) != digest:
                    raise BuildError(
                        f"source {source_id}: tracks pin different sha256 values"
                    )
                slot["sha256"] = digest
            slot["parts"][track] = entry
    return out


def merged_documents(
    parts: Mapping[str, Any], owners: Mapping[str, str], texts: Mapping[str, bytes]
) -> dict[str, Any]:
    out = {}
    for doc_id, track in sorted(owners.items()):
        doc = parts[track]["documents"].get(doc_id)
        if doc is None:
            raise BuildError(f"{doc_id}: no provenance in the {track} part")
        if doc.get("text_sha256") != sha256_bytes(texts[doc_id]):
            raise BuildError(
                f"{doc_id}: provenance text_sha256 does not match the text"
            )
        out[doc_id] = {"track": track, **doc}
    for track, part in parts.items():
        extra = sorted(set(part["documents"]) - set(owners))
        if extra:
            raise BuildError(f"{track} provenance covers unknown documents {extra}")
    return out


PART_SECTIONS = {
    "real": ("documents", "sources", "rows"),
    "digitise": ("documents", "sources", "rows_fragment"),
    "recon": ("documents", "sources", "witnesses", "row_fragments", "data_returns"),
}


def build() -> dict[Path, bytes]:
    fragments = {track: read_json(path) for track, path in FRAGMENTS.items()}
    part_bytes = {track: path.read_bytes() for track, path in PROVENANCE_PARTS.items()}
    parts = {track: json.loads(data) for track, data in part_bytes.items()}

    documents, owners = collect_documents(fragments, parts)
    doc_ids = {d["doc_id"] for d in documents}
    labels = {d["doc_id"]: d["label"] for d in documents}
    texts = {d["doc_id"]: (BUNDLE_DIR / d["text_file"]).read_bytes() for d in documents}

    fragment_rows, fragment_bytes = load_fragment_rows(doc_ids)
    pinned = _row_fragment_hashes(parts)
    for name, data in fragment_bytes.items():
        if pinned.get(name) != sha256_bytes(data):
            raise BuildError(
                f"rows/{name}: sha256 differs from the one its track's provenance pins"
            )
    assets, rooms, row_provenance = merge_logs(fragment_rows)

    outputs: dict[str, bytes] = {}
    for asset_id, rows in assets.items():
        outputs[f"{ASSET_LOG_DIR}/{asset_id}.jsonl"] = dumps_jsonl(rows)
    for room_id, rows in rooms.items():
        outputs[f"{CONTROL_LOG_DIR}/{room_id}.jsonl"] = dumps_jsonl(rows)
    asset_entries, room_entries = log_entries(
        assets,
        rooms,
        fragments["real"],
        labels,
        outputs,
        real_source_terms(fragment_rows, parts["real"]["sources"]),
    )

    witness_bytes, witness_entries, witness_provenance = load_witnesses(
        fragments["recon"]
    )
    outputs.update(witness_bytes)
    witness_ids = {w["evidence_id"] for w in witness_entries}
    labels_all = dict(labels)
    for entry in witness_entries:
        status = witness_provenance[entry["persona_id"]]["status"] or ""
        labels_all[entry["evidence_id"]] = status.removeprefix("STATUS: ")
    clash = sorted(witness_ids & doc_ids)
    if clash:
        raise BuildError(f"witness evidence ID(s) {clash} collide with documents")

    data_returns = load_data_returns(doc_ids)

    manifest = {
        "manifest_version": 2,
        "bundle_id": BUNDLE_ID,
        "bundle_version": BUNDLE_VERSION,
        "categories": list(CATEGORY_ORDER),
        "documents": documents,
        "asset_logs": asset_entries,
        "control_logs": room_entries,
        "witnesses": witness_entries,
        "data_returns": data_returns,
    }
    used = {d["category"] for d in documents}
    if used != set(CATEGORY_ORDER):
        raise BuildError(f"categories in use {sorted(used)} != {list(CATEGORY_ORDER)}")
    manifest_bytes = dumps_pretty(manifest)
    outputs["manifest.json"] = manifest_bytes

    bundle_files = {}
    for doc in documents:
        bundle_files.update(doc["sha256"])
    for name, data in outputs.items():
        if name != "manifest.json":
            bundle_files[name] = sha256_bytes(data)

    recon_returns = parts["recon"]["data_returns"]
    provenance = {
        "schema": "gb-2019-system-response/provenance/1",
        "bundle_id": BUNDLE_ID,
        "bundle_version": BUNDLE_VERSION,
        "generated_by": GENERATED_BY,
        "verified_by": VERIFIED_BY,
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "value_statuses": list(VALUE_STATUSES),
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
        "sources": merged_sources(parts),
        "documents": merged_documents(parts, owners, texts),
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
            "fragment": rel(DATA_RETURNS_FRAGMENT),
            "fragment_sha256": sha256_bytes(DATA_RETURNS_FRAGMENT.read_bytes()),
            "entries": data_returns,
            "not_held_basis": recon_returns.get("not_held_basis", []),
            "note": recon_returns.get("note"),
        },
        "integration": {
            "categories": CATEGORIES,
            "data_return_only": list(DATA_RETURN_ONLY),
            "row_order": "index_time_utc instant, then event_id/entry_id",
            "stripped_from_agent_files": ["kind", "provenance"],
        },
        "files": dict(sorted(bundle_files.items())),
    }

    result = {BUNDLE_DIR / name: data for name, data in sorted(outputs.items())}
    result[PROVENANCE_PATH] = dumps_sorted(provenance)
    return result


def owned_stale_files(outputs: Mapping[Path, bytes]) -> list[Path]:
    """Files in directories this step owns that a fresh build would not write."""
    stale = []
    for sub in (ASSET_LOG_DIR, CONTROL_LOG_DIR, WITNESS_DIR):
        folder = BUNDLE_DIR / sub
        if folder.is_dir():
            for path in sorted(folder.iterdir()):
                if path not in outputs:
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
    except BuildError as exc:
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
            path.unlink()
    for path in sorted(outputs):
        flag = "STALE " if args.check and path in differ else ""
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
