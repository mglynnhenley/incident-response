"""R05 landmark checks: digitised values against values stated in the report text.

Recomputed from the bundle CSVs alone (no PDFs). Agreements confirm the calibration; the source
conflicts that R05 documents must remain visible in the data, not be smoothed away.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ENV_ROOT = Path(__file__).resolve().parents[1]
DIGITISE_DIR = ENV_ROOT / "builder" / "system_response" / "digitise"
R05_DIR = (
    ENV_ROOT
    / "src"
    / "environment"
    / "incident"
    / "bundles"
    / "system_response"
    / "R05"
)
PROVENANCE = (
    ENV_ROOT
    / "src"
    / "environment"
    / "incident"
    / "private"
    / "system_response"
    / "provenance_R05.json"
)
sys.path.insert(0, str(DIGITISE_DIR))

import r05_checks as K  # noqa: E402


@pytest.fixture(scope="module")
def checks() -> dict[str, dict]:
    csvs = {fid: (R05_DIR / name).read_bytes() for fid, name in K.CSV_FILES.items()}
    return {c["check_id"]: c for c in K.run_checks(csvs)}


def test_provenance_records_the_same_checks(checks: dict[str, dict]) -> None:
    prov = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    recorded = {c["check_id"]: c for c in prov["validation"]["landmark_checks"]}
    assert recorded == checks


@pytest.mark.parametrize(
    ("check_id", "lo", "hi"),
    [
        ("F3-MW-pre", 789.0, 809.0),  # text: 799 MW
        ("E7-P-pre", 789.0, 809.0),  # ESO Table 1: 799 MW
        ("F3-MW-dip", 370.0, 430.0),  # text: "from 799MW to 400MW"
        ("F3-MW-post", 54.0, 70.0),  # text: 62 MW
        ("E7-P-post", 54.0, 70.0),  # ESO Table 1: stabilised at 62 MW
        ("F4-MW-pre", 395.0, 405.0),  # text: Hornsea 1B at 400 MW
        ("F4-MW-post", -8.0, 8.0),  # text: 1B and 1C WTGs reduce to 0 MW
        ("F4-kV-min", 19.0, 22.5),  # text: 34 kV system "falls to ~20kV"
        ("F4-kV-pre", 33.6, 34.6),  # text: target voltage 34 kV
        ("F3-V-pre", 398.0, 405.0),  # text: steady at ~400 kV
        ("F3-V-394", 390.0, 397.0),  # text: depressed to ~394 kV
    ],
)
def test_landmarks_agree_with_report_text(
    checks: dict[str, dict], check_id: str, lo: float, hi: float
) -> None:
    c = checks[check_id]
    assert lo <= c["digitised_value"] <= hi, c
    assert c["status"] == "consistent", c


def test_absorption_peak_is_of_the_reported_order(checks: dict[str, dict]) -> None:
    # text: "Hornsea now absorbs ~560MVAr"; the 20-ms chart and the finer ESO chart bracket it.
    assert -600 <= checks["F3-Q-min"]["digitised_value"] <= -450
    assert -820 <= checks["E8-Q-min"]["digitised_value"] <= -560


def test_pre_event_reactive_power_conflict_is_kept(checks: dict[str, dict]) -> None:
    for cid in ("F3-Q-pre", "E8-Q-pre"):
        c = checks[cid]
        assert -45 <= c["digitised_value"] <= -25, c  # charts: about -33 MVAr
        assert c["reference_value"] == 0.4 and c["status"].startswith("differs")


def test_voltage_onset_precedes_nget_inception(checks: dict[str, dict]) -> None:
    c = checks["E7-V-onset"]
    assert 33.460 <= c["digitised_value"] <= 33.482  # about 20 ms before 16:52:33.490
    assert -0.030 <= c["difference"] <= -0.008
    prov = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    sens = prov["validation"]["voltage_onset_threshold_sensitivity_s_after_1652"]
    assert max(sens.values()) < 33.490


def test_eso_fig7_and_fig8_voltage_agree() -> None:
    prov = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    cross = prov["validation"]["eso_fig7_vs_fig8_voltage"]
    assert cross["samples_compared"] > 250
    assert cross["rms_difference_kV_at_zero_lag"] < 0.5
    assert abs(cross["best_lag_ms"]) <= 5
