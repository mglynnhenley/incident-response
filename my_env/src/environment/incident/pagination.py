"""Opaque, deterministic pagination cursors for the query tools.

A cursor encodes the tool, a digest of the normalised query (instants in UTC, so the
same window written with another offset continues the same listing), the offset of
the next row, the bundle version and an integrity field ``k``: the first 16 hex digits
of ``sha256(tool|digest|offset|version|key)``, where ``key`` is the bundle's
``bundle_sha256`` (the manifest hash, which the agent cannot read). Cursors stay
deterministic, so recorded traces replay. Anything else (a cursor from another query,
tool or bundle, an edited cursor — including an edited offset —, an offset that is not
a whole number of pages, an offset past the end) is refused with
:class:`environment.incident.catalogue.CursorError`.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Mapping
from typing import Any

from environment.incident.catalogue import CursorError

__all__ = ["decode_cursor", "encode_cursor", "query_digest"]

_INVALID = "cursor is not valid; pass a next_cursor value unchanged"


def query_digest(query: Mapping[str, Any]) -> str:
    text = json.dumps(dict(query), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _integrity(tool: str, digest: str, offset: int, version: str, key: str) -> str:
    text = f"{tool}|{digest}|{offset}|{version}|{key}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def encode_cursor(
    tool: str, digest: str, offset: int, version: str, key: str = ""
) -> str:
    payload = json.dumps(
        {
            "k": _integrity(tool, digest, offset, version, key),
            "o": offset,
            "q": digest,
            "t": tool,
            "v": version,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(
    cursor: str,
    tool: str,
    digest: str,
    version: str,
    total: int,
    key: str = "",
    page_size: int | None = None,
) -> int:
    """The offset encoded in ``cursor`` for this exact query (raises CursorError)."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("utf-8"))
        offset = payload["o"]
        check = payload["k"]
        same = (
            payload["t"] == tool and payload["q"] == digest and payload["v"] == version
        )
    except (
        binascii.Error,
        UnicodeError,
        ValueError,
        KeyError,
        TypeError,
    ):
        raise CursorError(_INVALID) from None
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise CursorError(_INVALID)
    if not same:
        raise CursorError(
            "cursor belongs to a different query; repeat the same arguments with the "
            "next_cursor value, or omit cursor to start again"
        )
    if not isinstance(check, str) or check != _integrity(
        tool, digest, offset, version, key
    ):
        raise CursorError(_INVALID)
    if page_size is not None and offset % page_size:
        raise CursorError(_INVALID)
    if offset >= total:
        raise CursorError("cursor is past the end of the results")
    return offset
