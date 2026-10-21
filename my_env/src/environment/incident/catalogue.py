"""Hash-verified evidence catalogue.

The catalogue is the only route from a document ID to bundle files. It loads
``bundle/manifest.json``, checks its structure, and verifies the SHA-256 of every
artifact before anything is served. Any problem raises :class:`CatalogueError`; there
is no partial or best-effort mode (fail closed).

Listing order is deterministic (documents sorted by ID) and pagination uses an opaque,
deterministic cursor.

Two manifest versions are understood. A manifest without ``manifest_version`` is the
MVP format (version 1: documents only, the fixed :data:`CATEGORIES`), loaded exactly
as before. ``"manifest_version": 2`` adds asset logs, control-room logs, witness cards
and the data-return registry (see :mod:`environment.incident.system_bundle`); those
parts are then available as :attr:`Catalogue.sources`.
"""

from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import io
import json
import os
import re
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from environment.incident.locators import LocatorError, parse_iso_instant
from environment.incident.paths import DEFAULT_BUNDLE_DIR, MANIFEST_NAME

if TYPE_CHECKING:
    from environment.incident.system_bundle import SystemSources

__all__ = [
    "CATEGORIES",
    "DEFAULT_PAGE_SIZE",
    "Artifact",
    "Catalogue",
    "CatalogueError",
    "CursorError",
    "Document",
    "TimeseriesInfo",
    "render_numbered",
    "sha256_bytes",
]

CATEGORIES: tuple[str, ...] = (
    "measurement_data",
    "network_records",
    "generator_records",
    "personnel_accounts",
)
DEFAULT_PAGE_SIZE = 50

_DOC_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_ARTIFACT_BYTES = _MAX_ARTIFACT_BYTES
_V2_SECTIONS = ("asset_logs", "control_logs", "witnesses", "data_returns")


class CatalogueError(Exception):
    """The evidence bundle could not be loaded or failed verification."""


