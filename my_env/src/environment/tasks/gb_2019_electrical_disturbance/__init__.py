"""Task ``gb-2019-electrical-disturbance``: investigate the 9 August 2019 GB disturbance.

One step. The agent has exactly four tools (``list_documents``, ``request_document``,
``run_python``, ``submit_findings``), all thin adapters over
:class:`environment.incident.episode.Episode`. This module also holds the shared adapter
support (configuration, Karotte isolation hooks, result conversion) that the tool
modules in ``environment.tools`` import.

The step score is completion only (see ``judge.py``).
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Any, final

from fastmcp.tools.tool import ToolResult
from karotte import Step, Task, ToolConfigWriter, kill_processes, save_artifact
from karotte import tool_base as karotte_tool_base
from karotte.container import is_containerized
from loguru import logger
from mcp.types import TextContent
from pydantic import Field, WithJsonSchema

from environment import STUDENT_UID
from environment.incident.episode import (
    CONTEXT_CAP_TOKENS,
    OUTPUT_TOKEN_BUDGET,
    TOOL_NAMES,
    CallResult,
    Episode,
    EpisodeConfig,
)
from environment.incident.paths import DEFAULT_BUNDLE_DIR, DEFAULT_PRIVATE_DIR
from environment.incident.python_runner import NETWORK_FIREWALL, NETWORK_NAMESPACE
from environment.paths import ROOT_DATA_DIR, STUDENT_WORKDIR
from environment.system_prompts import get_system_prompt
from environment.tasks.gb_2019_electrical_disturbance.judge import EpisodeJudge
from environment.tasks.gb_2019_electrical_disturbance.prompt import (
    BRIEF,
    build_instructions,
)

TASK_ID = "gb-2019-electrical-disturbance"

__all__ = [
    "BRIEF",
    "TASK_ID",
    "GB2019ElectricalDisturbanceTask",
    "IncidentToolConfig",
    "InvestigationStep",
    "SubmissionArg",
    "TextArg",
    "call_episode_tool",
    "default_episode_dir",
    "make_episode",
    "to_tool_result",
]


# -- configuration ---------------------------------------------------------------
def default_episode_dir() -> Path:
    return ROOT_DATA_DIR / "episode"


def _default_python() -> str:
    if is_containerized():
        return str(STUDENT_WORKDIR / ".venv" / "bin" / "python")
    return sys.executable


def _default_student_uid() -> int | None:
    return STUDENT_UID if is_containerized() else None


class IncidentToolConfig(EpisodeConfig):
    """``EpisodeConfig`` with this environment's default locations.

    The task writes one of these for each of the four tools (``configure_tools``); the
    defaults only matter when a tool is constructed without a written config.
    """

    episode_dir: Path = Field(default_factory=default_episode_dir)
    evidence_dir: Path = Field(default_factory=lambda: STUDENT_WORKDIR / "evidence")
    scratch_dir: Path = Field(default_factory=lambda: STUDENT_WORKDIR / "scratch")
    bundle_dir: Path = DEFAULT_BUNDLE_DIR
    python_executable: str = Field(default_factory=_default_python)
    student_uid: int | None = Field(default_factory=_default_student_uid)


# -- MCP parameter types ---------------------------------------------------------
# FastMCP validates arguments against the Python annotations before the tool body
# runs, so with ``str | None`` a wrong-typed value (e.g. ``{"doc_id": 5}``) would be
# refused before the ledger saw it: not counted, not traced, no budget in the reply.
# These annotations accept any JSON value at validation time while advertising the
# same schema as before, so the call reaches ``Episode.call`` and is answered (and
# counted) as INVALID_ARGUMENT. An argument NAME a tool does not accept cannot be
# routed this way (FastMCP refuses ``**kwargs``): such calls are rejected by the MCP
# layer, are not counted, and show up as ``ledger_discrepancy`` in the judge's summary.
TextArg = Annotated[
    Any, WithJsonSchema({"anyOf": [{"type": "string"}, {"type": "null"}]})
]
SubmissionArg = Annotated[
    Any,
    WithJsonSchema(
        {
            "anyOf": [
                {"additionalProperties": True, "type": "object"},
                {"type": "string"},
                {"type": "null"},
            ]
        }
    ),
]


# -- Karotte isolation hooks for run_python ------------------------------------------
_netns_probe: dict[str, bool] = {}


def _network_namespace_usable(python_executable: str) -> bool:
    """Whether a student session can be started in its own network namespace.

    Probed once by starting one. Where the sandbox refuses user namespaces, the student
    is still cut off by Karotte's uid firewall (as for the ``bash`` tool), so we fall
    back to Karotte's own default rather than break every ``run_python`` call.
    """
    if python_executable not in _netns_probe:
        from karotte.subprocess import student_session_command

        argv, preexec = student_session_command(
            [python_executable, "-I", "-c", "pass"], disable_networking=True
        )
        try:
            probe = subprocess.run(
                argv,
                preexec_fn=preexec,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd="/",
                timeout=60,
                check=False,
            )
            usable = probe.returncode == 0
        except (OSError, subprocess.SubprocessError):
            usable = False
        if not usable:
            logger.warning(
                "run_python: a network namespace could not be created for the student; "
                "relying on Karotte's firewall for network isolation"
            )
        _netns_probe[python_executable] = usable
    return _netns_probe[python_executable]


class ContainerLauncher:
    """Starts ``run_python`` as a Karotte student session.

    The session gets its own network namespace (no interfaces) whenever one can be
    created, and always on gVisor, whose iptables Karotte does not trust. Where the
    sandbox refuses user namespaces (e.g. runc under Docker's default seccomp profile)
    it falls back to Karotte's own default for student sessions: the uid firewall,
    which blocks the internet but not loopback or the sandbox's own addresses, and is
    not enforced at all under ``KAROTTE_FIREWALL_TOLERATE``. :meth:`network_mode`
    reports which applies; it is shown in every ``run_python`` result
    (``data.limits.network``) and recorded in the pre-hook metadata and the episode's
    config snapshot.
    """

    def __init__(self, python_executable: str) -> None:
        self.python_executable = python_executable

    def network_mode(self) -> str:
        from karotte.confinement import network_needs_namespace

        if (
            _network_namespace_usable(self.python_executable)
            or network_needs_namespace()
        ):
            return NETWORK_NAMESPACE
        return NETWORK_FIREWALL

    def __call__(self, argv: list[str]):
        from karotte.subprocess import student_session_command

        return student_session_command(
            argv,
            0,
            1,
            2,
            disable_networking=self.network_mode() == NETWORK_NAMESPACE,
        )


def _container_cleanup() -> None:
    # Raises (e.g. karotte.UnreapableCohortError) when student processes survive; the
    # runner then fails the call closed and the ledger records it.
    kill_processes(STUDENT_UID)


def make_episode(config: EpisodeConfig) -> Episode:
    """An Episode with Karotte's student isolation injected when containerized."""
    if is_containerized():
        launcher = ContainerLauncher(config.python_executable)
        return Episode(
            config,
            launcher=launcher,
            cleanup=_container_cleanup,
            isolated=True,
            network_mode=launcher.network_mode,
        )
    return Episode(config)


def to_tool_result(result: CallResult) -> ToolResult:
    """One text block for the model (Karotte forwards only ``content[0]``) and the
    envelope as structured content."""
    return ToolResult(
        content=[TextContent(type="text", text=result.text)],
        structured_content=result.envelope,
        is_error=not result.ok,
    )


async def call_episode_tool(
    episode: Episode, tool: str, args: dict[str, Any]
) -> ToolResult:
    """Run one ledger call off the event loop (Python runs may take 30 s)."""
    result = await asyncio.to_thread(episode.call, tool, args)
    return to_tool_result(result)


# -- the task --------------------------------------------------------------------
def _answer_key_metadata() -> dict[str, Any]:
    path = DEFAULT_PRIVATE_DIR / "answer_key.json"
    try:
        key = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(key, dict):
        return {}
    meta = {}
    for name in ("key_version", "version", "review_status"):
        if name in key and isinstance(key[name], (str, int, float)):
            meta[name] = key[name]
    if "version" in meta and "key_version" not in meta:
        meta["key_version"] = meta.pop("version")
    return meta


@final
class GB2019ElectricalDisturbanceTask(Task):
    id = TASK_ID

    @property
    def system_prompt(self) -> str:
        return get_system_prompt(self.config.model, self.config.extra_config)

    @property
    def tools(self) -> list[str]:
        return list(TOOL_NAMES)

    def episode_config(self) -> IncidentToolConfig:
        return IncidentToolConfig()

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
            "output_token_budget": OUTPUT_TOKEN_BUDGET,
            "context_cap_tokens": CONTEXT_CAP_TOKENS,
        }
        return metadata

    @property
    def steps(self) -> list[Step]:
        return [InvestigationStep(config=self.config)]


class InvestigationStep(Step):
    @property
    def episode_config(self) -> IncidentToolConfig:
        return IncidentToolConfig()

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
            output_token_budget=OUTPUT_TOKEN_BUDGET,
        )

    @property
    def judge(self) -> EpisodeJudge:
        return EpisodeJudge(self.episode_config, self.config)

    def pre_scoring_hook(self) -> None:
        """Kill every student process, then save the episode directory.

        The episode directory is root-only, so it is saved even when the kill fails
        (those are the runs a reviewer most needs); the kill's error (e.g.
        ``UnreapableCohortError``, which Karotte scores as 0) is raised afterwards.
        """
        kill_error: Exception | None = None
        try:
            if is_containerized():
                kill_processes(STUDENT_UID)
        except Exception as exc:  # noqa: BLE001 - re-raised once the episode is saved
            kill_error = exc
        try:
            save_artifact(self.config, Path(self.episode_config.episode_dir))
        except Exception:
            if kill_error is None:
                raise
            logger.exception("could not save the episode directory after a failed kill")
        if kill_error is not None:
            raise kill_error
