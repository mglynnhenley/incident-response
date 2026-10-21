"""Regenerate the full-investigation grading fixtures (builder tool; not collected by pytest).

    uv run --frozen python tests/fixtures/fi/build_fi_fixtures.py

Writes ``submissions/*.json`` from the full-investigation reference submission plus
deliberate errors, validating each against the full-investigation bundle (valid fixtures
must pass ``validate_submission``; ``invalid_*`` must fail it). Rerun after changing the
reference submission. The fixtures are not bound to a key version: the tests
(``tests/test_fi_reference_fixtures.py``) grade them with the installed key and check the
outcomes listed in ``README.md``.
"""

import copy
import json
from pathlib import Path

from environment.incident.catalogue import Catalogue
from environment.incident.submission import validate_submission

ENV = Path(__file__).resolve().parents[3]
REF = (
    ENV
    / "src/environment/tasks/gb_2019_full_investigation/reference/reference_submission.json"
)
SR_INCORRECT = ENV / "tests/fixtures/sr/submissions/incorrect.json"
SUBS = Path(__file__).resolve().parent / "submissions"
SUBS.mkdir(parents=True, exist_ok=True)
catalogue = Catalogue.load(ENV / "src/environment/incident/bundles/full_investigation")
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


def finding(fid, statement, status, *citations, **extra):
    out = {
        "finding_id": fid,
        "statement": statement,
        "status": status,
        "citations": list(citations),
    }
    out.update(extra)
    return out


# -- correct = reference ----------------------------------------------------------------
write("correct", reference)

# -- uncited: every citation (and therefore every derivation) removed --------------------
uncited = copy.deepcopy(reference)
for f in uncited["findings"]:
    f["citations"] = []
    f.pop("derivation", None)
write("uncited", uncited)

# -- incomplete: the initiating event, the frequency record and the rail impact only ----
keep = (
    "F01", "F02", "F03", "F04", "F20", "F21", "F22", "F23", "F24", "F100", "F101",
    "F102", "F103", "F104", "F107", "F108",
)  # fmt: skip
ref = by_id(reference)
incomplete = shell(
    "Partial investigation: the initiating event, the measured frequency and the rail "
    "impact only. A lightning strike caused a single-phase (blue) to earth fault on one "
    "Eaton Socon–Wymondley 400 kV circuit at 16:52:33.490 BST, cleared in 70 ms and 74 ms "
    "and reclosed at 16:52:53 [F01, F02, F03, F04]. From the R01 1-s series: first "
    "minimum 49.083 Hz at 16:52:59 BST, event minimum 48.787 Hz at 16:53:49, first sample "
    "at or above 50 Hz at 16:57:16, and 33 s strictly below 49 Hz [F20, F21, F22, F23, "
    "F24]. ORR reports 29 Class 700/717 trains locked out by their own protection, 22 "
    "needing a technician, 7 restored by drivers and 31 stranded; 371 trains were "
    "cancelled and 220 part-cancelled [F100, F101, F102, F103, F104, F107, F108]. "
    "Generation losses, LFDD, restoration, other services, communications, compliance "
    "and causes were not examined.",
    [
        ("Initiating event", "See [F01, F02, F03, F04]."),
        ("Frequency", "See [F20, F21, F22, F23, F24]."),
        ("Rail", "See [F100, F101, F102, F103, F104, F107, F108]."),
    ],
    [copy.deepcopy(ref[fid]) for fid in keep],
)
write("incomplete", incomplete)

# -- uncertain: explicitly inconclusive --------------------------------------------------
uncertain = shell(
    "Explicitly inconclusive: I could not establish the sequence of events, its "
    "consequences or its causes with enough confidence to report findings. No "
    "conclusions are offered.",
    [("Scope", "No findings are made.")],
    [],
)
write("uncertain", uncertain)

