"""Regenerate the grading fixtures (builder tool; not collected by pytest).

    uv run --frozen python tests/fixtures/build_fixtures.py

Writes ``submissions/*.json`` (from the reference submission plus deliberate errors) and
the two builder-fixture decisions files, which are bound to the sha256 of their fixture
submission, to the answer key's ``key_version`` and ``key_sha256``, and to the bundle
sha256: rerun this after changing the reference submission or the answer key.
"""

import copy
import json
from pathlib import Path

from environment.incident.catalogue import Catalogue
from environment.incident.grading import key_sha256
from environment.incident.submission import validate_submission

ENV = Path(__file__).resolve().parents[2]

REF = (
    ENV
    / "src/environment/tasks/gb_2019_electrical_disturbance/reference/reference_submission.json"
)
FIX = ENV / "tests/fixtures"
SUBS = FIX / "submissions"
DECS = FIX / "decisions"
SUBS.mkdir(parents=True, exist_ok=True)
DECS.mkdir(parents=True, exist_ok=True)
catalogue = Catalogue.load(ENV / "src/environment/incident/bundle")
key = json.loads((ENV / "src/environment/incident/private/answer_key.json").read_text())
reference = json.loads(REF.read_text())


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


# -- correct = reference --------------------------------------------------------------
correct = write("correct", reference)

# -- uncited: reference with every citation removed (derivations need citations) -------
uncited = copy.deepcopy(reference)
for f in uncited["findings"]:
    f["citations"] = []
    f.pop("derivation", None)
write("uncited", uncited)

# -- incomplete: frequency dimension only ---------------------------------------------
freq = [
    f
    for f in reference["findings"]
    if f["finding_id"] in ("F20", "F21", "F22", "F23", "F24", "F25")
]
incomplete = {
    "schema_version": "3.0",
    "variant_id": "baseline",
    "report": {
        "executive_summary": "Partial investigation covering the frequency record only. From "
        "the R01 1-s series: first minimum 49.083 Hz at 16:52:59 BST, event minimum 48.787 Hz at "
        "16:53:49, first sample at or above 50 Hz 50.001 Hz at 16:57:16, and 33 s strictly below "
        "49 Hz [F20, F21, F22, F23]. Sub-second crossings are not resolvable [F24, F25]. The "
        "initiating event, the generator trips and their causes were not examined.",
        "sections": [
            {"heading": "Frequency", "body": "See [F20, F21, F22, F23, F24, F25]."},
        ],
    },
    "findings": freq,
}
write("incomplete", incomplete)

# -- uncertain: mostly hypothesis/unknown, explicitly inconclusive -------------------
uncertain = {
    "schema_version": "3.0",
    "variant_id": "baseline",
    "report": {
        "executive_summary": "Inconclusive. I could not establish the initiating event, the "
        "generation-trip sequence or the frequency landmarks with confidence from the work I "
        "completed. A lightning strike on the Eaton Socon–Wymondley circuit may have started "
        "the event [U01]. The trip sequence and the frequency figures were not determined [U02, "
        "U03]. The Little Barford root causes are recorded as not established [U04], and the "
        "Hornsea de-load may relate to its control system [U05].",
        "sections": [
            {
                "heading": "Status",
                "body": "Explicitly inconclusive: see [U01, U02, U03, U04, U05].",
            },
        ],
    },
    "findings": [
        {
            "finding_id": "U01",
            "status": "hypothesis",
            "statement": "A lightning strike on the Eaton Socon–Wymondley circuit may have initiated "
            "the disturbance.",
            "citations": [c("R03", "L25-L27")],
        },
        {
            "finding_id": "U02",
            "status": "unknown",
            "statement": "The order and timing of the generator trips could not be established from "
            "the work completed.",
            "citations": [c("S03", "L20-L29")],
        },
        {
            "finding_id": "U03",
            "status": "unknown",
            "statement": "The frequency minima and the time below 49 Hz were not computed; R01 was "
            "retrieved but not analysed.",
            "citations": [c("R01", "L18-L24")],
        },
        {
            "finding_id": "U04",
            "status": "unknown",
            "statement": "Why the ST1C speed signals disagreed and why the steam bypass pressure "
            "rose are not established.",
            "citations": [c("S04", "L56-L63")],
        },
        {
            "finding_id": "U05",
            "status": "hypothesis",
            "statement": "The Hornsea de-load may relate to its control system.",
            "citations": [c("S01", "L55-L57")],
        },
    ],
}
write("uncertain", uncertain)

