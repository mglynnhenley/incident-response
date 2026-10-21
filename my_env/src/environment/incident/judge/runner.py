"""Running the LLM judge on a submission and merging its proposals into a grade report.

:func:`judge_submission` builds one request per unit (:mod:`.prompt`), answers it from
the cache or the judge model, checks every response (schema, IDs, quotes) and
assembles a ``gb2019-sr-judge-output/1`` object for
:func:`environment.incident.sr_grading.merge_judge_proposals`. Judge values become
``judge`` proposals there: never final decisions, never values of ``auto_numeric``
criteria (those are never sent), and never confirmed severe flags.

:func:`judge_episode` and :func:`judge_submission_file` grade first (the automated
report supplies the citation checks, the routing of findings to tasks and the
binding), run the judge, re-grade with the judge output (and any human decisions) and
write ``judge_output.json``, ``judge_run.json`` and the merged ``grade.json`` to the
output directory (default ``<episode_dir>/judge/``). The grader, default key, bundle
and output budget are those of the key's task (:mod:`.tasks`): increment A's
``sr_grading`` by default, ``fi_grading`` for a full-investigation key.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from environment.incident import grading as mvp
from environment.incident import sr_grading
from environment.incident.catalogue import Catalogue
from environment.incident.episode import (
    SUBMISSION_FILE,
    SYSTEM_RESPONSE_TOOL_NAMES,
    build_transcript_summary,
)
from environment.incident.grading import normalise

from .cache import JudgeCache, cache_key
from .client import ChatClient, ChatResponse, JudgeClientError, OpenRouterClient
from .config import JudgeConfig, api_model_id, check_family, with_task_defaults
from .prompt import (
    BLIND_VERSION,
    Inputs,
    Rubric,
    Unit,
    build_units,
    load_rubric,
    prompt_template_sha256,
    prompt_version,
    repair_message,
)
from .schema import RESPONSE_SCHEMA, RESPONSE_SCHEMA_ID, validate
from .tasks import load_key as load_task_key
from .tasks import task_for_key
from .verify import check_span, find_report_location

__all__ = [
    "JUDGE_NOTE",
    "plan_submission",
    "JudgeError",
    "JudgeResult",
    "JudgeRun",
    "find_transcript",
    "judge_episode",
    "judge_submission",
    "judge_submission_file",
    "load_transcript",
    "parse_response",
    "request_payload",
    "usage_cost",
]

JUDGE_NOTE = (
    "LLM judge proposals for human sign-off: never final decisions, never values of "
    "auto_numeric criteria (not sent to the judge); auto_assisted_human proposals are "
    "recorded for the reviewer and ignored by the merge; severe flags are suggestions. "
    "Quotes were checked against the spans shown; hallucinated spans are listed and "
    "dropped. Withheld for a human (value null, judge value kept): evidence support 1 "
    "without a verified quote from a span the credited findings cite, 'supported' or "
    "'contradicted' without a verified quote, 'unsupported' with low confidence, and "
    "'not_factual'."
)
JUDGE_OUTPUT_FILE = "judge_output.json"
JUDGE_RUN_FILE = "judge_run.json"
MERGED_GRADE_FILE = "grade.json"
DEFAULT_OUT_DIR = "judge"
MIN_REPORT_WORDS = 3


class JudgeError(RuntimeError):
    """The judge could not be run on this target."""


@dataclass
class JudgeResult:
    judge_output: dict[str, Any]
    run_log: dict[str, Any]
    inputs: Inputs


@dataclass
class JudgeRun:
    """The outcome of :func:`judge_episode` / :func:`judge_submission_file`."""

    status: str
    judge_output: dict[str, Any] | None
    report: dict[str, Any]
    run_log: dict[str, Any]
    files: dict[str, str] = field(default_factory=dict)


# -- requests and responses ---------------------------------------------------------------
def request_payload(
    config: JudgeConfig, messages: Sequence[Mapping[str, str]]
) -> dict[str, Any]:
    """The chat-completions body: structured output (json_schema, strict),
    temperature 0 unless configured otherwise, usage accounting requested."""
    payload: dict[str, Any] = {
        "model": api_model_id(config.judge_model),
        "messages": [dict(m) for m in messages],
        "max_tokens": config.max_output_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "gb2019_sr_judge_response",
                "strict": True,
                "schema": RESPONSE_SCHEMA,
            },
        },
        "usage": {"include": True},
    }
    if config.temperature is not None:
        payload["temperature"] = config.temperature
    if config.provider:
        payload["provider"] = config.provider
    if config.reasoning:
        payload["reasoning"] = config.reasoning
    return payload


_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.S)


def parse_response(content: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse and schema-check a response text: ``(object, errors)``. A fenced or
    prefixed JSON object is accepted (the first JSON object in the text)."""
    text = (content or "").strip()
    match = _FENCE.match(text)
    if match:
        text = match.group(1)
    if not text:
        return None, ["empty response"]
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        start = text.find("{")
        if start < 0:
            return None, [f"not JSON: {exc.msg}"]
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError as exc2:
            return None, [f"not JSON: {exc2.msg} at character {exc2.pos}"]
    if not isinstance(obj, dict):
        return None, ["the response must be a JSON object"]
    errors = validate(obj, RESPONSE_SCHEMA)
    return (obj if not errors else None), errors


