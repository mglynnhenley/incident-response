"""Command line for the LLM judge (increment A's task by default; ``--task
gb-2019-full-investigation``, or a full-investigation ``--key``, for the full
investigation, whose defaults are its rubric and per-topic request scope).

    python -m environment.incident.judge run <episode_dir | submission.json> [options]
    python -m environment.incident.judge run <target> --dry-run      # plan and cost, no calls
    python -m environment.incident.judge run <target> --cache-only   # replay from cache
    python -m environment.incident.judge prompt <target> [--unit T06] # show what is sent
    python -m environment.incident.judge merge <target> --judge-output FILE [--decisions F]

``run`` grades the target, sends one request per unit to the judge (``openai/gpt-6.1-sol``
via OpenRouter unless configured otherwise; ``OPENROUTER_API_KEY`` must be set, or
``--env-file`` names a file that sets it), checks and caches the responses, and writes
``judge_output.json``, ``judge_run.json`` and the merged ``grade.json`` to
``<episode_dir>/judge/`` (or ``--out-dir``; required for a submission file). The
evaluated model is read from the run's transcript or ``--run-model``: a judge of the
same family is refused unless ``--allow-same-family``. A run costs money unless every
request is cached: check with ``--dry-run`` first.

``--task gb-2019-full-investigation`` selects that task's key, bundle, grader, output
budget and judge-config defaults (``configs/judge.fi.example.json`` spells them out);
without it the task follows the key's schema (a full-investigation ``--key`` also gets
that task's rubric and request scope for every setting the config does not set), and
increment A's task is the default.

Exit status: 0 judged (or dry run / nothing to judge), 3 some units failed (outputs
written, failed units stay pending), 2 configuration refused, 1 other errors.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from environment.incident import grading as mvp
from environment.incident.catalogue import Catalogue, CatalogueError
from environment.incident.episode import (
    SUBMISSION_FILE,
    SYSTEM_RESPONSE_TOOL_NAMES,
    build_transcript_summary,
)
from environment.incident.grading import GradingError

from .client import API_KEY_ENV, JudgeClientError
from .config import (
    TASK_CONFIG_DEFAULTS,
    JudgeConfigError,
    load_config,
    with_task_defaults,
)
from .prompt import build_units, load_rubric
from .runner import (
    DEFAULT_OUT_DIR,
    MERGED_GRADE_FILE,
    JudgeError,
    find_transcript,
    judge_episode,
    judge_submission_file,
    load_transcript,
)
from .tasks import load_key, task_for_key


def _load_env_file(path: str) -> None:
    """Set ``OPENROUTER_API_KEY`` from a dotenv-style file if it is not already set
    (no other variable is read; the value is never printed)."""
    if os.environ.get(API_KEY_ENV):
        return
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise JudgeConfigError(f"cannot read --env-file {path}: {exc}") from None
    for line in lines:
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == API_KEY_ENV:
            os.environ[API_KEY_ENV] = value.strip().strip("'\"")
            return


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", help="episode directory or submission JSON file")
    parser.add_argument(
        "--config", help="judge config JSON (configs/judge.example.json)"
    )
    parser.add_argument("--judge-model", help="override the configured judge model")
    parser.add_argument("--run-model", help="the evaluated model (else the transcript)")
    parser.add_argument("--transcript", help="the run's Karotte transcript JSON")
    parser.add_argument(
        "--task",
        choices=sorted(TASK_CONFIG_DEFAULTS),
        help="the task judged (default: from the key's schema; increment A's task "
        "without a key)",
    )
    parser.add_argument("--key", help="answer key (default: the task's private key)")
    parser.add_argument("--bundle", help="evidence bundle directory")
    parser.add_argument(
        "--allow-same-family",
        action="store_true",
        help="judge even if the judge is from the evaluated model's family (recorded)",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m environment.incident.judge",
        description="LLM judge for gb-2019-system-response and "
        "gb-2019-full-investigation (proposals for human sign-off; see the module "
        "docstring)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="judge a target and write the merged grade")
    _common(run)
    run.add_argument("--decisions", help="grading-decisions file to apply")
    run.add_argument("--cache-dir", help="cache directory (default <out-dir>/cache)")
    run.add_argument(
        "--out-dir", help=f"output directory (default <episode_dir>/{DEFAULT_OUT_DIR})"
    )
    run.add_argument("--cache-only", action="store_true", help="never call the model")
    run.add_argument(
        "--dry-run", action="store_true", help="plan requests and cost; send nothing"
    )
    run.add_argument("--env-file", help=f"file setting {API_KEY_ENV}")
    prompt = sub.add_parser("prompt", help="print what the judge would be sent")
    _common(prompt)
    prompt.add_argument("--unit", help="unit to print (default: list the units)")
    merge = sub.add_parser("merge", help="merge an existing judge output again")
    _common(merge)
    merge.add_argument("--judge-output", required=True)
    merge.add_argument("--decisions", help="grading-decisions file to apply")
    merge.add_argument("--out", help="write the merged report here (default stdout)")
    return parser


def _config(args: argparse.Namespace):
    return load_config(
        args.config,
        task=args.task,
        judge_model=args.judge_model,
        allow_same_family=True if args.allow_same_family else None,
    )


def _key(args: argparse.Namespace):
    return load_key(args.key, args.task)


def _catalogue(args: argparse.Namespace) -> Catalogue | None:
    return Catalogue.load(args.bundle) if args.bundle else None


def _run_model(args: argparse.Namespace, target: Path) -> tuple[str | None, Any]:
    transcript = Path(args.transcript) if args.transcript else None
    if transcript is None and target.is_dir():
        transcript = find_transcript(target)
    model = args.run_model
    if transcript is not None and not model:
        _, model = load_transcript(transcript)
    return model, transcript


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, default=str))


def _cmd_run(args: argparse.Namespace) -> int:
    if args.env_file:
        _load_env_file(args.env_file)
    config = _config(args)
    target = Path(args.target)
    key = _key(args) if args.key or args.task else None
    common = dict(
        config=config,
        run_model=args.run_model,
        decisions=args.decisions,
        key=key,
        catalogue=_catalogue(args),
        cache_dir=args.cache_dir,
        cache_only=args.cache_only,
        dry_run=args.dry_run,
    )
    if target.is_dir():
        result = judge_episode(
            target, transcript=args.transcript, out_dir=args.out_dir, **common
        )
    else:
        if not args.out_dir:
            raise JudgeError("--out-dir is required when the target is a file")
        result = judge_submission_file(target, out_dir=args.out_dir, **common)
    if result.status == "dry_run":
        _print(result.run_log)
        return 0
    log = result.run_log
    _print(
        {
            "status": result.status,
            "target": str(target),
            "files": result.files,
            "report_status": result.report.get("status"),
            "api_calls": log.get("api_calls"),
            "cache_hits": log.get("cache_hits"),
            "failed_units": log.get("failed_units"),
            "errors": log.get("errors"),
            "cost_this_run": log.get("cost_this_run"),
            "cost_recorded_total": log.get("cost_recorded_total"),
            "span_checks": (result.judge_output or {}).get("span_checks"),
            "reason": log.get("reason"),
        }
    )
    return 3 if result.status == "partial" else 0


def _base_report(args: argparse.Namespace, target: Path, key, catalogue):
    grading = task_for_key(key)
    if target.is_dir():
        catalogue, _ = grading.grader._catalogue_for_episode(target, catalogue)
        report = grading.grader.grade_episode(
            target, None, key=key, catalogue=catalogue
        )
        if report["run"]["outcome"] != "complete":
            raise JudgeError(f"run outcome is {report['run']['outcome']!r}")
        text = (target / SUBMISSION_FILE).read_text(encoding="utf-8")
    else:
        catalogue = catalogue or Catalogue.load(grading.bundle_dir)
        text = target.read_text(encoding="utf-8")
        report = grading.grader.grade_submission(text, catalogue, key)
    return text, report, catalogue


def _cmd_prompt(args: argparse.Namespace) -> int:
    target = Path(args.target)
    key = _key(args)
    # a full-investigation --key without --task still gets that task's defaults
    config = with_task_defaults(_config(args), task_for_key(key).task_id)
    text, report, catalogue = _base_report(args, target, key, _catalogue(args))
    run_model, _ = _run_model(args, target)
    sub, _ = mvp._as_submission(text, catalogue)
    inputs = build_units(
        sub,
        report,
        key,
        catalogue,
        config,
        load_rubric(config.rubric_path()),
        blind_terms=[run_model],
    )
    if not args.unit:
        _print(
            [
                {
                    "unit_id": u.unit_id,
                    "criteria": u.criterion_ids,
                    "findings_classified": u.finding_ids,
                    "prompt_chars": sum(len(m["content"]) for m in u.messages),
                    **(
                        {"findings_shown": u.shown_finding_ids}
                        if u.shown_finding_ids is not None
                        else {}
                    ),
                }
                for u in inputs.units
            ]
        )
        return 0
    unit = next((u for u in inputs.units if u.unit_id == args.unit), None)
    if unit is None:
        raise JudgeError(
            f"unknown unit {args.unit!r}; units: "
            + ", ".join(u.unit_id for u in inputs.units)
        )
    for message in unit.messages:
        print(f"===== {message['role']} =====")
        print(message["content"])
    return 0


def _cmd_merge(args: argparse.Namespace) -> int:
    target = Path(args.target)
    key = _key(args)
    grading = task_for_key(key)
    catalogue = _catalogue(args)
    if target.is_dir():
        transcript = (
            Path(args.transcript) if args.transcript else find_transcript(target)
        )
        events = load_transcript(transcript)[0] if transcript else None
        summary = (
            build_transcript_summary(
                target,
                events,
                output_token_budget=grading.output_token_budget,
                tool_names=SYSTEM_RESPONSE_TOOL_NAMES,
            )
            if events is not None
            else None
        )
        report = grading.grader.grade_episode(
            target,
            summary,
            args.decisions,
            key=key,
            catalogue=catalogue,
            judge_output=args.judge_output,
        )
    else:
        catalogue = catalogue or Catalogue.load(grading.bundle_dir)
        report = grading.grader.grade_submission(
            target.read_text(encoding="utf-8"),
            catalogue,
            key,
            None,
            args.decisions,
            args.judge_output,
        )
    if args.out:
        Path(args.out).write_text(
            json.dumps(
                report, indent=2, sort_keys=True, ensure_ascii=False, default=str
            )
            + "\n",
            encoding="utf-8",
        )
        _print({"status": report.get("status"), "out": args.out})
    else:
        _print(report)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "prompt":
            return _cmd_prompt(args)
        return _cmd_merge(args)
    except JudgeConfigError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except (
        JudgeError,
        JudgeClientError,
        GradingError,
        CatalogueError,
        OSError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


__all__ = ["MERGED_GRADE_FILE", "main"]

if __name__ == "__main__":
    sys.exit(main())
