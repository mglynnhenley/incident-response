# Full-investigation grading fixtures (builder-made)

Fixtures for task `gb-2019-full-investigation`, graded with the full-investigation key
(`private/full_investigation/answer_key.json`) on bundle `bundles/full_investigation`. They
are not bound to a key version: `tests/test_fi_reference_fixtures.py` grades them with the
installed key and checks the automated outcomes below. Regenerate with
`uv run --frozen python tests/fixtures/fi/build_fi_fixtures.py` after changing the
reference submission (`src/environment/tasks/gb_2019_full_investigation/reference/reference_submission.json`)
or increment A's `tests/fixtures/sr/submissions/incorrect.json`, whose findings X01-X15
the `incorrect` fixture reuses.

`submissions/`:

| File | What it is | Expected automated outcome |
|---|---|---|
| `correct.json` | byte copy of the reference submission | every criterion at content 1 and evidence 1 (decided or proposed); no flag |
| `uncited.json` | the reference with every citation (and so every derivation) removed | content proposals unchanged; evidence support 0 (decided) wherever a finding is matched; every finding flagged uncited |
| `incomplete.json` | initiating event, frequency and rail findings only | T01, T03, T04 and T10 covered (with T13.05, T16.02 and the summary criteria they feed); every other topic 0 |
| `uncertain.json` | explicitly inconclusive, no findings | nothing satisfied, nothing asserted |
| `incorrect.json` | increment A's wrong accounting bases and invented causes (X01-X15) plus wrong consequences, attributions and outcomes (X16-X32) | SF3 on the asserted January 2020 settlements (X16, and the summary), zeroing T14.04 and T14.05; a legal finding of breach asserted (X17); ORR's and GTR's counts merged without attribution (X18: T10.02a credited for ORR's 29, T10.02b and T10.02c 0, T10.05c 0); the Class 387s shut down themselves (T10.03b 0); software versions reversed (T10.04 0); traction supply lost as the cause (T10.01 0); a 48.8 Hz rail protection setting (T04.02 capped at 0.5); 873 delay minutes (T10.05b 0); the airport by its own protection (T11.01a 0) and the hospital by LFDD (T11.01b 0); the refinery by LFDD and Stanlow as a 9 August impact (T11.03 0); the early reconnection given to WPD (T14.03 0); 17:51/18:00 forced to 18:00 with no record named (T15.02 0) and BEIS at 17:00 (T15.01a 0); communications as a cause (T15.04 0); an ESQCR/OC7 obligation (T19.02 capped at 0.5); an invented record S09-GTR-42 (SF2); plus increment A's traps, SF1 and SF2 |
| `invalid_record_wrong_evidence.json` | a REMIT asset-log event cited under R11 | rejected by `validate_submission` |
| `invalid_unknown_record.json` | unknown Network Rail entry, REMIT event and GTR witness response | rejected (3 problems) |
| `invalid_malformed_record_locator.json` | `entry:` and `event:` without an ID | rejected (2 problems) |
| `invalid_line_locator_on_witness.json` | a witness (S09) cited with a line locator | rejected |
| `invalid_line_out_of_range.json` | a line beyond the end of S08 | rejected |
| `invalid_series_out_of_range.json` | a time outside R01's series | rejected |
| `invalid_data_return_out_of_range.json` | a line beyond the end of data return S05 | rejected |
| `invalid_unknown_evidence.json` | an evidence ID the bundle does not hold (S13) | rejected |
| `invalid_summary_601_words.json` | executive summary over the 600-word limit | rejected |
| `invalid_unknown_ref.json` | a report reference to an unknown finding | rejected |

Pre-screen limits these fixtures expose (judge criteria; the judge and a human decide):

- `incomplete`: T10.05c's pre-screen is 1 because F108 contrasts two delay measures
  ("while ORR's Table 1 totals ..."), which its `counts_contrasted` pattern reads as a
  count inconsistency; the fixture holds no inconsistent count.
- The airport and the hospital are separate findings in `incorrect` (X24, X32). Written in
  one sentence ("Newcastle Airport lost supply when its own site protection systems
  tripped, and Ipswich Hospital was disconnected by the LFDD scheme"), T11.01a's
  `airport_lfdd` element credits the airport with LFDD and the `airport_own_protection`
  contradiction is excused by the word "hospital".
- Grader limit (automated element, not a pre-screen): a count's clause is split at
  "and" only before a one-digit number (`fi_elements._COUNT_CLAUSE_BREAK`'s lookahead
  `\d\b`), so in X18 "27 were reset by their drivers and 30 needed a technician" is one
  clause. Here that does not change the outcome, but the correct "7 were restored by
  driver reset and 22 needed a technician" scores 0 on T10.02b and T10.02c (the reverse
  order scores 1 on both).
- `uncertain`: a summary saying "No conclusions, recommendations or requests are
  offered" gets T20.05's partial pre-screen (`summary_actions` matches "recommendations"
  without reading the negation); the fixture says "No conclusions are offered".