class CursorError(ValueError):
    """A ``list_documents`` cursor is malformed or belongs to another listing."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render_numbered(lines: tuple[str, ...] | list[str]) -> str:
    """Render text lines with ``%4d | `` line numbers (1-based)."""
    return "\n".join(f"{number:4d} | {line}" for number, line in enumerate(lines, 1))


@dataclass(frozen=True)
class TimeseriesInfo:
    time_column: str
    value_column: str
    unit: str
    first: datetime
    last: datetime
    rows: int
    interval_s: float
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """The manifest metadata as published to the agent."""
        return dict(self.raw)


@dataclass(frozen=True)
class Artifact:
    file: str
    media_type: str
    description: str
    sha256: str
    bytes: int
    timeseries: TimeseriesInfo | None = None

    @property
    def name(self) -> str:
        return PurePosixPath(self.file).name


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    owner: str
    date: str
    category: str
    text_file: str
    artifacts: tuple[Artifact, ...]
    text: str
    lines: tuple[str, ...]

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def timeseries(self) -> TimeseriesInfo | None:
        for artifact in self.artifacts:
            if artifact.timeseries is not None:
                return artifact.timeseries
        return None

    @property
    def text_artifact(self) -> Artifact:
        for artifact in self.artifacts:
            if artifact.file == self.text_file:
                return artifact
        raise CatalogueError(
            f"{self.doc_id}: text file is not an artifact"
        )  # pragma: no cover

    def summary(self) -> dict[str, str]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "owner": self.owner,
            "date": self.date,
            "category": self.category,
        }

    def numbered_text(self) -> str:
        return render_numbered(self.lines)


def split_lines(text: str) -> tuple[str, ...]:
    """Split document text into lines the way line locators count them (LF only)."""
    if not text:
        return ()
    if text.endswith("\n"):
        text = text[:-1]
    return tuple(text.split("\n"))


def _require_str(obj: dict[str, Any], key: str, where: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CatalogueError(f"{where}: '{key}' must be a non-empty string")
    return value


def check_relative_path(rel: Any, where: str) -> PurePosixPath:
    if not isinstance(rel, str) or not rel or "\\" in rel or "\x00" in rel:
        raise CatalogueError(f"{where}: invalid artifact path {rel!r}")
    path = PurePosixPath(rel)
    if path.is_absolute() or any(part in ("", ".", "..") for part in rel.split("/")):
        raise CatalogueError(
            f"{where}: artifact path {rel!r} must be a plain relative path"
        )
    return path


_check_relative_path = check_relative_path  # former private name


def read_regular_file_nofollow(root: Path, rel: PurePosixPath, max_bytes: int) -> bytes:
    """Read ``root/rel`` refusing symlinks at every component and non-regular files."""
    try:
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    except OSError as exc:
        raise CatalogueError(f"cannot open bundle directory {root}: {exc}") from None
    fds = [root_fd]
    try:
        dir_fd = root_fd
        parts = rel.parts
        for part in parts[:-1]:
            try:
                dir_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=dir_fd,
                )
            except OSError as exc:
                raise CatalogueError(
                    f"{rel}: cannot open directory {part!r}: {exc}"
                ) from None
            fds.append(dir_fd)
        try:
            fd = os.open(
                parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd
            )
        except OSError as exc:
            raise CatalogueError(f"{rel}: cannot open file: {exc}") from None
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise CatalogueError(f"{rel}: not a regular file")
            if info.st_size > max_bytes:
                raise CatalogueError(f"{rel}: larger than {max_bytes} bytes")
            data = handle.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise CatalogueError(f"{rel}: larger than {max_bytes} bytes")
            return data
    finally:
        for fd_ in reversed(fds):
            os.close(fd_)


def _parse_timeseries(raw: Any, where: str) -> TimeseriesInfo:
    if not isinstance(raw, dict):
        raise CatalogueError(f"{where}: 'timeseries' must be an object")
    try:
        first = parse_iso_instant(_require_str(raw, "first", where))
        last = parse_iso_instant(_require_str(raw, "last", where))
    except LocatorError as exc:
        raise CatalogueError(f"{where}: {exc}") from None
    rows = raw.get("rows")
    interval = raw.get("interval_s")
    if not isinstance(rows, int) or isinstance(rows, bool) or rows < 1:
        raise CatalogueError(f"{where}: 'rows' must be a positive integer")
    if (
        not isinstance(interval, (int, float))
        or isinstance(interval, bool)
        or interval <= 0
    ):
        raise CatalogueError(f"{where}: 'interval_s' must be a positive number")
    if first > last:
        raise CatalogueError(f"{where}: 'first' is after 'last'")
    return TimeseriesInfo(
        time_column=_require_str(raw, "time_column", where),
        value_column=_require_str(raw, "value_column", where),
        unit=_require_str(raw, "unit", where),
        first=first,
        last=last,
        rows=rows,
        interval_s=float(interval),
        raw=dict(raw),
    )


def _check_timeseries_csv(data: bytes, series: TimeseriesInfo, where: str) -> None:
    """The CSV must agree with its manifest metadata (columns, row count, first/last)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CatalogueError(f"{where}: CSV is not valid UTF-8: {exc}") from None
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise CatalogueError(f"{where}: CSV is empty") from None
    if series.time_column not in header or series.value_column not in header:
        raise CatalogueError(
            f"{where}: CSV header {header} lacks '{series.time_column}' or "
            f"'{series.value_column}'"
        )
    time_index = header.index(series.time_column)
    rows = [row for row in reader if row]
    if len(rows) != series.rows:
        raise CatalogueError(
            f"{where}: CSV has {len(rows)} data rows but the manifest says {series.rows}"
        )
    try:
        first = parse_iso_instant(rows[0][time_index])
        last = parse_iso_instant(rows[-1][time_index])
    except (LocatorError, IndexError) as exc:
        raise CatalogueError(f"{where}: CSV timestamps unreadable: {exc}") from None
    if first != series.first or last != series.last:
        raise CatalogueError(
            f"{where}: CSV spans {first.isoformat()}..{last.isoformat()} but the manifest "
            f"says {series.first.isoformat()}..{series.last.isoformat()}"
        )


