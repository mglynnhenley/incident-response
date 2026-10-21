"""Grading of a frozen submission for the system-response task (gb-2019-system-response).

The task's judge (``tasks/gb_2019_system_response/judge.py``) calls
:func:`grade_episode` (``episode_dir``, ``transcript_summary``). The answer key is
``private/system_response/answer_key.json`` (key schema ``gb2019-sr-answer-key/1``):
criteria for the handoff topics T01–T09, T12, T16 and T17, each with a ``task``, an
``assessment_mode``, report passages, visible-evidence locators, tolerances,
accounting-basis figures and positive/negative examples. Compound numeric criteria are
split into fields (``T02.02a``, ``T02.02b``) with equal ``subweight`` only as a
reporting convenience: no task total, overall score, threshold or ranking is computed.

The MVP grading machinery (:mod:`.grading`) is reused: the text/value/time elements
with entity binding, statement fallback, relative-time offsets and mechanism hedging;
the frequency landmark and duration checks against the frozen R01 series ("never an
automatic 0 when a candidate value exists"); contradiction rules; severe-flag
heuristics; status-labelling flags. This module adds:

* **Citation validation for manifest-v2 evidence**: record locators ``event:<id>``,
  ``entry:<id>``, ``response:<id>`` resolve through the catalogue's citation targets;
  *retrieved during the episode* considers every retrieval route in the ledger
  (``request_document``, ``request_data_return`` for data-return-only documents such as
  S05 and S06, ``query_frequency`` for R01, rows returned by ``query_asset_log`` and
  ``query_control_log``, responses returned by ``interview_witness``);
  :func:`resolve_text` gives the text of any locator; :func:`cited_spans` and
  :func:`criterion_rubric` give the judge track its inputs (the cited spans, the
  criterion's expectation, examples and keyed spans).
* **Accounting-basis checks** (:mod:`.sr_accounting`): every key figure named in the
  submission is classified by the basis it is given on (attributed, defined,
  unattributed, misattributed, mismatched); ``figure`` elements credit a figure only on
  its own basis, ``accounting_caps`` cap a criterion when a figure is given on another
  basis or overlapping estimates are summed, and derived sums are checked within 1 MW.
* **Flags and readers refined on real submissions** (review round 2): the labelling
  flag counts only the agent's own hedges (not attributed clauses, quoted spans,
  measurement caveats or reports of someone's hypothesis); the inferential-language
  flag spares "suggests / indicates / implies" whose subject is a source or record; a
  ``time`` element with ``read_statement_times`` also reads statement times when the
  finding's ``event_time`` is another boundary of the window (T05.01b).
* **Layered values**: each criterion keeps an automated layer, an optional judge layer
  (:func:`merge_judge_proposals`) and an optional human layer (grading decisions). The
  value shown is, in order: human (also "accept_judge" sign-offs), a confirmed severe
  flag (content 0), a decided automated value (``auto_numeric`` only), a judge proposal
  (``judge`` mode only, after accounting-basis caps and suspected severe flags), else
  ``pending``. Sentence-level contradiction rules of a ``judge`` criterion are a
  pre-screen flag for the reviewer (``flags.prescreen_contradictions``), not a cap on
  the judge's value; ``accept_judge`` cannot sign off a capped proposal (the reviewer
  gives the value). Sources are ``auto``, ``judge``, ``human``, ``severe_flag``,
  ``pending`` (and ``not_applicable`` for the evidence of content 0). The judge never
  decides ``auto_numeric`` or ``auto_assisted_human`` criteria, a judge 'supported' for
  a finding an automated numeric check contradicts is a conflict for a human
  (``flags.assertion_conflicts``), and severe flags are only confirmed by humans.

Content coverage, evidence support and assertion quality are reported separately per
task. ``status`` is ``provisional`` unless every criterion and assertion carries a human
value or sign-off, every suspected severe flag is adjudicated, explanation quality has
notes, the decisions file is not a builder fixture, an episode trace is available, the
bundle is the key's bundle and the key's review status is ``reviewed``.

Grading decisions (``decisions_schema`` ``gb2019-sr-grading-decisions/1``) have the MVP
layout (see :mod:`.grading`) with tasks as dimensions, plus an optional
``"accept_judge": true`` on a criterion or an assertion: the human signs off the judge's
proposal (applied when a judge layer is present).

Judge output (``judge_schema`` ``gb2019-sr-judge-output/1``), produced by the judge
track and merged by :func:`merge_judge_proposals`::

    {"judge_schema": "gb2019-sr-judge-output/1",
     "judge_model": "...", "rubric_version": "...", "prompt_sha256": "...",
     "binding": {"submission_sha256": "...", "key_version": "...",
                 "key_sha256": "...", "bundle_sha256": "..."},
     "criteria": {"T06.01": {"content": 1 | 0.5 | 0 | null,
                             "evidence_support": 1 | 0 | null,
                             "finding_ids": ["F07"], "rationale": "...",
                             "supporting_spans": [{...}]}},
     "assertions": {"F07": {"verdict": "supported" | "unsupported" | "contradicted",
                            "task": "T06"?, "rationale": "..."},
                    "J-1": {"verdict": "...", "text": "report sentence", "task": "T08"}},
     "severe_flags": [{"flag_id": "SF1", "finding_ids": [], "locations": [],
                       "rationale": "..."}]}

This module must not import ``karotte``.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from environment.incident import grading as mvp
from environment.incident import sr_accounting
from environment.incident.catalogue import Catalogue, CatalogueError
from environment.incident.episode import (
    SUBMISSION_FILE,
    SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET,
    SYSTEM_RESPONSE_TOOL_NAMES,
    EpisodeError,
    build_transcript_summary,
    read_config_snapshot,
    read_state,
    read_trace,
)
from environment.incident.grading import (
    CONTENT_VALUES,
    EVIDENCE_VALUES,
    VERDICTS,
    CitationCheck,
    DecisionsError,
    GradingError,
    _any,
    _Ctx,
    _public,
    normalise,
)
from environment.incident.locators import (
    RECORD_KINDS,
    Locator,
    LocatorError,
    parse_and_validate,
    parse_iso_instant,
)
from environment.incident.paths import (
    SYSTEM_RESPONSE_BUNDLE_DIR,
    SYSTEM_RESPONSE_PRIVATE_DIR,
)
from environment.incident.submission import extract_references

__all__ = [
    "DECISIONS_SCHEMA",
    "GRADE_SCHEMA",
    "GRADER_VERSION",
    "JUDGE_SCHEMA",
    "KEY_SCHEMA",
    "MODES",
    "DecisionsError",
    "GradingError",
    "JudgeOutputError",
    "check_decisions",
    "check_citations",
    "cited_spans",
    "criterion_rubric",
    "grade_episode",
    "grade_submission",
    "key_sha256",
    "load_decisions",
    "load_key",
    "merge_judge_proposals",
    "resolve_text",
    "review_template",
    "trace_info_from_episode",
]

GRADER_VERSION = "0.1.1"
GRADE_SCHEMA = "gb2019-sr-grade/1"
KEY_SCHEMA = "gb2019-sr-answer-key/1"
DECISIONS_SCHEMA = "gb2019-sr-grading-decisions/1"
JUDGE_SCHEMA = "gb2019-sr-judge-output/1"
DEFAULT_KEY_PATH = SYSTEM_RESPONSE_PRIVATE_DIR / "answer_key.json"
MODES = ("auto_numeric", "auto_assisted_human", "judge", "human")
SIGNED = ("auto", "human", "severe_flag")

INTERPRETATION = (
    "No pass threshold, overall score, task total or ranking is computed. Content "
    "coverage, evidence support and assertion quality are separate measures. Each "
    "value carries its source: 'auto' (decided by an automated check), 'judge' (an LLM "
    "judge proposal awaiting human sign-off), 'human', 'severe_flag' or 'pending'. "
    "'auto_proposal' values are automated suggestions for the reviewer, not grades. "
    "Field subweights within a handoff criterion are a reporting convenience only."
)

key_sha256 = mvp.key_sha256


class JudgeOutputError(GradingError):
    """A judge output is malformed or bound to another submission, key or bundle."""


# -- key ---------------------------------------------------------------------------------
def load_key(path: Path | str | None = None) -> dict[str, Any]:
    """Load the system-response answer key (default: the private key)."""
    key_path = Path(path) if path is not None else DEFAULT_KEY_PATH
    try:
        key = json.loads(key_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GradingError(f"cannot load the answer key {key_path}: {exc}") from None
    if not isinstance(key, dict) or key.get("key_schema") != KEY_SCHEMA:
        raise GradingError(f"{key_path} is not a {KEY_SCHEMA} answer key")
    return key


def _review_status(key: Mapping[str, Any]) -> str:
    return str(
        (key.get("review") or {}).get("status") or key.get("review_status") or "unknown"
    )


def _tasks(key: Mapping[str, Any]) -> list[str]:
    return [d["dimension_id"] for d in key["dimensions"]]


def _task_of(cid: str) -> str:
    return cid.split(".")[0]


# -- trace: every retrieval route ----------------------------------------------------
_R01_TOKENS = ("R01", "frequency_2019-08-09", "frequency_hz")


def _ranges(numbers: Iterable[int]) -> list[list[int]]:
    out: list[list[int]] = []
    for n in sorted(set(numbers)):
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return out


def trace_info_from_episode(episode_dir: Path | str) -> dict[str, Any]:
    """What the episode obtained, by route: documents (``request_document``,
    ``request_data_return``, ``query_frequency``), records returned by
    ``query_asset_log`` / ``query_control_log`` / ``interview_witness``, the R01 rows
    seen through ``query_frequency``, and the Python calls."""
    episode_dir = Path(episode_dir)
    state = read_state(episode_dir)
    trace = read_trace(episode_dir)
    routes: dict[str, list[str]] = {}
    first_seq: dict[str, int] = {}
    records: dict[str, dict[str, Any]] = {}
    rows_seen: set[int] = set()
    python_calls: list[dict[str, Any]] = []
    for record in trace:
        envelope = record.get("envelope") or {}
        tool = record.get("tool")
        seq = int(record.get("seq") or 0)
        if tool == "run_python" and record.get("python"):
            py = record["python"]
            code = str(py.get("code") or "")
            python_calls.append(
                {
                    "seq": seq,
                    "request_id": record.get("request_id"),
                    "ok": bool(envelope.get("ok")),
                    "exit_code": py.get("exit_code"),
                    "timed_out": py.get("timed_out"),
                    "code_sha256": py.get("code_sha256"),
                    "mentions_r01": any(token in code for token in _R01_TOKENS),
                }
            )
        if not envelope.get("ok"):
            continue
        data = envelope.get("data") or {}
        if tool in ("request_document", "request_data_return", "query_frequency"):
            for doc in envelope.get("evidence_ids") or []:
                if tool not in routes.setdefault(doc, []):
                    routes[doc].append(tool)
                first_seq.setdefault(doc, seq)
        if tool == "query_frequency":
            for row in data.get("rows") or []:
                if isinstance(row, list) and row and isinstance(row[0], int):
                    rows_seen.add(row[0])
        if tool in ("query_asset_log", "query_control_log"):
            kind, ident = (
                ("event", "event_id")
                if tool == "query_asset_log"
                else ("entry", "entry_id")
            )
            for row in data.get("rows") or []:
                if isinstance(row, Mapping) and row.get(ident):
                    records.setdefault(
                        f"{kind}:{row[ident]}",
                        {
                            "tool": tool,
                            "seq": seq,
                            "evidence_id": row.get("evidence_id"),
                        },
                    )
        if (
            tool == "interview_witness"
            and data.get("matched")
            and data.get("response_id")
        ):
            records.setdefault(
                f"response:{data['response_id']}",
                {
                    "tool": tool,
                    "seq": seq,
                    "evidence_id": (envelope.get("evidence_ids") or [None])[0],
                    "persona_id": data.get("persona_id"),
                },
            )
    retrieved = list(state.retrieved) if state else sorted(routes)
    for doc in retrieved:
        routes.setdefault(doc, ["state"])
    r01_seq = first_seq.get("R01")
    analysed = any(
        c["ok"] and c["mentions_r01"] and r01_seq is not None and c["seq"] > r01_seq
        for c in python_calls
    )
    by_kind = {kind: 0 for kind in RECORD_KINDS}
    for name in records:
        by_kind[name.split(":", 1)[0]] += 1
    return {
        "available": True,
        "retrieved": retrieved,
        "document_routes": routes,
        "first_retrieval_seq": first_seq,
        "records": records,
        "records_by_kind": by_kind,
        "frequency_rows_seen": _ranges(rows_seen),
        "python_calls": python_calls,
        "r01_analysed_with_python": analysed,
        "calls_used": state.calls_used if state else None,
        "frozen_at_request_id": state.frozen_at_request_id if state else None,
    }


def _row_seen(trace_info: Mapping[str, Any], row: int) -> bool:
    return any(a <= row <= b for a, b in trace_info.get("frequency_rows_seen") or [])


# -- citation targets and text ---------------------------------------------------------
def _target(catalogue: Catalogue, evidence_id: str) -> Any:
    get = getattr(catalogue, "citation_target", None)
    return get(evidence_id) if get is not None else catalogue.get(evidence_id)


_CSV_CACHE: dict[tuple[str, str], list[str]] = {}


def _series_lines(catalogue: Catalogue, doc_id: str) -> list[str]:
    doc = catalogue.get(doc_id)
    artifact = next(a for a in doc.artifacts if a.timeseries is not None)
    cache_key = (artifact.sha256, artifact.file)
    if cache_key not in _CSV_CACHE:
        text = catalogue.read_artifact(artifact).decode("utf-8")
        _CSV_CACHE[cache_key] = text.splitlines()[1:]
    return _CSV_CACHE[cache_key]


def _record(catalogue: Catalogue, kind: str, record_id: str) -> Any:
    sources = catalogue.sources
    if sources is None:
        return None
    if kind == "event":
        for log in sources.asset_logs.values():
            for row in log.rows:
                if row.record_id == record_id:
                    return row
    elif kind == "entry":
        for log in sources.control_logs.values():
            for row in log.rows:
                if row.record_id == record_id:
                    return row
    else:
        for card in sources.witnesses.values():
            for block in card.blocks:
                if block.response_id == record_id:
                    return block
    return None


def _record_text(kind: str, record: Any) -> str:
    if kind == "response":
        return f"{record.response_id}: {record.response_text}"
    raw = record.raw
    if kind == "event":
        parts = [
            raw.get("recorded_time"),
            raw.get("clock_basis"),
            raw.get("signal"),
            f"{raw.get('value')} {raw.get('unit') or ''}".strip()
            if raw.get("value") is not None
            else None,
            raw.get("text"),
        ]
    else:
        parts = [
            raw.get("recorded_time"),
            raw.get("clock_basis"),
            f"{raw.get('from')} -> {raw.get('to')}",
            raw.get("channel"),
            raw.get("text"),
        ]
    return " | ".join(str(p) for p in parts if p not in (None, ""))


def resolve_text(catalogue: Catalogue, evidence_id: str, locator: str) -> str:
    """The text a citation points at: numbered lines, time-series rows (as CSV lines),
    or a record (asset-log event, control-log entry, witness response). Raises
    :class:`LocatorError` when the locator does not resolve."""
    target = _target(catalogue, evidence_id)
    if target is None:
        raise LocatorError(f"unknown evidence_id {evidence_id!r}")
    loc = parse_and_validate(locator, target)
    if loc.kind in RECORD_KINDS:
        record = _record(catalogue, loc.kind, str(loc.start))
        if record is None:  # pragma: no cover - validated above
            raise LocatorError(f"{loc.normalized} not found")
        return _record_text(loc.kind, record)
    doc = catalogue.get(evidence_id)
    if loc.kind == "lines":
        return "\n".join(doc.lines[loc.start - 1 : loc.end])
    rows = _series_lines(catalogue, evidence_id)
    if loc.kind == "rows":
        return "\n".join(rows[loc.start - 1 : loc.end])
    series = doc.timeseries
    a = math.ceil((loc.start - series.first).total_seconds() / series.interval_s)
    b = math.floor((loc.end - series.first).total_seconds() / series.interval_s)
    return "\n".join(rows[a : b + 1])


@dataclass
class SRCitationCheck(CitationCheck):
    """A citation check with the retrieval route(s) that obtained the cited evidence."""

    routes: list[str] = field(default_factory=list)
    targets_keyed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out = super().to_dict()
        out["kind"] = self.locator_obj.kind if self.locator_obj is not None else None
        out["retrieval_routes"] = list(self.routes)
        out["targets_keyed_evidence_of"] = sorted(self.targets_keyed)
        return out


def check_citations(
    findings: Sequence[Mapping[str, Any]],
    catalogue: Catalogue,
    trace_info: Mapping[str, Any] | None,
) -> dict[str, list[SRCitationCheck]]:
    """Resolve every citation (documents and records) and say whether the cited
    evidence was obtained during the episode, and by which route. A record locator
    counts as retrieved when a tool returned that record, or (route ``document``) when
    the document it restates was retrieved."""
    docs = set(trace_info.get("retrieved") or []) if trace_info else None
    records = (trace_info or {}).get("records") or {}
    doc_routes = (trace_info or {}).get("document_routes") or {}
    out: dict[str, list[SRCitationCheck]] = {}
    for finding in findings:
        checks = []
        for index, citation in enumerate(finding.get("citations") or []):
            evidence_id = citation["evidence_id"]
            target = _target(catalogue, evidence_id)
            loc, error = None, None
            if target is None:
                error = f"unknown evidence_id {evidence_id!r}"
            else:
                try:
                    loc = parse_and_validate(citation["locator"], target)
                except LocatorError as exc:
                    error = str(exc)
            retrieved: bool | None = None
            routes: list[str] = []
            if trace_info is not None:
                if loc is not None and loc.kind in RECORD_KINDS:
                    hit = records.get(f"{loc.kind}:{loc.start}")
                    if hit:
                        retrieved, routes = True, [hit["tool"]]
                    elif evidence_id in (docs or set()):
                        retrieved, routes = True, ["document"]
                    else:
                        retrieved = False
                else:
                    retrieved = evidence_id in (docs or set())
                    routes = list(doc_routes.get(evidence_id, [])) if retrieved else []
            checks.append(
                SRCitationCheck(
                    finding_id=finding["finding_id"],
                    index=index,
                    evidence_id=evidence_id,
                    locator=citation["locator"],
                    normalized=loc.normalized if loc else None,
                    resolvable=loc is not None,
                    error=error,
                    retrieved=retrieved,
                    locator_obj=loc,
                    routes=routes,
                )
            )
        out[finding["finding_id"]] = checks
    return out


_KEYED_CACHE: dict[tuple[str, str, str], Locator | None] = {}


def _keyed_locator(catalogue: Catalogue, keyed: Mapping[str, Any]) -> Locator | None:
    cache_key = (catalogue.bundle_sha256, keyed["evidence_id"], keyed["locator"])
    if cache_key not in _KEYED_CACHE:
        target = _target(catalogue, keyed["evidence_id"])
        try:
            _KEYED_CACHE[cache_key] = (
                None if target is None else parse_and_validate(keyed["locator"], target)
            )
        except LocatorError:
            _KEYED_CACHE[cache_key] = None
    return _KEYED_CACHE[cache_key]


def _overlaps(
    check: CitationCheck, keyed: Mapping[str, Any], catalogue: Catalogue
) -> bool:
    loc = check.locator_obj
    if loc is None or check.evidence_id != keyed["evidence_id"]:
        return False
    target = _keyed_locator(catalogue, keyed)
    if target is None:
        return False
    if loc.kind in RECORD_KINDS or target.kind in RECORD_KINDS:
        return loc.kind == target.kind and loc.start == target.start
    if loc.kind == "lines":
        return target.kind == "lines" and loc.overlaps_lines(target.start, target.end)
    if target.kind == "lines":
        return False
    span = mvp._instants(loc, check.evidence_id, catalogue)
    tspan = mvp._instants(target, check.evidence_id, catalogue)
    return bool(span and tspan and span[0] <= tspan[1] and tspan[0] <= span[1])


def _targets(
    check: CitationCheck, keyed: Mapping[str, Any], catalogue: Catalogue
) -> bool:
    """Whether an overlapping citation is specific to the keyed span (a record, or a
    span at most a few times the keyed one and under half of a document)."""
    loc = check.locator_obj
    target = _keyed_locator(catalogue, keyed)
    if loc is None or target is None:
        return False
    if loc.kind in RECORD_KINDS:
        return True
    doc = catalogue.get(check.evidence_id)
    if doc is None:
        return False
    cited = mvp._span_size(loc, check.evidence_id, catalogue)
    wanted = mvp._span_size(target, check.evidence_id, catalogue)
    if cited is None or wanted is None:
        return False
    if (
        loc.kind == "lines"
        and doc.lines
        and cited >= mvp._WHOLE_DOCUMENT_SHARE * len(doc.lines)
    ):
        return False
    return cited <= max(mvp._TARGET_FACTOR * wanted, mvp._TARGET_FLOOR)


# -- context ------------------------------------------------------------------------------
@dataclass
class _SRCtx(_Ctx):
    accounting: sr_accounting.AccountingResult | None = None
    # Element types another task's grader adds (``type`` -> ``evaluate(el, ctx)``,
    # returning an element result like :func:`_eval`); see :func:`grade_submission`.
    # Empty for the system-response key, whose element types are all built in.
    element_types: Mapping[str, Callable[..., dict[str, Any]]] = field(
        default_factory=dict
    )
    # The validated submission (for added element types that read its parts).
    submission: Mapping[str, Any] | None = None


_FIGURE_LEVELS = {
    "attributed": 1.0,
    "defined": 1.0,
    "unattributed": 0.5,
    "misattributed": 0.0,
    "mismatched": 0.0,
}


def _eval_figure(el: Mapping[str, Any], ctx: _SRCtx) -> dict[str, Any]:
    """A ``figure`` element: the best basis classification of the element's figures
    among findings with a selected status (key ``levels``; ``require_qualifier`` caps
    a mention without its qualifier, e.g. estimate wording, at ``unqualified_level``).
    Mentions in the report text only, and figures given on a wrong basis, are listed
    for the reviewer."""
    wanted = set(el["figures"])
    statuses = el.get("statuses") or list(ctx.factual)
    levels = {**_FIGURE_LEVELS, **(el.get("levels") or {})}
    suspected = {s["finding_id"] for s in ctx.severe if s.get("finding_id")}
    accounting = ctx.accounting or sr_accounting.AccountingResult()
    best: tuple[float, int, str, dict[str, Any]] | None = None
    levels_by_finding: dict[str, float] = {}
    considered: list[str] = []
    report_only: list[dict[str, Any]] = []
    wrong: list[dict[str, Any]] = []
    without_unit: list[dict[str, Any]] = []
    for m in accounting.mentions:
        if m.figure_id not in wanted:
            continue
        if m.finding_id is None:
            report_only.append(m.to_dict())
            continue
        if m.finding_id in suspected or m.status not in statuses:
            continue
        if m.via == "bare":  # no unit: a candidate for a human, never credited
            without_unit.append(m.to_dict())
            continue
        level = float(levels.get(m.classification, 0.0))
        if el.get("require_qualifier") and not m.qualified:
            level = min(level, float(el.get("unqualified_level", 0.5)))
        if m.classification in sr_accounting.WRONG:
            wrong.append(m.to_dict())
        if m.finding_id not in considered:
            considered.append(m.finding_id)
        levels_by_finding[m.finding_id] = max(
            level, levels_by_finding.get(m.finding_id, 0.0)
        )
        cand = (level, ctx.order[m.finding_id], m.finding_id, m.to_dict())
        if best is None or (-cand[0], cand[1]) < (-best[0], best[1]):
            best = cand
    detail: dict[str, Any] = {}
    if report_only:
        detail["report_only"] = report_only[:5]
    if wrong:
        detail["wrong_basis"] = wrong[:5]
    if without_unit:
        detail["without_unit"] = without_unit[:5]
    considered.sort(key=lambda f: ctx.order[f])
    if best is None:
        return {
            "id": el["id"],
            "level": 0.0,
            "finding_id": None,
            "finding_ids": [],
            "considered": considered,
            "detail": detail,
        }
    # every finding that reaches the best level (their citations are all checked)
    tied = sorted(
        (f for f, v in levels_by_finding.items() if best[0] > 0 and v >= best[0]),
        key=lambda f: ctx.order[f],
    )
    return {
        "id": el["id"],
        "level": best[0],
        "finding_id": best[2] if best[0] > 0 else None,
        "finding_ids": tied,
        "considered": considered,
        "detail": {**best[3], **detail},
    }


def _eval_value_in_sentence(el: Mapping[str, Any], ctx: _SRCtx) -> dict[str, Any]:
    """A ``value`` element with an ``entity`` and ``near_scope: "sentence"``: the MVP
    rule reads ``near_any`` in the value's clause; here a statement value bound to the
    entity also counts when the wording is elsewhere in its sentence (table-style lists:
    "infeed losses (Table 2): ST1C 244 MW; Hornsea 737 MW; ..."). An in-tolerance value
    bound to the entity without that wording in its sentence is listed
    (``candidates_without_near``) for a human, never credited. A value whose own clause
    matches ``clause_unless_any`` (e.g. output before the event) is neither."""
    base = mvp._eval_element(el, ctx)
    if base["level"] >= 1 or not el.get("entity") or not el.get("from_text"):
        return base
    near = el.get("near_any") or []
    suspected = {s["finding_id"] for s in ctx.severe if s.get("finding_id")}
    fields = mvp._text_fields(el)
    exclude = el.get("exclude_values") or {}
    tol = float(exclude.get("abs_tol", 0)) + 1e-9
    credited: list[dict[str, Any]] = []
    noted: list[dict[str, Any]] = []
    for finding in ctx.findings:
        fid = finding["finding_id"]
        if fid in suspected or not ctx.status_ok(finding, el.get("statuses")):
            continue
        if any(_any(ctx.field_text(finding, fields), g) for g in el.get("none", [])):
            continue
        layout = ctx.layout(finding)
        if not mvp._all_groups(layout.text, el.get("context") or []):
            continue
        excluded = (
            list(exclude.get("values") or [])
            if exclude and not _any(layout.text, exclude.get("unless_any", []))
            else []
        )
        for value, start, end in mvp._text_value_spans(
            layout.text, el["unit"], ctx.aliases
        ):
            if layout.entity_at(start, end) != el["entity"]:
                continue
            if any(abs(value - float(x)) <= tol for x in excluded):
                continue
            clause = layout.clause_text(start)
            if near and _any(clause, near):
                continue  # read by the MVP rule
            if _any(clause, el.get("clause_unless_any") or ()):
                continue
            level, error = mvp._level_value(value, el)
            if level <= 0:
                continue
            sa, sb = layout._span(layout.sentences, start)
            item = {
                "finding_id": fid,
                "value": value,
                "level": level,
                "error": error,
                "sentence": layout.text[sa:sb][:200],
            }
            (credited if _any(layout.text[sa:sb], near) else noted).append(item)
    out = dict(base)
    if credited:
        best = min(
            credited,
            key=lambda c: (-c["level"], c["error"], ctx.order[c["finding_id"]]),
        )
        if best["level"] > base["level"]:
            fids = sorted(
                {c["finding_id"] for c in credited if c["level"] >= best["level"]},
                key=lambda f: ctx.order[f],
            )
            return {
                "id": el["id"],
                "considered": sorted(
                    set(base.get("considered") or []) | set(fids),
                    key=lambda f: ctx.order[f],
                ),
                "level": best["level"],
                "finding_id": best["finding_id"],
                "finding_ids": [best["finding_id"]],
                "detail": {
                    "value": best["value"],
                    "source": "statement (wording in the value's sentence)",
                    "error": best["error"],
                    "best_finding": best["finding_id"],
                },
            }
    if noted:
        out["detail"] = {
            **(base.get("detail") or {}),
            "candidates_without_near": noted[:5],
        }
        out["considered"] = sorted(
            set(base.get("considered") or []) | {c["finding_id"] for c in noted},
            key=lambda f: ctx.order[f],
        )
    return out


def _eval_time_with_statement_times(
    el: Mapping[str, Any], ctx: _SRCtx
) -> dict[str, Any]:
    """A ``time`` element with ``read_statement_times``: the MVP reader takes only a
    finding's ``event_time`` when it has one (a window boundary in the statement never
    overrides it). For a window whose start is the event time ("instructed between 16:58
    and 17:16 BST", event_time 16:58) the end is in the statement, so the statement's
    times are read as well; the better result counts."""
    base = mvp._eval_element(el, ctx)
    if base["level"] >= 1:
        return base
    stripped = replace(
        ctx,
        findings=[
            {k: v for k, v in f.items() if k != "event_time"} for f in ctx.findings
        ],
    )
    alt = mvp._eval_element(el, stripped)
    if alt["level"] <= base["level"]:
        return base
    detail = dict(alt.get("detail") or {})
    detail["source"] = "statement (the finding's event_time is another boundary)"
    return {**alt, "detail": detail}


def _eval(el: Mapping[str, Any], ctx: _SRCtx) -> dict[str, Any]:
    added = ctx.element_types.get(str(el.get("type")))
    if added is not None:
        return added(el, ctx)
    if el.get("type") == "figure":
        return _eval_figure(el, ctx)
    if el.get("type") == "value" and el.get("near_scope") == "sentence":
        return _eval_value_in_sentence(el, ctx)
    if el.get("type") == "time" and el.get("read_statement_times"):
        return _eval_time_with_statement_times(el, ctx)
    return mvp._eval_element(el, ctx)


def _cap_hits(caps: Sequence[Mapping[str, Any]], ctx: _SRCtx) -> list[dict[str, Any]]:
    """Accounting traps in findings with a factual status that match a cap rule."""
    accounting = ctx.accounting or sr_accounting.AccountingResult()
    found = []
    for cap in caps:
        for trap in accounting.traps:
            if trap["type"] not in cap.get("trap_types", ()):
                continue
            if cap.get("figures") and trap.get("figure_id") not in cap["figures"]:
                continue
            if cap.get("groups") and trap.get("group") not in cap["groups"]:
                continue
            if not trap.get("finding_id") or trap.get("status") not in ctx.factual:
                continue
            found.append(
                {
                    "id": cap["id"],
                    "finding_id": trap["finding_id"],
                    "effect": cap["effect"],
                    "note": cap.get("note") or trap.get("note"),
                    "trap": trap,
                }
            )
    return found


# Basis notes for candidates that the added element types (``element_types``, e.g. the
# full investigation's ``count``) list but do not credit: (detail key, note).
_ADDED_CANDIDATE_NOTES = (
    (
        "wrong_meaning",
        "the expected value ({value:g}) is given with wording of another meaning",
    ),
    (
        "alternative_without_source",
        "another account's value ({value:g}) is given without the source that "
        "reports it",
    ),
    (
        "alternative_misattributed",
        "another account's value ({value:g}) is attributed to a source that does not "
        "report it",
    ),
    (
        "times_without_near",
        "a time within tolerance ({value}) is given without the expected wording in "
        "its own clause",
    ),
    (
        "labelled_candidates",
        "the figure ({value}) is given in a finding labelled hypothesis, or labelled "
        "unknown with uncertainty wording in the figure's clause,",
    ),
)


def _score_rules(auto: Mapping[str, Any], ctx: _SRCtx) -> dict[str, Any]:
    """The MVP rule combination (:func:`.grading._score_rules`) with ``figure``
    elements and accounting caps. Caps and contradictions are also returned as
    ``caps`` so that they bound a judge proposal.

    Two optional fields of an element result (only the added element types use them;
    increment A's results never carry them): ``route_finding_ids``, the findings whose
    own content the element matched (the others, e.g. findings an executive summary
    merely refers to, are returned as ``unrouted_finding_ids`` and do not route a
    finding to the criterion's task); ``keyed_evidence``, keyed spans that replace the
    criterion's primary spans for evidence support (an alternative account's figure is
    supported by that account's spans)."""
    elements = [_eval(el, ctx) for el in auto.get("elements", [])]
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
    contradictions = mvp._contradictions(auto.get("contradictions", []), ctx)
    capped = contradictions + _cap_hits(auto.get("accounting_caps", []), ctx)
    caps: list[dict[str, Any]] = []
    for hit in capped:
        caps.append(
            {
                "kind": "contradiction" if "trap" not in hit else "accounting",
                "id": hit["id"],
                "finding_id": hit["finding_id"],
                "effect": hit["effect"],
                "note": hit.get("note"),
            }
        )
        if hit["effect"] == "zero" and content > 0:
            content, basis = (
                0.0,
                f"{caps[-1]['kind']} {hit['id']} ({hit['finding_id']})",
            )
        elif hit["effect"] == "cap_half" and content > 0.5:
            content, basis = (
                0.5,
                f"capped by {caps[-1]['kind']} {hit['id']} ({hit['finding_id']})",
            )
    notes = []
    for e in elements:
        if e["level"] < 1 and e["detail"].get("report_only_times"):
            notes.append(
                f"{e['id']}: a time within tolerance appears only in the report"
            )
        if e["level"] < 1 and e["detail"].get("report_only"):
            notes.append(f"{e['id']}: the figure appears only in the report text")
        if e["level"] < 1 and e["detail"].get("without_unit"):
            where = sorted({m["location"] for m in e["detail"]["without_unit"]})
            notes.append(
                f"{e['id']}: the figure appears without a unit in {', '.join(where)}"
            )
        if e["level"] < 1 and e["detail"].get("candidates_without_near"):
            items = e["detail"]["candidates_without_near"]
            where = sorted(
                {c["finding_id"] for c in items}, key=lambda f: ctx.order.get(f, 0)
            )
            notes.append(
                f"{e['id']}: a value within tolerance ({items[0]['value']:g}) is given "
                f"for the entity without the expected wording in its sentence in "
                f"{', '.join(where)}"
            )
        # candidates only the added element types report (increment A's elements
        # never carry these keys, so its notes are unchanged)
        for name, what in _ADDED_CANDIDATE_NOTES:
            if e["level"] < 1 and e["detail"].get(name):
                items = e["detail"][name]
                where = sorted(
                    {c["finding_id"] for c in items},
                    key=lambda f: ctx.order.get(f, 0),
                )
                notes.append(
                    f"{e['id']}: {what.format(value=items[0]['value'])} in "
                    f"{', '.join(where)}"
                )
    if notes and content < 1:
        basis += (
            "; note: "
            + "; ".join(notes)
            + " (not credited automatically: a human decides)"
        )
    zero_flags = set(auto.get("severe_flags_zero") or [])
    # ``severe_flags_zero_at`` (optional; not in increment A's key) restricts the
    # suspicions that cap the criterion to these locations, e.g. a summary criterion
    # capped only by a suspected assertion in the executive summary
    where = auto.get("severe_flags_zero_at")
    severe_hits = sorted(
        {
            s["flag_id"]
            for s in ctx.severe
            if s["flag_id"] in zero_flags
            and (where is None or s.get("location") in where)
        }
    )
    for flag_id in severe_hits:
        caps.append(
            {
                "kind": "severe_suspected",
                "id": flag_id,
                "flag_id": flag_id,
                "effect": "zero",
                "note": f"suspected severe flag {flag_id} (applies unless adjudicated "
                "false)",
            }
        )
    if severe_hits and content > 0:
        content, basis = 0.0, "suspected severe flag " + ", ".join(severe_hits)
    matched: list[str] = []
    for e in elements:
        for fid in e["finding_ids"]:
            if fid not in matched:
                matched.append(fid)
    for hit in capped:
        if hit["finding_id"] not in matched:
            matched.append(hit["finding_id"])
    matched.sort(key=lambda f: ctx.order[f])
    considered = sorted(
        {fid for e in elements for fid in e["considered"]} | set(matched),
        key=lambda f: ctx.order[f],
    )
    out = {
        "content": content,
        "basis": basis,
        "elements": elements,
        "contradictions": contradictions,
        "caps": caps,
        "matched_finding_ids": matched,
        "considered_finding_ids": considered,
        "conflicts": [],
    }
    if any("route_finding_ids" in e for e in elements):
        routing = {hit["finding_id"] for hit in capped}
        for e in elements:
            if "route_finding_ids" in e:
                routing |= set(e["route_finding_ids"])
            else:
                routing |= set(e["finding_ids"]) | set(e["considered"])
        out["unrouted_finding_ids"] = [f for f in considered if f not in routing]
    keyed = [
        item
        for e in elements
        if e["level"] > 0 and e.get("keyed_evidence")
        for item in e["keyed_evidence"]
    ]
    if keyed:
        out["keyed_evidence"] = keyed
    return out


def _assess_criterion(crit: Mapping[str, Any], ctx: _SRCtx) -> dict[str, Any]:
    auto = crit.get("auto") or {"kind": "none"}
    kind = auto.get("kind", "none")
    if kind in ("landmark", "duration"):
        out = mvp._score_landmark(auto, ctx, kind)
        out.setdefault("caps", [])
        return out
    if kind == "rules":
        out = _score_rules(auto, ctx)
        if crit.get("assessment_mode") == "judge":
            # Sentence-level contradiction rules are a pre-screen: for a judge
            # criterion they flag a sentence for the reviewer and bound the automated
            # proposal, never the judge's value (accounting traps and suspected severe
            # flags still do).
            out["caps"] = [
                {**c, "binding": False} if c["kind"] == "contradiction" else c
                for c in out["caps"]
            ]
        return out
    return {
        "content": None,
        "basis": "no automated check",
        "elements": [],
        "contradictions": [],
        "caps": [],
        "matched_finding_ids": [],
        "conflicts": [],
    }


def _evidence_view(
    crit: Mapping[str, Any], assessment: Mapping[str, Any]
) -> Mapping[str, Any]:
    """The criterion as evidence support reads it: unchanged, unless the content was
    credited through spans of its own (``keyed_evidence``, e.g. an alternative
    account's count), which then are the primary spans and the criterion's own
    primary spans become context."""
    keyed = assessment.get("keyed_evidence")
    if not keyed:
        return crit
    own = [
        {**item, "role": "context"}
        if item.get("role", "primary") == "primary"
        else item
        for item in crit.get("visible_evidence", [])
    ]
    return {
        **crit,
        "visible_evidence": [{**k, "role": "primary"} for k in keyed] + own,
    }


def _assess_evidence(
    crit: Mapping[str, Any], assessment: Mapping[str, Any], ctx: _SRCtx
) -> dict[str, Any]:
    """Evidence support of the matched findings: decided for R01 landmarks and for
    uncited/absent findings; otherwise a proposal (citations of keyed primary spans,
    including records, retrieved by any route)."""
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
    prefix = "" if assessment.get("content") else "content proposal is 0; "
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
            if not any(mvp._covers(c, t, ctx.catalogue) for c in relevant)
        ]
        retrieved = None
        if ctx.trace_info is not None:
            retrieved = doc_id in set(ctx.trace_info.get("retrieved") or [])
        decided = True
        if not relevant:
            basis, value = f"no resolvable {doc_id} time/row citation", 0
        elif uncovered:
            basis, value = f"{doc_id} citations do not cover {', '.join(uncovered)}", 0
        elif retrieved is False:
            basis, value = (
                f"{doc_id} was cited but never retrieved during the episode",
                0,
            )
        else:
            basis = (
                f"{doc_id} citation covers {', '.join(t.isoformat() for t in needed)}"
            )
            if not retrieved:
                basis += " (retrieval not checked: no trace)"
            value = 1
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
            if doc_id == "R01" and ctx.trace_info is not None:
                doc = ctx.catalogue.get("R01")
                series = doc.timeseries if doc else None
                seen = series is not None and all(
                    _row_seen(
                        ctx.trace_info,
                        int((t - series.first).total_seconds() // series.interval_s)
                        + 1,
                    )
                    for t in needed
                )
                if ctx.trace_info.get("r01_analysed_with_python"):
                    basis += "; R01 analysed with run_python"
                elif seen:
                    basis += "; the samples were read through query_frequency"
                else:
                    decided = False
                    basis += (
                        "; R01 was neither analysed with run_python nor were these "
                        "samples read through query_frequency: needs human review"
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
        proposal, basis = 1, "cites keyed evidence " + names(retrieved_ok)
    elif targeted:
        proposal, basis = 0, "keyed evidence cited but never obtained in the episode"
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
    return {
        "value": None,
        "decided": False,
        "proposal": proposal,
        "basis": prefix + basis,
        "citations": [c.to_dict() for c in checks],
    }


# -- severe flags ---------------------------------------------------------------------------
def _record_shapes(catalogue: Catalogue) -> tuple[set[str], set[tuple[str, str]]]:
    sources = catalogue.sources
    if sources is None:
        return set(), set()
    ids = {record_id for (_, record_id) in sources.owners}
    shapes = set()
    for record_id in ids:
        head, _, rest = record_id.partition("-")
        shapes.add((head, re.sub(r"\d+", "#", rest)))
    return ids, shapes


_LABELS_CACHE: dict[tuple[str, str], frozenset[str]] = {}
_ITEM_LABEL = re.compile(r"^\s*([A-Z]{1,3}\d{1,3}[a-z]?)(?=\s|$)")


def _item_labels(catalogue: Catalogue, doc_id: str) -> frozenset[str]:
    """The item labels that start lines of a document ("C2  Fault location: ..." in
    R03), as written; empty for unknown or non-text evidence."""
    cache_key = (catalogue.bundle_sha256, doc_id)
    if cache_key not in _LABELS_CACHE:
        doc = catalogue.get(doc_id)
        lines = list(getattr(doc, "lines", None) or []) if doc is not None else []
        _LABELS_CACHE[cache_key] = frozenset(
            m.group(1) for line in lines for m in [_ITEM_LABEL.match(line)] if m
        )
    return _LABELS_CACHE[cache_key]


def _invented_records(
    sub: Mapping[str, Any], flag: Mapping[str, Any], catalogue: Catalogue
) -> list[dict[str, Any]]:
    """Evidence IDs that are not in the bundle (e.g. S02, R09) and record IDs shaped
    like the bundle's records but absent from it (e.g. S07-E14). A reference to a
    labelled line of the document ("R03-C2" for R03's line "C2 ...") is not a record."""
    heur = flag.get("heuristic") or {}
    ids_rx = re.compile(heur["record_id_pattern"])
    ref_rx = (
        re.compile(heur["record_ref_pattern"])
        if heur.get("record_ref_pattern")
        else None
    )
    citable = getattr(catalogue, "citable_ids", None)
    valid = set(citable(public=False)) if citable else set(catalogue.ids())
    record_ids, shapes = _record_shapes(catalogue)
    places = [(f["finding_id"], f["statement"]) for f in sub["findings"]]
    places += [
        (f["finding_id"], str(f.get("derivation") or ""))
        for f in sub["findings"]
        if f.get("derivation")
    ]
    places += list(mvp._report_texts(sub))
    found: list[dict[str, Any]] = []
    for where, text in places:
        refs = set(ref_rx.findall(text)) if ref_rx else set()
        bad = {rid for rid in ids_rx.findall(text) if rid not in valid}
        for ref in refs:
            head, _, rest = ref.partition("-")
            if ref in record_ids or re.fullmatch(r"[RS]\d{2}", rest or ""):
                continue
            if rest in _item_labels(catalogue, head):
                continue  # a labelled line of the document ("R03-C2": R03 line "C2 ...")
            if (head, re.sub(r"\d+", "#", rest)) in shapes:
                bad.add(ref)
        for rid in sorted(bad):
            if any(f["location"] == where and f["match"] == rid for f in found):
                continue
            found.append(
                {
                    "flag_id": flag["flag_id"],
                    "location": where,
                    "finding_id": None if where.startswith("report.") else where,
                    "excerpt": text[:300],
                    "match": rid,
                }
            )
    return found


# The clause of a trigger for ``unless_clause_any`` (the full investigation's SF1;
# increment A's key does not carry it, so its severe flags keep ``mvp._detect_severe``):
# a negation excuses only the trigger in its own clause. The sentence is cut at
# semicolons, at contrast connectives and at "whose" ("the root causes are
# unestablished, but the GT1A bypass valve failed" still asserts the valve failure; "a
# faulty speed sensor whose origin is unknown" still asserts the sensor fault), and after
# a sentence-initial concessive clause ("Although the root cause remains unestablished,
# ST1C tripped because of a faulty speed sensor"). Colons do not cut: "Not established:
# whether a faulty sensor ..." is one claim. "And" does not cut either: "Unknown: whether
# X, and whether Y" is one claim, and wording cannot tell it from "the cause is unknown,
# and the valve failed".
_SEVERE_CLAUSE_BREAK = re.compile(
    r";|,?\s+\b(?:but|whereas|while|whilst|although|though|however|whose)\b"
)
_SEVERE_LEADING_CONCESSIVE = re.compile(
    r"^[\s*>#\u2022-]*(?:although|though|even though|while|whilst|whereas)\b[^,;]*,"
)
# A short head before a colon ("Unknown: ...", "Not established: ...") belongs to every
# semicolon part of the list after it: "Unknown: whether a failed speed sensor caused
# the ST1C trip; a bypass valve failure at GT1A".
_SEVERE_LIST_HEAD = re.compile(r"^[^:;]{1,50}?:\s")


def _severe_clause(text: str, start: int) -> str:
    """The clause of ``text`` (see ``_SEVERE_CLAUSE_BREAK``) around ``start``, with
    the sentence's list head when the clause starts after a semicolon."""
    cuts = [(m.start(), m.end()) for m in _SEVERE_CLAUSE_BREAK.finditer(text)]
    lead = _SEVERE_LEADING_CONCESSIVE.match(text)
    if lead:
        cuts.append((lead.end() - 1, lead.end()))
    a, b = 0, len(text)
    for cut_start, cut_end in sorted(cuts):
        if cut_end <= start:
            a = cut_end
        elif cut_start > start:
            b = cut_start
            break
    clause = text[a:b]
    head = _SEVERE_LIST_HEAD.match(text)
    if head is not None and a > 0 and text[a - 1] == ";":
        clause = head.group(0) + clause
    return clause


def _detect_clause_scoped(
    sub: Mapping[str, Any], flag: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """The MVP heuristic (``mvp._detect_severe``: statuses, sentence by sentence,
    ``context_any``, ``trigger_any``, sentence-wide ``unless_any``, one suspicion per
    flag and place) with ``unless_clause_any``: patterns that excuse a trigger match only
    in its own clause (``_severe_clause``). A trigger listed in ``mention_triggers`` (a
    bare mention such as "bypass valve", not an assertion) is excused by them anywhere in
    its sentence, as in increment A. A sentence whose first trigger match is excused is
    read on for a later match, of the same or a later trigger. Only the
    full-investigation key carries these fields."""
    heur = flag.get("heuristic") or {}
    statuses = heur.get("statuses")
    clause_unless = heur.get("unless_clause_any") or ()
    mentions = set(heur.get("mention_triggers") or ())
    candidates: list[tuple[str, str | None, str]] = []
    for finding in sub["findings"]:
        if statuses is None or finding["status"] in statuses:
            for sentence in mvp._sentences(finding["statement"]):
                candidates.append(
                    (finding["finding_id"], finding["finding_id"], sentence)
                )
    for path, text in mvp._report_texts(sub):
        for sentence in mvp._sentences(text):
            candidates.append((path, None, sentence))
    found: list[dict[str, Any]] = []
    for where, fid, text in candidates:
        norm = normalise(text)
        if heur.get("context_any") and not _any(norm, heur["context_any"]):
            continue
        hit = next(
            (
                m
                for p in heur.get("trigger_any", [])
                for m in mvp._rx(p).finditer(norm)
                if not _any(
                    norm if p in mentions else _severe_clause(norm, m.start()),
                    clause_unless,
                )
            ),
            None,
        )
        if hit is None or _any(norm, heur.get("unless_any", [])):
            continue
        if any(
            f["flag_id"] == flag["flag_id"] and f["location"] == where for f in found
        ):
            continue
        found.append(
            {
                "flag_id": flag["flag_id"],
                "location": where,
                "finding_id": fid,
                "excerpt": text[:300],
                "match": hit.group(0),
            }
        )
    return found


def _detect_severe(
    sub: Mapping[str, Any], key: Mapping[str, Any], catalogue: Catalogue
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for flag in key.get("severe_flags", []):
        heur = flag.get("heuristic") or {}
        if "record_id_pattern" in heur:
            found += _invented_records(sub, flag, catalogue)
        elif heur.get("unless_clause_any"):
            found += _detect_clause_scoped(sub, flag)
        else:
            found += mvp._detect_severe(sub, {"severe_flags": [flag]}, catalogue)
    return found


# -- labelling and inferential-language flags ------------------------------------------
# Hedges that make a factual finding read as a hypothesis. The nouns "hypothesis" and
# "suspicion" (and "X suspected Y") report someone's hypothesis, which a reported
# finding may do; only the agent's own verb forms count.
_LABEL_HEDGES = (
    r"\bmay\b",
    r"\bmight\b",
    r"\bpossibl",
    r"\bprobabl",
    r"\blikely\b",
    r"\bperhaps\b",
    r"\bhypothesi[sz](?:e|es|ed|ing)\b",
    r"\b(?:is|are|was|were) suspected\b",
    r"\bsuspected (?:to|that)\b",
    r"\b(?:i|we) suspect\b",
    r"\bappears? to\b",
    r"\bseems? to\b",
)
# A clause about the limits of a measurement ("1 s sampling means the true minima may
# be slightly lower", "the datum is not aligned ..., so an offset is possible") states
# an uncertainty, not a hedged claim.
_MEASUREMENT_CAVEAT = (
    r"\bsampling\b",
    r"\bbetween (?:the )?samples\b",
    r"\b\d+(?:\.\d+)? ?s (?:samples?|resolution|data)\b",
    r"\bsample (?:interval|rate|resolution|spacing)\b",
    r"\bclocks?\b",
    r"\boffsets?\b",
    r"\bdatum\b",
    r"\balign(?:ed|ment)\b",
    r"\bdigiti[sz]",
    r"\bresolution\b",
    r"\bprecision\b",
    r"\btimestamps?\b",
)
# A measurement caveat excuses a hedge only when the hedge is about the measured value
# itself ("1 s sampling means the true minima may be slightly lower", "a 0.5 s offset is
# possible"), not a claim made despite it ("given the clock offset, ST1C probably
# tripped before Hornsea"): the hedge's subject (the words before it back to the last
# comma, semicolon, colon or conjunction) must name a measured value or the caveat.
_MEASURED_VALUE = (
    r"\b(?:minim(?:um|a)|maxim(?:um|a)|nadir|lowest|highest|values?|readings?|figures?"
    r"|times?|timings?|timestamps?|instants?|offsets?|errors?|landmarks?|samples?|true"
    r"|actual|exact|precise|rocof|duration|magnitude|levels?|data)\b",
)
_HEDGE_SUBJECT_START = re.compile(
    r"(?:[,;:]\s|\b(?:so|because|means|mean|meant|that|which|and|but|while|whereas"
    r"|since|as|given|if|although|though|shows?|showed|suggests?|indicates?|implies)\b)"
)
# The subject of "suggests/indicates/implies" that makes the clause a third party's
# account: a named source or a party's document ("ESO's simulation suggests 430 MW",
# "DNO public posts indicate ...", "its simulation suggests"), not a record or the
# agent's own analysis ("the frequency record suggests", "the R01 trace indicates",
# "our analysis of the 1 s record indicates").
_THIRD_PARTY_SUBJECT = (
    r"\b(?:eso|ngeso|nget|national grid|ofgem|e3c|dnos?|elexon|rwe|ørsted|orsted|neso"
    r"|regulator|operators?|manufacturer|witness(?:es)?|s\d{2})\b",
    r"\b(?:its|their)\b",
    r"\b(?:simulations?|modell?ing|models?|stud(?:y|ies))\b",
)
_OWN_ANALYSIS = re.compile(r"\b(?:our|my|we|i)\b")


def _hedge_about_measurement(clause: str, start: int) -> bool:
    """Whether the hedge at ``start`` of a clause with a measurement caveat is about
    the measured value (see ``_MEASURED_VALUE``)."""
    before = clause[max(0, start - 100) : start]
    cuts = list(_HEDGE_SUBJECT_START.finditer(before))
    subject = before[cuts[-1].end() :] if cuts else before
    return _any(subject, _MEASURED_VALUE) or _any(subject, _MEASUREMENT_CAVEAT)


def _clauses_outside_attribution(
    statement: str, attribution: Mapping[str, Sequence[str]] | None
) -> list[str]:
    """The clauses of a statement (split at ';' and sentence ends) outside quoted spans
    that do not attribute their words to a named source (a source and an attribution
    verb in the clause; key ``conventions.inferential_attribution``)."""
    attribution = attribution or {}
    sources = tuple(attribution.get("sources") or mvp._ATTRIBUTION_SOURCES)
    verbs = tuple(attribution.get("verbs") or mvp._ATTRIBUTION_VERBS)
    text = mvp._QUOTED.sub(" ", normalise(statement))
    return [
        text[a:b]
        for a, b in mvp._spans(text, mvp._ATTRIBUTION_CLAUSE)
        if not (_any(text[a:b], sources) and _any(text[a:b], verbs))
    ]


def _labelling_flags(
    findings: Sequence[Mapping[str, Any]],
    factual: Sequence[str],
    attribution: Mapping[str, Sequence[str]] | None,
    exempt: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Factual findings whose own claim is hedged (should they be labelled hypothesis
    or unknown?). Hedges in attributed clauses and quoted spans do not count, nor do
    reports of someone's hypothesis or suspicion, nor a hedge about a measured value in
    a measurement caveat (``_hedge_about_measurement``). ``exempt`` (key
    ``conventions.labelling_exempt``; the full-investigation key only): wording whose
    hedge word is no hedge ("as soon as possible", a prohibition "may not restore ...
    without ESO instruction"); a hedge inside a match does not count."""
    out = []
    for f in findings:
        if f["status"] not in factual:
            continue
        terms: list[str] = []
        for clause in _clauses_outside_attribution(f.get("statement", ""), attribution):
            caveat = _any(clause, _MEASUREMENT_CAVEAT)
            spared = [
                m.span() for p in exempt or () for m in mvp._rx(p).finditer(clause)
            ]
            for pattern in _LABEL_HEDGES:
                for match in mvp._rx(pattern).finditer(clause):
                    if caveat and _hedge_about_measurement(clause, match.start()):
                        continue
                    if any(a <= match.start() < b for a, b in spared):
                        continue
                    if match.group(0) not in terms:
                        terms.append(match.group(0))
                    break
        if terms:
            out.append(
                {
                    "finding_id": f["finding_id"],
                    "status": f["status"],
                    "terms": terms,
                    "issue": "hedged wording with a factual status: should it be "
                    "labelled hypothesis or unknown?",
                }
            )
    return out


def _inferential_flags(
    findings: Sequence[Mapping[str, Any]],
    patterns: Sequence[str],
    attribution: Mapping[str, Sequence[str]] | None,
) -> list[dict[str, Any]]:
    """Findings labelled observed or reported whose statement reads as the agent's
    inference (MVP rule: outside quoted spans and attributed clauses), except
    "suggests / indicates / implies" whose subject is a named third party or its
    document ("its simulation suggests", "DNO public posts indicate"): that party's own
    account. A record (R01, "the frequency record", "the data") or the agent's own
    analysis as subject is still flagged. A key may list its own third-party subjects
    (``conventions.inferential_attribution.third_party_subjects``)."""
    subjects = tuple(
        (attribution or {}).get("third_party_subjects") or _THIRD_PARTY_SUBJECT
    )
    subject = re.compile(
        "(?:" + "|".join(subjects) + r")(?:'s?)?(?:\s+[\w'-]+){0,3}\s*$"
    )
    out = []
    for f in findings:
        if f["status"] not in mvp._INFERENTIAL_STATUSES:
            continue
        terms: list[str] = []
        for pattern in patterns:
            for clause in _clauses_outside_attribution(
                f.get("statement", ""), attribution
            ):
                match = mvp._rx(pattern).search(clause)
                if match is None:
                    continue
                verb = re.match(r"(?:suggest|indicat|impl)", match.group(0))
                before = clause[: match.start()]
                if (
                    verb
                    and subject.search(before)
                    and not _OWN_ANALYSIS.search(" ".join(before.split()[-6:]))
                ):
                    continue
                if match.group(0) not in terms:
                    terms.append(match.group(0))
                break
        if terms:
            out.append(
                {
                    "finding_id": f["finding_id"],
                    "status": f["status"],
                    "terms": terms,
                    "issue": f"inferential wording with status {f['status']}: is "
                    "this the agent's inference (status inferred) or a hypothesis? "
                    "Proposal for the reviewer; not scored.",
                }
            )
    return out


# -- decisions -------------------------------------------------------------------------------
load_decisions = mvp.load_decisions


def check_decisions(
    decisions: Mapping[str, Any],
    *,
    submission_sha256: str,
    key: Mapping[str, Any],
    finding_ids: Iterable[str],
    bundle_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate a decisions object (MVP rules, tasks as dimensions) and its binding;
    ``accept_judge`` must be a boolean when present."""
    if _public(decisions).get("decisions_schema") != DECISIONS_SCHEMA:
        raise DecisionsError(
            f"grading decisions rejected: decisions_schema must be {DECISIONS_SCHEMA!r}"
        )
    problems = []
    for section in ("criteria", "assertions"):
        for name, entry in (_public(decisions).get(section) or {}).items():
            if isinstance(entry, Mapping) and entry.get("accept_judge") not in (
                None,
                True,
                False,
            ):
                problems.append(f"{section}.{name}.accept_judge must be true or false")
    if problems:
        raise DecisionsError("grading decisions rejected: " + "; ".join(problems))
    translated = {**decisions, "decisions_schema": mvp.DECISIONS_SCHEMA}
    checked = mvp.check_decisions(
        translated,
        submission_sha256=submission_sha256,
        key=key,
        finding_ids=finding_ids,
        bundle_sha256=bundle_sha256,
    )
    checked["decisions_schema"] = DECISIONS_SCHEMA
    return checked


# -- resolving layered values ------------------------------------------------------------
def _capped(value: float, caps: Sequence[Mapping[str, Any]]) -> float:
    for cap in caps:
        if cap["effect"] == "zero":
            value = 0.0
        elif cap["effect"] == "cap_half":
            value = min(value, 0.5)
    return value


def _active_caps(
    caps: Sequence[Mapping[str, Any]], severe: Sequence[Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    """Caps that bound a judge proposal: accounting traps (and, for criteria the judge
    does not decide, contradictions), and suspected severe flags unless every suspicion
    of that flag is adjudicated false. Contradiction rules of a judge criterion are
    pre-screen flags (``binding`` false) and bound nothing."""
    suspected: dict[str, list[Any]] = {}
    for s in severe:
        if s.get("detected_by", "heuristic") == "heuristic":
            suspected.setdefault(s["flag_id"], []).append(s.get("confirmed"))
    rejected = {f for f, states in suspected.items() if all(c is False for c in states)}
    return [
        c
        for c in caps
        if c.get("binding", True)
        and (c.get("kind") != "severe_suspected" or c.get("flag_id") not in rejected)
    ]


def _prescreen_flags(caps: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [c for c in caps if not c.get("binding", True)]


def _resolve_row(row: dict[str, Any], severe: Sequence[Mapping[str, Any]]) -> None:
    mode = row["assessment_mode"]
    layers = row["layers"]
    auto = layers["auto"]
    judge = layers.get("judge") or {}
    human = layers.get("human") or {}
    caps = _active_caps(layers.get("caps") or [], severe)
    content: dict[str, Any] = {
        "auto_proposal": auto["content"],
        "judge_proposal": judge.get("content"),
    }
    judge_value = judge.get("content")
    capped_judge = None if judge_value is None else _capped(float(judge_value), caps)
    capped = capped_judge is not None and capped_judge < float(judge_value)
    cap_note = ""
    if capped:
        cap_note = (
            f" (judge proposed {judge_value}; capped to {capped_judge:g} by automated "
            "check(s) " + ", ".join(sorted({str(c["id"]) for c in caps})) + ")"
        )
    flagged = _prescreen_flags(layers.get("caps") or [])
    if flagged and judge_value is not None:
        cap_note += (
            "; pre-screen flag(s) for the reviewer, not applied to the judge's value: "
            + ", ".join(
                f"{c['kind']} {c['id']} ({c.get('finding_id')})" for c in flagged
            )
        )
    if human.get("content") is not None:
        content.update(value=human["content"], source="human")
        basis = "human decision"
        if (
            mode == "auto_numeric"
            and auto["decided"]
            and auto["content"] is not None
            and human["content"] != auto["content"]
        ):
            content["human_override_of_auto"] = True
    elif layers.get("severe_zero"):
        content.update(value=0, source="severe_flag")
        basis = (
            f"confirmed severe flag {', '.join(layers['severe_zero'])} sets the "
            f"content to 0 (automated check: {auto['basis']})"
        )
    elif human.get("accept_judge") and capped_judge is not None and capped:
        # A sign-off is of the value the judge proposed; when automated checks capped
        # it, the reviewer must give the value explicitly.
        content.update(value=None, source="pending", accept_judge_refused=True)
        basis = (
            "accept_judge cannot sign off a capped proposal" + cap_note + ": give an "
            "explicit content value"
        )
    elif human.get("accept_judge") and capped_judge is not None:
        content.update(value=capped_judge, source="human", signed_off_judge=True)
        basis = "human sign-off of the judge proposal" + cap_note
    elif mode == "auto_numeric" and auto["decided"]:
        content.update(value=auto["content"], source="auto")
        basis = auto["basis"]
    elif mode == "judge" and capped_judge is not None:
        content.update(value=capped_judge, source="judge")
        basis = f"judge proposal{cap_note}: {judge.get('rationale') or ''}".rstrip(": ")
    else:
        content.update(value=None, source="pending")
        basis = auto["basis"]
        if mode == "judge" and not judge:
            basis = "awaiting the judge (automated pre-screen: " + auto["basis"] + ")"
    content["basis"] = basis
    row["content"] = content

    auto_ev = layers["auto_evidence"]
    judge_ev = layers.get("judge_evidence") or None
    constrained = bool(judge_ev and judge_ev.get("constraint"))
    effective = judge_ev if constrained else auto_ev
    evidence: dict[str, Any] = {
        "auto_proposal": effective.get("proposal"),
        "judge_proposal": (judge_ev or {}).get("value"),
    }
    judge_usable = (
        mode == "judge"
        and judge_ev is not None
        and not judge_ev.get("decided")
        and judge_ev.get("value") is not None
        and (constrained or not auto_ev.get("decided"))
    )
    value = content["value"]
    if value == 0 and content["source"] != "pending":
        if human.get("evidence_support") is not None:
            evidence.update(
                value=human["evidence_support"],
                source="human",
                basis=effective["basis"],
            )
        else:
            evidence.update(
                value=None,
                source="not_applicable",
                basis=effective["basis"]
                if effective.get("not_applicable")
                else "content is 0",
            )
    elif human.get("evidence_support") is not None:
        evidence.update(
            value=human["evidence_support"], source="human", basis=effective["basis"]
        )
    elif human.get("accept_judge") and judge_usable:
        evidence.update(
            value=judge_ev["value"],
            source="human",
            signed_off_judge=True,
            basis="human sign-off of the judge proposal: " + judge_ev["basis"],
        )
    elif constrained and judge_ev.get("decided"):
        evidence.update(value=judge_ev["value"], source="auto", basis=judge_ev["basis"])
    elif judge_usable:
        evidence.update(
            value=judge_ev["value"], source="judge", basis=judge_ev["basis"]
        )
    elif effective.get("not_applicable"):
        if content["source"] == "pending":
            evidence.update(
                value=None, source="not_applicable", basis=effective["basis"]
            )
        else:
            evidence.update(
                value=None,
                source="pending",
                basis="content is credited but no finding matched automatically: "
                "evidence support needs a decision (list the credited finding_ids so "
                "that their citations can be checked)",
            )
    elif effective.get("decided"):
        evidence.update(
            value=effective["value"], source="auto", basis=effective["basis"]
        )
    else:
        evidence.update(value=None, source="pending", basis=effective["basis"])
    row["evidence_support"] = evidence


def _resolve_assertion(entry: dict[str, Any]) -> None:
    """The verdict of one assertion from its layers. An automated numeric check that
    contradicts the finding (an in-window structured value out of tolerance) bounds the
    judge: a judge verdict of 'supported' then becomes a conflict for a human (also
    when signed off with accept_judge) instead of a verdict (decision 15: automated
    checks are authoritative for numbers)."""
    layers = entry.get("layers") or {}
    human = layers.get("human") or {}
    judge = layers.get("judge") or {}
    numeric = layers.get("auto_numeric") or {}
    for name in ("verdict", "source", "signed_off_judge", "duplicate_of", "conflict"):
        entry.pop(name, None)
    conflict = (
        numeric.get("verdict") == "contradicted" and judge.get("verdict") == "supported"
    )
    conflict_note = {
        "judge_verdict": judge.get("verdict"),
        "auto_numeric_verdict": numeric.get("verdict"),
        "auto_numeric_basis": numeric.get("basis"),
        "note": "the judge's 'supported' conflicts with an automated numeric check "
        "that contradicts the finding: a human gives the verdict",
    }
    if human.get("duplicate_of"):
        entry.update(
            verdict=None, source="duplicate", duplicate_of=human["duplicate_of"]
        )
    elif human.get("verdict") is not None:
        entry.update(verdict=human["verdict"], source="human")
    elif human.get("accept_judge") and judge.get("verdict") is not None and conflict:
        entry.update(verdict=None, source="pending", conflict=conflict_note)
    elif human.get("accept_judge") and judge.get("verdict") is not None:
        entry.update(verdict=judge["verdict"], source="human", signed_off_judge=True)
    elif layers.get("severe_flags"):
        entry.update(verdict=layers["severe_verdict"], source="severe_flag")
    elif not entry.get("factual"):
        entry.update(verdict=None, source="labelled_hypothesis_or_unknown")
    elif conflict:
        entry.update(verdict=None, source="pending", conflict=conflict_note)
    elif judge.get("verdict") is not None:
        entry.update(verdict=judge["verdict"], source="judge")
    else:
        entry.update(verdict=None, source="pending")
    entry["judge_proposal"] = judge.get("verdict")


def _tally(items: list[dict[str, Any]]) -> dict[str, Any]:
    counted = [
        a for a in items if a["source"] in ("human", "judge", "pending", "severe_flag")
    ]
    out: dict[str, Any] = {
        v: sum(1 for a in counted if a["verdict"] == v) for v in VERDICTS
    }
    out["by_source"] = {
        s: sum(1 for a in items if a["source"] == s)
        for s in (
            "human",
            "judge",
            "severe_flag",
            "pending",
            "duplicate",
            "labelled_hypothesis_or_unknown",
        )
    }
    out["pending"] = out["by_source"]["pending"]
    decided = sum(out[v] for v in VERDICTS)
    human = [a for a in counted if a["source"] in ("human", "severe_flag")]
    human_decided = sum(1 for a in human if a["verdict"] in VERDICTS)
    if decided == 0:
        out["precision"] = None
        out["precision_note"] = (
            "undefined: no factual assertions"
            if not counted
            else "undefined: all pending"
        )
    else:
        out["precision"] = round(out["supported"] / decided, 4)
        notes = []
        if out["pending"]:
            notes.append("over decided assertions only")
        if out["by_source"]["judge"]:
            notes.append(
                f"includes {out['by_source']['judge']} judge proposal(s) awaiting human "
                "sign-off"
            )
        out["precision_note"] = "; ".join(notes) or "all assertions decided by humans"
    out["precision_human_only"] = (
        round(sum(1 for a in human if a["verdict"] == "supported") / human_decided, 4)
        if human_decided
        else None
    )
    return out


def _finalise(
    report: dict[str, Any], severe_status: Sequence[Mapping[str, Any]]
) -> None:
    """Resolve every row and assertion from its layers, then recompute the per-task
    measures, the flags that depend on them and the report status."""
    for row in report["criteria"]:
        _resolve_row(row, severe_status)
    for entry in report["assertion_quality"]["assertions"]:
        _resolve_assertion(entry)
    tasks = report["tasks"]
    coverage: dict[str, Any] = {}
    support: dict[str, Any] = {}
    by_handoff: dict[str, Any] = {}
    for task in tasks:
        rows = [c for c in report["criteria"] if c["task"] == task]
        sources = {c["criterion_id"]: c["content"]["source"] for c in rows}
        signed = [c for c in rows if c["content"]["source"] in SIGNED]
        judged = [c for c in rows if c["content"]["source"] == "judge"]
        coverage[task] = {
            "criteria": len(rows),
            "by_source": {
                s: sum(1 for v in sources.values() if v == s)
                for s in ("auto", "judge", "human", "severe_flag", "pending")
            },
            "decided_content_sum": sum(c["content"]["value"] for c in signed),
            "decided_content_max": len(signed),
            "judge_proposed_content_sum": sum(c["content"]["value"] for c in judged),
            "judge_proposed_content_max": len(judged),
            "by_criterion": {c["criterion_id"]: c["content"]["value"] for c in rows},
            "sources": sources,
            "auto_proposals": {
                c["criterion_id"]: c["content"]["auto_proposal"] for c in rows
            },
            "judge_proposals": {
                c["criterion_id"]: c["content"]["judge_proposal"] for c in rows
            },
        }
        support[task] = {
            "criteria": len(rows),
            "supported": sum(1 for c in rows if c["evidence_support"]["value"] == 1),
            "unsupported": sum(
                1
                for c in rows
                if c["evidence_support"]["value"] == 0
                and c["evidence_support"]["source"] in ("auto", "human", "judge")
            ),
            "by_source": {
                s: sum(1 for c in rows if c["evidence_support"]["source"] == s)
                for s in ("auto", "judge", "human", "pending", "not_applicable")
            },
            "by_criterion": {
                c["criterion_id"]: c["evidence_support"]["value"] for c in rows
            },
            "sources": {
                c["criterion_id"]: c["evidence_support"]["source"] for c in rows
            },
            "auto_proposals": {
                c["criterion_id"]: c["evidence_support"]["auto_proposal"] for c in rows
            },
        }
        for c in rows:
            parent = c["task_criterion"]
            entry = by_handoff.setdefault(
                parent, {"task": task, "fields": {}, "value": None, "sources": []}
            )
            entry["fields"][c["criterion_id"]] = {
                "subweight": c["subweight"],
                "content": c["content"]["value"],
                "source": c["content"]["source"],
            }
    for entry in by_handoff.values():
        fields = entry["fields"].values()
        entry["sources"] = sorted({f["source"] for f in fields})
        if all(f["content"] is not None for f in fields):
            entry["value"] = round(
                sum(f["subweight"] * f["content"] for f in fields), 4
            )
    report["content_coverage"] = {
        "by_task": coverage,
        "by_handoff_criterion": by_handoff,
        "note": "by_handoff_criterion combines a criterion's fields with their equal "
        "subweights once every field has a value (judge proposals included, see "
        "'sources'); no task total or overall score is computed",
    }
    report["evidence_support"] = {"by_task": support}
    assertions = report["assertion_quality"]["assertions"]
    report["assertion_quality"]["by_task"] = {
        task: _tally([a for a in assertions if a["dimension"] == task])
        for task in tasks + ["unassigned"]
    }
    report["assertion_quality"]["counts_all_tasks"] = {
        k: v
        for k, v in _tally(assertions).items()
        if k not in ("precision", "precision_note", "precision_human_only")
    }
    needs_review = []
    for c in report["criteria"]:
        if c["content"]["source"] in ("pending", "judge") or c["evidence_support"][
            "source"
        ] in ("pending", "judge"):
            needs_review.append(
                {
                    "criterion_id": c["criterion_id"],
                    "content": c["content"]["source"],
                    "evidence_support": c["evidence_support"]["source"],
                }
            )
    report["flags"]["needs_human_review"] = needs_review
    report["flags"]["prescreen_contradictions"] = [
        {
            "criterion_id": c["criterion_id"],
            "id": cap["id"],
            "finding_id": cap.get("finding_id"),
            "effect_on_prescreen": cap.get("effect"),
            "note": cap.get("note"),
        }
        for c in report["criteria"]
        for cap in _prescreen_flags(c["layers"].get("caps") or [])
    ]
    report["flags"]["assertion_conflicts"] = [
        {"assertion_id": a["assertion_id"], **a["conflict"]}
        for a in assertions
        if a.get("conflict")
    ]

    reasons: list[str] = []
    review_status = report["key"]["review_status"]
    if review_status != "reviewed":
        reasons.append(
            f"answer key review status is {review_status!r} (not 'reviewed')"
        )
    pending = [
        c["criterion_id"]
        for c in report["criteria"]
        if "pending" in (c["content"]["source"], c["evidence_support"]["source"])
    ]
    if pending:
        reasons.append(f"{len(pending)} criteria await a decision")
    judged = [
        c["criterion_id"]
        for c in report["criteria"]
        if "judge" in (c["content"]["source"], c["evidence_support"]["source"])
    ]
    if judged:
        reasons.append(
            f"{len(judged)} criteria carry judge proposals awaiting human sign-off"
        )
    open_assertions = [a for a in assertions if a["source"] == "pending"]
    if open_assertions:
        reasons.append(f"{len(open_assertions)} assertions await verdicts")
    conflicted = [a for a in assertions if a.get("conflict")]
    if conflicted:
        reasons.append(
            f"{len(conflicted)} judge verdicts conflict with automated numeric checks "
            "(a human gives the verdict)"
        )
    refused = [
        c["criterion_id"]
        for c in report["criteria"]
        if c["content"].get("accept_judge_refused")
    ]
    if refused:
        reasons.append(
            f"accept_judge cannot sign off capped proposals ({', '.join(refused)}): "
            "give explicit content values"
        )
    judge_assertions = [a for a in assertions if a["source"] == "judge"]
    if judge_assertions:
        reasons.append(
            f"{len(judge_assertions)} assertion verdicts are judge proposals awaiting "
            "human sign-off"
        )
    flags_open = [s for s in report["severe_flags"] if s["confirmed"] is None]
    if flags_open:
        reasons.append(
            f"{len(flags_open)} suspected severe assertions await adjudication"
        )
    decisions = report.get("decisions")
    if decisions is None:
        reasons.append("no grading-decisions file applied")
    elif decisions.get("builder_fixture"):
        reasons.append("the decisions file is a builder fixture, not a domain review")
    if report.get("trace") is None:
        reasons.append("no episode trace: retrieval was not checked")
    if not report["bundle"].get("matches_key"):
        reasons.append(
            "the answer key is bound to another bundle than the one graded: its "
            "evidence locators do not apply"
        )
    if report["explanation_quality"]["source"] != "human":
        reasons.append(
            "explanation quality not reviewed (no non-empty explanation_quality notes)"
        )
    reasons += list(report.get("integrity_notes") or [])
    report["status"] = "provisional" if reasons else "final"
    report["provisional_reasons"] = reasons


# -- assembling ---------------------------------------------------------------------------
def _criterion_evidence_layer(evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "value": evidence.get("value"),
        "decided": bool(evidence.get("decided")),
        "proposal": evidence.get("proposal"),
        "basis": evidence.get("basis"),
        "not_applicable": bool(evidence.get("not_applicable")),
    }


# A clock label written after a time range applies to both ends ("between 15:58 and
# 16:16 UTC", "15:58-16:16Z"): the MVP time reader would take the first end as BST.
_TIME = r"\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
_LABELLED_RANGE = re.compile(
    rf"(?<![\d:.])({_TIME})(\s*(?:-|–|—|to|and|until|till|through)\s*)({_TIME})"
    r"(\s?(?:utc|gmt|bst)\b|z\b)",
    re.IGNORECASE,
)


def _label_time_ranges(text: str) -> str:
    return _LABELLED_RANGE.sub(
        lambda m: f"{m.group(1)}{m.group(4)}{m.group(2)}{m.group(3)}{m.group(4)}", text
    )


def _labelled_finding(finding: Mapping[str, Any]) -> dict[str, Any]:
    """A finding as the time and value readers see it (time-range labels applied to
    the statement and derivation); the submission itself is not changed."""
    out = dict(finding)
    for name in ("statement", "derivation"):
        if isinstance(out.get(name), str):
            out[name] = _label_time_ranges(out[name])
    return out


def _ctx_for(
    sub: Mapping[str, Any],
    key: Mapping[str, Any],
    catalogue: Catalogue,
    citations: dict[str, list[SRCitationCheck]],
    trace_info: Mapping[str, Any] | None,
    severe: list[dict[str, Any]],
    element_types: Mapping[str, Callable[..., dict[str, Any]]] | None = None,
) -> _SRCtx:
    conv = key.get("conventions", {})
    findings = [_labelled_finding(f) for f in sub["findings"]]
    return _SRCtx(
        element_types=dict(element_types or {}),
        submission=sub,
        findings=findings,
        key=key,
        catalogue=catalogue,
        citations=citations,  # type: ignore[arg-type]
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
        order={f["finding_id"]: i for i, f in enumerate(findings)},
        entities=conv.get("entities", {}),
        masks=tuple(conv.get("entity_masks", ())),
        report=[
            (location, normalise(sentence))
            for location, text in mvp._report_texts(sub)
            for sentence in mvp._sentences(_label_time_ranges(text))
        ],
        hedges=tuple(conv.get("mechanism_hedge_patterns") or mvp._HEDGES),
        negations=tuple(
            conv.get("mechanism_negation_patterns") or mvp._MECHANISM_NEGATIONS
        ),
        hedged_statuses=tuple(conv.get("mechanism_hedged_statuses", ("hypothesis",))),
        accounting=sr_accounting.analyse(
            sub, mvp._report_texts(sub), key.get("accounting") or {}
        ),
    )


def grade_submission(
    submission: Any,
    catalogue: Catalogue | None = None,
    key: Mapping[str, Any] | None = None,
    trace_info: Mapping[str, Any] | None = None,
    decisions: Mapping[str, Any] | Path | str | None = None,
    judge_output: Mapping[str, Any] | Path | str | None = None,
    *,
    element_types: Mapping[str, Callable[..., dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Grade one valid v3 submission against the system-response key.

    ``trace_info`` comes from :func:`trace_info_from_episode` (``None``: retrieval not
    checked); ``decisions`` is a grading-decisions object or path; ``judge_output`` a
    judge output to merge (see :func:`merge_judge_proposals`). ``element_types`` adds
    element evaluators for another task's key (``type`` -> ``evaluate(el, ctx)``; the
    full investigation's grader, :mod:`.fi_grading`, uses it); the system-response key
    needs none."""
    catalogue = catalogue or Catalogue.load(SYSTEM_RESPONSE_BUNDLE_DIR)
    key = key if key is not None else load_key()
    sub, sub_sha = mvp._as_submission(submission, catalogue)
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
    citations = check_citations(findings, catalogue, trace_info)
    ctx = _ctx_for(sub, key, catalogue, citations, trace_info, severe, element_types)
    human_criteria = {
        k: _public(v) for k, v in ((dec or {}).get("criteria") or {}).items()
    }

    # -- severe flags (first: confirmed flags have effects) -----------------------------
    adjudications = [_public(a) for a in (dec or {}).get("severe_flags") or []]

    def adjudicates(decision: Mapping[str, Any], item: Mapping[str, Any]) -> bool:
        if decision.get("flag_id") != item["flag_id"]:
            return False
        if item.get("finding_id") and item["finding_id"] in (
            decision.get("finding_ids") or []
        ):
            return True
        return item.get("location") in (decision.get("locations") or [])

    severe_out = []
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
        if (
            not any(adjudicates(decision, s) for s in severe)
            and decision.get("confirmed") is not None
        ):
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
    flags_by_id = {f["flag_id"]: f for f in key.get("severe_flags", [])}
    flagged_findings: dict[str, list[str]] = {}
    zeroed: dict[str, list[str]] = {}
    for item in severe_out:
        if item["confirmed"] is not True:
            continue
        fids = [item.get("finding_id")] + list(item.get("finding_ids") or [])
        for fid in fids:
            if fid in ctx.order and item["flag_id"] not in flagged_findings.setdefault(
                fid, []
            ):
                flagged_findings[fid].append(item["flag_id"])
        # ``zero_content_at`` (optional; not in increment A's key): criteria a
        # confirmed flag zeroes only when it was found at one of these locations (a
        # flag a reviewer adds without a location zeroes them too)
        zero_at = (flags_by_id[item["flag_id"]].get("effect") or {}).get(
            "zero_content_at"
        ) or {}
        for cid in mvp._flag_effect(flags_by_id[item["flag_id"]])["zero_content"]:
            if cid in zero_at and item.get("location") not in [
                *zero_at[cid],
                "reviewer",
            ]:
                continue
            if item["flag_id"] not in zeroed.setdefault(cid, []):
                zeroed[cid].append(item["flag_id"])

    # -- criteria ---------------------------------------------------------------------------
    rows: list[dict[str, Any]] = []
    assessments: dict[str, Mapping[str, Any]] = {}
    finding_tasks: dict[str, dict[str, int]] = {fid: {} for fid in finding_ids}
    proposals: dict[str, tuple[str, str]] = {}
    numeric_contradictions: dict[str, str] = {}
    conflicts_all: list[dict[str, Any]] = []
    for crit in key["criteria"]:
        cid = crit["criterion_id"]
        mode = crit["assessment_mode"]
        kind = (crit.get("auto") or {}).get("kind")
        assessment = _assess_criterion(crit, ctx)
        assessments[cid] = assessment
        check = (crit.get("auto") or {}).get("convention_check")
        note = mvp._convention_note(check, assessments, ctx) if check else None
        if note:
            assessment = {**assessment, "basis": f"{assessment['basis']}; {note}"}
        evidence = _assess_evidence(_evidence_view(crit, assessment), assessment, ctx)
        human = human_criteria.get(cid, {})
        human_fids = [f for f in human.get("finding_ids") or [] if f in ctx.order]
        if (
            (human.get("content") or 0) > 0
            and human_fids
            and (
                evidence.get("not_applicable")
                or (
                    kind in ("landmark", "duration")
                    and human_fids != assessment["matched_finding_ids"]
                )
            )
        ):
            evidence = _assess_evidence(
                _evidence_view(crit, assessment),
                {**assessment, "matched_finding_ids": human_fids, "content": 1},
                ctx,
            )
            evidence["basis"] = "on the reviewer's finding_ids: " + evidence["basis"]
        decided = mode == "auto_numeric" and assessment.get("decided", True)
        unrouted = set(assessment.get("unrouted_finding_ids") or ())
        for fid in (
            assessment.get("considered_finding_ids")
            or assessment["matched_finding_ids"]
        ):
            counts = finding_tasks[fid]
            weight = 3 if fid in assessment["matched_finding_ids"] else 1
            if fid in unrouted:
                # only referred to (e.g. by the executive summary): the task is kept
                # among the finding's tasks but routes it only when no other task does
                weight = 0
            counts[crit["task"]] = counts.get(crit["task"], 0) + weight
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
                else:
                    verdict = None
                if verdict:
                    proposals.setdefault(
                        cand["finding_id"], (verdict, f"{cid}: {assessment['basis']}")
                    )
                if verdict == "contradicted":
                    numeric_contradictions.setdefault(
                        cand["finding_id"], f"{cid}: {assessment['basis']}"
                    )
        for hit in assessment.get("contradictions", []):
            proposals[hit["finding_id"]] = ("contradicted", f"{cid}: {hit['note']}")
        for conflict in assessment.get("conflicts", []):
            conflicts_all.append({"criterion_id": cid, **conflict})
        rows.append(
            {
                "criterion_id": cid,
                "task": crit["task"],
                "task_criterion": crit.get("task_criterion", cid),
                "field": crit.get("field"),
                "subweight": crit.get("subweight", 1),
                "dimension": crit["dimension"],
                "title": crit["title"],
                "assessment_mode": mode,
                "polarity": crit.get("polarity", "positive"),
                "origin": crit.get("origin", "handoff"),
                "matched_finding_ids": assessment["matched_finding_ids"],
                "human_finding_ids": human.get("finding_ids"),
                "human_notes": human.get("notes"),
                "judge_finding_ids": None,
                "layers": {
                    "auto": {
                        "content": assessment["content"],
                        "decided": bool(decided),
                        "basis": assessment["basis"],
                    },
                    "auto_evidence": _criterion_evidence_layer(evidence),
                    "judge": None,
                    "judge_evidence": None,
                    "human": {
                        k: human.get(k)
                        for k in (
                            "content",
                            "evidence_support",
                            "accept_judge",
                            "notes",
                        )
                    }
                    if human
                    else None,
                    "severe_zero": zeroed.get(cid, []),
                    "caps": assessment.get("caps", []),
                },
                "auto_checks": {
                    "elements": assessment.get("elements", []),
                    "candidates": assessment.get("candidates", []),
                    "other_candidates": assessment.get("other_candidates", []),
                    "contradictions": assessment.get("contradictions", []),
                    "caps": assessment.get("caps", []),
                    "conflicts": assessment.get("conflicts", []),
                    "evidence_citations": evidence["citations"],
                },
            }
        )

    # every citation: which criteria's primary keyed spans it targets
    by_id = {c["criterion_id"]: c for c in key["criteria"]}
    for checks in citations.values():
        for check in checks:
            for cid, crit in by_id.items():
                if any(
                    k.get("role", "primary") == "primary"
                    and _overlaps(check, k, catalogue)
                    and _targets(check, k, catalogue)
                    for k in crit.get("visible_evidence", [])
                ):
                    check.targets_keyed.append(cid)

    # accounting traps as assertion proposals
    accounting = ctx.accounting or sr_accounting.AccountingResult()
    for trap in accounting.traps:
        fid = trap.get("finding_id")
        if fid and fid in ctx.order and fid not in proposals:
            verdict = "unsupported" if trap["type"] == "overlap_sum" else "contradicted"
            proposals[fid] = (
                verdict,
                f"accounting: {trap['type']} "
                f"{trap.get('figure_id') or trap.get('group') or ''}".strip(),
            )
    flag_tasks = {
        f["flag_id"]: sorted(
            {_task_of(c) for c in f.get("applies_to", []) if c != "all"}
        )
        for f in key.get("severe_flags", [])
    }
    for item in severe:
        if item["finding_id"]:
            proposals[item["finding_id"]] = (
                "unsupported",
                f"suspected {item['flag_id']}",
            )
            for task in flag_tasks.get(item["flag_id"], []):
                counts = finding_tasks[item["finding_id"]]
                counts[task] = counts.get(task, 0) + 3

    # -- assertions ---------------------------------------------------------------------------
    human_assertions = {
        k: _public(v) for k, v in ((dec or {}).get("assertions") or {}).items()
    }
    assertions = []
    for finding in findings:
        fid = finding["finding_id"]
        counts = finding_tasks[fid]
        tasks_matched = sorted(counts)
        auto_task = (
            min(tasks_matched, key=lambda t: (-counts[t], t))
            if tasks_matched
            else "unassigned"
        )
        human = human_assertions.get(fid, {})
        proposal = proposals.get(fid)
        flagged = flagged_findings.get(fid)
        entry = {
            "assertion_id": fid,
            "kind": "finding",
            "status": finding["status"],
            "factual": finding["status"] in ctx.factual,
            "dimension": human.get("dimension") or auto_task,
            "dimensions_matched": tasks_matched,
            "cited": bool(finding.get("citations")),
            "auto_proposal": proposal[0] if proposal else None,
            "auto_basis": proposal[1] if proposal else None,
            "layers": {
                "human": human or None,
                "judge": None,
                "auto_numeric": {
                    "verdict": "contradicted",
                    "basis": numeric_contradictions[fid],
                }
                if fid in numeric_contradictions
                else None,
                "severe_flags": flagged or [],
                "severe_verdict": mvp._flag_effect(flags_by_id[flagged[0]])["verdict"]
                if flagged
                else None,
            },
        }
        if flagged:
            entry["confirmed_severe_flags"] = flagged
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
                "auto_proposal": None,
                "layers": {"human": human, "judge": None, "severe_flags": []},
                "notes": human.get("notes"),
            }
        )

    # -- flags ---------------------------------------------------------------------------------
    all_checks = [c for fid in finding_ids for c in citations[fid]]
    referenced = set()
    for _, text in mvp._report_texts(sub):
        referenced.update(extract_references(text))
    labelling = _labelling_flags(
        findings,
        ctx.factual,
        conv.get("inferential_attribution"),
        conv.get("labelling_exempt"),
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
            {
                f"{c.evidence_id} {c.normalized or c.locator}"
                for c in all_checks
                if c.retrieved is False
            }
        )
        if trace_info is not None
        else None,
        "cited_but_never_retrieved_findings": sorted(
            {c.finding_id for c in all_checks if c.retrieved is False}
        )
        if trace_info is not None
        else None,
        "records_cited_via_document_only": sorted(
            {
                f"{c.evidence_id} {c.normalized}"
                for c in all_checks
                if c.routes == ["document"]
            }
        ),
        "suspected_severe_assertions": severe,
        "labelling": labelling,
        "status_inferential_language": _inferential_flags(
            findings,
            tuple(conv.get("inferential_patterns") or mvp._INFERENTIAL),
            conv.get("inferential_attribution"),
        ),
        "labelled_hypotheses": [
            f["finding_id"] for f in findings if f["status"] == "hypothesis"
        ],
        "labelled_unknowns": [
            f["finding_id"] for f in findings if f["status"] == "unknown"
        ],
        "accounting_traps": accounting.traps,
        "conflicting_values": conflicts_all,
        "findings_not_referenced_in_report": [
            fid for fid in finding_ids if fid not in referenced
        ],
        "needs_human_review": [],
    }
    explanation = (dec or {}).get("explanation_quality") or {}
    explanation_reviewed = mvp._explanation_reviewed(explanation, _tasks(key))
    key_bundle = (key.get("bundle") or {}).get("bundle_sha256")
    report: dict[str, Any] = {
        "grade_schema": GRADE_SCHEMA,
        "grader_version": GRADER_VERSION,
        "status": "provisional",
        "provisional_reasons": [],
        "interpretation": INTERPRETATION,
        "key": {
            "key_id": key.get("key_id"),
            "key_version": key.get("key_version"),
            "review_status": _review_status(key),
            "key_sha256": key_sha256(key),
        },
        "bundle": {
            "bundle_id": catalogue.bundle_id,
            "bundle_version": catalogue.bundle_version,
            "bundle_sha256": catalogue.bundle_sha256,
            "matches_key": catalogue.bundle_sha256 == key_bundle,
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
        "judge": None,
        "trace": None
        if trace_info is None
        else {
            k: trace_info.get(k)
            for k in (
                "retrieved",
                "document_routes",
                "records_by_kind",
                "r01_analysed_with_python",
                "calls_used",
                "frozen_at_request_id",
            )
        },
        "tasks": _tasks(key),
        "deferred_criteria": key.get("deferred_criteria", []),
        "content_coverage": {},
        "evidence_support": {},
        "assertion_quality": {"assertions": assertions},
        "severe_flags": severe_out,
        "severe_flag_ids": [f["flag_id"] for f in key.get("severe_flags", [])],
        "accounting_basis": {
            **accounting.to_dict(),
            "note": "figures named in the submission, classified by the basis they are "
            "given on; traps are proposals for the reviewer (see flags.accounting_traps)",
        },
        "explanation_quality": {
            "notes": explanation.get("notes"),
            "by_dimension": explanation.get("by_dimension") or {},
            "source": "human" if explanation_reviewed else "pending",
        },
        "criteria": rows,
        "citations": [c.to_dict() for c in all_checks],
        "flags": flags,
        "integrity_notes": [],
    }
    if judge_output is not None:
        return merge_judge_proposals(report, judge_output)
    _finalise(report, severe_out)
    return report


# -- judge proposals ------------------------------------------------------------------------
def criterion_rubric(
    criterion_id: str,
    *,
    key: Mapping[str, Any] | None = None,
    catalogue: Catalogue | None = None,
) -> dict[str, Any]:
    """What the judge may see about one criterion: its expectation, scale, examples,
    accounting basis and the text of its keyed visible-evidence spans (never the
    report passages of the builder-only sources)."""
    key = key if key is not None else load_key()
    catalogue = catalogue or Catalogue.load(SYSTEM_RESPONSE_BUNDLE_DIR)
    crit = next(c for c in key["criteria"] if c["criterion_id"] == criterion_id)
    spans = []
    for keyed in crit.get("visible_evidence", []):
        try:
            text = resolve_text(catalogue, keyed["evidence_id"], keyed["locator"])
        except LocatorError as exc:
            text = f"(unresolvable: {exc})"
        spans.append(
            {
                "evidence_id": keyed["evidence_id"],
                "locator": keyed["locator"],
                "role": keyed.get("role", "primary"),
                "text": text,
            }
        )
    conv = key.get("conventions", {})
    return {
        "criterion_id": crit["criterion_id"],
        "task": crit["task"],
        "title": crit["title"],
        "assessment_mode": crit["assessment_mode"],
        "polarity": crit.get("polarity", "positive"),
        "expectation": crit["expectation"],
        "expected": _without_reviewer_notes(crit.get("expected")),
        "accounting_basis": crit.get("accounting_basis"),
        "content_scale": conv.get("content_scale"),
        "evidence_support_scale": conv.get("evidence_support_scale"),
        "examples": _without_reviewer_notes(crit["examples"]),
        "keyed_spans": spans,
    }


_REVIEWER_ONLY = frozenset({"prescreen", "reviewer_note"})


def _without_reviewer_notes(value: Any) -> Any:
    """``value`` without the key's reviewer-only fields (an example's automated
    pre-screen value; builder notes naming live runs, MVP criteria or the pre-screen)."""
    if isinstance(value, Mapping):
        return {
            k: _without_reviewer_notes(v)
            for k, v in value.items()
            if k not in _REVIEWER_ONLY
        }
    if isinstance(value, list):
        return [_without_reviewer_notes(v) for v in value]
    return value


def cited_spans(
    submission: Any, catalogue: Catalogue | None = None
) -> dict[str, list[dict[str, Any]]]:
    """The resolved text of every citation of a submission, by finding (for the judge:
    it sees the cited spans, not whole documents)."""
    catalogue = catalogue or Catalogue.load(SYSTEM_RESPONSE_BUNDLE_DIR)
    sub, _ = mvp._as_submission(submission, catalogue)
    out: dict[str, list[dict[str, Any]]] = {}
    for f in sub["findings"]:
        items = []
        for c in f.get("citations") or []:
            item = {"evidence_id": c["evidence_id"], "locator": c["locator"]}
            try:
                item["text"] = resolve_text(catalogue, c["evidence_id"], c["locator"])
            except LocatorError as exc:
                item["error"] = str(exc)
            items.append(item)
        out[f["finding_id"]] = items
    return out


def _load_judge(judge_output: Mapping[str, Any] | Path | str) -> dict[str, Any]:
    if isinstance(judge_output, (str, Path)):
        try:
            judge_output = json.loads(Path(judge_output).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise JudgeOutputError(f"cannot read judge output: {exc}") from None
    if not isinstance(judge_output, Mapping):
        raise JudgeOutputError("a judge output must be a JSON object")
    return dict(judge_output)


def _check_judge(judge: Mapping[str, Any], report: Mapping[str, Any]) -> list[str]:
    problems = []
    if judge.get("judge_schema") != JUDGE_SCHEMA:
        problems.append(f"judge_schema must be {JUDGE_SCHEMA!r}")
    for name in ("judge_model", "rubric_version"):
        if not isinstance(judge.get(name), str) or not judge[name].strip():
            problems.append(f"{name} is required")
    binding = judge.get("binding") or {}
    expected = {
        "submission_sha256": report["submission"]["sha256"],
        "key_version": report["key"]["key_version"],
        "key_sha256": report["key"]["key_sha256"],
        "bundle_sha256": report["bundle"]["bundle_sha256"],
    }
    for name, value in expected.items():
        if binding.get(name) != value:
            problems.append(f"binding.{name} does not match the graded {name}")
    known = {c["criterion_id"] for c in report["criteria"]}
    finding_ids = {
        a["assertion_id"]
        for a in report["assertion_quality"]["assertions"]
        if a["kind"] == "finding"
    }
    criteria = judge.get("criteria") or {}
    if not isinstance(criteria, Mapping):
        problems.append("criteria must be an object")
        criteria = {}
    for cid, entry in criteria.items():
        if cid not in known:
            problems.append(f"criteria.{cid}: unknown criterion")
            continue
        if not isinstance(entry, Mapping):
            problems.append(f"criteria.{cid}: must be an object")
            continue
        if entry.get("content") is not None and entry["content"] not in CONTENT_VALUES:
            problems.append(f"criteria.{cid}.content must be 1, 0.5, 0 or null")
        if (
            entry.get("evidence_support") is not None
            and entry["evidence_support"] not in EVIDENCE_VALUES
        ):
            problems.append(f"criteria.{cid}.evidence_support must be 1, 0 or null")
        for fid in entry.get("finding_ids") or []:
            if fid not in finding_ids:
                problems.append(f"criteria.{cid}.finding_ids: unknown finding {fid!r}")
    assertions = judge.get("assertions") or {}
    if not isinstance(assertions, Mapping):
        problems.append("assertions must be an object")
        assertions = {}
    tasks = set(report["tasks"])
    for aid, entry in assertions.items():
        if not isinstance(entry, Mapping):
            problems.append(f"assertions.{aid}: must be an object")
            continue
        if entry.get("verdict") is not None and entry["verdict"] not in VERDICTS:
            problems.append(
                f"assertions.{aid}.verdict must be one of {VERDICTS} or null"
            )
        if aid not in finding_ids and not str(entry.get("text") or "").strip():
            problems.append(f"assertions.{aid}: a report-only assertion needs 'text'")
        if entry.get("task") is not None and entry["task"] not in tasks:
            problems.append(f"assertions.{aid}.task: unknown task")
    flag_ids = set(report.get("severe_flag_ids") or ()) | {
        f["flag_id"] for f in report["severe_flags"]
    }
    for index, entry in enumerate(judge.get("severe_flags") or []):
        if not isinstance(entry, Mapping) or entry.get("flag_id") not in flag_ids:
            problems.append(f"severe_flags[{index}]: unknown flag_id")
    return problems


def _citation_index(report: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    index: dict[str, list[Mapping[str, Any]]] = {}
    for c in report.get("citations") or []:
        index.setdefault(c["finding_id"], []).append(c)
    return index


_LINES_LOCATOR = re.compile(r"^L(\d+)(?:-L(\d+))?$")
_ROWS_LOCATOR = re.compile(r"^rows?:(\d+)(?:-(\d+))?$")


def _span_matches_citation(
    span: Mapping[str, Any], citation: Mapping[str, Any]
) -> bool:
    """Whether a judge's supporting span may lie in a cited span: same evidence and
    overlapping lines or rows, or the same record; time and row locators of one series
    are not compared (the same series counts)."""
    if str(span.get("evidence_id") or "") != citation.get("evidence_id"):
        return False
    a = str(span.get("locator") or "").strip()
    b = str(citation.get("normalized") or citation.get("locator") or "").strip()
    for rx in (_LINES_LOCATOR, _ROWS_LOCATOR):
        ma, mb = rx.match(a), rx.match(b)
        if ma and mb:
            a0, a1 = int(ma.group(1)), int(ma.group(2) or ma.group(1))
            b0, b1 = int(mb.group(1)), int(mb.group(2) or mb.group(1))
            return a0 <= b1 and b0 <= a1
    records = tuple(f"{kind}:" for kind in RECORD_KINDS)
    if (
        a.startswith(records)
        or b.startswith(records)
        or a.startswith("L")
        or b.startswith("L")
    ):
        return a == b
    return True  # time/rows of the same series


def _judge_evidence(
    cid: str,
    entry: Mapping[str, Any],
    citations: Mapping[str, list[Mapping[str, Any]]],
) -> dict[str, Any] | None:
    """Evidence support for a judge criterion on the judge's finding_ids. The
    automated constraints decide 0 when those findings cite nothing usable, or when the
    judge's supporting quotes for an evidence value of 1 come only from cited spans
    never obtained during the episode; a 1 whose quotes lie in no span those findings
    cite is withheld for a human. Otherwise the judge's value is a proposal (with an
    automated proposal of 1 when a citation targets the criterion's keyed spans)."""
    fids = list(entry.get("finding_ids") or [])
    if not fids:
        if entry.get("evidence_support") is None:
            return None
        return {
            "value": entry["evidence_support"],
            "decided": False,
            "constraint": False,
            "proposal": None,
            "basis": "judge proposal (no finding_ids given)",
        }
    cites = [c for fid in fids for c in citations.get(fid, [])]
    if not cites:
        return {
            "value": 0,
            "decided": True,
            "constraint": True,
            "proposal": 0,
            "basis": f"the findings the judge relied on ({', '.join(fids)}) cite no "
            "evidence",
        }
    usable = [
        c
        for c in cites
        if c["resolvable"] and c["retrieved_during_episode"] is not False
    ]
    if not usable:
        return {
            "value": 0,
            "decided": True,
            "constraint": True,
            "proposal": 0,
            "basis": "the judge's findings cite only unresolvable or never-obtained "
            "evidence",
        }
    supporting = list(entry.get("supporting_spans") or [])
    # the judge's own value (the judge track withholds some 1s for a human:
    # ``judge_evidence_support`` keeps what the judge proposed)
    raw = entry.get("judge_evidence_support", entry.get("evidence_support"))
    if raw == 1 and supporting:
        mapped = [
            c for span in supporting for c in cites if _span_matches_citation(span, c)
        ]
        if mapped and not any(c in usable for c in mapped):
            return {
                "value": 0,
                "decided": True,
                "constraint": True,
                "proposal": 0,
                "basis": "the judge's supporting quotes come only from cited evidence "
                "that was never obtained during the episode (or does not resolve)",
            }
        if not mapped and entry.get("evidence_support") == 1:
            return {
                "value": None,
                "decided": False,
                "constraint": True,
                "proposal": None,
                "basis": "judge proposal withheld: its supporting quotes are not from "
                "spans that the findings it names cite (a human decides)",
            }
    targeted = [c for c in usable if cid in (c.get("targets_keyed_evidence_of") or [])]
    return {
        "value": entry.get("evidence_support"),
        "decided": False,
        "constraint": True,
        "proposal": 1 if targeted else None,
        "basis": (
            "judge proposal; automated: cites keyed evidence "
            + ", ".join(
                sorted({f"{c['evidence_id']} {c['normalized']}" for c in targeted})
            )
            if targeted
            else "judge proposal; automated: citations do not target the keyed spans "
            "(alternative evidence is allowed)"
        ),
    }


def merge_judge_proposals(
    report: Mapping[str, Any], judge_output: Mapping[str, Any] | Path | str
) -> dict[str, Any]:
    """Merge an LLM judge's proposals into a grade report; returns a new report.

    The judge layer only sets values for ``judge``-mode criteria (after automated caps:
    accounting-basis traps and suspected severe flags that are not adjudicated false;
    contradiction rules of judge criteria are flags for the reviewer, not caps),
    proposes evidence support on its finding_ids (automated constraints decide 0 when
    they cite nothing usable, or when the quotes for a 1 come only from cited evidence
    never obtained) and proposes assertion verdicts (a 'supported' that an automated
    numeric check contradicts becomes a conflict for a human).
    Proposals for ``auto_numeric``, ``auto_assisted_human`` and ``human`` criteria are
    recorded and ignored; severe-flag suggestions are recorded for adjudication.
    Human values always take precedence, and a human ``accept_judge`` signs a proposal
    off. The report stays provisional while any judge value lacks a human sign-off.
    Raises :class:`JudgeOutputError` for a malformed output or a binding to another
    submission, key or bundle."""
    judge = _load_judge(judge_output)
    out = copy.deepcopy(dict(report))
    problems = _check_judge(judge, out)
    if problems:
        raise JudgeOutputError("judge output rejected: " + "; ".join(problems))
    citations = _citation_index(out)
    ignored: list[dict[str, str]] = []
    applied: list[str] = []
    for row in out["criteria"]:
        entry = (judge.get("criteria") or {}).get(row["criterion_id"])
        if entry is None:
            continue
        entry = dict(entry)
        if row["assessment_mode"] != "judge":
            ignored.append(
                {
                    "criterion_id": row["criterion_id"],
                    "reason": f"{row['assessment_mode']} criteria are never decided by "
                    "the judge",
                }
            )
            row["judge_note"] = {
                "content": entry.get("content"),
                "rationale": entry.get("rationale"),
                "ignored": True,
            }
            continue
        row["layers"]["judge"] = {
            "content": entry.get("content"),
            "evidence_support": entry.get("evidence_support"),
            "finding_ids": list(entry.get("finding_ids") or []),
            "rationale": entry.get("rationale"),
            "supporting_spans": list(entry.get("supporting_spans") or []),
        }
        row["layers"]["judge_evidence"] = _judge_evidence(
            row["criterion_id"], entry, citations
        )
        row["judge_finding_ids"] = list(entry.get("finding_ids") or [])
        applied.append(row["criterion_id"])
    by_id = {a["assertion_id"]: a for a in out["assertion_quality"]["assertions"]}
    for aid, entry in (judge.get("assertions") or {}).items():
        layer = {
            "verdict": entry.get("verdict"),
            "rationale": entry.get("rationale"),
            "supporting_spans": list(entry.get("supporting_spans") or []),
        }
        if aid in by_id:
            by_id[aid]["layers"]["judge"] = layer
            if entry.get("task") and not (by_id[aid]["layers"].get("human") or {}).get(
                "dimension"
            ):
                by_id[aid]["dimension"] = entry["task"]
        else:
            out["assertion_quality"]["assertions"].append(
                {
                    "assertion_id": aid,
                    "kind": "report_text",
                    "text": entry.get("text"),
                    "factual": True,
                    "dimension": entry.get("task") or "unassigned",
                    "auto_proposal": None,
                    "layers": {"human": None, "judge": layer, "severe_flags": []},
                }
            )
    suggestions = []
    for entry in judge.get("severe_flags") or []:
        suggestions.append(
            {
                "flag_id": entry["flag_id"],
                "finding_ids": list(entry.get("finding_ids") or []),
                "locations": list(entry.get("locations") or []),
                "rationale": entry.get("rationale"),
                "note": "judge suggestion: severe flags are confirmed only by humans",
            }
        )
    out["judge"] = {
        "judge_model": judge.get("judge_model"),
        "rubric_version": judge.get("rubric_version"),
        "prompt_sha256": judge.get("prompt_sha256"),
        "cache_key": judge.get("cache_key"),
        "output_sha256": mvp._sha256_text(mvp._canonical(judge)),
        "criteria_applied": applied,
        "criteria_ignored": ignored,
        "severe_flag_suggestions": suggestions,
        "note": "judge values are proposals; a human signs them off (accept_judge or "
        "a value) before the report can be final",
    }
    _finalise(out, out["severe_flags"])
    return out


# -- episodes ---------------------------------------------------------------------------------
def _empty_measures(reason: str) -> dict[str, Any]:
    return {
        "content_coverage": None,
        "evidence_support": None,
        "assertion_quality": None,
        "severe_flags": [],
        "accounting_basis": None,
        "explanation_quality": None,
        "criteria": [],
        "citations": [],
        "flags": {},
        "measures_note": reason,
    }


def _catalogue_for_episode(
    episode_dir: Path, catalogue: Catalogue | None = None
) -> tuple[Catalogue, dict[str, Any]]:
    """The bundle the episode ran on (its recorded ``bundle_dir`` when present, else
    the installed system-response bundle); a bundle with another sha256 than the one
    the episode recorded raises :class:`GradingError`."""
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
            catalogue = Catalogue.load(SYSTEM_RESPONSE_BUNDLE_DIR)
    sha = recorded["bundle_sha256"]
    if sha and catalogue.bundle_sha256 != sha:
        raise GradingError(
            f"{episode_dir} was recorded on evidence bundle {recorded['bundle_version']} "
            f"(sha256 {sha[:12]}...), but the bundle given for grading is "
            f"{catalogue.bundle_version} (sha256 {catalogue.bundle_sha256[:12]}...): "
            "grade it against the bundle it ran on"
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
    judge_output: Mapping[str, Any] | Path | str | None = None,
) -> dict[str, Any]:
    """Grade an episode directory (``state.json``, ``trace.jsonl``,
    ``submission.json``). Incomplete runs get the run section and empty measures."""
    episode_dir = Path(episode_dir)
    summary = dict(transcript_summary or {})
    if "outcome" not in summary:
        summary = build_transcript_summary(
            episode_dir,
            None,
            output_token_budget=SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET,
            tool_names=SYSTEM_RESPONSE_TOOL_NAMES,
        )
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
                "key_sha256": key_sha256(key),
            },
            "bundle": _bundle_section(catalogue, key, recorded),
            "submission": None,
            "decisions": None,
            "judge": None,
            "tasks": _tasks(key),
            "trace": None
            if trace_info is None
            else {
                k: trace_info.get(k)
                for k in (
                    "retrieved",
                    "document_routes",
                    "records_by_kind",
                    "calls_used",
                )
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
    report = grade_submission(text, catalogue, key, trace_info, decisions, None)
    report["bundle"] = _bundle_section(catalogue, key, recorded)
    state = read_state(episode_dir)
    if (
        state is not None
        and state.submission_sha256
        and state.submission_sha256 != report["submission"]["sha256"]
    ):
        report["integrity_notes"].append(
            "submission.json does not match the sha256 in state.json"
        )
    if judge_output is not None:
        report = merge_judge_proposals(report, judge_output)
    else:
        _finalise(report, report["severe_flags"])
    return {**base, **report}


# -- review template ---------------------------------------------------------------------------
def review_template(
    target: Path | str | Mapping[str, Any],
    *,
    key: Mapping[str, Any] | None = None,
    catalogue: Catalogue | None = None,
    judge_output: Mapping[str, Any] | Path | str | None = None,
) -> dict[str, Any]:
    """A grading-decisions skeleton for a human reviewer, pre-filled with the automated
    and judge proposals under ``_context`` keys (ignored when the file is loaded).

    ``target`` is an episode directory, a grade report (a dict with ``criteria``), a
    submission file or a submission object."""
    key = key if key is not None else load_key()
    if (
        isinstance(target, Mapping)
        and "criteria" in target
        and "grade_schema" in target
    ):
        grade = dict(target)
        if judge_output is not None:
            grade = merge_judge_proposals(grade, judge_output)
    elif isinstance(target, (str, Path)) and Path(target).is_dir():
        grade = grade_episode(
            Path(target), key=key, catalogue=catalogue, judge_output=judge_output
        )
    else:
        grade = grade_submission(target, catalogue, key, None, None, judge_output)
    template: dict[str, Any] = {
        "_instructions": (
            "Fill in reviewer and date. For each criterion set content (1, 0.5, 0) and "
            "evidence_support (1, 0) after reading the cited evidence, or set "
            "accept_judge to true to sign off the judge's proposal (not possible for a "
            "proposal that automated checks capped: give the value; pre-screen "
            "contradiction flags are listed for you to check); list the finding_ids "
            "you relied on and add notes. Leave values null if undecided. For "
            "auto_numeric criteria null accepts the automated result; any value "
            "overrides it. For each factual finding set verdict (supported, "
            "unsupported, contradicted) or accept_judge (a judge verdict that conflicts "
            "with an automated numeric check needs a verdict); mark paraphrases with "
            "duplicate_of; add report-only assertions with a new ID, text and "
            "dimension (a task ID). Adjudicate every suspected severe flag (confirmed "
            "true/false); a confirmed flag makes its findings unsupported and sets the "
            "criteria in the key's effect to 0. Check the accounting-basis traps. Write "
            "explanation_quality notes (overall, or one per task). Save as a new "
            "decisions_version; never edit a version that has been used."
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
            "by_dimension": {t: None for t in _tasks(key)},
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
        judge = row["layers"].get("judge")
        template["criteria"][row["criterion_id"]] = {
            "content": None,
            "evidence_support": None,
            "accept_judge": False,
            "finding_ids": row["judge_finding_ids"] or row["matched_finding_ids"],
            "notes": "",
            "_context": {
                "title": crit["title"],
                "task": crit["task"],
                "assessment_mode": crit["assessment_mode"],
                "expectation": crit["expectation"],
                "accounting_basis": crit.get("accounting_basis"),
                "tolerances": crit.get("tolerances"),
                "current_content": row["content"],
                "current_evidence_support": row["evidence_support"],
                "judge": judge,
                "caps": row["layers"].get("caps"),
                "report_passages": crit["report_passages"],
                "visible_evidence": crit["visible_evidence"],
                "examples": crit["examples"],
            },
        }
    for a in grade["assertion_quality"]["assertions"]:
        if not a.get("factual"):
            continue
        context = {
            "dimension": a["dimension"],
            "auto_proposal": a.get("auto_proposal"),
            "auto_basis": a.get("auto_basis"),
            "judge_proposal": a.get("judge_proposal"),
        }
        if a.get("conflict"):
            context["conflict"] = a["conflict"]
        if a["kind"] == "finding":
            context.update(status=a["status"], cited=a["cited"])
            template["assertions"][a["assertion_id"]] = {
                "verdict": None,
                "accept_judge": False,
                "notes": "",
                "_context": context,
            }
        elif (a.get("layers") or {}).get("judge"):
            template["assertions"][a["assertion_id"]] = {
                "verdict": None,
                "accept_judge": False,
                "text": a.get("text"),
                "dimension": a["dimension"],
                "notes": "",
                "_context": context,
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
        "judge": grade.get("judge"),
        "accounting_traps": grade["flags"].get("accounting_traps"),
        "flags": {k: v for k, v in grade["flags"].items() if k != "needs_human_review"},
    }
    return template


# -- command line -------------------------------------------------------------------------------
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
        prog="python -m environment.incident.sr_grading",
        description="Grade gb-2019-system-response episodes and build review templates.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, helptext in (
        ("grade", "grade an episode directory"),
        ("grade-submission", "grade a submission file (no episode)"),
        ("review-template", "decisions template for an episode or submission"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("target", type=Path)
        p.add_argument("--bundle-dir", dest="bundle_dir", type=Path, default=None)
        p.add_argument("--judge", type=Path, default=None)
        p.add_argument("--out", type=Path, default=None)
        if name != "review-template":
            p.add_argument("--decisions", type=Path, default=None)
        if name == "grade":
            p.add_argument("--transcript", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        catalogue = Catalogue.load(args.bundle_dir) if args.bundle_dir else None
        if args.command == "grade":
            summary = None
            if args.transcript is not None:
                events = (
                    json.loads(args.transcript.read_text(encoding="utf-8")).get(
                        "events"
                    )
                    or []
                )
                summary = build_transcript_summary(
                    args.target,
                    events,
                    output_token_budget=SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET,
                    tool_names=SYSTEM_RESPONSE_TOOL_NAMES,
                )
            result = grade_episode(
                args.target,
                summary,
                args.decisions,
                catalogue=catalogue,
                judge_output=args.judge,
            )
        elif args.command == "grade-submission":
            result = grade_submission(
                args.target, catalogue, None, None, args.decisions, args.judge
            )
        else:
            result = review_template(
                args.target, catalogue=catalogue, judge_output=args.judge
            )
        _dump(result, args.out)
    except (GradingError, CatalogueError, EpisodeError, OSError) as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
