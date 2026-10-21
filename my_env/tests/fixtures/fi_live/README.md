# Real full-investigation runs (regression fixtures)

The real submissions of task `gb-2019-full-investigation` (bundle 0.1.0), copied byte for
byte from the local `out/` tree (not versioned) by `build_fi_live_fixtures.py`. As
`tests/fixtures/sr_live` does for increment A (decisions 40-48), they are the regression
fixtures of the full-investigation grader: real wording its flags, accounting,
pre-screens, routing and judge scoping must read (decision 77;
`tests/test_fi_grading_live_runs.py` part 2, `tests/test_fi_grading_pilot_run.py`,
`tests/test_judge_scope_errors.py`). Do not edit them: `runs.json` records every file's
sha256 and the canonical submission sha256 the episode froze in `state.json`, and the
tests check both.

| Directory | Run | Model | Outcome | Judged |
|---|---|---|---|---|
| `fi-pilot-opus55-001` | pilot (decision 64; 2026-10-20) | Claude Opus 5.5 | complete (31 calls, 37.3k output tokens, peak context 175k) | yes (decision 76) |
| `fi-panel-opus55-001` | first panel run (decision 77; 2026-10-20) | Claude Opus 5.5 | complete (29 calls) | yes |

Each directory holds the episode files grading needs: `submission.json`, `state.json`,
`trace.jsonl` and `episode_config.json`, and the judge's `judge_output.json` and
`judge_run.json` (gpt-6.1-sol, rubric 1.0.0, per-topic scope; produced with key 0.1.0).
The transcripts (1.2 and 2.5 MB) are not copied: `run_summary.json` is
`build_transcript_summary` of the transcript under the task's 80,000-token output
budget, so `grade_episode` sees the run's real outcome. The merged `judge/grade.json`
is not copied either: the tests merge the judge output again.

## How the tests grade them

`grade_episode(dir, run_summary)` with the judge output merged. The judge output is
bound to key 0.1.0. Key 0.1.1 changed no judge-visible text (criteria, examples without
pre-screen values, accounting figure descriptions, severe-flag definitions, examples
and non-examples: a test pins the digest of that text), so the tests re-bind it to the
installed key in memory and check that every judge request the installed key would send
has the same units and criteria, and differs, if at all, only where the corrected flags
and pre-screens route or show other findings (pilot T02, T07, T08, T17; panel T02, T05,
T07, T08, T12, T13, T14). No judge is called.

`runs.json` also records the model, the outcome, the judge output's binding and the key
and grader versions the fixtures were last graded with (`graded_with`; a test checks it
against the installed key and grader, so a key or grader change makes the tests point
here: re-read the outcomes, then rebuild with
`uv run --frozen python tests/fixtures/fi_live/build_fi_live_fixtures.py`).
