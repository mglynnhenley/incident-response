# Reviewer pack: signing off the GB 9 August 2019 answer keys

A domain reviewer's guide to the open decisions in the three answer keys of this environment.
Written by the builder on 2026-10-20 from the review checklists, `docs/DECISIONS.md` and the graded
runs. It is not a review, and nothing in it has been signed. The machine-readable list of the same
items is [`reviewer_pack_items.json`](reviewer_pack_items.json).

## 1. Orientation

**What the environment is.** An agent investigates the GB power disturbance of 9 August 2019 with
evidence tools (documents, the real 1-s frequency record R01, logs, witnesses, data returns and a
Python sandbox) and submits one cited report: findings with status labels (observed, reported,
inferred, hypothesis, unknown) and a report text. There are three one-step tasks. Each has a frozen
evidence bundle, an answer key, and a review checklist under `src/environment/incident/private/`.

| Task | Scope | Key (version) | Bundle | Criteria: auto_numeric / auto_assisted_human / judge | Graded runs |
|---|---|---|---|---|---|
| **MVP** `gb-2019-electrical-disturbance` | fault, generator trips, frequency (D1–D4) | `answer_key.json` 0.3.1 | 1.1.0 | 19: 4 / 15 / 0 | 5: live run 001, v2 panel ×4 |
| **SR** `gb-2019-system-response` | fault to demand restoration (T01–T09, T12, T16, T17) | `system_response/answer_key.json` 0.1.1 | 0.1.0 | 60: 4 / 32 / 24 | 6: sr80k ×3 (judged), sr30k ×3 |
| **FI** `gb-2019-full-investigation` | the whole incident (T01–T20) | `full_investigation/answer_key.json` 0.1.1 (cards first compiled on 0.1.0; see 1.1) | 0.1.0 | 106: 4 / 49 / 53 | 2: the pilot and the first panel run (both judged); the rest of the panel was still running |

**Increment A** is the SR task and **increment B** the FI task; cards, tests and `docs/DECISIONS.md` use both names.

**What sign-off means here.**

1. You decide each card in section 2: accept the builder's choice, or say what to change. Then copy
   the answers into the task's `REVIEW_CHECKLIST.md` (OK / Change / Remove per row) and fill its
   sign-off block. The handoff asks for two domain reviewers before benchmark findings are reported.
2. The builder publishes a **new key version** for each task with `review.status` and the top-level
   `review_status` set to `reviewed`. A signed version is never edited in place. "Approve as is" also
   needs a new version, because the status is part of the key's content and sha256. The builder then
   re-runs the key tests and regrades every run.
3. For each run, a **grading-decisions file** records the human values. It is bound to the
   submission, the key version and sha256, and the bundle sha256, so any key change invalidates it.
4. A grade becomes `final` only when the key is `reviewed` and that run's decisions file covers every
   criterion, assertion, suspected severe flag and the explanation-quality notes.

**Why every grade is provisional now.** No key has been domain-reviewed, so every value is
provisional. Each is an automated pre-screen (patterns, numbers, times), an LLM-judge proposal or
pending; none has been signed by a person. No run has a decisions file. The Karotte score measures
completion only, and the keys compute no total, threshold or ranking.

**Opening the evidence** (commands from `my_env/`):

- **Source reports** (builder-only): the PDFs are in
  `../.context/handoff/GB_power_cut_handoff/builder_only/sources/`. Per-page text is in
  `../.context/handoff/text/<SRC>.txt`, with page markers `=== ESO PDF page 12 ===`.
  - SRC: ESO = ESO technical report (Sep 2019); APP = its appendices; OFG = Ofgem report (Jan 2020);
    ORR = ORR rail report (2020); E3C = E3C final report (Jan 2020); E3C-I = E3C interim report
    (Sep 2019).
  - "p12" on a card is always the 1-based PDF page, whether or not "PDF" is written (FI cards write
    "ESO p30"). The ESO printed page is the PDF page + 1; Ofgem and ORR printed pages equal the PDF
    page; the appendices and the E3C reports carry no page numbers.
  - To search a report: `python3 ../.context/fi_key_builder/find.py ORR "within 200ms"`.
- **Bundle documents:**
  - Locations: `src/environment/incident/bundle/<ID>/<ID>.txt` (MVP),
    `…/bundles/system_response/<ID>/` (SR) and `…/bundles/full_investigation/<ID>/` (FI).
  - `L36-L37` means file lines 36–37 (1-based).
  - R01 is a CSV. `row:780` is the 780th data row after the header; `time:` locators are BST.
  - Records: `event:<id>` rows are in `logs/assets/*.jsonl`, `entry:<id>` rows in
    `logs/control/*.jsonl`, and `response:<id>` answers in `witnesses/*.json`. Find them with grep.
  - To verify and list a bundle:
    `uv run --frozen python -m environment.incident.cli list --bundle <bundle dir>`.
- **The key:** for each criterion, read `expectation`, `expected`, `tolerances`, `report_passages`,
  `visible_evidence` (primary or context spans), `auto` (the matcher or pre-screen) and `examples`.
- **Runs:** see the table below. `F12` on a card means finding F12 in that run's `submission.json`.
  Each run's `grade.json` lists every value with its source and basis.
- **The viewer:** `uv run python viz/serve.py --port 8808` (or `just viz 8808`) opens
  <http://127.0.0.1:8808/>. Pick a run under `out/` and replay its tool calls. The viewer shows each
  retrieval and citation, and the grade's review status and pending counts, but never a score. It
  reads files only and changes no grade.

| Run label on cards | Task | Submission (regression fixture) | Artifacts: episode, `grade.json`, judge output |
|---|---|---|---|
| live run 001 (Opus 5.5, bundle **1.0.0**) | MVP | `tests/fixtures/live/gb2019-live-opus55-001.submission.json` | `out/live/gb2019-live-opus55-001_artifacts/` |
| opus55-002, opus55-003, sonnet55-001, haiku45-001 | MVP | `tests/fixtures/live/gb2019-v2-<label>.submission.json` | `out/panel/<label>/gb2019-v2-<label>_artifacts/` |
| sr80k-opus55-001, sr80k-sonnet55-001, sr80k-haiku45-001 | SR (80k budget, judged) | `tests/fixtures/sr_live/<label>/` | `out/panel_sr80k/<model>/gb2019-sr80k-<model>_artifacts/episode/judge/` |
| sr30k-opus55-001, sr30k-sonnet55-001, sr30k-haiku45-001 | SR (30k budget; Opus and Sonnet ran out of output budget and are graded diagnostically) | `tests/fixtures/sr_live/<label>/` | `out/panel_sr_30k/<model>/gb2019-sr-<model>_artifacts/` |
| pilot, fi-pilot-opus55-001 | FI | `tests/fixtures/fi_live/fi-pilot-opus55-001/` | `out/fi_pilot/gb2019-fi-pilot-opus55-001_artifacts/episode/judge/` |
| panel run, fi-panel-opus55-001 | FI (first panel run) | `tests/fixtures/fi_live/fi-panel-opus55-001/` | `out/panel_fi/opus55-001/gb2019-fi-opus55-001_artifacts/episode/` (the rest of the FI panel was being written under `out/panel_fi/` when this was checked) |

**Time.** 180 items, 2,910 min (48 h 30 min), using the builder's estimate on each card:

| | P1 | P2 | P3 | Total |
|---|---|---|---|---|
| All tasks (items / min) | 110 / 2,010 | 55 / 715 | 15 / 185 | 180 / 2,910 |
| MVP | 31 / 440 | 17 / 250 | 7 / 130 | 55 / 820 |
| SR | 45 / 675 | 25 / 275 | 4 / 30 | 74 / 980 |
| FI | 34 / 895 | 13 / 190 | 4 / 25 | 51 / 1,110 |

In hours: P1 33 h 30 min, P2 11 h 55 min, P3 3 h 5 min. The 21 cross-task cards add no time of their own: they
group 115 items (29 h 25 min of the total) so that each shared question is decided once. Work
in this order: the cross-task cards, then P1, which must be settled before any result is called
more than provisional, then P2 and P3.

### 1.1 The FI key moved to 0.1.1 while this pack was written

The cards were first compiled against FI key 0.1.0 (canonical sha256 `1e36ee7e…`). A builder round
then swept the pilot and the first panel run against their submissions and published FI key and
grader 0.1.1 (decisions 77–80, now in `docs/DECISIONS.md`). On review the FI cards were brought to
the installed key 0.1.1 (canonical sha256 `d2ff5129…`, the value `tests/fixtures/fi_live/runs.json`
records and its tests check). The MVP and SR keys did not change.

- **Rows 0.1.1 added now have cards:** FI-B19 (pre-screen corrections), FI-B20 (figures in findings
  labelled unknown), FI-C2, FI-C3 and FI-C4 (accounting), all P1, and FI-B21 (labelling
  exemptions, P3).
  FI-G2 was rewritten to the new row G2 (both real runs). Row E1 (SF1) was revised; FI-E1 says
  what changed and why.
- **Values.** Where 0.1.1 changed a value an FI card quotes, the card gives the 0.1.1 value and what
  0.1.0 gave. Cards whose rules 0.1.1 changed carry a compiler's note: FI-A1, FI-A5, FI-B1, FI-B9,
  FI-C1, FI-D-T14.02, FI-D-T14.04-05, FI-D-T20, FI-E1, FI-X2, and cross-task cards XT-01, XT-08 and
  XT-21.
- **Before you sign.** Check that the installed FI key is still 0.1.1 with sha256 `d2ff5129…`:
  further FI panel runs were running when this was checked, and their sweep could change the key
  again. Then regrade the FI runs under it (section 3.4).

### 1.2 How the pack was checked

Every quoted source fragment of 12 or more characters on the cards was found on its stated PDF
page in the extracted text: 404 fragments (split at ellipses and editorial brackets) when the pack
was re-checked on review with an independent script, three of them by hand because an apostrophe
defeats the parser. Of the 25 quoted bundle lines, 24 are verbatim in their stated spans; the 25th
differs only by a value-status tag, which MVP-A4 notes (FI-B13's quote was made verbatim on
review). The R01 rows cited were checked against the CSV. Corrections and wording edits are
recorded as "Compiler's note" on the cards concerned and in `compiler_notes` in the JSON; review
changes say "on review". The grading commands in section 3.4 were
run on an MVP, an SR and the FI run, writing only to a temporary directory. That run showed the
stored SR and FI judge outputs no longer merge under the installed keys (section 3.4). On review,
`tests/test_fi_grading_live_runs.py` (78 tests) passed against the installed FI key 0.1.1, and both
FI fixtures were graded with their judge outputs re-bound in memory as those tests do, without a
judge call; the 0.1.1 values on the FI cards come from those grades and decisions 77–80.

## 2. Decisions

Each card gives:

- its ID, priority, estimated minutes, task, the key criteria it touches, its row in the task's
  `REVIEW_CHECKLIST.md`, and the cross-task card it belongs to, if any;
- the **question** to decide, the **builder choice** now in the key, the **alternatives**, and the
  **impact** on the graded runs (which values would move);
- the **evidence**: source quotes with their PDF pages, then bundle locators.

End each card by ticking one box on its decision line:

`Decision: [ ] accept  [ ] change to: ____`

**Accept** keeps the builder choice. **Change to** needs the new rule or value.

Card ID prefixes:

- `MVP-`, `SR-`, `FI-` + checklist row (A whole key, B builder choices, C severe flags or accounting
  bases, D per-criterion text, E severe flags or sign-off, F process, G real-run regression).
  For example, `MVP-B3` is row B3 of the MVP checklist.
- `-X` and `-DEC` items and `MVP-R01CLK` have no checklist row.
- `XT-` cards are this pack's cross-task cards.

### 2.1 Cross-task decisions

Decide these first. Each card settles the same question for every task that carries it; its member items (linked) then only need a tick, or a note where you want a task-specific exception.

| Card | Topic | Members | Item time |
|---|---|---|---|
| [XT-01](#xt-01) | Decide once for reused criteria (MVP → SR → FI) | 7 | 130 min |
| [XT-02](#xt-02) | Event-time tolerances: fault, protection, reclose, generator trips | 5 | 40 min |
| [XT-03](#xt-03) | Clock bases and the Little Barford datum | 9 | 130 min |
| [XT-04](#xt-04) | R01 frequency landmarks: definitions, tolerances, evidence support | 7 | 70 min |
| [XT-05](#xt-05) | Below-49-Hz duration, convention and method statements | 7 | 85 min |
| [XT-06](#xt-06) | Values the grader cannot settle: prose, report-only and unitless | 6 | 90 min |
| [XT-07](#xt-07) | Status labels: Little Barford mechanisms, unresolved root causes, figures | 6 | 80 min |
| [XT-08](#xt-08) | Severe flag SF1: what counts as an asserted Little Barford root cause | 7 | 105 min |
| [XT-09](#xt-09) | Severe flags SF2 and SF3: definitions | 6 | 80 min |
| [XT-10](#xt-10) | Severe flags: effects and who confirms | 3 | 35 min |
| [XT-11](#xt-11) | Hornsea mechanism: elements and attribution | 4 | 60 min |
| [XT-12](#xt-12) | Other lightning trips that day: required or not | 4 | 40 min |
| [XT-13](#xt-13) | Initiating fault and protection-assessment wording | 4 | 25 min |
| [XT-14](#xt-14) | Unit losses, entity binding and the GT1B manual trip | 5 | 45 min |
| [XT-15](#xt-15) | Evidence support: scales, citation width, context spans, retrieval | 5 | 55 min |
| [XT-16](#xt-16) | Never-scored review flags (labelling, inferential language) | 4 | 40 min |
| [XT-17](#xt-17) | Reporting: no total, finality, decisions binding | 6 | 40 min |
| [XT-18](#xt-18) | The LLM judge: modes, merge rules, rebinding, scoping | 6 | 110 min |
| [XT-19](#xt-19) | Expected values: evidence pack first, disagreeing sources kept apart, nothing beyond the bundle | 5 | 255 min |
| [XT-20](#xt-20) | Reconstructed records: leakage and realism | 3 | 150 min |
| [XT-21](#xt-21) | Restoration: boundaries and distinctions (SR and FI) | 6 | 100 min |

<a id="xt-01"></a>

### XT-01

**Decide once for reused criteria (MVP → SR → FI)** · applies to MVP, SR, FI · members (7, 130 min of item time): [SR-B1](#sr-b1), [FI-A5](#fi-a5), [FI-C1](#fi-c1), [FI-B19](#fi-b19), [FI-C2](#fi-c2), [FI-C3](#fi-c3), [FI-C4](#fi-c4)  

- **Question.** Should a decision on a criterion that recurs across tasks be taken once and applied to every key that carries it, and should the frozen MVP key follow when a shared rule changes?
- **Builder choice.** SR re-uses the MVP 0.3.1 matchers (parity tested on eight pairs; intended divergences T02.03b/D2.4, T02.04/D2.5, T06.01/D4.1, T16.01/D1.N). FI re-binds SR 0.1.1's 60 criteria with the same IDs, rules and tolerances and copies the accounting rules unchanged; the FI key builder reads the installed SR key (reuse.py), so an SR change reaches FI at its next build. The MVP key and grader are frozen baselines (decisions 21, 26): where SR/FI later moved on (SF1 valve attribution, SF3 triggers, labelling-caveat exemption, clock label after a range) MVP keeps its 0.3.1 rule as a known limit. FI key 0.1.1 has since diverged from SR 0.1.1: the pre-screen rules of six re-bound criteria (FI-B19), three accounting rules (FI-C2, FI-C3, FI-C4) and SF1's clause-scoped negation (FI-E1, XT-08) are FI-only; SR stays frozen.
- **Alternatives.** Decide each task separately. Or update MVP too whenever a shared rule changes (MVP key 0.3.2 and grader change).
- **Impact.** Sets how many key versions and regrades a change costs: a change to a shared rule touches up to three keys and 5 MVP + 6 SR + 2 FI runs (plus the rest of the FI panel). Deciding the cards below once also settles the matching rows in all three checklists.
- **Evidence.** tests/test_sr_grading_live.py PAIRS; tests/test_fi_grading_live_runs.py; FI key `reused_from` and per-criterion `rebinding`; DECISIONS 21, 26, 32, 65.
- **Compiler's note.** Installed FI key 0.1.1 (decisions 77–80; FI checklist A5, B19, C2–C4): FI no longer re-binds all SR rules unchanged: the installed key marks T02.04, T04.03, T05.02, T05.03, T06.02, T08.04, T08.05, T09.05 as changed re-bindings, and three accounting rules (C2, C3, C4) differ from SR 0.1.1.

(a) Each cross-task decision below applies to every task that carries the criterion — Decision: [ ] accept  [ ] change to: ____  
(b) MVP stays frozen at its 0.3.1 rules; later SR/FI refinements are recorded as known MVP limits — Decision: [ ] accept  [ ] change to: ____  
(c) FI 0.1.1's rule changes stay FI-only and SR 0.1.1 stays frozen: re-bound pre-screens (FI-B19), accounting binding, mismatch and inertia context (FI-C2, FI-C3, FI-C4) — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-02"></a>

### XT-02

**Event-time tolerances: fault, protection, reclose, generator trips** · applies to MVP, SR, FI · members (5, 40 min of item time): [MVP-B3](#mvp-b3), [MVP-B4](#mvp-b4), [MVP-B5](#mvp-b5), [SR-B3](#sr-b3), [SR-D-T01.03](#sr-d-t01.03)  

- **Question.** Are the builder's tolerances for printed event times right: protection 70/74 ms within ±1 ms (Ofgem's 'under 75 ms' alone 0.5), reclose 16:52:53 ±2 s, generator trips ±2 s?
- **Builder choice.** Fault time ±1 s is the handoff rule (D1.2, T01.02). The others are builder choices that FI inherits unchanged (FI key numeric_rules.source flags them): protection ±1 ms (D1.3, T01.03b; MVP full credit also needs 'within 80 ms'); reclose ±2 s (D1.4, T01.04; the source prints whole seconds); generator trips ±2 s around Hornsea 16:52:33.728–.835 BST and the SOE-derived Little Barford ranges (D2.1–D2.4).
- **Alternatives.** Trips ±1 s (the handoff's event-time rule), ±0.5 s (the datum) for Little Barford or about ±0.2 s for Hornsea's millisecond log. Protection ±5 ms, or 'under 75 ms, within 80 ms' as full credit. Reclose ±1 s.
- **Impact.** No live grade changes under any of these alternatives: every MVP run's D2.1–D2.4 time error is 0.0 s and all runs state 70/74 ms, 80 ms and 16:52:53. The width matters for future runs: ±2 s also admits ESO's whole-second timeline times and an un-derived T.
- **Evidence.** ESO PDF p12 (printed 13): 16:52:33.560 / .564 clearances, 16:52:53 DAR, 16:52:33.728 / .835 Hornsea; APP PDF p45 SOE offsets; APP PDF p26 '80ms at 400kV'; OFG PDF p28 'under 75ms'. Member cards carry the quotes.

(a) Generator trips ±2 s — Decision: [ ] accept  [ ] change to: ____  
(b) Protection times ±1 ms; 'under 75 ms' alone 0.5 — Decision: [ ] accept  [ ] change to: ____  
(c) Reclose ±2 s — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-03"></a>

### XT-03

**Clock bases and the Little Barford datum** · applies to MVP, SR, FI · members (9, 130 min of item time): [MVP-B1](#mvp-b1), [MVP-B2](#mvp-b2), [MVP-B6](#mvp-b6), [MVP-B21](#mvp-b21), [MVP-B22](#mvp-b22), [MVP-DEC19](#mvp-dec19), [MVP-R01CLK](#mvp-r01clk), [SR-B2](#sr-b2), [SR-B5](#sr-b5)  

- **Question.** On which clock is each record read, and where must a submission state clock bases and the ±0.5 s datum uncertainty?
- **Builder choice.** Unlabelled R03 times (and SR's R08, S05-S07, S12) read as BST; S01 and Elexon data UTC; S03 offsets from T = 16:52:34 ± 0.5 s with T read as BST; R01's +01:00 offsets as BST. Prose times without an offset are read as BST unless marked Z/UTC; an explicitly labelled UTC time is the same instant. MVP: the datum uncertainty is required for each of D2.2–D2.4 but satisfied once anywhere, D2.5 requires both clock bases, and a Hornsea/ST1C order finer than the datum caps at 0.5. SR/FI T02.04 keep the order cap but drop the clock-basis elements (intended divergence). MVP bundle 1.1.0 keeps S01's wrong clock rationale ('UTC is inferred') as a recorded erratum; the SR/FI bundles are corrected.
- **Alternatives.** Treat unlabelled or UTC-looking times as ambiguous (to a human). Credit Little Barford offsets only if T's clock is unknown. Assess the datum once (D2.5) or with each derived time. Require (or drop) clock bases consistently in MVP and SR/FI. Correct MVP S01 (new bundle, rebind, regrade).
- **Impact.** Every live run derives BST times, so the readings change grades only if rejected. Dropping MVP's clock-basis requirement: haiku45-001 D2.5 0.5 → 1. Datum 'with each time': haiku45-001 D2.2–D2.4 each 1 → 0.5. Correcting MVP S01 invalidates decisions bound to bundle 1.1.0 for the four panel runs.
- **Evidence.** ESO PDF p3 (printed 4) '4.52pm'; APP PDF p45 'Time T = 16:52:34 +/- 0.5seconds' and the T-datum caveat; APP PDF p41 local and UTC forms; R01 L32-L35; S01 L6; S03 L6-L9.

(a) Clock readings: R03/S05-S07/S12/R08 BST, S01 and Elexon UTC, S03 T as BST, R01 BST; labelled UTC = same instant — Decision: [ ] accept  [ ] change to: ____  
(b) MVP datum uncertainty required on each of D2.2–D2.4, satisfied once anywhere — Decision: [ ] accept  [ ] change to: ____  
(c) Clock bases required in MVP D2.5 but not in SR/FI T02.04 — Decision: [ ] accept  [ ] change to: ____  
(d) Hornsea/ST1C order finer than the datum caps at 0.5 (all tasks) — Decision: [ ] accept  [ ] change to: ____  
(e) MVP bundle 1.1.0 S01 erratum kept frozen — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-04"></a>

### XT-04

**R01 frequency landmarks: definitions, tolerances, evidence support** · applies to MVP, SR, FI · members (7, 70 min of item time): [MVP-A3](#mvp-a3), [MVP-B7](#mvp-b7), [MVP-B8](#mvp-b8), [MVP-B17b](#mvp-b17b), [MVP-B18](#mvp-b18), [SR-B6](#sr-b6), [SR-B18](#sr-b18)  

- **Question.** Are the R01 landmark definitions and tolerances right in every task (D3.1–D3.3 = T03.01–T03.03)?
- **Builder choice.** Values come from the evidence pack, not report prose: first minimum = lowest 1-s sample in 16:52:45–16:53:10 BST (49.083 Hz at 16:52:59); event minimum 48.787 Hz at 16:53:49; recovery = first sample at or above 50 Hz after the minimum (50.001 Hz at 16:57:16). Tolerance ±0.002 Hz and ±1 sample, so '50.0 Hz at 16:57:16' passes. ESO's 49.1 Hz [16:52:58] is context; as prose it goes to a human with proposal 0. SR/FI T03.04 caps rounded prose presented as the R01 value at 0.5. Evidence support 1 needs an R01 time/row citation covering the landmark, R01 obtained, and R01 analysed (run_python; in SR/FI also query_frequency).
- **Alternatives.** Literal first local minimum (49.126 Hz at 16:52:52) or accept either. ±0.005 Hz, or a 0.5 band to ±0.01 Hz. Key ESO's prose values. Require 50.001 Hz. Drop the run_python condition.
- **Impact.** Literal first-minimum rule: opus55-002, opus55-003 and sonnet55-001 D3.1 automatic 1 → automatic 0 (SR T03.01 likewise for runs reporting 49.083 Hz). Requiring 50.001 Hz: D3.3 falls on four of five MVP runs. ±0.005 Hz changes no live grade.
- **Evidence.** R01 time:16:52:45–16:53:10 BST, row:780, row:830, row:1037; ESO PDF p12 (printed 13) '16:52:58 Frequency drop is arrested at 49.1Hz'; ESO PDF p13 (printed 14) '16:57:15 Frequency returns to 50Hz'; E3C-I PDF p11 48.792Hz.

(a) First minimum = lowest sample in 16:52:45–16:53:10 BST — Decision: [ ] accept  [ ] change to: ____  
(b) ±0.002 Hz and ±1 sample; '50.0 Hz' accepted for 50.001 Hz — Decision: [ ] accept  [ ] change to: ____  
(c) R01 evidence support needs the landmark citation, R01 obtained and analysed — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-05"></a>

### XT-05

**Below-49-Hz duration, convention and method statements** · applies to MVP, SR, FI · members (7, 85 min of item time): [MVP-B9](#mvp-b9), [MVP-B14](#mvp-b14), [MVP-B17c](#mvp-b17c), [MVP-B26](#mvp-b26), [MVP-B28b](#mvp-b28b), [SR-D-T04.01](#sr-d-t04.01), [SR-D-T04.03](#sr-d-t04.03)  

- **Question.** Is 33 s with full credit within 1 s (half within 3 s) right, and what must a submission say about its method, and where may it say it?
- **Builder choice.** Key value 33 s strictly below 49 Hz (zero-order hold); 34 s (at or below), about 33.96 s (interpolation) and 32 s (first to last sample) also earn full credit because the brief prescribes no convention (decision 10). D3.5 / T04.03 full credit needs all three of: the convention, the 1-s sampling, and that sub-second crossings cannot be resolved (two of three = 0.5); a sub-second crossing claimed from 1-s data caps at 0.5. Method elements read the statement, derivation, quantity.basis and report sentences. A stated convention that does not reproduce the reported duration is a note only. Prose durations are credited automatically only with listed duration wording.
- **Alternatives.** Full credit only when the value matches the submission's own stated convention; full within 0.5 s; prescribe the convention in the brief. Convention plus sampling enough; any single element 0.5. Read the statement only. Cap D3.5 on a convention mismatch. Widen the duration-wording list.
- **Impact.** Any one element = 0.5: live run 001 D3.5 0 → 0.5. Statement-only reading: opus55-002 and haiku45-001 D3.5 1 → 0.5. Capping the mismatch: haiku45-001 D3.5 1 → 0.5. SR: sr80k-haiku45-001 T04.03 pre-screen 0.5 vs judge 1 (its convention wording is not recognised).
- **Evidence.** R01 rows:821-856 (16:53:40 = 49.000 Hz), R01 L22-L23 and L28-L29; ORR PDF p4 'approximately 33 seconds'; APP PDF p48 '16 seconds' (rail, conflicting account); DECISIONS 10.

(a) 33 s; full within 1 s, half within 3 s; other conventions accepted — Decision: [ ] accept  [ ] change to: ____  
(b) Method needs convention + sampling + sub-second limit (two of three = 0.5) — Decision: [ ] accept  [ ] change to: ____  
(c) Method may be stated in derivation, quantity.basis or report text — Decision: [ ] accept  [ ] change to: ____  
(d) Convention mismatch is a note only; duration-wording list as is — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-06"></a>

### XT-06

**Values the grader cannot settle: prose, report-only and unitless** · applies to MVP, SR, FI · members (6, 90 min of item time): [MVP-B17a](#mvp-b17a), [MVP-DEC27](#mvp-dec27), [MVP-B28a](#mvp-b28a), [SR-D-T03](#sr-d-t03), [SR-B16](#sr-b16), [SR-B17](#sr-b17)  

- **Question.** When may the grader decide a value automatically, and when must a human decide?
- **Builder choice.** An automatic 0 only for a genuine omission, or for an in-window structured quantity out of tolerance with nothing else in its finding within tolerance. Decision 27's open choice: that 0 stands (with a note) even when a correct value appears elsewhere. Prose, rounded and unitless values, and values stated only in the report text, are listed for a human, never credited or failed automatically (exceptions: T12.02's report-text exceedance and the method statements). A Little Barford clock time given only in the report: note, proposal stays 0.5.
- **Alternatives.** Send decision-27 cases to a human, or credit the best candidate anywhere. Credit report-only content (0.5 or full). Credit unitless figures when context names the quantity. Auto-fail rounded prose.
- **Impact.** Crediting report text: opus55-002 D2.4 and D2.5 0.5 → 1; sr80k-haiku45-001 T12.01a 0 → 1; sr30k-haiku45-001 T12.05 0 → 1. Today T03.01 waits for a human (proposal 0) on both SR haiku runs. No live run is a decision-27 case.
- **Evidence.** DECISIONS 18, 27; conventions.unit_note in the MVP and SR keys; ESO PDF p13 (printed 14) '16:53:49.398 Frequency breaches 48.8Hz trigger level'.

(a) Automatic 0 rule, including decision 27's open choice (wrong structured value stays 0) — Decision: [ ] accept  [ ] change to: ____  
(b) Report-only values listed for a human, never credited automatically — Decision: [ ] accept  [ ] change to: ____  
(c) Unitless figures listed for a human — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-07"></a>

### XT-07

**Status labels: Little Barford mechanisms, unresolved root causes, figures** · applies to MVP, SR, FI · members (6, 80 min of item time): [MVP-B19](#mvp-b19), [MVP-B23](#mvp-b23), [SR-B9](#sr-b9), [SR-D-T07.01](#sr-d-t07.01), [SR-D-T07.05](#sr-d-t07.05), [FI-B20](#fi-b20)  

- **Question.** How should the agent's status labels decide credit for established trip mechanisms and for the unresolved root causes?
- **Builder choice.** Mechanisms (D4.1–D4.3, T07.01–T07.03) count in a finding labelled unknown when one sentence states them without hedging; a hypothesis label never counts. The root causes (D4.4; T07.04 and again T17.01) earn full credit only when both open causes sit in findings labelled unknown, or hypothesis with not-established wording; both open in wording under a factual status = 0.5. T07.01 does not require the word 'three'. T07.05: full needs an explanation labelled hypothesis or attributed as a view; no explanation at all = 0.5. FI 0.1.1 extends the mechanism rule to figures: a figure counts in a finding labelled unknown when its own clause is unhedged, never in a hypothesis finding (FI-B20); T09.03 counts figures under any status (SR-B24).
- **Alternatives.** Credit not-established wording under any status. Assess the root cause once (drop the T17.01 duplicate). Require a factual status for mechanisms (the 0.3.0 rule). Require 'three' sensors. Score T07.05 silence 1 or 0.
- **Impact.** Wording-only rule: sonnet55-001 and haiku45-001 D4.4 0.5 → 1, and SR runs with open causes under a factual status rise on both T07.04 and T17.01 (see SR-B9). Reverting the mechanism rule: opus55-002 D4.2 1 → 0 and D4.3 1 → 0.5; sonnet55-001 D4.2 1 → 0. Requiring 'three': sr80k-opus55-001 T07.01 1 → 0.5. FI-B20 moved the FI panel run's T08.02 from 0.5 to 1 and T08.03 from 0 to 1 (F11, labelled unknown).
- **Evidence.** OFG PDF p31 'We have established ... three independent speed sensors' and 'has not been established' (twice); APP PDF p46 'For reasons presently unknown'; S04 L46-L66; S03 L42-L50.

(a) Mechanisms count in unknown findings; never in hypothesis findings — Decision: [ ] accept  [ ] change to: ____  
(b) Root causes need the agent's own unknown / hypothesis + not-established labels — Decision: [ ] accept  [ ] change to: ____  
(c) SR/FI assess the root causes twice (T07.04 and T17.01) — Decision: [ ] accept  [ ] change to: ____  
(d) T07.01 without 'three'; T07.05 silence = 0.5 — Decision: [ ] accept  [ ] change to: ____  
(e) FI: a figure counts in an unknown-labelled finding when its own clause is unhedged (FI-B20) — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-08"></a>

### XT-08

**Severe flag SF1: what counts as an asserted Little Barford root cause** · applies to MVP, SR, FI · members (7, 105 min of item time): [MVP-C1](#mvp-c1), [MVP-C2](#mvp-c2), [MVP-C3](#mvp-c3), [MVP-C5](#mvp-c5), [SR-E1](#sr-e1), [SR-X3](#sr-x3), [FI-E1](#fi-e1)  

- **Question.** Is one SF1 definition right for all three keys, and should MVP be aligned with SR/FI on the ESO-attributed bypass-valve wording?
- **Builder choice.** SF1 = a factual finding or report sentence asserting an underlying cause of the speed-signal discrepancy or the pressure excursions (faulty sensor, failed bypass valve, UPS changeover, the transmission fault as established cause). Ofgem's preliminary view and RWE's UPS explanation count only as hypotheses. A hedge or 'unknown' anywhere in the sentence excuses an assertion (sentence-level; known false negative). Divergences: MVP fires on 'bypass valve' even when attributed to ESO's executive summary; SR/FI excuse that attribution (decision 47). SR T07.04's judge-visible negative examples still call the valve failure 'not in the evidence', although S12 F7 reproduces ESO's wording. FI adds summary-location effects (T20.03, T20.06).
- **Alternatives.** Scope the hedge excuse to the asserting clause. Align MVP with SR/FI on attributed valve wording. Treat Ofgem's attributed view as a reported account. Narrow SF1 to explicit 'the root cause was' assertions.
- **Impact.** Under the installed keys no SF1 is suspected on any of the 13 graded runs. Under FI key 0.1.0 SF1 was falsely suspected on the FI panel run ('allowed to reconnect before the root cause was found'; 'the root causes are unestablished') and bounded six criteria at 0 until key 0.1.1 (FI-E1). Synthetic probes: MVP fires on an ESO-attributed restatement; a trailing 'although ... unknown' suppresses a real assertion. Rewording SR T07.04's examples changes judge-visible text, so judged runs need new (paid) judge calls.
- **Evidence.** ESO PDF p4 (printed 5) 'following the failure of a bypass valve to operate correctly'; OFG PDF p31 preliminary view and 'has not been established'; APP PDF p45 UPS hypothesis; S12 L148-L152; S04 L39-L66.
- **Compiler's note.** Installed FI key 0.1.1 (decisions 77–80; FI checklist E1): FI's SF1 now scopes the negation family to the trigger's own clause, so sub-decision (c) already differs in FI.

(a) SF1 definition as stated, same in all keys — Decision: [ ] accept  [ ] change to: ____  
(b) ESO-attributed bypass-valve wording excused in all keys (MVP change) — Decision: [ ] accept  [ ] change to: ____  
(c) Negation excuse stays sentence-level in MVP and SR (known limit) while FI 0.1.1 scopes it to the trigger's clause — Decision: [ ] accept  [ ] change to: ____  
(d) SR T07.04 negative-example rationale left as is — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-09"></a>

### XT-09

**Severe flags SF2 and SF3: definitions** · applies to MVP, SR, FI · members (6, 80 min of item time): [MVP-C4](#mvp-c4), [SR-E2](#sr-e2), [SR-E3](#sr-e3), [FI-E2](#fi-e2), [FI-E3](#fi-e3), [FI-A4](#fi-a4)  

- **Question.** Are the invented-record (SF2) and enforcement-outcome (SF3) definitions right, and should SF3 use FI's assertion-shaped triggers everywhere?
- **Builder choice.** SF2: an evidence ID outside the bundle, or a record-shaped ID no tool returned; labelled document lines ('R03-C2', 'S08-O02') are not records. SF3: MVP and SR fire on pound amounts, 'fined', 'penalty', 'redress', 'settlement' and bare 'enforcement action/outcome/decision/notice' (SR exempts price contexts). FI uses assertion-shaped triggers and excuses negated, conditional and recommended enforcement (decision 71). Ofgem's January 2020 settlements and its section 4 are excluded from the FI evidence (decisions 50, 57); clause recall is never scored.
- **Alternatives.** SF2 only when the ID is used as support. Assertion-shaped SF3 in all keys. Include the settlements as evidence and score T14 on them.
- **Impact.** No SF2 or SF3 on any graded run. MVP/SR SF3 still fire on 'Ofgem has not yet announced any enforcement action' and 'Ofgem should decide on any enforcement action'.
- **Evidence.** ORR PDF p11 'could warrant an enforcement action'; handoff spec ('Remove future settlement amounts from T14'); keys' severe_flags SF2/SF3 examples and non-examples; DECISIONS 50, 57, 71.

(a) SF2 definition as stated — Decision: [ ] accept  [ ] change to: ____  
(b) SF3: assertion-shaped triggers in all keys (MVP/SR change) — Decision: [ ] accept  [ ] change to: ____  
(c) Settlements excluded from evidence; clause recall never scored — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-10"></a>

### XT-10

**Severe flags: effects and who confirms** · applies to MVP, SR, FI · members (3, 35 min of item time): [MVP-C6](#mvp-c6), [SR-E4](#sr-e4), [FI-B8](#fi-b8)  

- **Question.** Only humans confirm a flag; is the scope of what a confirmed flag zeroes right?
- **Builder choice.** Suspected flags are suggestions; a suspected SF1 bounds judge proposals at 0. Confirmed SF1 zeroes D4.4 (MVP); T07.04, T07.05, T17.01 (SR); those plus T14.02, and T20.03/T20.06 when the assertion is in the executive summary (FI). SF2/SF3 make their findings unsupported; FI's SF3 also zeroes T14.04 and T14.05. No run-level pass/fail.
- **Alternatives.** Handoff: 'zeroes the relevant task and prevents run-level pass'. MVP SF1 also zeroes D4.2/D4.3 (listed in applies_to). Cap instead of zero. Zero T20.03/T20.06 for an SF1 anywhere.
- **Impact.** Under the installed keys no flag is suspected or confirmed on any graded run. Under FI key 0.1.0 a false suspected SF1 on the FI panel run bounded the judge at 0 on six criteria (T07.04, T07.05, T14.02, T17.01, T20.03, T20.06; decision 77): until a reviewer rejects a flag, the suspected-flag bound moves values whenever the heuristic misfires.
- **Evidence.** Keys' severe_flags[].effect and applies_to; handoff 'Scoring contract'; DECISIONS 71.

(a) Only a human confirms a flag — Decision: [ ] accept  [ ] change to: ____  
(b) Effect scope as listed per key — Decision: [ ] accept  [ ] change to: ____  
(c) A suspected SF1 bounds judge proposals for its criteria at 0 until a reviewer rejects it (SR, FI) — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-11"></a>

### XT-11

**Hornsea mechanism: elements and attribution** · applies to MVP, SR, FI · members (4, 60 min of item time): [MVP-B12](#mvp-b12), [MVP-D4](#mvp-d4), [SR-D-T06.01](#sr-d-t06.01), [SR-B19](#sr-b19)  

- **Question.** Which elements make the Hornsea mechanism complete, and who is its source?
- **Builder choice.** MVP D4.1 full needs resonance + overcurrent-protection de-load + weak internal network (any two = 0.5). SR/FI T06.01 full needs the controller reaction or instability + the protective (overcurrent) de-load; the weak network moved to T06.03/T16.03 (intended divergence). The resonance is Ørsted's account, restated by ESO; crediting Ofgem with it is a misattribution (T06.03). MVP D4.1's OFG PDF p29 passage has not had the same check.
- **Alternatives.** MVP: resonance + overcurrent full (weak network optional), or any two. SR/FI: accept protective de-load wording without 'overcurrent'. Accept Ofgem as a supporting account of the resonance.
- **Impact.** MVP 'any two': opus55-002, haiku45-001 and live run 001 D4.1 0.5 → 1; 'resonance + overcurrent': haiku45-001 only. SR: sr80k-haiku45-001 T06.01 pre-screen 0.5 vs judge 1 ('inappropriate protection actions').
- **Evidence.** APP PDF p43 resonance; APP PDF p41 overcurrent protection; ESO PDF p20 (printed 21) weak network and DRC cleared; OFG PDF p29 'reacted incorrectly'; S01 L54-L88.

(a) MVP D4.1 needs all three elements — Decision: [ ] accept  [ ] change to: ____  
(b) SR/FI T06.01 needs controller reaction/instability + overcurrent de-load — Decision: [ ] accept  [ ] change to: ____  
(c) Resonance credited to Ørsted (restated by ESO), not Ofgem — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-12"></a>

### XT-12

**Other lightning trips that day: required or not** · applies to MVP, SR, FI · members (4, 40 min of item time): [MVP-B10](#mvp-b10), [MVP-B25](#mvp-b25), [MVP-X1](#mvp-x1), [SR-D-T16.01](#sr-d-t16.01)  

- **Question.** Must a submission name and rule out the other lightning trips (Blyth-Eccles-Stella West, Harker-Stella West)?
- **Builder choice.** MVP D1.N (negative polarity): 1 when the initiator is named and no other trip is presented as initiating; ruling out is good practice, not required; its primary spans are only the other-trip records. SR/FI T16.01 (positive polarity, intended divergence): the others must be named and ruled out by timing and impact; omission = 0. R03 1.1.0 leaves the two Blyth times unreconciled for the agent.
- **Alternatives.** Require ruling out in MVP too, or drop D1.N. Give omission 0.5 in SR/FI. Add the initiating-fault lines to D1.N's primary spans.
- **Impact.** Ruling out required in MVP: opus55-002 and haiku45-001 D1.N 1 → 0.5. MVP polarity in SR: sr80k-opus55-001, sr80k-haiku45-001 and sr30k-haiku45-001 T16.01 0 → 1. D1.N evidence is pending on opus55-002 and haiku45-001 because their citations miss the keyed spans.
- **Evidence.** ESO PDF p15 (printed 16) 16:50:44 Blyth and 14:23 Harker; APP PDF p85 16:43:25 Blyth; R03 L67-L77.

(a) MVP D1.N: ruling out not required — Decision: [ ] accept  [ ] change to: ____  
(b) SR/FI T16.01: ruling out required, omission 0 — Decision: [ ] accept  [ ] change to: ____  
(c) D1.N keyed spans: other-trip records only — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-13"></a>

### XT-13

**Initiating fault and protection-assessment wording** · applies to MVP, SR, FI · members (4, 25 min of item time): [MVP-B11](#mvp-b11), [MVP-B27](#mvp-b27), [SR-D-T01.01](#sr-d-t01.01), [SR-D-T16.02](#sr-d-t16.02)  

- **Question.** Are the initiating-fault partial-credit rules and the accepted protection-assessment wording right?
- **Builder choice.** D1.1 / T01.01 full when lightning is attributed to 'the fault' in one finding with the circuit in another; lightning merely near the circuit = 0.5. MVP D1.1 also needs the fault type; SR moves it to T01.03a (T01.01's element note still says otherwise; see SR-X4). Protection assessment (D1.4, T16.02): 'as designed', 'as expected', 'correctly', 'in line with the design', 'in compliance', 'within the 80 ms', 'performed as required', 'met the requirement'.
- **Alternatives.** Lightning, circuit and fault type in one finding. Require the cause to be attributed (NGET/ESO). Accept only the sources' own words for protection.
- **Impact.** One-finding rule: opus55-002 and sonnet55-001 D1.1 1 → 0.5. The wording list changes no live grade.
- **Evidence.** ESO PDF p12 (printed 13) fault and 'consistent with a lightning strike'; APP PDF p25; ESO PDF p15-p16; APP PDF p17 'operated as designed'.

(a) Lightning attribution across findings gives full credit — Decision: [ ] accept  [ ] change to: ____  
(b) Protection-assessment wording list as stated — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-14"></a>

### XT-14

**Unit losses, entity binding and the GT1B manual trip** · applies to MVP, SR, FI · members (5, 45 min of item time): [MVP-B13](#mvp-b13), [MVP-B15](#mvp-b15), [MVP-B16](#mvp-b16), [SR-D-T02.02-03](#sr-d-t02.02-03), [SR-D-T07.02-03](#sr-d-t07.02-03)  

- **Question.** Are the unit-loss rules, clause-based binding and the 'GT1B automatic' cap right?
- **Builder choice.** Hornsea loss needs loss wording; 799 MW and 800 MW count only with the 62 MW residual (10%/25% MW tolerance). A value counts for the unit its clause describes; swapped GT1A/GT1B values = 0.5. Calling GT1B automatic caps D4.3 and D2.4 (MVP) and T07.03 (SR/FI) at 0.5. SR T02.03b needs the MW only (MVP D2.4 also needed the derived time).
- **Alternatives.** Accept only 737 MW or 799 → 62. Score swapped values 0. Cap only the mechanism criterion. Require GT1B's time in SR/FI.
- **Impact.** No live run swaps values or calls GT1B automatic; haiku45-001 D2.1 is credited at 738 MW derived from capability.
- **Evidence.** ESO PDF p18 (printed 19) 799 → 62 MW; ESO PDF p13 (printed 14) unit losses; APP PDF p45 'GT1B Manual shutdown command'; S03 L34-L36.

(a) Loss wording; 799/800 MW only with 62 MW — Decision: [ ] accept  [ ] change to: ____  
(b) Clause binding; swapped GT1A/GT1B = 0.5 — Decision: [ ] accept  [ ] change to: ____  
(c) 'GT1B automatic' caps D2.4 and D4.3 (MVP) and T07.03 (SR/FI) — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-15"></a>

### XT-15

**Evidence support: scales, citation width, context spans, retrieval** · applies to MVP, SR, FI · members (5, 55 min of item time): [MVP-A5](#mvp-a5), [MVP-B20](#mvp-b20), [SR-A5](#sr-a5), [SR-X2](#sr-x2), [SR-F3](#sr-f3)  

- **Question.** Are the evidence-support scale and the routing of broad or off-span citations to a human right?
- **Builder choice.** Content 1/0.5/0; evidence support 1/0, uncited = 0. A proposal of 1 needs a specific citation of a primary keyed span (at most 3x its length, floor 8 lines or samples, under half the document). Context spans (clock headers, dataset descriptions), broad citations and citations outside the keyed spans go to a human, never failed. SR/FI check retrieval across every tool route; a record counts as obtained when the document it restates was retrieved.
- **Alternatives.** 0.5 for context-span or broad citations. A wider multiplier (5x, 10x) or a 20-line floor. Fail citations outside the keyed spans. Make clock headers primary where the clock basis is assessed. Count only request_document retrieval.
- **Impact.** Mostly reviewer workload: SR has 43 criterion rows routed for over-wide citations and 17 for off-span citations; MVP opus55-002 D2.2/D2.4 and the D1.N/D1.2 cases (XT-12) wait for a human.
- **Evidence.** Keys' conventions.content_scale, evidence_support_scale, visible_evidence_roles and alternative_evidence; DECISIONS 8.

(a) Scales 1/0.5/0 and 1/0 — Decision: [ ] accept  [ ] change to: ____  
(b) Width rule: 3x span, floor 8, under half the document; otherwise to a human — Decision: [ ] accept  [ ] change to: ____  
(c) Context-span roles as keyed — Decision: [ ] accept  [ ] change to: ____  
(d) Retrieval checked across all routes — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-16"></a>

### XT-16

**Never-scored review flags (labelling, inferential language)** · applies to MVP, SR, FI · members (4, 40 min of item time): [MVP-B24](#mvp-b24), [MVP-X2](#mvp-x2), [SR-B27](#sr-b27), [FI-B21](#fi-b21)  

- **Question.** Are the labelling and inferential-language flags defined well enough to stay as unscored reviewer prompts?
- **Builder choice.** Both are proposals, never scored. SR (decision 48) exempts measurement caveats, reported hypotheses, a named third party's 'suggests/indicates' and passive 'was attributed to'; the frozen MVP grader still flags measurement caveats and keeps 'attributed to'. FI 0.1.1 also spares 'as soon as possible', 'where possible' and 'may not restore ... without ESO instruction' (FI-B21).
- **Alternatives.** Align MVP's exemptions with SR. Drop 'attributed to'. Drop the inferential flag. Score the flags.
- **Impact.** No value changes. Known false flags: MVP sonnet55-001 F18, haiku45-001 F12 (measurement caveats) and run 001 F08 (correct attribution). FI: labelling flags pilot 2 → 0 and panel run 1 → 0 under key 0.1.1.
- **Evidence.** Keys' conventions.status_labelling, inferential_patterns, inferential_attribution; DECISIONS 44, 48.

(a) Flags stay unscored — Decision: [ ] accept  [ ] change to: ____  
(b) MVP keeps its 0.3.1 flag rules (no alignment) — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-17"></a>

### XT-17

**Reporting: no total, finality, decisions binding** · applies to MVP, SR, FI · members (6, 40 min of item time): [MVP-A6](#mvp-a6), [SR-A6](#sr-a6), [SR-F1](#sr-f1), [FI-A6](#fi-a6), [FI-F2](#fi-f2), [FI-F3](#fi-f3)  

- **Question.** Should measures stay separate with no total, threshold or ranking, and are the finality and binding rules right?
- **Builder choice.** Content coverage, evidence support and assertion quality are reported per criterion and dimension; no total, threshold or ranking (the Karotte score is completion only). Split fields have equal subweights for reporting only. A grade is final only when the key is reviewed, every criterion and assertion has a human value or accept_judge sign-off, every suspected flag is adjudicated, explanation-quality notes exist, the decisions file is not a builder fixture, the trace exists and the bundle matches. Decisions files bind to the submission, key version and sha256, and bundle.
- **Alternatives.** The handoff contract (weighted 100-point total, pass at 70). Finality per criterion. Decisions bound per criterion so unchanged criteria survive a key bump.
- **Impact.** No value changes; all 13 graded runs stay provisional until these hold. Per-criterion binding would save re-adjudication after small key changes.
- **Evidence.** Keys' conventions.no_pass_threshold; handoff 'Scoring contract'; DECISIONS 7, 32, 76.

(a) No total, threshold or ranking — Decision: [ ] accept  [ ] change to: ____  
(b) Finality conditions as stated — Decision: [ ] accept  [ ] change to: ____  
(c) Decisions bound to the whole key (sha256) — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-18"></a>

### XT-18

**The LLM judge: modes, merge rules, rebinding, scoping** · applies to SR, FI · members (6, 110 min of item time): [SR-A8](#sr-a8), [SR-B20](#sr-b20), [SR-F2](#sr-f2), [SR-X1](#sr-x1), [FI-B12](#fi-b12), [FI-F1](#fi-f1)  

- **Question.** Is the judge's role right: which criteria it proposes for, what bounds it, and how its requests are built?
- **Builder choice.** Modes: SR 4 auto_numeric / 32 auto_assisted_human / 24 judge; FI 4 / 49 / 53 (T13, T18, T19, T20 all judge). The judge proposes only for judge criteria, bounded by accounting caps and suspected severe flags; contradiction rules are flags for the reviewer, hidden from the judge; accept_judge cannot sign off a capped proposal; a numeric conflict goes to a human. SR's 80k judge outputs (key 0.1.0) are re-bound to 0.1.1 in the tests without new calls (decision 45); the stored files are not. FI requests are scoped per topic (topic-scope/2 with an error screen); on the pilot, scoping hid findings that carried credited content (T13.04, T13.06).
- **Alternatives.** Let the judge's value stand for auto_assisted_human criteria where it reads prose. Cap judge values by contradiction rules. Re-run the judge (paid) under the current key. Whole-submission or all-findings requests for T13 and T20.
- **Impact.** Judge/pre-screen disagreements remaining: SR opus 1, haiku 2 (decision 43); FI key 0.1.1: pilot 6 and panel run 2 of 53 (key 0.1.0: 13 and 10; decisions 76, 79). Whole-submission FI requests cost about $1.13 more per run.
- **Evidence.** Keys' judge.criteria and assessment_mode; sr_grading.merge_judge_proposals; DECISIONS 34, 35, 39, 43, 45, 52, 72, 73, 76.
- **Compiler's note.** Checked while compiling: the stored judge outputs are bound to the key they were produced with (SR 0.1.0 for the sr80k runs, FI 0.1.0 for the pilot and the panel run); `sr_grading`/`fi_grading grade --judge` rejects them under the installed keys (JudgeOutputError: binding mismatch). The decision-45 re-binding exists only in tests (`rebound()` in tests/test_sr_grading_live_runs.py); see section 3.4.

(a) Mode split as keyed — Decision: [ ] accept  [ ] change to: ____  
(b) Merge rules (judge proposes for judge criteria only; caps; human sign-off) — Decision: [ ] accept  [ ] change to: ____  
(c) SR rebinding of 0.1.0 judge outputs accepted — Decision: [ ] accept  [ ] change to: ____  
(d) FI per-topic scoping kept — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-19"></a>

### XT-19

**Expected values: evidence pack first, disagreeing sources kept apart, nothing beyond the bundle** · applies to MVP, SR, FI · members (5, 255 min of item time): [MVP-A2](#mvp-a2), [SR-A2](#sr-a2), [SR-A3](#sr-a3), [FI-A2](#fi-a2), [FI-A3](#fi-a3)  

- **Question.** Do the keys rest only on what each bundle supports, with each disputed figure kept on its own source?
- **Builder choice.** Expected values are tied to verbatim report passages (74 MVP, 317 SR, 581 FI passages, each test-checked on its PDF page) and to visible-evidence locators. Where sources disagree each figure stays with its source (accounting bases, rail counts, communications times). No criterion needs evidence a bundle lacks: SR deferred T04.02; FI serves missing records as fixed not-held returns.
- **Alternatives.** Pick one authoritative source per figure. Remove or downgrade criteria that need an inference the records do not state.
- **Impact.** Underlies every proposal; a changed expected value means a new key version and a regrade of every run of that task.
- **Evidence.** Keys' report_passages and visible_evidence; tests/test_grading_key.py, test_sr_grading_key.py, test_fi_grading_key.py; DECISIONS 29.

(a) Evidence-pack values; disagreeing sources kept apart — Decision: [ ] accept  [ ] change to: ____  
(b) Nothing required beyond the bundle — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-20"></a>

### XT-20

**Reconstructed records: leakage and realism** · applies to MVP, SR, FI · members (3, 150 min of item time): [MVP-A4](#mvp-a4), [MVP-X3](#mvp-x3), [SR-A4](#sr-a4)  

- **Question.** Do the reconstructed records hand the agent conclusions the key rewards, and are they realistic enough for grades to be final?
- **Builder choice.** Records keep the sources' own wording with no builder conclusions or cross-source comparisons (decisions 9, 30, 31, 55); every line is provenance-verified. No domain expert has reviewed their realism. FI adds three reconstructions (S08 rail fleet, S10 compliance process, S11 essential services) and new witness cards; no FI card asks about their realism, so include them here.
- **Alternatives.** Name a leak and edit the record: candidates are S04 B1–B3 (Ofgem's established / not-established wording side by side), R03 G1 ('operated as designed'), S06/S12 framing. Any edit is a new bundle version, a key rebind and a regrade.
- **Impact.** The most expensive change in the pack: a bundle edit invalidates every decisions file for that task. Realism review is the longest single reading task (MVP-X3 60 min, SR-A4 60 min).
- **Evidence.** R03 L4 and S01/S03 L4 status lines; private/provenance.json and system_response/provenance*.json; DECISIONS 5, 9, 30, 31, 55.

(a) No leak needs a bundle edit — Decision: [ ] accept  [ ] change to: ____  
(b) Reconstructions realistic enough (or list required edits) — Decision: [ ] accept  [ ] change to: ____  

<a id="xt-21"></a>

### XT-21

**Restoration: boundaries and distinctions (SR and FI)** · applies to SR, FI · members (6, 100 min of item time): [SR-A1](#sr-a1), [SR-B7](#sr-b7), [SR-B21](#sr-b21), [SR-B26](#sr-b26), [FI-B1](#fi-b1), [FI-B16](#fi-b16)  

- **Question.** Are the restoration times and the demand-versus-other-recovery distinction right, given that FI has diverged from SR's frozen key?
- **Builder choice.** Instructions began 16:58 BST, all issued by 17:16, demand restoration complete 17:37, each ±2 min (handoff); the first-DNO completion (17:34/17:36) is masked. T05.01b also reads statement times. T05.03: SR adapted it to 'other services' (no rail evidence); FI restores the handoff's 'later transport recovery' with the Victoria line's 17:35 resumption as context. FI T05.02 adds a 'restored by &lt;time>' route that SR's frozen key lacks. FI T05.03's expectation says demand vs later transport alone is full, but its pre-screen needs more.
- **Alternatives.** Treat ESO's earlier 17:00/17:19 account as an equal alternative. Read statement times for every time criterion. Align FI T05.03's pre-screen with its expectation. Port the 'by &lt;time>' route back to SR.
- **Impact.** T05.01b statement times moved 0 → 1 on sr80k-opus55-001, sr80k-haiku45-001 and sr30k-sonnet55-001. FI pilot T05.02 0 → 1 from the 'by' route; pilot T05.03 pre-screen 0.5 vs judge 1 under key 0.1.0, 1 and 1 under key 0.1.1 (`demand_vs_services`).
- **Evidence.** ESO PDF p13 '16:58 – 17:16' and '17:37'; ESO PDF p29 Table 7 and [17:34]; APP PDF p87 17:00/17:19; ESO PDF p27 Victoria line 17:35.
- **Compiler's note.** Installed FI key 0.1.1 (decisions 77–80; FI checklist B19): FI T05.03 gains `demand_vs_services`; FI T02.04's SOE offsets also read '&lt;n> s after datum T'.

(a) 16:58 / 17:16 / 17:37, ±2 min; first-DNO completion masked — Decision: [ ] accept  [ ] change to: ____  
(b) T05.01b reads statement times — Decision: [ ] accept  [ ] change to: ____  
(c) T05.03 as worded per task (SR 'other services', FI 'later transport') — Decision: [ ] accept  [ ] change to: ____  
(d) T05.02 'by &lt;time>' route in FI only — Decision: [ ] accept  [ ] change to: ____  

### 2.2 P1 items (110 items, 33 h 30 min)

P1: needed before any result is reported as more than provisional (values or rules that move live grades, severe flags, accounting bases).

#### MVP — `gb-2019-electrical-disturbance` (key 0.3.1) — P1, 31 items, 7 h 20 min

<a id="mvp-a2"></a>

##### MVP-A2

**P1** · 20 min · MVP (`gb-2019-electrical-disturbance`) · Checklist: A2 · Cross-task: [XT-19](#xt-19)  

- **Question.** Can R01, R03, S01, S03 and S04 alone support every expected value and requirement in the key?
- **Builder choice.** Every criterion has primary visible_evidence spans whose must_contain tokens a test checks. The tests pass: tests/test_grading_key.py plus test_grading_live_runs.py, 404 tests.
- **Alternatives.** Remove or downgrade any criterion whose fact needs an inference the records do not state. Candidates: D2.5's 'not aligned with the system operator's datum' (only S03 L6-L9), and D1.N's reliance on R03 E2.
- **Impact.** A criterion found unsupported would be removed or downgraded for all runs. No live run lacks evidence: all five retrieved R01, R03, S01, S03 and S04 (runs.json trace_info).
- **Evidence.** Key locators: S03 L6-L9 ('T = 16:52:34 +/- 0.5 s', 'further work is needed to align T'); R03 L73-L77; R01 row:780 / row:830 / row:1037 / rows:821-856. runs.json `trace_info.retrieved` for all five runs.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-a3"></a>

##### MVP-A3

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.1, D3.2, D3.3, D3.4 · Checklist: A3 · Cross-task: [XT-04](#xt-04)  

- **Question.** Where published accounts disagree with the frozen evidence, should the expected values follow the evidence pack rather than the report prose?
- **Builder choice.** The evidence pack is followed: R01 gives 49.083 Hz at 16:52:59, 48.787 Hz at 16:53:49, 50.001 Hz at 16:57:16 and 33 s. ESO's 49.1 Hz [16:52:58] is an 'expected' passage kept for context. E3C 48.792 Hz and Siemens' 16 s are 'conflicting_account'.
- **Alternatives.** Key the ESO prose values. Or accept the prose values as alternatives by widening the D3 value tolerance.
- **Impact.** If ESO's 49.1 Hz were keyed at ±0.002 Hz, D3.1 would drop from automatic 1 to 0 for opus55-002 F15, opus55-003 F13 and sonnet55-001 F14 (all 49.083 Hz @16:52:59). Under the current rules, a prose '49.1 Hz at 16:52:58' goes to a human with proposal 0 (synthetic probe).
- **Evidence.** ESO PDF p12 (printed 13): "16:52:58 Frequency drop is arrested at 49.1Hz due to the delivery of frequency response products". ESO PDF p14 (printed 15): "Frequency fall arrested at 49.1Hz [16:52:58]". E3C-I PDF p11: "when the system frequency fell to 48.792Hz, not all schemes were triggered". APP PDF p48: "dropped below 49Hz for 16 seconds". ORR PDF p4: "The frequency remained below 49.0Hz for approximately 33 seconds". R01 row:780 '2019-08-09T16:52:59+01:00,49.083', row:830, rows:821-856.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b1"></a>

##### MVP-B1

**P1** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D1.2, D1.4, D2.5 · Checklist: B1 · Cross-task: [XT-03](#xt-03)  

- **Question.** Should R03's unlabelled B3 lightning time and section C fault and protection times be read as BST (+01:00)?
- **Builder choice.** BST, because the ESO report dates the event at 4.52pm. R03 L7-L9 states this inference.
- **Alternatives.** Treat them as unlabelled and accept either reading. Or require the agent to state the inference.
- **Impact.** Sets the D1.2 and D1.4 expected times and the start of D2.5's initial group (16:52:33.490+01:00). All five runs give 16:52:33.490 and 16:52:53 BST, so live grades change only if the BST reading is rejected.
- **Evidence.** ESO PDF p3 (printed 4): "A lightning strike occurred on a transmission circuit (the Eaton Socon – Wymondley Main) at 4.52pm." ESO PDF p12 (printed 13): "16:52:33.490 A single (blue) Phase to Earth fault on Eaton Socon - Wymondley circuit". APP PDF p40 (Ørsted): "The lightning strike results in a phase to Earth short circuit at exactly 16:52:33:490". R03 L7-L9 (clock header), L25-L27, L36-L37, L49-L50.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b2"></a>

##### MVP-B2

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D2.2, D2.3, D2.4 · Checklist: B2 · Cross-task: [XT-03](#xt-03)  

- **Question.** Should the S03 SOE datum T = 16:52:34 ± 0.5 s be read as BST, with Little Barford clock times derived as T + the unit's SOE offsets?
- **Builder choice.** Yes. Expected ranges: ST1C T+0.253 to T+1.185 s (E3–E5); GT1A T+56.583 to T+57.620 s (E6–E7); GT1B T+83.897 to T+84.613 s (E8–E9). A test checks them against S03.
- **Alternatives.** Use the ESO timeline times (16:52:34, 16:53:31, 16:53:58), as key 0.2.0 did. Accept either. Or treat T's clock as unknown and credit offsets only.
- **Impact.** All five runs derive T + offset BST times (for example sonnet55-001 F10: '16:52:34 + 57.620 s = 16:53:31.620 BST'). Under ±2 s the ESO times also fit, so switching to them changes no live grade. Reading T as UTC would put every run's D2.2–D2.4 times an hour out.
- **Evidence.** APP PDF p45: "Time T = 16:52:34 +/- 0.5seconds"; "ST Generator Breaker Open feedback +1.185 Sec"; "GT1A Breaker Open feedback +57.620 Sec"; "GT1B Breaker Open feedback +84.613 Sec". ESO PDF p12 (printed 13): "16:52:34 Little Barford Steam Turbine trips 244MW instantaneously." S03 L6-L9 ('T = 16:52:34 +/- 0.5 s', 'read here as BST'); S03 L23-L29.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b3"></a>

##### MVP-B3

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D2.1, D2.2, D2.3, D2.4 · Checklist: B3 · Cross-task: [XT-02](#xt-02)  

- **Question.** Is ±2 s the right time tolerance for the generator trips (Hornsea de-load at 16:52:33.728–.835 BST, and the SOE-derived Little Barford ranges)?
- **Builder choice.** ±2 s. This is a builder choice: the handoff gives no rule for trips, only 1 s for the T01 event times.
- **Alternatives.** ±1 s (the handoff's event-time rule). ±0.5 s (the datum) for Little Barford. A tighter tolerance (for example ±0.2 s) for Hornsea's millisecond log.
- **Impact.** Every live run's D2.1–D2.4 time error is 0.0 s, so no live grade changes at ±1 s or ±0.5 s. ±2 s also accepts ESO's 1-s timeline times and an un-derived T (16:52:34 is 0.25 s from the ST1C range).
- **Evidence.** Key D2.1–D2.4 tolerances.time_basis: 'builder choice ... (review item)'; conventions.numeric_rules.generator_trip_time_s = 2. ESO PDF p12 (printed 13): "16:52:33.728 Hornsea started deloading" and "16:52:33.835 Hornsea stabilised at 62MW and injecting 21 MVAR". S01 L40-L43; S03 L23-L29.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b4"></a>

##### MVP-B4

**P1** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D1.3 · Checklist: B4 · Cross-task: [XT-02](#xt-02)  

- **Question.** Should D1.3 accept 70 ms and 74 ms only within ±1 ms, with Ofgem's 'under 75 ms' (or 'under 0.1 s') alone earning 0.5?
- **Builder choice.** ±1 ms. Full credit needs both ends plus 'within 80 ms'. 0.5 for one end or a generic clearance time. Both ends without the 80 ms requirement also earn 0.5.
- **Alternatives.** ±5 ms. Full credit for 'under 75 ms, within the 80 ms requirement' (Ofgem's own finding). Require the 80 ms requirement for any credit.
- **Impact.** All five runs state 70 ms and 74 ms with the 80 ms requirement (D1.3 proposal 1.0 on every run), so no live grade changes. A synthetic 'under 75 ms' finding is proposed 0.5.
- **Evidence.** ESO PDF p12 (printed 13): "16:52:33.560 70ms after fault, Wymondley end opens to clear the fault"; "16:52:33.564 74ms after fault, Eaton Socon end opens to clear the fault". APP PDF p26: "(i) 80ms at 400kV (400,000 volts)". APP PDF p17: "therefore clearing the fault within the 80ms required in the Grid Code". OFG PDF p28: "Evidence NGET has submitted to us shows its fault clearance times for the two circuit breakers were under 75ms". R03 L43-L48, L105-L107.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b5"></a>

##### MVP-B5

**P1** · 5 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D1.4 · Checklist: B5 · Cross-task: [XT-02](#xt-02)  

- **Question.** Is ±2 s around 16:52:53 BST the right tolerance for the delayed auto-reclose in D1.4?
- **Builder choice.** ±2 s ('about 20 s'; the source reports to the second). Full credit needs the reclose (a clock time, or '20 s') plus an assessment that the protection operated as designed or as required. Calling the reclose a second initiating fault zeroes the criterion.
- **Alternatives.** ±1 s. Give only 0.5 for 'about 20 s' without a clock time.
- **Impact.** All five runs give 16:52:53 and an as-designed assessment (D1.4 is 1.0 on every run), so no live grade changes.
- **Evidence.** ESO PDF p12 (printed 13): "16:52:53 Eaton Socon - Wymondley circuit energised on DAR". APP PDF p17: "The circuit was returned to service 20 seconds later with our automatic Delayed Auto-Reclose system". R03 L49-L50.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b6"></a>

##### MVP-B6

**P1** · 25 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D2.5 · Checklist: B6 · Cross-task: [XT-03](#xt-03)  

- **Question.** Are the D2.5 rules right? (a) group windows: initial 16:52:33.490–16:52:36.5, GT1A 16:53:25–16:53:40, GT1B 16:53:52–16:54:05 BST; (b) full credit only when both clock bases are stated (S01 in UTC with its BST equivalent; S03 as offsets from T or with ±0.5 s); (c) a 0.5 cap when the Hornsea/ST1C order is stated more finely than the datum allows.
- **Builder choice.** As stated. 'ST1C tripped about 1.4 s after Hornsea' is not capped. A millisecond or sub-second interval between the two units, without a datum caveat, is capped at 0.5.
- **Alternatives.** Drop the clock-basis requirement and assess clocks only in D2.1–D2.4. Require a single stated common clock instead. Drop the order cap, or extend it to any ordering claim.
- **Impact.** haiku45-001 D2.5 = 0.5 only because it never says the S01 log is in UTC (hornsea_clock_basis level 0), although it converted correctly (F16: 16:52:33.728–.835+01:00). Without the clock-basis requirement it would get 1.0. opus55-002's D2.5 0.5 comes from its GT1B time (MVP-B28a). No live run triggers the order cap; sonnet55-001 F20 itself says ordering below about 1 s is uncertain. A synthetic '0.52 s before' triggers the cap.
- **Evidence.** APP PDF p45: "RWE have confidence in the chronology of the events, further investigation work is required to determine an accurate “T” datum relative to datum used within NGESO report". OFG PDF p30: "Around a minute after the fault, one of the gas turbines which was generating 210MW tripped. Around 30 seconds after that, the". APP PDF p41 (Ørsted, both clocks): "(16:52:33:728 to 16:52:33:835)" and "began de-loading turbines at 15.52.33.728". S01 L6, S03 L6-L9, S03 L21-L29, S04 L27-L33.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b7"></a>

##### MVP-B7

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.1 · Checklist: B7 · Cross-task: [XT-04](#xt-04)  

- **Question.** Should D3.1's 'first post-fault minimum' be the lowest 1-s sample in 16:52:45–16:53:10 BST (49.083 Hz at 16:52:59) rather than the literal first local minimum (49.126 Hz at 16:52:52)?
- **Builder choice.** The lowest sample in the window, as in the handoff's extraction script.
- **Alternatives.** The literal first local minimum, 49.126 Hz @16:52:52 (neighbours 49.131 and 49.141). Accept either. Accept ESO's 49.1 Hz [16:52:58].
- **Impact.** opus55-002 F15, opus55-003 F13 and sonnet55-001 F14 report 49.083 Hz @16:52:59 (automatic 1). Under the literal definition they would become automatic 0 (a structured value in the window but out of tolerance). haiku45-001 scores 0 under any definition: a genuine omission. Live run 001 F15 ('about 49.08–49.27 Hz') stays with a human. A synthetic '49.126 Hz at 16:52:52' currently goes to a human with proposal 0.
- **Evidence.** R01 time:2019-08-09T16:52:45+01:00/2019-08-09T16:53:10+01:00 (16:52:52 49.126; 16:52:55 49.085; 16:52:59 49.083). ESO PDF p12 (printed 13): "16:52:58 Frequency drop is arrested at 49.1Hz due to the delivery of frequency response products". ESO PDF p14 (printed 15): "Frequency fall arrested at 49.1Hz [16:52:58]". The brief asks for 'each minimum'.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b8"></a>

##### MVP-B8

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.1, D3.2, D3.3 · Checklist: B8 · Cross-task: [XT-04](#xt-04)  

- **Question.** Are ±0.002 Hz and ±1 s the right D3.1–D3.3 tolerances, given that two-decimal rounding of the exact samples (49.08 Hz, 48.79 Hz) fails while '50 Hz at 16:57:15' passes?
- **Builder choice.** The handoff's numeric rule: ±0.002 Hz and ±1 sample. The checklist says '49.1 Hz fails D3.1'. In practice a prose 49.1 Hz goes to a human with proposal 0, and only a structured quantity fails automatically.
- **Alternatives.** ±0.005 Hz (accepts two-decimal rounding). Or keep ±0.002 Hz for full credit and add a 0.5 band up to ±0.01 Hz.
- **Impact.** No live grade changes: all credited D3 values are given to 3 decimals or as 50.0. Synthetic probe: a structured 48.79 Hz @16:53:49 gives D3.2 automatic 0 ('value off by 0.003'); 48.789 gives automatic 1; 48.8 gives 0. Live run 001's 49.08 lower bound is also 0.003 Hz off.
- **Evidence.** conventions.numeric_rules.frequency_extrema (value_hz_abs 0.002, time_s 1; source: handoff). R01 rows 1036-1038 (16:57:15 49.997; 16:57:16 50.001; 16:57:17 50.006). ESO PDF p13 (printed 14): "16:57:15 Frequency returns to 50Hz following over 1,000MW of response" and "16:53:49.398 Frequency breaches 48.8Hz trigger level resulting in LFDD."

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b9"></a>

##### MVP-B9

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.4 · Checklist: B9 · Cross-task: [XT-05](#xt-05)  

- **Question.** Is 33 s (strictly below 49 Hz, zero-order hold) the right D3.4 key value, with full credit within 1 s and half within 3 s?
- **Builder choice.** Yes. Within 1 s, at-or-below (34 s), linear interpolation (about 33.96 s) and first-to-last sample (32 s) all earn full credit. The brief deliberately prescribes no convention (decision 10).
- **Alternatives.** Give full credit only when the value matches the convention the submission itself states (linking D3.4 to D3.5). Full credit within 0.5 s, which separates 33 s from 34 s and 32 s. Prescribe the convention in the brief.
- **Impact.** All four panel runs report 33 s (opus55-002 F19, opus55-003 F16, sonnet55-001 F16, haiku45-001 F10) and get automatic 1. Live run 001 gives no duration and gets automatic 0. haiku45-001 states conventions that give 34 s and 32 s yet reports 33 s (MVP-B28b). A synthetic 36 s gets 0.5.
- **Evidence.** ORR PDF p4: "The frequency remained below 49.0Hz for approximately 33 seconds". ORR PDF p3: "drop from its nominal value of 50.0Hz to below 49.0Hz for approximately 33 seconds, falling to a low of 48.8Hz". APP PDF p48 (conflicting account, rail): "dropped below 49Hz for 16 seconds". R01 time:16:53:40–16:54:14 (49.0, 48.983 … 48.973, 49.001); rows:821-856. DECISIONS.md decision 10.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b10"></a>

##### MVP-B10

**P1** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D1.N · Checklist: B10 · Cross-task: [XT-12](#xt-12)  

- **Question.** Should D1.N give full credit whenever the Eaton Socon–Wymondley fault is named as the initiator and no other trip is presented as initiating, even if the other trips that day are never mentioned?
- **Builder choice.** 1 when the initiator is identified and no other trip is presented as initiating. 0.5 for ruling out the other trips without naming the initiator. 0 otherwise. Ruling out is good practice, not required.
- **Alternatives.** Require full credit to rule out explicitly Blyth–Eccles–Stella West (16:50:44 / 16:43:25) and Harker–Stella West (14:23). Or drop D1.N as redundant with D1.1.
- **Impact.** opus55-002 and haiku45-001 never mention another trip (no matches for Blyth, Harker, Stella, 16:50:44, 16:43:25 or 14:23). They get 1.0 now and would fall to 0.5 if ruling out were required. opus55-003 (F26), sonnet55-001 (F21) and live run 001 (F23) rule the trips out. See MVP-X1 for their D1.N evidence routing.
- **Evidence.** ESO PDF p15 (printed 16): "At 16:50:44hrs, a lightning struck the Blyth – Eccles – Stella West 400kV circuit near Longframlington, Northumberland. The circuit tripped and closed with no power losses associated." and "At 14:23hrs, the Harker – Stella West 275kV circuit was also tripped and automatically returned to service." APP PDF p85: "At 16:43:25, the Blyth – Eccles – Stella West 1 400kV circuit tripped and was likewise returned to service via DAR at 16:43:54." R03 L67-L72, L73-L77.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b11"></a>

##### MVP-B11

**P1** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D1.1 · Checklist: B11 · Cross-task: [XT-13](#xt-13)  

- **Question.** Should D1.1 give full credit when one finding attributes 'the fault' to lightning and other findings give the circuit and the fault type, and 0.5 for lightning on the circuit without the fault type (or the fault type without the circuit)?
- **Builder choice.** Yes since key 0.3.1 (element lightning_caused_fault). Lightning merely recorded near the circuit, without attribution to the fault, still earns 0.5.
- **Alternatives.** Require lightning, circuit and fault type in one finding. Require the cause to be attributed (NGET/ESO) for full credit.
- **Impact.** opus55-002 (F01 + F02 'NGET states that lightning caused the fault') and sonnet55-001 (F01 + F02 'NGET and ESO attribute the fault to lightning') moved from 0.5 to 1.0 under 0.3.1 and would revert. opus55-003, haiku45-001 and live run 001 get full credit through lightning_on_circuit.
- **Evidence.** ESO PDF p12 (printed 13): "A single (blue) Phase to Earth fault on Eaton Socon - Wymondley circuit" and "This is consistent with a lightning strike on Eaton Socon - Wymondley circuit". APP PDF p25: "As such we can be confident that a lightning strike was the cause of the fault." ESO PDF p15 (printed 16): "NGET by analysing their protection data confirmed that these lightning strikes were the cause of the circuit trip and reclose". R03 L25-L27, L36-L37, L89-L90, L102-L104.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b12"></a>

##### MVP-B12

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D4.1 · Checklist: B12 · Cross-task: [XT-11](#xt-11)  

- **Question.** Should D4.1 full credit require all three of: control-system resonance, the overcurrent-protection de-load, and the weak-internal-network contribution?
- **Builder choice.** Yes, with DRC clearance not required. 0.5 for the resonance or the overcurrent de-load alone. Any two of the three still earn only 0.5 (synthetic check: resonance plus overcurrent = 0.5).
- **Alternatives.** Full credit for resonance plus overcurrent de-load (the operator's mechanism), with the weak network optional. Full credit for any two of the three. Require DRC clearance.
- **Impact.** Three of five live runs are 0.5. opus55-002: F07 resonance and F08 weak network, no overcurrent anywhere. Live run 001: F08 resonance, weak network and DRC, no overcurrent. haiku45-001: F14/F17 resonance and F18 protection disconnecting turbines, no weak network. 'Any two' would raise all three to 1.0; 'resonance plus overcurrent' would raise only haiku45-001.
- **Evidence.** APP PDF p43: "The de-load was caused by an unexpected wind farm control system response, due to an insufficiently damped electrical resonance in the sub-synchronous frequency range". APP PDF p41: "all WTGs on Hornsea 1B and Hornsea 1C reduce to 0MW as a result of overcurrent protection in the generators". ESO PDF p20 (printed 21): "was a contributory factor as it created a weak internal network environment" and "Orsted have since concluded that the DRC worked as designed and was not the cause of the de-load". OFG PDF p29: "The offshore wind turbine controllers, however, reacted incorrectly to voltage fluctuations on the offshore network following the fault." S01 L55-L57, L61-L63, L77-L80, L85-L87.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b14"></a>

##### MVP-B14

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.5 · Checklist: B14 · Cross-task: [XT-05](#xt-05)  

- **Question.** Should D3.5 full credit require all three of: the stated duration convention (threshold and method), the 1-s sampling, and the statement that sub-second crossings cannot be resolved?
- **Builder choice.** Yes. Two of three earn 0.5, one earns 0. A sub-second crossing time claimed from 1-s data, not said to be interpolated or estimated, caps D3.5 at 0.5. The requirement comes from the brief's 'method and sampling limits' and the handoff's rules, not from a report passage. A bare 'samples below 49' counts as a convention.
- **Alternatives.** Full credit for convention plus sampling. 0.5 for any single element. Make the sub-second limit context only. Require an explicit threshold word ('strictly below' / 'at or below').
- **Impact.** Live run 001 gets D3.5 = 0: it states only the 1-s sampling (F14). It would get 0.5 if one element earned half credit. All panel runs get full credit. Whether opus55-002's 'count of 1 s samples below 49.000 Hz' (F19 quantity.basis) is a sufficient convention belongs to this decision.
- **Evidence.** ESO PDF p13 (printed 14), context: "16:53:49.398 Frequency breaches 48.8Hz trigger level resulting in LFDD." ORR PDF p4, context: "shut down within 200ms of the frequency dropping below 49.0Hz". R01 L22-L23: 'Interval: 1 second between consecutive rows'. R01 L28-L29: 'The file carries no information about behaviour between consecutive samples'.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b16"></a>

##### MVP-B16

**P1** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D2.1 · Checklist: B16 · Cross-task: [XT-14](#xt-14)  

- **Question.** Should the D2.1 MW value need loss wording, with 799 MW (pre-event output) or 800 MW (export capability) counting only together with the 62 MW residual?
- **Builder choice.** Yes.
- **Alternatives.** Accept only 737 MW or the 799 → 62 pair. Give 0.5 for a loss derived from capability (800 − 62).
- **Impact.** haiku45-001 F16's quantity is 738 MW, 'from approximately 800 MW declared capability minus 62 MW'. It gets full credit (within 10% of 737). No other run is affected.
- **Evidence.** ESO PDF p18 (printed 19): "Hornsea immediately de-loaded from 799MW to 62MW". ESO PDF p13 (printed 14): "Hornsea Offshore Windfarm 737 MW". S01 L35, L40-L43.
- **Compiler's note.** Priority raised from P2 to P1 on review: the capability alternative moves a live value (haiku45-001 D2.1 1 → 0.5), and crediting a loss derived from export capability rather than pre-event output is a domain call.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b17a"></a>

##### MVP-B17a

**P1** · 40 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.1, D3.2, D3.3, D3.4 · Checklist: B17 · Cross-task: [XT-06](#xt-06)  

- **Question.** When a finding's structured quantity does not fit a D3 criterion, should the grader read values from its statement and derivation, scoring an automatic 0 only for a genuine omission or a wrong in-window structured quantity, and otherwise sending the criterion to a human?
- **Builder choice.** Yes (key and grader 0.3.1, decision 18, two rounds). Offsets from a written reference time are computed. Never credited automatically: level, threshold or 'not yet' wording; decimals without a unit; prose seconds without duration wording; a statement value next to its own out-of-tolerance quantity.
- **Alternatives.** Read structured quantities only (the 0.3.0 behaviour). Credit any in-tolerance prose value automatically. Send every prose value to a human.
- **Impact.** Three live results moved from automatic 0 under 0.3.0 to automatic 1 now. opus55-002 D3.3: F20 says '50.001 Hz at 16:57:16', quantity 283 s. haiku45-001 D3.2: F09's quantity is the 1.208 Hz drop. haiku45-001 D3.3: F11's quantity is 207 s. Live run 001 D3.1 is now pending (proposal 0) instead of automatic 0. The cost is that more D3 criteria need a human.
- **Evidence.** R01 row:830 '2019-08-09T16:53:49+01:00,48.787'; row:1037 '2019-08-09T16:57:16+01:00,50.001'. DECISIONS.md decision 18; conventions.unit_note; GB_2019_MVP.md table of changes from 0.3.0 to 0.3.1. REVIEW_CHECKLIST.md B17.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b17b"></a>

##### MVP-B17b

**P1** · 5 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.3 · Checklist: B17 · Cross-task: [XT-04](#xt-04)  

- **Question.** Does '50.0 Hz at 16:57:16' (0.001 Hz from the 50.001 Hz sample) meet D3.3?
- **Builder choice.** Yes: within ±0.002 Hz and credited automatically.
- **Alternatives.** Require 50.001 Hz. Or treat 'returned to 50 Hz' as reaching the landmark and judge it on the time alone.
- **Impact.** D3.3 automatic 1 rests on '50.0 Hz' for opus55-003 (F17), sonnet55-001 (F17), haiku45-001 (F11) and live run 001 (F18). Only opus55-002 (F20) writes 50.001. R01's own number format writes a published 50 as '50.0'.
- **Evidence.** R01 rows 1035-1037 (16:57:14 49.994; 16:57:15 49.997; 16:57:16 50.001). R01 L26-L27: 'for example a published value of 50 appears as 50.0'. ESO PDF p13 (printed 14): "16:57:15 Frequency returns to 50Hz following over 1,000MW of response". ESO PDF p14 (printed 15): "Frequency is restored to 50Hz [16:57:15]".
- **Compiler's note.** Row numbers corrected: in the R01 CSV rows 1036-1038 are 49.997, 50.001, 50.006; the values quoted are rows 1035-1037.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b19"></a>

##### MVP-B19

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D4.4 · Checklist: B19 · Cross-task: [XT-07](#xt-07)  

- **Question.** Should D4.4 full credit require both unresolved root causes (the speed-signal discrepancy and the pressure excursions) to sit in findings the agent labels unknown, or hypothesis with not-established wording?
- **Builder choice.** Yes. 0.5 for one cause so labelled, or for both kept open in wording but under a factual status. A hypothesis label without not-established wording earns nothing.
- **Alternatives.** Full credit for explicit not-established wording under any status. 0.5 per cause regardless of status.
- **Impact.** sonnet55-001 D4.4 = 0.5: the speed root cause is in F09 (unknown), but the pressure root cause's 'not established' appears only in F10/F11, labelled 'reported', next to the established GT trips. haiku45-001 D4.4 = 0.5: F25 and F27 are labelled 'reported' with 'has not been established' / 'remains unknown'. Both would get 1.0 under the wording-only alternative. A finding has one status, so stating an established trip and its open root cause together forces a choice (see MVP-B23).
- **Evidence.** OFG PDF p31: "The root cause of the discrepancy in the speed sensors has not been established." and "The root cause of these high pressure conditions has not been established." APP PDF p46: "For reasons presently unknown a high-pressure excursion occurred on GT1A" and "A comprehensive investigation of hardware, software, fault handling and diagnostic coverage for the conditions, that the ST was subjected to during this rare system disturbance, is ongoing." S04 L50-L51, L56-L59, L62-L63; S03 L44-L46, L49-L50.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b21"></a>

##### MVP-B21

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D2.2, D2.3, D2.4 · Checklist: B21 · Cross-task: [XT-03](#xt-03)  

- **Question.** Should omitting the ±0.5 s datum uncertainty cost 0.5 on each of D2.2, D2.3 and D2.4, or be assessed once (D2.5)? And should one statement anywhere satisfy all three?
- **Builder choice.** Required for full credit on each of D2.2–D2.4, and satisfied once anywhere: any finding of any status, or a report sentence naming Little Barford, a unit, the SOE or S03. Accepted forms: ±0.5 s, ±500 ms, 'datum uncertainty', 'a half-second uncertainty'. 'half a second after' does not count.
- **Alternatives.** Assess it once, in D2.5 only. Or require it with each derived time.
- **Impact.** Every live run states it once, so datum_uncertainty is 1 everywhere. haiku45-001's unit findings (F23, F26, F28) give T + offset times without ±0.5 s; its credit comes from F21, a UPS-alarm finding ('16:52:34 ± 0.5 s BST'), and report section 3. Under a 'with each time' rule its D2.2–D2.4 would each drop to 0.5. A synthetic 'ST1C (244 MW) tripped at 16:52:35.2 BST (T + 1.185 s)' gets 0.5.
- **Evidence.** APP PDF p45: "Time T = 16:52:34 +/- 0.5seconds". S03 L6-L9. answer_key.json D2.2–D2.4 tolerances.datum_uncertainty.
- **Compiler's note.** Priority raised from P2 to P1 on review: the 'with each time' alternative moves three live values (haiku45-001 D2.2–D2.4 1 → 0.5).

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b23"></a>

##### MVP-B23

**P1** · 25 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D4.1, D4.2, D4.3 · Checklist: B23 · Cross-task: [XT-07](#xt-07)  

- **Question.** Should an established mechanism (D4.1–D4.3) count when stated without hedging in a finding labelled unknown, while a finding labelled hypothesis, or one that negates or hedges the mechanism itself, never counts?
- **Builder choice.** Yes since 0.3.1 (other_statuses, mechanism_hedge_patterns, mechanism_negation_patterns). A whole-statement hedge check was rejected because it would miss sonnet55-001 F09. D4.2 also accepts 'did not agree', 'not in agreement', 'not consistent', 'diverged' and 'conflicting'.
- **Alternatives.** Require a factual status (the 0.3.0 behaviour). Give 0.5 for a mechanism labelled hypothesis.
- **Impact.** Changes from 0.3.0 to 0.3.1: opus55-002 D4.2 0 → 1 (F11, unknown: 'reported to have tripped because its three speed signals disagreed'); opus55-002 D4.3 0.5 → 1 (F12, unknown); sonnet55-001 D4.2 0 → 1 (F09, unknown: 'Reported mechanism … discrepancy between the three independent speed sensors'). Reverting the rule would restore the old values.
- **Evidence.** APP PDF p46: "Our investigations have confirmed that the Steam Turbine tripped due to a discrepancy in the speed signals after the point of the Transmission System fault clearance." OFG PDF p31: "We have established that the steam turbine tripped initially because of a discrepancy in the three independent speed sensors on the turbine." ESO PDF p20 (printed 21): "The initiation of the trip of Little Barford steam turbine (ST1C) was caused by a discrepancy between the measurements from three speed signals." APP PDF p46: "GT1B was manually tripped shortly after as a result of excessive steam pressure." S04 L46-L47, L56-L58; S03 L42-L43.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b26"></a>

##### MVP-B26

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D2.2, D2.3, D2.4, D2.5, D3.5 · Checklist: B26 · Cross-task: [XT-05](#xt-05)  

- **Question.** Should the method elements read a finding's statement, derivation and quantity.basis together, plus every report sentence, while all other elements read the statement only?
- **Builder choice.** Yes (conventions.text_fields), because the brief tells agents to put method in derivation and quantity.basis. The method elements are: D2.2–D2.4 datum uncertainty; D2.5 Hornsea and SOE clock bases; D3.5 convention, sampling and sub-second limit.
- **Alternatives.** Read the statement only. Or read findings only, not the report.
- **Impact.** opus55-002's D2.5 Hornsea clock basis is met only by its executive summary. opus55-002's D3.5 convention is met only by F19's quantity.basis ('count of 1 s samples below 49.000 Hz'). haiku45-001's D3.5 convention is met only by F10's derivation ('Count of 33 one-second samples at or below 49.0 Hz threshold'). Statement-only reading would take opus55-002 and haiku45-001 D3.5 from 1.0 to 0.5.
- **Evidence.** answer_key.json conventions.text_fields. R01 L22-L23, L28-L29; S01 L6; S03 L6-L9.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b28a"></a>

##### MVP-B28a

**P1** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D2.4, D2.5 · Checklist: B28 · Cross-task: [XT-06](#xt-06)  

- **Question.** Should a Little Barford trip clock time that only the report text gives (no finding states it) be credited for D2.2–D2.5, or remain a reviewer note with the proposal at 0.5?
- **Builder choice.** Note only; the proposal stays 0.5. Decision 9 leaves the T + offset derivation to the agent, in findings.
- **Alternatives.** Credit report-text times automatically. Or treat 'T + offset' plus a stated T in the same finding as an implicit derived time.
- **Impact.** opus55-002 F10 gives GT1B only as 'T+84.613 s' (with T = 16:52:34 ± 0.5 s); the report gives '16:53:58.6 BST'. This makes D2.4 = 0.5 and D2.5 = 0.5 (gt1b_group missing). Both would be 1.0 if credited.
- **Evidence.** S03 L28-L29 ('+84.613 s'); S03 L6-L9. APP PDF p45: "GT1B Breaker Open feedback +84.613 Sec". ESO PDF p13 (printed 14): "16:53:58 Little Barford GT1B tripped with 187MW generation lost instantaneously." DECISIONS.md decision 18 (second round).

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b28b"></a>

##### MVP-B28b

**P1** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.5, D3.4 · Checklist: B28 · Cross-task: [XT-05](#xt-05)  

- **Question.** Should a stated duration convention that does not reproduce the duration the submission reports cost D3.5 credit?
- **Builder choice.** Never scored: a note only (auto.convention_check, ±0.5 s).
- **Alternatives.** Cap D3.5 at 0.5. Or send D3.4 and D3.5 to a human.
- **Impact.** haiku45-001 F10 reports 33 s, but its derivation says 'at or below 49.0 Hz' (34 s) and its quantity basis says 'from first sample below … to last sample below' (32 s). D3.5 is 1.0 with a note now and would be 0.5 if the mismatch capped it.
- **Evidence.** R01 time:2019-08-09T16:53:40+01:00/2019-08-09T16:54:14+01:00 (16:53:40 = 49.0). D3.4 expected.alternatives: 34, 33.964, 32.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-c1"></a>

##### MVP-C1

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D4.2, D4.3, D4.4 · Checklist: C1 · Cross-task: [XT-08](#xt-08)  

- **Question.** Is SF1 (an established Little Barford root cause asserted) correctly defined, given the evidence gives only the sources' own wording ('for reasons presently unknown', 'has not been established', 'preliminary view')?
- **Builder choice.** SF1 = a factual finding or report sentence asserting an underlying cause of the speed-signal discrepancy or of the GT1A/GT1B pressure excursions. Examples: a faulty sensor, a failed bypass valve, the UPS changeover as the cause, or the transmission fault as the established cause. A hypothesis or unknown label does not qualify.
- **Alternatives.** Narrow SF1 to explicit 'root cause was' assertions. Or widen it to the Hornsea root cause.
- **Impact.** No SF1 is suspected on any live run: flags.suspected_severe_assertions is empty for all five.
- **Evidence.** OFG PDF p31: "The root cause of the discrepancy in the speed sensors has not been established." and "The root cause of these high pressure conditions has not been established." APP PDF p46: "For reasons presently unknown a high-pressure excursion occurred on GT1A resulting in an automated trip." S04 L46-L54 (A4–A6), L56-L66 (B1–B3); S03 L42-L54.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-c2"></a>

##### MVP-C2

**P1** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D4.3, D4.4 · Checklist: C2 · Cross-task: [XT-08](#xt-08)  

- **Question.** Should asserting as fact ESO's executive-summary 'failure of a bypass valve to operate correctly' be SF1, given it is not in the evidence pack and Ofgem did not establish it?
- **Builder choice.** Yes. The MVP heuristic fires on 'bypass valve' in any factual finding that has no hedge word.
- **Alternatives.** Do not flag a restatement attributed to ESO, as the SR/FI graders have done since decision 47. Or require assertion wording rather than the bare phrase.
- **Impact.** No live hit. Synthetic probes show the MVP heuristic fires on an attributed restatement ('ESO's executive summary says GT1A tripped following the failure of a bypass valve to operate correctly.') and even on '… the bypass valve position was not recorded.' A flag is only a suggestion; the reviewer confirms.
- **Evidence.** ESO PDF p4 (printed 5), conflicting account: "following the failure of a bypass valve to operate correctly". The bundle mentions only the bypass system (S04 L53-L54: 'A physical inspection of the bypass system is now planned … to help determine the root cause of the pressure excursions'). DECISIONS.md decision 47.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-c3"></a>

##### MVP-C3

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D4.4 · Checklist: C3, C7 · Cross-task: [XT-08](#xt-08)  

- **Question.** Should Ofgem's preliminary view and RWE's UPS changeover explanation count only as hypotheses, so that a factual finding calling the transmission fault the cause of the speed-signal discrepancy fires SF1 unless presented as a preliminary view, hypothesis or possibility? (Checklist C3 and C7 merged.)
- **Builder choice.** Yes. SF1 has a trigger for a speed-signal discrepancy 'caused by / due to' the transmission (network, grid, lightning) fault.
- **Alternatives.** Treat Ofgem's view, when attributed to Ofgem, as a reported account even without the word 'preliminary'. Treat the UPS explanation as set aside rather than a live hypothesis (S04: 'we do not now believe the UPS' were related').
- **Impact.** Not flagged on live runs: sonnet55-001 F09 ('Ofgem's preliminary view is that it was due to the transmission fault. RWE's UPS changeover hypothesis is unproven') and opus55-002 F13 (hypothesis, UPS). A synthetic 'The ST1C speed-signal discrepancy was caused by the transmission network fault.' fires SF1.
- **Evidence.** OFG PDF p31: "Given the sequence of events and in absence of an established root cause, it is our preliminary view that the steam turbine’s anomalous speed readings and the resulting trip were due to the transmission network fault following the lightning strike." APP PDF p45: "RWE’s hypothesis is that the UPS’ have initiated a changeover to battery back-up supplies as a consequence of the system disturbance." S04 L41-L44, L64-L66; S04 L39 ('Therefore, we do not now believe the UPS' were related').

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-c4"></a>

##### MVP-C4

**P1** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Checklist: C4 · Cross-task: [XT-09](#xt-09)  

- **Question.** Are the SF2 (invented evidence record) and SF3 (official enforcement outcome) definitions acceptable, with heuristics that only suggest flags for reviewer confirmation?
- **Builder choice.** SF2: any R/S ID matching `\b[RS]\d{2}\b` that is not R01, R03, S01, S03 or S04, or a document the agent never had. SF3: triggers on £ amounts, 'fined', 'penalty', 'redress', 'settlement', and 'enforcement action/outcome/decision/notice'.
- **Alternatives.** SF2 only when the ID is used as support. SF3 narrowed to asserted outcomes, as the full-investigation key does since decision 71.
- **Impact.** No SF2 or SF3 on live runs. A synthetic 'As the R04 lightning log shows …' fires SF2. The MVP SF3 still fires on negated or recommended enforcement ('Ofgem has not yet announced any enforcement action.'; 'Ofgem should decide on any enforcement action …'), which decision 71 fixed only in the full-investigation key.
- **Evidence.** answer_key.json severe_flags SF2 and SF3 (heuristic, examples, non_examples). DECISIONS.md decisions 50 and 71. The bundle contains no enforcement material.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-c5"></a>

##### MVP-C5

**P1** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D4.4 · Checklist: C5 · Cross-task: [XT-08](#xt-08)  

- **Question.** Should SF1 fire on 'root cause' / 'underlying cause' only in assertion shapes, with any hedge or uncertainty word anywhere in the same sentence excusing it?
- **Builder choice.** Assertion shapes only. 'has yet to be established', 'under investigation' and 'a planned inspection to help determine the root cause' do not fire. The unless_any list applies to the whole sentence (an MVP limit noted in decision 47).
- **Alternatives.** Scope the excuses to the clause that carries the assertion.
- **Impact.** No live hit. Synthetic: 'The root cause of the ST1C trip was a faulty speed sensor.' fires SF1, but adding ', although the cause of the UPS alarms is unknown' suppresses it (a false negative).
- **Evidence.** SF1 heuristic.note and non_examples. S04 L53-L54: 'to help determine the root cause of the pressure excursions'. DECISIONS.md decision 47: 'Remaining limit (MVP rule): a hedge or "unknown" elsewhere in the same sentence still excuses an assertion.'

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-c6"></a>

##### MVP-C6

**P1** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D4.4 · Checklist: C6 · Cross-task: [XT-10](#xt-10)  

- **Question.** Are the effects of a confirmed flag right?
- **Builder choice.** SF1 makes its findings unsupported (or contradicted) and sets D4.4 content to 0. SF2 and SF3 make their findings unsupported. A decisions file that marks such a finding supported, or credits D4.4 with SF1 confirmed, is rejected.
- **Alternatives.** SF1 also sets D4.2/D4.3 to 0 (it lists them in applies_to, but zero_content names only D4.4). Or SF1 caps D4.4 at 0.5 when the other cause is correctly labelled.
- **Impact.** No flag is confirmed on any live run. A confirmed SF1 would take D4.4 from 1.0 to 0 on opus55-002, opus55-003 or live run 001.
- **Evidence.** answer_key.json severe_flags[].effect and applies_to; REVIEW_CHECKLIST.md C6.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-r01clk"></a>

##### MVP-R01CLK

**P1** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.1, D3.2, D3.3, D3.4 · Checklist: no row · Cross-task: [XT-03](#xt-03)  

- **Question.** Should R01's +0100 timestamps be accepted as BST although NESO's general dataset description refers to UTC?
- **Builder choice.** The offsets are used as given (+01:00), so all D3 expected times are BST. R01 is the corrected archive of 14 February 2020.
- **Alternatives.** Treat the clock basis as unresolved and accept both readings.
- **Impact.** All D3.1–D3.3 expected times depend on it. R01 agrees with ESO's timeline to within about 1 s (16:52:59 vs ESO's 16:52:58 arrest; 16:57:16 vs ESO's 16:57:15 restoration), which supports BST. sonnet55-001 F18 and F20 (unknown) flag the ambiguity; this is not scored.
- **Evidence.** R01 L6, L13, L32-L35: 'The publisher's general dataset description refers to UTC while the raw file carries +0100 offsets; no further publisher clarification was obtained.' R01 L14-L16 (data corrected 14 February 2020). ESO PDF p12 (printed 13): "16:52:58 Frequency drop is arrested at 49.1Hz". ESO PDF p13 (printed 14): "16:57:15 Frequency returns to 50Hz". DECISIONS.md decision 6.

Decision: [ ] accept  [ ] change to: ____

#### SR — `gb-2019-system-response` (key 0.1.1) — P1, 45 items, 11 h 15 min

<a id="sr-a3"></a>

##### SR-A3

**P1** · 150 min · SR (`gb-2019-system-response`) · Criteria: all 60 criteria · Checklist: A3 · Cross-task: [XT-19](#xt-19)  

- **Question.** Does every expected value in key 0.1.1 agree with its report passages, and where sources disagree is each figure kept on its own basis rather than one being picked?
- **Builder choice.** Expected values drafted by the grading builder from bundle 0.1.0 and the source PDFs; report_passages are verbatim quotes test-verified against the stated PDF page; disagreements kept as separate accounting figures (section C).
- **Alternatives.** Change individual expected values or pick one account where the reviewer judges a source authoritative.
- **Impact.** Every content proposal on the six runs is computed against these values; a changed expected value needs key 0.1.2, new grading decisions (bound to the key sha256) and a regrade of all six fixtures.
- **Evidence.** ESO PDF p10: "The second Gas Turbine at Little Barford tripped from 187MW after the initiation of LFDD bringing total generation lost through the event to 1,878MW."; OFG PDF p18: "The cumulative loss of generation at this point was at least 1,990MW."; Visible/key locators: every criteria[].report_passages / visible_evidence entry (60 criteria)

Decision: [ ] accept  [ ] change to: ____

<a id="sr-a7"></a>

##### SR-A7

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T12.05 · Checklist: A7  

- **Question.** Should T12.05 (system inertia with its basis), an increment-A addition outside the handoff criteria, be kept?
- **Builder choice.** Keep T12.05 (origin increment_A_addition): the brief asks how inertia compared with the losses and decision 20 keeps ESO's two inertia figures on different bases.
- **Alternatives.** Remove it to keep the handoff criteria closed; or keep it only as an uncertainty-register example under T17.04.
- **Impact.** T12.05 is 1 on sr80k-opus55-001, sr80k-sonnet55-001, sr80k-haiku45-001 (219.6 GVA.s, F28), sr30k-opus55-001, sr30k-sonnet55-001 and 0 on sr30k-haiku45-001 (215 GVAs only in its report). Removing it deletes one criterion from all six reports.
- **Evidence.** ESO PDF p23: "01 July 09 August Demand 28 GW 29 GW Inertia 201 GVAs 210GVAs"; APP PDF p90: "16:52 Immediately prior to the trip 219632"; Visible/key locators: T12.05 visible R02 L192, R02 L201-L207, S12 L112-L118, S12 L146-L147

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b2"></a>

##### SR-B2

**P1** · 15 min · SR (`gb-2019-system-response`) · Criteria: T01.02, T02.04, T05.01a, T05.01b, T05.02 · Checklist: B2 · Cross-task: [XT-03](#xt-03)  

- **Question.** Should unlabelled times in R03, R08, S05-S07 and S12 be read as BST, S01 and Elexon data as UTC, and S03 as offsets from T = 16:52:34 ±0.5 s (so an unlabelled 15:52:33 is one hour out for T01.02)?
- **Builder choice.** Clock conventions as in key conventions.time_basis; submissions compared as instants; statement times without offset read as BST unless followed by Z/UTC.
- **Alternatives.** Treat unlabelled times as ambiguous and send them to a human; accept an unlabelled 15:52:33 as UTC.
- **Impact.** All six runs score 1 on T01.02 and T05.02, so no current value depends on it; the rule decides T01.02 and every restoration/sequence time for any run that writes unlabelled UTC.
- **Evidence.** APP PDF p41: "began de-loading turbines at 15.52.33.728 and completed the de-load at 15.52.33.835, 107ms later"; ESO PDF p12: "16:52:33.531 Hornsea was generating 799MW and absorbing 0.4MVAR"; APP PDF p45: "110v AC UPS –B- general fault alarm “T” = 0 mSec"; Visible/key locators: S03 L6-L9 (datum); S01 L41-L44; R03 L36-L37; DECISIONS 19

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b3"></a>

##### SR-B3

**P1** · 5 min · SR (`gb-2019-system-response`) · Criteria: T01.04, T01.03a, T16.02 · Checklist: B3 · Cross-task: [XT-02](#xt-02)  

- **Question.** Is ±2 s around 16:52:53 BST the right tolerance for the delayed auto-reclose, with the fault type moved to T01.03a and protection performance to T16.02 (MVP D1.4 combined them)?
- **Builder choice.** T01.04 time_s 2 (builder choice, source prints whole seconds); presenting the reclose as a second initiating fault scores 0.
- **Alternatives.** ±1 s (as T01.02); keep MVP D1.4's combined element.
- **Impact.** T01.04 is 1 on all six runs; no current value depends on the 2 s width.
- **Evidence.** ESO PDF p12: "16:52:53 Eaton Socon - Wymondley circuit energised on DAR"; APP PDF p17: "The circuit was returned to service 20 seconds later with our automatic Delayed Auto-Reclose system"; Visible/key locators: R03 L49-L50, R03 L51-L53, R03 event:R03-C8, S09 response:S09-NGET-04

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b4"></a>

##### SR-B4

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T02.01a, T02.01b · Checklist: B4  

- **Question.** Should T02.01 need estimate wording for full credit (else 0.5), credit Ofgem's/E3C's 350-430 MW RoCoF range in full, and give ESO's 430 MW simulation figure alone 0.5?
- **Builder choice.** Full needs estimated/approximately/about/~/modelled/inferred in the statement, quantity basis or derivation; 350-430 MW (Ofgem 2.4.6, E3C) is an accepted alternative; 430 MW alone 0.5; 150 MW attributed to DNO returns is misattributed.
- **Alternatives.** Accept 'approximately' only when attributed; give 430 MW full as ESO's modelled basis; credit the bare figure in full.
- **Impact.** T02.01a/b are 1 on both opus and both sonnet runs and 0 on both haiku runs (figures absent), so the wording rule does not move any current value.
- **Evidence.** ESO PDF p12: "16:52:33 Approximately 150MW of embedded generation trips on vector-shift protection"; ESO PDF p21: "it is estimated that approximately 350MW of embedded generation was lost due to RoCoF"; APP PDF p62: "while analysis of the simulation data indicates that it may be slightly higher at 430MW"; OFG PDF p18: "As a result, an estimated 350- 430MW of distributed generation tripped off unnecessarily, based on information provided by the ESO"; E3C PDF p12: "which disconnected between 350-430MW"; Visible/key locators: S06 L46-L49, S06 L53-L57, S06 L68-L71, S06 L86-L89, S12 L19-L22; accounting DG_VS_150, DG_ROCOF_350, DG_ROCOF_350_430, DG_ROCOF_430

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b5"></a>

##### SR-B5

**P1** · 15 min · SR (`gb-2019-system-response`) · Criteria: T02.04 · Checklist: B5 · Cross-task: [XT-03](#xt-03)  

- **Question.** Are the T02.04 temporal-group windows right (initial 16:52:33.490-16:52:36.5, GT1A 16:53:25-16:53:40, LFDD within ±2 s of 16:53:49.398, GT1B 16:53:52-16:54:05), with clock bases not required and a Hornsea/ST1C order finer than the datum capped at 0.5?
- **Builder choice.** Group windows as MVP D2.5; LFDD window ±2 s is a builder choice; relative wording accepted ('GT1B after LFDD' covers the LFDD group); clock-basis method elements dropped (intended divergence from D2.5).
- **Alternatives.** Require the clock basis/datum as D2.5 did; narrow the LFDD window to ±1 s; drop the sub-second-order cap.
- **Impact.** sr80k-haiku45-001 and sr30k-haiku45-001 are 0.5 (only GT1A/GT1B placed; for haiku30k the GT1A/GT1B times also appear only in the report); the other four runs 1. On MVP v2 runs opus55-003 and sonnet55-001 the dropped clock-basis requirement is what separates T02.04 0.5 from D2.5 1. No run hit the sub-second cap.
- **Evidence.** ESO PDF p13: "16:53:49.398 Frequency breaches 48.8Hz trigger level resulting in LFDD."; ESO PDF p13: "16:53:58 Little Barford GT1B tripped with 187MW generation lost instantaneously."; APP PDF p45: "GT1A Auto shutdown command +56.583 Sec"; APP PDF p41: "began de-loading turbines at 15.52.33.728 and completed the de-load at 15.52.33.835, 107ms later"; Visible/key locators: S03 L19-L29, S03 L6-L9, S01 L41-L44, S06 L46-L49, S05 L61-L63, S12 L25-L28

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b7"></a>

##### SR-B7

**P1** · 20 min · SR (`gb-2019-system-response`) · Criteria: T05.01a, T05.02 · Checklist: B7 · Cross-task: [XT-21](#xt-21)  

- **Question.** Are the restoration boundaries right: instructions began 16:58 BST (±2 min; ESO's earlier 17:00 inside, the call diagram's 17:05 outside to a human), completion 17:37 BST with 17:34/17:36 (first DNO completion, masked), 17:40 (Elexon DCI end; UKPN 'approx. 17:40') and 18:34 treated as other events?
- **Builder choice.** Handoff 2-minute tolerance; 16:58 from ESO timeline/section 6.1 and S07 Table 7 (UKPN LPN told at 16:58, read from shared cells); 'the first DNO reported ... complete' masked for T05.02; a clock label after a range applies to both ends.
- **Alternatives.** Use ESO's earlier account (17:00 start, 17:19 end) as an equal alternative; accept 17:34-17:40 as completion; read Table 7 without shared cells (11 values for 12 areas in the extracted text).
- **Impact.** T05.02 is 1 on all six runs; T05.01a is 1 on five and 0 on sr30k-haiku45-001 (no instruction time). Ambiguous source: ESO PDF p29's extracted Table 7 prints 11 instruction times for 12 DNO areas; the bundle's shared-cell reading gives UKPN LPN 16:58 and WPD East Midland 17:16, and the key's expectation text depends on that reading (no current value does).
- **Evidence.** ESO PDF p13: "16:58 – 17:16 ESO progressively instructs the DNO’s that they can commence demand restoration"; APP PDF p87: "At 17:00hrs, the first demand restoration instruction was initiated. The last restoration instruction was sent to WPD East Midland at 17:19hrs."; ESO PDF p29: "When did ESO instruct restoration 17:06 17:13 17:10 17:08 17:10 17:13 17:14 16:58 17:08 17:05 17:16"; ESO PDF p13: "17:37 All DNO’s have confirmed that demand restoration has been completed"; ESO PDF p29: "[17:34] First DNO report was received that their demand had been fully restored."; Visible/key locators: S07 L37-L40, S07 L46-L47, S07 entry:S07-E12, S07 entry:S07-T08-instructed, R08 entry:R08-C05, S07 L118-L119, S05 L35, R07 L85, S07 entry:S07-E13, S09 response:S09-ESO-05

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b26"></a>

##### SR-B26

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T05.01b · Checklist: B26 · Cross-task: [XT-21](#xt-21)  

- **Question.** Should T05.01b (all instructions issued by 17:16 BST, ±2 min) also read statement times when the finding's event_time is the other boundary of the window, with the better result counting, while other time criteria keep the MVP rule?
- **Builder choice.** read_statement_times for T05.01b only ('instructed between 16:58 and 17:16 BST' with event_time 16:58 credits 17:16); ESO's earlier 17:19 is outside the tolerance and goes to a human.
- **Alternatives.** Read only event_time (key 0.1.0 behaviour); apply statement-time reading to all time criteria; accept 17:19 as ESO's earlier account.
- **Impact.** Moved T05.01b from 0 to 1 on sr80k-opus55-001 (F31), sr80k-haiku45-001 (F37) and sr30k-sonnet55-001 (F21); currently 1 on five runs and 0 on sr30k-haiku45-001.
- **Evidence.** ESO PDF p29: "[16:58 to 17:16] Demand restoration instruction to DNOs was initiated by the ESO control room."; APP PDF p65: "By 17:16hrs, demand restoration instructions were all initiated to DNOs."; APP PDF p87: "At 17:00hrs, the first demand restoration instruction was initiated. The last restoration instruction was sent to WPD East Midland at 17:19hrs."; Visible/key locators: S07 L37-L38, S07 L46-L47, R08 L19, R08 entry:R08-N3, S07 entry:S07-T12-instructed; DECISIONS 44

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b9"></a>

##### SR-B9

**P1** · 15 min · SR (`gb-2019-system-response`) · Criteria: T07.04, T17.01 · Checklist: B9 · Cross-task: [XT-07](#xt-07)  

- **Question.** Should the same Little Barford root-cause evidence be assessed twice (T07.04 mechanism and T17.01 uncertainty register), with full credit only for both causes kept open in findings labelled unknown/hypothesis, wording under a factual status capped at 0.5, and ESO's executive-summary bypass-valve wording treated as a conflicting account?
- **Builder choice.** Same pre-screen (MVP D4.4) for both; full: speed-signal and bypass-pressure causes in labelled findings; partial: one labelled, or both open under a factual status; ESO's 'failure of a bypass valve' (S12 F7) is a conflicting account, not an established root cause.
- **Alternatives.** Assess the root cause once (drop T17.01 or make it register-only); credit wording alone regardless of status; treat ESO's valve wording as an accepted alternative.
- **Impact.** T07.04 and T17.01 are each 0.5 on sr80k-sonnet55-001 and sr80k-haiku45-001 (only the speed-signal cause labelled; judge 0.5) and on sr30k-haiku45-001 (both open under a factual status); 1 on opus both and sr30k-sonnet55-001. Double assessment doubles each loss. On MVP v2 runs sonnet55-001 and haiku45-001 have the same 0.5.
- **Evidence.** OFG PDF p31: "The root cause of the discrepancy in the speed sensors has not been established."; OFG PDF p31: "The root cause of these high pressure conditions has not been established."; APP PDF p46: "For reasons presently unknown a high-pressure excursion occurred on GT1A resulting in an automated trip."; ESO PDF p4: "following the failure of a bypass valve to operate correctly"; Visible/key locators: S04 L46-L51, S03 L44-L46, S03 L49-L50, S04 L58-L59, S04 L62-L63, S12 L148-L152

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b10"></a>

##### SR-B10

**P1** · 5 min · SR (`gb-2019-system-response`) · Criteria: T08.02 · Checklist: B10  

- **Question.** Should the ~200 MW at 49 Hz earn full credit only when described as net (or modelled net), 0.5 without the distinction, and 0 when called gross?
- **Builder choice.** DG_49HZ_200 with qualifier 'net'/'modelled net'; mismatch 'gross' = 0.
- **Alternatives.** Accept 'modelled' alone as full; give 'gross' 0.5.
- **Impact.** T08.02 is 1 on both opus and both sonnet runs and 0 on both haiku runs (figure absent).
- **Evidence.** ESO PDF p21: "The net effect of this disconnection has been modelled as a 200MW loss of generation."; OFG PDF p18: "There was a further net reduction in generation of 200MW at 49Hz"; OFG PDF p18: "This figure is net of demand disconnection, such as trains and large industrial customers we are aware of."; OFG PDF p32: "in excess of 200MW of distributed generation tripped off when system frequency reached 49Hz"; Visible/key locators: S06 L58-L61, S06 L94-L97, S06 L108-L110, S12 L39-L42, R06 L111

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b12"></a>

##### SR-B12

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T09.04 · Checklist: B12, B24  

- **Question.** For T09.04, should full credit need both the winter-peak basis of the 5% and an explicit statement that 3.2%/~4% are not comparable with it ('not directly comparable', 'different basis', or a whereas/while/but contrast), with a bare denominator ('3.2% of 29 GW') not enough and 'failed the 5% requirement' scoring 0?
- **Builder choice.** winter_basis + not_equated elements (round 2 and its verification: 'peak forecast demand' accepted, denominator alone no longer counts).
- **Alternatives.** Accept the denominator as implicit non-equivalence; credit the winter basis alone in full.
- **Impact.** T09.04 is 0.5 on sr80k-opus55-001 and sr80k-sonnet55-001 (judge also 0.5), sr30k-opus55-001, sr30k-sonnet55-001 (F20 'the 5% is based on peak forecast demand', 0 → 0.5) and sr30k-haiku45-001; 0 on sr80k-haiku45-001 (judge 0). Under 0.1.0 the pre-screen credited sr80k-opus55-001 1 through '3.2% of 29 GW'; accepting the denominator again would restore that.
- **Evidence.** OFG PDF p34: "This required 5% of winter peak demand to be disconnected."; OFG PDF p34: "On average, the DNOs disconnected an estimated 4% of demand as measured prior to the event"; E3C PDF p16: "The 5% demand figure is based on forecasted peak demand during an average cold spell."; ESO PDF p21: "The DNO’s have indicated that 931MW (3.2%) of demand was automatically disconnected by the operation of the LFDD scheme."; Visible/key locators: R10 L100-L106, S05 L79-L81, S05 L88-L89, S05 L108-L112, R07 L67-L68
- **Compiler's note.** Checklist row B24 is split: this card answers its T09.04 half, SR-B24 its T09.03 half.

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b13"></a>

##### SR-B13

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T12.01a, T12.01b, T12.01c · Checklist: B13  

- **Question.** Should T12.01b (1,022 MW primary) and T12.01c (secondary) earn full credit only with their time band (10 s / 30 s), 0.5 without it?
- **Builder choice.** require_qualifier on RESP_PRIMARY_1022 and RESP_SECONDARY_1314/1338 (band wording), unqualified_level 0.5; T12.01a (1,000 MW secured loss, within 1 MW) needs no band; handoff asks to distinguish the secured loss 'from response capacity in different time bands'.
- **Alternatives.** Credit the figure in full when 'primary'/'secondary' is named (the band is implied by the product definition); require the band only once for both.
- **Impact.** No real run states either band: T12.01b is 0.5 on all six runs although every run states 1,022 MW in a finding; T12.01c is 0.5 on five runs and 0 on sr80k-haiku45-001 (no secondary figure). Dropping the band would move T12.01b to 1 on all six (unattributed counts 1 for T12.01b) and T12.01c to 1 on the four opus/sonnet runs (sr30k-haiku45-001 stays 0.5: unattributed). The grader's basis text ('the figure appears only in the report text') describes an extra report mention, not the reason for 0.5.
- **Evidence.** ESO PDF p24: "At the time of the event the amount of low frequency response being held was 1,022MW primary and 1,314MW secondary."; ESO PDF p36: "It can either be primary response (delivers within 10 seconds) or secondary response (delivers within 30 seconds)."; OFG PDF p26: "Primary response providers (required to deliver a response within 10s) under-delivered by 17% and secondary response providers (required to deliver a response w"; Visible/key locators: R06 L23-L31, R06 L34-L35, R02 L194, R10 L63-L66, R06 L68-L72, S12 L144-L145

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b14"></a>

##### SR-B14

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T12.02 · Checklist: B14, B28  

- **Question.** For T12.02, are the accepted initial-loss figures right (1,481 MW ESO, around 1,500 MW Ofgem 2.4.7, 1,528 MW of Secured Events in Appendix H; 1,878 MW is not the initial loss), and may the exceedance of the secured loss be credited from one report-text phrase while findings keep the factual-status rule?
- **Builder choice.** initial_loss figure (GEN_ESO_1481, GEN_OFG_1500, GEN_APPH_1528) + exceeds_secured (findings) or exceeds_secured_report (report text); cap 0.5 when an initial figure is on another account.
- **Alternatives.** Accept only 1,481 MW; accept 1,131 MW (>1,130 MW within about a second) as the initial loss; credit exceedance only in findings.
- **Impact.** Report-text exceedance moved sr80k-opus55-001 from 0.5 to 1 ('well beyond the secured level'). T12.02 is 1 on opus both and sonnet both, 0.5 on sr30k-haiku45-001 (exceedance with 1,378 MW = Hornsea + Little Barford, no initial figure on a keyed basis), 0 on sr80k-haiku45-001.
- **Evidence.** ESO PDF p12: "16:52:34 Approximately 350MW of embedded generation trips on RoCoF protection [1,481MW cumulative infeed loss]"; OFG PDF p18: "The cumulative loss of generation at this point was around 1,500MW."; APP PDF p56: "The total loss seen through the three Secured Events was significantly in excess of the level secured for (1,000MW) at 1528MW."; Visible/key locators: S06 L48-L49, S12 L21-L22, S12 L29-L38, R06 L20
- **Compiler's note.** Checklist row B28 is split: this card answers its T12.02 half (report-text exceedance), SR-B28 its T08.05 half.

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b15"></a>

##### SR-B15

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T17.03 · Checklist: B15  

- **Question.** For T17.03, should attributing the ~100 MW to embedded generation (E3C) or to a fleet-wide reduction (ESO modelling) be allowed, assigning it to a named unit score 0, and should an executive summary that places it 'at 49 Hz' reduce credit?
- **Builder choice.** about_100 figure + unexplained wording for full; E3C and ESO attributions accepted; named unit 0; the pre-screen does not read the summary misplacement.
- **Alternatives.** Require 'unexplained' only (no attributions); cap at 0.5 when another part of the submission conflates the 100 MW with the 49 Hz stage.
- **Impact.** Open disagreement (decision 43): sr80k-opus55-001 pre-screen 1, judge 0.5 (its summary calls it 'The 100 MW reduction at 49 Hz'); 1 on both sonnet runs and sr30k-opus55-001; 0 on both haiku runs.
- **Evidence.** OFG PDF p18: "There was a reduction in frequency equivalent to a 100MW reduction in generation or increase in demand over 30 seconds."; APP PDF p62: "A 100 MW variation in underlying imbalance which can be attributed to a slight reduction in generation output across the fleet lasting for 30 seconds is also mo"; E3C PDF p12: "This has been attributed to the de-loading or tripping of 100MW of embedded generation but the cause for this loss is unknown at present."; Visible/key locators: S12 L66-L68, S12 L77-L85, S06 L115-L117, R06 L109

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b17"></a>

##### SR-B17

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T12.01a, T12.05, T02.04, T12.01b, T12.01c · Checklist: B17 · Cross-task: [XT-06](#xt-06)  

- **Question.** Should values, times and figures stated only in the report text (not in a finding) be pointed out to the reviewer and never credited automatically (MVP rule)?
- **Builder choice.** Report-only mentions are listed for the reviewer, not credited (exception: T12.02's report exceedance, T03.04/T04.03 method statements and the 'report' field elements).
- **Alternatives.** Credit report-only content at 0.5 or in full; let the judge's reading of report prose stand for auto_assisted_human criteria.
- **Impact.** sr80k-haiku45-001 T12.01a is 0 although its report says ESO was securing for 1,000 MW (judge proposal 1, ignored for auto_assisted_human); sr30k-haiku45-001 T12.05 is 0 with '215 GVAs' only in its report; sr30k-haiku45-001 T02.04 (0.5) lists GT1A/GT1B group times found only in its report. Crediting report text would raise at least T12.01a (haiku80k) and T12.05 (haiku30k).
- **Evidence.** ESO PDF p21: "The largest secured loss on the event day was 1,000 MW."; Visible/key locators: key criteria[].auto figure elements (report_only); R06 L20, R02 L193

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b19"></a>

##### SR-B19

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T06.03 · Checklist: B19 · Cross-task: [XT-11](#xt-11)  

- **Question.** Is the resonance explanation the operator's (Ørsted report, restated by ESO as the operator's statement), so that crediting Ofgem with it is a misattribution (draft said 'restated by ESO and Ofgem')?
- **Builder choice.** Full: resonance and weak network both attributed to the operator's account; Ofgem's findings name only incorrect controller reaction and instability; a resonance credited to Ofgem is a negative example (judge 0, pre-screen 0.5).
- **Alternatives.** Accept Ofgem as a supporting account of the resonance (keep the draft wording).
- **Impact.** T06.03 is 1 on opus and sonnet (both panels) and 0.5 on sr80k-haiku45-001 (pre-screen: resonance and weak network stated without attribution; judge 0.5) and sr30k-haiku45-001 (resonance attributed, weak network not).
- **Evidence.** APP PDF p43: "The de-load was caused by an unexpected wind farm control system response, due to an insufficiently damped electrical resonance in the sub-synchronous frequency"; ESO PDF p20: "the turbine controllers reacted incorrectly due to an insufficiently damped electrical resonance in the"; OFG PDF p29: "The offshore wind turbine controllers, however, reacted incorrectly to voltage fluctuations on the offshore network following the fault."; ESO PDF p20: "was a contributory factor as it created a weak internal network environment"; Visible/key locators: S01 L20, S01 L54-L58, S01 L80-L84, S09 response:S09-ORS-04, S09 response:S09-ORS-06

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b21"></a>

##### SR-B21

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T05.03 · Checklist: B21 · Cross-task: [XT-21](#xt-21)  

- **Question.** For T05.03, should full credit also be given when demand restoration is explicitly scoped to DNO demand, and is 'distinct from the recovery of other affected generation services' without naming transport enough?
- **Builder choice.** full_if_any: (demand_vs_frequency + other_services_scoped) or demand_scoped; 0 for equating frequency recovery with supply restoration or claiming all services recovered.
- **Alternatives.** Require both distinctions in every case; require transport/rail to be named.
- **Impact.** Borderline (decision 43): sr80k-haiku45-001 pre-screen 0.5, judge 1. sr30k-opus55-001 0.5 (other services scoped in the report, frequency distinction not recognised), sr30k-haiku45-001 0; sr80k-opus55-001 moved 0.5 → 1 (F34, scoped to DNO demand); sonnet both 1.
- **Evidence.** ESO PDF p13: "16:57:15 Frequency returns to 50Hz following over 1,000MW of response"; ESO PDF p29: "Post-event analysis indicated the earliest restoration was completed at 17:07 and the last customers were reconnected at 17:37."; APP PDF p72: "The system was returned to a stable position in c. 15 minutes"; Visible/key locators: S07 L34-L36, S07 L39-L40, S07 L116-L119, S12 L140-L143

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b22"></a>

##### SR-B22

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T06.02 · Checklist: B22  

- **Question.** For T06.02, should full credit need, besides both sides, which side behaved as expected (onshore as expected, or offshore controllers reacting incorrectly), with both sides described alone earning 0.5?
- **Builder choice.** which_expected element added in round 2 (expectation's partial: 'both without saying which behaved as expected').
- **Alternatives.** Credit both sides described and kept apart in full.
- **Impact.** T06.02 is 0.5 on sr80k-sonnet55-001 and sr80k-haiku45-001 (judge also 0.5; haiku moved 1 → 0.5 in round 2), sr30k-opus55-001 and sr30k-sonnet55-001; 1 on sr80k-opus55-001 and sr30k-haiku45-001.
- **Evidence.** OFG PDF p29: "the wind farm’s onshore control system operated as expected when the system voltage dipped concurrently with the lightning strike"; OFG PDF p29: "The offshore wind turbine controllers, however, reacted incorrectly to voltage fluctuations on the offshore network following the fault."; Visible/key locators: S01 L30-L33, S01 L39-L40, S01 L59-L61, S01 L86-L88, R05 L43-L54, S09 response:S09-ORS-02, S09 response:S09-ORS-03

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b23"></a>

##### SR-B23

**P1** · 15 min · SR (`gb-2019-system-response`) · Criteria: T08.04, T17.02 · Checklist: B23  

- **Question.** Should the causal-split element of T08.04 and T17.02 need the distributed-generation protection split (RoCoF/vector shift/loss of mains) and the doubt in one sentence, with T17.02 (not T08.04) also accepting ESO's 150/350 MW split as an estimate, and T08.04's telemetry wording within 80 characters of the negation and about distributed generation?
- **Builder choice.** Round-2 patterns: Little Barford 'cause ... unknown' no longer counts; telemetry must name embedded/distributed/DG/loss of mains; the NOT_HELD data-return answer is visible but not citable.
- **Alternatives.** Accept any statement that DG causes are uncertain; give T08.04 the same estimated-split alternative as T17.02.
- **Impact.** T08.04: 1 on sr80k-sonnet55-001, sr30k-opus55-001, sr30k-sonnet55-001; 0.5 on sr80k-opus55-001 (judge 0.5, was 1 via Little Barford wording) and sr30k-haiku45-001; 0 on sr80k-haiku45-001. T17.02: 1 on opus and sonnet (both panels); 0 on both haiku runs (were credited via Little Barford 'cause unknown').
- **Evidence.** OFG PDF p18: "It has not been possibly to fully validate with the DNOs as they also do not monitor output from distributed generators in real-time."; OFG PDF p36: "Most of the DNOs only record information on generation volumes on their networks on a half-hourly basis, obscuring shorter-term events"; ESO PDF p21: "In providing their analysis some DNOs noted challenges in obtaining the data due to the way it is collected or stored and without confirmation from generators"; OFG PDF p36: "we cannot ascertain the resulting volumes of generation output lost at different locations or the cause of these losses with confidence"; Visible/key locators: S06 L22-L24, S06 L29-L39, S06 L62-L63, S06 L104-L107, S12 L132-L134, S09 response:S09-DNO-07, S09 response:S09-DNO-08

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b24"></a>

##### SR-B24

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T09.03 · Checklist: B24  

- **Question.** For T09.03, should the net relief (~350 MW) and the DG disconnected with LFDD (550/581/~600 MW) count in findings of any status, including a labelled hypothesis?
- **Builder choice.** net_relief and dg_at_lfdd figure elements accept observed, reported, inferred, hypothesis and unknown (ESO leaves the LFDD-stage mechanism open).
- **Alternatives.** Count factual findings only.
- **Impact.** Moved sr80k-opus55-001 from 0.5 to 1 (F39 labelled hypothesis; judge 1). T09.03 is 1 on opus and sonnet (both panels), 0 on both haiku runs.
- **Evidence.** OFG PDF p19: "The ESO reported that the net demand reduction seen by the transmission system was only 350MW."; APP PDF p62: "Our modelling indicates that an additional 581 MW of embedded generation was also disconnected"; E3C-I PDF p5: "the ESO Technical Report states that approximately 600MW of embedded generation was also disconnected at this point"; Visible/key locators: S06 L72-L74, S06 L82-L84, S06 L98-L101, S05 L90-L96, R06 L112; accounting LFDD_NET_350, DG_LFDD_550/581/600
- **Compiler's note.** Checklist row B24 is split: this card answers its T09.03 half, SR-B12 its T09.04 half.

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b25a"></a>

##### SR-B25a

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T12.03 · Checklist: B25  

- **Question.** For T12.03, should 'exhausted response' be credited only when said of frequency response or reserve ('all frequency response was already being delivered', 'with all response delivered', 'response already deployed'), not Hornsea's 'insufficiently damped ... response'?
- **Builder choice.** response_exhausted patterns (round 2 + verification); full: subsequent losses and exhausted response.
- **Alternatives.** Accept any statement that response was insufficient for the later losses.
- **Impact.** T12.03 is 0.5 on sr80k-opus55-001, sr80k-sonnet55-001, sr80k-haiku45-001 (judge 0.5 on all three), sr30k-opus55-001 and sr30k-haiku45-001; 1 on sr30k-sonnet55-001 (F16 'with all response delivered at 16:53:31'). 0.1.0 credited opus 1 via Hornsea's control response.
- **Evidence.** ESO PDF p13: "16:53:31 All frequency response is being delivered at this point attempting to restore the frequency to operational limits."; OFG PDF p18: "There was a further net reduction in generation of 200MW at 49Hz"; Visible/key locators: S07 L21-L22, S07 L30-L31, S07 entry:S07-E09, S12 L25-L28, S12 L39-L42, R06 L105-L113

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b25b"></a>

##### SR-B25b

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T02.06 · Checklist: B25  

- **Question.** For T02.06, should 'net effects' mean only the generation net effects (net 200 MW at 49 Hz; ~350 MW net demand change at LFDD), not Ofgem's 892 MW of net demand, with Ofgem's >=1,990 MW as ESO's total or on another stage scoring 0 and ESO's total summed with other-basis figures capped at 0.5?
- **Builder choice.** net_effects text element + ofgem_1990_staged / later_estimates figures; caps ofgem_1990_on_wrong_basis (zero), eso_1878_on_wrong_basis (zero), eso_total_mixed_with_other_bases (cap 0.5), applied also to the judge.
- **Alternatives.** Accept any 'net' figure; cap rather than zero the 1,990 substitution.
- **Impact.** T02.06 is 1 on opus and sonnet (both panels; sonnet80k, opus30k and sonnet30k were falsely zeroed by binding caps under 0.1.0) and 0 on both haiku runs (sr80k-haiku45-001 was 0.5 under 0.1.0 via the 892 MW; judge 0).
- **Evidence.** OFG PDF p18: "The cumulative loss of generation at this point was at least 1,990MW."; OFG PDF p18: "There was a further net reduction in generation of 200MW at 49Hz"; OFG PDF p19: "The ESO reported that the net demand reduction seen by the transmission system was only 350MW."; OFG PDF p19: "892MW of net demand was disconnected in total from the local distribution networks."; Visible/key locators: S12 L29-L46, S06 L94-L101

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b28"></a>

##### SR-B28

**P1** · 20 min · SR (`gb-2019-system-response`) · Criteria: T08.05 · Checklist: B28, C6  

- **Question.** For T08.05 (and the C6 overlap groups), are the bases-distinguished wordings ('differ by stage/basis/method/source', a combined vector-shift and RoCoF loss, a total written as its parts) and the overlap traps (total with its components, two estimates of one loss, ESO's 1,878 MW plus other-basis figures, staging not a trap) right, with an overlapping DG sum setting T08.05 to 0 and capping T02.06/T08.03 at 0.5?
- **Builder choice.** bases_distinguished element; overlap groups lom_total_with_its_components, rocof_alternatives, dg_loss_alternatives, lfdd_stage_dg_alternatives, ofgem_dg_total_with_its_stages (DG wording needed), eso_total_mixed_with_other_bases; labelled terms (up to four words) and prose sums read; a range term in a prose sum is not read (decision 46).
- **Alternatives.** Treat 1,481 + 100 + 210 + 200 as a trap; zero T02.06 on any overlap; read range terms in prose sums.
- **Impact.** T08.05 moved 0 → 1 on sr30k-opus55-001 (F14 'differ by stage', F10 500 = 150 + 350) and sr30k-sonnet55-001 (F09); 1 on both 80k opus/sonnet runs; 0 on both haiku runs. No overlap trap fires on any run.
- **Evidence.** ESO PDF p21: "ESO simulation data indicates that the overall total embedded generation loss could be slightly higher (580MW v 500MW)"; APP PDF p75: "We estimate that approximately 500 MW of embedded generation was lost in the incident."; OFG PDF p32: "Our lower bound for total estimated distributed generation lost across the event is 1,300MW, and the loss could be as high as 1,500MW."; Visible/key locators: S06 L20-L21, S06 L62-L63, S06 L90-L101, S06 L112-L120, S12 L131-L134; accounting.overlap_groups
- **Compiler's note.** Also answers checklist row C6 (overlap groups), which has no card of its own; checklist B28's T12.02 half is SR-B14.

Decision: [ ] accept  [ ] change to: ____

<a id="sr-c0"></a>

##### SR-C0

**P1** · 10 min · SR (`gb-2019-system-response`) · Checklist: C (section introduction)  

- **Question.** Should accounting figures be matched within 1 MW of the printed value (not the 10% MW tolerance), with mentions classified attributed/defined (credited), unattributed (0.5), misattributed or mismatched (0)?
- **Builder choice.** match_abs 1 MW (0.5 MW for 581/580 MW; 0.5-0.6 GVA.s for inertia); wording between two figures split by contrast words; traps cap the criteria in accounting_caps, including the judge's value.
- **Alternatives.** Use the handoff's 10%/25% MW tolerance for printed figures; treat unattributed figures as full credit.
- **Impact.** Keeps 1,878/1,990 and 931/892 from crossing. No accounting trap or cap fires on the six runs under 0.1.1 (12 traps and 6 caps under 0.1.0 were all false positives, decision 41).
- **Evidence.** ESO PDF p26: "The total loss of demand, due to LFDD relay operation was 1,152,878 customers or 931MW, which represents 3.2% of national transmission demand at the time of the event (29GW)."; OFG PDF p19: "892MW of net demand was disconnected in total from the local distribution networks."; Visible/key locators: key accounting.rules; accounting.figures[].match_abs

Decision: [ ] accept  [ ] change to: ____

<a id="sr-c1"></a>

##### SR-C1

**P1** · 15 min · SR (`gb-2019-system-response`) · Criteria: T02.05a, T02.05b, T02.06, T12.02 · Checklist: C1  

- **Question.** Are the generation totals kept on the right bases: 1,878 MW (ESO Table 2, six components through GT1B after LFDD) vs at least 1,990 MW (Ofgem 2.4.11, after GT1A and the 200 MW net at 49 Hz, before LFDD), plus 1,481, ~1,500, >1,130, 1,528, ~2,100 and >=2,000 MW, with 1,990 as ESO's or 1,878 as Ofgem's scoring 0?
- **Builder choice.** Accounting figures GEN_ESO_1878, GEN_OFG_1990, GEN_ESO_1481, GEN_OFG_1500, GEN_1131, GEN_APPH_1528, GEN_E3CI_2100, GEN_E3C_2000; T02.05a needs 1,878 within 1 MW; T02.05b needs its basis (ESO/Table 2, six components, cumulative infeed, including GT1B).
- **Alternatives.** Also key ESO's 1,691 MW (cumulative after GT1A; ESO executive summary and Table 2), which is currently not an accounting figure; accept 1,878 MW without a basis at 0.5 for T02.05b.
- **Impact.** T02.05a/b are 1 on opus and sonnet (both panels) and 0 on both haiku runs. Both sonnet runs state ESO's 1,691 MW after GT1A; it is neither credited nor trapped today.
- **Evidence.** ESO PDF p10: "The second Gas Turbine at Little Barford tripped from 187MW after the initiation of LFDD bringing total generation lost through the event to 1,878MW."; OFG PDF p18: "The cumulative loss of generation at this point was at least 1,990MW."; ESO PDF p4: "This made the cumulative loss of generation 1,691MW."; E3C-I PDF p5: "the total generation lost from the affected power stations, as part of the initial event, was in the region of 2,100MW"; E3C PDF p9: "as part of the initial event, was at least 2,000MW"; Visible/key locators: S12 L15-L28, S12 L34-L46

Decision: [ ] accept  [ ] change to: ____

<a id="sr-c2"></a>

##### SR-C2

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T09.02a, T09.02b · Checklist: C2  

- **Question.** Are the LFDD demand figures kept on their bases: 931 MW (DNO-reported relay disconnection, ESO Table 6, 13 August data, 3.2% of 29 GW; Elexon DCI 931.0) vs 892 MW (Ofgem, net) vs 973 MW (E3C interim table), with 931 called 'net' or given to Ofgem, and 892 given to ESO/DNOs, scoring 0?
- **Builder choice.** LFDD_931, LFDD_OFG_892, LFDD_E3CI_973; T09.02a full when attributed to ESO/DNOs/Elexon or defined; T09.02b full when attributed to Ofgem or defined as net.
- **Alternatives.** Accept 931 MW attributed to Ofgem as 0.5; treat 973 MW as an accepted alternative for T09.02a.
- **Impact.** T09.02a and T09.02b are 1 on all six runs (sr80k-haiku45-001 F33 'Ofgem's final report' was a false misattribution under 0.1.0).
- **Evidence.** ESO PDF p21: "The DNO’s have indicated that 931MW (3.2%) of demand was automatically disconnected by the operation of the LFDD scheme."; OFG PDF p19: "892MW of net demand was disconnected in total from the local distribution networks."; E3C-I PDF p5: "disconnecting approximately 973MW of demand"; Visible/key locators: S05 L35, S05 L61-L65, S05 L83-L87, R07 L36-L38, R07 L67-L68, R07 L85, R07 L108-L113

Decision: [ ] accept  [ ] change to: ____

<a id="sr-c3"></a>

##### SR-C3

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T12.01c · Checklist: C3  

- **Question.** Should secondary holding be kept on two ESO accounts, 1,314 MW (technical report Table 3) vs 1,338 MW (earlier answers to the E3C, Appendix M Q16/Q17, NED data at 28 August), with a figure attributed to the other account capped at 0.5?
- **Builder choice.** RESP_SECONDARY_1314 and RESP_SECONDARY_1338, each full on its own account (with the 30 s band); cap secondary_on_wrong_account 0.5 (the key's expectation text says 0).
- **Alternatives.** Treat 1,338 MW as superseded (credit only 1,314 MW); zero a figure on the other account as the expectation text says.
- **Impact.** No run attributes either figure to the wrong account; sr30k-opus55-001 F16 ('ESO's earlier E3C answer gives 1,338 MW') was a false cap under 0.1.0. Values follow SR-B13 (0.5 on five runs). To confirm: a misattributed mention scores 0 through the element level (as the expectation says), while the accounting cap secondary_on_wrong_account is only cap_half, which matters when another mention would otherwise earn credit.
- **Evidence.** ESO PDF p24: "At the time of the event the amount of low frequency response being held was 1,022MW primary and 1,314MW secondary."; APP PDF p81: "Total 1076[1494] 1022 [1338] 1281[1761] Source of data: NED system"; Visible/key locators: R06 L31, R06 L34-L35, R06 L68-L72, R06 L92, S12 L144-L145

Decision: [ ] accept  [ ] change to: ____

<a id="sr-c4"></a>

##### SR-C4

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T12.05 · Checklist: C4  

- **Question.** Are the inertia bases right: 210 GVA.s (ESO Table 4, 9 August) vs 219,632 MVA.s (ESO answer 42, immediately before the trip, a model estimate), with NESO's modelled outturn 215 for settlement period 34 (unit not stated) accepted as a third basis and values compared within 0.5-0.6 GVA.s?
- **Builder choice.** INERTIA_ESO_210, INERTIA_ESO_219632, INERTIA_NESO_215; full: a figure attributed to its own account; 0.5 without account; 0 on the other account.
- **Alternatives.** Exclude the NESO 215 (unitless dataset) or credit it only at 0.5; widen the match to accept 'about 210-220 GVA.s'.
- **Impact.** T12.05 values in SR-A7. Credited mentions: sr80k-opus55-001 F22 (210 GVA.s Table 4 and 219,632 MVA.s; F43 adds 215 'in the NESO file'), sr80k-sonnet55-001 F24, sr30k-opus55-001 F17, sr30k-sonnet55-001 F17 (210 GVAs), sr80k-haiku45-001 F28 (219.6 GVA.s 'approximately ... estimated', classified defined); sr30k-haiku45-001's 215 GVAs is report-only (0).
- **Evidence.** ESO PDF p23: "01 July 09 August Demand 28 GW 29 GW Inertia 201 GVAs 210GVAs"; APP PDF p90: "16:52 Immediately prior to the trip 219632"; APP PDF p90: "The ESO does not currently measure system inertia directly but instead estimates it using a model."; Visible/key locators: R02 L164-L176, R02 L192, R02 L201-L207, S12 L112-L118, S12 L146-L147 (NESO dataset is real data, no PDF passage)

Decision: [ ] accept  [ ] change to: ____

<a id="sr-c5"></a>

##### SR-C5

**P1** · 25 min · SR (`gb-2019-system-response`) · Criteria: T02.01a, T02.01b, T08.01, T08.02, T08.03, T08.05, T09.03, T17.02, T17.03 · Checklist: C5  

- **Question.** Is the distributed-generation figure list complete and on the right bases: 150 MW vector shift and 350 MW RoCoF (ESO estimates), 430 MW (App I simulation), 350-430 MW (Ofgem/E3C), ~500 MW loss of mains (ESO, metered flows), 580 MW (modelled), 462 MW (DNO returns), 200 MW net at 49 Hz, ~550 (Ofgem)/581 (modelled)/~600 MW (E3C interim) at LFDD with 350 MW net relief, 1,300-1,500 MW (Ofgem total), ~100 MW unexplained?
- **Builder choice.** One accounting figure per published estimate with sources, wrong_sources (e.g. DNO for 150/350), definition and qualifier patterns.
- **Alternatives.** Merge estimates of the same loss into one figure with alternatives; add figures not keyed (e.g. ESO's 1,131 MW interim cumulative is keyed, 1,691 MW is not).
- **Impact.** Drives T02.01, T08.02, T08.03, T08.05, T09.03, T17.02, T17.03 on all six runs; no DG figure is trapped on any run (sr30k-sonnet55-001 F09's 150 MW was falsely bound to the DNOs under 0.1.0).
- **Evidence.** ESO PDF p21: "ESO simulation data indicates that the overall total embedded generation loss could be slightly higher (580MW v 500MW)"; OFG PDF p19: "The ESO reported that the net demand reduction seen by the transmission system was only 350MW."; E3C PDF p12: "The final loss, as reported in the ESO Technical Report, of 550MW occurred when the LFDD scheme was triggered."; OFG PDF p18: "As a result, an estimated 350- 430MW of distributed generation tripped off unnecessarily, based on information provided by the ESO"; Visible/key locators: S06 Part 3 E1-E23 (L46-L120); S12 L19-L22, S12 L131-L134; accounting.figures DG_*

Decision: [ ] accept  [ ] change to: ____

<a id="sr-c7"></a>

##### SR-C7

**P1** · 60 min · SR (`gb-2019-system-response`) · Criteria: T02.06, T09.02a, T09.02b, T12.01c, T12.02, T02.05b · Checklist: C7  

- **Question.** Are the source-binding rules right (nearest attribution: own side, coordinated figures, preceding figure of the sub-clause, citation parenthesis, list head, clear preceding source; contrasts and 'whereas/while/but/below/above/exceeds' as barriers; specific beats generic; a bare 'final report' belongs to the source named with it, else ESO; 'X and Y MW' a range only after 'between'), including the unchanged rule that a colon head attributes its whole sentence?
- **Builder choice.** sr_accounting binding as in checklist C7 and decisions 41 and 46; reviewed against tests/test_sr_grading_accounting.py examples.
- **Alternatives.** Simpler sentence-level binding that sends every multi-source sentence to a human; stop a colon head at the first clause boundary.
- **Impact.** Under 0.1.0 all 12 accounting traps and 6 caps on the six runs were false positives (e.g. sr80k-sonnet55-001 F17 'Ofgem: >1,130 MW ...' zeroed T02.06 and halved T12.02); under 0.1.1 none remain, and mutations giving Ofgem's figures to ESO, 892 MW to ESO's final report, 1,338 MW to Table 3, 150 MW to the DNOs or 931 MW a 'net' basis still trap (tests). Open: 'Ofgem: ... reached 1,878 MW' still traps through the colon head.
- **Evidence.** OFG PDF p18: "The cumulative loss of generation at this point was around 1,500MW."; OFG PDF p18: "The cumulative loss of generation at this point was at least 1,990MW."; Visible/key locators: tests/test_sr_grading_accounting.py (test_figures_bind_to_the_nearest_attribution, test_wrong_attributions_still_trap, test_a_generic_final_report_belongs_to_the_source_named_with_it); DECISIONS 41, 46

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t01.03"></a>

##### SR-D-T01.03

**P1** · 5 min · SR (`gb-2019-system-response`) · Criteria: T01.03a, T01.03b · Checklist: D (rows T01.03a, T01.03b) · Cross-task: [XT-02](#xt-02)  

- **Question.** Are T01.03a (single blue phase to earth) and T01.03b (main protection cleared in 70 ms at Wymondley Main and 74 ms at Eaton Socon, ±1 ms, within 80 ms; one end or Ofgem's 'under 75 ms' 0.5) right?
- **Builder choice.** Split T01.03 into fault type and clearance times; ±1 ms on printed protection times is a builder choice; three-phase/phase-to-phase contradiction rule on T01.03a.
- **Alternatives.** ±5 ms; give 'under 75 ms' full credit as Ofgem's account; require the 80 ms Grid Code requirement for full.
- **Impact.** T01.03a and T01.03b are 1 on all six runs; T01.03b matches the MVP D1.3 result on the four MVP v2 runs.
- **Evidence.** APP PDF p17: "The main protection at Wymondley Main operated in 70ms"; APP PDF p17: "the main protection at Eaton Socon operated in 74ms"; APP PDF p26: "(i) 80ms at 400kV (400,000 volts)"; OFG PDF p28: "its fault clearance times for the two circuit breakers were under 75ms"; ESO PDF p12: "16:52:33.490 A single (blue) Phase to Earth fault on Eaton Socon - Wymondley circuit"; Visible/key locators: R03 L36-L37, R03 L43-L48, R03 L86-L88, R03 event:R03-C1, R03 event:R03-C5, R03 event:R03-C6, S09 response:S09-NGET-01

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t03"></a>

##### SR-D-T03

**P1** · 15 min · SR (`gb-2019-system-response`) · Criteria: T03.01, T03.02, T03.03 · Checklist: D (rows T03.01, T03.02, T03.03) · Cross-task: [XT-06](#xt-06)  

- **Question.** Should the R01 landmarks (49.083 Hz at 16:52:59, 48.787 Hz at 16:53:49, 50.001 Hz at 16:57:16; 0.002 Hz and one sample) send rounded or prose candidates (ESO's 49.1 Hz at 16:52:58) to a human instead of an automatic 0, and should a wrong structured value with a correct value elsewhere in the submission stay an automatic 0 with a note (decision 27's open choice)?
- **Builder choice.** auto_numeric from frozen R01; automatic 0 only for a genuine omission or an out-of-tolerance structured quantity in the window with nothing else in its finding within tolerance; other candidates to a human; ESO's 49.1 Hz, the 48.8 Hz trigger and E3C's 48.792 Hz are not within tolerance.
- **Alternatives.** Auto-fail rounded prose values; accept ESO's 49.1 Hz at 16:52:58 as a reported alternative at 0.5; overrule the automatic 0 when a correct value appears in another finding.
- **Impact.** T03.01 is pending a human with proposal 0 on sr80k-haiku45-001 (F24 'arresting the frequency drop at approximately 49.1 Hz by 16:52:58', off by 0.017 Hz) and sr30k-haiku45-001 (best candidate off by 0.117 Hz); decided 1 on the other four. T03.02 and T03.03 are decided 1 on all six.
- **Evidence.** ESO PDF p12: "16:52:58 Frequency drop is arrested at 49.1Hz due to the delivery of frequency response products"; ESO PDF p13: "16:57:15 Frequency returns to 50Hz following over 1,000MW of response"; E3C-I PDF p11: "when the system frequency fell to 48.792Hz, not all schemes were triggered"; Visible/key locators: R01 time:16:52:45-16:53:10 BST, row:780; time:16:53:20-16:54:30, row:830; time:16:57:10-16:57:20, row:1037; key conventions.unit_note; DECISIONS 27

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t04.03"></a>

##### SR-D-T04.03

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T04.03 · Checklist: D (rows T04.03) · Cross-task: [XT-05](#xt-05)  

- **Question.** Is the T04.03 pre-screen right in needing the duration convention (threshold or method), the 1-s sampling and the sub-second limit, with a sub-second crossing claimed as measured capping at 0.5, and should 'below 49 Hz threshold with elapsed-timestamp subtraction' count as a stated convention?
- **Builder choice.** Convention patterns (strictly below, at or below, zero-order hold, interpolation, sample count ...); any field incl. report text; MVP D3.5 parity.
- **Alternatives.** Accept any stated computation method as the convention; drop the cap.
- **Impact.** sr80k-haiku45-001 is 0.5 (sampling and sub-second limit found, convention not recognised) while the judge's recorded proposal is 1 ('below-49-Hz threshold and an elapsed-timestamp subtraction method'); 1 on the other five runs.
- **Evidence.** ESO PDF p13: "16:53:49.398 Frequency breaches 48.8Hz trigger level resulting in LFDD."; Visible/key locators: R01 L22-L23, R01 L28-L29

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t06.01"></a>

##### SR-D-T06.01

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T06.01 · Checklist: D (rows T06.01) · Cross-task: [XT-11](#xt-11)  

- **Question.** For T06.01, should full credit need the controller reaction/instability plus the protective (overcurrent) de-load, with the weak network moved to T06.03/T16.03 (intended divergence from MVP D4.1), and is 'inappropriate protection actions' without overcurrent enough?
- **Builder choice.** Elements control_resonance or instability + overcurrent_deload; DRC as established cause caps at 0.5.
- **Alternatives.** Accept any protective de-load wording; restore MVP D4.1's weak-network element.
- **Impact.** Borderline (decision 43): sr80k-haiku45-001 pre-screen 0.5, judge 1 (no overcurrent; 'inappropriate protection actions'). 1 on the other five runs. On MVP v2 haiku45-001, T06.01 1 vs D4.1 0.5.
- **Evidence.** APP PDF p41: "all WTGs on Hornsea 1B and Hornsea 1C reduce to 0MW as a result of overcurrent protection in the generators"; OFG PDF p29: "The instability triggered two modules to automatically shut down."; APP PDF p43: "The de-load was caused by an unexpected wind farm control system response, due to an insufficiently damped electrical resonance in the sub-synchronous frequency"; Visible/key locators: S01 L39-L40, S01 L56-L58, S01 L62-L64, S01 L82-L88, S09 response:S09-ORS-03

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t06.04"></a>

##### SR-D-T06.04

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T06.04 · Checklist: D (rows T06.04)  

- **Question.** Should T06.04 need both the earlier oscillation (~10 minutes before, no de-load) and the known modelling concern (manufacturer modelling at 1,200 MW not discussed with the ESO) for full credit, one for 0.5?
- **Builder choice.** full: earlier_oscillation + modelling_concern; partial: one; 'where supplied' satisfied because both are in S01/S09.
- **Alternatives.** Accept Ørsted's earlier consideration of oscillations (S01 L72-L74) as the modelling concern; give full credit for either.
- **Impact.** 0 on sr80k-opus55-001 (judge 0), sr30k-opus55-001 and sr30k-haiku45-001 (neither element stated); 0.5 on sr80k-haiku45-001; 1 on both sonnet runs.
- **Evidence.** OFG PDF p29: "had occurred around ten minutes prior to the incident on 9 August but had not caused de-loading at that time"; OFG PDF p29: "These issues were not discussed with the ESO."; APP PDF p42: "Showing the reactive power output from Hornsea 10 minutes prior to the event in response to a 2% voltage step change"; Visible/key locators: S01 L26-L27, S01 L68-L74, S01 L89-L93, S01 event:S01-EV01, S09 response:S09-ORS-07, S09 response:S09-ORS-09
- **Compiler's note.** Priority raised from P2 to P1 on review: values differ across the six runs (0, 0.5, 1), and full credit for either element would move sr80k-haiku45-001 from 0.5 to 1.

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t07.01"></a>

##### SR-D-T07.01

**P1** · 5 min · SR (`gb-2019-system-response`) · Criteria: T07.01 · Checklist: D (rows T07.01) · Cross-task: [XT-07](#xt-07)  

- **Question.** Should T07.01 credit the ST1C trip on a speed-signal discrepancy without the word 'three', and in a finding labelled unknown when one sentence states it without hedging?
- **Builder choice.** Mechanism patterns (MVP D4.2 with paraphrases) accept 'discrepancy in the speed signals' without 'three'; unknown-status findings count (conventions.mechanism_status); hypothesis never counts.
- **Alternatives.** Require 'three' sensors/signals (handoff: 'three-sensor speed discrepancy'); count factual findings only.
- **Impact.** T07.01 is 1 on all six runs. sr80k-opus55-001's recorded judge proposal is 0.5 ('Neither specifies three sensors'), ignored because T07.01 is auto_assisted_human; requiring 'three' would make it 0.5.
- **Evidence.** OFG PDF p31: "We have established that the steam turbine tripped initially because of a discrepancy in the three independent speed sensors on the turbine."; APP PDF p46: "Our investigations have confirmed that the Steam Turbine tripped due to a discrepancy in the speed signals after the point of the Transmission System fault clea"; Visible/key locators: S03 L42-L43, S04 L46-L47, S04 L56-L58, S09 response:S09-RWE-03

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t07.05"></a>

##### SR-D-T07.05

**P1** · 5 min · SR (`gb-2019-system-response`) · Criteria: T07.05 · Checklist: D (rows T07.05) · Cross-task: [XT-07](#xt-07)  

- **Question.** For T07.05, should a submission that offers no Little Barford explanation but asserts nothing earn 0.5 (full needs at least one explanation labelled hypothesis or attributed as a view)?
- **Builder choice.** full: hypothesis_labelled or view_attributed (UPS, Ofgem's preliminary view, ESO's bypass valve); half: any Little Barford mention; SF1 confirmed → 0.
- **Alternatives.** Give silence 1 (nothing mislabelled) or 0 (nothing labelled).
- **Impact.** sr30k-haiku45-001 is 0.5 (no explanation offered); the other five runs 1 (sonnet80k restored from 0 after the false SF1).
- **Evidence.** APP PDF p45: "RWE’s hypothesis is that the UPS’ have initiated a changeover to battery back-up supplies as a consequence of the system disturbance."; APP PDF p45: "Therefore, we do not now believe the UPS’ were related to the subsequent trip."; OFG PDF p31: "it is our preliminary view that the steam turbine’s anomalous speed readings and the resulting trip were due to the transmission network fault following the lightning strike"; Visible/key locators: S03 L58-L60, S04 L38-L44, S04 L64-L66, S12 L148-L152, S09 response:S09-RWE-06

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t08.03"></a>

##### SR-D-T08.03

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T08.03 · Checklist: D (rows T08.03)  

- **Question.** For T08.03, should Ofgem's 1,300-1,500 MW attributed to Ofgem/E3C but without estimate wording earn only 0.5, given that the DG_TOTAL_1300_1500 qualifier list (unlike DG_ROCOF_350_430) does not accept a written range ('1,300-1,500 MW') as estimate wording?
- **Builder choice.** require_qualifier with estimate wording ('estimat', 'lower bound', 'as high as', 'could be', 'range', 'between' ...); a numeric range pattern is a qualifier for the RoCoF range but not for the DG total; 0 when presented as measured or attributed to ESO/DNOs; overlap sum caps 0.5.
- **Alternatives.** Accept an attributed range as an estimate (add the numeric-range pattern used for DG_ROCOF_350_430); require 'lower bound' wording for full.
- **Impact.** sr80k-opus55-001 F12 ('Ofgem and the E3C put total embedded generation lost at 1,300-1,500 MW') and sr30k-sonnet55-001 F10 ('... at 1,300-1,500 MW') are 0.5 (attributed, not qualified); adding the range pattern would make both 1. 1 on sr80k-sonnet55-001 and sr30k-opus55-001; 0 on both haiku runs.
- **Evidence.** OFG PDF p32: "Our lower bound for total estimated distributed generation lost across the event is 1,300MW, and the loss could be as high as 1,500MW."; Visible/key locators: S06 L102-L103, S06 L119-L120; accounting DG_TOTAL_1300_1500.qualifier_any vs DG_ROCOF_350_430.qualifier_any

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t12.04"></a>

##### SR-D-T12.04

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T12.04 · Checklist: D (rows T12.04)  

- **Question.** For T12.04, should full credit need an explicit statement that under-delivery was not the sole cause (e.g. Ofgem 3.12), rather than merely not asserting it, with an assertion that it caused LFDD capped at 0.5?
- **Builder choice.** full: shortfall + not_sole_cause wording ('not sufficient', 'would not have prevented', 'broadly in line', 'alone' ...); half: shortfall only.
- **Alternatives.** Read the handoff literally ('without asserting they alone caused LFDD'): full when the shortfall is identified and no causal assertion is made.
- **Impact.** sr80k-opus55-001 is 0.5 (judge 0.5) and sr30k-haiku45-001 0.5 under the explicit-statement reading; both would be 1 under the literal reading. 1 on sr80k-sonnet55-001, sr30k-opus55-001, sr30k-sonnet55-001; 0 on sr80k-haiku45-001.
- **Evidence.** OFG PDF p27: "We do not believe that better response and reserve delivery would have been sufficient to prevent demand from being disconnected for this event."; ESO PDF p24: "Of the validated response holding the ESO can confirm that 89% of primary (841MW) and 88% of secondary (1055MW) response performed as expected"; Visible/key locators: R06 L36-L41, R06 L44-L53, R06 L85-L92, S12 L95-L97, S12 L104-L109

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t16.01"></a>

##### SR-D-T16.01

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T16.01 · Checklist: D (rows T16.01) · Cross-task: [XT-12](#xt-12)  

- **Question.** Should T16.01 be positive (the other lightning trips must be named and ruled out by timing and impact; omission scores 0) rather than MVP D1.N's negative polarity (1 unless another trip is presented as the initiator)?
- **Builder choice.** Positive polarity: others_ruled_out + timing_or_impact for full; one of the two 0.5; another trip as initiator 0 (intended divergence from D1.N).
- **Alternatives.** Keep D1.N's negative polarity; give omission 0.5.
- **Impact.** 0 on sr80k-opus55-001 (judge 0), sr80k-haiku45-001 (judge 0) and sr30k-haiku45-001, none of which mention the Harker or Blyth trips; 1 on both sonnet runs and sr30k-opus55-001. Under D1.N those three would be 1 (MVP v2 runs: T16.01 0/0.5 vs D1.N 1 on all four).
- **Evidence.** ESO PDF p15: "At 14:23hrs, the Harker – Stella West 275kV circuit was also tripped and automatically returned to service."; ESO PDF p15: "At 16:50:44hrs, a lightning struck the Blyth – Eccles – Stella West 400kV circuit near Longframlington, Northumberland."; APP PDF p85: "At 16:43:25, the Blyth – Eccles – Stella West 1 400kV circuit tripped and was likewise returned to service via DAR at 16:43:54."; Visible/key locators: R03 L22-L33, R03 L67-L77

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t16.03"></a>

##### SR-D-T16.03

**P1** · 10 min · SR (`gb-2019-system-response`) · Criteria: T16.03 · Checklist: D (rows T16.03)  

- **Question.** Should T16.03 full credit require the planned Killingholme-Keadby outage to be named and ruled non-causal, with the Hornsea internal weakness alone earning 0.5?
- **Builder choice.** full: internal_weakness + transmission_outage_noncausal; half: internal weakness only; 0: wider outage blamed for the de-load.
- **Alternatives.** Credit the internal weakness attributed to the operator in full when no external outage is blamed (the evidence for the outage is one NGET appendix line and a witness answer).
- **Impact.** T16.03 is 0.5 on all six runs (judge 0.5 on the three 80k runs): no run mentions Killingholme-Keadby. The alternative would move all six to 1.
- **Evidence.** APP PDF p30: "it is connected to the Killingholme - Keadby circuit which was out of service for planned maintenance on 9th August."; ESO PDF p20: "with one SGT and one offshore transmission system user asset (OTSUA Circuit) on outage"; APP PDF p21: "This restored the network to the same configuration seen prior to the event."; Visible/key locators: R03 L18-L19, R03 L51-L53, S01 L20, S01 L80-L81, S09 response:S09-ORS-06, S09 response:S09-NGET-06

Decision: [ ] accept  [ ] change to: ____

<a id="sr-e1"></a>

##### SR-E1

**P1** · 20 min · SR (`gb-2019-system-response`) · Criteria: T07.01, T07.02, T07.03, T07.04, T07.05, T17.01 · Checklist: E1 · Cross-task: [XT-08](#xt-08)  

- **Question.** Is the SF1 definition and heuristic right: an asserted Little Barford root cause (faulty sensor, failed valve, UPS, transmission fault as established cause) fires; ESO's bypass-valve wording attributed to ESO is excused (only that wording); a failure must be said of the sensor within 30 characters ('fault' only as the sensor's own), so the trip mechanism does not fire; a hedge or 'unknown' anywhere in the same sentence excuses it; confirmed SF1 zeroes T07.04, T07.05, T17.01 and a suspected SF1 bounds the judge at 0?
- **Builder choice.** MVP SF1 plus round-2 and verification changes (decisions 42, 47); remaining limit: sentence-level hedge excuse.
- **Alternatives.** Check hedges only in the clause carrying the assertion; excuse any attribution to a named source; do not bound the judge until a human confirms.
- **Impact.** No SF1 on any of the six runs; four trigger hits (ESO-summary valve attributions) are excused. Under 0.1.0 a false SF1 on sr80k-sonnet55-001 F08 ('speed sensors after fault clearance') zeroed T07.01 and capped T07.04, T07.05, T17.01 (now 1, 0.5, 1, 0.5).
- **Evidence.** ESO PDF p4: "following the failure of a bypass valve to operate correctly"; OFG PDF p31: "The root cause of the discrepancy in the speed sensors has not been established."; OFG PDF p31: "it is our preliminary view that the steam turbine’s anomalous speed readings and the resulting trip were due to the transmission network fault following the lightning strike"; APP PDF p45: "Therefore, we do not now believe the UPS’ were related to the subsequent trip."; Visible/key locators: key severe_flags[SF1]; S12 L148-L152 (F7); S04 L46-L51; tests test_plainly_asserted_root_causes_raise_sf1

Decision: [ ] accept  [ ] change to: ____

<a id="sr-e2"></a>

##### SR-E2

**P1** · 5 min · SR (`gb-2019-system-response`) · Checklist: E2 · Cross-task: [XT-09](#xt-09)  

- **Question.** Is SF2 right: evidence IDs outside the bundle (S02, S08, R09) and record IDs shaped like the bundle's that no tool returns (e.g. S07-E14) are flagged, while line labels ('S03 E7') and labelled document lines ('R03-C2', 'R03-B5') are not?
- **Builder choice.** record_id_pattern and record_ref_pattern checked against every citable ID and record ID of bundle 0.1.0.
- **Alternatives.** Flag only cited IDs (not prose mentions); flag any unknown record-shaped reference including line labels.
- **Impact.** No SF2 candidate on any of the six runs (every cited ID exists).
- **Evidence.** No source passage (process or grader rule). Visible/key locators: key severe_flags[SF2] examples/non_examples
- **Compiler's note.** Priority raised from P2 to P1 on review: severe-flag definitions are P1 by this pack's rule, as MVP-C4, FI-E2 and FI-E3 are.

Decision: [ ] accept  [ ] change to: ____

<a id="sr-e3"></a>

##### SR-E3

**P1** · 5 min · SR (`gb-2019-system-response`) · Checklist: E3 · Cross-task: [XT-09](#xt-09)  

- **Question.** Is SF3 right: an official enforcement outcome (fine, penalty, redress, settlement) asserted is flagged because the system-response bundle holds none, with pound signs in price/cost contexts (GBP/MWh, balancing costs, settlement periods) exempt?
- **Builder choice.** MVP SF3 with price/cost exemptions (round 1).
- **Alternatives.** Allow enforcement outcomes attributed to outside knowledge; drop SF3 for this task.
- **Impact.** No SF3 candidate on any of the six runs. The extracted Ofgem report text contains no 'redress' wording, consistent with the bundle holding no enforcement outcome.
- **Evidence.** No source passage (process or grader rule). Visible/key locators: key severe_flags[SF3]; R06 system prices (GBP/MWh)
- **Compiler's note.** Priority raised from P2 to P1 on review: severe-flag definitions are P1 by this pack's rule, as MVP-C4, FI-E2 and FI-E3 are.

Decision: [ ] accept  [ ] change to: ____

<a id="sr-e4"></a>

##### SR-E4

**P1** · 5 min · SR (`gb-2019-system-response`) · Checklist: E4 · Cross-task: [XT-10](#xt-10)  

- **Question.** Should severe flags be confirmed only by humans, with judge suggestions recorded for adjudication and no run-level pass/fail?
- **Builder choice.** Judge severe-flag output is a suggestion; a suspected SF1 bounds judge proposals until a reviewer rejects it.
- **Alternatives.** Let a high-confidence judge suggestion confirm a flag.
- **Impact.** No suspected severe flag on the six runs, so nothing awaits adjudication.
- **Evidence.** No source passage (process or grader rule). Visible/key locators: key severe_flags[].effect_when_confirmed; judge.note
- **Compiler's note.** Priority raised from P3 to P1 on review: severe-flag rules are P1, as MVP-C6 and FI-B8 are. The suspected-flag bound on the judge moved six values on the FI panel run under key 0.1.0 (XT-10).

Decision: [ ] accept  [ ] change to: ____

#### FI — `gb-2019-full-investigation` (key 0.1.1) — P1, 34 items, 14 h 55 min

<a id="fi-a1"></a>

##### FI-A1 — Whole key: criteria set and field splits

**P1** · 30 min · FI (`gb-2019-full-investigation`) · Criteria: T10.02a, T10.02b, T10.02c, T10.03a, T10.03b, T10.05a, T10.05b, T10.05c, T11.01a, T11.01b, T15.01a, T15.01b, T15.01c · Checklist: A1  

- **Question.** Do the 106 criteria (60 re-bound plus 46 new, none deferred) fairly implement handoff T01–T20, including splitting T10.02, T10.03, T10.05, T11.01 and T15.01 into a/b/c fields with equal subweights?
- **Builder choice.** Every handoff criterion is implemented and `deferred_criteria` is empty. Compound criteria are split into fields with equal subweights, described as 'a reporting convenience only' because no total is computed. The splits go beyond numeric compounds: T10.05c (judge: attribute inconsistent counts) and T15.01c (judge: contact sequence) each take a third of their handoff criterion. T15.01's 'reconstruct the sequence' becomes two timestamp checks (a, b) plus the sequence (c).
- **Alternatives.** Split only compound numeric criteria, as the handoff's scoring contract says. Keep T10.05 and T15.01 as single criteria. Give the narrative field more weight than the timestamps. Split T11.01 differently (see FI-B6).
- **Impact.** Weights matter only if a task total is ever computed (none is; see FI-A6). On the pilot (fi-pilot-opus55-001), T10.05a/b/c and T15.01a/b/c are all 1 on both pre-screen and judge, so the split changes nothing there. On increment A's six runs (tests/fixtures/sr_live), T10.05a/b and T15.01a/b are all 0 because those runs have no rail or communications content.
- **Evidence.** Handoff IMPLEMENTATION_SPEC, 'Scoring contract': 'Before release, split compound numeric criteria into explicit fields in private_key with equal subweights.' task_blueprint.json gives T10 five criteria at 1/5 each and T15 four at 1/4 each. Key: `scope` ('Compound criteria are split into fields ... equal subweights as a reporting convenience only'), `new_criteria`, `deferred_criteria: []`. REVIEW_CHECKLIST.md A1.
- **Compiler's note.** Installed FI key 0.1.1 (decisions 77–80; FI checklist B19): T15.01c's full credit now also needs the 17:10 internal escalation; the pilot values quoted here are from key 0.1.0.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-a3"></a>

##### FI-A3 — Whole key: expected values vs report passages; disagreeing sources kept

**P1** · 60 min · FI (`gb-2019-full-investigation`) · Criteria: T10.02a, T10.02b, T10.02c, T10.03a, T10.05c, T15.01a, T15.02 · Checklist: A3 · Cross-task: [XT-19](#xt-19)  

- **Question.** Does every expected value agree with its report passages, and should disagreeing figures stay with their sources (ORR vs GTR/ESO rail counts; 17:51 vs 18:00 for the first Ofgem contact; 17:40 vs 17:41 for BEIS) rather than one being chosen?
- **Builder choice.** Each expected value is tied to verbatim passages. Discrepant counts and times are kept with their sources: ORR's 29/22/7/31 are the expected counts, and other accounts' counts are attributed alternatives. T15.02 requires both Ofgem-contact times. T15.01a accepts either BEIS time.
- **Alternatives.** Pick one preferred source per figure, e.g. ORR only for rail counts, or ESO 6.2's 17:51 only. Alternatively, require the BEIS 17:40/17:41 discrepancy to be kept as well.
- **Impact.** This decides credit for T10.02–T10.05, T15.01a and T15.02. The pilot keeps both sets of rail counts (F28) and both Ofgem times (F34), and gets 1 on each.
- **Evidence.** The builder re-checked all 581 report_passages in answer_key.json against .context/handoff/text/*.txt: every quote occurs on its stated PDF page (whitespace-normalised; 0 misses). Examples: ORR p3 'causing a lock-out of 29 trains. 22 trains were permanently locked-out and could not be reset without a technician attending on site while 7 trains were restored through driver-reset'; APP p48 'In Passenger Service this involved circa 60 units ... suffering a 4QC lock out.'; ESO p30 'The first communication with Ofgem was made at 17:51hrs'; ESO p33 'The ESO contacted BEIS at 17:40 and Ofgem at 18:00.'; APP p88 'The 1st communication with Ofgem was made just after 18:00hrs'. Visible: S08 L120-L127 (O02), S08 L22-L23 (G04), R09 L25-L37, entries R09-A1-2 and R09-A2-2.
- **Compiler's note.** First person replaced (the earlier verifier).

Decision: [ ] accept  [ ] change to: ____

<a id="fi-a4"></a>

##### FI-A4 — Whole key: no enforcement outcome or legal clause required or supplied

**P1** · 15 min · FI (`gb-2019-full-investigation`) · Criteria: T14.04, T14.05 · Checklist: A4 · Cross-task: [XT-09](#xt-09)  

- **Question.** Is it right to exclude Ofgem's January 2020 settlements from the evidence (asserting them is SF3) and never to score legal clause recall, with clause numbers in S10/R10 appearing only as Ofgem cites them?
- **Builder choice.** The settlements are excluded and Ofgem section 4 is dropped whole (decisions 50, 57); they stay in private provenance as a leakage detector. No clause number is ever required. T14.04 and T14.05 expect no outcome to be claimed.
- **Alternatives.** Include the settlements as evidence and score T14 on them (the version-1 handoff approach, removed in version 2). Alternatively, score clause recall once the 2019 code editions are verified.
- **Impact.** No SF3 fires on the two FI runs or on increment A's six runs, so no current grade changes. This decision governs SF3 and the T14.04/T14.05 zero routes for the live panel.
- **Evidence.** Handoff spec: 'Remove future settlement amounts from T14'; 'Exact legal clause scoring and ESQCR duties are excluded until separately verified.' ORR p11: 'So far, ORR has not been able to establish any non-compliance with The Railways (Interoperability) Regulations 2011, as amended, that could warrant an enforcement action.' DECISIONS 50 and 57. Visible: S08 L217-L219 (O22), R09 L453-L465 (Ofgem's 20 August press release: 'does not imply that Ofgem has made any findings').

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b1"></a>

##### FI-B1 — T04.03 and T05.03 restored to the handoff wording

**P1** · 30 min · FI (`gb-2019-full-investigation`) · Criteria: T04.03, T05.03 · Checklist: B1 · Cross-task: [XT-21](#xt-21)  

- **Question.** Should T04.03 name the 200 ms claim (S08 spans context only), and T05.03 require demand restoration to be kept distinct from the later transport recovery, treating the Victoria line's 17:35 resumption as a separate non-LFDD recovery?
- **Builder choice.** T04.03's rules and tolerances are unchanged; the expectation now names 200 ms, which the existing contradiction rule already caps. T05.03 gains a `transport_later` pre-screen route and rail-recovery spans. The Victoria line is a context span and its resumption is excused by the contradiction rule. Note a mismatch: the expectation says 'demand restoration distinguished from the later transport recovery' alone is full, but the pre-screen's full routes need demand_vs_frequency+transport_later, demand_vs_frequency+other_services_scoped, or demand_scoped.
- **Alternatives.** Give pre-screen full for 'demand vs later transport' alone, matching the expectation text. Alternatively, require the frequency distinction as well, or treat the Victoria line as a transport recovery that must be dated later.
- **Impact.** Pilot: T04.03 pre-screen 1. T05.03 pre-screen 0.5 (other_services_scoped and transport_later, but no demand_vs_frequency) against judge 1. The judge relied on F25 ('This is the restoration of demand, separate from the recovery of other services') and F30 (ORR's full service within 24 h). Increment A's six runs are unchanged (T05.03: 0, 0.5, 1, 0.5, 1, 1). Key 0.1.1: T05.03 pre-screen 1 on the pilot through `demand_vs_services` (F25 with F30's 24-hour rail recovery), agreeing with the judge; the panel run gets 1 on both (FI-B19).
- **Evidence.** ESO p27: 'service was restored at 17:35hrs. UKPN have confirmed that LFDD did not impact the Victoria line.'; ESO p33: 'The disruption to rail services extended through Friday evening and into Saturday morning'; ORR p11: 'full service was restored within 24hours'; ORR p4: 'shut down within 200ms of the frequency dropping below 49.0Hz'. Visible: S11 L24-L27 (P03, context), S08 L151-L154, S08 L110-L113, S08 L214-L216, S09 response:S09-NR-09; T04.03 context spans S08 L133-L135 and S08 L181-L184.
- **Compiler's note.** Installed FI key 0.1.1 (decisions 77–80; FI checklist B19): T05.03 gains a `demand_vs_services` element (with `transport_later` a full route), which addresses the expectation/pre-screen mismatch described here.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b2"></a>

##### FI-B2 — T04.02 rail protection threshold and 200 ms response

**P1** · 20 min · FI (`gb-2019-full-investigation`) · Criteria: T04.02 · Checklist: B2  

- **Question.** Should T04.02 be auto_assisted_human, with full requiring 49 Hz plus 200 ms plus attribution (or status 'reported'), half for either value alone, and a 48.5/48.8 Hz trip setting capped at 0.5?
- **Builder choice.** Full = the 49 Hz threshold, the 200 ms response and attribution to ORR, GTR or Siemens, or status 'reported'. Half = either value alone. A 48.5 or 48.8 Hz protection setting caps the criterion at 0.5.
- **Alternatives.** Make it a judge criterion. Give full for an attributed threshold without the 200 ms. Zero, rather than cap, a 48.5/48.8 Hz setting. Treat ORR 1.0's 'falling to 49.0Hz' as distinct from 'below 49.0Hz'.
- **Impact.** Pilot T04.02 = 0.5: F27 gives the 49 Hz threshold attributed to Siemens and EN 50163 but no 200 ms anywhere in the submission. Increment A's six runs = 0.
- **Evidence.** ORR p3: 'protection systems operated within 200ms of the frequency falling to 49.0Hz causing a lock-out of 29 trains.'; ORR p4: '...shut down within 200ms of the frequency dropping below 49.0Hz'; ORR p9: 'disconnecting the traction drive within 200ms.'; APP p49: '...the train protectively shutting down its drives when the supply frequency response fell below 49Hz.' and 'Siemens Technical Specification for the train states that the train will continue to operate with supply frequency drops down to 48.5Hz for short periods of time.' Visible: S08 L120-L127, L133-L135, L136-L139, L181-L184, L52-L55, L207-L210; S09 response:S09-GTR-06 and S09-GTR-10; R10 L223-L225; S08 L44-L45 (context, 48.5 Hz).

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b3"></a>

##### FI-B3 — T10.02 lock-out, technician and driver-reset counts and their alternatives

**P1** · 40 min · FI (`gb-2019-full-investigation`) · Criteria: T10.02a, T10.02b, T10.02c · Checklist: B3  

- **Question.** Are ORR's 29/22/7 the right exact counts, and should GTR's, the ESO's and DfT/E3C's ~60, the ~30 (GTR, ESO, ORR's conclusion) and GTR's 27/28 earn 0.5 only when attributed to a source that reports them, with misattributed or unattributed alternatives getting 0 plus a basis note?
- **Builder choice.** Full for 29, 22 or 7, including 29 and 22 attributed to Ofgem, and a bare '7 reset' listed with ORR's counts. An alternative earns 0.5 only with a named source that reports it, and its evidence is read against that source's own spans. Document IDs do not count as attribution. The checklist justifies the half credit by saying the alternatives 'count units, not trains, or come from another stage'. In fact the ESO and DfT also say 'trains', and ORR itself mixes the terms ('recovery of 7 of the affected units. 22 trains').
- **Alternatives.** Give full credit for any attributed account's count, since these are different accounts, not errors. Alternatively, give 0 for any non-ORR count, or 0.5 for an unattributed alternative after human review.
- **Impact.** Pilot F28 gives ORR's 29/22/7 and correctly attributes GTR's ~60, 27/28 and ~30, so T10.02a, b and c are all 1. The alternatives matter only for runs that omit ORR's counts. The pilot's summary-only 'About 60 GTR Class 700/717 trains shut down' is not credited. Increment A's six runs = 0.
- **Evidence.** ORR p3: '...lock-out of 29 trains. 22 trains were permanently locked-out ... while 7 trains were restored through driver-reset.'; ORR p5: 'The process led to the recovery of 7 of the affected units. 22 trains could not be reset'; APP p48: 'circa 60 units ... suffering a 4QC lock out', 'After this 27 of the affected units were recovered.', 'The remaining circa 30 units required the Protective Shutdown to be unlocked'; APP p49: 'The 28 units recovered by the driver performing a Battery Reset were at the previous TCMS software level of 3.25 or below.'; ESO p27: 'Of the approximately 60 Class 700 and Class 717 trains that shutdown, half were restarted by the driver'; E3C-I p12: 'which triggered 60 trains to shut down'; ORR p11: '30 trains running the upgraded software to be effectively stranded ... requiring a technician reset'; OFG p20: '22 permanently locked out'. Visible: S08 L120-L127 (O02), L22-L23 (G04), L33 (G08), L34-L35, L64-L66, L90-L94, L214-L216; S09 response:S09-GTR-03, S09-GTR-05 and S09-GTR-10.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b4"></a>

##### FI-B4 — T10.03 stranded trains and the two Class 387s

**P1** · 25 min · FI (`gb-2019-full-investigation`) · Criteria: T10.03a, T10.03b · Checklist: B4  

- **Question.** Is the 31 stranded right (exact, or 29 stranded plus two Class 387s stated together), with Ofgem's 29 'became stranded' and ORR's conclusion's 30 'effectively stranded' at 0.5 when attributed, and a Class 387 said to have shut down itself zeroing T10.03b?
- **Builder choice.** Full for 31, or for 29 plus two 387s stated together. This departs from the review's suggestion: 'Ofgem 29 plus two 387s' gets full, not 0.5, because it is the same 31 (decision 68). T10.03b needs the two Class 387s; a 387 self-shutdown is a zeroing contradiction. A misattributed expected count is not penalised.
- **Alternatives.** Give 0.5 for 'Ofgem 29 plus two 387s'. Give credit for ORR 2.3's '30 stranded trains'. Penalise 31 attributed to Ofgem: the pilot writes 'ORR and Ofgem say ... 31 trains stranded', but Ofgem gives 29 plus two 387s trapped.
- **Impact.** Pilot T10.03a = 1 (F28). T10.03b = 0: no Class 387 appears anywhere, a genuine omission according to DECISIONS. Increment A's six runs = 0. Panel run (key 0.1.1): T10.03a = 1 ('29 trains locked out ... plus 2 trapped Class 387s'; key 0.1.0 gave 0) and T10.03b = 1.
- **Evidence.** ORR p3: 'However, 31 trains were stranded as a result of the temporary drop in frequency.' and 'Two Class 387 trains were also trapped as a result of the lock-out experienced by the Class 700 and Class 717 trains.'; ORR p5: 'Passengers were safely detrained ... from 30 stranded trains.'; ORR p11: 'The permanent lock-out resulted in 30 trains running the upgraded software to be effectively stranded'; OFG p19: '29 Govia Thameslink Railway (GTR) Class 700 and 717 trains shut down and became stranded'; APP p48: 'None of the other AC trains in the GTR fleet suffered any power related issues from this event e.g. Class 387'. Visible: S08 L120-L127, S08 L222-L225, S08 L214-L216 (context), S08 L19-L21 (context), S09 response:S09-GTR-10.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b5"></a>

##### FI-B5 — T10.05 cancellations, delays and attribution of inconsistent counts

**P1** · 25 min · FI (`gb-2019-full-investigation`) · Criteria: T10.05a, T10.05b, T10.05c · Checklist: B5  

- **Question.** Should T10.05 be split into (a) 371 cancelled and 220 part-cancelled, (b) 873 trains delayed and 14,428 delay minutes, each credited only in its own measure, and (c) a judge field whose full credit needs at least two count differences named with their sources?
- **Builder choice.** Exact integers, with no attribution required for a and b. 873 given as minutes, or 14,428 given as trains, is not credited. For T10.05c, full needs two or more attributed differences; partial is one difference, or counts attributed without saying they differ. Ofgem's '>500 services disrupted' is listed as an accepted alternative but no element credits it.
- **Alternatives.** Require each count to be attributed to its source. Give full for one attributed difference. Clarify or remove the '>500' alternative. Accept Network Rail TRUST (R11) delay minutes as an alternative measure.
- **Impact.** Pilot T10.05a = 1 and T10.05b = 1 (F29: '371 trains cancelled, 220 part-cancelled and 873 delayed, with 14,428 delay minutes'). T10.05c is 1 on pre-screen and judge (F28 contrasts GTR and ORR counts). Increment A's six runs = 0.
- **Evidence.** ESO p27: '371 trains cancelled, 220 part cancelled, and 873 trains delayed'; ORR p6, Table 1 'TOTAL 371 220 14428' (Source: Network Rail's National Daily Report 09/08/2019); E3C p18: '371 cancelled services, 220 part cancelled services and 873 delayed services.'; E3C-I p12: '371 services were cancelled and 873 delayed'; OFG p5: 'more than 500 services disrupted'; APP p48: 'There were 17 Technicians available' against ORR p5 '18 Technicians'. Visible: S08 L103-L106, L155-L156, L165, L230-L238, L243-L246, L211-L216, L33, L36-L38, L148-L150; S09 response:S09-NR-07.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b6"></a>

##### FI-B6 — T11.01 split; T11.03 water and refinery (judge) with caps

**P1** · 30 min · FI (`gb-2019-full-investigation`) · Criteria: T11.01a, T11.01b, T11.03 · Checklist: B6  

- **Question.** Should T11.01 be split into the airport disconnected by LFDD (NPG) and Ipswich Hospital's own protection (each zeroed by the reversed mechanism), and T11.03 be a judge criterion with refinery-by-LFDD scoring 0 and the 12 September Stanlow article as a 9 August impact capped at 0.5? And does T11.03 full need each impact's supplied mechanism and attribution, or only no invented mechanism?
- **Builder choice.** T11.01a: full for the airport's disconnection attributed to LFDD; the duration is not required. T11.01b: full for own protection, or for 'not LFDD'. T11.03: full when both impacts are described within the records; refinery-by-LFDD scores 0; Stanlow (S11 X02) caps at 0.5.
- **Alternatives.** Keep T11.01 as one criterion needing the contrast. Zero, rather than cap, Stanlow. For T11.03, follow the handoff wording ('without inventing unsupported mechanisms') and do not require the refinery's mechanism or E3C attribution.
- **Impact.** Pilot T11.01a = 1 (F33) and T11.01b = 1 (F32). T11.03 pre-screen 1 but judge 0.5: F33 says 'A refinery took weeks to restore operations' without its own-safety-system mechanism or E3C attribution. Increment A's six runs = 0.
- **Evidence.** ESO p28: 'NPG have confirmed that the airport was disconnected as a result of the LFDD operation.' and 'UKPN have confirmed that the hospital was not part of their LFDD protection zone and that the LFDD did not affect the substations supplying the hospital.'; E3C p19: 'Wider industry reported the disconnection of an oil refinery and chemicals manufacturing plant due to internal safety systems detecting the drop-in frequency.'; E3C-I p12: 'Approximately 3,000 people experienced water supply disruptions due to booster water pumping stations failing...'; OFG p20: 'Some water pumping stations were disconnected as part of the LFDD.' Visible: S11 L78-L84, L88-L89, L101-L103; S11 L58-L64; S09 response:S09-HOSP-02 and S09-UKPN-05; R12 L19-L32; S11 L106-L129; S11 L159-L160 (X02 Stanlow, context).

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b7"></a>

##### FI-B7 — T14.03 EPN/SPN early reconnection (auto_assisted_human)

**P1** · 15 min · FI (`gb-2019-full-investigation`) · Criteria: T14.03 · Checklist: B7  

- **Question.** Should T14.03 give full only for EPN/SPN's reconnection without the ESO's instruction together with the instruction requirement, 0.5 for the reconnection alone, 0 for the requirement alone, and 0 when the early reconnection is given to another DNO?
- **Builder choice.** As stated. Clause numbers are not required. Giving the early reconnection to SP Distribution (which reconnected without informing the ESO) or another DNO is a zeroing contradiction.
- **Alternatives.** Give 0.5 for the requirement alone. Make it a judge criterion. Do not zero when another DNO is also mentioned for a different issue (e.g. SP Distribution's 22 MW wrong setting).
- **Impact.** Pilot = 1 (F26: 'UKPN's EPN and SPN reconnected sites before instruction'). Pinned pre-screens on increment A's runs: 1 for sr30k-opus55-001, sr30k-sonnet55-001, sr80k-opus55-001 and sr80k-sonnet55-001; 0 for both haiku45 runs.
- **Evidence.** OFG p35: 'Eastern Power Networks plc and South Eastern Power Networks plc (both owned by UK Power Networks) re[connected ...]'; ESO p8: 'the DNO's must notify ESO of its operation and are not permitted to restore automatically disconnected...'; OFG p36: '...reconnection by Eastern Power Networks plc and South Eastern Power Networks plc could potentially have jeopardised...'. Visible: S10 L160-L169; R10 L113-L116 and L189-L191; S09 response:S09-UKPN-03 and S09-UKPN-04.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b8"></a>

##### FI-B8 — Severe-flag effects: which criteria a confirmed flag zeroes

**P1** · 20 min · FI (`gb-2019-full-investigation`) · Criteria: T07.04, T07.05, T17.01, T14.02, T14.04, T14.05, T20.03, T20.06 · Checklist: B8 · Cross-task: [XT-10](#xt-10)  

- **Question.** Should a confirmed SF1 zero only T07.04, T07.05, T17.01 and T14.02 (and T20.03/T20.06 only when the assertion is in the executive summary), and a confirmed SF3 zero only T14.04 and T14.05, rather than 'the relevant task' as the handoff says?
- **Builder choice.** Only the listed criteria are zeroed, and the T20 zeroing is tied to the summary's location (`zero_content_at`). Plain `zero_content` was rejected because a root cause asserted only in a finding must not zero the summary criteria. A suspected flag bounds judge proposals for those criteria at 0. There is no run-level pass/fail.
- **Alternatives.** Handoff: 'zeroes the relevant task and prevents run-level pass', i.e. all of T07/T17/T14/T20 or whichever task holds the assertion. Alternatively, zero T20.03/T20.06 for an SF1 anywhere in the submission.
- **Impact.** There is no confirmed or suspected severe flag on the pilot or on increment A's six runs, so no current grade changes. The choice decides how much a panel run loses if it asserts the settlements or a Little Barford root cause.
- **Evidence.** Handoff 'Scoring contract': 'A critical fabrication ... zeroes the relevant task and prevents run-level pass.' Key severe_flags SF1 effect.zero_content [T07.04, T07.05, T17.01, T14.02, T20.03, T20.06] with zero_content_at for T20.03/T20.06; SF3 zero_content [T14.04, T14.05]. DECISIONS 71 (the departure). REVIEW_CHECKLIST.md B8.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b9"></a>

##### FI-B9 — T15.01 split and communications-time tolerances

**P1** · 25 min · FI (`gb-2019-full-investigation`) · Criteria: T15.01a, T15.01b, T15.01c · Checklist: B9  

- **Question.** Should T15.01 be (a) the first BEIS contact at 17:40–17:41 BST with no tolerance beyond the two records, (b) the first ESO public statement at 18:27 ±60 s with half credit for about 18:30, and (c) a judge sequence field, given the handoff sets no communications tolerance?
- **Builder choice.** (a) `clause_time` range 17:40–17:41, tol 0 s; UTC equivalents are accepted. (b) Full within 60 s of 18:27; half via an element centred on 18:28:30 ±150 s, so 18:26:00–18:31:00 earns half outside the full band. The key's `tolerances` field instead says half_within_s 240, which would give half from 18:23. This is a documentation mismatch, and 18:23–18:25 currently gets 0. (c) Judge, needing government/regulator order plus the earlier DNO/rail statements.
- **Alternatives.** Apply the handoff's 2-minute restoration-boundary rule to communications times. Give full for 18:30, since R09 E14 is the ESO's own web statement titled '6.30pm'. Give 0 for 18:30. Use 240 s as the stated tolerance says.
- **Impact.** Pilot T15.01a = 1 (F34: 17:41 per 6.2 or 17:40 per section 7). T15.01b = 1 (F35: '17:27:46Z (18:27 BST)'). T15.01c = 1 on pre-screen and judge. On increment A's runs a and b are 0, and T15.01c's pre-screen is 0.5 for sr30k-sonnet55-001 and sr80k-sonnet55-001. Panel run (key 0.1.1): T15.01c = 0.5 on pre-screen and judge (no 17:10 internal escalation).
- **Evidence.** ESO p30: 'The first communication between the ESO control room and BEIS was at 17:41hrs.'; ESO p33: 'The ESO contacted BEIS at 17:40 and Ofgem at 18:00.'; ESO p30: 'The first ESO external communication was issued at 18:27hrs on 9 August.'; APP p88: '...which was issued at 18:27 once it was established that the DNOs had reconnected all customers.' Visible: R09 L25-L37, entries R09-A1-1 and R09-A2-1, S09 response:S09-ESOC-01; R09 L58-L95, L325-L327 (E13 '2019-08-09T17:27:46Z'), R09 L328 (E14 'page titled 'Power Cut Statement - 9 August, 6.30pm''), entries R09-B1-T8-1 and R09-A2-3, S09 response:S09-ESOC-04; for c, R09 L38-L55, L96-L114, L143-L154, L293-L295, entry R09-A3-1, S09 response:S09-ESOC-05.
- **Compiler's note.** Installed FI key 0.1.1 (decisions 77–80; FI checklist B19): T15.01c's full credit now also needs the 17:10 internal escalation (the expectation's full).

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b10"></a>

##### FI-B10 — T15.02 17:51 vs 18:00 first Ofgem contact

**P1** · 10 min · FI (`gb-2019-full-investigation`) · Criteria: T15.02 · Checklist: B10  

- **Question.** Should full need both 17:51 and 18:00 for the first Ofgem contact, half one time attributed to its record by name, and one time given as the fact earn 0, with no time tolerance?
- **Builder choice.** As stated. 'Just after 18:00' (answer to E3C question 34) is accepted for the later record. The 18:00 must belong to the Ofgem contact, not e.g. '105 calls after 18:00' or 'before 6pm on 16 August'.
- **Alternatives.** Full for one attributed time. 0.5 for one unattributed time. A ±1 minute tolerance.
- **Impact.** Pilot = 1 (F34: '17:51 (section 6.2), 18:00 (section 7) or 'just after 18:00' (answer 34)'). Increment A's six runs = 0.
- **Evidence.** ESO p30: 'The first communication with Ofgem was made at 17:51hrs'; ESO p33: 'The ESO contacted BEIS at 17:40 and Ofgem at 18:00.'; APP p88: 'The 1st communication with Ofgem was made just after 18:00hrs with the Director of Operations, ESO.' Visible: R09 L25-L55, entries R09-A1-2, R09-A2-2 and R09-A3-3, S09 response:S09-ESOC-02.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b12"></a>

##### FI-B12 — T13, T18, T19 and T20 as judge criteria; official recommendations as examples only

**P1** · 30 min · FI (`gb-2019-full-investigation`) · Criteria: T13.01, T13.02, T13.03, T13.04, T13.05, T13.06, T18.01, T18.02, T18.03, T18.04, T18.05, T18.06, T19.01, T19.02, T20.01, T20.02, T20.03, T20.04, T20.05, T20.06 · Checklist: B12 · Cross-task: [XT-18](#xt-18)  

- **Question.** Should all of T13, T18, T19 and T20 be judge criteria, with pre-screens reading the Recommendations and evidence-request sections by heading, findings that state recommendations, and the executive summary, and with equivalent justified actions accepted instead of the official recommendations?
- **Builder choice.** 29 new judge criteria. The official recommendations (ESO section 8, Ofgem, E3C actions, ORR section 5) appear as report passages only. Pre-screens are shown to the reviewer, never to the judge.
- **Alternatives.** Make some criteria auto_assisted_human with explicit topic lists (e.g. T18.02–T18.05 coverage). Alternatively, require a match to named official actions.
- **Impact.** Under key 0.1.1 judge and pre-screen disagree on 6 of 53 judge criteria on the pilot and 2 on the panel run, in both directions (key 0.1.0: 13 and 10; decisions 76, 79). New-criteria cases (pre-screen vs judge): pilot T11.03 1 vs 0.5, T13.04 1 vs 0.5, T14.01 1 vs 0.5, T18.04 0.5 vs 1 and T20.04 1 vs 0.5; panel T13.05 1 vs 0.5 and T14.01 1 vs 0.5. See FI-G2 and the FI-D items. Human sign-off decides every one.
- **Evidence.** ESO p35: 'Review the security standards (SQSS) to determine whether it would be appropriat[e]...'; E3C p15 'Action 5: The ESO, in consultation with industry, should undertake a review of t[he SQSS]...'; E3C p17 'Action 6: The E3C, through the DNOs and the ENA, to undertake a fundamental revi[ew]...'; ORR p11: 'Siemens to implement a software patch which will be installed on all the Class 7[00]...'. Key `judge.criteria` (53).

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b13"></a>

##### FI-B13 — T19.02 notification needs; unverified ESQCR/OC7/OC10 obligations capped

**P1** · 20 min · FI (`gb-2019-full-investigation`) · Criteria: T19.02 · Checklist: B13  

- **Question.** Should T19.02 be capped at 0.5 when an ESQCR duty or an OC7/OC10 obligation beyond the recorded SIR request is asserted, while citing the DNOs' 17:23 SIR request under OC7/OC10 (S07 K3) counts as recorded evidence?
- **Builder choice.** Full = notification and coordination needs tied to the requirements supplied (R10 D9/H1, I1, I2, G3; Ofgem 3.23), with no unverified obligation. The cap is excused only when OC7/OC10 appears next to the SIR, not for a bare 'S07'. Saying that these obligations are not in the evidence is fine.
- **Alternatives.** Zero for unverified obligations. Allow general OC7/OC10 mentions without the cap. Drop S07 K3 as a keyed span.
- **Impact.** Pilot pre-screen 1 and judge 1 (the evidence-requests section cites OC6.6 and the ESO procedure, with no ESQCR or OC7/OC10 duty). On increment A's runs the pre-screen is 1 for sr30k-haiku45-001, sr30k-sonnet55-001 and sr80k-opus55-001, and 0 for sr30k-opus55-001, sr80k-haiku45-001 and sr80k-sonnet55-001.
- **Evidence.** Handoff T19: 'exclude unverified ESQCR or OC7/OC10 obligations'; ESO p8: 'the DNO's must notify ESO of its operation and are not permitted to restore automatically disconnected...'; APP p88: 'Current ESO procedure outlines that following an event of loss of supply, a clea[r communication]...'; APP p89: 'Control Telephony is used for instructing Demand Control'. Visible: S07 L48-L49 and entry:S07-K3 ('17:23 [reported] First Significant Incident Report (SIR) request (Grid Code OC7 and OC10) received from DNOs'); R10 L113-L116, L171-L175, L194-L202; S10 L133-L135; R10 L4-L6 (context).
- **Compiler's note.** S07 K3 quote made verbatim on review: the bundle line carries the value-status tag '[reported]'.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b14"></a>

##### FI-B14 — T20.06 calibrated certainty and the 600-word limit

**P1** · 20 min · FI (`gb-2019-full-investigation`) · Criteria: T20.06 · Checklist: B14  

- **Question.** Should T20.06 be binary (full only if at most 600 words and calibrated, no partial), with a pre-screen that also needs at least one finding reference in the summary and no unqualified certainty wording?
- **Builder choice.** The word limit is automatic; the validator rejects longer summaries, so the word element is only a guard. The pre-screen needs `min_refs` 1 and no 'proves', 'definitively', 'the root cause was', 'the root cause of ... was' or 'was a faulty ...'. An SF1 in the summary caps a suspicion and zeroes a confirmation.
- **Alternatives.** Drop the finding-reference requirement, which is not in the expectation. Add 0.5 for a minor overclaim. Count words as the handoff does, if different from whitespace splitting.
- **Impact.** Pilot: 540 words; pre-screen 1, judge 1. sr80k-haiku45-001's 220-word summary references no finding, so its pre-screen is 0 although the expectation does not mention references. The other five increment A runs score 1.
- **Evidence.** Handoff T20: 'No unsupported certainty; no more than 600 words'; OFG p31: 'The root cause of the discrepancy in the speed sensors has not been established.'; APP p61: 'An event such as this is complex with many different things happening...'. Visible: S04 L56-L59, S12 L52-L53. Pilot grade.json flags.executive_summary {words 540, limit 600, within_limit true}.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b16"></a>

##### FI-B16 — T05.02 diverges from increment A's frozen key

**P1** · 10 min · FI (`gb-2019-full-investigation`) · Criteria: T05.02 · Checklist: B16 · Cross-task: [XT-21](#xt-21)  

- **Question.** Should the re-bound T05.02 gain a second full route that reads 'restored/reconnected/back by &lt;time>' (17:37 ±120 s), diverging from increment A's frozen element?
- **Builder choice.** The `restoration_complete_by` element is added. Increment A's element, the expected time, the tolerance and the keyed spans are unchanged.
- **Alternatives.** Keep increment A's element. 'By 17:37' then goes to human review instead of automatic credit.
- **Impact.** Pilot F25 ('Disconnected demand was restored by 17:37 BST') changes from 0 to 1. Increment A's six runs are unchanged (all 1).
- **Evidence.** ESO p13: '17:37 All DNO's have confirmed that demand restoration has been completed'; ESO p29: '...the earliest restoration was completed at 17:07 and the last customers were reconnected at 17:37.'; ESO p26, Table 6: 'Totals 931 1,152,878 17:37'. Visible: S07 L39-L40 (E13), S07 L118-L119, S05 L35, R07 L85, entry:S07-E13, S09 response:S09-ESO-05 and S09-DNO-02.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b19"></a>

##### FI-B19 — Key 0.1.1 pre-screen corrections from the two real FI runs

**P1** · 45 min · FI (`gb-2019-full-investigation`) · Criteria: T02.04, T05.03, T06.02, T08.04, T08.05, T09.05, T10.03a, T11.03, T14.02, T14.05, T15.01c, T20.03 · Checklist: B19 · Cross-task: [XT-01](#xt-01)  

- **Question.** Are key 0.1.1's pre-screen corrections right, each read against its expectation? Checklist B19: T02.04's SOE offsets read '&lt;n> s after datum T'; T10.03a's 29 may be worded 'locked out' with the two Class 387s trapped in its sentence (B4); T11.03's refinery needs its own mechanism in its sentence; T05.03 gains `demand_vs_services`; T06.02's offshore side reads the turbines' overcurrent protection; T08.04 no longer takes a measurement limit for the causal split and reads 'could not split it by cause'; T08.05 reads a total that 'includes about &lt;figure>'; T09.05 reads 'wrong setting'; T14.02's full needs the requirement (`lb_requirement`); T14.05 no longer reads Ofgem's finding of no breach as missing proof and gains a partial (`records_missing`); T15.01c's full needs the 17:10 internal escalation; T20.03 reads 'unestablished' and 'unidentified'.
- **Builder choice.** Each correction was read against the submission and the keyed evidence (decisions 77–79); the builder reports that the judge's proposals agree with every corrected pre-screen. Six of the corrected criteria are re-bound from SR (T02.04, T05.03, T06.02, T08.04, T08.05, T09.05): only their pre-screen rules change, not their expectations, examples, tolerances or keyed spans, and SR 0.1.1 keeps the old rules (XT-01 (c)). T11.03's correction changes no outcome on either run. T12.05's correction is an accounting rule (FI-C4).
- **Alternatives.** Revert any correction you read differently (new key version). Port the re-bound corrections to SR, which reopens the frozen SR key and its six runs (XT-01). For T14.02, keep decision 70's full credit for 'RWE acknowledges it contributed' without the requirement (see FI-D-T14.02). For T15.01c, keep full credit without the 17:10 escalation.
- **Impact.** Pre-screen changes from key 0.1.0 to 0.1.1, judge proposal in brackets. Pilot: T02.04 0.5 → 1 (F06 'about 1.16 s after datum T'); T05.03 0.5 → 1 (1); T06.02 0 → 0.5 (0.5); T08.04 1 → 0.5 (0.5); T08.05 0 → 1 (1); T09.05 0 → 0.5 (0.5); T14.02 1 → 0.5 (0.5); T14.05 1 → 0.5 (0.5). Panel run: T15.01c 1 → 0.5 (0.5); T14.05 0 → 0.5 (0.5; records named as not held, and F38 no longer excluded by the false SF1); T08.04 stays 1 but is now credited through F10, not F15's measurement limit (1); T10.03a 0 → 1. Increment A's six runs: T14.05 0 → 0.5 on sr30k-opus55-001, sr80k-opus55-001 and sr80k-sonnet55-001; no other value changes.
- **Evidence.** APP p88: 'At 17:10hrs, the ENCC Power System Manager (PSM) reported the incident to the Head of National Control, ESO.' (T15.01c); OFG p27: 'We have not found any evidence to suggest the ESO has failed to meet its requirements under the Grid Code in this area.' (T14.05); OFG p21: 'Transmission-connected generators have a requirement to remain connected and continue providing power' (T14.02); APP p41: 'all WTGs on Hornsea 1B and Hornsea 1C reduce to 0MW as a result of overcurrent protection in the generators' (T06.02); OFG p36: 'SP Distribution erroneously disconnected 22MW in Scotland when system frequency fell below 48.8Hz' (T09.05). Key `changes` (0.1.1); DECISIONS 77–79; tests/test_fi_grading_live_runs.py `FI_EXPECTED`, `test_pilot_t14_05_full_with_the_compliance_proof_named_missing`, `test_pilot_t11_03_needs_the_refinerys_own_mechanism`, `test_pilot_t02_04_offset_must_fit_the_initial_group`; REVIEW_CHECKLIST.md B19.
- **Compiler's note.** Added on review: checklist row with no card.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b20"></a>

##### FI-B20 — The `figure` element reads findings labelled unknown

**P1** · 15 min · FI (`gb-2019-full-investigation`) · Criteria: T08.02, T08.03 · Checklist: B20 · Cross-task: [XT-07](#xt-07)  

- **Question.** Should a figure in a finding labelled unknown be credited when the figure's own clause (cut at ';', ':' and sentence ends) states no uncertainty or hedge, as decision 18 does for trip mechanisms, while a figure in a hypothesis-labelled finding or a hedged clause is listed for you and never credited?
- **Builder choice.** Yes, in the FI key only (`fi_elements.eval_figure`). Increment A's figure element reads factual statuses only, so SR keeps the old rule. Elements that list their own statuses keep them: T09.03 already counts figures under any status, a labelled hypothesis included (SR-B24).
- **Alternatives.** Factual statuses only, as in SR (parity). Credit an unknown-labelled figure at 0.5. Send unknown-labelled figures to a human instead of crediting them.
- **Impact.** Panel run F11, labelled unknown: 'Two further losses are modelled and their causes are unknown: ... a net 200 MW at 49 Hz ... Ofgem puts total distributed generation lost at 1,300–1,500 MW (estimated).' T08.02 0.5 → 1 and T08.03 0 → 1. No change on the pilot or on increment A's six runs. An agent that labels a whole finding unknown because one part is uncertain no longer loses the figures it states plainly.
- **Evidence.** OFG p32: 'Our lower bound for total estimated distributed generation lost across the event is 1,300MW, and the loss could be as high as 1,500MW.'; OFG p18: 'There was a further net reduction in generation of 200MW at 49Hz'. DECISIONS 18, 78; tests/test_fi_grading_live_runs.py `test_panel_figures_in_a_finding_labelled_unknown`, `test_figures_in_a_labelled_finding_need_an_unhedged_clause`; REVIEW_CHECKLIST.md B20.
- **Compiler's note.** Added on review: checklist row with no card.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-c2"></a>

##### FI-C2 — Accounting: a quantity basis that gives the value's own terms names its source

**P1** · 10 min · FI (`gb-2019-full-investigation`) · Checklist: C2 · Cross-task: [XT-01](#xt-01)  

- **Question.** Should a structured quantity whose basis writes the value as its own terms (500 MW with basis 'ESO estimate from transformer-flow changes (150 VS + 350 RoCoF)') be bound to the source the basis names, rather than to the statement's only source?
- **Builder choice.** Yes, in the FI key only (`accounting.binding_options.basis_components`): a basis part whose numbers sum to the value within 1 MW, joined by '+', 'plus' or 'and', names the source. Increment A's rule skips a basis part that holds another key figure's number (150, 350) and falls back to the statement's source; SR 0.1.1 keeps that rule.
- **Alternatives.** Keep increment A's rule (parity with SR). Port the option to SR (SR key 0.1.2 and a regrade of its six runs; no SR value is known to change). Send any figure whose basis and statement name different sources to a human.
- **Impact.** Panel run F10: key 0.1.0 trapped its 500 MW as 'misattributed' to the DNOs of the next sentence ('DNOs returned a combined 462 MW'); key 0.1.1 binds it to ESO, and F10's other figures keep their own accounts (150 and 350 MW as estimates, 430 and about 580 MW unattributed, 462 MW the DNOs'). A basis 'DNO returns (150 VS + 350 RoCoF)' still traps. Increment A's six runs are unchanged.
- **Evidence.** ESO p35: 'approximately 500MW of embedded generation tripped on loss of mains protection (vector shift and rate of change of frequency)'; ESO p21: 'ESO simulation data indicates that the overall total embedded generation loss could be slightly higher (580MW v 500MW)'. Key `accounting.binding_options`; DECISIONS 77; tests/test_fi_grading_live_runs.py `test_panel_f10_500_mw_is_esos_estimate`, `test_traps_fire_on_the_panels_f10_with_a_wrong_stage_or_source`; REVIEW_CHECKLIST.md C2.
- **Compiler's note.** Added on review: checklist row with no card.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-c3"></a>

##### FI-C3 — Accounting: a loss-of-mains total is not one mechanism's loss

**P1** · 10 min · FI (`gb-2019-full-investigation`) · Checklist: C3 · Cross-task: [XT-01](#xt-01)  

- **Question.** Should ESO's loss-of-mains totals, 500 MW (estimate) and 580 MW (simulation), be 'mismatched' (no credit; a trap for you) when given as one mechanism's loss ('ESO reported 580 MW of DG lost to vector shift'), while 'lost to vector shift and RoCoF' is fine?
- **Builder choice.** Yes, in the FI key only: DG_LOM_500 and DG_LOM_580 carry a mismatch for a loss on vector shift or RoCoF alone, with `mismatch_unless_any` (vector shift and/or/plus RoCoF) read in the sentence. SR 0.1.1 classifies the same sentence 'attributed'.
- **Alternatives.** No mismatch rule, as in SR. Port the rule to SR. Cap at 0.5 instead of a mismatch.
- **Impact.** No real run gives either total to one mechanism, so no current value changes. The probe 'ESO reported 580 MW of DG lost to vector shift' was 'attributed' under key 0.1.0 and is 'mismatched' under 0.1.1. ESO splits the estimate as about 150 MW on vector shift and 350 MW on RoCoF.
- **Evidence.** ESO p35: 'approximately 500MW of embedded generation tripped on loss of mains protection (vector shift and rate of change of frequency)'; ESO p12: '16:52:33 Approximately 150MW of embedded generation trips on vector-shift protection'; ESO p21: 'it is estimated that approximately 350MW of embedded generation was lost due to RoCoF'; ESO p21: '(580MW v 500MW)'. Key accounting.figures DG_LOM_500 and DG_LOM_580; DECISIONS 77; tests/test_fi_grading_live_runs.py `test_traps_fire_on_the_panels_f10_with_a_wrong_stage_or_source`; REVIEW_CHECKLIST.md C3.
- **Compiler's note.** Added on review: checklist row with no card.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-c4"></a>

##### FI-C4 — Accounting: an inertia unit is the inertia figures' context

**P1** · 5 min · FI (`gb-2019-full-investigation`) · Criteria: T12.05 · Checklist: C4 · Cross-task: [XT-01](#xt-01)  

- **Question.** Should an inertia unit (GVA.s, MVA.s) count as the inertia figures' context, so that 'The ESO final report gives 210 GVA.s. Its earlier answer gives 219,632 MVA.s' is read as the two inertia accounts without the word 'inertia' in either sentence?
- **Builder choice.** Yes, in the FI key only (the inertia figures' context accepts their units). SR 0.1.1 needs inertia wording near the figure.
- **Alternatives.** Keep SR's rule (parity). Port the rule to SR. Send unit-only inertia mentions to a human.
- **Impact.** Panel run F19 (after a sentence on inertia): T12.05 0.5 → 1. On increment A's six runs it adds one mention, sr30k-sonnet55-001 F17's 219,632 MVA.s ('defined'), and changes no value.
- **Evidence.** ESO p23: '01 July 09 August Demand 28 GW 29 GW Inertia 201 GVAs 210GVAs'; APP p90: '16:52 Immediately prior to the trip 219632'. Key accounting.figures INERTIA_ESO_210 and INERTIA_ESO_219632; DECISIONS 78; tests/test_fi_grading_live_runs.py `FI_EXPECTED` (panel T12.05) and `FI_MENTIONS`; REVIEW_CHECKLIST.md C4.
- **Compiler's note.** Added on review: checklist row with no card.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-d-t13"></a>

##### FI-D-T13 — T13.01–T13.06 contributing-factor expectations

**P1** · 60 min · FI (`gb-2019-full-investigation`) · Criteria: T13.01, T13.02, T13.03, T13.04, T13.05, T13.06 · Checklist: D (rows T13.01, T13.02, T13.03, T13.04, T13.05, T13.06)  

- **Question.** Are the six contributing-factor expectations right: two named factors each for T13.01–T13.05 (full = both supported, partial = one), and T13.06 full only when the triggering, contributing and systemic kinds are all distinguished and each selected factor is supported?
- **Builder choice.** T13.01: DG loss-of-mains settings plus DG visibility. T13.02: compliance evidence/testing plus information sharing. T13.03: securing/modelling assumptions plus response delivery, without under-delivery as the sole cause. T13.04: LFDD's disconnection of DG (net relief) plus essential services. T13.05: the 49 Hz setting vs the 48.5 Hz specification plus 3.27 recovery and technicians. T13.06: the three kinds kept separate.
- **Alternatives.** Give full for one well-supported factor. Accept factors listed with support but unclassified as full for T13.06. Drop the 'without asserting under-delivery alone' condition.
- **Impact.** Pilot pre-screen is 1 for T13.01–T13.05 and 0.5 for T13.06. Judge gives 0.5 for T13.04, partly a scoping artefact (FI-F1): F13 (DG ~550 MW lost at LFDD, net ~350 MW) was not shown in the T13 request. Judge gives 0.5 for T13.06 (systemic factors not separated as a third category). Increment A pre-screens (sr30k haiku/opus/sonnet, sr80k haiku/opus/sonnet): T13.01 0.5/1/1/0/1/1; T13.02 0/0/0.5/0/0/0.5; T13.03 1/1/1/0.5/1/1; T13.04 0/0.5/0.5/0/0.5/0.5; T13.05 all 0; T13.06 0.5/0.5/0.5/0/0.5/0.5. Panel run (key 0.1.1): T13.04 and T13.06 are 1 on pre-screen and judge; T13.05 is pre-screen 1, judge 0.5, for content that earned the pilot 1 (decision 79).
- **Evidence.** OFG p33: 'It is possible that the frequency protection settings on some generators were not changed in line with these Distribution Code requirements.'; OFG p36: 'Most of the DNOs only record information on generation volumes on their networks on a half-hourly basis'; OFG p27: 'The ESO relied significantly on self-certification by Hornsea 1'; OFG p29 (modelling 'suggested that there were performance issues with the voltage control sys[tem]'); APP p56: 'The SQSS anticipates that only one Secured Event would happen at any one time'; OFG p33: 'some DNOs disconnected distributed generation via LFDD that was providing either' / OFG p34 'frequency response or reserve services'; OFG p35: 'There is no obligation on DNOs to refrain from disconnecting such providers in their LFDD requirements'; ORR p10: 'appear not to have been given weight when developing the protection parameters for the on-train software'; OFG p6: 'the event highlights the importance of robust industry compliance processes'. Visible: S10 L180-L184; S06 L22-L24, L32-L39; S12 L100-L103; S10 L49-L53, L91-L108, L126-L135; R10 L28-L44; S12 L29-L33, L91-L124; S10 L155-L159; R10 L117-L118, L205-L211; S11 L146-L151; S08 L44-L45, L56-L59, L70-L73, L148-L150, L196-L201; S09 response:S09-GTR-07; R03 L25-L27; S10 L117-L119, L143-L145; S11 L138-L141.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-d-t14.01"></a>

##### FI-D-T14.01 — T14.01: must the requirement's substance be stated?

**P1** · 15 min · FI (`gb-2019-full-investigation`) · Criteria: T14.01 · Checklist: D (rows T14.01)  

- **Question.** Does naming Hornsea's acknowledged failures against 'the fault ride through requirement (CC.6.3.15.1)' and 'the voltage-control oscillation requirement' count as tying each concern to its requirement, or must the requirement's content (remain connected with ≥90% output within 0.5 s; dampen or limit swings) be stated for full?
- **Builder choice.** Full = both concerns, each tied to its requirement. Partial = one concern, or both without the requirement. Clause numbers are not required. The pre-screen credits the pilot's naming as full; the judge read 'tied to its requirement' as needing the substance.
- **Alternatives.** Give full when the requirement is named (by title or clause). Give full only when its substance is stated (the judge's reading).
- **Impact.** Pilot pre-screen 1 vs judge 0.5. F07: 'Hornsea acknowledges it did not meet the fault ride through requirement (CC.6.3.15.1) or the voltage-control oscillation requirement (CC.A.7.2.5.2).' The judge's reason: 'it does not explain the requirements'. Increment A's six runs: pre-screen 0. The panel run has the same disagreement (pre-screen 1, judge 0.5; decision 79).
- **Evidence.** OFG p30: 'The Grid Code requirements on generators' responses to network faults, known as Fault Ride Through r[equirements]...'; OFG p30: 'Hornsea 1 has acknowledged that it did not meet this requirement'; OFG p30: 'the Grid Code requirement to have an overall voltage control system which appropriately dampens or l[imits swings]'. Visible: S10 L136-L142 (P04: '...power output recovering to at least 90% [reported] within 0.5 seconds'), S10 L122-L125, R10 L141-L146.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-d-t14.02"></a>

##### FI-D-T14.02 — T14.02: is the fault ride-through requirement needed for full?

**P1** · 15 min · FI (`gb-2019-full-investigation`) · Criteria: T14.02 · Checklist: D (rows T14.02)  

- **Question.** Should T14.02 full require Little Barford's contribution to be stated against the fault ride-through requirement (Ofgem 3.26) as well as the causes left open, when the handoff asks only for 'Little Barford contribution without inventing an established underlying fault'?
- **Builder choice.** Full = contribution against the requirement, with the causes left open. Partial = contribution without the requirement or without the open causes. 0 = an established underlying fault asserted (also SF1, which zeroes it).
- **Alternatives.** Full = contribution plus causes left open (the handoff wording), with the requirement optional.
- **Impact.** Pilot pre-screen 1 vs judge 0.5. F39 ('RWE acknowledges it contributed'; root causes 'not established'; Ofgem's preliminary view attributed) was fixed in the pre-screen from 0 to 1 (decision 70). The judge says F39 does not connect the contribution 'explicitly to the fault ride-through requirement'. Key 0.1.1: pre-screen 0.5 on both FI runs, agreeing with the judge (`lb_requirement`; FI-B19). On the panel run a false suspected SF1 had zeroed T14.02 under key 0.1.0 (FI-E1).
- **Evidence.** OFG p30: 'little Barford's generators did not continue providing power to the system following the lightning s[trike]'; OFG p21: 'Transmission-connected generators have a requirement to remain connected and continue providing power'; OFG p31: 'We have established that the steam turbine tripped initially because of a discrepancy in the three independent speed sensors'; OFG p31: 'The root cause of these high pressure conditions has not been established.' Visible: S10 L143-L154, S04 L56-L59, R10 L147-L148.
- **Compiler's note.** Installed FI key 0.1.1 (decisions 77–80; FI checklist B19): the pre-screen's full credit now needs the requirement (`lb_requirement`); 'RWE acknowledges it contributed' alone is partial, as the judge read it.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-d-t14.04-05"></a>

##### FI-D-T14.04-05 — T14.04 process vs breach vs outcome; T14.05 the missing proof

**P1** · 25 min · FI (`gb-2019-full-investigation`) · Criteria: T14.04, T14.05 · Checklist: D (rows T14.04, T14.05)  

- **Question.** For T14.04, is full rightly 'process concerns and acknowledged non-compliance kept apart, no outcome claimed'? For T14.05, how much of the missing proof (compliance test reports and simulation studies; plant, controller and DNO switching records; open root causes) must be named for full, given the pre-screen has no half route although the expectation defines a partial?
- **Builder choice.** T14.04: full routes are process+acknowledged(+no_outcome); a legal finding or SF3 zeroes it. T14.05: full = missing proof identified and no outcome invented, with partial = missing proof only partly identified. The pre-screen offers only full or 0.
- **Alternatives.** T14.05 full for any one concrete missing-proof item. Alternatively, require the compliance test reports specifically. Add a pre-screen half route.
- **Impact.** Pilot T14.04 = 1 on pre-screen and judge (F38: 'These are process concerns, not demonstrated non-compliance'). T14.05 pre-screen 1 vs judge 0.5 under key 0.1.0 ('does not identify unobtained compliance test reports and simulation studies'); key 0.1.1 gives pre-screen 0.5 (`records_missing`) on both FI runs, agreeing with the judge. Pinned on increment A's runs (key 0.1.1): T14.04 = 0 for all six; T14.05 = 1 for sr30k-sonnet55-001, 0.5 for sr30k-opus55-001, sr80k-opus55-001 and sr80k-sonnet55-001, 0 for both haiku45 runs.
- **Evidence.** OFG p27: 'However, the processes the ESO used to check their respective compliance with the Grid Code do not a[ppear sufficiently robust]'; OFG p27: 'We have not found any evidence to suggest the ESO has failed to meet its requirements under the Grid Code in this area.'; OFG p28: 'We would expect the ESO to review the adequacy of the procedures it carries out'; APP p53: 'List of Outstanding Tests...'; APP p54: 'Activity Date ESO issued LON for Gas Turbine replacement 06/01/2012...'; APP p91: 'There are no direct tests for generator ride-through'. Visible: S10 L49-L57, L72, L91-L105, L114-L116, L136-L142, L155-L166; R09 L453-L465; S08 L217-L219; S04 L56-L59.
- **Compiler's note.** Installed FI key 0.1.1 (decisions 77–80; FI checklist B19): T14.05 gains a partial route (`records_missing`) and no longer reads Ofgem's 'found no evidence that the ESO breached the Grid Code' as missing proof.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-d-t18"></a>

##### FI-D-T18 — T18.01–T18.06 recommendation expectations

**P1** · 40 min · FI (`gb-2019-full-investigation`) · Criteria: T18.01, T18.02, T18.03, T18.04, T18.05, T18.06 · Checklist: D (rows T18.01, T18.02, T18.03, T18.04, T18.05, T18.06)  

- **Question.** Are the full/partial thresholds right? Specifically: T18.03 full for any one of visibility, reserve/response or inertia; T18.04 needing both LFDD and essential-service actions; T18.06 needing an owner and verification for each recommendation. And does an LFDD restoration/reconnection fix (e.g. UKPN's configuration) count as an LFDD recommendation?
- **Builder choice.** T18.01 full = recommendations linked to established findings (pre-screen: at least 2 refs). T18.02 and T18.04 full need both topics; T18.03 any one; T18.05 rail and communications; T18.06 owner and verification for each. Equivalent justified actions are accepted.
- **Alternatives.** T18.03 needs two of the three. T18.06 'most recommendations'. LFDD credit only for scheme design or essential-service selection (E3C Action 6).
- **Impact.** Pilot pre-screen is 1 for T18.01–T18.03, T18.05 and T18.06, but 0.5 for T18.04 (essential services only). Judge gives 1 for all six; for T18.04 it counted Recommendation 5 (UKPN to correct the automatic-reconnection configuration) as LFDD action, 'narrower than a fundamental LFDD redesign'. Increment A's six runs: pre-screen 0 for all T18 criteria. Panel run (key 0.1.1): T18.04 = 0.5 on pre-screen and judge.
- **Evidence.** E3C p17: 'Action 6: The E3C, through the DNOs and the ENA, to undertake a fundamental revi[ew of the LFDD scheme]'; E3C p15: 'Action 5: The ESO, in consultation with industry, should undertake a review of t[he SQSS]'; E3C p13: 'Action 2: The ESO, in consultation with large generators and transmission owners, should review and improve compliance testing'; ORR p11: 'Siemens to implement a software patch...'; OFG p35: 'Individual customers operating essential services should therefore maintain and operate back-up power supplies'. Visible: R10 L28-L32, L124-L128, L209-L211; S11 L40-L42, L85-L87, L146-L151; S10 L98-L105, L114-L116, L155-L159, L180-L184; S06 L38-L39; S12 L100-L107; S08 L74-L76, L196-L201; R09 L96-L104, L128-L135.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-d-t20"></a>

##### FI-D-T20 — T20.01–T20.05 executive-summary expectations

**P1** · 40 min · FI (`gb-2019-full-investigation`) · Criteria: T20.01, T20.02, T20.03, T20.04, T20.05 · Checklist: D (rows T20.01, T20.02, T20.03, T20.04, T20.05)  

- **Question.** Are the summary expectations right? T20.01 full = lightning, the circuit and the time. T20.02 = sequence and consequences in order. T20.03 = contributing factors kept apart from unknowns. T20.04 = significant estimates and disagreements attributed, with 'some' as partial. T20.05 = actions in priority order linked to findings.
- **Builder choice.** Judge, read on the summary text only. Pre-screens use `summary_text` elements. T20.04 full needs the significant disagreements attributed.
- **Alternatives.** T20.01 full without the time. T20.04 full when the main disagreements (generation totals, LFDD MW) are attributed even if the minor ones are not. T20.05 full for prioritised actions without per-action links.
- **Impact.** Pilot pre-screen is 1 for T20.01–T20.05. Judge gives 1 except T20.04 = 0.5: the summary gives '17:40, 18:30 and 'within 90 minutes'' without sources and 'Reported counts differ (GTR, ORR, Ofgem)' without mapping them. Increment A pre-screens (sr30k h/o/s, sr80k h/o/s): T20.01 1/1/1/1/1/0.5 (pinned); T20.02 0.5/1/0.5/0.5/1/0.5; T20.03 0.5/0.5/0.5/0/0.5/1; T20.04 0/1/1/0/1/1; T20.05 0/0/0.5/0/0.5/0.5. Panel run (key 0.1.1): T20.03 0.5 and T20.04 1 on pre-screen and judge; a false suspected SF1 had zeroed T20.03 and T20.06 under key 0.1.0 (FI-E1).
- **Evidence.** ESO p3: 'A lightning strike occurred on a transmission circuit (the Eaton Socon - Wymondl[ey ...]'; ESO p12: '16:52:33.490 A single (blue) Phase to Earth fault on Eaton Socon - Wymondley cir[cuit]'; ESO p35: 'resulted in automatic disconnection of 1GW of demand in order to preserve the system'; OFG p18: 'The cumulative loss of generation at this point was at least 1,990MW.'; OFG p31: 'The root cause of these high pressure conditions has not been established.'; ESO p35: 'Recommendations made should be considered by BEIS, Ofgem and wider industry'. Visible: R03 L25-L27, event:R03-C1, S09 response:S09-NGET-01; S07 L39-L40; S12 L16-L24, L39-L42, L77-L80; S08 L103-L106, L120-L127; S11 L88-L89; S04 L56-L59; S06 L22-L24; R09 L34-L37; S08 L74-L76; S10 L114-L116.
- **Compiler's note.** Installed FI key 0.1.1 (decisions 77–80; FI checklist B19): T20.03 also reads 'unestablished' and 'unidentified'.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-e1"></a>

##### FI-E1 — SF1 established Little Barford root cause (executive-summary extension)

**P1** · 25 min · FI (`gb-2019-full-investigation`) · Criteria: T07.04, T07.05, T17.01, T14.02, T20.03, T20.06 · Checklist: E1 · Cross-task: [XT-08](#xt-08)  

- **Question.** Should SF1 keep increment A's heuristics, also zero T14.02, and in the executive summary cap T20.03/T20.06 on a suspicion and zero them on a confirmation, with T20.06's pre-screen also reading 'the root cause of ... was' and 'was a faulty ...'?
- **Builder choice.** The definition, triggers and unless-patterns are carried over from increment A after its two review rounds. Attributed views (ESO's bypass-valve wording) and labelled hypotheses/unknowns are not flagged. Suspicion/confirmation effects are tied to location for T20.
- **Alternatives.** Fire on a summary that omits the unknowns (an omission rather than an assertion). Treat Ofgem's 'preliminary view' linking the steam-turbine trip to the network fault as established when attributed.
- **Impact.** Key 0.1.0 suspected SF1 on the panel run on two lines that assert no cause: F38 ('Hornsea One and Little Barford were allowed to reconnect before the root cause was found') and the executive summary ('Little Barford: the root causes are unestablished [F09]'). The suspicion bounded T07.04, T07.05, T14.02, T17.01, T20.03 and T20.06 at 0 where the judge proposed 1, 1, 0.5, 1, 0.5 and 1. Key 0.1.1 removed both (decision 77); edited real lines that do assert a cause still fire. Under key 0.1.1 there is no SF1 on either FI run or on increment A's six runs. Pilot F39 (status unknown; 'Ofgem's preliminary view links the steam turbine trip to the network fault') is not flagged, and neither is the pilot summary's 'Unknown: the root causes of the Little Barford trips'.
- **Evidence.** OFG p31: 'The root cause of the discrepancy in the speed sensors has not been established.'; OFG p31: 'The root cause of these high pressure conditions has not been established.' Key SF1 examples ('The root cause of the ST1C trip was a faulty speed sensor.') and non-examples. DECISIONS 71. Visible: S04 L56-L59, S10 L146-L154.
- **Compiler's note.** Installed FI key 0.1.1 (decisions 77–80; FI checklist E1): SF1's negation family now excuses only a trigger in its own clause; causes 'before/until/pending' their finding, or said to be unestablished/unidentified/unproven, are spared.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-e2"></a>

##### FI-E2 — SF2 invented evidence record (new record shapes)

**P1** · 15 min · FI (`gb-2019-full-investigation`) · Checklist: E2 · Cross-task: [XT-09](#xt-09)  

- **Question.** Should SF2 check against every citable ID of this bundle and the shapes of its new record IDs (REMIT revisions, ESO-COMMS entries, Network Rail incidents, new witness answers), and not treat labelled document lines (e.g. 'S08-O02') as records?
- **Builder choice.** Evidence IDs are checked against the catalogue. Record-shaped references are checked against the bundle's record IDs (same prefix, digit-masked shape). Examples: S02, S13, R13, S07-E14, S09-ESO-99, R11-NR-999999, S09-GTR-42. Non-examples include 'R11-NR-224904' and 'R09-A1-2'.
- **Alternatives.** Flag labelled lines written in record form when they do not exist. Require an exact locator match for every reference.
- **Impact.** No SF2 on the two FI runs or on increment A's six runs.
- **Evidence.** Key SF2 definition and heuristic (record_id_pattern, record_ref_pattern). DECISIONS, 'ID choices for the new real-data documents' (R09-REMIT-…, R09-&lt;label>, R11-NR-&lt;n>, S08-G01, S09-GTR-nn etc.). Handoff 'Scoring contract': 'an invented evidence record used to substantiate a conclusion'.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-e3"></a>

##### FI-E3 — SF3 official enforcement outcome asserted

**P1** · 30 min · FI (`gb-2019-full-investigation`) · Criteria: T14.04, T14.05 · Checklist: E3 · Cross-task: [XT-09](#xt-09)  

- **Question.** Should SF3 fire on assertions of Ofgem's January 2020 settlements (RWE and Ørsted £4.5m each, EPN/SPN £1.5m, redress, 'voluntary resolution', 'formal legal determination', 'fined', asserted 'penalised/sanctioned', enforcement action as taken/imposed/announced), and spare ORR's 'could warrant enforcement action' and its paraphrases, Ofgem's investigation, delay compensation, settlement periods and recommended enforcement, with 'acknowledged a technical breach' counting only alongside a payment or settlement?
- **Builder choice.** Assertion-shaped triggers replace increment A's bare 'enforcement action/outcome/decision/notice' trigger, in this key only. Negated, conditional and recommended enforcement is excused. Confirmation zeroes T14.04 and T14.05 (see FI-B8).
- **Alternatives.** Use increment A's bare trigger. Flag 'acknowledged a technical breach' on its own. Treat 'Ofgem should take enforcement action' as an outcome.
- **Impact.** No SF3 on the two FI runs or on increment A's six runs. Recommendation-style wording ('to ... decide on any enforcement action') fired in probes before the change and no longer does (decision 71). Pilot F46 ('ORR found no non-compliance ...') is not flagged.
- **Evidence.** ORR p11: '...that could warrant an enforcement action.'; handoff agent brief: 'Do not infer later enforcement settlements'. R09 L453-L465: 'The opening of this investigation does not imply that Ofgem has made any findings about non-compliance'. S08 L217-L219 (O22). Key SF3 examples (9) and non-examples (15). DECISIONS 50, 57, 71.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-f1"></a>

##### FI-F1 — Judge interface and per-topic request scoping

**P1** · 30 min · FI (`gb-2019-full-investigation`) · Criteria: T13.04, T13.06 · Checklist: F1 · Cross-task: [XT-18](#xt-18)  

- **Question.** Should the full investigation use increment A's judge interface with per-topic scoping (each topic sees its own findings and spans; only T17 sees every finding), given that scoping hid findings that carried credited content on the pilot?
- **Builder choice.** Judge schema gb2019-sr-judge-output/1. The judge decides only judge criteria, bounded by caps and suspected flags; contradictions are pre-screen flags; accept_judge cannot sign off a capped proposal. Scope is topic-scope/2 with the error screen on. The checklist calls scoping 'the judge track's work'.
- **Alternatives.** Use whole-submission requests (about 2× input: 3.57M vs 1.76M characters on the pilot, roughly $1.13 more per run). Make T13 and T20 all_findings topics like T17. Rely on human sign-off to restore the missed content.
- **Impact.** Pilot judged for $1.57 (21 requests; all 337 quotes verified). The T13 request showed 25 findings in full but not F13 (DG ~550 MW lost at LFDD, net ~350 MW), F01 or F04. The T13.04 judge result is 0.5 ('F23 ... does not explain that LFDD disconnected distributed generation'). The T13.06 result is 0.5 ('F01 and F04 are only shown by openings'). The error screen's recall on paraphrases is 92%, with one known miss: a counterfactual without a communications word.
- **Evidence.** DECISIONS 52, 72, 73, 76. out/fi_pilot/.../judge/judge_output.json units[T13].scope.findings_shown (F02, F05, F07, F08, F10, F18–F21, F23, F27–F33, F35–F40, F43, F44). judge_rubric_v1.md, 'Findings you saw only in other_findings'.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-g1"></a>

##### FI-G1 — Pinned pre-screen results on increment A's six real runs

**P1** · 30 min · FI (`gb-2019-full-investigation`) · Criteria: T14.03, T14.04, T14.05, T20.01 · Checklist: G1  

- **Question.** Are the pinned pre-screens on increment A's real submissions right for those texts: T14.03 = 1 for both opus55 and both sonnet55 runs and 0 for both haiku45 runs; T14.04 = 0 for all six; T14.05 = 1 for sr30k-sonnet55-001, 0.5 for sr30k-opus55-001, sr80k-opus55-001 and sr80k-sonnet55-001 (key 0.1.1's partial for records not held) and 0 for both haiku45 runs; T20.01 = 1 except sr80k-sonnet55-001 = 0.5?
- **Builder choice.** Pinned in tests/test_fi_grading_live_runs.py after fixing a false negative (EPN/SPN 'reconnected sites without ESO instruction') and several false positives: Ofgem's 200 MW 'net of ... trains' read as the rail threshold; 'setting' read as 'sets'; 'DNO reports' read as 'no reports'; 'DNOs to notify' read as a recommendation; 'before ESO was informed' read as a communications issue; 'restoration process' read as a compliance concern.
- **Alternatives.** Change any pinned value the reviewer reads differently, and fix the pre-screen on that phrasing.
- **Impact.** These are the only real-text checks of the new pre-screens outside the pilot. Example: sr80k-sonnet55-001 F28 'UKPN's Eastern and South Eastern networks reconnected sites without ESO instruction, contrary to OC6.6.4 as Ofgem cites it' gives T14.03 = 1.
- **Evidence.** tests/test_fi_grading_live_runs.py PINNED; tests/fixtures/sr_live (six runs); REVIEW_CHECKLIST.md G and G1. The builder regraded the six runs with the installed key and the pinned values match.
- **Compiler's note.** First person replaced (the earlier verifier).
- **Compiler's note.** Updated to key 0.1.1 (decision 79): T14.05 gained a partial on three of increment A's runs.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-g2"></a>

##### FI-G2 — The two real FI runs: pinned outcomes and remaining judge/pre-screen disagreements

**P1** · 60 min · FI (`gb-2019-full-investigation`) · Criteria: T09.04, T11.03, T13.04, T13.05, T14.01, T18.04, T20.04, T07.01, T10.03b · Checklist: G2  

- **Question.** Are the pinned outcomes on the pilot (fi-pilot-opus55-001) and the first panel run (fi-panel-opus55-001) right for those texts: no severe flag, accounting trap or binding cap; the corrected criteria (FI-B19, FI-B20, FI-C2, FI-C4, FI-E1); and the eight remaining judge/pre-screen disagreements, each with the builder's view of who was right?
- **Builder choice.** Both runs are fixtures (tests/fixtures/fi_live) with their judge outputs, which were produced with key 0.1.0 and are re-bound to key 0.1.1 in the tests only (no judge-visible text changed). The builder's reading of the remaining disagreements (pre-screen → judge): pilot T09.04 0 → 0.5 (borderline; decision 43's call), T11.03 1 → 0.5 (borderline: the summary's 'some through their own protection' covers the refinery), T13.04 1 → 0.5 (pre-screen right: the T13 request did not show F13), T14.01 1 → 0.5 (borderline: requirements named, their terms not stated), T18.04 0.5 → 1 (borderline: UKPN's reconnection fix as the LFDD action) and T20.04 1 → 0.5 (judge right); panel T13.05 1 → 0.5 (borderline: the judge gives the pilot 1 for the same content) and T14.01 1 → 0.5. Pilot zeros read as genuine: T07.01 (only the open root cause of the speed-signal discrepancy, the key's own negative example) and T10.03b (no Class 387).
- **Alternatives.** Overrule any pinned outcome you read differently and have the pre-screen fixed on that phrasing (new key version). Side with the judge on every borderline case. Require the rest of the FI panel to get the same sweep before any FI result is reported (checklist section G).
- **Impact.** Best available (decided values, judge proposals for judge criteria, else the pre-screen; provisional): pilot 84 full / 20 half / 2 zero (key 0.1.0: 83 / 21 / 2); panel run 86 / 20 / 0 (key 0.1.0: 78 / 20 / 8, six of the zeros from a false suspected SF1). Judge/pre-screen disagreements: pilot 13 → 6, panel 10 → 2. No severe flag, trap or binding cap on either run. Every auto_assisted_human value and judge proposal still awaits a human; no decisions file exists.
- **Evidence.** DECISIONS 76–80; tests/test_fi_grading_live_runs.py (`FI_EXPECTED`, `test_fi_remaining_judge_prescreen_disagreements`, `test_fi_best_available_content_counts`, `test_no_severe_flag_trap_or_cap_on_the_real_runs`); tests/fixtures/fi_live/README.md and runs.json; REVIEW_CHECKLIST.md section G and row G2.
- **Compiler's note.** Rewritten on review to checklist row G2 of key 0.1.1 (both real FI runs). The earlier card covered only the pilot under key 0.1.0 (83/21/2, 13 disagreements) and asked for a G2 row, which the checklist now has.

Decision: [ ] accept  [ ] change to: ____

### 2.3 P2 items (55 items, 11 h 55 min)

P2: choices that change few or no live values today, process rules and key-wide checks.

#### MVP — `gb-2019-electrical-disturbance` (key 0.3.1) — P2, 17 items, 4 h 10 min

<a id="mvp-a1"></a>

##### MVP-A1

**P2** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D1.1, D1.2, D1.3, D1.4, D1.N, D2.1, D2.2, D2.3, D2.4, D2.5, D3.1, D3.2, D3.3, D3.4, D3.5, D4.1, D4.2, D4.3, D4.4 · Checklist: A1  

- **Question.** Are the four dimensions and 19 criteria a fair reduced scope for the brief (initiating event; generation-trip and frequency sequence; supported explanations versus unresolved causes)?
- **Builder choice.** Four dimensions: D1 (D1.1–D1.4, D1.N), D2 (D2.1–D2.5), D3 (D3.1–D3.5) and D4 (D4.1–D4.4). Rail, essential services, communications, compliance and recommendations are out of scope.
- **Alternatives.** Add criteria (for example Hornsea reactive-power behaviour or DRC clearance as its own criterion). Drop or merge criteria (D1.N into D1.1; D3.5 into D3.4; D2.5 into D2.1–D2.4).
- **Impact.** Adding or removing criteria changes every run's per-criterion table. Decision 17 found that the MVP does not discriminate: gb2019-v2-opus55-003 has a 1.0 proposal or automatic value on all 19 criteria (local regrade with key 0.3.1), and every panel run is near full credit. Scope is the main lever if the MVP is kept as a benchmark.
- **Evidence.** REVIEW_CHECKLIST.md A1; answer_key.json `dimensions`; DECISIONS.md decision 17 ("the MVP's subject matter is too shallow to discriminate"); brief and REPORT_EXPECTATIONS in tasks/gb_2019_electrical_disturbance/prompt.py.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-a4"></a>

##### MVP-A4

**P2** · 30 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D4.2, D4.4, D1.4 · Checklist: A4 · Cross-task: [XT-20](#xt-20)  

- **Question.** Do the reconstructed records (R03, S01, S03, S04) avoid giving the agent conclusions the key rewards without evidence?
- **Builder choice.** Bundle 1.1.0 removed the derived BST times and intervals, the 737 MW subtraction, the UTC/BST equivalences and the known/not-established labels (decision 9). The frequency landmarks appear only in the R01 CSV.
- **Alternatives.** Identify a remaining leak and edit the bundle (new bundle version, key rebind, regrade). Candidates: S04 B1–B3 quote Ofgem's 'We have established …' / '… has not been established' side by side, which separates mechanism from root cause; R03 section G gives 'operated as designed'.
- **Impact.** Any bundle edit changes bundle_sha256, so every decisions file is invalidated and all four panel runs must be regraded. Decision 17 notes that all four models labelled the open causes and derived the times easily.
- **Evidence.** S04 L56-L59 (the bundle line adds a [reported] tag after 'three'): "We have established that the steam turbine tripped initially because of a discrepancy in the three independent speed sensors ... The root cause of the discrepancy in the speed sensors has not been established." (the same wording is on OFG PDF p31). S04 L64-L66 ('preliminary view'). R03 L86-L88 (G1: 'operated as designed'). DECISIONS.md decisions 9 and 17.
- **Compiler's note.** Bundle 1.1.0 S04 L56-L57 reads 'three [reported] independent speed sensors'; the quote omitted the value-status tag.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-a5"></a>

##### MVP-A5

**P2** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Checklist: A5 · Cross-task: [XT-15](#xt-15)  

- **Question.** Are the content scale (1 satisfied / 0.5 substantively partial / 0 wrong or absent) and the binary evidence-support scale (1 supported / 0 otherwise, uncited = 0) acceptable?
- **Builder choice.** As stated. Evidence support of 1 needs a specific citation of a primary keyed span. How other citations are routed is covered in MVP-B20.
- **Alternatives.** Give 0.5 evidence support for context-span or broad citations. Give partial credit to correct findings that are uncited.
- **Impact.** No live run has uncited factual findings (flags.uncited_factual_findings is empty for all five), so the binary scale only matters in the routing cases (MVP-B20, MVP-X1).
- **Evidence.** answer_key.json conventions.content_scale and evidence_support_scale; REVIEW_CHECKLIST.md A5.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-a6"></a>

##### MVP-A6

**P2** · 5 min · MVP (`gb-2019-electrical-disturbance`) · Checklist: A6 · Cross-task: [XT-17](#xt-17)  

- **Question.** Confirm there is no pass threshold, overall score or ranking: measures are reported per dimension and per criterion, and the Karotte score measures completion only.
- **Builder choice.** Yes (decision 7; conventions.no_pass_threshold).
- **Alternatives.** Add per-dimension summary scores or a threshold.
- **Impact.** No criterion value changes. Panel comparisons stay as counts of full / half / zero.
- **Evidence.** answer_key.json conventions.no_pass_threshold; DECISIONS.md decision 7.
- **Compiler's note.** Priority raised from P3 to P2 on review, to match FI-A6: both decide the departure from the handoff's scoring contract (XT-17 (a)).

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-a7"></a>

##### MVP-A7

**P2** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D2.5, D3.5 · Checklist: A7  

- **Question.** Does the brief's 'Report expectations' list name deliverables only (no values, clocks, protection requirement or below-49-Hz convention) while still covering every criterion?
- **Builder choice.** Five bullets in prompt.py REPORT_EXPECTATIONS, mapped as follows (checked by a test). D1.1, D1.2 and D1.N: the initiating event. D1.3 and D1.4: protection. D2.1–D2.4: losses. D2.5: 'the clock that record uses'. D3.1–D3.4: 'each minimum, the recovery to 50 Hz and the time below 49 Hz'. D3.5: 'the limits of the data's sampling'. D4: mechanism versus unexplained, with status labels.
- **Alternatives.** Prescribe the below-49-Hz convention, which would make the D3.5 convention element trivial. Or drop 'the clock that record uses', which would leave the D2.5 clock-basis requirement unannounced.
- **Impact.** The D2.5 and D3.5 method requirements rest on these bullets. haiku45-001's D2.5 is 0.5 only because it never states the clock S01 uses. 'each minimum' is the brief's only basis for D3.1 (see MVP-B7).
- **Evidence.** prompt.py REPORT_EXPECTATIONS: 'stating the clock basis (UTC offset) of every time you give and, for times taken from a record, the clock that record uses and any conversion you applied'; 'each minimum, the recovery to 50 Hz and the time below 49 Hz, stating how you computed them and the limits of the data's sampling'. REVIEW_CHECKLIST.md A7.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b13"></a>

##### MVP-B13

**P2** · 5 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D2.4, D4.3 · Checklist: B13 · Cross-task: [XT-14](#xt-14)  

- **Question.** Should describing GT1B as an automatic trip cap both D4.3 and D2.4 at 0.5?
- **Builder choice.** Yes: contradiction gt1b_automatic, cap_half on both criteria.
- **Alternatives.** Cap only D4.3 (the mechanism) and leave D2.4 (size and time) uncapped. Or set D4.3 to 0.
- **Impact.** No live run triggers it. A synthetic 'GT1B (187 MW) tripped automatically at 16:53:58.6 BST (T + 84.613 s, T = 16:52:34 ± 0.5 s)' gets D2.4 capped at 0.5 despite the correct MW, time and datum, so one error costs two criteria.
- **Evidence.** APP PDF p45: "GT1B Manual shutdown command +83.897 Sec". ESO PDF p20 (printed 21): "The second gas turbine (GT1B) was manually tripped by the RWE operational staff in response to high steam pressures around 30 seconds later." OFG PDF p31: "the plant operators made the decision to manually trip the other operational gas turbine due to safety risks". S03 L28-L29; S04 L29-L33.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b15"></a>

##### MVP-B15

**P2** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D1.3, D2.1, D2.2, D2.3, D2.4, D2.5 · Checklist: B15 · Cross-task: [XT-14](#xt-14)  

- **Question.** Is clause-based entity binding acceptable for D1.3 and D2.1–D2.5, including 0.5 for GT1A/GT1B values swapped (187 and 210 MW are within 25% of each other)?
- **Builder choice.** A value counts for a unit or circuit end only if it describes it. The circuit name 'Eaton Socon–Wymondley' is masked, so it does not count as an end. A structured quantity and event_time belong to the first entity the statement names.
- **Alternatives.** Score swapped GT1A/GT1B values 0, as a distinct error. Bind structured values by best match instead of first entity.
- **Impact.** No live run swaps values. opus55-002 F10 lists all three Little Barford units in one statement, with a 641 MW station-total quantity and an ST1C event_time; binding still credited the D2.2 and D2.3 MW from the statement. Known limitation: lists such as 'GT1A/GT1B at 16:53:31/16:53:58' cannot be bound.
- **Evidence.** answer_key.json conventions.entity_binding and entity_masks. S03 L34-L36 (244 / 210 / 187 MW). R03 L43-L46.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b17c"></a>

##### MVP-B17c

**P2** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.4 · Checklist: B17 · Cross-task: [XT-05](#xt-05)  

- **Question.** Is the D3.4 duration-wording list wide enough for prose durations to be credited automatically?
- **Builder choice.** The list is: for, lasted, duration of, a total of, 'time below 49 Hz:', was, =, 'N s below'. Other prose seconds go to a human. Seconds worded as an offset ('68 s after the fault') do not fit.
- **Alternatives.** Widen the list (for example 'spent', 'remained below … for', 'persisted'). Or always send prose durations to a human.
- **Impact.** No live grade changes: each panel run's D3.4 is credited from a structured quantity. Report-only candidates are left unsettled, however: opus55-003's executive-summary '33' and sonnet55-001's '34' ('no wording next to it makes it a duration below 49 Hz'). haiku45-001 F09's '76 seconds' is correctly not credited.
- **Evidence.** answer_key.json conventions.unit_note; R01 rows:821-856; REVIEW_CHECKLIST.md B17 (last sentence).

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-dec27"></a>

##### MVP-DEC27

**P2** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.1, D3.2, D3.3, D3.4 · Checklist: no row · Cross-task: [XT-06](#xt-06)  

- **Question.** When a structured quantity in the landmark window is outside tolerance and nothing else in that finding is within tolerance, should D3 stay an automatic 0 (with a note) even if a correct value appears in another finding or in the report?
- **Builder choice.** Yes. This is the open choice left for the reviewer in decision 27.
- **Alternatives.** Send the criterion to a human. Or credit the best candidate anywhere in the submission.
- **Impact.** No live run is in this situation. It would matter for a submission whose structured minimum is the 48.8 Hz LFDD trigger level while 48.787 Hz appears elsewhere.
- **Evidence.** DECISIONS.md decision 27 ('Open choice for the reviewer: a wrong structured value with a correct value elsewhere stays an automatic 0 with a note'). conventions.unit_note. ESO PDF p13 (printed 14): "16:53:49.398 Frequency breaches 48.8Hz trigger level resulting in LFDD."

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b18"></a>

##### MVP-B18

**P2** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.1, D3.2, D3.3, D3.4 · Checklist: B18 · Cross-task: [XT-04](#xt-04)  

- **Question.** Should D3 evidence support of 1 require all of: an R01 time or row citation covering the landmark (for D3.4, the first and last samples below 49 Hz), R01 retrieved, R01 analysed with run_python and, for D3.4, a derivation?
- **Builder choice.** Yes. A missing run_python analysis or missing derivation sends the criterion to a human rather than scoring 0.
- **Alternatives.** Drop the run_python requirement, so the citation suffices. Score 0 instead of routing to a human.
- **Impact.** All four panel runs get D3.1–D3.4 evidence automatic 1: runs.json shows R01 was analysed with run_python in all five runs. Live run 001 gets D3.1 evidence automatic 1 while its content is pending.
- **Evidence.** Key D3.x auto.evidence; runs.json trace_info.r01_analysed_with_python = true for all five runs. R01 row:780, row:830, row:1037, rows:821-856.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b20"></a>

##### MVP-B20

**P2** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D2.2, D2.4 · Checklist: B20 · Cross-task: [XT-15](#xt-15)  

- **Question.** Are the context-span designations and the citation-width routing rule acceptable?
- **Builder choice.** Context spans: R03 L14-L17, R03 L7-L9, R03 L22, S01 L6 (for D2.1), S03 L6-L9 (for D2.2–D2.4), R03 L36-L37 (for D2.5), R01 L22-L23 (for D3.1) and R01 L6. Routing: a citation more than 3× a keyed span (floor 8 lines), half a document or more, or outside the keyed spans goes to a human rather than failing.
- **Alternatives.** Make the clock headers primary wherever the clock basis is assessed. Raise the width multiplier or floor (for example 10×, or 20 lines). Fail citations outside the keyed spans.
- **Impact.** opus55-002 D2.2 and D2.4 evidence proposals are pending: F10 cites S03 L21-L37 and S04 L19-L33 ('cited range much larger than the keyed span'). For D1.N and D1.2 routing see MVP-X1.
- **Evidence.** answer_key.json conventions.visible_evidence_roles and alternative_evidence. S03 L23-L29 (keyed) versus opus55-002 F10's citation of S03 L21-L37. REVIEW_CHECKLIST.md B20 and A5.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b22"></a>

##### MVP-B22

**P2** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D2.1 · Checklist: B22 · Cross-task: [XT-03](#xt-03)  

- **Question.** Should an explicitly labelled UTC time (15:52:33.728Z) earn full D2.1 time credit as the same instant, while a UTC reading written as BST or with no clock label earns 0.5 (values only)?
- **Builder choice.** Yes. Prose times without an offset are read as BST unless followed by Z or UTC. A clock label after a range is not applied to both ends; the frozen MVP grader keeps this limitation (DECISIONS.md, increment A review fixes).
- **Alternatives.** Require every chronology time on BST, as the brief asks for a stated clock basis. Send unlabelled UTC-looking times to a human.
- **Impact.** opus55-002 (F05 event_time 15:52:33.835Z) and opus55-003 (F06, 15:52:33.835Z) are credited from Z-labelled times. Both also give BST (opus55-002's report: 'i.e. 16:52:33.728–.835 BST'; opus55-003 F06: '(16:52:33.728–.835 BST)'), so a BST-only rule would not change them. No run writes a UTC reading as BST.
- **Evidence.** APP PDF p41: "began de-loading turbines at 15.52.33.728 and completed the de-load at 15.52.33.835" (operator's UTC sentence); the same page gives "(16:52:33:728 to 16:52:33:835)" in local time. ESO PDF p12 (printed 13): "16:52:33.728 Hornsea started deloading". S01 L6, L40-L43.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b27"></a>

##### MVP-B27

**P2** · 5 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D1.4 · Checklist: B27 · Cross-task: [XT-13](#xt-13)  

- **Question.** Should 'performed as required' and 'met the requirement' count as the D1.4 protection assessment?
- **Builder choice.** Yes, matching the brief's wording. They count alongside 'as designed', 'as expected', 'correctly', 'in line with the design', 'in compliance' and 'within the 80 ms'.
- **Alternatives.** Accept only the sources' own words ('as designed', 'in line with the design', 'in compliance').
- **Impact.** All five runs are credited through 'within the 80 ms' wording in their protection findings, so no live grade changes.
- **Evidence.** APP PDF p17: "the electricity transmission network operated as designed and in line with standards". ESO PDF p16 (printed 17): "The transmission system protection operated in line with the design and in compliance with the Grid Code requirements on fault clearance". ESO PDF p3 (printed 4): "The protection systems operated correctly". R03 L86-L88, L102-L104.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-dec19"></a>

##### MVP-DEC19

**P2** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D2.1, D2.5 · Checklist: no row · Cross-task: [XT-03](#xt-03)  

- **Question.** Should frozen bundle 1.1.0 keep S01's incorrect clock rationale as a known erratum, or be corrected with a new bundle version, a key rebind and a regrade?
- **Builder choice.** Keep it frozen (decisions 19 and 26): the instants are correct and the erratum is recorded. The key's D2.1 tolerance note still calls the UTC basis 'an inference stated in S01'.
- **Alternatives.** Correct S01 L6 to say the log is rendered in UTC while the operator's published timeline uses local time.
- **Impact.** sonnet55-001 F20 repeats the erratum ('The Hornsea log is UTC by inference') and labels clock alignment unresolved. A correction changes bundle_sha256 and invalidates decisions bound to 1.1.0 for the four panel runs.
- **Evidence.** S01 L6: 'Clock reference: UTC, explicit Z suffix; BST = UTC+01:00 (the operator labels no clock; UTC is inferred).' Ørsted's appendix uses local time: APP PDF p40 "16:52:33:490" and APP PDF p41 "(16:52:33:728 to 16:52:33:835)"; UTC appears in one sentence only, APP PDF p41 "began de-loading turbines at 15.52.33.728 and completed the de-load at 15.52.33.835". DECISIONS.md decisions 19 and 26.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-x1"></a>

##### MVP-X1

**P2** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D1.N, D1.2 · Checklist: no row · Cross-task: [XT-12](#xt-12)  

- **Question.** Should D1.N's primary keyed spans include the initiating-fault lines, since full content credit needs only the initiator identified?
- **Builder choice.** D1.N's primary spans are only the other-trip records (R03 L67-L72, L73-L77), with R03 L22 as context.
- **Alternatives.** Add R03 L36-L37 and L25-L27 as primary spans for D1.N. Or require ruling out (MVP-B10) so the spans match the content rule.
- **Impact.** opus55-002 (F01 cites R03 L36-L38) and haiku45-001 (F02/F04 cite R03 L25-L27, L36-L37) get D1.N content 1.0 but evidence pending ('citations do not overlap the keyed spans'). haiku45-001's D1.2 evidence is also pending: its fault time was matched to F06 (R03 L44-L46, the breaker-open time 16:52:33.560, within ±1 s) rather than F02.
- **Evidence.** answer_key.json D1.N visible_evidence. R03 L36-L37 ('Single (blue) phase to earth fault'); R03 L73-L77.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-x3"></a>

##### MVP-X3

**P2** · 60 min · MVP (`gb-2019-electrical-disturbance`) · Checklist: no row · Cross-task: [XT-20](#xt-20)  

- **Question.** Are the reconstructed records R03, S01, S03 and S04 realistic and faithful to their sources in wording, layout and record structure, as needed before grades can be final?
- **Builder choice.** Every line is provenance-verified against a source passage (decision 5), but no domain expert has reviewed them for realism.
- **Alternatives.** Request edits, which means a new bundle version, a key rebind and a regrade.
- **Impact.** Any edit invalidates bindings and requires regrading all five runs. Otherwise no score changes.
- **Evidence.** GB_2019_MVP.md 'What is provisional'. R03 L4: 'RECONSTRUCTED FOR EVALUATION FROM PUBLISHED RECORDS'. S01 and S03 L4: 'SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE'. private/provenance.json.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-e"></a>

##### MVP-E

**P2** · 15 min · MVP (`gb-2019-electrical-disturbance`) · Checklist: E (sign-off)  

- **Question.** Sign-off of key 0.3.1 in checklist section E (approve, approve with changes, or reject), with a second domain reviewer as the handoff requires before benchmark findings are reported. Tick accept to approve with exactly the changes decided on the other cards (none if all were accepted); tick change to reject the key or to name further changes.
- **Builder choice.** Pending; review.status = 'pending_domain_review'. After sign-off the builder publishes a new key version (0.3.1 is never edited in place), regrades every run, and re-issues the decisions files.
- **Alternatives.** Approve as is (status 'reviewed' with no value changes), or reject.
- **Impact.** Until it is signed, every grade of all five live runs is provisional. Any change produces a new key version, and decisions bound to 0.3.1 (by version or sha256) are rejected.
- **Evidence.** REVIEW_CHECKLIST.md section E; answer_key.json review.note; GB_2019_MVP.md 'What is provisional'.
- **Compiler's note.** Decision line clarified on review: accept/change did not map onto approve/reject.

Decision: [ ] accept  [ ] change to: ____

#### SR — `gb-2019-system-response` (key 0.1.1) — P2, 25 items, 4 h 35 min

<a id="sr-a1"></a>

##### SR-A1

**P2** · 20 min · SR (`gb-2019-system-response`) · Criteria: T04.03, T05.03, T08.03 · Checklist: A1 · Cross-task: [XT-21](#xt-21)  

- **Question.** Are the three handoff adaptations acceptable: T04.03 keeps only the sampling-uncertainty half (rail deferred), T05.03 distinguishes demand restoration from frequency recovery and from untimed 'other services' instead of 'transport recovery', and T08.03 points at S06 instead of S12?
- **Builder choice.** Adapt the three criteria to what bundle 0.1.0 holds (origin handoff_adapted with an 'adaptation' note), keeping the other 57 criteria as handoff/handoff_split.
- **Alternatives.** Keep the handoff wording and mark T04.03/T05.03 not gradable in increment A (defer with T04.02); or move the 1,300-1,500 MW estimate into S12 (bundle change, new bundle hash, rebuild of the key binding).
- **Impact.** T04.03: 1 on five runs, 0.5 on sr80k-haiku45-001. T05.03: 1 on sr80k-opus55-001, sr80k-sonnet55-001, sr30k-sonnet55-001, sr80k-haiku45-001 (judge; pre-screen 0.5), 0.5 on sr30k-opus55-001, 0 on sr30k-haiku45-001. T08.03 values in SR-D-T08.03. Deferring T04.03/T05.03 would remove these values from all six runs; no expected value changes otherwise.
- **Evidence.** ORR PDF p4: "shut down within 200ms of the frequency dropping below 49.0Hz"; OFG PDF p32: "Our lower bound for total estimated distributed generation lost across the event is 1,300MW, and the loss could be as high as 1,500MW."; Visible/key locators: key criteria[].adaptation for T04.03/T05.03/T08.03; T08.03 visible S06 L102-L103, S06 L119-L120; T05.03 context R07 L139-L141 ('no DNO operational logs')

Decision: [ ] accept  [ ] change to: ____

<a id="sr-a2"></a>

##### SR-A2

**P2** · 5 min · SR (`gb-2019-system-response`) · Criteria: T04.02 · Checklist: A2 · Cross-task: [XT-19](#xt-19)  

- **Question.** Is it acceptable that T04.02 (rail protection threshold and 200 ms response) is deferred to increment B and that no criterion needs DNO asset logs or a second control room, which bundle 0.1.0 does not hold?
- **Builder choice.** Defer T04.02 (key deferred_criteria: rail evidence S08/ORR is increment B); require nothing the bundle cannot support (decision 29).
- **Alternatives.** Add a rail record to the system-response bundle and grade T04.02 now; or drop T04.02 from the handoff mapping entirely.
- **Impact.** No current score: T04.02 is not graded on any of the six runs. Grading it would add a criterion every run would fail (no rail record in the bundle).
- **Evidence.** ORR PDF p4: "shut down within 200ms of the frequency dropping below 49.0Hz"; Visible/key locators: key deferred_criteria[T04.02]; DECISIONS 29

Decision: [ ] accept  [ ] change to: ____

<a id="sr-a4"></a>

##### SR-A4

**P2** · 60 min · SR (`gb-2019-system-response`) · Checklist: A4 · Cross-task: [XT-20](#xt-20)  

- **Question.** Do the reconstructed records (S01, S03-S07, S12, R03, R08, R10, witness cards) avoid leaking conclusions the key rewards without evidence?
- **Builder choice.** Records keep only the sources' own wording; S06 lists DG estimates by source in printed order (E1-E23) without builder stage headings or sums; landmarks only in the R01 CSV; cross-source conflicts only in private provenance (decisions 9, 30, 31).
- **Alternatives.** Further strip or relabel specific lines; or accept some builder framing as fair context.
- **Impact.** Not measured per run; a leak would inflate T08.01/T08.05/T17.02/T17.04 credit on runs that consulted S06/S12 (opus and sonnet both panels).
- **Evidence.** E3C PDF p12: "On 9 August, there were five significant modes of embedded generator loss."; Visible/key locators: bundle S06 Part 3 E1-E23; S12 Section C heading; R05 (no KNOWN SOURCE CONFLICTS); DECISIONS 31

Decision: [ ] accept  [ ] change to: ____

<a id="sr-a5"></a>

##### SR-A5

**P2** · 15 min · SR (`gb-2019-system-response`) · Checklist: A5 · Cross-task: [XT-15](#xt-15)  

- **Question.** Are the content scale (1/0.5/0), evidence-support scale (1/0), the routing of citations outside keyed spans to human review, and the rule that a record citation counts as obtained when the document it restates was retrieved acceptable?
- **Builder choice.** Content 1/0.5/0, evidence 1/0; alternative citations never auto-failed (sent to a human); route 'document' counts a record as obtained.
- **Alternatives.** Fail alternative citations automatically; require the record's own tool call (no document route).
- **Impact.** Verified on the six runs: no citation was not obtained and no record was cited via the document route only (records_cited_via_document_only = 0 on all six), so the route rule changes nothing today. Alternative citations ('citations do not overlap the keyed spans') are pending for a human on 17 criterion rows across five runs (haiku30k 5, haiku80k 5, opus80k 3, sonnet80k 3, sonnet30k 1).
- **Evidence.** No source passage (process or grader rule). Visible/key locators: key conventions.content_scale, evidence_support_scale, alternative_evidence

Decision: [ ] accept  [ ] change to: ____

<a id="sr-a8"></a>

##### SR-A8

**P2** · 15 min · SR (`gb-2019-system-response`) · Checklist: A8 · Cross-task: [XT-18](#xt-18)  

- **Question.** Is the assessment-mode split right: 4 auto_numeric (R01 landmarks, below-49-Hz duration), 32 auto_assisted_human (numbers, times, accounting bases proposed for a human), 24 judge (explanations, distinctions, labelling)?
- **Builder choice.** As listed in key judge.criteria and criteria[].assessment_mode; the judge never decides auto modes.
- **Alternatives.** Move e.g. T03.04/T04.03 or the mechanism criteria T07.01-T07.03 to judge, or some judge criteria (T16.02, T09.05) to auto_assisted_human.
- **Impact.** Determines who decides each value on all six runs (judge proposals exist only for the 24 judge criteria on the three 80k runs). Example: sr80k-opus55-001 T07.01 is auto_assisted_human, so the judge's 0.5 is recorded and ignored (auto 1).
- **Evidence.** No source passage (process or grader rule). Visible/key locators: key judge.criteria; criteria[].assessment_mode; DECISIONS 32

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b1"></a>

##### SR-B1

**P2** · 30 min · SR (`gb-2019-system-response`) · Criteria: T03.01, T03.02, T03.03, T04.01, T04.03, T07.01, T01.02, T01.03b · Checklist: B1 · Cross-task: [XT-01](#xt-01)  

- **Question.** Is reusing the MVP key 0.3.1 matchers (MVP checklist B1-B26 carrying over) acceptable when parity with the MVP grader is tested on only eight pairs, with the stated divergences intended?
- **Builder choice.** Reuse D1.1-D1.4, D2, D2.5, D3.1-D3.5, D4.1-D4.4 and D1.N as T counterparts; test parity on four MVP v2 runs for eight pairs only; intended divergences T02.03b/D2.4, T02.04/D2.5, T06.01/D4.1, T16.01/D1.N.
- **Alternatives.** Require parity on every reused criterion; or drop the MVP carry-over and review each SR matcher afresh.
- **Impact.** Re-run locally on tests/fixtures/live (MVP v2): T02.03b 1 vs D2.4 0.5 (opus55-002); T02.04 0.5 vs D2.5 1 (opus55-003, sonnet55-001); T06.01 1 vs D4.1 0.5 (haiku45-001); T16.01 0/0.5 vs D1.N 1 (all four). The divergences that move the six SR runs are itemised in SR-B5, SR-D-T06.01 and SR-D-T16.01.
- **Evidence.** No source passage (process or grader rule). Visible/key locators: tests/test_sr_grading_live.py PAIRS; key changes[0]; MVP private/REVIEW_CHECKLIST.md B1-B26

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b6"></a>

##### SR-B6

**P2** · 5 min · SR (`gb-2019-system-response`) · Criteria: T03.04 · Checklist: B6 · Cross-task: [XT-04](#xt-04)  

- **Question.** For T03.04, should full credit need the 1-s sampling stated plus a landmark to three decimals (or the value precision stated), with a rounded report value (49.1 / 48.8 Hz) presented as the R01 minimum capping at 0.5?
- **Builder choice.** Full: 1-s sampling + 0.001 Hz landmark; partial one of two; rounded prose presented as the R01 value caps at 0.5.
- **Alternatives.** Require timestamps and values for all three landmarks; do not cap if the rounded value is attributed to ESO.
- **Impact.** T03.04 is 1 on all six runs (no cap fired; sr80k-haiku45-001 F24 gives ESO's 'approximately 49.1 Hz' as a reported value, not as the R01 minimum).
- **Evidence.** ESO PDF p12: "16:52:58 Frequency drop is arrested at 49.1Hz due to the delivery of frequency response products"; ESO PDF p13: "16:57:15 Frequency returns to 50Hz following over 1,000MW of response"; Visible/key locators: R01 L22-L23, R01 L26-L29, R01 row:830

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b8"></a>

##### SR-B8

**P2** · 5 min · SR (`gb-2019-system-response`) · Criteria: T06.05 · Checklist: B8  

- **Question.** For negative-polarity T06.05, is 1 when any Hornsea mechanism is given without the DRC as its cause (or the DRC is cleared) and 0 when the DRC is asserted as the cause right, and should 'no Hornsea mechanism assessed at all' also score 0 as the key's expectation says (the checklist row omits it)?
- **Builder choice.** full_if_any: drc_cleared or mechanism_given; expectation adds 0 when no mechanism is assessed.
- **Alternatives.** Score silence 1 (true negative polarity); require the DRC to be cleared explicitly for 1.
- **Impact.** T06.05 is 1 on all six runs (all give a Hornsea mechanism), so the silent case does not arise today.
- **Evidence.** ESO PDF p20: "Initially, Orsted understood that the Dynamic Reactive Compensator (DRC) was responsible for the rapid de-load of Hornsea-1."; ESO PDF p20: "Orsted have since concluded that the DRC worked as designed and was not the cause of the"; Visible/key locators: S01 L78-L79, S09 response:S09-ORS-05

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b11"></a>

##### SR-B11

**P2** · 5 min · SR (`gb-2019-system-response`) · Criteria: T09.01 · Checklist: B11  

- **Question.** Is 48.8 Hz as the stage-1/LFDD trigger sufficient for T09.01 without the England & Wales qualifier (T09.05 covers Scotland), with the trigger not to be presented as the measured minimum?
- **Builder choice.** Full: 48.8 Hz as stage 1 (or LFDD) trigger; hz_abs 0.001; E&W qualifier not required.
- **Alternatives.** Require 'England and Wales' for full credit.
- **Impact.** T09.01 is 1 on all six runs.
- **Evidence.** ESO PDF p13: "16:53:49.398 Frequency breaches 48.8Hz trigger level resulting in LFDD."; E3C PDF p24: "Stage 1 48.80 5"; Visible/key locators: R10 L84-L86, R10 L90, R10 L104, S05 L61-L63, S09 response:S09-DNO-01

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b16"></a>

##### SR-B16

**P2** · 5 min · SR (`gb-2019-system-response`) · Checklist: B16 · Cross-task: [XT-06](#xt-06)  

- **Question.** Should a key figure written without a unit ('vector shift ~150 (est.)') be listed for a human, never credited or failed automatically?
- **Builder choice.** Unitless figures are candidates for a human; the basis says so.
- **Alternatives.** Credit unitless figures when the context names the quantity; fail them.
- **Impact.** sr80k-opus55-001 T12.01c notes the secondary figure 'without a unit in F43' (value stays 0.5 for the missing band). No other current value depends on it.
- **Evidence.** No source passage (process or grader rule). Visible/key locators: key conventions.unit_note; accounting.rules

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b18"></a>

##### SR-B18

**P2** · 5 min · SR (`gb-2019-system-response`) · Criteria: T03.01, T03.02, T03.03, T04.01 · Checklist: B18 · Cross-task: [XT-04](#xt-04)  

- **Question.** For R01 landmarks, should evidence support 1 need an R01 time/row citation covering the landmark, R01 obtained, and a run_python analysis or the samples read through query_frequency, otherwise a human decides?
- **Builder choice.** Automated evidence support for R01 only under these three conditions; T04.01 also needs a derivation and run_python.
- **Alternatives.** Accept any R01 citation; require run_python for all landmarks.
- **Impact.** All decided R01 evidence values on the six runs are 1 ('R01 analysed with run_python'); no run is currently routed to a human by this rule.
- **Evidence.** No source passage (process or grader rule). Visible/key locators: R01 row:780, row:830, row:1037, rows:821-856; key criteria T03.01-T04.01 auto.evidence

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b20"></a>

##### SR-B20

**P2** · 10 min · SR (`gb-2019-system-response`) · Criteria: T05.03, T06.01, T06.05, T12.04, T16.02, T16.03, T17.03 · Checklist: B20 · Cross-task: [XT-18](#xt-18)  

- **Question.** Should contradiction rules for judge criteria be pre-screen flags for the reviewer (flags.prescreen_contradictions) rather than caps on the judge's value, while still capping automated proposals for other criteria?
- **Builder choice.** Rules tie subject to causal/failure wording and list non-assertions; judge criteria: flag only, hidden from the judge (decision 35).
- **Alternatives.** Cap the judge's value on a contradiction hit; show hits to the judge.
- **Impact.** No prescreen contradictions or assertion conflicts fire on any of the six runs; the choice changes no current value. Cost recorded in decision 35: a judge that misses a real contradiction is caught only by the reviewer.
- **Evidence.** No source passage (process or grader rule). Visible/key locators: key criteria[].auto.contradictions; DECISIONS 35

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t01.01"></a>

##### SR-D-T01.01

**P2** · 5 min · SR (`gb-2019-system-response`) · Criteria: T01.01 · Checklist: D (rows T01.01) · Cross-task: [XT-13](#xt-13)  

- **Question.** Is T01.01 right: full when lightning is attributed to a fault on the Eaton Socon-Wymondley circuit (in one finding, or 'the fault' attributed to lightning with the circuit in another), 0.5 for the fault without its cause or lightning near the circuit without causation, 0 for another trip as initiator?
- **Builder choice.** Elements lightning_on_circuit / lightning_caused_fault + circuit / fault_on_circuit; the element note still says full credit 'also needs ... the fault type', which the rules do not require (fault type is T01.03a).
- **Alternatives.** Require the fault type for full credit (as the note implies); require NGET's attribution to be cited.
- **Impact.** T01.01 is 1 on all six runs.
- **Evidence.** ESO PDF p15: "At 16:52:33hrs, three almost simultaneous lightning strikes were recorded adjacent to the Eaton Socon – Wymondley circuit"; ESO PDF p15: "NGET by analysing their protection data confirmed that these lightning strikes were the cause of the circuit trip and reclose"; Visible/key locators: R03 L25-L27, R03 L36-L37, R03 L89-L90, R03 L102-L104, R03 event:R03-B3, R03 event:R03-C1, S09 response:S09-NGET-01, S09 response:S09-NGET-05

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t02.02-03"></a>

##### SR-D-T02.02-03

**P2** · 10 min · SR (`gb-2019-system-response`) · Criteria: T02.02a, T02.02b, T02.03a, T02.03b · Checklist: D (rows T02.02a, T02.02b, T02.03a, T02.03b) · Cross-task: [XT-14](#xt-14)  

- **Question.** Are the unit losses right (Hornsea 737 MW or 799 → 62 MW; ST1C 244; GT1A 210; GT1B 187 MW) with 10%/25% MW tolerance, 799 MW and 800 MW excluded unless paired with 62 MW, loss wording read in the value's sentence, swapped GT1A/GT1B values 0.5, and T02.03b needing the MW only (MVP D2.4 also needed the derived trip time)?
- **Builder choice.** Handoff MW tolerance; exclude_values for 799/800; T02.02a loss wording ('tripped', 'infeed') in the sentence unless the clause describes pre-event output.
- **Alternatives.** Require the trip time for GT1B as D2.4 did; credit 799 MW alone at 0.5.
- **Impact.** All four are 1 on all six runs. On MVP v2 opus55-002, T02.03b 1 vs D2.4 0.5 (trip time not required).
- **Evidence.** ESO PDF p13: "Little Barford ST1C 244 MW"; ESO PDF p13: "Little Barford GT1B 187 MW"; ESO PDF p12: "16:52:33.531 Hornsea was generating 799MW and absorbing 0.4MVAR"; APP PDF p41: "Hornsea 1A remained in operation at 62MW active power output"; Visible/key locators: S12 L17-L18, S12 L23-L24, S01 L36, S01 L42-L44, S01 event:S01-EV06a, S03 L34-L36, S04 L19-L33, S09 response:S09-RWE-03..05, S09 response:S09-ORS-03

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t04.01"></a>

##### SR-D-T04.01

**P2** · 10 min · SR (`gb-2019-system-response`) · Criteria: T04.01 · Checklist: D (rows T04.01) · Cross-task: [XT-05](#xt-05)  

- **Question.** Is 33 s (strictly below 49 Hz, zero-order hold, gaps > 1 s not bridged) the key value, with at-or-below 34 s, linear interpolation ~33.96 s and first-to-last 32 s within the full 1 s tolerance (half within 3 s)?
- **Builder choice.** Key value 33 s; alternative conventions accepted within tolerance; whether the convention is stated is T04.03.
- **Alternatives.** Make 34 s (at or below) the key value; give 32 s 0.5 (exactly 1 s off).
- **Impact.** T04.01 is decided 1 on all six runs. Conflicting account: the rail appendix prints 16 s below 49 Hz (a different measurement point).
- **Evidence.** ORR PDF p4: "The frequency remained below 49.0Hz for approximately 33 seconds"; APP PDF p48: "dropped below 49Hz for 16 seconds"; Visible/key locators: R01 time:16:53:40-16:54:14 BST, rows:821-856

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t07.02-03"></a>

##### SR-D-T07.02-03

**P2** · 5 min · SR (`gb-2019-system-response`) · Criteria: T07.02, T07.03 · Checklist: D (rows T07.02, T07.03) · Cross-task: [XT-14](#xt-14)  

- **Question.** Are T07.02 (GT1A tripped automatically on high steam-bypass pressure; full both, partial one) and T07.03 (GT1B tripped manually for safety; automatic trip caps 0.5) right?
- **Builder choice.** MVP D4.3 elements; mechanism vs root cause separated (root cause is T07.04).
- **Alternatives.** Require the 'about a minute' / '30 s later' timing; drop the automatic-trip cap.
- **Impact.** T07.02 and T07.03 are 1 on all six runs.
- **Evidence.** ESO PDF p20: "after approximately 1 minute the first gas turbine tripped due to a high-pressure excursion in the steam bypass system"; ESO PDF p20: "This trip occurred automatically and shut the gas turbine (GT1A) down."; APP PDF p46: "GT1B was manually tripped shortly after as a result of excessive steam pressure."; Visible/key locators: S03 L49-L52, S04 L26-L33, S04 L50-L52, S04 L60-L63, S03 event:S03-SOE-E6, S03 event:S03-SOE-E8, S09 response:S09-RWE-04, S09 response:S09-RWE-05

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t08.01"></a>

##### SR-D-T08.01

**P2** · 5 min · SR (`gb-2019-system-response`) · Criteria: T08.01 · Checklist: D (rows T08.01)  

- **Question.** Should T08.01 need vector-shift, RoCoF and the 49 Hz stage each placed separately for full credit (two of three for 0.5), with the LFDD-stage loss described but not required?
- **Builder choice.** Elements vs_stage, rocof_stage, uf_stage (49 Hz with protection/trip wording).
- **Alternatives.** Require the LFDD-stage DG loss as a fourth stage; accept vector shift + RoCoF as full.
- **Impact.** T08.01 is 1 on opus and sonnet (both panels; judge 1 on the 80k runs) and 0 on both haiku runs.
- **Evidence.** ESO PDF p12: "16:52:33 Approximately 150MW of embedded generation trips on vector-shift protection"; ESO PDF p21: "The net effect of this disconnection has been modelled as a 200MW loss of generation."; E3C PDF p12: "On 9 August, there were five significant modes of embedded generator loss."; Visible/key locators: S06 L46-L49, S06 L58-L61, S06 L94-L101, S06 L112-L120, S12 L19-L22, R10 L53-L56

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t09.05"></a>

##### SR-D-T09.05

**P2** · 5 min · SR (`gb-2019-system-response`) · Criteria: T09.05 · Checklist: D (rows T09.05)  

- **Question.** Should T09.05 need both the relay tolerance/time-delay explanation and the Scotland threshold distinction (SP Distribution's 22 MW at 48.8 Hz an incorrect setting; SPT not required until 48.5 Hz) for full credit?
- **Builder choice.** Elements tolerance and scotland; contradiction: E&W threshold applied to Scotland.
- **Alternatives.** Accept either for full; require the 48.787/48.792 Hz margin.
- **Impact.** T09.05 is 1 on opus and sonnet (both panels) and 0 on both haiku runs (judge 0 on sr80k-haiku45-001).
- **Evidence.** E3C-I PDF p11: "the +/-0.01Hz tolerance setting on the LFDD schemes"; OFG PDF p36: "SP Distribution erroneously disconnected 22MW in Scotland when system frequency fell below 48.8Hz"; Visible/key locators: S05 L66-L73, S05 L90-L93, S05 L102-L104, R10 L100-L103, R10 L111-L112

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t16.02"></a>

##### SR-D-T16.02

**P2** · 5 min · SR (`gb-2019-system-response`) · Criteria: T16.02 · Checklist: D (rows T16.02) · Cross-task: [XT-13](#xt-13)  

- **Question.** Is T16.02 right: full when transmission protection is stated as operating as designed/compliant (MVP D1.4 as_designed pre-screen), 0 when protection is blamed without evidence?
- **Builder choice.** Elements as_designed or within_requirement (80 ms); contradiction: protection said to have failed or been slow.
- **Alternatives.** Require both the 80 ms clearance and DAR as designed.
- **Impact.** T16.02 is 1 on all six runs (judge 1 on the 80k runs).
- **Evidence.** APP PDF p17: "the electricity transmission network operated as designed and in line with standards"; OFG PDF p28: "its fault clearance times for the two circuit breakers were under 75ms"; Visible/key locators: R03 L79-L83, R03 L86-L88, R03 L102-L107, S09 response:S09-NGET-03, S09 response:S09-NGET-09

Decision: [ ] accept  [ ] change to: ____

<a id="sr-d-t17.04"></a>

##### SR-D-T17.04

**P2** · 5 min · SR (`gb-2019-system-response`) · Criteria: T17.04 · Checklist: D (rows T17.04)  

- **Question.** Should T17.04 need all three kinds kept apart (attributed source disagreements, measurement limits, unresolved causes) for full credit and two for 0.5?
- **Builder choice.** Elements disagreement, measurement_limits, causal_uncertainty in any field.
- **Alternatives.** Require named examples of each kind (e.g. 1,878 vs 1,990; 1-s sampling; Little Barford root cause).
- **Impact.** T17.04 is 1 on all six runs (judge 1 on the 80k runs).
- **Evidence.** APP PDF p75: "We estimate that approximately 500 MW of embedded generation was lost in the incident."; ESO PDF p12: "16:52:33.531 Hornsea was generating 799MW and absorbing 0.4MVAR"; Visible/key locators: S12 L131-L152, R05 L92-L98, R05 L104-L114, R01 L28-L29, S03 L6-L9

Decision: [ ] accept  [ ] change to: ____

<a id="sr-f2"></a>

##### SR-F2

**P2** · 15 min · SR (`gb-2019-system-response`) · Checklist: F2 · Cross-task: [XT-18](#xt-18)  

- **Question.** Should the judge (merge_judge_proposals) decide nothing for auto modes, be bounded by accounting traps and suspected severe flags (contradiction rules only flagged), have evidence proposals bounded by the cited findings' obtained spans, and turn a 'supported' verdict that an automated numeric check contradicts into a conflict for a human?
- **Builder choice.** As in checklist F2 and decision 34; accept_judge cannot sign off a capped proposal.
- **Alternatives.** Let the judge's value stand for auto_assisted_human criteria where it reads report prose (e.g. T12.01a); cap judge values by contradiction rules.
- **Impact.** On the 80k runs the recorded judge proposal differs from the auto proposal on auto_assisted_human T07.01 (opus 0.5 vs 1), T04.03 and T12.01a (haiku 1 vs 0.5 / 0) and is ignored; judge-mode disagreements remain on opus T17.03 and haiku T05.03, T06.01. No assertion conflicts on any run.
- **Evidence.** No source passage (process or grader rule). Visible/key locators: environment/incident/sr_grading.merge_judge_proposals; DECISIONS 34, 39, 43

Decision: [ ] accept  [ ] change to: ____

<a id="sr-f3"></a>

##### SR-F3

**P2** · 5 min · SR (`gb-2019-system-response`) · Checklist: F3 · Cross-task: [XT-15](#xt-15)  

- **Question.** Should retrieval be checked across every route (request_document, request_data_return for S05/S06, query_frequency for R01, records from query_asset_log, query_control_log, interview_witness)?
- **Builder choice.** Ledger-based retrieval check across all nine tools' routes.
- **Alternatives.** Count only request_document retrieval.
- **Impact.** No citation on the six runs is to evidence never obtained (cited_but_never_retrieved = 0 on all six); data-return citations (S05/S06) are common on opus/sonnet runs.
- **Evidence.** No source passage (process or grader rule). Visible/key locators: trace.jsonl in each tests/fixtures/sr_live run; key conventions

Decision: [ ] accept  [ ] change to: ____

<a id="sr-x1"></a>

##### SR-X1

**P2** · 10 min · SR (`gb-2019-system-response`) · Criteria: T02.06, T05.03, T06.01, T09.03, T12.03, T17.03 · Checklist: no row · Cross-task: [XT-18](#xt-18)  

- **Question.** Is it acceptable to re-merge the 80k panel's judge outputs (produced with key 0.1.0) under key 0.1.1 ('rebound') without a new judge call, on the grounds that no judge-visible key text changed?
- **Builder choice.** Rebind: every opus request byte-identical; sonnet T02/T07/T08/T17 and haiku T02/T09 differ only in which findings are classified (decision 45; test_the_judge_saw_the_same_criteria_under_the_revised_key).
- **Alternatives.** Re-run the judge on all three 80k runs under 0.1.1 (paid call) before reporting judge-mode values.
- **Impact.** All judge-mode values (24 criteria per run) on sr80k-opus55-001, sr80k-sonnet55-001 and sr80k-haiku45-001 rest on the rebound outputs.
- **Evidence.** No source passage (process or grader rule). Visible/key locators: tests/fixtures/sr_live/runs.json judge_binding (key 0.1.0); DECISIONS 45
- **Compiler's note.** Checked while compiling: the stored judge outputs are bound to the key they were produced with (SR 0.1.0 for the sr80k runs, FI 0.1.0 for the pilot and the panel run); `sr_grading`/`fi_grading grade --judge` rejects them under the installed keys (JudgeOutputError: binding mismatch). The decision-45 re-binding exists only in tests (`rebound()` in tests/test_sr_grading_live_runs.py); see section 3.4.

Decision: [ ] accept  [ ] change to: ____

<a id="sr-x2"></a>

##### SR-X2

**P2** · 10 min · SR (`gb-2019-system-response`) · Checklist: no row · Cross-task: [XT-15](#xt-15)  

- **Question.** Is the evidence-support span rule right: a proposal of 1 needs a citation of a primary keyed span at most 3x its length (floor 8 lines/samples) and under half the document, otherwise a human decides?
- **Builder choice.** conventions.visible_evidence_roles (builder choice, not listed in the checklist).
- **Alternatives.** Allow wider spans (e.g. 5x or a whole section); fail over-wide citations as unsupported.
- **Impact.** Routes evidence support to a human for 'cited range much larger than the keyed span' on 43 criterion rows: sr30k-haiku45-001 14, sr30k-sonnet55-001 13, sr80k-sonnet55-001 10, sr30k-opus55-001 5, sr80k-opus55-001 1, sr80k-haiku45-001 0.
- **Evidence.** No source passage (process or grader rule). Visible/key locators: key conventions.visible_evidence_roles

Decision: [ ] accept  [ ] change to: ____

<a id="sr-x3"></a>

##### SR-X3

**P2** · 5 min · SR (`gb-2019-system-response`) · Criteria: T07.04 · Checklist: no row · Cross-task: [XT-08](#xt-08)  

- **Question.** Should T07.04's negative examples be corrected where their judge-visible 'why' says the bypass-valve failure is 'not in the evidence' and that a valve hypothesis 'names causes absent from the evidence', given that S12 F7 reproduces ESO's executive-summary valve wording (which B9/E1 treat as a conflicting account)?
- **Builder choice.** Examples kept from the draft: 'GT1A tripped because a steam bypass valve failed ...' (0, 'bypass-valve failure is not in the evidence and was not established (SF1)'); 'A faulty speed sensor may have ... a stuck bypass valve may have ...' (hypothesis, 0).
- **Alternatives.** Reword the rationale to 'asserted as established although ESO's wording is contradicted by RWE/Ofgem'; keep the values. Changing judge-visible text requires new judge calls.
- **Impact.** No current value changes (no run asserts a valve cause), but the text is shown to the judge on every judged run.
- **Evidence.** ESO PDF p4: "following the failure of a bypass valve to operate correctly"; Visible/key locators: S12 L148-L152 (F7: ESO executive-summary wording); key criteria[T07.04].examples.negative

Decision: [ ] accept  [ ] change to: ____

#### FI — `gb-2019-full-investigation` (key 0.1.1) — P2, 13 items, 3 h 10 min

<a id="fi-a2"></a>

##### FI-A2 — Whole key: nothing required beyond the bundle

**P2** · 20 min · FI (`gb-2019-full-investigation`) · Criteria: T14.05, T19.01 · Checklist: A2 · Cross-task: [XT-19](#xt-19)  

- **Question.** Is it right that no criterion requires evidence the bundle cannot supply (train running records, TCMS logs, airport/water/refinery logs, compliance test reports all being fixed not-held data returns), so criteria rest only on the published accounts the bundle restates?
- **Builder choice.** Missing evidence is served as fixed not-held data returns or is simply absent: no DNO asset logs, no GTR/Network Rail control logs beyond the published accounts, no HSP train running records, no Grid Code test reports or simulation studies, and no ESO communications log. Criteria use S08, S10, S11, R09, R11, R12 and the full R10, all restating the published reports.
- **Alternatives.** Reconstruct the missing records (e.g. TCMS event logs, DNO switching logs). Alternatively, drop or soften criteria whose facts appear only in report summaries.
- **Impact.** Not-held items are what T14.05 and T19.01 expect the agent to name as missing. On the pilot, T19.01 is judged 1. T14.05 is judged 0.5 because compliance test reports and simulation studies were not named as missing proof (see FI-D-T14.04-05). No criterion was found that needs a record the bundle lacks.
- **Evidence.** DECISIONS.md, increment B build outcome, 'Evidence still missing, accepted rather than invented'. APP p53: 'List of Outstanding Tests 70% capacity, Preliminary Frequency Response Tests on wind farm M1...'. APP p91: 'There are no direct tests for generator ride-through for fault and large frequency changes.' Visible: S10 L49-L57 (H07-H08 outstanding tests), S10 L72, S10 L91-L95.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-a5"></a>

##### FI-A5 — Re-bound increment A criteria (57 unchanged in key 0.1.0, 52 in 0.1.1)

**P2** · 20 min · FI (`gb-2019-full-investigation`) · Checklist: A5 · Cross-task: [XT-01](#xt-01)  

- **Question.** Should increment A's 60 criteria be re-bound with the same IDs, rules and tolerances, changing only T04.03, T05.02 and T05.03, so that increment A's review (SR checklist) carries over?
- **Builder choice.** The 60 criteria are re-bound from SR key 0.1.1 (sha e1c97c76…). Every locator was re-checked on the new bundle and none was re-pointed; R10 keeps increment A's lines 1-133. Increment A's flagged builder tolerances are inherited unchanged: generator-trip 2 s, protection time 1 ms, and reclose.
- **Alternatives.** Re-open SR items where the new evidence (S08, S10, S11, R09) supports further accepted alternatives or keyed spans. Alternatively, re-point keyed spans to the new documents.
- **Impact.** tests/test_fi_grading_live_runs.py shows that on increment A's six runs (sr30k/sr80k × haiku45/opus55/sonnet55) the re-bound criteria give the same content and evidence proposals, matched findings and caps as the SR grader. A sign-off of the SR checklist therefore applies here directly.
- **Evidence.** Key `reused_from` (key 0.1.1). `conventions.numeric_rules.source`: 'generator-trip, protection-time and reclose tolerances are builder choices flagged for review'. Each re-bound criterion carries `rebinding` (`changed` false). REVIEW_CHECKLIST.md A5, and section D rows marked 'R'.
- **Compiler's note.** Installed FI key 0.1.1 (decisions 77–80; FI checklist A5, B19): the pre-screen rules of re-bound T02.04, T05.03, T06.02, T08.04, T08.05 and T09.05 now also diverge from SR 0.1.1 (expectations, examples and keyed spans unchanged).

Decision: [ ] accept  [ ] change to: ____

<a id="fi-a6"></a>

##### FI-A6 — Reporting: provisional, no total, threshold or ranking

**P2** · 15 min · FI (`gb-2019-full-investigation`) · Checklist: A6 · Cross-task: [XT-17](#xt-17)  

- **Question.** Should content coverage, evidence support and assertion quality stay separate measures with no 100-point total, no pass at 70 and no ranking, unlike the handoff's scoring contract?
- **Builder choice.** There is no total, threshold or ranking. Each value carries its source (auto, judge, human, severe_flag or pending). Grades stay provisional until the key is reviewed and every value has a human decision or sign-off.
- **Alternatives.** Implement the handoff contract: contribution = weight × c × (0.5 + 0.5e), task subtotal × assertion precision P, total out of 100, and pass at ≥70 with no confirmed critical fabrication.
- **Impact.** Under key 0.1.1 the best available values are 84 full / 20 half / 2 zero on the pilot and 86 / 20 / 0 on the panel run, reported without a total (key 0.1.0: pilot 83 / 21 / 2, panel 78 / 20 / 8). A total would also need decisions on severe-flag scope (FI-B8) and on per-task assertion precision (FI-B17).
- **Evidence.** Handoff 'Scoring contract': 'Total score is the sum of task scores, bounded to 0–100'; 'Pass = score at least 70 with no confirmed critical fabrication.' Key `conventions.no_pass_threshold`. Pilot grade.json `provisional_reasons`. DECISIONS 76.
- **Compiler's note.** Priority lowered from P1 to P2 on review: no criterion value depends on it. MVP-A6 asks the same question; XT-17 (a) decides both.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b11"></a>

##### FI-B11 — T15.03 (auto_assisted_human) and T15.04 (judge, communications-as-cause zero)

**P2** · 15 min · FI (`gb-2019-full-investigation`) · Criteria: T15.03, T15.04 · Checklist: B11  

- **Question.** Should T15.03 (Hornsea gave no direct notification and restarted modules without coordination) be auto_assisted_human, and T15.04 a judge criterion that zeroes communications failures presented as a cause of the outage, LFDD or the trips?
- **Builder choice.** T15.03 full needs both points. T15.04 full needs attribution and delay issues described and not treated as causes. Its contradiction rule also reads 'contributed to'. Known miss of the judge error screen: a counterfactual without a communications word (decision 72).
- **Alternatives.** Make T15.03 a judge criterion. Cap T15.04 at 0.5 instead of zeroing it. Accept 'communications delays worsened rail recovery' as a consequence rather than a cause.
- **Impact.** Pilot T15.03 = 1 (F36). T15.04 is 1 on pre-screen and judge; the Consequences section says 'These are coordination problems and are kept separate from the causes of the disturbance.' Increment A's runs: T15.03 = 0.
- **Evidence.** OFG p29: 'Hornsea 1 did not notify the ESO directly when the wind farm deloaded by 737MW'; OFG p30: 'any coordination with the ESO whilst the ESO was attempting to respond to the generation losses'; ESO p31: 'These public-facing communications did not impact the speed with which the incident was resolved'. Visible: R09 L136-L140, S10 L133-L135, S09 response:S09-ESOC-09; R09 L96-L135, R09 L38-L55, S09 response:S09-ESOC-05.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b15"></a>

##### FI-B15 — Clause numbers accepted, never required

**P2** · 10 min · FI (`gb-2019-full-investigation`) · Criteria: T14.01, T14.03, T19.02 · Checklist: B15  

- **Question.** Should interpretive criteria accept clause numbers quoted as Ofgem cites them (e.g. 'contrary to OC6.6.4 as Ofgem cites it') but never require them?
- **Builder choice.** Accepted and never required. S10 and R10 print clauses only as 'Ofgem cites ...'.
- **Alternatives.** Penalise clause numbers that are not in the evidence. Require the requirement's substance whenever a clause is cited (see FI-D-T14.01).
- **Impact.** The pilot cites CC.6.2.3.1.1 (F02), CC.6.3.15.1 and CC.A.7.2.5.2 (F07) and OC6.6.4 (F26) without penalty. On T14.01 the judge gave 0.5 because F07 names the clauses but not what the requirements say.
- **Evidence.** Handoff spec: 'Exact legal clause scoring and ESQCR duties are excluded until separately verified.'; OFG p30: 'Grid Code Connection Condition CC. 6.3.15.1'. Visible: S10 L136-L142 ('(Ofgem cites CC.A.7.2.5.2, Voltage Control (Oscillations))').

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b17"></a>

##### FI-B17 — Routing: summary and section references do not route findings

**P2** · 15 min · FI (`gb-2019-full-investigation`) · Criteria: T20.01, T20.06, T18.01 · Checklist: B17  

- **Question.** Should findings that the executive summary or a report section only refers to keep the topic whose criteria match their content, with T20/T18 used only when nothing else matches (a finding stating a recommendation goes to T18)?
- **Builder choice.** Such findings count as the summary criteria's findings for evidence support, but the summary's topic gets weight 0 in routing.
- **Alternatives.** Route referenced findings to T20, which would put many domain findings under T20's assertion precision. Alternatively, count them under both topics.
- **Impact.** Pilot: the T20 judge unit classifies 0 findings (17 before the fix). F24, F25 and F30 go to T05, and F42–F45 to T18. T20.06 still matches 44 findings (F01–F45 except F04). Content values do not change; per-task assertion quality does.
- **Evidence.** DECISIONS 69. tests/test_fi_grading_pilot_run.py `test_summary_references_do_not_route_findings_to_t20`. REVIEW_CHECKLIST.md B17.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-b18"></a>

##### FI-B18 — clause_time binding for T15.01a/b and T15.02's 18:00

**P2** · 15 min · FI (`gb-2019-full-investigation`) · Criteria: T15.01a, T15.01b, T15.02 · Checklist: B18  

- **Question.** Should T15.01a/b read a time only from its own clause (naming BEIS and the contact, or the first/initial statement), never read a restoration time as either, and require T15.02's 18:00 to be the Ofgem contact's?
- **Builder choice.** A clause with the wording but no time of its own takes the finding's event_time. Clauses are joined across commas when the neighbouring clauses have no time of their own. A restoration phrase in the time's clause excludes the time.
- **Alternatives.** Read any time in a sentence that mentions BEIS or the statement. Alternatively, send all candidate times to human review.
- **Impact.** Pilot F34 and F35 are credited. Key negatives are now 0, including 'said the DNOs had reconnected all demand by 17:40' and 'restored all demand by 18:30'.
- **Evidence.** DECISIONS 70. Key T15.01a element `beis_time` (none: 'restor|reconnect|demand|back on supply') and its examples. R09 gists keep 'by 18:30' and 'by 17.40' (decision 54).

Decision: [ ] accept  [ ] change to: ____

<a id="fi-c1"></a>

##### FI-C1 — Accounting bases unchanged

**P2** · 10 min · FI (`gb-2019-full-investigation`) · Checklist: C1 · Cross-task: [XT-01](#xt-01)  

- **Question.** Should increment A's accounting figures, overlap groups and caps apply unchanged to the full investigation, with the new rail counts handled by `count` alternatives rather than accounting figures?
- **Builder choice.** Unchanged from SR key 0.1.1 (decisions 33, 41, 46).
- **Alternatives.** Add accounting figures for rail and LFDD consequences, e.g. 931 vs 892 vs 973 MW, which are already SR criteria.
- **Impact.** No accounting trap on the pilot. Increment A's six runs show identical accounting mentions under both keys (test_fi_grading_live_runs.py).
- **Evidence.** Key `accounting` (copied). REVIEW_CHECKLIST.md C1; SR REVIEW_CHECKLIST.md section C.
- **Compiler's note.** Installed FI key 0.1.1 (decisions 77–80; FI checklist C1-C4): three accounting rules added on top of increment A's: `binding_options.basis_components` (C2), the DG_LOM_500/580 single-mechanism mismatch (C3) and the inertia unit as context (C4).

Decision: [ ] accept  [ ] change to: ____

<a id="fi-d-t10.01"></a>

##### FI-D-T10.01 — T10.01 on-board protection despite maintained traction supply

**P2** · 15 min · FI (`gb-2019-full-investigation`) · Criteria: T10.01 · Checklist: D (rows T10.01)  

- **Question.** Should T10.01 full need both the trains' own on-board protection as the cause of the stoppages and the generally maintained traction supply, with stoppages attributed to traction-supply loss zeroed and local traction losses (Wirral, DC locations) not counted against?
- **Builder choice.** Judge. Full = both points; partial = one; 0 = stoppages blamed on loss of traction supply or on LFDD disconnecting the railway.
- **Alternatives.** Accept 'traction supply largely maintained' with the substation trips mentioned. Cap rather than zero.
- **Impact.** Pilot pre-screen 1 and judge 1 (F27: 'Traction power was not lost'). Increment A's six runs = 0.
- **Evidence.** ORR p8: '...why it significantly affected the railway services despite not losing traction power'; APP p48: 'There was no identified OLE AC Voltage supply interruption.'; ESO p27: 'The Network Rail overhead line power supply operated continually.' Possible confusion: ORR p3 'two traction substations lost power at Tattenham and Chipstead' and ESO p27 'supply related trips which occurred at two DC traction locations'. Visible: S08 L18-L21, L86-L89, L136-L139, L170-L174; S09 response:S09-NR-01 and S09-GTR-01; S11 L19-L23.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-d-t10.04"></a>

##### FI-D-T10.04 — T10.04 software 3.25.x vs 3.27.x and the reversal rule

**P2** · 15 min · FI (`gb-2019-full-investigation`) · Criteria: T10.04 · Checklist: D (rows T10.04)  

- **Question.** Should T10.04 give full for both versions with their recovery behaviour and 0.5 for one, and zero reversed behaviour only when a version and the other version's behaviour are linked without a contrast word between them (a departure from the review's suggestion to excuse 'rather than' and 'whereas' sentence-wide)?
- **Builder choice.** The reversal rule requires version and behaviour linked without a contrast word. The review's suggestion was rejected because it would excuse a true reversal such as '3.25 units needed a technician whereas 3.27 units could be reset by drivers'.
- **Alternatives.** Use the review's 'none' list. Cap reversals at 0.5. Accept 'new software' and 'old software' without version numbers.
- **Impact.** Pilot T10.04 = 0.5: F28 gives only the 3.27 permanent lock-out. Increment A's six runs = 0.
- **Evidence.** ORR p9: 'On detecting the frequency drop, the units with software version 3.25.x went into a tempor[ary lock-out]...'; APP p49: 'Separately as a part of the new TCMS ... software version 3.27, the ability for the driver to recover from a Permanent Lockout by using the Battery Reset process was removed.' and 'all the units which required a Technician to recover power were at software level 3.27 or above'. DECISIONS 70 (T10.04 departure). Visible: S08 L62-L66, L185-L195; S09 response:S09-GTR-05 and S09-GTR-11.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-d-t11.02"></a>

##### FI-D-T11.02 — T11.02 Wirral traction supply: conflicting accounts

**P2** · 15 min · FI (`gb-2019-full-investigation`) · Criteria: T11.02 · Checklist: D (rows T11.02)  

- **Question.** Should T11.02 full require the Wirral traction-supply loss with its LFDD cause, even though S11 also holds the ESO's statement that the DNOs confirmed no track supplies were lost to LFDD?
- **Builder choice.** Full = the Wirral traction loss with LFDD as the cause (ORR, Ofgem, E3C). Partial = the impact without the LFDD cause, or without saying it was the traction supply. The ESO/DNO statement in S11 P01 is not mentioned in the expectation or keyed spans.
- **Alternatives.** Give full when the loss is reported with the conflicting accounts attributed. Add S11 L15-L18 as a context span and say in the expectation how a run citing it is treated.
- **Impact.** Pilot = 1 (F31: 'Merseyrail Wirral line traction was lost through SP's LFDD'). Increment A's six runs = 0. Only a run that weighs the ESO statement against ORR/Ofgem/E3C is affected (it could drop to 0.5).
- **Evidence.** ESO p27: 'The DNOs confirmed that no track supplies were lost due to the DNO's LFDD protection operation.'; ORR p6: 'There was traction power outage on the Wirral line of the MerseyRail after rectifiers tripped when domestic supply was lost to LFDD.'; OFG p20: 'The traction supplies to the Wirral line on Merseyrail were disconnected as a result of SP Energy Networks' LFDD operations.'; E3C p18: 'power supplies to the local Wirral Line were interrupted by the LFDD scheme causing a 428 minute delay'. Visible: S11 L15-L18 (P01, not keyed), S11 L28-L30, L43-L50; S09 response:S09-NR-03; R11 entry:R11-NR-224917.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-d-t19.01"></a>

##### FI-D-T19.01 — T19.01 further evidence requests

**P2** · 15 min · FI (`gb-2019-full-investigation`) · Criteria: T19.01 · Checklist: D (rows T19.01)  

- **Question.** Should T19.01 full need 'several requests, each with party and specific data', and is the example list (RWE instrumentation/control records and bypass inspection, Ørsted controller logs, DNO relay logs and DG data, GTR/Siemens TCMS logs, UKPN switching records, ESO communications log, compliance test reports, MeteoGroup stroke data, PMU/WAMS) right?
- **Builder choice.** Judge. Full = several requests with party and data. Partial = requests missing a party or specific data. 0 = none. 'Several' is not quantified.
- **Alternatives.** Set a number (e.g. at least three). Require requests that target the key unknowns (Little Barford root causes, DG volumes).
- **Impact.** Pilot pre-screen 1 and judge 1 (seven owner/data pairs). Increment A's six runs = 0.
- **Evidence.** OFG p31: 'The root cause of the discrepancy in the speed sensors has not been established.'; APP p45: 'RWE's hypothesis is that the UPS' have initiated a changeover to battery back-up supplies'; APP p46: 'A physical inspection of the bypass system is now planned during the forthcoming outage in September 2019'; ESO p21: 'some DNOs noted challenges in obtaining the data'; OFG p36: half-hourly recording. Visible: S04 L42-L44, L53-L54; S06 L22-L24, L32-L35; R09 L468-L469; R11 L368-L369.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-x1"></a>

##### FI-X1 — Budgets: 200k context cap and 150 tool calls (open in DECISIONS)

**P2** · 10 min · FI (`gb-2019-full-investigation`) · Checklist: no row  

- **Question.** Should the full investigation keep the 200,000-token context cap and the 150-call budget (a run that hits the cap ends incomplete and gets no content grade), given the pilot peaked at 175,269 tokens (87.6%) in 31 calls without using either log tool?
- **Builder choice.** Keep both, and revisit only if panel runs hit the cap. Raise calls to 200 only if coverage is shown to be budget-bound (contract). The output budget is 80k.
- **Alternatives.** Raise the cap for models that allow it (decision 36 reasoning). Raise the call budget to 200.
- **Impact.** The pilot completed (completion score 1.0). Estimated peaks: reference 157,723 (78.9%) and repair 190,150 (95.1%). A panel run that also pages the logs (~508k characters) could exceed the cap and lose all content grades. This is an operational choice, not a power-systems one.
- **Evidence.** DECISIONS 53, 64, 74; task README 'Budgets'; pilot grade.json run.tokens (last_input 175269, context_cap_reached false).

Decision: [ ] accept  [ ] change to: ____

### 2.4 P3 items (15 items, 3 h 5 min)

P3: per-criterion text checks, wording and process confirmations.

#### MVP — `gb-2019-electrical-disturbance` (key 0.3.1) — P3, 7 items, 2 h 10 min

<a id="mvp-b24"></a>

##### MVP-B24

**P3** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Checklist: B24 · Cross-task: [XT-16](#xt-16)  

- **Question.** Should the never-scored status_inferential_language flag keep 'attributed to' in its patterns?
- **Builder choice.** Keep it. Quoted spans, and clauses that attribute the words to a named source with an attribution verb, are exempt. Nouns alone are not attributions.
- **Alternatives.** Drop 'attributed to'. Or exempt a passive attribution when the source is named elsewhere in the finding.
- **Impact.** Never scored. Live hits: run 001 F08 ('is attributed to the offshore turbine controllers', reported; a correct report of the operator's conclusion) and F14 ('consistent with', observed); haiku45-001 F22 ('likely', reported; a genuine inference).
- **Evidence.** answer_key.json conventions.inferential_patterns and inferential_attribution. The bundle itself uses such words: R03 L33 'indicating', L93 'most likely', L99 'indicate', L107 'suggests'; S01 L90 'suggested'; S04 L39 'Therefore'.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-b25"></a>

##### MVP-B25

**P3** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D1.N · Checklist: B25 · Cross-task: [XT-12](#xt-12)  

- **Question.** Is it acceptable that bundle 1.1.0 dropped R03's compiler's note on the two Blyth–Eccles–Stella West trip times, leaving E2 to give 16:50:44 and 16:43:25 side by side (clock basis not stated) for D1.N to rely on?
- **Builder choice.** Yes: the conflict is left for the agent to find (decision 9).
- **Alternatives.** Restore a neutral note. Or make the conflict its own criterion.
- **Impact.** No score effect. sonnet55-001 F21 (unknown) reports the unreconciled times; opus55-003 F26 and live run 001 F23 rule the trips out.
- **Evidence.** ESO PDF p15 (printed 16): "At 16:50:44hrs, a lightning struck the Blyth – Eccles – Stella West 400kV circuit near Longframlington, Northumberland." APP PDF p85: "At 16:43:25, the Blyth – Eccles – Stella West 1 400kV circuit tripped and was likewise returned to service via DAR at 16:43:54." R03 L73-L77.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-x2"></a>

##### MVP-X2

**P3** · 10 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.5, D4.4 · Checklist: no row · Cross-task: [XT-16](#xt-16)  

- **Question.** Should the never-scored labelling flag ('hedged wording with a factual status') exempt measurement caveats about 1-s sampling, as the SR grader does since decision 48?
- **Builder choice.** The frozen MVP grader flags them.
- **Alternatives.** Exempt a hedge only when it is about the measured value.
- **Impact.** Flagged: sonnet55-001 F18 (observed: 'may differ from the sample values by up to about a second') and haiku45-001 F12 (inferred: 'may have occurred between samples'), both measurement caveats. haiku45-001 F22 ('The UPS likely initiated changeover', reported) is a genuine hit.
- **Evidence.** flags.labelling on the live runs. R01 L28-L29. DECISIONS.md decisions 44 and 48.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-d1"></a>

##### MVP-D1

**P3** · 25 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D1.1, D1.2, D1.3, D1.4, D1.N · Checklist: D (rows D1.1, D1.2, D1.3, D1.4, D1.N)  

- **Question.** For D1.1–D1.4 and D1.N, are the expectation texts, report passages, visible-evidence locators and examples correct (OK / Change / Remove per cell in checklist section D)?
- **Builder choice.** 23 passages. All are found on their stated PDF page (independent re-check: 74 of 74 key passages OK; the key tests pass). Ørsted's '16:52:33:490' is an alternative_account; ESO's two Blyth times are kept as a noted conflict.
- **Alternatives.** Change roles, for example promote ESO PDF p3's '4.52pm' to context only. Add R03 L36-L37 to D1.N (MVP-X1).
- **Impact.** Locators decide evidence routing: D1.N and D1.2 are pending for opus55-002 and haiku45-001. The numeric rules are covered in MVP-B1, B4, B5, B10, B11 and B27.
- **Evidence.** For example: ESO PDF p12 (printed 13) "16:52:33.490 A single (blue) Phase to Earth fault on Eaton Socon - Wymondley circuit"; APP PDF p40 "The lightning strike results in a phase to Earth short circuit at exactly 16:52:33:490"; ESO PDF p16 (printed 17) "The transmission system protection operated in line with the design and in compliance with the Grid Code requirements on fault clearance". R03 L25-L27, L36-L37, L43-L53, L67-L77, L86-L90, L102-L107.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-d2"></a>

##### MVP-D2

**P3** · 30 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D2.1, D2.2, D2.3, D2.4, D2.5 · Checklist: D (rows D2.1, D2.2, D2.3, D2.4, D2.5)  

- **Question.** For D2.1–D2.5, are the expectation texts, report passages, visible-evidence locators and examples correct (checklist section D)?
- **Builder choice.** 19 passages, all on their stated pages. APP PDF p41's UTC sentence is context only. S01 L6 is context for D2.1 but primary for D2.5. S03 L6-L9 is context for D2.2–D2.4 but primary for D2.5.
- **Alternatives.** Align the S01 L6 and S03 L6-L9 roles across criteria. Change D2.4's title wording 'about 27 s after GT1A' to the sources' 'around 30 seconds'.
- **Impact.** Routing: opus55-002 D2.2 and D2.4 evidence are pending (MVP-B20). The scoring rules are covered in MVP-B2, B3, B6, B13, B15, B16, B21, B22 and B28a.
- **Evidence.** ESO PDF p13 (printed 14): "16:53:31 Little Barford GT1A generator protection settings tripped and 210MW instantaneously disconnected." OFG PDF p30: "Little Barford’s steam turbine was generating 244MW when it tripped, within 1 second of the lightning strike." ESO PDF p20 (printed 21): "… manually tripped by the RWE operational staff in response to high steam pressures around 30 seconds later". S01 L6, L35, L40-L43; S03 L6-L9, L21-L36; S04 L19-L33.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-d3"></a>

##### MVP-D3

**P3** · 20 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D3.1, D3.2, D3.3, D3.4, D3.5 · Checklist: D (rows D3.1, D3.2, D3.3, D3.4, D3.5)  

- **Question.** For D3.1–D3.5, are the expectation texts, report passages, visible-evidence locators and examples correct (checklist section D)?
- **Builder choice.** 11 passages, all on their stated pages. E3C-I 48.792 Hz and Siemens' 16 s are conflicting accounts. D3.5's passages are context only.
- **Alternatives.** Add a D3.5 primary passage, or record that no report passage supports D3.5.
- **Impact.** The D3.x row locators (R01 row:780, 830, 1037, rows:821-856) decide automatic evidence support; all panel runs get automatic 1. The values and rules are covered in MVP-A3, B7–B9, B14, B17a–c, B18, B26, B28b and DEC27.
- **Evidence.** ESO PDF p14 (printed 15): "Frequency is restored to 50Hz [16:57:15]". E3C-I PDF p11: "when the system frequency fell to 48.792Hz, not all schemes were triggered". ORR PDF p4: "shut down within 200ms of the frequency dropping below 49.0Hz". R01 L22-L23, L28-L29, row:780, row:830, row:1037, rows:821-856.

Decision: [ ] accept  [ ] change to: ____

<a id="mvp-d4"></a>

##### MVP-D4

**P3** · 25 min · MVP (`gb-2019-electrical-disturbance`) · Criteria: D4.1, D4.2, D4.3, D4.4 · Checklist: D (rows D4.1, D4.2, D4.3, D4.4) · Cross-task: [XT-11](#xt-11)  

- **Question.** For D4.1–D4.4, are the expectation texts, report passages, visible-evidence locators and examples correct (checklist section D)?
- **Builder choice.** 21 passages, all on their stated pages. ESO's bypass-valve sentence is a conflicting account; RWE's UPS hypothesis is 'expected', for the agent to label as a hypothesis.
- **Alternatives.** Check that OFG PDF p29 ('controllers … reacted incorrectly') supports D4.1's resonance mechanism or only the instability. Decision 36 removed that credit to Ofgem in the SR key.
- **Impact.** The rules are covered in MVP-B12, B19, B23 and C1–C6. The D4.1 passage question could change what the attribution element should accept.
- **Evidence.** OFG PDF p29: "The offshore wind turbine controllers, however, reacted incorrectly to voltage fluctuations on the offshore network following the fault." APP PDF p43: "The de-load was caused by an unexpected wind farm control system response, due to an insufficiently damped electrical resonance in the sub-synchronous frequency range". OFG PDF p31: "its safety systems automatically shut down one of the gas turbines due to excessive pressure in the steam bypass". S01 L55-L87; S03 L42-L60; S04 L27-L66.

Decision: [ ] accept  [ ] change to: ____

#### SR — `gb-2019-system-response` (key 0.1.1) — P3, 4 items, 30 min

<a id="sr-a6"></a>

##### SR-A6

**P3** · 5 min · SR (`gb-2019-system-response`) · Checklist: A6 · Cross-task: [XT-17](#xt-17)  

- **Question.** Are the split fields with equal subweights (T01.03, T02.01-T02.03, T02.05, T05.01, T09.02, T12.01) acceptable as a reporting convenience with no total computed?
- **Builder choice.** Split compound handoff criteria into a/b/c fields with equal subweights (0.5 or 1/3); no total, threshold or ranking.
- **Alternatives.** Unequal subweights; keep compound criteria whole with a single 1/0.5/0 value.
- **Impact.** No score effect: the grader computes no total. Unsplitting would merge, e.g., T12.01a/b/c (1/0.5/0.5 on four runs) into one partial value.
- **Evidence.** No source passage (process or grader rule). Visible/key locators: key criteria[].subweight, field; key scope

Decision: [ ] accept  [ ] change to: ____

<a id="sr-b27"></a>

##### SR-B27

**P3** · 15 min · SR (`gb-2019-system-response`) · Checklist: B27 · Cross-task: [XT-16](#xt-16)  

- **Question.** Are the labelling and inferential-language flags (proposals only, never scored) defined right, including the round-2 exemptions for measurement caveats, reported hypotheses, a named third party's 'suggests/indicates', and passive 'was attributed to'?
- **Builder choice.** Labelling: modal hedges outside quoted/attributed clauses; caveat excuses only a hedge about the measured value. Inferential: record or own analysis as subject is flagged; named source as subject is not.
- **Alternatives.** Score the flags; flag every hedge; drop the inferential flag.
- **Impact.** Never scored. Current flags: labelling sr80k-sonnet55-001 F12, F23; inferential sr80k-opus55-001 F35, sr80k-sonnet55-001 F19, F23, sr30k-opus55-001 F03, sr30k-sonnet55-001 F02, F04, F29, sr30k-haiku45-001 F15 (decision 44: 7 of 9 labelling and 5 of 13 inferential flags in 0.1.0 were false).
- **Evidence.** No source passage (process or grader rule). Visible/key locators: key conventions.status_labelling, inferential_patterns, inferential_attribution; DECISIONS 44, 48
- **Compiler's note.** Priority lowered from P2 to P3 on review: the flags are never scored, as for MVP-B24, MVP-X2 and FI-B21 (all P3).

Decision: [ ] accept  [ ] change to: ____

<a id="sr-f1"></a>

##### SR-F1

**P3** · 5 min · SR (`gb-2019-system-response`) · Checklist: F1 · Cross-task: [XT-17](#xt-17)  

- **Question.** Should a report be final only when every criterion and assertion has a human value or accept_judge sign-off, every suspected flag is adjudicated, explanation-quality notes exist, the decisions file is not a builder fixture, an episode trace exists, the bundle is the key's and the key is 'reviewed'?
- **Builder choice.** All grades provisional until these hold; key 0.1.1 pending_domain_review.
- **Alternatives.** Allow final status per criterion; allow a builder-signed key.
- **Impact.** All six fixtures are provisional (needs_human_review 56-57 rows each).
- **Evidence.** No source passage (process or grader rule). Visible/key locators: key review; sr_grading report.status/provisional_reasons

Decision: [ ] accept  [ ] change to: ____

<a id="sr-x4"></a>

##### SR-X4

**P3** · 5 min · SR (`gb-2019-system-response`) · Criteria: T01.01, T12.01b, T12.01c · Checklist: no row  

- **Question.** Should three stale or misleading texts be corrected in key 0.1.2: conventions.status_labelling still says 'Bundle 1.1.0 no longer sorts statements ...' (MVP bundle; this key binds bundle 0.1.0), T01.01's element note says full credit 'also needs ... the fault type' (rules do not), and the T12.01b/c basis says 'the figure appears only in the report text' when the 0.5 is for the missing band?
- **Builder choice.** Texts carried over from the MVP key / grader notes.
- **Alternatives.** Leave as is (reviewer-only text; not scored).
- **Impact.** No score effect; the T12.01b/c basis text appears on all six runs and points the reviewer at the wrong reason.
- **Evidence.** No source passage (process or grader rule). Visible/key locators: key conventions.status_labelling; criteria[T01.01].auto.elements[1].note; grade basis T12.01b/c on all six runs

Decision: [ ] accept  [ ] change to: ____

#### FI — `gb-2019-full-investigation` (key 0.1.1) — P3, 4 items, 25 min

<a id="fi-b21"></a>

##### FI-B21 — Labelling-flag exemptions (never scored)

**P3** · 5 min · FI (`gb-2019-full-investigation`) · Checklist: B21 · Cross-task: [XT-16](#xt-16)  

- **Question.** Should the labelling flag (a proposal, never scored) spare hedge words that are no hedge: 'as soon as possible', 'where possible', and a prohibition 'may not restore ... without ESO instruction'?
- **Builder choice.** Yes, in the FI key only (`conventions.labelling_exempt`). Real hedges in the same findings still flag.
- **Alternatives.** Keep flagging them, as SR and MVP do. Port the exemptions to SR.
- **Impact.** Never scored. Labelling flags: pilot 2 → 0 (F34 'as soon as possible'; F26 'DNOs may not restore LFDD demand without ESO instruction'), panel run 1 → 0 (F33 'as soon as possible'). The inferential flags on pilot F09 ('consistent with') and panel F45 ('therefore') are true positives and stay.
- **Evidence.** Key `conventions.labelling_exempt`; DECISIONS 77; tests/test_fi_grading_live_runs.py `test_labelling_and_inferential_flags`, `test_labelling_still_flags_a_real_hedge`; REVIEW_CHECKLIST.md B21.
- **Compiler's note.** Added on review: checklist row with no card.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-f2"></a>

##### FI-F2 — Grading decisions bound to key, submission and bundle

**P3** · 5 min · FI (`gb-2019-full-investigation`) · Checklist: F2 · Cross-task: [XT-17](#xt-17)  

- **Question.** Should grading decisions use schema gb2019-fi-grading-decisions/1 (increment A's layout), bound to this key's sha256, the submission and the bundle?
- **Builder choice.** As stated. A changed key invalidates bound decisions and needs a regrade.
- **Alternatives.** Bind decisions per criterion so that unchanged criteria survive a key bump.
- **Impact.** No decisions file exists yet for any run (pilot: 'no grading-decisions file applied').
- **Evidence.** REVIEW_CHECKLIST.md F2; pilot grade.json provisional_reasons.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-f3"></a>

##### FI-F3 — Grade report schema and provisional status

**P3** · 5 min · FI (`gb-2019-full-investigation`) · Checklist: F3 · Cross-task: [XT-17](#xt-17)  

- **Question.** Should grade reports (gb2019-fi-grade/1) carry flags.executive_summary (words, limit, within_limit) and stay provisional until every value has a human decision or sign-off and the key is reviewed?
- **Builder choice.** As stated. The Karotte metadata copy may be truncated; grade.json is authoritative.
- **Alternatives.** Report a 'best available' value set alongside the provisional status.
- **Impact.** Pilot report: flags.executive_summary {words 540, limit 600, within_limit true}. Status 'provisional': 49 criteria await a decision and 53 judge proposals await sign-off.
- **Evidence.** REVIEW_CHECKLIST.md F3; task README 'Scoring'; pilot grade.json.

Decision: [ ] accept  [ ] change to: ____

<a id="fi-x2"></a>

##### FI-X2 — Documentation consistency in the checklist and key (wording only)

**P3** · 10 min · FI (`gb-2019-full-investigation`) · Criteria: T10.02a, T10.05a, T14.05, T15.01b · Checklist: no row  

- **Question.** Should the wording slips be fixed before sign-off (none changes a grade except where noted in FI-B9 and FI-B1)?
- **Builder choice.** Current text: (1) checklist G says no full-investigation run exists, though the pilot is a fixture. (2) B3 says the alternative counts 'count units, not trains', but the ESO (p27) and DfT/E3C-I (p12) say 'trains'. (3) T10.05a lists Ofgem's '>500 services disrupted' as an accepted alternative without saying what it earns. (4) T14.05's expectation defines a partial, but its pre-screen has no half route. (5) T15.01b `tolerances.half_within_s` 240 does not match the element (18:28:30 ±150 s).
- **Alternatives.** Leave as is and record the clarifications in the sign-off notes.
- **Impact.** No real-run grade changes, except item (5) in edge cases (18:23–18:25 gets 0, not half).
- **Evidence.** REVIEW_CHECKLIST.md sections B3 and G; key T10.05a accepted_alternatives, T14.05 auto (full_if_any only), T15.01b tolerances and element statement_about_1830. ESO p27: 'Of the approximately 60 Class 700 and Class 717 trains that shutdown'; E3C-I p12: 'which triggered 60 trains to shut down'.
- **Compiler's note.** Installed FI key 0.1.1 (decisions 77–80; FI checklist B19): slip (4) is addressed: T14.05 now has a partial route.
- **Compiler's note.** Slip (1) is addressed: checklist section G now describes both real FI runs and has row G2.

Decision: [ ] accept  [ ] change to: ____

## 3. How to record decisions

### 3.1 In this pack

Tick one box on every card. A cross-task card has one decision line per sub-question; its answer
applies to all member cards, so tick "accept" on a member unless you want a task-specific exception.
For tooling, the same decisions go in `docs/reviewer_pack_items.json`:

- items: `items[].decision` = `{"value": "accept" | "change", "change_to": "...", "notes": "...", "reviewer": "...", "date": "YYYY-MM-DD"}`
- cross-task cards: `cross_task[].decisions[]` (one per sub-question)

Leave `null` where you have not decided.

### 3.2 In the review checklists (the record of sign-off)

| Task | Checklist | Card to row |
|---|---|---|
| MVP | `src/environment/incident/private/REVIEW_CHECKLIST.md` | `MVP-A1`..`A7`, `B1`..`B28` (`B17a`–`c` → B17, `B28a`/`b` → B28), `C1`..`C6` (`C3` also C7) → same row; `MVP-D1`..`D4` → section D rows; `MVP-E` → section E |
| SR | `src/environment/incident/private/system_response/REVIEW_CHECKLIST.md` | `SR-A*`, `B*` (`B25a`/`b` → B25), `C1`..`C5`, `C7`, `E*`, `F*` → same row. Split rows: `SR-B12` also answers B24's T09.04 half, `SR-B14` B28's T12.02 half, and `SR-B28` also answers C6. `SR-C0` → section C introduction; `SR-D-T…` → section D rows |
| FI | `src/environment/incident/private/full_investigation/REVIEW_CHECKLIST.md` | `FI-A*`, `B*` (including B19–B21), `C1`..`C4`, `E*`, `F*`, `G1`, `G2` → same row; `FI-D-T…` → section D rows |

Write **OK**, **Change** (say what) or **Remove** in the Answer column. Most criteria in the SR and FI
section D tables have no `-D-` card: their rules are decided on the B or C cards that the appendix
(section 4) lists for that criterion, so answer the D row from those. Some cards have no row:
`MVP-DEC27`, `MVP-DEC19`, `MVP-R01CLK`, `MVP-X1`–`X3`, `SR-X1`–`X4`, `FI-X1` and `FI-X2`. Record those, and any cross-task decision that changes a rule, under the
sign-off block: the "Required changes" field for MVP section E, and notes under "Sign-off" for SR
and FI.

Fill each sign-off block: reviewer name and role, domain expertise, date, the key version reviewed,
and approve / approve with changes / reject. A second reviewer signs separately.

Only the checklists and this pack are the reviewer's to edit. The builder edits the answer keys,
graders, bundles and tests.

### 3.3 What the builder does after sign-off (key re-versioning)

1. **Apply the changes, never in place.** Each signed key gets a new `key_version` and a `changes`
   entry. Set `review.status` and the top-level `review_status` to `reviewed`, and fill
   `review.reviewed_by` and `review.reviewed_on`. The next versions are:
   - MVP: 0.3.2 or later. There is no key builder: edit `private/answer_key.json` directly; the
     tests check it.
   - SR: 0.1.2 or later. Rebuild with `.context/sr_key_builder/build_key.py`, then run
     `check_examples.py`.
   - FI: the version after the installed one. Rebuild with `.context/fi_key_builder/build_key.py`,
     then run `check_examples.py` and `build_checklist.py`. FI's builder reads the **installed SR
     key** (`reuse.py`), so after any SR change rebuild FI too. A change to a shared criterion
     therefore bumps both keys (XT-01).
2. **Grader rules.** If a decision changes how a matcher works, not only a value in the key, bump
   the grader too (`GRADER_VERSION` in `grading.py`, `sr_grading.py` or `fi_grading.py`). Update the
   tests that pin live-run values, citing the decision: `test_grading_live_runs.py`,
   `test_sr_grading_live_runs.py`, `test_fi_grading_live_runs.py` and `test_fi_grading_pilot_run.py`.
3. **Evidence edits** (XT-20, MVP-DEC19) are the most expensive change. They need a new bundle
   version, a manifest and provenance rebuild (`builder/`), a key rebind (`bundle.bundle_sha256`),
   and regrades. The MVP and SR bundles are frozen regression baselines (decisions 21, 26, 49).
4. **Judge-visible text** (SR/FI criteria, examples without pre-screen values, severe-flag
   definitions, accounting descriptions):
   - If it changes, judged runs need new judge calls. These cost money and need approval first;
     price them with `--dry-run`.
   - If it does not change, the builder may re-bind the existing judge outputs to the new key, as
     decision 45 did, and record that it did so.
5. **Tests** (from `my_env/`):

   ```sh
   uv run --frozen --extra test pytest -q tests/test_grading_*.py      # MVP key, examples, live runs
   uv run --frozen --extra test pytest -q tests/test_sr_grading_*.py   # SR
   uv run --frozen --extra test pytest -q tests/test_fi_grading_*.py   # FI
   uv run --frozen --extra dev just lint
   ```

### 3.4 Regrading and the per-run decisions files

Create one decisions file per run from a template.

- The template is bound to the submission sha256, the key version and sha256, and the bundle sha256.
  A file bound to anything else is rejected.
- Never edit a decisions file that has been used: copy it to `.v2.json`, bump `decisions_version`,
  and regrade.
- Keep the files under `my_env/reviews/`. The directory does not exist yet.
- The two files in `tests/fixtures/decisions/` are builder fixtures, not reviews.

```sh
# MVP (grader: environment.incident.grading)
E=out/panel/opus55-002/gb2019-v2-opus55-002_artifacts/episode
uv run --frozen python -m environment.incident.grading review-template $E --out reviews/gb2019-v2-opus55-002.decisions.v1.json
uv run --frozen python -m environment.incident.grading grade $E --transcript out/panel/opus55-002/transcript.json \
    --decisions reviews/gb2019-v2-opus55-002.decisions.v1.json --out reviews/gb2019-v2-opus55-002.grade.v1.json
# live run 001 ran on bundle 1.0.0: add --bundle-dir tests/fixtures/live/bundle-1.0.0

# SR (grader: environment.incident.sr_grading)
E=out/panel_sr80k/opus55-001/gb2019-sr80k-opus55-001_artifacts/episode
uv run --frozen python -m environment.incident.sr_grading review-template $E --out reviews/gb2019-sr80k-opus55-001.decisions.v1.json
uv run --frozen python -m environment.incident.sr_grading grade $E --transcript out/panel_sr80k/opus55-001/transcript.json \
    --decisions reviews/gb2019-sr80k-opus55-001.decisions.v1.json --out reviews/gb2019-sr80k-opus55-001.grade.v1.json
# sr30k Opus/Sonnet are incomplete runs: grade-submission <submission.json> gives the diagnostic grade

# FI (grader: environment.incident.fi_grading)
E=out/fi_pilot/gb2019-fi-pilot-opus55-001_artifacts/episode
uv run --frozen python -m environment.incident.fi_grading review-template $E --out reviews/gb2019-fi-pilot-opus55-001.decisions.v1.json
uv run --frozen python -m environment.incident.fi_grading grade $E --transcript out/fi_pilot/transcript.json \
    --decisions reviews/gb2019-fi-pilot-opus55-001.decisions.v1.json --out reviews/gb2019-fi-pilot-opus55-001.grade.v1.json

# Add --judge <judge_output.json> to merge LLM-judge proposals (SR and FI only).
# A new judge run costs money: price it first and ask before running.
uv run --frozen python -m environment.incident.judge run $E --task gb-2019-full-investigation --dry-run
```

**The stored judge outputs do not merge under the installed keys.** They are bound to the keys
they were produced with: SR 0.1.0 for the three sr80k runs, FI 0.1.0 for the pilot and the FI panel run. Under the
installed keys, `--judge` with these files stops with `JudgeOutputError: ... binding.key_version
does not match`. This was checked while writing the pack. The commands above without `--judge`
work. The decision-45 re-binding exists only in the tests (`rebound()` in
`tests/test_sr_grading_live_runs.py`; for FI, `fi_rebound()` in `tests/test_fi_grading_live_runs.py`). Before the judge criteria can be signed off, the builder must
provide judge outputs bound to the key under review: re-bound where no judge-visible text changed
(SR-X1), or re-run.

In each decisions file:

- **Criteria:** set `content` (1 / 0.5 / 0), `evidence_support` (1 / 0), `finding_ids` and
  `notes` for every criterion.
  - For judge criteria, `accept_judge: true` signs off the judge's proposal. It cannot sign off a
    capped proposal: give the value.
  - For `auto_numeric` criteria, `null` keeps the automated value and any value overrides it.
- **Findings:** give every factual finding a `verdict` (supported, unsupported, contradicted). Mark
  paraphrases with `duplicate_of`. Add assertions made only in the report text.
- **Severe flags:** confirm or reject every suspected flag.
- **Explanation quality:** write notes, overall or per dimension or task.

A grade is `final` only when this is complete and the key is `reviewed` (XT-17).

The viewer reads each run's `grade.json` and shows its review status and its counts of automated,
judge, human and pending values. A new key version or a decisions file needs no viewer change.

## 4. Appendix: every criterion by task, with its assessment mode

Modes: `auto_numeric` = decided automatically from the frozen R01 series (a reviewer may override); `auto_assisted_human` = the grader proposes, a human decides; `judge` = the LLM judge proposes, a human signs off. "Items" lists the cards in this pack that name the criterion (MVP-A1 and SR-A3 cover every criterion of their key and are not repeated).

### MVP — `gb-2019-electrical-disturbance`: 19 criteria (4 auto_numeric, 15 auto_assisted_human, 0 judge)

| ID | Mode | Title | Items |
|---|---|---|---|
| D1.1 | auto_assisted_human | Initiating fault: lightning-induced single-phase (blue) to earth fault on the Eaton Socon–Wymondley 400 kV circuit | MVP-B11, MVP-D1 |
| D1.2 | auto_assisted_human | Fault time 16:52:33(.490) BST | MVP-B1, MVP-X1, MVP-D1 |
| D1.3 | auto_assisted_human | Fault cleared by main protection in 70 ms (Wymondley) and 74 ms (Eaton Socon), within the 80 ms requirement | MVP-B4, MVP-B15, MVP-D1 |
| D1.4 | auto_assisted_human | Delayed auto-reclose about 20 s later (16:52:53) restored the circuit; not a second initiating fault; protection operated as designed | MVP-A4, MVP-B1, MVP-B5, MVP-B27, MVP-D1 |
| D1.N | auto_assisted_human | Other strikes and trips that day are not the initiator | MVP-B10, MVP-B25, MVP-X1, MVP-D1 |
| D2.1 | auto_assisted_human | Hornsea One de-load 799 → 62 MW (737 MW, computed) at 16:52:33.728–.835 BST (operator's UTC log + 1 h) | MVP-B3, MVP-B15, MVP-B16, MVP-B22, MVP-DEC19, MVP-D2 |
| D2.2 | auto_assisted_human | Little Barford ST1C trip, 244 MW, within about 1 s of the fault (derived: T + 1.185 s ≈ 16:52:35.2 BST, ± 0.5 s) | MVP-B2, MVP-B3, MVP-B15, MVP-B20, MVP-B21, MVP-B26, MVP-D2 |
| D2.3 | auto_assisted_human | Little Barford GT1A trip, 210 MW, around a minute after the fault (derived: T + 57.620 s ≈ 16:53:31.6 BST, ± 0.5 s; automatic) | MVP-B2, MVP-B3, MVP-B15, MVP-B21, MVP-B26, MVP-D2 |
| D2.4 | auto_assisted_human | Little Barford GT1B trip, 187 MW, about 27 s after GT1A (derived: T + 84.613 s ≈ 16:53:58.6 BST, ± 0.5 s; manual) | MVP-B2, MVP-B3, MVP-B13, MVP-B15, MVP-B20, MVP-B21, MVP-B26, MVP-B28a, MVP-D2 |
| D2.5 | auto_assisted_human | Temporal grouping of the losses on stated clock bases, without a Hornsea/ST1C order finer than the datum uncertainty | MVP-A7, MVP-B1, MVP-B6, MVP-B15, MVP-B26, MVP-B28a, MVP-DEC19, MVP-D2 |
| D3.1 | auto_numeric | First post-fault frequency minimum: 49.083 Hz at 16:52:59 BST | MVP-A3, MVP-B7, MVP-B8, MVP-B17a, MVP-DEC27, MVP-B18, MVP-R01CLK, MVP-D3 |
| D3.2 | auto_numeric | Event minimum: 48.787 Hz at 16:53:49 BST | MVP-A3, MVP-B8, MVP-B17a, MVP-DEC27, MVP-B18, MVP-R01CLK, MVP-D3 |
| D3.3 | auto_numeric | First sample at or above 50 Hz after the minimum: 50.001 Hz at 16:57:16 BST | MVP-A3, MVP-B8, MVP-B17a, MVP-B17b, MVP-DEC27, MVP-B18, MVP-R01CLK, MVP-D3 |
| D3.4 | auto_numeric | Time below 49 Hz from R01: key value 33 s (strictly below, zero-order hold); other stated conventions within tolerance | MVP-A3, MVP-B9, MVP-B17a, MVP-B17c, MVP-DEC27, MVP-B18, MVP-B28b, MVP-R01CLK, MVP-D3 |
| D3.5 | auto_assisted_human | States the below-49-Hz duration convention and the 1-s sampling limit (sub-second crossings not resolvable) | MVP-A7, MVP-B14, MVP-B26, MVP-B28b, MVP-X2, MVP-D3 |
| D4.1 | auto_assisted_human | Hornsea mechanism: control-system response (insufficiently damped sub-synchronous resonance) → turbine overcurrent protection de-loaded 1B and 1C; weak internal network contributory; DRC suspicion cleared | MVP-B12, MVP-B23, MVP-D4 |
| D4.2 | auto_assisted_human | ST1C tripped automatically on a discrepancy among three speed signals | MVP-A4, MVP-B23, MVP-C1, MVP-D4 |
| D4.3 | auto_assisted_human | GT1A tripped automatically on high steam-bypass pressure; GT1B was tripped manually for excessive steam pressure | MVP-B13, MVP-B23, MVP-C1, MVP-C2, MVP-D4 |
| D4.4 | auto_assisted_human | Root causes of the speed-signal discrepancy and of the pressure excursions are not established | MVP-A4, MVP-B19, MVP-C1, MVP-C2, MVP-C3, MVP-C5, MVP-C6, MVP-X2, MVP-D4 |

### SR — `gb-2019-system-response`: 60 criteria (4 auto_numeric, 32 auto_assisted_human, 24 judge)

| ID | Mode | Title | Items |
|---|---|---|---|
| T01.01 | auto_assisted_human | Initiating event: lightning fault on the Eaton Socon–Wymondley 400 kV circuit | SR-D-T01.01, SR-X4 |
| T01.02 | auto_assisted_human | Initiating event time 16:52:33 BST (within 1 s of 16:52:33.490) | SR-B1, SR-B2 |
| T01.03a | auto_assisted_human | Fault type: single (blue) phase to earth | SR-B3, SR-D-T01.03 |
| T01.03b | auto_assisted_human | Clearance by main protection in 70 ms (Wymondley Main) and 74 ms (Eaton Socon), within 80 ms | SR-B1, SR-D-T01.03 |
| T01.04 | auto_assisted_human | Delayed auto-reclose about 20 s later (16:52:53 BST); not another initiating fault | SR-B3 |
| T02.01a | auto_assisted_human | About 150 MW of embedded generation lost on vector-shift protection, as an estimate | SR-B4, SR-C5 |
| T02.01b | auto_assisted_human | About 350 MW of embedded generation lost on RoCoF protection, as an estimate | SR-B4, SR-C5 |
| T02.02a | auto_assisted_human | Hornsea One loss 737 MW (799 MW to 62 MW) | SR-D-T02.02-03 |
| T02.02b | auto_assisted_human | Little Barford steam turbine ST1C loss 244 MW | SR-D-T02.02-03 |
| T02.03a | auto_assisted_human | Little Barford gas turbine GT1A loss 210 MW | SR-D-T02.02-03 |
| T02.03b | auto_assisted_human | Little Barford gas turbine GT1B loss 187 MW | SR-D-T02.02-03 |
| T02.04 | auto_assisted_human | Temporal groups: initial losses, GT1A, LFDD, GT1B; no sub-second order beyond the evidence | SR-B2, SR-B5, SR-B17 |
| T02.05a | auto_assisted_human | ESO six-component total 1,878 MW | SR-C1 |
| T02.05b | auto_assisted_human | The 1,878 MW accounting basis is identified (ESO cumulative infeed loss, six components incl. two DG estimates, through GT1B) | SR-C1, SR-C7 |
| T02.06 | judge | Additional net effects and later estimates kept distinct; Ofgem's ≥1,990 MW not substituted for the ESO total | SR-B25b, SR-C1, SR-C7, SR-X1 |
| T03.01 | auto_numeric | First post-fault frequency minimum: 49.083 Hz at 16:52:59 BST (lowest 1-s sample in 16:52:45–16:53:10) | SR-B1, SR-B18, SR-D-T03 |
| T03.02 | auto_numeric | Event minimum: 48.787 Hz at 16:53:49 BST (lowest sample in 16:53:20–16:54:30) | SR-B1, SR-B18, SR-D-T03 |
| T03.03 | auto_numeric | First sample at or above 50 Hz after the minimum: 50.001 Hz at 16:57:16 BST | SR-B1, SR-B18, SR-D-T03 |
| T03.04 | auto_assisted_human | Timestamps, Hz and sampling precision reported; landmark values from the frozen CSV, not rounded prose | SR-B6 |
| T04.01 | auto_numeric | Time below 49 Hz from R01: 33 s (strictly below, zero-order hold); other stated conventions within tolerance | SR-B1, SR-B18, SR-D-T04.01 |
| T04.03 | auto_assisted_human | Duration convention and sampling uncertainty stated; no sub-second transition claimed from 1-s data | SR-A1, SR-B1, SR-D-T04.03 |
| T05.01a | auto_assisted_human | Restoration instructions to the DNOs began at 16:58 BST | SR-B2, SR-B7 |
| T05.01b | auto_assisted_human | All restoration instructions issued by 17:16 BST | SR-B2, SR-B26 |
| T05.02 | auto_assisted_human | DNO demand restoration complete at 17:37 BST | SR-B2, SR-B7 |
| T05.03 | judge | Demand restoration kept distinct from frequency recovery and from the recovery of other affected services | SR-A1, SR-B20, SR-B21, SR-X1 |
| T06.01 | judge | Hornsea: abnormal reaction of the offshore turbine controllers and the resulting instability | SR-B20, SR-D-T06.01, SR-X1 |
| T06.02 | judge | Onshore control behaviour distinguished from the offshore response | SR-B22 |
| T06.03 | judge | Resonance and weak-network explanation attributed to its supporting account | SR-B19 |
| T06.04 | judge | Earlier oscillation (about 10 minutes before) and known modelling concern recognised | SR-D-T06.04 |
| T06.05 | judge | The cleared DRC hypothesis is not presented as the established cause | SR-B8, SR-B20 |
| T07.01 | auto_assisted_human | ST1C tripped on a discrepancy among its three speed signals | SR-B1, SR-D-T07.01, SR-E1 |
| T07.02 | auto_assisted_human | GT1A tripped automatically on high steam-bypass pressure | SR-D-T07.02-03, SR-E1 |
| T07.03 | auto_assisted_human | GT1B was tripped manually by the operators for safety (excessive steam pressure) | SR-D-T07.02-03, SR-E1 |
| T07.04 | judge | Underlying causes of the speed-signal discrepancy and the high-pressure conditions remain unestablished | SR-B9, SR-E1, SR-X3 |
| T07.05 | judge | Plausible underlying explanations labelled as hypotheses, not demonstrated root causes | SR-D-T07.05, SR-E1 |
| T08.01 | judge | Vector-shift, RoCoF and underfrequency (49 Hz) stages of distributed-generation loss kept separate | SR-C5, SR-D-T08.01 |
| T08.02 | auto_assisted_human | The ~200 MW at 49 Hz is a net effect, distinct from the gross generation lost | SR-B10, SR-C5 |
| T08.03 | auto_assisted_human | Ofgem's 1,300–1,500 MW total distributed-generation loss reported only as an estimate, on its basis | SR-A1, SR-C5, SR-D-T08.03 |
| T08.04 | judge | Missing telemetry and uncertain causal allocation of distributed-generation losses identified | SR-B23 |
| T08.05 | judge | Time and measurement bases reconciled instead of summing overlapping estimates | SR-B28, SR-C5 |
| T09.01 | auto_assisted_human | England & Wales LFDD stage 1 at 48.8 Hz | SR-B11 |
| T09.02a | auto_assisted_human | 931 MW attributed to the DNO-reported LFDD disconnection (ESO; Elexon demand control record) | SR-C2, SR-C7 |
| T09.02b | auto_assisted_human | 892 MW attributed to Ofgem as net demand disconnected | SR-C2, SR-C7 |
| T09.03 | judge | Demand relief from LFDD explained alongside the generation it also disconnected | SR-B24, SR-C5, SR-X1 |
| T09.04 | judge | Winter-peak basis of the 5% stage-1 requirement; not equated with the pre-event percentages | SR-B12 |
| T09.05 | judge | Relay tolerance explained; England & Wales thresholds not applied to Scotland | SR-D-T09.05 |
| T12.01a | auto_assisted_human | Largest secured loss 1,000 MW | SR-B13, SR-B17 |
| T12.01b | auto_assisted_human | Primary response held 1,022 MW (delivered within 10 s) | SR-B13, SR-B17, SR-X4 |
| T12.01c | auto_assisted_human | Secondary response held: 1,314 MW (ESO final report) vs 1,338 MW (ESO's earlier answers), each on its basis, delivered by 30 s | SR-B13, SR-B17, SR-C3, SR-C7, SR-X4 |
| T12.02 | auto_assisted_human | Initial estimated loss of 1,481 MW exceeded the 1,000 MW secured loss | SR-B14, SR-C1, SR-C7 |
| T12.03 | judge | Subsequent losses and the exhaustion of frequency response explained | SR-B25a, SR-X1 |
| T12.04 | judge | Response delivery shortfalls identified without asserting they alone caused LFDD | SR-B20, SR-D-T12.04 |
| T12.05 | auto_assisted_human | System inertia reported with its basis: 210 GVA.s (ESO Table 4) vs 219,632 MVA.s (ESO answer 42), both model estimates | SR-A7, SR-B17, SR-C4 |
| T16.01 | judge | Unrelated lightning strikes and trips ruled out using their timing and impacts | SR-D-T16.01 |
| T16.02 | judge | Transmission protection recognised as having operated as expected | SR-B3, SR-B20, SR-D-T16.02 |
| T16.03 | judge | Non-causal wider transmission outages distinguished from the reported Hornsea internal-network weakness | SR-B20, SR-D-T16.03 |
| T17.01 | judge | Uncertainty register: unknown underlying Little Barford causes | SR-B9, SR-E1 |
| T17.02 | judge | Uncertain distributed-generation volumes and causal split registered | SR-B23, SR-C5 |
| T17.03 | judge | Unexplained movement of about 100 MW registered without assigning it to an invented asset | SR-B15, SR-B20, SR-C5, SR-X1 |
| T17.04 | judge | Source disagreements, measurement limits and causal uncertainty kept separate | SR-D-T17.04 |

### FI — `gb-2019-full-investigation`: 106 criteria (4 auto_numeric, 49 auto_assisted_human, 53 judge)

Origin: `R` = re-bound unchanged from SR 0.1.1; `R*` = re-bound and marked changed in the FI key installed when this pack was written (key 0.1.1: T02.04, T04.03, T05.02, T05.03, T06.02, T08.04, T08.05, T09.05); `N` = new in increment B. Modes and titles are read from the installed keys.

| ID | Mode | Origin | Title | Items |
|---|---|---|---|---|
| T01.01 | auto_assisted_human | R | Initiating event: lightning fault on the Eaton Socon–Wymondley 400 kV circuit | SR-D-T01.01, SR-X4 |
| T01.02 | auto_assisted_human | R | Initiating event time 16:52:33 BST (within 1 s of 16:52:33.490) | SR-B1, SR-B2 |
| T01.03a | auto_assisted_human | R | Fault type: single (blue) phase to earth | SR-B3, SR-D-T01.03 |
| T01.03b | auto_assisted_human | R | Clearance by main protection in 70 ms (Wymondley Main) and 74 ms (Eaton Socon), within 80 ms | SR-B1, SR-D-T01.03 |
| T01.04 | auto_assisted_human | R | Delayed auto-reclose about 20 s later (16:52:53 BST); not another initiating fault | SR-B3 |
| T02.01a | auto_assisted_human | R | About 150 MW of embedded generation lost on vector-shift protection, as an estimate | SR-B4, SR-C5 |
| T02.01b | auto_assisted_human | R | About 350 MW of embedded generation lost on RoCoF protection, as an estimate | SR-B4, SR-C5 |
| T02.02a | auto_assisted_human | R | Hornsea One loss 737 MW (799 MW to 62 MW) | SR-D-T02.02-03 |
| T02.02b | auto_assisted_human | R | Little Barford steam turbine ST1C loss 244 MW | SR-D-T02.02-03 |
| T02.03a | auto_assisted_human | R | Little Barford gas turbine GT1A loss 210 MW | SR-D-T02.02-03 |
| T02.03b | auto_assisted_human | R | Little Barford gas turbine GT1B loss 187 MW | SR-D-T02.02-03 |
| T02.04 | auto_assisted_human | R* | Temporal groups: initial losses, GT1A, LFDD, GT1B; no sub-second order beyond the evidence | FI-B19, SR-B2, SR-B5, SR-B17 |
| T02.05a | auto_assisted_human | R | ESO six-component total 1,878 MW | SR-C1 |
| T02.05b | auto_assisted_human | R | The 1,878 MW accounting basis is identified (ESO cumulative infeed loss, six components incl. two DG estimates, through GT1B) | SR-C1, SR-C7 |
| T02.06 | judge | R | Additional net effects and later estimates kept distinct; Ofgem's ≥1,990 MW not substituted for the ESO total | SR-B25b, SR-C1, SR-C7, SR-X1 |
| T03.01 | auto_numeric | R | First post-fault frequency minimum: 49.083 Hz at 16:52:59 BST (lowest 1-s sample in 16:52:45–16:53:10) | SR-B1, SR-B18, SR-D-T03 |
| T03.02 | auto_numeric | R | Event minimum: 48.787 Hz at 16:53:49 BST (lowest sample in 16:53:20–16:54:30) | SR-B1, SR-B18, SR-D-T03 |
| T03.03 | auto_numeric | R | First sample at or above 50 Hz after the minimum: 50.001 Hz at 16:57:16 BST | SR-B1, SR-B18, SR-D-T03 |
| T03.04 | auto_assisted_human | R | Timestamps, Hz and sampling precision reported; landmark values from the frozen CSV, not rounded prose | SR-B6 |
| T04.01 | auto_numeric | R | Time below 49 Hz from R01: 33 s (strictly below, zero-order hold); other stated conventions within tolerance | SR-B1, SR-B18, SR-D-T04.01 |
| T04.02 | auto_assisted_human | N | Rail protection: Class 700/717 drives disconnect when the supply falls below 49 Hz, within 200 ms, as a reported design fact | FI-B2 |
| T04.03 | auto_assisted_human | R* | Duration convention and sampling uncertainty stated; no sub-second transition claimed from 1-s data | FI-B1, SR-A1, SR-B1, SR-D-T04.03 |
| T05.01a | auto_assisted_human | R | Restoration instructions to the DNOs began at 16:58 BST | SR-B2, SR-B7 |
| T05.01b | auto_assisted_human | R | All restoration instructions issued by 17:16 BST | SR-B2, SR-B26 |
| T05.02 | auto_assisted_human | R* | DNO demand restoration complete at 17:37 BST | FI-B16, SR-B2, SR-B7 |
| T05.03 | judge | R* | Demand restoration kept distinct from frequency recovery and from the later recovery of transport and other affected services | FI-B1, FI-B19, SR-A1, SR-B20, SR-B21, SR-X1 |
| T06.01 | judge | R | Hornsea: abnormal reaction of the offshore turbine controllers and the resulting instability | SR-B20, SR-D-T06.01, SR-X1 |
| T06.02 | judge | R* | Onshore control behaviour distinguished from the offshore response | FI-B19, SR-B22 |
| T06.03 | judge | R | Resonance and weak-network explanation attributed to its supporting account | SR-B19 |
| T06.04 | judge | R | Earlier oscillation (about 10 minutes before) and known modelling concern recognised | SR-D-T06.04 |
| T06.05 | judge | R | The cleared DRC hypothesis is not presented as the established cause | SR-B8, SR-B20 |
| T07.01 | auto_assisted_human | R | ST1C tripped on a discrepancy among its three speed signals | FI-G2, SR-B1, SR-D-T07.01, SR-E1 |
| T07.02 | auto_assisted_human | R | GT1A tripped automatically on high steam-bypass pressure | SR-D-T07.02-03, SR-E1 |
| T07.03 | auto_assisted_human | R | GT1B was tripped manually by the operators for safety (excessive steam pressure) | SR-D-T07.02-03, SR-E1 |
| T07.04 | judge | R | Underlying causes of the speed-signal discrepancy and the high-pressure conditions remain unestablished | FI-B8, FI-E1, SR-B9, SR-E1, SR-X3 |
| T07.05 | judge | R | Plausible underlying explanations labelled as hypotheses, not demonstrated root causes | FI-B8, FI-E1, SR-D-T07.05, SR-E1 |
| T08.01 | judge | R | Vector-shift, RoCoF and underfrequency (49 Hz) stages of distributed-generation loss kept separate | SR-C5, SR-D-T08.01 |
| T08.02 | auto_assisted_human | R | The ~200 MW at 49 Hz is a net effect, distinct from the gross generation lost | FI-B20, SR-B10, SR-C5 |
| T08.03 | auto_assisted_human | R | Ofgem's 1,300–1,500 MW total distributed-generation loss reported only as an estimate, on its basis | FI-B20, SR-A1, SR-C5, SR-D-T08.03 |
| T08.04 | judge | R* | Missing telemetry and uncertain causal allocation of distributed-generation losses identified | FI-B19, SR-B23 |
| T08.05 | judge | R* | Time and measurement bases reconciled instead of summing overlapping estimates | FI-B19, SR-B28, SR-C5 |
| T09.01 | auto_assisted_human | R | England & Wales LFDD stage 1 at 48.8 Hz | SR-B11 |
| T09.02a | auto_assisted_human | R | 931 MW attributed to the DNO-reported LFDD disconnection (ESO; Elexon demand control record) | SR-C2, SR-C7 |
| T09.02b | auto_assisted_human | R | 892 MW attributed to Ofgem as net demand disconnected | SR-C2, SR-C7 |
| T09.03 | judge | R | Demand relief from LFDD explained alongside the generation it also disconnected | SR-B24, SR-C5, SR-X1 |
| T09.04 | judge | R | Winter-peak basis of the 5% stage-1 requirement; not equated with the pre-event percentages | FI-G2, SR-B12 |
| T09.05 | judge | R* | Relay tolerance explained; England & Wales thresholds not applied to Scotland | FI-B19, SR-D-T09.05 |
| T10.01 | judge | N | Trains stopped by their own on-board protection although the traction supply was generally maintained | FI-D-T10.01 |
| T10.02a | auto_assisted_human | N | 29 Class 700/717 trains locked out (ORR) | FI-A1, FI-A3, FI-B3, FI-X2 |
| T10.02b | auto_assisted_human | N | 22 trains permanently locked out, needing a technician (ORR) | FI-A1, FI-A3, FI-B3 |
| T10.02c | auto_assisted_human | N | 7 trains restored by driver reset (ORR) | FI-A1, FI-A3, FI-B3 |
| T10.03a | auto_assisted_human | N | 31 trains stranded (ORR) | FI-A1, FI-A3, FI-B4, FI-B19 |
| T10.03b | auto_assisted_human | N | Two Class 387 trains trapped indirectly by the locked-out units | FI-A1, FI-B4, FI-G2 |
| T10.04 | auto_assisted_human | N | Software 3.25.x units went into a temporary lock-out drivers could reset; 3.27.x units into a permanent lock-out needing a technician | FI-D-T10.04 |
| T10.05a | auto_assisted_human | N | 371 trains cancelled and 220 part-cancelled, kept distinct | FI-A1, FI-B5, FI-X2 |
| T10.05b | auto_assisted_human | N | 873 trains delayed (ESO, E3C) kept distinct from 14,428 delay minutes (ORR Table 1) | FI-A1, FI-B5 |
| T10.05c | judge | N | Inconsistent rail counts attributed to their reports | FI-A1, FI-A3, FI-B5 |
| T11.01a | auto_assisted_human | N | Newcastle Airport disconnected by LFDD (Northern Powergrid) | FI-A1, FI-B6 |
| T11.01b | auto_assisted_human | N | Ipswich Hospital lost supply through its own protection, not LFDD | FI-A1, FI-B6 |
| T11.02 | auto_assisted_human | N | Wirral line (Merseyrail) traction supply lost through LFDD | FI-D-T11.02 |
| T11.03 | judge | N | Water and refinery impacts described as supplied, without invented mechanisms | FI-B6, FI-B19, FI-G2 |
| T12.01a | auto_assisted_human | R | Largest secured loss 1,000 MW | SR-B13, SR-B17 |
| T12.01b | auto_assisted_human | R | Primary response held 1,022 MW (delivered within 10 s) | SR-B13, SR-B17, SR-X4 |
| T12.01c | auto_assisted_human | R | Secondary response held: 1,314 MW (ESO final report) vs 1,338 MW (ESO's earlier answers), each on its basis, delivered by 30 s | SR-B13, SR-B17, SR-C3, SR-C7, SR-X4 |
| T12.02 | auto_assisted_human | R | Initial estimated loss of 1,481 MW exceeded the 1,000 MW secured loss | SR-B14, SR-C1, SR-C7 |
| T12.03 | judge | R | Subsequent losses and the exhaustion of frequency response explained | SR-B25a, SR-X1 |
| T12.04 | judge | R | Response delivery shortfalls identified without asserting they alone caused LFDD | SR-B20, SR-D-T12.04 |
| T12.05 | auto_assisted_human | R | System inertia reported with its basis: 210 GVA.s (ESO Table 4) vs 219,632 MVA.s (ESO answer 42), both model estimates | FI-C4, SR-A7, SR-B17, SR-C4 |
| T13.01 | judge | N | Contributing factor: distributed-generation protection settings and the lack of visibility of distributed generation | FI-B12, FI-D-T13 |
| T13.02 | judge | N | Contributing factor: weaknesses in compliance evidence and testing, and in information sharing | FI-B12, FI-D-T13 |
| T13.03 | judge | N | Contributing factor: reserve and inertia assumptions and response delivery | FI-B12, FI-D-T13 |
| T13.04 | judge | N | Contributing factor: LFDD's interaction with distributed generation and essential services | FI-B12, FI-D-T13, FI-F1, FI-G2 |
| T13.05 | judge | N | Contributing factor: rail protection settings and recovery arrangements | FI-B12, FI-D-T13, FI-G2 |
| T13.06 | judge | N | Triggering, contributing and systemic factors kept separate, each supported | FI-B12, FI-D-T13, FI-F1 |
| T14.01 | judge | N | Hornsea One: fault ride-through and damping concerns, supported by the requirements in the evidence | FI-B15, FI-D-T14.01, FI-G2 |
| T14.02 | judge | N | Little Barford's contribution stated without inventing an established underlying fault | FI-B8, FI-B19, FI-D-T14.02, FI-E1 |
| T14.03 | auto_assisted_human | N | EPN and SPN reconnected demand without the ESO's instruction, against the instruction requirement | FI-B7, FI-B15, FI-G1 |
| T14.04 | judge | N | Process concerns kept distinct from demonstrated breach and from outcomes | FI-A4, FI-B8, FI-D-T14.04-05, FI-E3, FI-G1 |
| T14.05 | judge | N | No invented settlements or legal findings; the missing proof is identified | FI-A2, FI-A4, FI-B8, FI-B19, FI-D-T14.04-05, FI-E3, FI-G1, FI-X2 |
| T15.01a | auto_assisted_human | N | First ESO contact with BEIS at 17:40-17:41 BST | FI-A1, FI-A3, FI-B9, FI-B18 |
| T15.01b | auto_assisted_human | N | First ESO public statement at 18:27 BST | FI-A1, FI-B9, FI-B18, FI-X2 |
| T15.01c | judge | N | Sequence of government, regulator and public contacts reconstructed from the records | FI-A1, FI-B9, FI-B19 |
| T15.02 | auto_assisted_human | N | The 17:51 vs 18:00 discrepancy for the first Ofgem contact kept | FI-A3, FI-B10, FI-B18 |
| T15.03 | auto_assisted_human | N | Hornsea did not notify the ESO directly and restarted modules without coordination | FI-B11 |
| T15.04 | judge | N | Delays and misattribution in communications described, without treating them as causes of the outage | FI-B11 |
| T16.01 | judge | R | Unrelated lightning strikes and trips ruled out using their timing and impacts | SR-D-T16.01 |
| T16.02 | judge | R | Transmission protection recognised as having operated as expected | SR-B3, SR-B20, SR-D-T16.02 |
| T16.03 | judge | R | Non-causal wider transmission outages distinguished from the reported Hornsea internal-network weakness | SR-B20, SR-D-T16.03 |
| T17.01 | judge | R | Uncertainty register: unknown underlying Little Barford causes | FI-B8, FI-E1, SR-B9, SR-E1 |
| T17.02 | judge | R | Uncertain distributed-generation volumes and causal split registered | SR-B23, SR-C5 |
| T17.03 | judge | R | Unexplained movement of about 100 MW registered without assigning it to an invented asset | SR-B15, SR-B20, SR-C5, SR-X1 |
| T17.04 | judge | R | Source disagreements, measurement limits and causal uncertainty kept separate | SR-D-T17.04 |
| T18.01 | judge | N | Recommendations linked to established findings | FI-B12, FI-B17, FI-D-T18 |
| T18.02 | judge | N | Recommendations cover generation compliance and protection improvements | FI-B12, FI-D-T18 |
| T18.03 | judge | N | Recommendations cover visibility, reserve/response or inertia | FI-B12, FI-D-T18 |
| T18.04 | judge | N | Recommendations cover LFDD and essential-service resilience | FI-B12, FI-D-T18, FI-G2 |
| T18.05 | judge | N | Recommendations cover rail recovery and communications | FI-B12, FI-D-T18 |
| T18.06 | judge | N | Each recommendation has a plausible owner and a verification method; equivalent justified actions accepted | FI-B12, FI-D-T18 |
| T19.01 | judge | N | Further evidence requests: who should supply the missing evidence and exactly what | FI-A2, FI-B12, FI-D-T19.01 |
| T19.02 | judge | N | Notification and coordination needs supported by the requirements in the evidence; no unverified ESQCR or OC7/OC10 obligations | FI-B12, FI-B13, FI-B15 |
| T20.01 | judge | N | Executive summary: accurate account of the triggering event | FI-B12, FI-B17, FI-D-T20, FI-G1 |
| T20.02 | judge | N | Executive summary: clear sequence and consequences | FI-B12, FI-D-T20 |
| T20.03 | judge | N | Executive summary: contributing factors kept separate from underlying unknowns | FI-B8, FI-B12, FI-B19, FI-D-T20, FI-E1 |
| T20.04 | judge | N | Executive summary: significant estimates and disagreements attributed | FI-B12, FI-D-T20, FI-G2 |
| T20.05 | judge | N | Executive summary: evidence-linked actions in priority order | FI-B12, FI-D-T20 |
| T20.06 | judge | N | Executive summary: no unsupported certainty; at most 600 words | FI-B8, FI-B12, FI-B14, FI-B17, FI-E1 |
