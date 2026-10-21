# Evidence builder (builder-only; excluded from the image)

This directory rebuilds and verifies the approved agent bundle for the
"investigate the electrical disturbance" MVP. It reads builder-only handoff material
(official report PDFs, the NESO frequency archive, extracted per-page PDF text). That material
must never be copied into `src/` or the image.

Outputs (all under `src/environment/incident/`):

| File | Written by |
| --- | --- |
| `bundle/R01/frequency_2019-08-09_1640-1745_BST.csv` | `build_r01.py` |
| `bundle/R01/R01.txt`, `bundle/R03/R03.txt`, `bundle/S01/S01.txt`, `bundle/S03/S03.txt`, `bundle/S04/S04.txt` | hand-authored |
| `bundle/manifest.json` | `build_manifest.py` |
| `private/provenance.json`, `private/source_manifest.json` (copy of the handoff file) | `build_provenance.py` |

## Inputs

- `GB_HANDOFF_DIR`: the handoff root. Default: `<workspace>/.context/handoff/GB_power_cut_handoff`.
  The scripts use `source_manifest.json`, `builder_only/sources/*`, `data/frequency_...csv`,
  `verification/frequency_checks.json` and `SOURCE_STATUS.md`.
- `GB_TEXT_DIR`: per-page extracted PDF text `{ESO,APP,OFG,...}.txt` with markers
  `=== <ID> PDF page <n> ===` (n is the 1-based PDF page index). Default: `<handoff root>/../text`.
  These files match PyMuPDF's `page.get_text()` output for each page.

## Rebuild (from the environment root)

```bash
uv run --frozen python builder/build_r01.py          # NESO zip -> R01 CSV (+ handoff checks)
uv run --frozen python builder/build_manifest.py     # sha256 of every artifact -> manifest.json
uv run --frozen python builder/build_provenance.py   # segments + sources -> private/provenance.json
uv run --frozen python builder/verify_provenance.py  # full verification; non-zero exit on failure
```

Run `build_manifest.py` and `build_provenance.py` again after any edit to a bundle document.
Provenance segments use start anchors (line prefixes), so line ranges follow edits automatically.
A new line needs either an existing segment to absorb it or a new anchored segment.

### `build_r01.py`

Reproduces the handoff's `verification/check_frequency.py` exactly:

- explicit `+0100` offsets parsed as supplied (never naive UTC);
- the half-open slice `[16:40:00, 17:45:00)` BST;
- an assertion of 3900 rows at strict 1 s steps (no gaps or duplicates);
- `csv.writer` output (CRLF, float reprs).

It then asserts that the result is byte-identical to the handoff CSV and that every landmark in
`frequency_checks.json` is reproduced. Use `--check` to verify without writing.

### `verify_provenance.py`

1. Every handoff source file matches its sha256 in `source_manifest.json`.
   `private/source_manifest.json` is an exact copy of that file.
2. The manifest passes its schema checks. Categories are fixed, and only R01 has a time series.
   Every artifact hash matches, and the bundle holds no stray files.
3. Provenance passes these checks:
   - The labels match the documents' STATUS lines.
   - The text hashes match.
   - Every non-blank line is covered by exactly one segment.
   - Framing segments have no sources.
   - Every quote (at least 3 words) is found on its stated PDF page after normalisation. The
     normalisation applies NFKC and casefolding, unifies dashes and quotes, drops soft hyphens,
     and collapses whitespace.
4. The R01 CSV is rebuilt from the archive and compared byte-for-byte. The sample rows in
   `R01.txt` must be the CSV's first rows.
5. No document states the frequency landmarks.

With PyMuPDF available, step 3 also checks each quote against the PDF page itself:

```bash
uv run --no-project --with pymupdf python builder/verify_provenance.py --pdf on
```

## Tests

`tests/test_evidence_bundle.py` checks the following without PDFs:

- the manifest and its hashes;
- text conventions: labels, header block, line length and value-status tags;
- provenance coverage;
- R01 structure and landmarks;
- the absence of builder conveniences and epistemic labels (no derived BST times, intervals,
  arithmetic checks, UTC/BST equivalences, Known / Not established / hypothesis labels), and
  S04's source order.

It also checks R01 cross-document leakage and that no document states the landmark values.
Checks that need the handoff or the extracted text skip when those are absent.

```bash
uv run --frozen --extra test pytest -q -p no:randomly tests/test_evidence_bundle.py
```

## Authoring rules (see `.context/mvp_design.md`)

- S01, S03 and S04 carry the SYNTHESISED status label. R03 carries the RECONSTRUCTED label. R01
  is real measured data with unchanged values.
- Every value in R03, S01, S03 and S04 has a tag on the same line: `[measured]`, `[reported]`,
  `[estimated]` or `[illustrative]`. `[illustrative]` is not used in v1.
- Raw records come before clearly dated, attributed post-event annotations. Unknown underlying
  causes stay unknown.
- No document states another document's conclusions, and none states the frequency landmarks.
- Every document gives its clock basis. S01 uses UTC (Z), and the other documents use BST
  (+01:00). Where a source does not label its clock, the clock line says the reading is an
  inference. Log rows never claim more time precision than the source publishes.
- No builder-computed conveniences (bundle 1.1.0 onwards). S01 has one clock-basis line
  (BST = UTC+01:00) and no per-entry UTC/BST equivalences or computed MW differences. S03 gives
  the raw SOE offsets and the datum T = 16:52:34 +/- 0.5 s (with RWE's note that T still has
  to be aligned with the ESO datum), but no T + offset times, intervals or arithmetic checks.
  R03 has no compiler's note pointing out conflicting times. Readers derive these themselves.
- No builder epistemic labels (Known / Not known / Established / Not established / hypothesis /
  "a view"). Attributed statements are quoted or closely paraphrased in source order, and the
  sources' own words carry their status ("for reasons presently unknown", "has not been
  established", "RWE's hypothesis is", "preliminary view").