# -- incorrect -----------------------------------------------------------------------
incorrect = {
    "schema_version": "3.0",
    "variant_id": "baseline",
    "report": {
        "executive_summary": "The disturbance was initiated at 16:50:44 BST by lightning on the "
        "Blyth–Eccles–Stella West circuit [I01]; the Eaton Socon–Wymondley circuit then faulted "
        "again on re-energisation [I02]. Hornsea lost 400 MW and Little Barford's three units "
        "tripped [I10, I11, I12, I13]. The frequency was arrested at 49.1 Hz, fell to 48.8 Hz, "
        "returned to 50 Hz at 16:57 and was below 49 Hz for 16 seconds [I20, I21, I22, I23]. "
        "The ST1C trip was caused by a faulty speed sensor and GT1A by a failed bypass valve "
        "[I30, I31]; the Hornsea de-load was caused by its reactive compensator [I32].",
        "sections": [
            {
                "heading": "Account",
                "body": "See [I01, I02, I03, I10, I11, I12, I13]. Frequency: "
                "[I20, I21, I22, I23]. Causes: [I30, I31, I32].",
            },
        ],
    },
    "findings": [
        {
            "finding_id": "I01",
            "status": "reported",
            "statement": "The disturbance was initiated at 16:50:44 BST by a lightning strike on the "
            "Blyth–Eccles–Stella West 400 kV circuit.",
            "citations": [c("R03", "L73-L77")],
            "event_time": T("16:50:44"),
        },
        {
            "finding_id": "I02",
            "status": "reported",
            "statement": "The Eaton Socon–Wymondley circuit suffered a second fault when it was "
            "re-energised at 16:52:53.",
            "citations": [c("R03", "L49-L50")],
            "event_time": T("16:52:53"),
        },
        {
            "finding_id": "I03",
            "status": "reported",
            "statement": "Protection cleared the faults in under 75 ms.",
            "citations": [c("R03", "L105-L107")],
        },
        {
            "finding_id": "I10",
            "status": "reported",
            "statement": "Hornsea One reduced its output by 400 MW at 15:52:33.728 BST.",
            "citations": [c("S01", "L33-L34")],
            "quantity": {
                "value": 400,
                "unit": "MW",
                "basis": "read from the event log",
            },
            "event_time": T("15:52:33.728"),
        },
        {
            "finding_id": "I11",
            "status": "reported",
            "statement": "Little Barford ST1C tripped with 244 MW at about 16:52:35.2 "
            "BST (T + 1.185 s, T = 16:52:34 ± 0.5 s).",
            "citations": [c("S03", "L6-L9"), c("S03", "L23-L25"), c("S03", "L34")],
            "quantity": {
                "value": 244,
                "unit": "MW",
                "basis": "reported output at trip",
            },
            "event_time": T("16:52:35.185"),
        },
        {
            "finding_id": "I12",
            "status": "reported",
            "statement": "GT1A tripped with 210 MW at about 16:53:31.6 BST "
            "(T + 57.620 s, ± 0.5 s datum).",
            "citations": [c("S03", "L26-L27"), c("S03", "L35")],
            "quantity": {
                "value": 210,
                "unit": "MW",
                "basis": "reported output at trip",
            },
            "event_time": T("16:53:31.620"),
        },
        {
            "finding_id": "I13",
            "status": "reported",
            "statement": "GT1B tripped automatically on high steam pressure at 16:53:58 BST, losing "
            "187 MW.",
            "citations": [c("S03", "L36")],
            "quantity": {
                "value": 187,
                "unit": "MW",
                "basis": "reported output at trip",
            },
            "event_time": T("16:53:58"),
        },
        {
            "finding_id": "I20",
            "status": "observed",
            "statement": "Frequency was arrested at 49.1 Hz at 16:52:58 BST.",
            "citations": [
                c("R01", "time:2019-08-09T16:52:50+01:00/2019-08-09T16:53:05+01:00")
            ],
            "quantity": {"value": 49.1, "unit": "Hz", "basis": "frequency record"},
            "event_time": T("16:52:58"),
        },
        {
            "finding_id": "I21",
            "status": "observed",
            "statement": "The frequency fell to a minimum of 48.8 Hz at 16:53:49.398 BST.",
            "citations": [
                c("R01", "time:2019-08-09T16:53:40+01:00/2019-08-09T16:54:00+01:00")
            ],
            "quantity": {"value": 48.8, "unit": "Hz", "basis": "frequency record"},
            "event_time": T("16:53:49.398"),
        },
        {
            "finding_id": "I22",
            "status": "observed",
            "statement": "The frequency returned to 50 Hz at 16:57 BST.",
            "citations": [
                c("R01", "time:2019-08-09T16:56:00+01:00/2019-08-09T16:58:00+01:00")
            ],
            "quantity": {"value": 50.0, "unit": "Hz", "basis": "frequency record"},
            "event_time": T("16:57:00"),
        },
        {
            "finding_id": "I23",
            "status": "observed",
            "statement": "The frequency was below 49 Hz for 16 seconds.",
            "citations": [
                c("R01", "time:2019-08-09T16:53:41+01:00/2019-08-09T16:53:56+01:00")
            ],
            "quantity": {"value": 16, "unit": "s", "basis": "frequency record"},
        },
        {
            "finding_id": "I30",
            "status": "reported",
            "statement": "The root cause of the ST1C trip was a faulty speed sensor.",
            "citations": [c("S03", "L42-L43")],
        },
        {
            "finding_id": "I31",
            "status": "reported",
            "statement": "GT1A tripped because a steam bypass valve failed to operate correctly, "
            "which caused the high pressure.",
            "citations": [c("S04", "L50-L52")],
        },
        {
            "finding_id": "I32",
            "status": "reported",
            "statement": "The Hornsea de-load was caused by the Dynamic Reactive Compensator.",
            "citations": [c("S01", "L77-L78")],
        },
    ],
}
write("incorrect", incorrect)

