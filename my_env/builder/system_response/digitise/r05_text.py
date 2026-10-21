"""Assemble the R05 outputs: method note, calibration file, provenance, asset rows, manifest entry.

Builder-only. Everything is generated from the digitisation results so that the note, the CSVs and
the provenance always agree; the output is byte-deterministic (sorted keys, fixed rounding).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import r05_checks as K
from r05_figures import EXCLUDED, FIGURES

LABEL = "DIGITISED FROM PUBLISHED CHARTS — NOT ORIGINAL MEASUREMENT DATA"
STATUS_LINE = (
    f"STATUS: {LABEL}. Values were read from chart images in published reports; they are no more "
    "precise than the charts and every value carries an uncertainty."
)
TITLE = "Hornsea One voltage and power traces digitised from published charts, 9 August 2019"
OWNER = (
    "National Grid ESO (published report charts; Appendix D charts supplied by Ørsted)"
)
MAX_LINE = 110

SOURCE_META = {
    "ESO": {
        "title": "National Grid ESO, Technical Report on the events of 9 August 2019",
        "published": "2019-09-06",
        "licence": "No open licence stated in the document; PDF and chart images are not "
        "redistributed in the environment, only values read from the charts, with attribution.",
    },
    "APP": {
        "title": "Appendices to the Technical Report on the events of 9 August 2019 (Appendix D: "
        "Ørsted Technical Report for National Grid ESO, dated 5 September 2019)",
        "published": "2019-09-06",
        "licence": "No open licence stated in the document; PDF and chart images are not "
        "redistributed in the environment, only values read from the charts, with attribution.",
    },
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(obj: Any) -> bytes:
    return (
        json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _r(v: float, nd: int) -> float:
    out = round(float(v), nd)
    return 0.0 if out == 0 else out


def _src(
    source_id: str, page: int | None, section: str, quote: str | None, **extra: Any
) -> dict[str, Any]:
    printed = page + 1 if (source_id == "ESO" and page is not None) else None
    rec = {
        "source_id": source_id,
        "pdf_page": page,
        "printed_page": printed,
        "section": section,
        "quote": quote,
    }
    rec.update(extra)
    return rec


# ============================================================================================
# Method note (R05.txt)
# ============================================================================================


class Note:
    """Lines of R05.txt grouped into provenance segments."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.segments: list[dict[str, Any]] = []

    def add(
        self,
        lines: list[str],
        content: str,
        status: str,
        method: str,
        sources: list[dict[str, Any]],
        transformation: str | None = None,
    ) -> None:
        for line in lines:
            if len(line) > MAX_LINE or line != line.rstrip() or "\t" in line:
                raise ValueError(f"bad line ({len(line)} chars): {line!r}")
        start = len(self.lines) + 1
        self.lines.extend(lines)
        nonblank = [i for i, line in enumerate(lines, start) if line.strip()]
        if nonblank:
            self.segments.append(
                {
                    "lines": f"L{nonblank[0]}-L{nonblank[-1]}",
                    "content": content,
                    "value_status": status,
                    "extraction_method": method,
                    "transformation": transformation,
                    "sources": sources,
                }
            )

    def blank(self) -> None:
        self.lines.append("")

    def text(self) -> bytes:
        return ("\n".join(self.lines) + "\n").encode("utf-8")


def _wrap(text: str, indent: str = "", width: int = MAX_LINE) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = indent
    for w in words:
        if cur.strip() and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = indent + w
        else:
            cur = (cur + " " + w) if cur.strip() else indent + w
    if cur.strip():
        lines.append(cur)
    return lines


def _fig(fid: str) -> dict[str, Any]:
    return next(f for f in FIGURES if f["figure_id"] == fid)


def _script(section: str, script: str) -> dict[str, Any]:
    return {
        "source_id": "BUILDER",
        "pdf_page": None,
        "printed_page": None,
        "section": section,
        "quote": None,
        "script": script,
    }


def _caption_src(fig: dict[str, Any]) -> dict[str, Any]:
    return _src(fig["source_id"], fig["pdf_page"], fig["section"], fig["caption_quote"])


def _raster_src(fig: dict[str, Any], what: str) -> dict[str, Any]:
    return _src(
        fig["source_id"],
        fig["pdf_page"],
        f"{fig['short']} chart image (raster, PDF xref {fig['xref']})",
        None,
        transcribed_from_image=what,
    )


