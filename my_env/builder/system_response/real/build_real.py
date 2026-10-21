"""Build the real-data evidence documents R02, R04, R06 and R07 of the system-response bundle.

Builder-only (excluded from the image). Reads hash-checked inputs from GB_REAL_DATA_DIR,
GB_CATALOGUE_DIR and the per-page report text (GB_HANDOFF_DIR / GB_TEXT_DIR) and writes,
relative to the environment root:

* ``src/environment/incident/bundles/system_response/{R02,R04,R06,R07}/`` - text note + CSVs;
* ``builder/system_response/rows/real_r02_asset.jsonl`` and ``real_r06_control.jsonl`` - asset
  and control-log row fragments (with private ``provenance``) for the integration step;
* ``src/environment/incident/private/system_response/provenance_real.json`` - private provenance;
* ``builder/system_response/real/documents_real.json`` - manifest-v2 fragment (documents with
  sha256, labels, asset-log and control-log contributions) for the integration step.

Usage (from the environment root)::

    uv run --frozen python builder/system_response/real/build_real.py           # write
    uv run --frozen python builder/system_response/real/build_real.py --check   # compare only
    GB_REAL_DATA_DIR=builder/system_response/raw uv run --frozen python \\
        builder/system_response/real/build_real.py --check   # rebuild from the raw mirror

The same inputs always give byte-identical outputs.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import real_r02  # noqa: E402
import real_r04  # noqa: E402
import real_r06  # noqa: E402
import real_r07  # noqa: E402
from real_common import (  # noqa: E402
    BUNDLE_REL,
    ENV_ROOT,
    PRIVATE_REL,
    REAL_REL,
    ROWS_REL,
    BuildError,
    Inputs,
    json_bytes,
    jsonl_bytes,
    require,
    sha256_bytes,
)
from real_docbuild import DocBuild  # noqa: E402
from real_sources import SOURCES, public_source  # noqa: E402

DOC_IDS = ("R02", "R04", "R06", "R07")
BUILDERS = {"R02": real_r02, "R04": real_r04, "R06": real_r06, "R07": real_r07}
ROW_FILES = {"asset": "real_r02_asset.jsonl", "control": "real_r06_control.jsonl"}
PROVENANCE_NAME = "provenance_real.json"
DOCUMENTS_NAME = "documents_real.json"

REPORTS = {
    "ESO": {
        "title": "National Grid ESO, Technical Report on the events of 9 August 2019",
        "published": "2019-09-06",
        "licence": "National Grid ESO document hosted by Ofgem; not an open licence (builder-only)",
    },
    "APP": {
        "title": "Appendices to the ESO Technical Report on the events of 9 August 2019",
        "published": "2019-09-06",
        "licence": "National Grid ESO document hosted by Ofgem, includes third-party material; "
        "not an open licence (builder-only)",
    },
    "OFG": {
        "title": "Ofgem, 9 August 2019 power outage report",
        "published": "2020-01-03",
        "licence": "Open Government Licence v3.0 with exclusions (builder-only copy)",
    },
    "E3C-I": {
        "title": "Energy Emergencies Executive Committee, GB power system disruption - 9 August "
        "2019, interim report",
        "published": "cover dated September 2019; publisher file name dated 2019-10-03",
        "licence": "Open Government Licence v3.0 with exclusions (builder-only copy)",
    },
}

EXCLUDED = [
    {
        "item": "Text of archived DNO social-media posts (consequences dataset)",
        "reason": "Post text is the account holders' copyright under platform terms (not an open "
        "licence). R07 Part D gives the post time decoded from the post identifier and a short "
        "summary written for this exercise; no post text, handles or personal names are "
        "reproduced.",
    },
    {
        "item": "MeteoGroup / DTN, Met Office ATDnet and Blitzortung lightning stroke records",
        "reason": "Not publicly available (blocked or proprietary). R04 Part E reproduces only "
        "what the published ESO and NGET figures display.",
    },
    {
        "item": "Elexon physical notifications (PN) for 9 August 2019 after settlement period 4",
        "reason": "Absent from the publisher's API (ingestion gap); stated in R02 B9.",
    },
    {
        "item": "Report PDFs and NESO website documents",
        "reason": "Not open-licensed; never copied into the environment. Report tables are "
        "transcribed cell by cell with page references.",
    },
]


def build_docs(inputs: Inputs) -> list[DocBuild]:
    return [BUILDERS[doc_id].build(inputs) for doc_id in DOC_IDS]


def _handoff_sources(inputs: Inputs) -> dict[str, Any]:
    manifest = json.loads(
        (inputs.handoff / "source_manifest.json").read_text(encoding="utf-8")
    )
    by_id = {entry["id"]: entry for entry in manifest}
    out = {}
    for source_id, meta in REPORTS.items():
        entry = by_id[source_id]
        out[source_id] = {
            "kind": "pdf",
            **meta,
            "file": entry["file"],
            "sha256": entry["sha256"],
            "url": entry["url"],
            "retrieved_date_utc": entry.get("retrieved_date_utc"),
            "root": "GB_HANDOFF_DIR",
            "page_text": f"GB_TEXT_DIR/{source_id}.txt",
        }
    return out


def _catalogue_source(inputs: Inputs) -> dict[str, Any]:
    data = (inputs.cat_dir / "catalogue.json").read_bytes()
    return {
        "kind": "catalogue",
        "title": "Builder-only source artifact catalogue (tables extracted from the report PDFs)",
        "file": "catalogue.json",
        "sha256": sha256_bytes(data),
        "root": "GB_CATALOGUE_DIR",
    }


def _rows_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    return {
        "count": len(rows),
        f"by_{key}": dict(sorted(Counter(r[key] for r in rows).items())),
    }


def build_outputs(
    inputs: Inputs | None = None,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Every output file (path relative to the environment root) and a build report."""
    inputs = inputs or Inputs()
    docs = build_docs(inputs)
    outputs: dict[str, bytes] = {}
    documents_fragment = []
    prov_docs: dict[str, Any] = {}
    asset_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    for doc in docs:
        text = doc.text.render()
        folder = BUNDLE_REL / doc.doc_id
        outputs[str(folder / doc.text_name)] = text
        artifacts = [
            {
                "file": f"{doc.doc_id}/{doc.text_name}",
                "media_type": "text/plain",
                "description": "Readable record text; line numbers shown on retrieval are the "
                "citation locators.",
            }
        ]
        hashes = {f"{doc.doc_id}/{doc.text_name}": sha256_bytes(text)}
        prov_artifacts = {}
        for art in doc.artifacts:
            rel = f"{doc.doc_id}/{art.name}"
            outputs[str(folder / art.name)] = art.data
            entry = {
                "file": rel,
                "media_type": art.media_type,
                "description": art.description,
            }
            if art.timeseries:
                entry["timeseries"] = art.timeseries
            artifacts.append(entry)
            hashes[rel] = art.sha256
            prov_artifacts[rel] = {
                **art.provenance,
                "sha256": art.sha256,
                "bytes": len(art.data),
            }
        documents_fragment.append(
            {
                "doc_id": doc.doc_id,
                "title": doc.title,
                "owner": doc.owner,
                "date": doc.date,
                "category": doc.category,
                "label": doc.label,
                "text_file": f"{doc.doc_id}/{doc.text_name}",
                "artifacts": artifacts,
                "sha256": hashes,
            }
        )
        lines = text.decode("utf-8").split("\n")[:-1]
        prov_docs[doc.doc_id] = {
            "label": doc.label,
            "text_file": f"{doc.doc_id}/{doc.text_name}",
            "text_sha256": sha256_bytes(text),
            "line_count": len(lines),
            "construction": doc.construction,
            "segments": doc.text.segments(),
            "artifacts": prov_artifacts,
        }
        asset_rows.extend(doc.asset_rows)
        control_rows.extend(doc.control_rows)

    asset_rows.sort(
        key=lambda r: (r["asset_id"], r["signal"], r["index_time_utc"], r["event_id"])
    )
    control_rows.sort(key=lambda r: (r["room_id"], r["index_time_utc"], r["entry_id"]))
    for rows, id_key in ((asset_rows, "event_id"), (control_rows, "entry_id")):
        ids = [r[id_key] for r in rows]
        require(len(ids) == len(set(ids)), f"duplicate {id_key}")
    asset_bytes = jsonl_bytes(asset_rows)
    control_bytes = jsonl_bytes(control_rows)
    outputs[str(ROWS_REL / ROW_FILES["asset"])] = asset_bytes
    outputs[str(ROWS_REL / ROW_FILES["control"])] = control_bytes

    # Every registered dataset is referenced by some segment, artifact or row; listing all of
    # them keeps the provenance identical whichever data directory (original or mirror) is read.
    sources: dict[str, Any] = {}
    sources.update(_handoff_sources(inputs))
    sources["CATALOGUE"] = _catalogue_source(inputs)
    for key in sorted(SOURCES):
        sources[key] = public_source(key)
    referenced = _referenced_sources(prov_docs, asset_rows, control_rows)
    require(
        referenced <= set(sources),
        f"unregistered sources {sorted(referenced - set(sources))}",
    )
    require(
        set(SOURCES) <= referenced,
        f"unused sources {sorted(set(SOURCES) - referenced)}",
    )
    provenance = {
        "schema": "gb-2019-system-response/provenance-real/1",
        "generated_by": "builder/system_response/real/build_real.py",
        "documents_covered": list(DOC_IDS),
        "quote_normalisation": "NFKC; casefold; unify dashes, double quotes and apostrophes; "
        "drop soft hyphens; collapse whitespace (builder/verify_provenance.normalise). Report "
        "quotes are matched within the stated 1-based PDF page of GB_TEXT_DIR/<source>.txt; "
        "table cells are matched on the page with whitespace removed.",
        "page_numbering": "pdf_page is the 1-based PDF page index; printed_page is the number "
        "printed on that page where known (ESO = pdf_page + 1; OFG = pdf_page; APP, E3C-I null).",
        "value_statuses": "measured, reported, estimated, modelled, digitised, illustrative, "
        "framing",
        "sources": sources,
        "documents": prov_docs,
        "rows": {
            ROW_FILES["asset"]: {
                "sha256": sha256_bytes(asset_bytes),
                **_rows_summary(asset_rows, "signal"),
            },
            ROW_FILES["control"]: {
                "sha256": sha256_bytes(control_bytes),
                **_rows_summary(control_rows, "room_id"),
            },
        },
        "excluded": EXCLUDED,
    }
    outputs[str(PRIVATE_REL / PROVENANCE_NAME)] = json_bytes(provenance)

    fragment = {
        "schema": "gb-2019-system-response/documents-fragment/1",
        "generated_by": "builder/system_response/real/build_real.py",
        "note": "Manifest-v2 fragment for the integration step. 'category' values are proposals "
        "(the MVP categories plus two new ones); 'label' is the STATUS label of the text note.",
        "documents": documents_fragment,
        "asset_logs": real_r02.ASSET_LOG_CONTRIB,
        "control_logs": real_r06.CONTROL_LOG_CONTRIB,
        "row_files": {k: f"{ROWS_REL}/{v}" for k, v in ROW_FILES.items()},
    }
    outputs[str(REAL_REL / DOCUMENTS_NAME)] = json_bytes(fragment)

    report = {
        "inputs_used": {k: v for k, v in sorted(inputs.used.items())},
        "verification_skipped": inputs.skipped,
        "real_data_dir": str(inputs.real_dir),
        "asset_rows": len(asset_rows),
        "control_rows": len(control_rows),
        "outputs": {k: sha256_bytes(v) for k, v in sorted(outputs.items())},
    }
    return outputs, report


