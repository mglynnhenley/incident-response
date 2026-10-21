"""Pure-numpy digitisation primitives for R05 (Hornsea traces).

Builder-only. Imported by ``build_r05.py`` and by the tests; needs numpy only (no PyMuPDF and no
Pillow), so the calibration and extraction logic can be unit-tested on synthetic images.

Conventions
-----------
* Images are ``float64`` arrays of shape (H, W, 3) with values 0..255 (RGB, alpha composited on
  white by the caller).
* Pixel (row r, column c) has its centre at image coordinates (x=c, y=r); y grows downwards.
* Every calibration is a least-squares straight line ``value = intercept + slope * px`` fitted to
  at least three (pixel, value) tick pairs; residuals are reported in value units.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

WHITE = np.array([255.0, 255.0, 255.0])


# --------------------------------------------------------------------------------------------
# Linear calibration
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LinearFit:
    """value = intercept + slope * px, fitted by least squares to tick pairs."""

    slope: float
    intercept: float
    px: tuple[float, ...]
    values: tuple[float, ...]
    residuals: tuple[float, ...]  # fitted - printed, value units
    rms: float
    max_abs: float

    def value(self, px: float | np.ndarray) -> float | np.ndarray:
        return self.intercept + self.slope * px

    def pixel(self, value: float | np.ndarray) -> float | np.ndarray:
        return (value - self.intercept) / self.slope

    @property
    def px_rms(self) -> float:
        return self.rms / abs(self.slope)

    def as_dict(self, ndigits: int = 6) -> dict:
        return {
            "model": "value = intercept + slope * pixel",
            "slope_per_px": round(self.slope, ndigits),
            "intercept": round(self.intercept, ndigits),
            "n_ticks": len(self.px),
            "ticks": [
                {"pixel": round(p, 3), "value": v, "residual": round(r, ndigits)}
                for p, v, r in zip(self.px, self.values, self.residuals, strict=True)
            ],
            "rms_residual": round(self.rms, ndigits),
            "max_abs_residual": round(self.max_abs, ndigits),
            "rms_residual_px": round(self.px_rms, 4),
        }


def fit_linear(
    px: list[float] | np.ndarray, values: list[float] | np.ndarray
) -> LinearFit:
    """Least-squares line through (pixel, value) ticks; at least three ticks are required."""
    p = np.asarray(px, dtype=float)
    v = np.asarray(values, dtype=float)
    if p.shape != v.shape or p.ndim != 1:
        raise ValueError("px and values must be 1-D and the same length")
    if len(p) < 3:
        raise ValueError(f"need >= 3 ticks for a calibration, got {len(p)}")
    pm, vm = p.mean(), v.mean()
    sxx = float(((p - pm) ** 2).sum())
    if sxx == 0:
        raise ValueError("tick pixels are all equal")
    slope = float(((p - pm) * (v - vm)).sum() / sxx)
    intercept = float(vm - slope * pm)
    fitted = intercept + slope * p
    resid = fitted - v
    return LinearFit(
        slope=slope,
        intercept=intercept,
        px=tuple(float(x) for x in p),
        values=tuple(float(x) for x in v),
        residuals=tuple(float(x) for x in resid),
        rms=float(np.sqrt((resid**2).mean())),
        max_abs=float(np.abs(resid).max()),
    )


# --------------------------------------------------------------------------------------------
# Tick detection: gridlines and label centroids
# --------------------------------------------------------------------------------------------


def _runs(flags: np.ndarray, max_gap: int = 0) -> list[tuple[int, int]]:
    """Inclusive index runs where ``flags`` is true; runs separated by <= max_gap are merged."""
    idx = np.flatnonzero(flags)
    if idx.size == 0:
        return []
    runs: list[tuple[int, int]] = []
    start = prev = int(idx[0])
    for i in idx[1:]:
        i = int(i)
        if i - prev > max_gap + 1:
            runs.append((start, prev))
            start = i
        prev = i
    runs.append((start, prev))
    return runs


def gray_mask(
    img: np.ndarray, lo: float = 150.0, hi: float = 250.0, tol: float = 6.0
) -> np.ndarray:
    """Neutral grey pixels (gridline candidates)."""
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    return (np.abs(r - g) < tol) & (np.abs(g - b) < tol) & (r > lo) & (r < hi)


def gridlines(
    img: np.ndarray,
    orient: str,
    band: tuple[int, int],
    span: tuple[int, int],
    min_frac: float = 0.3,
) -> list[float]:
    """Centres of gridlines.

    orient "h": horizontal gridlines; ``band`` is the row range searched and ``span`` the column
    range in which a row must be mostly grey. orient "v": the transpose. Centres are weighted by
    darkness (255 - grey level) across the 1-2 anti-aliased pixel rows of each line.
    """
    sub = img if orient == "h" else img.transpose(1, 0, 2)
    lo, hi = band
    s0, s1 = span
    g = gray_mask(sub[lo:hi, s0:s1])
    frac = g.mean(axis=1)
    centres = []
    for a, b in _runs(frac >= min_frac):
        rows = np.arange(a, b + 1)
        dark = []
        for r in rows:
            sel = g[r]
            dark.append(float((255.0 - sub[lo + r, s0:s1][sel].mean(axis=1)).mean()))
        w = np.asarray(dark)
        centres.append(float(lo + (rows * w).sum() / w.sum()))
    return centres


def ink(img: np.ndarray) -> np.ndarray:
    """Darkness 0..255 (255 - min channel); text and lines are 'ink' on white."""
    return 255.0 - img.min(axis=2)


def label_centres(
    img: np.ndarray,
    orient: str,
    band: tuple[int, int],
    span: tuple[int, int],
    min_ink: float = 40.0,
    max_gap: int = 1,
) -> list[tuple[float, int, int]]:
    """Ink-weighted centres of text labels stacked along one axis.

    orient "v": labels stacked vertically (y-axis labels); ``band`` is the column range holding
    the labels and ``span`` the row range searched. The ink of each row is summed across the band
    and contiguous rows form one label. orient "h": labels side by side (x-axis labels); ``band``
    is the row range and ``span`` the column range. Returns (centre, first, last) per label.
    """
    k = ink(img)
    if orient == "v":
        prof = k[span[0] : span[1], band[0] : band[1]].sum(axis=1)
    else:
        prof = k[band[0] : band[1], span[0] : span[1]].sum(axis=0)
    out = []
    for a, b in _runs(prof >= min_ink, max_gap=max_gap):
        idx = np.arange(a, b + 1)
        w = prof[a : b + 1]
        out.append(
            (float(span[0] + (idx * w).sum() / w.sum()), span[0] + a, span[0] + b)
        )
    return out


def components(mask: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    """8-connected components of a boolean mask as (x0, y0, x1, y1, area), inclusive bounds.

    Scan-line run labelling with union-find (no scipy); output sorted by (y0, x0).
    """
    parent: list[int] = []

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    runs: list[tuple[int, int, int]] = []  # (row, a, b)
    prev: list[int] = []
    for r in range(mask.shape[0]):
        cur: list[int] = []
        for a, b in _runs(mask[r]):
            idx = len(runs)
            runs.append((r, a, b))
            parent.append(idx)
            for j in prev:
                _, pa, pb = runs[j]
                if pa <= b + 1 and pb >= a - 1:
                    ri, rj = find(idx), find(j)
                    if ri != rj:
                        parent[max(ri, rj)] = min(ri, rj)
            cur.append(idx)
        prev = cur
    boxes: dict[int, list[int]] = {}
    for i, (r, a, b) in enumerate(runs):
        root = find(i)
        bx = boxes.setdefault(root, [a, r, b, r, 0])
        bx[0] = min(bx[0], a)
        bx[1] = min(bx[1], r)
        bx[2] = max(bx[2], b)
        bx[3] = max(bx[3], r)
        bx[4] += b - a + 1
    return sorted((tuple(v) for v in boxes.values()), key=lambda t: (t[1], t[0]))  # type: ignore[misc]


def rectangles(
    mask: np.ndarray, min_w: int = 30, min_h: int = 15
) -> list[tuple[int, int, int, int]]:
    """Axis-aligned rectangle outlines drawn in ``mask`` pixels (annotation boxes).

    A rectangle needs a horizontal run (top edge) whose two ends start vertical runs of at least
    ``min_h`` rows that end on a second horizontal run (bottom edge) covering >= 90 % of the
    width. Overlapping detections (thick borders) are merged. Returns (x0, y0, x1, y1) inclusive.
    """
    h, w = mask.shape
    found: list[list[int]] = []
    for r in range(h - min_h):
        for a, b in _runs(mask[r]):
            if b - a + 1 < min_w:
                continue
            depth = []
            for c in (a, b):
                best = 0
                for cc in range(max(c - 1, 0), min(c + 2, w)):
                    n = 0
                    while r + n < h and mask[r + n, cc]:
                        n += 1
                    best = max(best, n)
                depth.append(best)
            d = min(depth)
            if d < min_h:
                continue
            bottom = r + d - 1
            span = mask[max(bottom - 1, 0) : bottom + 2, a : b + 1].any(axis=0).mean()
            if span < 0.9:
                continue
            for f in found:
                if not (a > f[2] or b < f[0] or r > f[3] or bottom < f[1]):
                    f[0], f[1] = min(f[0], a), min(f[1], r)
                    f[2], f[3] = max(f[2], b), max(f[3], bottom)
                    break
            else:
                found.append([a, r, b, bottom])
    return [tuple(f) for f in sorted(found, key=lambda f: (f[1], f[0]))]  # type: ignore[misc]


def dilate(mask: np.ndarray, n: int = 1) -> np.ndarray:
    """Square (8-neighbour) dilation by n pixels."""
    out = mask.copy()
    for _ in range(n):
        m = out.copy()
        m[1:] |= out[:-1]
        m[:-1] |= out[1:]
        m[:, 1:] |= out[:, :-1]
        m[:, :-1] |= out[:, 1:]
        m[1:, 1:] |= out[:-1, :-1]
        m[:-1, :-1] |= out[1:, 1:]
        m[1:, :-1] |= out[:-1, 1:]
        m[:-1, 1:] |= out[1:, :-1]
        out = m
    return out


# --------------------------------------------------------------------------------------------
# Colour membership
# --------------------------------------------------------------------------------------------


def blend_alpha(img: np.ndarray, colour: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Unmix each pixel as alpha*colour + (1-alpha)*white.

    Returns (alpha clipped to 0..1, residual distance of the pixel from that blend). A small
    residual with a high alpha means the pixel is (an anti-aliased part of) a stroke of this
    colour drawn over white.
    """
    d = WHITE - np.asarray(colour, dtype=float)
    q = WHITE - img
    alpha = (q @ d) / float(d @ d)
    alpha = np.clip(alpha, 0.0, 1.0)
    resid = np.linalg.norm(q - alpha[..., None] * d, axis=-1)
    return alpha, resid