def build_note(
    results: dict[str, Any], checks: list[dict[str, Any]], script: str
) -> Note:
    figs = results["figures"]
    del checks  # the note states no comparison with report text (decision 9)
    n = Note()
    header = [
        f"DOCUMENT R05 — {TITLE}",
        f"Owner/originator: {OWNER}",
        "Record type: digitised time series (four CSV files), a calibration file and this method note",
        *_wrap(STATUS_LINE),
        "Clock reference: times are given as printed on each chart's time axis; no chart prints a time "
        "zone.",
        "The time_bst_iso column appends +01:00 (BST = UTC+01:00) to the printed time; see CLOCK BASIS.",
        "Value-status legend: [digitised] value read from a published chart by the method below; [reported]",
        "value stated in the text of a published report. Tick values, pixel sizes and fit residuals are",
        "calibration metadata and are not tagged.",
    ]
    n.add(
        header,
        "Header: title, originator, record type, STATUS label, clock basis, value legend",
        "framing",
        "framing",
        [],
    )
    n.blank()

    # ---- sources -------------------------------------------------------------------------
    lines = ["SOURCES AND LICENCE"]
    lines += _wrap(
        "ESO: National Grid ESO, Technical Report on the events of 9 August 2019 (published 6 September "
        "2019), PDF page 19 (printed page 20): Figure 7 'Voltage and Active Power at Hornsea' and Figure 8 "
        "'Voltage and Reactive Power at Hornsea', section 4.2 Generation Performance."
    )
    lines += _wrap(
        "APP: Appendices to that report, Appendix D (Ørsted Technical Report for National Grid ESO, dated "
        "5 September 2019), PDF page 40 Figure 3 and PDF page 41 Figure 4."
    )
    lines += _wrap(
        "Licence: neither document states an open licence. The PDFs and chart images are not part of this "
        "record; only values read from the charts are given, with attribution."
    )
    n.add(
        lines,
        "Source documents, figures and pages; licence status",
        "reported",
        "paraphrase",
        [_caption_src(_fig(f["figure_id"])) for f in FIGURES],
    )
    n.blank()

    # ---- files ---------------------------------------------------------------------------
    lines = [
        "FILES (delivered with this document; after retrieval in $EVIDENCE_DIR/R05/)"
    ]
    for fig in FIGURES:
        res = figs[fig["figure_id"]]
        name = fig["csv"].split("/", 1)[1]
        sids = sorted({r["series_id"] for r in res["rows"]})
        lines.append(
            f"{name}: {fig['short']}, {len(res['rows'])} data rows, {len(sids)} series."
        )
    lines.append(
        "calibration.json: per chart, the axis ticks used, fitted pixel-to-value maps and residuals,"
    )
    lines.append("the series colours and stroke widths, and the uncertainty terms.")
    n.add(
        lines,
        "Artifact list with row and series counts",
        "digitised",
        "script",
        [_script("CSV row counts", script)],
    )
    n.blank()

    lines = [
        "CSV COLUMNS (UTF-8, comma-separated, LF line endings, one header row, long format)",
        "time_as_printed: the time on the chart's own time scale, in the chart's own format (see SERIES).",
        "time_bst_iso: time_as_printed as ISO-8601 with +01:00 appended; empty where the axis does not print",
        "  an absolute time for each sample (APP Figure 3).",
        "value, unit: the digitised value [digitised] and its unit (kV, MW or MVAr).",
        "uncertainty: half-width of the plausible range of value at that time, same unit (see UNCERTAINTY).",
        "series_id: <chart id>/<legend name as printed, spaces replaced by underscores>.",
        "sample_index: category index (APP charts: 0 = first plotted sample) or resampling index (ESO charts).",
        "time_uncertainty_s: uncertainty of the printed time scale itself, in seconds (see CLOCK BASIS).",
        "flags: empty, or ';'-separated: ambiguous_overlap (stroke overlaps others of similar colour; the",
        "  uncertainty includes this), at_axis_top / at_axis_bottom (stroke touches the plot edge, so the",
        "  plotted value may be clipped).",
    ]
    n.add(lines, "Column definitions", "framing", "framing", [])
    n.blank()

    # ---- series --------------------------------------------------------------------------
    f3, f4, e7, e8 = (
        _fig(x)
        for x in ("APP-p40-fig3", "APP-p41-fig4", "ESO-p19-fig7", "ESO-p19-fig8")
    )
    lines = ["SERIES"]
    lines += _wrap(
        f"APP p40 Figure 3 (Ørsted), title as printed '{f3['title_as_printed']}', caption 'Figure 3 – Showing "
        "Voltage, Active power (MW) and Reactive power (MVAr) from Hornsea One at the time of the de-load'. "
        "The report text says it shows the NETS voltage in the 400kV substation [reported]. Five traces: "
        "HOW V1, HOW V2, HOW V3 (voltage, left axis 'Voltage (kV)'; phase or line quantity not stated), HOW "
        "active MW and HOW reactive MVAr (right axis titled 'Reactive power (MVArs)', used for both). 70 "
        "plotted samples on a category axis labelled to 0.1 s ('52:33.0' ... '52:34.3', five samples per "
        "label); file app_p40_fig3_onshore.csv."
    )
    n.add(
        lines,
        "APP Figure 3: what the series are (titles, legends, axis titles transcribed from the chart image)",
        "reported",
        "transcription",
        [
            _caption_src(f3),
            _src("APP", 40, f3["section"], f3["measurement_point_quote"]),
            _raster_src(
                f3,
                f"title '{f3['title_as_printed']}'; legends HOW V1/V2/V3, HOW active MW, HOW reactive "
                "MVAr; axes 'Voltage (kV)', 'Reactive power (MVArs)', 'Time (mm:ss:milli)'",
            ),
        ],
    )
    lines = _wrap(
        f"APP p41 Figure 4 (Ørsted), title as printed '{f4['title_as_printed']}', caption 'Figure 4 – The de-load "
        "of Hornsea 1B due to overcurrent at the WTGs'. The report text says it depicts the offshore conditions "
        "at Hornsea 1B (circuit Z12) [reported]. Digitised: kV_PPM1_AVE ... kV_PPM4_AVE (34 kV collection-system "
        "voltage per PPM, left axis 'Voltage (kV)') and MW_OFS (right axis 'Active and Reactive Power "
        "(MW/MVAr)'; the abbreviation is not defined in the report). 79 plotted samples, each labelled with a "
        "time to the millisecond ('16:52:33.211' ... '16:52:33.999', spacing 9-11 ms); file "
        "app_p41_fig4_offshore_1b.csv."
    )
    n.add(
        lines,
        "APP Figure 4: what the series are",
        "reported",
        "transcription",
        [
            _caption_src(f4),
            _src("APP", 41, f4["section"], f4["measurement_point_quote"]),
            _raster_src(
                f4,
                f"title '{f4['title_as_printed']}'; legends kV_PPM1_AVE..kV_PPM4_AVE, MW_OFS, "
                "MVAr_PPM1..MVAr_PPM4; axes 'Voltage (kV)', 'Active and Reactive Power (MW/MVAr)', "
                "'Time (hh:mm:ss:msms)'",
            ),
        ],
    )
    lines = _wrap(
        "ESO p19 Figure 7 'Voltage and Active Power at Hornsea' and Figure 8 'Voltage and Reactive Power at "
        "Hornsea'. The ESO text describes the reaction 'as seen at the onshore connection point' [reported]. "
        "Figure 7: Hornsea Voltage (left axis 'Voltage (kV)') and Total Active Power (right axis 'Active Power "
        "(MW)'); Figure 8: Total Reactive Power (right axis printed 'Rective Power (MVAr)'). Continuous time "
        "axes with ticks every 0.25 s ('16:52:33.25' ... '16:52:34.25'); the logger's sample interval is not "
        "visible. Resampled every 5 ms from 16:52:33.005 to 16:52:34.485 (axis readings); files "
        "eso_p19_fig7_voltage_active_power.csv and eso_p19_fig8_reactive_power.csv."
    )
    n.add(
        lines,
        "ESO Figures 7 and 8: what the series are",
        "reported",
        "transcription",
        [
            _caption_src(e7),
            _caption_src(e8),
            _src(
                "ESO",
                18,
                "4.2 Generation Performance – Hornsea",
                e7["measurement_point_quote"],
            ),
            _raster_src(
                e7,
                "legends 'Hornsea Voltage', 'Total Active Power'; axes 'Voltage (kV)', "
                "'Active Power (MW)', 'Time'; tick labels 16:52:33.25 ... 16:52:34.25",
            ),
            _raster_src(
                e8,
                "legends 'Hornsea Voltage', 'Total Reactive Power'; right axis 'Rective Power "
                "(MVAr)'",
            ),
        ],
    )
    n.blank()

    # ---- method --------------------------------------------------------------------------
    lines = ["METHOD"]
    lines += _wrap(
        "1. Each chart's embedded raster image was extracted losslessly from the PDF with PyMuPDF at its native "
        "resolution (APP Figure 3 about 196 dpi, Figure 4 about 223 dpi, ESO Figure 7 about 150 dpi, Figure "
        "8 about 96 dpi on the page). A MuPDF render of the same page region agrees with the raster apart "
        "from resampling at line edges, so nothing else on the page (clip paths, vector drawings) alters the "
        "chart. Rendering at a higher resolution only interpolates these pixels and adds no information."
    )
    lines += _wrap(
        "2. Axes were calibrated from their printed ticks: tick positions measured in the image (gridlines, or "
        "the centres of the tick labels where the axis has no gridlines), tick values as printed, and a "
        "least-squares straight line fitted per axis (at least five ticks per axis; residuals under "
        "CALIBRATION)."
    )
    lines += _wrap(
        "3. Curves were extracted by colour. Each series' colour and stroke width were measured from its "
        "legend swatch. Call-out boxes, arrows and dashed lines (drawn on top of the charts) were masked; "
        "gridlines were modelled as background. The chart was then re-drawn from candidate vertex positions "
        "with every series in legend order (later series on top) and the positions chosen that best reproduce "
        "the image: dynamic programming over stroke positions found in the image, then refinement to "
        "0.05 px. For the APP charts the vertices are the plotted samples; for the ESO charts one vertex per "
        "pixel column, resampled every 5 ms (about one stroke width)."
    )
    lines += _wrap(
        "4. Checks: the digitised values were drawn back onto the source images and inspected; ESO Figure 7 "
        "and Figure 8 voltages (the same quantity) were digitised independently and agree. No digitised "
        "value was adjusted to agree with any value stated in a report's text."
    )
    n.add(
        lines,
        "Digitisation method",
        "digitised",
        "script",
        [_script("extraction, calibration, analysis-by-synthesis fit, QA", script)],
    )
    n.blank()

    # ---- calibration ---------------------------------------------------------------------
    lines = [
        "CALIBRATION (rms residual of the straight-line fit through the printed ticks)"
    ]
    for fig in FIGURES:
        cal = figs[fig["figure_id"]]["cal"]
        la, ra = fig["left_axis"], fig["right_axis"]
        lu = la["unit"]
        ru = (
            "MW/MVAr" if " or " in ra["unit"] else ra["unit"]
        )  # Fig 3/4: shared by MW and MVAr
        parts = [
            f"left {len(cal['left'].px)} ticks, {abs(cal['left'].slope):.4g} {lu}/px, rms {cal['left'].rms:.2g} {lu}",
            f"right {len(cal['right'].px)} ticks, {abs(cal['right'].slope):.3g} {ru}/px, rms {cal['right'].rms:.2g} {ru}",
        ]
        if fig["kind"] == "category":
            parts.append(
                f"x {fig['x_axis']['n_categories']} labels, {abs(1 / cal['x'].slope):.2f} px/sample, rms "
                f"{cal['x_px_rms']:.2f} px"
            )
        else:
            parts.append(
                f"time 5 ticks, {1000 * abs(cal['x'].slope):.2f} ms/px, rms {1000 * cal['x'].rms:.2f} ms"
            )
        lines += _wrap(f"{fig['short']}: " + "; ".join(parts) + ".")
    n.add(
        lines,
        "Calibration fit summary per chart",
        "digitised",
        "script",
        [_script("axis calibration", script)],
    )
    n.blank()

    # ---- uncertainty ---------------------------------------------------------------------
    lines = ["UNCERTAINTY"]
    lines += _wrap(
        "The uncertainty column combines in quadrature, in pixels converted to the series' unit: the axis "
        "fit's rms residual; half the stroke width (the plotted value lies somewhere within the drawn "
        "line); colour ambiguity (the half-width of the range of positions that reproduce the image about "
        "as well as the chosen one: small for a clearly visible stroke, large where strokes of similar "
        "colour overlap or an annotation hides the line); and the local slope times the time-axis fit "
        "residual. It does not include the uncertainty of the time scale itself (time_uncertainty_s) or any "
        "error in the original measurement."
    )
    for fig in FIGURES:
        res = figs[fig["figure_id"]]
        parts = []
        for unit in ("kV", "MW", "MVAr"):
            u = [float(r["uncertainty"]) for r in res["rows"] if r["unit"] == unit]
            if u:
                parts.append(f"{unit} median {np.median(u):.2g}, max {max(u):.2g}")
        lines += _wrap(f"{fig['short']}: " + "; ".join(parts) + ".")
    n.add(
        lines,
        "Uncertainty model and its range per chart",
        "digitised",
        "script",
        [_script("uncertainty terms", script)],
    )
    n.blank()

    # ---- clock basis ---------------------------------------------------------------------
    lines = ["CLOCK BASIS"]
    lines += _wrap(
        "No chart prints a time zone, and no chart states which recorder or clock produced its time scale "
        "or how that clock was synchronised. APP Figure 3 prints only minutes, seconds and tenths "
        "('52:33.0'); the hour comes from its title ('16:52'). Five consecutive samples share each label, so "
        "a sample's time is known only to about 0.1 s from its label; the labels do not say whether they are "
        "truncated or rounded. The spacing of about 20 ms per sample is an inference from five samples per "
        "0.1 s label, not printed. time_bst_iso is left empty for this chart."
    )
    lines += _wrap(
        "APP Figure 4 prints a time to the millisecond for every sample, with hour 16."
    )
    lines += _wrap(
        "ESO Figures 7 and 8 print tick labels to 0.01 s, with hour 16; times between ticks are read from "
        "the fitted scale. In time_bst_iso the printed hour is read as BST; this is an interpretation, not "
        "a statement on the charts."
    )
    n.add(
        lines,
        "Clock basis of each chart as printed and the BST reading used in time_bst_iso",
        "digitised",
        "transcription",
        [
            _raster_src(
                f3,
                "title 'Hornsea - 16:52, 9th August 2019'; x labels '52:33.0' ... '52:34.3' (5 each)",
            ),
            _raster_src(f4, "x labels '16:52:33.211' ... '16:52:33.999'"),
            _raster_src(
                e7,
                "tick labels 16:52:33.25, 16:52:33.50, 16:52:33.75, 16:52:34.00, 16:52:34.25",
            ),
            _raster_src(
                e8,
                "tick labels 16:52:33.25, 16:52:33.50, 16:52:33.75, 16:52:34.00, 16:52:34.25",
            ),
        ],
        transformation="Catalogue transcription of the category labels (extracted/*_timebase.csv) re-read "
        "visually against the native rasters for this build. Only what each chart prints is stated; "
        "comparisons with times written in report text are left to the reader (decision 9).",
    )
    n.blank()

    # ---- not digitised -------------------------------------------------------------------
    lines = ["NOT DIGITISED"]
    hidden = [
        v["k"]
        for s in figs["APP-p40-fig3"]["series"]
        if s["spec"]["legend"] == "HOW reactive MVAr"
        for v in s["vertices"]
        if "occluded" in v["flags"]
    ]
    lines += _wrap(
        f"APP Figure 3, HOW reactive MVAr samples {hidden[0]}-{hidden[-1]}: hidden behind the border of a "
        "call-out box drawn on the chart; omitted from the CSV."
    )
    for ex in EXCLUDED:
        lines += _wrap(
            f"{_fig(ex['figure_id'])['short']}, {', '.join(ex['series'])}: {ex['reason']}"
        )
    n.add(
        lines,
        "Series and samples deliberately not digitised, with reasons",
        "digitised",
        "script",
        [_script("occlusion and exclusion decisions", script)],
    )
    n.blank()

    lines = [
        "CITING THIS RECORD",
        "This note: L<n> or L<a>-L<b> using the line numbers shown when the document is retrieved.",
        "Summary readings from these series are also available as HORNSEA-ONE asset-log rows (evidence R05),",
        "cited as event:<event_id>. CSV values: cite the line of this note that describes the series and give",
        "the file, series_id and time_as_printed in the finding.",
    ]
    n.add(lines, "Citation help", "framing", "framing", [])
    return n


