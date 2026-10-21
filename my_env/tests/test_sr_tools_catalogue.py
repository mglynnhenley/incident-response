"""Manifest v2 loading: structure, hashes and fail-closed checks (synthetic bundle)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from sr_helpers import edit_manifest, make_sr_bundle, rehash

from environment.incident.catalogue import CATEGORIES, Catalogue, CatalogueError
from environment.incident.paths import (
    DEFAULT_BUNDLE_DIR,
    SYSTEM_RESPONSE_BUNDLE_DIR,
    SYSTEM_RESPONSE_PRIVATE_DIR,
)
from environment.incident.system_bundle import EvidenceTarget


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    return make_sr_bundle(tmp_path)


def test_v2_bundle_loads_with_all_sections(bundle: Path):
    cat = Catalogue.load(bundle)
    assert cat.is_v2 and cat.manifest_version == 2
    assert cat.categories == (
        "demand_records",
        "engineering_analysis",
        "generator_records",
        "measurement_data",
        "network_records",
    )
    assert cat.ids() == ["R01", "R03", "R07", "S05", "S06", "S12"]
    assert cat.listed_ids() == ["R01", "R03", "R07", "S06", "S12"]
    assert not cat.is_listed("S05") and not cat.is_listed("nope")
    sources = cat.sources
    assert list(sources.asset_logs) == ["DNO-A", "ESW-400", "PLANT-A"]
    assert list(sources.control_logs) == ["DNO-A", "SO-CONTROL"]
    assert list(sources.witnesses) == ["dno-engineer", "so-engineer"]
    assert len(sources.data_returns) == 3
    assert len(sources.frequency) == 1500 and sources.frequency.gaps == 0
    assert len(sources.asset_logs["PLANT-A"].rows) == 460
    # rows are ordered by index time, then ID
    times = [r.index_time for r in sources.asset_logs["PLANT-A"].rows]
    assert times == sorted(times)
    cat.verify()


def test_citation_targets_cover_documents_and_records(bundle: Path):
    cat = Catalogue.load(bundle)
    r03 = cat.citation_target("R03")
    assert isinstance(r03, EvidenceTarget) and r03.is_document
    assert "ESW-0001" in r03.records["event"] and r03.line_count == 20
    s07 = cat.citation_target("S07")
    assert not s07.is_document and s07.line_count == 0 and s07.timeseries is None
    assert "SO-001" in s07.records["entry"]
    s09 = cat.citation_target("S09")
    assert s09.records["response"] == {
        "S09-SO-01",
        "S09-SO-02",
        "S09-SO-03",
        "S09-DNO-01",
    }
    assert cat.citation_target("S99") is None
    # hidden documents are citable but not advertised
    assert cat.citation_target("S05").is_document
    assert "S05" in cat.citable_ids()  # S05 also carries records
    assert cat.citable_ids() == [
        "R01",
        "R02",
        "R03",
        "R05",
        "R07",
        "R08",
        "S05",
        "S06",
        "S07",
        "S09",
        "S12",
    ]


def test_v1_manifests_load_exactly_as_before(tmp_path: Path):
    from incident_helpers import make_bundle

    cat = Catalogue.load(make_bundle(tmp_path))
    assert not cat.is_v2 and cat.manifest_version == 1
    assert cat.categories == CATEGORIES
    assert cat.listed_ids() == cat.ids() == cat.citable_ids()
    assert cat.citation_target("R03") is cat.get("R03")


def test_the_frozen_mvp_bundle_is_still_version_1():
    cat = Catalogue.load(DEFAULT_BUNDLE_DIR)
    assert cat.manifest_version == 1 and not cat.is_v2


def test_default_locations():
    assert SYSTEM_RESPONSE_BUNDLE_DIR.parts[-2:] == ("bundles", "system_response")
    assert SYSTEM_RESPONSE_PRIVATE_DIR.parts[-2:] == ("private", "system_response")


# -- fail closed ------------------------------------------------------------------------
def _expect(bundle: Path, match: str) -> None:
    with pytest.raises(CatalogueError, match=match):
        Catalogue.load(bundle)


@pytest.mark.parametrize(
    "rel",
    [
        "logs/assets/ESW-400.jsonl",
        "logs/control/SO-CONTROL.jsonl",
        "witnesses/so-engineer.json",
        "R01/frequency.csv",
    ],
)
def test_tampered_files_fail_closed(bundle: Path, rel: str):
    path = bundle / rel
    path.write_bytes(path.read_bytes() + b" ")
    _expect(bundle, "sha256 mismatch")


def test_verify_detects_tampering_after_load(bundle: Path):
    cat = Catalogue.load(bundle)
    (bundle / "witnesses" / "dno-engineer.json").write_text("{}\n")
    with pytest.raises(CatalogueError, match="bundle modified"):
        cat.verify()


def test_symlinked_log_is_refused(bundle: Path, tmp_path: Path):
    target = bundle / "logs" / "assets" / "ESW-400.jsonl"
    outside = tmp_path / "outside.jsonl"
    outside.write_bytes(target.read_bytes())
    target.unlink()
    os.symlink(outside, target)
    _expect(bundle, "cannot open file")


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda m: m.update(manifest_version=3), "unsupported manifest_version"),
        (lambda m: m.update(manifest_version=True), "unsupported manifest_version"),
        (lambda m: m.update(asset_log=[]), "unexpected field"),
        (lambda m: m["asset_logs"][0].update(file="../x.jsonl"), "plain relative path"),
        (
            lambda m: m["asset_logs"][0].update(file="/etc/passwd"),
            "plain relative path",
        ),
        (lambda m: m["asset_logs"][0].pop("clock_note"), "missing field"),
        (lambda m: m["asset_logs"].append(dict(m["asset_logs"][0])), "duplicate"),
        (lambda m: m["control_logs"][0].update(extra=1), "unexpected field"),
        (lambda m: m["witnesses"][0].update(role="Other"), "does not match"),
        (lambda m: m["documents"][3].update(access="secret"), "access"),
        (lambda m: m["documents"][0].update(access="data_return"), "never be obtained"),
        (lambda m: m["documents"][0].update(note="x"), "unexpected field"),
        (lambda m: m.update(categories=["Bad Category"]), "invalid category"),
        (lambda m: m.update(categories=["measurement_data"]), "unknown category"),
        (lambda m: m["data_returns"][0].update(status="maybe"), "status"),
        (lambda m: m["data_returns"][0].pop("evidence_id"), "evidence_id"),
        (lambda m: m["data_returns"][0].update(evidence_id="S99"), "not a bundle doc"),
        (lambda m: m["data_returns"][1].update(evidence_id="S05"), "must not name"),
        (lambda m: m["data_returns"][1].pop("message"), "message"),
        (
            lambda m: m["data_returns"].append(
                dict(m["data_returns"][0], party=" synthetic  DNO a ")
            ),
            "duplicate data return",
        ),
        (
            lambda m: m.update(
                documents=[d for d in m["documents"] if d["doc_id"] != "R01"]
            ),
            "R01",
        ),
    ],
)
def test_manifest_problems_fail_closed(bundle: Path, mutate, match: str):
    edit_manifest(bundle, mutate)
    rehash(bundle)
    _expect(bundle, match)


@pytest.mark.parametrize("digest", ["abc", "A" * 64, None, {"other.jsonl": "0" * 64}])
def test_log_hashes_must_be_well_formed(bundle: Path, digest):
    edit_manifest(bundle, lambda m: m["asset_logs"][0].update(sha256=digest))
    _expect(bundle, "sha256")


def test_log_hash_may_be_a_file_mapping(bundle: Path):
    def as_mapping(manifest):
        entry = manifest["control_logs"][0]
        entry["sha256"] = {entry["file"]: entry["sha256"]}

    edit_manifest(bundle, as_mapping)
    assert Catalogue.load(bundle).is_v2


def test_v2_sections_without_manifest_version_are_refused(bundle: Path):
    edit_manifest(bundle, lambda m: m.pop("manifest_version"))
    _expect(bundle, 'no "manifest_version": 2')


def _rewrite_rows(bundle: Path, rel: str, edit) -> None:
    path = bundle / rel
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    edit(rows)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    rehash(bundle)


ESW = "logs/assets/ESW-400.jsonl"
SO = "logs/control/SO-CONTROL.jsonl"


@pytest.mark.parametrize(
    ("rel", "edit", "match"),
    [
        (ESW, lambda rows: rows[0].update(provenance={"x": 1}), "provenance"),
        (ESW, lambda rows: rows[0].update(kind="asset"), "unexpected field"),
        (ESW, lambda rows: rows[0].pop("clock_basis"), "missing field"),
        (ESW, lambda rows: rows[0].update(value_status="certain"), "value_status"),
        (
            ESW,
            lambda rows: rows[0].update(index_time_utc="2019-08-09T16:52:33+01:00"),
            "UTC",
        ),
        (ESW, lambda rows: rows[0].update(index_time_utc="16:52"), "ISO-8601"),
        (ESW, lambda rows: rows[0].update(index_uncertainty_s=-1), ">= 0"),
        (ESW, lambda rows: rows[0].update(index_uncertainty_s=True), "finite number"),
        (ESW, lambda rows: rows[0].update(evidence_id="S07"), "not listed"),
        (ESW, lambda rows: rows[0].update(asset_id="PLANT-A"), "does not match"),
        (ESW, lambda rows: rows[0].update(signal="other"), "not declared"),
        (ESW, lambda rows: rows[0].update(value=True), "finite number"),
        (ESW, lambda rows: rows[0].update(event_id="bad id"), "event_id"),
        (ESW, lambda rows: rows[1].update(event_id=rows[0]["event_id"]), "duplicate"),
        (ESW, lambda rows: rows[0].update(recorded_time=""), "recorded_time"),
        (SO, lambda rows: rows[0].update(text=None), "text"),
        (SO, lambda rows: rows[0].update(entry_id="SO-002"), "duplicate entry"),
        (SO, lambda rows: rows[0].update(room_id="DNO-A"), "does not match"),
    ],
)
def test_row_problems_fail_closed(bundle: Path, rel: str, edit, match: str):
    _rewrite_rows(bundle, rel, edit)
    _expect(bundle, match)


def test_record_ids_are_unique_across_logs(bundle: Path):
    def clash(rows):
        rows[0]["event_id"] = "PLANT-1-0000"

    _rewrite_rows(bundle, ESW, clash)
    _expect(bundle, "duplicate event ID")


def test_jsonl_must_be_strict(bundle: Path):
    path = bundle / ESW
    path.write_text(path.read_text() + "\n")  # blank line
    rehash(bundle)
    _expect(bundle, "blank")
    path.write_text(path.read_text().rstrip("\n"))  # no trailing newline
    rehash(bundle)
    _expect(bundle, "newline")
    path.write_text('{"a": 1, "a": 2}\n')
    rehash(bundle)
    _expect(bundle, "duplicate key")
    path.write_text('{"value": NaN}\n')
    rehash(bundle)
    _expect(bundle, "not valid JSON")


def _rewrite_card(bundle: Path, persona: str, edit) -> None:
    path = bundle / "witnesses" / f"{persona}.json"
    card = json.loads(path.read_text())
    edit(card)
    path.write_text(json.dumps(card))
    rehash(bundle)


@pytest.mark.parametrize(
    ("edit", "match"),
    [
        (lambda c: c.update(provenance=[]), "provenance"),
        (lambda c: c["blocks"][0].update(provenance=[{"q": 1}]), "provenance"),
        (lambda c: c["blocks"][0].update(note="x"), "unexpected field"),
        (lambda c: c.update(blocks=[]), "blocks"),
        (lambda c: c["blocks"][0].update(topics=[]), "topics"),
        (lambda c: c["blocks"][0].update(topics=["a", "a"]), "duplicate"),
        (lambda c: c["blocks"][0].update(response_text=" "), "response_text"),
        (lambda c: c.pop("unknown_response"), "missing field"),
        (lambda c: c.update(evidence_id="S10"), "does not match"),
        (
            lambda c: c["blocks"][1].update(response_id=c["blocks"][0]["response_id"]),
            "duplicate response_id",
        ),
    ],
)
def test_witness_card_problems_fail_closed(bundle: Path, edit, match: str):
    _rewrite_card(bundle, "so-engineer", edit)
    _expect(bundle, match)


def test_response_ids_are_unique_across_witnesses(bundle: Path):
    _rewrite_card(
        bundle,
        "dno-engineer",
        lambda c: c["blocks"][0].update(response_id="S09-SO-01"),
    )
    _expect(bundle, "duplicate response ID")


@pytest.mark.parametrize(
    ("edit", "match"),
    [
        (lambda lines: lines.insert(3, lines[2]), "rows but the manifest"),
        (
            lambda lines: lines.__setitem__(5, lines[5].split(",")[0] + ",abc"),
            "unreadable",
        ),
        (
            lambda lines: lines.__setitem__(5, lines[5].split(",")[0] + ",inf"),
            "not finite",
        ),
    ],
)
def test_frequency_series_problems_fail_closed(bundle: Path, edit, match: str):
    path = bundle / "R01" / "frequency.csv"
    lines = path.read_text().splitlines()
    edit(lines)
    path.write_text("\n".join(lines) + "\n")
    rehash(bundle)
    _expect(bundle, match)


def test_frequency_series_must_increase(tmp_path: Path):
    def swap(manifest, bundle):
        path = bundle / "R01" / "frequency.csv"
        lines = path.read_text().splitlines()
        lines[10], lines[11] = lines[11], lines[10]
        path.write_text("\n".join(lines) + "\n")

    with pytest.raises(CatalogueError, match="does not increase"):
        Catalogue.load(make_sr_bundle(tmp_path, mutate=swap))


def test_unlisted_record_free_documents_are_citable_but_not_advertised(tmp_path: Path):
    def drop_dno_logs(manifest, bundle):
        manifest["asset_logs"] = [
            e for e in manifest["asset_logs"] if e["asset_id"] != "DNO-A"
        ]
        manifest["control_logs"] = [
            e for e in manifest["control_logs"] if e["room_id"] != "DNO-A"
        ]

    cat = Catalogue.load(make_sr_bundle(tmp_path, mutate=drop_dno_logs))
    assert "S05" not in cat.citable_ids()
    assert "S05" in cat.citable_ids(public=False)
    assert cat.citation_target("S05").is_document


def test_cli_lists_v2_sources(bundle: Path, capsys):
    from environment.incident import cli

    assert cli.main(["list", "--bundle", str(bundle)]) == 0
    out = capsys.readouterr().out
    assert "S05" in out and "[data return only]" in out
    assert "asset   PLANT-A" in out and "room    SO-CONTROL" in out
    assert "witness so-engineer" in out and "relay timing logs: not_held" in out
    assert cli.main(["list", "--bundle", str(bundle), "--json"]) == 0
    listing = json.loads(capsys.readouterr().out)
    assert listing["manifest_version"] == 2
    assert {d["doc_id"]: d["listed"] for d in listing["documents"]}["S05"] is False
    assert [r["status"] for r in listing["data_returns"]] == [
        "available",
        "not_held",
        "refused",
    ]
    assert cli.main(["list", "--bundle", str(bundle), "--category", "nope"]) == 2