def _referenced_sources(
    prov_docs: dict[str, Any],
    asset_rows: list[dict[str, Any]],
    control_rows: list[dict[str, Any]],
) -> set[str]:
    found: set[str] = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "source_id" and isinstance(value, str):
                    found.add(value)
                elif key == "source_ids" and isinstance(value, list):
                    found.update(value)
                else:
                    walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(prov_docs)
    walk([r["provenance"] for r in asset_rows + control_rows])
    return found


def owned_dirs() -> list[Path]:
    return [ENV_ROOT / BUNDLE_REL / doc_id for doc_id in DOC_IDS]


def write_outputs(outputs: dict[str, bytes], root: Path) -> list[str]:
    written = []
    for rel, data in sorted(outputs.items()):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and path.read_bytes() == data:
            continue
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            handle.write(data)
            temp = Path(handle.name)
        temp.chmod(0o644)
        temp.replace(path)
        written.append(rel)
    # Remove stale files from the document folders this builder owns.
    expected = {str((root / rel).resolve()) for rel in outputs}
    for doc_id in DOC_IDS:
        folder = root / BUNDLE_REL / doc_id
        for path in sorted(folder.glob("*")):
            if path.is_file() and str(path.resolve()) not in expected:
                path.unlink()
                written.append(f"removed {path.relative_to(root)}")
    return written


