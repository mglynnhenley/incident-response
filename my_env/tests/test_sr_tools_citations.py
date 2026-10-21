"""Record locators (event:/entry:/response:) and v3 submission validation on a v2 bundle."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sr_helpers import make_sr_bundle, sr_submission

from environment.incident.catalogue import Catalogue
from environment.incident.locators import (
    LOCATOR_HELP,
    LocatorError,
    parse_locator,
    validate_locator,
)
from environment.incident.submission import validate_submission


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory) -> Catalogue:
    return Catalogue.load(make_sr_bundle(tmp_path_factory.mktemp("sr")))


@pytest.mark.parametrize(
    ("text", "normalized", "kind"),
    [
        ("event:ESW-0001", "event:ESW-0001", "event"),
        (" Event: ESW-0001 ", "event:ESW-0001", "event"),
        ("entry:SO-001", "entry:SO-001", "entry"),
        ("RESPONSE:S09-SO-02", "response:S09-SO-02", "response"),
        (
            "event:R02-B1610-T_HOWAO-2-20190809-SP34",
            "event:R02-B1610-T_HOWAO-2-20190809-SP34",
            "event",
        ),
    ],
)
def test_record_locators_parse(text, normalized, kind):
    loc = parse_locator(text)
    assert loc.normalized == normalized and loc.kind == kind
    assert loc.record_id == normalized.split(":", 1)[1]
    # the grading helpers stay safe on record kinds
    assert not loc.covers_time(datetime(2019, 8, 9, 15, 52, 33, tzinfo=UTC))
    assert not loc.overlaps_lines(1, 10) and not loc.overlaps_rows(1, 10)


@pytest.mark.parametrize(
    "text", ["event:", "event:../x", "entry:a b", "response:-x", "event:" + "x" * 81]
)
def test_malformed_record_locators(text):
    with pytest.raises(LocatorError, match="malformed"):
        parse_locator(text)


def test_mvp_locator_help_is_unchanged():
    assert LOCATOR_HELP.startswith("Locators: 'L12' or 'L12-L18'")


@pytest.mark.parametrize(
    ("evidence_id", "locator"),
    [
        ("R03", "event:ESW-0001"),
        ("R03", "L1-L20"),
        ("R02", "event:PLANT-1-0005"),
        ("R05", "event:PLANT-2-0229"),
        ("S05", "event:DNO-A-0001"),
        ("S05", "entry:DNO-A-E1"),
        ("S05", "L2"),
        ("S07", "entry:SO-004"),
        ("R08", "entry:SO-006"),
        ("S09", "response:S09-DNO-01"),
        ("R01", "time:2019-08-09T15:52:33Z"),
        ("R01", "rows:1-1500"),
    ],
)
def test_valid_citations(catalogue, evidence_id, locator):
    validate_locator(locator, catalogue.citation_target(evidence_id))


@pytest.mark.parametrize(
    ("evidence_id", "locator", "match"),
    [
        ("S07", "entry:SO-002", "belongs to evidence R08, not S07"),
        ("R03", "event:PLANT-1-0001", "belongs to evidence R02"),
        ("S12", "response:S09-SO-01", "belongs to evidence S09"),
        ("R03", "event:ESW-9999", "has no asset-log event"),
        ("R03", "entry:ESW-0001", "has no control-log entry"),
        ("S07", "L1", "no document text"),
        ("S09", "time:2019-08-09T15:52:33Z", "no document text"),
        ("R03", "L21", "out of range"),
        ("R03", "row:1", "no time series"),
    ],
)
def test_invalid_citations(catalogue, evidence_id, locator, match):
    with pytest.raises(LocatorError, match=match):
        validate_locator(locator, catalogue.citation_target(evidence_id))


def test_submission_with_record_citations_is_valid(catalogue):
    result = validate_submission(sr_submission(), catalogue)
    assert result.ok, result.errors


def test_submission_errors_name_the_right_evidence(catalogue):
    sub = sr_submission()
    sub["findings"][1]["citations"] = [
        {"evidence_id": "S07", "locator": "entry:SO-002"},
        {"evidence_id": "S99", "locator": "L1"},
        {"evidence_id": "S09", "locator": "response:nope"},
    ]
    result = validate_submission(sub, catalogue)
    assert not result.ok
    by_path = {e["path"]: e["message"] for e in result.errors}
    assert "R08" in by_path["findings[1].citations[0].locator"]
    unknown = by_path["findings[1].citations[1].evidence_id"]
    assert "unknown evidence_id 'S99'" in unknown
    valid = unknown.split("valid IDs: ")[1].split(", ")
    assert "S07" in valid and "S09" in valid  # record-only evidence is citable
    assert "witness response 'nope'" in by_path["findings[1].citations[2].locator"]


def test_unlisted_documents_are_accepted_as_citations(catalogue):
    sub = sr_submission()
    sub["findings"][0]["citations"] = [{"evidence_id": "S05", "locator": "L3"}]
    assert validate_submission(sub, catalogue).ok


def test_mvp_validation_messages_are_unchanged(tmp_path: Path):
    from incident_helpers import make_bundle, valid_submission

    mvp = Catalogue.load(make_bundle(tmp_path))
    sub = valid_submission()
    sub["findings"][0]["citations"] = [
        {"evidence_id": "R02", "locator": "L1"},
        {"evidence_id": "R03", "locator": "event:ESW-0001"},
    ]
    result = validate_submission(sub, mvp)
    by_path = {e["path"]: e["message"] for e in result.errors}
    assert by_path["findings[0].citations[0].evidence_id"] == (
        "unknown evidence_id 'R02'; valid IDs: R01, R03, S01, S03, S04"
    )
    assert "has no asset-log event" in by_path["findings[0].citations[1].locator"]
