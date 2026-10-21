"""Accounting-basis checks for the system-response grader (:mod:`.sr_grading`).

The records of 9 August 2019 give several totals for the same kind of quantity, each on
its own basis: ESO's six-component cumulative infeed loss (1,878 MW) is not Ofgem's
"at least 1,990 MW" at a different stage; the 931 MW of demand the DNOs reported as
disconnected by LFDD relays is not Ofgem's 892 MW of *net* demand or the E3C interim
table's 973 MW; ESO's final secondary response holding (1,314 MW, Table 3) is not its
earlier answer (1,338 MW, Appendix M); its inertia figure 210 GVA.s (Table 4) is not
the model estimate 219,632 MVA.s given in Appendix M; distributed-generation estimates
differ by source, stage and method. A figure is credited only when the basis it is
given on matches the record it comes from.

A *figure* (key ``accounting.figures``) is one number of one record::

    {"figure_id": "GEN_ESO_1878", "unit": "MW", "value": 1878, "match_abs": 1,
     "context_any": [...],      # the clause (else sentence) must be about this quantity
     "sources": ["eso", ...],   # source entities that give the figure on this basis
     "wrong_sources": [...],    # entities whose attribution is wrong for this figure
     "definition_any": [...],   # wording that identifies the basis without a source
     "mismatch_any": [...],     # wording in the figure's clause that contradicts it
     "mismatch_unless_any": [...],  # optional: own-side wording that cancels it
     "qualifier_any": [...],    # e.g. estimate wording (reported as ``qualified``)
     "components": [...]}       # optional: a sum of these terms defines the figure

or a range (``"range": [1300, 1500]``). Numbers are read from normalised text with a
unit (MW, GW, kW; GVA.s, MVA.s; Hz); a range is one mention and its endpoints are not
read as point figures. Two numbers are one range only when written as one: "between X
and Y", or "X-Y" / "X to Y" where X has no unit of its own (with a unit on both only for
a key range: "1,300 MW to 1,500 MW"), and never from a number that labels a table,
appendix or question ("rose from 1,481 MW to 1,990 MW", "150 MW and 350 MW" and "1,314
MW in Table 3 and 1,338 MW" are two figures each). A key figure written without a unit
in a text that names megawatts is listed as a ``bare`` candidate for a human and never
credited.

Wording between two numbers belongs to one of them only. A clause is first cut into
sub-clauses at contrast and comparison connectives ("vs", "versus", "compared with",
"rather than", "unlike", "whereas", "while", "but", "below", "above", "exceeds", "close
to", "than" not followed by a number, ...). Within a sub-clause, the wording between two
numbers is split at the last weak connective ("or", "with", "plus"), else at an opening
parenthesis not closed before the second number, else before a source named in the
possessive ("... with ESO's 931 MW"), else it all follows the first number. A number's
*own side* is its share of its sub-clause. Each mention is bound to the attribution
nearest to it (``accounting.source_entities``), in this order:

1. the nearest source on its own side;
2. a source shared by the figures coordinated with it ("a and b (Ofgem)", "the 150 MW
   vector-shift and 350 MW RoCoF estimates made by ESO", "... figures are ESO
   estimates"): figures joined only by "and" or a comma with at most three label words
   (not a stage such as "after GT1A"), the last naming the source after itself in a
   citation parenthesis or a trailing predicate with shared wording; not when a list
   head (step 3) covers the number;
   else the binding of the number before it in the same sub-clause (a shared subject:
   "ESO estimate from the DNO data plus the 150 MW" gives the 150 MW ESO's binding, not
   the DNOs'), unless "or"/"with" stands between them (alternatives from different
   sources) or that number's source is a citation parenthesis closed before this one
   ("1,878 MW (ESO) plus 1,300-1,500 MW");
   else a citation parenthesis after the next number of the sub-clause when nothing
   divides the wording between them ("350 MW because about 550 MW ... also tripped
   (Ofgem)"); a source merely on the next number's side is that number's;
3. the nearest list head before it in its sentence: a source followed by a colon ("Ofgem:
   more than 1,130 MW ...; about 1,500 MW ...; at least 1,990 MW ...", also with a
   parenthesis before the colon) or by a reporting verb ("Ofgem gives a, b and c"). The
   scope ends at the end of the sentence, at a contrast connective, at the next list
   head and, for a head inside parentheses, at the closing parenthesis; a reporting-verb
   list also at a semicolon and at an "and" that opens a new finite clause ("..., and
   1,878 MW is the cumulative total", "..., and LFDD relays disconnected 931 MW"; not
   "and 931 MW of demand disconnected by LFDD");
4. the nearest preceding source in the sentence, else the only source the sentence
   names (both only when no other number, no contrast connective and no "and" opening a
   new clause stands in between and the source's sub-clause has no number of its own; a
   source after the number not across a semicolon, and not a list head that introduces
   figures of its own);
5. when the number's sentence names no source at all: the source the finding's quantity
   basis or derivation gives, but only for the quantity's own value or a number that
   text also names (a basis describes its own quantity, not every number of the
   statement).

A source mention contained in a longer one ("e3c" inside "answers to the e3c") is
dropped; adjacent mentions joined only by a possessive, a space, "the" or an opening
parenthesis name one source: a specific source beats its generic parent ("ESO Table 3"
is ``eso_final``) and otherwise the owner named first wins ("the Ofgem final report",
"E3C interim Table 1" the E3C interim report's). A bare "final report" names no owner:
it is the report of an owner joined to it in either order or in the possessive with up
to three words between ("final report Ofgem", "Ofgem's January 2020 final report"), else
of the source "its" refers to (the nearest in the sentence: "Ofgem, in its final report,
..."), else of the nearest source in its clause ("the final report of the E3C"), and
only otherwise ESO's final report; never across a contrast. "Technical report" is ESO's.

A figure given as a finding's structured ``quantity`` is bound by its basis: the basis's
own binding of the value when the basis names it, else the source named in the parts of
the basis that carry no other number ("ESO Table 6 sum of DNO areas (gross, reported);
E3C 973 MW; Ofgem 892 MW net" gives 931 MW ESO's Table 6, not Ofgem's "net"), else the
binding of the same value written in the statement. With the key option
``accounting.binding_options.basis_components`` (the full-investigation key only), a
part whose numbers are the value's own terms ("ESO estimate from transformer-flow
changes (150 VS + 350 RoCoF)" for 500 MW) is not another figure and names its source.
Its mismatch wording is read in those parts and on the statement value's own side, never
in the whole statement.

Classification of a mention: ``mismatched`` (a ``mismatch_any`` pattern on its own
side, unless a ``mismatch_unless_any`` pattern is on that side or, when the side ends at
"and", "or", "plus", "+" or "/", in the words that directly follow it up to the next
punctuation or number: "lost to vector shift and RoCoF"), else ``misattributed`` (bound to a wrong source), else ``attributed`` (bound to
one of its sources), else ``defined`` (``definition_any`` in its sentence, quantity
basis or derivation, or the figure's components summed in an arithmetic expression),
else ``unattributed``.

Arithmetic expressions ("737 + 244 + 150 + 350 + 210 + 187 = 1,878 MW", also with up
to four label words per term: "1,878 MW + 200 MW net at 49 Hz = 2,078 MW", "loss of
mains 500 MW + vector shift 150 MW = 650 MW") are parsed from statements, derivations,
quantity bases and report sentences: the stated result must match the computed one
within 1 MW (handoff rule for derived sums), and terms that overlap (a total with one
of its own components, or two estimates of the same quantity on different bases; key
``accounting.overlap_groups``) are reported as an ``overlap_sum`` trap. Sums written in
prose ("about 500 MW on loss of mains plus 150 MW on vector shift, about 650 MW in
total", "adding the DNO's 462 MW to ESO's 500 MW estimate gives 962 MW") are read for
the same overlap trap when the stated total is the sum of the terms (within 1 MW or
1%); they are never arithmetic errors. Everything here is a proposal for the reviewer;
criteria use the classifications through ``figure`` elements and ``accounting_caps``
(see :mod:`.sr_grading`).

This module must not import ``karotte``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from environment.incident.grading import (
    _CLAUSE_BREAK,
    _SENTENCE_BREAK,
    _any,
    _rx,
    _sentences,
    _spans,
    _time_spans,
    normalise,
)

__all__ = [
    "CLASSIFICATIONS",
    "WRONG",
    "AccountingResult",
    "Arithmetic",
    "FigureMention",
    "TextUnit",
    "analyse",
    "arithmetic_checks",
    "component_mentions",
    "figure_mentions",
    "figure_traps",
    "overlap_traps",
    "prose_sums",
    "text_units",
]

CLASSIFICATIONS = (
    "attributed",
    "defined",
    "unattributed",
    "misattributed",
    "mismatched",
)
WRONG = ("misattributed", "mismatched")

_NUMBER = r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
_NO_PREFIX = r"(?<![\w.,:/])"
# unit words after a number, by canonical unit (factor to the canonical unit)
_UNIT_WORDS: dict[str, tuple[tuple[str, float], ...]] = {
    "MW": (
        (r"mw|megawatts?", 1.0),
        (r"gw|gigawatts?", 1000.0),
        (r"kw|kilowatts?", 0.001),
    ),
    "GVA.s": (
        (r"gva[.·\s-]?s(?:ec)?|gvas|gw[.·-]s|gws", 1.0),
        (r"mva[.·\s-]?s(?:ec)?|mvas|mw[.·-]s|mws", 0.001),
    ),
    "Hz": ((r"hz|hertz", 1.0),),
}


def _unit_regex(unit: str) -> str:
    return "|".join(f"(?:{words})" for words, _ in _UNIT_WORDS[unit])


def _factor(unit: str, word: str) -> float | None:
    for words, factor in _UNIT_WORDS[unit]:
        if re.fullmatch(words, word):
            return factor
    return None


def _num(text: str) -> float:
    return float(text.replace(",", ""))


@dataclass
class TextUnit:
    """A piece of submission text read sentence by sentence: a finding field or a
    report sentence. ``extra`` is the finding's quantity basis and derivation (where
    a basis or source may be named for a number in the statement); ``basis`` the
    normalised quantity basis alone and ``finding_quantity`` the finding's structured
    quantity (for every unit of a finding; ``quantity`` is set only on the unit that
    reads the structured quantity itself)."""

    location: str
    finding_id: str | None
    status: str | None
    source: str  # statement | derivation | quantity | report
    text: str  # normalised
    extra: str = ""
    quantity: Mapping[str, Any] | None = None
    basis: str = ""
    finding_quantity: Mapping[str, Any] | None = None


@dataclass
class FigureMention:
    figure_id: str
    value: Any
    unit: str
    location: str
    finding_id: str | None
    status: str | None
    source: str
    excerpt: str
    bound_source: str | None
    classification: str
    qualified: bool
    context_score: int
    via: str = "text"  # text | quantity | components | bare (no unit: not credited)

    def to_dict(self) -> dict[str, Any]:
        return {
            "figure_id": self.figure_id,
            "value": self.value,
            "unit": self.unit,
            "location": self.location,
            "finding_id": self.finding_id,
            "status": self.status,
            "field": self.source,
            "excerpt": self.excerpt,
            "bound_source": self.bound_source,
            "classification": self.classification,
            "qualified": self.qualified,
            "via": self.via,
        }


@dataclass
class Arithmetic:
    location: str
    finding_id: str | None
    status: str | None
    expression: str
    terms: list[float]
    signs: list[int]
    stated: float
    computed: float
    unit: str | None
    ok: bool
    context: str = field(default="", repr=False)  # the text unit it was read from

    def to_dict(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "finding_id": self.finding_id,
            "status": self.status,
            "expression": self.expression,
            "terms": [s * t for s, t in zip(self.signs, self.terms, strict=True)],
            "stated": self.stated,
            "computed": round(self.computed, 6),
            "unit": self.unit,
            "within_1_mw": self.ok,
        }


# -- text units --------------------------------------------------------------------
def text_units(
    submission: Mapping[str, Any], report_texts: Iterable[tuple[str, str]]
) -> list[TextUnit]:
    """Statement, derivation and quantity-basis sentences of every finding, and every
    report sentence, as normalised :class:`TextUnit` objects."""
    units: list[TextUnit] = []
    for finding in submission.get("findings") or []:
        fid = finding["finding_id"]
        quantity = finding.get("quantity") or None
        basis = normalise(str((quantity or {}).get("basis") or ""))
        derivation = normalise(str(finding.get("derivation") or ""))
        extra = " ; ".join(t for t in (basis, derivation) if t)
        statement = finding.get("statement") or ""
        for sentence in _sentences(statement):
            units.append(
                TextUnit(
                    location=fid,
                    finding_id=fid,
                    status=finding.get("status"),
                    source="statement",
                    text=normalise(sentence),
                    extra=extra,
                    basis=basis,
                    finding_quantity=quantity,
                )
            )
        if derivation:
            units.append(
                TextUnit(
                    location=fid,
                    finding_id=fid,
                    status=finding.get("status"),
                    source="derivation",
                    text=derivation,
                    extra=" ; ".join(t for t in (basis, normalise(statement)) if t),
                    basis=basis,
                    finding_quantity=quantity,
                )
            )
        if quantity is not None:
            units.append(
                TextUnit(
                    location=fid,
                    finding_id=fid,
                    status=finding.get("status"),
                    source="quantity",
                    text=normalise(statement),
                    extra=extra,
                    quantity=quantity,
                    basis=basis,
                    finding_quantity=quantity,
                )
            )
    for location, text in report_texts:
        for sentence in _sentences(text):
            units.append(
                TextUnit(
                    location=location,
                    finding_id=None,
                    status=None,
                    source="report",
                    text=normalise(sentence),
                )
            )
    return units


# -- numbers with units ---------------------------------------------------------------
@dataclass
class _Number:
    value: Any  # float, or (lo, hi) for a range
    unit: str
    start: int
    end: int


# A number that labels a table, appendix, question, section or the like is not a
# quantity: a range never starts at one ("1,314 MW in Table 3 and 1,338 MW").
_LABEL_BEFORE = re.compile(
    r"(?<![\w-])(?:table|appendix|app\.?|q|questions?|answers?|sections?|figures?|fig\.?"
    r"|para(?:graph)?s?|stages?|rows?|lines?|items?|steps?|no\.?)\s*$"
)


def _numbers(
    text: str, unit: str, known_ranges: Iterable[tuple[float, float]] = ()
) -> list[_Number]:
    """Values (and ranges) with a unit convertible to ``unit`` in normalised text.

    Two numbers are one range only when they are written as one: "between X and Y"
    (also "between X MW and Y MW"), or "X-Y" / "X to Y" where X has no unit of its own;
    with a unit on both ("1,300 MW to 1,500 MW") only for a range of the key
    (``known_ranges``). "Rose from 1,481 MW to 1,990 MW", "150 MW and 350 MW" and "1,314
    MW in Table 3 and 1,338 MW" are two figures each."""
    units = _unit_regex(unit)
    known = list(known_ranges)
    ranges = _rx(
        _NO_PREFIX
        + r"(between\s+)?"
        + _NUMBER
        + rf"\s?((?:{units}))?\s*(-|to|and)\s*"
        + _NUMBER
        + rf"\s?({units})(?![a-z])"
    )
    found: list[_Number] = []
    taken: list[tuple[int, int]] = []
    pos = 0
    while (match := ranges.search(text, pos)) is not None:
        pos = match.start() + 1
        factor = _factor(unit, match.group(6))
        if factor is None:
            continue
        lo, hi = _num(match.group(2)) * factor, _num(match.group(5)) * factor
        if lo >= hi:  # "2019-08 ..." or a decreasing pair is not a range
            continue
        between = match.group(1) is not None
        if _LABEL_BEFORE.search(text, 0, match.start()):
            continue
        if match.group(4) == "and" and not between:
            continue
        if (
            match.group(3)
            and not between
            and not any(_near(lo, a) and _near(hi, b) for a, b in known)
        ):
            continue
        found.append(_Number((lo, hi), unit, match.start(), match.end()))
        taken.append((match.start(), match.end()))
        pos = match.end()
    single = _rx(_NO_PREFIX + _NUMBER + rf"\s?\(?\s?({units})\s?\)?(?![a-z])")
    for match in single.finditer(text):
        if any(a <= match.start() < b for a, b in taken):
            continue
        factor = _factor(unit, match.group(2).strip())
        if factor is None:
            continue
        found.append(
            _Number(_num(match.group(1)) * factor, unit, match.start(), match.end())
        )
    found.sort(key=lambda n: n.start)
    return found


