## GB 9 August 2019: the full investigation (increment B)

Task id: `gb-2019-full-investigation`. One step. The MVP task `gb-2019-electrical-disturbance`
and increment A's task `gb-2019-system-response` are unchanged and stay frozen as
regression baselines (their bundles, keys and tests).

### Background

A retrospective investigation exercise covering the whole incident: the initiating fault,
the power-system response and restoration (increment A's topics T01–T09, T12, T16, T17),
and its consequences and lessons: the rail protection threshold (T04.02), rail impact
(T10), essential services (T11), contributing factors (T13), compliance observations
(T14), communications (T15), recommendations (T18), evidence requests and escalation
(T19) and the investigation summary (T20). Contract: `.context/increment_B_design.md`.

The agent receives (`prompt.py`):

- the brief: increment A's brief broadened to the consequences (rail and other essential
  services, communications), contributing factors, compliance concerns, recommendations
  and further evidence requests; increment A's clauses are kept word for word;
- the pilot plan's report sections as deliverables: an executive summary of at most 600
  words, then sections headed Chronology, Findings, Consequences, Uncertainties,
  Recommendations and Further evidence requests (`REPORT_SECTIONS`; also in the
  skeleton). Missing sections are not a validation error; they reduce coverage;
- "Report expectations" naming what the report and findings should cover for every
  topic, with no values, sites, train classes, counts, times, accounting bases,
  thresholds, legal clauses or conventions (`REPORT_EXPECTATIONS`, each item tagged with
  its handoff topics for builders; the tags are not shown);
- what is assessed (accuracy, coverage, evidence support, handling of uncertainty), and a
  scope note following the handoff's agent brief: compliance is assessed only against the
  requirements described in the evidence, and legal findings or enforcement outcomes the
  evidence does not contain are not to be stated (decision 50: the January 2020
  enforcement settlements are not in the evidence; asserting them is severe flag SF3);
- the evidence notice of increment A plus a retrospective-reconstruction notice (the
  catalogue date of every document is the incident date it covers, not the date of its
  sources, which each record names with their dates), the tool list, budgets (including
  what reaching the context cap does and the size of the evidence, decision 53) and the v3
  submission skeleton.

Evidence comes from the manifest-v2 bundle `environment/incident/bundles/full_investigation/`
(built separately by `builder/full_investigation/`): increment A's bundle copied
byte-identically with the same IDs, plus

- reconstructions: S08 rail fleet records, S10 compliance-process records, S11 essential
  services and the full R10 (requirements described in the reports);
- real data: R09 external communications (ESO, E3C, Ofgem and GOV.UK accounts, Elexon
  REMIT messages, organisational public posts and statements as gists), R11 rail
  performance records (Network Rail delay attribution, ORR periodic tables) and R12
  essential-service public statements (hospital trust; airport post times);
- four new categories: `transport_records` (R11, S08), `essential_services` (R12, S11),
  `communications_records` (R09) and `compliance_records` (S10);
- REMIT rows on the HORNSEA-ONE and LITTLE-BARFORD asset logs; the control rooms
  ESO-COMMS, NETWORK-RAIL-CONTROL and GTR-FLEET-CONTROL; five new witness cards
  (GTR fleet engineer, Network Rail control manager, ESO communications lead, hospital
  estates manager, UKPN EPN/SPN control engineer); and new data returns, supplied or not
  held.

No document carries manifest `keywords`: a described `request_document` matches on what
the catalogue shows, as increment A's tool description says. The bundle is never loaded
at import time; `pre_hook` verifies every hash and fails closed.

### Tools

The nine tools of increment A, unchanged: `list_documents`, `request_document`,
`query_frequency`, `query_asset_log`, `query_control_log`, `interview_witness`,
`request_data_return`, `run_python`, `submit_findings` (see
`../gb_2019_system_response/README.md`). This task writes its tool configuration with
increment A's `tool_profile` (`"system_response"`) and only a different `bundle_dir`, so
the descriptions and schemas the agent sees are increment A's; no new tool was needed.

### Budgets

