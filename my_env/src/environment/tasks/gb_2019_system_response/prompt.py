"""Agent-facing text for the GB 2019 power-system-response investigation.

The brief is verbatim from the increment-A contract. ``REPORT_EXPECTATIONS`` lists the
deliverables the rubric assesses for T01–T09, T12, T16 and T17 without any values,
sites, accounting bases, thresholds or computation conventions. The tool descriptions
(``TOOL_DESCRIPTIONS``) are the MCP descriptions of the nine tools under the
``system_response`` profile; like the instructions, they contain no incident facts.
The submission skeleton contains placeholders only.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from string import Template
from typing import Any

BRIEF = (
    "Investigate the electrical disturbance on 9 August 2019 and the power system's "
    "response, from the initiating event to the restoration of disconnected demand. "
    "Establish what happened and when, quantify the generation lost and the demand "
    "disconnected on the bases the records use, explain how frequency was contained "
    "and recovered, and distinguish supported explanations from unresolved causes. "
    "Support your findings with the available evidence."
)

# Deliverables only: no values, no sources' conclusions, no conventions. Each item maps
# to handoff topics (in brackets, for builders; not shown to the agent).
REPORT_EXPECTATIONS: tuple[tuple[str, str], ...] = (
    (
        "T01",
        "the initiating event: what it was, where and when it occurred, how it was "
        "cleared, whether the protection performed as required, and what happened to "
        "the affected circuit afterwards;",
    ),
    (
        "T02 T05",
        "a dated chronology from the initiating event to the restoration of "
        "disconnected demand, stating the clock basis (UTC offset) of every time you "
        "give and, for times taken from a record, the clock that record uses and any "
        "conversion you applied;",
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
        "T16",
        "the explanations you considered and ruled out, or could not rule out, with "
        "the evidence for each decision;",
    ),
    (
        "T17",
        "an uncertainty register that separates disagreements between sources "
        "(attributing each account to its source), limits of measurement, and causes "
        "that remain unresolved; label every finding with the status that fits it.",
    ),
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

DEFAULT_LIMITS: dict[str, Any] = {
    "max_tool_calls": 150,
    "list_page_size": 50,
    "frequency_page_size": 1000,
    "log_page_size": 200,
    "max_question_chars": 2000,
    "python_timeout_s": 30.0,
    "python_memory_bytes": 1 << 30,
    "max_output_chars": 20_000,
    "exec_summary_word_limit": 600,
    "variant_id": "baseline",
}

_COUNTED = (
    "Every call, including one with invalid argument values, uses 1 of your "
    "$max_tool_calls tool calls; each result reports the calls used and remaining. A "
    "call with an argument name this tool does not accept is rejected before it "
    "reaches the investigation and is not counted."
)

TOOL_DESCRIPTIONS: dict[str, str] = {
    "list_documents": f"""\
List the evidence catalogue: document IDs, neutral titles, owners, dates and categories.

`category` (optional) limits the documents to one category; the result lists the valid
categories. Results come in pages of up to $list_page_size documents; to get the next
page, pass the returned `next_cursor` as `cursor` (null means there are no more). The
first page (no cursor) also lists the other evidence by its public identifiers: asset
logs (`asset_id` and signals) for query_asset_log, control-room logs (`room_id`) for
query_control_log, witnesses (`persona_id`, role, organisation) for interview_witness,
and the (party, data_type) pairs you can ask for with request_data_return.

{_COUNTED}""",
    "request_document": f"""\
Retrieve one document, either by its exact ID (`doc_id`, as listed by list_documents) or by describing it with BOTH `party` (who holds it) and `description` (what it is); never both forms in one call.

A described request is matched deterministically against the listed documents' owners
and titles (the result reports the matcher version); the title must contain at least
half of the description's words. A unique best match is retrieved;
when several documents match equally the call fails with AMBIGUOUS_REQUEST and lists
the candidates without retrieving any (request one by doc_id); no match gives
UNKNOWN_ID.

