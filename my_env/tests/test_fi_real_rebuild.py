"""Rebuild the real-data evidence R09, R11 and R12 from builder inputs and compare.

Needs the builder-only inputs (GB_REAL_DATA_DIR, GB_CATALOGUE_DIR, the handoff source manifest and
the per-page report text); every test here skips when they are absent. With them, the committed
outputs must be reproduced byte for byte, both from ``.context/real_data`` and from the raw
mirror ``builder/full_investigation/raw``; every report quote, table cell, web quotation and gist
must pass its check; a changed input, a wrong quote and a near-verbatim gist must be refused.
"""

from __future__ import annotations

import csv
import gzip
import io
import shutil
import sys
from pathlib import Path

import pytest

ENV_ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ENV_ROOT / "builder" / "full_investigation" / "real"
sys.path.insert(0, str(REAL_DIR))

import fi_build_real  # noqa: E402
import fi_r09  # noqa: E402
import fi_real_common  # noqa: E402
import fi_sync_raw  # noqa: E402

INPUTS_PRESENT = all(
    path.exists()
    for path in (
        fi_real_common.real_data_dir()
        / "elexon"
        / "raw"
        / "REMIT_revision_details_selected.json",
        fi_real_common.real_data_dir()
        / "consequences"
        / "derived"
        / "comms_timeline_uk_local.csv",
        fi_real_common.catalogue_dir() / "extracted" / "ESO-p30-tab8.csv",
        fi_real_common.text_dir() / "E3C.txt",
        fi_real_common.handoff_dir() / "source_manifest.json",
    )
)
pytestmark = pytest.mark.skipif(
    not INPUTS_PRESENT, reason="builder-only inputs not available"
)

#: Sources that the mirror does not hold (not openly licensed, or only quoted).
NOT_MIRRORED = {
    key
    for key, spec in fi_build_real.SOURCES.items()
    if spec.get("mirror", "none") == "none"
}


@pytest.fixture(scope="module")
def built() -> tuple[dict[str, bytes], dict]:
    return fi_build_real.build_outputs(fi_real_common.FiInputs())


def test_rebuild_reproduces_committed_outputs(built) -> None:
    outputs, report = built
    assert fi_build_real.check_outputs(outputs, ENV_ROOT) == []
    assert report["verification_skipped"] == []
    assert report["rows"] == {
        "real_r09_asset.jsonl": 46,
        "real_r09_control.jsonl": 42,
        "real_r11_control.jsonl": 31,
    }


def test_rebuild_is_deterministic(built) -> None:
    again, _ = fi_build_real.build_outputs(fi_real_common.FiInputs())
    assert again == built[0]


def test_rebuild_from_raw_mirror_is_identical(built) -> None:
    inputs = fi_real_common.FiInputs(real_dir=fi_real_common.RAW_MIRROR_DIR)
    outputs, report = fi_build_real.build_outputs(inputs)
    assert outputs == built[0]
    # Only checks against sources that are not mirrored may be skipped.
    for note in report["verification_skipped"]:
        assert note.split(":")[0] in NOT_MIRRORED, note


def test_raw_mirror_is_reproducible() -> None:
    files, manifest = fi_sync_raw.build_mirror()
    for rel, data in files.items():
        on_disk = (fi_real_common.RAW_MIRROR_DIR / rel).read_bytes()
        if rel.endswith(".gz"):
            assert gzip.decompress(on_disk) == gzip.decompress(data), rel
        else:
            assert on_disk == data, rel
    assert {e["rel"] for e in manifest["files"]} == set(files)
    assert not any(
        fi_build_real.SOURCES[e["source_id"]].get("mirror", "none") == "none"
        for e in manifest["files"]
    )


def test_explanation_extract_matches_the_pdf() -> None:
    fitz = pytest.importorskip("fitz")
    spec = fi_build_real.SOURCES["nr_explanation"]
    pdf = (fi_real_common.real_data_dir() / spec["rel"]).read_bytes()
    document = fitz.open(stream=pdf, filetype="pdf")
    text = "".join(
        f"=== page {n} ===\n" + page.get_text() for n, page in enumerate(document, 1)
    )
    committed = (fi_real_common.RAW_MIRROR_DIR / spec["mirror_rel"]).read_text(
        encoding="utf-8"
    )
    assert committed == text


def test_changed_input_is_refused(tmp_path: Path) -> None:
    mirror = tmp_path / "raw"
    shutil.copytree(fi_real_common.RAW_MIRROR_DIR, mirror)
    remit = mirror / "elexon" / "raw" / "REMIT_revision_details_selected.json"
    remit.write_bytes(remit.read_bytes().replace(b"trip of BMU 2.", b"trip of BMU 9."))
    with pytest.raises(fi_real_common.BuildError, match="sha256"):
        fi_build_real.build_outputs(fi_real_common.FiInputs(real_dir=mirror))


def test_wrong_quotes_are_refused() -> None:
    inputs = fi_real_common.FiInputs()
    with pytest.raises(fi_real_common.BuildError, match="quote not found"):
        inputs.check_quote(
            "ESO", 30, "The first communication with Ofgem was made at 17:52hrs"
        )
    with pytest.raises(fi_real_common.BuildError, match="quote not found"):
        inputs.check_text_quote(
            "ofgem_pr_20190820", "Ofgem has found that the companies breached"
        )
    with pytest.raises(fi_real_common.BuildError, match="quote not found"):
        fi_real_common.extract_quote_ref(
            inputs, "nr_explanation", "x", "Pfpi minutes – the size of the cancellation"
        )


def test_near_verbatim_gists_are_refused() -> None:
    """A gist that copies four consecutive words of a post or page must stop the build."""
    inputs = fi_real_common.FiInputs()
    texts = fi_r09._post_texts(inputs)
    assert texts is not None
    post_id = "1159866619641892864"  # the 17:38:46 BST train-operator post
    copied = "The power network has failed in the large parts of London"
    assert copied in texts[post_id]["text"]
    item = {
        "kind": "posts",
        "post_ids": [int(post_id)],
        "organisation": "x",
        "channel": "x",
        "gist": f"says {copied.lower()}",
        "capture": "https://web.archive.org/web/20220728215944/https://twitter.com/TLRailUK/"
        "status/1159866619641892864",
    }
    with pytest.raises(
        fi_real_common.BuildError, match="gist tracks the source wording"
    ):
        fi_r09._check_item(inputs, item, texts, None)
    with pytest.raises(
        fi_real_common.BuildError, match="gist tracks the source wording"
    ):
        inputs.check_gist(
            "neso_statement_0908_2000", "by 18:30 all demand was restored by the DNOs"
        )


def test_every_part_e_gist_is_checked_against_its_source() -> None:
    """All gists pass the rule against the held sources, and each post is organisational."""
    inputs = fi_real_common.FiInputs()
    texts = fi_r09._post_texts(inputs)
    timeline = fi_r09._timeline(inputs)
    assert texts is not None and timeline is not None
    for item in fi_r09.ITEMS:
        ref = fi_r09._check_item(inputs, item, texts, timeline)
        assert ref["gist_rule"]
    assert inputs.skipped == []


def test_selected_posts_exclude_replies_to_the_public() -> None:
    raw = fi_real_common.FiInputs().real_bytes("comms_posts_embedded").decode("utf-8")
    rows = {r["tweet_id"]: r for r in csv.DictReader(io.StringIO(raw))}
    for item in fi_r09.ITEMS:
        for post_id in item.get("post_ids", []):
            row = rows.get(str(post_id))
            if row is not None:
                assert row["account_type"] == "organisation"
                assert "public_user" not in row["text"], post_id
