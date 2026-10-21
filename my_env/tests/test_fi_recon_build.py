"""Full-investigation reconstruction track: deterministic rebuild and full source verification.

Needs the builder-only inputs (handoff PDFs/text incl. ORR, source catalogue, real-data manifest
and the two saved web pages behind the S11 index entries); skips when they are absent, e.g. in
the image.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ENV_ROOT = Path(__file__).resolve().parents[1]
RECON = ENV_ROOT / "builder" / "full_investigation" / "recon"
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
        and (HANDOFF.parent / "text" / "ORR.txt").is_file()
        and (CATALOGUE / "extracted" / "ESO-p29-tab7.csv").is_file()
        and (REAL / "real_data_manifest.json").is_file()
        and (REAL / "consequences" / "raw" / "docs" / "esneft_p8309.html").is_file()
    ),
    reason="builder-only inputs not available",
)


@pytest.fixture(scope="module")
def recon():
    sys.path.insert(0, str(RECON))
    import build_fi_recon
    import fi_recon_common
    import verify_fi_recon

    return build_fi_recon, verify_fi_recon, fi_recon_common


def test_build_is_deterministic_and_matches_disk(recon) -> None:
    build, _, _ = recon
    first = build.build()
    assert first == build.build()
    stale = [
        str(p.relative_to(ENV_ROOT))
        for p, data in first.items()
        if not p.is_file() or p.read_bytes() != data
    ]
    assert not stale, f"run builder/full_investigation/recon/build_fi_recon.py: {stale}"


def test_full_verification_passes(recon) -> None:
    _, verify, _ = recon
    report = verify.run()
    assert not report.failures, "\n".join(report.failures)
    assert report.counts["documents with full line coverage"] == 4
    assert report.counts["witness cards checked"] == 5
    assert report.counts["witness topics selecting their own block"] >= 40
    assert report.counts["PDF quotes verified on page"] > 350
    assert report.counts["index entries without copied wording"] == 3
    assert report.counts["merged registry entries"] == 17 + 12


def test_verifier_catches_a_tampered_orr_quote(recon) -> None:
    _, verify, _ = recon
    report = verify.Report()
    ref = {
        "source_id": "ORR",
        "pdf_page": 3,
        "section": "1.0 Introduction",
        "quote": "causing a lock-out of 30 trains",
    }
    verify.Quotes().check("tamper", ref, report)
    assert report.failures


def test_verifier_catches_a_quote_on_the_wrong_page(recon) -> None:
    _, verify, _ = recon
    report = verify.Report()
    ref = {
        "source_id": "APP",
        "pdf_page": 49,
        "section": "Appendix F",
        "quote": "After this 27 of the affected units were recovered.",
    }
    verify.Quotes().check("wrong page", ref, report)
    assert report.failures and "found [48]" in report.failures[0]


def test_number_rule_flags_a_reconciled_count(recon) -> None:
    _, verify, _ = recon
    report = verify.Report()
    sources = [
        {"quote": "29 trains shut down; 22 permanently locked out", "section": "2.6"}
    ]
    verify.check_numbers("x", "51 [reported] trains in total", sources, [], report)
    assert report.failures


def test_index_entry_overlap_check_flags_copied_wording(recon) -> None:
    _, _, common = recon
    statement = common.statement_text("RAW-ESNEFT")
    copied = "The emergency generators at the hospital all worked."
    paraphrase = "Every standby generator on the site operated."
    assert common.shared_runs(copied, statement)
    assert not common.shared_runs(paraphrase, statement)


def test_saved_page_quote_must_be_on_the_page(recon) -> None:
    _, verify, common = recon
    report = verify.Report()
    ref = common.raw_src(
        "RAW-STANLOW", "the refinery was shut for nine weeks", "article"
    )
    verify.Quotes().check("raw", ref, report)
    assert report.failures
