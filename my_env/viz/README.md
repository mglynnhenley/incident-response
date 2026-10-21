# Agent world

A local pixel-art viewer for incident-response runs. The self-contained HTML uses
vanilla JavaScript, canvas sprites, and system monospace fonts. There are no
external assets, frontend dependencies, or build steps; the launcher uses only
Python's standard library.

Run these commands from `my_env/`:

```sh
uv run python viz/serve.py --port 8808
# Or:
just viz 8808
```

The launcher opens `http://127.0.0.1:8808/`. Add `--no-browser` to suppress that.
Stop it with Ctrl+C.

Choose a saved run discovered under `out/**/transcript.json`, or use **Open JSON**
or drag and drop to import a Karotte transcript. Runs are grouped by task: the MVP
(`gb-2019-electrical-disturbance`), the system response (`gb-2019-system-response`)
and the full investigation (`gb-2019-full-investigation`, for example the fake
scenarios in `out/fi/<scenario>/`). Runs that share a run ID, such as an archived copy,
are labelled with their folder. Play, pause, step,
scrub the timeline, change speed, or enable timestamp-based pacing. Click a station,
cabinet, witness or timeline event to inspect its story, arguments, code, results,
and findings. The station buttons under the office do the same from the keyboard.
Space toggles playback; the arrow keys step between events.

Every tool has a station:

| Tool | Station |
|---|---|
| `list_documents` | Catalogue desk |
| `request_document` by `doc_id` | That document's cabinet in the archive |
| `request_document` by `party` and `description` | Enquiries hatch (matched cabinet lights up; ambiguous candidates are laid out) |
| `query_frequency` | Frequency desk (draws the returned samples; MORE marks a `next_cursor`) |
| `query_asset_log` | Asset-log terminal (one icon per asset in the run) |
| `query_control_log` | Control room console (one screen per room in the run) |
| `interview_witness` | Interview corner (witness roles, no names; "not known" and topic choices shown) |
| `request_data_return` | Data-returns counter (NOT HELD and REFUSED are stamped refusals) |
| `run_python` | Python bench |
| `submit_findings` | Mailbox |

Stations for tools the run did not offer are shown closed. The cabinets, witnesses,
assets and control rooms come from the run: the task's document list, the catalogue,
and whatever the agent's calls returned. The office is laid out once per run so it
does not rearrange during playback. The archive's category bays come only from the
run's opening (the task's document list and the first catalogue listing): a document
whose category is shown only later, by a retrieval, a data return or a filtered
listing, stays in the unnamed bay, so the spacing at the start never reveals which
documents the run will obtain. Labels appear only once the agent has been shown them by
the selected event. Before the catalogue listing, cabinets carry only the
task's document IDs, category bands are blank, witness seats are empty, asset icons
are plain boxes, the control-room screens are dark and the plate reads NO ROOM YET. After that, documents
the catalogue omits (data-return-only records such as S05 and S06) carry a padlock
and a gold marker in the backpack. The inspector says "not listed yet" until then.
What was obtained, asked or refused always reflects the selected event. Unknown
tools wait on the thinking rug and stay inspectable.

Larger runs stay legible. When the full IDs no longer fit on one row, cabinets stack
in two rows, with each category kept in one bay; the full investigation's 22 documents
in twelve listed categories (including transport, essential services, communications
and compliance) and the unnamed bay of its two data-return documents fill two rows. Any cabinets beyond that go into a "+N" drawer. Past five
witnesses, a second row stands behind the bench (the full investigation's ten fill
both rows), and past ten the rest wait behind a "+N" card. Name tags use the
organisation's abbreviation or initials (UKPN, NR, NHS). Past five asset logs, the
last icon becomes a "+N" chip. Each control room has its own screen, tagged with the
last specific part of its ID (COMMS, ENCC, FLEET, RAIL); the plate below names the
room in full, the queried room's screen is framed and a gold corner marks a room
whose entries have been read. Past four rooms, the last screen becomes "+N". Each
"+N" opens the matching list in the inspector, which the station buttons also reach
from the keyboard; a room's screen, like an asset icon, opens that room's visits.
Past six refusals the data-returns spike shows its count.

