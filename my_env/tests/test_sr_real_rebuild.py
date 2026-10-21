"""Rebuild the real-data evidence (R02, R04, R06, R07) from builder inputs and compare.

Needs the builder-only inputs (GB_REAL_DATA_DIR, GB_CATALOGUE_DIR, the handoff source manifest
and the per-page report text); every test here skips when they are absent. With them, the
committed outputs must be reproduced byte for byte, both from ``.context/real_data`` and from
the raw mirror ``builder/system_response/raw``, every report quote and table cell must be found
on its PDF page, and a changed input must be refused.
"""

from __future__ import annotations

import gzip
import shutil
import sys
from pathlib import Path

import pytest

ENV_ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ENV_ROOT / "builder" / "system_response" / "real"
sys.path.insert(0, str(REAL_DIR))

import build_real  # noqa: E402
import real_common  # noqa: E402
import sync_raw  # noqa: E402

INPUTS_PRESENT = all(
    path.exists()
    for path in (
        real_common.real_data_dir() / "elexon" / "raw" / "DCI_201908.json",
        real_common.catalogue_dir() / "extracted" / "ESO-p26-tab6.csv",
        real_common.text_dir() / "ESO.txt",
        real_common.handoff_dir() / "source_manifest.json",
    )
)
pytestmark = pytest.mark.skipif(
    not INPUTS_PRESENT, reason="builder-only inputs not available"
)


@pytest.fixture(scope="module")
def built() -> tuple[dict[str, bytes], dict]:
    return build_real.build_outputs(real_common.Inputs())


def test_rebuild_reproduces_committed_outputs(built) -> None:
    outputs, report = built
    assert build_real.check_outputs(outputs, ENV_ROOT) == []
    assert report["verification_skipped"] == []
    assert report["asset_rows"] == 459 and report["control_rows"] == 139


def test_rebuild_is_deterministic(built) -> None:
    again, _ = build_real.build_outputs(real_common.Inputs())
    assert again == built[0]


def test_rebuild_from_raw_mirror_is_identical(built) -> None:
    inputs = real_common.Inputs(real_dir=real_common.RAW_MIRROR_DIR)
    outputs, report = build_real.build_outputs(inputs)
    assert outputs == built[0]
    # Only quote checks against sources that are not mirrored may be skipped.
    for note in report["verification_skipped"]:
        assert note.split(":")[0] in {
            "elexon_api_docs",
            "neso_demand_faq_docx",
            "neso_embedded_definition_docx",
            "consequences_comms_timeline",
        }


def test_raw_mirror_is_reproducible() -> None:
    files, manifest = sync_raw.build_mirror()
    for rel, data in files.items():
        on_disk = (real_common.RAW_MIRROR_DIR / rel).read_bytes()
        if rel.endswith(".gz"):
            assert gzip.decompress(on_disk) == gzip.decompress(data), rel
        else:
            assert on_disk == data, rel
    assert {e["rel"] for e in manifest["files"]} == set(files)


def test_changed_input_is_refused(tmp_path: Path) -> None:
    mirror = tmp_path / "raw"
    shutil.copytree(real_common.RAW_MIRROR_DIR, mirror)
    dci = mirror / "elexon" / "raw" / "DCI_201908.json"
    dci.write_bytes(dci.read_bytes().replace(b"931.0", b"932.0"))
    with pytest.raises(real_common.BuildError, match="sha256"):
        build_real.build_outputs(real_common.Inputs(real_dir=mirror))


def test_wrong_quote_is_refused() -> None:
    inputs = real_common.Inputs()
    with pytest.raises(real_common.BuildError, match="quote not found"):
        inputs.check_quote("OFG", 19, "893MW of net demand was disconnected")
    with pytest.raises(real_common.BuildError, match="not found"):
        inputs.check_cell("ESO", 26, "931,000")
