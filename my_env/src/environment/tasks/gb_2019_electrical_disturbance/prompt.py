"""Agent-facing text for the GB 2019 electrical-disturbance investigation.

The brief is verbatim from the MVP plan. ``REPORT_EXPECTATIONS`` lists the deliverables
the rubric assesses, without any values, sites or methods: in particular it does not say
how to count the time below a threshold (the agent must choose and state a convention),
which records use which clock, or what the protection requirements are.
The submission skeleton contains placeholders only — no incident facts, times or
quantities.
"""

from __future__ import annotations

import json
from typing import Any

BRIEF = (
    "Investigate the electrical disturbance on 9 August 2019. Establish the initiating "
    "event, reconstruct the generation-trip and frequency sequence, and distinguish "
    "supported explanations from unresolved causes. Support your findings with the "
    "available evidence."
)

# Deliverables only: no values, no sources' conclusions, no computation convention. Every
# criterion of the answer key maps to one of these items (REVIEW_CHECKLIST.md A7).
REPORT_EXPECTATIONS = (
    "- the initiating event, how it was cleared, and whether the protection performed "
    "as required;",
    "- a dated chronology of the disturbance, stating the clock basis (UTC offset) of "
    "every time you give and, for times taken from a record, the clock that record uses "
    "and any conversion you applied;",
    "- each loss of generation, with its size in megawatts and its timing;",
    "- the frequency excursion characterised from the measured frequency record: each "
    "minimum, the recovery to 50 Hz and the time below 49 Hz, stating how you computed "
    "them and the limits of the data's sampling;",
    "- for each trip, the mechanism that is established and what remains unexplained, "
    "with each finding labelled with the status that fits it.",
)

SUBMISSION_SKELETON: dict[str, Any] = {
    "schema_version": "3.0",
    "variant_id": "baseline",
    "report": {
        "executive_summary": "<at most 600 words; refer to findings like [F01]>",
        "sections": [
            {
                "heading": "<section heading>",
                "body": "<markdown text referring to findings like [F01] or [F01, F02]>",
            }
        ],
    },
    "findings": [
        {
            "finding_id": "F01",
            "statement": "<one claim, stated plainly>",
            "status": "<observed | reported | inferred | hypothesis | unknown>",
            "citations": [{"evidence_id": "<document ID>", "locator": "<locator>"}],
            "quantity": {
                "value": 0,
                "unit": "<unit>",
                "basis": "<how it was obtained>",
            },
            "event_time": "<YYYY-MM-DDTHH:MM:SS+HH:MM>",
            "derivation": "<how a computed value was derived from the cited inputs>",
        }
    ],
}


def build_instructions(
    *,
    max_tool_calls: int = 50,
    python_timeout_s: float = 30,
    python_memory_bytes: int = 1 << 30,
    max_output_chars: int = 20_000,
    exec_summary_word_limit: int = 600,
    variant_id: str = "baseline",
    context_cap_tokens: int = 200_000,
    output_token_budget: int = 30_000,
) -> str:
    memory_gib = python_memory_bytes / (1 << 30)
    memory = (
        f"{memory_gib:g} GiB" if memory_gib >= 1 else f"{python_memory_bytes} bytes"
    )
    skeleton = dict(SUBMISSION_SKELETON, variant_id=variant_id)
    skeleton_text = json.dumps(skeleton, indent=2, ensure_ascii=False)
    expectations = "\n".join(REPORT_EXPECTATIONS)
    return f"""\
# Brief

{BRIEF}

# Report expectations

Your report and findings should cover:
{expectations}

# Evidence

The evidence is a fixed catalogue of documents; use `list_documents` to see it and \
`request_document` to read a document by its exact ID. Some records are reconstructions \
prepared for this exercise from published investigation material: they say so in a \
STATUS line in their header. The header of each record also states its originator, \
record type and clock reference (UTC offset). Numeric values in reconstructed records \
are tagged [measured], [reported], [estimated] or [illustrative]; illustrative values \
add texture only and cannot establish a finding. Weigh the records as evidence: they may \
be incomplete, and some questions may not be answerable from them.

# Tools

- `list_documents(category?, cursor?)`: the catalogue (IDs, neutral titles, owners, \
dates, categories), in pages of up to 50.
- `request_document(doc_id)`: the document's text with line numbers (the line numbers \
are your citation locators). Its files, e.g. a CSV time series, are also written \
read-only under the directory named by the `EVIDENCE_DIR` environment variable of \
`run_python`, at the relative paths listed in `artifacts`.
- `run_python(code)`: runs Python 3.12 with numpy and pandas in a fresh process. The \
working directory is a scratch directory that persists between calls; variables do \
not. Only documents you have requested are present in `EVIDENCE_DIR`. No network.
- `submit_findings(submission)`: validates your submission and, if it is valid, \
freezes it.

# Budgets

- At most {max_tool_calls} tool calls in total, counting every call that reaches a \
tool: calls with invalid argument values, Python runs and submission attempts \
included. Each result shows the calls used and remaining. A call with malformed JSON \
arguments or an argument name the tool does not accept is rejected before it reaches \
the investigation and is not counted.
- Each Python call is limited to {python_timeout_s:g} seconds of wall time and \
{memory} of memory; stdout and stderr are each cut off after {max_output_chars} \
characters (print summaries, not whole tables).
- The conversation context is capped at {context_cap_tokens:,} tokens and your total \
output budget is {output_token_budget:,} tokens.

# Submission

Submit one JSON object in the v3 format below with `submit_findings`. The first valid \
submission is final and closes the investigation; after it is accepted, end your turn \
without further tool calls. An invalid submission is rejected with a list of problems \
({{path, message}}) and nothing is saved: fix the problems and submit again while budget \
remains. If you end your turn without a valid submission, or run out of tool calls, the \
investigation is recorded as incomplete.

Skeleton (every <...> is a placeholder to replace; remove optional fields you do not \
use):

```json
{skeleton_text}
```

Rules:
- `schema_version` is "3.0" and `variant_id` is "{variant_id}"; no other fields are \
allowed.
- `report.executive_summary` has at most {exec_summary_word_limit} words; \
`report.sections` is a list of {{heading, body}} written in markdown.
- In the report, refer to findings by ID in square brackets, e.g. [F01] or [F01, F02]. \
Square brackets in the report are reserved for finding IDs, and every bracketed ID must \
be the `finding_id` of one of your findings.
- Each finding makes one claim. `status` is one of: observed (seen directly in measured \
data), reported (stated in a record), inferred (your reasoning from cited evidence), \
hypothesis (a possible explanation that the evidence does not establish), unknown \
(something the evidence cannot determine; say what is unknown).
- `finding_id`: letters, digits, '_', '.' or '-' (at most 40 characters), unique; at \
most 200 findings.
- `citations` is a list of {{evidence_id, locator}} (it may be empty, but support your \
claims). Locators:
  - `L12` or `L12-L18`: numbered lines of a document's text (1-based, inclusive);
  - `time:<ISO-8601 with UTC offset>` or `time:<start>/<end>`: an instant or range of a \
time series (inclusive, within the series);
  - `row:<n>` or `rows:<a>-<b>`: data rows of a time series (1-based, header excluded).
- Optional: `quantity` {{value (a number), unit, basis}}; `event_time` (ISO-8601 with an \
explicit UTC offset); `derivation` (how a value was computed). A finding with a \
derivation must cite the evidence it was derived from.
"""