# --------------------------------------------------------------------------------------------
# Polyline model for category-axis line charts (Excel line charts, APP Fig 3 / Fig 4)
# --------------------------------------------------------------------------------------------


@dataclass
class Series:
    series_id: str
    colour: np.ndarray  # core RGB colour
    width: float  # stroke width in px
    axis: str  # "left" | "right"


@dataclass
class PolylineScene:
    """Analysis-by-synthesis model of a category line chart.

    Series are drawn in list order (later series on top) as anti-aliased round-joined strokes over
    ``background``. ``valid`` marks pixels that may be compared with the image (inside the plot
    area and not under author-drawn annotations, which sit on top of the chart).
    """

    img: np.ndarray
    background: np.ndarray
    valid: np.ndarray
    xk: np.ndarray
    series: list[Series]
    y: np.ndarray  # (S, N) vertex rows
    plot_rows: tuple[int, int]
    fixed: np.ndarray = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.fixed is None:
            self.fixed = np.zeros(self.y.shape, dtype=bool)


def _seg_dist(px: np.ndarray, py: np.ndarray, x1, y1, x2, y2) -> np.ndarray:
    """Distance from points to segments; segment endpoints may carry a leading candidate axis."""
    dx = x2 - x1
    dy = y2 - y1
    den = dx * dx + dy * dy
    den = np.where(den == 0, 1e-12, den)
    t = ((px - x1) * dx + (py - y1) * dy) / den
    t = np.clip(t, 0.0, 1.0)
    cx = x1 + t * dx
    cy = y1 + t * dy
    return np.sqrt((px - cx) ** 2 + (py - cy) ** 2)


