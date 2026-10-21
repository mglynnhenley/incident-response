"""Quote verification: every quote the judge returns must occur in the text of a span
it was shown; narrowed locators, span IDs and misplaced quotes are handled, invented
text is rejected."""

from __future__ import annotations

import pytest
from sr_grading_support import catalogue, key
from sr_judge_support import RUN_MODEL, base_report, config, small_submission

from environment.incident import grading as mvp
from environment.incident.judge import build_units, load_rubric
from environment.incident.judge.verify import (
    check_span,
    find_report_location,
    quote_occurs,
)


def shown(inputs, unit_id="T06"):
    unit = next(u for u in inputs.units if u.unit_id == unit_id)
    return inputs.index.shown_in(unit)


@pytest.fixture(scope="module")
def inputs():
    sub = small_submission()
    cfg = config(max_span_chars=400)
    sub_dict, _ = mvp._as_submission(sub, catalogue())
    return build_units(
        sub_dict,
        base_report(sub),
        key(),
        catalogue(),
        cfg,
        load_rubric(cfg.rubric_path()),
        blind_terms=[RUN_MODEL],
    )


@pytest.mark.parametrize(
    "quote, text, ok",
    [
        ("insufficiently damped", "an Insufficiently   damped\nresonance", True),
        ("sub-synchronous", "sub‑synchronous range", True),  # non-breaking hyphen
        ("“Our report”", '"our report" concludes', True),
        ("[L55] events of 9 August", "events of 9 August 2019", True),
        ("A1 ... resonance", "A1 Section: ... damped resonance", True),
        ("resonance ... A1", "A1 Section: ... damped resonance", False),  # order
        ("caused by the DRC", "the DRC was not the cause", False),
        ("MW", "799 MW", False),  # too short to verify anything
        ("", "anything", False),
        ("48.787", "2019-08-09T16:53:49+01:00,48.787", True),
    ],
)
def test_quote_occurs(quote, text, ok):
    assert quote_occurs(quote, text) is ok


def test_exact_span(inputs):
    check = check_span(
        {"evidence_id": "S01", "locator": "L54-L58", "quote": "dated 5 September 2019"},
        inputs.index,
    )
    assert check.ok and check.span["locator"] == "L54-L58"
    assert check.within == ["C1"]


def test_narrowed_locator_inside_a_shown_span(inputs):
    check = check_span(
        {"evidence_id": "S01", "locator": "l55", "quote": "events of 9 August 2019"},
        inputs.index,
    )
    assert check.ok and check.span["locator"] == "L55" and "C1" in check.within


def test_line_outside_every_shown_span_is_rejected(inputs):
    """S01 L1 resolves in the bundle, but the judge was never shown it."""
    text = catalogue().get("S01").lines[0]
    check = check_span(
        {"evidence_id": "S01", "locator": "L1", "quote": text[:40]}, inputs.index
    )
    assert not check.ok and check.reason == "quote not found in any shown span"


def test_span_id_as_locator(inputs):
    check = check_span(
        {"evidence_id": "C2", "locator": "C2", "quote": "Our report concludes"},
        inputs.index,
    )
    assert check.ok
    assert check.span == {
        "evidence_id": "S09",
        "locator": "response:S09-ORS-04",
        "quote": "Our report concludes",
    }
    bad = check_span(
        {"evidence_id": "S09", "locator": "C2", "quote": "the turbines were fine"},
        inputs.index,
    )
    assert not bad.ok and bad.reason == "quote not found in C2"


def test_wrong_locator_right_quote_is_relocated(inputs):
    check = check_span(
        {"evidence_id": "S01", "locator": "L90", "quote": "dated 5 September 2019"},
        inputs.index,
    )
    assert check.ok and check.span["relocated"] is True
    assert check.span["locator"] == "L54-L58"


@pytest.mark.parametrize(
    "item, reason",
    [
        (
            {"evidence_id": "S01", "locator": "L54-L58", "quote": "the DRC caused it"},
            "quote not found in any shown span",
        ),
        (
            {"evidence_id": "S02", "locator": "L3", "quote": "modelling note"},
            "no span of 'S02' was shown",
        ),
        (
            {"evidence_id": "R07", "locator": "L1", "quote": "demand disconnection"},
            "no span of 'R07' was shown",
        ),
        (
            {"evidence_id": "S01", "locator": "L54", "quote": "  "},
            "empty or too short quote",
        ),
        (
            {"evidence_id": "C99", "locator": "C99", "quote": "anything at all"},
            "no span of 'C99' was shown",
        ),
    ],
)
def test_hallucinated_spans_are_rejected(inputs, item, reason):
    check = check_span(item, inputs.index, shown(inputs))
    assert not check.ok and check.reason == reason
    assert check.span["quote"] == item["quote"]


def test_quotes_from_truncated_text_are_rejected():
    sub = small_submission()
    sub["findings"][0]["citations"].append({"evidence_id": "S12", "locator": "L1-L152"})
    cfg = config(max_span_chars=400)
    sub_dict, _ = mvp._as_submission(sub, catalogue())
    built = build_units(
        sub_dict,
        base_report(sub),
        key(),
        catalogue(),
        cfg,
        load_rubric(cfg.rubric_path()),
    )
    span = next(s for s in built.index.spans.values() if s.locator == "L1-L152")
    hidden = catalogue().get("S12").lines[140]
    assert hidden.strip() and hidden not in span.shown_text
    check = check_span(
        {"evidence_id": "S12", "locator": "L1-L152", "quote": hidden.strip()[:60]},
        built.index,
        shown(built),
    )
    assert not check.ok


def test_spans_shown_only_in_another_request_are_rejected(inputs):
    """Keyed spans of another unit were never in this request: a verbatim quote from
    one is still not a span this judge call saw."""
    t05 = next(u for u in inputs.units if u.unit_id == "T05")
    other = next(
        inputs.index.spans[s]
        for s in t05.keyed_span_ids
        if s.startswith("K") and inputs.index.spans[s].evidence_id == "S07"
    )
    item = {
        "evidence_id": other.evidence_id,
        "locator": other.locator,
        "quote": other.shown_text.split("\n")[0][:60],
    }
    assert check_span(item, inputs.index, shown(inputs, "T05")).ok
    rejected = check_span(item, inputs.index, shown(inputs, "T06"))
    assert not rejected.ok and rejected.reason == "no span of 'S07' was shown"
    by_id = check_span({**item, "locator": other.span_id}, inputs.index, shown(inputs))
    assert not by_id.ok


def test_report_locations(inputs):
    texts = inputs.report_texts
    assert find_report_location("The DRC was cleared by the operator.", texts) == (
        "report.sections[0].body"
    )
    assert find_report_location("prepared by [model]", texts) == (
        "report.sections[0].body"
    )
    assert find_report_location("Claude", texts) is None  # blinded text only
    assert find_report_location("Hornsea tripped on a cable fault", texts) is None