150 tool calls (invalid calls, Python and submissions count); Python 30 s wall time,
1 GiB; outputs capped at 20,000 characters per stream; context cap 200,000 tokens; output
budget 80,000 tokens (`FULL_INVESTIGATION_OUTPUT_TOKEN_BUDGET` in
`environment.incident.episode`, starting from increment A's figure, decision 36). The
contract allows raising the call budget to 200 only if a live panel shows coverage is
budget-bound, and asks for a decision if runs reach the context cap. The call budget has
not been measured for this task yet. The context cap was estimated before any live run
(decision 53): reading every listed document in full returns about 320,000 characters,
which at the 2.4 characters per token measured on increment A's panel is about 135,000
tokens, so an increment-A-style full read reaches the 200,000-token cap. The cap stays at
200,000 for now; R09 no longer repeats its REMIT rows in its text, and the instructions
state the size of the evidence and what reaching the cap does. One pilot run must confirm
the peak context before the panel.

### Scoring

Completion only (`1.0` = valid frozen submission within the tool-call and output-token
budgets), exactly as the MVP and increment A. `judge.FullInvestigationJudge` calls
`environment.incident.fi_grading.grade_episode(episode_dir, transcript_summary)` and
stores its report in `grade.json` beside the episode and in the scoring metadata. The
report is large (about 2 MB for the reference submission), and Karotte truncates metadata
strings past its limit, so the scoring metadata may carry a truncated grade (the viewer
says so): `grade.json` is authoritative. A grading error is reported in the metadata and
never changes the score. Neither the MVP grader nor increment A's `sr_grading` is ever
applied to this task's episodes.

Key: `private/full_investigation/answer_key.json` (key 0.1.0, pending domain review,
with `REVIEW_CHECKLIST.md`; built by `.context/fi_key_builder/`). `pre_hook` reports its
version and review status. Every grade is provisional until the key is reviewed and
every value has a human value or sign-off.

LLM judge (proposals for human sign-off, as in increment A; mocked in tests, costed when
run): `python -m environment.incident.judge run <episode_dir> --task
gb-2019-full-investigation --dry-run` plans and prices the requests without sending
anything; drop `--dry-run` to judge (`OPENROUTER_API_KEY` required). `--task` selects
this task's key, bundle, grader (`fi_grading`), output budget and judge defaults, which
`configs/judge.fi.example.json` spells out: the rubric
`private/full_investigation/judge_rubric_v1.md` and per-topic request scope (decision
52). Each topic's request carries only its own findings in full, the report text that
refers to them, their cited spans and the topic's keyed spans, plus every other finding
by ID, status and opening words; T17 (the uncertainty register) sees every finding and
the whole report but only its own findings' spans. A topic whose judge criteria an error
stated anywhere bounds (T15.04's communications presented as a cause, T14.04/T14.05's
enforcement outcome, ...) also shows every finding with a sentence that meets those
error patterns or whose sentence vocabulary ranks the topic (`error_screen`). On a
realistic synthetic submission scoped requests are about 44% of the input tokens of
whole-submission requests, 49% on the real pilot. Without `--task`, a
full-investigation `--key` brings the same defaults.

### Running

```bash
python -m environment.incident.cli list --bundle src/environment/incident/bundles/full_investigation
python -m environment.incident.cli replay out/<run>_artifacts/episode
karotte run --config configs/fi_live_run.example.json   # costed live run; ask first
```

Fake-model scenarios (`environment/fake_model_fi.py`; `karotte run --config
configs/fi_fake_<scenario>.json --runtime docker`; files in `reference/`): `reference`
(the default: a scripted investigation of the whole incident through all nine tools in
41 calls, every retrieval route, ten witness questions, the not-held data returns its
evidence requests name, `reference_analysis.py` and `reference_crosscheck.py` through
`run_python`, then `reference_submission.json`, which reaches content 1 and evidence
support 1 on all 106 criteria of the key), `repair` (the same investigation, an invalid
submission with wrong record locators on the new evidence, then the reference),
`no_submission` (the same investigation, then no submission) and `isolation_probe`
(sandbox probes of the full-investigation documents, logs, witness cards and private
provenance; hostile tool calls with path traversal and private IDs in the new documents,
rooms, personas, signals and data returns, requests for the excluded enforcement
settlements, a forged cursor, and prompt injection in a question to each new witness and
in a document description; then a materialisation probe). Any other unscripted
`gb-2019-*` task raises an error rather than playing another task's script.

The reference reads 12 of the 20 listed documents (R09 and R11 only through narrow log
windows), so that its context stays inside the cap: its estimated peak input is about
157,700 tokens (79% of 200,000), with the pilot's tokens-per-character fit
(`tests/test_fi_reference_context.py`). Reading the eight documents it leaves unread
would add about 66,000 tokens.