# ============================================================================================
# calibration.json
# ============================================================================================


def calibration_doc(results: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "evidence_id": "R05",
        "note": "Pixel coordinates refer to each chart's native embedded raster (origin top-left, y down).",
        "uncertainty_model": "uncertainty = |axis slope| * sqrt(axis_rms_px^2 + (stroke_width/2)^2 + "
        "colour_ambiguity_px^2 + (local_slope * time_axis_rms_px)^2)",
        "charts": [],
    }
    for fig in FIGURES:
        res = results["figures"][fig["figure_id"]]
        cal = res["cal"]
        axes = {
            "left": {
                "title_as_printed": fig["left_axis"]["title_as_printed"],
                "tick_positions": "gridlines",
                **cal["left"].as_dict(),
            },
            "right": {
                "title_as_printed": fig["right_axis"]["title_as_printed"],
                "tick_positions": "label centres shifted by the left axis's label-to-gridline offset "
                f"({cal['label_offset_px']:.2f} px)",
                **cal["right"].as_dict(),
                "check_value_at_top_and_bottom_gridline": [
                    cal["right_extent_check"]["right_value_at_top_gridline"],
                    cal["right_extent_check"]["right_value_at_bottom_gridline"],
                ],
            },
        }
        for side in ("left", "right"):
            dun = fig[f"{side}_axis"].get("display_unit_as_printed")
            if dun:
                axes[side]["display_unit_as_printed"] = dun
        if fig["kind"] == "category":
            xd = cal["x"].as_dict()
            axes["x"] = {
                "title_as_printed": fig["x_axis"]["title_as_printed"],
                "type": "category (samples drawn equally spaced; timestamps are labels only)",
                "tick_positions": "centres of the rotated category labels",
                "model": "sample_index = intercept + slope * pixel",
                "slope_per_px": xd["slope_per_px"],
                "intercept": xd["intercept"],
                "n_ticks": xd["n_ticks"],
                "rms_residual_samples": xd["rms_residual"],
                "rms_residual_px": round(cal["x_px_rms"], 4),
                "first_and_last_label_as_printed": [
                    res["labels"][0],
                    res["labels"][-1],
                ],
                "data_implied_offset_check_px": res["x_offset_check"]["best_offset_px"],
            }
        else:
            xd = cal["x"].as_dict()
            axes["x"] = {
                "title_as_printed": fig["x_axis"]["title_as_printed"],
                "type": "time scale",
                "tick_positions": "vertical gridlines under the printed labels",
                "model": "seconds after 16:52:00 (as printed) = intercept + slope * pixel",
                **{k: v for k, v in xd.items() if k != "model"},
                "ticks_as_printed": fig["x_axis"]["ticks_as_printed"],
                "label_rounding_s": fig["x_axis"]["label_rounding_s"],
                "resampling_step_s": fig["x_axis"]["step_s"],
            }
        series = []
        for s in res["series"]:
            spec = s["spec"]
            sw = res["scene_info"]["swatches"][spec["legend"]]
            entry = {
                "legend_as_printed": spec["legend"],
                "series_id": spec["series_id"],
                "axis": spec["axis"],
                "unit": spec["unit"],
                "quantity": spec["quantity"],
                "colour_rgb": sw["colour_rgb"],
                "stroke_width_px": sw["stroke_width_px"],
                "written_to_csv": spec.get("output", True),
            }
            series.append(entry)
        out["charts"].append(
            {
                "chart_id": fig["figure_id"],
                "source": f"{fig['source_id']} PDF page {fig['pdf_page']}",
                "caption_as_printed": fig["caption_quote"],
                "title_as_printed": fig["title_as_printed"],
                "csv": fig["csv"].split("/", 1)[1],
                "native_raster_px": res["image"]["native_px"],
                "native_raster_dpi_on_page": res["image"]["native_dpi"],
                "axes": axes,
                "series": series,
                "annotation_boxes_masked_px": res["scene_info"]["boxes"],
            }
        )
    return out


