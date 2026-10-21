"""Build R05: Hornsea One voltage/power traces digitised from four published charts.

Builder-only. Reads the handoff PDFs (``GB_HANDOFF_DIR``) and the source-catalogue category
labels (``GB_CATALOGUE_DIR``), extracts the embedded chart rasters losslessly with PyMuPDF,
calibrates every axis from its printed ticks, fits each plotted line by re-drawing the chart
(analysis by synthesis) and writes:

* ``src/environment/incident/bundles/system_response/R05/`` — ``R05.txt`` (method note), one CSV
  per figure and ``calibration.json`` (agent-visible);
* ``src/environment/incident/private/system_response/provenance_R05.json`` (private);
* ``builder/system_response/rows/r05_hornsea_traces.jsonl`` (asset-row fragment);
* ``builder/system_response/digitise/r05_manifest_fragment.json`` (for the integration step);
* QA overlays in ``GB_DIGITISE_QA_DIR`` (default ``<workspace>/.context/digitise_qa``).

Deterministic: the same inputs give byte-identical outputs (QA images excepted).

    uv run --no-project --with pymupdf --with numpy --with pillow \
        python builder/system_response/digitise/build_r05.py [--check] [--no-qa]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import r05_core as C  # noqa: E402
import r05_text  # noqa: E402
from r05_figures import DATE, FIGURES, SOURCES  # noqa: E402

ENV_ROOT = HERE.parents[2]
WORKSPACE = ENV_ROOT.parent
SCRIPT = "builder/system_response/digitise/build_r05.py"
BUILDER_VERSION = "1.0.0"


def _env_dir(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default)))


HANDOFF_DIR = _env_dir(
    "GB_HANDOFF_DIR", WORKSPACE / ".context" / "handoff" / "GB_power_cut_handoff"
)
CATALOGUE_DIR = _env_dir(
    "GB_CATALOGUE_DIR", WORKSPACE / ".context" / "source_catalogue"
)
QA_DIR = _env_dir("GB_DIGITISE_QA_DIR", WORKSPACE / ".context" / "digitise_qa")

BUNDLE_DIR = (
    ENV_ROOT / "src" / "environment" / "incident" / "bundles" / "system_response"
)
R05_DIR = BUNDLE_DIR / "R05"
PROVENANCE_PATH = (
    ENV_ROOT
    / "src"
    / "environment"
    / "incident"
    / "private"
    / "system_response"
    / "provenance_R05.json"
)
ROWS_PATH = (
    ENV_ROOT / "builder" / "system_response" / "rows" / "r05_hornsea_traces.jsonl"
)
MANIFEST_FRAGMENT_PATH = HERE / "r05_manifest_fragment.json"

CSV_COLUMNS = [
    "time_as_printed",
    "time_bst_iso",
    "value",
    "unit",
    "uncertainty",
    "series_id",
    "sample_index",
    "time_uncertainty_s",
    "flags",
]
DECIMALS = {"kV": 2, "MW": 1, "MVAr": 1}
REACH_PX = (
    12.0  # profile search half-range; reaching it means the vertex is unconstrained
)
AMBIGUOUS_PX = 3.0  # profile half-width above which a vertex is flagged ambiguous


# ============================================================================================
# Inputs
# ============================================================================================


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def handoff_sources() -> dict[str, dict[str, Any]]:
    """Source PDFs from the handoff manifest, sha256-verified."""
    manifest = json.loads(
        (HANDOFF_DIR / "source_manifest.json").read_text(encoding="utf-8")
    )
    by_id = {m["id"]: m for m in manifest}
    out = {}
    for sid, rel in SOURCES.items():
        entry = by_id[sid]
        if entry["file"] != rel:
            raise SystemExit(f"source {sid}: manifest file {entry['file']} != {rel}")
        digest = sha256_file(HANDOFF_DIR / rel)
        if digest != entry["sha256"]:
            raise SystemExit(f"source {sid}: sha256 mismatch ({digest})")
        out[sid] = {
            "file": rel,
            "sha256": digest,
            "url": entry["url"],
            "retrieved_date_utc": entry.get("retrieved_date_utc"),
        }
    return out


def extract_image(fig: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    """Native chart raster (alpha composited on white) plus a page-render cross-check."""
    import pymupdf

    doc = pymupdf.open(HANDOFF_DIR / SOURCES[fig["source_id"]])
    page = doc[fig["pdf_page"] - 1]
    xrefs = [info[0] for info in page.get_images(full=True)]
    if fig["xref"] not in xrefs:
        raise SystemExit(
            f"{fig['figure_id']}: xref {fig['xref']} not on page {fig['pdf_page']}"
        )
    pix = pymupdf.Pixmap(doc, fig["xref"])
    raw = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )
    if [pix.width, pix.height] != fig["native_px"]:
        raise SystemExit(f"{fig['figure_id']}: native size {pix.width}x{pix.height}")
    rgb = raw[..., :3].astype(float)
    if pix.alpha:
        a = raw[..., 3:4].astype(float) / 255.0
        rgb = np.round(rgb * a + 255.0 * (1.0 - a))
    rect = page.get_image_rects(fig["xref"])[0]
    # Render the same page region with MuPDF at the raster's own resolution and compare: this
    # checks that nothing on the page (clip paths, vector drawings) changes what the chart shows.
    zx = pix.width / rect.width
    zy = pix.height / rect.height
    rend = page.get_pixmap(matrix=pymupdf.Matrix(zx, zy), clip=rect, alpha=False)
    ra = np.frombuffer(rend.samples, dtype=np.uint8).reshape(
        rend.height, rend.width, rend.n
    )
    h = min(ra.shape[0], rgb.shape[0])
    w = min(ra.shape[1], rgb.shape[1])
    diff = np.abs(ra[:h, :w, :3].astype(float) - rgb[:h, :w])
    big = float((diff.max(axis=2) > 96).mean())
    # The same region rendered at 600 dpi (saved for QA only).
    hi = page.get_pixmap(
        matrix=pymupdf.Matrix(600 / 72, 600 / 72), clip=rect, alpha=False
    )
    info = {
        "pdf_page": fig["pdf_page"],
        "xref": fig["xref"],
        "page_bbox_pt": [round(v, 2) for v in (rect.x0, rect.y0, rect.x1, rect.y1)],
        "native_px": [pix.width, pix.height],
        "native_dpi": round(pix.width / rect.width * 72, 1),
        "decoded_pixels_sha256": sha256_bytes(pix.samples),
        "render_check": {
            "method": "page region rendered by MuPDF at the raster's native resolution and "
            "compared with the decoded raster",
            "rendered_px": [rend.width, rend.height],
            "mean_abs_diff": round(float(diff.mean()), 2),
            "fraction_pixels_diff_gt_96": round(big, 5),
        },
    }
    if big > 0.02:
        raise SystemExit(
            f"{fig['figure_id']}: page render differs from the raster ({big:.3f})"
        )
    return rgb, {"info": info, "render_600dpi": hi}


def category_labels(fig: dict[str, Any]) -> tuple[list[str], str]:
    path = CATALOGUE_DIR / fig["x_axis"]["timebase_csv"]
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))
    labels = [r["label_as_printed"].strip() for r in rows]
    if [int(r["k"]) for r in rows] != list(range(len(rows))):
        raise SystemExit(f"{path}: k column is not 0..n-1")
    pat = re.compile(fig["x_axis"]["label_pattern"])
    bad = [lab for lab in labels if not pat.match(lab)]
    if bad or len(labels) != fig["x_axis"]["n_categories"]:
        raise SystemExit(f"{path}: unexpected labels {bad[:3]} / count {len(labels)}")
    return labels, sha256_file(path)


# ============================================================================================
# Calibration
# ============================================================================================


def _bbox_centres(found: list[tuple[float, int, int]]) -> list[float]:
    return [(a + b) / 2.0 for _, a, b in found]


def swatch(img: np.ndarray, box: list[int]) -> tuple[np.ndarray, float]:
    """Core colour and stroke width of a horizontal legend swatch."""
    x0, x1, y0, y1 = box
    rows = img[y0:y1, x0 + 3 : x1 - 3].mean(axis=1)
    dist = np.linalg.norm(C.WHITE - rows, axis=1)
    core = np.round(rows[int(np.argmax(dist))])
    alpha, _ = C.blend_alpha(rows[:, None, :], core)
    return core, float(alpha.sum())


def calibrate(img: np.ndarray, fig: dict[str, Any]) -> dict[str, Any]:
    la, ra, xa = fig["left_axis"], fig["right_axis"], fig["x_axis"]
    pr = fig["plot_rows"]
    grid = [
        g
        for g in C.gridlines(
            img, "h", tuple(la["gridline_band"]), tuple(la["gridline_span"])
        )
        if pr[0] - 3 <= g <= pr[1] + 3
    ]
    if len(grid) != len(la["ticks_as_printed"]):
        raise SystemExit(
            f"{fig['figure_id']}: {len(grid)} gridlines for {la['ticks_as_printed']}"
        )
    left = C.fit_linear(grid, la["ticks_as_printed"])
    left_labels = _bbox_centres(
        C.label_centres(img, "v", tuple(la["label_band"]), tuple(la["label_span"]))
    )
    if len(left_labels) != len(grid):
        raise SystemExit(f"{fig['figure_id']}: {len(left_labels)} left labels")
    offset = float(np.mean(np.asarray(grid) - np.asarray(left_labels)))
    right_labels = _bbox_centres(
        C.label_centres(img, "v", tuple(ra["label_band"]), tuple(ra["label_span"]))
    )
    if len(right_labels) != len(ra["ticks_as_printed"]):
        raise SystemExit(f"{fig['figure_id']}: {len(right_labels)} right labels")
    right = C.fit_linear([p + offset for p in right_labels], ra["ticks_as_printed"])
    # Both value axes span the plot area: the right axis's printed extremes should fall on the
    # first and last gridline.
    extent = {
        "right_value_at_top_gridline": round(float(right.value(grid[0])), 2),
        "right_value_at_bottom_gridline": round(float(right.value(grid[-1])), 2),
        "printed_extremes": [ra["ticks_as_printed"][0], ra["ticks_as_printed"][-1]],
    }
    out: dict[str, Any] = {
        "left": left,
        "right": right,
        "label_offset_px": offset,
        "left_label_centres": left_labels,
        "right_extent_check": extent,
        "gridlines": grid,
    }
    if fig["kind"] == "category":
        found = C.label_centres(
            img, "h", tuple(xa["label_band"]), tuple(xa["label_span"]), max_gap=1
        )
        if len(found) != xa["n_categories"]:
            raise SystemExit(f"{fig['figure_id']}: {len(found)} category labels")
        centres = [c for c, _, _ in found]
        xfit = C.fit_linear(centres, list(range(len(centres))))
        out["x"] = xfit
        out["xk"] = np.array([float(xfit.pixel(k)) for k in range(len(centres))])
        out["x_px_rms"] = xfit.rms / abs(xfit.slope)
    else:
        vg = C.gridlines(
            img, "v", tuple(xa["gridline_band"]), tuple(xa["gridline_span"])
        )
        labels = _bbox_centres(
            C.label_centres(
                img, "h", tuple(xa["label_band"]), tuple(xa["label_span"]), max_gap=6
            )
        )
        if len(labels) != len(xa["ticks_as_printed"]):
            raise SystemExit(f"{fig['figure_id']}: {len(labels)} time labels")
        ticks_px = []
        for lab in labels:
            near = min(vg, key=lambda g: abs(g - lab))
            if abs(near - lab) > 6:
                raise SystemExit(
                    f"{fig['figure_id']}: no gridline under time label at {lab}"
                )
            ticks_px.append(near)
        secs = [_seconds(t) for t in xa["ticks_as_printed"]]
        xfit = C.fit_linear(ticks_px, secs)
        out["x"] = xfit
        out["time_labels_px"] = labels
        out["x_px_rms"] = xfit.rms / abs(xfit.slope)
    return out


def _seconds(label: str) -> float:
    """Seconds after 16:52:00 for a printed 'hh:mm:ss.ff' or 'mm:ss.f' label."""
    parts = label.split(":")
    if len(parts) == 3:
        h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
    else:
        h, m, s = 16, int(parts[0]), float(parts[1])
    return (h - 16) * 3600 + (m - 52) * 60 + s


def _fmt_axis_time(sec: float) -> str:
    ms = int(round(sec * 1000))
    whole, frac = divmod(ms, 1000)
    m, s = divmod(52 * 60 + whole, 60)
    return f"16:{m:02d}:{s:02d}.{frac:03d}"


def _bst_iso(label_hms: str) -> str:
    return f"{DATE}T{label_hms}+01:00"


# ============================================================================================
# Scene construction and extraction
# ============================================================================================


def occluders(
    img: np.ndarray, fig: dict[str, Any]
) -> tuple[np.ndarray, list[list[int]]]:
    """Author-drawn shapes on top of the chart: dashed lines, arrows, call-out boxes, text."""
    mx = img.max(axis=2)
    sat = mx - img.min(axis=2)
    dark = (mx < 120) & (sat < 40)
    occ = C.dilate(dark, 1)
    boxes: list[list[int]] = []
    r0, r1 = fig["plot_rows"]
    c0, c1 = fig["plot_cols"]
    plot_area = (r1 - r0) * (c1 - c0)
    for x0, y0, x1, y1 in C.rectangles(dark):
        # the chart's own outer frame is not an annotation
        if (x1 - x0) * (y1 - y0) < 0.25 * plot_area:
            boxes.append([x0, y0, x1, y1])
    if "box_fill" in fig:
        fill = (
            np.linalg.norm(img - np.asarray(fig["box_fill"], dtype=float), axis=2) < 25
        )
        for x0, y0, x1, y1, area in C.components(fill):
            if area >= 300:
                boxes.append([x0, y0, x1, y1])
    for x0, y0, x1, y1 in boxes:
        occ[max(y0 - 4, 0) : y1 + 5, max(x0 - 4, 0) : x1 + 5] = True
    return occ, sorted(boxes)


def background(img: np.ndarray, fig: dict[str, Any]) -> np.ndarray:
    """White plot area plus the gridlines (drawn beneath the series)."""
    r0, r1 = fig["plot_rows"]
    c0, c1 = fig["plot_cols"]
    bg = np.full_like(img, 255.0)
    g = C.gray_mask(img, lo=150, hi=252)
    for r in range(r0 - 3, r1 + 3):
        sel = g[r, c0:c1]
        if sel.mean() > 0.3:
            bg[r, c0:c1] = np.median(img[r, c0:c1][sel], axis=0)
    if fig["kind"] == "continuous":
        for c in range(c0, c1):
            sel = g[r0:r1, c]
            if sel.mean() > 0.3:
                col = np.median(img[r0:r1, c][sel], axis=0)
                rows = slice(r0 - 3, r1 + 3)
                keep = ~g[rows, c]
                bg[rows, c] = np.where(keep[:, None], bg[rows, c], col)
    return bg


def build_scene(
    img: np.ndarray, fig: dict[str, Any], cal: dict[str, Any]
) -> tuple[C.PolylineScene, dict]:
    occ, boxes = occluders(img, fig)
    r0, r1 = fig["plot_rows"]
    c0, c1 = fig["plot_cols"]
    valid = np.zeros(img.shape[:2], dtype=bool)
    valid[r0 - 3 : r1 + 3, c0:c1] = True
    valid &= ~occ
    series = []
    swatches = {}
    for spec in fig["series"]:
        colour, width = swatch(img, fig["legend_swatches"][spec["legend"]])
        swatches[spec["legend"]] = {
            "colour_rgb": [int(v) for v in colour],
            "stroke_width_px": round(width, 2),
        }
        series.append(C.Series(spec["series_id"], colour, width, spec["axis"]))
    if fig["kind"] == "category":
        xk = cal["xk"]
    else:
        xk = np.arange(c0, c1, dtype=float)
    scene = C.PolylineScene(
        img=img,
        background=background(img, fig),
        valid=valid,
        xk=xk,
        series=series,
        y=np.full((len(series), len(xk)), np.nan),
        plot_rows=(r0 - 3, r1 + 3),
    )
    return scene, {"boxes": boxes, "swatches": swatches, "occluder_px": int(occ.sum())}


def fit_category(scene: C.PolylineScene) -> dict[str, Any]:
    evidence = [C.init_from_evidence(scene, s) for s in range(len(scene.series))]
    for _ in range(2):
        for s in reversed(range(len(scene.series))):
            C.dp_series(scene, s)
    sweeps = C.refine(scene, sweeps=6, coarse=6.0)
    return {"evidence": evidence, "sweeps": sweeps}


def fit_continuous(scene: C.PolylineScene, fig: dict[str, Any]) -> dict[str, Any]:
    r0, r1 = scene.plot_rows
    c0, c1 = fig["plot_cols"]
    member_masks = []
    for ser in scene.series:
        a, res = C.blend_alpha(scene.img, ser.colour)
        member_masks.append(np.where((res <= 40) & scene.valid, a, 0.0))
    evidence = []
    for s, ser in enumerate(scene.series):
        cover = ~scene.valid
        for t in range(s + 1, len(scene.series)):
            cover = cover | C.dilate(member_masks[t] >= 0.5, 1)
        alpha = np.where(member_masks[s] >= 0.5, member_masks[s], 0.0)
        seed = _seed_row(alpha, c0, r0, r1)
        tr = C.trace_columns(alpha, cover, (c0, c1), (r0, r1), ser.width, seed_row=seed)
        evidence.append(np.isfinite(tr.centre))
        filled = C.fill_gaps(tr, max_gap=14).centre
        idx = np.arange(len(filled))
        ok = np.isfinite(filled)
        scene.y[s] = np.interp(idx, idx[ok], filled[ok])
    sweeps = C.refine(scene, sweeps=6, coarse=4.0)
    return {"evidence": evidence, "sweeps": sweeps}


def _seed_row(alpha: np.ndarray, c0: int, r0: int, r1: int) -> float:
    for c in range(c0, c0 + 40):
        rows = np.flatnonzero(alpha[r0:r1, c] >= 0.5)
        if rows.size:
            return float(r0 + rows.mean())
    return (r0 + r1) / 2.0


def vertex_uncertainty(
    scene: C.PolylineScene, cal: dict[str, Any], kind: str
) -> dict[str, np.ndarray]:
    """Per-vertex terms in pixels: colour ambiguity (loss profile) and local slope.

    Category charts: each vertex (one plotted sample) is moved alone. Per-column traces: a block
    of five columns is translated together (see ``r05_core.block_profile_halfwidth``).
    """
    S, N = scene.y.shape
    amb = np.zeros((S, N))
    unconstrained = np.zeros((S, N), dtype=bool)
    dx = np.diff(scene.xk)
    for s, ser in enumerate(scene.series):
        if kind == "category":
            tau = C.shift_tau(ser.colour, ser.width, float(np.median(dx)) * 2.0)
            for k in range(N):
                amb[s, k], unconstrained[s, k] = C.profile_halfwidth(
                    scene, s, k, tau, reach=REACH_PX
                )
        else:
            tau = C.shift_tau(ser.colour, ser.width, 5.0)
            for k in range(N):
                amb[s, k], unconstrained[s, k] = C.block_profile_halfwidth(
                    scene, s, k, tau, half=2, reach=REACH_PX
                )
    slope = np.zeros((S, N))
    for s in range(S):
        d = np.abs(np.diff(scene.y[s]) / dx)
        slope[s, 0] = d[0]
        slope[s, -1] = d[-1]
        slope[s, 1:-1] = np.maximum(d[:-1], d[1:])
    return {"amb": amb, "unconstrained": unconstrained, "slope": slope}


def _axis_cal(cal: dict[str, Any], axis: str) -> C.LinearFit:
    return cal["left"] if axis == "left" else cal["right"]


def series_vertices(
    fig: dict[str, Any],
    scene: C.PolylineScene,
    cal: dict[str, Any],
    unc: dict[str, np.ndarray],
) -> list[dict[str, Any]]:
    """Per series, per vertex: value, uncertainty (value units) and flags."""
    out = []
    top = cal["gridlines"][0]
    bottom = cal["gridlines"][-1]
    for s, spec in enumerate(fig["series"]):
        ser = scene.series[s]
        fitc = _axis_cal(cal, spec["axis"])
        scale = abs(fitc.slope)
        cal_px = fitc.rms / scale
        verts = []
        for k in range(scene.y.shape[1]):
            y = float(scene.y[s, k])
            flags = []
            if unc["unconstrained"][s, k]:
                flags.append("occluded")
            elif unc["amb"][s, k] > AMBIGUOUS_PX:
                flags.append("ambiguous_overlap")
            if y - ser.width / 2.0 <= top + 0.5:
                flags.append("at_axis_top")
            if y + ser.width / 2.0 >= bottom - 0.5:
                flags.append("at_axis_bottom")
            u_px = float(
                C.quadrature(
                    cal_px,
                    ser.width / 2.0,
                    unc["amb"][s, k],
                    unc["slope"][s, k] * cal["x_px_rms"],
                )
            )
            verts.append(
                {
                    "k": k,
                    "x_px": float(scene.xk[k]),
                    "y_px": y,
                    "value": float(fitc.value(y)),
                    "uncertainty": u_px * scale,
                    "u_terms_px": {
                        "calibration": cal_px,
                        "half_stroke": ser.width / 2.0,
                        "colour_ambiguity": float(unc["amb"][s, k]),
                        "slope_x_error": float(unc["slope"][s, k] * cal["x_px_rms"]),
                    },
                    "flags": flags,
                }
            )
        out.append({"spec": spec, "vertices": verts})
    return out


# ============================================================================================
# Rows of the CSVs
# ============================================================================================


def _num(v: float, unit: str) -> str:
    d = DECIMALS[unit]
    r = round(v, d)
    if r == 0:
        r = 0.0
    return f"{r:.{d}f}"


def category_rows(
    fig: dict[str, Any], series: list[dict[str, Any]], labels: list[str]
) -> list[dict[str, str]]:
    rows = []
    tunc = fig["x_axis"]["time_uncertainty_s"]
    out_series = [
        (s["spec"]["series_id"], s["spec"]["unit"], s["vertices"])
        for s in series
        if s["spec"].get("output", True)
    ]
    for sid, unit, verts in out_series:
        for v in verts:
            if "occluded" in v["flags"]:
                continue
            label = labels[v["k"]]
            iso = _bst_iso(label) if label.count(":") == 2 else ""
            rows.append(
                {
                    "time_as_printed": label,
                    "time_bst_iso": iso,
                    "value": _num(v["value"], unit),
                    "unit": unit,
                    "uncertainty": _num(
                        max(v["uncertainty"], 10 ** -DECIMALS[unit]), unit
                    ),
                    "series_id": sid,
                    "sample_index": str(v["k"]),
                    "time_uncertainty_s": f"{tunc:g}",
                    "flags": ";".join(sorted(v["flags"])),
                }
            )
    return rows


def continuous_rows(
    fig: dict[str, Any], series: list[dict[str, Any]], cal: dict[str, Any]
) -> tuple[list[dict[str, str]], dict[str, list[dict[str, Any]]]]:
    """Resample the per-column fit at the figure's time step."""
    xa = fig["x_axis"]
    xfit = cal["x"]
    c0, c1 = fig["plot_cols"]
    t_lo = float(xfit.value(c0 + 2))
    t_hi = float(xfit.value(c1 - 3))
    step = xa["step_s"]
    n0 = int(np.ceil(round(t_lo / step, 6)))
    n1 = int(np.floor(round(t_hi / step, 6)))
    times = [round(n * step, 6) for n in range(n0, n1 + 1)]
    tunc = round(float(np.hypot(xa["label_rounding_s"], xfit.rms)), 4)
    rows = []
    resampled: dict[str, list[dict[str, Any]]] = {}
    for s in series:
        spec = s["spec"]
        verts = s["vertices"]
        xs = np.array([v["x_px"] for v in verts])
        vals = np.array([v["value"] for v in verts])
        us = np.array([v["uncertainty"] for v in verts])
        pts = []
        for i, t in enumerate(times):
            x = float(xfit.pixel(t))
            j = int(np.floor(x - xs[0]))
            f = x - xs[0] - j
            a, b = verts[j], verts[j + 1]
            if "occluded" in a["flags"] or "occluded" in b["flags"]:
                continue
            value = vals[j] + f * (vals[j + 1] - vals[j])
            u = max(us[j], us[j + 1])
            flags = sorted(set(a["flags"]) | set(b["flags"]))
            pts.append(
                {
                    "i": i,
                    "t": t,
                    "value": float(value),
                    "uncertainty": float(u),
                    "flags": flags,
                }
            )
        resampled[spec["series_id"]] = pts
        if not spec.get("output", True):
            continue
        unit = spec["unit"]
        for p in pts:
            label = _fmt_axis_time(p["t"])
            rows.append(
                {
                    "time_as_printed": label,
                    "time_bst_iso": _bst_iso(label),
                    "value": _num(p["value"], unit),
                    "unit": unit,
                    "uncertainty": _num(
                        max(p["uncertainty"], 10 ** -DECIMALS[unit]), unit
                    ),
                    "series_id": spec["series_id"],
                    "sample_index": str(p["i"]),
                    "time_uncertainty_s": f"{tunc:g}",
                    "flags": ";".join(p["flags"]),
                }
            )
    return rows, resampled


