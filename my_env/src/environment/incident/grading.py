"""Grading of a frozen v3 submission against the reduced answer key.

Two layers, reported separately and never collapsed into one number:

* **Automated** (deterministic): numeric checks of the frequency landmarks (D3, from the
  frozen R01 series, with the key's tolerances; the value comes from the finding's
  ``quantity`` or, when that does not fit the criterion (missing, another unit, outside
  the value range, dated outside the window, or a unit the grader cannot read), from the
  statement and derivation, each value paired with the time written next to it; a value
  read only from prose is never failed automatically, and a criterion is decided as 0
  only when no candidate value appears anywhere in the submission or a structured
  quantity in the window is outside tolerance, see :func:`_select_numeric`);
  time / MW / text-pattern *proposals* for the other criteria (numbers and times are
  bound to the entity they describe, e.g. GT1A vs GT1B; method checks such as clock
  bases, the datum uncertainty and the duration convention also read a finding's
  ``derivation`` and ``quantity.basis`` and the report text; an established mechanism
  stated in a finding of another status, e.g. ``unknown`` for its open root cause,
  counts through the element's ``other_statuses``); validation of every citation
  locator (resolvable, document retrieved during the episode, R01 time ranges covering
  the landmark or its inputs, a derivation for derived values and R01 analysed with
  ``run_python``, line overlap with the keyed *primary* evidence spans); and flags
  (uncited findings, unresolvable citations, cited-but-never-retrieved documents,
  suspected severe assertions, hypothesis/unknown labelling, observed/reported findings
  worded as inferences, conflicting values). Flags are proposals for the reviewer; only
  the criteria and assertion measures carry grades.
* **Human**: a versioned grading-decisions JSON file (schema below) records, per
  criterion, content (1 / 0.5 / 0) and evidence support (1 / 0) with the finding IDs and
  notes; per assertion, supported / unsupported / contradicted; severe-flag
  adjudications; and explanation-quality notes. It is bound to one submission, one key
  (version and content sha256) and one bundle; a mismatched binding is rejected. A
  confirmed severe flag applies the key's effect (its findings become ``unsupported``,
  listed criteria get content 0, source ``severe_flag``); decisions that contradict it
  are rejected.

The report (:func:`grade_submission`, :func:`grade_episode`) gives, per dimension and per
criterion, **content coverage**, **evidence support** and **assertion quality**, each
value tagged with its source (``auto``, ``human`` or ``pending``). There is no pass
threshold, no overall score and no ranking. ``status`` is ``provisional`` unless every
criterion and assertion has a decision, every suspected severe flag is adjudicated,
explanation quality has non-empty notes, the decisions file is not a builder fixture,
an episode trace is available, and the key's review status is ``reviewed``.

Outcome semantics: a run whose outcome is not ``complete`` (no valid submission, or a
model-caused budget exhaustion) is reported with its reason and empty content measures.

Grading-decisions file (``decisions_schema`` ``gb2019-grading-decisions/1``)::

    {
      "decisions_schema": "gb2019-grading-decisions/1",
      "decisions_version": "1",            # bump on every edit; keep old files
      "builder_fixture": false,            # true only for test fixtures
      "reviewer": "name or role",          # required
      "date": "YYYY-MM-DD",                # required
      "binding": {"submission_sha256": "...", "key_version": "0.3.1",
                  "key_sha256": "...",     # grading.key_sha256(key)
                  "bundle_sha256": "..."}, # all four required
      "criteria": {"D1.1": {"content": 1 | 0.5 | 0 | null,
                            "evidence_support": 1 | 0 | null,
                            "finding_ids": ["F02"], "notes": "..."}},
      "assertions": {"F02": {"verdict": "supported" | "unsupported" | "contradicted" | null,
                             "duplicate_of": "F01"?, "dimension": "D1"?, "notes": "..."},
                     "R-1": {"verdict": "...", "text": "report-only sentence",
                             "dimension": "D4", "notes": "..."}},
      "severe_flags": [{"flag_id": "SF1", "finding_ids": ["F30"],
                        "locations": ["report.sections[2].body"],   # report-text hits
                        "confirmed": true | false | null, "notes": "..."}],
      "explanation_quality": {"notes": "...", "by_dimension": {"D1": "..."}}
    }                                      # notes, or a note for every dimension

``null`` means "not decided yet" (pending). Keys starting with ``_`` are ignored (the
review template puts automated proposals and context there). For ``auto_numeric``
criteria leave content/evidence ``null`` to accept a decided automated result, or set a
value to override it (explain in ``notes``); a criterion the matcher could not settle
(values only in prose) is pending until a value is set. When crediting content the
matcher did not find, list the ``finding_ids``: their citations are then checked (for
D3, automatically); otherwise evidence support stays pending until it is set.

This module must not import ``karotte``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from environment.incident.catalogue import Catalogue, CatalogueError
from environment.incident.episode import (
    SUBMISSION_FILE,
    EpisodeError,
    build_transcript_summary,
    read_config_snapshot,
    read_state,
    read_trace,
)
from environment.incident.locators import (
    Locator,
    LocatorError,
    parse_and_validate,
    parse_iso_instant,
)
from environment.incident.paths import DEFAULT_BUNDLE_DIR, DEFAULT_PRIVATE_DIR
from environment.incident.submission import (
    Submission,
    extract_references,
    validate_submission,
)

__all__ = [
    "DECISIONS_SCHEMA",
    "GRADE_SCHEMA",
    "GRADER_VERSION",
    "DecisionsError",
    "GradingError",
    "check_decisions",
    "grade_episode",
    "grade_submission",
    "key_sha256",
    "load_decisions",
    "load_key",
    "review_template",
    "trace_info_from_episode",
]

GRADER_VERSION = "0.3.1"
GRADE_SCHEMA = "gb2019-grade/1"
DECISIONS_SCHEMA = "gb2019-grading-decisions/1"
KEY_SCHEMA = "gb2019-answer-key/1"
DEFAULT_KEY_PATH = DEFAULT_PRIVATE_DIR / "answer_key.json"

CONTENT_VALUES = (0, 0.5, 1)
EVIDENCE_VALUES = (0, 1)
VERDICTS = ("supported", "unsupported", "contradicted")
BST = timezone(timedelta(hours=1))

INTERPRETATION = (
    "No pass threshold, overall score or ranking is computed. Content coverage, evidence "
    "support and assertion quality are separate measures. Values marked 'pending' await "
    "human adjudication; 'auto_proposal' values are automated suggestions for the "
    "reviewer, not grades."
)


class GradingError(Exception):
    """Grading inputs are unusable (key, catalogue or submission)."""


class DecisionsError(GradingError):
    """A grading-decisions file is malformed or bound to another submission/key."""


# -- text helpers ------------------------------------------------------------------
_DASHES = "‐‑‒–—―−﹘﹣－"
_DOUBLE_QUOTES = "“”„‟″«»"
_SINGLE_QUOTES = "‘’‚‛′´`"
_TRANSLATE = {ord(c): "-" for c in _DASHES}
_TRANSLATE.update({ord(c): '"' for c in _DOUBLE_QUOTES})
_TRANSLATE.update({ord(c): "'" for c in _SINGLE_QUOTES})
_TRANSLATE[0x00AD] = None


def normalise(text: str) -> str:
    """NFKC, casefold, unify dashes/quotes, drop soft hyphens, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATE).casefold()
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=4096)
def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def _any(text: str, patterns: Iterable[str]) -> bool:
    return any(_rx(p).search(text) for p in patterns)


def _all_groups(text: str, groups: Iterable[Iterable[str]]) -> bool:
    return all(_any(text, group) for group in groups)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# -- times and values in findings --------------------------------------------------
_ISO_IN_TEXT = re.compile(
    r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})"
)
_MERIDIEM = r"(\s*[ap]\.?m\.?(?![a-z]))?"
_HMS_IN_TEXT = re.compile(
    r"(?<![\d:.])(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)(?![\d:])"
    + _MERIDIEM
    + r"(\s*(?:z\b|utc\b|gmt\b|bst\b|\+01:?00|\+00:?00))?",
    re.IGNORECASE,
)
_HM_IN_TEXT = re.compile(
    r"(?<![\d:.])(\d{1,2}):(\d{2})(?![\d:])" + _MERIDIEM + r"(\s*(?:z\b|utc\b|bst\b))?",
    re.I,
)
_EVENT_DAY = (2019, 8, 9)


def _clock_time(
    h: str, m: str, s: str, suffix: str | None, meridiem: str | None = None
) -> datetime | None:
    try:
        hour, minute, seconds = int(h), int(m), float(s)
    except ValueError:
        return None
    half = (meridiem or "").strip().lower()[:1]
    if half and 1 <= hour <= 12:  # 12-hour clock: "4:52:59 pm" is 16:52:59
        hour = hour % 12 + (12 if half == "p" else 0)
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= seconds < 61):
        return None
    tag = (suffix or "").strip().lower().replace(":", "")
    tz = UTC if tag in ("z", "utc", "gmt", "+0000") else BST
    whole = int(seconds)
    micro = int(round((seconds - whole) * 1_000_000))
    if micro >= 1_000_000:
        whole, micro = whole + 1, micro - 1_000_000
    if whole >= 60:
        return None
    return datetime(*_EVENT_DAY, hour, minute, whole, micro, tzinfo=tz)


def _blank(text: str, start: int, end: int) -> str:
    return text[:start] + " " * (end - start) + text[end:]


def _time_spans(text: str) -> list[tuple[datetime, int, int]]:
    """Clock times in ``text`` with their character spans (see :func:`statement_times`)."""
    found: list[tuple[datetime, int, int]] = []
    masked = text
    for match in _ISO_IN_TEXT.finditer(text):
        try:
            found.append(
                (
                    parse_iso_instant(
                        match.group(0).replace("t", "T").replace("z", "Z")
                    ),
                    match.start(),
                    match.end(),
                )
            )
        except LocatorError:
            pass
        masked = _blank(masked, match.start(), match.end())
    for match in _HMS_IN_TEXT.finditer(masked):
        when = _clock_time(
            match.group(1),
            match.group(2),
            match.group(3),
            match.group(5),
            match.group(4),
        )
        if when is not None:
            found.append((when, match.start(), match.end()))
        masked = _blank(masked, match.start(), match.end())
    for match in _HM_IN_TEXT.finditer(masked):
        when = _clock_time(
            match.group(1), match.group(2), "0", match.group(4), match.group(3)
        )
        if when is not None:
            found.append((when, match.start(), match.end()))
    found.sort(key=lambda item: item[1])
    return found


def statement_times(text: str) -> list[datetime]:
    """Clock times written in free text: ISO instants, ``HH:MM:SS[.f]`` and ``HH:MM``
    (read as BST on 9 August 2019 unless marked Z/UTC/GMT; ``am``/``pm`` read as a
    12-hour clock)."""
    return [when for when, _, _ in _time_spans(text)]


# A clock time that is only the reference point of an offset ("207 s after reaching its
# minimum at 16:53:49", "26 s after fault inception at 16:52:33.490", "16:52:33 + 26 s")
# does not date the value written next to it: the offset gives the value's time. A
# reference without a number ("after the fault at 16:52:33", "seconds after 16:52:33")
# only bounds it.
_OFFSET_RELATION = re.compile(
    r"\b(after|before|later than|earlier than|since|following|prior to|from)\b", re.I
)
_OFFSET_DURATION = re.compile(
    r"(?:(?<![\w.])(\d+)\s?(?:min|mins|minutes?)\s+(?:and\s+)?)?"
    r"(?<![\w.])(\d+(?:\.\d+)?)\s?(ms|milliseconds?|s|secs?|seconds?|min|mins|minutes?)"
    r"\s*(?:\([^()]{0,40}\)\s*)?$",
    re.I,
)
_OFFSET_UNIT_ONLY = re.compile(
    r"\b(?:ms|milliseconds?|s|secs?|seconds?|mins?|minutes?)\s*$", re.I
)
_OFFSET_PLUS = re.compile(
    r"^\s*(?:\+|plus\b)\s*(\d+(?:\.\d+)?)\s?"
    r"(ms|milliseconds?|s|secs?|seconds?|min|mins|minutes?)(?![a-z])",
    re.I,
)
_OFFSET_SIGN = {
    "after": 1,
    "later than": 1,
    "since": 1,
    "following": 1,
    "from": 1,
    "before": -1,
    "earlier than": -1,
    "prior to": -1,
}
_SENTENCE_OR_SEMICOLON = re.compile(r"[;.!?](?=\s|$)")


def _duration_s(number: str, unit: str) -> float:
    u = unit.lower()
    if u.startswith("ms") or u.startswith("milli"):
        return float(number) / 1000
    if u.startswith("min"):
        return float(number) * 60
    return float(number)


def _resolved_time_spans(text: str) -> list[tuple[str, datetime, int, int]]:
    """Clock times in ``text`` as ``(kind, time, start, end)``. ``kind`` is ``at`` (a
    time written for what it describes), ``offset`` (a time computed from an offset to a
    written reference: "207 s after its minimum at 16:53:49" is 16:57:16), or ``after``
    / ``before`` (a reference without a number, which only bounds the time)."""
    out: list[tuple[str, datetime, int, int]] = []
    prev_end = 0
    for when, ts, te in _time_spans(text):
        pre = text[max(prev_end, ts - 120) : ts]
        cuts = [m.end() for m in _SENTENCE_OR_SEMICOLON.finditer(pre)]
        pre = pre[cuts[-1] :] if cuts else pre
        kind, resolved = "at", when
        relation = None
        for match in _OFFSET_RELATION.finditer(pre):
            relation = match
        if relation is not None:
            gap = pre[relation.end() :]
            if (
                len(gap) <= 60
                and not re.search(r"(?<!\w)\d", gap)
                and not _CLAUSE_BREAK.search(gap)
            ):
                word = re.sub(r"\s+", " ", relation.group(1).lower())
                sign = _OFFSET_SIGN[word]
                head = pre[: relation.start()]
                duration = _OFFSET_DURATION.search(head)
                if duration:
                    seconds = _duration_s(duration.group(2), duration.group(3))
                    if duration.group(1):
                        seconds += int(duration.group(1)) * 60
                    kind, resolved = "offset", when + timedelta(seconds=sign * seconds)
                elif word != "from" or _OFFSET_UNIT_ONLY.search(head):
                    kind = "after" if sign > 0 else "before"
        plus = _OFFSET_PLUS.match(text[te : te + 40])
        if kind == "at" and plus:
            kind = "offset"
            resolved = when + timedelta(
                seconds=_duration_s(plus.group(1), plus.group(2))
            )
        out.append((kind, resolved, ts, te))
        prev_end = te
    return out


def _dating_times(text: str, source: str) -> list[tuple[datetime, str]]:
    """The times ``text`` dates something at: written times and times computed from an
    offset (source ``"<source> offset"``); references without a number are left out."""
    return [
        (when, source if kind == "at" else f"{source} offset")
        for kind, when, _, _ in _resolved_time_spans(text)
        if kind in ("at", "offset")
    ]


def _finding_times(finding: Mapping[str, Any]) -> list[tuple[datetime, str]]:
    """The finding's ``event_time`` when it has one; otherwise the clock times written
    in its statement (so a stated window boundary never overrides an event time)."""
    if finding.get("event_time"):
        try:
            return [(parse_iso_instant(finding["event_time"]), "event_time")]
        except LocatorError:
            pass
    return [(t, "statement") for t in statement_times(finding.get("statement", ""))]


_UNIT_FACTORS = {
    "ms": ("s", 0.001),
    "s": ("s", 1.0),
    "min": ("s", 60.0),
    "mHz": ("Hz", 0.001),
    "Hz": ("Hz", 1.0),
    "kW": ("MW", 0.001),
    "MW": ("MW", 1.0),
    "GW": ("MW", 1000.0),
}
_EXTRA_UNITS = {
    "min": "min",
    "mins": "min",
    "minute": "min",
    "minutes": "min",
    "mhz": "mHz",
    "millihertz": "mHz",
    "kw": "kW",
    "gw": "GW",
}
_UNIT_TOKEN = re.compile(r"[^\W\d_]+")


def _unit_key(unit: str, aliases: Mapping[str, Sequence[str]]) -> str | None:
    """The canonical unit named by the leading word of ``unit`` (so ``"Hz (1-s
    sample)"`` is Hz and ``"s (zero-order hold)"`` is s), or ``None``."""
    raw = unicodedata.normalize("NFKC", unit).strip()
    match = _UNIT_TOKEN.match(raw)
    if match is None:
        return None
    token = match.group(0)
    if token == "MHz":  # megahertz, not a grid-frequency unit
        return None
    u = token.casefold()
    for key, names in aliases.items():
        if u == key.casefold() or u in names:
            return key
    return _EXTRA_UNITS.get(u)


def _convert(value: float, from_unit: str, to_unit: str) -> float | None:
    if from_unit == to_unit:
        return value
    a, b = _UNIT_FACTORS.get(from_unit), _UNIT_FACTORS.get(to_unit)
    if a and b and a[0] == b[0]:
        return value * a[1] / b[1]
    return None


_VALUE_UNITS = (
    r"mw|megawatts?|mhz|millihertz|ms|milliseconds?|hz|hertz|s|secs?|seconds?|mins?"
    r"|minutes?"
)
# "49.083 Hz", "187 MW", and the unit in brackets: "49.083 (Hz)"
_TEXT_VALUE = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s?"
    rf"(?:\(\s?({_VALUE_UNITS})\s?\)|({_VALUE_UNITS})(?![a-z]))"
)


def _text_value_spans(
    norm_text: str, unit: str, aliases: Mapping[str, Sequence[str]]
) -> list[tuple[float, int, int]]:
    """Values with a unit convertible to ``unit`` in normalised text, with spans."""
    values = []
    for match in _TEXT_VALUE.finditer(norm_text):
        found_unit = _unit_key(match.group(2) or match.group(3), aliases)
        if found_unit is None:
            continue
        value = _convert(float(match.group(1).replace(",", "")), found_unit, unit)
        if value is not None:
            values.append((value, match.start(), match.end()))
    return values


