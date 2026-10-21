"""Per-topic scoping of judge requests (decision 52).

Increment A's requests each carried the whole submission and every cited span, about
58,000 tokens re-sent for each of 13 topics (decision 37). A task that opts in
(:class:`~.config.JudgeScope` with ``mode="topic"``, in the judge config or the key's
``judge.scope``) sends each topic only:

* **its findings, in full** (status, statement, quantity, event time, derivation,
  citations). A finding belongs to a topic when any of these holds:

  - ``routed``: the automated grade assigns it to the topic (the findings the unit
    classifies are always among these);
  - ``matched``: the automated grade matched or considered it for one of the topic's
    criteria (``dimensions_matched``);
  - ``keyed_citation``: it cites evidence that overlaps a keyed span of one of the
    topic's criteria;
  - ``report_reference``: report text shown whole for the topic (an executive summary
    or a section that the topic's criteria read) refers to it;
  - ``vocabulary``: the topic is among its ``lexical_tasks_per_finding`` best topics
    by the key's own wording (criterion titles, expectations, accepted alternatives,
    expected values and example statements; inverse topic frequency weights, at least
    ``lexical_min_score``). This catches content the automated grade did not match;
  - ``error_screen`` and ``sentence_vocabulary`` (``error_screen`` setting, on by
    default): for a topic with judge criteria that an error stated anywhere bounds (a
    contradiction rule, or a severe flag that zeroes it), every finding with a sentence
    that meets one of those rules' patterns or a trigger of those flags (their
    exclusions ignored: the judge decides), or a sentence whose own best topics by
    vocabulary include the topic. A finding about another topic can carry one
    disqualifying sentence ("late ESO communications contributed to the demand
    disconnection" inside a response finding); its whole-finding vocabulary would not
    rank this topic, and recall of credited findings never measured it;

* **the report text that refers to them**: every sentence that refers to one of the
  topic's findings, sentences that refer to no finding but share the topic's
  vocabulary (as above), the whole executive summary when a criterion of the topic
  reads it (``summary_text``/``summary_words`` elements), and whole sections whose
  heading a criterion reads (``section_text``). Omitted text is marked ``[…]``, and the
  headings of sections not shown are listed;
* **their cited spans and the topic's keyed spans** (span IDs stay those of the whole
  submission, so ``C`` numbers can have gaps);
* **a compact list of the other findings** (ID, status and the opening words of the
  statement) for cross-reference. The rubric tells the judge not to credit a finding
  it saw only in that list; if it names one anyway, the runner records it and withholds
  evidence support that rests only on such findings.

Topics in ``all_findings_tasks`` are cross-cutting (an uncertainty register reads every
finding): their requests show every finding and the whole report, but still only the
cited spans of their own findings (the other findings' citations show ``"span": null``).

Selection uses the automated grade's routing and the key, never its values: the judge
still sees no pre-screen result. Everything here is deterministic, so a scoped request
and its cache key are reproducible.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from environment.incident import grading as mvp
from environment.incident import sr_grading
from environment.incident.submission import extract_references

from .config import JudgeScope

__all__ = [
    "EXCERPT_GAP",
    "REASONS",
    "SCOPE_VERSION",
    "Ranking",
    "ReportSentence",
    "TopicPlan",
    "Vocabulary",
    "build_vocabulary",
    "error_screen",
    "finding_gist",
    "plan_topic",
    "rank_topics",
    "report_sentences",
    "scoped_report",
    "screen_hits",
    "tokens",
]

SCOPE_VERSION = "topic-scope/2"
EXCERPT_GAP = "[…]"
SUMMARY_ELEMENTS = ("summary_text", "summary_words")
SECTION_ELEMENTS = ("section_text",)
SUMMARY_PART = -1

# why a finding is shown in full (recorded per unit in the judge output, never shown
# to the judge)
REASONS = (
    "routed",
    "matched",
    "keyed_citation",
    "report_reference",
    "vocabulary",
    "error_screen",
    "sentence_vocabulary",
    "all_findings",
)

_STOP = frozenset(
    """about above after again against all also although among and any are around
    because been before being below between both but can could did does done down
    during each either else even ever every few for from further had has have having
    her here hers him his how however into its itself just least less many may might
    more most much must neither nor not now off once one only onto other others our
    out over own per rather same she should since some such than that the their them
    then there these they this those though three through thus too two under until
    upon very via was were what when where whether which while who whom whose why will
    with within without would yet you your""".split()
)
_WORD = re.compile(r"[a-z][a-z0-9]*|\d{1,2}:\d{2}|\d[\d,]*(?:\.\d+)?")


def tokens(text: str) -> set[str]:
    """Content tokens: words of at least 3 characters (not stop words) cut to their
    first 7, clock times (``hh:mm``), and numbers with a decimal point or at least 3
    digits (thousands separators removed)."""
    folded = unicodedata.normalize("NFKC", text).casefold().replace("ø", "o")
    out: set[str] = set()
    for word in _WORD.findall(folded):
        if word[0].isdigit():
            if ":" in word:
                out.add(word)
                continue
            number = word.replace(",", "")
            if "." in number or len(number) >= 3:
                out.add(number)
        elif len(word) >= 3 and word not in _STOP:
            out.add(word[:7])
    return out


def _strings(obj: Any) -> Iterable[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, Mapping):
        for value in obj.values():
            yield from _strings(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            yield from _strings(value)


@dataclass
class Vocabulary:
    """Each topic's tokens from the key and their inverse topic frequency."""

    tasks: dict[str, frozenset[str]]
    idf: dict[str, float]

    def scores(self, text: str) -> dict[str, float]:
        found = tokens(text)
        return {
            task: sum(self.idf[t] for t in found & vocab)
            for task, vocab in self.tasks.items()
        }

    def best(self, text: str, count: int, min_score: float) -> list[str]:
        """The ``count`` topics with the highest scores of at least ``min_score``
        (ties broken by topic ID)."""
        if count <= 0:
            return []
        ranked = sorted(
            ((s, t) for t, s in self.scores(text).items() if s >= min_score),
            key=lambda st: (-st[0], st[1]),
        )
        return [t for _, t in ranked[:count]]


