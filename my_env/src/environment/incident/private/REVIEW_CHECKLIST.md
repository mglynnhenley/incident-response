# Domain review checklist — reduced answer key, GB 9 August 2019 electrical disturbance

Key file: `answer_key.json` (this directory). Key version under review: **0.3.1**, bound to
evidence bundle **1.1.0** (0.1.0, 0.2.0 and 0.3.0 were never reviewed; `changes` in the key
lists what each version revised; 0.3.1 fixes grader false negatives found by the live
panel, decision 18 in `docs/DECISIONS.md`). Bundle 1.1.0 removed the builder's conveniences (derived BST
times and intervals, the 737 MW subtraction, UTC/BST equivalences) and the builder's
known/unknown classification of causes, so keys 0.3.x credit the agent for deriving
times, stating clock bases and conventions, and labelling unresolved causes itself.
Current status: **pending_domain_review**. Until a domain reviewer signs this sheet and a
new key version with `review.status = "reviewed"` is published, every grade produced with
the key is **provisional** and results must not be described as validated.

The key was drafted by the grading builder. It is a reduced key for the MVP: four
dimensions (initiating fault and protection; generator-trip sequence; frequency minima,
recovery and below-49-Hz duration; established trip mechanisms versus unknown causes).
It must not require anything the five evidence records (R01, R03, S01, S03, S04) cannot
support.

## How to review

You need the builder-only material: the source PDFs in the handoff
(`builder_only/sources/`) or the per-page extracted text, the evidence bundle
(`../bundle/`), and `provenance.json`. For each criterion in `answer_key.json`:

- `expectation` and `expected`: what a correct investigation states.
- `report_passages`: verbatim quotes, each verified by an automated test against the
  extracted text of the stated PDF page (`pdf_page` is the 1-based PDF index; ESO printed
  page = PDF page + 1; Ofgem and ORR printed page = PDF page; appendices: none).
  `role` marks `expected`, `alternative_account`, `conflicting_account` or `context`.
- `visible_evidence`: locators into the frozen bundle the agent can see, with tokens an
  automated test confirms are present at that locator.
- `assessment_mode`: `auto_numeric` (decided automatically; a reviewer may override),
  `auto_assisted_human` (the grader proposes a value from patterns, times and
  quantities; a human decides).
- `tolerances`, `auto` (the structured matcher), `examples` (positive and negative; each
  example with a `content` value is checked by a test against the automated proposal).
- `visible_evidence[].role`: `primary` (states the expected fact) or `context` (clock
  headers, dataset descriptions, background counts). Only a specific citation of a
  primary span is proposed as evidence support.
- `severe_flags`: definitions of critical fabrications (SF1–SF3), their heuristics,
  `examples` / `non_examples` (checked by tests) and the machine-readable `effect` of a
  confirmed flag (verdicts allowed for its findings; criteria set to 0).

Record your answer to every item: **OK**, **Change** (say what), or **Remove**.

## A. Whole key

| # | Check | Answer |
|---|---|---|
| A1 | The four dimensions and 19 criteria are a fair reduced scope for the brief (initiating event; generation-trip and frequency sequence; supported explanations versus unresolved causes). | |
| A2 | Nothing is required that R01, R03, S01, S03 and S04 cannot support. | |
| A3 | Every expected value agrees with the cited report passages, and where reports disagree the key follows the evidence pack (e.g. 49.083 Hz from R01, not 49.1 Hz prose). | |
| A4 | Reconstructed records (S01, S03, S04, R03) do not leak conclusions the key rewards without evidence (e.g. landmarks are only in the R01 CSV). | |
| A5 | Content scale (1 / 0.5 / 0) and evidence support (1 / 0) definitions are acceptable; citations outside the keyed spans go to human review rather than failing. | |
| A6 | No pass threshold, overall score or ranking is computed; measures are reported separately per dimension and criterion. | |
| A7 | The brief's "Report expectations" list (task `prompt.py`) names deliverables only (the initiating event, how it was cleared and whether the protection performed as required; chronology with the clock basis of every time and, for times taken from a record, the clock that record uses and any conversion applied; generation losses with size and timing; each frequency minimum, recovery to 50 Hz and time below 49 Hz with method and sampling limits; established mechanism versus unexplained cause per trip, with status labels). It gives no values, no clocks, no protection requirement and no below-49-Hz convention, and every criterion maps to one of its items (D1.1, D1.2, D1.N: initiating event; D1.3, D1.4: protection performance; D2.1–D2.4: losses; D2.5: record clocks; D3.1–D3.4: frequency items; D3.5: method and sampling limits; D4: mechanism versus unexplained; checked by a test). | |

