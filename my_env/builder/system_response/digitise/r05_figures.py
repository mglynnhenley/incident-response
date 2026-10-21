"""Figure specifications for R05 (Hornsea traces digitised from published charts).

Builder-only constants. Pixel bands are in the native embedded raster of each chart (origin
top-left, y down) and only tell the detectors where to look; tick POSITIONS are measured from the
image (gridlines or label centres), tick VALUES are transcribed from the printed axis labels and
were checked visually against the native raster. The category labels of the two Ørsted charts
come from the source-catalogue transcription (``extracted/*_timebase.csv``), re-read visually for
this build, and are cross-checked in code for count and format.
"""

from __future__ import annotations

from typing import Any

DATE = "2019-08-09"

# Source documents (ids as in the handoff source_manifest.json).
SOURCES = {
    "ESO": "builder_only/sources/ESO_technical_report_2019.pdf",
    "APP": "builder_only/sources/ESO_appendices_2019.pdf",
}

FIGURES: list[dict[str, Any]] = [
    {
        "figure_id": "APP-p40-fig3",
        "csv": "R05/app_p40_fig3_onshore.csv",
        "source_id": "APP",
        "pdf_page": 40,
        "xref": 142,
        "native_px": [1233, 743],
        "kind": "category",
        "short": "APP p40 Figure 3",
        "section": "Appendix D – Hornsea Technical Report submitted by Ørsted (dated 5 September 2019)",
        "title_as_printed": "Hornsea - 16:52, 9th August 2019",
        "caption_quote": "Figure 3 – Showing Voltage, Active power (MW) and Reactive power (MVAr) from "
        "Hornsea One at the time of the de-load",
        "measurement_point_quote": "Figure 3 (above) shows NETS voltage in the 400kV substation",
        "plot_rows": [44, 633],
        "plot_cols": [85, 1142],
        "left_axis": {
            "title_as_printed": "Voltage (kV)",
            "display_unit_as_printed": "Thousands",
            "unit": "kV",
            "ticks_as_printed": [420, 410, 400, 390, 380, 370, 360, 350],
            "gridline_band": [40, 632],
            "gridline_span": [100, 1130],
            "label_band": [57, 78],
            "label_span": [40, 640],
        },
        "right_axis": {
            "title_as_printed": "Reactive power (MVArs)",
            "display_unit_as_printed": "Millions",
            "unit": "MW or MVAr (see series)",
            "ticks_as_printed": list(range(1500, -601, -100)),
            "label_band": [1151, 1177],
            "label_span": [40, 640],
        },
        "x_axis": {
            "title_as_printed": "Time (mm:ss:milli)",
            "label_band": [631, 668],
            "label_span": [80, 1150],
            "n_categories": 70,
            "timebase_csv": "extracted/APP-p40-fig3_timebase.csv",
            "label_pattern": r"^52:3[34]\.\d$",
            "time_uncertainty_s": 0.1,
        },
        "legend_swatches": {
            "HOW V1": [326, 350, 711, 720],
            "HOW V2": [423, 448, 711, 720],
            "HOW V3": [521, 545, 711, 720],
            "HOW active MW": [618, 644, 711, 720],
            "HOW reactive MVAr": [764, 789, 711, 720],
        },
        "series": [
            {
                "legend": "HOW V1",
                "series_id": "APP-p40-fig3/HOW_V1",
                "axis": "left",
                "unit": "kV",
                "quantity": "onshore 400 kV substation voltage, trace 'HOW V1' (phase or line not stated)",
            },
            {
                "legend": "HOW V2",
                "series_id": "APP-p40-fig3/HOW_V2",
                "axis": "left",
                "unit": "kV",
                "quantity": "onshore 400 kV substation voltage, trace 'HOW V2' (phase or line not stated)",
            },
            {
                "legend": "HOW V3",
                "series_id": "APP-p40-fig3/HOW_V3",
                "axis": "left",
                "unit": "kV",
                "quantity": "onshore 400 kV substation voltage, trace 'HOW V3' (phase or line not stated)",
            },
            {
                "legend": "HOW active MW",
                "series_id": "APP-p40-fig3/HOW_active_MW",
                "axis": "right",
                "unit": "MW",
                "quantity": "Hornsea One active power (plotted against the right axis titled "
                "'Reactive power (MVArs)')",
            },
            {
                "legend": "HOW reactive MVAr",
                "series_id": "APP-p40-fig3/HOW_reactive_MVAr",
                "axis": "right",
                "unit": "MVAr",
                "quantity": "Hornsea One reactive power (sign convention not printed on the chart)",
            },
        ],
        "box_fill": [64, 153, 218],
    },
    {
        "figure_id": "APP-p41-fig4",
        "csv": "R05/app_p41_fig4_offshore_1b.csv",
        "source_id": "APP",
        "pdf_page": 41,
        "xref": 145,
        "native_px": [1402, 797],
        "kind": "category",
        "short": "APP p41 Figure 4",
        "section": "Appendix D – Hornsea Technical Report submitted by Ørsted (dated 5 September 2019)",
        "title_as_printed": "Hornsea 1B - De-load event, voltage vs MW vs MVAr",
        "caption_quote": "Figure 4 – The de-load of Hornsea 1B due to overcurrent at the WTGs",
        "measurement_point_quote": "Figure 4 (below) depicts the offshore conditions at Hornsea 1B "
        "(circuit Z12)",
        "plot_rows": [36, 668],
        "plot_cols": [50, 1338],
        "left_axis": {
            "title_as_printed": "Voltage (kV)",
            "display_unit_as_printed": None,
            "unit": "kV",
            "ticks_as_printed": [40, 35, 30, 25, 20, 15, 10, 5, 0],
            "gridline_band": [30, 670],
            "gridline_span": [70, 1330],
            "label_band": [24, 41],
            "label_span": [30, 672],
        },
        "right_axis": {
            "title_as_printed": "Active and Reactive Power (MW/MVAr)",
            "display_unit_as_printed": None,
            "unit": "MW or MVAr (see series)",
            "ticks_as_printed": list(range(450, -101, -50)),
            "label_band": [1346, 1370],
            "label_span": [30, 672],
        },
        "x_axis": {
            "title_as_printed": "Time (hh:mm:ss:msms)",
            "label_band": [669, 731],
            "label_span": [45, 1345],
            "n_categories": 79,
            "timebase_csv": "extracted/APP-p41-fig4_timebase.csv",
            "label_pattern": r"^16:52:33\.\d{3}$",
            "time_uncertainty_s": 0.0005,
        },
        "legend_swatches": {
            "kV_PPM1_AVE": [225, 251, 771, 780],
            "kV_PPM2_AVE": [339, 366, 771, 780],
            "kV_PPM3_AVE": [453, 479, 771, 780],
            "kV_PPM4_AVE": [567, 593, 771, 780],
            "MW_OFS": [682, 708, 771, 780],
            "MVAr_PPM1": [771, 797, 771, 780],
            "MVAr_PPM2": [876, 902, 771, 780],
            "MVAr_PPM3": [982, 1007, 771, 780],
            "MVAr_PPM4": [1086, 1112, 771, 780],
        },
        "series": [
            {
                "legend": f"kV_PPM{i}_AVE",
                "series_id": f"APP-p41-fig4/kV_PPM{i}_AVE",
                "axis": "left",
                "unit": "kV",
                "quantity": f"Hornsea 1B offshore 34 kV collection-system voltage, PPM{i} "
                "('_AVE' as printed; averaging not stated)",
            }
            for i in (1, 2, 3, 4)
        ]
        + [
            {
                "legend": "MW_OFS",
                "series_id": "APP-p41-fig4/MW_OFS",
                "axis": "right",
                "unit": "MW",
                "quantity": "Hornsea 1B active power 'MW_OFS' (abbreviation not defined in the report)",
            }
        ]
        + [
            {
                "legend": f"MVAr_PPM{i}",
                "series_id": f"APP-p41-fig4/MVAr_PPM{i}",
                "axis": "right",
                "unit": "MVAr",
                "quantity": f"Hornsea 1B reactive power, PPM{i} (sign convention not printed)",
                # Kept in the re-drawn chart (their strokes cover the other series) but not
                # written out: see EXCLUDED below.
                "output": False,
            }
            for i in (1, 2, 3, 4)
        ],
        "box_fill": [58, 156, 222],
    },
    {
        "figure_id": "ESO-p19-fig7",
        "csv": "R05/eso_p19_fig7_voltage_active_power.csv",
        "source_id": "ESO",
        "pdf_page": 19,
        "xref": 55,
        "native_px": [1007, 565],
        "kind": "continuous",
        "short": "ESO p19 Figure 7",
        "section": "4.2 Generation Performance – Hornsea",
        "title_as_printed": "Hornsea Voltage and Active Power",
        "caption_quote": "Figure 7 – Voltage and Active Power at Hornsea",
        "measurement_point_quote": "the reaction of Hornsea wind farm as seen at the onshore connection point",
        "measurement_point_page": 18,
        "plot_rows": [92, 410],
        "plot_cols": [102, 900],
        "left_axis": {
            "title_as_printed": "Voltage (kV)",
            "display_unit_as_printed": None,
            "unit": "kV",
            "ticks_as_printed": [430, 420, 410, 400, 390, 380, 370, 360, 350],
            "gridline_band": [80, 420],
            "gridline_span": [110, 890],
            "label_band": [54, 87],
            "label_span": [80, 420],
        },
        "right_axis": {
            "title_as_printed": "Active Power (MW)",
            "display_unit_as_printed": None,
            "unit": "MW",
            "ticks_as_printed": [900, 800, 700, 600, 500, 400, 300, 200, 100, 0],
            "label_band": [916, 948],
            "label_span": [80, 420],
        },
        "x_axis": {
            "title_as_printed": "Time",
            "ticks_as_printed": [
                "16:52:33.25",
                "16:52:33.50",
                "16:52:33.75",
                "16:52:34.00",
                "16:52:34.25",
            ],
            "gridline_band": [95, 910],
            "gridline_span": [100, 400],
            "label_band": [415, 440],
            "label_span": [150, 860],
            "label_rounding_s": 0.005,
            "step_s": 0.005,
        },
        "legend_swatches": {
            "Hornsea Voltage": [307, 349, 529, 538],
            "Total Active Power": [509, 551, 529, 538],
        },
        "series": [
            {
                "legend": "Hornsea Voltage",
                "series_id": "ESO-p19-fig7/Hornsea_Voltage",
                "axis": "left",
                "unit": "kV",
                "quantity": "Hornsea voltage (measurement point and phase not stated on the chart)",
            },
            {
                "legend": "Total Active Power",
                "series_id": "ESO-p19-fig7/Total_Active_Power",
                "axis": "right",
                "unit": "MW",
                "quantity": "Hornsea total active power",
            },
        ],
    },
    {
        "figure_id": "ESO-p19-fig8",
        "csv": "R05/eso_p19_fig8_reactive_power.csv",
        "source_id": "ESO",
        "pdf_page": 19,
        "xref": 57,
        "native_px": [641, 362],
        "kind": "continuous",
        "short": "ESO p19 Figure 8",
        "section": "4.2 Generation Performance – Hornsea",
        "title_as_printed": "Hornsea Voltage and Reactive Power",
        "caption_quote": "Figure 8 – Voltage and Reactive Power at Hornsea",
        "measurement_point_quote": "the reaction of Hornsea wind farm as seen at the onshore connection point",
        "measurement_point_page": 18,
        "plot_rows": [59, 262],
        "plot_cols": [64, 574],
        "left_axis": {
            "title_as_printed": "Voltage (kV)",
            "display_unit_as_printed": None,
            "unit": "kV",
            "ticks_as_printed": [430, 420, 410, 400, 390, 380, 370, 360, 350],
            "gridline_band": [50, 270],
            "gridline_span": [70, 570],
            "label_band": [33, 56],
            "label_span": [50, 270],
        },
        "right_axis": {
            "title_as_printed": "Rective Power (MVAr)",
            "display_unit_as_printed": None,
            "unit": "MVAr",
            "ticks_as_printed": [900, 700, 500, 300, 100, -100, -300, -500, -700, -900],
            "label_band": [583, 609],
            "label_span": [50, 270],
        },
        "x_axis": {
            "title_as_printed": "Time",
            "ticks_as_printed": [
                "16:52:33.25",
                "16:52:33.50",
                "16:52:33.75",
                "16:52:34.00",
                "16:52:34.25",
            ],
            "gridline_band": [60, 580],
            "gridline_span": [60, 260],
            "label_band": [266, 282],
            "label_span": [90, 540],
            "label_rounding_s": 0.005,
            "step_s": 0.005,
        },
        "legend_swatches": {
            "Hornsea Voltage": [192, 218, 338, 345],
            "Total Reactive Power": [321, 348, 338, 345],
        },
        "series": [
            {
                "legend": "Hornsea Voltage",
                "series_id": "ESO-p19-fig8/Hornsea_Voltage",
                "axis": "left",
                "unit": "kV",
                "quantity": "Hornsea voltage (same quantity as Figure 7; used for the cross-check "
                "only, not written to the CSV)",
                "output": False,
            },
            {
                "legend": "Total Reactive Power",
                "series_id": "ESO-p19-fig8/Total_Reactive_Power",
                "axis": "right",
                "unit": "MVAr",
                "quantity": "Hornsea total reactive power (sign convention not printed on the chart)",
            },
        ],
    },
]


# Series that were examined and deliberately not digitised, with the reason (reported in R05.txt
# and in the provenance file).
EXCLUDED = [
    {
        "figure_id": "APP-p41-fig4",
        "series": ["MVAr_PPM1", "MVAr_PPM2", "MVAr_PPM3", "MVAr_PPM4"],
        "reason": "The four per-PPM reactive-power traces lie within a few pixels of each other "
        "for most of the event, MVAr_PPM1 and MVAr_PPM4 are drawn in the same colour, and "
        "repeated fits did not assign the overlapping strokes to the same series consistently "
        "(QA overlays showed strokes swapped between series after the de-load). They are not "
        "digitised rather than guessed.",
    },
    {
        "figure_id": "ESO-p19-fig8",
        "series": ["Hornsea Voltage"],
        "reason": "Same quantity as the voltage in ESO p19 Figure 7, drawn at lower resolution; "
        "digitised only to cross-check the two charts' axes, not written out.",
    },
]