def build_vocabulary(key: Mapping[str, Any]) -> Vocabulary:
    """Topic vocabularies from the judge-visible text of each topic's criteria
    (reviewer-only notes excluded)."""
    texts: dict[str, list[str]] = {d["dimension_id"]: [] for d in key["dimensions"]}
    for crit in key["criteria"]:
        visible = sr_grading._without_reviewer_notes(
            {
                name: crit.get(name)
                for name in (
                    "title",
                    "handoff_text",
                    "expectation",
                    "expected",
                    "accepted_alternatives",
                    "examples",
                )
            }
        )
        texts.setdefault(crit["task"], []).extend(_strings(visible))
    vocab = {task: frozenset(tokens(" ".join(parts))) for task, parts in texts.items()}
    df: dict[str, int] = {}
    for words in vocab.values():
        for word in words:
            df[word] = df.get(word, 0) + 1
    n = max(len(vocab), 1)
    return Vocabulary(
        tasks=vocab, idf={word: math.log(n / count) for word, count in df.items()}
    )


# -- report sentences ----------------------------------------------------------------------
@dataclass(frozen=True)
class ReportSentence:
    part: int  # SUMMARY_PART for the executive summary, else the section index
    line: int
    index: int  # position within the part
    text: str
    refs: tuple[str, ...]


