"""Karotte adapter for ``request_document`` (see ``environment.incident.episode``).

Under the MVP profile the tool takes ``doc_id`` only (description and schema
unchanged). Under the system-response profile (task ``gb-2019-system-response``) each
instance registers :func:`_system_response_call`, which also takes ``party`` and
``description``, with that task's description (``apply_tool_profile``).
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


@final
class request_document(ToolBase[IncidentToolConfig]):
    config_schema = IncidentToolConfig

    def __init__(self) -> None:
        super().__init__()
        self._episode = make_episode(self.config)
        apply_tool_profile(self, "request_document", _system_response_call)

    async def __call__(self, doc_id: TextArg = None) -> ToolResult:
        """Retrieve one document by its exact ID as shown by list_documents (e.g. "R01").

        Returns the document's text with line numbers. The line numbers are citation
        locators: cite them as {"evidence_id": "<ID>", "locator": "L12"} or "L12-L18".
        The document's files (for example a CSV time series) are also written, read-only,
        under the directory named by the EVIDENCE_DIR environment variable of run_python,
        at the relative paths listed in `artifacts`. A time series can also be cited as
        "time:<ISO-8601 with UTC offset>", "time:<start>/<end>", "row:<n>" or
        "rows:<a>-<b>".

        Every call, including one with invalid argument values, uses 1 of your
        50 tool calls. A call with an argument name this tool does not accept is
        rejected before it reaches the investigation and is not counted.
        """
        return await call_episode_tool(
            self._episode, "request_document", {"doc_id": doc_id}
        )


async def _system_response_call(
    self,
    doc_id: TextArg = None,
    party: TextArg = None,
    description: TextArg = None,
) -> ToolResult:
    """Retrieve one document by doc_id, or by party and description."""
    return await call_episode_tool(
        self._episode,
        "request_document",
        {"doc_id": doc_id, "party": party, "description": description},
    )
