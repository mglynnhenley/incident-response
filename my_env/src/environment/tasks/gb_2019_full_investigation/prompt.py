"""Agent-facing text for the GB 2019 full investigation (increment B).

The brief broadens increment A's brief (``gb_2019_system_response.prompt.BRIEF``) to the
whole incident: its consequences for rail and other essential services, the
communications around it, contributing factors, compliance concerns, recommendations and
further evidence requests. Increment A's clauses are kept word for word.

``REPORT_SECTIONS`` are the pilot plan's report sections (executive summary, chronology,
findings, consequences, uncertainties, recommendations, further evidence requests), given
as deliverables only. ``REPORT_EXPECTATIONS`` lists what the report and findings should
cover for every handoff topic T01-T20 without any values, sites, train classes, counts,
times, accounting bases, thresholds, legal clauses or computation conventions; each item
is tagged with its topics for builders (the tags are never shown to the agent).

The nine tools are increment A's tools under the same ``system_response`` profile, so
their MCP descriptions are increment A's (``gb_2019_system_response.prompt``); like the
instructions, they contain no incident facts. The submission skeleton contains
placeholders and the section headings only.
"""

from __future__ import annotations

import json
from typing import Any

from environment.incident.submission import MAX_FINDINGS

BRIEF = (
    "Investigate the electrical disturbance on 9 August 2019 and its consequences, "
    "from the initiating event to the restoration of disconnected demand and the "
    "recovery of affected services. Establish what happened and when, quantify the "
    "generation lost and the demand disconnected on the bases the records use, explain "
    "how frequency was contained and recovered, and assess the effects on rail and "
    "other essential services and the communications during and after the event. "
    "Identify the factors that contributed and the compliance concerns the records "
    "raise, distinguish supported explanations from unresolved causes, and recommend "
    "actions and further evidence requests that follow from your findings. Support "
    "your findings with the available evidence."
)

#: The report sections of the pilot plan, in order. The executive summary is
#: ``report.executive_summary``; the others are ``report.sections`` headings.
REPORT_SECTIONS: tuple[str, ...] = (
    "Executive summary",
    "Chronology",
    "Findings",
    "Consequences",
    "Uncertainties",
    "Recommendations",
    "Further evidence requests",
)
SECTION_HEADINGS: tuple[str, ...] = REPORT_SECTIONS[1:]

# Deliverables only: no values, no sources' conclusions, no conventions. Each item maps
# to handoff topics (in brackets, for builders; not shown to the agent). Items for
# increment A's topics keep increment A's wording except where the scope widens (the
# chronology now runs to the recovery of affected services).
REPORT_EXPECTATIONS: tuple[tuple[str, str], ...] = (
    (
        "T01",
        "the initiating event: what it was, where and when it occurred, how it was "
        "cleared, whether the protection performed as required, and what happened to "
        "the affected circuit afterwards;",
    ),
    (
        "T02 T05 T10 T15",
        "a dated chronology from the initiating event to the restoration of "
        "disconnected demand and the recovery of affected services, stating the clock "
        "basis (UTC offset) of every time you give and, for times taken from a record, "
        "the clock that record uses and any conversion you applied;",
    ),
    (
        "T02 T08",
        "each loss of generation, including distributed (embedded) generation, with "
        "its size in megawatts, its timing and whether the figure is measured, "
        "reported or estimated, and the total generation lost on each accounting basis "
        "the records use, saying which basis and stage each total refers to;",
    ),
    (
        "T03 T04",
        "the frequency excursion characterised from the measured frequency record: "
        "each minimum, the recovery to 50 Hz and the time below 49 Hz, stating how you "
        "computed them and the limits of the data's sampling;",
    ),
    (
        "T12",
        "how frequency was contained and recovered: the loss the system was secured "
        "against, the response and reserve held and delivered, the system inertia, and "
        "how these compared with the losses;",
    ),
    (
        "T09",
        "the low-frequency demand disconnection: what triggered it, how much demand was "
        "disconnected according to each record and the definition each uses, and how "
        "its performance compares with the requirements described in the evidence;",
    ),
    (
        "T05",
        "the restoration of disconnected demand: when it was instructed, how it "
        "proceeded and when it was complete, kept distinct from the recovery of other "
        "affected services;",
    ),
    (
        "T06 T07 T08",
        "for each loss of generation, the mechanism that is established, whose account "
        "establishes it, and what remains unexplained;",
    ),
    (
        "T04 T10",
        "the effects on rail services: which trains were affected and why, according "
        "to the records, and how that relates to the measured frequency record; how "
        "services were recovered and how long recovery took; and the scale of the "
        "disruption according to each record;",
    ),
    (
        "T11",
        "the effects on essential services and other critical facilities: which were "
        "affected, how each was affected according to the records, and what the "
        "records do not establish;",
    ),
    (
        "T15",
        "the communications during and after the event: who informed whom and when, "
        "between the parties involved, to government and the regulator, and to the "
        "public, according to each record; and any problems of notification or "
        "coordination, kept distinct from the causes of the disturbance;",
    ),
    (
        "T13",
        "the factors that contributed to the event and its consequences, separating "
        "the triggering event from contributing and wider systemic factors, with the "
        "evidence for each;",
    ),
    (
        "T14",
        "compliance observations: for each party concerned, what the evidence shows "
        "against the requirements described in the evidence, whether it is a concern "
        "about process or a demonstrated failure to comply, and what proof is missing;",
    ),
    (
        "T16",
        "the explanations you considered and ruled out, or could not rule out, with "
        "the evidence for each decision;",
    ),
    (
        "T17",
        "an uncertainty register that separates disagreements between sources "
        "(attributing each account to its source), limits of measurement, and causes "
        "that remain unresolved; label every finding with the status that fits it;",
    ),
    (
        "T18",
        "recommendations, each linked to the findings it addresses, naming the party "
        "that should act and how its completion could be verified;",
    ),
    (
        "T19",
        "further evidence requests and escalation: the evidence that is still missing, "
        "which party should supply it and exactly what is requested, and the "
        "notification and coordination between parties that the requirements described "
        "in the evidence call for;",
    ),
    (
        "T20",
        "an executive summary that gives the triggering event, the sequence of events "
        "and its consequences, separates contributing factors from causes that remain "
        "unknown, attributes significant estimates and disagreements to their sources, "
        "puts the recommended actions in priority order, and claims no more certainty "
        "than the evidence supports.",
    ),
)

