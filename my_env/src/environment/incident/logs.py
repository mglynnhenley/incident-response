"""Asset logs and control-room logs (manifest v2): rows, selection and rendering.

Each log is a JSONL file of rows. A row keeps the time **as recorded** with its clock
basis (both always shown first) and an ``index_time_utc`` with its uncertainty, used
only to select rows for a time window (decision 23); the index is a builder
conversion, never a replacement for the recorded time.

Asset row::

    {event_id, evidence_id, asset_id, recorded_time, clock_basis, index_time_utc,
     index_uncertainty_s, signal, value, unit, text, value_status}

Control row::

    {entry_id, evidence_id, room_id, recorded_time, clock_basis, index_time_utc,
     index_uncertainty_s, from, to, channel, text, value_status}

Rows are ordered by (index time, ID) and selected with ``start <= index < end``.
"""

from __future__ import annotations

import bisect
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from environment.incident.catalogue import CatalogueError
from environment.incident.matching import normalise_key
from environment.incident.schema_v2 import (
    EVIDENCE_ID_RE,
    NAME_ID_RE,
    RECORD_ID_RE,
    VALUE_STATUSES,
    check_keys,
    optional_str,
    require_id,
    require_number,
    require_str,
    require_str_list,
    require_utc_instant,
    strict_json_loads,
)

__all__ = [
    "ASSET_COLUMNS",
    "CONTROL_COLUMNS",
    "AssetLog",
    "AssetRow",
    "ControlLog",
    "ControlRow",
    "parse_asset_log",
    "parse_control_log",
    "render_rows",
    "select_rows",
]

ASSET_ROW_KEYS = (
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
)
CONTROL_ROW_KEYS = (
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
)
# Display order: the time as recorded and its clock come first.
ASSET_COLUMNS = (
    "recorded_time",
    "clock_basis",
    "event_id",
    "evidence_id",
    "signal",
    "value",
    "unit",
    "value_status",
    "text",
    "index_time_utc",
    "index_uncertainty_s",
)
CONTROL_COLUMNS = (
    "recorded_time",
    "clock_basis",
    "entry_id",
    "evidence_id",
    "from",
    "to",
    "channel",
    "value_status",
    "text",
    "index_time_utc",
    "index_uncertainty_s",
)
_MAX_ROWS = 100_000


@dataclass(frozen=True)
class AssetRow:
    raw: Mapping[str, Any]
    index_time: datetime

    @property
    def record_id(self) -> str:
        return str(self.raw["event_id"])

    @property
    def evidence_id(self) -> str:
        return str(self.raw["evidence_id"])

    @property
    def signal(self) -> str:
        return str(self.raw["signal"])

    def to_dict(self) -> dict[str, Any]:
        return {key: self.raw[key] for key in ASSET_ROW_KEYS}


@dataclass(frozen=True)
class ControlRow:
    raw: Mapping[str, Any]
    index_time: datetime

    @property
    def record_id(self) -> str:
        return str(self.raw["entry_id"])

    @property
    def evidence_id(self) -> str:
        return str(self.raw["evidence_id"])

    def to_dict(self) -> dict[str, Any]:
        return {key: self.raw[key] for key in CONTROL_ROW_KEYS}


@dataclass(frozen=True)
class AssetLog:
    asset_id: str
    title: str
    owner: str
    signals: tuple[str, ...]
    clock_note: str
    evidence_ids: tuple[str, ...]
    file: str
    sha256: str
    status: str | None
    source_note: str | None
    rows: tuple[AssetRow, ...]

    def summary(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "title": self.title,
            "owner": self.owner,
            "signals": list(self.signals),
            "evidence_ids": list(self.evidence_ids),
        }

    def resolve_signal(self, signal: str) -> str | None:
        """The declared signal equal to ``signal`` after normalisation, if any."""
        wanted = normalise_key(signal)
        for declared in self.signals:
            if normalise_key(declared) == wanted:
                return declared
        return None


@dataclass(frozen=True)
class ControlLog:
    room_id: str
    title: str
    owner: str
    clock_note: str | None
    evidence_ids: tuple[str, ...]
    file: str
    sha256: str
    status: str | None
    source_note: str | None
    rows: tuple[ControlRow, ...]

    def summary(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "title": self.title,
            "owner": self.owner,
            "evidence_ids": list(self.evidence_ids),
        }


