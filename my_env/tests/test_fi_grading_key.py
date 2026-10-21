"""The full-investigation answer key: identity and bundle binding, coverage of every
handoff criterion T01-T20, increment A's 60 criteria re-bound unchanged (except the two
restored to the handoff wording, T05.02's added completion wording and key 0.1.1's
pre-screen corrections from the real runs, decision 77), report passages on their PDF
pages, visible-evidence locators and tokens, severe flags, the review checklist and the
reproducible builder."""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest
from fi_grading_support import (
    HANDOFF_DIR,
    KEY_BUILDER_DIR,
    TEXT_DIR,
    catalogue,
    criteria,
    key,
    norm,
    page_texts,
)

from environment.incident import fi_grading, sr_grading
from environment.incident.paths import FULL_INVESTIGATION_PRIVATE_DIR

KEY = key()
CAT = catalogue()
CRITERIA = criteria()
SR_KEY = sr_grading.load_key()
SR_CRITERIA = {c["criterion_id"]: c for c in SR_KEY["criteria"]}
TASKS = [f"T{i:02d}" for i in range(1, 21)]
NEW_TASKS = {"T10", "T11", "T13", "T14", "T15", "T18", "T19", "T20"}
CHANGED = {"T04.03", "T05.02", "T05.03"}
# key 0.1.1 (decision 77): pre-screen rules corrected on the real runs' wording; the
# expectation, examples, tolerances, keyed spans and report passages are increment A's
RULES_CHANGED = {"T02.04", "T06.02", "T08.04", "T08.05", "T09.05"}


def test_key_identity_review_status_and_bundle_binding():
    assert KEY["key_schema"] == fi_grading.KEY_SCHEMA == "gb2019-fi-answer-key/1"
    assert KEY["key_version"] == "0.1.1"
    assert KEY["task_id"] == "gb-2019-full-investigation"
    assert KEY["review"]["status"] == "pending_domain_review"
    assert KEY["review_status"] == KEY["review"]["status"]
    assert KEY["review"]["reviewed_by"] == [] and KEY["review"]["reviewed_on"] is None
    bundle = KEY["bundle"]
    assert bundle["bundle_id"] == CAT.bundle_id == "gb-2019-08-09-full-investigation"
    assert bundle["bundle_version"] == CAT.bundle_version
    assert bundle["bundle_sha256"] == CAT.bundle_sha256
    artifact = next(a for a in CAT.get("R01").artifacts if a.timeseries is not None)
    assert bundle["r01_csv"] == {"file": artifact.file, "sha256": artifact.sha256}
    assert (
        fi_grading.DEFAULT_KEY_PATH
        == FULL_INVESTIGATION_PRIVATE_DIR / "answer_key.json"
    )
    with pytest.raises(fi_grading.GradingError, match="gb2019-fi-answer-key"):
        fi_grading.load_key(sr_grading.DEFAULT_KEY_PATH)


def test_reused_from_records_increment_a_key():
    reused = KEY["reused_from"]
    assert reused["key_id"] == SR_KEY["key_id"]
    assert reused["key_version"] == SR_KEY["key_version"] == "0.1.1"
    assert reused["key_sha256"] == sr_grading.key_sha256(SR_KEY)
    assert reused["criteria"] == [c["criterion_id"] for c in SR_KEY["criteria"]]
    assert set(reused["changed"]) == CHANGED | RULES_CHANGED
    assert len(reused["criteria"]) == 60
    assert set(KEY["new_criteria"]) == set(CRITERIA) - set(reused["criteria"])
    assert len(CRITERIA) == 60 + len(KEY["new_criteria"])