def _known_ranges(
    figures: Iterable[Mapping[str, Any]],
) -> dict[str, list[tuple[float, float]]]:
    """The key's range figures by unit (1,300-1,500 MW, 350-430 MW)."""
    out: dict[str, list[tuple[float, float]]] = {}
    for figure in figures:
        if "range" in figure:
            lo, hi = (float(x) for x in figure["range"])
            out.setdefault(figure.get("unit", "MW"), []).append((lo, hi))
    return out


def _quantity_number(quantity: Mapping[str, Any], unit: str) -> float | None:
    raw_unit = normalise(str(quantity.get("unit") or ""))
    try:
        value = float(quantity.get("value"))
    except (TypeError, ValueError):
        return None
    head = re.match(r"[a-z.·]+", raw_unit)
    if head is None:
        return None
    word = head.group(0).rstrip(".")
    factor = _factor(unit, word) if re.fullmatch(_unit_regex(unit), word) else None
    return None if factor is None else value * factor


# -- binding to a source entity -------------------------------------------------------
# Adjacent source mentions joined only by these name one source ("ofgem's final report",
# "the ofgem final report", "e3c interim table 1", "eso (table 6)").
_JOIN = re.compile(r"(?:'s?)?\s*(?:\(\s*)?(?:the\s+)?")
# An owner in the possessive and a report title with a few words (a date) between them
# name one source too ("ofgem's january 2020 final report").
_OWNER_GAP = re.compile(
    r"'s?\s+(?:(?!(?:of|in|on|about|from|to|by|with|for|and|or|than|the)\b)[\w,-]+\s+)"
    r"{1,3}"
)
# A report title that names no owner. "Final report" alone is the report of the source
# named with it or nearest to it ("in its final report ofgem gives", "ofgem, in its final
# report, ...", "the final report of the e3c"); ESO's final report (``eso_final``) only
# when ESO names it or no other source is named in its clause. "Technical report" is
# the title of ESO's report and is never generic.
_GENERIC_TITLE = re.compile(r"final report")
_GENERIC_NAME = "eso_final"
_ITS = re.compile(r"(?<![\w-])(?:its|their)\s+(?:[\w,-]+\s+){0,3}$")


