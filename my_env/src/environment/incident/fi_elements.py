"""Element types the full-investigation key adds to increment A's grader.

:mod:`.fi_grading` grades with :mod:`.sr_grading` and passes these evaluators as
``element_types``; each takes ``(element, ctx)`` (ctx is ``sr_grading._SRCtx``) and
returns an element result like the built-in ones: ``id``, ``level`` (1, 0.5 or 0),
``finding_id``, ``finding_ids`` (the findings that earn the level; their citations are
checked for evidence support), ``considered`` and ``detail``. The lessons of increment
A's real submissions (decisions 18, 27, 40-48) are built in:

* **never an automatic 0 when a candidate exists**: a count stated only in the report
  text, or without the expected wording in its clause, is listed for the reviewer
  (``report_only`` / ``candidates_without_near``, which ``sr_grading`` turns into a
  basis note "not credited automatically: a human decides"), never silently dropped;
* **a structured quantity that describes something else falls back to the
  statement**: a ``count`` reads the finding's quantity only when its unit names a
  counted thing, and always reads the statement too;
* **wording binds to its own clause**: a count is credited only when the expected
  wording is in its own clause (split at ";", ",", ":", "while", "whereas", "but", and
  at "and"/"or" before another count, also after a determiner: "and 22 ...", "and
  14,428 ...", "and the other 7 ..."); wording that gives the count another meaning
  (``mismatch_any``) is read only in the words bound to the count (from the previous
  count of its clause to the next), so a neighbouring count's wording never disqualifies
  it; an alternative count from another account is credited only with that account
  named in its sentence (its own ``attribution_any``);
* **a candidate is never silently 0**: an expected count with wording of another
  meaning (``wrong_meaning``), another account's count without its source
  (``alternative_without_source``) or given to another source
  (``alternative_misattributed``) is listed, and ``sr_grading`` turns each into a basis
  note for the reviewer;
* **evidence follows the credited account**: an alternative may name its own keyed
  spans (``evidence``); when the count is credited only through the alternative, the
  element returns them as ``keyed_evidence`` and evidence support is proposed against
  them (the criterion's primary spans, which hold the expected count, count as context);
* findings suspected of a severe assertion earn no credit (as in the built-in types).

Types:

``count``
    an exact integer (digits or number words) bound to wording in its clause, e.g.
    ORR's 29 lock-outs, 22 technician resets, 7 driver resets::

        {"id": "lockouts", "type": "count", "expected": 29,
         "context": [["lock-?out|locked out|shut ?down"]],   # groups, in the clause
         "none": [...],                  # patterns in the clause that exclude it
         "mismatch_any": [...],          # clause wording that gives it another meaning
         "allow_units": ["minutes?"],    # unit words allowed after the number
         "statuses": [...],
         "context_routes": [{"clause": [...], "sentence": [...]}],  # other wording
         "sentence_all": [...],          # groups the count's sentence must also hold
         "alternatives": [{"value": 60, "level": 0.5,
                           "attribution_any": ["gtr", "eso"],   # its own sources
                           "other_sources_any": ["orr", "ofgem"],  # misattribution
                           "evidence": [{"evidence_id": "S08", "locator": "L22-L23",
                                         "role": "primary", ...}],
                           "note": "..."}],
         "quantity_units": "trains?|units?"}

    ``context_routes`` are further ways to meet ``context``: the clause meets the
    route's ``clause`` groups and the sentence its ``sentence`` groups (e.g. a bare
    "7 reset" in a list with the 29 lock-outs and 22 permanent lock-outs).
    ``sentence_all`` restricts the element to counts whose sentence also holds these
    groups (e.g. 29 stranded together with the two Class 387s trapped, ORR's 31);
    other counts are not candidates of the element.

``clause_time``
    a clock time bound to wording in its own clause (the count's clause breaks), e.g.
    the first ESO contact with BEIS: unlike increment A's ``time`` element, which reads
    a finding's event time or every time of its statement when the wording is anywhere
    in it, a time counts only when its clause, joined across commas with neighbouring
    clauses that hold no time of their own ("At 17:41, the ESO first contacted BEIS"),
    meets ``context`` (and its sentence ``sentence``), and its own clause holds no
    ``none`` pattern; so a restoration time "by 17:40" in a finding that also names
    BEIS is not the BEIS contact. A clause that meets the context without a time of its
    own takes the finding's ``event_time``. ``expected``
    or ``expected_range`` with ``tol_s`` (full) and an optional ``half_tol_s`` (0.5);
    an in-tolerance time whose sentence, but not clause, has the wording, or one given
    only in the report text, is listed for a human, never credited::

        {"id": "beis_time", "type": "clause_time",
         "expected_range": ["...T17:40:00+01:00", "...T17:41:00+01:00"], "tol_s": 0,
         "context": [["beis|government"], ["contact|first|..."]],
         "none": [["restor|reconnect|demand"]], "statuses": [...]}

``summary_text``
    the executive summary (the T20 summary): every ``all`` group, and no ``none``
    pattern, in one sentence (``scope`` ``"sentence"``, the default) or anywhere in the
    summary (``scope`` ``"summary"``). The findings the matching sentences refer to
    ([F01]) are the element's findings. With ``negate`` the element is met when no
    sentence matches (e.g. no unsupported claim of certainty) and the summary refers to
    at least ``min_refs`` findings.

``section_text``
    the report sections whose heading matches ``heading_any`` (e.g. the
    recommendations): as ``summary_text`` over their sentences, plus ``min_refs``
    distinct finding references in the matching text (else ``level_without_refs``);
    with ``also_findings`` a finding whose statement meets the groups (and
    ``finding_any``) counts too, at ``findings_level`` (default 1).

``summary_words``
    the executive summary has at most ``max_words`` whitespace-separated words.

``figure`` (replaces increment A's built-in element for this key)
    increment A's ``figure`` element (``sr_grading._eval_figure``), which reads only
    findings with a factual status, plus findings labelled ``unknown`` whose clause of
    the figure (cut at ";", ":" and sentence ends) holds no uncertainty or hedge
    wording: a finding that registers unknown causes may also report an attributed
    estimate ("Two further losses ... their causes are unknown: ..., and a net 200 MW at
    49 Hz ...", "Ofgem puts total distributed generation lost at 1,300-1,500 MW
    (estimated)", the real Opus panel run's F11; decision 18's rule for mechanisms in
    unknown-labelled findings). Such a finding counts only when it raises the level.
    An element with its own ``statuses`` reads as written. A figure in a finding
    labelled ``hypothesis``, or in an unknown-labelled clause with uncertainty wording,
    is listed for a human (``labelled_candidates``), never credited.

This module must not import ``karotte``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import Any

from environment.incident import grading as mvp
from environment.incident import sr_accounting
from environment.incident import sr_grading as sr
from environment.incident.grading import _all_groups, _any, normalise
from environment.incident.submission import extract_references, word_count

__all__ = [
    "ELEMENT_TYPES",
    "bound_words",
    "count_clause",
    "count_mentions",
    "eval_clause_time",
    "eval_count",
    "eval_figure",
    "eval_section_text",
    "eval_summary_text",
    "eval_summary_words",
    "number_value",
]

_UNITS_1_19 = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_WORD_VALUES: dict[str, int] = {w: i for i, w in enumerate(_UNITS_1_19)}
_NUMBER_WORD = (
    r"(?:(?:"
    + "|".join(_TENS)
    + r")(?:[- ](?:"
    + "|".join(_UNITS_1_19[1:10])
    + r"))?|"
    + "|".join(sorted(_UNITS_1_19, key=len, reverse=True))
    + r")"
)
_COUNT = re.compile(
    rf"(?<![\w.,:/£$€#-])(\d{{1,3}}(?:,\d{{3}})+|\d+|{_NUMBER_WORD})"
    r"(?![\w]|[.,:/]\d|%|\s?-\s?\d)"
)
# A number that labels something is not a count: "Class 700", "version 3.27",
# "Stage 1", "Table 1", "period 5", "incident 224904", "CC.6.3", "Appendix M Q34".
_LABEL_BEFORE = re.compile(
    r"(?<![\w-])(?:class(?:es)?|version|v|software|level|stage|stages|table|tables"
    r"|period|incident|incidents|section|sections|appendix|app\.?|q|question|questions"
    r"|answer|answers|figure|fig\.?|para(?:graph)?s?|rows?|lines?|items?|no\.?|cc|oc"
    r"|platform|route|chapter|part|annex|box|module|modules|gt|st|rule|clause|step"
    r"|steps|bus|circuit|phase)\s*$"
)
# unit words after a number (not counts unless the element allows them)
_UNIT_AFTER = re.compile(
    r"\s?(?:hz|hertz|mw|megawatts?|gw|kw|kv|mva\w*|ms|milliseconds?|s|secs?|seconds?"
    r"|mins?|minutes?|hours?|hrs?|h|km|ka|am|pm|bst|utc|gmt|z|degrees?|°|per ?cent"
    r"|mvar|gva\w*|million|m|bn|k)(?![a-z])"
)
_MONTH_AFTER = re.compile(
    r"\s?(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?"
    r"|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b"
)
_MONTH_BEFORE = re.compile(
    r"(?:jan(?:uary)?|feb(?:ruary)?|march|april|june|july|aug(?:ust)?|sep(?:t(?:ember)?)?"
    r"|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s*$"
)


def number_value(token: str) -> int | None:
    """The integer a count token stands for ("29", "14,428", "twenty-two")."""
    token = token.strip().casefold()
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+|\d+", token):
        return int(token.replace(",", ""))
    parts = re.split(r"[- ]", token)
    if len(parts) == 1:
        if parts[0] in _TENS:
            return _TENS[parts[0]]
        return _WORD_VALUES.get(parts[0])
    if len(parts) == 2 and parts[0] in _TENS and parts[1] in _WORD_VALUES:
        return _TENS[parts[0]] + _WORD_VALUES[parts[1]]
    return None


def count_mentions(
    text: str, allow_units: Sequence[str] = ()
) -> list[tuple[int, int, int]]:
    """(value, start, end) of the counts in normalised ``text``: integers written in
    digits or words that are not labels ("Class 700", "Stage 1"), times, dates,
    decimals, versions ("3.27"), percentages or values with a unit (unless the unit is
    allowed, e.g. "14,428 delay minutes" counts minutes)."""
    allowed = (
        re.compile(r"\s?(?:" + "|".join(allow_units) + r")(?![a-z])")
        if allow_units
        else None
    )
    found: list[tuple[int, int, int]] = []
    for match in _COUNT.finditer(text):
        value = number_value(match.group(1))
        if value is None:
            continue
        before = text[max(0, match.start() - 24) : match.start()]
        after = text[match.end() : match.end() + 24]
        if _LABEL_BEFORE.search(before):
            continue
        if _MONTH_AFTER.match(after) or _MONTH_BEFORE.search(before):
            continue
        if _UNIT_AFTER.match(after) and not (allowed and allowed.match(after)):
            continue
        digits = match.group(1).replace(",", "")
        if digits.isdigit() and len(digits) == 4 and 1900 <= value <= 2099:
            continue  # a year
        found.append((value, match.start(), match.end()))
    return found


def _suspected(ctx: Any) -> set[str]:
    return {s["finding_id"] for s in ctx.severe if s.get("finding_id")}


def _result(
    el: Mapping[str, Any],
    level: float,
    finding_ids: Sequence[str],
    considered: Sequence[str],
    detail: Mapping[str, Any],
    order: Mapping[str, int],
) -> dict[str, Any]:
    fids = sorted(dict.fromkeys(finding_ids), key=lambda f: order.get(f, 0))
    return {
        "id": el["id"],
        "level": level,
        "finding_id": fids[0] if fids and level > 0 else None,
        "finding_ids": fids if level > 0 else [],
        "considered": sorted(dict.fromkeys(considered), key=lambda f: order.get(f, 0)),
        "detail": dict(detail),
    }


# -- count ----------------------------------------------------------------------------
# A count's clause: increment A's clause breaks, except that "and"/"or" divides only
# before another count, of any size and also after a determiner ("22 needed a
# technician and 7 were reset", "7 were reset and 22 needed a technician", "873
# delayed trains and 14,428 delay minutes", "and the other 7 were reset"), never inside
# a train class ("29 Class 700 and 717 trains were locked out").
_COUNT_DETERMINER = (
    r"(?:(?:the|a|an|another|other|others|remaining|further|final|last|only|just"
    r"|some|about|around|approximately|circa|c\.|nearly|almost|over|under)\s){0,3}"
)
_COUNT_CLAUSE_BREAK = re.compile(
    r";|,\s|:\s|\s(?:while|whereas|but|although|though|then|followed by)\s"
    r"|[.!?](?=\s|$)"
    r"|(?<!class \d{3})(?<!classes \d{3})\s(?:and|or)\s(?="
    + _COUNT_DETERMINER
    + r"(?:\d[\d,]*|"
    + _NUMBER_WORD
    + r")\b)"
)


def count_clause(text: str, start: int) -> str:
    """The clause of ``text`` around position ``start`` (see ``_COUNT_CLAUSE_BREAK``)."""
    a, b = _clause_span(text, start)
    return text[a:b]


def _clause_span(text: str, start: int) -> tuple[int, int]:
    """(start, end) of the clause of ``text`` around ``start``."""
    a, b = 0, len(text)
    for match in _COUNT_CLAUSE_BREAK.finditer(text):
        if match.end() <= start:
            a = match.end()
        elif match.start() >= start:
            b = match.end()
            break
    return a, b


def bound_words(
    text: str, start: int, end: int, counts: Sequence[tuple[int, int, int]]
) -> str:
    """The words bound to the count at ``start:end``: its clause from the end of the
    previous count of the clause (else the clause start) to the start of the next
    (else the clause end). ``counts`` are the text's count mentions."""
    a, b = _clause_span(text, start)
    for _, s, e in counts:
        if a <= s and e <= start:
            a = max(a, e)
        elif s >= end and s < b:
            b = s
            break
    return text[a:b]


