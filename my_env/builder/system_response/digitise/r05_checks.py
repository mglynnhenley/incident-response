"""Landmark checks for R05: digitised values against values stated in the report text.

Pure standard library + numpy: works on the CSV bytes alone, so the tests can re-run every check
on the bundle files without PyMuPDF. A check never edits the data; a disagreement between a chart
and a text value is reported (and kept as a source conflict), not corrected.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import numpy as np

CSV_FILES = {
    "APP-p40-fig3": "app_p40_fig3_onshore.csv",
    "APP-p41-fig4": "app_p41_fig4_offshore_1b.csv",
    "ESO-p19-fig7": "eso_p19_fig7_voltage_active_power.csv",
    "ESO-p19-fig8": "eso_p19_fig8_reactive_power.csv",
}

F3 = "APP-p40-fig3/"
F4 = "APP-p41-fig4/"
E7 = "ESO-p19-fig7/"
E8 = "ESO-p19-fig8/"


def parse_csv(data: bytes) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in csv.DictReader(io.StringIO(data.decode("utf-8"))):
        rec = dict(row)
        rec["value"] = float(row["value"])
        rec["uncertainty"] = float(row["uncertainty"])
        rec["sample_index"] = int(row["sample_index"])
        rec["t"] = axis_seconds(row["time_as_printed"])
        out.setdefault(row["series_id"], []).append(rec)
    return out


def axis_seconds(label: str) -> float:
    """Seconds after 16:52:00 for 'hh:mm:ss.fff' or 'mm:ss.f' as printed."""
    parts = label.split(":")
    if len(parts) == 3:
        return (int(parts[0]) - 16) * 3600 + (int(parts[1]) - 52) * 60 + float(parts[2])
    return (int(parts[0]) - 52) * 60 + float(parts[1])


def _sel(rows, k0=None, k1=None, t0=None, t1=None):
    out = []
    for r in rows:
        if k0 is not None and not (k0 <= r["sample_index"] <= k1):
            continue
        if t0 is not None and not (t0 <= r["t"] < t1):
            continue
        out.append(r)
    return out


def _level(rows) -> tuple[float, float, list[dict[str, Any]]]:
    vals = np.array([r["value"] for r in rows])
    unc = float(np.median([r["uncertainty"] for r in rows]))
    return float(np.median(vals)), unc, rows


def _extreme(rows, fn) -> tuple[float, float, list[dict[str, Any]]]:
    r = fn(rows, key=lambda x: (x["value"], x["sample_index"]))
    return r["value"], r["uncertainty"], [r]


def _check(
    cid: str,
    what: str,
    series: str,
    measured: tuple[float, float, list[dict[str, Any]]],
    reference: float | None,
    tolerance: float | None,
    ref_text: str,
    ref_source: dict[str, Any],
    kind: str = "compare",
) -> dict[str, Any]:
    value, unc, rows = measured
    if ".." in series and len(rows) == 1:
        series = rows[0][
            "series_id"
        ]  # an extreme over several traces: name the one it came from
    rec: dict[str, Any] = {
        "check_id": cid,
        "what": what,
        "series_id": series,
        "unit": rows[0]["unit"],
        "digitised_value": round(value, 2),
        "digitised_uncertainty": round(unc, 2),
        "samples": [r["sample_index"] for r in rows],
        "times_as_printed": [rows[0]["time_as_printed"], rows[-1]["time_as_printed"]],
        "reference_text": ref_text,
        "reference_source": ref_source,
        "reference_value": reference,
        "tolerance": tolerance,
    }
    if reference is not None and tolerance is not None:
        diff = value - reference
        rec["difference"] = round(diff, 2)
        rec["status"] = (
            "consistent"
            if abs(diff) <= tolerance + unc
            else "differs (kept as a source conflict)"
        )
    else:
        rec["status"] = kind
    return rec


def _src(source_id: str, page: int, quote: str) -> dict[str, Any]:
    return {"source_id": source_id, "pdf_page": page, "quote": quote}


def onset_time(
    rows: list[dict[str, Any]], drop: float = 1.0, hold: int = 3
) -> dict[str, float]:
    """First time the voltage leaves its pre-event level by more than ``drop`` kV.

    Pre-event level: median before 16:52:33.40 (axis reading). The onset is the linearly
    interpolated crossing of (level - drop) at the start of the first run of ``hold`` samples
    below it.
    """
    pre = [r["value"] for r in rows if r["t"] < 33.40]
    level = float(np.median(pre))
    thr = level - drop
    for i in range(1, len(rows) - hold):
        if (
            all(rows[j]["value"] < thr for j in range(i, i + hold))
            and rows[i - 1]["value"] >= thr
        ):
            a, b = rows[i - 1], rows[i]
            f = (a["value"] - thr) / (a["value"] - b["value"])
            return {
                "level_kV": level,
                "threshold_kV": thr,
                "t": a["t"] + f * (b["t"] - a["t"]),
            }
    raise ValueError("no onset found")


def run_checks(csvs: dict[str, bytes]) -> list[dict[str, Any]]:
    """All landmark checks; ``csvs`` maps figure_id -> CSV bytes."""
    f3 = parse_csv(csvs["APP-p40-fig3"])
    f4 = parse_csv(csvs["APP-p41-fig4"])
    e7 = parse_csv(csvs["ESO-p19-fig7"])
    e8 = parse_csv(csvs["ESO-p19-fig8"])
    p40 = "Figure 3 (above) shows NETS voltage in the 400kV substation initially steady at ~400kV"
    p41_799 = (
        "Hornsea reduces active power from 799MW to 400MW before returning to 799MW"
    )
    p41_560 = "Hornsea now absorbs ~560MVAr"
    p41_62 = "Hornsea 1A remained in operation at 62MW active power output"
    p41_394 = "voltage to ~394kV) and then injecting MVArs again"
    p41_1b = "Prior to the event, Hornsea 1B is operating at 400MW"
    p41_20 = "Hornsea 1B system voltage falls to ~20kV"
    p41_0 = "all WTGs on Hornsea 1B and Hornsea 1C reduce to 0MW"
    p41_34 = "target voltage 34kV"
    eso_t1 = "Hornsea was generating 799MW and absorbing 0.4MVAR"
    eso_t1_21 = "Hornsea stabilised at 62MW and injecting 21 MVAR"
    eso_fault = "16:52:33.490"
    checks: list[dict[str, Any]] = []
    mw = f3[F3 + "HOW_active_MW"]
    q3 = f3[F3 + "HOW_reactive_MVAr"]
    checks.append(
        _check(
            "F3-MW-pre",
            "Fig 3 active power, level before the disturbance (samples 0-22)",
            F3 + "HOW_active_MW",
            _level(_sel(mw, 0, 22)),
            799.0,
            10.0,
            p41_799,
            _src("APP", 41, p41_799),
        )
    )
    checks.append(
        _check(
            "F3-MW-dip",
            "Fig 3 active power, lowest value during the oscillation (samples 23-35)",
            F3 + "HOW_active_MW",
            _extreme(_sel(mw, 23, 35), min),
            400.0,
            30.0,
            p41_799,
            _src("APP", 41, p41_799),
        )
    )
    checks.append(
        _check(
            "F3-MW-post",
            "Fig 3 active power, level after the de-load (samples 45-69)",
            F3 + "HOW_active_MW",
            _level(_sel(mw, 45, 69)),
            62.0,
            8.0,
            p41_62,
            _src("APP", 41, p41_62),
        )
    )
    checks.append(
        _check(
            "F3-Q-pre",
            "Fig 3 reactive power before the disturbance (visible samples 0-22)",
            F3 + "HOW_reactive_MVAr",
            _level(_sel(q3, 0, 22)),
            0.4,
            10.0,
            eso_t1,
            _src("ESO", 12, eso_t1),
        )
    )
    checks.append(
        _check(
            "F3-Q-min",
            "Fig 3 reactive power, most negative value (samples 23-45)",
            F3 + "HOW_reactive_MVAr",
            _extreme(_sel(q3, 23, 45), min),
            -560.0,
            40.0,
            p41_560,
            _src("APP", 41, p41_560),
        )
    )
    vpre = [_level(_sel(f3[F3 + f"HOW_V{i}"], 0, 22)) for i in (1, 2, 3)]
    checks.append(
        _check(
            "F3-V-pre",
            "Fig 3 onshore voltage before the disturbance (mean of the three traces' medians)",
            F3 + "HOW_V1..V3",
            (float(np.mean([v[0] for v in vpre])), max(v[1] for v in vpre), vpre[0][2]),
            400.0,
            5.0,
            p40,
            _src("APP", 40, p40),
        )
    )
    late = [r for i in (1, 2, 3) for r in _sel(f3[F3 + f"HOW_V{i}"], 35, 38)]
    checks.append(
        _check(
            "F3-V-394",
            "Fig 3 lowest onshore voltage while reactive power is most negative (samples 35-38)",
            F3 + "HOW_V1..V3",
            _extreme(late, min),
            394.0,
            3.0,
            p41_394,
            _src("APP", 41, p41_394),
        )
    )
    mwo = f4[F4 + "MW_OFS"]
    checks.append(
        _check(
            "F4-MW-pre",
            "Fig 4 MW_OFS before the disturbance (samples 0-25)",
            F4 + "MW_OFS",
            _level(_sel(mwo, 0, 25)),
            400.0,
            5.0,
            p41_1b,
            _src("APP", 41, p41_1b),
        )
    )
    checks.append(
        _check(
            "F4-MW-post",
            "Fig 4 MW_OFS after the de-load (samples 65-78)",
            F4 + "MW_OFS",
            _level(_sel(mwo, 65, 78)),
            0.0,
            8.0,
            p41_0,
            _src("APP", 41, p41_0),
        )
    )
    kv_all = [r for i in (1, 2, 3, 4) for r in f4[F4 + f"kV_PPM{i}_AVE"]]
    checks.append(
        _check(
            "F4-kV-min",
            "Fig 4 lowest 34 kV collection-system voltage over the four PPMs",
            F4 + "kV_PPM1..4_AVE",
            _extreme(kv_all, min),
            20.0,
            2.5,
            p41_20,
            _src("APP", 41, p41_20),
        )
    )
    kv_pre = [_level(_sel(f4[F4 + f"kV_PPM{i}_AVE"], 0, 25)) for i in (1, 2, 3, 4)]
    checks.append(
        _check(
            "F4-kV-pre",
            "Fig 4 collection-system voltage before the disturbance (mean of PPM medians)",
            F4 + "kV_PPM1..4_AVE",
            (
                float(np.mean([v[0] for v in kv_pre])),
                max(v[1] for v in kv_pre),
                kv_pre[0][2],
            ),
            34.0,
            0.6,
            p41_34,
            _src("APP", 41, p41_34),
        )
    )
    p7 = e7[E7 + "Total_Active_Power"]
    v7 = e7[E7 + "Hornsea_Voltage"]
    checks.append(
        _check(
            "E7-P-pre",
            "ESO Fig 7 active power before 16:52:33.40 (axis reading)",
            E7 + "Total_Active_Power",
            _level(_sel(p7, t0=33.0, t1=33.40)),
            799.0,
            10.0,
            eso_t1,
            _src("ESO", 12, eso_t1),
        )
    )
    checks.append(
        _check(
            "E7-P-post",
            "ESO Fig 7 active power after 16:52:34.00 (axis reading)",
            E7 + "Total_Active_Power",
            _level(_sel(p7, t0=34.0, t1=35.0)),
            62.0,
            8.0,
            eso_t1_21,
            _src("ESO", 12, eso_t1_21),
        )
    )
    on = onset_time(v7)
    checks.append(
        {
            "check_id": "E7-V-onset",
            "what": "ESO Fig 7 voltage: first departure of more than 1 kV below its pre-event level",
            "series_id": E7 + "Hornsea_Voltage",
            "unit": "s after 16:52:00 (as printed)",
            "digitised_value": round(on["t"], 4),
            "threshold_kV": round(on["threshold_kV"], 2),
            "digitised_value_as_printed": f"16:52:{on['t']:06.3f}",
            "pre_event_level_kV": round(on["level_kV"], 2),
            "reference_text": eso_fault
            + " single (blue) phase to earth fault (ESO Table 1, source NGET)",
            "reference_source": _src(
                "ESO", 12, "A single (blue) Phase to Earth fault on Eaton Socon"
            ),
            "reference_value": 33.490,
            "difference": round(on["t"] - 33.490, 4),
            "tolerance": None,
            "status": "differs (kept as a source conflict): the chart's voltage falls before the "
            "fault inception time in the ESO timeline",
        }
    )
    q8 = e8[E8 + "Total_Reactive_Power"]
    checks.append(
        _check(
            "E8-Q-pre",
            "ESO Fig 8 reactive power before 16:52:33.40 (axis reading)",
            E8 + "Total_Reactive_Power",
            _level(_sel(q8, t0=33.0, t1=33.40)),
            0.4,
            10.0,
            eso_t1,
            _src("ESO", 12, eso_t1),
        )
    )
    checks.append(
        _check(
            "E8-Q-min",
            "ESO Fig 8 reactive power, most negative value",
            E8 + "Total_Reactive_Power",
            _extreme(q8, min),
            -560.0,
            40.0,
            p41_560,
            _src("APP", 41, p41_560),
        )
    )
    checks.append(
        _check(
            "E8-Q-post",
            "ESO Fig 8 reactive power after 16:52:34.20 (axis reading)",
            E8 + "Total_Reactive_Power",
            _level(_sel(q8, t0=34.2, t1=35.0)),
            21.0,
            10.0,
            eso_t1_21,
            _src("ESO", 12, eso_t1_21),
        )
    )
    return checks


def voltage_cross_check(
    fig7_voltage: list[dict[str, Any]], fig8_voltage: list[dict[str, Any]]
) -> dict[str, Any]:
    """ESO Fig 7 vs Fig 8 voltage (same quantity): RMS difference and best time lag."""
    a = {round(p["t"], 3): p["value"] for p in fig7_voltage}
    b = {round(p["t"], 3): p["value"] for p in fig8_voltage}
    best = None
    for lag_ms in range(-15, 16, 5):
        common = [t for t in a if round(t + lag_ms / 1000, 3) in b]
        d = np.array([a[t] - b[round(t + lag_ms / 1000, 3)] for t in common])
        rms = float(np.sqrt((d**2).mean()))
        if best is None or rms < best[1]:
            best = (lag_ms, rms, len(common))
    common = [t for t in a if t in b]
    d0 = np.array([a[t] - b[t] for t in common])
    return {
        "samples_compared": len(common),
        "rms_difference_kV_at_zero_lag": round(float(np.sqrt((d0**2).mean())), 3),
        "max_abs_difference_kV_at_zero_lag": round(float(np.abs(d0).max()), 3),
        "best_lag_ms": best[0],
        "rms_difference_kV_at_best_lag": round(best[1], 3),
    }