def _joined_name(first: str, second: str) -> str:
    """The source two adjacent mentions name: the specific one when one refines the
    other ("eso" + "table 3" is ``eso_final``), else the owner named first ("ofgem's"
    + "final report" is ``ofgem``)."""
    if second.startswith(f"{first}_"):
        return second
    return first


def _entity_mentions(
    text: str, entities: Mapping[str, Sequence[str]]
) -> list[tuple[int, int, str]]:
    found = {
        (m.start(), m.end(), name)
        for name, patterns in entities.items()
        for pattern in patterns
        for m in _rx(pattern).finditer(text)
        if m.end() > m.start()
    }
    keep = sorted(
        a
        for a in found
        if not any(
            b != a and b[0] <= a[0] and a[1] <= b[1] and (b[1] - b[0]) > (a[1] - a[0])
            for b in found
        )
    )
    # generic report titles ("final report"), resolved to their owner below
    generic = {
        (a, b)
        for a, b, name in keep
        if name == _GENERIC_NAME and _GENERIC_TITLE.fullmatch(text, a, b)
    }
    out: list[tuple[int, int, str]] = []
    titles: list[int] = []  # indices in ``out`` of generic titles not yet owned
    for mention in keep:
        is_title = (mention[0], mention[1]) in generic
        prev_title = bool(titles) and titles[-1] == len(out) - 1
        if (
            out
            and out[-1][1] <= mention[0]
            and (
                _JOIN.fullmatch(text, out[-1][1], mention[0])
                or (is_title and _OWNER_GAP.fullmatch(text, out[-1][1], mention[0]))
            )
        ):
            a, _, name = out[-1]
            if prev_title and not is_title:  # "final report ofgem": ofgem's
                titles.pop()
                name = _joined_name(mention[2], _GENERIC_NAME)
            elif is_title and not prev_title:  # "ofgem's final report"
                name = _joined_name(name, _GENERIC_NAME)
            else:
                name = _joined_name(name, mention[2])
            out[-1] = (a, mention[1], name)
        else:
            if is_title:
                titles.append(len(out))
            out.append(mention)
    if titles:
        out = _own_titles(text, out, set(titles))
    return out


def _own_titles(
    text: str, mentions: list[tuple[int, int, str]], titles: set[int]
) -> list[tuple[int, int, str]]:
    """A generic report title takes the source of the subject "its" refers to (the
    nearest other source in the sentence), else the nearest other source in its
    clause, else stays ESO's final report. Neither is looked for across a contrast
    ("210 gva.s (final report) vs 219,632 mva.s (earlier answer)")."""
    sentences = _subclauses(text, _spans(text, _SENTENCE_BREAK))
    clauses = _subclauses(text, _spans(text, _CLAUSE_BREAK))
    out = list(mentions)
    for i in sorted(titles):
        ts, te, _ = mentions[i]
        others = [m for j, m in enumerate(mentions) if j not in titles]
        if _ITS.search(text, 0, ts):
            scope = _containing(sentences, ts, len(text))
        else:
            scope = _containing(clauses, ts, len(text))
        near = [
            (ts - me if me <= ts else ms - te, ms, name)
            for ms, me, name in others
            if scope[0] <= ms and me <= scope[1]
        ]
        if near:
            out[i] = (ts, te, _joined_name(min(near)[2], _GENERIC_NAME))
    return out


def _containing(
    spans: Sequence[tuple[int, int]], pos: int, end: int
) -> tuple[int, int]:
    return next(((a, b) for a, b in spans if a <= pos < b), (0, end))


def _refine(name: str, names: Iterable[str]) -> str:
    """A specific source beats its generic parent named in the same span: "ESO Table
    3" is ESO's final report (``eso_final``), not just "ESO" (``eso``)."""
    refinements = sorted(n for n in names if n.startswith(f"{name}_"))
    return refinements[0] if len(refinements) == 1 else name


def _first_entity(text: str, entities: Mapping[str, Sequence[str]]) -> str | None:
    """The first source named in ``text`` (refined by a specific one named with it:
    "ESO Table 2" is ``eso_final``)."""
    found = _entity_mentions(text, entities)
    return _refine(found[0][2], {m[2] for m in found}) if found else None


# A list head: a source followed by a colon, possibly after a possessive, up to two words
# or a parenthesis ("ofgem: more than 1,130 mw ...", "eso table 2 cumulative: 981 mw ...",
# "eso appendix i (modelled inputs): ...") or by a reporting verb ("ofgem gives a, b and c",
# "the e3c interim report gives ...").
_COLON_HEAD = re.compile(
    r"(?:'s?)?(?:\s+[a-z][\w.'-]*){0,2}?\s*(?:\([^()]*\)\s*)?:(?!\d)"
)
_VERB_HEAD = re.compile(
    r"(?:'s?)?(?:\s+(?:report|table|account|answers?|data|returns?|timeline|summary"
    r"|figures?|text))?\s+(?:also\s+|then\s+|instead\s+)?(?:gives?|gave|reports?"
    r"|reported|puts?|says|said|states?|stated|estimates?|estimated|cites?|cited"
    r"|records?|recorded|lists?|listed|prints?|printed|shows?|showed|quotes?|quoted"
    r"|notes?|noted|has|had|counts?|counted|totals?|totalled)\b"
)


@dataclass
class _Head:
    name: str
    start: int  # the source mention
    end: int  # where the list starts (after the colon or verb)
    stop: int  # where its scope ends
    depth: int  # parentheses open at the source mention


def _list_heads(
    text: str,
    mentions: Sequence[tuple[int, int, str]],
    sentences: Sequence[tuple[int, int]],
    barriers: Sequence[int],
    openings: Sequence[int] = (),
) -> list[_Head]:
    """List heads and their scopes: to the end of the sentence (a reporting-verb list
    also to a semicolon and to an "and" that opens a new finite clause, see
    :func:`_opens_clause`), a contrast connective, the next head at the same or a lower
    parenthesis depth, and for a head inside parentheses the closing parenthesis."""
    heads: list[_Head] = []
    for ms, me, name in mentions:
        colon = _COLON_HEAD.match(text, me)
        verb = None if colon else _VERB_HEAD.match(text, me)
        match = colon or verb
        if match is None:
            continue
        end = match.end()
        _, stop = _containing(sentences, ms, len(text))
        stop = min([stop] + [pos for pos in barriers if pos >= end])
        if verb is not None:
            semi = text.find(";", end, stop)
            stop = semi if semi >= 0 else stop
            stop = min([stop] + [pos for pos in openings if pos >= end])
        depth = max(0, text.count("(", 0, ms) - text.count(")", 0, ms))
        if depth:
            close = text.find(")", end)
            stop = min(stop, close) if close >= 0 else stop
        heads.append(_Head(name, ms, end, stop, depth))
    for i, head in enumerate(heads):
        later = [h.start for h in heads[i + 1 :] if h.depth <= head.depth]
        if later:
            head.stop = min(head.stop, later[0])
    return heads


# "and" (or "so", "yet") that may open a new finite clause after a list of figures
_COORDINATOR = re.compile(r"(?:,\s*|\s)(?:and|so|yet)\s+")
# Finite verbs that make the wording after "and" a clause of its own ("..., and 1,878 MW
# is the cumulative total", "..., and LFDD relays disconnected 931 MW"): auxiliaries,
# present tenses and irregular past tenses ...
_FINITE = re.compile(
    r"(?<![\w-])(?:is|are|was|were|has|have|had|will|would|could|can|may|might|must"
    r"|should|did|does|do|gives|gave|reports|says|states|shows|puts|cites|lists|records"
    r"|notes|estimates|trips|fell|falls|rose|rises|came|comes|sits|lies|lay|includes"
    r"|exceeds|totals|accounts|amounts)(?![\w-])"
)
# ... and past forms that are also participles: after a figure they describe it ("931
# MW of demand disconnected by LFDD", "892 MW net of demand disconnected"), so there
# they open a clause only after ", and" and when a complement follows ("..., and about
# 150 MW of embedded generation tripped on vector shift"); never before "by".
_FINITE_ED = re.compile(
    r"(?<![\w-])(?:reported|said|stated|showed|put|cited|listed|recorded|noted"
    r"|estimated|tripped|disconnected|reached|dropped|remained|stayed|occurred"
    r"|totalled|included|exceeded|returned|amounted|accounted)(?![\w-])"
    r"(?!\s+by\b)"
)
_DETERMINER_BEFORE = re.compile(
    r"(?<![\w-])(?:the|an?|its|their|this|that|these|those|our|my|his|her)\s+$"
)
_LEAD = re.compile(
    r"(?:(?:the|an?|its|their|about|around|approximately|roughly|some|nearly|almost"
    r"|over|only|just|at least|more than|less than|up to|a further|another)(?![\w-])"
    r"\s*|~\s*)*"
)
_PART_END = re.compile(r",\s|;|:\s|[.!?](?=\s|$)")