Returns the document's text with line numbers. The line numbers are citation
locators: cite them as {{"evidence_id": "<ID>", "locator": "L12"}} or "L12-L18". The
document's files (for example a CSV time series) are also written, read-only, under
the directory named by the EVIDENCE_DIR environment variable of run_python, at the
relative paths listed in `artifacts`. A time series can also be cited as
"time:<ISO-8601 with UTC offset>", "time:<start>/<end>", "row:<n>" or "rows:<a>-<b>".

{_COUNTED}""",
    "query_frequency": f"""\
Read the measured system frequency record (evidence R01) for a time window, sample by sample.

`start` and `end` are ISO-8601 times with an explicit UTC offset (for example
2000-01-31T23:59:59+01:00 or 2000-01-31T22:59:59Z); the window includes `start` and
excludes `end`. `resolution_s` must be 1 (or omitted): samples are returned exactly as
recorded, never resampled, smoothed or interpolated. Up to $frequency_page_size samples
per call, each with its data-row number, timestamp and value; for the next page, repeat
the call with the same start and end and the returned `next_cursor` as `cursor`. A
window entirely outside the record fails with OUT_OF_RANGE.

The call also places the record's CSV file, read-only, under EVIDENCE_DIR for
run_python. Cite samples as {{"evidence_id": "R01", "locator": "time:<start>/<end>"}}
or "rows:<a>-<b>".

{_COUNTED}""",
    "query_asset_log": f"""\
Read the log of one asset (an `asset_id` listed by list_documents) for a time window: plant, circuit or network-group events and metered values.

`start` and `end` are ISO-8601 times with an explicit UTC offset; rows whose
index_time_utc is at or after `start` and before `end` are returned, in time order.
`signal` (optional) keeps one of the asset's signals. Up to $log_page_size rows per
call; for more, repeat the call with the same arguments and the returned `next_cursor`
as `cursor`. Each row gives the time as recorded and its clock basis first, then a
stable event_id, the row's evidence_id, signal, value, unit, value_status and text;
index_time_utc is a conversion used only to select rows, with its uncertainty in
seconds. Rows of one log may come from different evidence records. Cite a row as
{{"evidence_id": "<the row's evidence_id>", "locator": "event:<event_id>"}}.

{_COUNTED}""",
    "query_control_log": f"""\
Read the log of one control room (a `room` ID listed by list_documents) for a time window: timed calls, instructions and messages.

`start` and `end` are ISO-8601 times with an explicit UTC offset; entries whose
index_time_utc is at or after `start` and before `end` are returned, in time order. Up
to $log_page_size entries per call; for more, repeat the call with the same arguments
and the returned `next_cursor` as `cursor`. Each entry gives the time as recorded and
its clock basis first, then a stable entry_id, the entry's evidence_id, from, to,
channel, value_status and text; index_time_utc is a conversion used only to select
entries, with its uncertainty in seconds. Cite an entry as
{{"evidence_id": "<the entry's evidence_id>", "locator": "entry:<entry_id>"}}.

{_COUNTED}""",
    "interview_witness": f"""\
Put one question to a witness (a `persona_id` listed by list_documents) and receive an approved answer from their fact card.