#: Size of the evidence as the tools return it (characters of rendered tool results on
#: bundle 0.1.0, rounded): every listed document by ``request_document`` (smallest and
#: largest), and every asset- and control-log row by paging the log tools over the whole
#: record. ``tests/test_fi_task.py`` re-measures them on the shipped bundle (decision 53).
EVIDENCE_DOCUMENT_CHARS = 320_000
EVIDENCE_DOCUMENT_MIN_CHARS = 5_000
EVIDENCE_DOCUMENT_MAX_CHARS = 46_000
EVIDENCE_LOG_CHARS = 510_000

_BODY_PLACEHOLDER = "<markdown text referring to findings like [F01] or [F01, F02]>"

SUBMISSION_SKELETON: dict[str, Any] = {
    "schema_version": "3.0",
    "variant_id": "baseline",
    "report": {
        "executive_summary": "<at most 600 words; refer to findings like [F01]>",
        "sections": [
            {"heading": heading, "body": _BODY_PLACEHOLDER}
            for heading in SECTION_HEADINGS
        ],
    },
    "findings": [
        {
            "finding_id": "F01",
            "statement": "<one claim, stated plainly>",
            "status": "<observed | reported | inferred | hypothesis | unknown>",
            "citations": [{"evidence_id": "<evidence ID>", "locator": "<locator>"}],
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


def _memory_text(memory_bytes: int) -> str:
    gib = memory_bytes / (1 << 30)
    return f"{gib:g} GiB" if gib >= 1 else f"{memory_bytes} bytes"


def build_instructions(
    *,
    max_tool_calls: int = 150,
    python_timeout_s: float = 30,
    python_memory_bytes: int = 1 << 30,
    max_output_chars: int = 20_000,
    exec_summary_word_limit: int = 600,
    variant_id: str = "baseline",
    context_cap_tokens: int = 200_000,
    output_token_budget: int = 80_000,
    frequency_page_size: int = 1000,
    log_page_size: int = 200,
    list_page_size: int = 50,
) -> str:
    memory = _memory_text(python_memory_bytes)
    skeleton = dict(SUBMISSION_SKELETON, variant_id=variant_id)
    skeleton["report"] = dict(
        skeleton["report"],
        executive_summary=(
            f"<at most {exec_summary_word_limit} words; refer to findings like [F01]>"
        ),
    )
    skeleton_text = json.dumps(skeleton, indent=2, ensure_ascii=False)
    expectations = "\n".join(f"- {text}" for _, text in REPORT_EXPECTATIONS)
    headings = ", ".join(f'"{heading}"' for heading in SECTION_HEADINGS)
    return f"""\
# Brief

{BRIEF}

# Report expectations

Write the report in these sections: an executive summary of at most \
{exec_summary_word_limit} words (`report.executive_summary`), then \
`report.sections` with the headings {headings}, in that order. You may add further \
sections. Each section refers to the findings that support it.

Your report and findings should cover:
{expectations}

The report and findings are assessed for accuracy, for coverage of these expectations, \
for evidence support (whether the evidence you cite substantiates each claim) and for \
the handling of uncertainty. This is a technical investigation, not a legal or \
regulatory determination: assess compliance only against the requirements described in \
the evidence, and do not state legal findings or enforcement outcomes that the evidence \
does not contain.

# Evidence

The evidence is fixed. `list_documents` lists the documents by ID and, on its first \
page, the other evidence by its public identifiers: asset logs, control-room logs, \
witnesses and the data returns you can ask for.

This is a retrospective investigation. Records prepared for it may draw on material \
published after the event and do not claim to have existed in that form on the day. The \
date the catalogue lists for a document is the date of the incident it covers, not the \
date of its sources: each record names its sources and, where it uses them, their dates.

Each record says what kind of evidence it is:
- real published data extracts, whose header names the publisher, the dataset, the \
licence and the clock basis; their values are as published;
- values digitised from published figures, with their stated uncertainty;
- reconstructions prepared for this exercise from published investigation material, \
which say so in a STATUS line (log results and witness answers carry their STATUS \
with every result).

Values carry a status tag: [measured], [reported], [estimated], [modelled], \
[digitised] or [illustrative] (log rows carry it in a value_status column). Illustrative \
values add texture only and cannot establish a finding. Records may disagree, be \
incomplete, or use different clocks, definitions and accounting stages; some questions \
may not be answerable from them. Log rows give the time as recorded with its clock \
basis; their index_time_utc is a conversion used only to select rows by time and has a \
stated uncertainty. Witnesses answer only from fixed fact cards. A data return may be \
supplied, or the party may not hold it or may refuse it.

# Tools

- `list_documents(category?, cursor?)`: the catalogue (IDs, neutral titles, owners, \
dates, categories), in pages of up to {list_page_size}; the first page also lists asset \
logs, control-room logs, witnesses and data returns.
- `request_document(doc_id)` or `request_document(party, description)`: a document's \
text with line numbers (your citation locators); a described request that matches \
several documents equally lists them instead. Its files are also written read-only \
under the directory named by the `EVIDENCE_DIR` environment variable of `run_python`.
- `query_frequency(start, end, resolution_s=1, cursor?)`: the measured frequency \
record, sample by sample, for start <= time < end (up to {frequency_page_size} samples \
per call); it also places the record's CSV file in `EVIDENCE_DIR`.
- `query_asset_log(asset_id, start, end, signal?, cursor?)` and \
`query_control_log(room, start, end, cursor?)`: log rows in a time window (up to \
{log_page_size} per call), each with a stable ID.
- `interview_witness(persona_id, question)`: one question, one approved answer with a \
stable response ID; an unclear question returns the topics to choose from.
- `request_data_return(party, data_type)`: a party's data return, or its fixed answer \
that the data are not held or will not be supplied.
- `run_python(code)`: runs Python 3.12 with numpy and pandas in a fresh process. The \
working directory is a scratch directory that persists between calls; variables do \
not. Only evidence you have obtained is present in `EVIDENCE_DIR`. No network.
- `submit_findings(submission)`: validates your submission and, if it is valid, \
freezes it.

Paged results return a `next_cursor`; repeat the same call with it as `cursor` to \
continue.

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
output budget is {output_token_budget:,} tokens. A run that reaches the context cap ends \
at once and, without a frozen submission, is recorded as incomplete.
- Everything a tool returns stays in the conversation. The listed documents total about \
{EVIDENCE_DOCUMENT_CHARS:,} characters of numbered text (about \
{EVIDENCE_DOCUMENT_MIN_CHARS:,} to {EVIDENCE_DOCUMENT_MAX_CHARS:,} per document) and the \
asset and control-room logs about {EVIDENCE_LOG_CHARS:,} characters of rows, so reading \
everything in full does not fit in the context cap: choose what you read, and analyse the \
files of documents you have obtained with `run_python` rather than printing them.

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
data), reported (stated in a record or by a witness), inferred (your reasoning from \
cited evidence), hypothesis (a possible explanation that the evidence does not \
establish), unknown (something the evidence cannot determine; say what is unknown).
- `finding_id`: letters, digits, '_', '.' or '-' (at most 40 characters), unique; at \
most {MAX_FINDINGS} findings.
- `citations` is a list of {{evidence_id, locator}} (it may be empty, but support your \
claims). Locators:
  - `L12` or `L12-L18`: numbered lines of a document's text (1-based, inclusive);
  - `time:<ISO-8601 with UTC offset>` or `time:<start>/<end>`: an instant or range of a \
time series (inclusive, within the series);
  - `row:<n>` or `rows:<a>-<b>`: data rows of a time series (1-based, header excluded);
  - `event:<event_id>`, `entry:<entry_id>` or `response:<response_id>`: an asset-log \
row, a control-log entry or a witness answer, cited with the evidence_id that row or \
answer carries.
- Optional: `quantity` {{value (a number), unit, basis}}; `event_time` (ISO-8601 with an \
explicit UTC offset); `derivation` (how a value was computed). A finding with a \
derivation must cite the evidence it was derived from.
"""
