"""Citation locator grammar.

A citation is ``{"evidence_id": <document ID>, "locator": <locator>}``. Locators:

* text lines of the document's text file: ``L<n>`` or ``L<a>-L<b>`` (``L<a>-<b>`` and a
  lower-case ``l`` are accepted; surrounding whitespace is ignored). 1-based, inclusive,
  ``a <= b <= line_count``.
* time-series instants or ranges (documents with a time-series artifact only):
  ``time:<iso>`` or ``time:<iso>/<iso>``; ISO-8601 with an explicit offset (``Z`` or
  ``+HH:MM``/``-HH:MM``), optional fractional seconds; ``start <= end``; both within the
  series' first and last sample (inclusive).
* time-series data rows (1-based, header excluded): ``row:<n>`` or ``rows:<a>-<b>``.
* records of a manifest-v2 bundle: ``event:<event_id>`` (an asset-log row),
  ``entry:<entry_id>`` (a control-log entry) and ``response:<response_id>`` (a witness
  response). The citation's ``evidence_id`` must be the one the record belongs to.

:func:`parse_locator` returns a :class:`Locator` whose :attr:`Locator.normalized` form is
canonical (times in UTC), so equal locators compare equal regardless of how they were
written; comparisons are made on instants, never on strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

__all__ = [
    "Locator",
    "LocatorError",
    "LOCATOR_HELP",
    "RECORD_KINDS",
    "RECORD_LOCATOR_HELP",
    "parse_iso_instant",
    "parse_locator",
    "validate_locator",
    "parse_and_validate",
]

LOCATOR_HELP = (
    "Locators: 'L12' or 'L12-L18' for numbered lines of a document's text; for a time "
    "series also 'time:<ISO-8601 with offset>' or 'time:<start>/<end>' and 'row:<n>' or "
    "'rows:<a>-<b>' (data rows, 1-based, header excluded)."
)

RECORD_LOCATOR_HELP = (
    "Records are cited by ID with the evidence_id they belong to: 'event:<event_id>' "
    "(asset-log row), 'entry:<entry_id>' (control-log entry) or "
    "'response:<response_id>' (witness response)."
)
RECORD_KINDS = ("event", "entry", "response")
_RECORD_NAMES = {
    "event": "asset-log event",
    "entry": "control-log entry",
    "response": "witness response",
}

_MAX_LOCATOR_CHARS = 200

_ISO_PATTERN = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})"
_ISO_RE = re.compile(rf"^{_ISO_PATTERN}$")
_LINES_RE = re.compile(r"^[Ll](\d{1,9})(?:\s*-\s*[Ll]?(\d{1,9}))?$")
_TIME_RE = re.compile(rf"^({_ISO_PATTERN})(?:\s*/\s*({_ISO_PATTERN}))?$")
_ROWS_RE = re.compile(r"^(\d{1,9})(?:\s*-\s*(\d{1,9}))?$")
_RECORD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


class LocatorError(ValueError):
    """A locator is malformed or does not fit the cited document."""


def parse_iso_instant(text: str) -> datetime:
    """Parse an ISO-8601 timestamp that carries an explicit UTC offset.

    Accepted: ``YYYY-MM-DDTHH:MM:SS[.fraction](Z|+HH:MM|-HH:MM)``. Raises
    :class:`LocatorError` (a ``ValueError``) with a readable message otherwise.
    """
    if not isinstance(text, str):
        raise LocatorError(f"expected an ISO-8601 timestamp string, got {text!r}")
    candidate = text.strip()
    if not _ISO_RE.match(candidate):
        raise LocatorError(
            f"{text!r} is not an ISO-8601 timestamp with an explicit offset; "
            "use e.g. 2000-01-31T23:59:59+01:00 or 2000-01-31T22:59:59Z"
        )
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise LocatorError(f"{text!r} is not a valid date/time: {exc}") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:  # pragma: no cover
        raise LocatorError(f"{text!r} has no UTC offset")
    return parsed


def _canonical_instant(when: datetime) -> str:
    return when.astimezone(UTC).isoformat()


@dataclass(frozen=True)
class Locator:
    """A parsed locator.

    ``kind`` is ``"lines"`` or ``"rows"`` (``start``/``end`` are ints), ``"time"``
    (``start``/``end`` are timezone-aware datetimes) or a record kind ``"event"``,
    ``"entry"`` or ``"response"`` (``start == end`` is the record ID). Single
    positions have ``start == end``.
    """

    kind: Literal["lines", "time", "rows", "event", "entry", "response"]
    start: Any
    end: Any
    text: str

    @property
    def record_id(self) -> str | None:
        """The record ID of an event/entry/response locator (else ``None``)."""
        return str(self.start) if self.kind in RECORD_KINDS else None

    @property
    def normalized(self) -> str:
        if self.kind == "lines":
            if self.start == self.end:
                return f"L{self.start}"
            return f"L{self.start}-L{self.end}"
        if self.kind == "rows":
            if self.start == self.end:
                return f"row:{self.start}"
            return f"rows:{self.start}-{self.end}"
        if self.kind in RECORD_KINDS:
            return f"{self.kind}:{self.start}"
        start = _canonical_instant(self.start)
        if self.start == self.end:
            return f"time:{start}"
        return f"time:{start}/{_canonical_instant(self.end)}"

    def __str__(self) -> str:
        return self.normalized

    # -- helpers used by grading -------------------------------------------------
    def covers_time(self, when: datetime) -> bool:
        """Whether a time locator includes the instant ``when`` (inclusive)."""
        if self.kind != "time":
            return False
        _require_aware(when)
        return self.start <= when <= self.end

    def overlaps_time(self, start: datetime, end: datetime) -> bool:
        """Whether a time locator intersects the closed interval [start, end]."""
        if self.kind != "time":
            return False
        _require_aware(start)
        _require_aware(end)
        return self.start <= end and start <= self.end

    def covers_line(self, line: int) -> bool:
        return self.kind == "lines" and self.start <= line <= self.end

    def overlaps_lines(self, a: int, b: int) -> bool:
        """Whether a line locator intersects lines ``a``..``b`` (inclusive)."""
        if self.kind != "lines":
            return False
        lo, hi = min(a, b), max(a, b)
        return self.start <= hi and lo <= self.end

    def overlaps_rows(self, a: int, b: int) -> bool:
        if self.kind != "rows":
            return False
        lo, hi = min(a, b), max(a, b)
        return self.start <= hi and lo <= self.end


def _require_aware(when: datetime) -> None:
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("time comparisons need timezone-aware datetimes")


def parse_locator(text: str) -> Locator:
    """Parse ``text`` into a :class:`Locator` or raise :class:`LocatorError`."""
    if not isinstance(text, str):
        raise LocatorError(f"locator must be a string; got {type(text).__name__}")
    stripped = text.strip()
    if not stripped:
        raise LocatorError(f"locator is empty. {LOCATOR_HELP}")
    if len(stripped) > _MAX_LOCATOR_CHARS:
        raise LocatorError(f"locator is longer than {_MAX_LOCATOR_CHARS} characters")

    lowered = stripped.lower()
    if lowered.startswith("time:"):
        return _parse_time(stripped, stripped[5:].strip())
    for kind in RECORD_KINDS:
        if lowered.startswith(f"{kind}:"):
            return _parse_record(kind, stripped, stripped[len(kind) + 1 :].strip())
    for prefix in ("rows:", "row:"):
        if lowered.startswith(prefix):
            return _parse_rows(stripped, stripped[len(prefix) :].strip())
    if lowered.startswith("l"):
        return _parse_lines(stripped)
    raise LocatorError(f"unrecognised locator {text!r}. {LOCATOR_HELP}")


def _parse_lines(text: str) -> Locator:
    match = _LINES_RE.match(text)
    if not match:
        raise LocatorError(
            f"malformed line locator {text!r}; use 'L12' or 'L12-L18' (1-based, inclusive)"
        )
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) is not None else start
    if start < 1:
        raise LocatorError(f"line locator {text!r}: lines are numbered from 1")
    if start > end:
        raise LocatorError(
            f"line locator {text!r} is reversed: the first line must not exceed the last"
        )
    return Locator(kind="lines", start=start, end=end, text=text)


def _parse_rows(text: str, body: str) -> Locator:
    match = _ROWS_RE.match(body)
    if not match:
        raise LocatorError(
            f"malformed row locator {text!r}; use 'row:<n>' or 'rows:<a>-<b>' "
            "(data rows, 1-based, header excluded)"
        )
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) is not None else start
    if start < 1:
        raise LocatorError(f"row locator {text!r}: data rows are numbered from 1")
    if start > end:
        raise LocatorError(
            f"row locator {text!r} is reversed: the first row must not exceed the last"
        )
    return Locator(kind="rows", start=start, end=end, text=text)


def _parse_record(kind: str, text: str, body: str) -> Locator:
    if not _RECORD_ID_RE.match(body):
        raise LocatorError(
            f"malformed {_RECORD_NAMES[kind]} locator {text!r}; use '{kind}:<ID>' with "
            "the ID exactly as the tool returned it"
        )
    return Locator(kind=kind, start=body, end=body, text=text)  # type: ignore[arg-type]


def _parse_time(text: str, body: str) -> Locator:
    match = _TIME_RE.match(body)
    if not match:
        raise LocatorError(
            f"malformed time locator {text!r}; use 'time:<ISO-8601 with offset>' or "
            "'time:<start>/<end>', e.g. time:2000-01-31T23:59:59+01:00"
        )
    start = parse_iso_instant(match.group(1))
    end = parse_iso_instant(match.group(2)) if match.group(2) is not None else start
    if start > end:
        raise LocatorError(
            f"time locator {text!r} is reversed: the start must not be after the end"
        )
    return Locator(kind="time", start=start, end=end, text=text)


def validate_locator(loc: Locator | str, doc: Any) -> None:
    """Check that ``loc`` fits ``doc``; raise :class:`LocatorError` if it does not.

    ``doc`` needs ``doc_id``, ``line_count`` and ``timeseries`` (``None`` or an object
    with timezone-aware ``first``/``last`` datetimes and an int ``rows``), as provided by
    :class:`environment.incident.catalogue.Document`. Record locators (``event:``,
    ``entry:``, ``response:``) need ``doc.records`` (see ``_validate_record``); a target
    with ``is_document`` false accepts record locators only.
    """
    if isinstance(loc, str):
        loc = parse_locator(loc)
    doc_id = getattr(doc, "doc_id", "?")
    if loc.kind in RECORD_KINDS:
        _validate_record(loc, doc, doc_id)
        return
    if getattr(doc, "is_document", True) is False:
        raise LocatorError(
            f"{doc_id} has no document text or time series to cite with "
            f"{loc.normalized}. {RECORD_LOCATOR_HELP}"
        )
    if loc.kind == "lines":
        line_count = int(doc.line_count)
        if loc.end > line_count:
            raise LocatorError(
                f"{doc_id} has {line_count} lines; {loc.normalized} is out of range"
            )
        return

    series = getattr(doc, "timeseries", None)
    if series is None:
        raise LocatorError(
            f"{doc_id} has no time series; cite its text with line locators "
            "('L<n>' or 'L<a>-L<b>')"
        )
    if loc.kind == "rows":
        if loc.end > int(series.rows):
            raise LocatorError(
                f"the {doc_id} series has {series.rows} data rows; "
                f"{loc.normalized} is out of range"
            )
        return

    first, last = series.first, series.last
    for when in (loc.start, loc.end):
        if when < first or when > last:
            raise LocatorError(
                f"time {when.isoformat()} is outside the {doc_id} series "
                f"({first.isoformat()} to {last.isoformat()}, inclusive)"
            )


def _validate_record(loc: Locator, doc: Any, doc_id: str) -> None:
    """``doc`` must hold the record: ``doc.records[kind]`` is a set of IDs (an
    ``EvidenceTarget`` of a manifest-v2 bundle); ``doc.record_owner(kind, id)``, when
    present, names the evidence the record belongs to for the error message."""
    records = getattr(doc, "records", None) or {}
    record_id = str(loc.start)
    if record_id in (records.get(loc.kind) or ()):
        return
    name = _RECORD_NAMES[loc.kind]
    owner_of = getattr(doc, "record_owner", None)
    owner = owner_of(loc.kind, record_id) if callable(owner_of) else None
    if owner is not None and owner != doc_id:
        raise LocatorError(
            f"{name} {record_id!r} belongs to evidence {owner}, not {doc_id}; cite it "
            f'as {{"evidence_id": "{owner}", "locator": "{loc.normalized}"}}'
        )
    raise LocatorError(
        f"{doc_id} has no {name} {record_id!r}; use the ID exactly as the tool "
        f"returned it. {RECORD_LOCATOR_HELP}"
    )


def parse_and_validate(text: str, doc: Any) -> Locator:
    """Parse ``text`` and validate it against ``doc``; return the :class:`Locator`."""
    loc = parse_locator(text)
    validate_locator(loc, doc)
    return loc
