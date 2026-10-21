"""What the judge sees, and nothing else.

One request per *unit*: a task of the key (its ``judge`` / ``auto_assisted_human``
criteria and the factual findings the automated grader assigned to that task), plus an
``UNASSIGNED`` unit for factual findings no task claimed. Every request carries:

* the rubric (``private/system_response/judge_rubric_v1.md``) as the system message;
* the submission (report and findings), blinded: model-identity words are replaced by
  ``[model]``; no run ID, model ID, transcript, path or grader output is included;
* the resolved text of every cited span (:func:`sr_grading.resolve_text`), with notes
  for spans never obtained during the episode or unresolvable;
* the unit's criteria (expectation, expected values, tolerances, accepted
  alternatives, accounting figures, examples without the automated pre-screen and
  without reviewer-only notes) and their keyed visible-evidence spans from the agent
  bundle;
* the findings to classify and the severe-flag definitions.

Never: report passages or quotes from the source PDFs, provenance, the automated
pre-screen, other runs. The shared part (submission and cited spans) comes first so
that providers can reuse the prompt prefix across units.

That is increment A's request (scope ``submission``, the default; its prompts and cache
keys are unchanged). A task that opts in to per-topic scoping (decision 52,
:class:`~.config.JudgeScope` ``mode="topic"``) sends each unit only its own findings in
full, the report text that refers to them, their cited spans and its keyed spans, plus
a compact list of the other findings (:mod:`.scope`), under a short scope note before
the same template.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from environment.incident import grading as mvp
from environment.incident import sr_grading
from environment.incident.catalogue import Catalogue
from environment.incident.locators import (
    RECORD_KINDS,
    LocatorError,
    parse_and_validate,
)

from . import scope as topic_scope
from .config import JudgeConfig, JudgeScope, resolve_scope
from .schema import RESPONSE_SCHEMA, RESPONSE_SCHEMA_ID

__all__ = [
    "BLIND_PATTERNS",
    "PROMPT_VERSION",
    "TOPIC_PROMPT_VERSION",
    "Blinder",
    "Rubric",
    "Span",
    "SpanIndex",
    "Unit",
    "build_units",
    "load_rubric",
    "prompt_template_sha256",
    "prompt_version",
    "render_messages",
    "repair_message",
]

PROMPT_VERSION = "gb2019-sr-judge-prompt/1"
TOPIC_PROMPT_VERSION = "gb2019-judge-prompt-topic/1"
UNASSIGNED = "UNASSIGNED"
BLIND_TOKEN = "[model]"
BLIND_VERSION = "blind-1"
# Model and vendor names (an author naming itself, or run IDs in key examples).
BLIND_PATTERNS = (
    r"\banthropic\b",
    r"\bclaude[\w.\-]*",
    r"\bopus[\w.\-]*",
    r"\bsonnet[\w.\-]*",
    r"\bhaiku[\w.\-]*",
    r"\bopen\s?ai\b",
    r"\bchat\s?gpt\b",
    r"\bgpt[\w.\-]*",
    r"\bgemini[\w.\-]*",
    r"\bgemma[\w.\-]*",
    r"\bllama[\w.\-]*",
    r"\bmistral[\w.\-]*",
    r"\bmixtral[\w.\-]*",
    r"\bgrok[\w.\-]*",
    r"\bdeepseek[\w.\-]*",
    r"\bqwen[\w.\-]*",
)

USER_TEMPLATE = """\
<submission>
{submission}
</submission>

<cited_spans>
{cited_spans}
</cited_spans>

Unit {unit_id}: {unit_title}

<criteria>
{criteria}
</criteria>

<keyed_spans>
{keyed_spans}
</keyed_spans>

<classify>
{classify}
</classify>

Return one JSON object that matches the response schema ({schema_id}).
"criteria": exactly one entry for each of: {criterion_list}.
"assertions": exactly one entry for each of: {finding_list}.
"report_assertions": {report_rule}
"severe_flag_suggestions": only where a definition in <classify> is clearly met; \
otherwise [].
"""
# per-topic scoping (decision 52): this note precedes USER_TEMPLATE
TOPIC_NOTE_TEMPLATE = """\
Scope of this request: unit {unit_id} only. <submission> shows the findings of this \
unit in full ("findings"), the report text that refers to them ("report": parts shown \
"whole" or as an "excerpt", omitted text marked {gap}; "report_parts_not_shown" lists \
the rest) and every other finding only by ID, status and opening words \
("other_findings"). <cited_spans> holds the spans cited by this unit's own findings; \
a citation whose "span" is null is not shown in this request (span numbers can have \
gaps).