def write_csv(rows: list[dict[str, str]]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue().encode("utf-8")


# ============================================================================================
# Main
# ============================================================================================


def digitise_all(qa: bool) -> dict[str, Any]:
    sources = handoff_sources()
    results: dict[str, Any] = {"sources": sources, "figures": {}}
    for fig in FIGURES:
        fid = fig["figure_id"]
        img, extra = extract_image(fig)
        cal = calibrate(img, fig)
        scene, scene_info = build_scene(img, fig, cal)
        if fig["kind"] == "category":
            labels, labels_sha = category_labels(fig)
            fit = fit_category(scene)
        else:
            labels, labels_sha = [], None
            fit = fit_continuous(scene, fig)
        unc = vertex_uncertainty(scene, cal, fig["kind"])
        series = series_vertices(fig, scene, cal, unc)
        if fig["kind"] == "category":
            rows = category_rows(fig, series, labels)
            resampled = None
            xcheck = x_offset_check(scene)
        else:
            rows, resampled = continuous_rows(fig, series, cal)
            xcheck = None
        results["figures"][fid] = {
            "fig": fig,
            "img": img,
            "image": extra["info"],
            "render_600dpi": extra["render_600dpi"],
            "cal": cal,
            "scene": scene,
            "scene_info": scene_info,
            "fit": fit,
            "series": series,
            "rows": rows,
            "resampled": resampled,
            "labels": labels,
            "labels_sha256": labels_sha,
            "x_offset_check": xcheck,
            "csv_bytes": write_csv(rows),
        }
        print(f"{fid}: {len(rows)} rows", file=sys.stderr)
    return results


def x_offset_check(scene: C.PolylineScene) -> dict[str, Any]:
    """Loss of the re-drawn chart when every category position is shifted by a common offset.

    The category positions come from the label centres; the offset that best explains the
    plotted lines is reported (not applied) as a check on that calibration.
    """
    base_x = scene.xk.copy()
    base_y = scene.y.copy()
    offsets = [-1.0, -0.5, 0.0, 0.5, 1.0]
    losses = []
    for d in offsets:
        scene.xk = base_x + d
        scene.y = base_y.copy()
        C.refine(scene, sweeps=2, coarse=1.5)
        losses.append(C.total_loss(scene))
    scene.xk = base_x
    scene.y = base_y
    a, b, c = np.polyfit(offsets, losses, 2)
    best = float(-b / (2 * a)) if a > 0 else float("nan")
    return {
        "offsets_px": offsets,
        "relative_loss": [round(v / min(losses), 4) for v in losses],
        "best_offset_px": round(best, 2),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="verify outputs are up to date"
    )
    parser.add_argument("--no-qa", action="store_true", help="do not write QA overlays")
    args = parser.parse_args(argv)
    results = digitise_all(qa=not args.no_qa)
    outputs = r05_text.assemble(results, builder_version=BUILDER_VERSION, script=SCRIPT)
    targets = {
        R05_DIR / "R05.txt": outputs["text"],
        R05_DIR / "calibration.json": outputs["calibration"],
        PROVENANCE_PATH: outputs["provenance"],
        ROWS_PATH: outputs["rows"],
        MANIFEST_FRAGMENT_PATH: outputs["manifest_fragment"],
    }
    for fid, res in results["figures"].items():
        targets[BUNDLE_DIR / res["fig"]["csv"]] = res["csv_bytes"]
    if args.check:
        stale = [
            str(p)
            for p, data in targets.items()
            if not p.exists() or p.read_bytes() != data
        ]
        stray = (
            sorted(str(p) for p in R05_DIR.iterdir() if p not in targets)
            if R05_DIR.exists()
            else []
        )
        for p in stale:
            print(f"STALE: {p}", file=sys.stderr)
        for p in stray:
            print(f"STRAY: {p}", file=sys.stderr)
        return 1 if stale or stray else 0
    for path, data in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    if not args.no_qa:
        import r05_qa

        written = r05_qa.write_overlays(results, QA_DIR)
        for p in written:
            print(f"QA: {p}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