Asset-log rows show the time as recorded, the signal and the value. A row with a
unit but a null value (a REMIT revision published outside its event window, for
example) is shown as "value null" with its row text, which keeps the declared
figures; nothing is filled in.

Only an accepted submission puts finding cards in the mailbox tray. A rejected
attempt (for example `VALIDATION_FAILED` or `EPISODE_CLOSED`) comes back out of the
slot stamped RETURNED, and the tray keeps whatever was accepted before. The Findings
tab also shows the accepted report's executive summary and sections (chronology,
recommendations, further evidence requests and so on) as submitted, never those of
a rejected attempt.

The tool-call and output-token budgets and the context cap come from the task
metadata (for example 150 calls, an 80,000 or 30,000 output-token budget and a
200,000-token context cap), or from the scoring record for older transcripts. The
token meter turns red when output exceeds the budget, and a submission frozen over the
budget gets no celebration. The context cap applies to one turn's input, so the
context meter shows the latest turn's input tokens against the cap, as the episode
summary decides it; the line below gives the largest turn so far and the cumulative
input. The final card gives the
recorded outcome, such as **Run incomplete — output-token budget exhausted**.

To follow a local run as it writes its episode:

```sh
just viz-live
# A different episode directory and port:
just viz-live root_data/episode 8808
# Equivalent launcher command:
uv run python viz/serve.py --live root_data/episode --port 8808
```

Live mode polls `trace.jsonl`, `state.json` and `episode_config.json` every 500 ms and
waits if the trace does not exist yet. The episode configuration supplies the tool
names and tool-call budget before the first call. It follows completed tool calls;
reasoning, token usage and the output-token budget become available with the
finished transcript. When a matching transcript
appears under `out/`, **Reload full replay** opens it. Container runs need a
bind-mounted episode directory for live follow: otherwise their artifacts are
only copied to `out/` after the run ends.

**Completed — provisional** describes completion, not factual accuracy or
evidence quality. When a saved run has an accompanying `grade.json`, the viewer
also shows its review status, flags, and how many criteria and assertions await a
human decision (judge proposals included) and how many are decided (automated, human), and for the full
investigation the executive summary's word count against its limit as the grader
counted it. It never shows a score. Grading happens after the run, so these notes
appear only from the scoring event on; before it, including after seeking back, the
panel says so and offers a jump to the scoring event. When `episode/judge/` holds LLM
judge outputs, the viewer reports them as proposals awaiting human sign-off, and
notes when the requests were scoped per topic (the full investigation). An imported
transcript uses the grade embedded in its scoring record. Karotte caps a metadata
value at 1 MiB, so a full-investigation grade (about 2 MB) arrives truncated: the
viewer says so instead of reading it, and the saved run's `grade.json` has it whole.
A grading error in the scoring record is shown as recorded. `/api/runs` sends a
compact summary of each grade; the full files stay readable through `/api/file`.

## Results: Report, Grades and Compare

Three tabs sit above the office: **Office replay**, **Report** and **Grades**. Arrow
keys move between them. Report and Grades describe the finished run, not the selected
event. They never change the replay's state, and live follow shows them only once the
run is saved. In the office, the Findings tab offers **Open the full report** once a
submission is accepted, and the grading panel offers **Open the Grades tab** from the
scoring event on.

**Report** renders the frozen `episode/submission.json` as text, falling back to the
transcript's accepted submission for an imported file:

- **Report text.** The executive summary and each section, with headings, lists (an
  indented list nests inside its item, and an indented paragraph after it returns to
  that item), tables and bold. `[F01]` and `[F01, F02]` references link to the finding; a reference to an
  ID the submission does not contain stays plain text. Each finding says which sections
  refer to it, as the grader reads them.