def coverage(dist: np.ndarray, width: float) -> np.ndarray:
    """Box-filter anti-aliased stroke coverage for a pixel at distance ``dist`` from the centre."""
    return np.clip(width / 2.0 + 0.5 - dist, 0.0, 1.0)


def _window(scene: PolylineScene, k: int) -> tuple[int, int]:
    n = len(scene.xk)
    lo = scene.xk[max(k - 1, 0)] if k > 0 else scene.xk[0] - 4
    hi = scene.xk[min(k + 1, n - 1)] if k < n - 1 else scene.xk[-1] + 4
    c0 = max(int(np.floor(lo)), 0)
    c1 = min(int(np.ceil(hi)) + 1, scene.img.shape[1])
    return c0, c1


def _series_cov(
    scene: PolylineScene, s: int, c0: int, c1: int, r0: int, r1: int, yk=None, k=None
):
    """Coverage of series s over the window; optionally with vertex k replaced by candidates yk.

    Returns an array (C, h, w) when candidates are given, else (h, w).
    """
    xs = scene.xk
    ys = scene.y[s]
    n = len(xs)
    rows = np.arange(r0, r1, dtype=float)[:, None]
    cols = np.arange(c0, c1, dtype=float)[None, :]
    # Segments touching the window (with stroke margin).
    margin = scene.series[s].width + 2
    segs = [
        i
        for i in range(n - 1)
        if xs[i + 1] >= c0 - margin
        and xs[i] <= c1 + margin
        and np.isfinite(ys[i])
        and np.isfinite(ys[i + 1])
    ]
    if yk is None:
        dmin = np.full((r1 - r0, c1 - c0), np.inf)
        for i in segs:
            dmin = np.minimum(
                dmin, _seg_dist(cols, rows, xs[i], ys[i], xs[i + 1], ys[i + 1])
            )
        return coverage(dmin, scene.series[s].width)
    cand = np.asarray(yk, dtype=float)[:, None, None]
    dmin = np.full((len(cand), r1 - r0, c1 - c0), np.inf)
    for i in segs:
        y1 = cand if i == k else ys[i]
        y2 = cand if i + 1 == k else ys[i + 1]
        dmin = np.minimum(dmin, _seg_dist(cols, rows, xs[i], y1, xs[i + 1], y2))
    return coverage(dmin, scene.series[s].width)