def report_sentences(
    sub: Mapping[str, Any], known: Collection[str]
) -> dict[int, list[ReportSentence]]:
    """The report's sentences by part (lines are never joined), each with the known
    finding IDs it refers to (``[F01]``, ``[F01, F02]``)."""
    report = sub["report"]
    parts = [(SUMMARY_PART, report["executive_summary"])] + [
        (i, s["body"]) for i, s in enumerate(report.get("sections") or [])
    ]
    known = set(known)
    out: dict[int, list[ReportSentence]] = {}
    for part, text in parts:
        items: list[ReportSentence] = []
        for line_no, line in enumerate(text.split("\n")):
            for sentence in mvp._sentences(line):
                refs = tuple(
                    dict.fromkeys(r for r in extract_references(sentence) if r in known)
                )
                items.append(ReportSentence(part, line_no, len(items), sentence, refs))
        out[part] = items
    return out


def _excerpt(items: Sequence[ReportSentence], chosen: Collection[int]) -> str:
    """The chosen sentences in order: adjacent sentences joined as written (a space,
    or a line break between lines), gaps marked ``[…]``."""
    text = ""
    previous: ReportSentence | None = None
    for item in items:
        if item.index not in chosen:
            continue
        if previous is None:
            text = (EXCERPT_GAP + " " if item.index > 0 else "") + item.text
        elif item.index == previous.index + 1:
            text += ("\n" if item.line != previous.line else " ") + item.text
        else:
            text += " " + EXCERPT_GAP + " " + item.text
        previous = item
    if previous is not None and previous.index < len(items) - 1:
        text += " " + EXCERPT_GAP
    return text


@dataclass
class Ranking:
    """The best topics of every finding and of every report sentence that refers to
    no finding, by vocabulary (computed once per submission); ``finding_sentences``:
    for each finding, every topic that is among the best of one of its statement's
    sentences."""

    findings: dict[str, list[str]]
    sentences: dict[tuple[int, int], list[str]]
    finding_sentences: dict[str, set[str]] = field(default_factory=dict)


def rank_topics(
    sub: Mapping[str, Any],
    sentences: Mapping[int, Sequence[ReportSentence]],
    vocabulary: Vocabulary,
    scope: JudgeScope,
) -> Ranking:
    count, floor = scope.lexical_tasks_per_finding, scope.lexical_min_score
    findings = {}
    for f in sub["findings"]:
        text = " ".join(
            (
                str(f["statement"]),
                str(f.get("derivation") or ""),
                str((f.get("quantity") or {}).get("basis") or ""),
            )
        )
        findings[f["finding_id"]] = vocabulary.best(text, count, floor)
    unreferenced = {
        (part, item.index): vocabulary.best(item.text, count, floor)
        for part, items in sentences.items()
        for item in items
        if not item.refs
    }
    by_sentence = {
        f["finding_id"]: {
            task
            for sentence in mvp._sentences(str(f["statement"]))
            for task in vocabulary.best(sentence, count, floor)
        }
        for f in sub["findings"]
    }
    return Ranking(
        findings=findings, sentences=unreferenced, finding_sentences=by_sentence
    )


# Causal or counterfactual wording: with a contradiction rule's subject (its first
# group), a sentence that may state the error in other words than the rule ("the
# communications breakdown ... made the demand disconnection as large as it was").
CAUSAL_CUE = (
    r"\b(?:caus\w*|led to|lead to|leads to|result\w*|made|because|due to|contribut\w*"
    r"|would have|could have|prolong\w*|worsen\w*|exacerbat\w*|aggravat\w*|triggered"
    r"|responsible)\b",
)


