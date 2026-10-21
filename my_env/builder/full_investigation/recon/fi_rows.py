"""Control-log row fragment derived from S08 (``rows/recon_s08.jsonl``).

Rows restate entries of the bundle record S08; they add no fact of their own. A row is made only
where the published account prints a clock time for the entry ("only where sourced"): of the
rail accounts, only GTR's technical review does ("at 1653", event summary item 1). ORR's
"around 4:52pm" belongs to ORR's report, not to a railway control room, and ORR prints no other
clock time; the Network Rail and GTR timed incident records are real-data evidence of the
real-data track. So the GTR-FLEET-CONTROL room has one row and no NETWORK-RAIL-CONTROL row is
made here.

Time fields (decision 23, as ``builder/system_response/recon/recon_rows.py``): ``recorded_time``
is the time exactly as printed and ``clock_basis`` says how to read it; ``index_time_utc`` is an
instant used only for filtering, within +/- ``index_uncertainty_s`` of the true instant: a time
printed to the minute -> that minute, +/- 60 s; unlabelled clocks read as BST (UTC+01:00).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

BST = timedelta(hours=1)
ROOM_GTR = "GTR-FLEET-CONTROL"
GTR_CLOCK = (
    "hhmm as printed in GTR's technical review (event summary); no clock labelled, read as "
    "BST (UTC+01:00)"
)


def utc_from_bst_hhmm(hhmm: str) -> datetime:
    local = datetime(2019, 8, 9, int(hhmm[:2]), int(hhmm[2:]), tzinfo=UTC)
    return local - BST


def iso_z(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%S.") + f"{when.microsecond // 1000:03d}Z"


def s08_rows() -> list[dict[str, Any]]:
    """GTR-FLEET-CONTROL rows; ``anchor`` is the S08 line prefix of the restated entry."""
    return [
        {
            "anchor": "G01  ",
            "entry_id": "S08-G01",
            "evidence_id": "S08",
            "room_id": ROOM_GTR,
            "recorded_time": "1653",
            "clock_basis": GTR_CLOCK,
            "index_time_utc": iso_z(utc_from_bst_hhmm("1653")),
            "index_uncertainty_s": 60.0,
            "from": None,
            "to": None,
            "channel": "fleet technical review entry",
            "value_status": "reported",
        }
    ]
