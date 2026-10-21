"""Unit tests for the R05 digitisation primitives on synthetic charts (numpy only)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

DIGITISE_DIR = (
    Path(__file__).resolve().parents[1] / "builder" / "system_response" / "digitise"
)
sys.path.insert(0, str(DIGITISE_DIR))

import r05_core as C  # noqa: E402


def test_fit_linear_recovers_line_and_reports_residuals() -> None:
    px = [50.0, 133.0, 215.0, 297.0]
    vals = [420.0, 410.0, 400.0, 390.0]
    fit = C.fit_linear(px, vals)
    assert fit.slope < 0
    assert fit.value(50.0) == pytest.approx(420.0, abs=0.2)
    assert len(fit.residuals) == 4
    assert fit.rms == pytest.approx(float(np.sqrt(np.mean(np.square(fit.residuals)))))
    assert fit.pixel(fit.value(123.4)) == pytest.approx(123.4)
    d = fit.as_dict()
    assert d["n_ticks"] == 4 and len(d["ticks"]) == 4


def test_fit_linear_needs_three_ticks() -> None:
    with pytest.raises(ValueError):
        C.fit_linear([1.0, 2.0], [1.0, 2.0])


def _blank(h: int = 120, w: int = 200) -> np.ndarray:
    return np.full((h, w, 3), 255.0)


def test_gridlines_and_label_centres() -> None:
    img = _blank()
    for r in (20, 50, 80):
        img[r, 30:190] = 217.0
    # three dark "labels" left of the plot, centred on the gridlines
    for r in (20, 50, 80):
        img[r - 3 : r + 4, 5:15] = 40.0
    assert C.gridlines(img, "h", (0, 120), (30, 190)) == pytest.approx(
        [20.0, 50.0, 80.0]
    )
    found = C.label_centres(img, "v", (0, 25), (0, 120))
    assert [round((a + b) / 2) for _, a, b in found] == [20, 50, 80]


def test_components_rectangles_and_dilate() -> None:
    mask = np.zeros((60, 80), dtype=bool)
    mask[10, 10:50] = mask[30, 10:50] = True
    mask[10:31, 10] = mask[10:31, 49] = True
    mask[45:48, 60:63] = True
    comps = C.components(mask)
    assert len(comps) == 2
    assert C.rectangles(mask, min_w=30, min_h=15) == [(10, 10, 49, 30)]
    assert C.dilate(np.eye(5, dtype=bool), 1).sum() > 5


def _scene(img, xk, colours, widths, y_init, valid=None):
    series = [
        C.Series(f"s{i}", np.asarray(c, float), w, "left")
        for i, (c, w) in enumerate(zip(colours, widths))
    ]
    if valid is None:
        valid = np.ones(img.shape[:2], dtype=bool)
    return C.PolylineScene(
        img=img,
        background=np.full_like(img, 255.0),
        valid=valid,
        xk=np.asarray(xk, float),
        series=series,
        y=np.asarray(y_init, float).copy(),
        plot_rows=(0, img.shape[0]),
    )


def _synthetic(true_y, colours=((40, 110, 180), (255, 0, 0)), width=2.7, h=120, w=220):
    xk = np.linspace(15, 205, true_y.shape[1])
    truth = _scene(_blank(h, w), xk, colours, [width] * len(colours), true_y)
    img = np.round(C.render(truth))
    return img, xk


def test_polyline_fit_recovers_overlapping_series() -> None:
    true_y = np.array(
        [
            [60, 60, 60.4, 30.2, 90.6, 45.3, 61, 61],
            [62, 62, 61.7, 95.5, 25.1, 70.8, 62, 62],
        ]
    )
    img, xk = _synthetic(true_y)
    scene = _scene(
        img, xk, ((40, 110, 180), (255, 0, 0)), [2.7, 2.7], np.full_like(true_y, np.nan)
    )
    for s in range(2):
        C.init_from_evidence(scene, s)
    for _ in range(2):
        for s in (1, 0):
            C.dp_series(scene, s)
    C.refine(scene, sweeps=4, coarse=4.0)
    assert np.abs(scene.y - true_y).max() < 0.35


def test_profile_flags_vertex_hidden_by_annotation() -> None:
    true_y = np.array([[60, 60, 60, 60, 60, 60, 60, 60.0]])
    img, xk = _synthetic(true_y, colours=((0, 171, 68),))
    valid = np.ones(img.shape[:2], dtype=bool)
    c3, c5 = int(xk[2]) + 2, int(xk[5]) - 2
    valid[:, c3:c5] = False  # an opaque call-out box over vertices 3 and 4
    scene = _scene(img, xk, ((0, 171, 68),), [2.7], true_y, valid=valid)
    tau = C.shift_tau(scene.series[0].colour, 2.7, 2 * (xk[1] - xk[0]))
    visible_half, visible_hit = C.profile_halfwidth(scene, 0, 1, tau)
    hidden_half, hidden_hit = C.profile_halfwidth(scene, 0, 3, tau)
    assert not visible_hit and visible_half <= 1.0
    assert hidden_hit and hidden_half >= 11.0


def test_column_trace_and_block_profile_on_dense_trace() -> None:
    w = 160
    xs = np.arange(10, 150, dtype=float)
    true = 60 + 25 * np.sin((xs - 10) / 18.0)
    truth = _scene(_blank(120, w), xs, ((68, 114, 196),), [3.0], true[None])
    img = np.round(C.render(truth))
    alpha, resid = C.blend_alpha(img, np.array([68.0, 114.0, 196.0]))
    alpha = np.where(resid < 40, alpha, 0.0)
    tr = C.trace_columns(
        alpha, np.zeros(img.shape[:2], bool), (10, 150), (0, 120), 3.0, seed_row=60
    )
    filled = C.fill_gaps(tr, 10).centre
    assert np.nanmax(np.abs(filled - true)) < 3.0
    scene = _scene(img, xs, ((68, 114, 196),), [3.0], filled[None])
    C.refine(scene, sweeps=3, coarse=3.0)
    assert np.abs(scene.y[0] - true)[3:-3].max() < 0.6
    tau = C.shift_tau(scene.series[0].colour, 3.0, 5.0)
    half, hit = C.block_profile_halfwidth(scene, 0, 70, tau)
    assert not hit and half <= 1.5


def test_quadrature_and_resample() -> None:
    assert C.quadrature(3.0, 4.0) == pytest.approx(5.0)
    vals, near = C.resample(
        np.arange(10, 15),
        np.array([0.0, 1.0, 2.0, np.nan, 4.0]),
        np.array([10.5, 11.75, 12.5]),
    )
    assert vals[0] == pytest.approx(0.5) and vals[1] == pytest.approx(1.75)
    assert np.isnan(vals[2])