def _opens_clause(text: str, coordinator: re.Match[str]) -> bool:
    """Whether the wording after "and" (``coordinator``) opens a new finite clause
    rather than continuing a list of figures: a finite verb after its first figure
    ("and 1,878 MW is the cumulative total"; a participle-like past form only after ",
    and": "..., and about 150 MW ... tripped on vector shift") or before it ("and LFDD
    relays disconnected 931 MW", "and the cumulative infeed loss was 1,878 MW"), but
    not "and at least 1,990 MW after GT1A", "and 931 MW of demand disconnected by
    LFDD" or "and the 49 Hz loss". The wording is read to the next comma, semicolon or
    sentence end."""
    pos = coordinator.end()
    stop = _PART_END.search(text, pos)
    end = stop.start() if stop else len(text)
    start = _LEAD.match(text, pos, end).end()
    first = _TOKEN_NUMBER.search(text, start, end)
    if first is not None and first.start() == start:
        nxt = _TOKEN_NUMBER.search(text, first.end(), end)
        more = _COORDINATOR.search(text, first.end(), end)
        lo = first.end()
        hi = min([end] + [m.start() for m in (nxt, more) if m is not None])
        if _FINITE.search(text, lo, hi):
            return True
        comma = coordinator.group(0).lstrip().startswith(",")
        return comma and any(
            text[verb.end() : hi].strip() for verb in _FINITE_ED.finditer(text, lo, hi)
        )
    lo, hi = pos, first.start() if first is not None else end
    return any(
        not _DETERMINER_BEFORE.search(text, pos, verb.start())
        for pattern in (_FINITE, _FINITE_ED)
        for verb in pattern.finditer(text, lo, hi)
    )


# A citation parenthesis after a figure: "(ofgem)", "(eso table 2)", "(per ofgem)".
_CITATION_OPEN = re.compile(r"\(\s*(?:per |see |source:? |from |cf\.? )?")
# Wording that makes a trailing source shared by coordinated figures ("the 150 mw
# vector-shift and 350 mw rocof estimates made by eso", "... figures are eso's").
_SHARED = re.compile(
    r"(?<![\w-])(?:estimates|figures|values|numbers|totals|losses|both|are|were"
    r"|respectively|each)(?![\w-])"
)
# Two figures joined only by "and" or a comma, with at most three label words after the
# first ("150 mw vector-shift and 350 mw ...", "1,130 mw and 1,500 mw"); not across a
# stage, time or verb ("1,990 mw after gt1a and ...").
_COORDINATED = re.compile(
    r"((?:\s+[a-z][\w'-]*){0,3}?)\s*(?:,\s*(?:and\s+)?|\s+and\s+|\s*&\s*)"
    + _LEAD.pattern
)
_NOT_LABEL = re.compile(
    r"(?<![\w-])(?:after|before|at|within|by|from|through|during|until|since|when|then"
    r"|which|that|while|whereas|but|is|are|was|were|has|had|gives?|gave|reports?"
    r"|reported|says|said|states?|stated|shows?|showed)(?![\w-])"
)


def _trailing_source(
    text: str,
    number: _Number,
    side_end: int,
    mentions: Sequence[tuple[int, int, str]],
    citation_only: bool = False,
) -> str | None:
    """The source named after ``number`` at the end of its own side when it may be
    shared with figures before it: a citation parenthesis ("a and b (Ofgem)") or, unless
    ``citation_only``, a trailing predicate with shared wording ("... and 350 MW RoCoF
    estimates made by ESO", "... figures are ESO estimates")."""
    after = [m for m in mentions if m[0] >= number.end and m[1] <= side_end]
    if not after:
        return None
    ms, me, name = after[0]
    gap = text[number.end : ms]
    if _TOKEN_NUMBER.search(gap):
        return None
    opening = gap.rfind("(")
    if opening >= 0 and _CITATION_OPEN.fullmatch(gap, opening):
        close = text.find(")", me, side_end + 1)
        if 0 <= close - me <= 30 and "(" not in text[me:close]:
            return name
    if citation_only:
        return None
    rest = text[me:side_end]
    if _SHARED.search(gap) and len(re.findall(r"[a-z][\w'-]*", rest)) <= 3:
        return name
    return None


def _parenthesis_end(text: str, pos: int) -> int:
    """The position of the closing parenthesis of the innermost parenthesis open at
    ``pos``, or the end of the text when ``pos`` is not inside one."""
    depth = 0
    for i in range(pos - 1, -1, -1):
        if text[i] == ")":
            depth += 1
        elif text[i] == "(":
            if depth:
                depth -= 1
            else:
                inner = 0
                for j in range(pos, len(text)):
                    if text[j] == "(":
                        inner += 1
                    elif text[j] == ")":
                        if inner:
                            inner -= 1
                        else:
                            return j
                return len(text)
    return len(text)


def _bind_numbers(
    text: str,
    numbers: Sequence[_Number],
    mentions: Sequence[tuple[int, int, str]],
    sides: Mapping[tuple[int, int], tuple[tuple[int, int], tuple[int, int]]],
    clauses: Sequence[tuple[int, int]],
    sentences: Sequence[tuple[int, int]],
    barriers: Sequence[int],
    openings: Sequence[int] = (),
) -> dict[tuple[int, int], str | None]:
    """The source each number of ``text`` is given on (steps 1-4 of the module
    docstring; the quantity basis fallback is applied by the caller)."""
    ordered = sorted(numbers, key=lambda n: n.start)
    spans = [(n.start, n.end) for n in ordered]
    heads = _list_heads(text, mentions, sentences, barriers, openings)
    # a head after a figure that introduces figures of its own is not that figure's
    # source ("... 1,878 mw over the event; ofgem says ... and gives 1,990 mw")
    heading = {h.start for h in heads if any(h.end <= s < h.stop for s, _ in spans)}
    own: dict[tuple[int, int], str | None] = {}
    # where each number's own source closes: the end of a parenthesis around it
    closes: dict[tuple[int, int], int] = {}
    for number in ordered:  # 1. the nearest source on the number's own side
        start, end = number.start, number.end
        (a, b), _ = sides[(start, end)]
        near = []
        for ms, me, name in mentions:
            if ms < a or me > b:
                continue
            if me <= start:
                near.append((start - me, 0, name, ms))
            elif ms >= end:
                near.append((ms - end, 1, name, ms))
            else:
                near.append((0, 0, name, ms))
        if near:
            best = min(near)
            own[(start, end)] = _refine(best[2], {n[2] for n in near})
            closes[(start, end)] = _parenthesis_end(text, best[3])
        else:
            own[(start, end)] = None
    out: dict[tuple[int, int], str | None] = {}
    blocking = list(barriers) + list(openings)

    def coordinated_source(i: int) -> str | None:
        """The trailing source shared by the figures coordinated with figure ``i``
        ("the 150 mw vector-shift and 350 mw rocof estimates made by eso")."""
        j = i
        while j + 1 < len(ordered):
            left, right = ordered[j], ordered[j + 1]
            joined = _COORDINATED.fullmatch(text, left.end, right.start)
            if joined is None or _NOT_LABEL.search(joined.group(1)):
                return None
            name = own[(right.start, right.end)]
            if name is not None:
                (_, side_end), _ = sides[(right.start, right.end)]
                found = _trailing_source(text, right, side_end, mentions)
                return name if found == name else None
            j += 1
        return None

    for i, number in enumerate(ordered):
        start, end = number.start, number.end
        _, sub = sides[(start, end)]
        bound = own[(start, end)]
        covering = [h for h in heads if h.end <= start and end <= h.stop]
        # 2. a source shared by coordinated figures after it (it overrides a shared
        # subject, not a list head that covers the number)
        if bound is None and not covering:
            bound = coordinated_source(i)
        # ... a shared subject: the number before it in the same sub-clause (not
        # across alternatives: "or", "with")
        if bound is None and i > 0:
            prev = ordered[i - 1]
            if (
                prev.start >= sub[0]
                and out.get((prev.start, prev.end)) is not None
                and not _SEPARATE.search(text[prev.end : start])
                # not a citation parenthesis closed before the number ("1,878 mw
                # (eso) plus 1,300-1,500 mw ...")
                and closes.get((prev.start, prev.end), len(text)) > start
            ):
                bound = out[(prev.start, prev.end)]
        # ... or a citation parenthesis after the next number of the sub-clause when
        # nothing divides the wording between them ("350 MW because about 550 MW ...
        # also tripped (Ofgem)"); a source merely on the next number's side is that
        # number's ("1,878 MW ... the 1,990 MW in Ofgem's report")
        if bound is None and i + 1 < len(ordered):
            nxt = ordered[i + 1]
            if nxt.end <= sub[1] and _split_kind(text, number, nxt, mentions) is None:
                (_, side_end), _ = sides[(nxt.start, nxt.end)]
                cited = _trailing_source(
                    text, nxt, side_end, mentions, citation_only=True
                )
                if cited is not None and cited == own[(nxt.start, nxt.end)]:
                    bound = cited
        # 3. the nearest list head whose scope covers the number
        if bound is None and covering:
            bound = covering[-1].name
        # 4. the nearest preceding source, else the only one named, when clear
        if bound is None:
            others = [s for s in spans if s != (start, end)]

            def clear(ms: int, me: int, start: int = start, end: int = end) -> bool:
                lo, hi = (me, start) if me <= start else (end, ms)
                if any(lo <= os and oe <= hi for os, oe in others):
                    return False
                if any(lo <= pos < hi for pos in blocking):
                    return False
                # a source after the number: not across a semicolon, and not a head
                # that introduces figures of its own
                if ms >= end and (";" in text[end:ms] or ms in heading):
                    return False
                # a source in another clause that has a number of its own is that
                # number's
                ca, cb = next(((x, y) for x, y in clauses if x <= ms < y), (ms, me))
                return not any(ca <= os < cb for os, _ in others)

            before = [m for m in mentions if m[1] <= start and clear(m[0], m[1])]
            names = {m[2] for m in mentions if clear(m[0], m[1])}
            if before:
                bound = before[-1][2]
            elif len(names) == 1 and len({m[2] for m in mentions}) == 1:
                bound = next(iter(names))
        out[(start, end)] = bound
    return out


