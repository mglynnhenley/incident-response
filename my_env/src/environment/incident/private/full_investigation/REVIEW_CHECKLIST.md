# Domain review checklist — full-investigation answer key, GB 9 August 2019

Key file: `answer_key.json` (this directory), key schema `gb2019-fi-answer-key/1`.
Key version under review: **0.1.1** (grader `fi_grading` 0.1.1, building on
`sr_grading` 0.1.1), bound to the full-investigation evidence bundle
**0.1.0** (`bundle.bundle_sha256` in the key; a test checks it against the installed
bundle). Task: `gb-2019-full-investigation` (increment B: the whole incident, T01–T20).
Grader: `environment/incident/fi_grading.py` with the element types of
`environment/incident/fi_elements.py`; increment A's grader (`sr_grading.py`,
`sr_accounting.py`) does the grading. Builder: `.context/fi_key_builder/` (rebuilds the
key byte for byte; a test checks it).

Current status: **pending_domain_review**. Until a domain reviewer signs this sheet and a
new key version with `review.status = "reviewed"` (and the top-level `review_status`
mirror) is published, every grade produced with this key is **provisional** and results
must not be described as validated. A changed key needs new grading decisions (they are
bound to the key's sha256) and a regrade of every affected run.

The key has 106 criteria: increment A's 60 (key 0.1.1, same IDs, re-bound to this
bundle) and 46 new criteria for T04.02, T10, T11, T13, T14, T15, T18, T19 and T20
(17 auto_assisted_human, 29 judge). No handoff criterion is deferred. Adaptations from the handoff (contract
`.context/increment_B_design.md`): no enforcement outcome is required or supplied (Ofgem's
January 2020 settlements are excluded from the evidence, decision 50; asserting them is
SF3); no legal clause recall is scored; T18 is judged on linkage to established findings,
owner and verification method, with equivalent actions accepted; T19 asks who should
supply what, without ESQCR duties or OC7/OC10 obligations beyond the recorded SIR request
(S07 K3); T20 is the executive summary (at most
600 words, enforced by the submission validator) judged on accuracy, attribution,
prioritisation and calibrated certainty.

## How to review

As for increment A's key (`../system_response/REVIEW_CHECKLIST.md`, "How to review"): for
each criterion read `handoff_text`, `expectation`, `expected`, `tolerances`, the
`report_passages` (verbatim quotes verified by a test on the stated PDF page), the
`visible_evidence` (locators the agent can see, with tokens a test confirms; `primary`
spans support the fact, `context` spans do not earn an evidence proposal), the
`assessment_mode` (`auto_numeric`, `auto_assisted_human`: the grader proposes and a human
decides; `judge`: the LLM judge proposes, bounded by automated caps, and a human signs
off), the `auto` rules (for judge criteria a pre-screen shown to you, never to the
judge) and the `examples` (`content` is the value the key expects, `prescreen` the
pre-screen of a judge criterion; tests check both). Re-bound criteria carry `rebinding`
(`changed` false: identical to increment A's criterion). New element types (key
`conventions.fi_element_types`): `count` (exact integers bound to wording in their own
clause), `summary_text` and `summary_words` (the executive summary), `section_text`
(report sections by heading, e.g. Recommendations, and findings that state
recommendations or requests).

Record your answer to every item: **OK**, **Change** (say what), or **Remove**.

## A. Whole key

| # | Check | Answer |
|---|---|---|
| A1 | The 20 tasks and 106 criteria are a fair implementation of the handoff criteria T01–T20 with the adaptations above; split fields (suffix a, b, c) have equal subweights as a reporting convenience only. | |
| A2 | Nothing is required that the bundle cannot support: no train-level running records, no TCMS logs, no airport/water/refinery logs, no compliance test reports (all fixed not-held data returns); the criteria use only the published accounts the bundle restates. | |
| A3 | Every expected value agrees with its report passages, and where sources disagree the key keeps each figure with its source (ORR vs GTR rail counts; 17:51 vs 18:00; 17:40 vs 17:41). | |
| A4 | No criterion requires or supplies an enforcement outcome or a legal clause; clause numbers in S10/R10 appear only as Ofgem cites them and are never scored. | |
| A5 | The re-bound criteria: increment A's 60 criteria are unchanged except T04.03, T05.02 and T05.03 (items B1 and B16) and the pre-screen rules of T02.04, T05.03, T06.02, T08.04, T08.05 and T09.05 (key 0.1.1, item B19: expectations, examples and keyed spans unchanged); on increment A's six real submissions the re-bound criteria give increment A's automated results except the differences that test lists and explains (tests/test_fi_grading_live_runs.py). | |
| A6 | Grades stay provisional (no total, threshold or ranking); content coverage, evidence support and assertion quality are separate measures, as in increment A. | |

