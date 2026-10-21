# GB 9 August 2019 electrical disturbance — MVP guide

One Karotte task (`gb-2019-electrical-disturbance`, one step) in which an agent
investigates the electrical disturbance of 9 August 2019 with four tools
(`list_documents`, `request_document`, `run_python`, `submit_findings`) and five evidence
records (R01 frequency data; R03 transmission fault and protection records; S01 Hornsea
event log; S03 Little Barford alarm records; S04 Little Barford shift account). It submits
one v3 JSON object: a readable report (executive summary of at most 600 words) and cited
findings.

The agent's instructions are the plan's brief, verbatim, followed by a short **Report
expectations** list (`prompt.py`, `REPORT_EXPECTATIONS`): the initiating event, how it
was cleared and whether the protection performed as required; a dated chronology with the
clock basis of every time and, for times taken from a record, the clock that record uses
and any conversion applied; each generation loss with its size and timing; the frequency
excursion from the measured record (each minimum, recovery to 50 Hz, time below 49 Hz)
with the computation method and the sampling limits; and, for each trip, the
established mechanism versus what remains unexplained, with status labels. It names
deliverables only: no values, clocks, requirements, sites or causes, and no convention
for the time below 49 Hz (the agent must choose one and state it). Every criterion of
the key maps to one of these items (a test checks the mapping).

**Status: provisional.** The reduced answer key (`key_version` 0.3.1, bound to evidence
bundle 1.1.0) is `pending_domain_review`. Every grade is provisional until a domain reviewer signs
`src/environment/incident/private/REVIEW_CHECKLIST.md` and a reviewed key version is
published, and until the human decisions for that run are recorded. There is no pass
threshold, no overall score and no ranking.

## Layout

| Path | What |
|---|---|
| `src/environment/incident/` | reusable core (no Karotte import): catalogue, locators, episode ledger, Python runner, submission validation, replay, CLI |
| `src/environment/incident/bundle/` | the frozen agent-visible evidence bundle (hash-verified) |
| `src/environment/incident/private/` | grader-only: `provenance.json`, `answer_key.json`, `REVIEW_CHECKLIST.md`, source manifest |
| `src/environment/incident/frequency.py` | pure-Python reference analysis of R01 (landmarks, zero-order-hold duration) |
| `src/environment/incident/grading.py` | automated checks, human-decision merge, grade report, review template |
| `src/environment/tasks/gb_2019_electrical_disturbance/` | the Karotte task, prompt, judge; `reference/` holds the reference submission and analysis |
| `src/environment/fake_model.py` | scripted fake-agent scenarios |
| `tests/fixtures/` | fixture submissions and builder-made decisions files; `live/` holds five real live-run submissions (and the 1.0.0 bundle run 001 ran on) |
| `builder/` | builder-only scripts (R01 extraction, provenance verification); not in the image |

## Running the tests

```bash
cd my_env
uv run --frozen --extra test pytest -q            # everything
uv run --frozen --extra test pytest -q tests/test_grading_*.py
uv run --frozen --extra dev ruff format --check && uv run --frozen --extra dev ruff check
```