@dataclass
class _Reading:
    """One text read for figures: its numbers (of every unit), their own sides and
    sub-clauses, and the source each is bound to."""

    text: str
    clauses: list[tuple[int, int]]
    subclauses: list[tuple[int, int]]
    sentences: list[tuple[int, int]]
    mentions: list[tuple[int, int, str]]
    numbers: list[_Number]
    sides: dict[tuple[int, int], tuple[tuple[int, int], tuple[int, int]]]
    bindings: dict[tuple[int, int], str | None]


def _read(
    text: str,
    units: Iterable[str],
    entities: Mapping[str, Sequence[str]],
    ranges: Mapping[str, Sequence[tuple[float, float]]] | None = None,
) -> _Reading:
    clauses = _spans(text, _CLAUSE_BREAK)
    subclauses = _subclauses(text, clauses)
    sentences = _spans(text, _SENTENCE_BREAK)
    mentions = _entity_mentions(text, entities)
    numbers = sorted(
        (
            n
            for unit in units
            for n in _numbers(text, unit, (ranges or {}).get(unit, ()))
        ),
        key=lambda n: n.start,
    )
    sides = _own_sides(text, numbers, subclauses, mentions)
    barriers = [m.start() for m in _CONTRAST.finditer(text)]
    openings = [
        m.start() for m in _COORDINATOR.finditer(text) if _opens_clause(text, m)
    ]
    bindings = _bind_numbers(
        text, numbers, mentions, sides, subclauses, sentences, barriers, openings
    )
    return _Reading(
        text, clauses, subclauses, sentences, mentions, numbers, sides, bindings
    )


# -- figures ---------------------------------------------------------------------------
def _matches(figure: Mapping[str, Any], number: Any) -> bool:
    tol = float(figure.get("match_abs", 1)) + 1e-9
    if "range" in figure:
        if not isinstance(number, tuple):
            return False
        lo, hi = (float(x) for x in figure["range"])
        return abs(number[0] - lo) <= tol and abs(number[1] - hi) <= tol
    if isinstance(number, tuple):
        return False
    return abs(number - float(figure["value"])) <= tol


def _classify(
    figure: Mapping[str, Any],
    segment: str,
    tailed: str,
    sentence: str,
    extra: str,
    bound: str | None,
) -> str:
    # ``mismatch_unless_any`` (optional; increment A's figures never carry it): wording
    # on the figure's own side, or in the words directly coordinated with its end
    # (``tailed``, see ``_side_text``), that cancels its mismatch: "lost to vector shift"
    # and "lost to vector shift and RoCoF" end their own sides alike, at "and"
    if _any(segment, figure.get("mismatch_any") or ()) and not _any(
        tailed, figure.get("mismatch_unless_any") or ()
    ):
        return "mismatched"
    if bound is not None and bound in (figure.get("wrong_sources") or ()):
        return "misattributed"
    if bound is not None and bound in (figure.get("sources") or ()):
        return "attributed"
    if _any(sentence, figure.get("definition_any") or ()) or _any(
        extra, figure.get("definition_any") or ()
    ):
        return "defined"
    return "unattributed"


# Wording on either side of these belongs to different figures ("ESO's 1,878 MW vs
# Ofgem's at least 1,990 MW", "the 1,878 MW total sits below the at least 1,990 MW in
# Ofgem's report", "..., whereas 1,878 MW is ...", "462 MW, close to the estimated 150
# MW ..."). "than" or "close to" directly before a number is a quantifier ("more than
# 1,130 MW"), not a comparison; "against" is left out ("secured against a loss of 1,000
# MW").
_CONTRAST = re.compile(
    r"(?<![\w-])(?:vs\.?|v\.|versus|compared (?:with|to)|in contrast (?:with|to)|"
    r"contrasted with|as opposed to|rather than|instead of|unlike|whereas|while|but|"
    r"below|above|exceed(?:s|ed|ing)?|"
    r"(?:than|close to|similar to|comparable (?:to|with)|consistent with|in line with)"
    r"(?!\s+(?:about |around |approximately |roughly |~\s?)?\d))(?![\w-])"
)
# Weaker separators: between two figures, the wording after one introduces the next
# ("892 MW of net demand with ESO's 931 MW", "931 MW (ESO) or 892 MW (Ofgem)").
_ALTERNATIVE = re.compile(r"(?<![\w-])(?:or|with|plus)(?![\w-])")
_POSSESSIVE = re.compile(r"'s?(?![\w])")
# Alternatives: a figure after one of these is not given on the source of the figure
# before it ("931 MW (ESO) or 892 MW net").
_SEPARATE = re.compile(r"(?<![\w-])(?:or|with)(?![\w-])")


def _subclauses(text: str, clauses: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    """Clauses cut at contrast connectives (see ``_CONTRAST``)."""
    out: list[tuple[int, int]] = []
    for a, b in clauses:
        start = a
        for match in _CONTRAST.finditer(text, a, b):
            out.append((start, match.start()))
            start = match.end()
        out.append((start, b))
    return out


def _split_kind(
    text: str,
    left: _Number,
    right: _Number,
    mentions: Sequence[tuple[int, int, str]],
) -> tuple[int, str] | None:
    """Where and why the wording between two figures of one sub-clause divides: at
    the last weak connective ("or", "with", "plus"), else at an opening parenthesis
    that is not closed before the right figure ("931 MW of demand (net reduction ...
    about 350 MW)"), else before a source named in the possessive ("... with ESO's 931
    MW"); ``None`` when nothing divides it (the wording follows the left figure). A
    parenthesis around the left figure that closes before the right one is the left
    figure's ("(1,481 MW on ESO's basis) exceeded the secured 1,000 MW")."""
    lo, hi = left.end, right.start
    floor, depth = lo, 0
    for pos in range(lo, hi):
        if text[pos] == "(":
            depth += 1
        elif text[pos] == ")":
            if depth:
                depth -= 1
            else:
                floor = pos + 1
    weak = [m.start() for m in _ALTERNATIVE.finditer(text, floor, hi)]
    if weak:
        return weak[-1], "weak"
    unclosed: list[int] = []
    for pos in range(floor, hi):
        if text[pos] == "(":
            unclosed.append(pos)
        elif text[pos] == ")" and unclosed:
            unclosed.pop()
    if unclosed:
        return unclosed[0], "parenthesis"
    possessive = [
        ms
        for ms, me, _ in mentions
        if floor <= ms and me <= hi and _POSSESSIVE.match(text, me)
    ]
    if possessive:
        return possessive[-1], "possessive"
    return None


def _split(
    text: str,
    left: _Number,
    right: _Number,
    mentions: Sequence[tuple[int, int, str]],
) -> int:
    """Where the wording between two figures of one sub-clause divides (see
    :func:`_split_kind`); else after all of it (wording that follows a figure belongs
    to it)."""
    kind = _split_kind(text, left, right, mentions)
    return right.start if kind is None else kind[0]


def _own_sides(
    text: str,
    numbers: Sequence[_Number],
    subclauses: Sequence[tuple[int, int]],
    mentions: Sequence[tuple[int, int, str]],
) -> dict[tuple[int, int], tuple[tuple[int, int], tuple[int, int]]]:
    """For every number: the wording that belongs to it alone (its *own side*) and its
    sub-clause. Text between two numbers of one sub-clause goes to one of them only
    (:func:`_split`); a contrast connective ends both sides."""
    ordered = sorted(numbers, key=lambda n: n.start)
    out: dict[tuple[int, int], tuple[tuple[int, int], tuple[int, int]]] = {}
    for i, number in enumerate(ordered):
        sub = _containing(subclauses, number.start, len(text))
        a, b = sub
        if i > 0 and ordered[i - 1].start >= sub[0]:
            a = max(a, _split(text, ordered[i - 1], number, mentions))
        if i + 1 < len(ordered) and ordered[i + 1].end <= sub[1]:
            b = min(b, _split(text, number, ordered[i + 1], mentions))
        a = min(a, number.start)
        b = max(b, number.end)
        out[(number.start, number.end)] = ((a, b), sub)
    return out


def _near(a: float, b: float) -> bool:
    return abs(a - b) <= 1.0 + 1e-9


# A figure's own side ends at "and" (a clause break), which cuts "580 MW lost to vector
# shift and RoCoF" short of its second mechanism. ``mismatch_unless_any`` therefore also
# reads the words that directly follow a coordinator at the end of the own side, up to
# the next punctuation or number; never the rest of the sentence ("580 MW lost to
# vector shift, compared with 500 MW for vector shift and RoCoF" is still mismatched).
_COORDINATED_END = re.compile(r"(?:(?<![\w-])(?:and|or|plus)|[&+/])\s*$")
_COORDINATED_TAIL = re.compile(r"[^.;:,()\d]{0,40}")


def _side_text(reading: _Reading, number: _Number, coordinated: bool = False) -> str:
    """A number's own side; with ``coordinated``, extended by the words that directly
    follow a coordinator it ends at (see ``_COORDINATED_END``)."""
    (a, b), _ = reading.sides[(number.start, number.end)]
    return (
        _with_coordinated_tail(reading.text, a, b) if coordinated else reading.text[a:b]
    )


def _with_coordinated_tail(text: str, a: int, b: int) -> str:
    own = text[a:b]
    if _COORDINATED_END.search(own):
        tail = _COORDINATED_TAIL.match(text, b)
        own += tail.group(0) if tail else ""
    return own


def _named(reading: _Reading, value: float) -> list[_Number]:
    """The point numbers of a reading within 1 unit of ``value``."""
    return [
        n
        for n in reading.numbers
        if not isinstance(n.value, tuple) and _near(float(n.value), value)
    ]


_TOKEN_NUMBER = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\w])"
)