# -- incorrect: increment A's errors plus wrong consequences, attributions and outcomes --
sr_incorrect = json.loads(SR_INCORRECT.read_text(encoding="utf-8"))
incorrect_findings = copy.deepcopy(sr_incorrect["findings"])  # X01-X15
incorrect_findings += [
    # SF3: the excluded January 2020 enforcement settlements asserted
    finding(
        "X16",
        "In January 2020 Ofgem announced that RWE and Ørsted each agreed to make voluntary "
        "payments of £4.5m to the redress scheme, and that EPN and SPN paid £1.5m.",
        "reported",
        c("S10", "L117-L119"),
    ),
    # a legal finding of breach asserted
    finding(
        "X17",
        "Ofgem found that Hornsea One breached its licence and was found to be in breach "
        "of the Grid Code.",
        "reported",
        c("S10", "L136-L142"),
    ),
    # ORR's and GTR's counts merged into one account without attribution
    finding(
        "X18",
        "29 Class 700 and 717 trains were locked out: 27 were reset by their drivers and "
        "30 needed a technician to attend on site.",
        "reported",
        c("S08", "L120-L127"),
    ),
    # the Class 387s said to have shut down themselves
    finding(
        "X19",
        "Two Class 387 trains also shut down when the frequency fell below 49 Hz.",
        "reported",
        c("S08", "L120-L127"),
    ),
    # the software versions' recovery reversed
    finding(
        "X20",
        "Units on software 3.25.x went into a permanent lock-out needing a technician, "
        "while units on 3.27.x could be reset by drivers.",
        "reported",
        c("S08", "L185-L189"),
    ),
    # the traction supply loss given as the cause of the stoppages
    finding(
        "X21",
        "The Thameslink Class 700 trains stopped because their overhead-line traction "
        "supply was lost when LFDD disconnected the railway.",
        "reported",
        c("S08", "L86-L89"),
    ),
    # the rail protection threshold misstated
    finding(
        "X22",
        "The Class 700 and 717 protection tripped at 48.8 Hz.",
        "reported",
        c("S08", "L133-L135"),
    ),
    # delay measures mixed
    finding(
        "X23",
        "Rail services suffered 873 delay minutes.",
        "reported",
        c("S08", "L103-L106"),
    ),
    # essential services misattributed (one finding each: see README)
    finding(
        "X24",
        "Newcastle Airport lost supply when its own site protection systems tripped.",
        "reported",
        c("S11", "L78-L84"),
    ),
    finding(
        "X32",
        "Ipswich Hospital was disconnected by the LFDD scheme.",
        "reported",
        c("S11", "L58-L62"),
    ),
    finding(
        "X25",
        "An oil refinery was disconnected by LFDD, and the Stanlow refinery flared when its "
        "grid supply failed on 9 August.",
        "reported",
        c("S11", "L121-L125"),
        c("S11", "L159-L160"),
    ),
    # the early reconnection given to another DNO
    finding(
        "X26",
        "Western Power Distribution reconnected customers before being instructed by the "
        "ESO.",
        "reported",
        c("S10", "L160-L166"),
    ),
    # the 17:51 / 18:00 discrepancy forced to one time, with no record named
    finding(
        "X27",
        "The ESO first contacted Ofgem at 18:00 BST.",
        "reported",
        c("R10", "L194-L197"),
        event_time=T("18:00:00"),
    ),
    finding(
        "X28",
        "The ESO first contacted BEIS at 17:00 BST.",
        "reported",
        c("R10", "L194-L197"),
        event_time=T("17:00:00"),
    ),
    # communications presented as a cause
    finding(
        "X29",
        "The late ESO communications caused the demand disconnection to last longer and "
        "prolonged the outage.",
        "inferred",
        c("S07", "L39-L40"),
    ),
    # an unverified legal obligation relied on
    finding(
        "X30",
        "Under ESQCR and Grid Code OC7 the DNOs had to report the incident to the ESO "
        "within an hour.",
        "reported",
        c("R10", "L113-L116"),
    ),
    # an invented witness record
    finding(
        "X31",
        "GTR's fleet log S09-GTR-42 shows that 40 trains needed a technician.",
        "reported",
        c("S08", "L33"),
    ),
]
refs = ", ".join(f["finding_id"] for f in incorrect_findings)
incorrect = shell(
    sr_incorrect["report"]["executive_summary"]
    + " On the railway 29 trains locked out, 27 reset by drivers and 30 by technicians "
    "[X18]; the Class 387s shut down too and the traction supply was lost [X19, X21]. "
    "Newcastle Airport tripped on its own protection and Ipswich Hospital was cut by "
    "LFDD [X24, X32]. The ESO contacted Ofgem at 18:00 [X27]. Late communications "
    "prolonged the outage [X29]. It is established that the root cause was a faulty "
    "speed sensor [X09]. In January 2020 RWE and Ørsted paid £4.5m each into the redress "
    "scheme [X16].",
    [
        ("Findings", f"[{refs}]"),
        (
            "Recommendations",
            "1. Ofgem should fine the generators again [X16, X17].",
        ),
        (
            "Further evidence requests",
            "1. None needed [X31].",
        ),
    ],
    incorrect_findings,
)
write("incorrect", incorrect)

# -- invalid: record locators on the new evidence, and the general rules ----------------
invalid_specs = {
    # a REMIT asset-log event cited under another evidence ID
    "invalid_record_wrong_evidence": [
        ("F156", c("R11", "event:R09-REMIT-00056773-r1"))
    ],
    # an entry, an event and a witness response that do not exist
    "invalid_unknown_record": [
        ("F111", c("R11", "entry:R11-NR-999999")),
        ("F156", c("R09", "event:R09-REMIT-99999999-r1")),
        ("F102", c("S09", "response:S09-GTR-42")),
    ],
    # record locators without an ID
    "invalid_malformed_record_locator": [
        ("F151", c("R09", "entry:")),
        ("F156", c("R09", "event:")),
    ],
    # witness answers have no lines: S09 is cited by response only
    "invalid_line_locator_on_witness": [("F104", c("S09", "L3"))],
    # a line beyond the end of a new document
    "invalid_line_out_of_range": [("F102", c("S08", "L999"))],
    # a time outside R01's series (16:40-17:45 BST)
    "invalid_series_out_of_range": [
        ("F20", c("R01", "time:2019-08-09T12:00:00+01:00/2019-08-09T12:05:00+01:00"))
    ],
    # a line beyond the end of a data-return document
    "invalid_data_return_out_of_range": [("F71", c("S05", "L999"))],
    # an evidence ID the bundle does not hold
    "invalid_unknown_evidence": [("F130", c("S13", "L1"))],
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