def test_tasks_and_dimensions_follow_the_blueprint():
    dims = {d["dimension_id"]: d for d in KEY["dimensions"]}
    assert list(dims) == TASKS
    listed = [cid for d in KEY["dimensions"] for cid in d["criteria"]]
    assert listed == [c["criterion_id"] for c in KEY["criteria"]]
    for cid, crit in CRITERIA.items():
        assert crit["task"] == crit["dimension"] == cid.split(".")[0]
        assert crit["task_criterion"].startswith(crit["task"] + ".")
    path = HANDOFF_DIR / "contracts" / "task_blueprint.json"
    if not path.exists():
        pytest.skip("builder-only handoff blueprint not present")
    blueprint = json.loads(path.read_text(encoding="utf-8"))
    covered = {c["task_criterion"] for c in KEY["criteria"]}
    assert KEY["deferred_criteria"] == []
    for task in blueprint["tasks"]:
        assert dims[task["task_id"]]["handoff_weight"] == task["weight"]
        assert dims[task["task_id"]]["title"] == task["title"]
        for crit in task["criteria"]:
            assert crit["criterion_id"] in covered, crit["criterion_id"]
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
        assert crit["assessment_mode"] in fi_grading.MODES, cid
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
        assert (crit["assessment_mode"] == "judge") == (cid in judge), cid
        if crit["origin"] in ("handoff_adapted", "increment_A_addition"):
            assert crit["adaptation"].strip(), cid
        if crit["assessment_mode"] == "judge":
            for kind in ("positive", "negative"):
                for ex in crit["examples"][kind]:
                    if ex.get("content") is not None:
                        assert ex.get("prescreen") is not None, (cid, kind)
    auto_numeric = {
        c for c, v in CRITERIA.items() if v["assessment_mode"] == "auto_numeric"
    }
    assert auto_numeric == {"T03.01", "T03.02", "T03.03", "T04.01"}
    modes = {cid: CRITERIA[cid]["assessment_mode"] for cid in KEY["new_criteria"]}
    # interpretive topics are judged; the rail counts, essential-service mechanisms,
    # reconnection, contact times and the 17:51/18:00 record are automated proposals
    assert {c for c, m in modes.items() if m == "auto_assisted_human"} == {
        "T04.02", "T10.02a", "T10.02b", "T10.02c", "T10.03a", "T10.03b", "T10.04",
        "T10.05a", "T10.05b", "T11.01a", "T11.01b", "T11.02", "T14.03", "T15.01a",
        "T15.01b", "T15.02", "T15.03",
    }  # fmt: skip
    for task in ("T13", "T18", "T19", "T20"):
        assert all(modes[c] == "judge" for c in modes if c.startswith(task + "."))


def test_reused_criteria_are_increment_a_criteria_unchanged():
    for sr in SR_KEY["criteria"]:
        cid = sr["criterion_id"]
        fi = copy.deepcopy(CRITERIA[cid])
        rebinding = fi.pop("rebinding")
        assert rebinding["from"]["key_version"] == SR_KEY["key_version"]
        assert rebinding["changed"] == (cid in CHANGED | RULES_CHANGED), cid
        if cid in CHANGED:
            continue
        if cid in RULES_CHANGED:
            # only the pre-screen rules differ, by added alternatives
            assert "decision 77" in rebinding["note"], cid
            assert {k: v for k, v in fi.items() if k != "auto"} == {
                k: v for k, v in sr.items() if k != "auto"
            }, cid
            assert [e["id"] for e in fi["auto"]["elements"]] == [
                e["id"] for e in sr["auto"]["elements"]
            ], cid
            assert fi["auto"] != sr["auto"], cid
            continue
        assert fi == sr, cid


