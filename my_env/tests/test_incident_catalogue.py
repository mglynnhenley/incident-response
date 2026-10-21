"""Catalogue: hash verification (fail closed), listing, pagination and rendering."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from incident_helpers import DOCS, SERIES_ROWS, edit_manifest, make_bundle, rehash

from environment.incident.catalogue import (
    CATEGORIES,
    Catalogue,
    CatalogueError,
    CursorError,
    render_numbered,
)


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    return make_bundle(tmp_path)


def test_load_synthetic_bundle(bundle: Path):
    cat = Catalogue.load(bundle)
    assert cat.ids() == sorted(DOCS)
    assert cat.bundle_id == "synthetic-test-bundle"
    assert len(cat.bundle_sha256) == 64
    r03 = cat.get("R03")
    assert r03 is not None
    assert r03.line_count == DOCS["R03"][2]
    assert r03.lines[0].startswith("DOCUMENT R03")
    assert r03.timeseries is None
    r01 = cat.get("R01")
    assert r01.timeseries is not None and r01.timeseries.rows == SERIES_ROWS
    assert [a.name for a in r01.artifacts] == ["R01.txt", "series.csv"]
    assert r01.summary() == {
        "doc_id": "R01",
        "title": DOCS["R01"][1],
        "owner": "Synthetic owner R01",
        "date": "2019-08-09",
        "category": "measurement_data",
    }
    assert cat.get("R99") is None and "R99" not in cat and "R01" in cat


def test_render_numbered_uses_4d_line_numbers():
    text = render_numbered(["first", "", "third"])
    assert text == "   1 | first\n   2 | \n   3 | third"
    assert (
        render_numbered([f"x{i}" for i in range(1, 1001)]).splitlines()[-1]
        == "1000 | x1000"
    )


def test_identical_bundles_have_identical_hashes(tmp_path: Path):
    a = Catalogue.load(make_bundle(tmp_path / "a"))
    b = Catalogue.load(make_bundle(tmp_path / "b"))
    assert a.bundle_sha256 == b.bundle_sha256


def _expect_failure(bundle: Path, match: str) -> None:
    with pytest.raises(CatalogueError, match=match):
        Catalogue.load(bundle)


def test_tampered_artifact_fails_closed(bundle: Path):
    path = bundle / "R03" / "R03.txt"
    path.write_text(path.read_text() + "extra line\n")
    _expect_failure(bundle, "sha256 mismatch")


def test_tampered_csv_fails_closed(bundle: Path):
    path = bundle / "R01" / "series.csv"
    path.write_text(path.read_text().replace("49.990", "49.000"))
    _expect_failure(bundle, "sha256 mismatch")


def test_missing_artifact_fails_closed(bundle: Path):
    (bundle / "S01" / "S01.txt").unlink()
    _expect_failure(bundle, "cannot open file")


def test_missing_manifest_fails_closed(tmp_path: Path):
    (tmp_path / "empty").mkdir()
    _expect_failure(tmp_path / "empty", "cannot open file")
    _expect_failure(tmp_path / "nope", "unavailable")


def test_symlinked_artifact_is_refused(bundle: Path, tmp_path: Path):
    target = tmp_path / "outside.txt"
    original = bundle / "S04" / "S04.txt"
    target.write_bytes(original.read_bytes())  # same bytes, same hash
    original.unlink()
    os.symlink(target, original)
    _expect_failure(bundle, "cannot open file")


def test_symlinked_document_directory_is_refused(bundle: Path, tmp_path: Path):
    moved = tmp_path / "moved_S04"
    (bundle / "S04").rename(moved)
    os.symlink(moved, bundle / "S04")
    _expect_failure(bundle, "cannot open directory")


def test_hash_map_must_cover_exactly_the_artifacts(bundle: Path):
    edit_manifest(
        bundle, lambda m: m["documents"][1]["sha256"].update({"R03/x.txt": "0" * 64})
    )
    _expect_failure(bundle, "cover exactly")


def test_hash_missing_for_artifact(bundle: Path):
    edit_manifest(bundle, lambda m: m["documents"][1]["sha256"].clear())
    _expect_failure(bundle, "cover exactly")


@pytest.mark.parametrize(
    "bad_path", ["../R03/R03.txt", "/etc/passwd", "R03//R03.txt", "R03\\R03.txt"]
)
def test_unsafe_artifact_paths(bundle: Path, bad_path: str):
    def mutate(m):
        doc = m["documents"][1]
        doc["artifacts"][0]["file"] = bad_path
        doc["text_file"] = bad_path
        doc["sha256"] = {bad_path: "0" * 64}

    edit_manifest(bundle, mutate)
    _expect_failure(bundle, "path")


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda m: m["documents"][0].update(category="rail_records"),
            "unknown category",
        ),
        (lambda m: m["documents"][1].update(doc_id="R01"), "duplicate doc_id"),
        (lambda m: m["documents"][1].update(doc_id="../R03"), "invalid doc_id"),
        (lambda m: m["documents"][1].update(title=""), "title"),
        (lambda m: m.update(documents=[]), "non-empty"),
        (lambda m: m.pop("bundle_version"), "bundle_version"),
        (
            lambda m: m["documents"][1].update(text_file="R03/other.txt"),
            "not an artifact",
        ),
    ],
)
def test_manifest_structure_errors(bundle: Path, mutate, match):
    edit_manifest(bundle, mutate)
    _expect_failure(bundle, match)


def test_manifest_not_json(bundle: Path):
    (bundle / "manifest.json").write_text("{not json")
    _expect_failure(bundle, "not valid JSON")


def test_timeseries_metadata_must_match_csv(bundle: Path):
    edit_manifest(
        bundle,
        lambda m: m["documents"][0]["artifacts"][1]["timeseries"].update(
            rows=SERIES_ROWS + 1
        ),
    )
    _expect_failure(bundle, "data rows")


def test_timeseries_first_must_match_csv(bundle: Path):
    edit_manifest(
        bundle,
        lambda m: m["documents"][0]["artifacts"][1]["timeseries"].update(
            first="2019-08-09T16:52:31+01:00"
        ),
    )
    _expect_failure(bundle, "CSV spans")


def test_text_file_must_be_utf8(bundle: Path):
    (bundle / "S01" / "S01.txt").write_bytes(b"\xff\xfe not utf-8\n")
    rehash(bundle)
    _expect_failure(bundle, "UTF-8")


def test_read_artifact_reverifies_after_load(bundle: Path):
    cat = Catalogue.load(bundle)
    artifact = cat.get("S03").text_artifact
    assert cat.read_artifact(artifact).startswith(b"DOCUMENT S03")
    (bundle / "S03" / "S03.txt").write_text("changed\n")
    with pytest.raises(CatalogueError, match="sha256 mismatch"):
        cat.read_artifact(artifact)
    with pytest.raises(CatalogueError):
        cat.verify()


def test_listing_is_sorted_and_complete(bundle: Path):
    cat = Catalogue.load(bundle)
    page, cursor = cat.list_page()
    assert [d.doc_id for d in page] == sorted(DOCS) and cursor is None
    page, cursor = cat.list_page("generator_records")
    assert [d.doc_id for d in page] == ["S01", "S03"] and cursor is None
    assert cat.list_page("measurement_data")[0][0].doc_id == "R01"
    with pytest.raises(ValueError):
        cat.list_page("not_a_category")
    assert set(CATEGORIES) == {d[0] for d in DOCS.values()}


def test_pagination_with_deterministic_cursors(bundle: Path):
    cat = Catalogue.load(bundle)
    seen = []
    cursor = None
    cursors = []
    while True:
        page, cursor = cat.list_page(cursor=cursor, page_size=2)
        seen.extend(d.doc_id for d in page)
        cursors.append(cursor)
        if cursor is None:
            break
    assert seen == sorted(DOCS)
    assert len(cursors) == 3
    # deterministic: the same listing yields the same opaque cursors
    assert cat.list_page(page_size=2)[1] == cursors[0]
    assert Catalogue.load(bundle).list_page(page_size=2)[1] == cursors[0]


def test_bad_cursors(bundle: Path):
    cat = Catalogue.load(bundle)
    _, cursor = cat.list_page(page_size=1)
    with pytest.raises(CursorError, match="different listing"):
        cat.list_page("generator_records", cursor, page_size=1)
    for garbage in ["!!!", "abc", "eyJ4IjoxfQ"]:
        with pytest.raises(CursorError):
            cat.list_page(cursor=garbage)
    past_end = cat._encode_cursor(None, 99)
    with pytest.raises(CursorError, match="past the end"):
        cat.list_page(cursor=past_end)
