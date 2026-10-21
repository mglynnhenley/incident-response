"""The system-response answer key: identity, coverage of the handoff criteria, report
passages on their PDF pages, visible-evidence locators and tokens, tolerances and the
accounting-basis figures."""

from __future__ import annotations

import json
import re
from fractions import Fraction

import pytest
from sr_grading_support import (
    HANDOFF_DIR,
    TEXT_DIR,
    catalogue,
    criteria,
    key,
    norm,
    page_texts,
)

from environment.incident import frequency as fq
from environment.incident import sr_grading
from environment.incident.paths import SYSTEM_RESPONSE_BUNDLE_DIR

KEY = key()
CAT = catalogue()
CRITERIA = criteria()
TASKS = [
    "T01",
    "T02",
    "T03",
    "T04",
    "T05",
    "T06",
    "T07",
    "T08",
    "T09",
    "T12",
    "T16",
    "T17",
]
CSV_REL = "R01/frequency_2019-08-09_1640-1745_BST.csv"


def test_key_identity_review_status_and_bundle_binding():
    assert KEY["key_schema"] == sr_grading.KEY_SCHEMA
    assert KEY["key_version"] == "0.1.1"
    assert KEY["review"]["status"] == "pending_domain_review"
    assert KEY["review_status"] == KEY["review"]["status"]
    assert KEY["review"]["reviewed_by"] == [] and KEY["review"]["reviewed_on"] is None
    bundle = KEY["bundle"]
    assert bundle["bundle_id"] == CAT.bundle_id
    assert bundle["bundle_version"] == CAT.bundle_version == "0.1.0"
    assert bundle["bundle_sha256"] == CAT.bundle_sha256
    artifact = next(a for a in CAT.get("R01").artifacts if a.timeseries is not None)
    assert bundle["r01_csv"] == {"file": CSV_REL, "sha256": artifact.sha256}
    assert sr_grading.DEFAULT_KEY_PATH.parent.name == "system_response"


def test_tasks_and_dimensions():
    dims = {d["dimension_id"]: d for d in KEY["dimensions"]}
    assert list(dims) == TASKS
    listed = [cid for d in KEY["dimensions"] for cid in d["criteria"]]
    assert listed == [c["criterion_id"] for c in KEY["criteria"]]
    for cid, crit in CRITERIA.items():
        assert crit["task"] == crit["dimension"] == cid.split(".")[0]
        assert crit["task_criterion"].startswith(crit["task"] + ".")


def _blueprint() -> dict:
    path = HANDOFF_DIR / "contracts" / "task_blueprint.json"
    if not path.exists():
        pytest.skip("builder-only handoff blueprint not present")
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_handoff_criterion_is_covered_or_deferred():
    blueprint = _blueprint()
    deferred = {d["criterion_id"] for d in KEY["deferred_criteria"]}
    assert deferred == {"T04.02"}
    covered = {c["task_criterion"] for c in KEY["criteria"]}
    for task in blueprint["tasks"]:
        if task["task_id"] not in TASKS:
            continue
        weight = {d["dimension_id"]: d for d in KEY["dimensions"]}[task["task_id"]]
        assert weight["handoff_weight"] == task["weight"]
        for crit in task["criteria"]:
            cid = crit["criterion_id"]
            assert cid in covered or cid in deferred, cid
    # nothing beyond the handoff except the marked increment-A addition
    extra = {
        c["criterion_id"]
        for c in KEY["criteria"]
        if c["origin"] == "increment_A_addition"
    }
    assert extra == {"T12.05"}


def test_split_fields_have_equal_subweights_summing_to_one():
    groups: dict[str, list[dict]] = {}
    for crit in KEY["criteria"]:
        groups.setdefault(crit["task_criterion"], []).append(crit)
    for parent, fields in groups.items():
        weights = {Fraction(c["subweight"]).limit_denominator(12) for c in fields}
        assert len(weights) == 1, parent
        assert sum(Fraction(c["subweight"]).limit_denominator(12) for c in fields) == 1
        if len(fields) > 1:
            assert all(c["field"] and c["origin"] == "handoff_split" for c in fields)
            assert all(
                re.fullmatch(rf"{re.escape(parent)}[a-c]", c["criterion_id"])
                for c in fields
            )