"""
SPAN_TEMPLATE = '<span id="{span_id}" {attributes}>\n{text}\n</span>'
NO_SPANS = "(none)"
REPAIR_TEMPLATE = (
    "Your previous reply could not be used: {errors}. Reply again with only the "
    "corrected JSON object matching the response schema, with exactly the entries "
    "requested above."
)
_LINE_PREFIX = "[L{n}] "
_TRUNCATED = "[... truncated: {n} more characters not shown ...]"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def prompt_version(scope: JudgeScope | None = None) -> str:
    """The prompt version of a request scope."""
    return (
        TOPIC_PROMPT_VERSION if scope is not None and scope.scoped else PROMPT_VERSION
    )


def prompt_template_sha256(scope: JudgeScope | None = None) -> str:
    """sha256 of everything in the prompt that is code, not input: templates, response
    schema and blinding patterns (the rubric is hashed separately). A per-topic scope
    adds its note, selection version and settings; without one (increment A) the hash
    is exactly what it always was."""
    material: dict[str, Any] = {
        "prompt_version": PROMPT_VERSION,
        "user_template": USER_TEMPLATE,
        "span_template": SPAN_TEMPLATE,
        "repair_template": REPAIR_TEMPLATE,
        "line_prefix": _LINE_PREFIX,
        "truncated": _TRUNCATED,
        "response_schema_id": RESPONSE_SCHEMA_ID,
        "response_schema": RESPONSE_SCHEMA,
        "blind": [BLIND_VERSION, BLIND_TOKEN, list(BLIND_PATTERNS)],
    }
    if scope is not None and scope.scoped:
        material["topic_scope"] = {
            "prompt_version": TOPIC_PROMPT_VERSION,
            "note_template": TOPIC_NOTE_TEMPLATE,
            "selection_version": topic_scope.SCOPE_VERSION,
            "gap": topic_scope.EXCERPT_GAP,
            "settings": scope.public(),
        }
    return _sha256(_canonical(material))


# -- rubric ------------------------------------------------------------------------------
@dataclass(frozen=True)
class Rubric:
    rubric_id: str
    version: str
    sha256: str
    text: str
    path: str
    # the answer key the rubric is written for (front matter ``key``, first word)
    key_id: str | None = None


def load_rubric(path: Path | str) -> Rubric:
    """The versioned rubric prompt; its front matter names ``rubric_id`` and
    ``rubric_version``."""
    path = Path(path)
    data = path.read_bytes()
    text = data.decode("utf-8")
    meta: dict[str, str] = {}
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                name, value = line.split(":", 1)
                meta[name.strip()] = value.strip()
    if not meta.get("rubric_version") or not meta.get("rubric_id"):
        raise ValueError(f"{path}: front matter must give rubric_id and rubric_version")
    return Rubric(
        rubric_id=meta["rubric_id"],
        version=meta["rubric_version"],
        sha256=hashlib.sha256(data).hexdigest(),
        text=text,
        path=path.name,
        key_id=(meta.get("key") or "").split(" ")[0] or None,
    )


# -- blinding ----------------------------------------------------------------------------
class Blinder:
    """Replaces model and vendor names (and the evaluated model's ID) with
    ``[model]``; counts what it replaced."""

    def __init__(self, extra_terms: Iterable[str | None] = ()) -> None:
        terms: list[str] = []
        for term in extra_terms:
            if not term:
                continue
            for part in {term, term.split("/")[-1]}:
                part = part.strip()
                if len(part) >= 3:
                    terms.append(re.escape(part))
        patterns = sorted(terms, key=len, reverse=True) + list(BLIND_PATTERNS)
        self._rx = re.compile("|".join(f"(?:{p})" for p in patterns), re.I)
        self.count = 0

    def __call__(self, text: str) -> str:
        out, n = self._rx.subn(BLIND_TOKEN, text)
        self.count += n
        return out

    def quiet(self, text: str) -> str:
        """Blind without counting (evidence and rubric text)."""
        return self._rx.sub(BLIND_TOKEN, text)


# -- spans --------------------------------------------------------------------------------
@dataclass
class Span:
    """A span shown to the judge: cited (``C<n>``) or keyed (``K<n>``)."""

    span_id: str
    evidence_id: str
    locator: str
    title: str | None
    kind: str | None
    cited_by: list[str] = field(default_factory=list)
    keyed_roles: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    shown_text: str = ""
    rendered: str = ""
    resolvable: bool = True
    # False when a citation of this span was never obtained during the episode
    # (rendered as a note; such a span cannot earn evidence support)
    obtained: bool | None = None

    def render(self, criteria: Collection[str] = ()) -> str:
        """The span block; a keyed span names the request's ``criteria`` it is keyed
        for, and is ``primary`` if it states the expected fact for any of them."""
        attributes = [
            f'evidence_id="{self.evidence_id}"',
            f'locator="{_attr(self.locator)}"',
        ]
        if self.title:
            attributes.append(f'title="{_attr(self.title)}"')
        if self.cited_by:
            attributes.append(f'cited_by="{" ".join(self.cited_by)}"')
        roles = {c: r for c, r in self.keyed_roles.items() if c in criteria}
        if roles and self.span_id.startswith("K"):
            attributes.append(f'for="{" ".join(roles)}"')
            role = "primary" if "primary" in roles.values() else "context"
            attributes.append(f'role="{role}"')
        if self.notes:
            attributes.append(f'note="{_attr("; ".join(self.notes))}"')
        return SPAN_TEMPLATE.format(
            span_id=self.span_id,
            attributes=" ".join(attributes),
            text=self.rendered or "(no text)",
        )


def _attr(text: str) -> str:
    return text.replace('"', "'").replace("\n", " ")


class SpanIndex:
    """Spans shown in a request, with the catalogue to resolve narrowed locators."""

    def __init__(self, catalogue: Catalogue, blinder: Blinder, max_chars: int) -> None:
        self.catalogue = catalogue
        self.blinder = blinder
        self.max_chars = max_chars
        self.spans: dict[str, Span] = {}
        self._by_location: dict[tuple[str, str], str] = {}

    def by_evidence(
        self, evidence_id: str, allowed: Collection[str] | None = None
    ) -> list[Span]:
        """Resolvable spans of ``evidence_id`` (only those in ``allowed``, the span IDs
        one request showed, when given)."""
        return [
            s
            for s in self.spans.values()
            if s.evidence_id == evidence_id
            and s.resolvable
            and (allowed is None or s.span_id in allowed)
        ]

    def shown_in(self, unit: Unit) -> set[str]:
        """The span IDs a unit's request showed: every cited span (a scoped unit: the
        spans its findings cite) and its keyed spans."""
        if unit.cited_span_ids is not None:
            return set(unit.cited_span_ids) | set(unit.keyed_span_ids)
        return {s for s in self.spans if s.startswith("C")} | set(unit.keyed_span_ids)

    def find(self, evidence_id: str, locator: str) -> Span | None:
        sid = self._by_location.get(
            (evidence_id, _location_key(self, evidence_id, locator))
        )
        return self.spans.get(sid) if sid else None

    def resolve(self, evidence_id: str, locator: str) -> str | None:
        """The (blinded) text of a locator, or ``None`` when it does not resolve."""
        try:
            return self.blinder.quiet(
                sr_grading.resolve_text(self.catalogue, evidence_id, locator)
            )
        except (LocatorError, KeyError, ValueError, StopIteration):
            return None

    def add(
        self,
        prefix: str,
        evidence_id: str,
        locator: str,
        *,
        retrieved: bool | None = None,
    ) -> Span:
        loc_key = _location_key(self, evidence_id, locator)
        existing = self._by_location.get((evidence_id, loc_key))
        if existing is not None:
            return self.spans[existing]
        n = 1 + sum(1 for s in self.spans if s.startswith(prefix))
        span = Span(
            span_id=f"{prefix}{n}",
            evidence_id=evidence_id,
            locator=locator,
            title=None,
            kind=None,
        )
        self._fill(span)
        if retrieved is False and span.resolvable:
            span.notes.insert(0, "not obtained during the episode")
        if retrieved is not None:
            span.obtained = retrieved
        self.spans[span.span_id] = span
        self._by_location[(evidence_id, loc_key)] = span.span_id
        return span

    def _fill(self, span: Span) -> None:
        target = sr_grading._target(self.catalogue, span.evidence_id)
        if target is None:
            span.resolvable = False
            span.notes.append(f"unresolvable: unknown evidence_id {span.evidence_id!r}")
            return
        try:
            loc = parse_and_validate(span.locator, target)
        except LocatorError as exc:
            span.resolvable = False
            span.notes.append(f"unresolvable: {exc}")
            return
        span.kind = loc.kind
        span.locator = loc.normalized
        span.title = self._title(span.evidence_id, loc.kind, str(loc.start))
        if loc.kind == "lines":
            doc = self.catalogue.get(span.evidence_id)
            numbered = [
                (n, self.blinder.quiet(doc.lines[n - 1]))
                for n in range(loc.start, loc.end + 1)
            ]
        else:
            text = self.resolve(span.evidence_id, loc.normalized) or ""
            numbered = [(None, line) for line in text.split("\n")]
        shown: list[str] = []
        rendered: list[str] = []
        used = 0
        total = sum(len(t) + 1 for _, t in numbered)
        for n, line in numbered:
            if used + len(line) > self.max_chars and shown:
                break
            if used + len(line) > self.max_chars:
                line = line[: self.max_chars]
            shown.append(line)
            rendered.append((_LINE_PREFIX.format(n=n) if n is not None else "") + line)
            used += len(line) + 1
        span.shown_text = "\n".join(shown)
        if used < total:
            span.notes.append("truncated")
            rendered.append(_TRUNCATED.format(n=total - used))
        span.rendered = "\n".join(rendered)

    def _title(self, evidence_id: str, kind: str, record_id: str) -> str | None:
        doc = self.catalogue.get(evidence_id)
        sources = self.catalogue.sources
        if kind in RECORD_KINDS and sources is not None:
            if kind == "event":
                for log in sources.asset_logs.values():
                    if any(r.record_id == record_id for r in log.rows):
                        return f"{log.title} (asset log {log.asset_id})"
            elif kind == "entry":
                for room in sources.control_logs.values():
                    if any(r.record_id == record_id for r in room.rows):
                        return f"{room.title} (control log {room.room_id})"
            else:
                for card in sources.witnesses.values():
                    if any(b.response_id == record_id for b in card.blocks):
                        return (
                            f"Witness interview response ({card.role}, "
                            f"{card.organisation})"
                        )
        return doc.title if doc is not None else None


def _location_key(index: SpanIndex, evidence_id: str, locator: str) -> str:
    target = sr_grading._target(index.catalogue, evidence_id)
    if target is not None:
        try:
            return parse_and_validate(locator, target).normalized
        except LocatorError:
            pass
    return "raw:" + locator.strip()


# -- units --------------------------------------------------------------------------------
@dataclass
class Unit:
    unit_id: str
    task: str | None
    title: str
    criterion_ids: list[str]
    criteria: list[dict[str, Any]]
    finding_ids: list[str]
    keyed_span_ids: list[str]
    flags: list[dict[str, Any]]
    report_assertion_limit: int
    messages: list[dict[str, str]] = field(default_factory=list)
    # per-topic scope only (``None`` for increment A's whole-submission requests):
    # the findings shown in full (with why), and the cited spans shown
    scope: str | None = None
    shown_finding_ids: list[str] | None = None
    cited_span_ids: list[str] | None = None
    selection: dict[str, list[str]] | None = None

    @property
    def messages_sha256(self) -> str:
        return _sha256(_canonical(self.messages))

    def scope_record(self) -> dict[str, Any] | None:
        """What a scoped request showed (recorded in the judge output)."""
        if self.scope is None:
            return None
        return {
            "mode": self.scope,
            "findings_shown": list(self.shown_finding_ids or []),
            "cited_spans_shown": len(self.cited_span_ids or []),
            "selection": dict(self.selection or {}),
        }


@dataclass
class Inputs:
    """Everything shared by a submission's units."""

    submission: dict[str, Any]
    submission_json: str
    report_texts: list[tuple[str, str]]
    finding_ids: list[str]
    index: SpanIndex
    blinder: Blinder
    redactions: int
    units: list[Unit]
    scope: JudgeScope | None = None