_SUM_WORDING = re.compile(r"\+|\bplus\b|\band\b")


def _own_terms(tokens: Sequence[float], value: float, text: str) -> bool:
    """Whether the numbers of a basis part are the quantity's own terms: at least two
    numbers besides the value that add up to it within 1 unit, joined by "+", "plus"
    or "and" ("ESO estimate from transformer-flow changes (150 VS + 350 RoCoF)" for
    500 MW)."""
    terms = [t for t in tokens if not _near(t, value)]
    return (
        len(terms) >= 2
        and _near(sum(terms), value)
        and _SUM_WORDING.search(text) is not None
    )


def _quantity_basis(
    basis: _Reading,
    statement: _Reading,
    value: float,
    entities: Mapping[str, Sequence[str]],
    other_values: Iterable[float] = (),
    own_terms: bool = False,
) -> tuple[str | None, str, str]:
    """The source, the own wording and the own wording with its coordinated tails
    (``_side_text``; read by ``mismatch_unless_any`` only) of a structured quantity: the basis's binding of
    the value when the basis names it; else the basis parts (clauses) that carry no
    other figure (a number with a unit, or another key figure's value written without
    one: "alternatives 973 (E3C) and 892 net (Ofgem)"); else the binding of the same
    value written in the statement; else the statement's only source. With
    ``own_terms`` (key ``accounting.binding_options.basis_components``; the
    full-investigation key only) a part whose numbers are the value's own terms
    (:func:`_own_terms`) is not another figure: "ESO estimate from transformer-flow
    changes (150 VS + 350 RoCoF)" names the 500 MW's source."""
    others = [v for v in other_values if not _near(v, value)]
    own: list[str] = []
    tailed: list[str] = []
    bound: str | None = None
    named = _named(basis, value)
    if named:
        bound = basis.bindings.get((named[0].start, named[0].end))
        own.append(_side_text(basis, named[0]))
        tailed.append(_side_text(basis, named[0], coordinated=True))
    else:
        parts = []
        for a, b in basis.clauses:
            if any(a <= n.start < b for n in basis.numbers):
                continue
            tokens = [
                _num(m.group(1)) for m in _TOKEN_NUMBER.finditer(basis.text, a, b)
            ]
            if any(_near(t, v) for t in tokens for v in others) and not (
                own_terms and _own_terms(tokens, value, basis.text[a:b])
            ):
                continue
            parts.append(basis.text[a:b])
            tailed.append(_with_coordinated_tail(basis.text, a, b))
        own += parts
        bound = _first_entity(" ; ".join(parts), entities)
    in_statement = _named(statement, value)
    for n in in_statement:
        own.append(_side_text(statement, n))
        tailed.append(_side_text(statement, n, coordinated=True))
    if bound is None:
        bound = next(
            (
                statement.bindings[(n.start, n.end)]
                for n in in_statement
                if statement.bindings.get((n.start, n.end))
            ),
            None,
        )
    if bound is None and not in_statement:
        names = {name for _, _, name in statement.mentions}
        if len(names) == 1:
            bound = next(iter(names))
    return bound, " ; ".join(t for t in own if t), " ; ".join(t for t in tailed if t)


def _extra_binding(
    unit_text: TextUnit,
    reading: _Reading,
    number: _Number,
    units: Iterable[str],
    entities: Mapping[str, Sequence[str]],
    other_values: Iterable[float] = (),
    ranges: Mapping[str, Sequence[tuple[float, float]]] | None = None,
    own_terms: bool = False,
) -> str | None:
    """Step 5: the source the quantity basis or derivation gives a statement number
    that steps 1-4 leave unbound, only when the number is the quantity's own value or
    that text names it too (a basis describes its own quantity, not every number of
    the statement)."""
    if isinstance(number.value, tuple) or not unit_text.extra:
        return None
    value = float(number.value)
    extra = _read(unit_text.extra, units, entities, ranges)
    named = _named(extra, value)
    if named:
        bound = extra.bindings.get((named[0].start, named[0].end))
        return bound or _first_entity(unit_text.extra, entities)
    quantity = _quantity_number(unit_text.finding_quantity or {}, number.unit)
    if quantity is not None and _near(quantity, value) and unit_text.basis:
        basis = _read(unit_text.basis, units, entities, ranges)
        return _quantity_basis(
            basis, reading, value, entities, other_values, own_terms
        )[0]
    return None


def figure_mentions(
    units: Sequence[TextUnit],
    figures: Sequence[Mapping[str, Any]],
    entities: Mapping[str, Sequence[str]],
    options: Mapping[str, Any] | None = None,
) -> list[FigureMention]:
    """Every mention of a key figure in the submission, classified by basis.
    ``options``: the key's ``accounting.binding_options`` (``basis_components``, see
    :func:`_quantity_basis`; absent from increment A's key)."""
    own_terms = bool((options or {}).get("basis_components"))
    out: list[FigureMention] = []
    by_unit: dict[str, list[Mapping[str, Any]]] = {}
    for figure in figures:
        by_unit.setdefault(figure.get("unit", "MW"), []).append(figure)
    values: dict[str, list[float]] = {
        unit: [
            float(v)
            for f in figs
            for v in (f["range"] if "range" in f else [f["value"]])
        ]
        for unit, figs in by_unit.items()
    }
    ranges = _known_ranges(figures)
    for unit_text in units:
        text = unit_text.text
        reading = _read(text, by_unit, entities, ranges)
        quantity = unit_text.source == "quantity"
        basis = _read(unit_text.basis, by_unit, entities, ranges) if quantity else None
        for unit, candidates in by_unit.items():
            if quantity:
                value = _quantity_number(unit_text.quantity or {}, unit)
                if value is None:
                    continue
                numbers = [_Number(value, unit, 0, 0)]
            else:
                numbers = [n for n in reading.numbers if n.unit == unit]
            for number in numbers:
                scored: list[tuple[int, Mapping[str, Any]]] = []
                if quantity:
                    clause = sentence = text
                else:
                    ca, cb = _containing(reading.clauses, number.start, len(text))
                    sa, sb = _containing(reading.sentences, number.start, len(text))
                    clause, sentence = text[ca:cb], text[sa:sb]
                for figure in candidates:
                    if not _matches(figure, number.value):
                        continue
                    context = figure.get("context_any") or ()
                    if not context or _any(clause, context):
                        score = 2
                    elif _any(sentence, context) or (
                        quantity and _any(unit_text.extra, context)
                    ):
                        score = 1
                    else:
                        continue
                    scored.append((score, figure))
                if not scored:
                    continue
                best = max(score for score, _ in scored)
                if basis is not None:
                    bound, segment, tailed = _quantity_basis(
                        basis,
                        reading,
                        float(number.value),
                        entities,
                        values[unit],
                        own_terms,
                    )
                else:
                    segment = _side_text(reading, number)
                    tailed = _side_text(reading, number, coordinated=True)
                    bound = reading.bindings.get((number.start, number.end))
                    if bound is None:
                        bound = _extra_binding(
                            unit_text,
                            reading,
                            number,
                            by_unit,
                            entities,
                            values[unit],
                            ranges,
                            own_terms,
                        )
                for score, figure in scored:
                    if score < best:
                        continue
                    qualifier = figure.get("qualifier_any") or ()
                    qualified = bool(qualifier) and (
                        _any(sentence, qualifier) or _any(unit_text.extra, qualifier)
                    )
                    out.append(
                        FigureMention(
                            figure_id=figure["figure_id"],
                            value=list(number.value)
                            if isinstance(number.value, tuple)
                            else number.value,
                            unit=unit,
                            location=unit_text.location,
                            finding_id=unit_text.finding_id,
                            status=unit_text.status,
                            source=unit_text.source,
                            excerpt=sentence[:300],
                            bound_source=bound,
                            classification=_classify(
                                figure,
                                segment,
                                tailed,
                                sentence,
                                unit_text.extra,
                                bound,
                            ),
                            qualified=qualified,
                            context_score=score,
                            via="quantity" if quantity else "text",
                        )
                    )
        if not quantity and "MW" in by_unit:
            out += _bare_mentions(unit_text, by_unit["MW"], reading.numbers)
    return out