def _compose(
    scene: PolylineScene, covs: list[np.ndarray], r0, r1, c0, c1
) -> np.ndarray:
    out = scene.background[r0:r1, c0:c1]
    for s, cov in enumerate(covs):
        col = scene.series[s].colour
        out = out * (1.0 - cov[..., None]) + col * cov[..., None]
    return out


def window_loss(
    scene: PolylineScene, s: int, k: int, candidates: np.ndarray
) -> np.ndarray:
    """Sum of squared RGB differences between model and image near vertex k, per candidate y.

    Only pixels that series s can cover for some candidate are compared (columns between the
    neighbouring vertices, rows between the extreme candidate/neighbour positions plus the stroke
    width): every other pixel contributes the same amount to every candidate.
    """
    c0, c1 = _window(scene, k)
    n = len(scene.xk)
    ys = [float(v) for v in candidates]
    for j in (k - 1, k + 1):
        if 0 <= j < n and np.isfinite(scene.y[s, j]):
            ys.append(float(scene.y[s, j]))
    pad = scene.series[s].width + 2
    r0 = max(scene.plot_rows[0], int(np.floor(min(ys) - pad)))
    r1 = min(scene.plot_rows[1], int(np.ceil(max(ys) + pad)) + 1)
    if r1 <= r0:
        return np.zeros(len(candidates))
    covs: list[np.ndarray] = []
    for t in range(len(scene.series)):
        if t == s:
            covs.append(_series_cov(scene, t, c0, c1, r0, r1, yk=candidates, k=k))
        else:
            covs.append(_series_cov(scene, t, c0, c1, r0, r1)[None])
    model = _compose(scene, covs, r0, r1, c0, c1)
    diff = model - scene.img[r0:r1, c0:c1][None]
    sq = (diff**2).sum(axis=-1) * scene.valid[r0:r1, c0:c1][None]
    return sq.reshape(len(candidates), -1).sum(axis=1)


def init_from_evidence(
    scene: PolylineScene,
    s: int,
    alpha_min: float = 0.85,
    resid_max: float = 24.0,
) -> np.ndarray:
    """Initial vertex rows for series s from pixels that look like its colour over white.

    At each category column the runs of member pixels (blend alpha >= alpha_min and blend
    residual <= resid_max, inside the valid area) are candidates; the longest run is taken for the
    first vertex with evidence and afterwards the run nearest the previous vertex. Columns with no
    evidence are filled by linear interpolation (nearest value at the ends). Returns a boolean
    array marking the vertices that had direct evidence.
    """
    r0, r1 = scene.plot_rows
    alpha, resid = blend_alpha(scene.img[r0:r1], scene.series[s].colour)
    member = (alpha >= alpha_min) & (resid <= resid_max) & scene.valid[r0:r1]
    n = len(scene.xk)
    ys = np.full(n, np.nan)
    prev: float | None = None
    for k in range(n):
        c = int(round(scene.xk[k]))
        runs = _runs(member[:, c])
        if not runs:
            continue
        cands = [((a + b) / 2.0 + r0, b - a + 1) for a, b in runs]
        if prev is None:
            y = max(cands, key=lambda t: (t[1], -t[0]))[0]
        else:
            y = min(cands, key=lambda t: (abs(t[0] - prev), -t[1]))[0]
        ys[k] = y
        prev = y
    has = np.isfinite(ys)
    if has.any():
        idx = np.arange(n)
        ys = np.interp(idx, idx[has], ys[has])
    else:
        ys[:] = (r0 + r1) / 2.0
    scene.y[s] = ys
    return has