def _jsonl_objects(data: bytes, where: str) -> list[tuple[int, Any]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CatalogueError(f"{where}: not UTF-8: {exc}") from None
    if text and not text.endswith("\n"):
        raise CatalogueError(f"{where}: must end with a newline")
    lines = text.split("\n")[:-1] if text else []
    if len(lines) > _MAX_ROWS:
        raise CatalogueError(f"{where}: more than {_MAX_ROWS} rows")
    out = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            raise CatalogueError(f"{where}: line {number} is blank")
        out.append((number, strict_json_loads(line, f"{where} line {number}")))
    return out


def _common_row_fields(row: Mapping[str, Any], where: str, evidence_ids) -> datetime:
    evidence_id = require_id(row, "evidence_id", where, EVIDENCE_ID_RE)
    if evidence_id not in evidence_ids:
        raise CatalogueError(
            f"{where}: evidence_id {evidence_id!r} is not listed in the log's "
            f"evidence_ids {list(evidence_ids)}"
        )
    require_str(row, "recorded_time", where)
    require_str(row, "clock_basis", where)
    when = require_utc_instant(row, "index_time_utc", where)
    require_number(row, "index_uncertainty_s", where, minimum=0)
    status = row.get("value_status")
    if status not in VALUE_STATUSES:
        raise CatalogueError(
            f"{where}: value_status {status!r} is not one of {', '.join(VALUE_STATUSES)}"
        )
    return when


def _check_value(row: Mapping[str, Any], where: str) -> None:
    value = row.get("value")
    if value is None or isinstance(value, str):
        if isinstance(value, str) and not value.strip():
            raise CatalogueError(f"{where}: 'value' must not be blank")
        return
    require_number(row, "value", where)


def parse_asset_log(
    entry: Mapping[str, Any], data: bytes, sha256: str, where: str
) -> AssetLog:
    asset_id = require_id(entry, "asset_id", where, NAME_ID_RE)
    signals = require_str_list(entry, "signals", where)
    evidence_ids = require_str_list(entry, "evidence_ids", where)
    for evidence_id in evidence_ids:
        if not EVIDENCE_ID_RE.match(evidence_id):
            raise CatalogueError(f"{where}: invalid evidence ID {evidence_id!r}")
    rows: list[AssetRow] = []
    for number, obj in _jsonl_objects(data, f"{where} {entry['file']}"):
        at = f"{where} row {number}"
        row = check_keys(obj, at, ASSET_ROW_KEYS)
        require_id(row, "event_id", at, RECORD_ID_RE)
        when = _common_row_fields(row, at, evidence_ids)
        if row["asset_id"] != asset_id:
            raise CatalogueError(
                f"{at}: asset_id {row['asset_id']!r} does not match the log {asset_id!r}"
            )
        signal = require_str(row, "signal", at)
        if signal not in signals:
            raise CatalogueError(
                f"{at}: signal {signal!r} is not declared in the log's signals"
            )
        _check_value(row, at)
        for key in ("unit", "text"):
            optional_str(row, key, at)
        rows.append(AssetRow(raw=row, index_time=when))
    rows.sort(key=lambda r: (r.index_time, r.record_id))
    return AssetLog(
        asset_id=asset_id,
        title=require_str(entry, "title", where),
        owner=require_str(entry, "owner", where),
        signals=signals,
        clock_note=require_str(entry, "clock_note", where),
        evidence_ids=evidence_ids,
        file=str(entry["file"]),
        sha256=sha256,
        status=optional_str(entry, "status", where),
        source_note=optional_str(entry, "source_note", where),
        rows=tuple(rows),
    )


def parse_control_log(
    entry: Mapping[str, Any], data: bytes, sha256: str, where: str
) -> ControlLog:
    room_id = require_id(entry, "room_id", where, NAME_ID_RE)
    evidence_ids = require_str_list(entry, "evidence_ids", where)
    for evidence_id in evidence_ids:
        if not EVIDENCE_ID_RE.match(evidence_id):
            raise CatalogueError(f"{where}: invalid evidence ID {evidence_id!r}")
    rows: list[ControlRow] = []
    for number, obj in _jsonl_objects(data, f"{where} {entry['file']}"):
        at = f"{where} row {number}"
        row = check_keys(obj, at, CONTROL_ROW_KEYS)
        require_id(row, "entry_id", at, RECORD_ID_RE)
        when = _common_row_fields(row, at, evidence_ids)
        if row["room_id"] != room_id:
            raise CatalogueError(
                f"{at}: room_id {row['room_id']!r} does not match the log {room_id!r}"
            )
        require_str(row, "text", at)
        for key in ("from", "to", "channel"):
            optional_str(row, key, at)
        rows.append(ControlRow(raw=row, index_time=when))
    rows.sort(key=lambda r: (r.index_time, r.record_id))
    return ControlLog(
        room_id=room_id,
        title=require_str(entry, "title", where),
        owner=require_str(entry, "owner", where),
        clock_note=optional_str(entry, "clock_note", where),
        evidence_ids=evidence_ids,
        file=str(entry["file"]),
        sha256=sha256,
        status=optional_str(entry, "status", where),
        source_note=optional_str(entry, "source_note", where),
        rows=tuple(rows),
    )


def select_rows(
    rows: Sequence[AssetRow] | Sequence[ControlRow],
    start: datetime,
    end: datetime,
    signal: str | None = None,
) -> list[Any]:
    """Rows with ``start <= index_time < end`` (and the given signal), in order."""
    times = [row.index_time for row in rows]
    lo = bisect.bisect_left(times, start)
    hi = bisect.bisect_left(times, end)
    selected = list(rows[lo:hi])
    if signal is not None:
        selected = [row for row in selected if row.raw.get("signal") == signal]
    return selected


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        if (
            "|" in value
            or "\n" in value
            or "\r" in value
            or value != value.strip()
            or value.startswith('"')
        ):
            return json.dumps(value, ensure_ascii=False)
        return value
    return json.dumps(value)


def render_rows(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> str:
    """A ``|``-separated table: header, then one line per row (lossless: a cell that
    contains ``|``, a line break or surrounding spaces is written as a JSON string)."""
    lines = [" | ".join(columns)]
    for row in rows:
        lines.append(" | ".join(_cell(row.get(column)) for column in columns))
    return "\n".join(lines)
