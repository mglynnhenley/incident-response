"""Karotte adapter for ``list_documents`` (see ``environment.incident.episode``)."""

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


@final
class list_documents(ToolBase[IncidentToolConfig]):
    config_schema = IncidentToolConfig

    def __init__(self) -> None:
        super().__init__()
        self._episode = make_episode(self.config)
        apply_tool_profile(self, "list_documents")

    async def __call__(
        self, category: TextArg = None, cursor: TextArg = None
    ) -> ToolResult:
        """List the evidence catalogue: document IDs, neutral titles, owners, dates and categories.

        `category` (optional) limits the list to one of: measurement_data,
        network_records, generator_records, personnel_accounts. Results come in pages of
        up to 50 documents; to get the next page, pass the returned `next_cursor` as
        `cursor` (null means there are no more).

        Every call, including one with invalid argument values, uses 1 of your
        50 tool calls; each result reports the calls used and remaining. A call with an
        argument name this tool does not accept is rejected before it reaches the
        investigation and is not counted.
        """
        return await call_episode_tool(
            self._episode, "list_documents", {"category": category, "cursor": cursor}
        )
