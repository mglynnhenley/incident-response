"""query_frequency: offset-aware [start, end), resolution 1, pages <= 1000, R01 only."""

from __future__ import annotations

import csv
import io
import os
from pathlib import Path

import pytest
from sr_helpers import SERIES_ROWS, make_sr_bundle, series_csv, sr_config

from environment.incident.episode import Episode, read_state, render


@pytest.fixture
def episode(tmp_path: Path) -> Episode:
    ep = Episode(sr_config(tmp_path, make_sr_bundle(tmp_path / "src")))
    ep.reset()
    return ep


def _q(ep: Episode, start: str, end: str, **extra):
    return ep.call("query_frequency", {"start": start, "end": end, **extra})


def _csv_rows() -> list[list[str]]:
    return list(csv.reader(io.StringIO(series_csv())))[1:]


def test_window_is_start_inclusive_end_exclusive(episode: Episode):
    env = _q(episode, "2019-08-09T16:52:30+01:00", "2019-08-09T16:52:35+01:00").envelope
    assert env["ok"] and env["evidence_ids"] == ["R01"]
    data = env["data"]
    assert (
        data["total_rows"] == 5 and data["returned"] == 5 and env["next_cursor"] is None
    )
    assert [r[0] for r in data["rows"]] == [751, 752, 753, 754, 755]
    assert data["rows"][0][1] == "2019-08-09T16:52:30+01:00"
    assert data["rows"][-1][1] == "2019-08-09T16:52:34+01:00"
    assert data["window"]["rule"] == "start inclusive, end exclusive"
    assert data["columns"] == ["row", "timestamp", "frequency_hz"]


def test_offsets_are_honoured(episode: Episode):
    bst = _q(episode, "2019-08-09T16:52:30+01:00", "2019-08-09T16:52:40+01:00")
    utc = _q(episode, "2019-08-09T15:52:30Z", "2019-08-09T15:52:40.000+00:00")
    other = _q(episode, "2019-08-09T10:52:30-05:00", "2019-08-09T10:52:40-05:00")
    rows = bst.envelope["data"]["rows"]
    assert rows == utc.envelope["data"]["rows"] == other.envelope["data"]["rows"]
    fractional = _q(
        episode, "2019-08-09T16:52:30.5+01:00", "2019-08-09T16:52:32.5+01:00"
    )
    assert [r[0] for r in fractional.envelope["data"]["rows"]] == [752, 753]


def test_values_are_exactly_as_recorded(episode: Episode):
    result = _q(episode, "2019-08-09T16:40:00+01:00", "2019-08-09T16:40:20+01:00")
    expected = _csv_rows()[:20]
    assert [r[1:] for r in result.envelope["data"]["rows"]] == expected
    body = result.text.split("\n\n", 1)[1].splitlines()
    assert body[1] == "row,timestamp,frequency_hz"
    assert body[2] == f"1,{expected[0][0]},{expected[0][1]}"
    assert expected[0][1] == "50.000"  # trailing zeros preserved (text, not float)
    assert result.text == render(result.envelope)


@pytest.mark.parametrize("resolution", [2, 0.5, "1", True, [1], {"s": 1}])
def test_resolution_must_be_one(episode: Episode, resolution):
    result = _q(
        episode,
        "2019-08-09T16:52:30+01:00",
        "2019-08-09T16:52:35+01:00",
        resolution_s=resolution,
    )
    assert result.error_code == "INVALID_ARGUMENT" and result.counted


@pytest.mark.parametrize("resolution", [1, 1.0])
def test_resolution_one_is_accepted(episode: Episode, resolution):
    result = _q(
        episode,
        "2019-08-09T16:52:30+01:00",
        "2019-08-09T16:52:35+01:00",
        resolution_s=resolution,
    )
    assert result.ok


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2019-08-09T16:52:30", "2019-08-09T16:52:35+01:00"),  # no offset
        ("16:52:30", "16:52:35"),
        ("2019-08-09T16:52:35+01:00", "2019-08-09T16:52:35+01:00"),  # empty
        ("2019-08-09T16:52:35+01:00", "2019-08-09T16:52:30+01:00"),  # reversed
        (None, "2019-08-09T16:52:35+01:00"),
        ("2019-08-09T16:52:30+01:00", 5),
    ],
)
def test_bad_windows_are_invalid(episode: Episode, start, end):
    args = {k: v for k, v in {"start": start, "end": end}.items() if v is not None}
    assert episode.call("query_frequency", args).error_code == "INVALID_ARGUMENT"


