"""Shared validators for manifest-v2 bundle files (fail closed).

Every check raises :class:`environment.incident.catalogue.CatalogueError` with the
location of the problem. JSON is decoded strictly: duplicate keys, ``NaN`` and
``Infinity`` are refused, so a file means exactly one thing.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from typing import Any

from environment.incident.catalogue import CatalogueError
from environment.incident.locators import LocatorError, parse_iso_instant

__all__ = [
    "EVIDENCE_ID_RE",
    "NAME_ID_RE",
    "RECORD_ID_RE",
    "VALUE_STATUSES",
    "check_keys",
    "optional_str",
    "require_id",
    "require_number",
    "require_str",
    "require_str_list",
    "require_utc_instant",
    "strict_json_loads",
]

VALUE_STATUSES: tuple[str, ...] = (
    "measured",
    "reported",
    "estimated",
    "modelled",
    "digitised",
    "illustrative",
    "framing",
)

EVIDENCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
NAME_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
RECORD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_MAX_TEXT = 20_000


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate key {key!r}")
        out[key] = value
    return out


def _no_constant(name: str) -> Any:
    raise ValueError(f"{name} is not allowed")


def strict_json_loads(data: bytes | str, where: str) -> Any:
    try:
        text = data.decode("utf-8") if isinstance(data, bytes) else data
        return json.loads(
            text, object_pairs_hook=_no_duplicates, parse_constant=_no_constant
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise CatalogueError(f"{where}: not valid JSON: {exc}") from None


def check_keys(
    obj: Any,
    where: str,
    required: Iterable[str],
    optional: Iterable[str] = (),
) -> dict[str, Any]:
    if not isinstance(obj, Mapping):
        raise CatalogueError(f"{where}: must be a JSON object")
    required = tuple(required)
    allowed = set(required) | set(optional)
    if "provenance" in obj and "provenance" not in allowed:
        raise CatalogueError(
            f"{where}: 'provenance' is private and must be stripped from the "
            "agent-visible bundle"
        )
    extra = sorted(set(obj) - allowed)
    if extra:
        raise CatalogueError(f"{where}: unexpected field(s) {', '.join(extra)}")
    missing = [k for k in required if k not in obj]
    if missing:
        raise CatalogueError(f"{where}: missing field(s) {', '.join(missing)}")
    return dict(obj)


def require_str(obj: Mapping[str, Any], key: str, where: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CatalogueError(f"{where}: '{key}' must be a non-empty string")
    if len(value) > _MAX_TEXT:
        raise CatalogueError(f"{where}: '{key}' is longer than {_MAX_TEXT} characters")
    return value


def optional_str(obj: Mapping[str, Any], key: str, where: str) -> str | None:
    if obj.get(key) is None:
        return None
    return require_str(obj, key, where)


def require_id(
    obj: Mapping[str, Any], key: str, where: str, pattern: re.Pattern[str]
) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not pattern.match(value):
        raise CatalogueError(
            f"{where}: '{key}' must match {pattern.pattern} (got {value!r})"
        )
    return value


def require_str_list(
    obj: Mapping[str, Any], key: str, where: str, *, allow_empty: bool = False
) -> tuple[str, ...]:
    value = obj.get(key)
    if not isinstance(value, list) or (not value and not allow_empty):
        raise CatalogueError(f"{where}: '{key}' must be a non-empty list of strings")
    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise CatalogueError(
                f"{where}: '{key}[{index}]' must be a non-empty string"
            )
        items.append(item)
    if len(set(items)) != len(items):
        raise CatalogueError(f"{where}: '{key}' has duplicate entries")
    return tuple(items)


def require_number(
    obj: Mapping[str, Any], key: str, where: str, *, minimum: float | None = None
) -> int | float:
    value = obj.get(key)
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
    ):
        raise CatalogueError(f"{where}: '{key}' must be a finite number")
    if minimum is not None and value < minimum:
        raise CatalogueError(f"{where}: '{key}' must be >= {minimum}")
    return value


def require_utc_instant(obj: Mapping[str, Any], key: str, where: str) -> datetime:
    raw = require_str(obj, key, where)
    try:
        when = parse_iso_instant(raw)
    except LocatorError as exc:
        raise CatalogueError(f"{where}: '{key}': {exc}") from None
    if when.utcoffset() != timedelta(0):
        raise CatalogueError(
            f"{where}: '{key}' must be written in UTC ('Z' or '+00:00'), got {raw!r}"
        )
    return when
