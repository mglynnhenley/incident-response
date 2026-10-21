"""Checking what the judge returns against what it was shown.

Every quote must occur, word for word after normalisation (NFKC, case, dashes,
quotes, whitespace; ``[L<n>]`` prefixes ignored; ``...`` joins fragments that must
occur in order), in the text of a span the judge was shown. A narrowed locator
(``L55`` inside a shown ``L54-L58``) is accepted when its text lies inside a shown
span; a correct quote with a wrong locator is moved to the shown span that contains
it (``relocated``). Anything else is a hallucinated span: dropped and recorded.
Report quotes (report assertions, severe-flag suggestions) must occur in the
submission's report text.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from environment.incident import sr_grading
from environment.incident.grading import normalise
from environment.incident.locators import LocatorError, parse_and_validate

from .prompt import SpanIndex

__all__ = [
    "MIN_QUOTE_CHARS",
    "SpanCheck",
    "check_span",
    "find_report_location",
    "quote_occurs",
]

MIN_QUOTE_CHARS = 4
_PREFIX = re.compile(r"\[L\d+\]\s?")
_ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…)\s*")
_SPAN_ID = re.compile(r"^[CK]\d+$", re.I)


def _fragments(quote: str) -> list[str]:
    text = _PREFIX.sub("", quote)
    return [f for f in (normalise(p) for p in _ELLIPSIS.split(text)) if f]


def quote_occurs(quote: str, text: str) -> bool:
    """Whether every ``...``-separated fragment of ``quote`` occurs in ``text``, in
    order, after normalisation (and the quote has at least 4 characters)."""
    fragments = _fragments(quote)
    if sum(len(f) for f in fragments) < MIN_QUOTE_CHARS:
        return False
    haystack = normalise(_PREFIX.sub("", text))
    position = 0
    for fragment in fragments:
        found = haystack.find(fragment, position)
        if found < 0:
            return False
        position = found + len(fragment)
    return True


@dataclass
class SpanCheck:
    ok: bool
    span: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
    within: list[str] = field(default_factory=list)


def _shown_norm(text: str) -> str:
    return normalise(text)


def _containing(
    index: SpanIndex,
    evidence_id: str,
    text: str,
    allowed: Collection[str] | None = None,
) -> list[str]:
    needle = normalise(text)
    if not needle:
        return []
    return [
        s.span_id
        for s in index.by_evidence(evidence_id, allowed)
        if needle in _shown_norm(s.shown_text)
    ]


def check_span(
    item: Mapping[str, Any],
    index: SpanIndex,
    allowed: Collection[str] | None = None,
) -> SpanCheck:
    """Verify one ``{evidence_id, locator, quote}`` returned by the judge against the
    spans its request showed (``allowed`` span IDs; all spans when ``None``)."""
    evidence_id = str(item.get("evidence_id") or "").strip()
    locator = str(item.get("locator") or "").strip()
    quote = str(item.get("quote") or "")
    returned = {"evidence_id": evidence_id, "locator": locator, "quote": quote}
    if sum(len(f) for f in _fragments(quote)) < MIN_QUOTE_CHARS:
        return SpanCheck(False, returned, "empty or too short quote")

    for ref in (locator, evidence_id):
        if (
            _SPAN_ID.match(ref)
            and ref.upper() in index.spans
            and (allowed is None or ref.upper() in allowed)
        ):
            span = index.spans[ref.upper()]
            if not span.resolvable:
                return SpanCheck(False, returned, f"{span.span_id} is unresolvable")
            if quote_occurs(quote, span.shown_text):
                return SpanCheck(
                    True,
                    _accepted(span.evidence_id, span.locator, quote, False),
                    within=_containing(
                        index, span.evidence_id, span.shown_text, allowed
                    ),
                )
            return SpanCheck(False, returned, f"quote not found in {span.span_id}")

    candidates = index.by_evidence(evidence_id, allowed)
    if not candidates:
        return SpanCheck(False, returned, f"no span of {evidence_id!r} was shown")
    text = index.resolve(evidence_id, locator) if locator else None
    if text is not None and quote_occurs(quote, text):
        within = _containing(index, evidence_id, text, allowed)
        if within:
            normalized = index.find(evidence_id, locator)
            loc = (
                normalized.locator
                if normalized
                else _normalized(index, evidence_id, locator)
            )
            return SpanCheck(
                True, _accepted(evidence_id, loc, quote, False), within=within
            )
    hits = [s for s in candidates if quote_occurs(quote, s.shown_text)]
    if hits:
        return SpanCheck(
            True,
            _accepted(evidence_id, hits[0].locator, quote, True),
            within=[s.span_id for s in hits],
        )
    return SpanCheck(False, returned, "quote not found in any shown span")


def _normalized(index: SpanIndex, evidence_id: str, locator: str) -> str:
    target = sr_grading._target(index.catalogue, evidence_id)
    try:
        return parse_and_validate(locator, target).normalized
    except (LocatorError, AttributeError):
        return locator


def _accepted(
    evidence_id: str, locator: str, quote: str, relocated: bool
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "evidence_id": evidence_id,
        "locator": locator,
        "quote": quote,
    }
    if relocated:
        out["relocated"] = True
    return out


def find_report_location(
    quote: str, report_texts: Sequence[tuple[str, str]]
) -> str | None:
    """The report location (``report.executive_summary``, ``report.sections[i].body``)
    whose text contains ``quote``, else ``None``."""
    for location, text in report_texts:
        if quote_occurs(quote, text):
            return location
    return None
