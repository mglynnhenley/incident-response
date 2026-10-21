# Decision log — GB 9 August 2019 investigation environment

Each entry: decision, why, and what it costs. Newest last. "Plan" = `.context/attachments/aZy5w9/plan.md`;
"handoff" = the builder-only GB power cut handoff ZIP.

## Stage 1 — MVP (initiating fault, generator trips, frequency)

1. **One Karotte task, one step, four tools** (`list_documents`, `request_document`, `run_python`,
   `submit_findings`). Per plan. Reusable core in `environment/incident/` with no Karotte import; tools are thin
   adapters.
2. **Evidence lives inside the installed package, root-only in the container.** Retrieval copies a document into
   `/workdir/evidence/<ID>/` (root-owned, read-only). Python runs as the unprivileged student user, offline, with
   `RLIMIT_AS` 1 GiB and a 30 s timeout, so it can only see retrieved documents. Verified in Docker: 17/17
   isolation probes denied.
3. **Budget counting at the tool ledger, not the model loop.** Karotte can only stop a step on a final message, so
   tools return `BUDGET_EXCEEDED`/`EPISODE_CLOSED` and the judge classifies outcomes. Calls with unknown argument
   names are rejected by FastMCP before the ledger and are not counted (documented to the agent).
4. **Output-token budget (30k) enforced at grading**, because Karotte cannot stop a run mid-way; a submission after
   the budget is exhausted is graded `incomplete_submission`.
