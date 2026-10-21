"""Karotte adapter for ``query_frequency`` (see ``environment.incident.episode``).

Used by task ``gb-2019-system-response`` only; the description is
``environment.tasks.gb_2019_system_response.prompt.TOOL_DESCRIPTIONS["query_frequency"]`` with
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
from environment.tasks.gb_2019_system_response import (
    NumberArg,
    apply_tool_profile,
)
from environment.tasks.gb_2019_system_response.prompt import tool_description


@final
class query_frequency(ToolBase[IncidentToolConfig]):
    config_schema = IncidentToolConfig

    def __init__(self) -> None:
        super().__init__()
        self._episode = make_episode(self.config)
        apply_tool_profile(self, "query_frequency", always=True)

    async def __call__(
        self,
        start: TextArg = None,
        end: TextArg = None,
        resolution_s: NumberArg = None,
        cursor: TextArg = None,
    ) -> ToolResult:
        """Read the measured system frequency record for a time window."""
        return await call_episode_tool(
            self._episode,
            "query_frequency",
            {
                "start": start,
                "end": end,
                "resolution_s": resolution_s,
                "cursor": cursor,
            },
        )


query_frequency.__call__.__doc__ = tool_description("query_frequency")
