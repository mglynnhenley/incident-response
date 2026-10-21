"""Submission v3 validation: every schema and semantic rule."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest
from incident_helpers import make_bundle, valid_submission

from environment.incident.catalogue import Catalogue
from environment.incident.submission import (
    extract_references,
    validate_submission,
    word_count,
)


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory) -> Catalogue:
    return Catalogue.load(make_bundle(tmp_path_factory.mktemp("bundle")))


def _errors(raw, catalogue, **kwargs):
    result = validate_submission(raw, catalogue, **kwargs)
    assert not result.ok
    assert result.submission is None and result.sha256 is None
    return result.errors


def _paths(errors):
    return [e["path"] for e in errors]


def _with(mutator):
    sub = valid_submission()
    mutator(sub)
    return sub


def test_valid_submission(catalogue):
    result = validate_submission(valid_submission(), catalogue)
    assert result.ok, result.errors
    assert result.findings_count == 2
    canonical = result.canonical_json
    assert json.loads(canonical) == valid_submission()
    assert canonical == json.dumps(
        valid_submission(), sort_keys=True, indent=2, ensure_ascii=False
    )
    assert result.sha256 == hashlib.sha256(canonical.encode()).hexdigest()


def test_json_string_and_dict_give_same_canonical_form(catalogue):
    a = validate_submission(valid_submission(), catalogue)
    b = validate_submission(json.dumps(valid_submission(), indent=4), catalogue)
    assert b.ok and a.sha256 == b.sha256


def test_empty_findings_list_is_valid_inconclusive(catalogue):
    sub = valid_submission(findings=[])
    sub["report"] = {"executive_summary": "Inconclusive.", "sections": []}
    assert validate_submission(sub, catalogue).ok


def test_citing_any_catalogue_document_is_allowed_even_if_not_retrieved(catalogue):
    sub = _with(
        lambda s: s["findings"][0]["citations"].append(
            {"evidence_id": "S04", "locator": "L1"}
        )
    )
    assert validate_submission(sub, catalogue).ok


def test_empty_citations_allowed_without_derivation(catalogue):
    sub = _with(lambda s: s["findings"][0].update(citations=[]))
    assert validate_submission(sub, catalogue).ok


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        (None, "no submission"),
        ("{not json", "not valid JSON"),
        ("[1, 2]", "must be a JSON object"),
        ('{"a": 1, "a": 2}', "duplicate key"),
        ('{"value": NaN}', "not valid JSON"),
        (42, "must be a JSON object"),
    ],
)
def test_unparseable_input(catalogue, raw, fragment):
    errors = _errors(raw, catalogue)
    assert errors[0]["path"] == "submission"
    assert fragment in errors[0]["message"]


def test_non_finite_number_in_dict_rejected(catalogue):
    sub = _with(lambda s: s["findings"][1]["quantity"].update(value=float("inf")))
    errors = _errors(sub, catalogue)
    assert errors[0]["path"] in ("submission", "findings[1].quantity.value")


def test_extra_fields_forbidden(catalogue):
    errors = _errors(_with(lambda s: s.update(tasks=[])), catalogue)
    assert errors == [
        {
            "path": "tasks",
            "message": "unexpected field 'tasks'; it is not part of the v3 submission format",
        }
    ]
    errors = _errors(
        _with(lambda s: s["findings"][0].update(confidence=0.9)), catalogue
    )
    assert _paths(errors) == ["findings[0].confidence"]
    errors = _errors(
        _with(lambda s: s["findings"][0]["citations"][0].update(page=3)), catalogue
    )
    assert _paths(errors) == ["findings[0].citations[0].page"]


def test_missing_required_fields(catalogue):
    errors = _errors(_with(lambda s: s["findings"][0].pop("citations")), catalogue)
    assert errors == [
        {"path": "findings[0].citations", "message": "required field is missing"}
    ]
    errors = _errors(_with(lambda s: s.pop("report")), catalogue)
    assert _paths(errors) == ["report"]
    errors = _errors(_with(lambda s: s["report"].pop("sections")), catalogue)
    assert _paths(errors) == ["report.sections"]


@pytest.mark.parametrize(
    ("mutator", "path"),
    [
        (lambda s: s["findings"][0].update(statement=5), "findings[0].statement"),
        (lambda s: s["findings"][0].update(statement="   "), "findings[0].statement"),
        (
            lambda s: s["findings"][1]["quantity"].update(value="49.95"),
            "findings[1].quantity.value",
        ),
        (
            lambda s: s["findings"][1]["quantity"].update(value=True),
            "findings[1].quantity.value",
        ),
        (
            lambda s: s["findings"][1]["quantity"].update(unit=""),
            "findings[1].quantity.unit",
        ),
        (
            lambda s: s["findings"][1]["quantity"].pop("basis"),
            "findings[1].quantity.basis",
        ),
        (
            lambda s: s["findings"][0].update(citations={"evidence_id": "R03"}),
            "findings[0].citations",
        ),
        (lambda s: s.update(findings={}), "findings"),
        (
            lambda s: s["report"].update(executive_summary=""),
            "report.executive_summary",
        ),
        (
            lambda s: s["report"]["sections"][0].update(body=""),
            "report.sections[0].body",
        ),
        (lambda s: s["findings"][1].update(derivation=""), "findings[1].derivation"),
    ],
)
def test_type_and_emptiness_errors(catalogue, mutator, path):
    errors = _errors(_with(mutator), catalogue)
    assert path in _paths(errors), errors


def test_integer_quantity_value_is_accepted(catalogue):
    sub = _with(lambda s: s["findings"][1]["quantity"].update(value=50))
    assert validate_submission(sub, catalogue).ok


def test_status_must_be_known(catalogue):
    errors = _errors(
        _with(lambda s: s["findings"][0].update(status="confirmed")), catalogue
    )
    assert errors[0]["path"] == "findings[0].status"
    assert "observed, reported, inferred, hypothesis, unknown" in errors[0]["message"]
    for status in ("observed", "reported", "inferred", "hypothesis", "unknown"):
        assert validate_submission(
            _with(lambda s, st=status: s["findings"][0].update(status=st)), catalogue
        ).ok


def test_schema_version_and_variant(catalogue):
    errors = _errors(valid_submission(schema_version="2.0"), catalogue)
    assert errors == [
        {"path": "schema_version", "message": "must be '3.0' (got '2.0')"}
    ]
    errors = _errors(valid_submission(variant_id="closed_book"), catalogue)
    assert errors == [
        {"path": "variant_id", "message": "must be 'baseline' (got 'closed_book')"}
    ]
    assert validate_submission(
        valid_submission(variant_id="P1"), catalogue, variant_id="P1"
    ).ok


@pytest.mark.parametrize("bad_id", ["F 1", "-F1", "F/1", "", "F" * 41, "Ä1"])
def test_finding_id_pattern(catalogue, bad_id):
    sub = _with(lambda s: s["findings"][0].update(finding_id=bad_id))
    sub["report"] = {"executive_summary": "No references.", "sections": []}
    errors = _errors(sub, catalogue)
    assert "findings[0].finding_id" in _paths(errors)


def test_finding_id_allowed_characters(catalogue):
    sub = _with(lambda s: s["findings"][0].update(finding_id="D1.2_a-b"))
    sub["report"] = {"executive_summary": "See [D1.2_a-b] and [F02].", "sections": []}
    assert validate_submission(sub, catalogue).ok


def test_duplicate_finding_ids(catalogue):
    sub = _with(lambda s: s["findings"][1].update(finding_id="F01"))
    sub["report"] = {"executive_summary": "See [F01].", "sections": []}
    errors = _errors(sub, catalogue)
    assert errors == [
        {
            "path": "findings[1].finding_id",
            "message": "duplicate finding_id 'F01' (already used by findings[0])",
        }
    ]


def test_executive_summary_word_limit(catalogue):
    ok = valid_submission()
    ok["report"]["executive_summary"] = " ".join(["word"] * 599) + " [F01]"
    assert word_count(ok["report"]["executive_summary"]) == 600
    assert validate_submission(ok, catalogue).ok
    too_long = copy.deepcopy(ok)
    too_long["report"]["executive_summary"] += " extra"
    errors = _errors(too_long, catalogue)
    assert errors == [
        {
            "path": "report.executive_summary",
            "message": "has 601 words; the limit is 600 whitespace-separated words",
        }
    ]
    assert validate_submission(too_long, catalogue, word_limit=601).ok


def test_report_references_must_exist(catalogue):
    sub = valid_submission()
    sub["report"]["executive_summary"] = "See [F01] and [F09]."
    sub["report"]["sections"] = [
        {"heading": "Heading [F07]", "body": "Body [F01, F08] and [F09]."}
    ]
    errors = _errors(sub, catalogue)
    assert ("report.executive_summary", "F09") in {
        (e["path"], e["message"].split("[")[1].split("]")[0]) for e in errors
    }
    paths = _paths(errors)
    assert paths.count("report.sections[0].body") == 2  # F08 and F09, each once
    assert "report.sections[0].heading" in paths
    assert all("reserved for finding IDs" in e["message"] for e in errors)


def test_square_bracket_words_are_treated_as_references(catalogue):
    sub = valid_submission()
    sub["report"]["executive_summary"] = "The record [sic] says so [F01]."
    errors = _errors(sub, catalogue)
    assert "[sic]" in errors[0]["message"]
    # brackets that are not ID-shaped are plain text
    sub["report"]["executive_summary"] = "A [two words] note and [ ] and [F01]."
    assert validate_submission(sub, catalogue).ok


def test_extract_references():
    assert extract_references("a [F01] b [F02, F03] c [F04 ,F05]") == [
        "F01",
        "F02",
        "F03",
        "F04",
        "F05",
    ]
    assert extract_references("[not an id] [] [x y]") == []


def test_unknown_evidence_id(catalogue):
    sub = _with(lambda s: s["findings"][0]["citations"][0].update(evidence_id="R02"))
    errors = _errors(sub, catalogue)
    assert errors[0]["path"] == "findings[0].citations[0].evidence_id"
    assert "unknown evidence_id 'R02'" in errors[0]["message"]
    assert "R01, R03, S01, S03, S04" in errors[0]["message"]
    # exact match only
    sub = _with(lambda s: s["findings"][0]["citations"][0].update(evidence_id="r03"))
    assert "findings[0].citations[0].evidence_id" in _paths(_errors(sub, catalogue))


@pytest.mark.parametrize(
    ("evidence_id", "locator", "fragment"),
    [
        ("R03", "line 3", "malformed line locator"),
        ("R03", "p.3", "unrecognised"),
        ("R03", "L5-L3", "reversed"),
        ("R03", "L29-L31", "out of range"),
        ("R03", "time:2019-08-09T16:52:35+01:00", "no time series"),
        ("R01", "time:2019-08-09T17:00:00+01:00", "outside"),
        ("R01", "time:2019-08-09T16:52:35", "malformed time locator"),
        ("R01", "rows:1-21", "out of range"),
    ],
)
def test_bad_locators(catalogue, evidence_id, locator, fragment):
    sub = _with(
        lambda s: s["findings"][0]["citations"][0].update(
            evidence_id=evidence_id, locator=locator
        )
    )
    errors = _errors(sub, catalogue)
    assert errors[0]["path"] == "findings[0].citations[0].locator"
    assert fragment in errors[0]["message"]


def test_too_many_findings(catalogue):
    findings = [
        {
            "finding_id": f"F{i:03d}",
            "statement": "s",
            "status": "unknown",
            "citations": [],
        }
        for i in range(201)
    ]
    sub = valid_submission(findings=findings)
    sub["report"] = {"executive_summary": "Many.", "sections": []}
    errors = _errors(sub, catalogue)
    assert errors == [
        {"path": "findings", "message": "has 201 findings; at most 200 are allowed"}
    ]
    sub["findings"] = findings[:200]
    assert validate_submission(sub, catalogue).ok


def test_derivation_requires_citations(catalogue):
    sub = _with(lambda s: s["findings"][1].update(citations=[]))
    errors = _errors(sub, catalogue)
    assert errors == [
        {
            "path": "findings[1].citations",
            "message": "a finding with a derivation must cite the evidence it was derived from",
        }
    ]


@pytest.mark.parametrize(
    "event_time",
    [
        "2019-08-09T16:52:35",
        "16:52:35",
        "2019-08-09",
        "2019-13-09T16:52:35+01:00",
        "soon",
    ],
)
def test_event_time_needs_iso_with_offset(catalogue, event_time):
    sub = _with(lambda s: s["findings"][1].update(event_time=event_time))
    errors = _errors(sub, catalogue)
    assert _paths(errors) == ["findings[1].event_time"]


def test_event_time_with_z_offset_ok(catalogue):
    sub = _with(lambda s: s["findings"][1].update(event_time="2019-08-09T15:52:35Z"))
    assert validate_submission(sub, catalogue).ok


def test_all_semantic_problems_are_reported_together(catalogue):
    sub = valid_submission(schema_version="9", variant_id="x")
    sub["report"]["executive_summary"] = "See [F77]."
    sub["findings"][0]["citations"][0]["evidence_id"] = "ZZZ"
    errors = _errors(sub, catalogue)
    assert {"schema_version", "variant_id", "report.executive_summary"} <= set(
        _paths(errors)
    )
    assert "findings[0].citations[0].evidence_id" in _paths(errors)


def test_error_list_is_capped(catalogue):
    findings = [
        {
            "finding_id": f"F{i:03d}",
            "statement": "s",
            "status": "unknown",
            "citations": [{"evidence_id": "NOPE", "locator": "L1"}],
        }
        for i in range(150)
    ]
    sub = valid_submission(findings=findings)
    sub["report"] = {"executive_summary": "x", "sections": []}
    errors = _errors(sub, catalogue)
    assert len(errors) == 101
    assert errors[-1]["message"] == "... and 50 more problems not shown"


def test_deeply_nested_json_is_a_repairable_problem(catalogue):
    text = '{"a":' * 100_000 + "1" + "}" * 100_000
    assert _errors(text, catalogue) == [
        {
            "path": "submission",
            "message": "JSON nested too deeply; a v3 submission needs only a few "
            "levels of nesting",
        }
    ]
    nested: dict = {}
    cursor = nested
    for _ in range(100_000):
        cursor["a"] = {}
        cursor = cursor["a"]
    assert _paths(_errors(nested, catalogue)) == ["submission"]
