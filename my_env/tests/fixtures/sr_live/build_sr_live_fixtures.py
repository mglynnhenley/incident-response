"""Copy the six real system-response runs into this directory (builder tool; not
collected by pytest; needs the local ``out/`` tree, which is not versioned).

    uv run --frozen python tests/fixtures/sr_live/build_sr_live_fixtures.py

For each run it copies, byte for byte, the episode files grading needs
(``submission.json``, ``state.json``, ``trace.jsonl``, ``episode_config.json``) and,
for the judged 80k runs, ``judge/judge_output.json``. The transcripts are not copied:
``run_summary.json`` is ``build_transcript_summary`` of the transcript under the output
budget the run was judged by (30k panel: 30,000; 80k panel: 80,000). ``runs.json``
records every file's sha256, the canonical submission sha256 the episode froze, the
bundle, the judge output's binding and the key and grader versions the fixtures were
last graded with.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from environment.incident import sr_grading
from environment.incident.episode import (
    SYSTEM_RESPONSE_TOOL_NAMES,
    build_transcript_summary,
    read_state,
)
from environment.incident.judge.runner import load_transcript

HERE = Path(__file__).resolve().parent
ENV = HERE.parents[2]
RUNS = [
    # run_id, panel directory, run directory, artifacts prefix, output budget
    ("sr80k-opus55-001", "panel_sr80k", "opus55-001", "gb2019-sr80k", 80000),
    ("sr80k-sonnet55-001", "panel_sr80k", "sonnet55-001", "gb2019-sr80k", 80000),
    ("sr80k-haiku45-001", "panel_sr80k", "haiku45-001", "gb2019-sr80k", 80000),
    ("sr30k-opus55-001", "panel_sr_30k", "opus55-001", "gb2019-sr", 30000),
    ("sr30k-sonnet55-001", "panel_sr_30k", "sonnet55-001", "gb2019-sr", 30000),
    ("sr30k-haiku45-001", "panel_sr_30k", "haiku45-001", "gb2019-sr", 30000),
]
EPISODE_FILES = ("submission.json", "state.json", "trace.jsonl", "episode_config.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    key = sr_grading.load_key()
    out = []
    for run_id, panel, run_dir, prefix, budget in RUNS:
        src = ENV / "out" / panel / run_dir
        episode = src / f"{prefix}-{run_dir}_artifacts" / "episode"
        dest = HERE / run_id
        dest.mkdir(parents=True, exist_ok=True)
        files = {}
        for name in EPISODE_FILES:
            shutil.copyfile(episode / name, dest / name)
            files[name] = sha(dest / name)
        judge = episode / "judge" / "judge_output.json"
        binding = None
        if judge.exists():
            shutil.copyfile(judge, dest / "judge_output.json")
            files["judge_output.json"] = sha(dest / "judge_output.json")
            binding = json.loads(judge.read_text(encoding="utf-8"))["binding"]
        events, model = load_transcript(src / "transcript.json")
        summary = build_transcript_summary(
            episode,
            events,
            output_token_budget=budget,
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
                "model": model,
                "panel": panel,
                "output_token_budget": budget,
                "outcome": summary["outcome"],
                "incomplete_reason": summary.get("incomplete_reason"),
                "judged": binding is not None,
                "source": f"out/{panel}/{run_dir}/{prefix}-{run_dir}_artifacts/episode",
                "files": files,
                "submission_sha256": state.submission_sha256 if state else None,
                "bundle_version": config["bundle_version"],
                "bundle_sha256": config["bundle_sha256"],
                "judge_binding": binding,
            }
        )
        print(run_id, summary["outcome"], "judged" if binding else "not judged")
    (HERE / "runs.json").write_text(
        json.dumps(
            {
                "_note": "Real system-response runs copied byte for byte from out/ (see "
                "README.md). judge_binding is the key the judge output was produced "
                "with; the tests re-merge it under the installed key (rebound).",
                "graded_with": {
                    "key_version": key["key_version"],
                    "key_sha256": sr_grading.key_sha256(key),
                    "grader_version": sr_grading.GRADER_VERSION,
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