def _clause_and_sentence(layout: Any, start: int) -> tuple[str, str]:
    clause = count_clause(layout.text, start)
    sa, sb = layout._span(layout.sentences, start)
    return clause, layout.text[sa:sb]


def _alternative(el: Mapping[str, Any], value: int) -> Mapping[str, Any] | None:
    for alt in el.get("alternatives") or []:
        values = alt.get("values") or [alt.get("value")]
        if value in [int(v) for v in values if v is not None]:
            return alt
    return None


def _count_level(
    el: Mapping[str, Any], value: int, sentence: str
) -> tuple[float, str | None]:
    """(level, how) of one count bound to its clause: the expected value, else an
    alternative account's value named with its own source in the count's sentence
    (``alternative_misattributed`` when only another source is named)."""
    if value == int(el["expected"]):
        return 1.0, "expected"
    alt = _alternative(el, value)
    if alt is not None:
        if _any(sentence, alt.get("attribution_any") or ()):
            return float(alt.get("level", 0.5)), "alternative"
        if _any(sentence, alt.get("other_sources_any") or ()):
            return 0.0, "alternative_misattributed"
        return 0.0, "alternative_unattributed"
    return 0.0, None


def _meets_context(el: Mapping[str, Any], clause: str, sentence: str) -> bool:
    """The count's wording: ``context`` in its clause, or a ``context_routes`` route
    (its ``clause`` groups in the clause and its ``sentence`` groups in the
    sentence)."""
    if _all_groups(clause, el.get("context") or []):
        return True
    return any(
        _all_groups(clause, route.get("clause") or [])
        and _all_groups(sentence, route.get("sentence") or [])
        for route in el.get("context_routes") or []
    )