def render(scene: PolylineScene) -> np.ndarray:
    """Re-draw the whole chart from the fitted vertices (used for residual checks and QA)."""
    h, w = scene.img.shape[:2]
    out = scene.background.copy()
    for s, ser in enumerate(scene.series):
        cov = np.zeros((h, w))
        ys = scene.y[s]
        pad = ser.width / 2.0 + 2
        for i in range(len(scene.xk) - 1):
            if not (np.isfinite(ys[i]) and np.isfinite(ys[i + 1])):
                continue
            x1, x2 = scene.xk[i], scene.xk[i + 1]
            c0 = max(int(np.floor(min(x1, x2) - pad)), 0)
            c1 = min(int(np.ceil(max(x1, x2) + pad)) + 1, w)
            r0 = max(int(np.floor(min(ys[i], ys[i + 1]) - pad)), 0)
            r1 = min(int(np.ceil(max(ys[i], ys[i + 1]) + pad)) + 1, h)
            rows = np.arange(r0, r1, dtype=float)[:, None]
            cols = np.arange(c0, c1, dtype=float)[None, :]
            d = _seg_dist(cols, rows, x1, ys[i], x2, ys[i + 1])
            cov[r0:r1, c0:c1] = np.maximum(cov[r0:r1, c0:c1], coverage(d, ser.width))
        out = out * (1.0 - cov[..., None]) + ser.colour * cov[..., None]
    return out


def total_loss(scene: PolylineScene) -> float:
    r0, r1 = scene.plot_rows
    model = render(scene)
    sq = ((model - scene.img) ** 2).sum(axis=-1) * scene.valid
    return float(sq[r0:r1].sum())


def evidence_candidates(
    scene: PolylineScene,
    s: int,
    k: int,
    member: np.ndarray,
    col_radius: int = 2,
    merge: float = 0.75,
) -> list[float]:
    """Candidate rows for vertex k: member-pixel runs in nearby columns, current value and the
    other series' positions at k."""
    r0 = scene.plot_rows[0]
    c = int(round(scene.xk[k]))
    cands: list[float] = []
    for cc in range(c - col_radius, c + col_radius + 1):
        if 0 <= cc < member.shape[1]:
            for a, b in _runs(member[:, cc]):
                cands.append((a + b) / 2.0 + r0)
    if np.isfinite(scene.y[s, k]):
        cands.append(float(scene.y[s, k]))
    # A series with no visible pixels is most plausibly hidden under another series' stroke.
    for t in range(len(scene.series)):
        if t != s and np.isfinite(scene.y[t, k]):
            cands.append(float(scene.y[t, k]))
    cands.sort()
    out: list[float] = []
    for v in cands:
        if not out or v - out[-1] > merge:
            out.append(v)
    return out


def _segment_cost(
    scene: PolylineScene, s: int, k: int, ya: np.ndarray, yb: np.ndarray
) -> np.ndarray:
    """Loss over the columns of segment (k, k+1) for every pair (ya[i], yb[j]); shape (A, B)."""
    x1, x2 = scene.xk[k], scene.xk[k + 1]
    c0 = int(np.ceil(x1))
    c1 = int(np.ceil(x2))
    pad = scene.series[s].width + 2
    lo = min(float(ya.min()), float(yb.min())) - pad
    hi = max(float(ya.max()), float(yb.max())) + pad
    r0 = max(scene.plot_rows[0], int(np.floor(lo)))
    r1 = min(scene.plot_rows[1], int(np.ceil(hi)) + 1)
    rows = np.arange(r0, r1, dtype=float)[:, None]
    cols = np.arange(c0, c1, dtype=float)[None, :]
    others = [
        _series_cov(scene, t, c0, c1, r0, r1) if t != s else None
        for t in range(len(scene.series))
    ]
    target = scene.img[r0:r1, c0:c1]
    valid = scene.valid[r0:r1, c0:c1]
    out = np.zeros((len(ya), len(yb)))
    for i, a in enumerate(ya):
        d = _seg_dist(cols, rows, x1, a, x2, np.asarray(yb, dtype=float)[:, None, None])
        cov = coverage(d, scene.series[s].width)
        layers = [cov if t == s else others[t][None] for t in range(len(scene.series))]
        model = _compose(scene, layers, r0, r1, c0, c1)
        sq = ((model - target[None]) ** 2).sum(axis=-1) * valid[None]
        out[i] = sq.reshape(len(yb), -1).sum(axis=1)
    return out


