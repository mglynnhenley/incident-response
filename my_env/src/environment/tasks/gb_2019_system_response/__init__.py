"""Task ``gb-2019-system-response``: the 9 August 2019 disturbance and the system's response.

One step, nine tools (``environment.incident.episode.SYSTEM_RESPONSE_TOOL_NAMES``), all
thin adapters over :class:`environment.incident.episode.Episode` running on the
manifest-v2 bundle ``environment/incident/bundles/system_response``. The MVP task
``gb-2019-electrical-disturbance`` is unchanged and shares the four MVP tool modules:
under this task's ``tool_profile`` ("system_response") each adapter instance takes the
descriptions in :mod:`.prompt` (150-call budget, record locators) and
``request_document`` also accepts ``party`` + ``description``
(:func:`apply_tool_profile`).

The bundle is never loaded at import time; ``pre_hook`` verifies it (fail closed).
The step score is completion only (see ``judge.py``).
"""

from __future__ import annotations

import json
import types
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal, final

from karotte import Step, Task, ToolConfigWriter
from karotte import tool_base as karotte_tool_base
from pydantic import Field, WithJsonSchema

from environment.incident.episode import (
    CONTEXT_CAP_TOKENS,
    SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET,
    SYSTEM_RESPONSE_TOOL_NAMES,
)
from environment.incident.paths import (
    DEFAULT_PRIVATE_DIR,
    SYSTEM_RESPONSE_BUNDLE_DIR,
    SYSTEM_RESPONSE_PRIVATE_DIR,
)
from environment.system_prompts import get_system_prompt
from environment.tasks.gb_2019_electrical_disturbance import (
    IncidentToolConfig,
    InvestigationStep,
    make_episode,
)
from environment.tasks.gb_2019_system_response.judge import SystemResponseJudge
from environment.tasks.gb_2019_system_response.prompt import (
    BRIEF,
    build_instructions,
    tool_description,
)

TASK_ID = "gb-2019-system-response"
MAX_TOOL_CALLS = 150
KEY_CANDIDATES = (
    SYSTEM_RESPONSE_PRIVATE_DIR / "answer_key.json",
    DEFAULT_PRIVATE_DIR / "system_response_key.json",
)

__all__ = [
    "BRIEF",
    "MAX_TOOL_CALLS",
    "TASK_ID",
    "GB2019SystemResponseTask",
    "NumberArg",
    "SystemResponseStep",
    "SystemResponseToolConfig",
    "apply_tool_profile",
]

# Like ``TextArg``: any JSON value passes the MCP layer (so a wrong-typed value is
# answered and counted by the ledger as INVALID_ARGUMENT), while the advertised schema
# is a number or null.
NumberArg = Annotated[
    Any, WithJsonSchema({"anyOf": [{"type": "number"}, {"type": "null"}]})
]


class SystemResponseToolConfig(IncidentToolConfig):
    """The tool configuration this task writes for each of its nine tools.

    Every field lives on ``EpisodeConfig``, so the shared MVP tool modules (whose
    ``config_schema`` is ``IncidentToolConfig``) read it unchanged.
    """

    bundle_dir: Path = SYSTEM_RESPONSE_BUNDLE_DIR
    max_tool_calls: int = Field(default=MAX_TOOL_CALLS, ge=1)
    tool_profile: Literal["mvp", "system_response"] = "system_response"


def _with_doc(function: Callable[..., Any], doc: str) -> Callable[..., Any]:
    copy = types.FunctionType(
        function.__code__,
        function.__globals__,
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    copy.__kwdefaults__ = function.__kwdefaults__
    copy.__annotations__ = dict(function.__annotations__)
    copy.__qualname__ = function.__qualname__
    copy.__module__ = function.__module__
    copy.__doc__ = doc
    return copy


def apply_tool_profile(
    tool: Any,
    name: str,
    system_response_call: Callable[..., Any] | None = None,
    *,
    always: bool = False,
) -> None:
    """Give a tool adapter instance its system-response description (and signature).

    Karotte registers ``tool_instance.__call__``; under the ``system_response`` profile
    (or ``always``, for tools that only this task uses) the instance gets its own bound
    ``__call__`` whose docstring is :func:`.prompt.tool_description` with the
    configured limits, and whose signature is ``system_response_call`` when given (e.g.
    ``request_document`` with ``party`` and ``description``). Under the MVP profile
    the class's ``__call__`` (description and schema) is left untouched.
    """
    config = tool.config
    if not always and getattr(config, "tool_profile", "mvp") != "system_response":
        return
    function = system_response_call or type(tool).__call__
    tool.__call__ = types.MethodType(
        _with_doc(function, tool_description(name, config)), tool
    )


def _answer_key_metadata() -> dict[str, Any]:
    for path in KEY_CANDIDATES:
        try:
            key = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
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
class GB2019SystemResponseTask(Task):
    id = TASK_ID

    @property
    def system_prompt(self) -> str:
        return get_system_prompt(self.config.model, self.config.extra_config)

    @property
    def tools(self) -> list[str]:
        return list(SYSTEM_RESPONSE_TOOL_NAMES)

    def episode_config(self) -> SystemResponseToolConfig:
        return SystemResponseToolConfig()

    def configure_tools(self) -> None:
        config = self.episode_config()
        # Read the directory at call time so it can be redirected (tests).
        writer = ToolConfigWriter(karotte_tool_base.CONFIGS_DIR)
        for name in SYSTEM_RESPONSE_TOOL_NAMES:
            writer.write(name, config)

    def pre_hook(self) -> dict[str, Any]:
        config = self.episode_config()
        metadata = make_episode(config).reset()
        metadata["task_id"] = self.id
        metadata.update(_answer_key_metadata())
        metadata["budgets"] = {
            **metadata.get("budgets", {}),
            "output_token_budget": SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET,
            "context_cap_tokens": CONTEXT_CAP_TOKENS,
        }
        return metadata

    @property
    def steps(self) -> list[Step]:
        return [SystemResponseStep(config=self.config)]


class SystemResponseStep(InvestigationStep):
    """The investigation step (``pre_scoring_hook`` as the MVP: kill student
    processes, then save the episode directory)."""

    @property
    def episode_config(self) -> SystemResponseToolConfig:
        return SystemResponseToolConfig()

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
            output_token_budget=SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET,
            frequency_page_size=cfg.frequency_page_size,
            log_page_size=cfg.log_page_size,
        )

    @property
    def judge(self) -> SystemResponseJudge:
        return SystemResponseJudge(self.episode_config, self.config)
