"""Copy the real full-investigation runs into this directory (builder tool; not
collected by pytest; needs the local ``out/`` tree, which is not versioned).

    uv run --frozen python tests/fixtures/fi_live/build_fi_live_fixtures.py

For each run it copies, byte for byte, the episode files grading needs
(``submission.json``, ``state.json``, ``trace.jsonl``, ``episode_config.json``) and the
judge's ``judge/judge_output.json`` and ``judge/judge_run.json`` (the merged
``judge/grade.json`` is not copied: the tests merge the judge output again). The
transcript is not copied: ``run_summary.json`` is ``build_transcript_summary`` of the
transcript under the task's output budget (80,000). ``runs.json`` records every file's
sha256, the canonical submission sha256 the episode froze, the bundle, the judge
output's binding (the key it was produced with) and the key and grader versions the
fixtures were last graded with. As ``tests/fixtures/sr_live`` does for increment A
(decisions 40-48), these are the regression fixtures of the full-investigation grader:
real wording its pre-screens, flags, accounting and routing must read (decision 77).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from environment.incident import fi_grading
from environment.incident.episode import (
    FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET,
    SYSTEM_RESPONSE_TOOL_NAMES,
    build_transcript_summary,
    read_state,
)
from environment.incident.judge.runner import load_transcript

HERE = Path(__file__).resolve().parent
ENV = HERE.parents[2]
RUNS = [
    # run_id, what, run directory under out/, artifacts directory
    (
        "fi-pilot-opus55-001",
        "pilot (decision 64)",
        "fi_pilot",
        "gb2019-fi-pilot-opus55-001_artifacts",
    ),
    (
        "fi-panel-opus55-001",
        "first panel run (decision 77)",
        "panel_fi/opus55-001",
        "gb2019-fi-opus55-001_artifacts",
    ),
]
EPISODE_FILES = ("submission.json", "state.json", "trace.jsonl", "episode_config.json")
JUDGE_FILES = ("judge_output.json", "judge_run.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    key = fi_grading.load_key()
    out = []
    for run_id, what, run_dir, artifacts in RUNS:
        src = ENV / "out" / run_dir
        episode = src / artifacts / "episode"
        dest = HERE / run_id
        dest.mkdir(parents=True, exist_ok=True)
        files = {}
        for name in EPISODE_FILES:
            shutil.copyfile(episode / name, dest / name)
            files[name] = sha(dest / name)
        binding = None
        for name in JUDGE_FILES:
            path = episode / "judge" / name
            if path.exists():
                shutil.copyfile(path, dest / name)
                files[name] = sha(dest / name)
        if (dest / "judge_output.json").exists():
            judge = json.loads((dest / "judge_output.json").read_text(encoding="utf-8"))
            binding = judge["binding"]
            judge_meta = {
                "judge_model": judge.get("judge_model"),
                "rubric_version": judge.get("rubric_version"),
                "scope_mode": (judge.get("scope") or {}).get("mode"),
            }
        events, model = load_transcript(src / "transcript.json")
        summary = build_transcript_summary(
            episode,
            events,
            output_token_budget=FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET,
            tool_names=SYSTEM_RESPONSE_TOOL_NAMES,
        )
        (dest / "run_summary.json").write_text(
            json.dumps(
                summary, indent=1, ensure_ascii=False, sort_keys=True, default=str
            )
            + "\n",
            encoding="utf-8",
        )
        files["run_summary.json"] = sha(dest / "run_summary.json")
        config = json.loads((episode / "episode_config.json").read_text())
        state = read_state(episode)
        out.append(
            {
                "run_id": run_id,
                "what": what,
                "model": model,
                "output_token_budget": FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET,
                "outcome": summary["outcome"],
                "incomplete_reason": summary.get("incomplete_reason"),
                "judged": binding is not None,
                "source": f"out/{run_dir}/{artifacts}/episode",
                "files": files,
                "submission_sha256": state.submission_sha256 if state else None,
                "bundle_version": config["bundle_version"],
                "bundle_sha256": config["bundle_sha256"],
                "judge_binding": binding,
                **({"judge": judge_meta} if binding is not None else {}),
            }
        )
        print(run_id, summary["outcome"], "judged" if binding else "not judged")
    (HERE / "runs.json").write_text(
        json.dumps(
            {
                "_note": "Real full-investigation runs copied byte for byte from out/ "
                "(see README.md). judge_binding is the key the judge output was "
                "produced with; the tests re-bind it to the installed key in memory "
                "(no judge-visible key text changed).",
                "graded_with": {
                    "key_version": key["key_version"],
                    "key_sha256": fi_grading.key_sha256(key),
                    "grader_version": fi_grading.GRADER_VERSION,
                },
                "runs": out,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