def dp_series(
    scene: PolylineScene,
    s: int,
    alpha_min: float = 0.85,
    resid_max: float = 24.0,
    col_radius: int = 2,
    bridge_step: float = 2.0,
) -> None:
    """Choose series s's vertex rows by dynamic programming over candidate stroke positions.

    Candidates at each vertex are the centres of runs of pixels that look like the series colour
    in nearby columns, plus the current value; a vertex with no evidence (hidden under an
    annotation or a later series) gets a grid spanning its neighbours' candidates. The path
    minimises the summed segment losses of the full re-drawn chart with the other series fixed.
    """
    r0, r1 = scene.plot_rows
    alpha, resid = blend_alpha(scene.img[r0:r1], scene.series[s].colour)
    member = (alpha >= alpha_min) & (resid <= resid_max) & scene.valid[r0:r1]
    n = len(scene.xk)
    cand = [evidence_candidates(scene, s, k, member, col_radius) for k in range(n)]
    for k in range(n):
        if len(cand[k]) <= 1:
            near = [v for j in (k - 1, k + 1) if 0 <= j < n for v in cand[j]]
            if near:
                lo, hi = min(near), max(near)
                grid = list(np.arange(lo, hi + 1e-9, bridge_step))
                cand[k] = sorted(set(cand[k]) | {float(v) for v in grid})
    arrs = [np.asarray(c, dtype=float) for c in cand]
    cost = np.zeros(len(arrs[0]))
    back: list[np.ndarray] = []
    for k in range(n - 1):
        seg = _segment_cost(scene, s, k, arrs[k], arrs[k + 1])
        tot = cost[:, None] + seg
        back.append(np.argmin(tot, axis=0))
        cost = tot.min(axis=0)
    path = [int(np.argmin(cost))]
    for k in range(n - 2, -1, -1):
        path.append(int(back[k][path[-1]]))
    path.reverse()
    scene.y[s] = np.array([arrs[k][path[k]] for k in range(n)])


def refine(
    scene: PolylineScene, sweeps: int = 4, coarse: float = 8.0, tol: float = 0.05
) -> int:
    """Coordinate descent on every free vertex: coarse 0.5-px grid, then 0.05-px grid.

    Ties are broken towards the current value, so vertices with no visible evidence stay where
    the initialisation put them. Returns the number of sweeps performed.
    """
    S, N = scene.y.shape
    done = 0
    for _ in range(sweeps):
        done += 1
        biggest = 0.0
        for s in range(S):
            for k in range(N):
                if scene.fixed[s, k] or not np.isfinite(scene.y[s, k]):
                    continue
                y0 = scene.y[s, k]
                grid = y0 + np.arange(-coarse, coarse + 1e-9, 0.5)
                loss = window_loss(scene, s, k, grid)
                best = grid[_argmin_near(loss, grid, y0)]
                fine = best + np.arange(-0.5, 0.5 + 1e-9, 0.05)
                loss = window_loss(scene, s, k, fine)
                new = float(fine[_argmin_near(loss, fine, y0)])
                biggest = max(biggest, abs(new - y0))
                scene.y[s, k] = new
        if biggest < tol:
            break
    return done


def _argmin_near(loss: np.ndarray, grid: np.ndarray, y0: float) -> int:
    m = loss.min()
    tie = np.flatnonzero(loss <= m + 1e-6 * max(1.0, abs(m)))
    return int(tie[np.argmin(np.abs(grid[tie] - y0))])


def profile_halfwidth(
    scene: PolylineScene,
    s: int,
    k: int,
    tau: float,
    reach: float = 12.0,
    step: float = 0.25,
) -> tuple[float, bool]:
    """Half-width (px) of the set of vertex positions whose loss is within ``tau`` of the best.

    This is the colour-ambiguity / occlusion term: a cleanly visible vertex gives a narrow set, a
    vertex hidden under a later-drawn series or an annotation gives a wide one. The second value
    is True when the set reaches the search limit (the vertex is unconstrained by the image).
    """
    y0 = scene.y[s, k]
    grid = y0 + np.arange(-reach, reach + 1e-9, step)
    loss = window_loss(scene, s, k, grid)
    ok = loss <= loss.min() + tau
    half = float(np.abs(grid[ok] - y0).max())
    return half, bool(ok[0] or ok[-1])