def error_screen(
    crits: Iterable[Mapping[str, Any]], key: Mapping[str, Any]
) -> list[tuple[str, list[list[str]]]]:
    """The sentence patterns of the errors that bound the topic's judge criteria:
    every contradiction rule's ``all`` groups, its subject (first group) with causal
    wording (``CAUSAL_CUE``) when the rule has several groups, and every trigger of a
    severe flag the criterion is zeroed by (``severe_flags_zero``), as (name, groups);
    exclusions (``none``, ``unless_any``) are ignored, so the judge sees borderline
    sentences too."""
    flags = {f["flag_id"]: f for f in key.get("severe_flags") or []}
    screens: list[tuple[str, list[list[str]]]] = []
    for crit in crits:
        if crit.get("assessment_mode") != "judge":
            continue
        auto = crit.get("auto") or {}
        for rule in auto.get("contradictions") or []:
            name = f"{crit['criterion_id']}:{rule['id']}"
            screens.append((name, rule["all"]))
            if len(rule["all"]) > 1:
                screens.append((name + ":subject", [rule["all"][0], list(CAUSAL_CUE)]))
        for flag_id in auto.get("severe_flags_zero") or []:
            heuristic = (flags.get(flag_id) or {}).get("heuristic") or {}
            if heuristic.get("trigger_any"):
                screens.append((flag_id, [list(heuristic["trigger_any"])]))
    return screens


def screen_hits(
    statement: str, screens: Sequence[tuple[str, list[list[str]]]]
) -> list[str]:
    """The screens one of the statement's sentences meets."""
    sentences = [mvp.normalise(s) for s in mvp._sentences(statement)]
    return [
        name
        for name, groups in screens
        if any(mvp._all_groups(text, groups) for text in sentences)
    ]


# -- what one topic shows --------------------------------------------------------------
@dataclass
class TopicPlan:
    """The findings and report text one scoped request shows.

    ``focal``: the topic's own findings (with why); their cited spans are shown.
    ``shown``: the findings shown in full: the focal ones, or every finding for a
    cross-cutting topic (``all_findings``), whose other findings come without spans."""

    task: str | None
    order: list[str] = field(default_factory=list)
    focal: dict[str, list[str]] = field(default_factory=dict)  # finding -> reasons
    full_parts: set[int] = field(default_factory=set)
    sentences: dict[int, set[int]] = field(default_factory=dict)  # part -> indexes
    all_findings: bool = False

    def add(self, fid: str, reason: str) -> None:
        reasons = self.focal.setdefault(fid, [])
        if reason not in reasons:
            reasons.append(reason)

    @property
    def shown(self) -> list[str]:
        if self.all_findings:
            return list(self.order)
        return [fid for fid in self.order if fid in self.focal]

    def selection(self) -> dict[str, list[str]]:
        """Why each finding is shown in full."""
        return {
            fid: list(self.focal.get(fid) or ["all_findings"]) for fid in self.shown
        }


def _element_types(crits: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        el
        for crit in crits
        for el in ((crit.get("auto") or {}).get("elements") or [])
        if isinstance(el, Mapping)
    ]


def _full_parts(sub: Mapping[str, Any], crits: Sequence[Mapping[str, Any]]) -> set[int]:
    """Report parts the topic's criteria read whole: the executive summary
    (``summary_*`` elements) and sections whose heading matches a ``section_text``
    element."""
    parts: set[int] = set()
    elements = _element_types(crits)
    if any(el.get("type") in SUMMARY_ELEMENTS for el in elements):
        parts.add(SUMMARY_PART)
    patterns = [
        re.compile(p, re.I)
        for el in elements
        if el.get("type") in SECTION_ELEMENTS
        for p in el.get("heading_any") or []
    ]
    for i, section in enumerate(sub["report"].get("sections") or []):
        if any(p.search(section["heading"]) for p in patterns):
            parts.add(i)
    return parts