def _text_values(
    text: str, unit: str, aliases: Mapping[str, Sequence[str]]
) -> list[float]:
    return [v for v, _, _ in _text_value_spans(normalise(text), unit, aliases)]


def _quantity_state(
    finding: Mapping[str, Any], unit: str, aliases: Mapping[str, Sequence[str]]
) -> tuple[str, float | None]:
    """(state, value in ``unit``): state is ``none`` (no quantity), ``ok``,
    ``other_unit`` (a recognised unit of another dimension) or ``unrecognised``."""
    quantity = finding.get("quantity")
    if not quantity:
        return "none", None
    found_unit = _unit_key(str(quantity.get("unit", "")), aliases)
    if found_unit is None:
        return "unrecognised", None
    value = _convert(float(quantity["value"]), found_unit, unit)
    return ("ok", value) if value is not None else ("other_unit", None)


def _quantity_value(
    finding: Mapping[str, Any], unit: str, aliases: Mapping[str, Sequence[str]]
) -> float | None:
    return _quantity_state(finding, unit, aliases)[1]


# -- binding values and times to the entity they describe --------------------------
_CLAUSE_BREAK = re.compile(
    r";|,\s|:\s|\s(?:and|while|whereas|but|then|followed by)\s|[.!?](?=\s|$)"
)
_SENTENCE_BREAK = re.compile(r"[.!?](?=\s|$)")


def _spans(text: str, breaks: re.Pattern[str]) -> list[tuple[int, int]]:
    spans, start = [], 0
    for match in breaks.finditer(text):
        spans.append((start, match.end()))
        start = match.end()
    spans.append((start, len(text)))
    return spans


@dataclass
class _Layout:
    """A statement prepared for entity binding: normalised text with the key's masked
    phrases (e.g. the circuit name that contains both end names) blanked, the entity
    mentions, and clause and sentence spans."""

    text: str
    mentions: list[tuple[int, int, str]]
    clauses: list[tuple[int, int]]
    sentences: list[tuple[int, int]]

    @property
    def primary(self) -> str | None:
        """The first entity mentioned: the subject the structured ``quantity`` and
        ``event_time`` of the finding are taken to describe."""
        return self.mentions[0][2] if self.mentions else None

    def _span(self, spans: list[tuple[int, int]], pos: int) -> tuple[int, int]:
        return next(((a, b) for a, b in spans if a <= pos < b), (0, len(self.text)))

    def clause_text(self, pos: int) -> str:
        a, b = self._span(self.clauses, pos)
        return self.text[a:b]

    def entity_at(self, start: int, end: int) -> str | None:
        """The entity a value or time at ``start:end`` describes: the nearest mention in
        the same clause (preceding on ties); else the nearest preceding mention in the
        same sentence; else the only entity the statement mentions; else ``None``."""
        a, b = self._span(self.clauses, start)
        near = []
        for ms, me, name in self.mentions:
            if ms < a or me > b:
                continue
            if me <= start:
                near.append((start - me, 0, name))
            elif ms >= end:
                near.append((ms - end, 1, name))
            else:
                near.append((0, 0, name))
        if near:
            return min(near)[2]
        sa, _ = self._span(self.sentences, start)
        before = [m for m in self.mentions if m[0] >= sa and m[1] <= start]
        if before:
            return before[-1][2]
        names = {m[2] for m in self.mentions}
        return next(iter(names)) if len(names) == 1 else None


def _make_layout(
    statement: str, entities: Mapping[str, Sequence[str]], masks: Sequence[str]
) -> _Layout:
    text = normalise(statement)
    for pattern in masks:
        for match in list(_rx(pattern).finditer(text)):
            text = _blank(text, match.start(), match.end())
    mentions = {
        (match.start(), match.end(), name)
        for name, patterns in entities.items()
        for pattern in patterns
        for match in _rx(pattern).finditer(text)
    }
    return _Layout(
        text=text,
        mentions=sorted(mentions),
        clauses=_spans(text, _CLAUSE_BREAK),
        sentences=_spans(text, _SENTENCE_BREAK),
    )


