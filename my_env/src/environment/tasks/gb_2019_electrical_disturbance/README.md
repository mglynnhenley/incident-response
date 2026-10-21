## GB 9 August 2019 electrical disturbance (MVP)

Task id: `gb-2019-electrical-disturbance`. One step.

### Background

A retrospective investigation exercise. The agent receives the brief from the MVP plan
(initiating event, generation-trip and frequency sequence, supported explanations versus
unresolved causes), a neutral catalogue of five evidence records (R01, R03, S01, S03,
S04), and four tools. Some records are labelled reconstructions; R01 is a real measured
frequency extract.

After the verbatim brief, a short "Report expectations" list (`prompt.py`,
`REPORT_EXPECTATIONS`) names what the report should cover: the initiating event, how it
was cleared and whether the protection performed as required; a dated chronology with the
clock basis of every time and, for times taken from a record, the clock that record uses
and any conversion applied; each generation loss with its size and timing; the frequency
excursion from the measured record (each minimum, recovery to 50 Hz, time below 49 Hz)
with the computation method and sampling limits; and, for each trip, the established
mechanism versus what remains unexplained, labelled with finding statuses. It contains
no values, clocks or requirements and does not prescribe how to count the time below
49 Hz: the agent chooses and states its convention. Every criterion of the answer key
maps to one of these items.

### Motivation

Tests whether an agent can find the relevant evidence, analyse real frequency data, and
write a cited account that keeps established mechanisms apart from unknown causes.

### Tools

Exactly four, all thin adapters (`environment/tools/*.py`) over the reusable core in
`environment/incident/`:

| Tool | Purpose |
| --- | --- |
| `list_documents(category?, cursor?)` | catalogue page (50 per page, opaque cursor) |
| `request_document(doc_id)` | numbered text + read-only copies in `EVIDENCE_DIR` |
| `run_python(code)` | Python 3.12 with numpy/pandas; cwd = persistent scratch dir |
| `submit_findings(submission)` | v3 validation; the first valid submission freezes |

Every result is one text block (compact JSON header + body) for the model, and the full
envelope `{ok, request_id, tool, evidence_ids, data, error, next_cursor, budget}` as
structured content. Rendering of the deterministic tools is byte-stable, so traces replay.

Every parameter is optional and accepts any JSON value at the MCP layer while advertising
its documented schema (`TextArg`, `SubmissionArg`), so missing or wrong-typed values reach
the ledger and come back as a counted `INVALID_ARGUMENT` (or `VALIDATION_FAILED` for a
submission). Two kinds of call never reach the ledger and are not counted: tool-call JSON
that does not parse (Karotte answers it) and an argument name the tool does not accept
(FastMCP refuses it; tools cannot take `**kwargs`). The prompt and tool descriptions say
so, and the judge reports such calls as `transcript_summary.ledger_discrepancy`.

### Budgets

50 tool calls (calls with invalid argument values, Python and submission attempts
included; see above for the calls that are not counted); Python 30 s wall time, 1 GiB
memory (Linux), outputs capped at 20,000 characters per stream; context cap
200,000 tokens (`step_context_window_limit`); output budget 30,000 tokens (measured from
the transcript up to the accepted submission).

### Isolation

In the container `run_python` runs as the student (Karotte's
`student_session_command`) with `RLIMIT_AS`/`RLIMIT_CORE`/`RLIMIT_FSIZE`, a minimal
environment, and `kill_processes(STUDENT_UID)` after every call.

- Network: the session gets its own network namespace with no interfaces whenever the
  sandbox allows one (always on gVisor). Where user namespaces are refused (e.g. runc
  under Docker's default seccomp profile) it falls back to Karotte's default for student
  sessions, the uid firewall: that blocks the internet but not loopback or the sandbox's
  own addresses, and enforces nothing when `KAROTTE_FIREWALL_TOLERATE` hands isolation to
  an outer harness. Every result reports which applies (`data.limits.network`:
  `namespace` or `karotte_firewall`), as do the pre-hook metadata and
  `episode_config.json` (`network_mode`).
- Cleanup fails closed: if `kill_processes` raises (e.g. `UnreapableCohortError`), the
  call is reported as `INTERNAL_ERROR`, the scratch directory is not inspected beside
  processes that may still be alive, `state.cleanup_failures` is incremented (the judge
  reports it under `transcript_summary.isolation`), and the next `run_python` call kills
  leftovers before running anything. `pre_scoring_hook` saves the episode directory even
  when its own kill fails, then re-raises (Karotte scores that as misbehaviour, 0).
- Root-side work after each call is bounded: the scratch walk stops after 5,000 entries,
  8 levels or 2 s, and at most 64 MiB of listed files are hashed per call (beyond that a
  file's `sha256` is null and `hash_skipped` is true).

The bundle and private data live under `/root` and the ledger under
`/root_data/episode`; neither is readable by the student. `environment/incident_checks.py`
verifies this at image build (`karotte check`), including, as the student, that files in
a materialised evidence directory cannot be written, replaced, renamed or symlinked.
Outside a container the runner is in development mode and says so in `data.limits`.

### Data

`environment/incident/bundle/` (agent-visible, hash-verified at load; fails closed) and
`environment/incident/private/` (grader-only). The episode directory holds `state.json`,
`trace.jsonl`, `episode_config.json`, `submission.json` (frozen) and `grade.json`; it is
saved as an artifact before scoring.

### Scoring

The step score is **completion only**: `1.0` when a valid submission was frozen within
the tool-call and output-token budgets, otherwise `0.0` with an `incomplete_reason`
(`tool_budget_exhausted`, `context_cap_reached`, `output_token_budget_exhausted`,
`final_message_without_submission`, `time_limit`). It is not a quality score and there is
no pass threshold. When `environment.incident.grading` is installed, the judge calls
`grade_episode(episode_dir, transcript_summary)` and stores the result in `grade.json`
and the scoring metadata; those quality measures stay provisional until human
adjudication and domain review of the answer key.

### Running

```bash
karotte run --config configs/fake_run.json          # scripted fake agent, no model cost
python -m environment.incident.cli list             # verify and list the bundle
python -m environment.incident.cli inspect out/<run>_artifacts/episode
python -m environment.incident.cli replay out/<run>_artifacts/episode
python -m environment.incident.cli validate submission.json
python -m environment.incident.cli grade out/<run>_artifacts/episode --transcript out/transcript.json
```

`configs/live_run.example.json` is the template for a separately requested, costed live
run.
