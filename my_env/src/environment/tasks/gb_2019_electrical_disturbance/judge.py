"""EpisodeJudge: run outcome, budgets and (optionally) the grading hook.

The scalar score is COMPLETION ONLY: 1.0 when a valid submission was frozen within the
tool-call and output-token budgets, else 0.0. It says nothing about the quality of the
investigation. Quality measures (content coverage, evidence support, unsupported
assertions) come from ``environment.incident.grading`` when it is installed, are stored
in ``grade.json`` and the scoring metadata, and remain provisional until human
adjudication and domain review of the answer key.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import traceback
from pathlib import Path
from typing import Any

from karotte import EvaluationRunConfig, Judge, save_artifact
from karotte.schemas.scoring import Scoring
from karotte.schemas.transcript import Transcript
from loguru import logger

from environment.incident.episode import (
    CONTEXT_CAP_TOKENS,
    GRADE_FILE,
    OUTPUT_TOKEN_BUDGET,
    EpisodeConfig,
    build_transcript_summary,
)

GRADING_MODULE = "environment.incident.grading"

SCORE_SEMANTICS = (
    "Completion only: 1.0 means a valid submission was frozen within the tool-call and "
    "output-token budgets; 0.0 means the run is incomplete. It is NOT a quality score. "
    "Content coverage, evidence support and unsupported assertions are reported "
    "separately under 'grading' and are provisional until human adjudication."
)


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    return value


class EpisodeJudge(Judge):
    """Judges one episode from its ledger files and the run transcript."""

    def __init__(
        self,
        episode_config: EpisodeConfig,
        run_config: EvaluationRunConfig | None = None,
        *,
        output_token_budget: int = OUTPUT_TOKEN_BUDGET,
        context_cap: int | None = None,
        run_grading: bool = True,
    ) -> None:
        self.episode_config = episode_config
        self.run_config = run_config
        self.output_token_budget = output_token_budget
        if context_cap is None and run_config is not None:
            context_cap = run_config.resolve_step_context_window_limit(0)
        self.context_cap = context_cap or CONTEXT_CAP_TOKENS
        self.run_grading = run_grading

    @property
    def episode_dir(self) -> Path:
        return Path(self.episode_config.episode_dir)

    def evaluate(self, transcript: Transcript) -> Scoring:
        events = [event.model_dump(mode="json") for event in transcript.events]
        summary = build_transcript_summary(
            self.episode_dir,
            events,
            max_tool_calls=self.episode_config.max_tool_calls,
            output_token_budget=self.output_token_budget,
            context_cap=self.context_cap,
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
        """Run ``grade_episode`` if available. Never raises: grading problems (also
        while importing the grading module) are reported, so the completion outcome
        is always scored."""
        try:
            grading = importlib.import_module(GRADING_MODULE)
        except ModuleNotFoundError as exc:
            if exc.name != GRADING_MODULE:
                logger.error("grading import failed: {}", traceback.format_exc())
                return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
            return {
                "status": "unavailable",
                "reason": f"{GRADING_MODULE} not installed",
            }
        except Exception as exc:  # noqa: BLE001 - grading must not crash the run
            logger.error("grading import failed: {}", traceback.format_exc())
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        grade_episode = getattr(grading, "grade_episode", None)
        if grade_episode is None:
            return {"status": "unavailable", "reason": "grade_episode() not provided"}
        try:
            result = _jsonable(grade_episode(self.episode_dir, summary))
            # Plain JSON only, so the scoring metadata always serialises.
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
