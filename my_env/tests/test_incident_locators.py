"""Locator grammar: parsing, normalisation, validation and grading helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from incident_helpers import SERIES_ROWS, make_bundle

from environment.incident.catalogue import Catalogue
from environment.incident.locators import (
    Locator,
    LocatorError,
    parse_and_validate,
    parse_iso_instant,
    parse_locator,
    validate_locator,
)

BST = timezone(timedelta(hours=1))


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory) -> Catalogue:
    return Catalogue.load(make_bundle(tmp_path_factory.mktemp("bundle")))


@pytest.mark.parametrize(
    ("text", "start", "end", "normalized"),
    [
        ("L12", 12, 12, "L12"),
        ("L12-L14", 12, 14, "L12-L14"),
        ("L12-14", 12, 14, "L12-L14"),
        ("l12-l14", 12, 14, "L12-L14"),
        ("  L12 - L14  ", 12, 14, "L12-L14"),
        ("L5-L5", 5, 5, "L5"),
        ("L007", 7, 7, "L7"),
    ],
)
def test_line_locators(text, start, end, normalized):
    loc = parse_locator(text)
    assert (loc.kind, loc.start, loc.end, loc.normalized) == (
        "lines",
        start,
        end,
        normalized,
    )
    assert str(loc) == normalized


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "12",
        "L0",
        "L0-L3",
        "L5-L3",
        "Lx",
        "L1-L2-L3",
        "line 5",
        "L-5",
        "L1,L2",
    ],
)
def test_malformed_line_locators(text):
    with pytest.raises(LocatorError):
        parse_locator(text)


def test_non_string_locator():
    with pytest.raises(LocatorError):
        parse_locator(12)  # type: ignore[arg-type]


def test_time_locators_normalise_to_utc_and_compare_instants():
    a = parse_locator("time:2019-08-09T16:52:35+01:00")
    b = parse_locator("time:2019-08-09T15:52:35Z")
    assert a.kind == "time"
    assert a.normalized == b.normalized == "time:2019-08-09T15:52:35+00:00"
    assert a.start == b.start
    rng = parse_locator(
        "TIME:2019-08-09T16:52:35+01:00 / 2019-08-09T16:52:40.500+01:00"
    )
    assert rng.normalized == (
        "time:2019-08-09T15:52:35+00:00/2019-08-09T15:52:40.500000+00:00"
    )
    same = parse_locator("time:2019-08-09T16:52:35+01:00/2019-08-09T15:52:35Z")
    assert same.normalized == "time:2019-08-09T15:52:35+00:00"


@pytest.mark.parametrize(
    "text",
    [
        "time:2019-08-09T16:52:35",  # no offset
        "time:2019-08-09T16:52:35+0100",  # offset without colon
        "time:2019-08-09 16:52:35+01:00",  # space instead of T
        "time:2019-02-30T16:52:35+01:00",  # impossible date
        "time:2019-08-09T16:52:40+01:00/2019-08-09T16:52:35+01:00",  # reversed
        "time:",
        "time:yesterday",
    ],
)
def test_malformed_time_locators(text):
    with pytest.raises(LocatorError):
        parse_locator(text)


@pytest.mark.parametrize(
    ("text", "normalized"),
    [
        ("row:5", "row:5"),
        ("rows:3-7", "rows:3-7"),
        ("ROWS:3 - 7", "rows:3-7"),
        ("rows:4", "row:4"),
    ],
)
def test_row_locators(text, normalized):
    assert parse_locator(text).normalized == normalized


@pytest.mark.parametrize(
    "text", ["row:0", "rows:7-3", "rows:a-b", "row:", "rows:1-2-3"]
)
def test_malformed_row_locators(text):
    with pytest.raises(LocatorError):
        parse_locator(text)


def test_unknown_prefix():
    with pytest.raises(LocatorError, match="unrecognised"):
        parse_locator("page:4")


def test_validate_lines_against_document(catalogue):
    r03 = catalogue.get("R03")
    validate_locator("L1", r03)
    validate_locator(f"L1-L{r03.line_count}", r03)
    with pytest.raises(LocatorError, match="out of range"):
        validate_locator(f"L{r03.line_count}-L{r03.line_count + 1}", r03)


def test_validate_time_and_rows(catalogue):
    r01 = catalogue.get("R01")
    # first and last samples are inclusive bounds
    validate_locator("time:2019-08-09T16:52:30+01:00/2019-08-09T16:52:49+01:00", r01)
    validate_locator("time:2019-08-09T15:52:49Z", r01)
    with pytest.raises(LocatorError, match="outside"):
        validate_locator("time:2019-08-09T16:52:29+01:00", r01)
    with pytest.raises(LocatorError, match="outside"):
        validate_locator(
            "time:2019-08-09T16:52:40+01:00/2019-08-09T16:52:50+01:00", r01
        )
    validate_locator(f"rows:1-{SERIES_ROWS}", r01)
    with pytest.raises(LocatorError, match="out of range"):
        validate_locator(f"row:{SERIES_ROWS + 1}", r01)
    # line locators still address R01's text file
    validate_locator("L1-L3", r01)


def test_time_and_rows_rejected_for_text_only_documents(catalogue):
    with pytest.raises(LocatorError, match="no time series"):
        validate_locator("time:2019-08-09T16:52:35+01:00", catalogue.get("S01"))
    with pytest.raises(LocatorError, match="no time series"):
        validate_locator("row:1", catalogue.get("S04"))


def test_parse_and_validate_returns_locator(catalogue):
    loc = parse_and_validate("L2-L3", catalogue.get("S03"))
    assert isinstance(loc, Locator) and loc.normalized == "L2-L3"


def test_grading_helpers():
    lines = parse_locator("L10-L20")
    assert lines.overlaps_lines(5, 10) and lines.overlaps_lines(20, 25)
    assert lines.overlaps_lines(25, 15)
    assert not lines.overlaps_lines(1, 9) and not lines.overlaps_lines(21, 30)
    assert lines.covers_line(15) and not lines.covers_line(9)
    assert not lines.covers_time(datetime(2019, 8, 9, 15, 52, tzinfo=UTC))

    span = parse_locator("time:2019-08-09T16:53:20+01:00/2019-08-09T16:54:30+01:00")
    assert span.covers_time(datetime(2019, 8, 9, 16, 53, 49, tzinfo=BST))
    assert span.covers_time(datetime(2019, 8, 9, 15, 53, 20, tzinfo=UTC))
    assert not span.covers_time(datetime(2019, 8, 9, 16, 54, 31, tzinfo=BST))
    assert span.overlaps_time(
        datetime(2019, 8, 9, 16, 54, 0, tzinfo=BST),
        datetime(2019, 8, 9, 17, 0, tzinfo=BST),
    )
    assert not span.overlaps_lines(1, 100)
    with pytest.raises(ValueError):
        span.covers_time(datetime(2019, 8, 9, 16, 53, 49))  # naive

    rows = parse_locator("rows:5-8")
    assert rows.overlaps_rows(8, 9) and not rows.overlaps_rows(9, 12)


def test_parse_iso_instant():
    assert parse_iso_instant("2019-08-09T16:53:49+01:00") == datetime(
        2019, 8, 9, 15, 53, 49, tzinfo=UTC
    )
    assert parse_iso_instant("2019-08-09T15:53:49.25Z").microsecond == 250000
    for bad in ["2019-08-09T16:53:49", "16:53:49", "", "2019-08-09"]:
        with pytest.raises(LocatorError):
            parse_iso_instant(bad)
