"""Karotte adapter for ``query_control_log`` (see ``environment.incident.episode``).

Used by task ``gb-2019-system-response`` only; the description is
``environment.tasks.gb_2019_system_response.prompt.TOOL_DESCRIPTIONS["query_control_log"]`` with
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
class query_control_log(ToolBase[IncidentToolConfig]):
    config_schema = IncidentToolConfig

    def __init__(self) -> None:
        super().__init__()
        self._episode = make_episode(self.config)
        apply_tool_profile(self, "query_control_log", always=True)

    async def __call__(
        self,
        room: TextArg = None,
        start: TextArg = None,
        end: TextArg = None,
        cursor: TextArg = None,
    ) -> ToolResult:
        """Read one control room's log entries for a time window."""
        return await call_episode_tool(
            self._episode,
            "query_control_log",
            {"room": room, "start": start, "end": end, "cursor": cursor},
        )


query_control_log.__call__.__doc__ = tool_description("query_control_log")
