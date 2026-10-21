"""The system-response reference analyses (reference_analysis.py, reference_crosscheck.py).

Both are sent through ``run_python`` by the fake agent's reference scenario. Here they run
in a subprocess against the bundle's own files (the evidence directory has the same
layout), and their printed results must agree with the grader's frozen-R01 analysis and
with the numbers the reference submission states.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from functools import lru_cache

import pytest

from environment import fake_model
from environment.incident.frequency import load_series, reference_landmarks
from environment.incident.paths import SYSTEM_RESPONSE_BUNDLE_DIR

CSV = SYSTEM_RESPONSE_BUNDLE_DIR / "R01" / "frequency_2019-08-09_1640-1745_BST.csv"


def _run(path) -> str:
    env = {
        "EVIDENCE_DIR": str(SYSTEM_RESPONSE_BUNDLE_DIR),
        "PATH": os.environ.get("PATH", ""),
    }
    result = subprocess.run(
        [sys.executable, str(path)],
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
    return _run(fake_model.SR_REFERENCE_ANALYSIS)


@lru_cache(maxsize=1)
def crosscheck() -> str:
    return _run(fake_model.SR_REFERENCE_CROSSCHECK)


@lru_cache(maxsize=1)
def reference() -> dict:
    return json.loads(fake_model.SR_REFERENCE_SUBMISSION.read_text(encoding="utf-8"))


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
    assert (
        "first 2019-08-09T16:53:41+01:00 (row 822), last 2019-08-09T16:54:13+01:00 (row 854)"
        in out
    )
    assert "strictly increasing True; duplicates 0; steps other than 1 s 0" in out


def test_the_submission_cites_the_rows_the_analysis_prints():
    by = {f["finding_id"]: f for f in reference()["findings"]}
    out = analysis()
    for fid, row in (("F20", 780), ("F21", 830), ("F22", 1037)):
        locators = {c["locator"] for c in by[fid]["citations"]}
        assert f"row:{row}" in locators and f"(row {row})" in out


@pytest.mark.parametrize(
    "line",
    [
        "Hornsea One total: SP33 830.1 MW, SP34 640.1 MW, SP35 97.9 MW; SP33 - SP35 = 732.2 MW",
        "T_HOWAO-2: SP33 397.8 MW -> SP35 14.2 MW",
        "T_HOWAO-3: SP33 357.4 MW -> SP35 14.9 MW",
        "T_HOWAO-1: SP33 74.9 MW -> SP35 68.8 MW",
        "T_LBAR-1: SP33 663.4 MW -> SP35 -9.6 MW",
        "5-min demand summary: 29068 MW at 15:50Z, low 28230 MW at 2019-08-09T16:10:00Z, drop 838 MW",
        "S03 E5 ST generator breaker open feedback: T + 1.185 s = 2019-08-09T16:52:35.185+01:00 +/- 0.5 s",
        "S03 E7 GT1A breaker open feedback: T + 57.62 s = 2019-08-09T16:53:31.620+01:00 +/- 0.5 s",
        "S03 E9 GT1B breaker open feedback: T + 84.613 s = 2019-08-09T16:53:58.613+01:00 +/- 0.5 s",
        "GT1B breaker after GT1A breaker: 26.993 s",
        "S01 Hornsea de-load starts: 15:52:33.728Z = 2019-08-09T16:52:33.728+01:00",
        "Table 2 cumulative after RoCoF (est.): 1481 MW",
        "six-component sum 1878 MW (printed: 1,878 MW)",
        "Little Barford units: 641 MW (printed: 641 MW)",
    ],
)
def test_crosscheck_output(line):
    assert line in crosscheck()


def test_crosscheck_reads_the_mel_redeclaration_the_submission_cites():
    out = crosscheck()
    assert (
        "T_LBAR-1 2019-08-09T15:57:00Z 2019-08-09T15:58:00Z        664        0" in out
    )
    f93 = next(f for f in reference()["findings"] if f["finding_id"] == "F93")
    assert "from 664 MW to 0 between 15:57Z and 15:58Z" in f93["statement"]
    assert {
        "evidence_id": "R02",
        "locator": "event:R02-MELS-T_LBAR-1-20190809T1557Z",
    } in (f93["citations"])


def test_scripts_only_read_obtained_evidence():
    """The scripts read the R01 CSV (query_frequency) and R02/R07 files (requested in the
    reference scenario before the cross-check), nothing else."""
    for path, docs in (
        (fake_model.SR_REFERENCE_ANALYSIS, {"R01"}),
        (fake_model.SR_REFERENCE_CROSSCHECK, {"R02", "R07"}),
    ):
        code = path.read_text(encoding="utf-8")
        compile(code, str(path), "exec")
        assert set(re.findall(r'"(R0\d|S\d\d)"', code)) == docs, path.name
