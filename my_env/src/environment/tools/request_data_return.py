"""Karotte adapter for ``request_data_return`` (see ``environment.incident.episode``).

Used by task ``gb-2019-system-response`` only; the description is
``environment.tasks.gb_2019_system_response.prompt.TOOL_DESCRIPTIONS["request_data_return"]`` with
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
class request_data_return(ToolBase[IncidentToolConfig]):
    config_schema = IncidentToolConfig

    def __init__(self) -> None:
        super().__init__()
        self._episode = make_episode(self.config)
        apply_tool_profile(self, "request_data_return", always=True)

    async def __call__(
        self,
        party: TextArg = None,
        data_type: TextArg = None,
    ) -> ToolResult:
        """Ask a party for a registered data return."""
        return await call_episode_tool(
            self._episode,
            "request_data_return",
            {"party": party, "data_type": data_type},
        )


request_data_return.__call__.__doc__ = tool_description("request_data_return")
