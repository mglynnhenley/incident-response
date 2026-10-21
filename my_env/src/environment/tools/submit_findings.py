"""Karotte adapter for ``submit_findings`` (see ``environment.incident.submission``)."""

from typing import final

from fastmcp.tools.tool import ToolResult
from karotte import ToolBase

from environment.tasks.gb_2019_electrical_disturbance import (
    IncidentToolConfig,
    SubmissionArg,
    call_episode_tool,
    make_episode,
)
from environment.tasks.gb_2019_system_response import apply_tool_profile


@final
class submit_findings(ToolBase[IncidentToolConfig]):
    config_schema = IncidentToolConfig

    def __init__(self) -> None:
        super().__init__()
        self._episode = make_episode(self.config)
        apply_tool_profile(self, "submit_findings")

    async def __call__(self, submission: SubmissionArg = None) -> ToolResult:
        """Submit your investigation as one v3 JSON object (pass the object or its JSON text).

        The format is given in the task instructions: schema_version "3.0", variant_id
        "baseline", a report (an executive_summary of at most 600 words plus sections of
        {heading, body}) and findings, each with finding_id, statement, status (observed,
        reported, inferred, hypothesis or unknown), citations [{evidence_id, locator}]
        and optional quantity, event_time and derivation.

        An invalid submission is not saved: the result lists every problem as
        {path, message}; fix them and submit again while budget remains. The first valid
        submission is final and closes the investigation; after it is accepted, end
        your turn without further tool calls.

        Every call, including an invalid submission, uses 1 of your 50 tool calls. A
        call with an argument name this tool does not accept is rejected before it
        reaches the investigation and is not counted.
        """
        return await call_episode_tool(
            self._episode, "submit_findings", {"submission": submission}
        )