# ============================================================================================
# Asset rows (fragment for the integration step)
# ============================================================================================

# (check_id, signal, what the value is). Signal names are public (the catalogue lists each
# log's signals), so they name the series only; what the value is goes into the row text.
ROW_SPECS = [
    (
        "F3-MW-pre",
        "active power, APP p40 Fig 3 (digitised)",
        "Level before the disturbance",
    ),
    (
        "F3-MW-dip",
        "active power, APP p40 Fig 3 (digitised)",
        "Lowest plotted sample during the oscillation",
    ),
    (
        "F3-MW-post",
        "active power, APP p40 Fig 3 (digitised)",
        "Level after the de-load",
    ),
    (
        "F3-Q-pre",
        "reactive power, APP p40 Fig 3 (digitised)",
        "Level before the disturbance",
    ),
    (
        "F3-Q-min",
        "reactive power, APP p40 Fig 3 (digitised)",
        "Most negative plotted sample",
    ),
    (
        "F4-MW-pre",
        "offshore active power MW_OFS, APP p41 Fig 4 (digitised)",
        "Hornsea 1B (T_HOWAO-2), level before the disturbance",
    ),
    (
        "F4-kV-min",
        "offshore 34 kV collection-system voltage, APP p41 Fig 4 (digitised)",
        "Hornsea 1B, lowest sample over PPM1-PPM4",
    ),
    (
        "F4-MW-post",
        "offshore active power MW_OFS, APP p41 Fig 4 (digitised)",
        "Hornsea 1B (T_HOWAO-2), level after the de-load",
    ),
    (
        "E7-V-onset",
        "voltage, ESO p19 Fig 7 (digitised)",
        "First fall of more than 1 kV below the pre-event level",
    ),
    (
        "E8-Q-pre",
        "total reactive power, ESO p19 Fig 8 (digitised)",
        "Level before the disturbance",
    ),
]

