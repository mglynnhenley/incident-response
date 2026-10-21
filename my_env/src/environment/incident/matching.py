"""Versioned, deterministic free-text matching.

Two matchers, each identified by a version string that tools report with every result
(a change to any rule below needs a new version, so recorded traces stay explainable):

``doc-tokens-2`` (``request_document(party=..., description=...)``)
    The party is compared with each listed document's owner (plus optional manifest
    ``party_aliases``), the description with its ID, title and optional manifest
    ``keywords`` (not its category: a category word such as "records" says nothing about
    which document is meant). A document is a candidate when at least one party token
    matches AND its ID/title/keywords cover at least half of the distinct description
    tokens (rounded up). Candidates are ranked by (description tokens matched, party
    tokens matched); a unique best candidate is selected, a tie at the top is ambiguous
    (the tied candidates are returned, none is selected), and no candidate means no
    match. (``doc-tokens-1`` also matched the category and selected on a single
    matching description word.)

``witness-topics-2`` (``interview_witness``)
    A question whose tokens are exactly one block's topic selects that block. Otherwise
    a block can answer only if the question covers ALL tokens of at least one of its
    topics; such blocks are ranked by (topics fully covered, distinct question tokens
    found in the block's topics) and the unique best one answers, while a tie is
    ambiguous (the tied blocks' topics are offered as choices). A question that only
    shares some words with topics is never answered: it is ambiguous, and only the
    blocks that share the most question tokens are offered as topic choices. Choices
    are capped at :data:`MAX_TOPIC_CHOICES` blocks (lowest block index first); the
    number of further tied blocks is reported, never their topics. A question with no
    token in common with any topic gets the witness's fixed "not known" response. (A
    fact block is never supplied for an unrelated question just because one word
    overlaps.) ``witness-topics-1`` offered every block the question touched, without a
    cap.

Normalisation (both matchers): Unicode NFKC, case folding, accents and a few
letter variants folded to ASCII (``Ø`` -> ``o``), dashes and quotes unified, then
tokens are maximal runs of letters and digits. Stop words are dropped and a light,
fixed suffix rule maps plurals and ``-ed``/``-ing`` forms to a common stem. Two tokens
match when they are equal or when the shorter, at least five characters long, begins
the longer ("restor" matches "restoration"). Question and description text are only
ever tokenised: they are never executed, used as paths or echoed into evidence.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

__all__ = [
    "DOC_MATCHER_VERSION",
    "MAX_TOPIC_CHOICES",
    "TOPIC_MATCHER_VERSION",
    "DocumentCandidate",
    "DocumentMatch",
    "TopicMatch",
    "match_documents",
    "match_topics",
    "min_description_coverage",
    "normalise_key",
    "normalise_text",
    "tokens",
    "tokens_match",
]

DOC_MATCHER_VERSION = "doc-tokens-2"
TOPIC_MATCHER_VERSION = "witness-topics-2"
#: Most topic choices an ambiguous question is shown (further tied blocks are counted).
MAX_TOPIC_CHOICES = 3

_LETTER_FOLDS = str.maketrans(
    {
        "ø": "o",
        "æ": "ae",
        "œ": "oe",
        "ð": "d",
        "þ": "th",
        "ł": "l",
        "đ": "d",
        "ı": "i",
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "―": "-",
        "−": "-",
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "­": None,
    }
)
_TOKEN_RE = re.compile(r"[^\W_]+")
_SPACE_RE = re.compile(r"\s+")

STOPWORDS = frozenset(
    """
    a about above after again against all also am an and any are as at be because been
    before being below between both but by can could did do does doing down during each
    few for from further had has have having he her here hers him his how i if in into
    is it its itself just me more most my no nor not now of off on once only or other
    our ours out over own please same she should so some such than that the their them
    then there these they this those through to too under until up very was we were
    what when where which while who whom why will with would you your yours
    tell describe explain give know let us
    """.split()
)


def normalise_text(text: str) -> str:
    """NFKC, case-folded, ASCII-folded text with unified dashes and quotes."""
    folded = unicodedata.normalize("NFKC", text).casefold().translate(_LETTER_FOLDS)
    decomposed = unicodedata.normalize("NFKD", folded)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", stripped)


def normalise_key(text: str) -> str:
    """Normalised text with collapsed whitespace, for exact identifier comparison."""
    return _SPACE_RE.sub(" ", normalise_text(text)).strip()


def _stem(token: str) -> str:
    """Fixed suffix rules: plural, then ``-ing``/``-ed``, then a final ``e``."""
    if len(token) > 4 and token.endswith("ies"):
        token = token[:-3] + "y"
    elif (
        len(token) > 3
        and token.endswith("s")
        and not token.endswith(("ss", "us", "is"))
    ):
        token = token[:-1]
    for suffix in ("ing", "ed"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            stem = token[: -len(suffix)]
            if not (suffix == "ed" and stem.endswith("e")):
                if len(stem) > 3 and stem[-1] == stem[-2] and stem[-1] not in "aeiouls":
                    stem = stem[:-1]
                token = stem
            break
    if len(token) > 4 and token.endswith("e") and not token.endswith("ee"):
        token = token[:-1]
    return token


def tokens(text: str) -> tuple[str, ...]:
    """Content tokens of ``text`` in order (stop words removed, stems applied)."""
    words = _TOKEN_RE.findall(normalise_text(text))
    return tuple(_stem(w) for w in words if w not in STOPWORDS)


_MIN_PREFIX = 5


def tokens_match(a: str, b: str) -> bool:
    """Equal, or the shorter (at least five characters) is a prefix of the longer."""
    if a == b:
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= _MIN_PREFIX and long_.startswith(short)


def _matched(wanted: Iterable[str], available: Iterable[str]) -> set[str]:
    """The tokens of ``wanted`` that match at least one token of ``available``."""
    pool = tuple(set(available))
    return {w for w in wanted if any(tokens_match(w, a) for a in pool)}


# -- documents ---------------------------------------------------------------------
@dataclass(frozen=True)
class DocumentCandidate:
    doc_id: str
    description_score: int
    party_score: int

    @property
    def score(self) -> tuple[int, int]:
        return (self.description_score, self.party_score)


@dataclass(frozen=True)
class DocumentMatch:
    """``selected`` is a doc ID or ``None``; ``candidates`` are the tied best ones
    when the request is ambiguous (empty when nothing matched)."""

    selected: str | None
    candidates: tuple[DocumentCandidate, ...]
    party_tokens: tuple[str, ...]
    description_tokens: tuple[str, ...]
    version: str = DOC_MATCHER_VERSION

    @property
    def ambiguous(self) -> bool:
        return self.selected is None and len(self.candidates) > 1


def min_description_coverage(description_tokens: Sequence[str]) -> int:
    """Description tokens a document must cover to be a candidate: half, rounded up."""
    return max(1, (len(set(description_tokens)) + 1) // 2)


def match_documents(
    party: str,
    description: str,
    documents: Iterable[tuple[str, str, str]],
) -> DocumentMatch:
    """Match ``(party, description)`` against ``(doc_id, party_text, description_text)``.

    ``description_text`` is the document's ID, title and keywords (never its category).
    """
    party_tokens = tuple(dict.fromkeys(tokens(party)))
    description_tokens = tuple(dict.fromkeys(tokens(description)))
    wanted_party = set(party_tokens)
    wanted_description = set(description_tokens)
    needed = min_description_coverage(description_tokens)
    candidates: list[DocumentCandidate] = []
    for doc_id, party_text, description_text in documents:
        party_score = len(_matched(wanted_party, tokens(party_text)))
        description_score = len(_matched(wanted_description, tokens(description_text)))
        if party_score >= 1 and description_tokens and description_score >= needed:
            candidates.append(DocumentCandidate(doc_id, description_score, party_score))
    if not candidates:
        return DocumentMatch(None, (), party_tokens, description_tokens)
    best = max(c.score for c in candidates)
    top = tuple(
        sorted((c for c in candidates if c.score == best), key=lambda c: c.doc_id)
    )
    if len(top) == 1:
        return DocumentMatch(top[0].doc_id, top, party_tokens, description_tokens)
    return DocumentMatch(None, top, party_tokens, description_tokens)


# -- witness topics -------------------------------------------------------------------
@dataclass(frozen=True)
class TopicMatch:
    """``kind`` is ``"match"`` (one block index in ``blocks``), ``"ambiguous"`` (the
    block indices offered as topic choices, at most :data:`MAX_TOPIC_CHOICES`) or
    ``"none"``. ``withheld`` counts further tied blocks that were not offered."""

    kind: str
    blocks: tuple[int, ...]
    question_tokens: tuple[str, ...]
    version: str = TOPIC_MATCHER_VERSION
    withheld: int = 0


def _ambiguous(tied: Sequence[int], question_tokens: tuple[str, ...]) -> TopicMatch:
    ordered = tuple(sorted(tied))
    return TopicMatch(
        "ambiguous",
        ordered[:MAX_TOPIC_CHOICES],
        question_tokens,
        withheld=max(0, len(ordered) - MAX_TOPIC_CHOICES),
    )


def match_topics(question: str, blocks: Sequence[Sequence[str]]) -> TopicMatch:
    """Match ``question`` against each block's topic list (see the module docstring)."""
    question_tokens = tokens(question)
    asked = set(question_tokens)
    if not asked:
        return TopicMatch("none", (), question_tokens)

    exact = tuple(
        index
        for index, topics in enumerate(blocks)
        if any(tokens(topic) == question_tokens for topic in topics)
    )
    if len(exact) == 1:
        return TopicMatch("match", exact, question_tokens)
    if len(exact) > 1:
        return _ambiguous(exact, question_tokens)

    scores: list[tuple[int, int]] = []
    for topics in blocks:
        topic_sets = [set(tokens(topic)) for topic in topics]
        full = sum(1 for t in topic_sets if t and len(_matched(t, asked)) == len(t))
        covered = len(_matched(asked, set().union(*topic_sets))) if topic_sets else 0
        scores.append((full, covered))
    best = max(scores, default=(0, 0))
    if best[0] >= 1:
        top = tuple(index for index, score in enumerate(scores) if score == best)
        if len(top) == 1:
            return TopicMatch("match", top, question_tokens)
        return _ambiguous(top, question_tokens)
    if best[1] >= 1:
        # Only the blocks sharing the most question tokens are offered, never every
        # block the question touches (the choices would enumerate the card).
        top = tuple(index for index, score in enumerate(scores) if score[1] == best[1])
        return _ambiguous(top, question_tokens)
    return TopicMatch("none", (), question_tokens)