def check_outputs(outputs: dict[str, bytes], root: Path) -> list[str]:
    problems = []
    for rel, data in sorted(outputs.items()):
        path = root / rel
        if not path.is_file():
            problems.append(f"missing {rel}")
        elif path.read_bytes() != data:
            problems.append(f"differs {rel}")
    for doc_id in DOC_IDS:
        folder = root / BUNDLE_REL / doc_id
        for path in sorted(folder.glob("*")):
            rel = str(path.relative_to(root))
            if rel not in outputs:
                problems.append(f"stray {rel}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare, write nothing")
    parser.add_argument("--out-root", type=Path, default=ENV_ROOT, help="output root")
    parser.add_argument(
        "--report", action="store_true", help="print the build report as JSON"
    )
    args = parser.parse_args(argv)
    try:
        outputs, report = build_outputs()
    except BuildError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if args.check:
        problems = check_outputs(outputs, args.out_root)
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        if problems:
            return 1
        print(
            f"OK: {len(outputs)} outputs match ({report['asset_rows']} asset rows, "
            f"{report['control_rows']} control rows)"
        )
    else:
        written = write_outputs(outputs, args.out_root)
        for rel in written:
            print(f"wrote {rel}")
        print(f"{len(outputs)} outputs ({len(written)} changed)")
    for note in report["verification_skipped"]:
        print(f"note: {note}")
    if args.report:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