def _criterion_item(
    crit: Mapping[str, Any],
    key: Mapping[str, Any],
    keyed_ids: list[str],
) -> dict[str, Any]:
    figures = {
        f["figure_id"]: f for f in (key.get("accounting") or {}).get("figures", [])
    }
    basis = crit.get("accounting_basis") or ""
    ids = [p.strip() for p in re.split(r"[;,]", basis) if p.strip()]
    item: dict[str, Any] = {
        "criterion_id": crit["criterion_id"],
        "title": crit["title"],
        "handoff_text": crit.get("handoff_text"),
        "polarity": crit.get("polarity", "positive"),
        "expectation": crit["expectation"],
        "expected": crit.get("expected"),
        "tolerances": crit.get("tolerances"),
        "accepted_alternatives": crit.get("accepted_alternatives") or [],
    }
    if ids:
        item["accounting_figures"] = [
            {
                k: figures[i].get(k)
                for k in (
                    "figure_id",
                    "value",
                    "unit",
                    "quantity",
                    "basis",
                    "stage",
                    "value_status",
                )
                if figures[i].get(k) is not None
            }
            for i in ids
            if i in figures
        ]
    examples = crit.get("examples") or {}
    item["examples"] = {
        side: list(examples.get(side, [])) for side in ("positive", "negative")
    }
    item["keyed_spans"] = keyed_ids
    # reviewer-only key fields (an example's pre-screen value, builder notes naming
    # live runs, MVP criteria or the pre-screen) are never shown
    return {
        k: sr_grading._without_reviewer_notes(v)
        for k, v in item.items()
        if v is not None
    }