def eval_count(el: Mapping[str, Any], ctx: Any) -> dict[str, Any]:
    """A ``count`` element (see the module docstring)."""
    statuses = el.get("statuses") or list(ctx.factual)
    none = el.get("none") or []
    mismatch = el.get("mismatch_any") or []
    allow = el.get("allow_units") or []
    qunits = el.get("quantity_units")
    expected = int(el["expected"])
    suspected = _suspected(ctx)
    best: tuple[float, int, str, dict[str, Any]] | None = None
    levels: dict[str, float] = {}
    via_alternative: dict[str, Mapping[str, Any]] = {}
    considered: list[str] = []
    noted: list[dict[str, Any]] = []
    wrong: list[dict[str, Any]] = []
    unattributed: list[dict[str, Any]] = []
    misattributed: list[dict[str, Any]] = []
    for finding in ctx.findings:
        fid = finding["finding_id"]
        if fid in suspected or finding.get("status") not in statuses:
            continue
        layout = ctx.layout(finding)
        # (value, clause, sentence, bound words, source)
        candidates: list[tuple[int, str, str, str, str]] = []
        quantity = finding.get("quantity") or {}
        if qunits and quantity:
            unit = normalise(str(quantity.get("unit") or ""))
            raw = quantity.get("value")
            if (
                isinstance(raw, (int, float))
                and float(raw).is_integer()
                and re.match(rf"(?:{qunits})\b", unit)
            ):
                basis = normalise(str(quantity.get("basis") or ""))
                whole = layout.text + " ; " + basis
                candidates.append((int(raw), whole, whole, whole, "quantity"))
        mentions = count_mentions(layout.text, allow)
        for value, start, end in mentions:
            clause, sentence = _clause_and_sentence(layout, start)
            bound = bound_words(layout.text, start, end, mentions)
            candidates.append((value, clause, sentence, bound, "statement"))
        for value, clause, sentence, bound, source in candidates:
            if any(_any(clause, group) for group in none):
                continue
            if not _all_groups(sentence, el.get("sentence_all") or []):
                continue
            if mismatch and _any(bound, mismatch):
                if value == expected:
                    wrong.append(
                        {"finding_id": fid, "value": value, "clause": clause[:200]}
                    )
                continue
            if not _meets_context(el, clause, sentence):
                if _all_groups(sentence, el.get("context") or []):
                    level, how = _count_level(el, value, sentence)
                    if level > 0 or how == "expected":
                        noted.append(
                            {
                                "finding_id": fid,
                                "value": value,
                                "sentence": sentence[:200],
                            }
                        )
                continue
            if fid not in considered:
                considered.append(fid)
            level, how = _count_level(el, value, sentence)
            item = {"finding_id": fid, "value": value, "clause": clause[:200]}
            if how == "alternative_unattributed":
                unattributed.append(item)
            elif how == "alternative_misattributed":
                misattributed.append(item)
            if level <= 0:
                continue
            if level > levels.get(fid, 0.0):
                levels[fid] = level
                if how == "alternative":
                    via_alternative[fid] = _alternative(el, value) or {}
                else:
                    via_alternative.pop(fid, None)
            cand = (
                level,
                ctx.order[fid],
                fid,
                {"value": value, "source": source, "how": how},
            )
            if best is None or (-cand[0], cand[1]) < (-best[0], best[1]):
                best = cand
    detail: dict[str, Any] = {}
    if noted and (best is None or best[0] < 1):
        detail["candidates_without_near"] = noted[:5]
    if wrong:
        detail["wrong_meaning"] = wrong[:5]
    if unattributed:
        detail["alternative_without_source"] = unattributed[:5]
    if misattributed:
        detail["alternative_misattributed"] = misattributed[:5]
    if best is None or best[0] < 1:
        report_only = []
        for location, sentence in ctx.report:
            layout = mvp._make_layout(sentence, ctx.entities, ctx.masks)
            for value, start, _ in count_mentions(layout.text, allow):
                if value != expected:
                    continue
                clause = count_clause(layout.text, start)
                if (
                    _meets_context(el, clause, layout.text)
                    and _all_groups(layout.text, el.get("sentence_all") or [])
                    and not any(_any(clause, g) for g in none)
                ):
                    report_only.append({"location": location, "value": value})
        if report_only:
            detail["report_only"] = report_only[:5]
    if best is None:
        return _result(el, 0.0, [], considered, detail, ctx.order)
    tied = [f for f, v in levels.items() if v >= best[0]]
    out = _result(el, best[0], tied, considered, {**best[3], **detail}, ctx.order)
    # credited only through an alternative account: its own spans are the evidence
    alts = [via_alternative.get(f) for f in tied]
    if tied and all(alts):
        keyed: list[dict[str, Any]] = []
        for alt in alts:
            for item in (alt or {}).get("evidence") or []:
                if item not in keyed:
                    keyed.append(dict(item))
        if keyed:
            out["keyed_evidence"] = keyed
    return out


