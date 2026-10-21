"""R05 outputs: bundle files, method note conventions, provenance, asset-row fragment.

No PDFs or PyMuPDF needed. Quote checks against the extracted PDF text skip when that text is
absent; the byte-for-byte rebuild check runs only with GB_RUN_DIGITISE_BUILD=1 (it needs PyMuPDF and
takes about a minute and a half).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

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
ROWS = ENV_ROOT / "builder" / "system_response" / "rows" / "r05_hornsea_traces.jsonl"
FRAGMENT = DIGITISE_DIR / "r05_manifest_fragment.json"
HANDOFF_DIR = Path(
    os.environ.get(
        "GB_HANDOFF_DIR",
        str(ENV_ROOT.parent / ".context" / "handoff" / "GB_power_cut_handoff"),
    )
)
TEXT_DIR = Path(os.environ.get("GB_TEXT_DIR", str(HANDOFF_DIR.parent / "text")))

sys.path.insert(0, str(DIGITISE_DIR))
sys.path.insert(0, str(ENV_ROOT / "builder"))

import r05_checks as K  # noqa: E402
from r05_figures import FIGURES  # noqa: E402

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
ASSET_KEYS = {
    "event_id",
    "evidence_id",
    "asset_id",
    "recorded_time",
    "clock_basis",
    "index_time_utc",
    "index_uncertainty_s",
    "signal",
    "value",
    "unit",
    "text",
    "value_status",
}
VALUE_STATUSES = {
    "measured",
    "reported",
    "estimated",
    "modelled",
    "digitised",
    "illustrative",
    "framing",
}
TAG = re.compile(r"\[([a-z]+)\]")
LABEL = "DIGITISED FROM PUBLISHED CHARTS — NOT ORIGINAL MEASUREMENT DATA"
EXPECTED_FILES = {
    "R05.txt",
    "calibration.json",
    "app_p40_fig3_onshore.csv",
    "app_p41_fig4_offshore_1b.csv",
    "eso_p19_fig7_voltage_active_power.csv",
    "eso_p19_fig8_reactive_power.csv",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(name: str) -> list[dict[str, str]]:
    return list(
        csv.DictReader(io.StringIO((R05_DIR / name).read_text(encoding="utf-8")))
    )


def _prov() -> dict[str, Any]:
    return json.loads(PROVENANCE.read_text(encoding="utf-8"))


def test_bundle_holds_exactly_the_r05_files() -> None:
    assert {p.name for p in R05_DIR.iterdir()} == EXPECTED_FILES


@pytest.mark.parametrize("fig", FIGURES, ids=[f["figure_id"] for f in FIGURES])
def test_csv_structure(fig: dict[str, Any]) -> None:
    name = fig["csv"].split("/", 1)[1]
    raw = (R05_DIR / name).read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    rows = _rows(name)
    assert list(rows[0].keys()) == CSV_COLUMNS
    expected_ids = {s["series_id"] for s in fig["series"] if s.get("output", True)}
    assert {r["series_id"] for r in rows} == expected_ids
    for r in rows:
        assert r["series_id"].startswith(fig["figure_id"] + "/")
        assert r["unit"] in {"kV", "MW", "MVAr"}
        v, u = float(r["value"]), float(r["uncertainty"])
        assert u > 0 and u == u and v == v
        assert set(filter(None, r["flags"].split(";"))) <= {
            "ambiguous_overlap",
            "at_axis_top",
            "at_axis_bottom",
        }
        assert float(r["time_uncertainty_s"]) > 0
        if fig["figure_id"] == "APP-p40-fig3":
            assert (
                re.fullmatch(r"52:3[34]\.\d", r["time_as_printed"])
                and r["time_bst_iso"] == ""
            )
        else:
            assert re.fullmatch(r"16:52:3[34]\.\d{3}", r["time_as_printed"])
            assert r["time_bst_iso"] == f"2019-08-09T{r['time_as_printed']}+01:00"
            datetime.fromisoformat(r["time_bst_iso"])
    by_series: dict[str, list[int]] = {}
    for r in rows:
        by_series.setdefault(r["series_id"], []).append(int(r["sample_index"]))
    for idx in by_series.values():
        assert idx == sorted(idx) and len(set(idx)) == len(idx)


def test_category_samples_and_occlusion() -> None:
    f3 = _rows("app_p40_fig3_onshore.csv")
    q = [
        int(r["sample_index"])
        for r in f3
        if r["series_id"] == "APP-p40-fig3/HOW_reactive_MVAr"
    ]
    assert q == list(range(0, 4)) + list(range(19, 70))  # 4-18 hidden by a call-out box
    for sid in ("HOW_V1", "HOW_V2", "HOW_V3", "HOW_active_MW"):
        assert [
            int(r["sample_index"]) for r in f3 if r["series_id"].endswith(sid)
        ] == list(range(70))
    f4 = _rows("app_p41_fig4_offshore_1b.csv")
    assert not any("MVAr" in r["series_id"] for r in f4)
    labels = sorted({(int(r["sample_index"]), r["time_as_printed"]) for r in f4})
    assert (
        len(labels) == 79
        and labels[0][1] == "16:52:33.211"
        and labels[-1][1] == "16:52:33.999"
    )


def test_eso_resampling_is_regular() -> None:
    for name in (
        "eso_p19_fig7_voltage_active_power.csv",
        "eso_p19_fig8_reactive_power.csv",
    ):
        rows = _rows(name)
        for sid in {r["series_id"] for r in rows}:
            ts = [
                K.axis_seconds(r["time_as_printed"])
                for r in rows
                if r["series_id"] == sid
            ]
            steps = {round(b - a, 6) for a, b in zip(ts, ts[1:], strict=False)}
            assert steps == {0.005}
            assert ts[0] >= 33.0 and ts[-1] <= 34.5


def test_method_note_conventions() -> None:
    raw = (R05_DIR / "R05.txt").read_bytes()
    text = raw.decode("utf-8")
    assert raw.endswith(b"\n") and b"\r" not in raw and b"\t" not in raw
    lines = text.split("\n")[:-1]
    for i, line in enumerate(lines, 1):
        assert len(line) <= 110, f"L{i} too long"
        assert line == line.rstrip(), f"L{i} trailing whitespace"
    assert lines[0].startswith("DOCUMENT R05 — ")
    assert any(line.startswith("Owner/originator:") for line in lines[:4])
    assert f"STATUS: {LABEL}." in " ".join(lines[:6])
    assert any(
        line.startswith("Clock reference:") and "zone" in line for line in lines[:8]
    )
    assert "UTC+01:00" in " ".join(lines[:10])
    assert set(TAG.findall(text)) <= VALUE_STATUSES
    for heading in (
        "SOURCES AND LICENCE",
        "SERIES",
        "METHOD",
        "CALIBRATION",
        "UNCERTAINTY",
        "CLOCK BASIS",
        "NOT DIGITISED",
    ):
        assert any(line.startswith(heading) for line in lines), heading
    flat = " ".join(lines)
    # Per-chart clock facts only: what each chart prints, no time zone, hour 16 on APP Fig 4.
    assert "No chart prints a time zone" in flat
    assert (
        "APP Figure 4 prints a time to the millisecond for every sample, with hour 16."
        in flat
    )
    assert "how that clock was synchronised" in flat


def test_method_note_leaves_cross_source_comparison_to_the_reader() -> None:
    """Decision 9: no compiler's note sets R05 against S01, R03 or S07 (ESO Table 1, NGET or
    the Ørsted text times) or says which clock notation those sources share."""
    flat = " ".join((R05_DIR / "R05.txt").read_text(encoding="utf-8").split())
    for phrase in (
        "KNOWN SOURCE CONFLICTS",
        "conflict",
        "16:52:33.490",
        "16:52:33.531",
        "15.52.33",
        "0.4MVAR",
        "Table 1",
        "NGET",
        "clock notation",
        "mixes",
        "timeline",
        "inception",
    ):
        assert phrase not in flat, phrase
    rows = ROWS.read_text(encoding="utf-8")
    for phrase in ("15.52.33", "report timeline", "report text"):
        assert phrase not in rows, phrase


def test_calibration_file() -> None:
    cal = json.loads((R05_DIR / "calibration.json").read_text(encoding="utf-8"))
    assert [c["chart_id"] for c in cal["charts"]] == [f["figure_id"] for f in FIGURES]
    for chart in cal["charts"]:
        for side in ("left", "right", "x"):
            axis = chart["axes"][side]
            assert axis["n_ticks"] >= 3
        for side in ("left", "right"):
            assert chart["axes"][side]["rms_residual_px"] < 1.0
            assert all("residual" in t for t in chart["axes"][side]["ticks"])
        assert chart["axes"]["x"]["rms_residual_px"] < 1.0


def test_provenance_covers_note_and_artifacts() -> None:
    prov = _prov()
    doc = prov["documents"]["R05"]
    assert doc["label"] == prov["label"] == LABEL
    text = (R05_DIR / "R05.txt").read_text(encoding="utf-8")
    assert doc["text_sha256"] == _sha(R05_DIR / "R05.txt")
    lines = text.split("\n")[:-1]
    assert doc["line_count"] == len(lines)
    covered: dict[int, int] = {}
    for seg in doc["segments"]:
        a, b = (int(x) for x in re.fullmatch(r"L(\d+)-L(\d+)", seg["lines"]).groups())
        for n in range(a, b + 1):
            covered[n] = covered.get(n, 0) + 1
        assert seg["value_status"] in VALUE_STATUSES
        if seg["extraction_method"] == "framing":
            assert seg["sources"] == [] and seg["value_status"] == "framing"
        else:
            assert seg["sources"]
    for n, line in enumerate(lines, 1):
        if line.strip():
            assert covered.get(n) == 1, f"L{n} covered {covered.get(n, 0)} times"
    for rel, art in doc["artifacts"].items():
        assert art["sha256"] == _sha(R05_DIR.parent / rel), rel
        assert art["value_status"] == "digitised"
    for sid in ("ESO", "APP"):
        src = prov["sources"][sid]
        assert (
            len(src["sha256"]) == 64
            and src["url"].startswith("https://")
            and "licence" in src
        )
    assert prov["rows_fragment"]["sha256"] == _sha(ROWS)


def test_manifest_fragment_hashes() -> None:
    frag = json.loads(FRAGMENT.read_text(encoding="utf-8"))
    assert frag["doc_id"] == "R05" and frag["text_file"] == "R05/R05.txt"
    assert (
        {a["file"] for a in frag["artifacts"]}
        == set(frag["sha256"])
        == {f"R05/{n}" for n in EXPECTED_FILES}
    )
    for rel, digest in frag["sha256"].items():
        assert digest == _sha(R05_DIR.parent / rel)


def test_asset_row_fragment() -> None:
    raw = ROWS.read_text(encoding="utf-8")
    lines = raw.splitlines()
    assert 3 <= len(lines) <= 15
    ids = set()
    for line in lines:
        row = json.loads(line)
        assert line == json.dumps(row, sort_keys=True, ensure_ascii=False)
        assert set(row) == ASSET_KEYS | {"kind", "provenance"}
        assert (
            row["kind"] == "asset"
            and row["evidence_id"] == "R05"
            and row["asset_id"] == "HORNSEA-ONE"
        )
        assert row["value_status"] == "digitised" and "[digitised]" in row["text"]
        assert isinstance(row["value"], (int, float)) and row["unit"] in {
            "kV",
            "MW",
            "MVAr",
        }
        assert re.fullmatch(r"2019-08-09T15:52:3[34]\.\d{3}Z", row["index_time_utc"])
        assert 0 < row["index_uncertainty_s"] <= 0.5
        assert "zone" in row["clock_basis"]
        assert row["provenance"]["csv"].startswith("R05/")
        ids.add(row["event_id"])
    assert len(ids) == len(lines)


def _normalise_pages() -> dict[str, dict[int, str]]:
    from verify_provenance import load_page_texts, normalise

    pages = {}
    for sid in ("ESO", "APP"):
        path = TEXT_DIR / f"{sid}.txt"
        if not path.exists():
            pytest.skip("extracted PDF text not available")
        pages[sid] = {n: normalise(t) for n, t in load_page_texts(path, sid).items()}
    return pages


def test_every_quote_is_on_its_page() -> None:
    from verify_provenance import normalise

    pages = _normalise_pages()
    prov = _prov()
    quotes = []
    for seg in prov["documents"]["R05"]["segments"]:
        quotes += [s for s in seg["sources"] if s.get("quote")]
    for art in prov["documents"]["R05"]["artifacts"].values():
        quotes += [s for s in art["sources"] if s.get("quote")]
    for chk in prov["validation"]["landmark_checks"]:
        quotes.append(chk["reference_source"])
    assert len(quotes) > 20
    for q in quotes:
        assert len(q["quote"].split()) >= 3, q
        assert normalise(q["quote"]) in pages[q["source_id"]][q["pdf_page"]], q


@pytest.mark.skipif(
    os.environ.get("GB_RUN_DIGITISE_BUILD") != "1", reason="set GB_RUN_DIGITISE_BUILD=1"
)
def test_rebuild_is_byte_identical() -> None:
    cmd = [
        "uv",
        "run",
        "--no-project",
        "--with",
        "pymupdf",
        "--with",
        "numpy",
        "--with",
        "pillow",
        "python",
        str(DIGITISE_DIR / "build_r05.py"),
        "--check",
        "--no-qa",
    ]
    proc = subprocess.run(
        cmd, cwd=ENV_ROOT, capture_output=True, text=True, timeout=900
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
