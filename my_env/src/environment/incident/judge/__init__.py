"""LLM judge for the system-response task (``gb-2019-system-response``), decision 25,
and the full investigation (``gb-2019-full-investigation``, :mod:`.tasks`).

The judge proposes values for the key's interpretive criteria (``judge`` mode; the
``auto_assisted_human`` criteria are judged too, as notes for the reviewer) and
verdicts for the submission's factual assertions. Its output goes through
:func:`environment.incident.sr_grading.merge_judge_proposals`: judge values are
proposals a human signs off, never final decisions, never values of ``auto_numeric``
criteria (which are never sent), and severe flags are only suggested.

* Model: ``openai/gpt-6.1-sol`` through OpenRouter's OpenAI-compatible API by default
  (configurable, ``configs/judge.example.json``). A judge from the evaluated model's
  family is refused unless ``--allow-same-family`` is given.
* Key: ``OPENROUTER_API_KEY`` from the environment, never logged or written.
* Request: temperature 0 where supported, structured output (``json_schema``, strict).
* Input: the blinded submission, the criterion rubric (expectation, accepted
  alternatives, examples), the resolved cited spans and keyed visible-evidence spans
  (:mod:`.prompt`). Never provenance, source PDFs, the automated pre-screen or other
  runs. By default every request carries the whole submission and every cited span
  (increment A, unchanged). A task or key can opt in to per-topic scoping (decision 52,
  :class:`JudgeScope`, :mod:`.scope`): each topic's request then carries only its own
  findings, the report text that refers to them, their cited spans and its keyed spans,
  plus a compact list of the other findings. The full investigation does
  (``configs/judge.fi.example.json``, rubric
  ``private/full_investigation/judge_rubric_v1.md``).
* Checks: schema validation with one repair attempt, unknown IDs dropped, every
  returned quote verified against the span text shown (hallucinated spans dropped and
  counted), unsupported "evidence 1" and verdicts withheld for a human (:mod:`.verify`).
* Cache: by sha256 of (submission, bundle, key, rubric version and sha, judge model,
  prompt template sha, request settings, unit, messages) under the output directory or
  a configured directory; re-runs are free and reproduce the same output.
* Cost: provider-reported usage and cost per request (estimated from configured prices
  when the provider gives none), in the judge output and the run log.

Command line: ``python -m environment.incident.judge run <episode_dir>`` (see
``--help``). This package must not import ``karotte``.
"""

from __future__ import annotations

from .cache import JudgeCache, cache_key
from .client import (
    API_KEY_ENV,
    ChatClient,
    ChatResponse,
    JudgeClientError,
    OpenRouterClient,
)
from .config import (
    DEFAULT_JUDGE_MODEL,
    TASK_CONFIG_DEFAULTS,
    JudgeConfig,
    JudgeConfigError,
    JudgeScope,
    api_model_id,
    check_family,
    load_config,
    model_family,
    resolve_scope,
    with_task_defaults,
)
from .prompt import (
    PROMPT_VERSION,
    TOPIC_PROMPT_VERSION,
    build_units,
    load_rubric,
    prompt_template_sha256,
    prompt_version,
)
from .runner import (
    JudgeError,
    JudgeResult,
    JudgeRun,
    judge_episode,
    judge_submission,
    judge_submission_file,
    parse_response,
    plan_submission,
    request_payload,
    usage_cost,
)
from .schema import RESPONSE_SCHEMA, RESPONSE_SCHEMA_ID
from .tasks import TASKS, GradingTask, task_for_key

__all__ = [
    "API_KEY_ENV",
    "DEFAULT_JUDGE_MODEL",
    "PROMPT_VERSION",
    "RESPONSE_SCHEMA",
    "RESPONSE_SCHEMA_ID",
    "TASKS",
    "TASK_CONFIG_DEFAULTS",
    "TOPIC_PROMPT_VERSION",
    "ChatClient",
    "ChatResponse",
    "GradingTask",
    "JudgeCache",
    "JudgeClientError",
    "JudgeConfig",
    "JudgeConfigError",
    "JudgeError",
    "JudgeResult",
    "JudgeRun",
    "JudgeScope",
    "OpenRouterClient",
    "api_model_id",
    "build_units",
    "cache_key",
    "check_family",
    "judge_episode",
    "judge_submission",
    "judge_submission_file",
    "load_config",
    "load_rubric",
    "model_family",
    "parse_response",
    "plan_submission",
    "prompt_template_sha256",
    "prompt_version",
    "request_payload",
    "resolve_scope",
    "task_for_key",
    "usage_cost",
    "with_task_defaults",
]
