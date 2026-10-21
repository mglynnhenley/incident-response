"""Human grading decisions: schema, binding, merge, status and the review template."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from environment.incident.catalogue import Catalogue
from environment.incident.grading import (
    DECISIONS_SCHEMA,
    DecisionsError,
    grade_submission,
    key_sha256,
    load_key,
    main,
    review_template,
)
from environment.incident.paths import DEFAULT_BUNDLE_DIR

ENV_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ENV_ROOT / "tests" / "fixtures"
CATALOGUE = Catalogue.load(DEFAULT_BUNDLE_DIR)
KEY = load_key()


def sub(name: str) -> dict:
    return json.loads(
        (FIXTURES / "submissions" / f"{name}.json").read_text(encoding="utf-8")
    )


def decisions(name: str) -> dict:
    return json.loads(
        (FIXTURES / "decisions" / f"{name}.decisions.json").read_text(encoding="utf-8")
    )


def rows(report: dict) -> dict[str, dict]:
    return {c["criterion_id"]: c for c in report["criteria"]}


def test_fixture_decision_files_are_marked_as_builder_fixtures():
    for name in ("correct", "incorrect"):
        d = decisions(name)
        assert d["builder_fixture"] is True
        assert "not a domain reviewer" in d["reviewer"]
        assert "NOT a domain review" in d["_note"]
        assert d["decisions_schema"] == DECISIONS_SCHEMA
        assert d["binding"]["key_version"] == KEY["key_version"]
        assert d["binding"]["key_sha256"] == key_sha256(KEY)
        assert d["binding"]["bundle_sha256"] == CATALOGUE.bundle_sha256


def test_correct_decisions_merge():
    report = grade_submission(
        sub("correct"), CATALOGUE, KEY, None, decisions("correct")
    )
    r = rows(report)
    for cid in ("D3.1", "D3.2", "D3.3", "D3.4"):
        assert r[cid]["content"]["source"] == "auto"  # left null: auto result accepted
    for cid in ("D1.1", "D2.5", "D3.5", "D4.4"):
        assert r[cid]["content"] == {**r[cid]["content"], "value": 1, "source": "human"}
        assert r[cid]["evidence_support"]["source"] == "human"
        assert r[cid]["human_finding_ids"]
    coverage = report["content_coverage"]["by_dimension"]
    assert all(coverage[d]["pending"] == 0 for d in coverage)
    assert coverage["D1"]["decided_content_sum"] == 5
    quality = report["assertion_quality"]
    assert quality["counts_all_dimensions"]["pending"] == 0
    assert quality["counts_all_dimensions"]["supported"] == 26
    for dim in ("D1", "D2", "D3", "D4"):
        assert quality["by_dimension"][dim]["precision"] == 1.0
    assert report["decisions"]["builder_fixture"] is True
    assert report["explanation_quality"]["source"] == "human"
    # still provisional: the key is unreviewed and the decisions are a fixture
    assert report["status"] == "provisional"
    reasons = " | ".join(report["provisional_reasons"])
    assert "pending_domain_review" in reasons and "builder fixture" in reasons
    assert "await" not in reasons


def test_incorrect_decisions_merge_with_severe_flags():
    report = grade_submission(
        sub("incorrect"), CATALOGUE, KEY, None, decisions("incorrect")
    )
    severe = report["severe_flags"]
    assert {(s["flag_id"], s["location"], s["confirmed"]) for s in severe} == {
        ("SF1", "I30", True),
        ("SF1", "I31", True),
        ("SF1", "report.executive_summary", True),
    }
    quality = report["assertion_quality"]
    counts = quality["counts_all_dimensions"]
    assert (counts["supported"], counts["unsupported"], counts["contradicted"]) == (
        3,
        2,
        9,
    )
    assert counts["pending"] == 0
    d3 = quality["by_dimension"]["D3"]
    assert d3["contradicted"] == 4 and d3["precision"] == 0.0
    r = rows(report)
    assert (
        r["D2.4"]["content"]["value"] == 0.5
        and r["D2.4"]["content"]["source"] == "human"
    )
    assert r["D1.1"]["evidence_support"]["source"] == "not_applicable"
    assert (
        r["D3.1"]["content"]["source"] == "auto" and r["D3.1"]["content"]["value"] == 0
    )


def test_human_override_of_auto_is_recorded():
    d = decisions("correct")
    d["criteria"]["D3.1"] = {
        "content": 0.5,
        "evidence_support": None,
        "notes": "override",
    }
    row = rows(grade_submission(sub("correct"), CATALOGUE, KEY, None, d))["D3.1"]
    assert row["content"]["value"] == 0.5 and row["content"]["source"] == "human"
    assert row["content"]["auto_proposal"] == 1.0
    assert row["content"]["human_override_of_auto"] is True
    assert row["evidence_support"]["source"] == "auto"


def test_binding_to_another_submission_is_rejected():
    with pytest.raises(DecisionsError, match="submission_sha256 does not match"):
        grade_submission(sub("incorrect"), CATALOGUE, KEY, None, decisions("correct"))


def test_binding_to_another_key_version_is_rejected():
    key = copy.deepcopy(KEY)
    key["key_version"] = "9.9.9"
    with pytest.raises(DecisionsError, match="key_version"):
        grade_submission(sub("correct"), CATALOGUE, key, None, decisions("correct"))


def test_binding_to_an_edited_key_is_rejected():
    """Editing the key without a version bump (here a tolerance) invalidates decisions."""
    key = copy.deepcopy(KEY)
    d22 = next(c for c in key["criteria"] if c["criterion_id"] == "D2.2")
    d22["auto"]["elements"][0]["full_rel"] = 0.5
    with pytest.raises(DecisionsError, match="key_sha256"):
        grade_submission(sub("correct"), CATALOGUE, key, None, decisions("correct"))


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda d: d["criteria"]["D1.1"].update(content=0.7),
            "content must be 1, 0.5, 0",
        ),
        (
            lambda d: d["criteria"]["D1.1"].update(evidence_support=0.5),
            "evidence_support must be",
        ),
        (lambda d: d["criteria"].update({"D9.9": {"content": 1}}), "unknown criterion"),
        (
            lambda d: d["criteria"]["D1.1"].update(finding_ids=["F77"]),
            "unknown finding",
        ),
        (
            lambda d: d["assertions"]["F01"].update(verdict="maybe"),
            "verdict must be one of",
        ),
        (
            lambda d: d["assertions"].update({"R-1": {"verdict": "unsupported"}}),
            "needs 'text'",
        ),
        (lambda d: d.update(reviewer=""), "reviewer is required"),
        (lambda d: d.update(date=None), "date is required"),
        (lambda d: d.update(decisions_schema="other/1"), "decisions_schema"),
        (lambda d: d["severe_flags"].append({"flag_id": "SF9"}), "unknown flag_id"),
        (lambda d: d["binding"].update(bundle_sha256="0" * 64), "bundle_sha256"),
        (lambda d: d["binding"].pop("bundle_sha256"), "bundle_sha256 is missing"),
        (lambda d: d["binding"].pop("key_sha256"), "key_sha256 is missing"),
        (
            lambda d: d["severe_flags"].append(
                {"flag_id": "SF1", "finding_ids": ["F77"], "confirmed": False}
            ),
            "severe_flags\\[0\\].finding_ids: unknown finding",
        ),
        (
            lambda d: d.update(explanation_quality={"notes": 3}),
            "explanation_quality.notes must be text",
        ),
        (
            lambda d: d.update(
                explanation_quality={"notes": "x", "by_dimension": {"D9": "y"}}
            ),
            "by_dimension.D9: unknown dimension",
        ),
    ],
)
def test_malformed_decisions_are_rejected(mutate, message):
    d = decisions("correct")
    mutate(d)
    with pytest.raises(DecisionsError, match=message):
        grade_submission(sub("correct"), CATALOGUE, KEY, None, d)


def test_report_only_assertions_and_duplicates():
    d = decisions("correct")
    d["assertions"]["F03"] = {"verdict": None, "duplicate_of": "F04"}
    d["assertions"]["R-1"] = {
        "verdict": "unsupported",
        "text": "Prose-only claim in the executive summary.",
        "dimension": "D4",
    }
    quality = grade_submission(sub("correct"), CATALOGUE, KEY, None, d)[
        "assertion_quality"
    ]
    assert quality["counts_all_dimensions"]["duplicates"] == 1
    d4 = quality["by_dimension"]["D4"]
    assert d4["unsupported"] == 1
    assert d4["precision"] == round(d4["supported"] / (d4["supported"] + 1), 4)


def test_precision_undefined_without_assertions():
    report = grade_submission(sub("uncertain"), CATALOGUE, KEY)
    for dim, q in report["assertion_quality"]["by_dimension"].items():
        assert q["precision"] is None, dim


def test_final_status_requires_reviewed_key_complete_decisions_and_trace():
    key = copy.deepcopy(KEY)
    key["review"]["status"] = "reviewed"
    key["review_status"] = "reviewed"
    d = decisions("correct")
    d["builder_fixture"] = False
    # a reviewed key is a new key: its decisions are bound to its sha256
    d["binding"]["key_sha256"] = key_sha256(key)
    trace = {"available": True, "retrieved": ["R01", "R03", "S01", "S03", "S04"]}
    report = grade_submission(sub("correct"), CATALOGUE, key, trace, d)
    assert report["status"] == "final", report["provisional_reasons"]
    # one undecided criterion keeps it provisional
    d["criteria"]["D4.1"]["content"] = None
    report = grade_submission(sub("correct"), CATALOGUE, key, trace, d)
    assert report["status"] == "provisional"
    assert "1 criteria await human decisions" in report["provisional_reasons"]


def test_review_template_round_trip(tmp_path: Path):
    template = review_template(sub("incorrect"), key=KEY, catalogue=CATALOGUE)
    assert template["decisions_schema"] == DECISIONS_SCHEMA
    assert template["reviewer"] is None and template["date"] is None
    assert template["binding"]["key_version"] == KEY["key_version"]
    assert template["binding"]["key_sha256"] == key_sha256(KEY)
    assert template["binding"]["bundle_sha256"] == CATALOGUE.bundle_sha256
    # explanation-quality placeholders are null, never pre-filled empty strings
    assert template["explanation_quality"] == {
        "notes": None,
        "by_dimension": {"D1": None, "D2": None, "D3": None, "D4": None},
    }
    assert set(template["criteria"]) == {c["criterion_id"] for c in KEY["criteria"]}
    d31 = template["criteria"]["D3.1"]
    assert d31["content"] is None and d31["_context"]["auto_content"]["value"] == 0
    assert d31["_context"]["report_passages"]
    assert template["assertions"]["I20"]["_context"]["auto_proposal"] == "contradicted"
    assert {f["flag_id"] for f in template["severe_flags"]} == {"SF1"}
    # an unfilled template is not a valid decisions file
    with pytest.raises(DecisionsError, match="reviewer is required"):
        grade_submission(sub("incorrect"), CATALOGUE, KEY, None, template)
    # filled in, it applies
    template.update(reviewer="test reviewer", date="2026-10-19", builder_fixture=True)
    for entry in template["criteria"].values():
        entry["content"] = 0
    for entry in template["assertions"].values():
        entry["verdict"] = "contradicted"
    for entry in template["severe_flags"]:
        entry["confirmed"] = True
    path = tmp_path / "decisions.v1.json"
    path.write_text(json.dumps(template), encoding="utf-8")
    report = grade_submission(sub("incorrect"), CATALOGUE, KEY, None, path)
    assert report["decisions"]["decisions_version"] == "1"
    assert all(s["confirmed"] for s in report["severe_flags"])
    # untouched explanation placeholders do not count as a review
    assert report["explanation_quality"]["source"] == "pending"
    assert any(
        "explanation quality not reviewed" in r for r in report["provisional_reasons"]
    )


def test_grading_cli_grade_submission(tmp_path: Path, capsys):
    out = tmp_path / "grade.json"
    code = main(
        [
            "grade-submission",
            str(FIXTURES / "submissions" / "correct.json"),
            "--decisions",
            str(FIXTURES / "decisions" / "correct.decisions.json"),
            "--out",
            str(out),
        ]
    )
    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["decisions"]["reviewer"].startswith("grading builder")
    code = main(
        [
            "grade-submission",
            str(FIXTURES / "submissions" / "incorrect.json"),
            "--decisions",
            str(FIXTURES / "decisions" / "correct.decisions.json"),
        ]
    )
    assert code == 1
    assert "submission_sha256 does not match" in capsys.readouterr().err
    template_path = tmp_path / "template.json"
    assert (
        main(
            [
                "review-template",
                str(FIXTURES / "submissions" / "correct.json"),
                "--out",
                str(template_path),
            ]
        )
        == 0
    )
    assert (
        json.loads(template_path.read_text())["binding"]["submission_sha256"]
        == report["submission"]["sha256"]
    )
