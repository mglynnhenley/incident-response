"""Clock conventions of the real-data builder and of its asset/control rows.

Elexon timestamps are UTC; Elexon/NESO settlement periods follow the UK local clock (BST =
UTC+01:00 on 9 August 2019), so settlement period 34 is 16:30-17:00 BST (15:30-16:00 UTC).
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ENV_ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ENV_ROOT / "builder" / "system_response" / "real"
ROWS_DIR = ENV_ROOT / "builder" / "system_response" / "rows"
BUNDLE_DIR = (
    ENV_ROOT / "src" / "environment" / "incident" / "bundles" / "system_response"
)
sys.path.insert(0, str(REAL_DIR))

import real_common  # noqa: E402

BST = timezone(timedelta(hours=1))
DAY = date(2019, 8, 9)


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def rows(name: str) -> list[dict]:
    return [
        json.loads(x)
        for x in (ROWS_DIR / name).read_text(encoding="utf-8").splitlines()
    ]


def test_settlement_period_34_is_1630_to_1700_bst() -> None:
    start, end = real_common.settlement_period_bounds_utc(DAY, 34)
    assert start == datetime(2019, 8, 9, 15, 30, tzinfo=UTC)
    assert end == datetime(2019, 8, 9, 16, 0, tzinfo=UTC)
    assert start.astimezone(BST).strftime("%H:%M") == "16:30"
    assert end.astimezone(BST).strftime("%H:%M") == "17:00"


@pytest.mark.parametrize(
    ("period", "start_utc"),
    [
        (1, "2019-08-08T23:00:00Z"),
        (2, "2019-08-08T23:30:00Z"),
        (35, "2019-08-09T16:00:00Z"),
        (48, "2019-08-09T22:30:00Z"),
    ],
)
def test_settlement_period_starts(period: int, start_utc: str) -> None:
    start, end = real_common.settlement_period_bounds_utc(DAY, period)
    assert start == utc(start_utc) and end - start == timedelta(minutes=30)


def test_clock_rule_refuses_dates_it_does_not_cover() -> None:
    with pytest.raises(real_common.BuildError):
        real_common.settlement_period_bounds_utc(date(2019, 10, 27), 1)
    with pytest.raises(real_common.BuildError):
        real_common.settlement_period_bounds_utc(DAY, 51)


def test_parse_utc_reads_zone_less_elexon_times_as_utc() -> None:
    assert real_common.parse_utc("2019-08-09T16:00:00") == datetime(
        2019, 8, 9, 16, tzinfo=UTC
    )
    assert real_common.parse_utc("2019-08-09T15:54:00Z") == datetime(
        2019, 8, 9, 15, 54, tzinfo=UTC
    )
    with pytest.raises(real_common.BuildError):
        real_common.parse_utc("2019-08-09T16:54:00+01:00")


def test_b1610_rows_index_the_middle_of_their_settlement_period() -> None:
    b1610 = [r for r in rows("real_r02_asset.jsonl") if "B1610" in r["signal"]]
    assert len(b1610) == 192
    for row in b1610:
        period = row["provenance"]["record"]["settlementPeriod"]
        start, end = real_common.settlement_period_bounds_utc(DAY, period)
        index = utc(row["index_time_utc"])
        assert row["index_uncertainty_s"] == 900
        assert (
            index - timedelta(seconds=900) == start
            and index + timedelta(seconds=900) == end
        )
        half_hour_end = row["provenance"]["record"]["halfHourEndTime"]
        assert real_common.parse_utc(half_hour_end) == end
        assert f"settlementPeriod {period} " in row["recorded_time"]
        assert half_hour_end in row["recorded_time"]
    sp34 = next(r for r in b1610 if r["event_id"] == "R02-B1610-T_LBAR-1-20190809-SP34")
    window = (
        utc(sp34["index_time_utc"]) - timedelta(seconds=sp34["index_uncertainty_s"]),
        utc(sp34["index_time_utc"]) + timedelta(seconds=sp34["index_uncertainty_s"]),
    )
    assert [t.astimezone(BST).strftime("%H:%M") for t in window] == ["16:30", "17:00"]
    assert "halfHourEndTime 2019-08-09T16:00:00" in sp34["recorded_time"]


def test_mel_and_control_rows_index_their_recorded_utc_time() -> None:
    for row in rows("real_r02_asset.jsonl"):
        if row["signal"].endswith("MEL MW"):
            assert row["index_time_utc"] == row["provenance"]["record"]["timeFrom"]
            assert row["recorded_time"].startswith(f"timeFrom {row['index_time_utc']}")
            assert row["index_uncertainty_s"] == 0
    for row in rows("real_r06_control.jsonl"):
        assert row["recorded_time"] == f"acceptanceTime {row['index_time_utc']}"
        assert row["index_uncertainty_s"] == 60
        assert row["clock_basis"].startswith("UTC")


@pytest.mark.parametrize(
    ("post_id", "expected"),
    [
        (1159858936037748736, "2019-08-09T16:08:14"),
        (1159868588607639552, "2019-08-09T16:46:35"),
        (1159882018148278274, "2019-08-09T17:39:57"),
    ],
)
def test_post_identifier_decoding(post_id: int, expected: str) -> None:
    decoded = real_common.snowflake_utc(post_id)
    assert decoded.replace(microsecond=0) == datetime.fromisoformat(expected).replace(
        tzinfo=UTC
    )


def test_r07_post_times_are_decoded_from_their_identifiers() -> None:
    import real_r07

    text = (BUNDLE_DIR / "R07" / "R07.txt").read_text(encoding="utf-8")
    for post in real_r07.DNO_POSTS:
        stamp = real_common.iso_z(
            real_common.snowflake_utc(post["post_id"]).replace(microsecond=0)
        )
        assert f"{stamp} | {post['organisation']} |" in text


def test_fuelinst_rows_lie_in_their_settlement_period() -> None:
    import csv

    path = BUNDLE_DIR / "R02" / "R02_elexon_fuelinst_5min_20190809.csv"
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            start, end = real_common.settlement_period_bounds_utc(
                DAY, int(row["settlementPeriod"])
            )
            assert start <= utc(row["startTime"]) < end
            assert utc(row["publishTime"]) - utc(row["startTime"]) == timedelta(
                minutes=5
            )
