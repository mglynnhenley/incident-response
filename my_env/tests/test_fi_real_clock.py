"""Clock conventions of the R09/R11 rows (full-investigation real-data track).

Report and Network Rail times are written without a zone and indexed as BST (UTC+01:00 on 9-20
August 2019); post times are decoded from post identifiers (UTC); Elexon REMIT times are UTC.
The recorded time and its basis stay primary in every row; the index is only for selection.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ENV_ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ENV_ROOT / "builder" / "full_investigation" / "real"
ROWS_DIR = ENV_ROOT / "builder" / "full_investigation" / "rows"
sys.path.insert(0, str(REAL_DIR))

import fi_real_common  # noqa: E402


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def rows(name: str) -> list[dict]:
    return [
        json.loads(x)
        for x in (ROWS_DIR / name).read_text(encoding="utf-8").splitlines()
    ]


def decode(post_id: int) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
        milliseconds=(post_id >> 22) + 1288834974657
    )


@pytest.mark.parametrize(
    ("day", "clock", "expected"),
    [
        ("2019-08-09", "17:51", "2019-08-09T16:51:00Z"),
        ("2019-08-09", "00:24", "2019-08-08T23:24:00Z"),
        ("2019-08-10", "08:33", "2019-08-10T07:33:00Z"),
        ("2019-08-09", "16:52:33", "2019-08-09T15:52:33Z"),
    ],
)
def test_bst_to_utc(day: str, clock: str, expected: str) -> None:
    assert fi_real_common.utc_z(fi_real_common.bst_to_utc(day, clock)) == expected


def test_bst_to_utc_refuses_dates_without_a_coded_rule() -> None:
    with pytest.raises(fi_real_common.BuildError):
        fi_real_common.bst_to_utc("2019-10-27", "01:30")


def test_snowflake_decoding_matches_known_posts() -> None:
    # ESO's 18:27:46 BST post and the airport's 17:49:50 BST post (UTC = BST - 1 h).
    assert fi_real_common.utc_z(decode(1159878953596792833)) == "2019-08-09T17:27:46Z"
    assert fi_real_common.utc_z(fi_real_common.post_time(1159869406102425601)) == (
        "2019-08-09T16:49:50Z"
    )


def test_network_rail_rows_index_the_recorded_start_as_bst() -> None:
    for row in rows("real_r11_control.jsonl"):
        match = re.search(
            r"(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2})", row["recorded_time"]
        )
        assert match, row["recorded_time"]
        dd, mm, yyyy, hh, mi = (int(x) for x in match.groups())
        local = datetime(yyyy, mm, dd, hh, mi, tzinfo=UTC)
        assert utc(row["index_time_utc"]) == local - timedelta(hours=1)
        assert row["index_uncertainty_s"] == 60
        assert "BST" in row["clock_basis"]


def test_eso_comms_rows_index_their_recorded_time() -> None:
    days = {"FRIDAY": 9, "SATURDAY": 10, "SUNDAY": 11}
    checked = 0
    for row in rows("real_r09_control.jsonl"):
        recorded = row["recorded_time"]
        index = utc(row["index_time_utc"])
        if recorded.startswith("post identifier"):
            stamp = re.search(r"\d{4}-\d{2}-\d{2}T[\d:.]+Z", recorded).group(0)
            assert index == utc(stamp)
            checked += 1
            continue
        match = re.fullmatch(
            r"(?:(FRIDAY|SATURDAY|SUNDAY) )?(\d{2}):(\d{2})(?:hrs)?", recorded
        )
        if match is None:
            continue
        day = days.get(match.group(1) or "FRIDAY")
        local = datetime(
            2019, 8, day, int(match.group(2)), int(match.group(3)), tzinfo=UTC
        )
        assert index == local - timedelta(hours=1), row["entry_id"]
        checked += 1
    assert checked >= 30


def test_remit_rows_index_the_publication_time() -> None:
    for row in rows("real_r09_asset.jsonl"):
        assert row["recorded_time"] == f"publishTime {row['index_time_utc']}"
        assert row["index_uncertainty_s"] == 0
        assert row["provenance"]["record"]["publishTime"] == row["index_time_utc"]