def _flag_item(flag: Mapping[str, Any]) -> dict[str, Any]:
    return {
        k: flag[k]
        for k in ("flag_id", "title", "definition", "examples", "non_examples")
        if k in flag
    }


def _submission_view(sub: Mapping[str, Any], index: SpanIndex) -> dict[str, Any]:
    report = sub["report"]
    findings = []
    for f in sub["findings"]:
        item: dict[str, Any] = {
            "finding_id": f["finding_id"],
            "status": f["status"],
            "statement": f["statement"],
        }
        for name in ("quantity", "event_time", "derivation"):
            if f.get(name) is not None:
                item[name] = f[name]
        cites = []
        for c in f.get("citations") or []:
            span = index.find(c["evidence_id"], c["locator"])
            cites.append(
                {
                    "span": span.span_id if span else None,
                    "evidence_id": c["evidence_id"],
                    "locator": c["locator"],
                }
            )
        item["citations"] = cites
        findings.append(item)
    return {
        "executive_summary": report["executive_summary"],
        "sections": [
            {"heading": s["heading"], "body": s["body"]}
            for s in report.get("sections", [])
        ],
        "findings": findings,
    }


def build_units(
    submission: Mapping[str, Any],
    report: Mapping[str, Any],
    key: Mapping[str, Any],
    catalogue: Catalogue,
    config: JudgeConfig,
    rubric: Rubric,
    *,
    blind_terms: Sequence[str | None] = (),
) -> Inputs:
    """Split a submission into judge requests (one per task with criteria to judge or
    findings to classify, plus ``UNASSIGNED``) and render their messages. ``report``
    is the automated grade report of the same submission: it supplies the citation
    checks and which task each factual finding belongs to (never its grades). The
    request scope is :func:`~.config.resolve_scope` of the config and the key."""
    scope = resolve_scope(config, key)
    blinder = Blinder(blind_terms)
    index = SpanIndex(catalogue, blinder, config.max_span_chars)
    retrieved = {
        (c["finding_id"], c["index"]): c.get("retrieved_during_episode")
        for c in report.get("citations") or []
    }
    for f in submission["findings"]:
        for i, c in enumerate(f.get("citations") or []):
            span = index.add(
                "C",
                c["evidence_id"],
                c["locator"],
                retrieved=retrieved.get((f["finding_id"], i)),
            )
            if f["finding_id"] not in span.cited_by:
                span.cited_by.append(f["finding_id"])
            if retrieved.get((f["finding_id"], i)) is False:
                span.obtained = False
                if (
                    span.resolvable
                    and "not obtained during the episode" not in span.notes
                ):
                    span.notes.insert(0, "not obtained during the episode")
    view = _submission_view(submission, index)
    submission_json = blinder(json.dumps(view, indent=1, ensure_ascii=False))
    redactions = blinder.count
    report_texts = [
        (loc, blinder.quiet(text)) for loc, text in mvp._report_texts(submission)
    ]
    cited = [s for s in index.spans.values() if s.span_id.startswith("C")]
    cited_text = "\n\n".join(s.render() for s in cited) or NO_SPANS

    factual = {
        a["assertion_id"]: a["dimension"]
        for a in report["assertion_quality"]["assertions"]
        if a.get("kind") == "finding" and a.get("factual")
    }
    order = [f["finding_id"] for f in submission["findings"]]
    titles = {d["dimension_id"]: d["title"] for d in key["dimensions"]}
    criteria_by_task: dict[str, list[Mapping[str, Any]]] = {}
    for crit in key["criteria"]:
        if crit["assessment_mode"] in config.modes:
            criteria_by_task.setdefault(crit["task"], []).append(crit)
    flags = list(key.get("severe_flags") or [])
    units: list[Unit] = []
    tasks = [d["dimension_id"] for d in key["dimensions"]] + [UNASSIGNED]
    known_tasks = set(tasks[:-1])
    for task in tasks:
        crits = criteria_by_task.get(task, [])
        if task == UNASSIGNED:
            fids = [f for f in order if f in factual and factual[f] not in known_tasks]
        else:
            fids = [f for f in order if factual.get(f) == task]
        if not crits and not fids:
            continue
        keyed_ids_all: list[str] = []
        items = []
        for crit in crits:
            keyed_ids: list[str] = []
            for keyed in crit.get("visible_evidence", []):
                span = index.add("K", keyed["evidence_id"], keyed["locator"])
                role = keyed.get("role", "primary")
                if span.keyed_roles.get(crit["criterion_id"]) != "primary":
                    span.keyed_roles[crit["criterion_id"]] = role
                if span.span_id not in keyed_ids:
                    keyed_ids.append(span.span_id)
                if span.span_id not in keyed_ids_all:
                    keyed_ids_all.append(span.span_id)
            items.append(_criterion_item(crit, key, keyed_ids))
        cids = {c["criterion_id"] for c in crits}
        unit_flags = [
            _flag_item(f)
            for f in flags
            if "all" in f.get("applies_to", []) or cids & set(f.get("applies_to", []))
        ]
        limit = (
            config.max_report_assertions
            if config.report_assertions and task != UNASSIGNED
            else 0
        )
        units.append(
            Unit(
                unit_id=task,
                task=task if task != UNASSIGNED else None,
                title=titles.get(task, "findings not assigned to a task"),
                criterion_ids=[c["criterion_id"] for c in crits],
                criteria=items,
                finding_ids=fids,
                keyed_span_ids=keyed_ids_all,
                flags=unit_flags,
                report_assertion_limit=limit,
            )
        )
    inputs = Inputs(
        submission=dict(submission),
        submission_json=submission_json,
        report_texts=report_texts,
        finding_ids=order,
        index=index,
        blinder=blinder,
        redactions=redactions,
        units=units,
        scope=scope if scope.scoped else None,
    )
    if scope.scoped:
        _scope_units(inputs, view, report, key, rubric, scope)
        return inputs
    for unit in units:
        unit.messages = render_messages(unit, inputs, rubric, cited_text)
    return inputs