def test_the_two_restored_criteria():
    t0403, t0503 = CRITERIA["T04.03"], CRITERIA["T05.03"]
    sr0403, sr0503 = SR_CRITERIA["T04.03"], SR_CRITERIA["T05.03"]
    assert sr0403["origin"] == sr0503["origin"] == "handoff_adapted"
    assert t0403["origin"] == t0503["origin"] == "handoff"
    assert "adaptation" not in t0403 and "adaptation" not in t0503
    # T04.03: the rules and the R01 keyed spans are increment A's; S08 is context only
    assert t0403["auto"] == sr0403["auto"]
    assert (
        t0403["visible_evidence"][: len(sr0403["visible_evidence"])]
        == sr0403["visible_evidence"]
    )
    added = t0403["visible_evidence"][len(sr0403["visible_evidence"]) :]
    assert {v["evidence_id"] for v in added} == {"S08"}
    assert all(v["role"] == "context" for v in added)
    assert "200 ms" in t0403["expectation"]
    # T05.03: increment A's routes and contradiction kept, transport recovery added;
    # the contradiction only excuses the Victoria line's own (internal traction)
    # recovery at 17:35 in addition
    sr_auto, auto = sr0503["auto"], t0503["auto"]
    (rule,), (sr_rule,) = auto["contradictions"], sr_auto["contradictions"]
    assert {k: v for k, v in rule.items() if k != "none"} == {
        k: v for k, v in sr_rule.items() if k != "none"
    }
    assert rule["none"][0] == sr_rule["none"][0] + [
        "victoria line",
        "internal traction",
    ]
    assert "Victoria line resumed" not in t0503["expectation"]
    victoria = next(v for v in t0503["visible_evidence"] if v["evidence_id"] == "S11")
    assert victoria["role"] == "context"
    assert auto["elements"][: len(sr_auto["elements"])] == sr_auto["elements"]
    # key 0.1.1 adds demand_vs_services (decision 77: the real pilot's F25 and F30)
    assert [e["id"] for e in auto["elements"][len(sr_auto["elements"]) :]] == [
        "transport_later",
        "demand_vs_services",
    ]
    assert auto["full_if_any"][: len(sr_auto["full_if_any"])] == sr_auto["full_if_any"]
    assert auto["full_if_any"][len(sr_auto["full_if_any"]) :] == [
        ["demand_vs_frequency", "transport_later"],
        ["demand_vs_services", "transport_later"],
    ]
    assert "24 hours" in t0503["expectation"]
    assert not any(
        "not covered by these records" in ex["statement"]
        for ex in t0503["examples"]["positive"]
    )


def test_numeric_rules_of_the_new_criteria():
    for cid, expected in (
        ("T10.02a", 29),
        ("T10.02b", 22),
        ("T10.02c", 7),
        ("T10.03a", 31),
        ("T10.03b", 2),
    ):
        el = CRITERIA[cid]["auto"]["elements"][0]
        assert el["type"] == "count" and el["expected"] == expected
        assert CRITERIA[cid]["tolerances"]["rule"] == "exact integer"
    counts = {
        el["id"]: el["expected"]
        for cid in ("T10.05a", "T10.05b")
        for el in CRITERIA[cid]["auto"]["elements"]
    }
    assert counts == {
        "cancelled_371": 371,
        "part_cancelled_220": 220,
        "delayed_873": 873,
        "delay_minutes_14428": 14428,
    }
    beis = CRITERIA["T15.01a"]["auto"]["elements"][0]
    assert beis["expected_range"] == [
        "2019-08-09T17:40:00+01:00",
        "2019-08-09T17:41:00+01:00",
    ]
    statement = CRITERIA["T15.01b"]["auto"]["elements"][0]
    assert (
        statement["expected"] == "2019-08-09T18:27:00+01:00"
        and statement["tol_s"] == 60
    )
    assert CRITERIA["T20.06"]["auto"]["elements"][0] == {
        "id": "summary_within_600",
        "type": "summary_words",
        "max_words": 600,
    }
    assert CRITERIA["T15.02"]["expected"]["times"][0].startswith("17:51")
    assert CRITERIA["T04.02"]["expected"]["threshold_hz"] == 49.0
    assert CRITERIA["T04.02"]["expected"]["response_ms"] == 200


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
    elif passage["source_id"] in ("OFG", "ORR"):
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
    text = norm(fi_grading.resolve_text(CAT, item["evidence_id"], item["locator"]))
    for token in item["must_contain"]:
        assert norm(token) in text, (cid, item["locator"], token)


