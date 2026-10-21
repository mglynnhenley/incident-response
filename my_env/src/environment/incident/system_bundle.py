"""Manifest v2: the system-response bundle (documents + logs + witnesses + returns).

A v2 manifest declares ``"manifest_version": 2`` and may contain only these keys::

    {
      "manifest_version": 2,
      "bundle_id": "...", "bundle_version": "...",
      "categories": ["..."],                       (optional; else taken from documents)
      "documents": [ MVP document entries, plus optional
                     "access": "catalogue" | "data_return",
                     "party_aliases": [...], "keywords": [...],
                     "label": "<STATUS label of the text; informational>" ],
      "asset_logs":   [{asset_id, title, owner, signals, clock_note, evidence_ids,
                        file, sha256, status?, source_note?}],
      "control_logs": [{room_id, title, owner, evidence_ids, file, sha256,
                        clock_note?, status?, source_note?}],
      "witnesses":    [{persona_id, role, organisation, evidence_id, file, sha256}],
      "data_returns": [{party, data_type, status, evidence_id?, message?}]
    }

``sha256`` of a log or witness file is its hex digest (or ``{file: digest}``). Every
file is read without following symlinks and hash-verified; any problem raises
:class:`CatalogueError` (fail closed). A document with ``access: "data_return"`` is not
listed and is obtained through ``request_data_return``; it must be the evidence of an
available data return. The bundle must contain the R01 frequency series, which
``query_frequency`` serves.

Record IDs (``event_id``, ``entry_id``, ``response_id``) are unique within their kind
across the bundle; each belongs to exactly one evidence ID, which a citation locator
``event:<id>`` / ``entry:<id>`` / ``response:<id>`` must name.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from environment.incident.catalogue import (
    MAX_ARTIFACT_BYTES,
    CatalogueError,
    Document,
    check_relative_path,
    read_regular_file_nofollow,
    sha256_bytes,
)
from environment.incident.logs import (
    AssetLog,
    ControlLog,
    parse_asset_log,
    parse_control_log,
)
from environment.incident.returns import DataReturnRegistry
from environment.incident.schema_v2 import check_keys, require_str_list
from environment.incident.series import (
    FREQUENCY_DOC_ID,
    FrequencySeries,
    parse_frequency_series,
)
from environment.incident.witness import WitnessCard, parse_witness_card

if TYPE_CHECKING:
    from environment.incident.catalogue import Catalogue

__all__ = [
    "ACCESS_MODES",
    "MANIFEST_VERSION",
    "RECORD_KINDS",
    "V2_SECTIONS",
    "EvidenceTarget",
    "SystemSources",
    "evidence_target",
    "load_v2",
]

MANIFEST_VERSION = 2
V2_SECTIONS = ("asset_logs", "control_logs", "witnesses", "data_returns")
DOCUMENT_KEYS = (
    "doc_id",
    "title",
    "owner",
    "date",
    "category",
    "text_file",
    "artifacts",
    "sha256",
)
DOCUMENT_OPTIONAL_KEYS = ("access", "party_aliases", "keywords", "label")
ACCESS_MODES = ("catalogue", "data_return")
RECORD_KINDS = ("event", "entry", "response")
_CATEGORY_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class EvidenceTarget:
    """What a citation's ``evidence_id`` resolves to in a v2 bundle: a document (line,
    time and row locators) and/or records (event, entry and response locators)."""

    doc_id: str
    document: Document | None
    records: Mapping[str, frozenset[str]]
    owners: Mapping[tuple[str, str], str] = field(repr=False)

    @property
    def is_document(self) -> bool:
        return self.document is not None

    @property
    def line_count(self) -> int:
        return self.document.line_count if self.document is not None else 0

    @property
    def timeseries(self) -> Any:
        return self.document.timeseries if self.document is not None else None

    def record_owner(self, kind: str, record_id: str) -> str | None:
        return self.owners.get((kind, record_id))


@dataclass(frozen=True)
class SystemSources:
    asset_logs: dict[str, AssetLog]
    control_logs: dict[str, ControlLog]
    witnesses: dict[str, WitnessCard]
    data_returns: DataReturnRegistry
    frequency: FrequencySeries
    access: dict[str, str]
    match_text: dict[str, tuple[str, str]]
    owners: dict[tuple[str, str], str]
    evidence_records: dict[str, dict[str, frozenset[str]]]
    files: tuple[tuple[str, str], ...]

    def summaries(self) -> dict[str, list[dict[str, Any]]]:
        """Public identifiers for ``list_documents`` (never statuses or contents)."""
        return {
            "asset_logs": [log.summary() for log in self.asset_logs.values()],
            "control_logs": [log.summary() for log in self.control_logs.values()],
            "witnesses": [card.summary() for card in self.witnesses.values()],
            "data_returns": self.data_returns.summaries(),
        }


def _file_hash(entry: Mapping[str, Any], where: str) -> str:
    raw = entry.get("sha256")
    if isinstance(raw, dict):
        if set(raw) != {entry.get("file")}:
            raise CatalogueError(
                f"{where}: 'sha256' must cover exactly the file {entry.get('file')!r}"
            )
        raw = raw[entry["file"]]
    if not isinstance(raw, str) or not _HEX_RE.match(raw):
        raise CatalogueError(f"{where}: 'sha256' must be a lower-case hex digest")
    return raw


def _read_verified(
    bundle: Path, entry: Mapping[str, Any], where: str
) -> tuple[str, bytes, str]:
    rel = entry.get("file")
    path = check_relative_path(rel, where)
    expected = _file_hash(entry, where)
    data = read_regular_file_nofollow(bundle, path, MAX_ARTIFACT_BYTES)
    actual = sha256_bytes(data)
    if actual != expected:
        raise CatalogueError(
            f"{where}: sha256 mismatch for {rel} (manifest {expected[:12]}..., file "
            f"{actual[:12]}...)"
        )
    return str(rel), data, expected


def _section(manifest: Mapping[str, Any], key: str) -> list[Any]:
    raw = manifest.get(key, [])
    if not isinstance(raw, list):
        raise CatalogueError(f"manifest: '{key}' must be a list")
    return raw


def _categories(manifest: Mapping[str, Any], raw_docs: list[Any]) -> tuple[str, ...]:
    if "categories" in manifest:
        categories = require_str_list(manifest, "categories", "manifest")
    else:
        categories = tuple(
            sorted(
                {
                    str(d.get("category"))
                    for d in raw_docs
                    if isinstance(d, dict) and isinstance(d.get("category"), str)
                }
            )
        )
    for category in categories:
        if not _CATEGORY_RE.match(category):
            raise CatalogueError(f"manifest: invalid category {category!r}")
    return categories


def load_v2(
    cls: type[Catalogue], bundle: Path, manifest: dict[str, Any], manifest_sha: str
) -> Catalogue:
    """Build a v2 :class:`Catalogue` (called by ``Catalogue.load``)."""
    check_keys(
        manifest,
        "manifest",
        ("manifest_version", "bundle_id", "bundle_version", "documents"),
        ("categories", *V2_SECTIONS),
    )
    bundle_id = manifest.get("bundle_id")
    bundle_version = manifest.get("bundle_version")
    for key, value in (("bundle_id", bundle_id), ("bundle_version", bundle_version)):
        if not isinstance(value, str) or not value.strip():
            raise CatalogueError(f"manifest: '{key}' must be a non-empty string")
    raw_docs = manifest.get("documents")
    if not isinstance(raw_docs, list) or not raw_docs:
        raise CatalogueError("manifest: 'documents' must be a non-empty list")
    categories = _categories(manifest, raw_docs)

    documents: list[Document] = []
    access: dict[str, str] = {}
    match_text: dict[str, tuple[str, str]] = {}
    for index, raw in enumerate(raw_docs):
        where = f"documents[{index}]"
        check_keys(raw, where, DOCUMENT_KEYS, DOCUMENT_OPTIONAL_KEYS)
        doc = cls._load_document(bundle, raw, where, categories)
        if doc.doc_id in access:
            raise CatalogueError(f"duplicate doc_id {doc.doc_id!r}")
        mode = raw.get("access", "catalogue")
        if mode not in ACCESS_MODES:
            raise CatalogueError(
                f"document {doc.doc_id}: access {mode!r} is not one of "
                f"{', '.join(ACCESS_MODES)}"
            )
        aliases = (
            require_str_list(raw, "party_aliases", f"document {doc.doc_id}")
            if "party_aliases" in raw
            else ()
        )
        keywords = (
            require_str_list(raw, "keywords", f"document {doc.doc_id}")
            if "keywords" in raw
            else ()
        )
        access[doc.doc_id] = mode
        # Matcher doc-tokens-2: the description is matched against the ID, title and
        # keywords only; the category is shared by many documents and would make a
        # single category word select or tie documents that do not fit the request.
        match_text[doc.doc_id] = (
            " ".join((doc.owner, *aliases)),
            " ".join((doc.doc_id, doc.title, *keywords)),
        )
        documents.append(doc)
    by_id = {doc.doc_id: doc for doc in documents}
    if not any(mode == "catalogue" for mode in access.values()):
        raise CatalogueError("manifest: no document is listed in the catalogue")

    files: list[tuple[str, str]] = []
    owners: dict[tuple[str, str], str] = {}

    def claim(kind: str, record_id: str, evidence_id: str, where: str) -> None:
        if (kind, record_id) in owners:
            raise CatalogueError(f"{where}: duplicate {kind} ID {record_id!r}")
        owners[(kind, record_id)] = evidence_id

    asset_logs: dict[str, AssetLog] = {}
    for index, raw in enumerate(_section(manifest, "asset_logs")):
        where = f"asset_logs[{index}]"
        entry = check_keys(
            raw,
            where,
            (
                "asset_id",
                "title",
                "owner",
                "signals",
                "clock_note",
                "evidence_ids",
                "file",
                "sha256",
            ),
            ("status", "source_note"),
        )
        rel, data, digest = _read_verified(bundle, entry, where)
        log = parse_asset_log(entry, data, digest, where)
        if log.asset_id in asset_logs:
            raise CatalogueError(f"{where}: duplicate asset_id {log.asset_id!r}")
        for row in log.rows:
            claim("event", row.record_id, row.evidence_id, f"{where} {rel}")
        asset_logs[log.asset_id] = log
        files.append((rel, digest))

    control_logs: dict[str, ControlLog] = {}
    for index, raw in enumerate(_section(manifest, "control_logs")):
        where = f"control_logs[{index}]"
        entry = check_keys(
            raw,
            where,
            ("room_id", "title", "owner", "evidence_ids", "file", "sha256"),
            ("clock_note", "status", "source_note"),
        )
        rel, data, digest = _read_verified(bundle, entry, where)
        log = parse_control_log(entry, data, digest, where)
        if log.room_id in control_logs:
            raise CatalogueError(f"{where}: duplicate room_id {log.room_id!r}")
        for row in log.rows:
            claim("entry", row.record_id, row.evidence_id, f"{where} {rel}")
        control_logs[log.room_id] = log
        files.append((rel, digest))

    witnesses: dict[str, WitnessCard] = {}
    for index, raw in enumerate(_section(manifest, "witnesses")):
        where = f"witnesses[{index}]"
        entry = check_keys(
            raw,
            where,
            ("persona_id", "role", "organisation", "evidence_id", "file", "sha256"),
        )
        rel, data, digest = _read_verified(bundle, entry, where)
        card = parse_witness_card(entry, data, digest, where)
        if card.persona_id in witnesses:
            raise CatalogueError(f"{where}: duplicate persona_id {card.persona_id!r}")
        for block in card.blocks:
            claim("response", block.response_id, card.evidence_id, f"{where} {rel}")
        witnesses[card.persona_id] = card
        files.append((rel, digest))

    returns = DataReturnRegistry.parse(
        _section(manifest, "data_returns"), set(by_id), "data_returns"
    )
    reachable = returns.evidence_ids()
    for doc_id, mode in access.items():
        if mode == "data_return" and doc_id not in reachable:
            raise CatalogueError(
                f"document {doc_id}: access 'data_return' but no available data "
                "return names it, so it could never be obtained"
            )

    frequency_doc = by_id.get(FREQUENCY_DOC_ID)
    if frequency_doc is None or frequency_doc.timeseries is None:
        raise CatalogueError(
            f"manifest: a v2 bundle must contain document {FREQUENCY_DOC_ID} with its "
            "time series (served by query_frequency)"
        )
    if access[FREQUENCY_DOC_ID] != "catalogue":
        raise CatalogueError(f"document {FREQUENCY_DOC_ID} must be listed")
    series_artifact = next(
        a for a in frequency_doc.artifacts if a.timeseries is not None
    )
    frequency = parse_frequency_series(
        frequency_doc,
        read_regular_file_nofollow(
            bundle, PurePosixPath(series_artifact.file), MAX_ARTIFACT_BYTES
        ),
    )

    evidence_records: dict[str, dict[str, set[str]]] = {}
    for (kind, record_id), evidence_id in owners.items():
        evidence_records.setdefault(evidence_id, {k: set() for k in RECORD_KINDS})
        evidence_records[evidence_id][kind].add(record_id)
    frozen_records = {
        evidence_id: {kind: frozenset(ids) for kind, ids in kinds.items()}
        for evidence_id, kinds in evidence_records.items()
    }
    sources = SystemSources(
        asset_logs=dict(sorted(asset_logs.items())),
        control_logs=dict(sorted(control_logs.items())),
        witnesses=dict(sorted(witnesses.items())),
        data_returns=returns,
        frequency=frequency,
        access=access,
        match_text=match_text,
        owners=owners,
        evidence_records=frozen_records,
        files=tuple(sorted(files)),
    )
    return cls(
        bundle_dir=bundle,
        bundle_id=str(bundle_id),
        bundle_version=str(bundle_version),
        manifest_sha256=manifest_sha,
        documents=documents,
        categories=categories,
        sources=sources,
        manifest_version=MANIFEST_VERSION,
    )


def evidence_target(
    sources: SystemSources, evidence_id: str, document: Document | None
) -> EvidenceTarget | None:
    records = sources.evidence_records.get(evidence_id)
    if document is None and records is None:
        return None
    return EvidenceTarget(
        doc_id=evidence_id,
        document=document,
        records=records or {kind: frozenset() for kind in RECORD_KINDS},
        owners=sources.owners,
    )