def test_criterion_fields_and_modes():
    judge = set(KEY["judge"]["criteria"])
    for cid, crit in CRITERIA.items():
        assert crit["assessment_mode"] in sr_grading.MODES, cid
        assert crit["title"].strip() and crit["expectation"].strip(), cid
        assert crit["handoff_text"].strip(), cid
        assert crit["tolerances"], cid
        assert crit["report_passages"], cid
        assert crit["visible_evidence"], cid
        assert any(
            v.get("role", "primary") == "primary" for v in crit["visible_evidence"]
        ), cid
        assert crit["examples"]["positive"] and crit["examples"]["negative"], cid
        assert crit["accepted_alternatives"], cid
        assert crit["polarity"] == ("negative" if cid == "T06.05" else "positive")
        assert (crit["assessment_mode"] == "judge") == (cid in judge), cid
        if crit["origin"] in ("handoff_adapted", "increment_A_addition"):
            assert crit["adaptation"].strip(), cid
    auto_numeric = {
        c for c, v in CRITERIA.items() if v["assessment_mode"] == "auto_numeric"
    }
    assert auto_numeric == {"T03.01", "T03.02", "T03.03", "T04.01"}


def test_numeric_tolerances_follow_the_handoff_rules():
    for cid in ("T03.01", "T03.02", "T03.03"):
        auto = CRITERIA[cid]["auto"]
        assert auto["value"]["abs_tol"] == 0.002 and auto["time"]["tol_s"] == 1
    assert CRITERIA["T04.01"]["auto"]["value"] == {
        "expected": 33,
        "full_abs": 1,
        "half_abs": 3,
    }
    assert CRITERIA["T04.03"]["auto"]["convention_check"]["criterion"] == "T04.01"
    for cid in ("T02.02a", "T02.02b", "T02.03a", "T02.03b"):
        mw = next(e for e in CRITERIA[cid]["auto"]["elements"] if e["id"] == "mw")
        assert (mw["full_rel"], mw["half_rel"]) == (0.10, 0.25)
    fault = CRITERIA["T01.02"]["auto"]["elements"][0]
    assert fault["tol_s"] == 1 and fault["expected"] == "2019-08-09T16:52:33.490+01:00"
    for cid, expected in (
        ("T05.01a", "2019-08-09T16:58:00+01:00"),
        ("T05.01b", "2019-08-09T17:16:00+01:00"),
        ("T05.02", "2019-08-09T17:37:00+01:00"),
    ):
        element = CRITERIA[cid]["auto"]["elements"][0]
        assert element["tol_s"] == 120 and element["expected"] == expected
    figures = {f["figure_id"]: f for f in KEY["accounting"]["figures"]}
    assert figures["GEN_ESO_1878"]["match_abs"] == 1
    assert sorted(figures["GEN_ESO_1878"]["components"]) == sorted(
        [244, 737, 150, 350, 210, 187]
    )
    assert sum(figures["GEN_ESO_1878"]["components"]) == 1878


def test_frequency_expectations_come_from_the_frozen_series():
    lm = fq.reference_landmarks(fq.load_series(SYSTEM_RESPONSE_BUNDLE_DIR / CSV_REL))
    for cid, name in (
        ("T03.01", "first_local_minimum"),
        ("T03.02", "event_minimum"),
        ("T03.03", "first_at_or_above_50_after_minimum"),
    ):
        expected = CRITERIA[cid]["expected"]
        assert expected["value_hz"] == lm[name]["value_hz"]
        assert expected["time"] == lm[name]["time"]
        assert CRITERIA[cid]["auto"]["value"]["expected"] == lm[name]["value_hz"]
    assert (
        CRITERIA["T04.01"]["expected"]["duration_s"]
        == lm["below_49"]["covered_below_s"]
        == 33
    )


PASSAGES = [
    (c["criterion_id"], i, p)
    for c in KEY["criteria"]
    for i, p in enumerate(c["report_passages"])
]