CLOCK = {
    "APP-p40-fig3": "As printed on APP p40 Figure 3: axis labels mm:ss.t, five samples per label; hour '16:52' "
    "from the chart title; no time zone printed. Index time reads the labels as BST, sample k at "
    "16:52:33.000 + 0.020k (an inference; labels may be truncated or rounded).",
    "APP-p41-fig4": "As printed on APP p41 Figure 4: per-sample labels hh:mm:ss.mmm with hour 16; no time zone "
    "printed. Index time reads the labels as BST (an interpretation). The chart does not state which "
    "recorder or clock produced its time scale.",
    "ESO-p19-fig7": "As read from the ESO p19 Figure 7 time scale (tick labels hh:mm:ss.ss); no time zone "
    "printed. Index time reads the scale as BST (an interpretation).",
    "ESO-p19-fig8": "As read from the ESO p19 Figure 8 time scale (tick labels hh:mm:ss.ss); no time zone "
    "printed. Index time reads the scale as BST (an interpretation).",
}


def _ranges(ks: list[int]) -> str:
    """'0-3, 19-22' style list of sample indices."""
    out: list[str] = []
    ks = sorted(ks)
    start = prev = ks[0]
    for k in ks[1:] + [None]:  # type: ignore[list-item]
        if k is not None and k == prev + 1:
            prev = k
            continue
        out.append(str(start) if start == prev else f"{start}-{prev}")
        if k is not None:
            start = prev = k
    return ", ".join(out)