def test_windows_outside_the_record_are_out_of_range(episode: Episode):
    before = _q(episode, "2019-08-09T15:00:00+01:00", "2019-08-09T16:40:00+01:00")
    after = _q(episode, "2019-08-09T17:05:00+01:00", "2019-08-09T17:10:00+01:00")
    for result in (before, after):
        assert result.error_code == "OUT_OF_RANGE" and result.counted
        assert "2019-08-09T16:40:00+01:00" in result.envelope["error"]["message"]
    partial = _q(episode, "2019-08-09T17:04:58+01:00", "2019-08-09T18:00:00+01:00")
    assert partial.ok and partial.envelope["data"]["total_rows"] == 2
    tiny = _q(episode, "2019-08-09T16:50:00.2+01:00", "2019-08-09T16:50:00.8+01:00")
    assert tiny.ok and tiny.envelope["data"]["total_rows"] == 0  # empty is not an error
    assert "no rows (0 of 0)" in tiny.text


def test_pages_hold_at_most_1000_rows_and_cursors_continue(episode: Episode):
    start, end = "2019-08-09T16:40:00+01:00", "2019-08-09T17:10:00+01:00"
    first = _q(episode, start, end)
    data = first.envelope["data"]
    assert data["page_size"] == 1000 and data["returned"] == 1000
    assert data["total_rows"] == SERIES_ROWS
    cursor = first.envelope["next_cursor"]
    assert cursor
    # the same window written with another offset continues the same listing
    second = _q(episode, "2019-08-09T15:40:00Z", "2019-08-09T16:10:00Z", cursor=cursor)
    assert second.ok and second.envelope["next_cursor"] is None
    rows = data["rows"] + second.envelope["data"]["rows"]
    assert [r[0] for r in rows] == list(range(1, SERIES_ROWS + 1))
    assert second.envelope["data"]["offset"] == 1000
    # cursors are deterministic
    again = _q(episode, start, end)
    assert again.envelope["next_cursor"] == cursor
    assert again.envelope["data"] == first.envelope["data"]


def test_cursor_misuse_is_invalid(episode: Episode):
    start, end = "2019-08-09T16:40:00+01:00", "2019-08-09T17:10:00+01:00"
    cursor = _q(episode, start, end).envelope["next_cursor"]
    other_window = _q(episode, start, "2019-08-09T17:00:00+01:00", cursor=cursor)
    assert other_window.error_code == "INVALID_ARGUMENT"
    assert "different query" in other_window.envelope["error"]["message"]
    for bad in ("garbage", cursor[:-3] + "AAA", "e30"):
        assert _q(episode, start, end, cursor=bad).error_code == "INVALID_ARGUMENT"
    asset_cursor_misuse = episode.call(
        "query_asset_log",
        {"asset_id": "PLANT-A", "start": start, "end": end, "cursor": cursor},
    )
    assert asset_cursor_misuse.error_code == "INVALID_ARGUMENT"


def test_smaller_configured_pages(tmp_path: Path):
    ep = Episode(
        sr_config(tmp_path, make_sr_bundle(tmp_path / "src"), frequency_page_size=7)
    )
    ep.reset()
    seen: list[int] = []
    cursor = None
    while True:
        args = {
            "start": "2019-08-09T16:50:00+01:00",
            "end": "2019-08-09T16:50:20+01:00",
        }
        if cursor:
            args["cursor"] = cursor
        env = ep.call("query_frequency", args).envelope
        seen += [r[0] for r in env["data"]["rows"]]
        cursor = env["next_cursor"]
        if not cursor:
            break
    assert seen == list(range(601, 621))