_BARE = re.compile(
    r"(?<![\w.,:/±])(\d{1,3}(?:,\d{3})+|\d+)"
    r"(?![\w:]|[.,]\d|\s?(?:%|hz|mw|gw|kw|ms|s\b))"
)


def _bare_mentions(
    unit_text: TextUnit,
    figures: Sequence[Mapping[str, Any]],
    numbers: Sequence[_Number],
) -> list[FigureMention]:
    """Key figures written without a unit in a text that names megawatts ("vector
    shift ~150 (est.)", "737 + 244 + ... = 1878"): candidates a human decides, never
    credited automatically (``via`` ``bare``)."""
    text = unit_text.text
    if not re.search(r"\b(?:mw|gw|megawatt)", text + " " + unit_text.extra):
        return []
    taken = [(n.start, n.end) for n in numbers] + [
        (a, b) for _, a, b in _time_spans(text)
    ]
    clauses = _spans(text, _CLAUSE_BREAK)
    sentences = _spans(text, _SENTENCE_BREAK)
    out = []
    for match in _BARE.finditer(text):
        if any(a <= match.start() < b for a, b in taken):
            continue
        value = _num(match.group(1))
        ca, cb = _containing(clauses, match.start(), len(text))
        sa, sb = _containing(sentences, match.start(), len(text))
        for figure in figures:
            if "range" in figure or not _matches(figure, value):
                continue
            context = figure.get("context_any") or ()
            if context and not (
                _any(text[ca:cb], context) or _any(text[sa:sb], context)
            ):
                continue
            out.append(
                FigureMention(
                    figure_id=figure["figure_id"],
                    value=value,
                    unit=figure.get("unit", "MW"),
                    location=unit_text.location,
                    finding_id=unit_text.finding_id,
                    status=unit_text.status,
                    source=unit_text.source,
                    excerpt=text[sa:sb][:300],
                    bound_source=None,
                    classification="unattributed",
                    qualified=False,
                    context_score=1,
                    via="bare",
                )
            )
    return out


# -- arithmetic -----------------------------------------------------------------------
_TOKEN = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
_END = r"(?![\w]|\.\d)"
# A term may carry up to four label words ("loss of mains 500 mw + vector shift 150 mw",
# "200 mw net at 49 hz"): words (not verbs, conjunctions or the result keywords) or a
# frequency. A hyphen between two letters ("vector-shift") is not a minus sign.
_LABEL = (
    r"(?:(?!(?:is|are|was|were|be|been|gives?|gave|makes?|made|equals?|total\w*|and|or"
    r"|but|so|then|than|which|that|this|plus|minus)(?![\w'-]))[a-z][a-z0-9'-]*"
    r"|\d+(?:\.\d+)?\s?hz(?![a-z]))"
)
_OP = r"(?:\+|(?<![a-z])-|-(?![a-z]))"
_TERM = _TOKEN + r"\s?(?:mw|gw)?(?![a-z])(?:\s+" + _LABEL + r"){0,4}?"
_EXPRESSION = re.compile(
    _NO_PREFIX
    + _TERM
    + r"(?:\s*"
    + _OP
    + r"\s*(?:"
    + _LABEL
    + r"\s+){0,4}?"
    + _TERM
    + r")+"
    + r"\s*(?:=|≈|~=|equals|gives|makes|totals?|totall?ing|is|are)\s*"
    + r"(?:about |approximately |approx\.? |around |~ ?|c\. ?)?"
    + _TOKEN
    + r"\s?(?:mw|gw)?"
    + _END
)
_OPERATOR = re.compile(r"\s*(" + _OP + r")\s*")
_RESULT = re.compile(
    r"\s*(=|≈|~=|(?<![\w-])(?:equals|gives|makes|totals?|totall?ing|is|are)(?![\w-]))\s*"
)
_TERM_NUMBER = re.compile(
    r"(?<![\w.,])(" + _TOKEN + r")(?![\w])(?!\s?hz(?![a-z]))\s?(mw|gw)?(?![a-z])"
)


def _expression_terms(expression: str) -> tuple[list[int], list[float], float] | None:
    head, _, tail = _RESULT.split(expression, maxsplit=1)
    pieces = _OPERATOR.split(head)
    signs, terms = [1], []
    try:
        terms.append(_term_value(pieces[0]))
        for i in range(1, len(pieces), 2):
            signs.append(1 if pieces[i] == "+" else -1)
            terms.append(_term_value(pieces[i + 1]))
        result = re.search(_TOKEN + r"\s?(?:mw|gw)?", tail)
        if result is None:
            return None
        stated = _term_value(result.group(0))
    except (ValueError, IndexError):
        return None
    return signs, terms, stated


def _term_value(text: str) -> float:
    """The megawatt number of a (possibly labelled) term; exactly one is required."""
    found = list(_TERM_NUMBER.finditer(text))
    if len(found) != 1:
        raise ValueError(text)
    value = float(found[0].group(1).replace(",", ""))
    return value * 1000 if found[0].group(2) == "gw" else value


def arithmetic_checks(units: Sequence[TextUnit]) -> list[Arithmetic]:
    """Sums and differences of megawatt figures written as ``a + b - c = d``. Only
    expressions with a megawatt unit, or in a text that names megawatts, are kept;
    clock times, dates and ranges are not expressions."""
    out: list[Arithmetic] = []
    seen: set[tuple[str, str]] = set()
    for unit in units:
        if unit.source == "quantity":
            continue
        for match in _EXPRESSION.finditer(unit.text):
            expression = match.group(0)
            if (unit.location, expression) in seen:
                continue
            parsed = _expression_terms(expression)
            if parsed is None:
                continue
            signs, terms, stated = parsed
            named = bool(re.search(r"\b(?:mw|gw)\b", expression)) or bool(
                re.search(r"\b(?:mw|gw|megawatt)", unit.text + " " + unit.extra)
            )
            if not named or len(terms) < 2 or min(terms) <= 0:
                continue
            seen.add((unit.location, expression))
            computed = sum(s * t for s, t in zip(signs, terms, strict=True))
            out.append(
                Arithmetic(
                    location=unit.location,
                    finding_id=unit.finding_id,
                    status=unit.status,
                    expression=expression,
                    terms=terms,
                    signs=signs,
                    stated=stated,
                    computed=computed,
                    unit="MW",
                    ok=abs(computed - stated) <= 1 + 1e-9,
                    context=unit.text,
                )
            )
    return out


# Sums written in prose ("about 500 MW on loss of mains plus 150 MW on vector shift,
# about 650 MW in total"; "adding the DNO's 462 MW to ESO's 500 MW estimate gives 962
# MW"). The wording between the terms and before the stated total is short and has no
# other figure; the stated total must be the sum of the terms (within 1 MW or 1%).
_PROSE_WORDS = r"(?:[\s,]+(?:[a-z][\w'-]*|\d+(?:\.\d+)?\s?hz(?![a-z])|~))"
_PROSE_PLUS = re.compile(
    _PROSE_WORDS + r"{0,5}?[\s,]+plus" + _PROSE_WORDS + r"{0,4}\s*"
)
_PROSE_TO = re.compile(_PROSE_WORDS + r"{0,5}?\s+to" + _PROSE_WORDS + r"{0,4}\s*")
_PROSE_RESULT = re.compile(
    r"(?:=|≈|(?<![\w-])(?:about|around|approximately|roughly|some|in total|total(?:ling"
    r"|ing|led|s)?|a total of|gives?|giving|gave|makes?|making|comes? to|came to"
    r"|amounts? to|sums? to|yields?)(?![\w-]))"
)
_PROSE_GAP = re.compile(_PROSE_WORDS + r"{0,6}\s*")
_PROSE_ADD = re.compile(r"(?<![\w-])add(?:s|ed|ing)?(?![\w-])")
_IN_TOTAL = re.compile(r"\s*(?:mw|gw)?\s+(?:in total|in all|altogether|combined)\b")