def plan_topic(
    task: str | None,
    *,
    sub: Mapping[str, Any],
    report: Mapping[str, Any],
    key: Mapping[str, Any],
    scope: JudgeScope,
    ranking: Ranking,
    sentences: Mapping[int, Sequence[ReportSentence]],
    classify: Sequence[str],
) -> TopicPlan:
    """Which findings and report text the request for ``task`` (``None``: the
    unassigned findings) shows."""
    order = [f["finding_id"] for f in sub["findings"]]
    plan = TopicPlan(task=task, order=order)
    for fid in classify:
        plan.add(fid, "routed")
    if task is None:
        chosen = {
            part: {s.index for s in items if set(s.refs) & set(plan.focal)}
            for part, items in sentences.items()
        }
        plan.sentences = {p: c for p, c in chosen.items() if c}
        return plan

    if task in scope.all_findings_tasks:
        plan.all_findings = True
    task_crits = [c for c in key["criteria"] if c["task"] == task]
    crit_ids = {c["criterion_id"] for c in task_crits}
    for a in report["assertion_quality"]["assertions"]:
        if a.get("kind") != "finding":
            continue
        if a.get("dimension") == task:
            plan.add(a["assertion_id"], "routed")
        elif task in (a.get("dimensions_matched") or []):
            plan.add(a["assertion_id"], "matched")
    for check in report.get("citations") or []:
        if crit_ids & set(check.get("overlaps_keyed_evidence_of") or []):
            plan.add(check["finding_id"], "keyed_citation")
    plan.full_parts = _full_parts(sub, task_crits)
    for part in plan.full_parts:
        for item in sentences.get(part, []):
            for fid in item.refs:
                plan.add(fid, "report_reference")
    for fid in order:
        if task in ranking.findings.get(fid, []):
            plan.add(fid, "vocabulary")
    screens = error_screen(task_crits, key) if scope.error_screen else []
    if screens:
        for f in sub["findings"]:
            fid = f["finding_id"]
            if screen_hits(str(f["statement"]), screens):
                plan.add(fid, "error_screen")
            elif task in ranking.finding_sentences.get(fid, ()):
                plan.add(fid, "sentence_vocabulary")
    if plan.all_findings:
        plan.full_parts = set(sentences)
    # keep the submission's order
    plan.focal = {fid: plan.focal[fid] for fid in order if fid in plan.focal}

    focal = set(plan.focal)
    for part, items in sentences.items():
        if part in plan.full_parts:
            plan.sentences[part] = {s.index for s in items}
            continue
        chosen = {
            s.index
            for s in items
            if set(s.refs) & focal
            or (not s.refs and task in ranking.sentences.get((part, s.index), []))
        }
        if chosen:
            plan.sentences[part] = chosen
    return plan


def finding_gist(finding: Mapping[str, Any], chars: int) -> str:
    """``F07 (reported): The opening words of the statement …`` (cut at a word)."""
    statement = " ".join(str(finding["statement"]).split())
    if len(statement) > chars:
        cut = statement[:chars].rsplit(" ", 1)[0].rstrip(",;:")
        statement = (cut or statement[:chars]) + " …"
    return f"{finding['finding_id']} ({finding['status']}): {statement}"


def scoped_report(
    sub: Mapping[str, Any],
    plan: TopicPlan,
    sentences: Mapping[int, Sequence[ReportSentence]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """The report parts a scoped request shows (whole or excerpt) and the headings of
    the sections it leaves out."""
    report = sub["report"]
    sections = report.get("sections") or []
    shown: list[dict[str, Any]] = []
    left_out: list[str] = []
    for part in [SUMMARY_PART, *range(len(sections))]:
        items = sentences.get(part, [])
        chosen = plan.sentences.get(part, set())
        whole = part in plan.full_parts or bool(items and len(chosen) == len(items))
        if not chosen and not whole:
            left_out.append(
                "(executive summary)"
                if part == SUMMARY_PART
                else sections[part]["heading"]
            )
            continue
        entry: dict[str, Any] = (
            {"part": "executive_summary"}
            if part == SUMMARY_PART
            else {"part": "section", "heading": sections[part]["heading"]}
        )
        if whole:
            entry["shown"] = "whole"
            entry["text"] = (
                report["executive_summary"]
                if part == SUMMARY_PART
                else sections[part]["body"]
            )
        else:
            entry["shown"] = "excerpt"
            entry["text"] = _excerpt(items, chosen)
        shown.append(entry)
    return shown, left_out