Tests that compare against builder-only material (the extracted PDF page text, the
handoff `frequency_checks.json`) look for it at
`../.context/handoff/{GB_power_cut_handoff,text}` (override with `GB_HANDOFF_DIR` and
`GB_TEXT_DIR`) and skip when it is absent. The grading tests cover: the reference R01
analysis reproducing the handoff checks exactly; every key quote found on its stated PDF
page; every visible-evidence locator resolving and containing its tokens; each key
example agreeing with the automated proposal; the automated outcomes for the correct,
incorrect, uncited, uncertain and incomplete fixtures; rejection of the invalid
fixtures; decisions merge and binding rejection; regression tests for reviewed
grading defects and for the key 0.3.0 checks (derived Little Barford times and the datum
uncertainty, clock bases, the duration convention, status labelling, the
`status_inferential_language` flag) in `tests/test_grading_regressions.py`; the D3/D4
outcomes of the five real live-run submissions and the key 0.3.1 rules (decision 18) in
`tests/test_grading_live_runs.py`; and end-to-end runs of the fake
scenarios through the episode core, the judge, grading, the CLI and replay (one of them
through Karotte's real runner and MCP server).

## Scripted fake-agent run (no model cost)

```bash
karotte run --config configs/fake_run.json --runtime docker
```

Without a terminal (from a script or an agent), add `--no-ui`: the interactive display
otherwise keeps the process running after the run has finished. An existing
`out/<run_id>_artifacts/` is not overwritten (a `_2` suffix is added), so move old
artifacts away first.

The fake model (`environment/fake_model.py`) dispatches on the run's `task_id`: the
template `example-task` gets the template's scripted `bash` turns, and
`gb-2019-electrical-disturbance` plays one scenario, chosen by
`extra_config.fake_scenario` in the run config (default `reference`):

| Scenario | What it does | Expected outcome |
|---|---|---|
| `reference` | lists the catalogue, requests R01, R03, S01, S03, S04, runs `reference_analysis.py`, submits the reference submission | `complete`, score 1.0 |
| `repair` | as `reference`, but the first submission is invalid and is repaired | `complete`, 1 invalid attempt |
| `no_submission` | retrieves and analyses, then ends without submitting | `incomplete_submission` / `final_message_without_submission` |
| `isolation_probe` | probes the sandbox from `run_python` before any retrieval, then submits an explicitly inconclusive (empty) submission | `complete`; read the PASS/FAIL lines |

To pick a scenario, pass a config with `extra_config`, e.g.

```bash
jq '. + {extra_config: {fake_scenario: "isolation_probe"}, run_id: "gb2019-probe"}' \
  configs/fake_run.json > /tmp/gb2019_probe.json
karotte run --config /tmp/gb2019_probe.json --runtime docker
```

The isolation probe prints one line per probe; **PASS means access was denied** (for
the evidence listing: nothing was materialised before retrieval). It tries to read the
bundle, private, episode, tool-config and protected-store locations, list `/root`, list
`EVIDENCE_DIR` before any retrieval, connect to 1.1.1.1:443, resolve a host name, create
files outside the scratch directory (each created file is removed at once), and start a
background process that a second call checks for. Run it in the container only: in local
development mode isolation is not enforced and most probes FAIL by design.

The transcript is written to `out/transcript.json`; the episode directory
(`state.json`, `trace.jsonl`, `episode_config.json`, `submission.json`) and `grade.json`
are saved under `out/<run_id>_artifacts/`.

## Inspecting, replaying and grading a run

```bash
E=out/gb2019-fake_artifacts/episode
python -m environment.incident.cli list                 # verify and list the bundle
python -m environment.incident.cli inspect $E           # ledger state and every call
python -m environment.incident.cli inspect $E --seq 7   # exactly what the model saw for call 7
python -m environment.incident.cli replay $E            # deterministic calls must match byte for byte
python -m environment.incident.cli replay $E --rerun-python
python -m environment.incident.cli validate submission.json
python -m environment.incident.cli grade $E --transcript out/transcript.json --out grade.json
python -m environment.incident.cli review-template $E --out decisions.v1.json
```

(Prefix with `uv run --frozen` outside the container.) An episode is graded against
the evidence bundle it ran on, which `episode_config.json` records (`bundle_version`,
`bundle_sha256`). By default the grader uses the episode's own `bundle_dir` when it
exists locally, else the installed bundle; if that is not the recorded bundle, `grade`
and `review-template` stop with a `GradingError` naming both versions instead of
checking the citations against other documents. Pass the recorded bundle with
`--bundle DIR` (alias `--bundle-dir`). The grade report's `bundle` section gives
`matches_episode` and `matches_key`; grading on a bundle the key is not bound to adds a
provisional reason. The grading module has its own entry point, which also applies a
decisions file (and takes `--bundle-dir` too):

```bash
python -m environment.incident.grading grade $E --transcript out/transcript.json \
    --decisions reviews/gb2019-fake.decisions.v1.json --out grade.reviewed.json
python -m environment.incident.grading grade-submission submission.json [--decisions F]
python -m environment.incident.grading review-template $E|submission.json --out F
```

### What the grade report contains

- `run`: outcome `complete` or `incomplete_submission` with the reason
  (`final_message_without_submission`, `tool_budget_exhausted`, `context_cap_reached`,
  `output_token_budget_exhausted`, `time_limit`), tool-call and token figures, ledger
  discrepancy, isolation mode. For incomplete runs the content measures are empty.
- `content_coverage.by_dimension`, `evidence_support.by_dimension`,
  `assertion_quality.by_dimension` — three separate measures, per dimension and (in
  `criteria`) per criterion. Each value has a `source`: `auto`, `human`, `pending` or
  `not_applicable`; pending values carry the automated `auto_proposal`.
- `criteria[]`: for each of the 19 criteria the content and evidence-support values,
  the matched findings and the automated checks (pattern elements, numeric candidates,
  contradictions, conflicting values, cited locators).
- `citations[]`: every citation with its normalised locator, whether it resolves,
  whether the document was retrieved during the episode, and which criteria's keyed
  spans it overlaps.
- `flags`: uncited findings, unresolvable citations, cited-but-never-retrieved
  documents, suspected severe assertions (SF1 established Little Barford root cause; SF2
  invented evidence record; SF3 enforcement outcome), labelling issues (hedged wording
  with a factual status), `status_inferential_language` (findings labelled observed or
  reported whose statement uses inferential wording such as "consistent with",
  "suggests", "indicates", "likely", "therefore", "implies" or "attributed to"; patterns
  in the key's `conventions.inferential_patterns`. Words inside single or double quotes,
  and clauses that attribute them to a named source ("Ofgem states ...", "according to
  R03 ..."; `conventions.inferential_attribution`), are the records' own wording and are
  not flagged. A proposal for the reviewer, never scored), labelled hypotheses/unknowns,
  conflicting
  landmark values, findings not referenced in the report, and what needs human review.
- `status` (`provisional` or `final`) and `provisional_reasons`.

Automated decisions: the D3 frequency landmarks (D3.1–D3.4) are checked against the
frozen R01 series (± 0.002 Hz and ± 1 sample; duration 33 s, full within 1 s, half within
3 s). The key value for the duration is strictly below 49 Hz under a zero-order hold, but
the brief prescribes no convention: at or below 49 Hz (34 s; 16:53:40 is exactly
49.000 Hz), linear interpolation (about 33.96 s) and the first-to-last-sample span (32 s)
all earn full credit, and D3.5 asks whether the submission states its convention and the
1-s sampling limit. The value is the finding's `quantity` (the
unit is read from its leading word, so `Hz (1-s sample)` is Hz; mHz, ms and min are
converted) or, when the quantity does not fit the criterion (missing, unreadable unit,
another unit such as "283 s after the fault", outside the value range such as a 1.208 Hz
drop, or dated only outside the window), a value written in the statement or
derivation, paired with the time written next to it in the same clause (else the
`event_time`); a time that is only the reference of an offset ("207 s after its minimum
at 16:53:49") dates the value at the computed time. A value dated in the landmark window
beats any value without a time; numbers without a time worded as thresholds, limits or
statistics, described as before the event, or dated outside the window elsewhere in the
submission are not candidates. A value read only from prose is never failed
automatically: if none is within tolerance the criterion goes to a human
(`needs_human_review`). Some candidates are never credited automatically either: a timed
value worded as a level or "not yet" ("still below 50 Hz at 16:57:15"), a number written
without a unit, prose seconds without duration wording, and a statement value beside
its own finding's out-of-tolerance quantity. A D3 criterion is decided as 0 only when
no candidate appears anywhere (findings of any status and the report text) or when a
structured quantity placed in the window is outside tolerance and nothing else in its
finding is within tolerance; a candidate only in the report or in a finding labelled
hypothesis/unknown also goes to a human (`auto_checks.other_candidates` lists it).
D3 evidence
support requires an R01 time/row citation covering the landmark (or the first and last
sample below 49 Hz) and R01 retrieved in the episode; when R01 was never analysed with
`run_python`, or the derived duration (D3.4) has no `derivation`, it goes to a human.
Uncited findings get evidence support 0. Everything else is an automated *proposal* for
the reviewer. Since key 0.3.0 the proposals also check what bundle 1.1.0 leaves to the
agent: D2.1 expects the Hornsea UTC log times on the chronology's clock (an unlabelled
UTC reading is read as BST and is an hour out); D2.2–D2.4 expect clock times derived as
T + offset and the ± 0.5 s datum uncertainty stated somewhere for the Little Barford
times (± 500 ms and "a half-second uncertainty" also count); D2.5 expects both clock
bases (S01 UTC, S03 datum T) and caps a Hornsea/ST1C order stated more finely than the
datum; D3.5 expects the duration convention and the sampling limit. These method checks
read a finding's statement, `derivation` and `quantity.basis` together, and each sentence
of the report, because the brief tells the agent to put how a value was obtained in
`derivation` and `quantity.basis` (`conventions.text_fields`); every other check reads
the statement only. D4.4 gives full credit only when the unresolved causes
sit in findings the agent labels `unknown` (or `hypothesis` with not-established wording).
Since key 0.3.1 the established mechanisms (D4.1–D4.3) are also recognised in a finding
labelled `unknown` when one sentence states the mechanism with the trip or de-load and
without hedging, negation or uncertainty about the mechanism itself, because agents state
the mechanism and its open root cause together in such a finding; a finding labelled
`hypothesis` never counts, and the status otherwise matters only for D4.4. Numbers and times count for a unit or circuit end only when they describe
it (the nearest unit or end named in the same clause; the circuit name "Eaton
Socon–Wymondley" names neither end), and contradiction rules are applied sentence by
sentence. An evidence-support proposal of 1 needs a specific citation (at most 3x the
keyed span, floor 8 lines) of a *primary* keyed span; context spans (clock headers,
dataset descriptions), whole-document citations and citations outside the keyed spans
are sent for review, never failed, because alternative evidence is allowed.

## Human review workflow and file versioning

1. Generate a template: `python -m environment.incident.cli review-template <episode>
   --out reviews/<run_id>.decisions.v1.json`. It is bound to the frozen submission's
   sha256, the key version, the key's content sha256 and the bundle sha256 (all
   required), and pre-filled with the automated proposals under `_context` keys
   (ignored by the loader). Undecided values, including the explanation-quality notes,
   are `null`.
2. The reviewer reads the cited evidence and fills in `reviewer`, `date`, and for every
   criterion `content` (1 / 0.5 / 0), `evidence_support` (1 / 0), `finding_ids` and
   `notes`. For `auto_numeric` criteria `null` accepts the automated value and any value
   overrides it (recorded as `human_override_of_auto`); a D3 criterion the matcher
   could not settle (values only in prose) is pending until you set it. When you credit
   a criterion the matcher missed, list its `finding_ids`: their citations are then
   checked (automatically for D3); otherwise evidence support stays pending until you
   set it. For every factual finding set `verdict` (`supported`, `unsupported`,
   `contradicted`); mark paraphrases with `duplicate_of`; add assertions that appear
   only in the report prose with a new ID, `text` and `dimension`. Confirm or reject
   every suspected severe flag. A confirmed flag applies the key's `effect`: its
   findings become `unsupported` (source `severe_flag`) and, for SF1, D4.4 content
   becomes 0; a decisions file that marks such a finding `supported` or credits D4.4 is
   rejected. Write explanation-quality notes, overall or for every dimension.
3. Grade with the decisions: `python -m environment.incident.grading grade <episode>
   --decisions reviews/<run_id>.decisions.v1.json --out reviews/<run_id>.grade.v1.json`.
4. Versioning: never edit a decisions file that has been used. Copy it to
   `.v2.json`, bump `decisions_version`, and regrade. A decisions file bound to another
   submission, key version, key content (sha256) or bundle is rejected
   (`DecisionsError`). When the key changes (a new `key_version`; any edit changes its
   sha256), issue new decisions files for every affected run.

The two files in `tests/fixtures/decisions/` are builder fixtures (`builder_fixture:
true`) used only to test the merge. They are not domain reviews.

A grade becomes `final` only when: the key's review status is `reviewed`; every
criterion has a content and evidence-support decision (automated, human or a confirmed
severe flag's effect); every factual assertion has a verdict; every suspected severe
flag is adjudicated; explanation quality has been reviewed (non-empty overall notes, or
a non-empty note for every dimension; blank template placeholders do not count); the
decisions file is not a builder fixture; and the episode trace was available.

## Live run 001 findings and why the task changed

Run `gb2019-live-opus55-001` (Claude Opus 5.5; bundle 1.0.0, key 0.2.0; artifacts in
`out/live/gb2019-live-opus55-001_artifacts/`) finished in 9 of 50 tool calls, using about
7.8k of the 30k output tokens and 31k of the 200k context. All 23 findings were cited and
no severe flag fired, but about 18 of them restated a single evidence line. Bundle 1.0.0
had done the investigator's work:

- S03 gave derived BST times and intervals;
- S01 gave the 799 − 62 = 737 MW subtraction and the UTC/BST equivalences;
- S04 sorted statements into known, not known, not established and still a hypothesis.

The automated misses were D3.1 (the first minimum was given only as a range), D3.4 (no
time below 49 Hz) and D3.5 (no sampling limit). The brief never asked for any of these.
The task was too easy, and it was partly graded on things the brief did not request.

What changed:

- **Evidence (bundle 1.1.0).** The records keep raw values, the offsets, the SOE datum
  T = 16:52:34 ± 0.5 s and one clock-basis line each. The builder-computed conveniences
  are gone. So is the builder's classification of causes: S04 is now a chronological
  shift narrative followed by the operator's (30 August 2019) and Ofgem's (3 January
  2020) statements, in each source's order and wording.
- **Brief.** A "Report expectations" list names the deliverables (see the top of this
  guide). It gives no values and no duration convention.
- **Reference submission.** Findings that give derived clock times or the 737 MW
  subtraction (F10–F13) are labelled `inferred`, because bundle 1.1.0 no longer states
  them; `reported` is kept for what a record states.
- **Key 0.3.0.** Every locator was re-pointed to the edited records. The changes by
  criterion:
  - D2.1–D2.4: the agent derives the BST times itself (UTC + 1 h; T + offset).
    D2.2–D2.4 also need the ± 0.5 s datum uncertainty.
  - D2.5: needs both clock bases, and no Hornsea/ST1C order finer than the datum.
  - D3.4: same tolerance, with examples for 34 s (at or below 49 Hz) and linear
    interpolation.
  - D3.5: needs the stated duration convention and the 1-s sampling limit.
  - D4.4: needs the agent's own `unknown`/`hypothesis` labels on the unresolved causes.
  - SF1: also fires when the transmission fault is asserted as the established cause of
    the speed-signal discrepancy.
- **Grader 0.3.0.** New review flag `status_inferential_language`. Its first example is
  run 001's F14: "the largest 1 s fall was 0.151 Hz, consistent with about 981 MW
  (737 + 244) lost", labelled `observed`.

**Offline re-grade of run 001 with key 0.3.0 (sanity check).** The run was graded against
bundle 1.0.0, rebuilt byte for byte from its own trace (the `request_document` envelopes
carry each text and its sha256). Outputs went to `/tmp`; the stored artifacts are
unchanged.

- No automated content proposal changed. D1.1–D2.5, D4.2–D4.4, D3.2 and D3.3 are still
  1; D4.1 is still 0.5; D3.1 is still pending at 0; D3.4 and D3.5 are still 0.
- The reason: on a bundle that handed it the conversions and the labels, the run had
  already derived the Little Barford times with ± 0.5 s, labelled the Hornsea log as
  UTC, and labelled both open causes `unknown`.
- The new flag lists F14 ("consistent with") and F08 ("attributed to"). F08 is an
  attribution the run reported correctly, so a reviewer would keep its status.
- The run 001 submission does not validate against bundle 1.1.0 (four citations are out
  of range). Grade an old run against the bundle it ran on: pass `--bundle-dir DIR`
  (`catalogue=` in `grade_episode`). Without it the grader now refuses, because the
  installed bundle (1.1.0) is not the one the episode recorded (1.0.0).

Whether the revised task separates models is for the planned live panel to show; this
re-grade cannot.

**Key and grader 0.3.1 (decision 18).** Re-grading the live panel (bundle 1.1.0) found
grader false negatives. Expected values and tolerances did not change. What changed:

- D3 now reads the statement and derivation when the structured quantity describes
  something else, and decides 0 only on a genuine omission or a structured value that is
  wrong for the landmark.
- D4.1–D4.3 recognise a mechanism stated in a finding labelled `unknown`.
- Second verification round (still 0.3.1): offsets to a written reference time are
  computed; wording the grader cannot settle (timed "still below" or "not yet", no unit,
  prose seconds without duration wording, a statement value beside its own wrong
  quantity) goes to a human instead of being credited or failed; a `hypothesis` label or
  a denied mechanism earns no D4.1–D4.3 credit; D1.1 accepts lightning attributed to
  "the fault" in its own finding; reviewer notes for D2 times given only in the report
  and for a D3.5 convention that does not give the reported duration.

Changes in the automated results (all other D1–D4 values and proposals are unchanged):

| Run | Criterion | 0.3.0 | 0.3.1 |
|---|---|---|---|
| opus55-002 | D3.3 (F20: "50.001 Hz at 16:57:16", quantity 283 s) | auto 0 | auto 1 |
| opus55-002 | D4.2 (F11, status unknown) / D4.3 (F12, status unknown) | proposal 0 / 0.5 | 1 / 1 |
| sonnet55-001 | D4.2 (F09, status unknown) | proposal 0 | 1 |
| haiku45-001 | D3.2 (F09: quantity = the 1.208 Hz drop) | auto 0 | auto 1 |
| haiku45-001 | D3.3 (F11: quantity 207 s; F08's pre-event average had been picked) | auto 0 | auto 1 |
| opus55-002 | D1.1 (F01 circuit and fault type; F02 "NGET states that lightning caused the fault") | proposal 0.5 | 1 |
| sonnet55-001 | D1.1 (F01; F02 "NGET and ESO attribute the fault to lightning") | proposal 0.5 | 1 |

Haiku's D3.1 is still an automatic 0: it never reported the first minimum. Run 001 on
bundle 1.0.0 is unchanged: D3.1 is pending and D3.4 is an automatic 0, with no time
below 49 Hz anywhere. The submissions are regression fixtures in `tests/fixtures/live/`.

## What is provisional

- The answer key (0.3.1) has not been domain-reviewed (`REVIEW_CHECKLIST.md` lists the
  builder choices that need a decision, e.g. the ± 2 s generator-trip time tolerance,
  the D1.N and D2.5 scoring rules, and the reading of R03 and S03 times as BST).
- All `auto_assisted_human` proposals come from text patterns, times and quantities;
  they are suggestions for the reviewer, not grades.
- Severe-flag detection is heuristic; only a reviewer's confirmation makes a flag count.
- The reconstructed records (S01, S03, S04 and R03) have private provenance but have not
  been realism-reviewed by a domain expert.

## Known limitations

- Pattern-based proposals miss paraphrases and can be fooled by negations in unusual
  wording; reviewers should read the `auto_checks` and the cited spans. Entity binding
  is clause-based: a structured `quantity` / `event_time` is taken to describe the first
  unit the statement names, and lists such as "GT1A/GT1B at 16:53:31/16:53:58" cannot
  be bound reliably.
- Times written only in prose are read as BST unless marked Z/UTC; an `event_time` with an
  explicit offset is always preferred.
- Assertions are counted per finding; claims made only in the report prose need to be
  added by the reviewer.
- The scalar Karotte score is completion only (1.0 = a valid submission frozen within the
  budgets); it says nothing about quality.
- Locally (outside the container) `run_python` runs in development mode: no user switch,
  no network isolation and no memory limit on macOS. Isolation claims hold only in the
  container image (`karotte check` runs `incident_checks.py`; the `isolation_probe`
  scenario exercises it adversarially).
- Rail impacts, essential services, communications, compliance, recommendations and
  variants are out of scope for this MVP.

## Requesting a costed live run

A live run uses a real model and costs money; it is not run automatically. To request
one: (1) finish the domain review of the key, or accept that results are provisional;
(2) run the fake scenarios in the container and check the isolation probe; (3) estimate
the cost from measured dry runs (up to 50 tool calls, a 200,000-token context cap and a
30,000-token output budget per run) and current provider prices; (4) ask the project
owner for an explicit go-ahead with that estimate. Then copy
`configs/live_run.example.json`, set the model and the API-key variable, and run
`karotte run --config <your config> --runtime docker`. Grade and review the run as
described above.