def _scope_units(
    inputs: Inputs,
    view: Mapping[str, Any],
    report: Mapping[str, Any],
    key: Mapping[str, Any],
    rubric: Rubric,
    scope: JudgeScope,
) -> None:
    """Per-topic requests (decision 52): each unit shows its own findings, the report
    text that refers to them, their cited spans and its keyed spans, and lists the
    other findings compactly (:mod:`.scope`)."""
    sub = inputs.submission
    sentences = topic_scope.report_sentences(sub, inputs.finding_ids)
    ranking = topic_scope.rank_topics(
        sub, sentences, topic_scope.build_vocabulary(key), scope
    )
    items = {f["finding_id"]: f for f in view["findings"]}
    raw = {f["finding_id"]: f for f in sub["findings"]}
    for unit in inputs.units:
        plan = topic_scope.plan_topic(
            unit.task,
            sub=sub,
            report=report,
            key=key,
            scope=scope,
            ranking=ranking,
            sentences=sentences,
            classify=unit.finding_ids,
        )
        shown = plan.shown
        cited = {
            c["span"]
            for fid in plan.focal
            for c in items[fid]["citations"]
            if c["span"] is not None
        } | {sid for sid in unit.keyed_span_ids if sid.startswith("C")}
        cited_ids = [sid for sid in inputs.index.spans if sid in cited]
        parts, left_out = topic_scope.scoped_report(sub, plan, sentences)
        scoped: dict[str, Any] = {"report": parts}
        if left_out:
            scoped["report_parts_not_shown"] = left_out
        # a finding shown in full without its spans (a cross-cutting topic shows every
        # finding but only its own findings' spans): those citations point nowhere
        scoped["findings"] = [
            items[fid]
            if fid in plan.focal
            else {
                **items[fid],
                "citations": [
                    {**c, "span": c["span"] if c["span"] in cited else None}
                    for c in items[fid]["citations"]
                ],
            }
            for fid in shown
        ]
        scoped["other_findings"] = [
            topic_scope.finding_gist(raw[fid], scope.title_chars)
            for fid in inputs.finding_ids
            if fid not in shown
        ]
        unit.scope = "topic"
        unit.shown_finding_ids = shown
        unit.cited_span_ids = cited_ids
        unit.selection = plan.selection()
        cited_text = (
            "\n\n".join(inputs.index.spans[sid].render() for sid in cited_ids)
            or NO_SPANS
        )
        unit.messages = render_messages(
            unit,
            inputs,
            rubric,
            cited_text,
            submission_json=inputs.blinder.quiet(
                json.dumps(scoped, indent=1, ensure_ascii=False)
            ),
        )


