# Domain review checklist — system-response answer key, GB 9 August 2019

Key file: `answer_key.json` (this directory), key schema `gb2019-sr-answer-key/1`.
Key version under review: **0.1.1** (grader 0.1.1), bound to the system-response evidence bundle
**0.1.0** (`bundle.bundle_sha256` in the key; a test checks it against the installed
bundle). Task: `gb-2019-system-response` (increment A: initiating fault to the
restoration of disconnected demand). Grader: `environment/incident/sr_grading.py`
(with `sr_accounting.py` for the accounting-basis checks).

Current status: **pending_domain_review**. Until a domain reviewer signs this sheet and a
new key version with `review.status = "reviewed"` (and the top-level `review_status`
mirror) is published, every grade produced with this key is **provisional** and results
must not be described as validated. A changed key needs new grading decisions (they are
bound to the key's sha256) and a regrade of every affected run.

The key was drafted by the grading builder. It covers the handoff topics T01–T09, T12,
T16 and T17 (60 criteria, including split fields and one addition, T12.05: 4
`auto_numeric`, 32 `auto_assisted_human`, 24 `judge`; `judge.criteria` lists the 24).
Review round 1 (still 0.1.0, nothing released in between; see the key's `changes`)
narrowed contradiction rules, accounting binding and overlap groups, and some
pre-screens on real phrasing. Review round 2 (0.1.1: grades of 0.1.0 had been reported
for the two live panels) read every flag, cap and judge/pre-screen disagreement on the
six real submissions (`tests/fixtures/sr_live`, `tests/test_sr_grading_live_runs.py`)
and corrected the false positives and negatives it confirmed: accounting source binding,
SF1 on the trip mechanism, nine pre-screens, the labelling and inferential-language
flags (items B21–B27, C7, E1). An independent check of round 2 (still 0.1.1, nothing
released in between) corrected binding rules that crossed clauses, the owner of a bare
"final report", range parsing, overlapping sums written with labels or in prose, SF1
recall, five pre-screens and the flag exemptions (items B23–B25, B27, B28, C6, C7, E1).
Judge-visible key text did not change. The items below describe the current key. It must not
require anything the bundle cannot support: the rail criterion T04.02 is deferred to
increment B; the bundle has no DNO asset logs and one control room (ESO-ENCC), which no
criterion requires.

## How to review

You need the builder-only material: the source PDFs in the handoff
(`builder_only/sources/`) or the per-page extracted text, the evidence bundle
(`../../bundles/system_response/`), and `provenance.json` in this directory. For each
criterion in `answer_key.json`:

- `handoff_text`: the handoff criterion it implements; `task_criterion`, `field` and
  `subweight`: a compound criterion split into fields (`T02.02a`, `T02.02b`, ...) with
  equal subweights. Subweights are a reporting convenience only: the grader computes no
  task total, overall score, threshold or ranking. `origin` is `handoff`,
  `handoff_split`, `handoff_adapted` (with `adaptation` saying what changed and why) or
  `increment_A_addition`.
- `expectation`, `expected`: what a correct investigation states.
- `report_passages`: verbatim quotes, each verified by a test against the extracted text
  of the stated PDF page (`pdf_page` is the 1-based PDF index; ESO printed page = PDF page
  + 1; Ofgem printed page = PDF page; appendices and E3C: none). Most are the provenance
  quotes behind the keyed bundle lines; `role` is `expected`, `alternative_account`,
  `conflicting_account` or `context`.
- `visible_evidence`: locators the agent can see, with tokens a test confirms at that
  locator. Locator kinds: lines (`L12-L18`), R01 time/rows, and records:
  `event:<id>` (asset-log rows), `entry:<id>` (control-log entries), `response:<id>`
  (witness answers, evidence S09). S05 and S06 are data-return-only documents
  (`request_data_return`). `role` `primary` spans support the expected fact; `context`
  spans (clock headers, scope notes) do not earn an evidence proposal.
- `assessment_mode`: `auto_numeric` (decided automatically from the frozen R01 series; a
  reviewer may override), `auto_assisted_human` (the grader proposes from patterns,
  values, times and accounting-basis checks; a human decides; the judge never decides
  these), `judge` (interpretive: the LLM judge proposes, bounded by automated caps; a
  human signs off), `human`.
- `auto`: the automated matcher (for `judge` criteria a pre-screen shown to the judge and
  to you), `tolerances`, `accounting_basis` (figure IDs in `accounting.figures`) and
  `examples` (positive and negative; `content` is the value the key expects, `prescreen`
  the pre-screen proposal of a judge criterion; tests check both). `reviewer_note` fields
  (in examples and tolerances) are notes for you; neither they nor `prescreen` are shown
  to the judge, which sees no MVP criterion IDs, live runs or pre-screen.
- `severe_flags`: SF1–SF3 with heuristics, examples, non-examples and the
  machine-readable effect of a confirmed flag.

Record your answer to every item: **OK**, **Change** (say what), or **Remove**.

## A. Whole key

| # | Check | Answer |
|---|---|---|
| A1 | The 12 tasks and 60 criteria are a fair implementation of the handoff criteria for T01–T09, T12, T16 and T17 (adaptations: T04.03 keeps only the sampling-uncertainty half because rail is deferred; T05.03 distinguishes demand restoration from frequency recovery and from other services, because the bundle times no transport recovery; T08.03 points at S06, where this bundle reproduces Ofgem's estimate, not S12). | |
| A2 | Nothing is required that the bundle cannot support (no DNO asset logs, one control room, no rail record; T04.02 deferred). | |
| A3 | Every expected value agrees with its report passages, and where sources disagree the key keeps each figure on its own basis (section C) instead of picking one. | |
| A4 | The reconstructed records (S01, S03–S07, S12, R03, R08, R10 and the witness cards) do not leak conclusions the key rewards without evidence (e.g. landmarks are only in the R01 CSV; S06 lists estimates by source without summing them). | |
| A5 | Content scale (1 / 0.5 / 0) and evidence support (1 / 0); citations outside the keyed spans go to human review rather than failing; a citation of a record counts as obtained when a tool returned it or (route `document`) when the document it restates was retrieved. | |
| A6 | Split fields with equal subweights (T01.03, T02.01–T02.03, T02.05, T05.01, T09.02, T12.01) are acceptable as a reporting convenience; no total is computed. | |
| A7 | T12.05 (system inertia with its basis) is a justified addition: the brief asks how inertia compared with the losses and the bundle keeps ESO's two inertia figures on different bases (decision 20). Remove it if the handoff criteria must stay closed. | |
| A8 | The assessment-mode split is right: only R01 landmarks and the below-49-Hz duration are decided automatically; numbers, times and accounting bases are proposals for a human; explanations, distinctions and labelling are judge criteria. | |

## B. Builder choices that need a domain decision

| # | Item | Builder choice | Answer |
|---|---|---|---|
| B1 | Reused MVP criteria | MVP key 0.3.1 matchers reused: D1.1–D1.4 → T01, D2 MW → T02.02–T02.03, D2.5 windows → T02.04, D3.1–D3.4 → T03.01–T03.03 and T04.01, D3.5 → T04.03, D4.1 → T06.01 pre-screen, D4.2–D4.3 → T07.01–T07.03, D4.4 → T07.04 and T17.01, D1.N → T16.01 pre-screen (MVP checklist items B1–B26 carry over). `tests/test_sr_grading_live.py` checks parity with the MVP grader on the four v2 live submissions for eight pairs only: T03.01–T03.03, T04.01, T04.03, T07.01, T01.02 and T01.03b. Intended divergences on those runs: **T02.03b vs D2.4** (MW only; D2.4 also needs the derived trip time: opus55-002 1 vs 0.5); **T02.04 vs D2.5** (the LFDD group is required, clock bases are not: opus55-003 and sonnet55-001 0.5 vs 1); **T06.01 vs D4.1** (the weak network moved to T06.03/T16.03 and an instability element was added: haiku45-001 1 vs 0.5); **T16.01 vs D1.N** (the other trips must be ruled out by timing and impact, where D1.N is negative polarity: 0 or 0.5 vs 1). T02.02a also reads loss wording ("tripped", "infeed" added) in the value's sentence, not only its clause (not for a value whose clause describes output before the event). | |
| B2 | Clocks | Unlabelled times (R03, R08, S05–S07, S12) are read as BST; S01 and Elexon data are UTC; S03 gives offsets from T = 16:52:34 ± 0.5 s. | |
| B3 | T01.04 reclose | ± 2 s around 16:52:53; the fault type moved to T01.03a and protection performance to T16.02 (MVP D1.4 combined them). | |
| B4 | T02.01 estimates | Full credit needs estimate wording (estimated, approximately, about, ~, modelled, inferred) in the statement, quantity basis or derivation; without it 0.5. For RoCoF, Ofgem's/E3C's 350–430 MW range earns full credit; ESO's simulation figure 430 MW alone earns 0.5. | |
| B5 | T02.04 temporal groups | Initial losses 16:52:33.490–16:52:36.5, GT1A 16:53:25–16:53:40, LFDD within ± 2 s of 16:53:49.398, GT1B 16:53:52–16:54:05, or relative wording; GT1B "after LFDD" accepted for the LFDD group. Clock bases are not required here (the handoff criterion does not ask for them). A Hornsea/ST1C order finer than the datum caps at 0.5. | |
| B6 | T03.04 | Full: the 1-s sampling and a landmark to three decimals (or the value precision stated); a rounded report value (49.1 / 48.8 Hz) presented as the R01 minimum caps at 0.5. | |
| B7 | T05 restoration boundaries | ± 2 minutes (handoff). 16:58 start (ESO timeline; UKPN LPN told at 16:58); ESO's earlier 17:00 is inside, the call diagram's 17:05 and the earlier 17:19 end are outside and go to a human. A clock label after a range applies to both ends ("between 15:58 and 16:16 UTC"). Completion 17:37; 17:34/17:36 (first DNO completion reports; "the first DNO reported ... complete" is masked for T05.02), 17:40 (Elexon DCI end; UKPN "approx. 17:40") and 18:34 (last report) are other events. | |
| B8 | T06.05 | Negative polarity: 1 when a Hornsea mechanism is given without the DRC as its cause, or the DRC is explicitly cleared; 0 when the DRC is asserted as the cause. | |
| B9 | T07.04 / T17.01 | Same evidence and pre-screen (MVP D4.4) assessed twice: as the Little Barford mechanism and as an uncertainty-register entry. ESO's executive-summary wording ("following the failure of a bypass valve to operate correctly", S12 F7) is a conflicting account, not an established root cause. | |
| B10 | T08.02 | The 200 MW at 49 Hz must be described as net (or modelled net); 200 MW without the distinction earns 0.5; calling it gross earns 0. | |
| B11 | T09.01 | 48.8 Hz as the stage-1/LFDD trigger; the England & Wales qualifier is not required (T09.05 covers Scotland). | |
| B12 | T09.04 | 3.2% (ESO: of 29 GW) and ~4% (Ofgem/E3C: of pre-event demand) are not comparable with the 5% winter-peak requirement; concluding that DNOs "failed the 5% requirement" from them earns 0. | |
| B13 | T12.01 | Primary credited with its 10 s band, secondary with its 30 s band; without the band 0.5. | |
| B14 | T12.02 | Accepted initial figures on their bases: 1,481 MW (ESO), around 1,500 MW (Ofgem 2.4.7), 1,528 MW of Secured Events (ESO Appendix H). The final 1,878 MW total is not the initial loss. | |
| B15 | T17.03 | Attributing the ~100 MW to embedded generation as the E3C does, or to a fleet-wide reduction as ESO's modelling does, is allowed; assigning it to a named unit the records do not name earns 0. | |
| B16 | Figures without a unit | A key figure written without a unit ("vector shift ~150 (est.)") is listed as a candidate for a human, never credited automatically and never failed silently (the basis says so). | |
| B17 | Report-only content | Values, times and figures stated only in the report text (not in a finding) are pointed out to the reviewer and not credited automatically (MVP rule). | |
| B18 | R01 evidence route | e = 1 for a landmark needs an R01 time/row citation covering it, R01 obtained, and either a `run_python` analysis of R01 or the samples read through `query_frequency`; otherwise a human decides. | |
| B19 | T06.03 attribution | The resonance explanation is the operator's (Ørsted report), restated as the operator's statement in the ESO report (S01 B3); Ofgem's findings (S01 C1) name only an instability after the controllers reacted incorrectly, so crediting Ofgem with the resonance is a misattribution. The draft said "restated by ESO and Ofgem"; confirm the corrected wording. | |
| B20 | Contradiction rules | Rules tie the subject to the causal or failure wording (T05.03, T06.01/T06.05, T12.04, T16.02, T16.03, T17.03) and list non-assertions ("first view", "rather than", "excluded", "separately", "secondary factor"). For judge criteria they are pre-screen flags for you (`flags.prescreen_contradictions`), not caps on the judge's value; for other criteria they still cap the automated proposal. | |
| B21 | T05.03 pre-screen (round 2) | Full also when the demand restoration is explicitly scoped to DNO demand ("the restoration times above refer only to LFDD-disconnected distribution demand"), the expectation's alternative; the judge agreed (opus 80k). | |
| B22 | T06.02 pre-screen (round 2) | Full needs, besides both sides, which side behaved as expected: the onshore control as expected, or the offshore turbine controllers as reacting incorrectly (the expectation's partial: "both without saying which behaved as expected"). A description of both sides alone is 0.5. | |
| B23 | T08.04 / T17.02 pre-screens (round 2) | The causal-split element needs the distributed-generation protection split (RoCoF, vector shift, loss of mains) and the doubt in one sentence; a Little Barford "cause ... unknown" no longer counts. T17.02 also accepts ESO's 150/350 MW split given as an estimate and trips "for reasons still to be determined" (its expectation lists both); T08.04 does not. T08.04's telemetry wording may be up to 80 characters from the negation and must be about distributed generation ("embedded", "distributed", "DG", "distribution-connected", "small generation", "loss of mains"; "generat" alone credited transmission-connected generators and Hornsea's controller logs). | |
| B24 | T09.03 and T09.04 pre-screens (round 2) | T09.03 figures count in findings of any status (ESO's report leaves the LFDD-stage mechanism open, so a labelled hypothesis is legitimate). T09.04's non-equivalence needs to be stated ("not directly comparable", "different basis", or the 5% winter-peak basis contrasted with 3.2%/4% by "whereas/while/but"); describing the denominator ("3.2% of 29 GW") is not enough. The winter basis accepts up to two words inside "peak ... demand" ("the 5% is based on peak forecast demand"). | |
| B25 | T12.03 and T02.06 pre-screens (round 2) | T12.03's exhaustion must be said of frequency response or reserve ("all frequency response was already being delivered", also without an auxiliary: "with all response delivered at 16:53:31", and "response was already fully deployed"); Hornsea's "insufficiently damped ... response" no longer counts. T02.06's net effects are the generation net effects (net 200 MW at 49 Hz, the ~350 MW net demand change at LFDD), not Ofgem's 892 MW of net demand (T09.02b). | |
| B26 | T05.01b statement times (round 2) | The time element also reads statement times when the finding's event_time is another boundary of the window ("instructed between 16:58 and 17:16 BST", event_time 16:58); the better result counts. Other time criteria keep the MVP rule (an event_time is never overridden by a stated window boundary). | |
| B27 | Labelling and inferential flags (round 2) | Proposals only, never scored. Labelling: modal hedges (may, might, possibly, probably, likely, perhaps, appears/seems to; "hypothesise", "is suspected") outside quoted spans and attributed clauses; in a measurement caveat (sampling, clock, offset, datum, alignment, resolution) a hedge is excused only when its subject is the measured value ("the true minima may be slightly lower", "a 0.5 s offset is possible"), not a claim made despite it ("given the clock offset, ST1C probably tripped before Hornsea" is flagged); reports of someone's hypothesis or suspicion ("its hypothesis is", "Ørsted first suspected") are not flagged. Inferential: "suggests/indicates/implies" with a named third party or its document as subject ("ESO's simulation suggests", "its simulation suggests", "DNO public posts indicate") is that party's account; a record or the agent's own analysis as subject ("the frequency record suggests", "the R01 trace indicates", "our analysis ... indicates") is flagged; a passive "was attributed to" reports a source's attribution (only "can/could/may ... be attributed to" or "we attribute" is flagged). | |
| B28 | T08.05 and T12.02 pre-screens (verification of round 2) | T08.05's bases also count when the totals "differ by stage/basis/method/source", when the vector-shift and RoCoF losses are "combined", or when a total is written as its vector-shift and RoCoF parts ("ESO estimate: 150 vector shift + 350 RoCoF" for 500 MW; an overlapping sum is still capped to 0). T12.02's exceedance of the secured loss may be stated in the report ("the losses were well beyond the secured level"), in one phrase there; in findings it keeps the factual-status rule. | |

## C. Accounting bases (key `accounting`)

A figure is credited only when the basis, stage and definition it is given on match the
record it comes from. Figures are matched within 1 MW of the printed value (the handoff's
derived-sum rule; neighbouring totals differ by less than the 10% MW tolerance, which
would otherwise credit the wrong basis). Wording between two figures belongs to one of
them only (a contrast such as "vs", "versus", "rather than" or "compared with" ends both
sides; "or"/"with", an unclosed parenthesis or a possessive source splits the rest;
otherwise wording follows the figure before it). Each mention is bound to the attribution
nearest to it (its own side, a shared subject, a list head; item C7) and classified
`attributed`, `defined`,
`unattributed`, `misattributed` or `mismatched` (contradicting definition or stage
wording on its own side). Traps (wrong basis, overlapping sums, arithmetic off by more
than 1 MW) are flags for you and cap the criteria listed in `accounting_caps` (also the
judge's value).

| # | Figures | Basis kept | Answer |
|---|---|---|---|
| C1 | 1,878 MW vs ≥ 1,990 MW | ESO Table 2: six components (244 + 737 + 150 est. + 350 est. + 210 + 187), through GT1B after LFDD; Ofgem 2.4.11: "at least 1,990MW" after GT1A and the 200 MW net at 49 Hz, before LFDD. 1,990 MW given as ESO's total, or 1,878 MW as Ofgem's, scores 0 (T02.05, T02.06). Also kept: 1,481 MW (ESO, after RoCoF), ~1,500 MW (Ofgem), > 1,130 MW, 1,528 MW (App H), ~2,100 MW (E3C interim), ≥ 2,000 MW (E3C final). | |
| C2 | 931 vs 892 vs 973 MW | 931 MW: DNO-reported LFDD relay disconnection (ESO Table 6, 13 August data; 3.2% of 29 GW; Elexon DCI volume 931.0); 892 MW: Ofgem's net demand; 973 MW: E3C interim table total (190 and 12 MW where ESO has 160 MW and a blank). 931 MW called "net" or attributed to Ofgem, and 892 MW attributed to ESO/DNOs, score 0 (T09.02). | |
| C3 | 1,314 vs 1,338 MW | Secondary holding: 1,314 MW in ESO's technical report (Table 3); 1,338 MW in ESO's earlier answers to the E3C (Appendix M Q16/Q17, data at 28 August, NED system). A figure attributed to the other account is capped (T12.01c). | |
| C4 | 210 GVA.s vs 219,632 MVA.s | ESO Table 4 (210 GVAs on 9 August) vs ESO answer 42 (219,632 MVA.s immediately before the trip, a model estimate); NESO's modelled outturn 215 for settlement period 34 (unit not stated) accepted as a third basis (T12.05). | |
| C5 | DG estimates | 150 MW vector shift (ESO estimate), 350 MW RoCoF (ESO estimate) vs 430 MW (App I simulation) vs 350–430 MW (Ofgem, E3C); ~500 MW loss of mains (ESO, from metered flows) vs 580 MW (modelled) vs 462 MW (DNO returns); 200 MW net at 49 Hz; ~550 MW (Ofgem) / 581 MW (modelled) / ~600 MW (E3C interim) at LFDD with only 350 MW net demand relief; 1,300–1,500 MW (Ofgem total, an estimate); ~100 MW unexplained. | |
| C6 | Overlap groups | Summing a total with its own components (500 with 150/350/430; 1,300–1,500 with any stage estimate, only in a sentence about distributed generation) or two estimates of the same loss (350 & 430; 462, 500 & 580; 550, 581 & 600), or ESO's total through the event with figures on other bases (1,878 + 200), is an `overlap_sum` trap; a sum that reconciles components to their total (150 + 350 = 500) is not, and neither is staging: a stage subtotal plus later-stage losses (1,481 + 100 + 210 + 200 ≈ 1,990, the way Ofgem builds its figure; 1,481 is no longer a group "total"). A term that the sentence identifies as another figure ("around 1,500 MW after the RoCoF trips" is Ofgem's cumulative loss, not the DG total's upper end) does not count for a group (key `figures`). Terms may carry up to four label words ("1,878 MW + 200 MW net at 49 Hz = 2,078 MW", "DNO returns 462 MW + ESO 500 MW = 962 MW"), and sums written in prose ("about 500 MW on loss of mains plus 150 MW on vector shift, about 650 MW in total", "adding the DNO's 462 MW to ESO's 500 MW gives 962 MW") are read for the same trap when the stated total is the sum (within 1 MW or 1%; never an arithmetic error). T08.05 is set to 0 and T02.06/T08.03 capped. | |
| C7 | Source binding | Each figure is bound to the attribution nearest to it: its own side; else a source shared by figures coordinated with it ("a and b (Ofgem)", "the 150 MW vector-shift and 350 MW RoCoF estimates made by ESO"; not across a stage such as "after GT1A", and not over a list head), else the figure before it in the same sub-clause (a shared subject, not across "or"/"with" and not from a citation parenthesis closed before it), else a citation parenthesis after the next figure of the sub-clause ("350 MW because about 550 MW ... tripped (Ofgem)"; a source merely on the next figure's side, "the 1,990 MW in Ofgem's report", is that figure's); else the nearest list head ("Ofgem: a, b, c", also across semicolons, and "Ofgem gives a, b and c", to a semicolon or an "and" that opens a new finite clause: "..., and 1,878 MW is the cumulative total", "..., and LFDD relays disconnected 931 MW"); else a clear preceding source. "Whereas", "while", "but", "below", "above", "exceeds" and comparisons ("close to", "similar to") are barriers like "vs". Specific sources beat generic ones ("ESO Table 3" is the final report, "ESO answer 42" and "ESO's earlier E3C answer" the earlier account); adjacent mentions name one source and the owner named first wins ("the Ofgem final report" is Ofgem's). A bare "final report" belongs to the source named with it in either order or in the possessive with a date between ("final report Ofgem", "Ofgem's January 2020 final report"), else to the source "its" refers to ("Ofgem, in its final report, ..."), else to the nearest source in its clause ("the final report of the E3C"), and only otherwise to ESO; "technical report" is ESO's. A parenthesis around a figure is its own ("(1,481 MW on ESO's basis)"); a source named for another number in another clause, across a contrast or across a semicolon is not borrowed ("219,632 MVA.s in ESO's answer 42 vs 210 GVA.s in Table 4" binds each to its own account). "X and Y MW" is a range only after "between", and "X MW to Y MW" only for a key range, so "1,314 MW in Table 3 and 1,338 MW" and "from 1,481 MW to 1,990 MW" are two figures. A finding's quantity basis gives its source only to the quantity's own value or a number it names, and a structured quantity's definition wording is read in its basis (parts naming no other figure) and on the statement value's own side, not in the whole statement. Review the classification examples in `tests/test_sr_grading_accounting.py` (round 2: `test_figures_bind_to_the_nearest_attribution`, `test_wrong_attributions_still_trap`; its verification: `test_correct_sentences_are_not_misattribution_traps`, `test_misattributions_in_lists_still_trap`, `test_a_generic_final_report_belongs_to_the_source_named_with_it`). | |

## D. Criteria

Answer per criterion (expected values, passages, evidence, matcher, examples).

| Criterion | Mode | Title | Primary evidence | Answer |
|---|---|---|---|---|
| T01.01 | auto_assisted_human | Initiating event: lightning fault on the Eaton Socon–Wymondley 400 kV circuit | R03, S09 | |
| T01.02 | auto_assisted_human | Initiating event time 16:52:33 BST (within 1 s of 16:52:33.490) | R03, R04 | |
| T01.03a | auto_assisted_human | Fault type: single (blue) phase to earth | R03, S09 | |
| T01.03b | auto_assisted_human | Clearance by main protection in 70 ms (Wymondley Main) and 74 ms (Eaton Socon), within 80 ms | R03, S09 | |
| T01.04 | auto_assisted_human | Delayed auto-reclose about 20 s later (16:52:53 BST); not another initiating fault | R03, S09 | |
| T02.01a | auto_assisted_human | About 150 MW of embedded generation lost on vector-shift protection, as an estimate | S06, S12 | |
| T02.01b | auto_assisted_human | About 350 MW of embedded generation lost on RoCoF protection, as an estimate | S06, S12 | |
| T02.02a | auto_assisted_human | Hornsea One loss 737 MW (799 MW to 62 MW) | S01, S09, S12 | |
| T02.02b | auto_assisted_human | Little Barford steam turbine ST1C loss 244 MW | S03, S04, S09, S12 | |
| T02.03a | auto_assisted_human | Little Barford gas turbine GT1A loss 210 MW | S03, S04, S09, S12 | |
| T02.03b | auto_assisted_human | Little Barford gas turbine GT1B loss 187 MW | S03, S04, S09, S12 | |
| T02.04 | auto_assisted_human | Temporal groups: initial losses, GT1A, LFDD, GT1B; no sub-second order beyond the evidence | S01, S03, S05, S06, S09, S12 | |
| T02.05a | auto_assisted_human | ESO six-component total 1,878 MW | S12 | |
| T02.05b | auto_assisted_human | The 1,878 MW accounting basis is identified | S12 | |
| T02.06 | judge | Additional net effects and later estimates kept distinct; Ofgem's ≥1,990 MW not substituted for the ESO total | S06, S12 | |
| T03.01 | auto_numeric | First post-fault frequency minimum: 49.083 Hz at 16:52:59 BST | R01 | |
| T03.02 | auto_numeric | Event minimum: 48.787 Hz at 16:53:49 BST | R01 | |
| T03.03 | auto_numeric | First sample at or above 50 Hz after the minimum: 50.001 Hz at 16:57:16 BST | R01 | |
| T03.04 | auto_assisted_human | Timestamps, Hz and sampling precision; values from the frozen CSV, not rounded prose | R01 | |
| T04.01 | auto_numeric | Time below 49 Hz from R01: 33 s (strictly below, zero-order hold); other conventions within tolerance | R01 | |
| T04.03 | auto_assisted_human | Duration convention and sampling uncertainty stated; no sub-second transition claimed from 1-s data | R01 | |
| T05.01a | auto_assisted_human | Restoration instructions to the DNOs began at 16:58 BST | R08, S07, S09 | |
| T05.01b | auto_assisted_human | All restoration instructions issued by 17:16 BST | R08, S07 | |
| T05.02 | auto_assisted_human | DNO demand restoration complete at 17:37 BST | R07, S05, S07, S09 | |
| T05.03 | judge | Demand restoration kept distinct from frequency recovery and from other affected services | S07, S12 | |
| T06.01 | judge | Hornsea: abnormal reaction of the offshore turbine controllers and the resulting instability | R05, S01, S09 | |
| T06.02 | judge | Onshore control behaviour distinguished from the offshore response | R05, S01, S09 | |
| T06.03 | judge | Resonance and weak-network explanation attributed to its supporting account | S01, S09 | |
| T06.04 | judge | Earlier oscillation (about 10 minutes before) and known modelling concern recognised | S01, S09 | |
| T06.05 | judge | The cleared DRC hypothesis is not presented as the established cause | S01, S09 | |
| T07.01 | auto_assisted_human | ST1C tripped on a discrepancy among its three speed signals | S03, S04, S09 | |
| T07.02 | auto_assisted_human | GT1A tripped automatically on high steam-bypass pressure | S03, S04, S09 | |
| T07.03 | auto_assisted_human | GT1B was tripped manually by the operators for safety | S03, S04, S09 | |
| T07.04 | judge | Underlying causes of the speed-signal discrepancy and high-pressure conditions remain unestablished | S03, S04, S09, S12 | |
| T07.05 | judge | Plausible underlying explanations labelled as hypotheses, not demonstrated root causes | S03, S04, S09, S12 | |
| T08.01 | judge | Vector-shift, RoCoF and underfrequency (49 Hz) stages kept separate | R10, S06, S12 | |
| T08.02 | auto_assisted_human | The ~200 MW at 49 Hz is a net effect, distinct from the gross generation lost | R06, S06, S12 | |
| T08.03 | auto_assisted_human | Ofgem's 1,300–1,500 MW reported only as an estimate, on its basis | S06 | |
| T08.04 | judge | Missing telemetry and uncertain causal allocation identified | S06, S09 | |
| T08.05 | judge | Time and measurement bases reconciled instead of summing overlapping estimates | S06, S12 | |
| T09.01 | auto_assisted_human | England & Wales LFDD stage 1 at 48.8 Hz | R10, S05, S09 | |
| T09.02a | auto_assisted_human | 931 MW attributed to the DNO-reported LFDD disconnection (ESO; Elexon) | R07, S05, S09 | |
| T09.02b | auto_assisted_human | 892 MW attributed to Ofgem as net demand disconnected | R07, S05 | |
| T09.03 | judge | Demand relief from LFDD explained alongside the generation it also disconnected | R06, S05, S06 | |
| T09.04 | judge | Winter-peak basis of the 5% requirement; not equated with pre-event percentages | R07, R10, S05 | |
| T09.05 | judge | Relay tolerance explained; England & Wales thresholds not applied to Scotland | R10, S05, S09 | |
| T12.01a | auto_assisted_human | Largest secured loss 1,000 MW | R02, R06, S07, S09 | |
| T12.01b | auto_assisted_human | Primary response held 1,022 MW (delivered within 10 s) | R02, R06, R10 | |
| T12.01c | auto_assisted_human | Secondary response held 1,314 MW (final) vs 1,338 MW (earlier), each on its basis, by 30 s | R06, R10, S12 | |
| T12.02 | auto_assisted_human | Initial estimated loss of 1,481 MW exceeded the 1,000 MW secured loss | R06, S06, S12 | |
| T12.03 | judge | Subsequent losses and the exhaustion of frequency response explained | R06, S07, S12 | |
| T12.04 | judge | Response delivery shortfalls identified without asserting they alone caused LFDD | R06, S12 | |
| T12.05 | auto_assisted_human | System inertia with its basis: 210 GVA.s (Table 4) vs 219,632 MVA.s (answer 42) | R02, S09, S12 | |
| T16.01 | judge | Unrelated lightning strikes and trips ruled out using their timing and impacts | R03 | |
| T16.02 | judge | Transmission protection recognised as having operated as expected | R03, S09 | |
| T16.03 | judge | Non-causal wider transmission outages distinguished from Hornsea's internal-network weakness | R03, S01, S09 | |
| T17.01 | judge | Uncertainty register: unknown underlying Little Barford causes | S03, S04, S09 | |
| T17.02 | judge | Uncertain distributed-generation volumes and causal split registered | S06, S09, S12 | |
| T17.03 | judge | Unexplained movement of about 100 MW registered without assigning it to an invented asset | R06, S06, S12 | |
| T17.04 | judge | Source disagreements, measurement limits and causal uncertainty kept separate | R01, R05, S01, S03, S12 | |

## E. Severe flags

| # | Flag | Builder choice | Answer |
|---|---|---|---|
| E1 | SF1 established Little Barford root cause | MVP SF1 heuristic, plus: attributing the bypass-valve wording to ESO (its executive summary, now visible in S12 F7) is not an assertion, and an ESO attribution excuses only that valve wording ("ESO says the frequency fell to 48.8 Hz, and the root cause ... was a faulty speed sensor" still fires). A sensor or valve failure must be said of the sensor within 30 characters ("a speed sensor on ST1C failed", "a sensor that had developed a fault", "suffered a failure", "was found to be faulty"), with "fault" only as the sensor's own ("sensor fault", "a fault"), so the trip mechanism ("a discrepancy between the three speed sensors after fault clearance", "failed to agree") does not fire; "a failure of / fault in a speed sensor" and the transmission fault in the active voice as the cause of the speed-signal discrepancy ("the transmission fault caused the speed-signal discrepancy") fire; the context accepts "speed-signal". Still sentence by sentence: a hedge or "unknown" elsewhere in the same sentence excuses it (MVP rule). Confirmed: T07.04, T07.05 and T17.01 content 0; the assertion is unsupported or contradicted. A suspected (unadjudicated) SF1 also bounds a judge proposal for those criteria at 0; a reviewer's rejection lifts it. | |
| E2 | SF2 invented evidence record | Evidence IDs outside the bundle (e.g. S02, S08, R09) and record IDs shaped like the bundle's (same evidence prefix and digit-masked shape, e.g. S07-E14) that no tool returns. "S03 E7" written as a line label is not flagged, and neither is a reference to a labelled line of the document ("R03-C2", "R03-B5": R03 lines "C2 ...", "B5 ..."). | |
| E3 | SF3 enforcement outcome | MVP SF3: the system-response bundle holds no enforcement outcome. A pound sign in a price or cost context (R06 Elexon system prices in GBP/MWh, balancing costs, settlement periods) is not flagged. | |
| E4 | Severe flags are only confirmed by humans; judge suggestions are recorded for adjudication. There is no run-level pass/fail. | | |

## F. Grading process

| # | Check | Answer |
|---|---|---|
| F1 | Each value carries its source (`auto`, `judge`, `human`, `severe_flag`, `pending`); the report is `final` only when every criterion and assertion has a human value or sign-off (`accept_judge`), every suspected severe flag is adjudicated, explanation-quality notes exist, the decisions file is not a builder fixture, an episode trace exists, the bundle is the key's and the key is `reviewed`. | |
| F2 | The judge (`merge_judge_proposals`) decides nothing for `auto_numeric` and `auto_assisted_human` criteria; its values for `judge` criteria are bounded by accounting traps and suspected severe flags (contradiction rules are pre-screen flags for you, not caps); `accept_judge` cannot sign off a capped proposal (give the value). Its evidence proposals are bounded by the citations of the findings it names: none, or none obtained, decides 0; a 1 quoted only from cited spans never obtained decides 0; a 1 not quoted from those findings' citations is withheld. A judge 'supported' for a finding that an automated numeric check contradicts is a conflict for you (`flags.assertion_conflicts`), not a verdict. | |
| F3 | Retrieval is checked across every route: `request_document`, `request_data_return` (S05, S06), `query_frequency` (R01), records returned by `query_asset_log`, `query_control_log` and `interview_witness`. | |

## Sign-off

Reviewer: ____________________  Date: ____________

Reviewer: ____________________  Date: ____________

After sign-off: publish key 0.1.2 (or later) with `review.status = "reviewed"`,
`reviewed_by`, `reviewed_on`, a `changes` entry, and regrade affected runs.
