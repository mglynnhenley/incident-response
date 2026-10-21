"""Regenerate the system-response grading fixtures (builder tool; not collected by pytest).

    uv run --frozen python tests/fixtures/sr/build_sr_fixtures.py

Writes ``submissions/*.json`` from the system-response reference submission plus
deliberate errors, validating each against the system-response bundle (valid fixtures must
pass ``validate_submission``; ``invalid_*`` must fail it). Rerun after changing the
reference submission. The fixtures are not bound to a key version: the tests grade them
with the installed key and check the outcomes listed in ``README.md``.
"""

import copy
import json
from pathlib import Path

from environment.incident.catalogue import Catalogue
from environment.incident.submission import validate_submission

ENV = Path(__file__).resolve().parents[3]
REF = (
    ENV
    / "src/environment/tasks/gb_2019_system_response/reference/reference_submission.json"
)
SUBS = Path(__file__).resolve().parent / "submissions"
SUBS.mkdir(parents=True, exist_ok=True)
catalogue = Catalogue.load(ENV / "src/environment/incident/bundles/system_response")
reference = json.loads(REF.read_text(encoding="utf-8"))


def T(hms):
    return f"2019-08-09T{hms}+01:00"


def c(doc, loc):
    return {"evidence_id": doc, "locator": loc}