def _utc(sec_after_1652: float) -> str:
    base = datetime(2019, 8, 9, 15, 52, 0, tzinfo=UTC)
    t = base + timedelta(seconds=round(sec_after_1652, 3))
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def asset_rows(results: dict[str, Any], checks: list[dict[str, Any]]) -> bytes:
    by_check = {c["check_id"]: c for c in checks}
    lines = []
    for i, (cid, signal, what) in enumerate(ROW_SPECS, 1):
        c = by_check[cid]
        fid = c["series_id"].split("/")[0]
        fig = _fig(fid)
        res = results["figures"][fid]
        unit = c["unit"]
        if cid == "E7-V-onset":
            t = c["digitised_value"]
            recorded = c["digitised_value_as_printed"] + " (read from the axis scale)"
            idx_t, idx_u = t, float(res["rows"][0]["time_uncertainty_s"])
            value, unit = c["threshold_kV"], "kV"
            text = (
                f"Digitised from ESO p19 Figure 7 (Hornsea Voltage): the trace first falls more than 1 kV below its "
                f"pre-event level of {c['pre_event_level_kV']:.1f} kV at {c['digitised_value_as_printed']} on the "
                "chart's time scale [digitised]. Read from a published chart image; not an original record."
            )
        else:
            first, last = c["times_as_printed"]
            if fid == "APP-p40-fig3":
                ks = c["samples"]
                t0, t1 = 33.0 + 0.02 * min(ks), 33.0 + 0.02 * max(ks)
                tu = 0.1
            else:
                t0, t1 = K.axis_seconds(first), K.axis_seconds(last)
                tu = float(res["rows"][0]["time_uncertainty_s"])
            idx_t = (t0 + t1) / 2
            idx_u = (t1 - t0) / 2 + tu
            recorded = first if first == last else f"{first} to {last}"
            recorded += (
                " (axis labels as printed)"
                if fid.startswith("APP")
                else " (read from the axis scale)"
            )
            value, unc = c["digitised_value"], c["digitised_uncertainty"]
            how = "median of samples" if len(c["samples"]) > 1 else "sample"
            krange = _ranges(c["samples"])
            sid = c["series_id"]
            text = (
                f"{what}. Digitised from {fig['short']}: {how} {krange} of '{sid}' = {value:g} +/- {unc:g} {unit} "
                "[digitised]. Read from a published chart image; not an original record."
            )
        lines.append(
            {
                "kind": "asset",
                "event_id": f"R05-HOW-{i:03d}",
                "evidence_id": "R05",
                "asset_id": "HORNSEA-ONE",
                "recorded_time": recorded,
                "clock_basis": CLOCK[fid],
                "index_time_utc": _utc(idx_t),
                "index_uncertainty_s": round(idx_u, 4),
                "signal": signal,
                "value": value,
                "unit": unit,
                "text": text,
                "value_status": "digitised",
                "provenance": {
                    "check_id": cid,
                    "chart_id": fid,
                    "source_id": fig["source_id"],
                    "pdf_page": fig["pdf_page"],
                    "csv": fig["csv"],
                    "series_id": c["series_id"],
                    "samples": c.get("samples"),
                    "builder": "builder/system_response/digitise/build_r05.py",
                },
            }
        )
    return "".join(
        json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in lines
    ).encode("utf-8")


