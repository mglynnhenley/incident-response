"""Reference R01 analysis (environment.incident.frequency) and reference_analysis.py."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from environment.incident import frequency as fq
from environment.incident.paths import DEFAULT_BUNDLE_DIR

ENV_ROOT = Path(__file__).resolve().parents[1]
CSV_NAME = "frequency_2019-08-09_1640-1745_BST.csv"
BUNDLE_CSV = DEFAULT_BUNDLE_DIR / "R01" / CSV_NAME
HANDOFF_DIR = Path(
    os.environ.get(
        "GB_HANDOFF_DIR",
        str(ENV_ROOT.parent / ".context" / "handoff" / "GB_power_cut_handoff"),
    )
)
HANDOFF_CHECKS = HANDOFF_DIR / "verification" / "frequency_checks.json"
REFERENCE_ANALYSIS = (
    ENV_ROOT
    / "src/environment/tasks/gb_2019_electrical_disturbance/reference/reference_analysis.py"
)
NESO_ZIP_SHA256 = "bce1b0d8bbbbbbaa1d8574a43b0352559e0290102bc6787eff0af53d02811d86"

# The handoff's verification/frequency_checks.json (copied here so the test also runs
# where the builder-only handoff is absent).
EXPECTED_CHECKS = {
    "source_sha256": NESO_ZIP_SHA256,
    "rows": 3900,
    "interval": "[16:40:00,17:45:00) BST",
    "missing_seconds": 0,
    "first_nadir": ["2019-08-09T16:52:59+01:00", 49.083],
    "second_nadir": ["2019-08-09T16:53:49+01:00", 48.787],
    "return_ge_50": ["2019-08-09T16:57:16+01:00", 50.001],
    "below_49_seconds_zero_order_hold": 33,
    "below_49_first_sample": "2019-08-09T16:53:41+01:00",
    "below_49_last_sample": "2019-08-09T16:54:13+01:00",
    "timezone": "Parsed explicit +0100 offsets; UTC is local time minus one hour. Report "
    "event alignment checked; no publisher clarification obtained.",
}


@pytest.fixture(scope="module")
def samples() -> list[fq.Sample]:
    return fq.load_series(BUNDLE_CSV)


def test_bundle_csv_reproduces_handoff_checks_exactly(samples):
    checks = fq.handoff_checks(samples, source_sha256=NESO_ZIP_SHA256)
    assert checks == EXPECTED_CHECKS
    if HANDOFF_CHECKS.exists():
        handoff = json.loads(HANDOFF_CHECKS.read_text(encoding="utf-8"))
        assert (
            fq.handoff_checks(samples, source_sha256=handoff["source_sha256"])
            == handoff
        )
        # byte-level: the same JSON text as the handoff file
        assert json.dumps(checks, indent=2) == HANDOFF_CHECKS.read_text(
            encoding="utf-8"
        )


def test_series_checks(samples):
    check = fq.check_series(samples)
    assert check.ok
    assert check.rows == 3900 and check.missing_seconds == 0
    assert check.offsets == ["+01:00"]
    assert check.first.isoformat() == "2019-08-09T16:40:00+01:00"
    assert check.last.isoformat() == "2019-08-09T17:44:59+01:00"


def test_reference_landmarks(samples):
    lm = fq.reference_landmarks(samples)
    assert lm["first_local_minimum"]["value_hz"] == 49.083
    assert lm["first_local_minimum"]["time"] == "2019-08-09T16:52:59+01:00"
    assert lm["first_local_minimum"]["row"] == 780
    assert lm["first_local_minimum"]["is_local_minimum"]
    assert lm["event_minimum"]["value_hz"] == 48.787
    assert lm["event_minimum"]["time"] == "2019-08-09T16:53:49+01:00"
    assert lm["event_minimum"]["row"] == 830
    assert lm["first_at_or_above_50_after_minimum"]["value_hz"] == 50.001
    assert (
        lm["first_at_or_above_50_after_minimum"]["time"] == "2019-08-09T16:57:16+01:00"
    )
    below = lm["below_49"]
    assert below["covered_below_s"] == 33.0 and below["missing_s"] == 0.0
    assert below["samples_below"] == 33
    assert below["first_below"] == ["2019-08-09T16:53:41+01:00", 48.983]
    assert below["last_below"] == ["2019-08-09T16:54:13+01:00", 48.973]
    assert len(below["runs"]) == 1


def test_threshold_is_strictly_below(samples):
    at_40 = next(s for s in samples if s.time == fq.bst("16:53:40"))
    assert at_40.value == 49.0  # exactly at the threshold: not below
    result = fq.duration_below(
        samples, 49.0, start=fq.bst("16:53:40"), end=fq.bst("16:53:42")
    )
    assert result.covered_below_s == 1.0 and result.samples_below == 1


def _series(rows: list[tuple[str, float]]) -> list[fq.Sample]:
    text = "timestamp,frequency_hz\r\n" + "".join(
        f"2019-08-09T{t}+01:00,{v}\r\n" for t, v in rows
    )
    return fq.parse_series(text)


def test_zero_order_hold_does_not_bridge_gaps():
    samples = _series(
        [
            ("16:00:00", 49.5),
            ("16:00:01", 48.9),
            ("16:00:02", 48.9),
            # 16:00:03 .. 16:00:05 missing
            ("16:00:06", 48.8),
            ("16:00:07", 49.2),
        ]
    )
    check = fq.check_series(samples)
    assert not check.ok and check.missing_seconds == 3
    assert check.gaps[0]["step_s"] == 4.0
    result = fq.duration_below(
        samples, 49.0, start=fq.bst("16:00:00"), end=fq.bst("16:00:08")
    )
    # 16:00:01 (1 s) + 16:00:02 (held 1 s only, gap not bridged) + 16:00:06 (1 s)
    assert result.covered_below_s == 3.0
    assert result.missing_s == 3.0
    assert result.covered_s == 5.0
    assert [r["duration_s"] for r in result.runs] == [2.0, 1.0]


def test_window_clipping_and_missing_edges():
    samples = _series([("16:00:00", 48.0), ("16:00:01", 48.0)])
    result = fq.duration_below(
        samples, 49.0, start=fq.bst("15:59:58"), end=fq.bst("16:00:01.500")
    )
    assert result.covered_below_s == 1.5
    assert result.missing_s == 2.0


def test_duplicates_and_disorder_detected():
    dup = _series([("16:00:00", 50.0), ("16:00:00", 50.0), ("16:00:01", 50.0)])
    assert fq.check_series(dup).duplicates == ["2019-08-09T16:00:00+01:00"]
    back = _series([("16:00:01", 50.0), ("16:00:00", 50.0)])
    assert not fq.check_series(back).strictly_increasing


def test_naive_timestamps_rejected():
    with pytest.raises(fq.FrequencyError, match="explicit UTC offset"):
        fq.parse_series("timestamp,frequency_hz\n2019-08-09T16:00:00,50.0\n")


def test_offsets_compared_as_instants():
    samples = fq.parse_series(
        "timestamp,frequency_hz\n2019-08-09T15:00:00Z,49.0\n2019-08-09T16:00:01+01:00,48.0\n"
    )
    assert fq.check_series(samples).ok
    assert (
        fq.window_minimum(samples, fq.bst("16:00:00"), fq.bst("16:00:02")).value == 48.0
    )


def test_reference_analysis_script_prints_landmarks(tmp_path: Path):
    evidence = tmp_path / "evidence" / "R01"
    evidence.mkdir(parents=True)
    shutil.copy(BUNDLE_CSV, evidence / CSV_NAME)
    out = subprocess.run(
        [sys.executable, str(REFERENCE_ANALYSIS)],
        env={"EVIDENCE_DIR": str(tmp_path / "evidence"), "PATH": os.environ["PATH"]},
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    ).stdout
    assert "49.083 Hz at 2019-08-09T16:52:59+01:00" in out
    assert "48.787 Hz at 2019-08-09T16:53:49+01:00" in out
    assert "50.001 Hz at 2019-08-09T16:57:16+01:00" in out
    assert "time below 49 Hz (zero-order hold, 1-s samples): 33 s" in out
    assert "missing data in window: 0 s" in out
    assert "steps other than 1 s 0" in out and "duplicates 0" in out


def test_bst_helper():
    assert fq.bst("16:52:33.490").isoformat() == "2019-08-09T16:52:33.490000+01:00"
    assert fq.bst("16:52:33") - fq.bst("16:52:32") == timedelta(seconds=1)
