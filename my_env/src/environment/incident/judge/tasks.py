"""Which grader, key, bundle and output budget a judge run uses.

The judge track serves increment A's task (``gb-2019-system-response``, grader
:mod:`environment.incident.sr_grading`, the default and unchanged) and the full
investigation (``gb-2019-full-investigation``, grader
:mod:`environment.incident.fi_grading`, built on increment A's grader with the same
judge-output interface). A run's task follows from its answer key's schema, or from
``--task`` on the command line, which also selects the task's judge-config defaults
(:data:`~.config.TASK_CONFIG_DEFAULTS`: the full investigation's rubric and per-topic
request scope, decision 52).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from environment.incident import fi_grading, sr_grading
from environment.incident.episode import (
    FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET,
    SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET,
)
from environment.incident.grading import GradingError
from environment.incident.paths import (
    FULL_INVESTIGATION_BUNDLE_DIR,
    SYSTEM_RESPONSE_BUNDLE_DIR,
)

from .config import FULL_INVESTIGATION_TASK, SYSTEM_RESPONSE_TASK

__all__ = [
    "FULL_INVESTIGATION",
    "SYSTEM_RESPONSE",
    "TASKS",
    "GradingTask",
    "load_key",
    "task_for_key",
]


@dataclass(frozen=True)
class GradingTask:
    task_id: str
    grader: ModuleType
    key_schema: str
    bundle_dir: Path
    output_token_budget: int


SYSTEM_RESPONSE = GradingTask(
    task_id=SYSTEM_RESPONSE_TASK,
    grader=sr_grading,
    key_schema=sr_grading.KEY_SCHEMA,
    bundle_dir=SYSTEM_RESPONSE_BUNDLE_DIR,
    output_token_budget=SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET,
)
FULL_INVESTIGATION = GradingTask(
    task_id=FULL_INVESTIGATION_TASK,
    grader=fi_grading,
    key_schema=fi_grading.KEY_SCHEMA,
    bundle_dir=FULL_INVESTIGATION_BUNDLE_DIR,
    output_token_budget=FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET,
)
TASKS = {t.task_id: t for t in (SYSTEM_RESPONSE, FULL_INVESTIGATION)}


def task_for_key(key: Mapping[str, Any] | None) -> GradingTask:
    """The task of an answer key (by its ``key_schema``); increment A's when ``None``
    or unrecognised (its grader then reports what is wrong with the key)."""
    if key is not None:
        for task in TASKS.values():
            if key.get("key_schema") == task.key_schema:
                return task
    return SYSTEM_RESPONSE


def load_key(path: Path | str | None = None, task: str | None = None) -> dict[str, Any]:
    """An answer key: the file at ``path`` with the grader its schema names (or
    ``task``'s grader), else ``task``'s private key (increment A's by default)."""
    if path is None:
        return TASKS[task or SYSTEM_RESPONSE_TASK].grader.load_key()
    if task is None:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GradingError(f"cannot load the answer key {path}: {exc}") from None
        grader = task_for_key(raw if isinstance(raw, Mapping) else None).grader
    else:
        grader = TASKS[task].grader
    return grader.load_key(path)