class Catalogue:
    """The verified, read-only catalogue of agent-visible documents."""

    def __init__(
        self,
        bundle_dir: Path,
        bundle_id: str,
        bundle_version: str,
        manifest_sha256: str,
        documents: list[Document],
        *,
        categories: tuple[str, ...] = CATEGORIES,
        sources: SystemSources | None = None,
        manifest_version: int = 1,
    ) -> None:
        self.bundle_dir = bundle_dir
        self.bundle_id = bundle_id
        self.bundle_version = bundle_version
        self.manifest_sha256 = manifest_sha256
        self.categories = tuple(categories)
        self.sources = sources
        self.manifest_version = manifest_version
        ordered = sorted(documents, key=lambda d: d.doc_id)
        self._documents: dict[str, Document] = {d.doc_id: d for d in ordered}

    # -- loading --------------------------------------------------------------
    @classmethod
    def load(cls, bundle_dir: Path | str = DEFAULT_BUNDLE_DIR) -> Catalogue:
        """Load and verify a bundle; raise :class:`CatalogueError` on any problem."""
        bundle = Path(bundle_dir)
        try:
            info = os.lstat(bundle)
        except OSError as exc:
            raise CatalogueError(
                f"bundle directory {bundle} is unavailable: {exc}"
            ) from None
        if not stat.S_ISDIR(info.st_mode):
            raise CatalogueError(f"bundle path {bundle} is not a real directory")

        manifest_bytes = read_regular_file_nofollow(
            bundle, PurePosixPath(MANIFEST_NAME), 4 * 1024 * 1024
        )
        try:
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CatalogueError(f"manifest is not valid JSON: {exc}") from None
        if not isinstance(manifest, dict):
            raise CatalogueError("manifest must be a JSON object")
        version = manifest.get("manifest_version")
        if version is not None:
            if version != 2 or isinstance(version, bool):
                raise CatalogueError(
                    f"manifest: unsupported manifest_version {version!r} (expected 2, "
                    "or no manifest_version for the MVP format)"
                )
            from environment.incident.system_bundle import load_v2

            return load_v2(cls, bundle, manifest, sha256_bytes(manifest_bytes))
        present = [key for key in _V2_SECTIONS if key in manifest]
        if present:
            raise CatalogueError(
                f'manifest has {", ".join(present)} but no "manifest_version": 2'
            )
        bundle_id = _require_str(manifest, "bundle_id", "manifest")
        bundle_version = _require_str(manifest, "bundle_version", "manifest")
        raw_docs = manifest.get("documents")
        if not isinstance(raw_docs, list) or not raw_docs:
            raise CatalogueError("manifest: 'documents' must be a non-empty list")

        documents: list[Document] = []
        seen: set[str] = set()
        for index, raw in enumerate(raw_docs):
            doc = cls._load_document(bundle, raw, f"documents[{index}]")
            if doc.doc_id in seen:
                raise CatalogueError(f"duplicate doc_id {doc.doc_id!r}")
            seen.add(doc.doc_id)
            documents.append(doc)
        return cls(
            bundle_dir=bundle,
            bundle_id=bundle_id,
            bundle_version=bundle_version,
            manifest_sha256=sha256_bytes(manifest_bytes),
            documents=documents,
        )

    @staticmethod
    def _load_document(
        bundle: Path,
        raw: Any,
        where: str,
        categories: tuple[str, ...] = CATEGORIES,
    ) -> Document:
        if not isinstance(raw, dict):
            raise CatalogueError(f"{where}: must be an object")
        doc_id = _require_str(raw, "doc_id", where)
        if not _DOC_ID_RE.match(doc_id):
            raise CatalogueError(f"{where}: invalid doc_id {doc_id!r}")
        where = f"document {doc_id}"
        category = _require_str(raw, "category", where)
        if category not in categories:
            raise CatalogueError(f"{where}: unknown category {category!r}")
        text_file = _require_str(raw, "text_file", where)
        raw_artifacts = raw.get("artifacts")
        hashes = raw.get("sha256")
        if not isinstance(raw_artifacts, list) or not raw_artifacts:
            raise CatalogueError(f"{where}: 'artifacts' must be a non-empty list")
        if not isinstance(hashes, dict):
            raise CatalogueError(f"{where}: 'sha256' must be an object")

        files = []
        for item in raw_artifacts:
            if not isinstance(item, dict):
                raise CatalogueError(f"{where}: each artifact must be an object")
            files.append(_require_str(item, "file", where))
        if len(set(files)) != len(files):
            raise CatalogueError(f"{where}: duplicate artifact files")
        names = [PurePosixPath(f).name for f in files]
        if len(set(names)) != len(names):
            raise CatalogueError(f"{where}: artifact file names must be unique")
        if set(hashes) != set(files):
            raise CatalogueError(
                f"{where}: 'sha256' must cover exactly the artifact files "
                f"(artifacts {sorted(files)}, hashes {sorted(hashes)})"
            )
        if text_file not in files:
            raise CatalogueError(f"{where}: text_file {text_file!r} is not an artifact")

        artifacts: list[Artifact] = []
        text: str | None = None
        series_count = 0
        for item in raw_artifacts:
            rel_str = item["file"]
            rel = check_relative_path(rel_str, where)
            expected = hashes[rel_str]
            if not isinstance(expected, str) or not _SHA256_RE.match(expected):
                raise CatalogueError(f"{where}: bad sha256 for {rel_str}")
            data = read_regular_file_nofollow(bundle, rel, _MAX_ARTIFACT_BYTES)
            actual = sha256_bytes(data)
            if actual != expected:
                raise CatalogueError(
                    f"{where}: sha256 mismatch for {rel_str} (manifest {expected[:12]}..., "
                    f"file {actual[:12]}...)"
                )
            series = None
            if item.get("timeseries") is not None:
                series_count += 1
                series = _parse_timeseries(item["timeseries"], f"{where} {rel_str}")
                _check_timeseries_csv(data, series, f"{where} {rel_str}")
            if rel_str == text_file:
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise CatalogueError(
                        f"{where}: text file is not UTF-8: {exc}"
                    ) from None
            artifacts.append(
                Artifact(
                    file=rel_str,
                    media_type=_require_str(item, "media_type", where),
                    description=_require_str(item, "description", where),
                    sha256=expected,
                    bytes=len(data),
                    timeseries=series,
                )
            )
        if series_count > 1:
            raise CatalogueError(
                f"{where}: at most one time-series artifact is allowed"
            )
        assert text is not None
        return Document(
            doc_id=doc_id,
            title=_require_str(raw, "title", where),
            owner=_require_str(raw, "owner", where),
            date=_require_str(raw, "date", where),
            category=category,
            text_file=text_file,
            artifacts=tuple(artifacts),
            text=text,
            lines=split_lines(text),
        )

    # -- access ---------------------------------------------------------------
    @property
    def bundle_sha256(self) -> str:
        """SHA-256 of the manifest, which itself pins every artifact hash."""
        return self.manifest_sha256

    def ids(self) -> list[str]:
        return list(self._documents)

    def get(self, doc_id: str) -> Document | None:
        return self._documents.get(doc_id)

    def __contains__(self, doc_id: object) -> bool:
        return doc_id in self._documents

    def __iter__(self) -> Iterator[Document]:
        return iter(self._documents.values())

    def __len__(self) -> int:
        return len(self._documents)

    def read_artifact(self, artifact: Artifact) -> bytes:
        """Read an artifact again, re-verifying its hash (fails closed)."""
        data = read_regular_file_nofollow(
            self.bundle_dir, PurePosixPath(artifact.file), _MAX_ARTIFACT_BYTES
        )
        if sha256_bytes(data) != artifact.sha256:
            raise CatalogueError(
                f"sha256 mismatch for {artifact.file}; bundle modified"
            )
        return data

    def verify(self) -> None:
        """Re-verify every artifact (and, in a v2 bundle, every log and card) on disk."""
        for doc in self:
            for artifact in doc.artifacts:
                self.read_artifact(artifact)
        if self.sources is not None:
            for rel, digest in self.sources.files:
                data = read_regular_file_nofollow(
                    self.bundle_dir, PurePosixPath(rel), _MAX_ARTIFACT_BYTES
                )
                if sha256_bytes(data) != digest:
                    raise CatalogueError(f"sha256 mismatch for {rel}; bundle modified")

    # -- manifest v2 ------------------------------------------------------------
    @property
    def is_v2(self) -> bool:
        return self.sources is not None

    def is_listed(self, doc_id: str) -> bool:
        """Whether ``doc_id`` appears in ``list_documents`` and can be requested by ID
        without first being obtained (v2 ``access: "data_return"`` documents cannot)."""
        if doc_id not in self._documents:
            return False
        if self.sources is None:
            return True
        return self.sources.access.get(doc_id) == "catalogue"

    def listed_ids(self) -> list[str]:
        return [doc_id for doc_id in self._documents if self.is_listed(doc_id)]

    def citation_target(self, evidence_id: str) -> Any:
        """What a citation's ``evidence_id`` resolves to, or ``None``.

        Version 1: the :class:`Document`. Version 2: an
        :class:`environment.incident.system_bundle.EvidenceTarget` covering the
        document (if any) and the records (events, entries, responses) of that ID.
        """
        if self.sources is None:
            return self.get(evidence_id)
        from environment.incident.system_bundle import evidence_target

        return evidence_target(self.sources, evidence_id, self.get(evidence_id))

    def citable_ids(self, *, public: bool = True) -> list[str]:
        """Evidence IDs a citation may name (``public``: without unlisted documents,
        for messages to the agent; unlisted documents are still accepted)."""
        if self.sources is None:
            return self.ids()
        docs = self.listed_ids() if public else self.ids()
        return sorted(set(docs) | set(self.sources.evidence_records))

    # -- listing --------------------------------------------------------------
    def _encode_cursor(self, category: str | None, offset: int) -> str:
        payload = json.dumps(
            {"c": category or "", "o": offset, "v": self.bundle_version},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    def _decode_cursor(self, cursor: str, category: str | None) -> int:
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
            offset = payload["o"]
            same_listing = payload["c"] == (category or "")
            same_version = payload["v"] == self.bundle_version
        except (binascii.Error, UnicodeDecodeError, ValueError, KeyError, TypeError):
            raise CursorError(
                "cursor is not valid; pass a next_cursor value unchanged"
            ) from None
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise CursorError("cursor is not valid; pass a next_cursor value unchanged")
        if not same_listing or not same_version:
            raise CursorError(
                "cursor belongs to a different listing; repeat the same category filter"
            )
        return offset

    def list_page(
        self,
        category: str | None = None,
        cursor: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[Document], str | None]:
        """One page of documents (sorted by ID) and the cursor of the next page."""
        if category is not None and category not in self.categories:
            raise ValueError(f"unknown category {category!r}")
        docs = [
            d
            for d in self
            if (category is None or d.category == category) and self.is_listed(d.doc_id)
        ]
        offset = self._decode_cursor(cursor, category) if cursor else 0
        if offset > len(docs):
            raise CursorError("cursor is past the end of the listing")
        page = docs[offset : offset + page_size]
        end = offset + len(page)
        next_cursor = self._encode_cursor(category, end) if end < len(docs) else None
        return page, next_cursor
