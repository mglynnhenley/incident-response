"""Build the reconstruction track's outputs for the full-investigation bundle.

Builder-only and deterministic (same inputs -> byte-identical outputs; no timestamps). Writes:

- ``bundles/full_investigation/{S08,S10,S11}/<ID>.txt``: laid out from the hand-authored
  sources ``builder/full_investigation/recon/text/<ID>.src.txt`` (``fi_text.py``);
- ``bundles/full_investigation/R10/R10.txt``: the system-response R10 (lines 1-133,
  byte-identical, hash pinned) followed by Sections F-K from ``text/R10_additions.src.txt``;
- ``bundles/full_investigation/witnesses/<persona_id>.json``: the five new S09 cards, agent-visible
  (block provenance stripped; same byte layout as the system-response integration writes);
- ``builder/full_investigation/rows/recon_s08.jsonl``: control-log row fragment (``kind`` and
  ``provenance`` per line, as in increment A);
- ``builder/full_investigation/rows/data_returns.json``: data-return registry additions;
- ``builder/full_investigation/recon/documents.json``: manifest metadata proposed for this track's
  documents, witnesses and control room;
- ``private/full_investigation/provenance_recon.json``: segment provenance of every document,
  witness block, row and registry entry, the excluded enforcement outcomes (leakage detectors)
  and the index-entry checks.

The system-response bundle's other documents, logs and witness cards are copied unchanged by the
integration step; this track neither writes nor changes them.

    uv run --frozen python builder/full_investigation/recon/build_fi_recon.py          # write
    uv run --frozen python builder/full_investigation/recon/build_fi_recon.py --check  # compare
    uv run --frozen python builder/full_investigation/recon/verify_fi_recon.py
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fi_doc_specs  # noqa: E402
import fi_returns  # noqa: E402
import fi_rows  # noqa: E402
import fi_text  # noqa: E402
import fi_witnesses  # noqa: E402
import recon_doc_specs as sr_doc_specs  # noqa: E402  (increment A; frozen R10 spec)
from fi_recon_common import (  # noqa: E402
    AUTHORED_DOCS,
    CATALOGUE_EXTRACTS,
    DATA_RETURNS_PATH,
    DOCUMENTS_META_PATH,
    ENV_ROOT,
    FI_BUNDLE_DIR,
    FI_ROWS_DIR,
    GENERATED_BY,
    LABELS,
    PDF_SOURCES,
    PROVENANCE_PATH,
    R10_FROZEN_LINES,
    R10_FROZEN_SHA256,
    REAL_DATA_MANIFEST_SHA256,
    REAL_FILES,
    ROW_FRAGMENT,
    SOURCE_TITLES,
    SR_BUNDLE_DIR,
    SR_PRIVATE_DIR,
    TEXT_SRC_DIR,
    VERIFIED_BY,
    WITNESS_DIR,
    WITNESS_EVIDENCE_ID,
    WITNESS_LABEL,
    dumps_card,
    dumps_json,
    dumps_jsonl,
    handoff_dir,
    resolve_segments,
    sha256_bytes,
    sha256_file,
    text_lines,
)

DOC_META: dict[str, dict[str, Any]] = {
    "R10": {
        "title": "Operating requirements as described in the published reports (selection)",
        "owner": "Compiled from National Grid ESO, Ofgem, E3C and ORR reports",
        "category": "requirements",
        "party_aliases": ["system operator", "regulator"],
    },
    "S08": {
        "title": "Rail fleet and service records, 9 August 2019",
        "owner": "Govia Thameslink Railway (fleet technical review); rail accounts published by "
        "ORR, National Grid ESO, Ofgem and the E3C",
        "category": "rail_records",
        "party_aliases": ["train operator", "GTR", "rail regulator"],
    },
    "S10": {
        "title": "Generator and network compliance-process records, 9 August 2019",
        "owner": "National Grid ESO (compliance process records); Ofgem and E3C statements",
        "category": "compliance_records",
        "party_aliases": ["system operator", "regulator"],
    },
    "S11": {
        "title": "Essential services and infrastructure supply impact records, 9 August 2019",
        "owner": "Compiled from National Grid ESO, Ofgem, E3C and ORR published accounts",
        "category": "essential_services_records",
        "party_aliases": ["system operator", "regulator", "E3C"],
    },
}
TEXT_DESCRIPTION = (
    "Readable record text; line numbers shown on retrieval are the citation locators."
)
CONTROL_LOGS = {
    fi_rows.ROOM_GTR: {
        "title": "GTR fleet control: technical-review entries with a printed clock time",
        "owner": "Govia Thameslink Railway (technical review dated 3 September 2019)",
        "evidence_ids": ["S08"],
        "clock_note": {"S08": fi_rows.GTR_CLOCK},
        "source_note": {
            "S08": "rows restate entries of the reconstructed rail fleet record S08."
        },
        "status": "STATUS: SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE (rows of S08).",
    }
}

# --------------------------------------------------------------------------- documents


def r10_bytes() -> bytes:
    frozen = (SR_BUNDLE_DIR / "R10" / "R10.txt").read_bytes()
    if sha256_bytes(frozen) != R10_FROZEN_SHA256:
        raise SystemExit(
            "system-response R10 is not the frozen 0.1.0 text (sha256 differs)"
        )
    if len(text_lines(frozen)) != R10_FROZEN_LINES:
        raise SystemExit("system-response R10 line count changed")
    additions = fi_text.layout(
        (TEXT_SRC_DIR / "R10_additions.src.txt")
        .read_text(encoding="utf-8")
        .lstrip("\n")
    )
    return frozen + b"\n" + additions.encode("utf-8")


def document_outputs() -> dict[str, bytes]:
    out = {"R10/R10.txt": r10_bytes()}
    for doc_id in AUTHORED_DOCS:
        source = (TEXT_SRC_DIR / f"{doc_id}.src.txt").read_text(encoding="utf-8")
        out[f"{doc_id}/{doc_id}.txt"] = fi_text.layout(source).encode("utf-8")
    return out


def doc_spec(doc_id: str) -> dict[str, Any]:
    if doc_id == "R10":
        spec = copy.deepcopy(sr_doc_specs.R10_SPEC)
        spec["construction"] += fi_doc_specs.R10_ADDITIONS_CONSTRUCTION
        spec["segments"] = spec["segments"] + copy.deepcopy(
            fi_doc_specs.R10_ADDITION_SEGMENTS
        )
        return spec
    return copy.deepcopy(getattr(fi_doc_specs, f"{doc_id}_SPEC"))


def provenance_documents(written: dict[str, bytes]) -> dict[str, Any]:
    documents: dict[str, Any] = {}
    for doc_id in sorted(DOC_META):
        data = written[f"{doc_id}/{doc_id}.txt"]
        lines = text_lines(data)
        spec = doc_spec(doc_id)
        entry: dict[str, Any] = {
            "label": LABELS[doc_id],
            "text_file": f"{doc_id}/{doc_id}.txt",
            "text_sha256": sha256_bytes(data),
            "line_count": len(lines),
            "origin": (
                f"system-response bundle 0.1.0 R10 (lines 1-{R10_FROZEN_LINES}, byte-identical, "
                f"sha256 {R10_FROZEN_SHA256}) + Sections F-K from "
                "builder/full_investigation/recon/text/R10_additions.src.txt"
                if doc_id == "R10"
                else f"hand-authored: builder/full_investigation/recon/text/{doc_id}.src.txt "
                "laid out by fi_text.py"
            ),
            "construction": spec["construction"],
            "segments": resolve_segments(doc_id, lines, spec["segments"]),
        }
        if doc_id != "R10":
            source = TEXT_SRC_DIR / f"{doc_id}.src.txt"
            entry["source_text"] = {
                "file": source.relative_to(ENV_ROOT).as_posix(),
                "sha256": sha256_file(source),
            }
        documents[doc_id] = entry
    return documents


# --------------------------------------------------------------------------- rows


def _entry_span(lines: list[str], anchor: str, doc_id: str) -> tuple[int, int]:
    matches = [i for i, line in enumerate(lines) if line.startswith(anchor)]
    if len(matches) != 1:
        raise SystemExit(f"{doc_id}: row anchor {anchor!r} matched lines {matches}")
    first = last = matches[0]
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


def row_outputs(
    documents: dict[str, Any], written: dict[str, bytes]
) -> list[dict[str, Any]]:
    out = []
    for row in fi_rows.s08_rows():
        doc_id = row["evidence_id"]
        lines = text_lines(written[f"{doc_id}/{doc_id}.txt"])
        first, last = _entry_span(lines, row["anchor"], doc_id)
        segment = _covering_segment(documents[doc_id]["segments"], first + 1)
        finished = {k: v for k, v in row.items() if k != "anchor"}
        finished["text"] = " ".join(" ".join(lines[first : last + 1]).split())
        finished["kind"] = "control"
        finished["provenance"] = {
            "evidence_id": doc_id,
            "doc_lines": f"L{first + 1}-L{last + 1}",
            "segment_lines": segment["lines"],
            "segment": segment["content"],
            "value_status_of_segment": segment["value_status"],
            "sources": segment["sources"],
            "index_rule": "see builder/full_investigation/recon/fi_rows.py docstring",
        }
        out.append(finished)
    return out


# --------------------------------------------------------------------------- witnesses


def witness_cards() -> dict[str, dict[str, Any]]:
    """persona_id -> source card (blocks with provenance)."""
    out = {}
    for card in fi_witnesses.cards():
        out[card["persona_id"]] = {
            "persona_id": card["persona_id"],
            "role": card["role"],
            "organisation": card["organisation"],
            "evidence_id": card["evidence_id"],
            "status": "STATUS: " + WITNESS_LABEL,
            "unknown_response": card["unknown_response"],
            "blocks": card["blocks"],
        }
    return out


def visible_card(card: dict[str, Any]) -> bytes:
    public = {k: v for k, v in card.items() if k != "blocks"}
    public["blocks"] = [
        {k: v for k, v in block.items() if k != "provenance"}
        for block in card["blocks"]
    ]
    return dumps_card(public)


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
            "licence_note": (
                "Crown copyright, Open Government Licence v3.0 except where otherwise stated "
                "(ORR report footer). Builder-only; never copied into the environment."
                if source_id == "ORR"
                else "Builder-only; never copied into the environment. Reuse rights of "
                "third-party appendix material are not cleared (handoff spec)."
            ),
        }
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
        "sha256": REAL_DATA_MANIFEST_SHA256,
    }
    for raw_id, meta in REAL_FILES.items():
        sources[raw_id] = {
            "kind": "saved_web_page",
            "root": "GB_REAL_DATA_DIR",
            "use": "fact check and word-overlap check of an index entry only; not mirrored",
            **{
                k: v
                for k, v in meta.items()
                if k not in ("statement_start", "statement_end")
            },
        }
    return sources


# --------------------------------------------------------------------------- metadata


def documents_meta(
    written: dict[str, bytes], visible: dict[str, bytes], rows_bytes: bytes
) -> dict[str, Any]:
    docs = []
    for doc_id in sorted(DOC_META):
        text_file = f"{doc_id}/{doc_id}.txt"
        meta = DOC_META[doc_id]
        entry = {
            "doc_id": doc_id,
            "title": meta["title"],
            "owner": meta["owner"],
            "category": meta["category"],
            "party_aliases": meta["party_aliases"],
            "date": "2019-08-09",
            "label": LABELS[doc_id],
            "text_file": text_file,
            "artifacts": [
                {
                    "file": text_file,
                    "media_type": "text/plain",
                    "description": TEXT_DESCRIPTION,
                    "sha256": sha256_bytes(written[text_file]),
                }
            ],
        }
        if doc_id == "R10":
            entry["replaces"] = (
                "system-response R10 in this bundle only (lines 1-133 identical; Sections F-K "
                "appended)"
            )
        docs.append(entry)
    cards = []
    for persona_id, data in sorted(visible.items()):
        card = json.loads(data)
        cards.append(
            {
                "persona_id": persona_id,
                "role": card["role"],
                "organisation": card["organisation"],
                "evidence_id": card["evidence_id"],
                "file": f"witnesses/{persona_id}.json",
                "sha256": sha256_bytes(data),
                "blocks": len(card["blocks"]),
            }
        )
    logs = []
    for room_id, meta in sorted(CONTROL_LOGS.items()):
        logs.append({"room_id": room_id, **meta})
    return {
        "track": "recon",
        "generated_by": GENERATED_BY,
        "note": "Proposed manifest-v2 entries for this track's additions to the full-investigation "
        "bundle. Everything else (increment A's documents, logs, five witness cards and 17 data "
        "returns) is copied unchanged from the system-response bundle by the integration step. "
        "Categories are proposals. Witness cards are written agent-visible (provenance stripped; "
        "block provenance is in private/full_investigation/provenance_recon.json). "
        "rows/data_returns.json holds the registry additions only. The control room "
        "GTR-FLEET-CONTROL is new and needs log metadata (proposed below) and a viewer station.",
        "documents": docs,
        "witnesses": cards,
        "witness_evidence_id": WITNESS_EVIDENCE_ID,
        "control_logs": logs,
        "row_fragments": {
            ROW_FRAGMENT: {
                "rows": len(rows_bytes.splitlines()),
                "sha256": sha256_bytes(rows_bytes),
            }
        },
        "data_returns": {
            "file": "builder/full_investigation/rows/data_returns.json",
            "mode": "additions to the system-response registry (no overlap of party/data_type)",
            "parties": fi_returns.PARTIES,
        },
    }


# --------------------------------------------------------------------------- build


EXCLUDED_NOTE = (
    "Decision 50: Ofgem's January 2020 enforcement outcomes (voluntary payments to the Energy "
    "Industry Voluntary Redress Scheme: Hornsea 1 and RWE Generation GBP 4.5m each; Eastern and "
    "South Eastern Power Networks GBP 1.5m in aggregate) are public but excluded from all "
    "agent-visible evidence: the handoff forbids supplying or requiring enforcement outcomes, and "
    "asserting them is severe flag SF3. They are recorded here, with their verified source "
    "passages, as a leakage/memorisation detector for the grader. Ofgem section 4 and the "
    "executive summary's settlement paragraphs are not restated anywhere in S10."
)


def excluded_records() -> dict[str, Any]:
    from fi_recon_common import EXCLUDED_PATTERNS, src

    section4 = "Section 4, Compliance, voluntary action and enforcement"
    return {
        "note": EXCLUDED_NOTE,
        "detector_patterns": list(EXCLUDED_PATTERNS),
        "passages": [
            src(
                "OFG",
                6,
                "Executive Summary, Compliance, voluntary action and enforcement",
                "agreed to make voluntary payments of £4.5m each to the Energy Industry Voluntary "
                "Redress Scheme.",
            ),
            src(
                "OFG",
                6,
                "Executive Summary, Compliance, voluntary action and enforcement",
                "agreed to make voluntary payments of £1.5m in aggregate to the Energy Industry "
                "Voluntary Redress Scheme.",
            ),
            src(
                "OFG",
                37,
                section4 + ", 4.1",
                "Each licensee has agreed to make a voluntary payment of £4.5m to the Energy "
                "Industry Voluntary Redress Scheme",
            ),
            src(
                "OFG",
                37,
                section4 + ", footnote 32",
                "Eastern Power Networks has therefore agreed to pay £1.45m and South Eastern Power "
                "Networks has agreed to pay £0.05m.",
            ),
        ],
    }


def build() -> dict[Path, bytes]:
    written = document_outputs()
    documents = provenance_documents(written)
    rows = row_outputs(documents, written)
    rows_bytes = dumps_jsonl(rows).encode("utf-8")
    cards = witness_cards()
    visible = {pid: visible_card(card) for pid, card in cards.items()}
    registry = fi_returns.registry()

    sr_provenance = SR_PRIVATE_DIR / "provenance.json"
    provenance = {
        "track": "recon",
        "generated_by": GENERATED_BY,
        "verified_by": VERIFIED_BY,
        "bundle": "src/environment/incident/bundles/full_investigation",
        "inputs": {
            "GB_HANDOFF_DIR": "handoff root (source_manifest.json)",
            "GB_TEXT_DIR": "per-page extracted PDF text {ESO,APP,OFG,E3C,E3C-I,ORR}.txt",
            "GB_CATALOGUE_DIR": "source catalogue extracts named in sources (sha256 pinned)",
            "GB_REAL_DATA_DIR": "real_data_manifest.json (refusal bases, index-entry facts) and "
            "two saved web pages behind the S11 index entries (never copied)",
        },
        "inherited": {
            "note": "Documents, logs, witness cards and data returns copied unchanged from the "
            "system-response bundle keep that bundle's provenance; R10 lines 1-133 keep increment "
            "A's segments (repeated below).",
            "provenance": sr_provenance.relative_to(ENV_ROOT).as_posix(),
            "provenance_sha256": sha256_file(sr_provenance),
        },
        "quote_normalisation": "NFKC; casefold; unify dashes, double quotes and apostrophes; "
        "drop soft hyphens; collapse whitespace. PDF quotes are matched within the stated "
        "1-based PDF page; catalogue quotes within the named row and field; real-data manifest "
        "quotes within the named record field; saved-page quotes within the page's visible text.",
        "number_rule": "Every number on a sourced line of S08, S10, S11 and R10 Sections F-K and "
        "in every new witness answer occurs in its segment's quotes or source section labels, or "
        "is listed in the segment's allow_numbers with the reason in transformation.",
        "sources": source_records(),
        "documents": documents,
        "witnesses": {
            pid: {
                "file": f"witnesses/{pid}.json",
                "visible_sha256": sha256_bytes(visible[pid]),
                "label": WITNESS_LABEL,
                "blocks": {
                    block["response_id"]: {
                        "topics": block["topics"],
                        "sources": block["provenance"],
                    }
                    for block in card["blocks"]
                },
            }
            for pid, card in sorted(cards.items())
        },
        "row_fragments": {
            ROW_FRAGMENT: {
                "evidence_id": "S08",
                "rows": len(rows),
                "sha256": sha256_bytes(rows_bytes),
                "provenance": {row["entry_id"]: row["provenance"] for row in rows},
            }
        },
        "data_returns": {
            "file": "builder/full_investigation/rows/data_returns.json",
            "mode": "additions",
            "not_held_basis": [
                {"party": p, "data_type": t, "basis": basis}
                for (p, t), basis in sorted(fi_returns.NOT_HELD_BASIS.items())
            ],
            "note": fi_returns.NOT_HELD_NOTE,
        },
        "excluded_from_agent_evidence": excluded_records(),
        "index_entries": {
            "S11 X01": "RAW-ESNEFT",
            "S11 X02": "RAW-STANLOW",
            "witness S09-HOSP-03": "RAW-ESNEFT",
            "rule": "at most three consecutive words shared with the indexed text "
            "(verify_fi_recon.py)",
        },
    }

    outputs: dict[Path, bytes] = {}
    for rel, data in written.items():
        outputs[FI_BUNDLE_DIR / rel] = data
    for pid, data in visible.items():
        outputs[WITNESS_DIR / f"{pid}.json"] = data
    outputs[FI_ROWS_DIR / ROW_FRAGMENT] = rows_bytes
    outputs[DATA_RETURNS_PATH] = dumps_json(registry).encode("utf-8")
    outputs[DOCUMENTS_META_PATH] = dumps_json(
        documents_meta(written, visible, rows_bytes)
    ).encode("utf-8")
    outputs[PROVENANCE_PATH] = dumps_json(provenance).encode("utf-8")
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="compare with disk, write nothing"
    )
    args = parser.parse_args(argv)
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
        flag = "STALE " if args.check and path in stale else ""
        print(f"{flag}{path.relative_to(ENV_ROOT)}")
    if args.check and stale:
        print(f"{len(stale)} output(s) differ from a fresh build")
        return 1
    print(
        f"{len(outputs)} outputs; {len(stale)} {'differ' if args.check else 'written'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