def usage_cost(usage: Mapping[str, Any], config: JudgeConfig) -> tuple[float, str]:
    """``(cost in USD, "provider" | "estimated")``: OpenRouter's reported cost, else
    tokens times the configured prices."""
    cost = usage.get("cost")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        return float(cost), "provider"
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    estimate = (
        prompt * config.price_per_million_input_usd
        + completion * config.price_per_million_output_usd
    ) / 1_000_000
    return round(estimate, 6), "estimated"


_USAGE_COUNTS = (
    "calls",
    "prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "cached_prompt_tokens",
)


def _sum_usage(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Sum usage summaries (``cost_source`` is ``mixed`` when sources differ)."""
    total: dict[str, Any] = {name: 0 for name in _USAGE_COUNTS}
    total["cost_usd"] = 0.0
    sources = []
    for item in items:
        for name in _USAGE_COUNTS:
            total[name] += int(item.get(name) or 0)
        total["cost_usd"] += float(item.get("cost_usd") or 0)
        if item.get("cost_source") and item["cost_source"] not in sources:
            sources.append(item["cost_source"])
    total["cost_usd"] = round(total["cost_usd"], 6)
    total["cost_source"] = (
        None if not sources else sources[0] if len(sources) == 1 else "mixed"
    )
    return total


def _usage_summary(
    attempts: Sequence[Mapping[str, Any]], config: JudgeConfig
) -> dict[str, Any]:
    """Tokens and cost of a unit's attempts, as the provider reported them."""
    items = []
    for attempt in attempts:
        usage = attempt.get("usage") or {}
        cost, source = usage_cost(usage, config)
        items.append(
            {
                "calls": 1,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get(
                    "reasoning_tokens"
                ),
                "cached_prompt_tokens": (usage.get("prompt_tokens_details") or {}).get(
                    "cached_tokens"
                ),
                "cost_usd": cost,
                "cost_source": source,
            }
        )
    return _sum_usage(items)


# -- checking one unit's response ----------------------------------------------------------
@dataclass
class _Checked:
    criteria: dict[str, dict[str, Any]] = field(default_factory=dict)
    assertions: dict[str, dict[str, Any]] = field(default_factory=dict)
    report_assertions: list[dict[str, Any]] = field(default_factory=list)
    severe: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    allowed: set[str] | None = None
    spans: dict[str, int] = field(
        default_factory=lambda: {
            "returned": 0,
            "verified": 0,
            "relocated": 0,
            "rejected": 0,
        }
    )


def _content(value: Any) -> float | int:
    return 1 if value == 1 else 0.5 if value == 0.5 else 0


def _check_spans(
    items: Sequence[Mapping[str, Any]], inputs: Inputs, checked: _Checked, where: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    accepted, rejected, within = [], [], set()
    for item in items:
        checked.spans["returned"] += 1
        result = check_span(item, inputs.index, checked.allowed)
        if result.ok:
            checked.spans["verified"] += 1
            if result.span.get("relocated"):
                checked.spans["relocated"] += 1
            accepted.append({**result.span, "shown_in": result.within})
            within.update(result.within)
        else:
            checked.spans["rejected"] += 1
            rejected.append({**result.span, "reason": result.reason})
            checked.issues.append(
                f"{where}: hallucinated span dropped ({result.span.get('evidence_id')} "
                f"{result.span.get('locator')}: {result.reason})"
            )
    return accepted, rejected, within


def _known_findings(
    ids: Sequence[str], inputs: Inputs, checked: _Checked, where: str
) -> list[str]:
    out = []
    for fid in ids:
        fid = str(fid).strip()
        if fid in inputs.finding_ids:
            if fid not in out:
                out.append(fid)
        else:
            checked.issues.append(f"{where}: unknown finding {fid!r} ignored")
    return out


def _withhold(
    verdict: str, confidence: str, accepted: Sequence[Any], issues: list[str]
) -> str | None:
    """The verdict to propose, or ``None`` (a human decides) when ``supported`` or
    ``contradicted`` has no verified quote, or ``unsupported`` is given with low
    confidence (the judge sees only part of the evidence pack)."""
    if verdict in ("supported", "contradicted") and not accepted:
        issues.append(
            f"verdict {verdict!r} withheld: no verified supporting quote (a human "
            "decides)"
        )
        return None
    if verdict == "unsupported" and confidence == "low":
        issues.append(
            "low-confidence 'unsupported' withheld: the judge saw only part of the "
            "evidence (a human decides)"
        )
        return None
    return verdict


def _check_unit(parsed: Mapping[str, Any], unit: Unit, inputs: Inputs) -> _Checked:
    index = inputs.index
    checked = _Checked(allowed=index.shown_in(unit))
    # a scoped unit shows some findings only in its cross-reference list: evidence
    # support rests only on spans cited by findings it showed in full
    in_full = (
        set(unit.shown_finding_ids) if unit.shown_finding_ids is not None else None
    )
    for entry in parsed["criteria"]:
        cid = str(entry["criterion_id"]).strip()
        where = f"criteria.{cid}"
        if cid not in unit.criterion_ids:
            checked.issues.append(
                f"{where}: not a criterion of unit {unit.unit_id} (ignored)"
            )
            continue
        if cid in checked.criteria:
            checked.issues.append(f"{where}: duplicate entry ignored")
            continue
        fids = _known_findings(entry["finding_ids"], inputs, checked, where)
        accepted, rejected, within = _check_spans(
            entry["supporting_spans"], inputs, checked, where
        )
        content = _content(entry["content"])
        evidence: int | None = int(entry["evidence_support"])
        issues: list[str] = []
        credited = set(fids)
        if in_full is not None:
            listed_only = [f for f in fids if f not in in_full]
            if listed_only:
                credited &= in_full
                issues.append(
                    f"finding(s) {', '.join(listed_only)} were shown to the judge only "
                    "in the cross-reference list of this unit (a human checks the "
                    "credit)"
                )
                checked.issues.append(f"{where}: {issues[-1]}")
        if evidence == 1 and content:
            cited_for = {
                s.span_id
                for s in index.spans.values()
                if s.span_id.startswith("C") and set(s.cited_by) & credited
            }
            obtained = {
                sid for sid in cited_for if index.spans[sid].obtained is not False
            }
            if not within & cited_for:
                evidence = None
                issues.append(
                    "evidence_support 1 withheld: no verified quote from a span cited "
                    "by the findings named (a human decides)"
                )
                checked.issues.append(f"{where}: {issues[-1]}")
            elif not within & obtained:
                evidence = None
                issues.append(
                    "evidence_support 1 withheld: the verified quotes come only from "
                    "cited spans not obtained during the episode (a human decides)"
                )
                checked.issues.append(f"{where}: {issues[-1]}")
        checked.criteria[cid] = {
            "content": content,
            "evidence_support": evidence,
            "judge_evidence_support": int(entry["evidence_support"]),
            "finding_ids": fids,
            "rationale": entry["rationale"],
            "confidence": entry["confidence"],
            "supporting_spans": accepted,
            "rejected_spans": rejected,
            "issues": issues,
            "unit": unit.unit_id,
        }
    missing = [c for c in unit.criterion_ids if c not in checked.criteria]
    if missing:
        checked.issues.append(
            f"criteria not returned (left pending): {', '.join(missing)}"
        )

    for entry in parsed["assertions"]:
        fid = str(entry["finding_id"]).strip()
        where = f"assertions.{fid}"
        if fid not in unit.finding_ids:
            checked.issues.append(
                f"{where}: not a finding to classify in unit {unit.unit_id} (ignored)"
            )
            continue
        if fid in checked.assertions:
            checked.issues.append(f"{where}: duplicate entry ignored")
            continue
        accepted, rejected, _ = _check_spans(entry["spans"], inputs, checked, where)
        raw = entry["verdict"]
        verdict: str | None = raw
        rationale = entry["rationale"]
        issues = []
        if raw == "not_factual":
            verdict = None
            rationale = f"judge: not a factual assertion. {rationale}"
        else:
            verdict = _withhold(raw, entry["confidence"], accepted, issues)
            if verdict is None:
                checked.issues.append(f"{where}: {issues[-1]}")
        checked.assertions[fid] = {
            "verdict": verdict,
            "judge_verdict": raw,
            "task": unit.task,
            "rationale": rationale,
            "confidence": entry["confidence"],
            "supporting_spans": accepted,
            "rejected_spans": rejected,
            "issues": issues,
            "unit": unit.unit_id,
        }
    missing = [f for f in unit.finding_ids if f not in checked.assertions]
    if missing:
        checked.issues.append(
            f"assertions not returned (left pending): {', '.join(missing)}"
        )

    report_items = list(parsed["report_assertions"])
    if len(report_items) > unit.report_assertion_limit:
        checked.issues.append(
            f"report_assertions: {len(report_items)} returned, "
            f"{unit.report_assertion_limit} allowed (extra ignored)"
        )
        report_items = report_items[: unit.report_assertion_limit]
    for n, entry in enumerate(report_items, 1):
        where = f"report_assertions[{n - 1}]"
        if len(normalise(entry["text"]).split()) < MIN_REPORT_WORDS:
            checked.issues.append(f"{where}: text too short to be a claim (dropped)")
            continue
        location = find_report_location(entry["text"], inputs.report_texts)
        if location is None:
            checked.issues.append(f"{where}: text not found in the report (dropped)")
            continue
        accepted, rejected, _ = _check_spans(entry["spans"], inputs, checked, where)
        issues = []
        verdict = _withhold(entry["verdict"], entry["confidence"], accepted, issues)
        if verdict is None:
            checked.issues.append(f"{where}: {issues[-1]}")
        checked.report_assertions.append(
            {
                "verdict": verdict,
                "judge_verdict": entry["verdict"],
                "text": entry["text"],
                "location": location,
                "task": unit.task,
                "rationale": entry["rationale"],
                "confidence": entry["confidence"],
                "supporting_spans": accepted,
                "rejected_spans": rejected,
                "issues": issues,
                "unit": unit.unit_id,
            }
        )

    flag_ids = {f["flag_id"] for f in unit.flags}
    for n, entry in enumerate(parsed["severe_flag_suggestions"]):
        where = f"severe_flag_suggestions[{n}]"
        flag_id = str(entry["flag_id"]).strip()
        if flag_id not in flag_ids:
            checked.issues.append(f"{where}: unknown flag {flag_id!r} (ignored)")
            continue
        fids = _known_findings(entry["finding_ids"], inputs, checked, where)
        locations = []
        quote = str(entry.get("report_quote") or "").strip()
        if quote:
            location = find_report_location(quote, inputs.report_texts)
            if location is None:
                checked.issues.append(f"{where}: report_quote not found in the report")
            else:
                locations.append(location)
        if not fids and not locations:
            checked.issues.append(
                f"{where}: no finding or verified report quote (dropped)"
            )
            continue
        checked.severe.append(
            {
                "flag_id": flag_id,
                "finding_ids": fids,
                "locations": locations,
                "report_quote": quote if locations else None,
                "rationale": entry["rationale"],
                "unit": unit.unit_id,
            }
        )
    return checked


# -- one submission -----------------------------------------------------------------------
def _attempt_record(response: ChatResponse, errors: Sequence[str]) -> dict[str, Any]:
    record = response.to_dict()
    record["errors"] = list(errors)
    return record


@dataclass
class _Prepared:
    binding: dict[str, Any]
    family: dict[str, Any]
    rubric: Rubric
    template_sha: str
    inputs: Inputs
    request_settings: dict[str, Any]
    model_id: str
    warnings: list[str] = field(default_factory=list)

    def material(self, unit: Unit) -> dict[str, Any]:
        """The cache-key material of one unit's request (a per-topic scope adds its
        settings; increment A's material is unchanged)."""
        scope = self.inputs.scope
        extra = {"scope": scope.public()} if scope is not None else {}
        return {
            **extra,
            "submission_sha256": self.binding["submission_sha256"],
            "bundle_sha256": self.binding["bundle_sha256"],
            "key_sha256": self.binding["key_sha256"],
            "key_version": self.binding["key_version"],
            "rubric_id": self.rubric.rubric_id,
            "rubric_version": self.rubric.version,
            "rubric_sha256": self.rubric.sha256,
            "judge_model": self.model_id,
            "prompt_template_sha256": self.template_sha,
            "request": self.request_settings,
            "unit_id": unit.unit_id,
            "messages_sha256": unit.messages_sha256,
        }


def _prepare(
    submission: Any,
    report: Mapping[str, Any],
    key: Mapping[str, Any],
    catalogue: Catalogue,
    config: JudgeConfig,
    run_model: str | None,
    rubric: Rubric | None,
) -> _Prepared:
    family = check_family(
        config.judge_model, run_model, allow_same_family=config.allow_same_family
    )
    sub, sub_sha = mvp._as_submission(submission, catalogue)
    binding = {
        "submission_sha256": report["submission"]["sha256"],
        "key_version": report["key"]["key_version"],
        "key_sha256": report["key"]["key_sha256"],
        "bundle_sha256": report["bundle"]["bundle_sha256"],
    }
    if sub_sha != binding["submission_sha256"]:
        raise JudgeError("the report was not produced for this submission")
    if binding["key_sha256"] != sr_grading.key_sha256(key):
        raise JudgeError("the report was not produced with this answer key")
    if binding["bundle_sha256"] != catalogue.bundle_sha256:
        raise JudgeError("the report was not produced on this bundle")
    rubric = rubric or load_rubric(config.rubric_path())
    warnings = []
    if rubric.key_id and rubric.key_id != key.get("key_id"):
        warnings.append(
            f"rubric {rubric.rubric_id} {rubric.version} is written for key "
            f"{rubric.key_id}, not {key.get('key_id')} (check the judge config)"
        )
    inputs = build_units(
        sub, report, key, catalogue, config, rubric, blind_terms=[run_model]
    )
    return _Prepared(
        warnings=warnings,
        binding=binding,
        family=family,
        rubric=rubric,
        template_sha=prompt_template_sha256(inputs.scope),
        inputs=inputs,
        request_settings={
            k: v
            for k, v in config.public().items()
            if k in ("temperature", "max_output_tokens", "provider", "reasoning")
        },
        model_id=api_model_id(config.judge_model),
    )


def _cached(
    cache: JudgeCache | None, ck: str, material: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, list[str]]:
    """(attempts, parsed, errors) of a cache entry that still validates."""
    entry = cache.get(ck, material) if cache is not None else None
    if entry is None:
        return [], None, []
    attempts = list(entry["attempts"])
    parsed, errors = parse_response(str(attempts[-1].get("content") or ""))
    return (attempts, parsed, []) if parsed is not None else ([], None, errors)


def plan_submission(
    submission: Any,
    report: Mapping[str, Any],
    *,
    key: Mapping[str, Any],
    catalogue: Catalogue,
    config: JudgeConfig,
    run_model: str | None = None,
    cache: JudgeCache | None = None,
    rubric: Rubric | None = None,
) -> dict[str, Any]:
    """A dry run: the requests a judge run would send, which are cached, and an
    approximate cost (about 4 characters per token; output at most
    ``max_output_tokens`` per request). Nothing is sent."""
    prep = _prepare(submission, report, key, catalogue, config, run_model, rubric)
    units = []
    for unit in prep.inputs.units:
        material = prep.material(unit)
        ck = cache_key(material)
        _, parsed, _ = _cached(cache, ck, material)
        chars = sum(len(m["content"]) for m in unit.messages)
        item: dict[str, Any] = {
            "unit_id": unit.unit_id,
            "criteria": len(unit.criterion_ids),
            "findings_classified": len(unit.finding_ids),
            "prompt_chars": chars,
            "approx_input_tokens": chars // 4,
            "cached": parsed is not None,
            "cache_key": ck,
        }
        if unit.scope is not None:
            item["findings_shown"] = len(unit.shown_finding_ids or [])
            item["cited_spans_shown"] = len(unit.cited_span_ids or [])
        units.append(item)
    todo = [u for u in units if not u["cached"]]
    tokens = sum(u["approx_input_tokens"] for u in todo)
    scope = prep.inputs.scope
    extra: dict[str, Any] = (
        {
            "scope": scope.public(),
            "findings": len(prep.inputs.finding_ids),
            "approx_input_tokens_all_units": sum(
                u["approx_input_tokens"] for u in units
            ),
        }
        if scope is not None
        else {}
    )
    return {
        "dry_run": True,
        "judge_model": prep.model_id,
        "rubric_version": prep.rubric.version,
        **extra,
        "family_check": prep.family,
        "blinding_redactions": prep.inputs.redactions,
        "units": units,
        **({"warnings": prep.warnings} if prep.warnings else {}),
        "requests_to_send": len(todo),
        "approx_input_tokens_to_send": tokens,
        "approx_cost_usd": {
            "input": round(tokens * config.price_per_million_input_usd / 1e6, 4),
            "output_upper_bound": round(
                len(todo)
                * config.max_output_tokens
                * config.price_per_million_output_usd
                / 1e6,
                4,
            ),
        },
    }


@dataclass
class _UnitState:
    unit: Unit
    material: dict[str, Any]
    cache_key: str
    record: dict[str, Any]
    attempts: list[dict[str, Any]] = field(default_factory=list)
    parsed: dict[str, Any] | None = None
    calls: int = 0


def _call_unit(
    state: _UnitState, client: ChatClient, config: JudgeConfig, cache: JudgeCache | None
) -> None:
    """Ask the judge for one unit (with up to ``max_attempts`` schema repairs) and
    cache a valid response. Errors are recorded on the unit, never raised."""
    messages = [dict(m) for m in state.unit.messages]
    try:
        for _ in range(config.max_attempts):
            response = client.complete(request_payload(config, messages))
            state.calls += 1
            parsed, errors = parse_response(response.content)
            if parsed is None and response.finish_reason == "length":
                errors = [*errors, "the reply was cut off at max_output_tokens"]
            state.attempts.append(_attempt_record(response, errors))
            if parsed is not None:
                state.parsed = parsed
                break
            messages += repair_message(response.content, errors)
    except JudgeClientError as exc:
        state.record["error"] = str(exc)
        return
    if state.parsed is None:
        state.record["error"] = (
            f"no valid response after {len(state.attempts)} attempt(s): "
            + "; ".join(state.attempts[-1]["errors"][:5])
        )
        return
    state.record["source"] = "api"
    if cache is not None:
        cache.put(state.cache_key, state.material, {"attempts": state.attempts})


def judge_submission(
    submission: Any,
    report: Mapping[str, Any],
    *,
    key: Mapping[str, Any],
    catalogue: Catalogue,
    config: JudgeConfig,
    run_model: str | None = None,
    client: ChatClient | None = None,
    client_factory: Callable[[], ChatClient] | None = None,
    cache: JudgeCache | None = None,
    cache_only: bool = False,
    rubric: Rubric | None = None,
) -> JudgeResult:
    """Judge one valid submission. ``report`` is its automated grade report (same
    submission, key and bundle). The client is created lazily, only when a unit is not
    in the cache. Raises :class:`JudgeConfigError` when the judge-family rule refuses
    the judge (before anything is sent)."""
    prep = _prepare(submission, report, key, catalogue, config, run_model, rubric)
    binding, rubric, inputs = prep.binding, prep.rubric, prep.inputs
    template_sha, model_id, family = prep.template_sha, prep.model_id, prep.family
    states: list[_UnitState] = []
    for unit in inputs.units:
        material = prep.material(unit)
        ck = cache_key(material)
        state = _UnitState(
            unit=unit,
            material=material,
            cache_key=ck,
            record={
                "unit_id": unit.unit_id,
                "task": unit.task,
                "criteria": list(unit.criterion_ids),
                "findings_classified": list(unit.finding_ids),
                "cache_key": ck,
                "messages_sha256": unit.messages_sha256,
                "prompt_chars": sum(len(m["content"]) for m in unit.messages),
                "status": "failed",
                "source": None,
                "error": None,
                "issues": [],
            },
        )
        if unit.scope is not None:
            state.record["scope"] = unit.scope_record()
        state.attempts, state.parsed, stale = _cached(cache, ck, material)
        if state.parsed is not None:
            state.record["source"] = "cache"
        elif stale:
            state.record["issues"].append(
                "cached response no longer validates: " + "; ".join(stale[:3])
            )
        if state.parsed is None and cache_only:
            state.record["error"] = (
                "not in the cache (cache-only run: nothing was sent)"
            )
        states.append(state)

    pending = [s for s in states if s.parsed is None and not cache_only]
    if pending:
        try:
            if client is None:
                if client_factory is None:
                    raise JudgeClientError("no judge client configured")
                client = client_factory()
        except JudgeClientError as exc:
            for state in pending:
                state.record["error"] = str(exc)
            pending = []
    if pending:
        assert client is not None
        workers = min(config.concurrency, len(pending))
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(
                    pool.map(lambda st: _call_unit(st, client, config, cache), pending)
                )
        else:
            for state in pending:
                _call_unit(state, client, config, cache)

    unit_records: list[dict[str, Any]] = []
    checked_units: list[tuple[Unit, _Checked]] = []
    fresh_usage = [
        _usage_summary(s.attempts, config) for s in states if s.calls and s.attempts
    ]
    total_usage: list[dict[str, Any]] = []
    served: set[str] = set()
    for state in states:
        record, attempts, unit = state.record, state.attempts, state.unit
        usage = _usage_summary(attempts, config) if attempts else None
        if state.parsed is not None and usage is not None:
            total_usage.append(usage)
        record["usage"] = usage
        record["attempts"] = len(attempts)
        record["temperature_sent"] = (
            attempts[-1].get("temperature_sent") if attempts else None
        )
        record["served_models"] = sorted(
            {str(a["model"]) for a in attempts if a.get("model")}
        )
        served.update(record["served_models"])
        if state.parsed is not None:
            checked = _check_unit(state.parsed, unit, inputs)
            checked_units.append((unit, checked))
            record["status"] = "ok"
            record["issues"] += checked.issues
            record["span_checks"] = dict(checked.spans)
        unit_records.append(record)
    api_calls = sum(s.calls for s in states)
    hits = sum(1 for s in states if s.record["source"] == "cache")

    criteria: dict[str, Any] = {}
    assertions: dict[str, Any] = {}
    severe: list[dict[str, Any]] = []
    seen_texts: set[str] = set()
    seen_flags: set[str] = set()
    spans = {"returned": 0, "verified": 0, "relocated": 0, "rejected": 0}
    for unit, checked in checked_units:
        criteria.update(checked.criteria)
        assertions.update(checked.assertions)
        for name in spans:
            spans[name] += checked.spans[name]
        n = 0
        for item in checked.report_assertions:
            text_key = normalise(item["text"])
            if text_key in seen_texts:
                continue
            seen_texts.add(text_key)
            n += 1
            aid = f"J-{unit.unit_id}-{n}"
            while aid in inputs.finding_ids:  # never shadow a finding
                aid += "j"
            assertions[aid] = item
        for item in checked.severe:
            flag_key = json.dumps(
                [
                    item["flag_id"],
                    sorted(item["finding_ids"]),
                    sorted(item["locations"]),
                ]
            )
            if flag_key not in seen_flags:
                seen_flags.add(flag_key)
                severe.append(item)
    failed = [r["unit_id"] for r in unit_records if r["status"] != "ok"]
    judge_output = {
        "judge_schema": sr_grading.JUDGE_SCHEMA,
        "judge_model": model_id,
        "judge_models_served": sorted(served),
        "rubric_id": rubric.rubric_id,
        "rubric_version": rubric.version,
        "rubric_sha256": rubric.sha256,
        "prompt_version": prompt_version(inputs.scope),
        "prompt_sha256": template_sha,
        "prompt_template_sha256": template_sha,
        "response_schema": RESPONSE_SCHEMA_ID,
        "cache_key": cache_key({"units": sorted(r["cache_key"] for r in unit_records)}),
        "binding": binding,
        "config": config.public(),
        **({"scope": inputs.scope.public()} if inputs.scope is not None else {}),
        "family_check": family,
        "blinding": {
            "version": BLIND_VERSION,
            "submission_redactions": inputs.redactions,
        },
        "complete": not failed,
        "failed_units": failed,
        "units": [
            {k: v for k, v in r.items() if k not in ("prompt_chars", "source")}
            for r in unit_records
        ],
        "criteria": criteria,
        "assertions": assertions,
        "severe_flags": severe,
        "span_checks": spans,
        "usage": _sum_usage(total_usage),
        "note": JUDGE_NOTE,
    }
    run_log = {
        "api_calls": api_calls,
        "cache_hits": hits,
        "units": len(unit_records),
        "failed_units": failed,
        "cost_this_run": _sum_usage(fresh_usage),
        "cost_recorded_total": judge_output["usage"],
        "unit_sources": {r["unit_id"]: r["source"] for r in unit_records},
        "prompt_chars": {r["unit_id"]: r["prompt_chars"] for r in unit_records},
        "errors": {r["unit_id"]: r["error"] for r in unit_records if r["error"]},
    }
    if prep.warnings:
        run_log["warnings"] = list(prep.warnings)
    return JudgeResult(judge_output=judge_output, run_log=run_log, inputs=inputs)


# -- transcripts (the evaluated model, never shown to the judge) -----------------------------
def find_transcript(episode_dir: Path) -> Path | None:
    """A Karotte transcript next to a saved episode (``<run>_artifacts/episode`` with
    ``transcript.json`` beside the artifacts directory, as ``karotte run`` saves them);
    a transcript whose ``run_id`` is not the artifacts' run is ignored."""
    episode_dir = Path(episode_dir)
    artifacts = episode_dir.parent
    run_id = (
        artifacts.name[: -len("_artifacts")]
        if artifacts.name.endswith("_artifacts")
        else None
    )
    for candidate in (
        episode_dir / "transcript.json",
        artifacts / "transcript.json",
        artifacts.parent / "transcript.json",
    ):
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("events"), list):
            continue
        if run_id and data.get("run_id") and data["run_id"] != run_id:
            continue
        return candidate
    return None


def load_transcript(path: Path | str) -> tuple[list[dict[str, Any]], str | None]:
    """``(events, model)`` of a Karotte transcript JSON."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JudgeError(f"cannot read transcript {path}: {exc}") from None
    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list):
        raise JudgeError(f"{path} is not a transcript (no events)")
    events = [e for e in events if isinstance(e, dict)]
    for event in events:
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        for value in (event.get("model"), data.get("model")):
            if isinstance(value, str) and value.strip():
                return events, value.strip()
    return events, None


# -- episodes and files ----------------------------------------------------------------------
def _write_json(path: Path, obj: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, default=str)
        + "\n",
        encoding="utf-8",
    )
    return str(path)


def _default_client_factory(config: JudgeConfig) -> Callable[[], ChatClient]:
    def make() -> ChatClient:
        return OpenRouterClient(
            base_url=config.base_url,
            timeout_s=config.timeout_s,
            max_retries=config.max_http_retries,
            app_title=config.app_title,
        )

    return make


def _cache_for(
    config: JudgeConfig, cache_dir: Path | str | None, out_dir: Path
) -> JudgeCache:
    if cache_dir is not None:
        return JudgeCache(cache_dir)
    if config.cache_dir:
        return JudgeCache(config.cache_dir)
    return JudgeCache(out_dir / "cache")


def _finish(
    result: JudgeResult,
    report: dict[str, Any],
    out_dir: Path,
    write: bool,
    extra_log: Mapping[str, Any],
) -> JudgeRun:
    log = {**result.run_log, **extra_log}
    status = "judged" if result.judge_output["complete"] else "partial"
    log["status"] = status
    files: dict[str, str] = {}
    if write:
        files["judge_output"] = _write_json(
            out_dir / JUDGE_OUTPUT_FILE, result.judge_output
        )
        files["judge_run"] = _write_json(out_dir / JUDGE_RUN_FILE, log)
        files["grade"] = _write_json(out_dir / MERGED_GRADE_FILE, report)
    return JudgeRun(
        status=status,
        judge_output=result.judge_output,
        report=report,
        run_log=log,
        files=files,
    )


def judge_episode(
    episode_dir: Path | str,
    *,
    config: JudgeConfig,
    run_model: str | None = None,
    transcript: Path | str | None = None,
    decisions: Mapping[str, Any] | Path | str | None = None,
    key: Mapping[str, Any] | None = None,
    catalogue: Catalogue | None = None,
    client: ChatClient | None = None,
    client_factory: Callable[[], ChatClient] | None = None,
    cache_dir: Path | str | None = None,
    cache_only: bool = False,
    out_dir: Path | str | None = None,
    write: bool = True,
    dry_run: bool = False,
    task: str | None = None,
) -> JudgeRun:
    """Grade an episode, judge its submission and write the merged grade. The
    evaluated model comes from ``run_model`` or the run's transcript (it only drives
    the judge-family rule and the blinding; it is never shown to the judge). The
    grader is the key's task's (``task`` names the default key when ``key`` is not
    given: increment A's unless ``gb-2019-full-investigation``)."""
    episode_dir = Path(episode_dir)
    out = Path(out_dir) if out_dir is not None else episode_dir / DEFAULT_OUT_DIR
    transcript_path = Path(transcript) if transcript else find_transcript(episode_dir)
    events = None
    transcript_model = None
    if transcript_path is not None:
        events, transcript_model = load_transcript(transcript_path)
    run_model = run_model or transcript_model
    check_family(
        config.judge_model, run_model, allow_same_family=config.allow_same_family
    )
    key = key if key is not None else load_task_key(None, task)
    grading = task_for_key(key)
    config = with_task_defaults(config, grading.task_id)
    grader = grading.grader
    catalogue, _ = grader._catalogue_for_episode(episode_dir, catalogue)
    summary = (
        build_transcript_summary(
            episode_dir,
            events,
            output_token_budget=grading.output_token_budget,
            tool_names=SYSTEM_RESPONSE_TOOL_NAMES,
        )
        if events is not None
        else None
    )
    base = grader.grade_episode(episode_dir, summary, key=key, catalogue=catalogue)
    extra = {
        "target": str(episode_dir),
        "transcript": str(transcript_path) if transcript_path else None,
    }
    if base["run"]["outcome"] != "complete":
        report = grader.grade_episode(
            episode_dir, summary, decisions, key=key, catalogue=catalogue
        )
        return JudgeRun(
            status="not_judged",
            judge_output=None,
            report=report,
            run_log={
                **extra,
                "status": "not_judged",
                "reason": f"run outcome is {base['run']['outcome']!r}: nothing to judge",
                "api_calls": 0,
            },
        )
    text = (episode_dir / SUBMISSION_FILE).read_text(encoding="utf-8")
    cache = _cache_for(config, cache_dir, out)
    if dry_run:
        plan = plan_submission(
            text,
            base,
            key=key,
            catalogue=catalogue,
            config=config,
            run_model=run_model,
            cache=cache,
        )
        return JudgeRun("dry_run", None, base, {**extra, **plan, "status": "dry_run"})
    result = judge_submission(
        text,
        base,
        key=key,
        catalogue=catalogue,
        config=config,
        run_model=run_model,
        client=client,
        client_factory=client_factory or _default_client_factory(config),
        cache=cache,
        cache_only=cache_only,
    )
    report = grader.grade_episode(
        episode_dir,
        summary,
        decisions,
        key=key,
        catalogue=catalogue,
        judge_output=result.judge_output,
    )
    return _finish(result, report, out, write, extra)


def judge_submission_file(
    path: Path | str,
    *,
    config: JudgeConfig,
    out_dir: Path | str,
    run_model: str | None = None,
    decisions: Mapping[str, Any] | Path | str | None = None,
    key: Mapping[str, Any] | None = None,
    catalogue: Catalogue | None = None,
    client: ChatClient | None = None,
    client_factory: Callable[[], ChatClient] | None = None,
    cache_dir: Path | str | None = None,
    cache_only: bool = False,
    write: bool = True,
    dry_run: bool = False,
    task: str | None = None,
) -> JudgeRun:
    """Judge a bare submission file (no episode: retrieval is not checked) with the
    grader, default key and bundle of the key's task (``task`` as in
    :func:`judge_episode`)."""
    path = Path(path)
    check_family(
        config.judge_model, run_model, allow_same_family=config.allow_same_family
    )
    key = key if key is not None else load_task_key(None, task)
    grading = task_for_key(key)
    config = with_task_defaults(config, grading.task_id)
    grader = grading.grader
    catalogue = catalogue or Catalogue.load(grading.bundle_dir)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise JudgeError(f"cannot read {path}: {exc}") from None
    base = grader.grade_submission(text, catalogue, key)
    cache = _cache_for(config, cache_dir, Path(out_dir))
    extra = {"target": str(path)}
    if dry_run:
        plan = plan_submission(
            text,
            base,
            key=key,
            catalogue=catalogue,
            config=config,
            run_model=run_model,
            cache=cache,
        )
        return JudgeRun("dry_run", None, base, {**extra, **plan, "status": "dry_run"})
    result = judge_submission(
        text,
        base,
        key=key,
        catalogue=catalogue,
        config=config,
        run_model=run_model,
        client=client,
        client_factory=client_factory or _default_client_factory(config),
        cache=cache,
        cache_only=cache_only,
    )
    report = grader.grade_submission(
        text, catalogue, key, None, decisions, result.judge_output
    )
    return _finish(result, report, Path(out_dir), write, extra)
