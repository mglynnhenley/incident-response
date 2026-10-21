"""Karotte adapter for ``interview_witness`` (see ``environment.incident.episode``).

Used by task ``gb-2019-system-response`` only; the description is
``environment.tasks.gb_2019_system_response.prompt.TOOL_DESCRIPTIONS["interview_witness"]`` with
the configured limits.
"""

from typing import final

from fastmcp.tools.tool import ToolResult
from karotte import ToolBase

from environment.tasks.gb_2019_electrical_disturbance import (
    IncidentToolConfig,
    TextArg,
    call_episode_tool,
    make_episode,
)
from environment.tasks.gb_2019_system_response import apply_tool_profile
from environment.tasks.gb_2019_system_response.prompt import tool_description


@final
class interview_witness(ToolBase[IncidentToolConfig]):
    config_schema = IncidentToolConfig

    def __init__(self) -> None:
        super().__init__()
        self._episode = make_episode(self.config)
        apply_tool_profile(self, "interview_witness", always=True)

    async def __call__(
        self,
        persona_id: TextArg = None,
        question: TextArg = None,
    ) -> ToolResult:
        """Put one question to a witness and receive an approved answer."""
        return await call_episode_tool(
            self._episode,
            "interview_witness",
            {"persona_id": persona_id, "question": question},
        )


interview_witness.__call__.__doc__ = tool_description("interview_witness")
