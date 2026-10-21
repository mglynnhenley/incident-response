"""Grading of a frozen submission for the full investigation (gb-2019-full-investigation).

The task's judge (``tasks/gb_2019_full_investigation/judge.py``) calls
:func:`grade_episode` (``episode_dir``, ``transcript_summary``). The answer key is
``private/full_investigation/answer_key.json`` (key schema ``gb2019-fi-answer-key/1``):
increment A's 60 criteria (same IDs, re-bound to the full-investigation bundle) and
criteria for the handoff topics T04.02, T10, T11, T13, T14, T15, T18, T19 and T20.

Increment A's grader does the grading (:mod:`.sr_grading`, with :mod:`.sr_accounting`):
the same separation of content coverage, evidence support and assertion quality (no
total, threshold or ranking), the same layered values (automated, judge, human), the
same provisional status, citation checks over every retrieval route, accounting-basis
checks, severe flags, labelling and inferential-language flags, and the same judge merge
semantics (:func:`merge_judge_proposals`: the judge only sets values of ``judge``
criteria, after accounting caps and suspected severe flags; contradiction rules of a
judge criterion are pre-screen flags for the reviewer; a human signs every judge value
off). The judge interface is increment A's (judge output schema
``gb2019-sr-judge-output/1``, decision 34). This module adds:

* the full-investigation defaults: bundle ``bundles/full_investigation``, this task's
  key, its output-token budget (80,000) and tool set for the transcript summary;
* the element types of :mod:`.fi_elements` (``count`` for the rail counts,
  ``summary_text`` and ``summary_words`` for the executive summary that is the T20
  summary, ``section_text`` for the recommendations and evidence-request sections,
  and ``figure``, increment A's figure element that also reads a finding labelled
  unknown when the figure's own clause states no uncertainty);
* key fields that only this key carries and the shared code reads (key 0.1.1,
  decisions 77 and 81): SF1's clause-scoped negations (``unless_clause_any``) and its
  bare-mention triggers (``mention_triggers``), the accounting option
  ``binding_options.basis_components`` and ``mismatch_unless_any``, and
  ``conventions.labelling_exempt``; increment A's outputs are unchanged;
* its own grade, key and grading-decisions schemas (decisions are bound to this key);
* ``flags.executive_summary``: the summary's word count against the 600-word limit.

The lessons of increment A's real submissions (decisions 18, 27, 40-48) come with the
reused machinery and are built into the new criteria and element types: a candidate
value is never silently scored 0 (it goes to a human), wording binds to its own clause,
contradiction rules tie the subject to the verb and list non-assertions, SF1 fires only
on an asserted root cause, and labelling and inferential flags spare attributed
clauses (the key adds the rail and communications parties to the attribution sources).

This module must not import ``karotte``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from environment.incident import fi_elements
from environment.incident import grading as mvp
from environment.incident import sr_grading as sr
from environment.incident.catalogue import Catalogue, CatalogueError
from environment.incident.episode import (
    FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET,
    SUBMISSION_FILE,
    SYSTEM_RESPONSE_TOOL_NAMES,
    EpisodeError,
    build_transcript_summary,
    read_config_snapshot,
    read_state,
)
from environment.incident.grading import DecisionsError, GradingError, _public
from environment.incident.paths import (
    FULL_INVESTIGATION_BUNDLE_DIR,
    FULL_INVESTIGATION_PRIVATE_DIR,
)
from environment.incident.submission import word_count

__all__ = [
    "DECISIONS_SCHEMA",
    "DEFAULT_KEY_PATH",
    "ELEMENT_TYPES",
    "GRADER_VERSION",
    "GRADE_SCHEMA",
    "JUDGE_SCHEMA",
    "KEY_SCHEMA",
    "MODES",
    "SUMMARY_WORD_LIMIT",
    "TASK_ID",
    "DecisionsError",
    "GradingError",
    "JudgeOutputError",
    "check_citations",
    "check_decisions",
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

TASK_ID = "gb-2019-full-investigation"
GRADER_VERSION = "0.1.1"
GRADE_SCHEMA = "gb2019-fi-grade/1"
KEY_SCHEMA = "gb2019-fi-answer-key/1"
DECISIONS_SCHEMA = "gb2019-fi-grading-decisions/1"
JUDGE_SCHEMA = sr.JUDGE_SCHEMA  # increment A's judge interface (decision 34)
DEFAULT_KEY_PATH = FULL_INVESTIGATION_PRIVATE_DIR / "answer_key.json"
MODES = sr.MODES
SUMMARY_WORD_LIMIT = 600
ELEMENT_TYPES = fi_elements.ELEMENT_TYPES

INTERPRETATION = (
    sr.INTERPRETATION
    + " The executive summary is the investigation summary (T20); recommendations "
    "(T18) and evidence requests (T19) are read from the findings and the report "
    "sections."
)

JudgeOutputError = sr.JudgeOutputError
key_sha256 = sr.key_sha256
load_decisions = sr.load_decisions
trace_info_from_episode = sr.trace_info_from_episode
resolve_text = sr.resolve_text
check_citations = sr.check_citations
merge_judge_proposals = sr.merge_judge_proposals


# -- key and decisions ---------------------------------------------------------------
def load_key(path: Path | str | None = None) -> dict[str, Any]:
    """Load the full-investigation answer key (default: the private key)."""
    key_path = Path(path) if path is not None else DEFAULT_KEY_PATH
    try:
        key = json.loads(key_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GradingError(f"cannot load the answer key {key_path}: {exc}") from None
    if not isinstance(key, dict) or key.get("key_schema") != KEY_SCHEMA:
        raise GradingError(f"{key_path} is not a {KEY_SCHEMA} answer key")
    return key


def _default_catalogue() -> Catalogue:
    return Catalogue.load(FULL_INVESTIGATION_BUNDLE_DIR)


def _as_sr_decisions(decisions: Mapping[str, Any]) -> dict[str, Any]:
    """A full-investigation decisions object in increment A's schema (same layout),
    after checking its own schema name."""
    if _public(decisions).get("decisions_schema") != DECISIONS_SCHEMA:
        raise DecisionsError(
            f"grading decisions rejected: decisions_schema must be {DECISIONS_SCHEMA!r}"
        )
    return {**decisions, "decisions_schema": sr.DECISIONS_SCHEMA}


def check_decisions(
    decisions: Mapping[str, Any],
    *,
    submission_sha256: str,
    key: Mapping[str, Any],
    finding_ids: Any,
    bundle_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate a decisions object (increment A's rules: tasks as dimensions, the
    binding to this submission, key and bundle, ``accept_judge`` booleans)."""
    checked = sr.check_decisions(
        _as_sr_decisions(decisions),
        submission_sha256=submission_sha256,
        key=key,
        finding_ids=finding_ids,
        bundle_sha256=bundle_sha256,
    )
    checked["decisions_schema"] = DECISIONS_SCHEMA
    return checked