# ============================================================================================
# Provenance, manifest fragment
# ============================================================================================


def assemble(
    results: dict[str, Any], builder_version: str, script: str
) -> dict[str, bytes]:
    csvs = {fid: res["csv_bytes"] for fid, res in results["figures"].items()}
    checks = K.run_checks(csvs)
    f7 = results["figures"]["ESO-p19-fig7"]["resampled"]["ESO-p19-fig7/Hornsea_Voltage"]
    f8 = results["figures"]["ESO-p19-fig8"]["resampled"]["ESO-p19-fig8/Hornsea_Voltage"]
    cross = K.voltage_cross_check(f7, f8)
    onset_sens = {
        f"drop_{d}_kV": round(
            K.onset_time(
                K.parse_csv(csvs["ESO-p19-fig7"])["ESO-p19-fig7/Hornsea_Voltage"],
                drop=d,
            )["t"],
            4,
        )
        for d in (0.5, 1.0, 2.0)
    }
    note = build_note(results, checks, script)
    text = note.text()
    calib = _json(calibration_doc(results))
    rows = asset_rows(results, checks)
    artifacts: dict[str, Any] = {}
    for fig in FIGURES:
        res = results["figures"][fig["figure_id"]]
        artifacts[fig["csv"]] = {
            "extraction_method": "script",
            "value_status": "digitised",
            "script": script,
            "sha256": _sha(res["csv_bytes"]),
            "rows": len(res["rows"]),
            "series": sorted({r["series_id"] for r in res["rows"]}),
            "sources": [_caption_src(fig)],
            "image": res["image"],
            "transformation": "native raster -> axis calibration from printed ticks -> analysis-by-synthesis "
            "polyline fit -> per-sample value and uncertainty"
            + (" -> resampled every 5 ms" if fig["kind"] == "continuous" else ""),
            "category_labels": (
                {
                    "file": "source_catalogue/" + fig["x_axis"]["timebase_csv"],
                    "sha256": res["labels_sha256"],
                }
                if fig["kind"] == "category"
                else None
            ),
            "fit": {
                "sweeps": res["fit"]["sweeps"],
                "x_offset_check": res["x_offset_check"],
                "vertices_flagged": _flag_counts(res),
            },
        }
    artifacts["R05/calibration.json"] = {
        "extraction_method": "script",
        "value_status": "digitised",
        "script": script,
        "sha256": _sha(calib),
        "sources": [_caption_src(f) for f in FIGURES],
    }
    provenance = {
        "evidence_id": "R05",
        "bundle": "system_response",
        "builder_version": builder_version,
        "generated_by": script,
        "label": LABEL,
        "sources": {
            **{
                sid: {**SOURCE_META[sid], **meta}
                for sid, meta in sorted(results["sources"].items())
            },
            "BUILDER": {
                "kind": "script",
                "file": script,
                "title": "R05 digitisation builder (with r05_core.py, r05_figures.py, "
                "r05_checks.py, r05_text.py)",
                "builder_version": builder_version,
            },
            "SOURCE-CATALOGUE": {
                "kind": "builder_input",
                "title": "Source catalogue transcription of the category-axis labels "
                "(re-read visually against the native rasters)",
                "files": {
                    "source_catalogue/" + f["x_axis"]["timebase_csv"]: results[
                        "figures"
                    ][f["figure_id"]]["labels_sha256"]
                    for f in FIGURES
                    if f["kind"] == "category"
                },
            },
        },
        "documents": {
            "R05": {
                "label": LABEL,
                "text_file": "R05/R05.txt",
                "text_sha256": _sha(text),
                "line_count": len(note.lines),
                "construction": "Generated by the builder from the digitisation results. Values in the CSVs are "
                "read from four raster charts in the ESO report and its Appendix D (Ørsted); nothing is "
                "reconstructed or invented. The note describes the series, the method, calibration, "
                "uncertainty, clock basis as printed and exclusions. Comparisons of the digitised values with "
                "values and times stated in report text (validation.landmark_checks) are kept in this "
                "provenance only: the agent compares the records itself (decision 9; decision 20 conflicts "
                "stay discoverable from R05 against S01, R03 and S07).",
                "segments": note.segments,
                "artifacts": artifacts,
            }
        },
        "validation": {
            "landmark_checks": checks,
            "eso_fig7_vs_fig8_voltage": cross,
            "voltage_onset_threshold_sensitivity_s_after_1652": onset_sens,
            "qa_overlays": "written to GB_DIGITISE_QA_DIR (default <workspace>/.context/digitise_qa); "
            "inspected visually",
            "excluded": EXCLUDED,
        },
        "rows_fragment": {
            "file": "builder/system_response/rows/r05_hornsea_traces.jsonl",
            "sha256": _sha(rows),
            "rows": rows.count(b"\n"),
        },
    }
    manifest_fragment = {
        "doc_id": "R05",
        "title": TITLE,
        "owner": OWNER,
        "date": "2019-08-09",
        "category": "measurement_data",
        "text_file": "R05/R05.txt",
        "artifacts": [
            {
                "file": "R05/R05.txt",
                "media_type": "text/plain",
                "description": "Method note: series, method, calibration, uncertainty, clock basis, exclusions",
            },
            *[
                {
                    "file": f["csv"],
                    "media_type": "text/csv",
                    "description": f"Values digitised from {f['short']} (long format: one row per series and "
                    "sample, with uncertainty)",
                }
                for f in FIGURES
            ],
            {
                "file": "R05/calibration.json",
                "media_type": "application/json",
                "description": "Axis calibration, series colours and stroke widths, uncertainty model",
            },
        ],
        "sha256": {
            "R05/R05.txt": _sha(text),
            **{
                f["csv"]: _sha(results["figures"][f["figure_id"]]["csv_bytes"])
                for f in FIGURES
            },
            "R05/calibration.json": _sha(calib),
        },
        "note": "No 'timeseries' descriptor: the CSVs are long-format (several series, repeated times) and APP "
        "Figure 3 has no absolute per-sample time.",
    }
    return {
        "text": text,
        "calibration": calib,
        "provenance": _json(provenance),
        "rows": rows,
        "manifest_fragment": _json(manifest_fragment),
    }


def _flag_counts(res: dict[str, Any]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for s in res["series"]:
        counts: dict[str, int] = {}
        for v in s["vertices"]:
            for f in v["flags"]:
                counts[f] = counts.get(f, 0) + 1
        out[s["spec"]["series_id"]] = dict(sorted(counts.items()))
    return out
