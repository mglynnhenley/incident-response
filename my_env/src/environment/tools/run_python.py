"""Karotte adapter for ``run_python`` (see ``environment.incident.python_runner``).

In the container the code runs as the unprivileged student
(``karotte.subprocess.student_session_command``), in its own network namespace where
the sandbox allows one and otherwise behind Karotte's student firewall (reported in
``data.limits.network``); every student process is killed after each call
(``karotte.kill_processes``), and the call fails closed if that cannot be confirmed.
Outside a container it runs in local development mode, where isolation is not enforced
and the result says so.
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
class run_python(ToolBase[IncidentToolConfig]):
    config_schema = IncidentToolConfig

    def __init__(self) -> None:
        super().__init__()
        self._episode = make_episode(self.config)
        apply_tool_profile(self, "run_python")

    async def __call__(self, code: TextArg = None) -> ToolResult:
        """Run Python 3.12 code (numpy and pandas available) in a fresh process; returns stdout and stderr.

        Retrieved documents are read-only under os.environ["EVIDENCE_DIR"] (only documents
        already fetched with request_document are there), e.g.
        pandas.read_csv(os.path.join(os.environ["EVIDENCE_DIR"], "R01", "<file>.csv")).
        The working directory is a scratch directory that persists between calls (also
        os.environ["SCRATCH_DIR"]); Python variables do not persist. No network access.
        Each call may use at most 30 seconds of wall time and 1 GiB of memory; stdout and
        stderr are each cut off after 20000 characters, so print summaries rather than
        whole tables. Files created or changed in the scratch directory are listed.

        Every call, including one with invalid argument values, uses 1 of your
        50 tool calls. A call with an argument name this tool does not accept is
        rejected before it reaches the investigation and is not counted.
        """
        return await call_episode_tool(self._episode, "run_python", {"code": code})