def _prose_total(text: str, last: _Number, result: _Number) -> bool:
    """Whether ``result`` is given as the total of the terms before it: a result word
    in the short gap after the last term ("..., about 650 MW", "gives 962 MW") or "in
    total" after it."""
    gap = text[last.end : result.start]
    if not _PROSE_GAP.fullmatch(gap):
        return False
    return bool(_PROSE_RESULT.search(gap)) or bool(_IN_TOTAL.match(text, result.end))


def prose_sums(units: Sequence[TextUnit]) -> list[Arithmetic]:
    """Sums of megawatt figures written in words ("X plus Y ..., about Z in total",
    "adding X to Y gives Z"). They are read for overlapping terms only (the
    ``overlap_sum`` trap); a prose sum is never an arithmetic error."""
    out: list[Arithmetic] = []
    for unit in units:
        if unit.source == "quantity":
            continue
        text = unit.text
        numbers = [n for n in _numbers(text, "MW") if not isinstance(n.value, tuple)]
        found: list[tuple[int, int, list[float], float]] = []
        for i in range(len(numbers)):
            chain = [numbers[i]]
            adding = _PROSE_ADD.search(
                text, max(0, numbers[i].start - 40), numbers[i].start
            )
            joiner = _PROSE_TO if adding and len(chain) == 1 else _PROSE_PLUS
            k = i
            while k + 1 < len(numbers) and joiner.fullmatch(
                text, numbers[k].end, numbers[k + 1].start
            ):
                chain.append(numbers[k + 1])
                k += 1
                joiner = _PROSE_PLUS
            if len(chain) < 2 or k + 1 >= len(numbers):
                continue
            result = numbers[k + 1]
            if not _prose_total(text, chain[-1], result):
                continue
            terms = [float(n.value) for n in chain]
            stated = float(result.value)
            if abs(sum(terms) - stated) > max(1.0, 0.01 * stated) + 1e-9:
                continue
            found.append((chain[0].start, result.end, terms, stated))
        for a, b, terms, stated in found:
            if any(x <= a and b <= y and (x, y) != (a, b) for x, y, _, _ in found):
                continue  # a shorter chain inside a longer one
            out.append(
                Arithmetic(
                    location=unit.location,
                    finding_id=unit.finding_id,
                    status=unit.status,
                    expression=text[a:b],
                    terms=terms,
                    signs=[1] * len(terms),
                    stated=stated,
                    computed=sum(terms),
                    unit="MW",
                    ok=True,
                    context=text,
                )
            )
    return out


def _close(a: float, b: float, tol: float = 1.0) -> bool:
    return abs(a - b) <= tol + 1e-9


def _multiset_match(terms: Sequence[float], components: Sequence[float]) -> bool:
    remaining = list(components)
    if len(terms) != len(remaining):
        return False
    for term in terms:
        hit = next((c for c in remaining if _close(term, c)), None)
        if hit is None:
            return False
        remaining.remove(hit)
    return True


def component_mentions(
    arithmetic: Sequence[Arithmetic], figures: Sequence[Mapping[str, Any]]
) -> list[FigureMention]:
    """A sum of a figure's ``components`` that gives the figure defines its basis
    (e.g. the six ESO components summed to 1,878 MW)."""
    out: list[FigureMention] = []
    for item in arithmetic:
        if any(s < 0 for s in item.signs):
            continue
        for figure in figures:
            components = figure.get("components")
            if not components or "value" not in figure:
                continue
            if not _close(item.stated, float(figure["value"])):
                continue
            if not _multiset_match(item.terms, [float(c) for c in components]):
                continue
            out.append(
                FigureMention(
                    figure_id=figure["figure_id"],
                    value=item.stated,
                    unit=figure.get("unit", "MW"),
                    location=item.location,
                    finding_id=item.finding_id,
                    status=item.status,
                    source="arithmetic",
                    excerpt=item.expression,
                    bound_source=None,
                    classification="defined",
                    qualified=False,
                    context_score=2,
                    via="components",
                )
            )
    return out


def _term_identities(
    item: Arithmetic, figures: Sequence[Mapping[str, Any]]
) -> dict[float, set[str]]:
    """What each term of an expression stands for: the key figures that the same
    number, written with its unit in the expression's text, is a mention of ("around
    1,500 MW after the RoCoF trips, then 1,500 + 100 + ..." makes 1,500 Ofgem's
    cumulative loss, not the upper end of its distributed-generation total). Terms the
    text does not identify are absent."""
    if not figures or not item.context:
        return {}
    unit = TextUnit(
        location=item.location,
        finding_id=item.finding_id,
        status=item.status,
        source="arithmetic",
        text=item.context,
    )
    found = [
        m
        for m in figure_mentions([unit], figures, {})
        if m.via == "text" and not isinstance(m.value, list)
    ]
    out: dict[float, set[str]] = {}
    for term in item.terms:
        ids = {m.figure_id for m in found if _close(float(m.value), term)}
        if ids:
            out[term] = ids
    return out


def overlap_traps(
    arithmetic: Sequence[Arithmetic],
    groups: Sequence[Mapping[str, Any]],
    figures: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Sums whose terms overlap: a total added to one of its own components (unless
    the expression reconciles the components to that total), or two estimates of the
    same quantity on different bases (``alternatives``).

    Terms are matched to a group by value, and only when they may stand for the
    group's quantity: a group's ``context_any`` must occur in the expression's text,
    and a term that the text identifies as a key figure outside the group's
    ``figures`` (see :func:`_term_identities`) is not one of the group's values."""
    traps: list[dict[str, Any]] = []
    for item in arithmetic:
        identities = _term_identities(item, figures)
        for group in groups:
            context = group.get("context_any") or ()
            if context and not _any(item.context, context):
                continue
            covered = set(group.get("figures") or ())
            plus = [
                t
                for s, t in zip(item.signs, item.terms, strict=True)
                if s > 0
                and not (covered and t in identities and not identities[t] & covered)
            ]
            totals = [float(x) for x in group.get("totals") or ()]
            components = [float(x) for x in group.get("components") or ()]
            alternatives = [float(x) for x in group.get("alternatives") or ()]
            hit_totals = [t for t in plus if any(_close(t, x) for x in totals)]
            hit_parts = [t for t in plus if any(_close(t, x) for x in components)]
            hit_alts = {
                x for t in plus for x in alternatives if _close(t, x)
            }  # distinct alternatives used
            reconciles = any(_close(item.stated, x) for x in totals) and not hit_totals
            overlap = (hit_totals and hit_parts and not reconciles) or len(
                hit_alts
            ) >= 2
            if overlap:
                traps.append(
                    {
                        "type": "overlap_sum",
                        "group": group["id"],
                        "location": item.location,
                        "finding_id": item.finding_id,
                        "status": item.status,
                        "excerpt": item.expression,
                        "note": group.get("note")
                        or "terms that describe overlapping quantities are summed",
                    }
                )
    return traps


def figure_traps(mentions: Sequence[FigureMention]) -> list[dict[str, Any]]:
    """Mentions given on a wrong basis (misattributed or with contradicting
    definition wording)."""
    return [
        {
            "type": m.classification,
            "figure_id": m.figure_id,
            "location": m.location,
            "finding_id": m.finding_id,
            "status": m.status,
            "bound_source": m.bound_source,
            "excerpt": m.excerpt,
        }
        for m in mentions
        if m.classification in WRONG
    ]


@dataclass
class AccountingResult:
    mentions: list[FigureMention] = field(default_factory=list)
    arithmetic: list[Arithmetic] = field(default_factory=list)
    traps: list[dict[str, Any]] = field(default_factory=list)
    prose_sums: list[Arithmetic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mentions": [m.to_dict() for m in self.mentions],
            "arithmetic": [a.to_dict() for a in self.arithmetic],
            "prose_sums": [
                {k: v for k, v in a.to_dict().items() if k != "within_1_mw"}
                for a in self.prose_sums
            ],
            "traps": self.traps,
        }


def analyse(
    submission: Mapping[str, Any],
    report_texts: Iterable[tuple[str, str]],
    accounting: Mapping[str, Any],
) -> AccountingResult:
    """All figure mentions, arithmetic checks and traps of one submission."""
    units = text_units(submission, report_texts)
    figures = list(accounting.get("figures") or ())
    entities = accounting.get("source_entities") or {}
    mentions = figure_mentions(
        units, figures, entities, accounting.get("binding_options")
    )
    arithmetic = arithmetic_checks(units)
    prose = prose_sums(units)
    mentions += component_mentions(arithmetic, figures)
    traps = figure_traps(mentions)
    traps += overlap_traps(
        arithmetic + prose, accounting.get("overlap_groups") or (), figures
    )
    for item in arithmetic:
        if not item.ok:
            traps.append(
                {
                    "type": "arithmetic",
                    "location": item.location,
                    "finding_id": item.finding_id,
                    "status": item.status,
                    "excerpt": item.expression,
                    "note": f"stated {item.stated:g} MW, computed {item.computed:g} MW "
                    "(derived sums must match their components within 1 MW)",
                }
            )
    return AccountingResult(
        mentions=mentions, arithmetic=arithmetic, traps=traps, prose_sums=prose
    )
