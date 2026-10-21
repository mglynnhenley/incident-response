"""QA overlays for R05: the digitised CSV values drawn back onto the source raster.

Builder-only (needs Pillow). Values are read back from the CSV bytes and mapped to pixels through
the inverse calibration, so a correct overlay checks extraction, calibration and formatting
together. Output goes outside the environment (``GB_DIGITISE_QA_DIR``); not part of the bundle.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import numpy as np
import r05_core as C
from PIL import Image, ImageDraw

# Overlay colour per series (chosen to contrast with the series' own stroke colour).
INK = [
    (0, 0, 0),
    (255, 0, 255),
    (120, 60, 0),
    (0, 90, 0),
    (90, 0, 140),
    (0, 0, 0),
    (255, 0, 255),
    (0, 0, 120),
    (120, 0, 0),
]

CROPS = {
    "APP-p40-fig3": [(400, 100, 720, 520, 4), (85, 160, 460, 480, 3)],
    "APP-p41-fig4": [
        (560, 40, 1010, 360, 3),
        (560, 470, 1010, 610, 4),
        (860, 300, 1100, 620, 4),
    ],
    "ESO-p19-fig7": [(330, 85, 560, 415, 4), (320, 170, 400, 240, 8)],
    "ESO-p19-fig8": [(180, 50, 360, 265, 6), (240, 180, 300, 262, 8)],
}


def _csv_series(data: bytes) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for row in csv.DictReader(io.StringIO(data.decode("utf-8"))):
        out.setdefault(row["series_id"], []).append(row)
    return out


def _series_axis(fig: dict[str, Any], sid: str) -> str:
    for spec in fig["series"]:
        if sid == spec["series_id"]:
            return spec["axis"]
    return "right"


def _points(
    res: dict[str, Any], sid: str, rows: list[dict[str, str]]
) -> list[tuple[float, float, float, str]]:
    fig, cal = res["fig"], res["cal"]
    fitc = cal["left"] if _series_axis(fig, sid) == "left" else cal["right"]
    pts = []
    for r in rows:
        if fig["kind"] == "category":
            x = float(cal["xk"][int(r["sample_index"])])
        else:
            hms = r["time_as_printed"]
            h, m, s = hms.split(":")
            t = (int(h) - 16) * 3600 + (int(m) - 52) * 60 + float(s)
            x = float(cal["x"].pixel(t))
        y = float(fitc.pixel(float(r["value"])))
        u = float(r["uncertainty"]) / abs(fitc.slope)
        pts.append((x, y, u, r["flags"]))
    return pts


def _draw(
    res: dict[str, Any], crop: tuple[int, int, int, int] | None, z: int
) -> Image.Image:
    img = res["img"].astype(np.uint8)
    im = Image.fromarray(img)
    if crop is None:
        crop = (0, 0, im.width, im.height)
    x0, y0, x1, y1 = crop
    im = im.crop(crop).resize(((x1 - x0) * z, (y1 - y0) * z), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    series = _csv_series(res["csv_bytes"])
    for i, (sid, rows) in enumerate(sorted(series.items())):
        ink = INK[i % len(INK)]
        pts = _points(res, sid, rows)
        xy = [((x - x0) * z + z / 2, (y - y0) * z + z / 2) for x, y, _, _ in pts]
        if len(xy) > 1:
            d.line(xy, fill=ink, width=1)
        if res["fig"]["kind"] == "category":
            for (px, py), (_, _, u, flags) in zip(xy, pts, strict=True):
                bad = "ambiguous" in flags or "identity" in flags
                col = (255, 0, 0) if bad else ink
                d.ellipse((px - 2, py - 2, px + 2, py + 2), outline=col)
                d.line((px, py - u * z, px, py + u * z), fill=col, width=1)
    return im


def _residual(res: dict[str, Any]) -> Image.Image:
    scene = res["scene"]
    model = C.render(scene)
    diff = np.abs(model - scene.img).max(axis=2) * scene.valid
    out = np.clip(255 - diff * 2, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def write_overlays(results: dict[str, Any], qa_dir: Path) -> list[Path]:
    qa_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for fid, res in results["figures"].items():
        im = _draw(res, None, 2)
        p = qa_dir / f"{fid}_overlay_full.png"
        im.save(p)
        written.append(p)
        for j, (x0, y0, x1, y1, z) in enumerate(CROPS.get(fid, [])):
            p = qa_dir / f"{fid}_overlay_zoom{j + 1}.png"
            _draw(res, (x0, y0, x1, y1), z).save(p)
            written.append(p)
        p = qa_dir / f"{fid}_model_residual.png"
        _residual(res).save(p)
        written.append(p)
        hi = res["render_600dpi"]
        p = qa_dir / f"{fid}_page_render_600dpi.png"
        hi.save(str(p))
        written.append(p)
    written.extend(_cross_check_eso(results, qa_dir))
    return written


def _cross_check_eso(results: dict[str, Any], qa_dir: Path) -> list[Path]:
    """Plot ESO Fig 7 and Fig 8 voltage resampled series together (time alignment check)."""
    f7 = results["figures"].get("ESO-p19-fig7")
    f8 = results["figures"].get("ESO-p19-fig8")
    if not f7 or not f8:
        return []
    a = f7["resampled"]["ESO-p19-fig7/Hornsea_Voltage"]
    b = f8["resampled"]["ESO-p19-fig8/Hornsea_Voltage"]
    w, h = 1200, 500
    im = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)

    def xy(t: float, v: float) -> tuple[float, float]:
        return (40 + (t - 33.0) / 1.5 * (w - 80), 20 + (430 - v) / 80 * (h - 40))

    for g in range(350, 431, 10):
        d.line((xy(33.0, g), xy(34.5, g)), fill=(220, 220, 220))
    for pts, col in ((a, (68, 114, 196)), (b, (255, 0, 255))):
        d.line([xy(p["t"], p["value"]) for p in pts], fill=col, width=1)
    p = qa_dir / "ESO-p19-fig7-vs-fig8_voltage.png"
    im.save(p)
    return [p]