def write(name, sub, expect_valid=True):
    result = validate_submission(sub, catalogue)
    assert result.ok == expect_valid, (name, result.errors)
    path = SUBS / f"{name}.json"
    text = json.dumps(sub, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    print(name, "valid" if result.ok else f"invalid: {result.errors}")
    return result


def shell(summary, sections, findings):
    return {
        "schema_version": "3.0",
        "variant_id": "baseline",
        "report": {
            "executive_summary": summary,
            "sections": [{"heading": h, "body": b} for h, b in sections],
        },
        "findings": findings,
    }


def by_id(sub):
    return {f["finding_id"]: f for f in sub["findings"]}


# -- correct = reference ----------------------------------------------------------------
write("correct", reference)

# -- uncited: every citation (and therefore every derivation) removed --------------------
uncited = copy.deepcopy(reference)
for f in uncited["findings"]:
    f["citations"] = []
    f.pop("derivation", None)
write("uncited", uncited)

# -- incomplete: initiating event and frequency only -------------------------------------
keep = ("F01", "F02", "F03", "F04", "F20", "F21", "F22", "F23", "F24")
ref = by_id(reference)
incomplete = shell(
    "Partial investigation: the initiating event and the measured frequency only. A "
    "lightning strike caused a single-phase (blue) to earth fault on one Eaton "
    "Socon–Wymondley 400 kV circuit at 16:52:33.490 BST, cleared in 70 ms and 74 ms and "
    "reclosed at 16:52:53 [F01, F02, F03, F04]. From the R01 1-s series: first minimum "
    "49.083 Hz at 16:52:59 BST, event minimum 48.787 Hz at 16:53:49, first sample at or "
    "above 50 Hz 50.001 Hz at 16:57:16, and 33 s strictly below 49 Hz [F20, F21, F22, F23, "
    "F24]. Generation losses, accounting bases, response, LFDD, restoration and causes "
    "were not examined.",
    [
        ("Initiating event", "See [F01, F02, F03, F04]."),
        ("Frequency", "See [F20, F21, F22, F23, F24]."),
    ],
    [copy.deepcopy(ref[fid]) for fid in keep],
)
write("incomplete", incomplete)

# -- uncertain: explicitly inconclusive --------------------------------------------------
uncertain = shell(
    "Explicitly inconclusive: I could not establish the sequence of events, the "
    "generation lost or the demand disconnected with enough confidence to report "
    "findings. No conclusions are offered.",
    [("Scope", "No findings are made.")],
    [],
)
write("uncertain", uncertain)

# -- incorrect: wrong accounting bases, overlapping sums, invented causes and records ----
incorrect_findings = [
    {
        "finding_id": "X01",
        "statement": "The initiating event was the lightning trip of the Blyth–Eccles–Stella "
        "West 400 kV circuit at 16:50:44 BST, which started the loss of generation.",
        "status": "reported",
        "citations": [c("R03", "L73-L77")],
    },
    {
        "finding_id": "X02",
        "statement": "The ESO's technical report (Table 2) gives the total generation lost "
        "as 1,990 MW.",
        "status": "reported",
        "citations": [c("S12", "L16-L24")],
        "quantity": {"value": 1990, "unit": "MW", "basis": "ESO Table 2"},
    },
    {
        "finding_id": "X03",
        "statement": "Ofgem reports that LFDD disconnected 931 MW of demand.",
        "status": "reported",
        "citations": [c("S05", "L83-L87")],
    },
    {
        "finding_id": "X04",
        "statement": "The DNOs reported 892 MW of demand disconnected by LFDD relays.",
        "status": "reported",
        "citations": [c("S05", "L35")],
    },
    {
        "finding_id": "X05",
        "statement": "In total 1,462 MW of distributed generation was lost on loss-of-mains "
        "protection: 150 MW + 350 MW + 500 MW + 462 MW = 1,462 MW.",
        "status": "inferred",
        "citations": [c("S06", "L46-L49"), c("S06", "L20-L21")],
        "derivation": "150 + 350 + 500 + 462 = 1,462 MW",
    },
    {
        "finding_id": "X06",
        "statement": "Adding the ESO's 1,878 MW, the further 200 MW at 49 Hz and the 550 MW "
        "lost with LFDD gives 1,878 MW + 200 MW + 550 MW = 2,628 MW of generation lost.",
        "status": "inferred",
        "citations": [c("S12", "L16-L24"), c("S06", "L94-L101")],
        "derivation": "1,878 + 200 + 550 = 2,628 MW",
    },
    {
        "finding_id": "X07",
        "statement": "The ESO's technical report (Table 3) gives 1,338 MW of secondary "
        "response held.",
        "status": "reported",
        "citations": [c("R06", "L31")],
    },
    {
        "finding_id": "X08",
        "statement": "ESO Table 4 gives system inertia of 219,632 MVA.s on 9 August.",
        "status": "reported",
        "citations": [c("R02", "L192")],
    },
    {
        "finding_id": "X09",
        "statement": "The root cause of the ST1C trip was a faulty speed sensor, and GT1A "
        "tripped because a bypass valve failed to open.",
        "status": "reported",
        "citations": [c("S04", "L56-L59")],
    },
    {
        "finding_id": "X10",
        "statement": "GT1B tripped automatically on high steam pressure, as recorded in the "
        "ESO control log entry S07-E14.",
        "status": "reported",
        "citations": [c("S03", "L52")],
    },
    {
        "finding_id": "X11",
        "statement": "The Dynamic Reactive Compensator failed and caused the Hornsea One "
        "de-load.",
        "status": "reported",
        "citations": [c("S01", "L78-L79")],
    },
    {
        "finding_id": "X12",
        "statement": "The frequency minimum was 48.8 Hz at 16:53:49 BST.",
        "status": "observed",
        "citations": [
            c("R01", "time:2019-08-09T16:53:20+01:00/2019-08-09T16:54:30+01:00")
        ],
        "quantity": {"value": 48.8, "unit": "Hz", "basis": "R01"},
        "event_time": T("16:53:49"),
    },
    {
        "finding_id": "X13",
        "statement": "The first post-fault minimum was 49.1 Hz at 16:52:58 BST.",
        "status": "observed",
        "citations": [
            c("R01", "time:2019-08-09T16:52:45+01:00/2019-08-09T16:53:10+01:00")
        ],
        "quantity": {"value": 49.1, "unit": "Hz", "basis": "ESO timeline"},
        "event_time": T("16:52:58"),
    },
    {
        "finding_id": "X14",
        "statement": "Frequency was below 49 Hz for 40 s.",
        "status": "observed",
        "citations": [
            c("R01", "time:2019-08-09T16:53:40+01:00/2019-08-09T16:54:14+01:00")
        ],
        "quantity": {"value": 40, "unit": "s", "basis": "estimate from the chart"},
    },
    {
        "finding_id": "X15",
        "statement": "All demand was restored at 18:34 BST.",
        "status": "reported",
        "citations": [c("S07", "L52-L53")],
        "event_time": T("18:34:00"),
    },
]
incorrect = shell(
    "The Blyth–Eccles–Stella West trip at 16:50:44 started the event [X01]. The ESO's "
    "Table 2 total is 1,990 MW [X02]; Ofgem reports 931 MW of LFDD disconnection and the "
    "DNOs 892 MW [X03, X04]. Distributed generation lost on loss-of-mains protection "
    "totalled 1,462 MW, and overall 2,628 MW of generation was lost [X05, X06]. Secondary "
    "response held was 1,338 MW per Table 3 and inertia 219,632 MVA.s per Table 4 [X07, "
    "X08]. A faulty speed sensor and a failed bypass valve caused the Little Barford trips; "
    "GT1B tripped automatically (S07-E14) [X09, X10]. The DRC caused the Hornsea de-load "
    "[X11]. Frequency fell to 49.1 Hz and then 48.8 Hz and was below 49 Hz for 40 s "
    "[X12, X13, X14]. Demand was restored at 18:34 [X15].",
    [
        (
            "Findings",
            "[X01, X02, X03, X04, X05, X06, X07, X08, X09, X10, X11, X12, X13, X14, X15]",
        )
    ],
    incorrect_findings,
)
write("incorrect", incorrect)

# -- invalid: record locators (new kinds) and the general rules ------------------------
invalid_specs = {
    # an asset-log event cited with another record's evidence ID
    "invalid_record_wrong_evidence": [("F10", c("R03", "event:S01-EV09"))],
    # a control-log entry, asset-log event and witness response that do not exist
    "invalid_unknown_record": [
        ("F30", c("S07", "entry:S07-E99")),
        ("F12", c("S03", "event:S03-SOE-E77")),
        ("F40", c("S09", "response:S09-ORS-99")),
    ],
    # record locators without an ID
    "invalid_malformed_record_locator": [
        ("F01", c("R03", "event:")),
        ("F31", c("S07", "entry:")),
    ],
    # witness answers have no lines: S09 is cited by response only
    "invalid_line_locator_on_witness": [("F44", c("S09", "L3"))],
    # a time outside R07's demand series (14:00-19:00Z)
    "invalid_series_out_of_range": [
        ("F78", c("R07", "time:2019-08-09T12:00:00Z/2019-08-09T13:00:00Z"))
    ],
    # a line beyond the end of a data-return document
    "invalid_data_return_out_of_range": [("F64", c("S06", "L999"))],
    # an evidence ID the bundle does not hold
    "invalid_unknown_evidence": [("F42", c("S02", "L1"))],
}
for name, changes in invalid_specs.items():
    sub = copy.deepcopy(reference)
    found = by_id(sub)
    for fid, citation in changes:
        found[fid]["citations"].append(citation)
    write(name, sub, expect_valid=False)

over = copy.deepcopy(reference)
over["report"]["executive_summary"] = " ".join(["word"] * 601)
write("invalid_summary_601_words", over, expect_valid=False)

unknown_ref = copy.deepcopy(reference)
unknown_ref["report"]["sections"][0]["body"] += " See also [F99]."
write("invalid_unknown_ref", unknown_ref, expect_valid=False)