# -- clause_time --------------------------------------------------------------------
def _time_level(el: Mapping[str, Any], when: Any) -> tuple[float, float]:
    """(level, error in seconds) of a time against the element's expectation."""
    error = mvp._time_error(when, el)
    if error <= float(el.get("tol_s", 0)) + 1e-9:
        return 1.0, error
    if el.get("half_tol_s") is not None and error <= float(el["half_tol_s"]) + 1e-9:
        return 0.5, error
    return 0.0, error


def _sentence_clauses(text: str, sa: int, sb: int) -> list[tuple[int, int, bool]]:
    """The clauses of ``text[sa:sb]`` (``_COUNT_CLAUSE_BREAK``) as (start, end,
    ends_with_comma)."""
    out: list[tuple[int, int, bool]] = []
    pos = sa
    for match in _COUNT_CLAUSE_BREAK.finditer(text, sa, sb):
        if match.end() <= pos:
            continue
        out.append((pos, match.end(), match.group(0).startswith(",")))
        pos = match.end()
    if pos < sb:
        out.append((pos, sb, False))
    return out


def _time_segments(
    text: str, sa: int, sb: int, times: Sequence[int]
) -> dict[int, tuple[str, str]]:
    """For each clause of a sentence: (its own text, its segment). A clause's segment
    is the clause joined, across commas only, with neighbouring clauses that hold no
    time of their own ("At 17:41, the ESO first contacted BEIS": the time's clause is
    "at 17:41, " and its segment names BEIS); keyed by the clause start."""
    clauses = _sentence_clauses(text, sa, sb)
    timed = [any(a <= t < b for t in times) for a, b, _ in clauses]
    out: dict[int, tuple[str, str]] = {}
    for i, (a, b, _) in enumerate(clauses):
        lo = i
        while lo > 0 and clauses[lo - 1][2] and not timed[lo - 1]:
            lo -= 1
        hi = i
        while hi + 1 < len(clauses) and clauses[hi][2] and not timed[hi + 1]:
            hi += 1
        out[a] = (text[a:b], text[clauses[lo][0] : clauses[hi][1]])
    return out