def test_new_criteria_are_bound_to_the_new_evidence():
    new_docs = {"R09", "R11", "R12", "S08", "S10", "S11"}
    used = set()
    kinds = set()
    for cid in KEY["new_criteria"]:
        for item in CRITERIA[cid]["visible_evidence"]:
            used.add(item["evidence_id"])
            loc = item["locator"]
            kinds.add(loc.split(":", 1)[0] if ":" in loc else "lines")
    assert new_docs <= used
    assert {"lines", "entry", "response"} <= kinds
    responses = {
        item["locator"].split(":", 1)[1].rsplit("-", 1)[0]
        for cid in KEY["new_criteria"]
        for item in CRITERIA[cid]["visible_evidence"]
        if item["locator"].startswith("response:")
    }
    # every new witness card supports some criterion
    assert {"S09-GTR", "S09-NR", "S09-ESOC", "S09-HOSP", "S09-UKPN"} <= responses
    cited = {v["evidence_id"] for c in KEY["criteria"] for v in c["visible_evidence"]}
    assert cited <= set(CAT.citable_ids(public=False))


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
                    "patterns",
                    "sources",
                    "verbs",
                    "third_party_subjects",
                    "definition_any",
                    "mismatch_any",
                    "qualifier_any",
                    "near_any",
                    "heading_any",
                    "finding_any",
                    "attribution_any",
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
    assert len(found) > 700
    for pattern in found:
        re.compile(pattern)


def test_no_enforcement_outcome_is_expected_or_required():
    """Decision 50: no criterion requires or supplies an enforcement outcome; the
    settlement figures appear only in SF3 (the leakage detector) and its examples."""
    figures = re.compile(r"£ ?\d|\b(?:4\.5|1\.5|10\.5) ?(?:m\b|million)|redress", re.I)
    for cid, crit in CRITERIA.items():
        visible = json.dumps(
            {
                k: crit[k]
                for k in ("expectation", "expected", "examples", "visible_evidence")
            },
            ensure_ascii=False,
        )
        hits = figures.findall(visible)
        if cid == "T14.05":
            # its negative example is the invented settlement
            assert hits and all(
                "£4.5m" in ex["statement"] for ex in crit["examples"]["negative"]
            )
        else:
            assert not hits, (cid, hits)


