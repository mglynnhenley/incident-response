"""Build the reconstruction track's outputs for the system-response bundle.

Builder-only and deterministic (same inputs -> byte-identical outputs; no timestamps). Writes:

- ``bundles/system_response/{R01,R03,S03,S04}``: byte-identical copies of MVP bundle 1.1.0;
- ``bundles/system_response/S01/S01.txt``: MVP S01 with the decision-19 clock line;
- ``bundles/system_response/R08/R08.txt``: generated from the catalogue transcription of ESO
  Appendix J (see ``recon_r08.py``);
- ``builder/system_response/rows/witnesses/<persona_id>.json``: S09 source cards (blocks
  carry ``provenance``; ``builder/system_response/build_bundle.py`` writes the agent-visible
  copies to ``bundles/system_response/witnesses/`` with it stripped);
- ``builder/system_response/rows/recon_{r03,s01,s03,s07,r08}.jsonl``: asset/control row
  fragments (each line adds ``kind`` and ``provenance``);
- ``builder/system_response/rows/data_returns.json``: data-return registry fragment;
- ``builder/system_response/recon/documents.json``: manifest metadata proposed for this track's
  documents and witnesses (titles, owners, categories, artifact descriptions, hashes);
- ``private/system_response/provenance_recon.json``: segment provenance of every document,
  witness block, row fragment and registry entry.

R10, S05, S06, S07 and S12 are hand-authored in the bundle (inputs here, never rewritten).

    uv run --frozen python builder/system_response/recon/build_recon.py          # write
    uv run --frozen python builder/system_response/recon/build_recon.py --check  # compare only
    uv run --frozen python builder/system_response/recon/verify_recon.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import recon_doc_specs  # noqa: E402
import recon_r08  # noqa: E402
import recon_returns  # noqa: E402
import recon_rows  # noqa: E402
import recon_witnesses  # noqa: E402
from recon_common import (  # noqa: E402
    AUTHORED_DOCS,
    CATALOGUE_EXTRACTS,
    COPIED_DOCS,
    DATA_RETURNS_PATH,
    DOCUMENTS_META_PATH,
    ENV_ROOT,
    GENERATED_BY,
    LABELS,
    MVP_BUNDLE_DIR,
    PDF_SOURCES,
    PROVENANCE_PATH,
    ROWS_DIR,
    SOURCE_TITLES,
    SR_BUNDLE_DIR,
    VERIFIED_BY,
    WITNESS_DIR,
    WITNESS_EVIDENCE_ID,
    WITNESS_LABEL,
    dumps_json,
    dumps_jsonl,
    handoff_dir,
    mvp_build,
    resolve_segments,
    sha256_bytes,
    sha256_file,
    text_lines,
)

R01_CSV = "R01/frequency_2019-08-09_1640-1745_BST.csv"

DOC_META: dict[str, dict[str, Any]] = {
    "R01": {
        "title": "System frequency record, 9 August 2019, 16:40-17:45 BST",
        "owner": "National Grid ESO (NESO published dataset)",
        "category": "measurement_data",
    },
    "R03": {
        "title": "Transmission fault and protection records, 9 August 2019",
        "owner": "National Grid Electricity Transmission (NGET); lightning data MeteoGroup",
        "category": "network_records",
    },
    "R08": {
        "title": "Operational call record between control rooms, 9 August 2019",
        "owner": "National Grid ESO (call diagram, Appendix J to the ESO technical report)",
        "category": "operational_records",
    },
    "R10": {
        "title": "Operating requirements as described in the published reports (selection)",
        "owner": "Compiled from National Grid ESO, Ofgem and E3C reports",
        "category": "requirements",
    },
    "S01": {
        "title": "Hornsea One offshore wind farm event log, 9 August 2019",
        "owner": "Ørsted (Hornsea One operator)",
        "category": "generator_records",
    },
    "S03": {
        "title": "Little Barford power station alarm and sequence-of-events records, "
        "9 August 2019",
        "owner": "RWE Generation (Little Barford power station)",
        "category": "generator_records",
    },
    "S04": {
        "title": "Little Barford power station shift account, 9 August 2019",
        "owner": "RWE Generation (Little Barford station operating staff)",
        "category": "personnel_accounts",
    },
    "S05": {
        "title": "Distribution network operator demand disconnection and restoration returns, "
        "9 August 2019",
        "owner": "Distribution Network Operators (returns as tabulated by National Grid ESO and "
        "the E3C)",
        "category": "distribution_returns",
    },
    "S06": {
        "title": "Embedded generation returns and published loss estimates, 9 August 2019",
        "owner": "Distribution Network Operators; National Grid ESO, Ofgem and E3C estimates",
        "category": "distribution_returns",
    },
    "S07": {
        "title": "ESO control room log, 9 August 2019",
        "owner": "National Grid ESO (Electricity National Control Centre)",
        "category": "operational_records",
    },
    "S12": {
        "title": "Engineering analysis records, 9 August 2019",
        "owner": "National Grid ESO, with Ofgem and E3C analysis as attributed",
        "category": "analysis_records",
    },
}
TEXT_DESCRIPTION = (
    "Readable record text; line numbers shown on retrieval are the citation locators."
)
ROW_FRAGMENTS = {
    "recon_r03.jsonl": "R03",
    "recon_s01.jsonl": "S01",
    "recon_s03.jsonl": "S03",
    "recon_s07.jsonl": "S07",
    "recon_r08.jsonl": "R08",
}


# --------------------------------------------------------------------------- documents


def derive_s01() -> bytes:
    lines = text_lines((MVP_BUNDLE_DIR / "S01" / "S01.txt").read_bytes())
    matches = [i for i, line in enumerate(lines) if line.startswith("Clock reference:")]
    if len(matches) != 1 or lines[matches[0]] != recon_doc_specs.S01_MVP_CLOCK_LINE:
        raise SystemExit("MVP S01 clock line is not the expected frozen 1.1.0 line")
    index = matches[0]
    new = lines[:index] + list(recon_doc_specs.S01_CLOCK_LINES) + lines[index + 1 :]
    return ("\n".join(new) + "\n").encode("utf-8")


def document_outputs() -> tuple[dict[str, bytes], dict[str, Any]]:
    """Return {bundle-relative path: bytes} for written docs and the R08 build info."""
    out: dict[str, bytes] = {}
    for doc_id in COPIED_DOCS:
        out[f"{doc_id}/{doc_id}.txt"] = (
            MVP_BUNDLE_DIR / doc_id / f"{doc_id}.txt"
        ).read_bytes()
    out[R01_CSV] = (MVP_BUNDLE_DIR / R01_CSV).read_bytes()
    out["S01/S01.txt"] = derive_s01()
    text, specs, records, info = recon_r08.build_r08()
    out["R08/R08.txt"] = text.encode("utf-8")
    info = {**info, "specs": specs, "records": records}
    return out, info


def doc_bytes(doc_id: str, written: dict[str, bytes]) -> bytes:
    key = f"{doc_id}/{doc_id}.txt"
    if key in written:
        return written[key]
    path = SR_BUNDLE_DIR / key
    if not path.is_file():
        raise SystemExit(f"authored document missing: {path}")
    return path.read_bytes()


def doc_specs_for(doc_id: str, r08_specs: list[dict[str, Any]]) -> dict[str, Any]:
    if doc_id in COPIED_DOCS:
        return mvp_build.DOCUMENT_SPECS[doc_id]
    if doc_id == "S01":
        return recon_doc_specs.s01_spec()
    if doc_id == "R08":
        return {
            "construction": (
                "Generated by recon_r08.py. Header and summary notes restate the Appendix J page "
                "text; each call row restates one row of the source catalogue's transcription "
                "of the raster call diagram (printed time, arrow direction, lane(s), annotation "
                "text), checked field by field against the pinned CSV. Boxes without an arrow "
                "of their own and side boxes beside a block of rows are listed separately with "
                "their printed position; lane-reading doubts recorded by the catalogue are kept "
                "as compiler's notes. Differences from ESO's other accounts of the same calls "
                "(e.g. 17:32 vs 17:22 for informing TNCC) are not reconciled here."
            ),
            "segments": r08_specs,
        }
    return recon_doc_specs.NEW_DOC_SPECS[doc_id]


def provenance_documents(
    written: dict[str, bytes], r08_specs: list[dict[str, Any]]
) -> dict[str, Any]:
    documents: dict[str, Any] = {}
    for doc_id in sorted(DOC_META):
        data = doc_bytes(doc_id, written)
        lines = text_lines(data)
        spec = doc_specs_for(doc_id, r08_specs)
        segments = resolve_segments(doc_id, lines, spec["segments"])
        entry: dict[str, Any] = {
            "label": LABELS[doc_id],
            "text_file": f"{doc_id}/{doc_id}.txt",
            "text_sha256": sha256_bytes(data),
            "line_count": len(lines),
            "origin": (
                "copied from MVP bundle 1.1.0 (byte-identical)"
                if doc_id in COPIED_DOCS
                else "MVP bundle 1.1.0 S01 with the decision-19 clock line"
                if doc_id == "S01"
                else "generated from a pinned catalogue extract"
                if doc_id == "R08"
                else "hand-authored"
            ),
            "construction": spec["construction"],
            "segments": segments,
        }
        if doc_id == "R01":
            entry["artifacts"] = {
                R01_CSV: {
                    **mvp_build.DOCUMENT_SPECS["R01"]["artifacts"][R01_CSV],
                    "sha256": sha256_bytes(written[R01_CSV]),
                }
            }
        documents[doc_id] = entry
    return documents


# --------------------------------------------------------------------------- rows


def _entry_span(lines: list[str], anchor: str, doc_id: str) -> tuple[int, int]:
    matches = [i for i, line in enumerate(lines) if line.startswith(anchor)]
    if len(matches) != 1:
        raise SystemExit(f"{doc_id}: row anchor {anchor!r} matched lines {matches}")
    first = matches[0]
    last = first
    while (
        last + 1 < len(lines) and lines[last + 1][:1] == " " and lines[last + 1].strip()
    ):
        last += 1
    return first, last


def _covering_segment(segments: list[dict[str, Any]], line_no: int) -> dict[str, Any]:
    for segment in segments:
        start, end = (int(x) for x in segment["lines"][1:].split("-L"))
        if start <= line_no <= end:
            return segment
    raise SystemExit(f"no segment covers line {line_no}")


def finish_rows(
    rows: list[dict[str, Any]],
    kind: str,
    documents: dict[str, Any],
    written: dict[str, bytes],
) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        doc_id = row["evidence_id"]
        lines = text_lines(doc_bytes(doc_id, written))
        first, last = _entry_span(lines, row["anchor"], doc_id)
        segment = _covering_segment(documents[doc_id]["segments"], first + 1)
        text = row.get("text") or " ".join(" ".join(lines[first : last + 1]).split())
        finished = {k: v for k, v in row.items() if k != "anchor"}
        finished["text"] = text
        finished["kind"] = kind
        finished["provenance"] = {
            "evidence_id": doc_id,
            "doc_lines": f"L{first + 1}-L{last + 1}",
            "segment_lines": segment["lines"],
            "segment": segment["content"],
            "value_status_of_segment": segment["value_status"],
            "sources": segment["sources"],
            "index_rule": "see builder/system_response/recon/recon_rows.py docstring",
        }
        out.append(finished)
    return out


def row_outputs(
    documents: dict[str, Any],
    written: dict[str, bytes],
    r08_records: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    return {
        "recon_r03.jsonl": finish_rows(
            recon_rows.r03_rows(), "asset", documents, written
        ),
        "recon_s01.jsonl": finish_rows(
            recon_rows.s01_rows(), "asset", documents, written
        ),
        "recon_s03.jsonl": finish_rows(
            recon_rows.s03_rows(), "asset", documents, written
        ),
        "recon_s07.jsonl": finish_rows(
            recon_rows.s07_rows(), "control", documents, written
        ),
        "recon_r08.jsonl": finish_rows(
            recon_rows.r08_rows(r08_records), "control", documents, written
        ),
    }


# --------------------------------------------------------------------------- witnesses


def witness_outputs() -> dict[str, dict[str, Any]]:
    out = {}
    for card in recon_witnesses.cards():
        out[f"{card['persona_id']}.json"] = {
            "persona_id": card["persona_id"],
            "role": card["role"],
            "organisation": card["organisation"],
            "evidence_id": card["evidence_id"],
            "status": "STATUS: " + WITNESS_LABEL,
            "unknown_response": card["unknown_response"],
            "blocks": card["blocks"],
        }
    return out


# --------------------------------------------------------------------------- sources


def source_records() -> dict[str, Any]:
    handoff = handoff_dir()
    entries = {
        e["id"]: e
        for e in json.loads(
            (handoff / "source_manifest.json").read_text(encoding="utf-8")
        )
    }
    sources: dict[str, Any] = {}
    for source_id in PDF_SOURCES:
        title, published = SOURCE_TITLES[source_id]
        entry = entries[source_id]
        sources[source_id] = {
            "kind": "pdf",
            "title": title,
            "published": published,
            "file": entry["file"],
            "sha256": entry["sha256"],
            "url": entry["url"],
            "retrieved_date_utc": entry.get("retrieved_date_utc"),
            "licence_note": "Builder-only; never copied into the environment. Reuse rights of "
            "third-party appendix material are not cleared (handoff spec).",
        }
    for source_id in ("NESO-F", "HANDOFF-STATUS"):
        record = dict(mvp_build.SOURCE_META[source_id])
        if record["kind"] == "archive":
            entry = entries[source_id]
            record.update(file=entry["file"], sha256=entry["sha256"], url=entry["url"])
            record["retrieved_date_utc"] = entry.get("retrieved_date_utc")
        else:
            record["sha256"] = sha256_file(handoff / record["file"])
        sources[source_id] = record
    for extract_id, meta in CATALOGUE_EXTRACTS.items():
        sources[extract_id] = {
            "kind": "catalogue_extract",
            "root": "GB_CATALOGUE_DIR",
            **meta,
        }
    sources["REAL-DATA-MANIFEST"] = {
        "kind": "real_data_manifest",
        "root": "GB_REAL_DATA_DIR",
        "file": "real_data_manifest.json",
        "title": "Real-data search and verification manifest (records of datasets found, blocked "
        "or not found)",
        "sha256": "5ae03bec654fb84d1a23da3a59581957bbe314125745776c299d0d00c17adffd",
    }
    return sources


# --------------------------------------------------------------------------- metadata


def documents_meta(
    written: dict[str, bytes], witnesses: dict[str, bytes]
) -> dict[str, Any]:
    docs = []
    for doc_id in sorted(DOC_META):
        text_file = f"{doc_id}/{doc_id}.txt"
        data = doc_bytes(doc_id, written)
        artifacts = [
            {
                "file": text_file,
                "media_type": "text/plain",
                "description": TEXT_DESCRIPTION,
                "sha256": sha256_bytes(data),
            }
        ]
        if doc_id == "R01":
            mvp = json.loads(
                (MVP_BUNDLE_DIR / "manifest.json").read_text(encoding="utf-8")
            )
            r01 = next(d for d in mvp["documents"] if d["doc_id"] == "R01")
            artifacts = []
            for artifact in r01["artifacts"]:
                artifacts.append(
                    {**artifact, "sha256": sha256_bytes(written[artifact["file"]])}
                )
        docs.append(
            {
                "doc_id": doc_id,
                **DOC_META[doc_id],
                "date": "2019-08-09",
                "label": LABELS[doc_id],
                "text_file": text_file,
                "artifacts": artifacts,
            }
        )
    cards = []
    for name, data in sorted(witnesses.items()):
        card = json.loads(data)
        cards.append(
            {
                "persona_id": card["persona_id"],
                "role": card["role"],
                "organisation": card["organisation"],
                "evidence_id": card["evidence_id"],
                "file": f"witnesses/{name}",
                "source_sha256_with_provenance": sha256_bytes(data),
                "blocks": len(card["blocks"]),
            }
        )
    return {
        "track": "recon",
        "generated_by": GENERATED_BY,
        "note": "Proposed manifest-v2 entries for this track's documents and witness cards. "
        "Categories R08/S07 operational_records, R10 requirements, S05/S06 distribution_returns, "
        "S12 analysis_records are proposals for the integration step. Witness cards here still "
        "carry block provenance; strip it before hashing the agent-visible copy.",
        "documents": docs,
        "witnesses": cards,
        "witness_evidence_id": WITNESS_EVIDENCE_ID,
        "row_fragments": sorted(ROW_FRAGMENTS),
        "data_returns": "builder/system_response/rows/data_returns.json",
    }


# --------------------------------------------------------------------------- build


def build() -> dict[Path, bytes]:
    written, r08 = document_outputs()
    documents = provenance_documents(written, r08["specs"])
    rows = row_outputs(documents, written, r08["records"])
    witnesses = {
        name: dumps_json(card).encode("utf-8")
        for name, card in witness_outputs().items()
    }
    registry = recon_returns.registry()

    provenance = {
        "track": "recon",
        "generated_by": GENERATED_BY,
        "verified_by": VERIFIED_BY,
        "bundle": "src/environment/incident/bundles/system_response",
        "inputs": {
            "GB_HANDOFF_DIR": "handoff root (source_manifest.json, SOURCE_STATUS.md)",
            "GB_TEXT_DIR": "per-page extracted PDF text {ESO,APP,OFG,E3C,E3C-I}.txt",
            "GB_CATALOGUE_DIR": "source catalogue extracts named in sources (sha256 pinned)",
            "GB_REAL_DATA_DIR": "real_data_manifest.json (refusal basis only)",
        },
        "quote_normalisation": "NFKC; casefold; unify dashes, double quotes and apostrophes; "
        "drop soft hyphens; collapse whitespace. PDF quotes are matched within the stated "
        "1-based PDF page; catalogue quotes within the named row and field.",
        "number_rule": "Every number on a sourced line of R08, R10, S05, S06, S07, S12 and in "
        "every witness answer occurs in its segment's quotes or source section labels, or is "
        "listed in the segment's allow_numbers with the reason in transformation.",
        "sources": source_records(),
        "documents": documents,
        "witnesses": {
            json.loads(data)["persona_id"]: {
                "file": f"witnesses/{name}",
                "label": WITNESS_LABEL,
                "blocks": {
                    block["response_id"]: {
                        "topics": block["topics"],
                        "sources": block["provenance"],
                    }
                    for block in json.loads(data)["blocks"]
                },
            }
            for name, data in sorted(witnesses.items())
        },
        "row_fragments": {
            name: {
                "evidence_id": ROW_FRAGMENTS[name],
                "rows": len(items),
                "sha256": sha256_bytes(dumps_jsonl(items).encode("utf-8")),
            }
            for name, items in sorted(rows.items())
        },
        "data_returns": {
            "file": "builder/system_response/rows/data_returns.json",
            "not_held_basis": [
                {"party": p, "data_type": t, "basis": basis}
                for (p, t), basis in sorted(recon_returns.NOT_HELD_BASIS.items())
            ],
            "note": recon_returns.NOT_HELD_NOTE,
        },
        "r08_extract": {k: v for k, v in r08.items() if k not in ("specs", "records")},
    }

    outputs: dict[Path, bytes] = {}
    for rel, data in written.items():
        outputs[SR_BUNDLE_DIR / rel] = data
    for name, data in witnesses.items():
        outputs[WITNESS_DIR / name] = data
    for name, items in rows.items():
        outputs[ROWS_DIR / name] = dumps_jsonl(items).encode("utf-8")
    outputs[DATA_RETURNS_PATH] = dumps_json(registry).encode("utf-8")
    outputs[DOCUMENTS_META_PATH] = dumps_json(
        documents_meta(written, witnesses)
    ).encode("utf-8")
    outputs[PROVENANCE_PATH] = dumps_json(provenance).encode("utf-8")
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="compare with disk, write nothing"
    )
    args = parser.parse_args(argv)
    for doc_id in AUTHORED_DOCS:
        if not (SR_BUNDLE_DIR / doc_id / f"{doc_id}.txt").is_file():
            raise SystemExit(f"missing authored document {doc_id}")
    outputs = build()
    stale = []
    for path, data in sorted(outputs.items()):
        current = path.read_bytes() if path.is_file() else None
        if current != data:
            stale.append(path)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    for path in sorted(outputs):
        print(
            f"{'STALE ' if args.check and path in stale else ''}{path.relative_to(ENV_ROOT)}"
        )
    if args.check and stale:
        print(f"{len(stale)} output(s) differ from a fresh build")
        return 1
    print(
        f"{len(outputs)} outputs; {len(stale)} {'differ' if args.check else 'written'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