def block_profile_halfwidth(
    scene: PolylineScene,
    s: int,
    k: int,
    tau: float,
    half: int = 2,
    reach: float = 12.0,
    step: float = 0.25,
) -> tuple[float, bool]:
    """As :func:`profile_halfwidth`, but translating vertices k-half..k+half together.

    For densely sampled (per-column) traces a single vertex can be moved as a narrow spike while
    its neighbours still cover the stroke, which says little about where the curve is; moving a
    short block vacates the stroke's pixels, so the loss measures the curve's local position.
    The second value is True only when the plausible set reaches the limit on both sides.
    """
    n = len(scene.xk)
    lo, hi = max(k - half, 0), min(k + half, n - 1)
    c0 = max(int(np.floor(scene.xk[max(lo - 1, 0)])), 0)
    c1 = min(int(np.ceil(scene.xk[min(hi + 1, n - 1)])) + 1, scene.img.shape[1])
    deltas = np.arange(-reach, reach + 1e-9, step)
    ys = scene.y[s]
    span = ys[max(lo - 1, 0) : min(hi + 2, n)]
    pad = scene.series[s].width + 2
    r0 = max(scene.plot_rows[0], int(np.floor(np.nanmin(span) - reach - pad)))
    r1 = min(scene.plot_rows[1], int(np.ceil(np.nanmax(span) + reach + pad)) + 1)
    rows = np.arange(r0, r1, dtype=float)[:, None]
    cols = np.arange(c0, c1, dtype=float)[None, :]
    dd = deltas[:, None, None]
    dmin = np.full((len(deltas), r1 - r0, c1 - c0), np.inf)
    xs = scene.xk
    for i in range(max(lo - 2, 0), min(hi + 2, n - 1)):
        y1 = ys[i] + (dd if lo <= i <= hi else 0.0)
        y2 = ys[i + 1] + (dd if lo <= i + 1 <= hi else 0.0)
        dmin = np.minimum(dmin, _seg_dist(cols, rows, xs[i], y1, xs[i + 1], y2))
    cov_s = coverage(dmin, scene.series[s].width)
    layers = [
        cov_s if t == s else _series_cov(scene, t, c0, c1, r0, r1)[None]
        for t in range(len(scene.series))
    ]
    model = _compose(scene, layers, r0, r1, c0, c1)
    sq = ((model - scene.img[r0:r1, c0:c1][None]) ** 2).sum(axis=-1) * scene.valid[
        r0:r1, c0:c1
    ][None]
    loss = sq.reshape(len(deltas), -1).sum(axis=1)
    ok = loss <= loss.min() + tau
    halfw = float(np.abs(deltas[ok]).max())
    return halfw, bool(ok[0] and ok[-1])


def shift_tau(
    colour: np.ndarray, width: float, length: float, shift: float = 0.5
) -> float:
    """Loss change caused by moving a clean horizontal stroke by ``shift`` px over white.

    Used as the profile threshold: positions that explain the image no worse than a ``shift``-px
    displacement of a fully visible stroke of the same colour and width are treated as plausible.
    """
    rows = np.arange(-10, 11, dtype=float)
    a = coverage(np.abs(rows), width)
    b = coverage(np.abs(rows - shift), width)
    d = WHITE - np.asarray(colour, dtype=float)
    per_col = float((((a - b)[:, None] * d[None, :]) ** 2).sum())
    return per_col * length


# --------------------------------------------------------------------------------------------
# Column tracing for continuous time-axis charts (ESO Fig 7 / Fig 8)
# --------------------------------------------------------------------------------------------


@dataclass
class ColumnTrace:
    cols: np.ndarray  # column index
    centre: np.ndarray  # stroke centre row (NaN if no evidence)
    top: np.ndarray  # first stroke row
    bottom: np.ndarray  # last stroke row
    flag: list[str]  # "" | "interpolated" | "apex" | "clipped_top" | "clipped_bottom"