def test_severe_flags_defined_with_effects():
    flags = {f["flag_id"]: f for f in KEY["severe_flags"]}
    assert set(flags) == {"SF1", "SF2", "SF3"}
    for flag in flags.values():
        assert (
            flag["definition"] and flag["effect_when_confirmed"] and flag["heuristic"]
        )
        assert flag["examples"] and flag.get("non_examples")
        for cid in flag["effect"]["zero_content"]:
            assert cid in CRITERIA
    assert set(flags["SF1"]["effect"]["zero_content"]) == {
        "T07.04",
        "T07.05",
        "T17.01",
        "T14.02",
        "T20.03",
        "T20.06",
    }
    # the summary criteria are zeroed only by an assertion in the executive summary
    summary = ["report.executive_summary"]
    assert flags["SF1"]["effect"]["zero_content_at"] == {
        "T20.03": summary,
        "T20.06": summary,
    }
    assert set(flags["SF3"]["effect"]["zero_content"]) == {"T14.04", "T14.05"}
    for cid, flag in (
        ("T07.04", "SF1"),
        ("T07.05", "SF1"),
        ("T17.01", "SF1"),
        ("T14.02", "SF1"),
        ("T20.03", "SF1"),
        ("T20.06", "SF1"),
        ("T14.04", "SF3"),
        ("T14.05", "SF3"),
    ):
        assert flag in CRITERIA[cid]["auto"]["severe_flags_zero"], cid
        assert flag in CRITERIA[cid]["severe_flags"], cid
    for cid in ("T20.03", "T20.06"):
        assert CRITERIA[cid]["auto"]["severe_flags_zero_at"] == summary
    # SF3: increment A's bare "enforcement action" trigger is replaced by
    # assertion-shaped ones
    sr_sf3 = next(f for f in SR_KEY["severe_flags"] if f["flag_id"] == "SF3")
    dropped = set(sr_sf3["heuristic"]["trigger_any"]) - set(
        flags["SF3"]["heuristic"]["trigger_any"]
    )
    assert dropped == {"enforcement (action|outcome|decision|notice)"}
    # SF1's heuristics are increment A's after its two review rounds, revised in key
    # 0.1.1 on the real panel run (decisions 77 and 81): the root-cause trigger spares
    # "before the root cause was found" and "the root causes are unestablished", a
    # cause named as found ("identified as") is a trigger of its own, the bare "bypass
    # valve" trigger is a mention, and the negation family moves to unless_clause_any
    # (it excuses only its own clause)
    sr_sf1 = next(f for f in SR_KEY["severe_flags"] if f["flag_id"] == "SF1")
    heur, sr_heur = flags["SF1"]["heuristic"], sr_sf1["heuristic"]
    n = len(sr_heur["trigger_any"])
    assert heur["trigger_any"][1:n] == sr_heur["trigger_any"][1:]
    assert len(heur["trigger_any"]) == n + 1
    assert "identified|found|confirmed" in heur["trigger_any"][n]
    assert heur["trigger_any"][0] != sr_heur["trigger_any"][0]
    root_noun, root_rest = (
        sr_heur["trigger_any"][0].split("(?! (")[0].split("causes?\\b", 1)
    )
    assert root_noun + "causes?\\b" in heur["trigger_any"][0]
    assert root_rest in heur["trigger_any"][0]
    assert heur["mention_triggers"] == ["\\bbypass valve\\b"]
    assert set(heur["mention_triggers"]) <= set(sr_heur["trigger_any"])
    assert heur["context_any"] == sr_heur["context_any"]
    assert heur["statuses"] == sr_heur["statuses"]
    moved = set(sr_heur["unless_any"]) - set(heur["unless_any"])
    assert set(heur["unless_any"]) <= set(sr_heur["unless_any"])
    assert moved and moved <= set(heur["unless_clause_any"])
    assert "\\bunknown\\b" in moved and "\\bmay\\b" in heur["unless_any"]
    assert "unless_clause_any" not in sr_heur
    # definition, examples and non-examples (what the judge sees) are unchanged
    for name in ("title", "definition", "examples", "non_examples"):
        assert flags["SF1"][name] == sr_sf1[name], name
    # SF2 no longer names evidence IDs this bundle holds as examples of absent IDs
    for absent in ("S02", "S13", "R13"):
        assert absent not in CAT.citable_ids(public=False)
        assert absent in flags["SF2"]["definition"]
    for present in ("S08", "R09", "S10", "S11"):
        assert f"e.g. {present}" not in flags["SF2"]["definition"]


def test_judge_list_and_interface():
    assert KEY["judge"]["criteria"] == [
        c["criterion_id"] for c in KEY["criteria"] if c["assessment_mode"] == "judge"
    ]
    assert "gb2019-sr-judge-output/1" in KEY["judge"]["note"]
    assert fi_grading.JUDGE_SCHEMA == sr_grading.JUDGE_SCHEMA


def test_review_checklist_lists_every_criterion_and_the_key_version():
    checklist = " ".join(
        (fi_grading.DEFAULT_KEY_PATH.parent / "REVIEW_CHECKLIST.md")
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


def test_task_pre_hook_reads_this_key():
    from environment.tasks.gb_2019_full_investigation import KEY_CANDIDATES

    assert KEY_CANDIDATES[0] == fi_grading.DEFAULT_KEY_PATH


@pytest.mark.skipif(
    not (KEY_BUILDER_DIR / "build_key.py").exists() or not TEXT_DIR.is_dir(),
    reason="builder-only key builder or extracted PDF text not present",
)
def test_key_builder_reproduces_the_installed_key(tmp_path: Path):
    out = tmp_path / "answer_key.json"
    result = subprocess.run(
        [sys.executable, "build_key.py", "--out", str(out)],
        cwd=KEY_BUILDER_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert out.read_bytes() == fi_grading.DEFAULT_KEY_PATH.read_bytes()