@pytest.mark.skipif(
    not TEXT_DIR.is_dir(), reason="builder-only extracted PDF text not present"
)
@pytest.mark.parametrize(
    ("cid", "index", "passage"), PASSAGES, ids=[f"{c}-{i}" for c, i, _ in PASSAGES]
)
def test_report_passage_quote_is_on_the_stated_pdf_page(cid, index, passage):
    page = page_texts(passage["source_id"]).get(passage["pdf_page"])
    assert page is not None, (passage["source_id"], passage["pdf_page"])
    assert norm(passage["quote"]) in norm(page), (cid, passage["quote"])
    assert len(passage["quote"].split()) >= 3
    if passage["source_id"] == "ESO":
        assert passage["printed_page"] == passage["pdf_page"] + 1
    elif passage["source_id"] in ("APP", "E3C", "E3C-I"):
        assert passage["printed_page"] is None
    elif passage["source_id"] == "OFG":
        assert passage["printed_page"] == passage["pdf_page"]
    assert passage["role"] in {
        "expected",
        "alternative_account",
        "conflicting_account",
        "context",
    }


def test_every_criterion_has_an_expected_or_context_passage():
    for cid, crit in CRITERIA.items():
        roles = {p["role"] for p in crit["report_passages"]}
        assert roles & {"expected", "context"}, cid


EVIDENCE = [
    (c["criterion_id"], i, v)
    for c in KEY["criteria"]
    for i, v in enumerate(c["visible_evidence"])
]


@pytest.mark.parametrize(
    ("cid", "index", "item"), EVIDENCE, ids=[f"{c}-{i}" for c, i, _ in EVIDENCE]
)
def test_visible_evidence_resolves_and_contains_tokens(cid, index, item):
    assert item["must_contain"], (cid, item)
    assert item["role"] in ("primary", "context")
    text = norm(sr_grading.resolve_text(CAT, item["evidence_id"], item["locator"]))
    for token in item["must_contain"]:
        assert norm(token) in text, (cid, item["locator"], token)


def test_visible_evidence_uses_every_locator_kind_and_data_return_documents():
    kinds = set()
    docs = set()
    for _, _, item in EVIDENCE:
        loc = item["locator"]
        kinds.add(loc.split(":", 1)[0] if ":" in loc else "lines")
        docs.add(item["evidence_id"])
    assert {"lines", "time", "row", "event", "entry", "response"} <= kinds
    data_return_only = {
        d for d, mode in CAT.sources.access.items() if mode == "data_return"
    }
    assert data_return_only == {"S05", "S06"} and data_return_only <= docs
    assert "S09" in docs  # witness responses