def trace_columns(
    alpha: np.ndarray,
    occluder: np.ndarray,
    col_range: tuple[int, int],
    row_range: tuple[int, int],
    width: float,
    seed_row: float,
    min_alpha: float = 0.35,
    occluder_merge: int = 6,
) -> ColumnTrace:
    """Follow one stroke column by column.

    ``alpha``: membership of each pixel in the series colour (0..1). ``occluder``: pixels drawn
    on top of the series (other series, annotation lines, boxes, text). In each column the runs
    of member pixels are found; runs separated only by occluder pixels (or <= 1 px) are merged;
    the run nearest the previous column's centre is kept. The centre is the midpoint of the run's
    sub-pixel edges. Columns where the stroke is hidden are left NaN for interpolation.
    """
    r0, r1 = row_range
    cols = np.arange(col_range[0], col_range[1])
    centre = np.full(len(cols), np.nan)
    top = np.full(len(cols), np.nan)
    bottom = np.full(len(cols), np.nan)
    flag = [""] * len(cols)
    prev = seed_row
    for j, c in enumerate(cols):
        a = alpha[r0:r1, c]
        occ = occluder[r0:r1, c]
        runs = _runs(a >= min_alpha)
        if not runs:
            continue
        # merge runs separated by occluder pixels or tiny gaps
        merged = [runs[0]]
        for ra, rb in runs[1:]:
            pa, pb = merged[-1]
            gap = slice(pb + 1, ra)
            if ra - pb - 1 <= 1 or (ra - pb - 1 <= occluder_merge and occ[gap].all()):
                merged[-1] = (pa, rb)
            else:
                merged.append((ra, rb))
        best = min(merged, key=lambda ab: abs((ab[0] + ab[1]) / 2 + r0 - prev))
        ra, rb = best
        # sub-pixel edges: partial alpha at the ends of the run
        t = r0 + ra - 0.5 + (1.0 - _edge_alpha(a, ra, -1))
        b = r0 + rb + 0.5 - (1.0 - _edge_alpha(a, rb, +1))
        top[j], bottom[j] = t, b
        centre[j] = (t + b) / 2.0
        if (rb - ra + 1) < width - 1.0 and (
            occ[max(ra - 2, 0) : ra].any() or occ[rb + 1 : rb + 3].any()
        ):
            # stroke partly covered by an occluder: centre unreliable
            centre[j] = np.nan
            flag[j] = "interpolated"
        prev = centre[j] if np.isfinite(centre[j]) else prev
    return ColumnTrace(cols=cols, centre=centre, top=top, bottom=bottom, flag=flag)


def _edge_alpha(a: np.ndarray, i: int, direction: int) -> float:
    """Membership of the pixel just outside run end i (0 if outside the array)."""
    j = i + direction
    if 0 <= j < len(a):
        return float(min(max(a[j], 0.0), 1.0))
    return 0.0


def fill_gaps(trace: ColumnTrace, max_gap: int) -> ColumnTrace:
    """Linear interpolation across NaN gaps up to ``max_gap`` columns; longer gaps stay NaN."""
    c = trace.centre.copy()
    flag = list(trace.flag)
    good = np.isfinite(c)
    idx = np.arange(len(c))
    for a, b in _runs(~good):
        if a == 0 or b == len(c) - 1 or (b - a + 1) > max_gap:
            continue
        c[a : b + 1] = np.interp(idx[a : b + 1], [a - 1, b + 1], [c[a - 1], c[b + 1]])
        for i in range(a, b + 1):
            flag[i] = "interpolated"
    return ColumnTrace(trace.cols, c, trace.top, trace.bottom, flag)


def column_half_extent(trace: ColumnTrace, width: float) -> np.ndarray:
    """Half the vertical extent of the stroke in each column, at least half the stroke width."""
    ext = (trace.bottom - trace.top) / 2.0
    ext = np.where(np.isfinite(ext), ext, np.nan)
    return np.maximum(ext, width / 2.0)


def resample(
    cols: np.ndarray, values: np.ndarray, x: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Linear interpolation of a per-column series at fractional columns ``x``.

    Returns (values, index of the nearer neighbour column) and NaN where either neighbour is NaN
    or x is outside the column range.
    """
    out = np.full(len(x), np.nan)
    near = np.full(len(x), -1, dtype=int)
    for i, xi in enumerate(x):
        j = int(np.floor(xi)) - int(cols[0])
        if j < 0 or j + 1 >= len(cols):
            continue
        f = xi - np.floor(xi)
        a, b = values[j], values[j + 1]
        if np.isfinite(a) and np.isfinite(b):
            out[i] = a + f * (b - a)
            near[i] = j if f < 0.5 else j + 1
    return out, near


def quadrature(*terms: float | np.ndarray) -> float | np.ndarray:
    total = 0.0
    for t in terms:
        total = total + np.asarray(t, dtype=float) ** 2
    return np.sqrt(total)