def test_query_materialises_r01_for_python(episode: Episode):
    assert os.listdir(episode.config.evidence_dir) == []
    result = _q(episode, "2019-08-09T16:52:30+01:00", "2019-08-09T16:52:31+01:00")
    assert result.envelope["data"]["artifact_path"] == "R01/frequency.csv"
    assert read_state(episode.episode_dir).retrieved == ["R01"]
    py = episode.run_python(
        "import os, pandas as pd\n"
        "df = pd.read_csv(os.path.join(os.environ['EVIDENCE_DIR'], 'R01', 'frequency.csv'))\n"
        "print(len(df), sorted(os.listdir(os.environ['EVIDENCE_DIR'])))"
    )
    assert py.envelope["data"]["stdout"] == f"{SERIES_ROWS} ['R01']\n"


def _edit_cursor(cursor: str, **changes) -> str:
    import base64
    import json

    payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    payload.update(changes)
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def test_an_edited_cursor_offset_is_refused(episode: Episode):
    """Review probe p2: the offset is authenticated (integrity field keyed by the bundle
    sha256) and must be a whole number of pages; only next_cursor values are accepted."""
    start, end = "2019-08-09T16:40:00+01:00", "2019-08-09T17:10:00+01:00"
    cursor = _q(episode, start, end).envelope["next_cursor"]
    assert _q(episode, start, end, cursor=cursor).ok
    for offset in (1, 999, 1001, SERIES_ROWS - 1, 0):
        edited = _edit_cursor(cursor, o=offset)
        result = _q(episode, start, end, cursor=edited)
        assert result.error_code == "INVALID_ARGUMENT", offset
        assert "cursor is not valid" in result.envelope["error"]["message"]
    # Removing or forging the integrity field does not help either.
    for changes in ({"k": "0" * 16}, {"k": None}):
        assert _q(
            episode, start, end, cursor=_edit_cursor(cursor, **changes)
        ).error_code == ("INVALID_ARGUMENT")
    # Junk appended to a valid cursor is not silently ignored.
    assert _q(episode, start, end, cursor=cursor + "!!").error_code == (
        "INVALID_ARGUMENT"
    )


def test_cursors_are_deterministic_and_bound_to_the_bundle(tmp_path: Path):
    start, end = "2019-08-09T16:40:00+01:00", "2019-08-09T17:10:00+01:00"
    bundle = make_sr_bundle(tmp_path / "src")
    cursors = []
    for name in ("a", "b"):
        ep = Episode(sr_config(tmp_path / name, bundle))
        ep.reset()
        cursors.append(_q(ep, start, end).envelope["next_cursor"])
    assert cursors[0] == cursors[1]
    from environment.incident.pagination import decode_cursor, query_digest

    query = {
        "start": "2019-08-09T15:40:00+00:00",
        "end": "2019-08-09T16:10:00+00:00",
        "resolution_s": 1,
    }
    ep = Episode(sr_config(tmp_path / "c", bundle))
    ep.reset()
    key = ep.catalogue.bundle_sha256
    digest = query_digest(query)
    version = ep.catalogue.bundle_version
    total = SERIES_ROWS
    args = ("query_frequency", digest, version, total)
    assert decode_cursor(cursors[0], args[0], args[1], args[2], args[3], key) == 1000
    from environment.incident.catalogue import CursorError

    with pytest.raises(CursorError):
        decode_cursor(cursors[0], args[0], args[1], args[2], args[3], "other bundle")


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("0001-01-01T00:00:00+23:59", "2019-08-09T16:41:00+01:00"),
        ("2019-08-09T16:41:00+01:00", "9999-12-31T23:59:59-23:59"),
    ],
)
def test_instants_without_a_utc_equivalent_are_invalid(episode: Episode, start, end):
    """Review probes p3/p4: formerly INTERNAL_ERROR (OverflowError)."""
    result = _q(episode, start, end)
    assert result.error_code == "INVALID_ARGUMENT" and result.counted
    assert "time out of range" in result.envelope["error"]["message"]
    details = result.envelope["error"]["details"]
    assert details[0]["message"] == "time out of range"