Answers are fixed texts selected deterministically by topic (the result reports the
matcher version). A question that clearly matches one topic returns that answer with a
stable `response_id`. A question that does not clearly match one topic fails with
AMBIGUOUS_REQUEST and lists the closest topics (at most three answers' worth) to choose
from; ask again naming one, or ask more specifically. A question
outside the witness's knowledge returns their fixed "not known" answer, which is not
citable. Ask one thing per question, in plain words (at most $max_question_chars
characters). Cite an answer as
{{"evidence_id": "<the result's evidence_id>", "locator": "response:<response_id>"}}.

{_COUNTED}""",
    "request_data_return": f"""\
Ask a party for a data return, giving `party` and `data_type` as listed by list_documents (case and spacing do not matter).

If the party supplies it, the return is a document: its numbered text comes back (cite
lines as {{"evidence_id": "<ID>", "locator": "L12"}}) and its files are placed,
read-only, under EVIDENCE_DIR for run_python. A party may instead answer that it does
not hold the data (NOT_HELD) or decline to supply it (REFUSED); these answers are fixed
and asking again does not change them.

{_COUNTED}""",
    "run_python": f"""\
Run Python 3.12 code (numpy and pandas available) in a fresh process; returns stdout and stderr.

Evidence files are read-only under os.environ["EVIDENCE_DIR"]. Only what you have
obtained is there: documents you requested, data returns you received, and the
frequency record once you have queried it, e.g.
pandas.read_csv(os.path.join(os.environ["EVIDENCE_DIR"], "R01", "<file>.csv")). The
working directory is a scratch directory that persists between calls (also
os.environ["SCRATCH_DIR"]); Python variables do not persist. No network access. Each
call may use at most $python_timeout_s seconds of wall time and $python_memory of
memory; stdout and stderr are each cut off after $max_output_chars characters, so
print summaries rather than whole tables. Files created or changed in the scratch
directory are listed.

{_COUNTED}""",
    "submit_findings": """\
Submit your investigation as one v3 JSON object (pass the object or its JSON text).

The format is given in the task instructions: schema_version "3.0", variant_id
"$variant_id", a report (an executive_summary of at most $exec_summary_word_limit words
plus sections of {heading, body}) and findings, each with finding_id, statement,
status (observed, reported, inferred, hypothesis or unknown), citations
[{evidence_id, locator}] and optional quantity, event_time and derivation. Locators:
"L12" or "L12-L18" (numbered document lines); "time:...", "row:..." or "rows:..." (a
time series); "event:<event_id>", "entry:<entry_id>" or "response:<response_id>" (a log
row or a witness answer, cited with the evidence_id it carries).

An invalid submission is not saved: the result lists every problem as
{path, message}; fix them and submit again while budget remains. The first valid
submission is final and closes the investigation; after it is accepted, end your turn
without further tool calls.

Every call, including an invalid submission, uses 1 of your $max_tool_calls tool calls.
A call with an argument name this tool does not accept is rejected before it reaches
the investigation and is not counted.""",
}


def _memory_text(memory_bytes: int) -> str:
    gib = memory_bytes / (1 << 30)
    return f"{gib:g} GiB" if gib >= 1 else f"{memory_bytes} bytes"


def _limits(config: Any = None) -> dict[str, Any]:
    values = dict(DEFAULT_LIMITS)
    if config is not None:
        source = config if isinstance(config, Mapping) else None
        for key in DEFAULT_LIMITS:
            value = (
                source.get(key) if source is not None else getattr(config, key, None)
            )
            if value is not None:
                values[key] = value
    return values


def tool_description(name: str, config: Any = None) -> str:
    """The MCP description of tool ``name`` under the system-response profile, with the
    limits of ``config`` (an ``EpisodeConfig`` or mapping; defaults otherwise)."""
    values = _limits(config)
    values["python_timeout_s"] = f"{float(values['python_timeout_s']):g}"
    values["python_memory"] = _memory_text(int(values["python_memory_bytes"]))
    return Template(TOOL_DESCRIPTIONS[name]).substitute(values)


def build_instructions(
    *,
    max_tool_calls: int = 150,
    python_timeout_s: float = 30,
    python_memory_bytes: int = 1 << 30,
    max_output_chars: int = 20_000,
    exec_summary_word_limit: int = 600,
    variant_id: str = "baseline",
    context_cap_tokens: int = 200_000,
    output_token_budget: int = 30_000,
    frequency_page_size: int = 1000,
    log_page_size: int = 200,
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
    return f"""\
# Brief

{BRIEF}

# Report expectations

Your report and findings should cover:
{expectations}

# Evidence

The evidence is fixed. `list_documents` lists the documents by ID and, on its first \
page, the other evidence by its public identifiers: asset logs, control-room logs, \
witnesses and the data returns you can ask for.

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
dates, categories), in pages of up to 50; the first page also lists asset logs, \
control-room logs, witnesses and data returns.
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
data), reported (stated in a record or by a witness), inferred (your reasoning from \
cited evidence), hypothesis (a possible explanation that the evidence does not \
establish), unknown (something the evidence cannot determine; say what is unknown).
- `finding_id`: letters, digits, '_', '.' or '-' (at most 40 characters), unique; at \
most 200 findings.
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