def _clause_meets(el: Mapping[str, Any], segment: str, sentence: str) -> bool:
    return _all_groups(segment, el.get("context") or []) and _all_groups(
        sentence, el.get("sentence") or []
    )


def eval_clause_time(el: Mapping[str, Any], ctx: Any) -> dict[str, Any]:
    """A ``clause_time`` element (see the module docstring)."""
    statuses = el.get("statuses") or list(ctx.factual)
    none = el.get("none") or []
    suspected = _suspected(ctx)
    best: tuple[float, float, int, str, dict[str, Any]] | None = None
    levels: dict[str, float] = {}
    considered: list[str] = []
    noted: list[dict[str, Any]] = []
    for finding in ctx.findings:
        fid = finding["finding_id"]
        if fid in suspected or finding.get("status") not in statuses:
            continue
        layout = ctx.layout(finding)
        text = layout.text
        spans = mvp._time_spans(text)
        candidates: list[tuple[Any, str]] = []
        untimed_meets = False
        for sa, sb in layout.sentences:
            sentence = text[sa:sb]
            starts = [start for _, start, _ in spans if sa <= start < sb]
            segments = _time_segments(text, sa, sb, starts)
            for clause_start, (clause, segment) in segments.items():
                times = [
                    when
                    for when, start, _ in spans
                    if clause_start <= start < clause_start + len(clause)
                ]
                # a restoration phrase in the time's own clause disqualifies it
                if any(_any(clause, g) for g in none):
                    continue
                if not times:
                    if _clause_meets(el, clause, sentence):
                        untimed_meets = True
                    continue
                if _clause_meets(el, segment, sentence):
                    candidates += [(when, "statement") for when in times]
                elif _all_groups(sentence, el.get("context") or []):
                    for when in times:
                        if _time_level(el, when)[0] > 0:
                            noted.append(
                                {
                                    "finding_id": fid,
                                    "value": when.isoformat(),
                                    "sentence": sentence[:200],
                                }
                            )
        # a clause with the wording but no time of its own takes the event time
        if untimed_meets and finding.get("event_time"):
            try:
                candidates.append(
                    (mvp.parse_iso_instant(finding["event_time"]), "event_time")
                )
            except mvp.LocatorError:
                pass
        if candidates and fid not in considered:
            considered.append(fid)
        for when, source in candidates:
            level, error = _time_level(el, when)
            if level <= 0:
                continue
            levels[fid] = max(level, levels.get(fid, 0.0))
            cand = (
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
            if best is None or (-cand[0], cand[1], cand[2]) < (
                -best[0],
                best[1],
                best[2],
            ):
                best = cand
    detail: dict[str, Any] = {}
    if noted and (best is None or best[0] < 1):
        detail["times_without_near"] = noted[:5]
    if best is None or best[0] < 1:
        report_times = []
        for location, sentence in ctx.report:
            layout = mvp._make_layout(sentence, ctx.entities, ctx.masks)
            text = layout.text
            spans = mvp._time_spans(text)
            segments = _time_segments(text, 0, len(text), [s for _, s, _ in spans])
            for when, start, _ in spans:
                clause_start = max(c for c in segments if c <= start)
                clause, segment = segments[clause_start]
                if (
                    _clause_meets(el, segment, text)
                    and not any(_any(clause, g) for g in none)
                    and _time_level(el, when)[0] > 0
                ):
                    report_times.append(
                        {"location": location, "time": when.isoformat()}
                    )
        if report_times:
            detail["report_only_times"] = report_times[:5]
    if best is None:
        return _result(el, 0.0, [], considered, detail, ctx.order)
    tied = [f for f, v in levels.items() if v >= best[0]]
    return _result(el, best[0], tied, considered, {**best[4], **detail}, ctx.order)


# -- the executive summary and report sections -----------------------------------------
def _sentences_with_refs(text: str) -> list[tuple[str, list[str]]]:
    """(normalised sentence, finding references) of a report text."""
    out = []
    for sentence in mvp._sentences(text):
        out.append((normalise(sentence), extract_references(sentence)))
    return out


def _match_parts(
    el: Mapping[str, Any], parts: Sequence[tuple[str, list[str]]]
) -> tuple[bool, list[str]]:
    """Whether the sentences meet the element (per sentence or over all of them), and
    the finding references of the sentences that do."""
    groups = el.get("all") or []
    none = el.get("none") or []
    if el.get("scope", "sentence") == "sentence":
        refs: list[str] = []
        hit = False
        for text, found in parts:
            if any(_any(text, g) for g in none):
                continue
            if _all_groups(text, groups):
                hit = True
                refs += found
        return hit, refs
    usable = [(t, r) for t, r in parts if not any(_any(t, g) for g in none)]
    joined = " ".join(t for t, _ in usable)
    if usable and _all_groups(joined, groups):
        # the references of the sentences that meet at least one group (not of every
        # sentence of the summary)
        return True, [
            ref
            for text, found in usable
            if not groups or any(_any(text, g) for g in groups)
            for ref in found
        ]
    return False, []


def _report_only(result: dict[str, Any], routes: Sequence[str] = ()) -> dict[str, Any]:
    """Mark a result whose findings are (mostly) only referred to by report text: they
    are its findings for evidence support, but only ``routes`` (findings whose own
    statement met the element) route a finding to the criterion's task (see
    ``sr_grading._score_rules``). An executive summary refers to findings of every
    topic; they belong to their own topics, not to the summary's."""
    result["route_finding_ids"] = [f for f in result["finding_ids"] if f in routes]
    return result


def _known(refs: Sequence[str], ctx: Any) -> list[str]:
    suspected = _suspected(ctx)
    return [r for r in dict.fromkeys(refs) if r in ctx.order and r not in suspected]


def eval_summary_text(el: Mapping[str, Any], ctx: Any) -> dict[str, Any]:
    """A ``summary_text`` element (see the module docstring). With ``negate`` the
    element is met when NO summary sentence matches (e.g. no claim of certainty);
    the matching sentences are listed for the reviewer."""
    summary = str(
        ((ctx.submission or {}).get("report") or {}).get("executive_summary") or ""
    )
    parts = _sentences_with_refs(summary)
    hit, refs = _match_parts(el, parts)
    if el.get("negate"):
        detail: dict[str, Any] = {"where": "report.executive_summary"}
        if hit:
            detail["matching_sentences"] = [
                text[:200]
                for text, _ in parts
                if _match_parts({**el, "scope": "sentence"}, [(text, [])])[0]
            ][:5]
            return _report_only(_result(el, 0.0, [], [], detail, ctx.order))
        # met: the summary's claims rest on the findings it refers to (a summary that
        # refers to fewer than ``min_refs`` findings makes no claim to assess)
        fids = _known([ref for _, found in parts for ref in found], ctx)
        if len(fids) < int(el.get("min_refs", 0)):
            detail["note"] = "the summary refers to no finding"
            return _report_only(_result(el, 0.0, [], [], detail, ctx.order))
        return _report_only(_result(el, 1.0, fids, fids, detail, ctx.order))
    fids = _known(refs, ctx)
    detail = {"where": "report.executive_summary"} if hit else {}
    if hit and not fids:
        detail["note"] = "the matching summary text refers to no finding"
    return _report_only(_result(el, 1.0 if hit else 0.0, fids, fids, detail, ctx.order))


def eval_section_text(el: Mapping[str, Any], ctx: Any) -> dict[str, Any]:
    """A ``section_text`` element (see the module docstring)."""
    sections = ((ctx.submission or {}).get("report") or {}).get("sections") or []
    heading_any = el.get("heading_any") or []
    parts: list[tuple[str, list[str]]] = []
    headings = []
    for i, section in enumerate(sections):
        if _any(normalise(str(section.get("heading") or "")), heading_any):
            headings.append(f"report.sections[{i}]")
            parts += _sentences_with_refs(str(section.get("body") or ""))
    hit, refs = _match_parts(el, parts) if parts else (False, [])
    fids = _known(refs, ctx)
    via_findings: list[str] = []
    if el.get("also_findings"):
        suspected = _suspected(ctx)
        statuses = el.get("statuses")
        for finding in ctx.findings:
            fid = finding["finding_id"]
            if fid in suspected or (statuses and finding.get("status") not in statuses):
                continue
            text = ctx.text(finding)
            if not _any(text, el.get("finding_any") or [r".*"]):
                continue
            if any(_any(text, g) for g in el.get("none") or []):
                continue
            if _all_groups(text, el.get("all") or []):
                via_findings.append(fid)
    need = int(el.get("min_refs", 0))
    enough = len(fids) >= need
    level = 0.0
    if hit and enough:
        level = 1.0
    elif via_findings:
        level = float(el.get("findings_level", 1.0))
    elif hit:
        level = float(el.get("level_without_refs", 0.0))
    detail: dict[str, Any] = {"sections": headings}
    if hit:
        detail["references"] = fids
    if via_findings:
        detail["findings"] = via_findings
    if hit and not enough:
        detail["note"] = (
            f"the matching section text refers to {len(fids)} finding(s); {need} "
            "expected"
        )
    return _report_only(
        _result(el, level, fids + via_findings, fids + via_findings, detail, ctx.order),
        via_findings,
    )


# -- figure ---------------------------------------------------------------------------
_FIGURE_CLAUSE_BREAK = re.compile(r";|:\s|[.!?](?=\s|$)")


def _figure_clause(excerpt: str, value: Any) -> str:
    """The clause of a mention's sentence (``excerpt``, normalised) that holds the
    figure (its first number, written with or without thousands separators); the whole
    sentence when the number is not found in it."""
    first = value[0] if isinstance(value, (list, tuple)) else value
    n = int(round(float(first)))
    forms = sorted({f"{n:,}", str(n)}, key=len, reverse=True)
    found = re.search(
        r"(?<![\d.,])(?:" + "|".join(re.escape(f) for f in forms) + r")(?![\d])",
        excerpt,
    )
    if found is None:
        return excerpt
    a, b = 0, len(excerpt)
    for match in _FIGURE_CLAUSE_BREAK.finditer(excerpt):
        if match.end() <= found.start():
            a = match.end()
        elif match.start() >= found.end():
            b = match.start()
            break
    return excerpt[a:b]


def _figure_value_text(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "-".join(f"{float(v):g}" for v in value)
    return f"{float(value):g}"


def eval_figure(el: Mapping[str, Any], ctx: Any) -> dict[str, Any]:
    """A ``figure`` element (see the module docstring): increment A's evaluation, then
    the figures of unknown-labelled findings whose own clause states no uncertainty."""
    base = sr._eval_figure(el, ctx)
    if el.get("statuses"):
        return base
    wanted = set(el["figures"])
    accounting = ctx.accounting or sr_accounting.AccountingResult()
    suspected = _suspected(ctx)
    labelled = [
        m
        for m in accounting.mentions
        if m.figure_id in wanted
        and m.finding_id is not None
        and m.finding_id not in suspected
        and m.status in ctx.labelled_statuses
        and m.via != "bare"
    ]
    if not labelled:
        return base
    doubts = tuple(ctx.uncertainty) + tuple(ctx.hedges)
    open_ids = {
        id(m)
        for m in labelled
        if m.status == "unknown"
        and not _any(_figure_clause(m.excerpt, m.value), doubts)
    }
    if base["level"] < 1 and open_ids:
        kept = [
            m
            for m in accounting.mentions
            if m.status not in ctx.labelled_statuses or id(m) in open_ids
        ]
        widened = replace(
            ctx,
            accounting=sr_accounting.AccountingResult(
                mentions=kept,
                arithmetic=accounting.arithmetic,
                traps=accounting.traps,
                prose_sums=accounting.prose_sums,
            ),
        )
        alt = sr._eval_figure({**el, "statuses": [*ctx.factual, "unknown"]}, widened)
        if alt["level"] > base["level"]:
            from_unknown = sorted(
                {m.finding_id for m in labelled if id(m) in open_ids}
                & set(alt["finding_ids"]),
                key=lambda f: ctx.order.get(f, 0),
            )
            detail = dict(alt["detail"])
            if from_unknown:
                detail["from_labelled_unknown"] = from_unknown
            return {**alt, "detail": detail}
    if base["level"] >= 1:
        return base
    others = [m for m in labelled if id(m) not in open_ids]
    if not others:
        return base
    detail = dict(base["detail"])
    detail["labelled_candidates"] = [
        {
            "finding_id": m.finding_id,
            "status": m.status,
            "value": _figure_value_text(m.value),
            "excerpt": m.excerpt[:200],
        }
        for m in others[:5]
    ]
    considered = sorted(
        set(base["considered"]) | {m.finding_id for m in others},
        key=lambda f: ctx.order.get(f, 0),
    )
    return {**base, "detail": detail, "considered": considered}


def eval_summary_words(el: Mapping[str, Any], ctx: Any) -> dict[str, Any]:
    """A ``summary_words`` element: the summary is within ``max_words``."""
    summary = str(
        ((ctx.submission or {}).get("report") or {}).get("executive_summary") or ""
    )
    words = word_count(summary)
    limit = int(el.get("max_words", 600))
    return _report_only(
        _result(
            el,
            1.0 if words <= limit else 0.0,
            [],
            [],
            {"words": words, "max_words": limit},
            ctx.order,
        )
    )


ELEMENT_TYPES: dict[str, Callable[..., dict[str, Any]]] = {
    "figure": eval_figure,
    "count": eval_count,
    "clause_time": eval_clause_time,
    "summary_text": eval_summary_text,
    "section_text": eval_section_text,
    "summary_words": eval_summary_words,
}