def _walk_patterns(obj, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if (
                k
                in (
                    "all",
                    "none",
                    "context",
                    "context_any",
                    "trigger_any",
                    "unless_any",
                    "statement_any",
                    "uncertainty_patterns",
                    "inferential_patterns",
                    "mechanism_hedge_patterns",
                    "mechanism_negation_patterns",
                    "patterns",
                    "sources",
                    "verbs",
                    "definition_any",
                    "mismatch_any",
                    "qualifier_any",
                    "near_any",
                )
                and isinstance(v, list)
                and v
                and isinstance(v[0], (str, list))
            ):
                groups = v if isinstance(v[0], list) else [v]
                for group in groups:
                    for pattern in group:
                        found.append(pattern)
            else:
                _walk_patterns(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _walk_patterns(v, found)


def test_all_patterns_compile():
    found: list[str] = []
    _walk_patterns(KEY, found)
    for entity_patterns in KEY["accounting"]["source_entities"].values():
        found += entity_patterns
    assert len(found) > 500
    for pattern in found:
        re.compile(pattern)


def test_accounting_figures_are_consistent_and_visible():
    accounting = KEY["accounting"]
    entities = set(accounting["source_entities"])
    figures = {f["figure_id"]: f for f in accounting["figures"]}
    assert len(figures) == len(accounting["figures"])
    bundle_text = norm(" ".join(" ".join(CAT.get(d).lines) for d in CAT.ids())).replace(
        ",", ""
    )
    for fid, fig in figures.items():
        assert set(fig.get("sources", [])) <= entities, fid
        assert set(fig.get("wrong_sources", [])) <= entities, fid
        assert not set(fig.get("sources", [])) & set(fig.get("wrong_sources", [])), fid
        assert fig["basis"] and fig["stage"] and fig["value_status"], fid
        values = fig["range"] if "range" in fig else [fig["value"]]
        for value in values:
            printed = {f"{value:g}"}
            if fig["unit"] == "GVA.s":
                printed.add(f"{value * 1000:g}")
            assert any(p in bundle_text for p in printed), (fid, printed)
    used = set()
    for crit in KEY["criteria"]:
        for el in (crit.get("auto") or {}).get("elements", []):
            if el.get("type") == "figure":
                used.update(el["figures"])
        for cap in (crit.get("auto") or {}).get("accounting_caps", []):
            used.update(cap.get("figures", []))
            for group in cap.get("groups", []):
                assert group in {g["id"] for g in accounting["overlap_groups"]}
    assert used <= set(figures)
    for key_figure in (
        "GEN_ESO_1878",
        "GEN_OFG_1990",
        "LFDD_931",
        "LFDD_OFG_892",
        "RESP_SECONDARY_1314",
        "RESP_SECONDARY_1338",
        "INERTIA_ESO_210",
        "INERTIA_ESO_219632",
        "LFDD_E3CI_973",
    ):
        assert key_figure in figures


def test_severe_flags_defined_with_effects():
    flags = {f["flag_id"]: f for f in KEY["severe_flags"]}
    assert set(flags) == {"SF1", "SF2", "SF3"}
    assert "root cause" in flags["SF1"]["title"].lower()
    assert "invented evidence record" in flags["SF2"]["title"].lower()
    assert "enforcement" in flags["SF3"]["title"].lower()
    for flag in flags.values():
        assert (
            flag["definition"] and flag["effect_when_confirmed"] and flag["heuristic"]
        )
        assert flag["examples"] and flag.get("non_examples")
        for cid in flag["effect"]["zero_content"]:
            assert cid in CRITERIA
    assert set(flags["SF1"]["effect"]["zero_content"]) == {"T07.04", "T07.05", "T17.01"}
    for cid in ("T07.04", "T07.05", "T17.01"):
        assert "SF1" in CRITERIA[cid]["auto"]["severe_flags_zero"]


def test_bundle_scope_limits_are_respected():
    """Nothing requires what the bundle lacks: no DNO asset log, one control room, no
    rail record (T04.02 deferred)."""
    sources = CAT.sources
    assert set(sources.control_logs) == {"ESO-ENCC"}
    assert not any(a.startswith("DNO") for a in sources.asset_logs)
    cited = {v["evidence_id"] for c in KEY["criteria"] for v in c["visible_evidence"]}
    assert cited <= set(CAT.citable_ids(public=False))
    assert not cited & {"S02", "S08", "S10", "S11", "R09"}
    rail = [
        c for c in KEY["criteria"] if re.search(r"\brail\b", c["expectation"], re.I)
    ]
    assert {c["criterion_id"] for c in rail} <= {"T05.03"}


def test_review_checklist_lists_every_criterion_and_the_key_version():
    checklist = " ".join(
        (sr_grading.DEFAULT_KEY_PATH.parent / "REVIEW_CHECKLIST.md")
        .read_text(encoding="utf-8")
        .split()
    )
    assert f"Key version under review: **{KEY['key_version']}**" in checklist
    assert f"bundle **{KEY['bundle']['bundle_version']}**" in checklist
    assert "pending_domain_review" in checklist
    for cid in CRITERIA:
        assert f"| {cid} | {CRITERIA[cid]['assessment_mode']} |" in checklist, cid
    for flag in KEY["severe_flags"]:
        assert flag["flag_id"] in checklist
    assert "T04.02" in checklist  # the deferred rail criterion


def test_task_pre_hook_reads_this_key():
    from environment.tasks.gb_2019_system_response import KEY_CANDIDATES

    assert KEY_CANDIDATES[0] == sr_grading.DEFAULT_KEY_PATH
