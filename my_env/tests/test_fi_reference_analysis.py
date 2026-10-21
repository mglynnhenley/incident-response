"""The full-investigation reference analyses (reference_analysis.py, reference_crosscheck.py).

Both are sent through ``run_python`` by the fake agent's reference scenario (without
their module docstrings). Here they run in a subprocess against the bundle's own files
(the evidence directory has the same layout), and their printed results must agree with
the grader's frozen-R01 analysis, with the bundle's records and with the numbers the
reference submission states.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import lru_cache

from environment import fake_model_fi
from environment.incident.frequency import load_series, reference_landmarks
from environment.incident.paths import FULL_INVESTIGATION_BUNDLE_DIR

BUNDLE = FULL_INVESTIGATION_BUNDLE_DIR
CSV = BUNDLE / "R01" / "frequency_2019-08-09_1640-1745_BST.csv"


def _run(code: str) -> str:
    env = {"EVIDENCE_DIR": str(BUNDLE), "PATH": os.environ.get("PATH", "")}
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@lru_cache(maxsize=1)
def analysis() -> str:
    return _run(fake_model_fi.fi_reference_analysis_code())


@lru_cache(maxsize=1)
def crosscheck() -> str:
    return _run(fake_model_fi.fi_reference_crosscheck_code())


@lru_cache(maxsize=1)
def findings() -> dict[str, dict]:
    sub = json.loads(fake_model_fi.FI_REFERENCE_SUBMISSION.read_text(encoding="utf-8"))
    return {f["finding_id"]: f for f in sub["findings"]}


def test_analysis_reproduces_the_grader_landmarks():
    out = analysis()
    lm = reference_landmarks(load_series(CSV))
    for name, row in (
        ("first_local_minimum", 780),
        ("event_minimum", 830),
        ("first_at_or_above_50_after_minimum", 1037),
    ):
        value, time = lm[name]["value_hz"], lm[name]["time"]
        assert f"{value:.3f} Hz at {time} (row {row})" in out
    assert (
        "time below 49 Hz (zero-order hold, 1-s samples): 33 s; missing data in window: 0 s"
        in out
    )
    assert "time at or below 49 Hz (zero-order hold): 34 s" in out
    assert "time below 49 Hz (linear interpolation between samples): 33.964 s" in out
    assert "strictly increasing True; duplicates 0; steps other than 1 s 0" in out


def test_analysis_brackets_the_49_hz_crossing_for_the_rail_finding():
    out = analysis()
    line = (
        "first fall below 49 Hz lies between 16:53:40 (49.000 Hz, row 821) and "
        "16:53:41 (48.983 Hz, row 822); a 200 ms response cannot be resolved from 1-s "
        "samples"
    )
    assert line in out
    f100 = findings()["F100"]
    assert {"evidence_id": "R01", "locator": "rows:821-822"} in f100["citations"]
    assert "between 16:53:40 and 16:53:41 BST" in f100["statement"]


def test_crosscheck_sums_eso_table_2():
    out = crosscheck()
    assert (
        "components 244 + 737 + 150 + 350 + 210 + 187 = 1878 MW; printed cumulative "
        "1878 MW; running sums match the cumulative column: True" in out
    )
    assert "cumulative after the RoCoF trips (fourth row): 1481 MW" in out
    assert "1,878 MW" in findings()["F17"]["statement"]


def test_crosscheck_sums_orr_table_1_and_the_lock_out_counts():
    out = crosscheck()
    assert (
        "8 routes sum to 371 cancelled, 220 part-cancelled, 14428 delay minutes; "
        "printed TOTAL 371 | 220 | 14428; match: True" in out
    )
    assert (
        "technician 22 + driver 7 = 29 (locked out 29); locked out 29 + 2 Class 387 = "
        "31 (stranded 31); detrained from 30 trains" in out
    )
    assert "29 + 2 = 31" in findings()["F103"]["derivation"]


def test_crosscheck_sums_the_lfdd_tables():
    out = crosscheck()
    assert "14 areas sum to 931 MW" in out and "14 areas sum to 973 MW" in out
    assert "difference 42 MW" in out
    assert (
        "differs: Western Power Distribution (WPD) West Midlands: ESO 160 MW, E3C 190 MW"
        in out
    )
    assert (
        "differs: Western Power Distribution (WPD) South West: ESO not given, E3C 12 MW"
        in out
    )


def test_crosscheck_converts_the_little_barford_datum_and_utc_times():
    out = crosscheck()
    for line in (
        "E5 ST generator breaker open feedback: T + 1.185 s = 16:52:35.185 BST",
        "E7 GT1A breaker open feedback: T + 57.620 s = 16:53:31.620 BST",
        "E9 GT1B breaker open feedback: T + 84.613 s = 16:53:58.613 BST",
        "2019-08-09T15:52:33.728+00:00 = 2019-08-09T16:52:33.728000+01:00",
        "2019-08-09T17:27:46.703+00:00 = 2019-08-09T18:27:46.703000+01:00",
        "2019-08-09T16:54:44+00:00 = 2019-08-09T17:54:44+01:00",
    ):
        assert line in out, line
    by = findings()
    assert by["F11"]["event_time"] == "2019-08-09T16:52:35.185+01:00"
    assert "18:27:46 BST" in by["F152"]["statement"]
    assert "17:54:44 BST" in by["F156"]["statement"]


def test_the_transcribed_utc_times_are_the_rows_the_tools_return():
    """The two UTC times the cross-check types in come from log rows (which write no
    files): the ESO-COMMS row R09-E13 and the REMIT row R09-REMIT-00056773-r1."""
    rows = {}
    for path in (BUNDLE / "logs").rglob("*.jsonl"):
        for line in path.read_text("utf-8").splitlines():
            r = json.loads(line)
            rows[r.get("event_id") or r.get("entry_id")] = r
    assert "17:27:46.703Z" in rows["R09-E13"]["recorded_time"]
    assert rows["R09-REMIT-00056773-r1"]["recorded_time"] == (
        "publishTime 2019-08-09T16:54:44Z"
    )
    code = fake_model_fi.fi_reference_crosscheck_code()
    assert "2019-08-09T17:27:46.703+00:00" in code
    assert "2019-08-09T16:54:44+00:00" in code
