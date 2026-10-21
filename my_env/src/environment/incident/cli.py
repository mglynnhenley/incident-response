"""Command line for builders and reviewers.

    python -m environment.incident.cli list [--bundle DIR] [--category C] [--json]
        (``--bundle src/environment/incident/bundles/system_response`` for the v2 bundle)
    python -m environment.incident.cli inspect EPISODE_DIR [--seq N] [--json]
    python -m environment.incident.cli replay EPISODE_DIR [--bundle DIR] [--rerun-python]
    python -m environment.incident.cli validate SUBMISSION.json [--bundle DIR]
    python -m environment.incident.cli grade EPISODE_DIR [--transcript T.json]
        [--bundle DIR] [--out F]
    python -m environment.incident.cli review-template EPISODE_DIR [--bundle DIR] [--out F]

``grade`` and ``review-template`` import ``environment.incident.grading`` lazily; it is
built separately and the commands say so clearly when it is absent.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from environment.incident.catalogue import CATEGORIES, Catalogue, CatalogueError
from environment.incident.episode import (
    EpisodeError,
    build_transcript_summary,
    read_state,
    read_trace,
    render,
)
from environment.incident.paths import DEFAULT_BUNDLE_DIR
from environment.incident.replay import replay_episode
from environment.incident.submission import validate_submission

GRADING_MODULE = "environment.incident.grading"
_REVIEW_TEMPLATE_FUNCTIONS = (
    "review_template",
    "make_review_template",
    "build_review_template",
    "write_review_template",
)


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    return value


def _print_json(value: Any) -> None:
    print(json.dumps(_jsonable(value), indent=2, ensure_ascii=False, default=str))


def _v2_listing(catalogue: Catalogue) -> dict[str, Any]:
    sources = catalogue.sources
    assert sources is not None
    return {
        "asset_logs": [
            {**log.summary(), "rows": len(log.rows), "file": log.file}
            for log in sources.asset_logs.values()
        ],
        "control_logs": [
            {**log.summary(), "rows": len(log.rows), "file": log.file}
            for log in sources.control_logs.values()
        ],
        "witnesses": [
            {**card.summary(), "blocks": len(card.blocks), "file": card.file}
            for card in sources.witnesses.values()
        ],
        "data_returns": [
            {
                "party": entry.party,
                "data_type": entry.data_type,
                "status": entry.status,
                "evidence_id": entry.evidence_id,
            }
            for entry in sources.data_returns
        ],
    }


def _cmd_list(args: argparse.Namespace) -> int:
    catalogue = Catalogue.load(args.bundle)
    if args.category is not None and args.category not in catalogue.categories:
        print(
            f"unknown category {args.category!r}; this bundle has: "
            f"{', '.join(catalogue.categories)}",
            file=sys.stderr,
        )
        return 2
    docs = [d for d in catalogue if args.category in (None, d.category)]
    if args.json:
        listing: dict[str, Any] = {
            "bundle_id": catalogue.bundle_id,
            "bundle_version": catalogue.bundle_version,
            "bundle_sha256": catalogue.bundle_sha256,
            "documents": [
                {
                    **d.summary(),
                    "line_count": d.line_count,
                    "artifacts": [
                        {"file": a.file, "bytes": a.bytes, "sha256": a.sha256}
                        for a in d.artifacts
                    ],
                }
                for d in docs
            ],
        }
        if catalogue.is_v2:
            listing["manifest_version"] = catalogue.manifest_version
            for doc in listing["documents"]:
                doc["listed"] = catalogue.is_listed(doc["doc_id"])
            listing.update(_v2_listing(catalogue))
        _print_json(listing)
        return 0
    print(
        f"bundle {catalogue.bundle_id} v{catalogue.bundle_version} "
        f"sha256 {catalogue.bundle_sha256} (all artifact hashes verified)"
    )
    for d in docs:
        hidden = "" if catalogue.is_listed(d.doc_id) else "  [data return only]"
        print(
            f"{d.doc_id:<5} {d.category:<19} {d.date:<10} {d.line_count:>4} lines  "
            f"{d.title}{hidden}"
        )
    if catalogue.is_v2:
        extra = _v2_listing(catalogue)
        for log in extra["asset_logs"]:
            print(
                f"asset   {log['asset_id']:<16} {log['rows']:>6} rows  {log['title']}"
            )
        for log in extra["control_logs"]:
            print(f"room    {log['room_id']:<16} {log['rows']:>6} rows  {log['title']}")
        for card in extra["witnesses"]:
            print(
                f"witness {card['persona_id']:<16} {card['blocks']:>6} blocks "
                f"{card['role']} ({card['organisation']})"
            )
        for entry in extra["data_returns"]:
            print(
                f"return  {entry['party']} / {entry['data_type']}: {entry['status']}"
                + (f" -> {entry['evidence_id']}" if entry["evidence_id"] else "")
            )
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    episode_dir = Path(args.episode_dir)
    state = read_state(episode_dir)
    trace = read_trace(episode_dir)
    if args.seq is not None:
        for record in trace:
            if record.get("seq") == args.seq:
                if args.json:
                    _print_json(record)
                else:
                    print(render(record["envelope"]))
                return 0
        print(f"no trace record with seq {args.seq}", file=sys.stderr)
        return 1
    if args.json:
        _print_json({"state": state.to_dict() if state else None, "trace": trace})
        return 0
    if state is None:
        print(f"{episode_dir}: no state.json (episode not started)")
    else:
        print(json.dumps(state.to_dict(), indent=2))
    for record in trace:
        print(
            f"{record.get('request_id')} {record.get('tool'):<17} "
            f"{'counted' if record.get('counted') else 'uncounted':<9} "
            f"{record.get('outcome_code'):<18} "
            f"{'deterministic' if record.get('deterministic') else 'python':<13} "
            f"{str(record.get('rendered_text_sha256'))[:12]}"
        )
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    report = replay_episode(
        args.episode_dir,
        bundle_dir=args.bundle,
        rerun_python=args.rerun_python,
        python_executable=args.python,
    )
    if args.json:
        _print_json(report.to_dict())
    else:
        print(report.summary_text())
    return 0 if report.ok else 1


def _cmd_validate(args: argparse.Namespace) -> int:
    raw = (
        sys.stdin.read()
        if args.submission == "-"
        else Path(args.submission).read_text()
    )
    catalogue = Catalogue.load(args.bundle)
    result = validate_submission(
        raw, catalogue, word_limit=args.word_limit, variant_id=args.variant
    )
    if args.json:
        _print_json(
            {
                "ok": result.ok,
                "errors": result.errors,
                "sha256": result.sha256,
                "findings_count": result.findings_count,
            }
        )
    elif result.ok:
        print(f"valid: {result.findings_count} findings, sha256 {result.sha256}")
    else:
        print(f"invalid: {len(result.errors)} problem(s)")
        for err in result.errors:
            print(f"  {err['path']}: {err['message']}")
    return 0 if result.ok else 1


def _load_grading() -> ModuleType | None:
    try:
        return importlib.import_module(GRADING_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name not in (GRADING_MODULE, "environment.incident.grading"):
            raise
        return None


def _grading_missing(command: str) -> int:
    print(
        f"'{command}' needs {GRADING_MODULE}, which is not installed in this build. "
        "Grading is provided by the separate grading component; add it and retry.",
        file=sys.stderr,
    )
    return 2


def transcript_summary_for(
    episode_dir: Path, transcript_path: Path | None
) -> dict[str, Any]:
    """Transcript summary + outcome in the shape the judge passes to grading."""
    events = None
    if transcript_path is not None:
        data = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
        events = list(data.get("events") or [])
    return build_transcript_summary(Path(episode_dir), events)


def _grading_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    """``catalogue=`` for the grading functions when ``--bundle`` was given."""
    if getattr(args, "bundle", None) is None:
        return {}
    return {"catalogue": Catalogue.load(args.bundle)}


def _grading_error(grading: ModuleType, exc: Exception) -> int:
    """Report a grading error (e.g. an episode recorded on another bundle) cleanly."""
    error = getattr(grading, "GradingError", None)
    if error is None or not isinstance(exc, error):
        raise exc
    print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 1


def _cmd_grade(args: argparse.Namespace) -> int:
    grading = _load_grading()
    if grading is None or not hasattr(grading, "grade_episode"):
        return _grading_missing("grade")
    episode_dir = Path(args.episode_dir)
    summary = transcript_summary_for(episode_dir, args.transcript)
    try:
        result = _jsonable(
            grading.grade_episode(episode_dir, summary, **_grading_kwargs(args))
        )
    except Exception as exc:  # noqa: BLE001 - non-grading errors are re-raised
        return _grading_error(grading, exc)
    text = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"grade written to {args.out}")
    else:
        print(text)
    return 0


def _cmd_review_template(args: argparse.Namespace) -> int:
    grading = _load_grading()
    if grading is None:
        return _grading_missing("review-template")
    func = next(
        (
            getattr(grading, n)
            for n in _REVIEW_TEMPLATE_FUNCTIONS
            if hasattr(grading, n)
        ),
        None,
    )
    if func is None:
        print(
            f"{GRADING_MODULE} provides no review-template function (looked for "
            f"{', '.join(_REVIEW_TEMPLATE_FUNCTIONS)}).",
            file=sys.stderr,
        )
        return 2
    try:
        result = _jsonable(func(Path(args.episode_dir), **_grading_kwargs(args)))
    except Exception as exc:  # noqa: BLE001 - non-grading errors are re-raised
        return _grading_error(grading, exc)
    text = (
        result
        if isinstance(result, str)
        else json.dumps(result, indent=2, ensure_ascii=False, default=str)
    )
    if args.out:
        Path(args.out).write_text(text if text.endswith("\n") else text + "\n")
        print(f"review template written to {args.out}")
    else:
        print(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m environment.incident.cli",
        description="Inspect, replay and validate GB 2019 investigation episodes.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="list the catalogue (verifies every hash)")
    p.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE_DIR)
    p.add_argument(
        "--category", help=f"one category (MVP bundle: {', '.join(CATEGORIES)})"
    )
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_list)

    p = sub.add_parser("inspect", help="show an episode's state and trace")
    p.add_argument("episode_dir", type=Path)
    p.add_argument("--seq", type=int, help="print what the model saw for this call")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_inspect)

    p = sub.add_parser("replay", help="replay a trace in a fresh temporary episode")
    p.add_argument("episode_dir", type=Path)
    p.add_argument(
        "--bundle",
        type=Path,
        default=None,
        help="bundle to replay against (default: the recorded bundle_dir; if it does not "
        "exist here, the installed bundle at the same package path or with the recorded "
        "bundle_sha256)",
    )
    p.add_argument("--rerun-python", action="store_true")
    p.add_argument("--python", default=None, help="interpreter for --rerun-python")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_replay)

    p = sub.add_parser("validate", help="validate a v3 submission file ('-' = stdin)")
    p.add_argument("submission")
    p.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE_DIR)
    p.add_argument("--variant", default="baseline")
    p.add_argument("--word-limit", type=int, default=600)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_validate)

    bundle_help = (
        "bundle the episode ran on (default: its recorded bundle_dir if present, else "
        "the installed bundle); grading refuses a bundle other than the recorded one"
    )
    p = sub.add_parser("grade", help="grade an episode (needs the grading component)")
    p.add_argument("episode_dir", type=Path)
    p.add_argument("--transcript", type=Path, default=None)
    p.add_argument(
        "--bundle", "--bundle-dir", dest="bundle", type=Path, help=bundle_help
    )
    p.add_argument("--out", type=Path, default=None)
    p.set_defaults(func=_cmd_grade)

    p = sub.add_parser(
        "review-template", help="write a human-review template (needs grading)"
    )
    p.add_argument("episode_dir", type=Path)
    p.add_argument(
        "--bundle", "--bundle-dir", dest="bundle", type=Path, help=bundle_help
    )
    p.add_argument("--out", type=Path, default=None)
    p.set_defaults(func=_cmd_review_template)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (CatalogueError, EpisodeError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
