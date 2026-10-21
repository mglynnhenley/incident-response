"""SystemResponseJudge: run outcome, budgets and the (optional) grading hook.

As for the MVP task, the scalar score is COMPLETION ONLY: 1.0 when a valid submission
was frozen within the tool-call (150) and output-token budgets, else 0.0. It says
nothing about the quality of the investigation.

Grading is ``environment.incident.sr_grading.grade_episode(episode_dir,
transcript_summary)``, imported when the episode is judged: its (provisional) report is
stored in ``grade.json`` and the scoring metadata; if the module or the function is
missing the metadata says grading is unavailable, and a grading error is reported there
without changing the score. The MVP grader (``environment.incident.grading``) is never
applied to this task's episodes: its answer key belongs to the MVP bundle.
"""

from __future__ import annotations

import importlib
import json
import traceback
from typing import Any

from karotte import save_artifact
from karotte.schemas.scoring import Scoring
from karotte.schemas.transcript import Transcript
from loguru import logger

from environment.incident.episode import (
    GRADE_FILE,
    SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET,
    SYSTEM_RESPONSE_TOOL_NAMES,
    build_transcript_summary,
)
from environment.tasks.gb_2019_electrical_disturbance.judge import (
    SCORE_SEMANTICS,
    EpisodeJudge,
    _jsonable,
)

GRADING_MODULE = "environment.incident.sr_grading"

__all__ = ["GRADING_MODULE", "SystemResponseJudge"]


class SystemResponseJudge(EpisodeJudge):
    """Judges one system-response episode from its ledger files and the transcript."""

    grading_module = GRADING_MODULE

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("output_token_budget", SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET)
        super().__init__(*args, **kwargs)

    def evaluate(self, transcript: Transcript) -> Scoring:
        events = [event.model_dump(mode="json") for event in transcript.events]
        summary = build_transcript_summary(
            self.episode_dir,
            events,
            max_tool_calls=self.episode_config.max_tool_calls,
            output_token_budget=self.output_token_budget,
            context_cap=self.context_cap,
            tool_names=SYSTEM_RESPONSE_TOOL_NAMES,
        )
        grading = self._grade(summary) if self.run_grading else {"status": "disabled"}
        complete = summary["outcome"] == "complete"
        metadata = {
            "score_semantics": SCORE_SEMANTICS,
            "outcome": summary["outcome"],
            "incomplete_reason": summary["incomplete_reason"],
            "incomplete_reasons": summary["incomplete_reasons"],
            "provisional": True,
            "transcript_summary": summary,
            "grading": grading,
        }
        return Scoring(
            score=1.0 if complete else 0.0,
            metadata=metadata,
            continue_task=complete,
        )

    def _grade(self, summary: dict[str, Any]) -> dict[str, Any]:
        """Run ``grade_episode`` from :attr:`grading_module` if it exists. Never
        raises: grading problems are reported, so the outcome is always scored."""
        name = self.grading_module
        try:
            grading = importlib.import_module(name)
        except ModuleNotFoundError as exc:
            if exc.name != name:
                logger.error("grading import failed: {}", traceback.format_exc())
                return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
            return {"status": "unavailable", "reason": f"{name} not installed"}
        except Exception as exc:  # noqa: BLE001 - grading must not crash the run
            logger.error("grading import failed: {}", traceback.format_exc())
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        grade_episode = getattr(grading, "grade_episode", None)
        if grade_episode is None:
            return {"status": "unavailable", "reason": "grade_episode() not provided"}
        try:
            result = _jsonable(grade_episode(self.episode_dir, summary))
            result = json.loads(json.dumps(result, ensure_ascii=False, default=str))
        except Exception as exc:  # noqa: BLE001 - grading must not crash the run
            logger.error("grading failed: {}", traceback.format_exc())
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        grade_path = self.episode_dir / GRADE_FILE
        try:
            grade_path.write_text(
                json.dumps(
                    result, indent=2, sort_keys=True, ensure_ascii=False, default=str
                )
                + "\n",
                encoding="utf-8",
            )
            if self.run_config is not None:
                save_artifact(self.run_config, grade_path)
        except (OSError, TypeError, ValueError) as exc:
            return {
                "status": "graded",
                "grade": result,
                "write_error": f"{type(exc).__name__}: {exc}",
            }
        return {"status": "graded", "grade": result, "grade_file": str(grade_path)}
