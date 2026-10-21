# System-response grading fixtures (builder-made)

Fixtures for task `gb-2019-system-response`, graded with the system-response key
(`private/system_response/answer_key.json`) on bundle `bundles/system_response`. They are
not bound to a key version: `tests/test_sr_reference_fixtures.py` grades them with the
installed key and checks the automated outcomes below. Regenerate with
`uv run --frozen python tests/fixtures/sr/build_sr_fixtures.py` after changing the reference
submission (`src/environment/tasks/gb_2019_system_response/reference/reference_submission.json`).

`submissions/`:

| File | What it is | Expected automated outcome |
|---|---|---|
| `correct.json` | byte copy of the reference submission | every criterion at content 1 and evidence 1 (decided or proposed); no flag |
| `uncited.json` | the reference with every citation (and so every derivation) removed | content proposals unchanged; evidence support 0 (decided) everywhere |
| `incomplete.json` | initiating event and frequency findings only | T01, T03, T04 (and T16 where they overlap) covered; the other tasks 0 |
| `uncertain.json` | explicitly inconclusive, no findings | nothing satisfied, nothing asserted |
| `incorrect.json` | wrong accounting bases and invented causes | traps: 1,990 MW as ESO's Table 2 total, 931 MW attributed to Ofgem, 892 MW to the DNOs, 1,338 MW to Table 3, 219,632 MVA.s to Table 4; overlapping DG estimates summed (150 + 350 + 500 + 462 MW) and ESO's 1,878 MW added to net effects; severe flags SF1 (faulty sensor, failed bypass valve) and SF2 (invented entry S07-E14); contradictions: another lightning trip as initiator, the DRC as cause, GT1B automatic; wrong R01 landmarks and duration (automatic 0) |
| `invalid_record_wrong_evidence.json` | an asset-log event cited under another evidence ID | rejected by `validate_submission` |
| `invalid_unknown_record.json` | unknown control-log entry, asset-log event and witness response | rejected (3 problems) |
| `invalid_malformed_record_locator.json` | `event:` and `entry:` without an ID | rejected (2 problems) |
| `invalid_line_locator_on_witness.json` | a witness (S09) cited with a line locator | rejected |
| `invalid_series_out_of_range.json` | a time outside R07's demand series | rejected |
| `invalid_data_return_out_of_range.json` | a line beyond the end of data return S06 | rejected |
| `invalid_unknown_evidence.json` | an evidence ID the bundle does not hold (S02) | rejected |
| `invalid_summary_601_words.json` | executive summary over the 600-word limit | rejected |
| `invalid_unknown_ref.json` | a report reference to an unknown finding | rejected |
