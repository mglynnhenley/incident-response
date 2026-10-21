# Real system-response runs (regression fixtures)

The six real submissions of the two increment-A live panels (task `gb-2019-system-response`,
bundle 0.1.0), copied byte for byte from the local `out/` tree (not versioned) by
`build_sr_live_fixtures.py`. They are the regression fixtures for decision 40 in
`docs/DECISIONS.md` (review round 2: grader false positives and negatives found by
reading every flag and cap on real submissions) and are used by
`tests/test_sr_grading_live_runs.py`. Do not edit them: `runs.json` records every file's
sha256 and the canonical submission sha256 the episode froze in `state.json`, and the
tests check both.

| Directory | Panel | Model | Outcome under its budget | Judged |
|---|---|---|---|---|
| `sr80k-opus55-001` | 80k (2026-10-20) | Claude Opus 5.5 | complete (47 calls) | yes |
| `sr80k-sonnet55-001` | 80k | Claude Sonnet 5.5 | complete (30 calls) | yes |
| `sr80k-haiku45-001` | 80k | Claude Haiku 4.5 | complete (17 calls) | yes |
| `sr30k-opus55-001` | 30k | Claude Opus 5.5 | incomplete: output budget (36.4k) | no |
| `sr30k-sonnet55-001` | 30k | Claude Sonnet 5.5 | incomplete: output budget (30.6k) | no |
| `sr30k-haiku45-001` | 30k | Claude Haiku 4.5 | complete (26.6k) | no |

Each directory holds the episode files grading needs: `submission.json`, `state.json`
(retrieved documents, frozen submission sha256), `trace.jsonl` (the ledger: retrieval
routes, records returned, Python calls) and `episode_config.json` (the bundle the episode
ran on). The transcripts (1-2 MB each) are not copied: `run_summary.json` is
`build_transcript_summary` of the transcript under the output budget the run was judged
by (30,000 for the 30k panel, 80,000 for the 80k panel), so `grade_episode` sees the
run's real outcome. The 80k runs also keep `judge_output.json` (gpt-6.1-sol, rubric
1.0.0), produced with key 0.1.0.

## How the tests grade them

* 80k runs: `grade_episode(dir, run_summary)` and the judge output merged. The judge
  output is bound to key 0.1.0; key 0.1.1 changed no judge-visible text (criteria,
  examples without pre-screen values, accounting figure descriptions, severe-flag
  definitions), so the tests re-bind it to the installed key in memory and check that
  every judge request the installed key would send has the same criteria and differs,
  if at all, only in which findings it asks the judge to classify (sonnet T02, T07, T08,
  T17; haiku T02, T09). No judge is called.
* 30k runs: Opus and Sonnet are incomplete, so `grade_episode` computes no measures;
  all three are graded diagnostically with `grade_submission` and the episode's trace
  information (`trace_info_from_episode`), as in the decision log's panel-1 entry.

`runs.json` also records the model, panel, budget, outcome, the judge output's binding
(key 0.1.0) and the key and grader versions the fixtures were last graded with
(`graded_with`; a test checks it against the installed key and grader, so a key or
grader change makes the tests point here: re-read the outcomes, then rebuild).