# -- inputs ------------------------------------------------------------------------
def load_key(path: Path | str | None = None) -> dict[str, Any]:
    """Load the answer key (default: the private key next to the bundle)."""
    key_path = Path(path) if path is not None else DEFAULT_KEY_PATH
    try:
        key = json.loads(key_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GradingError(f"cannot load the answer key {key_path}: {exc}") from None
    if not isinstance(key, dict) or key.get("key_schema") != KEY_SCHEMA:
        raise GradingError(f"{key_path} is not a {KEY_SCHEMA} answer key")
    return key


def key_sha256(key: Mapping[str, Any]) -> str:
    """sha256 of the canonical JSON of an answer key (decisions are bound to it)."""
    return _sha256_text(_canonical(key))


_key_sha256 = key_sha256


def _review_status(key: Mapping[str, Any]) -> str:
    return str(
        (key.get("review") or {}).get("status") or key.get("review_status") or "unknown"
    )


def _as_submission(raw: Any, catalogue: Catalogue) -> tuple[dict[str, Any], str]:
    """(plain submission dict, canonical sha256); raises GradingError if invalid."""
    if isinstance(raw, Submission):
        raw = raw.model_dump(mode="json", exclude_none=True)
    if isinstance(raw, (str, Path)) and not (
        isinstance(raw, str) and raw.lstrip().startswith("{")
    ):
        raw = Path(raw).read_text(encoding="utf-8")
    result = validate_submission(raw, catalogue)
    if not result.ok or result.canonical_json is None or result.sha256 is None:
        raise GradingError(f"submission is not valid: {result.errors[:5]}")
    return json.loads(result.canonical_json), result.sha256


# -- decisions ---------------------------------------------------------------------
def load_decisions(path: Path | str) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DecisionsError(f"cannot read decisions file {path}: {exc}") from None
    if not isinstance(data, dict):
        raise DecisionsError("a decisions file must be a JSON object")
    return data


def _public(obj: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in obj.items() if not str(k).startswith("_")}


def _flag_effect(flag: Mapping[str, Any]) -> dict[str, Any]:
    """The machine-readable consequence of confirming a severe flag (key ``effect``):
    the verdicts allowed for its findings and the criteria whose content becomes 0."""
    effect = flag.get("effect") or {}
    return {
        "verdicts": tuple(effect.get("verdicts") or ("unsupported", "contradicted")),
        "verdict": effect.get("verdict", "unsupported"),
        "zero_content": tuple(effect.get("zero_content") or ()),
    }


def _explanation_reviewed(
    explanation: Mapping[str, Any], dimensions: Sequence[str]
) -> bool:
    """Explanation quality counts as reviewed when the overall notes, or a note for
    every dimension, are non-empty (blank template placeholders do not count)."""

    def filled(value: Any) -> bool:
        return isinstance(value, str) and bool(value.strip())

    by_dim = explanation.get("by_dimension") or {}
    return filled(explanation.get("notes")) or (
        bool(dimensions) and all(filled(by_dim.get(d)) for d in dimensions)
    )


def check_decisions(
    decisions: Mapping[str, Any],
    *,
    submission_sha256: str,
    key: Mapping[str, Any],
    finding_ids: Iterable[str],
    bundle_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate a decisions object and its binding; return it with ``_``-keys removed.

    Raises :class:`DecisionsError` on any problem, including a binding to another
    submission, key (version or content) or bundle (decisions are never applied to the
    wrong run), and decisions that contradict a confirmed severe flag.
    """
    d = _public(decisions)
    problems: list[str] = []
    if d.get("decisions_schema") != DECISIONS_SCHEMA:
        problems.append(f"decisions_schema must be {DECISIONS_SCHEMA!r}")
    for name in ("decisions_version", "reviewer", "date"):
        if not isinstance(d.get(name), (str, int)) or not str(d.get(name)).strip():
            problems.append(f"{name} is required")
    binding = d.get("binding") or {}
    if binding.get("submission_sha256") != submission_sha256:
        problems.append(
            "binding.submission_sha256 does not match the graded submission "
            f"({str(binding.get('submission_sha256'))[:12]}... vs {submission_sha256[:12]}...)"
        )
    if binding.get("key_version") != key.get("key_version"):
        problems.append(
            f"binding.key_version {binding.get('key_version')!r} does not match the answer "
            f"key version {key.get('key_version')!r}"
        )
    if binding.get("key_sha256") != key_sha256(key):
        problems.append(
            "binding.key_sha256 is missing or does not match the answer key (was the key "
            "edited? decisions must be re-issued for a changed key)"
        )
    if bundle_sha256 is not None and binding.get("bundle_sha256") != bundle_sha256:
        problems.append(
            "binding.bundle_sha256 is missing or does not match the graded bundle"
        )
    known = {c["criterion_id"] for c in key["criteria"]}
    fids = set(finding_ids)
    for cid, entry in (d.get("criteria") or {}).items():
        if cid not in known:
            problems.append(f"criteria.{cid}: unknown criterion")
            continue
        if not isinstance(entry, Mapping):
            problems.append(f"criteria.{cid}: must be an object")
            continue
        entry = _public(entry)
        if entry.get("content") is not None and entry["content"] not in CONTENT_VALUES:
            problems.append(f"criteria.{cid}.content must be 1, 0.5, 0 or null")
        if (
            entry.get("evidence_support") is not None
            and entry["evidence_support"] not in EVIDENCE_VALUES
        ):
            problems.append(f"criteria.{cid}.evidence_support must be 1, 0 or null")
        for fid in entry.get("finding_ids") or []:
            if fid not in fids:
                problems.append(f"criteria.{cid}.finding_ids: unknown finding {fid!r}")
    dims = {dim["dimension_id"] for dim in key["dimensions"]}
    for aid, entry in (d.get("assertions") or {}).items():
        if not isinstance(entry, Mapping):
            problems.append(f"assertions.{aid}: must be an object")
            continue
        entry = _public(entry)
        verdict = entry.get("verdict")
        if verdict is not None and verdict not in VERDICTS:
            problems.append(
                f"assertions.{aid}.verdict must be one of {VERDICTS} or null"
            )
        if aid not in fids and not str(entry.get("text") or "").strip():
            problems.append(f"assertions.{aid}: a report-only assertion needs 'text'")
        if entry.get("dimension") is not None and entry["dimension"] not in dims:
            problems.append(f"assertions.{aid}.dimension: unknown dimension")
        dup = entry.get("duplicate_of")
        if (
            dup is not None
            and dup not in fids
            and dup not in (d.get("assertions") or {})
        ):
            problems.append(f"assertions.{aid}.duplicate_of: unknown assertion {dup!r}")
    flags = {f["flag_id"]: f for f in key.get("severe_flags", [])}
    assertions = {
        aid: _public(entry)
        for aid, entry in (d.get("assertions") or {}).items()
        if isinstance(entry, Mapping)
    }
    criteria = {
        cid: _public(entry)
        for cid, entry in (d.get("criteria") or {}).items()
        if isinstance(entry, Mapping)
    }
    for index, entry in enumerate(d.get("severe_flags") or []):
        if not isinstance(entry, Mapping) or entry.get("flag_id") not in flags:
            problems.append(f"severe_flags[{index}]: unknown flag_id")
            continue
        if entry.get("confirmed") not in (True, False, None):
            problems.append(
                f"severe_flags[{index}].confirmed must be true, false or null"
            )
        for fid in entry.get("finding_ids") or []:
            if fid not in fids:
                problems.append(
                    f"severe_flags[{index}].finding_ids: unknown finding {fid!r}"
                )
        if entry.get("confirmed") is not True:
            continue
        # A confirmed flag has fixed consequences (the key's effect_when_confirmed);
        # decisions that contradict them are rejected rather than silently mixed.
        effect = _flag_effect(flags[entry["flag_id"]])
        # a finding's heuristic location is its finding_id
        targets = list(entry.get("finding_ids") or []) + [
            loc for loc in entry.get("locations") or [] if loc in fids
        ]
        for fid in targets:
            verdict = assertions.get(fid, {}).get("verdict")
            if verdict is not None and verdict not in effect["verdicts"]:
                problems.append(
                    f"assertions.{fid}.verdict is {verdict!r} but severe flag "
                    f"{entry['flag_id']} is confirmed for it (allowed: "
                    f"{', '.join(effect['verdicts'])} or null)"
                )
        for cid in effect["zero_content"]:
            content = criteria.get(cid, {}).get("content")
            if content not in (None, 0):
                problems.append(
                    f"criteria.{cid}.content is {content!r} but severe flag "
                    f"{entry['flag_id']} is confirmed, which sets it to 0"
                )
    dims_known = {dim["dimension_id"] for dim in key["dimensions"]}
    explanation = d.get("explanation_quality")
    if explanation is not None:
        if not isinstance(explanation, Mapping):
            problems.append("explanation_quality must be an object")
        else:
            if explanation.get("notes") is not None and not isinstance(
                explanation["notes"], str
            ):
                problems.append("explanation_quality.notes must be text or null")
            by_dim = explanation.get("by_dimension")
            if by_dim is not None and not isinstance(by_dim, Mapping):
                problems.append("explanation_quality.by_dimension must be an object")
            for dim, note in (
                (by_dim or {}).items() if isinstance(by_dim, Mapping) else ()
            ):
                if dim not in dims_known:
                    problems.append(
                        f"explanation_quality.by_dimension.{dim}: unknown dimension"
                    )
                elif note is not None and not isinstance(note, str):
                    problems.append(
                        f"explanation_quality.by_dimension.{dim} must be text or null"
                    )
    if problems:
        raise DecisionsError("grading decisions rejected: " + "; ".join(problems))
    return d


# -- trace information -------------------------------------------------------------
def trace_info_from_episode(episode_dir: Path | str) -> dict[str, Any]:
    """Retrievals and Python calls recorded in an episode's ledger."""
    episode_dir = Path(episode_dir)
    state = read_state(episode_dir)
    trace = read_trace(episode_dir)
    first_seq: dict[str, int] = {}
    python_calls = []
    for record in trace:
        envelope = record.get("envelope") or {}
        if record.get("tool") == "request_document" and envelope.get("ok"):
            for doc in envelope.get("evidence_ids") or []:
                first_seq.setdefault(doc, int(record.get("seq") or 0))
        if record.get("tool") == "run_python" and record.get("python"):
            py = record["python"]
            code = str(py.get("code") or "")
            python_calls.append(
                {
                    "seq": record.get("seq"),
                    "request_id": record.get("request_id"),
                    "ok": bool(envelope.get("ok")),
                    "exit_code": py.get("exit_code"),
                    "timed_out": py.get("timed_out"),
                    "code_sha256": py.get("code_sha256"),
                    # the R01 CSV is the only CSV in the bundle
                    "mentions_r01": any(
                        token in code
                        for token in ("R01", "frequency_2019-08-09", ".csv")
                    ),
                }
            )
    r01_seq = first_seq.get("R01")
    analysed = any(
        c["ok"]
        and c["mentions_r01"]
        and r01_seq is not None
        and (c["seq"] or 0) > r01_seq
        for c in python_calls
    )
    return {
        "available": True,
        "retrieved": list(state.retrieved) if state else sorted(first_seq),
        "first_retrieval_seq": first_seq,
        "python_calls": python_calls,
        "r01_analysed_with_python": analysed,
        "calls_used": state.calls_used if state else None,
        "frozen_at_request_id": state.frozen_at_request_id if state else None,
    }


# -- citations ---------------------------------------------------------------------
@dataclass
class CitationCheck:
    finding_id: str
    index: int
    evidence_id: str
    locator: str
    normalized: str | None
    resolvable: bool
    error: str | None
    retrieved: bool | None
    locator_obj: Locator | None = field(default=None, repr=False)
    keyed_overlap: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "index": self.index,
            "evidence_id": self.evidence_id,
            "locator": self.locator,
            "normalized": self.normalized,
            "resolvable": self.resolvable,
            "error": self.error,
            "retrieved_during_episode": self.retrieved,
            "overlaps_keyed_evidence_of": sorted(self.keyed_overlap),
        }


def _check_citations(
    findings: Sequence[Mapping[str, Any]],
    catalogue: Catalogue,
    trace_info: Mapping[str, Any] | None,
) -> dict[str, list[CitationCheck]]:
    retrieved = set(trace_info.get("retrieved") or []) if trace_info else None
    out: dict[str, list[CitationCheck]] = {}
    for finding in findings:
        checks = []
        for index, citation in enumerate(finding.get("citations") or []):
            doc = catalogue.get(citation["evidence_id"])
            loc, error = None, None
            if doc is None:
                error = f"unknown evidence_id {citation['evidence_id']!r}"
            else:
                try:
                    loc = parse_and_validate(citation["locator"], doc)
                except LocatorError as exc:
                    error = str(exc)
            checks.append(
                CitationCheck(
                    finding_id=finding["finding_id"],
                    index=index,
                    evidence_id=citation["evidence_id"],
                    locator=citation["locator"],
                    normalized=loc.normalized if loc else None,
                    resolvable=loc is not None,
                    error=error,
                    retrieved=None
                    if retrieved is None
                    else citation["evidence_id"] in retrieved,
                    locator_obj=loc,
                )
            )
        out[finding["finding_id"]] = checks
    return out


def _series_row_instant(
    catalogue: Catalogue, evidence_id: str, row: int
) -> datetime | None:
    doc = catalogue.get(evidence_id)
    series = doc.timeseries if doc else None
    if series is None:
        return None
    return series.first + timedelta(seconds=series.interval_s * (row - 1))


def _covers(check: CitationCheck, when: datetime, catalogue: Catalogue) -> bool:
    loc = check.locator_obj
    if loc is None:
        return False
    if loc.kind == "time":
        return loc.covers_time(when)
    if loc.kind == "rows":
        a = _series_row_instant(catalogue, check.evidence_id, loc.start)
        b = _series_row_instant(catalogue, check.evidence_id, loc.end)
        return a is not None and b is not None and a <= when <= b
    return False


def _overlaps(
    check: CitationCheck, keyed: Mapping[str, Any], catalogue: Catalogue
) -> bool:
    if check.locator_obj is None or check.evidence_id != keyed["evidence_id"]:
        return False
    doc = catalogue.get(check.evidence_id)
    try:
        target = parse_and_validate(keyed["locator"], doc)
    except LocatorError:
        return False
    loc = check.locator_obj
    if loc.kind == "lines":
        return target.kind == "lines" and loc.overlaps_lines(target.start, target.end)
    # time and row locators: compare as instants
    span = _instants(loc, check.evidence_id, catalogue)
    tspan = _instants(target, check.evidence_id, catalogue)
    return bool(span and tspan and span[0] <= tspan[1] and tspan[0] <= span[1])


def _instants(
    loc: Locator, evidence_id: str, catalogue: Catalogue
) -> tuple[datetime, datetime] | None:
    if loc.kind == "time":
        return loc.start, loc.end
    if loc.kind == "rows":
        a = _series_row_instant(catalogue, evidence_id, loc.start)
        b = _series_row_instant(catalogue, evidence_id, loc.end)
        return (a, b) if a and b else None
    return None


# -- the automated assessment of one criterion -------------------------------------
# What a ``text`` element may read (key element ``fields``; default: the statement
# only). The finding fields are joined into one text per finding, so the groups of
# ``all`` may be met across them (e.g. the unit named in the statement and the method in
# the derivation). ``report`` adds the report text, one sentence at a time.
TEXT_FIELDS = ("statement", "derivation", "quantity.basis", "report")
_FINDING_FIELDS = TEXT_FIELDS[:-1]


def _text_fields(el: Mapping[str, Any]) -> tuple[str, ...]:
    """The validated ``fields`` of an element (``("statement",)`` when absent)."""
    fields = tuple(el.get("fields") or ("statement",))
    unknown = [f for f in fields if f not in TEXT_FIELDS]
    if unknown:
        raise GradingError(
            f"element {el.get('id')!r}: unknown fields {unknown} (allowed: "
            f"{', '.join(TEXT_FIELDS)})"
        )
    if fields != ("statement",) and el.get("type") != "text":
        raise GradingError(f"element {el.get('id')!r}: only text elements take fields")
    if "report" in fields and (
        el.get("statuses") or el.get("labelled") or el.get("uncertain")
    ):
        raise GradingError(
            f"element {el.get('id')!r}: report text has no status, so 'report' cannot "
            "be combined with statuses, labelled or uncertain"
        )
    other = el.get("other_statuses")
    if other is not None:
        groups = other.get("all") if isinstance(other, Mapping) else None
        if (
            el.get("type") != "text"
            or fields != ("statement",)
            or not el.get("statuses")
            or not isinstance(groups, list)
            or not all(isinstance(g, list) for g in groups)
        ):
            raise GradingError(
                f"element {el.get('id')!r}: 'other_statuses' needs a text element on the "
                "statement with 'statuses' and an 'all' list of pattern groups"
            )
    return fields


def _finding_field(finding: Mapping[str, Any], name: str) -> str:
    if name == "quantity.basis":
        return str((finding.get("quantity") or {}).get("basis") or "")
    return str(finding.get(name) or "")


@dataclass
class _Ctx:
    findings: list[dict[str, Any]]
    key: Mapping[str, Any]
    catalogue: Catalogue
    citations: dict[str, list[CitationCheck]]
    trace_info: Mapping[str, Any] | None
    severe: list[dict[str, Any]]
    aliases: Mapping[str, Sequence[str]]
    factual: tuple[str, ...]
    labelled_statuses: tuple[str, ...]
    uncertainty: tuple[str, ...]
    order: dict[str, int]
    entities: Mapping[str, Sequence[str]] = field(default_factory=dict)
    masks: tuple[str, ...] = ()
    layouts: dict[str, _Layout] = field(default_factory=dict)
    # (location, normalised sentence) for every sentence of the report text
    report: list[tuple[str, str]] = field(default_factory=list)
    # hedging wording that keeps a sentence from reporting a mechanism (other_statuses)
    hedges: tuple[str, ...] = ()
    # wording that frames a mechanism as unproven, denied or open (other_statuses)
    negations: tuple[str, ...] = ()
    # statuses that offer a mechanism only as a possibility (other_statuses)
    hedged_statuses: tuple[str, ...] = ("hypothesis",)

    def text(self, finding: Mapping[str, Any]) -> str:
        return normalise(finding.get("statement", ""))

    def field_text(self, finding: Mapping[str, Any], fields: Sequence[str]) -> str:
        """The normalised text of the finding fields a text element reads, joined with
        '; ' so that a pattern never runs from one field into the next."""
        if tuple(fields) == ("statement",):
            return self.text(finding)
        parts = (
            normalise(_finding_field(finding, name))
            for name in fields
            if name in _FINDING_FIELDS
        )
        return " ; ".join(p for p in parts if p)

    def layout(self, finding: Mapping[str, Any]) -> _Layout:
        fid = finding["finding_id"]
        if fid not in self.layouts:
            self.layouts[fid] = _make_layout(
                finding.get("statement", ""), self.entities, self.masks
            )
        return self.layouts[fid]

    def status_ok(
        self, finding: Mapping[str, Any], statuses: Sequence[str] | None
    ) -> bool:
        return statuses is None or finding.get("status") in statuses

    def labelled(self, finding: Mapping[str, Any]) -> bool:
        return finding.get("status") in self.labelled_statuses or _any(
            self.text(finding), self.uncertainty
        )

    def uncertain(self, finding: Mapping[str, Any]) -> bool:
        """Status ``unknown`` or explicit wording that something is not established
        (a ``hypothesis`` label alone does not say the cause is unknown)."""
        return finding.get("status") == "unknown" or _any(
            self.text(finding), self.uncertainty
        )


def _level_value(value: float, spec: Mapping[str, Any]) -> tuple[float, float]:
    expected = float(spec["expected"])
    error = abs(value - expected)
    if "abs_tol" in spec:
        return (1.0 if error <= float(spec["abs_tol"]) + 1e-9 else 0.0), error
    if "full_abs" in spec:
        if error <= float(spec["full_abs"]) + 1e-9:
            return 1.0, error
        return (0.5 if error <= float(spec["half_abs"]) + 1e-9 else 0.0), error
    rel = error / abs(expected) if expected else float("inf")
    if rel <= float(spec["full_rel"]) + 1e-9:
        return 1.0, error
    return (0.5 if rel <= float(spec["half_rel"]) + 1e-9 else 0.0), error


def _time_error(when: datetime, spec: Mapping[str, Any]) -> float:
    if spec.get("expected_range"):
        a = parse_iso_instant(spec["expected_range"][0])
        b = parse_iso_instant(spec["expected_range"][1])
        if a <= when <= b:
            return 0.0
        return min(abs((when - a).total_seconds()), abs((when - b).total_seconds()))
    return abs((when - parse_iso_instant(spec["expected"])).total_seconds())


def _element_values(
    el: Mapping[str, Any],
    finding: Mapping[str, Any],
    ctx: _Ctx,
    layout: _Layout | None,
) -> list[tuple[float, str]]:
    """Values a value element may use. With an ``entity`` the structured quantity
    counts only when that entity is the finding's subject, and each statement value
    only when it is bound to that entity (see :meth:`_Layout.entity_at`); ``near_any``
    then requires matching wording in the statement (quantity) or the value's clause."""
    near = el.get("near_any") or []
    text = layout.text if layout is not None else ctx.text(finding)
    values: list[tuple[float, str]] = []
    q = _quantity_value(finding, el["unit"], ctx.aliases)
    if q is not None and (
        layout is None
        or (layout.primary == el["entity"] and (not near or _any(text, near)))
    ):
        values.append((q, "quantity"))
    if el.get("from_text"):
        for value, start, end in _text_value_spans(text, el["unit"], ctx.aliases):
            if layout is not None:
                if layout.entity_at(start, end) != el["entity"]:
                    continue
                if near and not _any(layout.clause_text(start), near):
                    continue
            values.append((value, "statement"))
    exclude = el.get("exclude_values")
    if exclude and not _any(text, exclude.get("unless_any", [])):
        tol = float(exclude.get("abs_tol", 0)) + 1e-9
        values = [
            (v, s)
            for v, s in values
            if not any(abs(v - float(x)) <= tol for x in exclude["values"])
        ]
    return values


def _element_times(
    el: Mapping[str, Any],
    finding: Mapping[str, Any],
    layout: _Layout | None,
) -> list[tuple[datetime, str]]:
    """Times a time element may use (entity binding as in :func:`_element_values`)."""
    if layout is None:
        return _finding_times(finding)
    near = el.get("near_any") or []
    times: list[tuple[datetime, str]] = []
    if (
        finding.get("event_time")
        and layout.primary == el["entity"]
        and (not near or _any(layout.text, near))
    ):
        try:
            times.append((parse_iso_instant(finding["event_time"]), "event_time"))
        except LocatorError:
            pass
    for when, start, end in _time_spans(layout.text):
        if layout.entity_at(start, end) != el["entity"]:
            continue
        if near and not _any(layout.clause_text(start), near):
            continue
        times.append((when, "statement"))
    return times


def _report_times(el: Mapping[str, Any], ctx: _Ctx) -> list[dict[str, Any]]:
    """Times within tolerance that a report sentence gives for a time element's entity
    (bound as in a statement; the element's context in the same sentence). The report
    is not a finding, so these are pointed out to the reviewer, never credited."""
    found: list[dict[str, Any]] = []
    for location, sentence in ctx.report:
        layout = _make_layout(sentence, ctx.entities, ctx.masks)
        if not _all_groups(layout.text, el.get("context") or []):
            continue
        for when, _ in _element_times(el, {"statement": sentence}, layout):
            if _time_error(when, el) <= float(el.get("tol_s", 0)) + 1e-9:
                found.append({"location": location, "time": when.isoformat()})
    return found


def _report_hits(el: Mapping[str, Any], ctx: _Ctx) -> list[str]:
    """Report locations with a sentence that meets a text element (``fields`` with
    ``report``): every ``all`` group and no ``none`` pattern in one sentence."""
    hits: list[str] = []
    for location, sentence in ctx.report:
        if location in hits or any(_any(sentence, g) for g in el.get("none", [])):
            continue
        if _all_groups(sentence, el["all"]):
            hits.append(location)
    return hits


# Splits a sentence into the parts a negation or uncertainty word can qualify on its
# own: "ST1C tripped because its speed signals disagreed; the root cause of that has
# not been established" states the mechanism, "It has not been established that ST1C
# tripped because ..." does not.
_MECHANISM_SEGMENT_BREAK = re.compile(
    r";|:\s|,?\s(?:but|although|though|whereas|however|while)\s|,\s(?:and|which)\s"
)
# A part (or a later sentence) about the root cause, the reason or "why" may be open
# without hedging the mechanism itself.
_ROOT_CAUSE_SUBJECT = re.compile(
    r"\broot cause|\bunderlying cause|\bwhy\b|\bwhat (?:caused|triggered|led|drove)"
    r"|\breasons?\b|\bcause of (?:the|that|this|these|those|its|their)\b|\bwhose cause\b"
)
# A later sentence that refers back to the mechanism ("This remains a hypothesis.",
# "This has not been confirmed.") hedges it.
_ANAPHOR = re.compile(
    r"^\W*(?:this|that|these|those|it|such|which|the (?:above|same|mechanism|explanation"
    r"|account|attribution|claim|finding))\b"
)
# A part that is only a label ("Unknown: ...", "Not established: ...").
_LABEL_ONLY = re.compile(
    r"^\W*(?:unknown|not (?:yet )?(?:been )?established|unconfirmed|unproven|unresolved"
    r"|undetermined|uncertain|unclear|unexplained|open|hypothes\w*)\W*$"
)
# Default negation wording (the key's conventions.mechanism_negation_patterns override it).
_MECHANISM_NEGATIONS = (
    r"\bnot (?:yet )?(?:been )?(?:established|confirmed|proven|proved|shown|demonstrated"
    r"|verified|known)\b",
    r"\bno (?:evidence|proof|confirmation|indication)\b",
    r"\b(?:unconfirmed|unproven|unverified|unsubstantiated)\b",
    r"\bruled out\b",
    r"\b(?:disproved|disproven|refuted|discounted|dismissed|rejected)\b",
    r"\b(?:unknown|unclear|uncertain|undetermined|not known|not clear) (?:whether|if|that)\b",
    r"\bnot (?:because of|due to|caused by|the result of)\b",
)


def _mechanism_hedged(
    sentences: Sequence[str], index: int, groups: Sequence[Sequence[str]], ctx: _Ctx
) -> bool:
    """Whether sentence ``index`` (normalised) states the mechanism with hedging,
    negation or uncertainty wording: ``mechanism_hedge_patterns`` anywhere in the
    sentence; ``mechanism_negation_patterns`` or ``uncertainty_patterns`` in a part of
    the sentence that carries the mechanism (or is only a label), unless that part is
    about the root cause; or any of them in a later sentence that refers back to it."""
    text = sentences[index]
    if _any(text, ctx.hedges):
        return True
    doubts = ctx.negations + ctx.uncertainty
    patterns = [p for group in groups for p in group]
    for part in _MECHANISM_SEGMENT_BREAK.split(text):
        if not _any(part, doubts) or _ROOT_CAUSE_SUBJECT.search(part):
            continue
        if _any(part, patterns) or _LABEL_ONLY.match(part):
            return True
    return any(
        _ANAPHOR.search(later)
        and _any(later, ctx.hedges + doubts)
        and not _ROOT_CAUSE_SUBJECT.search(later)
        for later in sentences[index + 1 :]
    )


def _reports_in_a_sentence(
    finding: Mapping[str, Any], el: Mapping[str, Any], ctx: _Ctx
) -> bool:
    """Whether one sentence of the statement reports what a text element looks for
    (every group of the element's ``all`` and of ``other_statuses.all``) without hedging
    (see :func:`_mechanism_hedged`): how a finding whose status the element does not
    list (e.g. ``unknown``, for the open root cause) still counts for an established
    mechanism it states. A status in ``mechanism_hedged_statuses`` (``hypothesis``)
    offers the mechanism only as a possibility and never counts."""
    if finding.get("status") in ctx.hedged_statuses:
        return False
    extra = (el.get("other_statuses") or {}).get("all") or []
    sentences = [normalise(s) for s in _sentences(finding.get("statement", ""))]
    for i, text in enumerate(sentences):
        if (
            _all_groups(text, el["all"])
            and _all_groups(text, extra)
            and not _mechanism_hedged(sentences, i, [*el["all"], *extra], ctx)
        ):
            return True
    return False


def _eval_element(el: Mapping[str, Any], ctx: _Ctx) -> dict[str, Any]:
    statuses = el.get("statuses")
    fields = _text_fields(el)
    best: tuple[float, float, int, str, dict[str, Any]] | None = None
    hits: list[str] = []
    considered: list[str] = []
    other_status: list[str] = []
    suspected = {s["finding_id"] for s in ctx.severe if s.get("finding_id")}
    for finding in ctx.findings:
        # A finding suspected of a severe assertion earns no positive credit.
        if finding["finding_id"] in suspected:
            continue
        if not ctx.status_ok(finding, statuses):
            # other_statuses: a finding of another status counts when one sentence
            # reports the element (e.g. the trip mechanism) without hedging.
            if not (
                el.get("other_statuses") and _reports_in_a_sentence(finding, el, ctx)
            ):
                continue
            other_status.append(finding["finding_id"])
        text = ctx.field_text(finding, fields)
        fid = finding["finding_id"]
        if any(_any(text, group) for group in el.get("none", [])):
            continue
        layout = ctx.layout(finding) if el.get("entity") else None
        context_text = layout.text if layout is not None else text
        if el["type"] == "text":
            if not _all_groups(text, el["all"]):
                continue
            if el.get("labelled") and not ctx.labelled(finding):
                continue
            if el.get("uncertain") and not ctx.uncertain(finding):
                continue
            hits.append(fid)
            considered.append(fid)
            cand = (1.0, 0.0, ctx.order[fid], fid, {})
        elif el["type"] == "value":
            if not _all_groups(context_text, el.get("context") or []):
                continue
            considered.append(fid)
            values = _element_values(el, finding, ctx, layout)
            cand = None
            for value, source in values:
                level, error = _level_value(value, el)
                option = (
                    level,
                    error,
                    ctx.order[fid],
                    fid,
                    {"value": value, "source": source, "error": error},
                )
                if cand is None or (-option[0], option[1], option[2]) < (
                    -cand[0],
                    cand[1],
                    cand[2],
                ):
                    cand = option
            if cand is None:
                continue
            if cand[0] > 0:
                hits.append(fid)
        elif el["type"] == "time":
            if not _all_groups(context_text, el.get("context") or []):
                continue
            considered.append(fid)
            cand = None
            for when, source in _element_times(el, finding, layout):
                error = _time_error(when, el)
                level = 1.0 if error <= float(el.get("tol_s", 0)) + 1e-9 else 0.0
                option = (
                    level,
                    error,
                    ctx.order[fid],
                    fid,
                    {
                        "time": when.isoformat(),
                        "source": source,
                        "error_s": round(error, 3),
                    },
                )
                if cand is None or (-option[0], option[1], option[2]) < (
                    -cand[0],
                    cand[1],
                    cand[2],
                ):
                    cand = option
            if cand is None:
                continue
            if cand[0] > 0:
                hits.append(fid)
        else:  # pragma: no cover - key validation
            raise GradingError(f"unknown element type {el['type']!r}")
        if best is None or (-cand[0], cand[1], cand[2]) < (-best[0], best[1], best[2]):
            best = cand
    # Report sentences count for text elements that list "report" in their fields; they
    # satisfy the element but are not findings (no finding_id, no citations).
    in_report = _report_hits(el, ctx) if "report" in fields else []
    report_detail: dict[str, Any] = {"report_locations": in_report} if in_report else {}
    if el["type"] == "time" and el.get("entity") and (best is None or best[0] < 1):
        report_times = _report_times(el, ctx)
        if report_times:
            report_detail["report_only_times"] = report_times
    other_status = [f for f in other_status if f in hits]
    if other_status:
        report_detail["other_status_finding_ids"] = other_status
    if best is None:
        return {
            "id": el["id"],
            "level": 1.0 if in_report else 0.0,
            "finding_id": None,
            "finding_ids": [],
            "considered": considered,
            "detail": report_detail,
        }
    return {
        "id": el["id"],
        "considered": considered,
        "level": best[0],
        "finding_id": best[3] if best[0] > 0 else None,
        "finding_ids": hits
        if el["type"] == "text"
        else ([best[3]] if best[0] > 0 else []),
        "detail": {**best[4], "best_finding": best[3], **report_detail},
    }


def _contradictions(
    rules: Sequence[Mapping[str, Any]], ctx: _Ctx
) -> list[dict[str, Any]]:
    """Contradiction rules, evaluated sentence by sentence: every ``all`` group and no
    ``none`` pattern must match within one sentence of a factual finding."""
    found = []
    for rule in rules:
        for finding in ctx.findings:
            if finding.get("status") not in ctx.factual:
                continue
            sentences = [normalise(s) for s in _sentences(finding.get("statement", ""))]
            if any(
                _all_groups(text, rule["all"])
                and not any(_any(text, g) for g in rule.get("none", []))
                for text in sentences
            ):
                found.append(
                    {
                        "id": rule["id"],
                        "finding_id": finding["finding_id"],
                        "effect": rule["effect"],
                        "note": rule.get("note"),
                    }
                )
    return found


def _score_rules(auto: Mapping[str, Any], ctx: _Ctx) -> dict[str, Any]:
    elements = [_eval_element(el, ctx) for el in auto.get("elements", [])]
    levels = {e["id"]: e["level"] for e in elements}
    content = 0.0
    basis = "no element set satisfied"
    for group in auto.get("full_if_any", []):
        if group and all(levels.get(i, 0) >= 1 for i in group):
            content, basis = 1.0, f"full: {', '.join(group)}"
            break
    if content < 1:
        for group in list(auto.get("half_if_any", [])) + list(
            auto.get("full_if_any", [])
        ):
            if group and all(levels.get(i, 0) >= 0.5 for i in group):
                content, basis = 0.5, f"partial: {', '.join(group)}"
                break
    contradictions = _contradictions(auto.get("contradictions", []), ctx)
    for hit in contradictions:
        if hit["effect"] == "zero" and content > 0:
            content, basis = 0.0, f"contradiction {hit['id']} ({hit['finding_id']})"
        elif hit["effect"] == "cap_half" and content > 0.5:
            content, basis = (
                0.5,
                f"capped by contradiction {hit['id']} ({hit['finding_id']})",
            )
    unmet = [
        e for e in elements if e["level"] < 1 and e["detail"].get("report_only_times")
    ]
    if unmet and content < 1:
        notes = []
        for e in unmet:
            by_time: dict[str, list[str]] = {}
            for t in e["detail"]["report_only_times"]:
                by_time.setdefault(t["time"], []).append(t["location"])
            notes += [
                f"{e['id']} {when} in {', '.join(locations)}"
                for when, locations in list(by_time.items())[:2]
            ]
        basis += (
            "; note: only the report text gives a time within tolerance for "
            + "; ".join(notes)
            + " (no finding states it: a human decides)"
        )
    zero_flags = set(auto.get("severe_flags_zero") or [])
    severe_hits = [s for s in ctx.severe if s["flag_id"] in zero_flags]
    if severe_hits and content > 0:
        content, basis = (
            0.0,
            "suspected severe flag "
            + ", ".join(sorted({s["flag_id"] for s in severe_hits})),
        )
    matched: list[str] = []
    for e in elements:
        for fid in e["finding_ids"]:
            if fid not in matched:
                matched.append(fid)
    for hit in contradictions:
        if hit["finding_id"] not in matched:
            matched.append(hit["finding_id"])
    matched.sort(key=lambda f: ctx.order[f])
    considered = sorted(
        {fid for e in elements for fid in e["considered"]} | set(matched),
        key=lambda f: ctx.order[f],
    )
    return {
        "content": content,
        "basis": basis,
        "elements": elements,
        "contradictions": contradictions,
        "matched_finding_ids": matched,
        "considered_finding_ids": considered,
        "conflicts": [],
    }


# -- D3: landmark values and durations ----------------------------------------------
# Wording that marks a number as a threshold, limit or statistic rather than a measured
# landmark ("below 49 Hz", "the 48.8 Hz LFDD stage", "averaging 50.006 Hz"). Without a
# time such a number is not a candidate value for a landmark; with a time it is
# credited only by a human (see _select_numeric).
_THRESHOLD_BEFORE = re.compile(
    r"(?:\b(?:below|above|under|over|beneath|exceed(?:s|ed|ing)?|cross(?:es|ed|ing)?"
    r"|threshold|limit|trigger(?: level)?|setting|averag(?:e|es|ed|ing)|mean|nominal"
    r"|statutory|range of|between|than)(?:\s+(?:is|was|of|at))?|[<>≤≥]=?)\s*(?:the\s+)?"
    r"(?:(?:about|approximately|around|roughly|some)\s+)?$"
)
_THRESHOLD_AFTER = re.compile(
    r"^\s*(?:threshold|limit|trigger|setting|lfdd|level|(?:first |1st )?stage"
    r"|or (?:above|below|higher|lower|more|less|over|under))\b"
)
_PRE_EVENT = re.compile(
    r"\bpre-?(?:disturbance|fault|event|incident)\b"
    r"|\bbefore the (?:fault|event|disturbance|incident)\b"
)
# With a time, a number is in doubt (credited only by a human) when its wording makes it
# a state or a statistic rather than the landmark reached at that time: below a level,
# a threshold or setting, an average or range ("still below 50 Hz at 16:57:15"), or in a
# clause that says the landmark was not (yet) reached ("had not returned to 50 Hz by
# 16:57:16", "remained at 49.2 Hz until 16:53:30"). Reaching a level ("returned to 50 Hz
# or above at 16:57:16", "rose above 50 Hz at 16:57:16") is the landmark itself.
_STATE_BEFORE = re.compile(
    r"(?:\b(?:below|under|beneath|threshold|limit|trigger(?: level)?|setting"
    r"|averag(?:e|es|ed|ing)|mean|nominal|statutory|range of|between|less than"
    r"|lower than)(?:\s+(?:is|was|of|at))?|[<≤]=?)\s*(?:the\s+)?"
    r"(?:(?:about|approximately|around|roughly|some)\s+)?$"
)
_STATE_AFTER = re.compile(
    r"^\s*(?:threshold|limit|trigger|setting|lfdd|level|(?:first |1st )?stage"
    r"|or (?:below|lower|less|under))\b"
)
_NOT_REACHED_BEFORE = re.compile(
    r"\b(?:not|never|no longer|nor|neither|still|yet|without)\b|n't\b"
)
_UNTIL = re.compile(r"\b(?:until|till)\b")
# Seconds that are an offset, a sampling interval or an uncertainty rather than a
# duration ("283 s after the fault", "1 s samples", "± 0.5 s", "T + 1.185 s").
_SECONDS_BEFORE = re.compile(r"(?:±|\+/-|\+|\bevery|\bper|\bwithin)\s*$")
_SECONDS_AFTER = re.compile(
    r"^\)?\s*(?:after|before|later|earlier|sampl|interval|resolution|spacing|step"
    r"|series|data\b|record)"
)
# A quantity basis that words a number of seconds as an offset from an event or a clock
# time ("16:53:41 minus 16:52:33 (after the fault)"), not as a time below a threshold.
_OFFSET_BASIS = re.compile(
    r"\b(?:after|since|following|before|prior to)\s+(?:the\s+)?(?:fault|inception"
    r"|lightning|strike|event|disturbance|incident|trip|minimum|nadir|start|onset|datum"
    r"|t\b|\d{1,2}:\d{2})"
)
_BELOW_WORDING = re.compile(r"\b(?:below|under|beneath|less than)\b|[<≤]")
# Wording next to a number of seconds that makes it a duration below the threshold
# ("for 33 s", "lasted 33 s", "duration of 33 s", "time below 49 Hz: 33 s", "= 33 s",
# "33 s below 49 Hz", "33 s strictly below"). A number of seconds read from prose
# without such wording ("took 33 s to fall to below 49 Hz") is credited only by a human.
_DURATION_BEFORE = re.compile(
    r"(?:\bfor|\blast(?:s|ed|ing)?|\bduration(?: of)?|\bperiod of|\ba total of"
    r"|\btotal(?:l?ed|l?ing)?(?: of)?|\bspent"
    r"|\b(?:time|duration|period)\b[^.;]{0,40}?\b(?:was|is|were|of|came to|comes to)"
    r"|\bcount\w*\b[^.;]{0,60}?\b(?:gives?|gave|yields?|is|was)|[:=≈])"
    r"\s*(?:(?:about|approximately|approx\.?|around|roughly|some|just|nearly|almost"
    r"|~)\s*)?$"
)
_DURATION_AFTER = re.compile(
    r"^\s*(?:\([^()]{0,40}\)\s*)?(?:(?:in total|in all|total|cumulative(?:ly)?)\s+)?"
    r"(?:(?:(?:strictly|at or|at-or-|continuously)\s*)?(?:below|under|beneath|<|≤)"
    r"|(?:of|in)\s+(?:total\s+)?(?:time|duration)\b|from the first|between the first)"
)
# A number written without a unit in a sentence about frequency ("a first trough of
# 49.083 at 16:52:59") is a candidate a human decides, never an automatic 0.
_UNITLESS_NUMBER = re.compile(r"(?<![\w.:,+±/-])(\d+\.\d+)(?![\d.,]*\d)")
_ANY_UNIT_AFTER = re.compile(
    r"^\s?\(?\s?(?:hz|hertz|mhz|millihertz|mw|megawatts?|gw|kw|w|ms|milliseconds?|s"
    r"|secs?|seconds?|mins?|minutes?|h|hrs?|hours?|kv|kva|mva|mvar|mvars|ka|a|v|km|m"
    r"|mm|%|percent|gva|gvas|pu|p\.u|rpm|x)(?![a-z])"
)
_FREQUENCY_WORDING = re.compile(r"\bhz\b|hertz|frequen|\bf\s?=")
# "49,083 Hz" read with a decimal comma (as thousands it is no grid frequency).
_DECIMAL_COMMA_HZ = re.compile(r"(?<![\w.,])(\d{2}),(\d{1,3})\s?\(?\s?(?:hz|hertz)\b")


@dataclass
class _Mention:
    """A number that may be the value of a D3 landmark or duration.

    ``times`` are the clock times that date it (see :func:`_text_mentions`): written
    next to it, the finding's ``event_time``, or computed from an offset to a written
    reference (source ``"... offset"``); ``bounds`` are references without a number
    ("after the fault at 16:52:33"), which only bound its time. ``weak`` says why a
    mention without any time is not a candidate (threshold or statistic wording, or
    described as before the event); ``doubt`` says why a prose mention with a time is
    credited only by a human (a state, statistic or "not yet" wording);
    ``excluded`` says why a mention is never a candidate (seconds that are an offset or
    sampling interval); ``unsettled`` says why a candidate is credited only by a human
    (no unit written, no duration wording); ``context`` are the times in the finding's
    derivation and quantity basis, which place a mention without a time of its own
    (e.g. a pre-event average computed over 16:40-16:52)."""

    value: float | None
    source: str  # quantity, statement, derivation, unrecognised_unit or report
    times: list[tuple[datetime, str]]
    location: str  # the finding_id, or the report location
    finding: Mapping[str, Any] | None = None
    weak: str | None = None
    doubt: str | None = None
    excluded: str | None = None
    unsettled: str | None = None
    unitless: bool = False
    context: list[datetime] = field(default_factory=list)
    bounds: list[tuple[str, datetime]] = field(default_factory=list)


def _containing(
    spans: Sequence[tuple[int, int]], pos: int, end: int
) -> tuple[int, int]:
    return next(((a, b) for a, b in spans if a <= pos < b), (0, end))


def _seconds_not_a_duration(text: str, start: int, end: int) -> bool:
    """Whether the seconds at ``text[start:end]`` are worded as an offset, a sampling
    interval or an uncertainty."""
    before, after = text[max(0, start - 60) : start], text[end : end + 60]
    return bool(_SECONDS_BEFORE.search(before) or _SECONDS_AFTER.search(after))


def _unitless_spans(text: str) -> list[tuple[float, int, int]]:
    """Decimal numbers written without any unit in sentences about frequency."""
    masked = text
    for _, start, end in _time_spans(text):
        masked = _blank(masked, start, end)
    sentences = _spans(text, _SENTENCE_BREAK)
    found = []
    for match in _UNITLESS_NUMBER.finditer(masked):
        if _ANY_UNIT_AFTER.match(masked[match.end() : match.end() + 12]):
            continue
        sa, sb = _containing(sentences, match.start(), len(text))
        if _FREQUENCY_WORDING.search(text[sa:sb]):
            found.append((float(match.group(1)), match.start(), match.end()))
    return found


def _text_mentions(
    text: str,
    unit: str,
    aliases: Mapping[str, Sequence[str]],
    value_range: tuple[float, float],
    *,
    source: str,
    location: str,
    finding: Mapping[str, Any] | None = None,
    first: Sequence[tuple[datetime, str]] = (),
    last: Sequence[tuple[datetime, str]] = (),
) -> list[_Mention]:
    """Values of ``unit`` within ``value_range`` written in normalised ``text``, each
    with the clock times paired to it.

    Each time written in a clause is paired with the nearest value of the unit in that
    clause (the preceding one on ties), so in "fell from 49.995 Hz at 16:52:33 to a
    minimum of 48.787 Hz at 16:53:49" each value gets its own time. A time that is the
    reference of an offset dates the value at the computed time ("50.0 Hz 207 s after its
    minimum at 16:53:49" is 50.0 Hz at 16:57:16); a reference without a number only
    bounds it (see :func:`_resolved_time_spans`). A value with no time of its own takes
    ``first`` (the finding's ``event_time``), else the times of the text that no value
    claims, else ``last``. For Hz, decimal numbers written without a unit in a sentence
    about frequency are read too, as unsettled mentions."""
    lo, hi = value_range
    values = [(v, s, e, "") for v, s, e in _text_value_spans(text, unit, aliases)]
    if unit == "Hz":
        values += [
            (v, s, e, "written without a unit") for v, s, e in _unitless_spans(text)
        ]
        commas = [
            (
                float(f"{m.group(1)}.{m.group(2)}"),
                m.start(),
                m.end(),
                "written with a decimal comma",
            )
            for m in _DECIMAL_COMMA_HZ.finditer(text)
        ]
        # the decimal reading replaces the thousands reading of the same number
        values = [
            v for v in values if not any(c[1] <= v[1] < c[2] for c in commas)
        ] + commas
        values.sort(key=lambda item: item[1])
    clauses = _spans(text, _CLAUSE_BREAK)
    sentences = _spans(text, _SENTENCE_BREAK)
    owned: list[list[tuple[str, datetime]]] = [[] for _ in values]
    unowned: list[tuple[str, datetime]] = []
    for kind, when, ts, te in _resolved_time_spans(text):
        a, b = _containing(clauses, ts, len(text))
        # (written without a unit, distance): a value written with its unit claims
        # the time before a bare number in the same clause does
        nearest: tuple[tuple[bool, int, int], int] | None = None
        for i, (_, vs, ve, bare) in enumerate(values):
            if not a <= vs < b:
                continue
            if ve <= ts:
                distance = (bool(bare), ts - ve, 0)
            elif vs >= te:
                distance = (bool(bare), vs - te, 1)
            else:
                distance = (bool(bare), 0, 0)
            if nearest is None or distance < nearest[0]:
                nearest = (distance, i)
        if nearest is None:
            unowned.append((kind, when))
        else:
            owned[nearest[1]].append((kind, when))

    def dating(items: Sequence[tuple[str, datetime]]) -> list[tuple[datetime, str]]:
        return [
            (t, source if kind == "at" else f"{source} offset")
            for kind, t in items
            if kind in ("at", "offset")
        ]

    mentions = []
    for i, (value, vs, ve, unitless) in enumerate(values):
        if not lo <= value <= hi:
            continue
        times = dating(owned[i]) or list(first) or dating(unowned) or list(last)
        bounds = [(kind, t) for kind, t in owned[i] if kind in ("after", "before")]
        before, after = text[max(0, vs - 60) : vs], text[ve : ve + 60]
        ca, cb = _containing(clauses, vs, len(text))
        weak = doubt = excluded = unsettled = None
        if unit == "s":
            if _seconds_not_a_duration(text, vs, ve):
                excluded = "an offset, sampling interval or uncertainty"
            elif not (_DURATION_BEFORE.search(before) or _DURATION_AFTER.search(after)):
                unsettled = "no wording next to it makes it a duration below 49 Hz"
        else:
            if _THRESHOLD_BEFORE.search(before) or _THRESHOLD_AFTER.search(after):
                weak = "a threshold, limit or statistic"
            else:
                sa, sb = _containing(sentences, vs, len(text))
                if _PRE_EVENT.search(text[sa:sb]):
                    weak = "described as before the event"
            if _STATE_BEFORE.search(before) or _STATE_AFTER.search(after):
                doubt = "it is worded as a level, threshold or statistic"
            elif _NOT_REACHED_BEFORE.search(text[ca:vs]) or _UNTIL.search(text[ca:cb]):
                doubt = "its clause says the landmark was not (yet) reached"
        if unitless:
            unsettled = unitless
        mentions.append(
            _Mention(
                value=value,
                source=source,
                times=times,
                location=location,
                finding=finding,
                weak=weak,
                doubt=doubt,
                excluded=excluded,
                unsettled=unsettled,
                unitless=bool(unitless),
                bounds=bounds,
            )
        )
    return mentions


def _d3_finding_times(finding: Mapping[str, Any]) -> list[tuple[datetime, str]]:
    """The finding's ``event_time`` when it has one; otherwise the times its statement
    dates something at (written times, and times computed from an offset)."""
    if finding.get("event_time"):
        try:
            return [(parse_iso_instant(finding["event_time"]), "event_time")]
        except LocatorError:
            pass
    return _dating_times(finding.get("statement", ""), "statement")


def _offset_quantity(
    finding: Mapping[str, Any], value: float, aliases: Mapping[str, Sequence[str]]
) -> bool:
    """Whether a structured quantity in seconds is worded as an offset rather than a
    duration: its statement writes the same number only as an offset ("68 s after the
    fault"), or its basis words it as one ("16:53:41 minus 16:52:33 (after the
    fault)") without any below-threshold wording."""
    basis = normalise(str((finding.get("quantity") or {}).get("basis") or ""))
    if _OFFSET_BASIS.search(basis) and not _BELOW_WORDING.search(basis):
        return True
    statement = normalise(finding.get("statement", ""))
    same = [
        _seconds_not_a_duration(statement, s, e)
        for v, s, e in _text_value_spans(statement, "s", aliases)
        if abs(v - value) < 1e-6
    ]
    return bool(same) and all(same)


def _finding_mentions(
    finding: Mapping[str, Any],
    unit: str,
    value_range: tuple[float, float],
    ctx: _Ctx,
) -> list[_Mention]:
    """Every mention a finding offers: its structured ``quantity`` (when its unit
    converts to ``unit``, it is within ``value_range`` and, in seconds, it is not worded
    as an offset), the values written in its statement and derivation, and a quantity
    in a unit the grader cannot read."""
    fid = finding["finding_id"]
    lo, hi = value_range
    statement = ctx.text(finding)
    event = (
        [t for t in _d3_finding_times(finding) if t[1] == "event_time"]
        if finding.get("event_time")
        else []
    )
    context = [
        t
        for name in ("derivation", "quantity.basis")
        for t, _ in _dating_times(_finding_field(finding, name), name)
    ]
    state, q = _quantity_state(finding, unit, ctx.aliases)
    if state == "ok" and unit == "s" and q is not None:
        if _offset_quantity(finding, q, ctx.aliases):
            state = "offset"
    out: list[_Mention] = []
    if state == "ok" and q is not None and lo <= q <= hi:
        out.append(
            _Mention(
                value=q,
                source="quantity",
                times=_d3_finding_times(finding),
                location=fid,
                finding=finding,
                weak="described as before the event"
                if _PRE_EVENT.search(statement)
                else None,
            )
        )
    statement_clock = _dating_times(statement, "statement")
    out += _text_mentions(
        statement,
        unit,
        ctx.aliases,
        value_range,
        source="statement",
        location=fid,
        finding=finding,
        first=event,
    )
    out += _text_mentions(
        normalise(str(finding.get("derivation") or "")),
        unit,
        ctx.aliases,
        value_range,
        source="derivation",
        location=fid,
        finding=finding,
        first=event,
        last=statement_clock,
    )
    if state == "unrecognised":
        try:
            raw = float(finding["quantity"]["value"])
        except (TypeError, ValueError):
            raw = None
        if raw is not None and lo <= raw <= hi:
            out.append(
                _Mention(
                    value=None,
                    source="unrecognised_unit",
                    times=_d3_finding_times(finding),
                    location=fid,
                    finding=finding,
                )
            )
    for mention in out:
        mention.context = context
    return out


def _identifying(value: float) -> bool:
    """A value written to at least three decimals (48.787) identifies one landmark; a
    round value (50, 49.27) may be repeated for different moments."""
    return abs(round(value * 100, 6) - round(value * 100)) > 1e-6


@dataclass
class _Selection:
    """What :func:`_select_numeric` found for a D3 criterion."""

    candidates: list[dict[str, Any]]
    others: list[dict[str, Any]]
    # candidates without a time, set aside because another finding is placed in the
    # window (pointed out to the reviewer when nothing in the window is credited)
    untimed: list[dict[str, Any]]
    # values dated outside the window by a time written next to them (not candidates)
    dated_outside: list[dict[str, Any]]


def _select_numeric(auto: Mapping[str, Any], ctx: _Ctx, with_time: bool) -> _Selection:
    """Candidates for a D3 landmark or duration.

    ``candidates`` come from findings with a status the criterion selects: the
    structured ``quantity`` when it fits the criterion (unit, value range, in seconds
    not worded as an offset and, for a landmark, a time in the window or no time at
    all), together with the values written in its statement and derivation, which count
    only when the quantity is outside tolerance and are then left to a human; otherwise
    the values written in the statement and derivation (e.g. a quantity that gives the
    seconds after the fault or the size of a frequency drop); otherwise a quantity in a
    unit the grader cannot read. For a landmark, a value dated in the window is
    preferred over any value without a time.

    ``others`` are the same kinds of mention in findings of any other status and in the
    report text, and values dated outside the window only by an offset computed from a
    reference time. They never earn credit; they keep a criterion with no credited
    finding from being decided as absent (a human reviews them instead).

    A value dated outside the window by a time written next to it is not a candidate
    (it describes another moment). A mention without any time is not a candidate when
    its wording makes it a threshold, limit or statistic, when it is described as before
    the event, when a reference ("after the minimum at 16:53:49") places it outside the
    window, when the finding's derivation or quantity basis dates it outside the window,
    or when the same precise value is dated outside the window elsewhere in the
    submission by a written time. Each entry's ``unsettled`` says why it is credited
    only by a human; ``keep`` says when an unsettled entry is kept at all (see
    :func:`_score_landmark`).
    """
    select = auto["select"]
    unit = select["units"][0]
    lo, hi = select.get("value_range", [float("-inf"), float("inf")])
    window = select.get("time_window") if with_time else None
    start = parse_iso_instant(window[0]) if window else None
    end = parse_iso_instant(window[1]) if window else None
    statement_any = select.get("statement_any")

    def in_window(times: Sequence[tuple[datetime, str]]) -> list[tuple[datetime, str]]:
        return [t for t in times if start <= t[0] <= end]

    def written(times: Sequence[tuple[datetime, str]]) -> bool:
        return any(not src.endswith("offset") for _, src in times)

    per_finding: list[tuple[Mapping[str, Any], bool, list[_Mention]]] = []
    for finding in ctx.findings:
        if statement_any and not _any(ctx.text(finding), statement_any):
            continue
        selected = ctx.status_ok(finding, select.get("statuses"))
        per_finding.append(
            (finding, selected, _finding_mentions(finding, unit, (lo, hi), ctx))
        )
    in_report = [
        mention
        for location, sentence in ctx.report
        if not statement_any or _any(sentence, statement_any)
        for mention in _text_mentions(
            sentence, unit, ctx.aliases, (lo, hi), source="report", location=location
        )
    ]
    mentions = [m for _, _, ms in per_finding for m in ms] + in_report
    dated_outside = {
        round(m.value, 6)
        for m in mentions
        if window
        and m.value is not None
        and m.times
        and not in_window(m.times)
        and written(m.times)
    }

    def classify(m: _Mention) -> str:
        """``use`` (a candidate), ``other`` (dated outside the window only by an
        offset: for the reviewer) or ``drop``."""
        if m.excluded:
            return "drop"
        if not window:
            return "use"
        if m.times:
            if in_window(m.times):
                return "use"
            return "drop" if written(m.times) else "other"
        if any(
            (kind == "after" and t > end) or (kind == "before" and t < start)
            for kind, t in m.bounds
        ):
            return "drop"
        if m.weak:
            return "drop"
        if m.context and not any(start <= t <= end for t in m.context):
            return "drop"
        if (
            m.value is not None
            and _identifying(m.value)
            and round(m.value, 6) in dated_outside
        ):
            return "drop"
        return "use"

    def entry(m: _Mention, beside: Mapping[str, Any] | None = None) -> dict[str, Any]:
        times = in_window(m.times) if window else list(m.times)
        outside = bool(window and m.times and not times)
        if outside:  # an offset dates it outside the window: show that time
            times = list(m.times)
        reasons: list[str] = []
        keep: list[str] = []
        if m.doubt and m.times:  # a level or "not yet" with a time
            reasons.append(m.doubt)
            keep.append("within")
        if m.unsettled:
            reasons.append(m.unsettled)
            keep.append("value" if m.unitless else "always")
        if beside is not None:
            q = beside.get("quantity") or {}
            reasons.append(
                f"the structured quantity of {beside['finding_id']} "
                f"({q.get('value')} {q.get('unit')}) gives another value"
            )
            keep.append("better")
        return {
            "finding": m.finding,
            "location": m.location,
            "value": m.value,
            "value_source": m.source,
            "times": times,
            "timed": bool(times) and not outside,
            "outside_window": outside,
            "unsettled": "; ".join(reasons) or None,
            "keep": keep,
        }

    candidates: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []
    for finding, selected, found in per_finding:
        sorted_out = [(m, classify(m)) for m in found]

        def use(sources: tuple[str, ...]) -> list[_Mention]:
            return [m for m, c in sorted_out if m.source in sources and c == "use"]

        chosen = [entry(m) for m in use(("quantity",))]
        prose = use(("statement", "derivation"))
        if chosen:
            # the quantity outside tolerance must not hide the statement's values
            chosen += [entry(m, beside=finding) for m in prose]
        else:
            chosen = [entry(m) for m in prose] or [
                entry(m) for m in use(("unrecognised_unit",))
            ]
        (candidates if selected else others).extend(chosen)
        others += [entry(m) for m, c in sorted_out if c == "other"]
    others += [entry(m) for m in in_report if classify(m) in ("use", "other")]
    untimed: list[dict[str, Any]] = []
    if window:
        # A finding without any time is considered only when no finding is placed in
        # the window (it cannot be told apart from the other landmarks otherwise).
        timed = [c for c in candidates if c["timed"]]
        if timed:
            untimed = [c for c in candidates if not c["timed"]]
            candidates = timed
    outside_written = [
        entry(m)
        for m in mentions
        if window
        and not m.excluded
        and not m.weak
        and m.times
        and not in_window(m.times)
        and written(m.times)
    ]
    return _Selection(candidates, others, untimed, outside_written)


def _evaluate_numeric(
    cand: Mapping[str, Any], auto: Mapping[str, Any], with_time: bool
) -> dict[str, Any]:
    if cand["value"] is None:
        value_level, value_error = 0.0, None
    else:
        value_level, value_error = _level_value(cand["value"], auto["value"])
    time_ok: bool | None = None
    time_error = None
    time_source = None
    if with_time:
        spec = auto["time"]
        errors = [(_time_error(t, spec), src) for t, src in cand["times"]]
        if errors:
            time_error, time_source = min(errors)
            time_ok = time_error <= float(spec["tol_s"]) + 1e-9
        else:
            time_ok = False
        level = 1.0 if value_level >= 1 and time_ok else 0.0
    else:
        level = value_level
    finding = cand.get("finding")
    out = {
        "finding_id": finding["finding_id"] if finding else None,
        "value": cand["value"],
        "value_source": cand["value_source"],
        "value_error": None if value_error is None else round(value_error, 6),
        "value_level": value_level,
        "time_ok": time_ok,
        "time_error_s": None if time_error is None else round(time_error, 3),
        "time_source": time_source,
        "level": level,
    }
    if with_time:
        out["timed"] = cand["timed"]
        out["times"] = [t.isoformat() for t, _ in cand["times"]]
    if cand.get("unsettled"):
        # credited only by a human: never an automatic level above 0
        out["unsettled"] = cand["unsettled"]
        out["level_if_settled"] = level
        out["level"] = 0.0
    return out


def _evaluate_kept(
    cands: Sequence[Mapping[str, Any]], auto: Mapping[str, Any], with_time: bool
) -> list[dict[str, Any]]:
    """Evaluate candidates, dropping unsettled ones their ``keep`` rules exclude:
    ``within`` (a threshold or "not yet" wording with a time: kept only when value and
    time are within tolerance), ``value`` (no unit: kept only when the value is within
    tolerance and any time is too) and ``better`` (a statement value beside a structured
    quantity: kept only when it scores higher than the quantity)."""
    evaluated = [(c, _evaluate_numeric(c, auto, with_time)) for c in cands]
    quantity_level: dict[str | None, float] = {}
    for _, e in evaluated:
        if e["value_source"] == "quantity":
            fid = e["finding_id"]
            quantity_level[fid] = max(quantity_level.get(fid, 0.0), e["level"])
    out = []
    for cand, e in evaluated:
        rules = cand.get("keep") or []
        raw = e.get("level_if_settled", e["level"])
        if "within" in rules and raw <= 0:
            continue
        if "value" in rules and not (
            e["value_level"] >= 1 and (not e.get("timed") or e["time_ok"])
        ):
            continue
        if "better" in rules and raw <= quantity_level.get(e["finding_id"], 0.0):
            continue
        e["location"] = cand["location"]
        if cand.get("finding"):
            e["status"] = cand["finding"].get("status")
        if cand.get("outside_window"):
            e["outside_window"] = True
        out.append(e)
    return out


def _describe_other(other: Mapping[str, Any], unit: str) -> str:
    value = (
        "a value in an unrecognised unit"
        if other["value"] is None
        else f"{other['value']:g} {unit}"
    )
    when = f" at {', '.join(other['times'])}" if other.get("times") else ""
    if other.get("outside_window"):
        when += " (an offset dates it outside the window)"
    where = other["location"]
    if other.get("status"):
        where += f" (status {other['status']})"
    return f"{value}{when} in {where}"


def _raw_level(e: Mapping[str, Any]) -> float:
    return float(e.get("level_if_settled", e["level"]))


def _candidate_order(e: Mapping[str, Any]) -> tuple:
    return (
        -e["level"],
        -_raw_level(e),
        float("inf") if e["value_error"] is None else e["value_error"],
        e["time_error_s"] or 0.0,
        e["value_source"] != "quantity",
    )


def _score_landmark(auto: Mapping[str, Any], ctx: _Ctx, kind: str) -> dict[str, Any]:
    with_time = kind == "landmark"
    windowed = with_time and bool(auto["select"].get("time_window"))
    unit = auto["select"]["units"][0]
    selection = _select_numeric(auto, ctx, with_time)

    evaluated = sorted(
        _evaluate_kept(selection.candidates, auto, with_time),
        key=lambda e: (*_candidate_order(e), ctx.order[e["finding_id"]]),
    )
    unique: list[dict[str, Any]] = []
    for e in evaluated:  # each finding's best value only
        if all(u["finding_id"] != e["finding_id"] for u in unique):
            unique.append(e)
    evaluated = unique
    others = sorted(
        _evaluate_kept(selection.others, auto, with_time), key=_candidate_order
    )
    untimed = _evaluate_kept(selection.untimed, auto, with_time)
    best = evaluated[0] if evaluated else None
    settled = next((e for e in evaluated if not e.get("unsettled")), None)
    floor = settled["level"] if settled else 0.0
    # unsettled values that would score higher than anything credited automatically
    open_values = [e for e in evaluated if e.get("unsettled") and _raw_level(e) > floor]
    conflicts = []
    if best is not None and best["level"] > 0:
        for other in evaluated[1:]:
            # Only structured quantities are reported as conflicting values: a number
            # read from prose may describe something else (e.g. the 49 Hz threshold).
            if other["level"] < best["level"] and other["value_source"] == "quantity":
                conflicts.append(
                    {
                        "finding_id": other["finding_id"],
                        "value": other["value"],
                        "note": "another finding in the same window gives a value outside "
                        "tolerance",
                    }
                )
    listed = "; ".join(_describe_other(o, unit) for o in others[:5])

    def reason(e: Mapping[str, Any]) -> str:
        if e["level"] >= 1:
            text = (
                "value and time within tolerance"
                if with_time
                else "within the full tolerance"
            )
        elif e["level"] > 0:
            text = "within the half tolerance"
        else:
            reasons = []
            if e["value_error"] is None:
                reasons.append("quantity unit not recognised")
            elif e["value_level"] < 1:
                reasons.append(f"value off by {e['value_error']:g}")
            if with_time and not e["time_ok"]:
                reasons.append(
                    "time not stated"
                    if e["time_error_s"] is None
                    else f"time off by {e['time_error_s']:g} s"
                )
            text = "; ".join(reasons) or "outside tolerance"
        if e["value_source"] != "quantity":
            text += f" ({e['value_source'].replace('_', ' ')})"
        return text

    decided = True
    if best is None:
        basis = "no finding reports this landmark (unit and time window)"
        if others:
            decided = False
            basis = (
                "needs human review: "
                + basis
                + " among the findings with a factual status, but a candidate value "
                f"appears elsewhere: {listed}"
            )
        else:
            basis += "; no candidate value anywhere in the submission"
            outside = [
                f"{e['value']:g} {unit} at "
                f"{', '.join(t.isoformat() for t, _ in e['times'])} in {e['location']}"
                for e in selection.dated_outside[:5]
            ]
            if outside:
                basis += (
                    " (values dated outside the window describe other moments: "
                    + "; ".join(outside)
                    + ")"
                )
    elif open_values:
        decided = False
        basis = (
            "needs human review: "
            + "; ".join(
                f"{_describe_other(e, unit)} would be within "
                f"{'the half ' if _raw_level(e) < 1 else ''}tolerance, but "
                f"{e['unsettled']}"
                for e in open_values[:5]
            )
            + (
                f"; best candidate credited automatically: {reason(settled)}"
                if settled
                else ""
            )
        )
    else:
        basis = reason(best)
    if best is not None and not open_values and best["level"] == 0:
        # A structured quantity placed in the window (any quantity for a duration) and
        # outside tolerance is decided; anything less certain goes to a human: values
        # read from prose, quantities in units the grader cannot read, and quantities
        # without a time in the window.
        unsettled = [
            e["finding_id"] for e in evaluated if e["value_source"] != "quantity"
        ]
        if unsettled:
            decided = False
            basis = (
                "needs human review: no structured quantity within tolerance and "
                f"{', '.join(unsettled)} state(s) values only in the statement or "
                f"derivation text or in an unrecognised unit; best candidate: {basis}"
            )
        elif windowed and not best["timed"]:
            decided = False
            basis = (
                "needs human review: the structured quantity of "
                f"{best['finding_id']} has no time in the landmark window, so it may "
                f"describe another moment; best candidate: {basis}"
            )
        else:
            within = [o for o in others if _raw_level(o) >= 1] + [
                u for u in untimed if u["value_level"] >= 1
            ]
            if within:  # decided, but point the reviewer at the inconsistency
                basis += (
                    "; note: a value within tolerance also appears in "
                    + "; ".join(_describe_other(o, unit) for o in within[:5])
                )
    return {
        "content": best["level"] if best else 0.0,
        "decided": decided,
        "basis": basis,
        "candidates": evaluated,
        "other_candidates": others,
        "matched_finding_ids": [best["finding_id"]] if best else [],
        "considered_finding_ids": [e["finding_id"] for e in evaluated],
        "elements": [],
        "contradictions": [],
        "conflicts": conflicts,
    }


def _convention_note(
    spec: Mapping[str, Any], assessments: Mapping[str, Mapping[str, Any]], ctx: _Ctx
) -> str | None:
    """Reviewer aid (``auto.convention_check``, never scored): whether the duration
    convention stated in the finding credited for the duration criterion reproduces the
    duration it reports. "Count of 33 samples at or below 49 Hz" does not (at or below
    gives 34 s)."""
    duration = assessments.get(spec["criterion"]) or {}
    best = (duration.get("candidates") or [None])[0]
    if not best or best.get("finding_id") is None or best.get("value") is None:
        return None
    finding = next(f for f in ctx.findings if f["finding_id"] == best["finding_id"])
    text = ctx.field_text(finding, _FINDING_FIELDS)
    stated = [c for c in spec["conventions"] if _any(text, c["patterns"])]
    tol = float(spec.get("abs_tol", 0.5)) + 1e-9
    if not stated or any(abs(best["value"] - float(c["value"])) <= tol for c in stated):
        return None
    listed = "; ".join(f"{c['label']} gives {float(c['value']):g} s" for c in stated)
    return (
        f"note: the convention {best['finding_id']} states does not reproduce the "
        f"{best['value']:g} s it reports for {spec['criterion']} ({listed})"
    )


def _assess_criterion(crit: Mapping[str, Any], ctx: _Ctx) -> dict[str, Any]:
    auto = crit.get("auto") or {"kind": "none"}
    kind = auto.get("kind", "none")
    if kind in ("landmark", "duration"):
        return _score_landmark(auto, ctx, kind)
    if kind == "rules":
        return _score_rules(auto, ctx)
    return {
        "content": None,
        "basis": "no automated check",
        "elements": [],
        "contradictions": [],
        "matched_finding_ids": [],
        "conflicts": [],
    }


# A cited span "targets" a keyed span when it is at most this many times as long (with
# a floor in lines/samples) and covers less than this share of a line-numbered document.
_TARGET_FACTOR = 3
_TARGET_FLOOR = 8
_WHOLE_DOCUMENT_SHARE = 0.5


def _span_size(loc: Locator, evidence_id: str, catalogue: Catalogue) -> float | None:
    if loc.kind == "lines":
        return float(loc.end - loc.start + 1)
    span = _instants(loc, evidence_id, catalogue)
    if span is None:
        return None
    doc = catalogue.get(evidence_id)
    step = doc.timeseries.interval_s if doc and doc.timeseries else 1
    return (span[1] - span[0]).total_seconds() / step + 1


def _targets(
    check: CitationCheck, keyed: Mapping[str, Any], catalogue: Catalogue
) -> bool:
    """Whether an overlapping citation is specific to the keyed span (not a citation of
    a large part or the whole of the document)."""
    doc = catalogue.get(check.evidence_id)
    loc = check.locator_obj
    if doc is None or loc is None:
        return False
    try:
        target = parse_and_validate(keyed["locator"], doc)
    except LocatorError:
        return False
    cited = _span_size(loc, check.evidence_id, catalogue)
    wanted = _span_size(target, check.evidence_id, catalogue)
    if cited is None or wanted is None:
        return False
    if (
        loc.kind == "lines"
        and doc.lines
        and cited >= _WHOLE_DOCUMENT_SHARE * len(doc.lines)
    ):
        return False
    return cited <= max(_TARGET_FACTOR * wanted, _TARGET_FLOOR)


def _assess_evidence(
    crit: Mapping[str, Any], assessment: Mapping[str, Any], ctx: _Ctx
) -> dict[str, Any]:
    """Automated evidence support: decided for D3 landmarks and for uncited/absent
    findings; otherwise a proposal for the human reviewer."""
    auto = crit.get("auto") or {}
    matched = list(assessment["matched_finding_ids"])
    checks = [c for fid in matched for c in ctx.citations.get(fid, [])]
    if not matched:
        return {
            "value": None,
            "decided": True,
            "proposal": None,
            "not_applicable": True,
            "basis": "no finding addresses the criterion",
            "citations": [],
        }
    if not checks:
        return {
            "value": 0,
            "decided": True,
            "proposal": 0,
            "basis": "the matching findings cite no evidence",
            "citations": [],
        }
    if not assessment.get("content"):
        prefix = "content proposal is 0; "
    else:
        prefix = ""
    cited = [c.to_dict() for c in checks]
    unresolvable = [c for c in checks if not c.resolvable]
    if auto.get("kind") in ("landmark", "duration"):
        ev = auto.get("evidence") or {}
        doc_id = ev.get("evidence_id", "R01")
        relevant = [c for c in checks if c.evidence_id == doc_id and c.resolvable]
        needed = [parse_iso_instant(t) for t in ev.get("must_cover", [])]
        uncovered = [
            t.isoformat()
            for t in needed
            if not any(_covers(c, t, ctx.catalogue) for c in relevant)
        ]
        retrieved = None
        if ctx.trace_info is not None:
            retrieved = doc_id in set(ctx.trace_info.get("retrieved") or [])
        decided = True
        if not relevant:
            basis = f"no resolvable {doc_id} time/row citation"
            value = 0
        elif uncovered:
            basis = f"{doc_id} citations do not cover {', '.join(uncovered)}"
            value = 0
        elif retrieved is False:
            basis = f"{doc_id} was cited but never retrieved during the episode"
            value = 0
        else:
            basis = (
                f"{doc_id} citation covers {', '.join(t.isoformat() for t in needed)}"
                + ("" if retrieved else " (retrieval not checked: no trace)")
            )
            value = 1
            # e = 1 needs "any required calculation": a derived value must say how it
            # was computed, and the series must have been analysed in the episode.
            by_id = {f["finding_id"]: f for f in ctx.findings}
            if ev.get("require_derivation"):
                missing = [
                    fid
                    for fid in matched
                    if not str(by_id.get(fid, {}).get("derivation") or "").strip()
                ]
                if missing:
                    decided = False
                    basis += (
                        f"; {', '.join(missing)} gives no derivation for this derived "
                        "value: needs human review"
                    )
            if (
                doc_id == "R01"
                and ctx.trace_info is not None
                and ctx.trace_info.get("r01_analysed_with_python") is False
            ):
                decided = False
                basis += (
                    "; R01 was never analysed with run_python in the episode: needs "
                    "human review"
                )
        return {
            "value": value if decided else None,
            "decided": decided,
            "proposal": value,
            "basis": basis,
            "citations": cited,
        }
    overlaps: list[tuple[CitationCheck, Mapping[str, Any]]] = []
    for check in checks:
        for keyed in crit.get("visible_evidence", []):
            if _overlaps(check, keyed, ctx.catalogue):
                if crit["criterion_id"] not in check.keyed_overlap:
                    check.keyed_overlap.append(crit["criterion_id"])
                overlaps.append((check, keyed))
    primary = [(c, k) for c, k in overlaps if k.get("role", "primary") == "primary"]
    targeted = [c for c, k in primary if _targets(c, k, ctx.catalogue)]
    retrieved_ok = [c for c in targeted if c.retrieved is not False]

    def names(items: Iterable[CitationCheck]) -> str:
        return ", ".join(sorted({f"{c.evidence_id} {c.normalized}" for c in items}))

    if retrieved_ok:
        proposal, basis = 1, "cites keyed evidence spans " + names(retrieved_ok)
    elif targeted:
        proposal, basis = 0, "keyed spans cited but the document was never retrieved"
    elif primary:
        proposal, basis = (
            None,
            "cited range much larger than the keyed span ("
            + names(c for c, _ in primary)
            + "): needs human review",
        )
    elif overlaps:
        proposal, basis = (
            None,
            "cites only context spans (" + names(c for c, _ in overlaps) + "), not the "
            "evidence for the claim: needs human review",
        )
    else:
        proposal, basis = (
            None,
            "citations do not overlap the keyed spans: needs human review (alternative "
            "evidence is allowed)",
        )
    if unresolvable:
        basis += f"; {len(unresolvable)} unresolvable citation(s)"
    basis = prefix + basis
    return {
        "value": None,
        "decided": False,
        "proposal": proposal,
        "basis": basis,
        "citations": [c.to_dict() for c in checks],
    }


# -- severe flags and labelling ----------------------------------------------------
_HEDGES = (
    r"\bmay\b",
    r"\bmight\b",
    r"\bpossibl",
    r"\bprobabl",
    r"\blikely\b",
    r"\bperhaps\b",
    r"\bhypothes",
    r"\bsuspect",
    r"\bappears? to\b",
    r"\bseems? to\b",
)
# Inferential wording that suggests a finding is the agent's inference rather than an
# observation or a reported statement (the key's conventions.inferential_patterns
# override this default). Only a review proposal: it never changes a grade.
_INFERENTIAL = (
    r"\bconsistent with\b",
    r"\bsuggest(s|ed|ing)?\b",
    r"\bindicat(e|es|ed|ing)\b",
    r"\blikely\b",
    r"\btherefore\b",
    r"\bimpl(y|ies|ied|ying)\b",
    r"\battributed to\b",
    r"\bthus\b",
    r"\bhence\b",
)
_INFERENTIAL_STATUSES = ("observed", "reported")
# Quoted spans (after normalise() unifies quote characters) are the record's own words:
# an inference quoted from a source is correctly 'reported'. A single-quoted span opens
# and closes at a word edge, so apostrophes ("operator's", "operators'") are not quotes.
_QUOTED = re.compile(r'"[^"]*"' r"|(?<!\w)'(?=\S)(?:[^']|'(?=\w))*?(?<=\S)'(?!\w)")
# A clause that attributes its words to a named source (a source and an attribution
# verb in the same clause) reports the record's account, which may itself use words
# such as 'indicate', 'suggests' or 'therefore' (the key's
# conventions.inferential_attribution overrides these defaults).
_ATTRIBUTION_SOURCES = (
    r"\beso\b",
    r"\bnget\b",
    r"national grid",
    r"\bofgem\b",
    r"\brwe\b",
    r"ørsted",
    r"\borsted\b",
    r"\bneso\b",
    r"\bgrid code\b",
    r"\b(the|its) (operator|regulator|system operator|network owner|station|manufacturer)\b",
    r"\boperator'?s\b",
    r"\b(r01|r03|s01|s03|s04)\b",
    r"\b(the|its) (\w+ )?(log|record|report|account|investigation|statement|narrative|soe)\b",
)
_ATTRIBUTION_VERBS = (
    r"\bstates\b",
    r"\bstated\b",
    r"\bsays\b",
    r"\bsaid\b",
    r"\baccording to\b",
    r"\bconclude[sd]\b",
    r"\bnotes\b",
    r"\bnoted\b",
    r"\bwrites\b",
    r"\bwrote\b",
    r"\bfinds\b",
    r"\bfound\b",
    r"\bconfirm(s|ed)\b",
    r"\bexplain(s|ed)\b",
    r"\b(reports|records) (that|a|an|the|its|their)\b",
    r"\b(reported|recorded|described|stated|given) (by|that)\b",
    r"\bdescribes\b",
    r"\bassess(es|ed)\b",
    r"\bview\b",
    r"\bbelieves?\b",
    r"\bconsider(s|ed)\b",
    r"\bin (its|their) words\b",
)
_ATTRIBUTION_CLAUSE = re.compile(r"[;.!?](?=\s|$)")


def _inferential_terms(
    statement: str,
    patterns: Sequence[str],
    attribution: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """Inferential wording in a statement outside quoted spans and outside clauses
    (split at ';' and sentence ends) that attribute their words to a named source."""
    attribution = attribution or {}
    sources = tuple(attribution.get("sources") or _ATTRIBUTION_SOURCES)
    verbs = tuple(attribution.get("verbs") or _ATTRIBUTION_VERBS)
    text = _QUOTED.sub(" ", normalise(statement))
    clauses = [
        text[a:b]
        for a, b in _spans(text, _ATTRIBUTION_CLAUSE)
        if not (_any(text[a:b], sources) and _any(text[a:b], verbs))
    ]
    found: list[str] = []
    for pattern in patterns:
        for clause in clauses:
            match = _rx(pattern).search(clause)
            if match and match.group(0) not in found:
                found.append(match.group(0))
                break
    return found


def _status_inferential_language(
    findings: Sequence[Mapping[str, Any]],
    patterns: Sequence[str],
    attribution: Mapping[str, Sequence[str]] | None = None,
) -> list[dict[str, Any]]:
    """Findings labelled observed or reported whose statement reads as an inference
    (e.g. 'consistent with', 'suggests', 'therefore'): the reviewer decides whether the
    status should be inferred (or hypothesis). Never scored automatically."""
    out = []
    for finding in findings:
        if finding["status"] not in _INFERENTIAL_STATUSES:
            continue
        terms = _inferential_terms(finding.get("statement", ""), patterns, attribution)
        if terms:
            out.append(
                {
                    "finding_id": finding["finding_id"],
                    "status": finding["status"],
                    "terms": terms,
                    "issue": f"inferential wording with status {finding['status']}: is "
                    "this the agent's inference (status inferred) or a hypothesis? "
                    "Proposal for the reviewer; not scored.",
                }
            )
    return out


def _report_texts(sub: Mapping[str, Any]) -> list[tuple[str, str]]:
    report = sub["report"]
    texts = [("report.executive_summary", report["executive_summary"])]
    for i, section in enumerate(report.get("sections", [])):
        texts.append((f"report.sections[{i}].heading", section["heading"]))
        texts.append((f"report.sections[{i}].body", section["body"]))
    return texts


# A full stop that ends one of these abbreviations does not end the sentence
# ("... 15:52:33.728Z, i.e. 16:52:33.728 BST").
_ABBREVIATION_END = re.compile(r"(?:^|[\s(])(?:i\.e|e\.g|cf|vs|approx|incl)\.$", re.I)


def _sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for line in re.split(r"\n+", text):
        merged: list[str] = []  # lines (e.g. list items) are never joined
        for part in re.split(r"(?<=[.!?])\s+", line):
            part = part.strip()
            if not part:
                continue
            if merged and _ABBREVIATION_END.search(merged[-1]):
                merged[-1] += " " + part
            else:
                merged.append(part)
        sentences.extend(merged)
    return sentences


def _detect_severe(
    sub: Mapping[str, Any], key: Mapping[str, Any], catalogue: Catalogue
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for flag in key.get("severe_flags", []):
        heur = flag.get("heuristic") or {}
        if "record_id_pattern" in heur:
            rx = re.compile(heur["record_id_pattern"])
            places = [(f["finding_id"], f["statement"]) for f in sub["findings"]]
            places += [(path, text) for path, text in _report_texts(sub)]
            for where, text in places:
                for rid in sorted(set(rx.findall(text))):
                    if rid not in catalogue:
                        found.append(
                            {
                                "flag_id": flag["flag_id"],
                                "location": where,
                                "finding_id": where
                                if not where.startswith("report.")
                                else None,
                                "excerpt": text[:300],
                                "match": rid,
                            }
                        )
            continue
        statuses = heur.get("statuses")
        candidates: list[tuple[str, str | None, str]] = []
        for finding in sub["findings"]:
            if statuses is None or finding["status"] in statuses:
                # sentence by sentence: a hedge in one sentence does not excuse another
                for sentence in _sentences(finding["statement"]):
                    candidates.append(
                        (finding["finding_id"], finding["finding_id"], sentence)
                    )
        for path, text in _report_texts(sub):
            for sentence in _sentences(text):
                candidates.append((path, None, sentence))
        for where, fid, text in candidates:
            norm = normalise(text)
            if heur.get("context_any") and not _any(norm, heur["context_any"]):
                continue
            hit = next(
                (p for p in heur.get("trigger_any", []) if _rx(p).search(norm)), None
            )
            if hit is None or _any(norm, heur.get("unless_any", [])):
                continue
            if any(
                f["flag_id"] == flag["flag_id"] and f["location"] == where
                for f in found
            ):
                continue  # one suspicion per flag and place
            found.append(
                {
                    "flag_id": flag["flag_id"],
                    "location": where,
                    "finding_id": fid,
                    "excerpt": text[:300],
                    "match": _rx(hit).search(norm).group(0),
                }
            )
    return found


# -- assembling the report ---------------------------------------------------------
def _criterion_value(auto_value: Any, decided_auto: bool, human: Any) -> dict[str, Any]:
    if human is not None:
        out = {"value": human, "source": "human", "auto_proposal": auto_value}
        if decided_auto and auto_value is not None and human != auto_value:
            out["human_override_of_auto"] = True
        return out
    if decided_auto:
        return {"value": auto_value, "source": "auto", "auto_proposal": auto_value}
    return {"value": None, "source": "pending", "auto_proposal": auto_value}


def _dimension_of(cid: str) -> str:
    return cid.split(".")[0]


def grade_submission(
    submission: Any,
    catalogue: Catalogue | None = None,
    key: Mapping[str, Any] | None = None,
    trace_info: Mapping[str, Any] | None = None,
    decisions: Mapping[str, Any] | Path | str | None = None,
) -> dict[str, Any]:
    """Grade one valid v3 submission; returns the GradeReport dict.

    ``submission``: dict, JSON text, path or :class:`Submission`. ``trace_info``: from
    :func:`trace_info_from_episode` (``None`` = no episode: retrieval is not checked).
    ``decisions``: a grading-decisions object or path (see the module docstring).
    """
    catalogue = catalogue or Catalogue.load(DEFAULT_BUNDLE_DIR)
    key = key if key is not None else load_key()
    sub, sub_sha = _as_submission(submission, catalogue)
    findings = list(sub["findings"])
    finding_ids = [f["finding_id"] for f in findings]
    if isinstance(decisions, (str, Path)):
        decisions = load_decisions(decisions)
    dec = (
        check_decisions(
            decisions,
            submission_sha256=sub_sha,
            key=key,
            finding_ids=finding_ids,
            bundle_sha256=catalogue.bundle_sha256,
        )
        if decisions is not None
        else None
    )
    conv = key.get("conventions", {})
    severe = _detect_severe(sub, key, catalogue)
    citations = _check_citations(findings, catalogue, trace_info)
    ctx = _Ctx(
        findings=findings,
        key=key,
        catalogue=catalogue,
        citations=citations,
        trace_info=trace_info,
        severe=severe,
        aliases=conv.get("unit_aliases", {}),
        factual=tuple(
            conv.get("factual_statuses", ("observed", "reported", "inferred"))
        ),
        labelled_statuses=tuple(
            conv.get("labelled_statuses", ("hypothesis", "unknown"))
        ),
        uncertainty=tuple(conv.get("uncertainty_patterns", ())),
        order={fid: i for i, fid in enumerate(finding_ids)},
        entities=conv.get("entities", {}),
        masks=tuple(conv.get("entity_masks", ())),
        report=[
            (location, normalise(sentence))
            for location, text in _report_texts(sub)
            for sentence in _sentences(text)
        ],
        hedges=tuple(conv.get("mechanism_hedge_patterns") or _HEDGES),
        negations=tuple(
            conv.get("mechanism_negation_patterns") or _MECHANISM_NEGATIONS
        ),
        hedged_statuses=tuple(conv.get("mechanism_hedged_statuses", ("hypothesis",))),
    )
    human_criteria = {
        k: _public(v) for k, v in ((dec or {}).get("criteria") or {}).items()
    }

    # -- severe flag adjudication (first: confirmed flags have effects) ---------------
    severe_out = []
    adjudications = [_public(a) for a in (dec or {}).get("severe_flags") or []]

    def adjudicates(decision: Mapping[str, Any], item: Mapping[str, Any]) -> bool:
        if decision.get("flag_id") != item["flag_id"]:
            return False
        if item.get("finding_id") and item["finding_id"] in (
            decision.get("finding_ids") or []
        ):
            return True
        return item.get("location") in (decision.get("locations") or [])

    for item in severe:
        decision = next((a for a in adjudications if adjudicates(a, item)), None)
        confirmed = None if decision is None else decision.get("confirmed")
        severe_out.append(
            {
                **item,
                "detected_by": "heuristic",
                "confirmed": confirmed,
                "source": "pending" if confirmed is None else "human",
                "notes": (decision or {}).get("notes"),
            }
        )
    for decision in adjudications:
        covered = any(adjudicates(decision, s) for s in severe)
        if not covered and decision.get("confirmed") is not None:
            severe_out.append(
                {
                    "flag_id": decision["flag_id"],
                    "location": "reviewer",
                    "finding_id": None,
                    "finding_ids": decision.get("finding_ids"),
                    "detected_by": "reviewer",
                    "confirmed": decision["confirmed"],
                    "source": "human",
                    "notes": decision.get("notes"),
                }
            )
    # Effects of confirmed flags (key effect_when_confirmed / effect): the findings
    # become unsupported assertions and the listed criteria get content 0.
    flags_by_id = {f["flag_id"]: f for f in key.get("severe_flags", [])}
    flagged_findings: dict[str, list[str]] = {}
    zeroed: dict[str, list[str]] = {}
    confirmed_sets = [
        (
            item["flag_id"],
            [item.get("finding_id")] + list(item.get("finding_ids") or []),
        )
        for item in severe_out
        if item["confirmed"] is True
    ] + [
        (a["flag_id"], list(a.get("finding_ids") or []))
        for a in adjudications
        if a.get("confirmed") is True
    ]
    for flag_id, fids in confirmed_sets:
        for fid in fids:
            if fid in ctx.order and flag_id not in flagged_findings.setdefault(fid, []):
                flagged_findings[fid].append(flag_id)
        for cid in _flag_effect(flags_by_id[flag_id])["zero_content"]:
            if flag_id not in zeroed.setdefault(cid, []):
                zeroed[cid].append(flag_id)

    criteria_out = []
    assessments: dict[str, Mapping[str, Any]] = {}
    finding_dims: dict[str, dict[str, int]] = {fid: {} for fid in finding_ids}
    assertion_proposals: dict[str, tuple[str, str]] = {}
    needs_review: list[dict[str, Any]] = []
    conflicts_all: list[dict[str, Any]] = []
    for crit in key["criteria"]:
        cid = crit["criterion_id"]
        mode = crit["assessment_mode"]
        kind = (crit.get("auto") or {}).get("kind")
        assessment = _assess_criterion(crit, ctx)
        assessments[cid] = assessment
        check = (crit.get("auto") or {}).get("convention_check")
        note = _convention_note(check, assessments, ctx) if check else None
        if note:
            assessment = {
                **assessment,
                "basis": f"{assessment['basis']}; {note}",
                "notes": [note],
            }
        evidence = _assess_evidence(crit, assessment, ctx)
        human = human_criteria.get(cid, {})
        content = _criterion_value(
            assessment["content"],
            mode == "auto_numeric" and assessment.get("decided", True),
            human.get("content"),
        )
        content_basis = assessment["basis"]
        if cid in zeroed and content["source"] != "human":
            content = {
                "value": 0,
                "source": "severe_flag",
                "auto_proposal": assessment["content"],
            }
            content_basis = (
                f"confirmed severe flag {', '.join(zeroed[cid])} sets the content to 0 "
                f"(automated check: {assessment['basis']})"
            )
        content_value = content["value"]
        human_fids = [f for f in human.get("finding_ids") or [] if f in ctx.order]
        if (
            content["source"] == "human"
            and (content_value or 0) > 0
            and human_fids
            and (
                evidence.get("not_applicable")
                or (
                    kind in ("landmark", "duration")
                    and human_fids != assessment["matched_finding_ids"]
                )
            )
        ):
            # The reviewer credited findings the matcher did not pick: check the
            # evidence of those findings instead.
            evidence = _assess_evidence(
                crit,
                {
                    **assessment,
                    "matched_finding_ids": human_fids,
                    "content": content_value,
                },
                ctx,
            )
            evidence["basis"] = "on the reviewer's finding_ids: " + evidence["basis"]

        def not_applicable(basis: str) -> dict[str, Any]:
            if human.get("evidence_support") is not None:
                return {
                    "value": human["evidence_support"],
                    "source": "human",
                    "auto_proposal": evidence["proposal"],
                    "basis": evidence["basis"],
                }
            return {
                "value": None,
                "source": "not_applicable",
                "auto_proposal": evidence["proposal"],
                "basis": basis,
            }

        if content_value == 0 and content["source"] != "pending":
            ev_out = not_applicable(
                evidence["basis"] if evidence.get("not_applicable") else "content is 0"
            )
        elif evidence.get("not_applicable") and content["source"] == "pending":
            ev_out = not_applicable(evidence["basis"])
        elif evidence.get("not_applicable"):
            # content credited (by a reviewer) although no finding matched automatically
            ev_out = _criterion_value(None, False, human.get("evidence_support"))
            ev_out["basis"] = (
                "content is credited but no finding matched automatically: evidence "
                "support needs a human decision (or list the credited finding_ids so "
                "that their citations can be checked)"
            )
        else:
            ev_out = _criterion_value(
                evidence["proposal"], evidence["decided"], human.get("evidence_support")
            )
            ev_out["basis"] = evidence["basis"]
        # Dimension evidence for assertion bookkeeping: a criterion a finding satisfies
        # (or contradicts) weighs 3, one it was merely considered for weighs 1.
        for fid in (
            assessment.get("considered_finding_ids")
            or assessment["matched_finding_ids"]
        ):
            counts = finding_dims[fid]
            weight = 3 if fid in assessment["matched_finding_ids"] else 1
            counts[_dimension_of(cid)] = counts.get(_dimension_of(cid), 0) + weight
        if mode == "auto_numeric":
            for cand in assessment.get("candidates", [])[:1]:
                if cand["level"] >= 1:
                    verdict = "supported"
                elif (
                    cand["value_source"] == "quantity"
                    and cand.get("timed", True)
                    and (
                        cand["value_level"] == 0
                        or (
                            cand["time_ok"] is False
                            and cand["time_error_s"] is not None
                        )
                    )
                ):
                    verdict = "contradicted"
                else:  # prose values and values without a time are not judged
                    verdict = None
                if verdict:
                    assertion_proposals.setdefault(
                        cand["finding_id"], (verdict, f"{cid}: {assessment['basis']}")
                    )
        for hit in assessment["contradictions"]:
            assertion_proposals[hit["finding_id"]] = (
                "contradicted",
                f"{cid}: {hit['note']}",
            )
        if content["source"] == "pending" or ev_out["source"] == "pending":
            needs_review.append(
                {
                    "criterion_id": cid,
                    "content": content["source"] == "pending",
                    "evidence_support": ev_out["source"] == "pending",
                }
            )
        for conflict in assessment.get("conflicts", []):
            conflicts_all.append({"criterion_id": cid, **conflict})
        criteria_out.append(
            {
                "criterion_id": cid,
                "dimension": crit["dimension"],
                "title": crit["title"],
                "assessment_mode": mode,
                "polarity": crit.get("polarity", "positive"),
                "content": {**content, "basis": content_basis},
                "evidence_support": ev_out,
                "matched_finding_ids": assessment["matched_finding_ids"],
                "human_finding_ids": human.get("finding_ids"),
                "human_notes": human.get("notes"),
                "auto_checks": {
                    "notes": assessment.get("notes", []),
                    "elements": assessment.get("elements", []),
                    "candidates": assessment.get("candidates", []),
                    "other_candidates": assessment.get("other_candidates", []),
                    "contradictions": assessment.get("contradictions", []),
                    "conflicts": assessment.get("conflicts", []),
                    "evidence_citations": evidence["citations"],
                },
            }
        )

    flag_dims = {
        f["flag_id"]: sorted(
            {_dimension_of(c) for c in f.get("applies_to", []) if c != "all"}
        )
        for f in key.get("severe_flags", [])
    }
    for item in severe:
        if item["finding_id"]:
            assertion_proposals[item["finding_id"]] = (
                "unsupported",
                f"suspected {item['flag_id']}",
            )
            for dim in flag_dims.get(item["flag_id"], []):
                counts = finding_dims[item["finding_id"]]
                counts[dim] = counts.get(dim, 0) + 3

    # -- assertions --------------------------------------------------------------------
    human_assertions = {
        k: _public(v) for k, v in ((dec or {}).get("assertions") or {}).items()
    }
    assertions = []
    for finding in findings:
        fid = finding["finding_id"]
        factual = finding["status"] in ctx.factual
        human = human_assertions.get(fid, {})
        counts = finding_dims[fid]
        dims = sorted(counts)
        # the dimension with most matched criteria (earliest dimension on ties)
        auto_dim = min(dims, key=lambda d: (-counts[d], d)) if dims else "unassigned"
        dimension = human.get("dimension") or auto_dim
        proposal = assertion_proposals.get(fid)
        flagged = flagged_findings.get(fid)
        entry = {
            "assertion_id": fid,
            "kind": "finding",
            "status": finding["status"],
            "factual": factual,
            "dimension": dimension,
            "dimensions_matched": sorted(dims),
            "cited": bool(finding.get("citations")),
            "auto_proposal": proposal[0] if proposal else None,
            "auto_basis": proposal[1] if proposal else None,
        }
        if flagged:
            entry["confirmed_severe_flags"] = flagged
        if human.get("duplicate_of"):
            entry.update(
                verdict=None, source="duplicate", duplicate_of=human["duplicate_of"]
            )
        elif flagged and human.get("verdict") is None:
            entry.update(
                verdict=_flag_effect(flags_by_id[flagged[0]])["verdict"],
                source="severe_flag",
            )
        elif not factual and not flagged:
            entry.update(verdict=None, source="labelled_hypothesis_or_unknown")
        elif human.get("verdict") is not None:
            entry.update(verdict=human["verdict"], source="human")
        else:
            entry.update(verdict=None, source="pending")
        if human.get("notes"):
            entry["notes"] = human["notes"]
        assertions.append(entry)
    for aid, human in human_assertions.items():
        if aid in finding_ids:
            continue
        assertions.append(
            {
                "assertion_id": aid,
                "kind": "report_text",
                "text": human.get("text"),
                "factual": True,
                "dimension": human.get("dimension") or "unassigned",
                "verdict": human.get("verdict")
                if not human.get("duplicate_of")
                else None,
                "source": "duplicate"
                if human.get("duplicate_of")
                else ("human" if human.get("verdict") else "pending"),
                "notes": human.get("notes"),
            }
        )

    # -- aggregates (per dimension only) --------------------------------------------------
    dims = [d["dimension_id"] for d in key["dimensions"]]
    coverage: dict[str, Any] = {}
    support: dict[str, Any] = {}
    for dim in dims:
        rows = [c for c in criteria_out if c["dimension"] == dim]
        decided = [
            c
            for c in rows
            if c["content"]["source"] in ("auto", "human", "severe_flag")
        ]
        pending = [c for c in rows if c["content"]["source"] == "pending"]
        coverage[dim] = {
            "criteria": len(rows),
            "decided": len(decided),
            "pending": len(pending),
            "decided_content_sum": sum(c["content"]["value"] for c in decided),
            "decided_content_max": len(decided),
            "content_sum_including_auto_proposals": sum(
                (
                    c["content"]["value"]
                    if c["content"]["source"] != "pending"
                    else (c["content"]["auto_proposal"] or 0)
                )
                for c in rows
            ),
            "by_criterion": {c["criterion_id"]: c["content"]["value"] for c in rows},
            "auto_proposals": {
                c["criterion_id"]: c["content"]["auto_proposal"] for c in rows
            },
            "sources": {c["criterion_id"]: c["content"]["source"] for c in rows},
        }
        support[dim] = {
            "criteria": len(rows),
            "supported": sum(1 for c in rows if c["evidence_support"]["value"] == 1),
            "unsupported": sum(
                1
                for c in rows
                if c["evidence_support"]["value"] == 0
                and c["evidence_support"]["source"] in ("auto", "human")
            ),
            "pending": sum(
                1 for c in rows if c["evidence_support"]["source"] == "pending"
            ),
            "not_applicable": sum(
                1 for c in rows if c["evidence_support"]["source"] == "not_applicable"
            ),
            "by_criterion": {
                c["criterion_id"]: c["evidence_support"]["value"] for c in rows
            },
            "auto_proposals": {
                c["criterion_id"]: c["evidence_support"]["auto_proposal"] for c in rows
            },
            "sources": {
                c["criterion_id"]: c["evidence_support"]["source"] for c in rows
            },
        }

    def tally(items: list[dict[str, Any]]) -> dict[str, Any]:
        counted = [
            a for a in items if a["source"] in ("human", "pending", "severe_flag")
        ]
        out = {v: sum(1 for a in counted if a["verdict"] == v) for v in VERDICTS}
        out["pending"] = sum(1 for a in counted if a["source"] == "pending")
        out["labelled_hypothesis_or_unknown"] = sum(
            1 for a in items if a["source"] == "labelled_hypothesis_or_unknown"
        )
        out["duplicates"] = sum(1 for a in items if a["source"] == "duplicate")
        decided = sum(out[v] for v in VERDICTS)
        if decided == 0:
            out["precision"] = None
            out["precision_note"] = (
                "undefined: no factual assertions"
                if not counted
                else "undefined: all pending"
            )
        else:
            out["precision"] = round(out["supported"] / decided, 4)
            out["precision_note"] = (
                "over decided assertions only"
                if out["pending"]
                else "all assertions decided"
            )
        return out

    assertion_quality = {
        "by_dimension": {
            dim: tally([a for a in assertions if a["dimension"] == dim])
            for dim in dims + ["unassigned"]
        },
        "counts_all_dimensions": {
            k: v
            for k, v in tally(assertions).items()
            if k not in ("precision", "precision_note")
        },
        "assertions": assertions,
    }

    # -- flags ------------------------------------------------------------------------
    all_checks = [c for fid in finding_ids for c in citations[fid]]
    referenced = set()
    for _, text in _report_texts(sub):
        referenced.update(extract_references(text))
    labelling = []
    for finding in findings:
        if finding["status"] in ctx.factual and _any(ctx.text(finding), _HEDGES):
            labelling.append(
                {
                    "finding_id": finding["finding_id"],
                    "status": finding["status"],
                    "issue": "hedged wording with a factual status: should it be "
                    "labelled hypothesis or unknown?",
                }
            )
    flags = {
        "uncited_findings": [
            f["finding_id"] for f in findings if not f.get("citations")
        ],
        "uncited_factual_findings": [
            f["finding_id"]
            for f in findings
            if not f.get("citations") and f["status"] in ctx.factual
        ],
        "unresolvable_citations": [c.to_dict() for c in all_checks if not c.resolvable],
        "cited_but_never_retrieved": sorted(
            {c.evidence_id for c in all_checks if c.retrieved is False}
        )
        if trace_info is not None
        else None,
        "cited_but_never_retrieved_findings": sorted(
            {c.finding_id for c in all_checks if c.retrieved is False}
        )
        if trace_info is not None
        else None,
        "suspected_severe_assertions": severe,
        "labelling": labelling,
        "status_inferential_language": _status_inferential_language(
            findings,
            tuple(conv.get("inferential_patterns") or _INFERENTIAL),
            conv.get("inferential_attribution"),
        ),
        "labelled_hypotheses": [
            f["finding_id"] for f in findings if f["status"] == "hypothesis"
        ],
        "labelled_unknowns": [
            f["finding_id"] for f in findings if f["status"] == "unknown"
        ],
        "conflicting_values": conflicts_all,
        "findings_not_referenced_in_report": [
            fid for fid in finding_ids if fid not in referenced
        ],
        "needs_human_review": needs_review,
    }

    # -- status --------------------------------------------------------------------------
    reasons = []
    review_status = _review_status(key)
    if review_status != "reviewed":
        reasons.append(
            f"answer key review status is {review_status!r} (not 'reviewed')"
        )
    pending_criteria = [
        c["criterion_id"]
        for c in criteria_out
        if c["content"]["source"] == "pending"
        or c["evidence_support"]["source"] == "pending"
    ]
    if pending_criteria:
        reasons.append(f"{len(pending_criteria)} criteria await human decisions")
    pending_assertions = [
        a["assertion_id"] for a in assertions if a["source"] == "pending"
    ]
    if pending_assertions:
        reasons.append(f"{len(pending_assertions)} assertions await human verdicts")
    pending_flags = [s for s in severe_out if s["confirmed"] is None]
    if pending_flags:
        reasons.append(
            f"{len(pending_flags)} suspected severe assertions await adjudication"
        )
    if dec is None:
        reasons.append("no grading-decisions file applied")
    elif dec.get("builder_fixture"):
        reasons.append("the decisions file is a builder fixture, not a domain review")
    if trace_info is None:
        reasons.append("no episode trace: document retrieval was not checked")
    key_bundle = (key.get("bundle") or {}).get("bundle_sha256")
    if key_bundle and catalogue.bundle_sha256 != key_bundle:
        reasons.append(
            f"the answer key is bound to bundle {(key.get('bundle') or {}).get('bundle_version')} "
            f"but the submission was graded on bundle {catalogue.bundle_version}: the "
            "key's evidence locators do not apply"
        )
    explanation = (dec or {}).get("explanation_quality") or {}
    explanation_reviewed = _explanation_reviewed(explanation, dims)
    if not explanation_reviewed:
        reasons.append(
            "explanation quality not reviewed (no non-empty explanation_quality notes)"
        )

    return {
        "grade_schema": GRADE_SCHEMA,
        "grader_version": GRADER_VERSION,
        "status": "provisional" if reasons else "final",
        "provisional_reasons": reasons,
        "interpretation": INTERPRETATION,
        "key": {
            "key_id": key.get("key_id"),
            "key_version": key.get("key_version"),
            "review_status": review_status,
            "key_sha256": _key_sha256(key),
        },
        "bundle": {
            "bundle_id": catalogue.bundle_id,
            "bundle_version": catalogue.bundle_version,
            "bundle_sha256": catalogue.bundle_sha256,
            "matches_key": catalogue.bundle_sha256
            == (key.get("bundle") or {}).get("bundle_sha256"),
        },
        "submission": {
            "sha256": sub_sha,
            "findings": len(findings),
            "executive_summary_words": len(sub["report"]["executive_summary"].split()),
            "statuses": {
                s: sum(1 for f in findings if f["status"] == s)
                for s in ("observed", "reported", "inferred", "hypothesis", "unknown")
            },
        },
        "decisions": None
        if dec is None
        else {
            "decisions_version": dec.get("decisions_version"),
            "reviewer": dec.get("reviewer"),
            "date": dec.get("date"),
            "builder_fixture": bool(dec.get("builder_fixture")),
            "binding": dec.get("binding"),
        },
        "trace": None
        if trace_info is None
        else {
            k: trace_info.get(k)
            for k in (
                "retrieved",
                "r01_analysed_with_python",
                "calls_used",
                "frozen_at_request_id",
            )
        },
        "content_coverage": {"by_dimension": coverage},
        "evidence_support": {"by_dimension": support},
        "assertion_quality": assertion_quality,
        "severe_flags": severe_out,
        "explanation_quality": {
            "notes": explanation.get("notes"),
            "by_dimension": explanation.get("by_dimension") or {},
            "source": "human" if explanation_reviewed else "pending",
        },
        "criteria": criteria_out,
        "citations": [c.to_dict() for c in all_checks],
        "flags": flags,
    }


def _empty_measures(reason: str) -> dict[str, Any]:
    return {
        "content_coverage": None,
        "evidence_support": None,
        "assertion_quality": None,
        "severe_flags": [],
        "explanation_quality": None,
        "criteria": [],
        "citations": [],
        "flags": {},
        "measures_note": reason,
    }


def _catalogue_for_episode(
    episode_dir: Path, catalogue: Catalogue | None = None
) -> tuple[Catalogue, dict[str, Any]]:
    """The catalogue to grade an episode against, and the bundle the episode recorded.

    Without ``catalogue``: the episode's own ``bundle_dir`` when it exists here, else the
    installed bundle. Either way the catalogue must be the bundle the episode ran on
    (``bundle_sha256`` in ``episode_config.json``): citations are line ranges of that
    bundle's documents, so grading against another version would check them against
    other text. A mismatch raises :class:`GradingError`.
    """
    snapshot = read_config_snapshot(episode_dir) or {}
    recorded = {
        "bundle_version": snapshot.get("bundle_version"),
        "bundle_sha256": snapshot.get("bundle_sha256"),
    }
    if catalogue is None:
        candidate = (snapshot.get("config") or {}).get("bundle_dir")
        if candidate and Path(candidate).is_dir():
            try:
                catalogue = Catalogue.load(candidate)
            except CatalogueError:
                catalogue = None
        if catalogue is None:
            catalogue = Catalogue.load(DEFAULT_BUNDLE_DIR)
    sha = recorded["bundle_sha256"]
    if sha and catalogue.bundle_sha256 != sha:
        raise GradingError(
            f"{episode_dir} was recorded on evidence bundle "
            f"{recorded['bundle_version']} (sha256 {sha[:12]}...), but the bundle given "
            f"for grading is {catalogue.bundle_version} (sha256 "
            f"{catalogue.bundle_sha256[:12]}...). Its citations refer to the recorded "
            "bundle: grade it against that bundle (--bundle-dir DIR on the command line, "
            "catalogue= in grade_episode)."
        )
    return catalogue, recorded


def _bundle_section(
    catalogue: Catalogue, key: Mapping[str, Any], recorded: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "bundle_id": catalogue.bundle_id,
        "bundle_version": catalogue.bundle_version,
        "bundle_sha256": catalogue.bundle_sha256,
        "matches_key": catalogue.bundle_sha256
        == (key.get("bundle") or {}).get("bundle_sha256"),
        # None: the episode recorded no bundle hash (nothing to compare)
        "matches_episode": None
        if not recorded.get("bundle_sha256")
        else catalogue.bundle_sha256 == recorded["bundle_sha256"],
        "episode_bundle_version": recorded.get("bundle_version"),
    }


def grade_episode(
    episode_dir: Path | str,
    transcript_summary: Mapping[str, Any] | None = None,
    decisions: Mapping[str, Any] | Path | str | None = None,
    *,
    key: Mapping[str, Any] | None = None,
    catalogue: Catalogue | None = None,
) -> dict[str, Any]:
    """Grade an episode directory (``state.json``, ``trace.jsonl``, ``submission.json``).

    ``transcript_summary`` is the judge's summary (outcome, reasons, budgets); without
    it the outcome is derived from the ledger alone. Incomplete runs get a run section
    with the reason and empty content measures.

    ``catalogue`` (default: the episode's bundle, see :func:`_catalogue_for_episode`)
    must be the bundle the episode ran on; a different bundle raises
    :class:`GradingError`.
    """
    episode_dir = Path(episode_dir)
    summary = dict(transcript_summary or {})
    if "outcome" not in summary:
        summary = build_transcript_summary(episode_dir, None)
    key = key if key is not None else load_key()
    catalogue, recorded = _catalogue_for_episode(episode_dir, catalogue)
    run = {
        "outcome": summary.get("outcome"),
        "incomplete_reason": summary.get("incomplete_reason"),
        "incomplete_reasons": summary.get("incomplete_reasons") or [],
        "submission_valid": summary.get("submission_valid"),
        "transcript_available": summary.get("transcript_available"),
        "tool_calls": {
            "transcript_episode_tools": summary.get("tool_calls_episode_tools"),
            "by_tool": summary.get("tool_calls_by_tool"),
            "ledger_discrepancy": summary.get("ledger_discrepancy"),
        },
        "tokens": {
            "output_total": summary.get("output_tokens_total"),
            "output_before_freeze": summary.get("output_tokens_before_freeze"),
            "last_input": summary.get("last_input_tokens"),
            "output_budget_exceeded": summary.get("output_token_budget_exceeded"),
            "context_cap_reached": summary.get("context_cap_reached"),
        },
        "budgets": summary.get("budgets"),
        "isolation": summary.get("isolation"),
    }
    try:
        trace_info: dict[str, Any] | None = trace_info_from_episode(episode_dir)
    except EpisodeError as exc:
        trace_info = None
        run["trace_error"] = str(exc)
    base = {
        "grade_schema": GRADE_SCHEMA,
        "grader_version": GRADER_VERSION,
        "episode_dir": str(episode_dir),
        "run": run,
    }
    if run["outcome"] != "complete":
        reason = (
            f"run outcome is {run['outcome']!r} ({run['incomplete_reason']}): content "
            "measures are not computed for incomplete runs"
        )
        return {
            **base,
            "status": "provisional",
            "provisional_reasons": [
                reason,
                f"answer key review status is {_review_status(key)!r}",
            ],
            "interpretation": INTERPRETATION,
            "key": {
                "key_id": key.get("key_id"),
                "key_version": key.get("key_version"),
                "review_status": _review_status(key),
                "key_sha256": _key_sha256(key),
            },
            "bundle": _bundle_section(catalogue, key, recorded),
            "submission": None,
            "decisions": None,
            "trace": None
            if trace_info is None
            else {
                k: trace_info.get(k)
                for k in ("retrieved", "r01_analysed_with_python", "calls_used")
            },
            **_empty_measures(reason),
        }
    path = episode_dir / SUBMISSION_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GradingError(
            f"complete run without a readable {SUBMISSION_FILE}: {exc}"
        ) from None
    report = grade_submission(text, catalogue, key, trace_info, decisions)
    report["bundle"] = _bundle_section(catalogue, key, recorded)
    state = read_state(episode_dir)
    if (
        state is not None
        and state.submission_sha256
        and state.submission_sha256 != report["submission"]["sha256"]
    ):
        report["provisional_reasons"].append(
            "submission.json does not match the sha256 in state.json"
        )
        report["status"] = "provisional"
    return {**base, **report}


# -- review template ---------------------------------------------------------------
def review_template(
    target: Path | str | Mapping[str, Any] | Submission,
    *,
    key: Mapping[str, Any] | None = None,
    catalogue: Catalogue | None = None,
) -> dict[str, Any]:
    """A grading-decisions skeleton for a human reviewer, pre-filled with the automated
    proposals (under ``_context`` keys, which the loader ignores).

    ``target`` is an episode directory, a submission file, or a submission object.
    """
    key = key if key is not None else load_key()
    if isinstance(target, (str, Path)) and Path(target).is_dir():
        grade = grade_episode(Path(target), key=key, catalogue=catalogue)
    else:
        grade = grade_submission(target, catalogue, key, None, None)
    template: dict[str, Any] = {
        "_instructions": (
            "Fill in reviewer and date; for each criterion set content (1, 0.5, 0) and "
            "evidence_support (1, 0) after reading the cited evidence, list the finding_ids "
            "you relied on and add notes. Leave a value null if undecided. For auto_numeric "
            "criteria null accepts the automated result; any value overrides it. For each "
            "factual finding set verdict (supported, unsupported, contradicted); mark "
            "paraphrases with duplicate_of; add report-only assertions with a new ID, text "
            "and dimension. Adjudicate every suspected severe flag (confirmed true/false); "
            "a confirmed flag makes its findings unsupported and sets the criteria in the "
            "key's effect to 0, so do not mark them supported or credit those criteria. "
            "Write explanation_quality notes (overall, or one per dimension): the grade "
            "stays provisional until they are filled in. If you credit a criterion the "
            "matcher missed, list the finding_ids so their citations are checked. Save as "
            "a new decisions_version; never edit a version that has been used."
        ),
        "decisions_schema": DECISIONS_SCHEMA,
        "decisions_version": "1",
        "builder_fixture": False,
        "reviewer": None,
        "date": None,
        "binding": None,
        "criteria": {},
        "assertions": {},
        "severe_flags": [],
        "explanation_quality": {
            "notes": None,
            "by_dimension": {d["dimension_id"]: None for d in key["dimensions"]},
        },
    }
    if not grade.get("criteria"):
        template["_context"] = {
            "run": grade.get("run"),
            "note": grade.get("measures_note") or "nothing to review",
        }
        return template
    template["binding"] = {
        "submission_sha256": grade["submission"]["sha256"],
        "key_version": key.get("key_version"),
        "key_sha256": key_sha256(key),
        "bundle_sha256": grade["bundle"]["bundle_sha256"],
    }
    by_id = {c["criterion_id"]: c for c in key["criteria"]}
    for row in grade["criteria"]:
        crit = by_id[row["criterion_id"]]
        template["criteria"][row["criterion_id"]] = {
            "content": None,
            "evidence_support": None,
            "finding_ids": row["matched_finding_ids"],
            "notes": "",
            "_context": {
                "title": crit["title"],
                "assessment_mode": crit["assessment_mode"],
                "expectation": crit["expectation"],
                "tolerances": crit.get("tolerances"),
                "auto_content": row["content"],
                "auto_evidence_support": row["evidence_support"],
                "report_passages": crit["report_passages"],
                "visible_evidence": crit["visible_evidence"],
                "examples": crit["examples"],
            },
        }
    for a in grade["assertion_quality"]["assertions"]:
        if a["kind"] != "finding" or not a["factual"]:
            continue
        template["assertions"][a["assertion_id"]] = {
            "verdict": None,
            "notes": "",
            "_context": {
                "status": a["status"],
                "dimension": a["dimension"],
                "cited": a["cited"],
                "auto_proposal": a["auto_proposal"],
                "auto_basis": a["auto_basis"],
            },
        }
    for item in grade["severe_flags"]:
        template["severe_flags"].append(
            {
                "flag_id": item["flag_id"],
                "finding_ids": [item["finding_id"]] if item.get("finding_id") else [],
                "locations": [] if item.get("finding_id") else [item.get("location")],
                "confirmed": None,
                "notes": "",
                "_context": {
                    "location": item.get("location"),
                    "excerpt": item.get("excerpt"),
                    "match": item.get("match"),
                },
            }
        )
    template["_context"] = {
        "grade_status": grade["status"],
        "flags": {k: v for k, v in grade["flags"].items() if k != "needs_human_review"},
    }
    return template


# -- command line ------------------------------------------------------------------
def _dump(obj: Any, out: Path | None) -> None:
    text = (
        json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True, default=str)
        + "\n"
    )
    if out is None:
        sys.stdout.write(text)
    else:
        out.write_text(text, encoding="utf-8")
        print(f"written {out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m environment.incident.grading",
        description="Grade GB 2019 episodes/submissions and build human-review templates.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    bundle_help = (
        "evidence bundle directory to grade against (default: the episode's recorded "
        "bundle_dir if present, else the installed bundle); an episode must be graded "
        "against the bundle it ran on"
    )
    p = sub.add_parser("grade", help="grade an episode directory")
    p.add_argument("episode_dir", type=Path)
    p.add_argument("--transcript", type=Path, default=None)
    p.add_argument("--decisions", type=Path, default=None)
    p.add_argument(
        "--bundle-dir", "--bundle", dest="bundle_dir", type=Path, help=bundle_help
    )
    p.add_argument("--out", type=Path, default=None)
    p = sub.add_parser("grade-submission", help="grade a submission file (no episode)")
    p.add_argument("submission", type=Path)
    p.add_argument("--decisions", type=Path, default=None)
    p.add_argument(
        "--bundle-dir", "--bundle", dest="bundle_dir", type=Path, help=bundle_help
    )
    p.add_argument("--out", type=Path, default=None)
    p = sub.add_parser(
        "review-template", help="decisions template for an episode or submission"
    )
    p.add_argument("target", type=Path)
    p.add_argument(
        "--bundle-dir", "--bundle", dest="bundle_dir", type=Path, help=bundle_help
    )
    p.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        catalogue = (
            Catalogue.load(args.bundle_dir) if args.bundle_dir is not None else None
        )
        if args.command == "grade":
            summary = None
            if args.transcript is not None:
                events = (
                    json.loads(args.transcript.read_text(encoding="utf-8")).get(
                        "events"
                    )
                    or []
                )
                summary = build_transcript_summary(args.episode_dir, events)
            _dump(
                grade_episode(
                    args.episode_dir, summary, args.decisions, catalogue=catalogue
                ),
                args.out,
            )
        elif args.command == "grade-submission":
            _dump(
                grade_submission(
                    args.submission, catalogue, None, None, args.decisions
                ),
                args.out,
            )
        else:
            _dump(review_template(args.target, catalogue=catalogue), args.out)
    except (GradingError, CatalogueError, EpisodeError, OSError) as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