5. **Reconstructed records are labelled and provenance-verified.** Every non-blank line maps to a source passage;
   `builder/verify_provenance.py` checks every verbatim provenance quote against its stated PDF page
   (or, for the few quotes from the handoff's `SOURCE_STATUS.md`, against that text) and all hashes.
6. **R01 is real data**, rebuilt byte-for-byte from the NESO August 2019 archive; landmarks reproduced
   (49.083 Hz @16:52:59, 48.787 Hz @16:53:49, 50.001 Hz @16:57:16, 33 s strictly below 49 Hz).
7. **No pass threshold, no ranking.** Content coverage, evidence support and assertion quality are reported
   separately; Karotte's scalar is completion only (1.0 = valid frozen submission). Results stay provisional until
   a human adjudicates and a domain reviewer signs off the key.
8. **Citations are line/time/row locators validated at submission** (unknown IDs and out-of-range locators are
   repairable errors), then re-checked at grading. Alternative evidence is never auto-failed.

## Stage 1b — after live run 001 (Claude Opus 5.5, 2026-10-20)

Run 001: complete in 9/50 calls, $0.24; every finding correct, but ~18 of 23 were near-verbatim transcriptions.

9. **The task was too easy; make it deeper, not bigger.** Removed builder-computed conveniences (derived BST times,
   intervals, sums, UTC/BST notes) and builder meta-labels ("Known/Not established/Still a hypothesis") from the
   evidence. The agent must now align clocks, compute, and decide epistemic status from the sources' own wording.
10. **Brief asks for what is graded, never the answers.** Added "Report expectations" (chronology with clock basis,
    MW and timing, frequency minima/recovery/time below 49 Hz with method, mechanism vs unexplained cause). The
    49 Hz convention is deliberately unspecified: 16:53:40 is exactly 49.000 Hz, so strict-below (33 s) and
    at-or-below (34 s) differ and the agent must state its method.
11. **Difficulty is judged by a live model panel, not by the builder** (Opus 5.5 ×2, Sonnet 5.5, Haiku 4.5).

## Stage 2 — widen to the full incident (decided 2026-10-20 with the user)

12. **Full handoff toolset** in addition to the four tools: `query_frequency`, `query_asset_log`,
    `query_control_log`, `interview_witness`, `request_data_return` (deterministic matching, pagination, stable
    IDs), as specified in the handoff. All go through the same ledger and isolation boundary.
13. **Two increments.** Increment A — system response: distributed generation, LFDD, response/reserves/inertia,
    restoration. Increment B — consequences: rail, essential services, communications, compliance,
    recommendations. Live-tested after each.
14. **Budget 150 tool calls** (handoff/pilot default); context cap 200k and output budget 30k unchanged unless the
    live panel shows they bind unfairly.
15. **Grading adds an LLM judge** for interpretation, compliance and recommendations: versioned rubric, a judge from a
    different model family than the evaluated model where possible, cached by submission/evidence/rubric/model/
    prompt hashes, blinded model identity. Automated numeric/citation checks remain authoritative for numbers; a
    human still spot-checks and signs off. Results stay provisional.
16. **Use as much real data as possible.** Real public datasets (NESO, Elexon, operator/regulator records) are
    preferred over reconstruction; figures from the official appendices are digitised with stated uncertainty;
    reconstruction is used only where no primary record is public, and is labelled. Sourcing log:
    `.context/real_data/REAL_DATA.md`; figure/table catalogue: `.context/source_catalogue/catalogue.md`.

## Stage 1c — live panel on the de-digested task (bundle 1.1.0, key 0.3.0; 2026-10-20)

Opus 5.5 ×2, Sonnet 5.5, Haiku 4.5 via OpenRouter; all complete in 9–12 calls; total ≈ $2.15
(≈ $0.25–0.6 per run). Artifacts: `/tmp/panel_env/out/panel/*` (copied to `out/panel/`).

17. **De-digesting alone did not make the MVP hard.** All four models derived BST times from UTC and the T datum,
    kept the ±0.5 s uncertainty, labelled unresolved causes, and computed 33 s strictly below 49 Hz (two explicitly
    noted 16:53:40 = 49.000 Hz). Haiku 4.5 performed close to Opus. The remaining spread is small (Haiku omitted the
    first local minimum). Conclusion: the MVP's subject matter is too shallow to discriminate; difficulty has to come
    from the full incident's conflicting accounts and accounting bases — which supports widening (decisions 12–16).
18. **Grader false negatives found by real submissions, fixed before widening.** When a finding's structured
    `quantity` describes something else (e.g. "283 s after the fault") while the statement and `event_time` give the
    landmark (50.001 Hz at 16:57:16), D3 auto-scored 0. Rule now: fall back to the statement whenever the structured
    quantity's unit or range does not fit the criterion, and never auto-score 0 if any finding mentions a
    candidate value — route to human review instead. Mechanism matchers also accept paraphrases ("disagreed").
    Implemented as key 0.3.1 / grader 0.3.1. Expected values and tolerances are unchanged.
    - **D3.** The statement and derivation are also read when the quantity's unit, value range or time window does
      not fit. Each value is paired with the time written next to it, else the `event_time`. A value dated in the
      window beats any value without a time.
    - **Not candidates:** numbers without a time worded as thresholds or statistics, numbers described as before
      the event, and a value dated outside the window elsewhere.
    - **Automatic 0** only for a genuine omission (no candidate in any finding or the report) or for a structured
      quantity in the window that is wrong.
    - **D4.1–D4.3.** A finding of any status counts when one sentence states the mechanism with the trip and
      without hedging. The status matters for D4.4 only.
    - **Cost:** a D3 candidate that appears only in the report, or only in a finding labelled hypothesis or unknown,
      now needs a human. Regression fixtures are the five live submissions in `tests/fixtures/live/`.
    - **Second verification round (still 0.3.1, nothing released in between).** A verifier found the same rule
      broken by wording the first fix did not anticipate, and some new automatic credit. Changes:
      a clock time that is only the reference of an offset dates the value at the computed time ("50.0 Hz 207 s
      after its minimum at 16:53:49" is 16:57:16), and a reference without a number ("after the fault at
      16:52:33") only bounds it; a value dated outside the window only by an offset is listed for review rather
      than dropped (one dated by a time written next to it is still not a candidate: haiku's D3.1 stays 0).
      Never credited automatically, even within tolerance: a timed value worded as a level or "not yet"
      ("still below 50 Hz at 16:57:15"), a decimal without a unit, prose seconds without duration wording
      ("took 33 s to fall"), and a statement value beside its own finding's out-of-tolerance quantity. A seconds
      quantity worded as an offset does not fit D3.4. D4.1–D4.3: a finding labelled hypothesis never counts, and
      negation or uncertainty about the mechanism itself, or a later "This remains a hypothesis.", keeps an
      unknown finding from counting. A blanket whole-statement hedge check was rejected: sonnet55-001 F09 states
      the mechanism and then, in other sentences, Ofgem's "preliminary view" and RWE's UPS "hypothesis".
      D1.1 gains a scoring group (lightning attributed to "the fault" in one finding, the circuit in another).
      Reviewer notes, never scored: D2 times given only in the report (T + offset stays the agent's job,
      decision 9) and a D3.5 convention that does not give the reported duration.
    - **Cost of the second round:** more D3 criteria go to a human (any prose value whose wording the grader
      cannot settle). Live runs: only the D1.1 proposals of opus55-002 and sonnet55-001 change (0.5 → 1).

## Source catalogue (2026-10-20)

`.context/source_catalogue/catalogue.md` — 122 operational artifacts across the six PDFs (37 raster figures,
30 tables, 34 text records, 9 maps, …); 31 tables extracted to CSV and token-checked; 6 used fully by the bundle,
15 partly, 92 unused.

19. **S01 clock line must be corrected.** The catalogue critic found that Ørsted's report prints local time (16:52)
    almost everywhere; the "15.52.33.728" notation appears in one sentence only. S01's instants (UTC with Z) are
    correct, but its header's rationale ("the operator labels no clock; UTC is inferred") is not. Fix: state that
    this reconstructed log is rendered in UTC and that the operator's published timeline uses local time.
    Deferred until the grader fix lands (a bundle edit changes the bundle hash the key binds to).
20. **Real conflicts found in the sources become evidence for the widened task, not cleaned away:** Hornsea reactive
    power before the event (ESO Table 1 "absorbing 0.4 MVAr" vs ≈ −33 MVAr on ESO Fig 8); inertia 210 GVA·s
    (ESO Table 4) vs 219,632 MVA·s (Appendix M Q42); secondary response 1,314 MW (ESO Table 3) vs 1,338 MW
    (Appendix M Q16/Q17); the Hornsea voltage onset ≈ 20 ms before NGET's 16:52:33.490 inception (Fig 7).

## Increment A design (2026-10-20) — full contract: `.context/increment_A_design.md`

21. **New task `gb-2019-system-response`; the MVP task stays frozen** as a regression baseline with its own bundle.
    Scope: T01–T09, T12, T16, T17 (fault → demand restoration). Rail, essential services, communications,
    compliance, recommendations and summary wait for increment B.
22. **Evidence order of preference: real public data → official published tables/figures (digitised with stated
    uncertainty) → labelled reconstruction.** Real sources now in use: NESO 1-s frequency; Elexon FUELINST, INDO,
    B1610, MELs, BOALF, QAS, NIV, DCI (931 MW 16:54–17:40 BST); NESO demand and (modelled) embedded and inertia
    estimates; METAR/Met Office weather. Reconstruction only where no public primary record exists (DNO returns, DG
    returns, control-room log text, witness accounts).
23. **Asset and control logs carry the time as recorded plus an indexing time used only for filtering**, with its
    uncertainty stated. A time-range query tool needs an absolute index; the raw recorded time and clock basis stay
    primary in every row.
24. **Witnesses are fixed fact cards with deterministic topic matching** — no deception, documented disagreements
    allowed, "not known" for anything else; each response has a citable ID.
25. **Judge: `openai/gpt-6.1-sol` via OpenRouter by default** — a different model family from the Anthropic models
    under test, structured output, ≈ $2/$10 per M tokens. It proposes; it never decides numeric criteria; cached by
    content hashes; humans sign off.
26. **Decision 19 is applied only in the new system-response bundle.** The MVP bundle 1.1.0 stays frozen so the
    five live runs graded against it remain comparable; its S01 header rationale is recorded here as a known
    erratum (the instants are correct).
27. **Grader key 0.3.1 (MVP).** Real submissions drove four rounds of false-negative/false-positive fixes (statement
    fallback, relative-time offsets such as "207 s after the 16:53:49 minimum", threshold/negation wording,
    mechanism paraphrases). The five live submissions are regression fixtures (`tests/fixtures/live/`). Open choice
    for the reviewer: a wrong structured value with a correct value elsewhere stays an automatic 0 with a note.

### Increment A implementation notes — review fixes (bundle 0.1.0 rebuilt, 2026-10-20)

- **Decisions 9 and 20 in the new evidence.** Conflicts stay in the records but no compiler's
  note points them out, as in MVP R03 since 1.1.0. R05 no longer has "KNOWN SOURCE CONFLICTS"
  or cross-source clock alignment. It states only what each chart prints, and the comparisons
  stay in private provenance (`validation.landmark_checks`). S06 Part 3 lists the estimates by
  source in printed order (E1-E23), each with the source's own timing words and no builder
  stage headings. S12 Section C has a neutral heading ("records of a change of about 100 MW,
  by source").
- **Value tags.** App I Table 1 is "[modelled]" in every row of both R06 and S12, as the
  table's inputs. Ofgem and E3C figures are tagged by their own wording: "[reported]" unless
  the source calls the figure an estimate or approximation, or attributes it to modelling.
- **R07 Part D.** It holds builder-written gists (organisation, decoded time, gist), which
  `check_posts` forbids from sharing more than 3 consecutive words with the post. The
  STATUS line scopes "nothing synthesised" to Parts A-C.
- **Witnesses (decision 24): matcher `witness-topics-2`.** Topics name subjects, never
  findings, and `verify_bundle` runs the landmark check over every topic. An ambiguous
  question shows only the closest tied blocks, at most 3, with a count of any others.
  - **Cost:** a question phrased with finding words (e.g. "bypass") may only get choices.
- **`request_document` matching: matcher `doc-tokens-2`.** Matching ignores the category, and
  the ID, title or keywords must cover at least half the description words.
- **Pagination cursors** carry an integrity field keyed by the bundle sha256, and their
  offsets must be page-aligned. Edited cursors are refused. A cursor is valid only for the
  exact bundle that issued it.
- **Replay** resolves a missing recorded bundle path by its package-relative tail, then by
  `bundle_sha256`.
- **Data-return refusals** say only "not held in this evidence pack" plus what the recorded
  basis states.
- **Signal names and attribution.** ESW-400 signal names are neutral, and the outcome
  wording stays in row text. The Elexon attribution in the manifest comes from the real
  track's source records.
- **Checks and fake scenarios.** The image checks also load and verify the system-response
  bundle, protect its logs, cards and private directory, and probe it via
  `SystemResponseToolConfig`. A system-response `isolation_probe` fake scenario now exists;
  the other system-response scenarios still wait for the grading track.

## Increment A build outcome (2026-10-20)

28. **System-response bundle 0.1.0:** 16 documents (R01–R08, R10, S01, S03–S07, S12; S05/S06 only via
    `request_data_return` from the DNOs), 777 log rows (HORNSEA-ONE 312, LITTLE-BARFORD 180, ESO-ENCC 277 incl.
    139 real BOALF instructions, ESW-400 8), 5 witness cards, a fixed data-return registry. Rebuilds byte-identically
    from `.context` and from the committed raw mirror (`builder/system_response/raw/`, open-licensed slices only).
29. **Known gaps accepted rather than invented:** no DNO asset logs and no control logs for NGET, DNO, RWE or Ørsted
    rooms — no public primary record exists and the published call summary covers only ESO's side. The key must not
    require them.
30. **R05 digitisation uses the PDFs' native embedded rasters** (lossless extraction; upsampled renders add no
    information). Axis fits < 0.5 px rms. Fig 4's four per-PPM MVAr traces are excluded (indistinguishable colours);
    Fig 3 MVAr samples 4–18 omitted (hidden by a call-out). Cross-source comparisons live only in private
    provenance — the agent must find the conflicts itself.
31. **Evidence must not pre-sort conclusions** (review finding): S06 lists published DG estimates by source in
    printed order, not under builder-written stage headings; R05 no longer computes the onset/MVAr conflicts.

## Increment A grading (2026-10-20)

Grader `environment/incident/sr_grading.py` (+ `sr_accounting.py`), judge track
`environment/incident/judge/`, key `private/system_response/answer_key.json` 0.1.0
(`pending_domain_review`; built by `.context/sr_key_builder/build_key.py`, which rebuilds it
byte for byte), checklist `private/system_response/REVIEW_CHECKLIST.md`. The task's judge
calls `sr_grading.grade_episode(episode_dir, transcript_summary)`; the score stays
completion only (decision 7).

32. **60 criteria for T01–T09, T12, T16, T17, by assessment mode: 4 `auto_numeric`, 32
    `auto_assisted_human`, 24 `judge`** (`key.judge.criteria` lists the 24). `auto_numeric`
    (T03.01–T03.03 landmarks, T04.01 duration) is decided from the frozen R01 series; a
    reviewer may override. `auto_assisted_human` (values, times, mechanisms, accounting
    bases) gets an automated proposal that a human decides; the judge's values for these
    are recorded and ignored. `judge` criteria (distinctions, attributions, labelling,
    the uncertainty register) get a judge proposal that a human signs off. Compound
    handoff criteria are split into fields (T01.03, T02.01–T02.03, T02.05, T05.01,
    T09.02, T12.01) with equal subweights for reporting only. T04.02 (rail) is deferred;
    T12.05 (inertia with its basis) is an increment-A addition. Content coverage,
    evidence support and assertion quality stay separate; no total, threshold or
    ranking; every report is provisional until the key is reviewed and every value has a
    human value or sign-off.
    - **MVP parity, stated exactly.** `tests/test_sr_grading_live.py` checks the same
      automated results as the MVP grader on the four v2 live runs for eight pairs only
      (T03.01–T03.03, T04.01, T04.03, T07.01, T01.02, T01.03b). T02.03b, T02.04, T06.01
      and T16.01 diverge by design (checklist B1). The key builder's handoff summary
      said 27 `auto_assisted_human` and 29 `judge` criteria and claimed parity on every
      reused criterion; both were wrong.
33. **Accounting bases** (key `accounting`, decision 20). A figure is credited only on
    the source, stage and definition of the record it comes from: 1,878 MW (ESO Table 2,
    six components, through GT1B) vs at least 1,990 MW (Ofgem, after GT1A and the 49 Hz
    net reduction); 931 MW (DNO-reported LFDD, ESO; Elexon DCI) vs 892 MW (Ofgem, net)
    vs 973 MW (E3C interim); 1,314 MW (ESO Table 3) vs 1,338 MW (ESO's earlier answers);
    210 GVA.s (Table 4) vs 219,632 MVA.s (answer 42); distributed-generation estimates
    by source, stage and method.
    - **Matching within 1 MW**, not the 10% MW tolerance, because neighbouring totals
      (1,878/1,990, 931/892) would otherwise cross. Mentions are classified attributed,
      defined, unattributed (0.5), misattributed or mismatched (0); figures without a
      unit and report-only figures go to a human.
    - **Wording between two figures belongs to one of them.** A contrast ("vs",
      "versus", "compared with", "rather than", "unlike", "than" not before a number)
      ends both sides. "or", "with" or "plus", an unclosed parenthesis, or a source named
      in the possessive splits the rest; otherwise the wording follows the figure before
      it. Mismatch wording and the source binding read the figure's own side only.
    - **Arithmetic.** Derived sums must match within 1 MW. Overlap traps are a total
      with its own component, two estimates of one loss, or ESO's through-event total
      with figures on other bases (1,878 + 200). A term counts for a group only if the
      sentence does not identify it as another figure (key `figures`). The DG-total
      group needs distributed-generation wording. Staging is not a trap: a stage
      subtotal plus later losses (1,481 + 100 + 210 + 200 ≈ Ofgem's 1,990).
    - **Caps.** Accounting traps cap the criteria in `accounting_caps`, including a
      judge's value (decision 15: automated checks are authoritative for numbers).
34. **Judge interface** (decision 25). One request per unit: a task with `judge` or
    `auto_assisted_human` criteria, plus `UNASSIGNED` for unrouted factual findings.
    `auto_numeric` criteria are never sent.
    - **What the judge sees.** The system message is the rubric
      (`judge_rubric_v1.md`, 1.0.0). The user message has the blinded submission
      (model and vendor names replaced), the resolved cited spans (marked "not obtained
      during the episode" or unresolvable where relevant), the unit's criteria and keyed
      spans, and the severe-flag definitions. It never sees report passages,
      provenance, other runs, the pre-screen or reviewer notes. `reviewer_note` and
      `prescreen` fields are stripped, and a test asserts that no message names live
      runs, MVP criterion IDs, key conventions or the pre-screen.
    - **Response checks.** The response must be strict JSON (schema
      `gb2019-sr-judge-response/1`). Every quote is checked word for word against a
      shown span: hallucinated spans are dropped and a correct quote under a wrong
      locator is relocated.
    - **Withheld for a human.** Evidence support 1 is withheld without a verified quote
      from an obtained span that the credited findings cite. So is a 'supported' or
      'contradicted' verdict without a verified quote, a low-confidence 'unsupported',
      and 'not_factual'.
    - **Merge** (`merge_judge_proposals`). The judge only sets values for `judge`
      criteria, after accounting caps and suspected severe flags. Evidence is decided 0
      when the credited findings cite nothing usable, or when a 1 is quoted only from
      cited spans never obtained. A judge 'supported' for a finding that an automated
      numeric check contradicts becomes a conflict for a human, not a verdict.
      `accept_judge` cannot sign off a capped proposal: the reviewer gives the value.
      Severe flags are only suggested.
    - **Caching.** The cache key is the sha256 of the submission, bundle, key, rubric,
      judge model, prompt template, request settings, unit and exact messages. Changing
      any input is a miss. Only validated responses are stored, and they are re-checked
      on every read.
    - **Refusals.** A judge from the evaluated model's family, or a run whose model is
      unknown, is refused before anything is sent (`--allow-same-family` overrides, and
      the override is recorded). `--dry-run` prices a run. Tests never call a model:
      they use a mocked client.
35. **Contradiction rules are a pre-screen, not a cap on the judge (review round 1).**
    Sentence-level regex rules fired on correct, even exemplary, statements: services
    restored "longer" after demand, a Killingholme connection point next to
    "contributed to the de-load", "incorrect protection operation can be excluded",
    "at" inside "rather", Ørsted's "first view" of the DRC. For `judge` criteria a hit
    now bounds only the automated proposal and is listed in
    `flags.prescreen_contradictions` and in the content basis for the reviewer. The
    rules (T05.03, T06.01/T06.05, T12.04, T16.02, T16.03, T17.03) now tie the subject to
    the causal or failure verb and list more non-assertions. These hits are not shown
    to the judge, because the rubric says it sees no automated grading.
    - **Cost:** a judge that misses a real contradiction is caught only by the reviewer
      reading the flag.
36. **Pre-screen and flag fixes from real phrasing (review round 1).**
    - **T02.02a** reads loss wording ("tripped" and "infeed" added) anywhere in the
      value's sentence, which covers table-style lists, unless the value's own clause
      describes output before the event. An in-tolerance Hornsea value with no such
      wording is a noted candidate, never a silent 0.
    - **Time ranges.** A clock label after a range applies to both ends ("between 15:58
      and 16:16 UTC"). The frozen MVP grader keeps this limitation.
    - **T05.02.** "The first DNO reported ... complete" (17:34/17:36) is masked, so it
      is not read as the completion of all restoration at 17:37.
    - **SF3** ignores pounds in price and cost contexts (R06 system prices in GBP/MWh).
    - **SF2** accepts references to labelled document lines ("R03-C2").
    - **T06.03** no longer credits Ofgem with the resonance explanation: Ofgem's
      findings name an instability, and only Ørsted (restated by ESO) names a resonance.
      The domain reviewer is asked to confirm this (checklist B19).
    - **Version.** The key stays 0.1.0 with a `changes` entry, since nothing was
      released in between. Its sha256 changed, so any cached judge responses and
      decisions bound to the old key no longer apply.
37. **Reference coverage.**
    - **Reference submission.** `tasks/gb_2019_system_response/reference/reference_submission.json`
      has 70 findings and reaches an automated proposal of 1, with an evidence proposal
      of 1, on all 60 criteria. It has no cap, trap, flag or severe flag. Every source
      figure a finding states is in the text of one of its own citations (a test checks
      this for the figures the review found missing: F30, F42, F47, F60, F65, F75, F76,
      F90 and F93).
    - **Reference scenario.** The `reference` fake scenario uses all nine tools and
      every retrieval route. Every cited record is returned by a call in the script.
    - **Fixtures.** `tests/fixtures/sr/` has fixtures for correct, uncited, incomplete,
      uncertain, incorrect and nine invalid submissions, rebuilt with
      `build_sr_fixtures.py`.
    - **`isolation_probe`.** It makes 28 hostile tool calls (`SR_TOOL_PROBES`): path
      traversal, private IDs, and prompt injection in five witness questions and one
      `request_document` description. The Docker trace has 21 `UNKNOWN_ID`, 2
      `INVALID_ARGUMENT`, 3 `AMBIGUOUS_REQUEST` (topic choices only) and 2 "not known"
      answers; a test checks the same tally locally. An earlier report gave "31 calls"
      with three answers counted twice and "four injections", which was wrong.

## Increment A grading outcome (2026-10-20)

32. **Key `system_response/answer_key.json` 0.1.0 (pending domain review): 60 criteria** — 4 auto_numeric (frequency
    landmarks, time below 49 Hz), 27 auto_assisted_human, 29 judge. Rail criterion T04.02 deferred to increment B;
    T12.05 (inertia 210 vs 219.6 GVA·s) added and flagged for review.
33. **Accounting bases are graded, not just numbers:** a figure is credited only on its own basis and stage
    (1,878 vs ≥1,990 MW; 931 vs 892 vs 973 MW; 1,314 vs 1,338 MW; 210 vs 219.6 GVA·s; DG estimates by stage).
    Summing overlapping estimates or a total with its own components is flagged and caps the criterion.
34. **Judge interface:** one request per task topic; the judge sees only the blinded submission, the rubric and the
    resolved cited + keyed spans (no automated pre-screen, no provenance); returned quotes must occur in the span
    text; outputs cached by content hashes; temperature is not sent for gpt-6.1-sol (OpenRouter lists no such
    parameter) and this is recorded; merged values are `judge` proposals bounded by automatic caps and need
    `accept_judge` sign-off.
35. **Reference investigation uses all nine tools in 48/150 calls**; its compact submission is ≈ 14k output tokens,
    so the 30k output-token budget may bind for real models that also reason — the live panel decides whether to
    raise it (handoff allows logging reasoning separately).

## Increment A live panel 1 (30k output budget; 2026-10-20)

Opus 5.5: 38 calls, 36.4k output tokens before submitting → incomplete (budget). Sonnet 5.5: 34 calls, 30.6k →
incomplete (budget). Haiku 4.5: 18 calls, no witnesses/control log/data returns, 26.6k → complete. Diagnostic
grading ignoring the budget: Opus 52/60 criteria at full credit, Sonnet 50/60, Haiku 29/60 (18 zeros). Cost
≈ $11.20 (late turns re-send ≈ 150k tokens of context). Artifacts: `out/panel_sr_30k/`.

36. **The widened task's output budget is raised to 80k (user decision).** At 30k the rule — which counts reasoning
    tokens Karotte cannot separate and Opus 5.5 cannot disable — failed the two most thorough investigations and
    passed the shallowest, i.e. it measured brevity, not investigation. 80k keeps a hard, measurable limit with
    headroom over the observed 31–37k. The MVP task keeps 30k (`SYSTEM_RESPONSE_OUTPUT_TOKEN_BUDGET` is separate;
    tested). The panel is re-run under the new figure so the agent is told the budget it is judged by.
37. **Judge cost is higher than first estimated:** each of 13 topic requests re-sends the whole submission and all
    cited spans (≈ 58k tokens), ≈ 750k input tokens per run (≈ $0.4–1.9 depending on prompt caching). Follow-up:
    send each topic only its own findings and spans.

## Increment A live panel 2 (80k output budget, judged; 2026-10-20)

All three complete. Opus 5.5: 47 calls, all 9 tools; Sonnet 5.5: 30 calls; Haiku 4.5: 17 calls (no witnesses, no
control log, no data returns). Best-available content (automatic decisions, judge proposals for judge-mode
criteria, pre-screen for the rest; provisional, not human-signed): Opus 47 full / 10 half / 3 zero; Sonnet
50 / 9 / 1; Haiku 28 / 10 / 22. Judge (gpt-6.1-sol) cost $1.57 / $2.35 / $1.09; panel + judge ≈ $17.20; cumulative
OpenRouter spend $30.82. Artifacts: `out/panel_sr80k/`.

38. **The widened task discriminates; the MVP did not.** Haiku drops to about half of Opus/Sonnet, mainly on
    distributed generation (T08), LFDD accounting (T09), response/reserves (T12) and the uncertainty register (T17),
    which need the data returns, witnesses and conflicting accounting bases it never consulted.
39. **The judge disagreed with the regex pre-screen on 6–8 of 24 judge criteria per run, in both directions**, so
    neither alone is trusted: judge proposals plus human sign-off remain the rule, and disagreements are listed for
    the reviewer.
40. **Real submissions again exposed grader heuristics** (accounting source binding marked correctly attributed
    Ofgem figures as misattributed; SF1 fired on a correct statement of the speed-sensor *mechanism*). Fixed with the
    six real submissions as regression fixtures before any results are reported as more than provisional.

## Increment A review round 2: the six real submissions (key 0.1.1, grader 0.1.1; 2026-10-20)

Every flag (accounting traps and caps, severe flags, labelling, inferential language, invented records), every
automated decision and cap, and every judge/pre-screen disagreement on the six real submissions (80k panel: complete,
judged; 30k panel: Opus and Sonnet incomplete on the budget, Haiku complete, graded diagnostically) was read against
the submission text and the keyed evidence. The runs are now regression fixtures (`tests/fixtures/sr_live`,
`tests/test_sr_grading_live_runs.py`), with the true positives (and mutations of the real texts that must still trap)
asserted alongside the corrected outcomes.

41. **Source binding uses the attribution nearest to each figure** (`sr_accounting`). Confirmed false positives:
    "Ofgem: >1,130 MW ..., about 1,500 MW ..., and at least 1,990 MW ..." (sonnet 80k F17, sonnet 30k F11) bound to
    ESO through the quantity basis of another number (cap 0 on T02.06, 0.5 on T12.02); "Ofgem's final report" and "the
    Ofgem final report" read as ESO's final report (haiku 80k F33 and its report); "ESO estimate from the DNO data
    plus the 150 MW" gave the 150 MW to the DNOs (sonnet 30k F09); "ESO's earlier E3C answer" bound to the E3C (opus
    30k F16, cap on T12.01c); structured quantities "mismatched" by wording about other figures anywhere in the
    statement (sonnet 80k F12 "gross", F27 Ofgem's "net"; opus 30k F12 "(before LFDD)" of the 1,481 MW, cap 0 on
    T02.06; sonnet 30k F19). The order is now: own side; the preceding figure of the sub-clause (not across
    "or"/"with") or the next when nothing divides them; a list head ("X: a, b, c", "X gives a, b and c"); a clear
    preceding source; and the quantity basis only for its own value or a number it names. Adjacent mentions name one
    source (owner first, specific beats generic); a parenthesis around a figure is its own; a structured quantity is
    bound and checked on its basis (parts naming no other figure) and the statement value's own side. All 12
    accounting traps and the 6 accounting caps on the six runs were false positives and are gone; mutations that give Ofgem's figures to ESO, 892 MW
    to ESO's final report, 1,338 MW to Table 3, 150 MW to the DNOs or 931 MW a "net" basis still trap.
42. **SF1 fires only for an asserted root cause, not the trip mechanism.** The sensor-failure trigger allowed any 20
    characters between "sensor" and "fault", so "the three ... speed sensors after fault clearance" (sonnet 80k F08,
    RWE's and Ofgem's mechanism) was a suspected SF1: it zeroed T07.01 and capped T07.04, T07.05 and T17.01. The
    failure must now be said of the sensor ("the sensor failed", "a sensor fault", "faulty sensor"). The four other
    SF1 trigger hits on the six runs all attribute the bypass-valve wording to ESO's executive summary and stay
    excused; no run asserts a root cause, so no SF1 remains. No SF2 (every ID cited exists) or SF3 candidates.
43. **Judge vs pre-screen disagreements: who was right** (judge outputs unchanged, only pre-screens fixed).
    - Pre-screen wrong (fixed): opus T05.03 (restoration explicitly scoped to DNO demand is the expectation's
      alternative for full), T08.04 (causal split credited from Little Barford's "cause ... unknown"), T09.03 (F39's
      net relief ignored because it is labelled hypothesis), T09.04 ("3.2% of 29 GW" counted as non-equivalence),
      T12.03 (Hornsea's "insufficiently damped ... response" counted as exhausted response); sonnet T02.06, T07.04,
      T07.05, T17.01 (false accounting cap and SF1), T09.04, T12.03 (as opus); haiku T02.06 (Ofgem's 892 MW net
      demand counted as a generation net effect), T06.02 (both sides described, but not which behaved as expected),
      T08.04 and T17.02 (Little Barford "cause unknown"), T09.04, T12.03.
    - Judge right, pre-screen kept (no reliable pattern): opus T17.03 (the summary places the ~100 MW "at 49 Hz",
      conflating it with the 200 MW stage).
    - Borderline, left to the reviewer: haiku T05.03 ("distinct from the recovery of other affected generation
      services" without naming transport) and T06.01 (protective de-load described as "inappropriate protection
      actions", no overcurrent).
    Remaining disagreements: opus 1 (was 6), sonnet 0 (was 6), haiku 2 (was 8).
44. **Other false positives and negatives from the sweep.** T05.01b read only a finding's event_time (16:58), never
    the end of the "16:58-17:16" window in its statement (opus 80k F31, haiku 80k F37, sonnet 30k F21): the element
    now also reads statement times (`read_statement_times`). Labelling flags fired on measurement caveats ("1 s
    sampling means the true minima may be slightly lower", "a 0.5 s offset is possible") and on reports of someone's
    hypothesis ("its hypothesis is", "Ørsted first suspected"): 7 of 9 were false (kept: sonnet 80k F12 "probably
    larger", F23 "likely"). Inferential flags fired on "its simulation suggests" and "DNO public posts indicate" (the
    record's account) and on a passive "was attributed to": 5 of 13 were false. T08.04's telemetry wording may be 80
    characters from its negation ("no DNO feeder-level ... or embedded generation telemetry"). The labelling and
    inferential flags remain proposals, never scored. Auto-numeric decisions (R01 landmarks, duration) were all right,
    including Haiku's genuine T03.01 omission.
45. **Versions and the re-merge of the judge outputs.** 0.1.0 grades were reported (decision 38), so this is key
    0.1.1 and grader 0.1.1 (checklist rule: a changed key needs a new version and a regrade; the reviewed key will be
    0.1.2 or later). No judge-visible key text changed (criteria, examples without pre-screen values, accounting
    figure descriptions, severe-flag definitions: checked against 0.1.0 field by field), so the existing judge outputs
    were re-merged without a judge call, rebound to key 0.1.1 with the old binding recorded (`rebound`). Every opus
    request is byte-identical under 0.1.1; sonnet T02/T07/T17 and haiku T02/T09 differ only in which findings the
    judge is asked to classify (the task assignment follows the corrected pre-screens). Regrades:
    `/tmp/sr_regrade/{before,after}/`. Best-available content (decided values, judge proposals after caps for judge
    criteria, else the pre-screen; provisional, not human-signed):

    | Run | before (full/half/zero) | after (corrected, decision 46) | traps | severe | caps | labelling | inferential |
    |---|---|---|---|---|---|---|---|
    | sr80k-opus55-001 | 47/10/3 | 49/9/2 (first reported 48/10/2) | 0 → 0 | 0 → 0 | 0 → 0 | 2 → 0 | 2 → 1 |
    | sr80k-sonnet55-001 | 48/7/5 | 52/8/0 | 4 → 0 | 1 → 0 | 5 → 0 | 5 → 2 | 3 → 2 |
    | sr80k-haiku45-001 | 28/10/22 | 29/10/21 | 2 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 |
    | sr30k-opus55-001 | 52/5/3 | 52/7/1 (first reported 51/7/2) | 2 → 0 | 0 → 0 | 2 → 0 | 0 → 0 | 1 → 1 |
    | sr30k-sonnet55-001 | 50/7/3 | 54/6/0 (first reported 52/6/2) | 4 → 0 | 0 → 0 | 2 → 0 | 2 → 0 | 4 → 3 |
    | sr30k-haiku45-001 | 29/13/18 | 27/13/20 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 3 → 1 |

    (Decision 38's Sonnet 50/9/1 counted the judge proposals before the false caps; with the caps applied it was
    48/7/5.) The 30k runs lose credit where a pre-screen had credited the wrong text (T09.04's non-equivalence;
    T12.03 for Opus and Haiku, whose only "response" was Hornsea's "insufficiently damped" control response; Haiku's
    T02.06 and T17.02) and gain it where a false cap or reader had removed it (T02.06, T05.01b, T12.02). *Corrected
    by decision 46:* Sonnet 30k's T12.03 loss was not of this kind. Its F16 "with all response delivered at
    16:53:31" paraphrases ESO's 16:53:31 entry, and the round-2 exhaustion pattern wrongly required an auxiliary.
    The first-reported 30k counts also missed T08.05 for Opus and Sonnet and Sonnet's T09.04 winter basis.

## SR grader corrections from real submissions (verification of review round 2; key 0.1.1, grader 0.1.1; 2026-10-20)

An independent check of decisions 41–45 used mutations of the six real texts (`/tmp/verif`) and found the round
had over-fitted in places. All eight reported issues were confirmed and fixed, each with regression tests (synthetic
sentences in `tests/test_sr_grading_accounting.py` and `tests/test_sr_grading_prescreen.py`; mutations of the real
texts in `tests/test_sr_grading_live_runs.py`). The key and grader stay 0.1.1: nothing was released in between,
and the key's `changes` record the revision. No judge-visible key text changed (checked field by field), so the
judge outputs on disk were re-merged without a judge call. Sonnet 80k's T08 judge request now also lists F11 for
classification.

46. **Binding stays inside the clause it belongs to** (`sr_accounting`).
    - **List scope.** A reporting-verb list ("Ofgem gives a, b and c") ends at an "and" that opens a new finite
      clause. Figures with participles ("1,878 MW of generation lost", "931 MW … disconnected by LFDD") stay in the
      list.
    - **Barriers.** "whereas", "while", "but", "below", "above", "exceeds" and comparisons ("close to", "similar
      to") act like "vs".
    - **Borrowing from the next figure.** A later figure lends its source only through a citation parenthesis
      ("… also tripped (Ofgem)") or a trailing predicate shared by coordinated figures ("… estimates made by ESO").
      Such a predicate overrides a shared subject but not a list head.
    - **Other borrowing.** A source after a figure is not taken across a semicolon or from a head that introduces
      its own figures. A citation parenthesis closed before the next figure is not a shared subject.
    - **"Final report".** A bare "final report" belongs to the source named with it ("in its final report Ofgem",
      "Ofgem's January 2020 final report") or the nearest source in its clause, never across a contrast. It is
      ESO's only by default.
    - **Ranges.** "X and Y MW" is a range only after "between", and "X MW to Y MW" only for a key range. This
      recovers "1,338 MW in Appendix M", the 219,632 MVA.s after "Table 4", and the last items of rising lists.
    - **Sums.** Expression terms may carry up to four label words. Prose sums ("X plus Y, about Z in total",
      "adding X to Y gives Z") feed the overlap trap but are never arithmetic errors.
    - **Not changed.** A colon head still attributes its whole sentence ("Ofgem: … reached 1,878 MW" traps). A
      range term in a prose sum is not read.
47. **SF1 recall restored.** The failure word may again be up to 30 characters after the sensor, but "fault" counts
    only as the sensor's own ("sensor fault", "a fault"). The reviewer's suggested negative lookahead was not used:
    it misses "one of the three speed sensors failed after the fault" and fires on "speed sensors saw the
    transmission fault". New triggers cover "a failure of / fault in a speed sensor" and the transmission fault in
    the active voice as the cause of the speed-signal discrepancy. The context also accepts "speed-signal", and an
    ESO attribution excuses only the bypass-valve wording. On the six runs the only hits are the four ESO-summary
    valve attributions, all still excused. Remaining limit (MVP rule): a hedge or "unknown" elsewhere in the same
    sentence still excuses an assertion.
48. **Pre-screens and flags.**
    - **Pre-screens.** T12.03 accepts "all response delivered" without an auxiliary and "response already
      deployed". T08.05 accepts "differ by stage", a combined vector-shift and RoCoF loss, and a total written as its
      parts. T09.04 accepts "peak forecast demand". T08.04's telemetry wording must be about distributed generation.
      T12.02 also reads the exceedance in report text.
    - **Inferential flag.** "suggests/indicates" is exempt only with a named third party or its document as subject.
      R01, "the record", "the data" and "our analysis" are flagged again.
    - **Labelling flag.** A measurement caveat excuses only a hedge about the measured value.
    - **Real runs.** Flags on the six runs are unchanged.

    Best-available content (full/half/zero; provisional, not human-signed). Accounting traps, severe flags, caps and
    labelling/inferential flags are unchanged on all six runs (0, 0, 0; flags as in decision 45).

    | Run | 0.1.0 | round 2 as first reported | now | changed criteria |
    |---|---|---|---|---|
    | sr80k-opus55-001 | 47/10/3 | 48/10/2 | 49/9/2 | T12.02 0.5 → 1 (report "well beyond the secured level"; judge note 1) |
    | sr80k-sonnet55-001 | 48/7/5 | 52/8/0 | 52/8/0 | none (F11 now classified under T08) |
    | sr80k-haiku45-001 | 28/10/22 | 29/10/21 | 29/10/21 | none |
    | sr30k-opus55-001 | 52/5/3 | 51/7/2 | 52/7/1 | T08.05 0 → 1 (F14 "differ by stage", F10 500 = 150 + 350) |
    | sr30k-sonnet55-001 | 50/7/3 | 52/6/2 | 54/6/0 | T08.05 0 → 1; T09.04 0 → 0.5; T12.03 0.5 → 1 (F16) |
    | sr30k-haiku45-001 | 29/13/18 | 27/13/20 | 27/13/20 | none |

    Regrades: `/tmp/r3/{before,after}/`.

## Increment B design (2026-10-20) — full contract: `.context/increment_B_design.md`

49. **New task `gb-2019-full-investigation`; increment A's task stays frozen** as a regression baseline (as the MVP
    did). Adds T04.02, T10, T11, T13, T14, T15, T18, T19, T20 to increment A's 60 criteria, whose IDs are unchanged.
50. **Ofgem's January 2020 enforcement settlements are excluded from the agent-visible evidence**, although public:
    the handoff forbids requiring or supplying enforcement outcomes, and asserting them is severe flag SF3. They stay
    in private provenance as a leakage/memorisation detector.
51. **Communications evidence uses organisational public statements only** (anonymised derived data; no personal
    handles), plus Elexon REMIT publication times; the 17:51 vs 18:00 discrepancy is preserved where both records
    exist.
52. **Judge requests are scoped per topic** (only that topic's findings and cited/keyed spans) to address the cost
    found in decision 37.

## Increment B build outcome (2026-10-20)

**Bundle `gb-2019-08-09-full-investigation` 0.1.0** (`bundles/full_investigation/`, built by
`builder/full_investigation/`: real track `real/fi_build_real.py`, reconstruction track
`recon/build_fi_recon.py`, integration `build_bundle.py`, checks `verify_bundle.py`).

- **Documents.** 22 documents with 61 artifacts. 20 are listed; S05 and S06 are reachable
  only as data returns. The 16 increment-A documents are byte-identical copies under the
  same IDs (43 files copied unchanged). R10 is replaced by the full edition, whose lines
  1-133 are A's R10. The new documents are R09, R11 and R12 (real data) and S08, S10 and
  S11 (reconstructions). 792 provenance segments cover every non-blank line.
- **Logs: 897 rows,** of which 777 are A's rows, unchanged.
  - Asset logs: HORNSEA-ONE 337, LITTLE-BARFORD 201 and ESW-400 8 (46 new REMIT rows).
  - Control rooms: ESO-ENCC 277, ESO-COMMS 42, NETWORK-RAIL-CONTROL 31 and
    GTR-FLEET-CONTROL 1.
- **Witnesses:** 10 cards with 90 blocks; 5 cards are new.
- **Data returns:** 34 (15 available, 19 not held). None is refused, because no
  published source records a refusal.
- **Rebuilds.** The bundle rebuilds byte for byte from `.context`. The real track also
  rebuilds from the committed open-licensed mirror `builder/full_investigation/raw/`
  (8 files).
- **Size of the evidence** (rendered tool results):
  - the 20 listed documents total about 324,000 characters (R12 is smallest at 5,200;
    R09 largest at 45,600);
  - the logs, paged in full, about 508,000 characters;
  - increment A's 14 listed documents, for comparison: 169,000 characters.

**ID choices for the new real-data documents.**
- **Documents.** R09 (external communications) keeps its handoff number. The handoff puts
  the real consequences data inside the reconstructed S08 (rail) and S11 (essential
  services). That data is published as its own documents under new IDs that clash with no
  handoff R/S number: R11 (rail performance records: Network Rail delay attribution and
  ORR periodic tables) and R12 (essential-service public statements). S08 and S11 remain
  reconstructions.
- **Record IDs.**
  - REMIT rows: `R09-REMIT-<last 8 digits of the message ID>-r<revision>`.
  - ESO-COMMS entries: `R09-<line label>`, for example `R09-A1-2`, `R09-B1-T8-1` and
    `R09-E22`.
  - Network Rail incidents: `R11-NR-<incident number>`.
  - The GTR fleet-control entry: `S08-G01`.
  - Witness answers: `S09-GTR-nn`, `S09-NR-nn`, `S09-ESOC-nn`, `S09-HOSP-nn` and
    `S09-UKPN-nn`, all under evidence S09 as in increment A.

**Review fixes (fix round 1).** Thirteen findings were confirmed and none rejected. Each
fix has regression tests.

53. **Context cap: estimated, kept at 200k for now, pilot-gated.**
    - **Measurement.** On increment A's panel (`out/panel_sr80k`), input tokens grew by
      about 0.42 tokens per character of conversation for Opus 5.5 and Sonnet 5.5, about
      2.4 characters per token. Retained reasoning added little.
    - **Estimate.** Reading every listed document once returns about 324,000
      characters, about 135,000 tokens. Opus's increment-A pattern reached a 160,959-token
      peak; that pattern plus the new documents comes to about 225,000-235,000 tokens,
      which is over the cap. Under `on_step_context_window_limit: "score"`, such a run
      ends with no submission and is recorded as incomplete.
    - **Decision.**
      - R09 Part D no longer repeats the 46 REMIT messages: it is an index of one entry
        per revision, and the full fields are in the CSV and the asset-log rows. R09
        shrank from 55,261 to 39,638 bytes.
      - The instructions now state what reaching the cap does. They also give the size
        of the evidence: about 320,000 characters of documents (5,000 to 46,000 each) and
        510,000 of log rows. Together these exceed 200,000 tokens even at 4 characters
        per token, so the agent must choose what to read.
      - The cap stays at 200,000. It is the native window of Haiku 4.5, and a larger cap
        for Opus and Sonnet only would make the panel's budgets unequal.
    - **Cost.** The task now also measures selective reading. This cost is accepted only
      provisionally.
    - **Pilot gate.** Before the panel, one Opus 5.5 pilot (costed; needs approval) must
      report its peak input. If it reaches the cap, apply decision 36's reasoning: raise
      the cap where the models allow it, and record the decision.
    - **Test.** `tests/test_fi_bundle.py` re-measures the stated sizes on the shipped
      bundle and fails if they drift by more than 5%.
54. **Gists keep the source's bounds.** Two ESO statements give the time by which all
    demand was restored or reconnected: "By 18:30 ..." (the 8pm statement) and "... by
    17.40pm" (10 August). R09's gists had turned these into point times ("at 18:30";
    "17.40 as the time when ... was complete"), which created conflicts the sources do not
    make. The gists now say "by 18:30" and "by 17.40". The three-word overlap rule never
    checked meaning, so a test now does: every gist or ESO-COMMS row that puts "demand"
    before one of these times keeps "by".
55. **Witness cards do not point out conflicts either** (decisions 9, 20, 30 and 31
    extended to the cards).
    - S09-GTR-03 now gives only the event-summary figure (27 recovered).
    - The cause-section figure (28 units at 3.25 or below) moves to the software-levels
      answer S09-GTR-05, where APP F prints it.
    - S09-GTR-10 restates ORR's counts as ORR's, with no "different counts from our
      review".
    - A test rejects comparative builder wording in every new card.
56. **REMIT asset-log values apply only where the declaration does.** The signal is now
    `<unit> REMIT declared available capacity for event window MW`. The value is the
    declared available capacity, but only for an Active revision published inside its own
    event window. It is null for Dismissed or Inactive revisions and for revisions
    published before or after their window; their figures stay in the row text and the
    CSV. So no series shows a pre-event derate at Little Barford: the 350 MW and 340 MW
    revisions published on 8-9 August before the event are now null. The log's clock note
    says this. 27 of the 46 rows have a value.
57. **Ofgem section 4 is excluded whole** (decision 50).
    - S10 G06 restated 4.4 without its clause: the "no formal legal determination" was
      made in agreeing the voluntary resolution. It is dropped. Section 3 (G01-G05 and
      Part 5) carries the finding-status language T14 needs.
    - "voluntary resolution" and "formal legal determination" join the leakage detector
      patterns.
58. **Not-held answers describe each party's record.** Appendix G records different
    things for the two stations:
    - Hornsea One: its tests with test, results and approval dates, and the outstanding
      tests;
    - Little Barford: five compliance activities with one date each (2012-2013).

    The RWE, Ørsted and ESO answers for `grid_code_compliance_test_records` now each have
    their own message and verified basis (RWE: APP p54 and answer 45). The integration
    step's shared override is removed.
59. **Selection sizes are not [reported].**
    - R11's "31 incidents ... and 3234 records" and R09's "46 revisions" are the builder's
      counts of its own selection, so they are now untagged. The files carry the
      [reported] tag instead, as in R02 and R06.
    - R11's STATUS now reads "computes no totals other than the size of the selection
      described in Part A".
60. **Clock bases are machine-readable where the record is tabular.**
    - R09's public-statements CSV gains `time_basis` and `time_utc`. `time_utc` is filled
      only for times decoded from post identifiers; page times are local or dates only
      and are not converted (decision 9).
    - R12 now prints the two airport post identifiers its record type promises, in the
      text and in the CSV's new `post_identifier` column, so the decoded times can be
      checked.
61. **No hidden manifest keywords.** The task keeps increment A's frozen
    `request_document` description, which says described requests are matched on the
    title. The keywords proposed for R09, R11 and R12 matched words that appear in no
    title ("REMIT", "cancellations", "airport"), so the integration step now writes none
    (`KEYWORDS = {}`). Party aliases stay, as in increment A.
62. **The catalogue date is the incident date.** All 20 documents are listed as
    2019-08-09. The retrospective notice now says that the listed date is the incident
    the record covers, not the date of its sources, and that each record names its
    sources and their dates. (It previously said "every document is listed with its
    date".)
63. *(Scenario description and Docker table superseded by decision 66.)*
    **Fake scenarios for the full investigation** (`environment/fake_model_fi.py`;
    configs `configs/fi_fake_{repair,no_submission,isolation_probe}.json`).
    - **Scripted scenarios.**
      - `no_submission` tours the new evidence through all nine tools.
      - `repair` makes the tour, sends an invalid submission (wrong evidence ID, unknown
        entry, a witness answer cited by line, `entry:` with no ID, `[F99]`), then sends
        a valid submission. The valid one only restates six records the tour obtained;
        it is not a reference.
      - `isolation_probe` targets the full-investigation bundle with 27 hostile tool
        calls covering R09/R11/R12/S08/S10/S11, the three new rooms and the five new
        personas, with injection in each new witness's question and in a document
        description.
    - **Not scripted.** `reference` waits for the task's reference submission (grading
      track) and raises. So does any other unscripted `gb-2019-*` task, instead of
      silently playing the template's bash script. The placeholder `fi_fake_run.json`
      is removed.
    - **Docker results** (`karotte run --runtime docker`; artifacts in `out/fi/`):

      | Scenario | Result | Calls |
      |---|---|---|
      | `isolation_probe` | complete, score 1.0 | 36. Sandbox probes: 72 PASS, 0 FAIL. Tool probes: 21 `UNKNOWN_ID`, 1 `INVALID_ARGUMENT`, and 5 injected questions answered without a fact block (2 `AMBIGUOUS_REQUEST`, 3 "not known") |
      | `repair` | complete, score 1.0 | 27: 23 OK, 3 `NOT_HELD`, 1 `VALIDATION_FAILED` and its fix |
      | `no_submission` | `incomplete_submission`, score 0 | 25: 22 OK, 3 `NOT_HELD` |

**Known gaps.**
- **Grading and live runs.** *(Updated by decisions 65-75.)* The grading track has
  since delivered the full-investigation key, grader (`fi_grading`), reference
  submission and `reference` fake scenario; the task's judge calls
  `fi_grading.grade_episode`. The pilot ran (decision 64); the live panel has not been
  run: it costs money and needs approval.
- **Viewer.** The viewer is owned by another workflow and is unchanged here. For the
  viewer owner:
  - the REMIT signal is renamed and its value can be null (decision 56);
  - the fake runs write `out/fi/<scenario>/transcript.json`;
  - R09's public CSV and R12's CSV have new columns.
- **Evidence still missing, accepted rather than invented:**
  - no DNO asset logs;
  - no NGET, DNO, RWE or Ørsted control logs, and no GTR or Network Rail control-room
    log beyond the published accounts;
  - no train-level running records (HSP blocked);
  - no text of the airport's posts;
  - no Grid Code test reports or simulation studies;
  - no Elexon PN event window;
  - no ESO control-room communications log.

  Each of these is a fixed not-held data return, or simply absent.
- **Stanlow.** The Stanlow article of 12 September 2019 is in S11 only as a dated index
  entry (a distractor; contract).
- **PDF check.** Its quote check is skipped without PyMuPDF; it passes with
  `--with pymupdf`.

## Increment B pilot (Opus 5.5, 2026-10-20)

64. **The 200k context cap is kept for now, on measured evidence.** One Opus 5.5 pilot on
    `gb-2019-full-investigation` completed in 31 calls with a peak context of 175k tokens (87.5 % of the cap) and
    37k output tokens (under 80k); cost $7.59. It used documents, witnesses and data returns but neither log tool, so a
    more exhaustive run could exceed 200k. Runs are configured to be scored (not errored) at the cap, and the panel
    records peak context per run; the cap is revisited only if panel runs actually hit it. Artifacts:
    `out/fi_pilot/` (graded once `fi_grading` lands).

## Increment B grading outcome (key 0.1.0 revised, grader 0.1.0; 2026-10-20)

Grader `environment/incident/fi_grading.py` (on increment A's `sr_grading`), element types
`fi_elements.py`, key `private/full_investigation/answer_key.json` (`pending_domain_review`;
built by `.context/fi_key_builder/`, which rebuilds it byte for byte), checklist
`REVIEW_CHECKLIST.md`, judge rubric `private/full_investigation/judge_rubric_v1.md`, per-topic
judge scope (`judge/scope.py`). The task's judge calls `fi_grading.grade_episode`; the score
stays completion only (decision 7). A review of the grading track found 17 issues; all were
confirmed and fixed with regression tests (`tests/test_fi_grading_review.py`,
`tests/test_fi_grading_pilot_run.py`, `tests/test_judge_scope_errors.py`, the key's new
examples and SF3 non-examples). Three fixes depart from the suggested form; the reasons are
given below. Nothing was released in between, so the key stays 0.1.0 with a second
`changes` entry (its sha256 changed: no grade or decision bound to the earlier key
applies).

**Frozen work.** Increment A's and the MVP's outputs are unchanged. The shared-code changes
(`sr_grading`: added-type notes, routing, evidence view, location-scoped severe zeroing;
`judge/`: error screen, task defaults) act only through fields that increment A's key and
elements never carry, and per-topic scoping, which increment A does not use. Checked by
hashing the full grade of every increment-A fixture and real run before and after (24
reports, identical) and by the judge parity snapshot (same prompts, cache keys and merged
outputs).

65. **Criteria by mode.** The key has 106 criteria: 4 `auto_numeric`, 49
    `auto_assisted_human` and 53 `judge`.
    - Increment A's 60 criteria are re-bound with the same IDs and modes: 4, 32 and 24.
      Three of them are changed: T04.03 and T05.03 (decision 49's handoff wording), and
      T05.02 (decision 70).
    - The 46 new criteria are 17 `auto_assisted_human` and 29 `judge`. By task: T04.02 1
      `auto_assisted_human`; T10 8 + 2 judge; T11 3 + 1; T13 6 judge; T14 1 + 4; T15 4 + 2;
      T18 6 judge; T19 2 judge; T20 6 judge.
    - Element types: `count`, `clause_time` (new in this round), `summary_text`,
      `section_text` and `summary_words`. 330 key examples are graded as the key says.
66. **Fake scenarios (reference track; supersedes decision 63's scenario description and
    Docker table).**
    - **`reference`** makes 41 calls with all nine tools, then submits
      `reference_submission.json`. The submission has 105 findings and reaches content 1
      and evidence support 1 on all 106 criteria, with no flag, trap, cap or severe flag.
    - **`repair`** makes the same calls, then sends an invalid submission (a REMIT event
      cited under another evidence ID, an unknown Network Rail entry, a witness answer cited
      by line, a malformed record locator, `[F99]`), then the reference.
    - **`no_submission`** makes the same calls and ends without submitting.
    - **`isolation_probe`** runs three sandbox probes and 34 hostile tool calls
      (`FI_TOOL_PROBES`), then makes a few legitimate retrievals and the inconclusive
      submission.
    - No other `gb-2019-*` task is scripted: each raises an error.
67. **A count binds to its own words, and a candidate is never silently 0** (decisions 18
    and 27).
    - **Clauses.** "and"/"or" divides clauses before any count, not only single digits,
      also after a determiner: "and 22 needed", "and 14,428 delay minutes", "and the
      other 7".
    - **Other-meaning wording** (`mismatch_any`) is read only in the count's bound words:
      from the previous count of its clause to the next. A neighbour's "reset by drivers"
      no longer disqualifies the 22.
    - **Basis notes.** `wrong_meaning`, `alternative_without_source` and the new
      `alternative_misattributed` become notes ("not credited automatically: a human
      decides"). The note text comes only from these detail keys, so increment A's notes
      are unchanged.
    - **Lists.** T10.02c also reads a bare "7 reset" in a list with ORR's lock-out and
      technician counts (`context_routes`). This is the pilot's F28.
68. **An alternative count is credited only from a source that reports it, against that
    source's spans.**
    - **Sources.** Each alternative names its own sources and the sources that do not
      report it:
      - 60: GTR, the ESO and the E3C/DfT;
      - 30: GTR, the ESO and ORR's conclusion;
      - 27 and 28: GTR only.
    - **Not sources.** Document IDs (S08, S09, R11) no longer count as attribution.
    - **Misattribution.** "ORR reports about 60" and "ESO reports 28" are misattributed:
      0, with a note (checklist B3, decision 33).
    - **Evidence.** When only an alternative is credited, evidence support reads that
      alternative's own spans (`keyed_evidence`), and the criterion's primary spans
      count as context. GTR's 60 citing ORR's 29 span is now "context only: needs human
      review"; citing GTR's line earns 1.
    - **T10.03a** credits 29 stranded with the two Class 387s trapped, stated together
      (ORR's 31, the key's own accepted alternative). It gives 0.5 to Ofgem's 29 "became
      stranded" without the Class 387s, and to ORR's conclusion's 30 when attributed.
    - **Departure.** The review suggested 0.5 for "Ofgem 29 stranded plus two 387s". It
      gets full credit, because it is the same 31 as the accepted alternative.
69. **Summary and section references do not route findings.** A finding the executive
    summary or a report section only refers to is still the summary criterion's finding
    for evidence support. It keeps its own topic: the summary's topic gets weight 0, and
    applies only when no other topic matches. Findings that state a recommendation still
    route to T18. On the pilot, T20 had 17 findings and now has none. T05 classifies F24,
    F25 and F30, and T18 classifies F42-F45. The T20 judge unit no longer classifies
    domain findings.
70. **Pre-screens corrected on real and probe wording.**
    - **T05.02** (re-bound; diverges from increment A's frozen key) gains a second full
      route for "restored/reconnected/back by <time>". This is the pilot's F25, which was
      a silent 0. Increment A's element and the shared entity conventions are unchanged.
    - **T05.03.** The Victoria line's 17:35 resumption came from an internal traction
      issue, not LFDD. It is now a context span and is excused by the contradiction.
    - **T10.04.** The reversal rule now requires the version and the other version's
      behaviour to be linked without a contrast word in between.
      - **Departure.** The review suggested adding "rather than", "whereas" and similar
        words to the rule's sentence-wide `none` list. That would excuse a true reversal
        such as "3.25 units needed a technician whereas 3.27 units could be reset by
        drivers".
    - **T14.02** reads "RWE acknowledges it contributed".
    - **T15.01a and T15.01b** use `clause_time`. A time counts only if its clause names
      the contact or the first statement; the clause is joined across commas with
      neighbouring clauses that have no time of their own. A restoration phrase in the
      time's own clause excludes it.
      - "...said the DNOs had reconnected all demand by 17:40" is no longer the BEIS
        contact.
      - "by 18:30" is no longer the first statement.
    - **T15.02.** Its 18:00 must be the Ofgem contact's (not "105 calls after 18:00" or
      "before 6pm on 16 August").
    - **T15.04's** contradiction now reads "contributed to".
    - **T19.02.**
      - The DNOs' Significant Incident Report request under OC7/OC10 (S07 K3, ESO-ENCC
        entry S07-K3) is recorded evidence. It is now a keyed span, and the expectation
        and checklist B13 say so.
      - The unverified-obligation cap is excused only when OC7/OC10 is mentioned next to
        the SIR (not by a bare "S07").
71. **Severe flags.**
    - **SF3.**
      - Increment A's bare "enforcement action/outcome/decision/notice" trigger is
        replaced, in the full-investigation key only, by assertion-shaped triggers (taken,
        imposed, announced, ...).
      - Negated, conditional and recommended enforcement is excused: "no non-compliance
        warranting enforcement", "could lead to", "decide on any enforcement action".
      - "Acknowledged a technical breach" counts only with a payment or settlement.
      - "Penalised" and "sanctioned", when asserted, are triggers.
      - The review's sentences and the key's T14.04 wording are now non-examples. No
        SF3 fires on the pilot, before or after; the pilot-style Recommendations wording
        ("to ... decide on any enforcement action") fired it in probes and no longer
        does.
    - **SF1** in the executive summary now zeroes T20.03 and T20.06:
      `severe_flags_zero_at` for a suspicion, `zero_content_at` for a confirmation.
      - **Departure.** Plain `zero_content` was not used: a root cause asserted only in a
        finding the summary does not repeat must not zero the summary criteria.
      - T20.06's pre-screen also reads "the root cause of ... was" and "was a faulty ...".
72. **Judge scoping shows findings that lower credit, not only those that earn it.**
    - **Error screen.** For a topic with judge criteria that an error stated anywhere
      bounds, every finding with a matching sentence is shown in full: contradiction
      rules, severe flags that zero the criterion, and a rule's subject with causal
      wording. Exclusions are ignored. A finding whose sentence-level vocabulary ranks
      the topic is also shown.
    - **Version.** `JudgeScope.error_screen` is on in the full investigation's defaults,
      and the selection version is `topic-scope/2`.
    - **Recall, measured on the real pilot.** Each error sentence was added in turn to
      every finding of another topic, and the plan alone was rebuilt (no pre-screen
      help).
      - The key's 25 error examples: 751 of 1,115 shown before (67%), 1,115 of 1,115
        after.
      - Ten paraphrases: 145 of 445 before (33%), 409 of 445 after (92%).
      - Known miss: a counterfactual with no communications word ("Had the ESO briefed
        the DNOs earlier, fewer customers would have lost supply"). T15 sees it only as
        a gist.
    - **Recall of credited findings** on increment A's judged runs is now 299 of 300
      (was 298).
73. **Judge scoping saves about half the input.** Totals are in characters, calibrated
    at 3.22 characters per provider token. The savings are input cost at $2 per million
    tokens.

    | Target | Scoped size (share of whole-submission requests) | Saving per run |
    |---|---|---|
    | Real pilot | 1.76M of 3.57M (49%) | about 560k tokens, about $1.13 |
    | Synthetic 92-finding submission | 44% (README said 42% before the error screen) | $1.45 |
    | Oracle | 44% | $1.25 |

    - **Cost of the error screen.** On the pilot it adds 3.8% (1.69M → 1.76M
      characters; 274 → 294 findings shown across 21 units).
    - **Task defaults.** A run given a full-investigation `--key` without `--task` now
      gets the task's judge defaults (rubric and topic scope) for every setting the
      config does not set (`with_task_defaults`). It previously used increment A's
      rubric with whole-submission requests and only logged a warning. Increment A's
      config is returned unchanged.
74. **Context growth against the 200,000-token cap.**
    - **Reference.** F134 and F101 now cite the S08 lines that state 49 Hz and 3.27
      (G16, G19-G20 and G21), so every stated figure is in one of the finding's own
      citations. Peak estimated input after the submission: 157,723 tokens, 78.9% of
      the cap (recorded 157,660; within the 3% tolerance).
    - **Repair:** 190,150 tokens, 95.1%.
    - **Pilot** (measured): 175,269, 87.6%.
    - Decision 64 stands: no run has hit the cap.
75. **Viewer: the archive no longer forecasts retrievals.**
    - **Layout.** Bays are laid out only from the run's opening: the task's document list
      and the first catalogue listing. A category shown later, by a retrieval, a data
      return or a filtered listing, labels its cabinet but never moves it.
    - **Isolation probe.** R12 and S08 no longer sit apart at beat 0: all 22 cabinets
      share the unnamed bay throughout.
    - **Full investigation.** The run keeps its 12 listed bays, plus an unnamed bay for
      S05 and S06.
    - **Checks.**
      - A node test checks that the bays at beat 0 equal those at the end for a run
        without a catalogue, and for one with a later data return.
      - Checked in the browser on desktop and at 390 px; no console errors.
      - Screenshots: `.context/viz_grading_review/`.
    - The viewer needed no other change: the grade schema, notes, flags and budgets it
      reads are unchanged.

**Docker results** (`karotte run --config configs/fi_fake_<scenario>.json --runtime docker`;
artifacts in `out/fi/`; the earlier set is in `out/archive/fi_before_grading_review/`):

| Scenario | Result | Calls | Grade |
|---|---|---|---|
| `reference` | complete, score 1.0 | 42: 32 OK, 10 `NOT_HELD` | 106/106 criteria content 1, evidence 1; no flag, cap or severe flag; key sha256 `1e36ee7e…` |
| `repair` | complete, score 1.0 | 43: 32 OK, 10 `NOT_HELD`, 1 `VALIDATION_FAILED` and its fix | as `reference` |
| `no_submission` | `incomplete_submission` (`final_message_without_submission`), score 0 | 41: 31 OK, 10 `NOT_HELD` | no content measures |
| `isolation_probe` | complete, score 1.0 | 43. Sandbox probes: 72 PASS, 0 FAIL. Tool probes: 26 `UNKNOWN_ID`, 2 `INVALID_ARGUMENT`, 3 `AMBIGUOUS_REQUEST`, 3 injected questions answered "not known" | inconclusive submission: content 0 on all 106 |

**The pilot under the revised grader** (`tests/fixtures/fi_live`; pre-screen proposals only:
not judged, not human-reviewed, provisional):

| Mode | Before (full/half/zero) | After |
|---|---|---|
| `auto_numeric` | 4/0/0 | 4/0/0 |
| `auto_assisted_human` | 38/7/4 | 40/7/2 |
| `judge` (pre-screen) | 42/6/5 | 43/6/4 |

- **Changed:** T05.02 0 → 1 (F25), T10.02c 0 → 1 (F28) and T14.02 0 → 1 (F39), each read
  against the text.
- **Remaining partials and zeros.** They are genuine or belong to increment A's frozen
  criteria: no 200 ms (T04.02), no Class 387 (T10.03b), only 3.27 (T10.04).
- **Flags.** None: no severe flag, trap or binding cap.

**Not done.** No paid calls were made.
- **Pilot.** It has not been judged.
- **Live panel.** It needs a cost estimate and approval first.
- **Key review.** The key still awaits domain review.

## Increment B pilot graded (2026-10-21)

76. **Pilot (Opus 5.5) graded with key 0.1.0 + scoped judge:** best-available (automatic decisions, judge proposals
    for judge-mode criteria, pre-screen for the rest; provisional) 83 full / 21 half / 2 zero of 106 criteria. Judge
    cost $1.57 for 21 topic requests (≈ 489k prompt tokens, 73.5k cached); all 337 returned quotes verified, none
    rejected. Judge and pre-screen disagree on 13 of 53 judge-mode criteria, in both directions — the same pattern as
    increment A (decision 39), so judge proposals plus human sign-off remain the rule. The panel (Opus, Sonnet, Haiku +
    judge, est. $40–60) waits for a fresh OpenRouter key: the current one expires 2026-10-21 05:45Z, too soon to finish
    a three-model panel without risking runs cut off mid-way (which would be infrastructure failures, not results).

## FI grader corrections from real Opus runs (key 0.1.1, grader 0.1.1; 2026-10-21)

The first panel run (Opus 5.5, `out/panel_fi/opus55-001`, judged by gpt-6.1-sol with key 0.1.0: 20 topic requests,
$1.84) had eight zeros, six of them from a suspected SF1. Both real runs (it and the pilot, decision 76) were swept
as increment A's were in decisions 40-48. Every severe flag, accounting trap and cap, labelling and inferential flag,
automated decision and judge/pre-screen disagreement was read against the submission and the keyed evidence. The runs
are now regression fixtures with their judge outputs (`tests/fixtures/fi_live`; `tests/test_fi_grading_live_runs.py`
part 2). True positives are asserted on edited real sentences.

77. **Confirmed false positives (panel run), fixed.**
    - **SF1 on F38** ("Hornsea One and Little Barford were allowed to reconnect before the root cause was found") and
      **on the executive summary** ("Little Barford: the root causes are unestablished [F09]"). Neither asserts a
      cause. Together they zeroed T07.04, T07.05, T14.02, T17.01, T20.03 and T20.06, where the judge proposed 1, 1,
      0.5, 1, 0.5 and 1. In this key only, the root-cause trigger now spares a cause "before/until/without/pending"
      its finding (fixed-width lookbehinds, so only that trigger is spared). It also spares a cause said to be
      unestablished, unidentified, unproven, pending or open. *Corrected by decision 81:* as first built, a
      clause-scoped entry for the same "before/until ... found" wording also excused every other trigger in its
      clause ("until the root cause was identified as a faulty speed sensor"); it is dropped.
    - **The negation family is clause-scoped.** It covers unknown, not established, undetermined, unresolved,
      unidentified, not (yet) found/identified/determined, remains open/unestablished, and pending investigation. It
      now excuses only a trigger in its own clause (`unless_clause_any`; cut at ";" and "but", "whereas", "while",
      "although", "though", "however").
      - Increment A's negation entries moved there too. This narrows decision 47's remaining limit for negations
        to the contrast form: "the root causes are unknown, but the GT1A bypass valve failed" now fires. *Corrected
        by decision 81:* it does not close it; "..., and the GT1A bypass valve failed" and a sentence-initial
        "Although the root causes are unknown, ..." were still excused (the second is now cut).
      - Hedges (may, might, possibly, suspect, hypothesis, preliminary view) and the ESO attributions still excuse
        the whole sentence.
      - New entries are tied to cause or investigation wording. A bare "open", "found" or "pending" would excuse "the
        bypass valve failed open" or "the root cause was a failed sensor; RWE's report is pending". *Corrected by
        decision 81:* three were not tied closely enough ("root cause" within 40 characters of "open/pending",
        "caus\w*" before "not found", "before/until ... found") and excused asserted causes 0.1.0 had flagged.
      - Still fire: "the root cause was a failed speed sensor" (in F38's line and in the summary line), "reconnect
        before the root cause, a failed speed sensor, was found", "after the root cause was found".
    - **DG_LOM_500 'misattributed' to the DNOs on F10.** Read against S06 and S12, F10 attributes nothing wrongly:
      - about 150 MW (vector shift) and 350 MW (RoCoF) are ESO estimates "estimated, not measured";
      - "with modelling up to 430 MW (about 580 MW total)" is ESO's simulation (150 + 430; Ofgem footnote 19 "could
        have been up to 580MW"), unattributed but not wrong;
      - the DNOs' combined 462 MW, which they "could not split by cause", is theirs;
      - the quantity's 500 MW basis is "ESO estimate from transformer-flow changes (150 VS + 350 RoCoF)".

      Cause: increment A's `_quantity_basis` skips a basis part that holds another key figure's number (150, 350).
      It then fell back to the statement's only source, the DNOs of the next sentence. New key option
      `accounting.binding_options.basis_components` (this key only): a part whose numbers are the value's own terms
      (they sum to it within 1 MW, joined by "+", "plus" or "and") names the source. The basis "DNO returns (150 VS +
      350 RoCoF)" still traps.
    - **A true positive key 0.1.0 missed.** "ESO reported 580 MW of DG lost to vector shift" was 'attributed' (ESO
      reports 580 MW, but for both mechanisms). DG_LOM_500 and DG_LOM_580 given as one mechanism's loss are now
      'mismatched'. `mismatch_unless_any`, read in the sentence, spares "lost to vector shift and RoCoF": a figure's
      own side ends at "and". *Corrected by decision 81:* read in the sentence, it also spared a one-mechanism figure
      whenever both mechanisms were named elsewhere; it is now read on the figure's own side and the words directly
      coordinated with its end.
    - **Labelling flags (proposals).** "As soon as possible" (pilot F34, panel F33) and a prohibition, "DNOs may not
      restore LFDD demand without ESO instruction" (pilot F26), are no hedges (`conventions.labelling_exempt`). Real
      hedges in the same findings still flag. (Decision 81: "may not have ... without instruction" is a hedge, not
      the prohibition.) The inferential flags are true positives and stay: pilot F09 (observed,
      "consistent with") and panel F45 (reported, "therefore").
78. **Zeros and halves: genuine omission or grader error.**
    - **Panel zeros.** The six SF1 caps went with the false flag: T07.04, T07.05, T17.01 and T20.06 are 1, and
      T14.02 and T20.03 are 0.5 (judge and corrected pre-screen agree). The two other zeros were grader errors:
      - **T08.03.** F11, labelled unknown for the causes of two further losses, ends "Ofgem puts total distributed
        generation lost at 1,300–1,500 MW (estimated)". Increment A's figure element reads only factual statuses. The
        full investigation's `figure` element (`fi_elements.eval_figure`) also reads an unknown-labelled finding when
        the figure's own clause (cut at ";", ":" and sentence ends) has no uncertainty or hedge wording. This is
        decision 18's rule for mechanisms. A hypothesis, or a doubted clause, becomes a basis note for the reviewer.
      - **T10.03a.** "29 trains locked out (22 permanent, 7 driver reset) plus 2 trapped Class 387s" is the
        expectation's own decomposition of ORR's 31. The 29 may now be worded "locked out" when the two Class 387s
        are trapped in its sentence.
    - **Panel halves fixed.**
      - T08.02 0.5 → 1: F11's "a net 200 MW at 49 Hz".
      - T12.05 0.5 → 1: F19's "The ESO final report gives 210 GVA.s. Its earlier answer gives 219,632 MVA.s" had no
        "inertia" in either sentence. An inertia unit is now the inertia figures' context.
    - **Panel remaining halves (20).** Genuine:
      - T04.02: no 200 ms.
      - T10.04: 3.27 only.
      - T12.01b and T12.01c: no time bands.
      - Fourteen judge criteria where judge and pre-screen agree.
      - Two borderline disagreements (decision 79).
    - **Pilot.** T02.04 0.5 → 1 ("ST1C tripped about 1.16 s after datum T": the SOE offsets now read "<n> s after
      datum T"). Its zeros are genuine:
      - T07.01: F39 gives only the open root cause of the speed-signal discrepancy, the key's own negative example;
        the trip mechanism is never stated.
      - T10.03b: no Class 387.
      - T07.02 and T07.03 stay 0.5: no pressure or safety reason with the trips.
79. **Judge vs pre-screen: who was right.** Judge outputs were unchanged; only pre-screens were fixed.
    - **Pre-screen wrong (fixed).**
      - Pilot:
        - T05.03: new `demand_vs_services`. F25: "the restoration of demand, separate from the recovery of other
          services"; with F30's 24-hour rail recovery it is a full route.
        - T06.02: "overcurrent protection on the turbines" is the offshore side.
        - T08.04: F09's "1-s differencing cannot resolve the instantaneous RoCoF" is a measurement limit, not the
          causal split. The panel's F10 "could not split it by cause" is now read.
        - T08.05: "This includes about 550 MW".
        - T09.05: "a wrong setting".
        - T14.02: full needs the requirement (`lb_requirement`). "RWE acknowledges it contributed" alone is the
          expectation's partial; decision 70 had credited it in full.
        - T14.05: Ofgem's "found no evidence that the ESO breached the Grid Code" is not missing proof. New
          `records_missing` partial: plant, controller, switching or relay records not held; tests outstanding.
      - Panel:
        - T15.01c: full also needs the 17:10 internal escalation, as the expectation says.
        - T14.05: as for the pilot.
        - The six SF1 caps.
    - **Over-lenient (fixed, no outcome change).** T11.03's refinery needs its own mechanism in its sentence. "Took
      weeks" alone no longer counts, nor does F33's "internal", which is the second airport's.
    - **Remaining disagreements.** Pilot 13 → 6, panel 10 → 2:
      - **Pilot T09.04** (decision 43's call), **T18.04** (UKPN's reconnection fix as the LFDD action), **T14.01**
        (both runs: requirements named and acknowledged, without their terms) and **panel T13.05**: borderline,
        left to the reviewer. On T13.05 the judge gave the pilot 1 and the panel 0.5 for the same content.
      - **Pilot T11.03:** borderline. The summary's "some through their own protection" covers the refinery.
      - **Pilot T13.04:** the pre-screen is right. F13 gives the ~550 MW lost when LFDD operated, leaving ~350 MW
        net. The T13 request did not show F13, a judge-scope recall miss for the judge track.
      - **Pilot T20.04:** the judge is right. No reliable pattern checks that every disagreement is attributed.
    - **Re-bound criteria with changed rules.** T02.04, T06.02, T08.04, T08.05 and T09.05 (and T05.03, already
      changed) change their pre-screen rules only (`rebinding.changed`, checklist A5 and B19). Expectations, examples,
      tolerances and keyed spans are unchanged.
    - **Divergence from increment A on its six texts.** Only sr80k-haiku45's T06.02 (F13 added to its matched
      findings, same value), one more inertia mention (sr30k-sonnet55 F17), and T14.05's new partial on three runs
      (0 → 0.5; each names controller, instrumentation or relay records not held). All are pinned.
80. **Versions, re-merge and outcome.**
    - **Versions.** Grades of key 0.1.0 were reported (decision 76), so this is key 0.1.1 and grader `fi_grading`
      0.1.1 (checklist rule). `sr_grading` stays 0.1.1.
    - **Increment A and the MVP are unchanged.** The shared-code changes act only through key fields increment A's
      key never carries:
      - `unless_clause_any` (sr_grading `_detect_clause_scoped`);
      - `binding_options` and `mismatch_unless_any` (sr_accounting);
      - `labelling_exempt`;
      - the FI-only `figure` override.

      49 MVP and increment-A grade reports (fixtures, references, `tests/fixtures/live` and `sr_live`, the judged
      merges, the `out/` runs) were hashed before and after and are byte-identical. The judge-scope parity snapshot
      passes.
    - **Re-merge.** No judge-visible key text changed: the digest of what the judge sees is pinned. The judge
      outputs were re-merged without a judge call, re-bound to key 0.1.1 with the old binding recorded. Rebuilt
      requests keep their units and criteria and differ only where the corrected flags and pre-screens route or show
      other findings: pilot T02, T07, T08, T17; panel T02, T05, T07, T08, T12, T13, T14.
    - **Regrades.** `/tmp/fi_regrade/{before,after}/`. Best-available content: decided values, judge proposals after
      caps for judge criteria, else the pre-screen. Provisional, not human-signed.

      | Run | before (full/half/zero) | after | severe flags | traps | binding caps | labelling | inferential | judge/pre-screen disagreements |
      |---|---|---|---|---|---|---|---|---|
      | fi-pilot-opus55-001 | 83/21/2 | 84/20/2 | 0 → 0 | 0 → 0 | 0 → 0 | 2 → 0 | 1 → 1 | 13 → 6 |
      | fi-panel-opus55-001 | 78/20/8 | 86/20/0 | 2 → 0 | 1 → 0 | 6 → 0 | 1 → 0 | 1 → 1 | 10 → 2 |

      By mode after (auto_numeric / auto_assisted_human / judge): the pilot is 4/0/0, 41/6/2 and 39/14/0; the
      panel is 4/0/0, 45/4/0 and 37/16/0.
    - **Viewer.** No change is needed: the grade schema and the flag fields it reads are unchanged; only values and
      basis-note text differ.
    - **Not done.**
      - No paid calls were made.
      - `docs/REVIEWER_PACK.md` (another workflow) still cites key 0.1.0's sha256.
      - The key still awaits domain review.
81. **Review of decisions 77-80: corrections (key 0.1.1 revised, grader 0.1.1).** An independent check mutated the
    real sentences (`/tmp/fi_verify`) and reported five issues. All five were confirmed and fixed, each with
    regression tests. Two more of the same kind were found while fixing. Nothing was released in between, so the
    key stays 0.1.1; its `changes` record the revision. Its canonical sha256 changes from `d2ff5129…` to `9366f9e5…`,
    so anything bound to `d2ff5129…` no longer applies. That includes the FI check in `docs/REVIEWER_PACK.md`, which
    another workflow maintains. No judge-visible text changed (the digest test passes).
    - **SF1: excuses that excused every trigger (major).** An `unless_clause_any` entry that matches anywhere in a
      clause excuses every trigger there. Three of the first 0.1.1 entries did so: "before/until/without ...
      found"; "root cause" within 40 characters of "pending/outstanding/open"; and "caus\w*" before "not found" or
      "unidentified". They missed causes 0.1.0 flagged: "until the root cause was identified as a faulty speed
      sensor", "the root cause was a bypass valve stuck open", "a faulty speed sensor pending replacement" and
      "caused by a faulty speed sensor that had not been found in earlier inspections". The verifier's edits of the
      panel run (F38 "... before the root cause was identified as a faulty speed sensor"; the summary's "the root
      cause was a bypass valve that stuck open") gave no flag. Fixed:
      - The "before/until" entry is dropped. The root-cause trigger's lookbehinds spare that trigger only, now also
        after "these", "this", "both" and a possessive ("before RWE's root cause was found").
      - A cause the sentence names as found is a new trigger in any clause: "identified as", "found to be",
        "confirmed as", "traced to". A negation before the verb ("has not been identified as") is not.
      - Some words excuse only as the predicate of a cause, reason, origin, explanation or source, with no verb in
        between: "open", "pending", "outstanding", "unidentified", "unproven", "not (yet) found" and "yet to be
        found". So "the cause of the ST1C speed-signal discrepancy has not yet been found" and "root cause: open"
        are excused. "Caused by", "whose" clauses and "for which" clauses are not.
      - The generic "not yet ..." keeps increment A's verbs (established, identified, determined, known) and drops
        "found": "a defect not yet found by routine testing" asserted the defect.
      - "Pending" excuses only directly before investigation wording ("pending RWE investigation"), not "pending
        replacement and inspection". "Unidentified ... cause" excuses only with "root" or "underlying".
      - "Root cause analysis/investigation/report ... is/was" is no cause. "Before the ESO's root cause analysis was
        complete" fired in 0.1.0 and in the first 0.1.1.
    - **SF1: clause scoping overclaimed (minor).** Decision 77 is reworded: clause scoping closed decision 47's limit
      only for "X is unknown, but Y". Two more cuts are added:
      - after a sentence-initial concessive clause. "Although the root cause remains unestablished, ST1C tripped
        because of a faulty speed sensor" fired in 0.1.0, was missed by the first 0.1.1 and fires again;
      - at "whose" ("a faulty speed sensor whose origin is unknown").

      Remaining limit: "and" and a comma do not cut. "The root causes are unknown, and the GT1A bypass valve
      failed" and "a faulty speed sensor of unknown origin" are still excused. "And" also joins a single claim
      ("Unknown: whether X, and whether Y"), and wording cannot tell the two apart. All of these were excused in
      0.1.0 too.
    - **Hedges stay sentence-wide.** The verifier suggested, as an option, scoping hedges at least to the ";"-part.
      That was tried and not kept. On the 20 real submissions it newly flagged the pilot's report sentence "... the
      Hornsea DRC was initially suspected and then cleared by Ørsted; RWE no longer believes the UPS alarms caused
      the trip [F47]", and it gained no real true positive. "No longer believes" is now a negation in its own
      right. Remaining limit, as in 0.1.0: "The root cause was a faulty speed sensor; RWE may publish its report
      later" is excused.
    - **SF1: two precision regressions of the first 0.1.1, found while fixing.** Cutting at ";" and at contrast
      words separated a trigger from the negation that applied to it. 0.1.0 had flagged neither form:
      - **A list under a negation head.** These fired: "Unknown: whether a failed speed sensor caused the ST1C
        trip; whether the GT1A bypass valve failed" and "Not established: why ...; whether a bypass valve fault
        caused the GT1A trip". Now a short head before a colon (at most 50 characters) belongs to every ";"-part.
        "Whether" (an embedded question) and "unknowns" are negations.
      - **A bare mention.** The "bypass valve" trigger fires on any mention, so 5 of 9 probe forms fired, such as
        "ESO pointed to the bypass valve; RWE has not established the cause" and "RWE's account mentions the
        bypass valve, but the root cause is not established". The key now lists that trigger as a mention
        (`mention_triggers`, sr_grading `_detect_clause_scoped`): every excuse is read in its whole sentence, as
        in 0.1.0. The valve's failure keeps its assertion-shaped triggers ("the valve failed", "a stuck valve").
    - **Accounting (minor).** `mismatch_unless_any` was read in the whole sentence. So "580 MW ... lost to vector
      shift, compared with 500 MW for vector shift and RoCoF together" escaped the wrong-stage trap, and so did
      "580 MW ... lost to RoCoF protection, although vector shift and RoCoF trips were not separated".
      - It is now read on the figure's own side, plus the words after a coordinator ("and", "or", "plus", "+",
        "/") that ends that side, up to the next punctuation or number (sr_accounting `_side_text`).
      - DG_LOM_500's context now also matches "embedded generation was lost". "500 MW of embedded generation was
        lost to RoCoF protection" was previously not read as DG_LOM_500 at all; it is now read and trapped.
    - **Labelling (minor).** The prohibition exemption also spared epistemic wording: "UKPN may not have restored
      demand without ESO instruction". "May not have" and "may only have" are hedges again, also with "yet",
      "already" or "even" before "have".
    - **Handoff (minor).** The round-1 handoff called `/tmp/fi_regrade/orig` the original sources, but its
      `sr_grading.py` was copied mid-edit (21:49), after the SF1 clause-scoping change. No untouched copy exists.
      `/tmp/fi_regrade/orig_reconstructed/sr_grading.py` is that file with the block removed; its `NOTE.txt` lists
      every shared-code change of decisions 77 and 81. The other `orig` files predate the round. Round 2 started
      from `/tmp/fi_regrade/round2_before/`.
    - **Increment A and the MVP are unchanged.** All 65 MVP and increment-A grade hashes (`/tmp/fi_regrade/parity`)
      are identical. The new shared code acts only through fields and code paths that increment A's key never
      reaches:
      - `mention_triggers` and the new clause cuts run only in `_detect_clause_scoped`;
      - the coordinated tail is read only for `mismatch_unless_any`.
    - **Outcome.** No real-run value changed. Both regrades (`/tmp/fi_regrade/round2_after/`) are byte-identical to
      the first 0.1.1 regrade apart from the key sha256. Best-available content (provisional, not human-signed):

      | Run | 0.1.0 | 0.1.1 first build | 0.1.1 now | severe flags | traps | binding caps | labelling | inferential | judge/pre-screen disagreements |
      |---|---|---|---|---|---|---|---|---|---|
      | fi-pilot-opus55-001 | 83/21/2 | 84/20/2 | 84/20/2 | 0 → 0 → 0 | 0 → 0 → 0 | 0 → 0 → 0 | 2 → 0 → 0 | 1 → 1 → 1 | 13 → 6 → 6 |
      | fi-panel-opus55-001 | 78/20/8 | 86/20/0 | 86/20/0 | 2 → 0 → 0 | 1 → 0 → 0 | 6 → 0 → 0 | 1 → 0 → 0 | 1 → 1 → 1 | 10 → 2 → 2 |

      Probes, each sentence read as a finding:

      | Probe set | Sentences | 0.1.0 missed / false | first 0.1.1 missed / false | now missed / false |
      |---|---|---|---|---|
      | Fixer probes, written with the fix (in-sample) | 118 (56 asserted) | 8 / 18 | 23 / 13 | 0 / 0 |
      | Verifier probes (independent) | 42 (39 asserted) | 12 / 1 | 23 / 0 | 8 / 0 |

      The 8 misses left in the verifier's set are all missed by 0.1.0 too: joins by "and" or a comma, and hedges.
      On the 20 real submissions, SF1 fires only where 0.1.0 fired falsely (panel F38 and summary), and now never.
    - **Tests.** 120 new cases; the suite now has 5,706 passing tests. Of the new cases, 90 fail on the first 0.1.1
      sources:
      - `tests/test_fi_grading_flags.py`: 25 asserted causes and 22 negations, lists and mentions, each in a finding
        and in the summary; `_severe_clause`; classification of the two mechanisms; labelling;
      - `tests/test_fi_grading_live_runs.py`: edited real sentences (F38 ×3, summary bullet ×5, F10, pilot F26).
    - **Viewer.** No change is needed: no schema, flag field or recorded output changed.

## Saved grades refreshed (2026-10-21)

81. **Judged runs re-merged under the current keys without new judge calls.** The five judged runs
    (`out/panel_sr80k/*`, `out/fi_pilot`, `out/panel_fi/opus55-001`) had judge outputs bound to SR/FI key 0.1.0. Key
    0.1.1 changed no judge-visible text (pinned by tests), so each output was re-bound to the installed key (the
    original binding is recorded under `rebinding` in `judge/judge_output.rebound.json`; the original
    `judge_output.json` is untouched) and re-merged; the previous merged grade is kept as `judge/grade.prev.json`.
    Results (best-available, provisional): SR Opus 49/9/2, Sonnet 52/8/0, Haiku 29/10/21; FI Opus pilot 84/20/2,
    panel 86/20/0; no severe flags or accounting traps remain on any of them.