- **Findings.** Status chips (observed, reported, inferred, hypothesis, unknown), with a
  status filter. Each card gives quantities, event times and derivations as submitted,
  any grade flags (uncited, hedged or inferential wording, accounting, suspected
  severe), and links to the criteria that matched it.
- **Citations.** Each citation is a chip. A chip is marked when the grade says the
  citation **does not resolve**, cites evidence **never obtained** during the run, or
  cites a record obtained only **via its document**.
- **Evidence drawer.** A chip opens the drawer: the cited lines with a few lines of
  context, the time-series rows (`time:`, `row:`, `rows:`), or the asset-log event,
  control-log entry or witness answer (`event:`, `entry:`, `response:`).
- **Which bundle.** The text comes from the bundle the run used, matched by the manifest
  sha256 in `episode_config.json`. A run from a bundle that is not on disk (the MVP live
  run used bundle 1.0.0; the repository holds 1.1.0) is told so, and no text is shown,
  because lines can differ between versions.
- **Incomplete runs.** An incomplete run's submission, such as the 30k system-response
  run that exhausted its output budget, is shown under an **Incomplete** banner because
  it was not graded.

**Grades** reads `episode/judge/grade.json` when it exists (it supersedes the run's
`grade.json`), else `grade.json`, else the grade embedded in an imported transcript:

- **Banner and header.** A **Provisional — awaiting human sign-off** banner (with the
  grader's reasons), then the outcome, the budgets used, the answer key version and
  review status, and which file the grade came from.
- **Three measures.** Content coverage (full, half, zero), evidence support
  (supported, not supported, not applicable) and assertion quality (supported,
  unsupported, contradicted, not checked), each with a class for values without one
  (see **Counting**). Each has its own card and per-topic
  rows (T01–T20 or D1–D4) with counts and a small stacked bar. They are never added
  together, and no score, threshold or ranking is shown. The grade names no topics, so
  each row shows its first criterion title as a hint.
- **Where each value comes from.** Every value names its source: automated decision,
  judge proposal, capped by automated check, pre-screen proposal (the automated
  suggestion for the reviewer; grade.json records it as pending), human decision,
  confirmed severe flag or pending. Proposals are striped.
- **Capped values.** The grader records a judge proposal that an automated check lowered
  (a suspected severe flag, unless a reviewer rejects it, or an accounting cap) with
  source `judge`, the capped value and the judge's own value in `judge_proposal`. The
  viewer attributes such a value to the cap, never to the judge: "Zero · Capped by
  automated check · judge proposed Full". The criterion names the check that capped it
  and shows the grade's basis with its cap note. Capped values are counted under their
  own source on the Grades tab and the compare page.
- **Counting.** **Best available** counts the decided value, else the judge's proposal,
  else the pre-screen's. This reproduces the full-investigation pilot's 83 full, 21 half
  and 2 zero of decision 76; the class without a value is then **No proposal** (nothing
  proposed yet). **Decided only** counts every proposal as **Pending**. In either mode
  each card, topic row and compare cell also says how many values await a human decision
  and what is proposed for them: the pilot's content reads "102 of 106 awaiting a human
  decision (53 judge proposals · 49 pre-screen proposals) · 4 automated decisions",
  which matches the grade's own 53 judge and 49 pending criteria.
- **Criterion detail.** Expanding a topic shows its criteria (or, for assertion
  quality, its assertions). Each gives the assessment mode, both values with sources,
  the pre-screen and evidence bases, the judge's rationale and quoted spans (which open
  in the drawer), and a judge comment that was not applied. It also lists matched
  findings (linked to the Report), caps and pre-screen contradictions. A judge value
  that differs from the pre-screen's is highlighted as a disagreement for a human to
  decide.
- **Flags and legend.** A flags section lists severe, accounting, labelling,
  inferential, citation and reference flags with their excerpts. **What do these words
  mean?** explains every term.

