"""Task ``gb-2019-full-investigation``: the 9 August 2019 incident and its consequences.

Increment B. One step and the same nine tools as increment A
(``environment.incident.episode.SYSTEM_RESPONSE_TOOL_NAMES``), all thin adapters over
:class:`environment.incident.episode.Episode`, now running on the manifest-v2 bundle
``environment/incident/bundles/full_investigation`` (increment A's bundle, copied with
the same IDs, plus the rail, essential-services, communications and compliance
evidence). The task writes its tool configuration with increment A's ``tool_profile``
(``"system_response"``), so every tool keeps increment A's description and schema; only
the bundle differs. The MVP task and increment A's task ``gb-2019-system-response`` are
frozen and unchanged.

Budgets: 150 tool calls, an 80,000-token output budget
(:data:`~environment.incident.episode.FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET`) and the
200,000-token context cap; the instructions state what reaching the cap does and the size
of the evidence (decision 53: an increment-A-style full read would reach the cap, to be
confirmed by a pilot before the panel). The bundle is never loaded at import time; ``pre_hook``
verifies it (fail closed). The step score is completion only (see ``judge.py``), and
grading is ``environment.incident.fi_grading.grade_episode`` once that module exists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, final

from karotte import Step, Task, ToolConfigWriter
from karotte import tool_base as karotte_tool_base
from pydantic import Field

from environment.incident.episode import (
    CONTEXT_CAP_TOKENS,
    FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET,
    SYSTEM_RESPONSE_TOOL_NAMES,
)
from environment.incident.paths import (
    FULL_INVESTIGATION_BUNDLE_DIR,
    FULL_INVESTIGATION_PRIVATE_DIR,
)
from environment.system_prompts import get_system_prompt
from environment.tasks.gb_2019_electrical_disturbance import (
    IncidentToolConfig,
    InvestigationStep,
    make_episode,
)
from environment.tasks.gb_2019_full_investigation.judge import (
    FullInvestigationJudge,
)
from environment.tasks.gb_2019_full_investigation.prompt import (
    BRIEF,
    build_instructions,
)

TASK_ID = "gb-2019-full-investigation"
MAX_TOOL_CALLS = 150
TOOL_NAMES = SYSTEM_RESPONSE_TOOL_NAMES
KEY_CANDIDATES = (FULL_INVESTIGATION_PRIVATE_DIR / "answer_key.json",)

__all__ = [
    "BRIEF",
    "MAX_TOOL_CALLS",
    "TASK_ID",
    "TOOL_NAMES",
    "FullInvestigationStep",
    "FullInvestigationToolConfig",
    "GB2019FullInvestigationTask",
]


class FullInvestigationToolConfig(IncidentToolConfig):
    """The tool configuration this task writes for each of its nine tools.

    Every field lives on ``EpisodeConfig``, so the shared tool modules (whose
    ``config_schema`` is ``IncidentToolConfig``) read it unchanged. The profile is
    increment A's: the tools, their descriptions and their schemas are the same.
    """

    bundle_dir: Path = FULL_INVESTIGATION_BUNDLE_DIR
    max_tool_calls: int = Field(default=MAX_TOOL_CALLS, ge=1)
    tool_profile: Literal["mvp", "system_response"] = "system_response"


def _answer_key_metadata() -> dict[str, Any]:
    """Version and review status of this task's key, if it exists yet (never raises)."""
    for path in KEY_CANDIDATES:
        try:
            key = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(key, dict):
            continue
        meta = {
            name: key[name]
            for name in ("key_version", "version", "review_status")
            if isinstance(key.get(name), (str, int, float))
        }
        if "version" in meta and "key_version" not in meta:
            meta["key_version"] = meta.pop("version")
        meta["key_file"] = path.name
        return meta
    return {}


@final
class GB2019FullInvestigationTask(Task):
    id = TASK_ID

    @property
    def system_prompt(self) -> str:
        return get_system_prompt(self.config.model, self.config.extra_config)

    @property
    def tools(self) -> list[str]:
        return list(TOOL_NAMES)

    def episode_config(self) -> FullInvestigationToolConfig:
        return FullInvestigationToolConfig()

    def configure_tools(self) -> None:
        config = self.episode_config()
        # Read the directory at call time so it can be redirected (tests).
        writer = ToolConfigWriter(karotte_tool_base.CONFIGS_DIR)
        for name in TOOL_NAMES:
            writer.write(name, config)

    def pre_hook(self) -> dict[str, Any]:
        config = self.episode_config()
        metadata = make_episode(config).reset()
        metadata["task_id"] = self.id
        metadata.update(_answer_key_metadata())
        metadata["budgets"] = {
            **metadata.get("budgets", {}),
            "output_token_budget": FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET,
            "context_cap_tokens": CONTEXT_CAP_TOKENS,
        }
        return metadata

    @property
    def steps(self) -> list[Step]:
        return [FullInvestigationStep(config=self.config)]


class FullInvestigationStep(InvestigationStep):
    """The investigation step (``pre_scoring_hook`` as the MVP: kill student
    processes, then save the episode directory)."""

    @property
    def episode_config(self) -> FullInvestigationToolConfig:
        return FullInvestigationToolConfig()

    @property
    def instructions(self) -> str:
        cfg = self.episode_config
        return build_instructions(
            max_tool_calls=cfg.max_tool_calls,
            python_timeout_s=cfg.python_timeout_s,
            python_memory_bytes=cfg.python_memory_bytes,
            max_output_chars=cfg.max_output_chars,
            exec_summary_word_limit=cfg.exec_summary_word_limit,
            variant_id=cfg.variant_id,
            context_cap_tokens=CONTEXT_CAP_TOKENS,
            output_token_budget=FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET,
            frequency_page_size=cfg.frequency_page_size,
            log_page_size=cfg.log_page_size,
            list_page_size=cfg.list_page_size,
        )

    @property
    def judge(self) -> FullInvestigationJudge:
        return FullInvestigationJudge(self.episode_config, self.config)
