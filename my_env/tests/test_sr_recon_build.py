"""Reconstruction track: deterministic rebuild and full source verification.

Needs the builder-only inputs (handoff PDFs/text, source catalogue, real-data manifest);
skips when they are absent, e.g. in the image.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ENV_ROOT = Path(__file__).resolve().parents[1]
RECON = ENV_ROOT / "builder" / "system_response" / "recon"
WORKSPACE = ENV_ROOT.parent
HANDOFF = Path(
    os.environ.get(
        "GB_HANDOFF_DIR",
        str(WORKSPACE / ".context" / "handoff" / "GB_power_cut_handoff"),
    )
)
CATALOGUE = Path(
    os.environ.get("GB_CATALOGUE_DIR", str(WORKSPACE / ".context" / "source_catalogue"))
)
REAL = Path(
    os.environ.get("GB_REAL_DATA_DIR", str(WORKSPACE / ".context" / "real_data"))
)

pytestmark = pytest.mark.skipif(
    not (
        (HANDOFF / "source_manifest.json").is_file()
        and (HANDOFF.parent / "text" / "APP.txt").is_file()
        and (CATALOGUE / "extracted" / "APP-p65-fig-operational-calls.csv").is_file()
        and (REAL / "real_data_manifest.json").is_file()
    ),
    reason="builder-only inputs not available",
)


@pytest.fixture(scope="module")
def recon():
    sys.path.insert(0, str(RECON))
    import build_recon
    import verify_recon

    return build_recon, verify_recon


def test_build_is_deterministic_and_matches_disk(recon) -> None:
    build_recon, _ = recon
    first = build_recon.build()
    second = build_recon.build()
    assert first == second
    stale = [
        str(p.relative_to(ENV_ROOT))
        for p, data in first.items()
        if not p.is_file() or p.read_bytes() != data
    ]
    assert not stale, f"run builder/system_response/recon/build_recon.py: {stale}"


def test_full_verification_passes(recon) -> None:
    _, verify_recon = recon
    report = verify_recon.run("off")
    assert not report.failures, "\n".join(report.failures)
    assert report.counts["documents with full line coverage"] == 11
    assert report.counts["witness cards checked"] == 5
    assert report.counts["PDF quotes verified on page (extracted text)"] > 500


def test_verifier_catches_a_tampered_quote(recon, monkeypatch) -> None:
    _, verify_recon = recon
    quotes = verify_recon.Quotes("off")
    report = verify_recon.Report()
    ref = {
        "source_id": "ESO",
        "pdf_page": 12,
        "section": "x",
        "quote": "Frequency at 49.0Hz, ESO securing",
    }
    quotes.check("tamper", ref, report)
    assert report.failures


def test_verifier_number_rule_flags_invented_value(recon) -> None:
    _, verify_recon = recon
    report = verify_recon.Report()
    sources = [
        {"quote": "approximately 150MW of embedded generation", "section": "4.2"}
    ]
    verify_recon.check_numbers(
        "x", "approximately 160 MW [estimated]", sources, [], report
    )
    assert report.failures