# -- grading ---------------------------------------------------------------------------
def _finish(report: dict[str, Any], summary_text: str | None) -> dict[str, Any]:
    """Mark an increment-A report as a full-investigation report."""
    report["grade_schema"] = GRADE_SCHEMA
    report["grader_version"] = GRADER_VERSION
    report["task_id"] = TASK_ID
    report["interpretation"] = INTERPRETATION
    report["builds_on"] = {
        "grader": "environment.incident.sr_grading",
        "grader_version": sr.GRADER_VERSION,
    }
    if summary_text is not None and isinstance(report.get("flags"), dict):
        words = word_count(summary_text)
        report["flags"]["executive_summary"] = {
            "words": words,
            "limit": SUMMARY_WORD_LIMIT,
            "within_limit": words <= SUMMARY_WORD_LIMIT,
        }
    return report


def grade_submission(
    submission: Any,
    catalogue: Catalogue | None = None,
    key: Mapping[str, Any] | None = None,
    trace_info: Mapping[str, Any] | None = None,
    decisions: Mapping[str, Any] | Path | str | None = None,
    judge_output: Mapping[str, Any] | Path | str | None = None,
) -> dict[str, Any]:
    """Grade one valid v3 submission against the full-investigation key (see
    :func:`environment.incident.sr_grading.grade_submission`: ``trace_info`` from
    :func:`trace_info_from_episode`, ``decisions`` a decisions object or path with
    schema ``gb2019-fi-grading-decisions/1``, ``judge_output`` a judge output to merge).
    """
    catalogue = catalogue or _default_catalogue()
    key = key if key is not None else load_key()
    if isinstance(decisions, (str, Path)):
        decisions = load_decisions(decisions)
    translated = _as_sr_decisions(decisions) if decisions is not None else None
    report = sr.grade_submission(
        submission,
        catalogue,
        key,
        trace_info,
        translated,
        None,
        element_types=ELEMENT_TYPES,
    )
    sub, _ = mvp._as_submission(submission, catalogue)
    _finish(report, sub["report"]["executive_summary"])
    if judge_output is not None:
        report = merge_judge_proposals(report, judge_output)
    return report