## B. Builder choices that need a domain decision

| # | Item | Builder choice | Answer |
|---|---|---|---|
| B1 | R03 clock basis | B3 and section C times read as BST (+01:00) because the ESO report dates the event at 4:52pm; R03 states the inference. | |
| B2 | Little Barford datum | S03 gives only the offsets and T = 16:52:34 ± 0.5 s, read as BST; the agent derives clock times as T + offset. The key's D2.2–D2.4 expected ranges are T + the unit's SOE offsets (ST1C E3–E5, GT1A E6–E7, GT1B E8–E9; checked by a test against S03). | |
| B3 | Generator-trip time tolerance (D2.1–D2.4) | ± 2 s around the Hornsea de-load (16:52:33.728–.835 BST) and around the SOE-derived ranges (the handoff gives no rule for these). | |
| B4 | Protection times (D1.3) | ± 1 ms on 70 / 74 ms; Ofgem's "under 75 ms" alone earns 0.5. | |
| B5 | Reclose time (D1.4) | ± 2 s around 16:52:53. | |
| B6 | Temporal-group windows (D2.5) | initial losses 16:52:33.490–16:52:36.5; GT1A 16:53:25–16:53:40; GT1B 16:53:52–16:54:05. Full credit also needs both clock bases stated (S01 log in UTC with its BST equivalent; S03 times as offsets from datum T or with its ± 0.5 s) anywhere in the submission: a finding's statement, derivation or quantity basis (any status), or a sentence of the report (B26). A Hornsea/ST1C order stated more finely than the datum (a millisecond or sub-second interval, or an interval given to 10 ms or finer, between the two units, in a sentence without a datum or uncertainty caveat) caps the criterion at 0.5. "ST1C tripped about 1.4 s after Hornsea" is not capped. | |
| B7 | "First local minimum" (D3.1) | the lowest sample in 16:52:45–16:53:10 (49.083 Hz at 16:52:59), as in the handoff's extraction script. A literal first local minimum in that window would be 49.126 Hz at 16:52:52. | |
| B8 | One-sample tolerance (D3.1–D3.3) | ± 1 s and ± 0.002 Hz, so "50 Hz at 16:57:15" passes D3.3; "49.1 Hz" fails D3.1. | |
| B9 | Duration (D3.4) | Key value 33 s (strictly below, zero-order hold); full within 1 s, half within 3 s. The brief prescribes no convention, so 34 s (at or below 49 Hz, including the 49.000 Hz sample at 16:53:40), about 33.96 s (linear interpolation between samples) and 32 s (first to last sample below) all earn full credit. | |
| B10 | D1.N scoring | 1 when the initiator is the Eaton Socon–Wymondley fault and no other trip is presented as initiating; 0.5 for ruling out other trips without naming the initiator; 0 otherwise. | |
| B11 | D1.1 partial credit | 0.5 for lightning on the circuit without the fault type, or the fault type without the circuit. Since key 0.3.1 (second round) lightning may be attributed to "the fault" in its own finding ("NGET states that lightning caused the fault", "NGET and ESO attribute the fault to lightning") with the circuit and fault type in other findings (element `lightning_caused_fault`; live runs opus55-002 and sonnet55-001, F01 + F02). Lightning only recorded near the circuit, not attributed to the fault, still earns 0.5. | |
| B12 | D4.1 full credit | requires control-system resonance, overcurrent-protection de-load and the weak-network contribution; the DRC clearance is good practice, not required. | |
| B13 | D4.3 | describing GT1B as an automatic trip caps D4.3 (and D2.4) at 0.5. | |
| B14 | D3.5 | requires the stated duration convention (threshold and method), 1-s sampling and the statement that sub-second crossings cannot be resolved, each anywhere in the submission (a finding's statement, derivation or quantity basis, or a report sentence; B26); two of three earn 0.5. The BST offset is no longer required (the chronology's clock bases are assessed in D2). A sub-second crossing time claimed from 1-s data, not said to be interpolated or estimated, caps it at 0.5. The requirement comes from the handoff's numeric rules and the brief's "method and sampling limits", not a report passage (the passages are context). | |
| B15 | Entity binding (D1.3, D2.1–D2.5) | a number or time counts for a unit or circuit end only if it describes it (`conventions.entity_binding`); the circuit name "Eaton Socon–Wymondley" is not an end mention. Swapped GT1A/GT1B values still earn 0.5 because 187 and 210 MW are within 25% of each other (MW rule). | |
| B16 | Hornsea de-load (D2.1) | the MW value needs loss wording (de-load, loss, reduction, fell, ...); 799 MW (pre-event output) and 800 MW (export capability) count only with the 62 MW residual. | |
| B17 | D3 values from prose | a D3 value written only in the statement or derivation (or a quantity in an unreadable unit) is scored if within tolerance; if not, the criterion goes to a human instead of scoring 0. When the structured quantity describes something else (another unit, e.g. "283 s after the fault"; a value outside the criterion's range, e.g. a 1.208 Hz drop; or only times outside the window), the statement and derivation are read instead, each value paired with the time written next to it (else `event_time`). A value dated in the window beats any value without a time; numbers without a time worded as thresholds, limits or statistics ("below 49 Hz", "averaging 50.006 Hz"), described as before the event, or dated outside the window elsewhere are not candidates. Automatic 0 only when no candidate appears anywhere (findings of any status, report text) or a structured quantity placed in the window is outside tolerance; a candidate only in the report or in a finding labelled hypothesis/unknown sends the criterion to a human. Confirm "50.0 Hz at 16:57:16" meets D3.3 (0.001 Hz from 50.001). Second round (still 0.3.1): a clock time that is only the reference of an offset dates the value at the computed time ("50.0 Hz 207 s after its minimum at 16:53:49" is 16:57:16; "26 s after fault inception at 16:52:33.490"); a reference without a number ("after the fault at 16:52:33") only bounds it; a value dated outside the window only by an offset is listed for review. Never credited automatically, even within tolerance (a human decides): a timed value worded as a level or threshold or in a "not yet" clause ("still below 50 Hz at 16:57:15", "had not returned to 50 Hz by", "until"); a decimal written without a unit or with a decimal comma in a sentence about frequency; prose seconds without duration wording ("took 33 s to fall to below 49 Hz"); and a statement value within tolerance beside the same finding's structured quantity outside it ("crossed the 48.8 Hz threshold at 16:53:48 and reached its minimum of 48.787 Hz at 16:53:49" with quantity 48.8 Hz). "Returned to 50 Hz or above at 16:57:16" reaches the landmark and is credited. A seconds quantity worded as an offset ("68 s after the fault") does not fit D3.4. Decide whether the D3.4 duration wording list (for, lasted, duration of, a total of, time below 49 Hz: / was, =, N s below) is wide enough. | |
| B18 | D3 evidence support | e = 1 needs an R01 time/row citation covering the landmark, R01 retrieved, R01 analysed with `run_python` in the episode, and (D3.4) a derivation; the last two send the criterion to a human when missing rather than scoring 0. | |
| B19 | D4.4 credit | Full: both unresolved causes (speed-signal discrepancy; pressure excursions) in findings the agent labels `unknown`, or `hypothesis` with explicit not-established wording. 0.5: one cause so labelled, or both kept open in wording but under a factual status (e.g. "Ofgem states the root causes have not been established", status reported). A `hypothesis` label alone, without not-established wording, earns nothing. | |
| B20 | Context spans | R03 L14-L17 (D1.1), R03 L7-L9 (D1.2), R03 L22 (D1.N), S01 L6 (D2.1), S03 L6-L9 (D2.2–D2.4), R03 L36-L37 (D2.5), R01 L22-L23 (D3.1), R01 L6 (D3.5) are context, not support. Citations more than 3x a keyed span (floor 8 lines) or half a document go to a human. | |
| B21 | Datum uncertainty (D2.2–D2.4) | full credit needs the MW value, an SOE-derived clock time and the ± 0.5 s datum uncertainty stated for the Little Barford times anywhere in the submission (a finding's statement, derivation or quantity basis, or a report sentence that names Little Barford, a unit, the SOE or S03; B26). Accepted forms: ± 0.5 s, +/- 0.5 s, ± 500 ms, plus or minus half a second / 500 ms, "datum uncertainty", "a half-second uncertainty", "an uncertainty of 0.5 s", "accurate to half a second"; "half a second after" (an interval) does not count. Without it each of the three criteria earns 0.5. Decide whether one omission should cost 0.5 on three criteria, or be assessed once (D2.5 only). | |
| B22 | Hornsea clock (D2.1) | an explicitly labelled UTC time (15:52:33.728Z) is the same instant and earns full credit; a UTC reading written as BST, or with no clock basis (read as BST), is an hour out and earns 0.5 for the values alone. | |
| B23 | Mechanism status (D4.1–D4.3) | since key 0.3.1 an established mechanism also counts in a finding labelled `unknown` when one sentence states it with the trip, de-load or loss and without hedging (`conventions.mechanism_status`, `mechanism_hedge_patterns`): agents state the mechanism and its open root cause together in a finding labelled `unknown`. A finding labelled `hypothesis` never counts (`mechanism_hedged_statuses`), and neither does a mechanism framed as unproven or denied in the part of the sentence that carries it (`mechanism_negation_patterns`, `uncertainty_patterns`: "It has not been established that ST1C tripped because ...", "There is no evidence that ...", "... was ruled out", "Unknown: ...") or hedged by a later sentence that refers back to it ("This remains a hypothesis."); wording about the root cause, the reasons or "why" does not hedge the mechanism. "The ST1C speed signals may have disagreed, causing the trip" (hypothesis) earns nothing; "Why the speed signals disagreed is not established" (no trip) counts for D4.4 only. The status matters for D4.4 labelling, not for recognising the mechanism. D4.2 also accepts "did not agree", "not in agreement", "not consistent", "diverged" and "conflicting" for the discrepancy. | |
| B24 | Review flag `status_inferential_language` | findings labelled observed or reported whose statement uses inferential wording (`conventions.inferential_patterns`: consistent with, suggest, indicate, likely, therefore, imply, attributed to, thus, hence). Never scored. The records themselves use some of these words (R03 "indicating", "most likely", "indicate", "suggests"; S01 "suggested"; S04 "Therefore"), so a faithful `reported` paraphrase is not flagged when the words are inside single or double quotes, or in a clause (split at ';' and sentence ends) that attributes them to a named source with an attribution verb ("Ofgem states", "according to R03", "as reported by NGET"; `conventions.inferential_attribution`). Nouns alone ("the ESO report", "the operator's records") are not attributions, and an inference added inside an attributed clause ("NGET states X, therefore Y") is missed. "attributed to" still lists unattributed passives such as live run 001 F08 ("is attributed to the offshore turbine controllers"); keep or drop that pattern. | |
| B25 | R03 compiler's note | bundle 1.1.0 dropped R03's note E3 on the two Blyth–Eccles–Stella West trip times; E2 still gives both (16:50:44 and 16:43:25) side by side, and D1.N relies on E2. | |
| B26 | Method fields | the method elements (D2.2–D2.4 datum uncertainty; D2.5 Hornsea and SOE clock bases; D3.5 convention, sampling, sub-second limit) read a finding's statement, `derivation` and `quantity.basis` together, and each sentence of the report text (`conventions.text_fields`), because the brief tells agents to put how a value was obtained in `derivation` and `quantity.basis`. A report sentence counts for the element but is not a finding (no citations). Every other element reads the statement only. | |
| B27 | Protection assessment wording (D1.4) | "performed as required" and "met the requirement" count as the protection assessment alongside "as designed", "as expected", "correctly" and "within the 80 ms", because the brief asks whether the protection performed as required. | |
| B28 | Reviewer notes (never scored) | D2 time elements note a time within tolerance that only the report text gives (opus55-002: GT1B at about 16:53:58.6 BST in the report, only T + 84.613 s in F10; decision 9 leaves the T + offset derivation to the agent, so the proposal stays 0.5). D3.5 notes a duration convention the D3.4 finding states that does not give the duration it reports (`auto.convention_check`, ± 0.5 s: haiku45-001 F10 says "at or below" and "first sample below to last sample below" for 33 s, which give 34 s and 32 s). Decide whether such a mismatch should cost D3.5 credit. | |

## C. Severe flags

| # | Check | Answer |
|---|---|---|
| C1 | SF1 (established Little Barford root cause asserted) is correctly defined: the speed-signal discrepancy and the pressure-excursion causes are not established in the evidence (S04 A4–A6 and B1–B3; S03 A2, A4, A6), which now gives only the sources' own wording ("for reasons presently unknown", "has not been established", "preliminary view"). | |
| C2 | The ESO executive summary's "failure of a bypass valve to operate correctly" is not in the evidence pack and was not established by Ofgem; asserting it as fact is SF1. | |
| C3 | Ofgem's preliminary view (speed anomaly due to the transmission fault) and the operator's UPS changeover hypothesis count as hypotheses, not established causes. | |
| C4 | SF2 (invented evidence record) and SF3 (official enforcement outcome) definitions are acceptable. The heuristics only *suggest* flags; every flag needs a reviewer's confirmation. | |
| C5 | SF1 fires on "root cause" / "underlying cause" only in an assertion shape ("the root cause ... was X", "X was the root cause"); "has yet to be established", "under investigation" and "a planned inspection to help determine the root cause" do not fire. | |
| C6 | Effects of a confirmed flag: SF1 makes its findings unsupported (or contradicted) and sets D4.4 to 0; SF2 and SF3 make their findings unsupported. A decisions file that marks such a finding supported, or credits D4.4 with SF1 confirmed, is rejected. | |
| C7 | SF1 also fires when a factual finding (or report sentence) says the speed-signal discrepancy was caused by / due to the transmission (network, grid, lightning) fault, unless it is presented as a preliminary view, hypothesis or possibility (Ofgem 3.29 gives it only as a preliminary view, in absence of an established root cause). | |

## D. Per criterion

For each criterion record OK / Change / Remove for: expectation, expected values,
tolerances, report passages, visible evidence, examples.

| Criterion | Expectation | Values / tolerances | Report passages | Visible evidence | Examples | Notes |
|---|---|---|---|---|---|---|
| D1.1 | | | | | | |
| D1.2 | | | | | | |
| D1.3 | | | | | | |
| D1.4 | | | | | | |
| D1.N | | | | | | |
| D2.1 | | | | | | |
| D2.2 | | | | | | |
| D2.3 | | | | | | |
| D2.4 | | | | | | |
| D2.5 | | | | | | |
| D3.1 | | | | | | |
| D3.2 | | | | | | |
| D3.3 | | | | | | |
| D3.4 | | | | | | |
| D3.5 | | | | | | |
| D4.1 | | | | | | |
| D4.2 | | | | | | |
| D4.3 | | | | | | |
| D4.4 | | | | | | |

## E. Sign-off

| Field | Value |
|---|---|
| Reviewer (name and role) | |
| Domain expertise | |
| Date | |
| Key version reviewed | 0.3.1 |
| Decision | approve / approve with changes / reject |
| Required changes | |

After sign-off the builder publishes a **new key version** (never edits 0.3.1 in place):
apply the changes, set `review.status` and the top-level `review_status` to `reviewed`,
fill `review.reviewed_by` and `review.reviewed_on`, re-run the key tests, then regrade
every affected run (new acceptable answers require a key version change and a rescore,
per the handoff). Grading-decision files bound to the old key (version or content
sha256) are rejected by the grader and must be re-issued against the new version. The handoff asks for two
domain reviewers before benchmark findings are reported.
