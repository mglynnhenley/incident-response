"""FullInvestigationJudge: run outcome, budgets and the (optional) grading hook.

As for the MVP and the system-response task, the scalar score is COMPLETION ONLY: 1.0
when a valid submission was frozen within the tool-call (150) and output-token (80,000)
budgets, else 0.0. It says nothing about the quality of the investigation.

Grading is ``environment.incident.fi_grading.grade_episode(episode_dir,
transcript_summary)``, imported when the episode is judged; its report is written to
``grade.json`` beside the episode and put in the scoring metadata. Karotte truncates
metadata strings past its limit, so the metadata may carry a truncated grade:
``grade.json`` is authoritative. An import or grading error is reported in the metadata
without changing the score. Neither the MVP grader (``environment.incident.grading``)
nor increment A's grader (``environment.incident.sr_grading``) is ever applied to this
task's episodes: their answer keys belong to other bundles.
"""

from __future__ import annotations

from typing import Any

from environment.incident.episode import FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET
from environment.tasks.gb_2019_system_response.judge import SystemResponseJudge

GRADING_MODULE = "environment.incident.fi_grading"

__all__ = ["GRADING_MODULE", "FullInvestigationJudge"]


class FullInvestigationJudge(SystemResponseJudge):
    """Judges one full-investigation episode from its ledger files and the transcript.

    The nine tools, the transcript summary and the outcome rules are increment A's
    (:class:`SystemResponseJudge`); only the grading module and the output-token budget
    are this task's own.
    """

    grading_module = GRADING_MODULE

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("output_token_budget", FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET)
        super().__init__(*args, **kwargs)