## B. Builder choices that need a domain decision

| # | Choice | Answer |
|---|---|---|
| B1 | T04.03 and T05.03 return to the handoff wording. Increment A had adapted them only because the rail evidence was deferred. T04.03's rules are unchanged (its contradiction rule already caps "within 200 ms" claimed from 1-s data); S08 spans are context only. T05.03 gains a `transport_later` pre-screen route and the rail-recovery records (full rail service within 24 hours, ORR; disruption into Saturday morning, ESO); increment A's positive example ("not covered by these records") is replaced. The Victoria line's resumption at 17:35 (S11 P03) is not a later recovery: its suspension came from an internal traction issue, not LFDD, and it resumed before the 17:37 completion. It is a context span, and T05.03's contradiction excuses it. | |
| B2 | T04.02 is `auto_assisted_human` (values plus attribution), not `judge`: full needs 49 Hz, 200 ms and attribution to the rail accounts or status `reported`. A 48.5/48.8 Hz trip setting caps it at 0.5. | |
| B3 | T10.02 counts are ORR's (29/22/7). GTR's and the ESO's counts (circa 60 units, about 30 needing a technician, 27 or 28 recovered by drivers; ORR's own conclusion: 30 needing a technician) earn 0.5 only when attributed in the same sentence to a source that reports them: 60 to GTR, the ESO or the E3C/DfT; 30 to GTR, the ESO or ORR's conclusion; 27 and 28 to GTR only. They count units, not trains, or come from another stage of the reports. An alternative given to a source that does not report it (e.g. "ORR reports about 60") is misattributed and earns nothing; it and an unattributed alternative are listed for the reviewer in the basis, never credited. An alternative's evidence proposal is checked against its own source's spans (the expected count's spans count as context for it). | |
| B4 | T10.03 is split: 31 stranded (exact) and the two Class 387s trapped indirectly; a Class 387 said to have shut down itself is a contradiction (GTR: no other AC class had power issues). The 31 may be given as its parts in one sentence (29 stranded, or locked out, and two Class 387s trapped: full; key 0.1.1 reads "29 trains locked out ... plus 2 trapped Class 387s", the expectation's own decomposition). Ofgem's 29 "became stranded" (without the Class 387s) and ORR's conclusion's 30 "effectively stranded" earn 0.5 when attributed to their source. | |
| B5 | T10.05 is split into (a) 371 cancelled and 220 part-cancelled, (b) 873 trains delayed and 14,428 delay minutes (ORR Table 1 total), each figure only in its own measure, and (c) inconsistent counts attributed (judge; full needs at least two differences with their sources). | |
| B6 | T11.01 is split into the airport (LFDD, NPG) and Ipswich Hospital (own protection; not in UKPN's LFDD zone). T11.03 (water and refinery) is a judge criterion; its pre-screen caps an LFDD mechanism for the refinery (zero) and the 12 September 2019 Stanlow article presented as a 9 August impact (half). | |
| B7 | T14.03 is `auto_assisted_human`: full needs EPN/SPN's reconnection without the ESO's instruction and the instruction requirement; the requirement alone is 0; the early reconnection given to another DNO (e.g. SP Distribution, which reconnected without informing the ESO) is a contradiction. | |
| B8 | SF3's confirmed effect zeroes T14.04 and T14.05; SF1's also zeroes T14.02 (in addition to increment A's T07.04, T07.05, T17.01). | |
| B9 | T15.01 is split: (a) the first BEIS contact in 17:40–17:41 BST (the two records; no tolerance beyond them), (b) the first public statement at 18:27 ±60 s (half for about 18:30, the website statement titled "6.30pm"), (c) the contact sequence (judge). Comms tolerances are builder choices: the handoff gives none. | |
| B10 | T15.02: full needs both 17:51 and 18:00 for the first Ofgem contact; half one time attributed to its record by name (section 6.2 / section 7 / Appendix M / R09 entries); one time as the fact is 0. | |
| B11 | T15.03 (Hornsea's notification and restart coordination, Ofgem 3.23) is `auto_assisted_human`; T15.04 (delay and attribution issues, not causes) is `judge` with a contradiction for communications presented as a cause of the outage. | |
| B12 | T13 (contributing factors), T18 (recommendations), T19 (evidence requests and escalation) and T20 (the executive summary) are all `judge` criteria. Their pre-screens read the Recommendations / evidence-request sections by heading and findings that state recommendations or requests, and the executive summary; official recommendations (ESO section 8, Ofgem, E3C actions, ORR section 5) are report passages as examples only: equivalent justified actions are accepted. | |
| B13 | T19.02 caps at 0.5 an ESQCR duty or an OC7/OC10 obligation asserted as applying beyond what the evidence records (not supplied or verified); stating that they are not in the evidence is fine. The evidence does record the DNOs' first Significant Incident Report (SIR) request under Grid Code OC7 and OC10 at 17:23 (S07 K3, ESO-ENCC entry S07-K3): citing that request is not an unverified obligation, and it is a keyed span. | |
| B14 | T20.06: the 600-word limit is automatic (the validator rejects longer summaries, so this is a guard); the pre-screen also needs at least one finding reference and no unqualified certainty wording ("proves", "definitively", "the root cause was"). | |
| B15 | Interpretive criteria accept clause numbers when quoted as Ofgem cites them (e.g. "contrary to OC6.6.4 as Ofgem cites it") but never require them. | |
| B16 | T05.02 (re-bound) diverges from increment A's frozen key: its completion wording also reads "restored/reconnected/back by <time>" (the first full-investigation pilot wrote "Disconnected demand was restored by 17:37 BST" and got a silent 0). | |
| B17 | Findings that the executive summary or a report section only refers to are the summary criteria's findings for evidence support, but they keep the dimension of the topic whose criteria match their own content; a T20 or T18 dimension is used only when no other topic matches the finding (a finding that states a recommendation itself routes to T18). | |
| B19 | Key 0.1.1 corrections from the two real runs (decisions 77-80; each read against the submission, the keyed evidence and, for judge criteria, the judge's proposal): T02.04's SOE offsets read "<n> s after datum T" (re-bound, rules only); T10.03a's 29 may be worded "locked out" with the two Class 387s trapped in its sentence (B4); T11.03's refinery needs its own mechanism in its sentence ("took weeks" alone no longer counts); T05.03 gains `demand_vs_services` (demand restoration said in one sentence to be separate from the other services' recovery; with `transport_later` a full route); T06.02's offshore side reads the turbines' overcurrent protection; T08.04 no longer reads a measurement limit ("1-s data cannot resolve RoCoF") as the causal split and reads "could not split it by cause"; T08.05 reads a total that "includes about <figure>"; T09.05 reads "wrong setting"; T14.02's full needs the requirement (`lb_requirement`; "RWE acknowledges it contributed" alone is partial, as the expectation says); T14.05 no longer reads Ofgem's "found no evidence that the ESO breached the Grid Code" as missing proof and gains a partial route (`records_missing`: plant, controller, switching or relay records not held; tests outstanding); T15.01c's full also needs the 17:10 internal escalation (the expectation's full); T20.03 reads "unestablished" and "unidentified". | |
| B20 | The `figure` element of this key also reads a finding labelled `unknown` when the figure's own clause (cut at ";", ":" and sentence ends) states no uncertainty or hedge (decision 18's rule for mechanisms): the real panel run's F11 registers unknown causes and reports Ofgem's 1,300-1,500 MW (estimated) and a net 200 MW at 49 Hz. A figure in a finding labelled `hypothesis`, or in an unknown-labelled clause with uncertainty wording, is listed for you, never credited. | |
| B21 | Labelling flags (proposals, never scored) spare hedge words that are no hedge (`conventions.labelling_exempt`): "as soon as possible", "where possible", and a prohibition "may not restore ... without ESO instruction". "May not have" / "may only have" is epistemic and still flagged ("UKPN may not have restored demand without ESO instruction"; decision 81). | |
| B18 | T15.01a and T15.01b read a time only from its own clause (`clause_time`): the BEIS contact's clause names BEIS and the contact, the first statement's clause names the first or initial statement, and a restoration time ("all demand reconnected by 17:40", "restored by 18:30") is never read as either. T15.02's 18:00 must be the Ofgem contact's (in a clause with Ofgem or contact wording, or attributed to section 7 / Appendix M / question 34). | |

## C. Accounting bases (key `accounting`)

Increment A's key 0.1.1 (see `../system_response/REVIEW_CHECKLIST.md`, section C, and
decisions 33, 41 and 46) with three additions in key 0.1.1 (decision 77). The new criteria
use count elements, not accounting figures: rail counts are attributed by the `count`
element's alternatives.

| # | Check | Answer |
|---|---|---|
| C1 | Increment A's accounting figures, overlap groups and caps apply to the full investigation, with C2-C4. | |
| C2 | `binding_options.basis_components`: a structured quantity whose basis gives the value's own terms ("ESO estimate from transformer-flow changes (150 VS + 350 RoCoF)" for 500 MW) is bound to the source the basis names. Increment A's rule skipped any basis part holding another key figure's number and fell back to the statement's only source (the real panel run's F10: the DNOs of the next sentence, a false misattribution trap). | |
| C3 | DG_LOM_500 and DG_LOM_580 (the loss-of-mains totals, vector shift and RoCoF together) are mismatched when given as one mechanism's loss ("ESO reported 580 MW of DG lost to vector shift"); "lost to vector shift and RoCoF" is not (`mismatch_unless_any`, read on the figure's own side and the words directly coordinated with its end, never elsewhere in the sentence: "580 MW lost to vector shift, compared with 500 MW for vector shift and RoCoF" is mismatched; decision 81). DG_LOM_500's context also reads "embedded generation was lost". | |
| C4 | An inertia unit (GVA.s, MVA.s) is the inertia figures' context: "The ESO final report gives 210 GVA.s. Its earlier answer gives 219,632 MVA.s" (the real panel run's F19, after a sentence on inertia) is read. | |

## D. Criteria

`R` = re-bound from increment A (unchanged unless marked "changed"), `N` = new.

| ID | Mode | Title | Origin | Keyed evidence | Answer |
|---|---|---|---|---|---|
| T01.01 | auto_assisted_human | Initiating event: lightning fault on the Eaton Socon–Wymondley 400 kV circuit | R | R03, S09 | |
| T01.02 | auto_assisted_human | Initiating event time 16:52:33 BST (within 1 s of 16:52:33.490) | R | R03, R04 | |
| T01.03a | auto_assisted_human | Fault type: single (blue) phase to earth | R | R03, S09 | |
| T01.03b | auto_assisted_human | Clearance by main protection in 70 ms (Wymondley Main) and 74 ms (Eaton Socon), within 80 ms | R | R03, S09 | |
| T01.04 | auto_assisted_human | Delayed auto-reclose about 20 s later (16:52:53 BST); not another initiating fault | R | R03, S09 | |
| T02.01a | auto_assisted_human | About 150 MW of embedded generation lost on vector-shift protection, as an estimate | R | S06, S12 | |
| T02.01b | auto_assisted_human | About 350 MW of embedded generation lost on RoCoF protection, as an estimate | R | S06, S12 | |
| T02.02a | auto_assisted_human | Hornsea One loss 737 MW (799 MW to 62 MW) | R | S01, S09, S12 | |
| T02.02b | auto_assisted_human | Little Barford steam turbine ST1C loss 244 MW | R | S03, S04, S09, S12 | |
| T02.03a | auto_assisted_human | Little Barford gas turbine GT1A loss 210 MW | R | S03, S04, S09, S12 | |
| T02.03b | auto_assisted_human | Little Barford gas turbine GT1B loss 187 MW | R | S03, S04, S09, S12 | |
| T02.04 | auto_assisted_human | Temporal groups: initial losses, GT1A, LFDD, GT1B; no sub-second order beyond the evidence | R changed | S01, S03, S05, S06, S09, S12 | |
| T02.05a | auto_assisted_human | ESO six-component total 1,878 MW | R | S12 | |
| T02.05b | auto_assisted_human | The 1,878 MW accounting basis is identified (ESO cumulative infeed loss, six components incl. two DG estimates, through GT1B) | R | S12 | |
| T02.06 | judge | Additional net effects and later estimates kept distinct; Ofgem's ≥1,990 MW not substituted for the ESO total | R | S06, S12 | |
| T03.01 | auto_numeric | First post-fault frequency minimum: 49.083 Hz at 16:52:59 BST (lowest 1-s sample in 16:52:45–16:53:10) | R | R01 | |
| T03.02 | auto_numeric | Event minimum: 48.787 Hz at 16:53:49 BST (lowest sample in 16:53:20–16:54:30) | R | R01 | |
| T03.03 | auto_numeric | First sample at or above 50 Hz after the minimum: 50.001 Hz at 16:57:16 BST | R | R01 | |
| T03.04 | auto_assisted_human | Timestamps, Hz and sampling precision reported; landmark values from the frozen CSV, not rounded prose | R | R01 | |
| T04.01 | auto_numeric | Time below 49 Hz from R01: 33 s (strictly below, zero-order hold); other stated conventions within tolerance | R | R01 | |
| T04.02 | auto_assisted_human | Rail protection: Class 700/717 drives disconnect when the supply falls below 49 Hz, within 200 ms, as a reported design fact | N handoff | R10, S08, S09 | |
| T04.03 | auto_assisted_human | Duration convention and sampling uncertainty stated; no sub-second transition claimed from 1-s data | R changed | R01 | |
| T05.01a | auto_assisted_human | Restoration instructions to the DNOs began at 16:58 BST | R | R08, S07, S09 | |
| T05.01b | auto_assisted_human | All restoration instructions issued by 17:16 BST | R | R08, S07 | |
| T05.02 | auto_assisted_human | DNO demand restoration complete at 17:37 BST | R changed | R07, S05, S07, S09 | |
| T05.03 | judge | Demand restoration kept distinct from frequency recovery and from the later recovery of transport and other affected services | R changed | S07, S08, S09, S12 | |
| T06.01 | judge | Hornsea: abnormal reaction of the offshore turbine controllers and the resulting instability | R | R05, S01, S09 | |
| T06.02 | judge | Onshore control behaviour distinguished from the offshore response | R changed | R05, S01, S09 | |
| T06.03 | judge | Resonance and weak-network explanation attributed to its supporting account | R | S01, S09 | |
| T06.04 | judge | Earlier oscillation (about 10 minutes before) and known modelling concern recognised | R | S01, S09 | |
| T06.05 | judge | The cleared DRC hypothesis is not presented as the established cause | R | S01, S09 | |
| T07.01 | auto_assisted_human | ST1C tripped on a discrepancy among its three speed signals | R | S03, S04, S09 | |
| T07.02 | auto_assisted_human | GT1A tripped automatically on high steam-bypass pressure | R | S03, S04, S09 | |
| T07.03 | auto_assisted_human | GT1B was tripped manually by the operators for safety (excessive steam pressure) | R | S03, S04, S09 | |
| T07.04 | judge | Underlying causes of the speed-signal discrepancy and the high-pressure conditions remain unestablished | R | S03, S04, S09, S12 | |
| T07.05 | judge | Plausible underlying explanations labelled as hypotheses, not demonstrated root causes | R | S03, S04, S09, S12 | |
| T08.01 | judge | Vector-shift, RoCoF and underfrequency (49 Hz) stages of distributed-generation loss kept separate | R | R10, S06, S12 | |
| T08.02 | auto_assisted_human | The ~200 MW at 49 Hz is a net effect, distinct from the gross generation lost | R | R06, S06, S12 | |
| T08.03 | auto_assisted_human | Ofgem's 1,300–1,500 MW total distributed-generation loss reported only as an estimate, on its basis | R | S06 | |
| T08.04 | judge | Missing telemetry and uncertain causal allocation of distributed-generation losses identified | R changed | S06, S09 | |
| T08.05 | judge | Time and measurement bases reconciled instead of summing overlapping estimates | R changed | S06, S12 | |
| T09.01 | auto_assisted_human | England & Wales LFDD stage 1 at 48.8 Hz | R | R10, S05, S09 | |
| T09.02a | auto_assisted_human | 931 MW attributed to the DNO-reported LFDD disconnection (ESO; Elexon demand control record) | R | R07, S05, S09 | |
| T09.02b | auto_assisted_human | 892 MW attributed to Ofgem as net demand disconnected | R | R07, S05 | |
| T09.03 | judge | Demand relief from LFDD explained alongside the generation it also disconnected | R | R06, S05, S06 | |
| T09.04 | judge | Winter-peak basis of the 5% stage-1 requirement; not equated with the pre-event percentages | R | R07, R10, S05 | |
| T09.05 | judge | Relay tolerance explained; England & Wales thresholds not applied to Scotland | R changed | R10, S05, S09 | |
| T10.01 | judge | Trains stopped by their own on-board protection although the traction supply was generally maintained | N handoff | S08, S09, S11 | |
| T10.02a | auto_assisted_human | 29 Class 700/717 trains locked out (ORR) | N handoff_split | S08, S09 | |
| T10.02b | auto_assisted_human | 22 trains permanently locked out, needing a technician (ORR) | N handoff_split | S08, S09 | |
| T10.02c | auto_assisted_human | 7 trains restored by driver reset (ORR) | N handoff_split | S08, S09 | |
| T10.03a | auto_assisted_human | 31 trains stranded (ORR) | N handoff_split | S08 | |
| T10.03b | auto_assisted_human | Two Class 387 trains trapped indirectly by the locked-out units | N handoff_split | S08, S09 | |
| T10.04 | auto_assisted_human | Software 3.25.x units went into a temporary lock-out drivers could reset; 3.27.x units into a permanent lock-out needing a technician | N handoff | S08, S09 | |
| T10.05a | auto_assisted_human | 371 trains cancelled and 220 part-cancelled, kept distinct | N handoff_split | S08, S09 | |
| T10.05b | auto_assisted_human | 873 trains delayed (ESO, E3C) kept distinct from 14,428 delay minutes (ORR Table 1) | N handoff_split | S08, S09 | |
| T10.05c | judge | Inconsistent rail counts attributed to their reports | N handoff_split | S08, S09 | |
| T11.01a | auto_assisted_human | Newcastle Airport disconnected by LFDD (Northern Powergrid) | N handoff_split | S11 | |
| T11.01b | auto_assisted_human | Ipswich Hospital lost supply through its own protection, not LFDD | N handoff_split | R12, S09, S11 | |
| T11.02 | auto_assisted_human | Wirral line (Merseyrail) traction supply lost through LFDD | N handoff | R11, S09, S11 | |
| T11.03 | judge | Water and refinery impacts described as supplied, without invented mechanisms | N handoff | S11 | |
| T12.01a | auto_assisted_human | Largest secured loss 1,000 MW | R | R02, R06, S07, S09 | |
| T12.01b | auto_assisted_human | Primary response held 1,022 MW (delivered within 10 s) | R | R02, R06, R10 | |
| T12.01c | auto_assisted_human | Secondary response held: 1,314 MW (ESO final report) vs 1,338 MW (ESO's earlier answers), each on its basis, delivered by 30 s | R | R06, R10, S12 | |
| T12.02 | auto_assisted_human | Initial estimated loss of 1,481 MW exceeded the 1,000 MW secured loss | R | R06, S06, S12 | |
| T12.03 | judge | Subsequent losses and the exhaustion of frequency response explained | R | R06, S07, S12 | |
| T12.04 | judge | Response delivery shortfalls identified without asserting they alone caused LFDD | R | R06, S12 | |
| T12.05 | auto_assisted_human | System inertia reported with its basis: 210 GVA.s (ESO Table 4) vs 219,632 MVA.s (ESO answer 42), both model estimates | R | R02, S09, S12 | |
| T13.01 | judge | Contributing factor: distributed-generation protection settings and the lack of visibility of distributed generation | N handoff | R10, S06, S10, S12 | |
| T13.02 | judge | Contributing factor: weaknesses in compliance evidence and testing, and in information sharing | N handoff | S10 | |
| T13.03 | judge | Contributing factor: reserve and inertia assumptions and response delivery | N handoff | R10, S12 | |
| T13.04 | judge | Contributing factor: LFDD's interaction with distributed generation and essential services | N handoff | R10, S10, S11 | |
| T13.05 | judge | Contributing factor: rail protection settings and recovery arrangements | N handoff | S08, S09 | |
| T13.06 | judge | Triggering, contributing and systemic factors kept separate, each supported | N handoff | R03, S10, S11, S12 | |
| T14.01 | judge | Hornsea One: fault ride-through and damping concerns, supported by the requirements in the evidence | N handoff | R10, S10 | |
| T14.02 | judge | Little Barford's contribution stated without inventing an established underlying fault | N handoff | R10, S04, S10 | |
| T14.03 | auto_assisted_human | EPN and SPN reconnected demand without the ESO's instruction, against the instruction requirement | N handoff | R10, S09, S10 | |
| T14.04 | judge | Process concerns kept distinct from demonstrated breach and from outcomes | N handoff | R09, S08, S10 | |
| T14.05 | judge | No invented settlements or legal findings; the missing proof is identified | N handoff | S04, S10 | |
| T15.01a | auto_assisted_human | First ESO contact with BEIS at 17:40-17:41 BST | N handoff_split | R09, S09 | |
| T15.01b | auto_assisted_human | First ESO public statement at 18:27 BST | N handoff_split | R09, S09 | |
| T15.01c | judge | Sequence of government, regulator and public contacts reconstructed from the records | N handoff_split | R09, S09 | |
| T15.02 | auto_assisted_human | The 17:51 vs 18:00 discrepancy for the first Ofgem contact kept | N handoff | R09, S09 | |
| T15.03 | auto_assisted_human | Hornsea did not notify the ESO directly and restarted modules without coordination | N handoff | R09, S09, S10 | |
| T15.04 | judge | Delays and misattribution in communications described, without treating them as causes of the outage | N handoff | R09, S09 | |
| T16.01 | judge | Unrelated lightning strikes and trips ruled out using their timing and impacts | R | R03 | |
| T16.02 | judge | Transmission protection recognised as having operated as expected | R | R03, S09 | |
| T16.03 | judge | Non-causal wider transmission outages distinguished from the reported Hornsea internal-network weakness | R | R03, S01, S09 | |
| T17.01 | judge | Uncertainty register: unknown underlying Little Barford causes | R | S03, S04, S09 | |
| T17.02 | judge | Uncertain distributed-generation volumes and causal split registered | R | S06, S09, S12 | |
| T17.03 | judge | Unexplained movement of about 100 MW registered without assigning it to an invented asset | R | R06, S06, S12 | |
| T17.04 | judge | Source disagreements, measurement limits and causal uncertainty kept separate | R | R01, R05, S01, S03, S12 | |
| T18.01 | judge | Recommendations linked to established findings | N handoff | S08, S10, S11 | |
| T18.02 | judge | Recommendations cover generation compliance and protection improvements | N handoff | R10, S10 | |
| T18.03 | judge | Recommendations cover visibility, reserve/response or inertia | N handoff | R10, S06, S12 | |
| T18.04 | judge | Recommendations cover LFDD and essential-service resilience | N handoff | R10, S10, S11 | |
| T18.05 | judge | Recommendations cover rail recovery and communications | N handoff | R09, S08 | |
| T18.06 | judge | Each recommendation has a plausible owner and a verification method; equivalent justified actions accepted | N handoff | S08, S10, S11 | |
| T19.01 | judge | Further evidence requests: who should supply the missing evidence and exactly what | N handoff | R09, R11, S04, S06 | |
| T19.02 | judge | Notification and coordination needs supported by the requirements in the evidence; no unverified ESQCR or OC7/OC10 obligations | N handoff | R10, S07, S10 | |
| T20.01 | judge | Executive summary: accurate account of the triggering event | N handoff | R03, S09 | |
| T20.02 | judge | Executive summary: clear sequence and consequences | N handoff | S07, S08, S11, S12 | |
| T20.03 | judge | Executive summary: contributing factors kept separate from underlying unknowns | N handoff | S04, S06, S12 | |
| T20.04 | judge | Executive summary: significant estimates and disagreements attributed | N handoff | R09, S08, S12 | |
| T20.05 | judge | Executive summary: evidence-linked actions in priority order | N handoff | S08, S10 | |
| T20.06 | judge | Executive summary: no unsupported certainty; at most 600 words | N handoff | S04, S12 | |

## E. Severe flags

| # | Flag | Check | Answer |
|---|---|---|---|
| E1 | SF1 | Established Little Barford root cause asserted: increment A's heuristics after its two review rounds, revised in key 0.1.1 on the real panel run (decisions 77 and 81). The root-cause trigger alone spares a cause "before/until/without/pending" its finding ("allowed to reconnect before the root cause was found", also "before RWE's root cause was found") and one said to be unestablished, unidentified, unproven, pending or open ("the root causes are unestablished"); a cause named as found ("until the root cause was identified as a faulty speed sensor", "traced to") fires, and "root cause analysis" is no cause. The negation family (unknown, not established, undetermined, unresolved, remains open, pending investigation, whether, no longer believes, ...; "open", "pending", "not found" and "unidentified" only as the predicate of a cause, reason or origin) excuses only a trigger in its own clause: cut at ";", "but", "whereas", "while", "although", "though", "however", "whose" and after a sentence-initial concessive clause, so "the root causes are unknown, but the bypass valve failed" and "Although the root cause remains unestablished, ST1C tripped because of a faulty speed sensor" fire. A short head before a colon belongs to every ";"-part ("Unknown: a; b"). Not cut: "and" ("the root causes are unknown, and the bypass valve failed" is still excused). Hedges and the ESO attributions excuse the whole sentence, as in increment A, and the bare "bypass valve" mention is excused by any of them anywhere in its sentence. Confirmed effect zeroes T07.04, T07.05, T17.01 and now T14.02, and T20.03 and T20.06 when the assertion is in the executive summary (a suspicion there caps their pre-screens; T20.06's pre-screen also reads "the root cause of ... was" and "was a faulty ..."). | |
| E2 | SF2 | Invented evidence record: checked against every citable ID of this bundle and the shapes of its record IDs (REMIT revisions, ESO-COMMS entries, Network Rail incidents, the new witness answers); labelled document lines ("S08-O02") are not records. | |
| E3 | SF3 | Enforcement outcome asserted: fires on Ofgem's January 2020 settlements (voluntary payments of 4.5m each by RWE and Orsted, 1.5m by EPN and SPN, the redress scheme, "voluntary resolution", "formal legal determination", "fined", settlements with Ofgem), in findings and in report text including the executive summary; spares what the bundle holds (ORR's "could warrant enforcement action" and its paraphrases: "no non-compliance warranting enforcement", "did not justify enforcement action"; Ofgem's investigation that "does not imply" findings and "could lead to enforcement action"; delay compensation, market prices and settlement periods; recommendations that a regulator "should consider" or "decide on any" enforcement). "Enforcement action" counts only when asserted as taken, imposed or announced, and "acknowledged a technical breach" (a paraphrase of S10 P08) only with a payment, settlement or redress. Confirmed effect zeroes T14.04 and T14.05. | |

## F. Grading process

| # | Check | Answer |
|---|---|---|
| F1 | The judge interface is increment A's (judge output schema `gb2019-sr-judge-output/1`, decision 34): the judge sets values only for `judge` criteria, bounded by accounting caps and suspected severe flags; contradiction rules of judge criteria are pre-screen flags for you; `accept_judge` cannot sign off a capped proposal. Per-topic span scoping (decision 52) is the judge track's work. | |
| F2 | Grading decisions use schema `gb2019-fi-grading-decisions/1` (increment A's layout) and are bound to this key's sha256, the submission and the bundle. | |
| F3 | Grade reports (`gb2019-fi-grade/1`) carry `flags.executive_summary` (words, limit, within_limit) and stay provisional until every value has a human value or sign-off and this key is reviewed. | |

## G. Real-submission regression (decisions 18, 27, 40–48)

Increment A's six real submissions (`tests/fixtures/sr_live`) are graded with this key in
`tests/test_fi_grading_live_runs.py`: the re-bound criteria reproduce increment A's
automated results except the listed key 0.1.1 differences, and the new pre-screens were
read against the same texts. The two real full-investigation runs (Opus 5.5 pilot and
panel run, both judged; `tests/fixtures/fi_live`) were swept in key 0.1.1 (decision 77):
every flag, cap, automated decision and judge/pre-screen disagreement read against the
submissions; the corrections are items B19-B21, C2, C3 and E1 (decision 81 reviewed them
against mutations of the real sentences). Fixed before release: a false negative
(EPN/SPN "reconnected sites without ESO instruction") and false positives (Ofgem's 200 MW
at 49 Hz "net of ... trains" read as the rail threshold; "setting" read as rail "sets";
"DNO reports" read as "no reports"; a requirement "DNOs to notify" read as a
recommendation; a reconnection "before ESO was informed" read as a communications issue;
"restoration process" read as a compliance-process concern). The first full-investigation
panel must get the same treatment before any result is reported as more than
provisional: read every flag, cap and judge/pre-screen disagreement against the
submissions, fix the grader on real phrasing, and add the runs as fixtures. Each later
panel needs the same.

| # | Check | Answer |
|---|---|---|
| G1 | The pinned pre-screen results on increment A's runs (T14.03, T14.04, T14.05, T20.01) are right for those texts. | |
| G2 | On the two real full-investigation runs, the pinned outcomes (no severe flag, trap or cap; the corrected criteria; the remaining judge/pre-screen disagreements, each with who was right) are right for those texts. | |

## Sign-off

Reviewer: ______________________ Date: __________ Key version signed: ______

Second reviewer (handoff: two domain reviewers): ______________________ Date: __________