# -- invalid fixtures ------------------------------------------------------------------
bad = copy.deepcopy(reference)
bad["findings"][0]["status"] = "certain"
del bad["findings"][1]["citations"]
bad["findings"][2]["confidence"] = "high"
write("invalid_schema", bad, expect_valid=False)

bad = copy.deepcopy(reference)
bad["findings"][0]["citations"] = [c("R04", "L1-L5")]
write("invalid_unknown_evidence", bad, expect_valid=False)

bad = copy.deepcopy(reference)
bad["findings"][0]["citations"] = [c("R03", "L999")]
bad["findings"][10]["citations"] = [c("R01", "time:2019-08-09T18:00:00+01:00")]
bad["findings"][11]["citations"] = [c("S03", "lines 3 to 4")]
write("invalid_bad_locator", bad, expect_valid=False)

bad = copy.deepcopy(reference)
words = bad["report"]["executive_summary"].split()
filler = ("The investigation records each claim with its evidence. " * 200).split()
bad["report"]["executive_summary"] = " ".join((words + filler)[:601])
write("invalid_summary_601_words", bad, expect_valid=False)

bad = copy.deepcopy(reference)
bad["findings"][1]["finding_id"] = "F01"
write("invalid_duplicate_ids", bad, expect_valid=False)

bad = copy.deepcopy(reference)
bad["report"]["sections"][0]["body"] += " See also [F99]."
write("invalid_unknown_ref", bad, expect_valid=False)

# -- decisions fixtures ----------------------------------------------------------------
FIXTURE_NOTE = (
    "BUILDER FIXTURE for automated tests of the decisions merge. It is NOT a domain review "
    "and must never be used to describe results as validated."
)