Links are shareable: `#run=<path under out/>&view=report&finding=F03`, or
`#run=<path>&view=grades&measure=evidence&count=decided&topic=T05&criterion=T05.03`.

**Compare** lives at `http://127.0.0.1:8808/compare`, or use **Compare runs** in the
header:

- **What it shows.** Every run under `out/`, grouped by task, as a matrix of runs ×
  topics. Each cell is a small stacked bar with its counts and, below them, how many
  values await a human decision, beside the run's outcome, tool calls, peak context
  (largest turn's input tokens) and output tokens.
- **Filters.** Task, model, measure, count mode, and whether to include `out/archive/`
  (also kept in the hash, for example `/compare#task=gb-2019-system-response&archived=hide`).
- **Ordering.** Runs are listed by model and folder, never by a measure. An incomplete
  or ungraded run says why instead of showing cells.
- **Opening a cell.** Clicking a cell (or pressing Enter on it) opens that run's Grades
  tab at that topic. The page carries the same provisional banner.

Changing a filter, the count mode, the measure or the Report's status filter rebuilds
the view; keyboard focus returns to the control that was used.

The compare page reads `/api/results`, which carries each run's metrics and a compact
projection of its grade (about 20–35 KB for a full investigation, against 1.2 MB for
the whole grade). The projection keeps the grade's schema, so the viewer counts it with
the same code as a full grade. Only the opened run's whole grade is fetched.

The evidence drawer reads `/api/evidence?bundle=<manifest sha256>&evidence_id=R03&locator=L36-L40`
(and `/api/bundles` lists what is on disk). It is read-only and reads only files a
bundle manifest lists: the MVP bundle, `bundles/system_response` and
`bundles/full_investigation`. Each file must match its manifest hash. No link is
followed anywhere along the path, nothing is read outside the bundle, and nothing under
`private/` (answer keys, provenance, checklists) is ever served. Evidence IDs are
identifiers, not paths. A citation that does not resolve comes back with the reason, as
the grader would give it. Everything is rendered as text.

The HTML keeps three separate inline scripts: a pure data adapter normalizes
transcripts and traces, reconstructs state when seeking, and reads submissions and
grades for the results views (report text, per-topic counts, value sources, compare
grouping); the canvas scene renders the office and animations; the controller handles
loading, playback, live polling, the inspector, the Report, Grades and Compare views
and the evidence drawer. The adapter can be tested without a browser.

Run the server and data-adapter tests from `my_env/`:

```sh
uv run --frozen --extra test pytest -q tests/test_visualiser.py
node --test tests/test_visualiser_data.cjs
```

The Node tests use the built-in test runner and require no package installation.
They run the scene against a no-op canvas and the controller against a minimal fake
DOM. That covers layout bounds, the reveal rules, mailbox decisions and live-reset
behaviour without a browser, and a synthetic full-investigation run (22 documents,
ten witnesses, four control rooms, REMIT rows with null values, the context cap, the
report sections and a truncated grade) in replay and live. Synthetic results tests
cover report rendering and finding links, value sources and per-topic counts, judge
and pre-screen disagreements, compare grouping, the evidence drawer, hash links and the
compare page, capped judge values, nested report lists, the awaiting-a-human counts,
focus after a control rebuilds a view, and the rules that keep the Report inside a
390 px screen. The server tests resolve every locator kind on each of the three real
bundles and refuse traversal, `private/`, linked and unlisted files. Tests against saved
run fixtures (`out/fi/`, `out/fi_pilot/`, `out/panel_sr80k/` and others) are skipped
when those fixtures are absent. They check that every citation the grader checked
resolves the same way here, that the FI pilot counts 83/21/2 best available with 13
judge-mode disagreements, that the judged panel runs name their capped values (six in
`panel_fi`, four in the 80k sonnet run) and await a human for exactly the grade's judge
and pending values, and that report references match the grader's
unreferenced-findings flag.
