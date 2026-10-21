## GB 9 August 2019: power-system response (increment A)

Task id: `gb-2019-system-response`. One step. The MVP task `gb-2019-electrical-disturbance`
is unchanged and stays the regression baseline (its bundle, key and tests are frozen).

### Background

A retrospective investigation exercise covering the initiating fault through to the
restoration of disconnected demand (handoff topics T01–T09, T12, T16, T17). The agent
receives the brief from the increment-A contract (`.context/increment_A_design.md`),
"Report expectations" that name the deliverables without values or conventions
(`prompt.py`, `REPORT_EXPECTATIONS`, each tagged with its handoff topic for builders),
an evidence notice, the tool list, budgets and the v3 submission skeleton.

Evidence comes from the manifest-v2 bundle `environment/incident/bundles/system_response/`
(real public data first, then digitised official figures, then labelled reconstruction;
decisions 16 and 22). It is never loaded at import time; `pre_hook` verifies every hash
and fails closed.

### Tools

Nine tools, all thin adapters (`environment/tools/*.py`) over
`environment.incident.episode.Episode`, sharing one ledger:

| Tool | Purpose |
| --- | --- |
| `list_documents(category?, cursor?)` | documents (50 per page); first page also lists asset logs, control rooms, witnesses and (party, data_type) pairs |
| `request_document(doc_id)` or `(party, description)` | numbered text + read-only files; described requests use matcher `doc-tokens-2` (owner + ID/title/keywords, at least half the description words; not the category); ties give `AMBIGUOUS_REQUEST` with candidates |
| `query_frequency(start, end, resolution_s=1, cursor?)` | R01 samples, start inclusive, end exclusive, ≤1000 per page, values as recorded; materialises R01 for Python; `OUT_OF_RANGE` outside the record |
| `query_asset_log(asset_id, start, end, signal?, cursor?)` | ≤200 rows per page selected by `index_time_utc`; rows show `recorded_time` and `clock_basis` first; stable `event_id` |
| `query_control_log(room, start, end, cursor?)` | as above for control rooms; stable `entry_id` |
| `interview_witness(persona_id, question)` | fixed fact blocks, matcher `witness-topics-2`; unclear question → `AMBIGUOUS_REQUEST` with the topics of the closest blocks only (at most 3; topics name subjects, never findings); otherwise the card's "not known" answer; stable `response_id` |
| `request_data_return(party, data_type)` | registry fixed before the run: a document (materialised like `request_document`) or `NOT_HELD` / `REFUSED` |
| `run_python(code)` | as MVP; sees only what was obtained (documents, data returns, R01 after `query_frequency`) |
| `submit_findings(submission)` | v3 as MVP; locators add `event:<id>`, `entry:<id>`, `response:<id>` (the citation's `evidence_id` must be the record's) |

The four MVP tool modules are shared with the MVP task. This task writes its tool config
with `tool_profile: "system_response"`; under that profile each adapter instance takes
the descriptions in `prompt.TOOL_DESCRIPTIONS` (150-call budget, record locators) and
`request_document` registers a signature with `party` and `description`
(`apply_tool_profile`). Under the MVP profile descriptions and schemas are byte-for-byte
unchanged.

Every parameter is optional at the MCP layer and accepts any JSON value while advertising
its schema, so missing or wrong-typed values reach the ledger as a counted
`INVALID_ARGUMENT`. Calls with an argument name a tool does not declare are refused by
FastMCP before the ledger (not counted); the judge reports them as
`transcript_summary.ledger_discrepancy`.

Matching and refusal behaviour is deterministic and versioned (`matcher_version` in every
result); question and description text is only tokenised — never executed, used as a
path or echoed into evidence — so prompt-injection text is answered like any other
question. IDs are only looked up in the verified manifest (path traversal yields
`UNKNOWN_ID`).

### Budgets

150 tool calls (as the MVP, invalid calls, Python and submissions count); Python 30 s
wall time, 1 GiB; outputs capped at 20,000 characters per stream; context cap 200,000
tokens; output budget 80,000 tokens (raised from 30,000 after the first live panel, decision 36).

### Scoring

Completion only (`1.0` = valid frozen submission within the tool-call and output-token
budgets), exactly as the MVP. `judge.SystemResponseJudge` calls
`environment.incident.sr_grading.grade_episode(episode_dir, transcript_summary)` and
stores its report in `grade.json` and the scoring metadata (an import or grading error is
reported there; it never changes the score). The MVP grader is never applied to this
task's episodes.

### Grading (provisional)

Key `private/system_response/answer_key.json` (0.1.1, grader 0.1.1, `pending_domain_review`; checklist
`REVIEW_CHECKLIST.md`): 60 criteria for T01–T09, T12, T16, T17 — 4 `auto_numeric` (R01
landmarks and the below-49-Hz duration, decided automatically), 32 `auto_assisted_human`
(automated proposals for a human: values, times, accounting bases), 24 `judge` (an LLM
judge proposes, a human signs off). Content coverage, evidence support and assertion
quality are reported separately; no total, threshold or ranking. Accounting-basis checks
(`sr_accounting.py`) keep each figure on its own source, stage and definition (1,878 vs
at least 1,990 MW; 931 vs 892 vs 973 MW; 1,314 vs 1,338 MW; 210 GVA.s vs 219,632 MVA.s;
distributed-generation estimates), binding each figure to the attribution nearest to it, and flag overlapping sums. The six real live-panel runs are regression fixtures (`tests/fixtures/sr_live`, decision 40). The LLM judge
(`environment.incident.judge`, default `openai/gpt-6.1-sol` via OpenRouter, refused for
the evaluated model's family unless overridden) sees the blinded submission, the
criterion rubric, the resolved cited spans and the keyed spans, nothing else; its output
is cached by content hashes and merged as proposals (`sr_grading.merge_judge_proposals`).
Design notes: `docs/DECISIONS.md`, "Increment A grading".

### Running

```bash
python -m environment.incident.cli list --bundle src/environment/incident/bundles/system_response
python -m environment.incident.cli replay out/<run>_artifacts/episode
karotte run --config configs/sr_live_run.example.json   # costed live run; ask first
```

Fake-model scenarios for this task (`karotte run` with `extra_config.fake_scenario`): `reference` (a scripted investigation through every tool, then the reference submission in `reference/`), `repair` (an invalid first submission, then the reference), `no_submission`, and `isolation_probe` (sandbox probes of the system-response bundle, logs, witness cards and private data, then 28 hostile tool calls: path traversal, private IDs and prompt injection in five witness questions and one document description).