def decisions(sub_result, criteria, assertions, severe, notes):
    return {
        "_note": FIXTURE_NOTE,
        "decisions_schema": "gb2019-grading-decisions/1",
        "decisions_version": "1",
        "builder_fixture": True,
        "reviewer": "grading builder (fixture; not a domain reviewer)",
        "date": "2026-10-19",
        "binding": {
            "submission_sha256": sub_result.sha256,
            "key_version": key["key_version"],
            "key_sha256": key_sha256(key),
            "bundle_sha256": catalogue.bundle_sha256,
        },
        "criteria": criteria,
        "assertions": assertions,
        "severe_flags": severe,
        "explanation_quality": notes,
    }


crit_ids = [cr["criterion_id"] for cr in key["criteria"]]
ref_by_dim = {
    "D1.1": ["F01", "F02"],
    "D1.2": ["F02"],
    "D1.3": ["F03", "F04", "F05"],
    "D1.4": ["F05", "F06", "F07"],
    "D1.N": ["F02", "F08"],
    "D2.1": ["F10"],
    "D2.2": ["F11"],
    "D2.3": ["F12"],
    "D2.4": ["F13"],
    "D2.5": ["F15", "F16"],
    "D3.1": ["F20"],
    "D3.2": ["F21"],
    "D3.3": ["F22"],
    "D3.4": ["F23"],
    "D3.5": ["F23", "F24", "F25"],
    "D4.1": ["F30", "F31", "F32", "F33"],
    "D4.2": ["F34"],
    "D4.3": ["F35", "F36"],
    "D4.4": ["F37", "F38", "F39", "F40"],
}
correct_dec = decisions(
    correct,
    {
        cid: {
            "content": 1,
            "evidence_support": 1,
            "finding_ids": ref_by_dim[cid],
            "notes": "fixture",
        }
        for cid in crit_ids
        if not cid.startswith("D3.") or cid == "D3.5"
    },
    {
        f["finding_id"]: {"verdict": "supported", "notes": "fixture"}
        for f in reference["findings"]
        if f["status"] in ("observed", "reported", "inferred")
    },
    [],
    {
        "notes": "fixture: clear, cited account",
        "by_dimension": {d: "fixture" for d in ("D1", "D2", "D3", "D4")},
    },
)
(DECS / "correct.decisions.json").write_text(
    json.dumps(correct_dec, indent=2, ensure_ascii=False) + "\n"
)

