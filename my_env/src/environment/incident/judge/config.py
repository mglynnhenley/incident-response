"""Judge configuration and the model-family rule.

The default judge is ``openai/gpt-6.1-sol`` through OpenRouter (decision 25): a
different model family from the Anthropic models under test. A judge from the
evaluated model's family is refused unless ``allow_same_family`` is set explicitly
(the override is recorded in the judge output); so is a run whose model cannot be
determined, because the rule cannot then be checked.

Request scope (decision 52): by default every request carries the whole submission and
every cited span (increment A's behaviour, unchanged). A task opts in to per-topic
scoping with a :class:`JudgeScope` whose ``mode`` is ``"topic"``, given either in the
judge config (``scope``) or in the answer key (``judge.scope``); the config wins. See
:mod:`.prompt` for what a scoped request contains.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from environment.incident.paths import DEFAULT_PRIVATE_DIR, SYSTEM_RESPONSE_PRIVATE_DIR

__all__ = [
    "DEFAULT_JUDGE_MODEL",
    "JUDGEABLE_MODES",
    "SCOPE_MODES",
    "TASK_CONFIG_DEFAULTS",
    "JudgeConfig",
    "JudgeConfigError",
    "JudgeScope",
    "api_model_id",
    "check_family",
    "load_config",
    "model_family",
    "resolve_scope",
    "with_task_defaults",
]

DEFAULT_JUDGE_MODEL = "openai/gpt-6.1-sol"
DEFAULT_RUBRIC = "judge_rubric_v1.md"
JUDGEABLE_MODES = ("judge", "auto_assisted_human")
SCOPE_MODES = ("submission", "topic")
SYSTEM_RESPONSE_TASK = "gb-2019-system-response"
FULL_INVESTIGATION_TASK = "gb-2019-full-investigation"
# Per-task defaults under the file and the overrides (``load_config(task=...)``).
# Increment A's task has none: its requests are unchanged. The full investigation
# uses its own rubric and per-topic scoping (decision 52); configs/judge.fi.example.json
# spells the same settings out (a test checks they agree).
TASK_CONFIG_DEFAULTS: dict[str, dict[str, Any]] = {
    SYSTEM_RESPONSE_TASK: {},
    FULL_INVESTIGATION_TASK: {
        "rubric_file": "full_investigation/judge_rubric_v1.md",
        "app_title": "gb2019-fi-judge",
        "scope": {
            "mode": "topic",
            "lexical_tasks_per_finding": 3,
            "lexical_min_score": 4.0,
            "all_findings_tasks": ["T17"],
            "title_chars": 90,
            "error_screen": True,
        },
    },
}


class JudgeConfigError(ValueError):
    """The judge cannot run with this configuration (nothing was sent)."""


class JudgeScope(BaseModel):
    """What one judge request carries (decision 52).

    ``submission`` (the default, increment A's behaviour): the whole submission and
    every cited span in every request. ``topic``: a unit's request carries only the
    findings of its topic in full, the report text that refers to them (whole
    executive summary or sections where the unit's criteria read them), their cited
    spans and the unit's keyed spans, plus a compact list of the other findings (ID,
    status and the opening words of the statement) for cross-reference.

    A finding belongs to a topic when the automated grade routes it there, matched or
    considered it for one of the topic's criteria, it cites a keyed span of the
    topic's criteria, the report text shown whole for the topic refers to it, or it is
    among its ``lexical_tasks_per_finding`` best topics by the key's own vocabulary
    (criterion titles, expectations, alternatives and example statements; a minimum
    score of ``lexical_min_score``). ``all_findings_tasks`` are cross-cutting topics
    (for example the uncertainty register) whose requests show every finding in full
    and the whole report, but still only the cited spans of their own findings.
    ``error_screen``: a topic whose judge criteria an error stated anywhere bounds (a
    contradiction rule or a severe flag) also shows every finding with a sentence that
    meets those patterns, or whose own best topics by vocabulary include the topic."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["submission", "topic"] = "submission"
    lexical_tasks_per_finding: int = Field(default=3, ge=0, le=20)
    lexical_min_score: float = Field(default=4.0, ge=0)
    all_findings_tasks: list[str] = Field(default_factory=list)
    title_chars: int = Field(default=110, ge=20, le=400)
    error_screen: bool = True

    @property
    def scoped(self) -> bool:
        return self.mode == "topic"

    def public(self) -> dict[str, Any]:
        return self.model_dump()


def resolve_scope(config: JudgeConfig, key: Mapping[str, Any] | None) -> JudgeScope:
    """The effective request scope: the config's ``scope`` if set, else the key's
    ``judge.scope``, else ``submission`` (increment A's behaviour)."""
    if config.scope is not None:
        return config.scope
    raw = ((key or {}).get("judge") or {}).get("scope")
    if raw is None:
        return JudgeScope()
    try:
        return JudgeScope(**raw) if isinstance(raw, Mapping) else JudgeScope(mode=raw)
    except ValueError as exc:
        raise JudgeConfigError(
            f"invalid judge.scope in the answer key: {exc}"
        ) from None


class JudgeConfig(BaseModel):
    """Settings of one judge run (``configs/judge.example.json``). The API key is
    never part of the configuration: it is read from ``OPENROUTER_API_KEY``.

    ``temperature`` is sent only where the model supports it (the client checks
    OpenRouter's model listing; ``openai/gpt-6.1-sol`` takes none). ``max_output_tokens``
    includes any reasoning tokens."""

    model_config = ConfigDict(extra="forbid")

    judge_model: str = DEFAULT_JUDGE_MODEL
    base_url: str = "https://openrouter.ai/api/v1"
    temperature: float | None = 0.0
    max_output_tokens: int = Field(default=24_000, ge=256)
    timeout_s: float = Field(default=300.0, gt=0)
    max_http_retries: int = Field(default=3, ge=0, le=10)
    max_attempts: int = Field(default=2, ge=1, le=5)
    concurrency: int = Field(default=4, ge=1, le=16)
    provider: dict[str, Any] | None = Field(
        default_factory=lambda: {"require_parameters": True}
    )
    reasoning: dict[str, Any] | None = None
    price_per_million_input_usd: float = Field(default=2.0, ge=0)
    price_per_million_output_usd: float = Field(default=10.0, ge=0)
    modes: list[str] = Field(default_factory=lambda: list(JUDGEABLE_MODES))
    report_assertions: bool = True
    max_report_assertions: int = Field(default=8, ge=0, le=50)
    max_span_chars: int = Field(default=6_000, ge=200)
    rubric_file: str = DEFAULT_RUBRIC
    cache_dir: str | None = None
    allow_same_family: bool = False
    app_title: str = "gb2019-sr-judge"
    scope: JudgeScope | None = None

    @field_validator("modes")
    @classmethod
    def _modes(cls, value: list[str]) -> list[str]:
        bad = [m for m in value if m not in JUDGEABLE_MODES]
        if bad:
            raise ValueError(
                f"modes {bad} cannot be judged (allowed: {list(JUDGEABLE_MODES)}; "
                "auto_numeric criteria are never sent to the judge)"
            )
        if not value:
            raise ValueError("modes must name at least one assessment mode")
        return list(dict.fromkeys(value))

    @field_validator("judge_model")
    @classmethod
    def _model(cls, value: str) -> str:
        if not api_model_id(value):
            raise ValueError("judge_model is empty")
        return value.strip()

    def rubric_path(self) -> Path:
        """The rubric file: an absolute path as given; a bare file name in
        ``private/system_response/`` (increment A's default); a relative path with a
        directory (``full_investigation/judge_rubric_v1.md``) under ``private/``."""
        path = Path(self.rubric_file)
        if path.is_absolute():
            return path
        if len(path.parts) > 1:
            return DEFAULT_PRIVATE_DIR / path
        return SYSTEM_RESPONSE_PRIVATE_DIR / path

    def public(self) -> dict[str, Any]:
        """The settings that shape a request (recorded in outputs and cache keys).
        ``scope`` appears only when the config sets one, so increment A's outputs
        are unchanged."""
        extra = {"scope": self.scope.public()} if self.scope is not None else {}
        return {
            "judge_model": api_model_id(self.judge_model),
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "max_attempts": self.max_attempts,
            "provider": self.provider,
            "reasoning": self.reasoning,
            "modes": self.modes,
            "report_assertions": self.report_assertions,
            "max_report_assertions": self.max_report_assertions,
            "max_span_chars": self.max_span_chars,
            **extra,
        }


def load_config(
    path: Path | str | None = None, *, task: str | None = None, **overrides: Any
) -> JudgeConfig:
    """A config from a JSON file (keys starting with ``_`` are comments) plus
    overrides that are not ``None``, over the ``task``'s defaults
    (:data:`TASK_CONFIG_DEFAULTS`) when a task is named."""
    data: dict[str, Any] = {}
    if task is not None:
        if task not in TASK_CONFIG_DEFAULTS:
            raise JudgeConfigError(
                f"unknown task {task!r} (known: {', '.join(TASK_CONFIG_DEFAULTS)})"
            )
        data.update(TASK_CONFIG_DEFAULTS[task])
    if path is not None:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise JudgeConfigError(f"cannot read judge config {path}: {exc}") from None
        if not isinstance(raw, dict):
            raise JudgeConfigError(f"{path}: a judge config is a JSON object")
        data.update({k: v for k, v in raw.items() if not k.startswith("_")})
    data.update({k: v for k, v in overrides.items() if v is not None})
    try:
        return JudgeConfig(**data)
    except ValueError as exc:
        raise JudgeConfigError(f"invalid judge config: {exc}") from None


def with_task_defaults(config: JudgeConfig, task: str | None) -> JudgeConfig:
    """``config`` with ``task``'s defaults (:data:`TASK_CONFIG_DEFAULTS`) for the
    settings it does not set explicitly (from a file, an override or
    ``load_config(task=...)``). A run whose task follows from its answer key (a
    full-investigation ``--key`` without ``--task``) thus gets that task's rubric and
    request scope, not increment A's. Increment A's task has no defaults: its config is
    returned unchanged."""
    defaults = TASK_CONFIG_DEFAULTS.get(task or "") or {}
    missing = {k: v for k, v in defaults.items() if k not in config.model_fields_set}
    if not missing:
        return config
    data = config.model_dump(exclude_unset=True)
    data.update(missing)
    try:
        return JudgeConfig(**data)
    except ValueError as exc:  # pragma: no cover - the defaults are valid
        raise JudgeConfigError(f"invalid judge config: {exc}") from None


def api_model_id(model: str) -> str:
    """The OpenRouter model ID (a Karotte-style ``openrouter/`` prefix removed)."""
    model = (model or "").strip()
    return model[len("openrouter/") :] if model.startswith("openrouter/") else model


# Name patterns first (a model served through another vendor keeps its family), then
# the vendor prefix of an OpenRouter-style ID.
_NAME_FAMILIES = (
    (r"claude", "anthropic"),
    (r"(?:^|[/._-])(?:chat)?gpt|(?:^|/)o[1-9](?:$|[-.])|openai", "openai"),
    (r"gemini|gemma|palm|bard", "google"),
    (r"llama", "meta"),
    (r"mistral|mixtral|codestral|ministral|magistral", "mistral"),
    (r"grok", "xai"),
    (r"deepseek", "deepseek"),
    (r"qwen", "qwen"),
    (r"command-?r|cohere", "cohere"),
)
_VENDOR_FAMILIES = {
    "anthropic": "anthropic",
    "openai": "openai",
    "google": "google",
    "meta-llama": "meta",
    "meta": "meta",
    "mistralai": "mistral",
    "x-ai": "xai",
    "xai": "xai",
    "deepseek": "deepseek",
    "qwen": "qwen",
    "cohere": "cohere",
}


def model_family(model: str | None) -> str | None:
    """The model family of a model ID (``anthropic``, ``openai``, ...), ``None`` when
    unknown."""
    if not model:
        return None
    name = api_model_id(model).lower()
    for pattern, family in _NAME_FAMILIES:
        if re.search(pattern, name):
            return family
    vendor = name.split("/", 1)[0] if "/" in name else ""
    return _VENDOR_FAMILIES.get(vendor)


def check_family(
    judge_model: str, run_model: str | None, *, allow_same_family: bool = False
) -> dict[str, Any]:
    """Refuse a judge from the evaluated model's family (or an unknown evaluated
    model) unless ``allow_same_family``; returns what to record. The evaluated model's
    ID itself is not recorded, only its family."""
    judge_family = model_family(judge_model)
    run_family = model_family(run_model)
    same = run_family is not None and judge_family == run_family
    record = {
        "judge_model_family": judge_family,
        "run_model_family": run_family,
        "run_model_known": bool(run_model),
        "same_family": same,
        "allow_same_family": allow_same_family,
    }
    if allow_same_family:
        return record
    if not run_model:
        raise JudgeConfigError(
            "the evaluated model is unknown, so the judge-family rule cannot be "
            "checked: pass --run-model (or a transcript), or --allow-same-family"
        )
    if run_family is None:
        raise JudgeConfigError(
            f"cannot tell the model family of the evaluated model {run_model!r}: "
            "pass --allow-same-family to judge anyway"
        )
    if same:
        raise JudgeConfigError(
            f"refusing judge {api_model_id(judge_model)!r}: it is from the evaluated "
            f"model's family ({run_family}); choose a judge from another family or "
            "pass --allow-same-family (recorded in the judge output)"
        )
    return record