def criterion_rubric(
    criterion_id: str,
    *,
    key: Mapping[str, Any] | None = None,
    catalogue: Catalogue | None = None,
) -> dict[str, Any]:
    """What the judge may see about one criterion (increment A's rule: expectation,
    scale, examples, accounting basis and keyed spans; never report passages or
    reviewer notes)."""
    return sr.criterion_rubric(
        criterion_id,
        key=key if key is not None else load_key(),
        catalogue=catalogue or _default_catalogue(),
    )


def cited_spans(
    submission: Any, catalogue: Catalogue | None = None
) -> dict[str, list[dict[str, Any]]]:
    """The resolved text of every citation of a submission, by finding."""
    return sr.cited_spans(submission, catalogue or _default_catalogue())


# -- episodes ------------------------------------------------------------------------
def _catalogue_for_episode(
    episode_dir: Path, catalogue: Catalogue | None = None
) -> tuple[Catalogue, dict[str, Any]]:
    """The bundle the episode ran on (its recorded ``bundle_dir`` when present, else
    the installed full-investigation bundle); a bundle with another sha256 than the
    one the episode recorded raises :class:`GradingError`."""
    snapshot = read_config_snapshot(episode_dir) or {}
    if catalogue is None:
        candidate = (snapshot.get("config") or {}).get("bundle_dir")
        if candidate and Path(candidate).is_dir():
            try:
                catalogue = Catalogue.load(candidate)
            except CatalogueError:
                catalogue = None
        if catalogue is None:
            catalogue = _default_catalogue()
    return sr._catalogue_for_episode(episode_dir, catalogue)


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
            output_token_budget=FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET,
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
        report = {
            **base,
            "status": "provisional",
            "provisional_reasons": [
                reason,
                f"answer key review status is {sr._review_status(key)!r}",
            ],
            "interpretation": INTERPRETATION,
            "key": {
                "key_id": key.get("key_id"),
                "key_version": key.get("key_version"),
                "review_status": sr._review_status(key),
                "key_sha256": key_sha256(key),
            },
            "bundle": sr._bundle_section(catalogue, key, recorded),
            "submission": None,
            "decisions": None,
            "judge": None,
            "tasks": sr._tasks(key),
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
            **sr._empty_measures(reason),
        }
        return _finish(report, None)
    path = episode_dir / SUBMISSION_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GradingError(
            f"complete run without a readable {SUBMISSION_FILE}: {exc}"
        ) from None
    report = grade_submission(text, catalogue, key, trace_info, decisions, None)
    report["bundle"] = sr._bundle_section(catalogue, key, recorded)
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
        sr._finalise(report, report["severe_flags"])
    return {**base, **report}


# -- review template -----------------------------------------------------------------
def review_template(
    target: Path | str | Mapping[str, Any],
    *,
    key: Mapping[str, Any] | None = None,
    catalogue: Catalogue | None = None,
    judge_output: Mapping[str, Any] | Path | str | None = None,
) -> dict[str, Any]:
    """A grading-decisions skeleton for a human reviewer (increment A's template with
    this task's decisions schema). ``target`` is an episode directory, a grade report,
    a submission file or a submission object."""
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
    template = sr.review_template(grade, key=key)
    template["decisions_schema"] = DECISIONS_SCHEMA
    return template


# -- command line ----------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m environment.incident.fi_grading",
        description="Grade gb-2019-full-investigation episodes and build review "
        "templates.",
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
                    output_token_budget=FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET,
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
        sr._dump(result, args.out)
    except (GradingError, CatalogueError, EpisodeError, OSError) as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
