# Live-run submissions (real model output)

Copied byte for byte from the live runs' `episode/submission.json` (the `out/` tree is not
versioned). They are the regression fixtures for decision 18 in `docs/DECISIONS.md`
(grader false negatives found by real submissions) and are used by
`tests/test_grading_live_runs.py`. Do not edit them: `runs.json` records each file's
sha256 and the canonical submission sha256 the episode froze in `state.json`, and the
tests check both.

| File | Run | Model | Bundle |
|---|---|---|---|
| `gb2019-v2-opus55-002.submission.json` | panel, 2026-10-20 | Claude Opus 5.5 | 1.1.0 |
| `gb2019-v2-opus55-003.submission.json` | panel, 2026-10-20 | Claude Opus 5.5 | 1.1.0 |
| `gb2019-v2-sonnet55-001.submission.json` | panel, 2026-10-20 | Claude Sonnet 5.5 | 1.1.0 |
| `gb2019-v2-haiku45-001.submission.json` | panel, 2026-10-20 | Claude Haiku 4.5 | 1.1.0 |
| `gb2019-live-opus55-001.submission.json` | live run 001 | Claude Opus 5.5 | **1.0.0** |

Bundle 1.1.0 is the installed bundle (`src/environment/incident/bundle`). Run 001 ran on
bundle 1.0.0 and cites lines that do not exist in 1.1.0, so it must be graded against the
bundle it ran on: `bundle-1.0.0/` is that bundle, rebuilt byte for byte from the run's own
trace (the `request_document` envelopes carry each text and its sha256; see
`docs/GB_2019_MVP.md`, "Offline re-grade of run 001"). Its `bundle_sha256` matches the
one the episode recorded (`runs.json`).

`runs.json` also keeps, per run, the documents retrieved and whether R01 was analysed
with `run_python` (from `grading.trace_info_from_episode` on the run's ledger), so the
tests grade with the same trace information as `grade_episode` without the full traces.
