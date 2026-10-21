"""query_asset_log and query_control_log: selection, pagination, rendering, errors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sr_helpers import make_sr_bundle, sr_config

from environment.incident.episode import Episode, render
from environment.incident.logs import ASSET_COLUMNS, CONTROL_COLUMNS, render_rows

DAY_START, DAY_END = "2019-08-09T00:00:00Z", "2019-08-10T00:00:00Z"


@pytest.fixture
def episode(tmp_path: Path) -> Episode:
    ep = Episode(sr_config(tmp_path, make_sr_bundle(tmp_path / "src")))
    ep.reset()
    return ep


def _asset(ep: Episode, asset_id: str, start=DAY_START, end=DAY_END, **extra):
    return ep.call(
        "query_asset_log", {"asset_id": asset_id, "start": start, "end": end, **extra}
    )


def _room(ep: Episode, room: str, start=DAY_START, end=DAY_END, **extra):
    return ep.call(
        "query_control_log", {"room": room, "start": start, "end": end, **extra}
    )


def test_asset_rows_are_selected_by_index_time(episode: Episode):
    env = _asset(
        episode, "ESW-400", "2019-08-09T16:52:33.490+01:00", "2019-08-09T15:52:33.564Z"
    ).envelope
    assert env["ok"] and env["evidence_ids"] == ["R03"]
    rows = env["data"]["rows"]
    # start inclusive (.490), end exclusive (.564)
    assert [r["event_id"] for r in rows] == ["ESW-0001", "ESW-0002"]
    assert set(rows[0]) == {
        "event_id",
        "evidence_id",
        "asset_id",
        "recorded_time",
        "clock_basis",
        "index_time_utc",
        "index_uncertainty_s",
        "signal",
        "value",
        "unit",
        "text",
        "value_status",
    }
    data = env["data"]
    assert data["clock_note"] == "Synthetic clock note."
    assert data["status"] == "STATUS: SYNTHETIC TEST LOG - NOT EVIDENCE"
    assert data["log_coverage"]["rows"] == 5
    assert "only to select rows" in data["selection_note"]


def test_rows_render_with_recorded_time_and_clock_first(episode: Episode):
    result = _asset(episode, "ESW-400")
    body = result.text.split("\n\n", 1)[1].splitlines()
    assert body[0].startswith("--- asset ESW-400 log, rows 1-5 of 5")
    assert body[1].split(" | ")[:2] == ["recorded_time", "clock_basis"]
    assert body[1].split(" | ") == list(ASSET_COLUMNS)
    first = body[2].split(" | ")
    assert first[0] == "T+753.490 s"
    assert first[1] == "synthetic relay clock (BST, UTC+01:00)"
    assert first[2] == "ESW-0001" and first[-2] == "2019-08-09T15:52:33.490Z"
    assert result.text == render(result.envelope)


def test_signal_filter_and_unknown_signal(episode: Episode):
    env = _asset(episode, "ESW-400", signal="  CIRCUIT   state ").envelope
    assert env["data"]["signal"] == "circuit state"
    assert [r["event_id"] for r in env["data"]["rows"]] == ["ESW-0004", "ESW-0005"]
    bad = _asset(episode, "ESW-400", signal="voltage")
    assert bad.error_code == "UNKNOWN_ID" and bad.counted
    assert "protection operation" in bad.envelope["error"]["message"]


def test_rows_from_several_evidence_records(episode: Episode):
    env = _asset(episode, "PLANT-A", "2019-08-09T15:40:00Z", "2019-08-09T15:40:20Z")
    data = env.envelope["data"]
    assert [r["evidence_id"] for r in data["rows"]] == ["R02", "R05", "R02", "R05"]
    assert env.envelope["evidence_ids"] == ["R02", "R05"]


def test_asset_pages_hold_at_most_200_rows(episode: Episode):
    first = _asset(episode, "PLANT-A").envelope
    assert first["data"]["page_size"] == 200 and first["data"]["returned"] == 200
    assert first["data"]["total_rows"] == 460
    ids = [r["event_id"] for r in first["data"]["rows"]]
    cursor = first["next_cursor"]
    pages = 1
    while cursor:
        env = _asset(episode, "PLANT-A", cursor=cursor).envelope
        assert env["ok"], env["error"]
        ids += [r["event_id"] for r in env["data"]["rows"]]
        cursor = env["next_cursor"]
        pages += 1
    assert pages == 3 and len(ids) == len(set(ids)) == 460
    # rows come in index-time order, ties broken by ID
    again = _asset(episode, "PLANT-A").envelope
    assert again["data"]["rows"] == first["data"]["rows"]
    assert again["next_cursor"] == first["next_cursor"]


def test_cursor_is_bound_to_the_signal_and_asset(episode: Episode):
    cursor = _asset(episode, "PLANT-A").envelope["next_cursor"]
    assert _asset(
        episode, "PLANT-A", signal="T_PLANT-1 B1610 MWh", cursor=cursor
    ).error_code == ("INVALID_ARGUMENT")
    assert _room(episode, "SO-CONTROL", cursor=cursor).error_code == "INVALID_ARGUMENT"
    # the same query with an equivalent offset keeps the cursor valid
    same = _asset(
        episode,
        "PLANT-A",
        "2019-08-09T01:00:00+01:00",
        "2019-08-10T01:00:00+01:00",
        cursor=cursor,
    )
    assert same.ok and same.envelope["data"]["offset"] == 200


def test_empty_windows_are_not_errors(episode: Episode):
    env = _asset(
        episode, "ESW-400", "2019-08-09T20:00:00Z", "2019-08-09T21:00:00Z"
    ).envelope
    assert env["ok"] and env["data"]["rows"] == [] and env["evidence_ids"] == []
    assert env["next_cursor"] is None


@pytest.mark.parametrize(
    ("args", "code"),
    [
        ({"start": DAY_START, "end": DAY_END}, "INVALID_ARGUMENT"),
        ({"asset_id": "NOPE", "start": DAY_START, "end": DAY_END}, "UNKNOWN_ID"),
        ({"asset_id": "../ESW-400", "start": DAY_START, "end": DAY_END}, "UNKNOWN_ID"),
        ({"asset_id": "esw-400", "start": DAY_START, "end": DAY_END}, "UNKNOWN_ID"),
        ({"asset_id": "ESW-400", "end": DAY_END}, "INVALID_ARGUMENT"),
        ({"asset_id": "ESW-400", "start": "today", "end": DAY_END}, "INVALID_ARGUMENT"),
        (
            {"asset_id": "ESW-400", "start": DAY_END, "end": DAY_START},
            "INVALID_ARGUMENT",
        ),
        ({"asset_id": 4, "start": DAY_START, "end": DAY_END}, "INVALID_ARGUMENT"),
        (
            {"asset_id": "ESW-400", "start": DAY_START, "end": DAY_END, "room": "x"},
            "INVALID_ARGUMENT",
        ),
    ],
)
def test_asset_argument_errors(episode: Episode, args, code):
    result = episode.call("query_asset_log", args)
    assert result.error_code == code and result.counted


def test_control_log_rows(episode: Episode):
    result = _room(
        episode, "SO-CONTROL", "2019-08-09T15:50:00Z", "2019-08-09T16:30:00Z"
    )
    env = result.envelope
    assert env["ok"] and env["evidence_ids"] == ["R08", "S07"]
    rows = env["data"]["rows"]
    assert [r["entry_id"] for r in rows] == [
        "SO-001",
        "SO-002",
        "SO-003",
        "SO-004",
        "SO-005",
    ]
    assert env["data"]["room"] == "SO-CONTROL" and "signal" not in env["data"]
    body = result.text.split("\n\n", 1)[1].splitlines()
    assert body[0].startswith("--- control room SO-CONTROL log, rows 1-5 of 5")
    assert body[1].split(" | ") == list(CONTROL_COLUMNS)
    # cells with a bar, a line break or padding are JSON strings (lossless)
    assert '"Synthetic call | with a bar"' in body[3]
    assert '"Synthetic call\\nwith a break"' in body[4]
    assert '"  Synthetic padded entry"' in body[5]
    assert len(body) == 7


def test_rooms_and_assets_are_separate_namespaces(episode: Episode):
    room = _room(episode, "DNO-A").envelope
    asset = _asset(episode, "DNO-A").envelope
    assert room["data"]["rows"][0]["entry_id"] == "DNO-A-E1"
    assert asset["data"]["rows"][0]["event_id"] == "DNO-A-0001"
    assert _room(episode, "ESW-400").error_code == "UNKNOWN_ID"


def test_control_log_rejects_unknown_arguments(episode: Episode):
    result = episode.call(
        "query_control_log",
        {"room": "SO-CONTROL", "start": DAY_START, "end": DAY_END, "signal": "x"},
    )
    assert result.error_code == "INVALID_ARGUMENT"


def test_render_rows_is_lossless():
    rows = [
        {"a": "plain", "b": "x | y", "c": None},
        {"a": 1.5, "b": '"quoted', "c": True},
    ]
    text = render_rows(rows, ["a", "b", "c"])
    lines = text.splitlines()
    assert lines[0] == "a | b | c"
    assert lines[1] == 'plain | "x | y" | '
    assert lines[2] == f"1.5 | {json.dumps(chr(34) + 'quoted')} | true"


def test_an_edited_log_cursor_offset_is_refused(episode: Episode):
    import base64

    cursor = _asset(episode, "PLANT-A").envelope["next_cursor"]
    payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    for offset in (1, 199, 201, 459):
        edited = dict(payload, o=offset)
        text = json.dumps(edited, sort_keys=True, separators=(",", ":"))
        forged = base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")
        assert _asset(episode, "PLANT-A", cursor=forged).error_code == (
            "INVALID_ARGUMENT"
        ), offset


@pytest.mark.parametrize("tool", ["query_asset_log", "query_control_log"])
def test_log_windows_without_a_utc_equivalent_are_invalid(episode: Episode, tool):
    ident = (
        {"asset_id": "ESW-400"} if tool == "query_asset_log" else {"room": "SO-CONTROL"}
    )
    result = episode.call(
        tool,
        {**ident, "start": "0001-01-01T00:00:00+23:59", "end": DAY_END},
    )
    assert result.error_code == "INVALID_ARGUMENT"
    assert "time out of range" in result.envelope["error"]["message"]