inc = validate_submission(incorrect, catalogue)
incorrect_dec = decisions(
    inc,
    {
        "D1.1": {
            "content": 0,
            "evidence_support": None,
            "finding_ids": ["I01"],
            "notes": "wrong initiator",
        },
        "D1.2": {
            "content": 0,
            "evidence_support": None,
            "finding_ids": [],
            "notes": "fault time absent",
        },
        "D1.3": {
            "content": 0.5,
            "evidence_support": 1,
            "finding_ids": ["I03"],
            "notes": "Ofgem summary only",
        },
        "D1.4": {
            "content": 0,
            "evidence_support": None,
            "finding_ids": ["I02"],
            "notes": "reclose called a second fault",
        },
        "D1.N": {
            "content": 0,
            "evidence_support": None,
            "finding_ids": ["I01"],
            "notes": "other trip as initiator",
        },
        "D2.1": {
            "content": 0,
            "evidence_support": None,
            "finding_ids": ["I10"],
            "notes": "400 MW, UTC time as BST",
        },
        "D2.2": {
            "content": 1,
            "evidence_support": 1,
            "finding_ids": ["I11"],
            "notes": "",
        },
        "D2.3": {
            "content": 1,
            "evidence_support": 1,
            "finding_ids": ["I12"],
            "notes": "",
        },
        "D2.4": {
            "content": 0.5,
            "evidence_support": 1,
            "finding_ids": ["I13"],
            "notes": "called automatic",
        },
        "D2.5": {
            "content": 0.5,
            "evidence_support": 0,
            "finding_ids": ["I11", "I12", "I13"],
            "notes": "Hornsea time wrong",
        },
        "D3.5": {
            "content": 0,
            "evidence_support": None,
            "finding_ids": [],
            "notes": "absent",
        },
        "D4.1": {
            "content": 0,
            "evidence_support": None,
            "finding_ids": ["I32"],
            "notes": "DRC asserted",
        },
        "D4.2": {
            "content": 0,
            "evidence_support": None,
            "finding_ids": ["I30"],
            "notes": "root cause, not mechanism",
        },
        "D4.3": {
            "content": 0.5,
            "evidence_support": 1,
            "finding_ids": ["I13", "I31"],
            "notes": "GT1B automatic",
        },
        "D4.4": {
            "content": 0,
            "evidence_support": None,
            "finding_ids": ["I30", "I31"],
            "notes": "SF1 confirmed",
        },
    },
    {
        "I01": {"verdict": "contradicted", "notes": "R03 E2: no power losses"},
        "I02": {"verdict": "contradicted", "notes": "R03 C8-C9: designed reclose"},
        "I03": {"verdict": "supported", "notes": "R03 G7"},
        "I10": {"verdict": "contradicted", "notes": "S01: 799 - 62 = 737 MW reduction"},
        "I11": {"verdict": "supported"},
        "I12": {"verdict": "supported"},
        "I13": {"verdict": "contradicted", "notes": "manual trip"},
        "I20": {"verdict": "contradicted", "notes": "R01: 49.083 Hz at 16:52:59"},
        "I21": {"verdict": "contradicted", "notes": "R01: 48.787 Hz"},
        "I22": {"verdict": "contradicted", "notes": "R01: 16:57:16"},
        "I23": {"verdict": "contradicted", "notes": "R01: 33 s"},
        "I30": {"verdict": "unsupported", "notes": "SF1"},
        "I31": {"verdict": "unsupported", "notes": "SF1"},
        "I32": {"verdict": "contradicted", "notes": "S01 B1"},
    },
    [
        {
            "flag_id": "SF1",
            "finding_ids": ["I30"],
            "confirmed": True,
            "notes": "fixture",
        },
        {
            "flag_id": "SF1",
            "finding_ids": ["I31"],
            "confirmed": True,
            "notes": "fixture",
        },
        {
            "flag_id": "SF1",
            "locations": ["report.executive_summary"],
            "confirmed": True,
            "notes": "fixture",
        },
    ],
    {"notes": "fixture: confident but wrong account", "by_dimension": {}},
)
(DECS / "incorrect.decisions.json").write_text(
    json.dumps(incorrect_dec, indent=2, ensure_ascii=False) + "\n"
)
(FIX / "README.md").write_text(
    "# Grading fixtures (builder-made)\n\n"
    "`submissions/`: v3 submissions for the grading tests. `correct.json` is a copy of the "
    "reference submission; `uncited.json` is the reference with every citation (and therefore "
    "every derivation) removed; `incorrect.json` deliberately contains wrong landmark values, "
    "rounded prose times, a wrong initiator, an automatic GT1B trip and asserted Little Barford "
    "root causes; `uncertain.json` is explicitly inconclusive; `incomplete.json` covers the "
    "frequency dimension only; `invalid_*.json` must be rejected by `validate_submission`.\n\n"
    "`decisions/`: grading-decisions files used to test the merge of human decisions. They are "
    "BUILDER FIXTURES (`builder_fixture: true`), not domain reviews, and are bound to the "
    "sha256 of their fixture submission, to key version "
    f"{key['key_version']} and the key's content sha256, and to the bundle sha256. "
    "Regenerate everything with `uv run --frozen python tests/fixtures/build_fixtures.py` "
    "after changing the reference submission or the answer key.\n\n"
    "`live/`: real live-run submissions (not builder-made, not regenerated by this script), "
    "used by `tests/test_grading_live_runs.py`; see `live/README.md`.\n",
    encoding="utf-8",
)
print("decisions written")