def render_messages(
    unit: Unit,
    inputs: Inputs,
    rubric: Rubric,
    cited_text: str,
    submission_json: str | None = None,
) -> list[dict[str, str]]:
    """A unit's system and user messages; a scoped unit passes its own submission
    view and cited spans, and gets the scope note before the template."""
    blind = inputs.blinder.quiet
    keyed = [
        inputs.index.spans[sid] for sid in unit.keyed_span_ids if sid.startswith("K")
    ]
    keyed_text = "\n\n".join(s.render(unit.criterion_ids) for s in keyed) or NO_SPANS
    reused = [sid for sid in unit.keyed_span_ids if sid.startswith("C")]
    if reused:
        keyed_text += (
            "\n\n(Keyed spans also cited by the submission, shown in <cited_spans>: "
            + ", ".join(reused)
            + ")"
        )
    classify = {
        "findings_to_classify": unit.finding_ids,
        "report_assertions_allowed": unit.report_assertion_limit,
        "severe_flags": unit.flags,
    }
    report_rule = (
        f"at most {unit.report_assertion_limit} factual claims from the report prose "
        "on this unit's topic that restate no finding (text copied word for word), "
        "or []."
        if unit.report_assertion_limit
        else "[] (not requested in this unit)."
    )
    user = USER_TEMPLATE.format(
        submission=submission_json
        if submission_json is not None
        else inputs.submission_json,
        cited_spans=cited_text,
        unit_id=unit.unit_id,
        unit_title=unit.title,
        criteria=blind(json.dumps(unit.criteria, indent=1, ensure_ascii=False)),
        keyed_spans=keyed_text,
        classify=blind(json.dumps(classify, indent=1, ensure_ascii=False)),
        schema_id=RESPONSE_SCHEMA_ID,
        criterion_list=", ".join(unit.criterion_ids) or "(none: return [])",
        finding_list=", ".join(unit.finding_ids) or "(none: return [])",
        report_rule=report_rule,
    )
    if unit.scope == "topic":
        user = (
            TOPIC_NOTE_TEMPLATE.format(
                unit_id=unit.unit_id, gap=topic_scope.EXCERPT_GAP
            )
            + user
        )
    return [
        {"role": "system", "content": blind(rubric.text)},
        {"role": "user", "content": user},
    ]


def repair_message(previous: str, errors: Sequence[str]) -> list[dict[str, str]]:
    shown = "; ".join(errors[:12]) + (
        f"; and {len(errors) - 12} more" if len(errors) > 12 else ""
    )
    return [
        {"role": "assistant", "content": previous[:20_000]},
        {"role": "user", "content": REPAIR_TEMPLATE.format(errors=shown)},
    ]
