"""Build the real-data evidence documents R09, R11 and R12 of the full-investigation bundle.

Builder-only (excluded from the image). Reads hash-checked inputs from GB_REAL_DATA_DIR,
GB_CATALOGUE_DIR and the per-page report text (GB_HANDOFF_DIR / GB_TEXT_DIR) and writes,
relative to the environment root:

* ``src/environment/incident/bundles/full_investigation/{R09,R11,R12}/`` - text note + CSVs;
* ``builder/full_investigation/rows/real_r09_asset.jsonl`` (REMIT events on HORNSEA-ONE and
  LITTLE-BARFORD), ``real_r09_control.jsonl`` (ESO-COMMS) and ``real_r11_control.jsonl``
  (NETWORK-RAIL-CONTROL) - row fragments with private ``provenance`` for the integration step;
* ``src/environment/incident/private/full_investigation/provenance_real.json`` - private
  provenance of these documents and rows (increment A's real documents R02, R04, R06 and R07 are
  copied unchanged by the integration step and keep their own provenance);
* ``builder/full_investigation/real/documents_real.json`` - manifest-v2 fragment.

Evidence IDs (recorded choice): R09 keeps its handoff number (external communications). The real
consequences data that the handoff places inside the reconstructed S08 (rail fleet records) and
S11 (essential services) are separate real-data documents with new IDs that do not clash with any
handoff R/S number: R11 rail performance records (Network Rail, ORR) and R12 essential-service
public statements. S08 and S11 stay reconstructions owned by the reconstruction track.

Usage (from the environment root)::

    uv run --frozen python builder/full_investigation/real/fi_build_real.py           # write
    uv run --frozen python builder/full_investigation/real/fi_build_real.py --check   # compare
    GB_REAL_DATA_DIR=builder/full_investigation/raw uv run --frozen python \\
        builder/full_investigation/real/fi_build_real.py --check   # rebuild from the mirror

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

import fi_r09  # noqa: E402
import fi_r11  # noqa: E402
import fi_r12  # noqa: E402
from fi_real_common import (  # noqa: E402
    BUILDER,
    BUNDLE_REL,
    ENV_ROOT,
    PRIVATE_REL,
    REAL_REL,
    REPORTS,
    ROWS_REL,
    BuildError,
    FiInputs,
    json_bytes,
    jsonl_bytes,
    require,
    sha256_bytes,
)
from fi_sources import SOURCES, public_source  # noqa: E402

DOC_IDS = ("R09", "R11", "R12")
BUILDERS = {"R09": fi_r09, "R11": fi_r11, "R12": fi_r12}
ROW_FILES = {
    "real_r09_asset.jsonl": ("asset", "R09"),
    "real_r09_control.jsonl": ("control", "R09"),
    "real_r11_control.jsonl": ("control", "R11"),
}
PROVENANCE_NAME = "provenance_real.json"
DOCUMENTS_NAME = "documents_real.json"
SCHEMA_PREFIX = "gb-2019-full-investigation"

EXCLUDED = [
    {
        "item": "Ofgem press release of 3 January 2020 (payments by the companies involved) and "
        "the GOV.UK press release of 3 January 2020 that reports them",
        "reason": "Decision 50: enforcement settlements are not agent-visible evidence (the "
        "handoff forbids requiring or supplying enforcement outcomes; asserting them is severe "
        "flag SF3). Kept here only as a leakage detector.",
        "sources": [
            {
                "file": "consequences/raw/docs/ofgem_pr_2020-01-03_companies_pay_10.5m.html",
                "sha256": "c9c2a16d817f3e789b8fcbc7349249deb043ff4e190b2bc7e64c8b324ee5e694",
                "url": "https://www.ofgem.gov.uk/press-release/"
                "companies-pay-ps105-million-over-9-august-power-cut",
            },
            {
                "file": "consequences/raw/comms/govuk_content_measures-to-make-britains-power-"
                "network-more-resilient-planned-after-august-power-outage.json",
                "sha256": "a369ce1ec648bfb4a983acf07bb6df979a9f899c50161fb45d40bb18b649320a",
                "url": "https://www.gov.uk/api/content/government/news/measures-to-make-"
                "britains-power-network-more-resilient-planned-after-august-power-outage",
            },
        ],
        "leakage_markers": [
            "4.5 million",
            "£4.5m",
            "£1.5m",
            "£10.5 million",
            "voluntary payments",
        ],
    },
    {
        "item": "NESO web pages 'National Grid ESO response to E3C and Ofgem reports' (2020) and "
        "'09 August 2019: one year on' (2020)",
        "reason": "Published after the period R09 covers; the response page accompanies the "
        "January 2020 enforcement outcome (decision 50).",
    },
    {
        "item": "Hydrocarbon Processing / Reuters article of 12 September 2019 on a power cut at "
        "the Stanlow refinery",
        "reason": "A different event (12 September 2019), and the publisher states 'COPYING AND "
        "DISTRIBUTING ARE PROHIBITED WITHOUT PERMISSION OF THE PUBLISHER': not licensed, so not "
        "included even as a dated distractor.",
        "sources": [
            {
                "file": "consequences/raw/docs/"
                "hydrocarbonprocessing_2019-09-12_stanlow_power_cut_DIFFERENT_EVENT.html",
                "sha256": "b8fb9c1bd628b610a06db2096bc557d3ca37bea410c9083a9f51aff87c507803",
            }
        ],
    },
    {
        "item": "Text of public posts, web statements and pages (ESO, DNOs, train operators, "
        "National Rail Enquiries, ESNEFT)",
        "reason": "Not openly licensed. R09 Part E and R12 Part A give times, organisations and "
        "gists written for this record; no gist shares more than three consecutive words with "
        "its source.",
    },
    {
        "item": "Posts by personal accounts (including a minister's account), replies to members "
        "of the public, account handles and personal names",
        "reason": "Decision 51: organisational public statements only; no personal handles. "
        "Personal names printed in ESO Table 8 are replaced by roles.",
    },
    {
        "item": "Thameslink service-updates page (capture 2019-08-09T17:53:53Z) and the "
        "Newcastle Airport post of 15 August 2019",
        "reason": "Not used: the Thameslink page carries the same notice as the National Rail "
        "Enquiries page in R09 with ambiguous item times; the airport post is not about 9 "
        "August.",
    },
    {
        "item": "Network Rail records of other incidents in period 2019-20 P5",
        "reason": "Outside R11's stated selection rule (incident start on 9 August 2019 and "
        "reason XK or responsible manager METR). Not judged for relevance.",
    },
    {
        "item": "Elexon REMIT message of T_DRAXX-4 (2016) held in the same retrieval batch",
        "reason": "Outside R09's unit selection (Hornsea One and Little Barford).",
    },
]


def build_docs(inputs: FiInputs) -> list[Any]:
    return [BUILDERS[doc_id].build(inputs) for doc_id in DOC_IDS]


def _handoff_sources(inputs: FiInputs) -> dict[str, Any]:
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


def _catalogue_source(inputs: FiInputs) -> dict[str, Any]:
    data = (inputs.cat_dir / "catalogue.json").read_bytes()
    return {
        "kind": "catalogue",
        "title": "Builder-only source artifact catalogue (tables extracted from the report PDFs)",
        "file": "catalogue.json",
        "sha256": sha256_bytes(data),
        "root": "GB_CATALOGUE_DIR",
    }


def _referenced_sources(obj: Any) -> set[str]:
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "source_id" and isinstance(value, str):
                    found.add(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(obj)
    return found


def build_outputs(
    inputs: FiInputs | None = None,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Every output file (path relative to the environment root) and a build report."""
    inputs = inputs or FiInputs()
    docs = build_docs(inputs)
    outputs: dict[str, bytes] = {}
    fragment_docs = []
    prov_docs: dict[str, Any] = {}
    rows_by_file: dict[str, list[dict[str, Any]]] = {name: [] for name in ROW_FILES}
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
        fragment_docs.append(
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
                "party_aliases_proposal": doc.party_aliases,
                "keywords_proposal": doc.keywords,
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
            **({"notes": doc.notes} if doc.notes else {}),
        }
        for row in doc.asset_rows + doc.control_rows:
            name = f"real_{doc.doc_id.lower()}_{row['kind']}.jsonl"
            require(name in rows_by_file, f"no row file for {name}")
            rows_by_file[name].append(row)

    rows_summary: dict[str, Any] = {}
    for name, rows in rows_by_file.items():
        kind, evidence_id = ROW_FILES[name]
        require(rows, f"{name}: no rows")
        id_key = "event_id" if kind == "asset" else "entry_id"
        log_key = "asset_id" if kind == "asset" else "room_id"
        rows.sort(key=lambda r: (r[log_key], r["index_time_utc"], r[id_key]))
        ids = [r[id_key] for r in rows]
        require(len(ids) == len(set(ids)), f"{name}: duplicate {id_key}")
        require(
            {r["evidence_id"] for r in rows} == {evidence_id}, f"{name}: evidence IDs"
        )
        data = jsonl_bytes(rows)
        outputs[str(ROWS_REL / name)] = data
        by = "signal" if kind == "asset" else "room_id"
        rows_summary[name] = {
            "sha256": sha256_bytes(data),
            "count": len(rows),
            f"by_{by}": dict(sorted(Counter(r[by] for r in rows).items())),
        }

    sources: dict[str, Any] = {}
    sources.update(_handoff_sources(inputs))
    sources["CATALOGUE"] = _catalogue_source(inputs)
    for key in sorted(SOURCES):
        sources[key] = public_source(key)
    referenced = _referenced_sources(prov_docs) | _referenced_sources(
        [r["provenance"] for rows in rows_by_file.values() for r in rows]
    )
    require(
        referenced <= set(sources),
        f"unregistered sources {sorted(referenced - set(sources))}",
    )
    require(
        set(SOURCES) <= referenced,
        f"unused sources {sorted(set(SOURCES) - referenced)}",
    )
    provenance = {
        "schema": f"{SCHEMA_PREFIX}/provenance-real/1",
        "generated_by": BUILDER,
        "documents_covered": list(DOC_IDS),
        "evidence_id_choice": "R09 keeps its handoff number. R11 (rail performance records) and "
        "R12 (essential-service public statements) are new IDs for the real parts of the "
        "handoff's S08 and S11; no handoff R/S number is reused. Increment A's documents are "
        "copied unchanged by the integration step with their own provenance.",
        "quote_normalisation": "NFKC; casefold; unify dashes, double quotes and apostrophes; "
        "drop soft hyphens; collapse whitespace (builder/verify_provenance.normalise). Report "
        "quotes are matched within the stated 1-based PDF page of GB_TEXT_DIR/<source>.txt; "
        "table cells on the page with whitespace removed (ESO Table 8 on PDF pages 30-31); "
        "web and API quotations in the page text with HTML tags removed; Network Rail "
        "explanation quotations in the committed text extract of the PDF.",
        "gist_rule": "A gist written for this record shares no run of more than three "
        "consecutive words with its source text (tokens [a-z0-9%]+ after casefolding); checked "
        "whenever the source is held.",
        "page_numbering": "pdf_page is the 1-based PDF page index; printed_page is the number "
        "printed on that page where known (ESO = pdf_page + 1; OFG = pdf_page; APP, E3C-I and "
        "E3C null).",
        "value_statuses": "measured, reported, estimated, modelled, digitised, illustrative, "
        "framing",
        "sources": sources,
        "documents": prov_docs,
        "rows": rows_summary,
        "excluded": EXCLUDED,
    }
    outputs[str(PRIVATE_REL / PROVENANCE_NAME)] = json_bytes(provenance)

    fragment = {
        "schema": f"{SCHEMA_PREFIX}/documents-fragment/1",
        "generated_by": BUILDER,
        "note": "Manifest-v2 fragment for the integration step. 'category', "
        "'party_aliases_proposal', 'keywords_proposal' and the log '*_proposal' fields are "
        "proposals; 'label' is the STATUS label of the text note. Rows extend increment A's "
        "HORNSEA-ONE and LITTLE-BARFORD asset logs (evidence ID R09) and add two control rooms.",
        "evidence_id_choice": provenance["evidence_id_choice"],
        "documents": fragment_docs,
        "asset_logs": fi_r09.ASSET_LOG_CONTRIB,
        "control_logs": fi_r09.CONTROL_LOG_CONTRIB + fi_r11.CONTROL_LOG_CONTRIB,
        "row_files": {name: f"{ROWS_REL}/{name}" for name in ROW_FILES},
        "data_returns_proposal": DATA_RETURNS_PROPOSAL,
    }
    outputs[str(REAL_REL / DOCUMENTS_NAME)] = json_bytes(fragment)

    report = {
        "inputs_used": dict(sorted(inputs.used.items())),
        "verification_skipped": inputs.skipped,
        "real_data_dir": str(inputs.real_dir),
        "rows": {name: len(rows) for name, rows in rows_by_file.items()},
        "outputs": {k: sha256_bytes(v) for k, v in sorted(outputs.items())},
    }
    return outputs, report


#: Proposals for the data-return registry (the integration step decides). Refusal messages
#: state only what the record basis states (increment A convention). Party names follow the
#: reconstruction track's registry (rows/data_returns.json), which already holds the not-held
#: entries for train running, airport, water and refinery logs; they are not repeated here.
DATA_RETURNS_PROPOSAL = [
    {
        "party": "NETWORK_RAIL",
        "data_type": "delay_attribution_records",
        "status": "available",
        "evidence_id": "R11",
        "message": "Network Rail delay-attribution records for incidents of 9 August 2019 with "
        "reason XK or responsible manager METR, with the code glossary, and ORR periodic tables.",
    },
    {
        "party": "ELEXON",
        "data_type": "remit_messages",
        "status": "available",
        "evidence_id": "R09",
        "message": "REMIT unavailability messages for Hornsea One and Little Barford, every "
        "revision held, with publication times, inside the external communications record.",
    },
    {
        "party": "ESO",
        "data_type": "external_communications_record",
        "status": "available",
        "evidence_id": "R09",
        "message": "Published accounts of ESO contacts with government and the regulator, media "
        "statements, public posts and web statements, and calls to DNO helplines.",
    },
    {
        "party": "ESO",
        "data_type": "control_room_communications_log",
        "status": "not_held",
        "message": "Not held in this evidence pack: no ESO control-room communication log or "
        "call recording is published; the available records are the published accounts.",
    },
    {
        "party": "HOSPITAL_TRUST",
        "data_type": "public_statement",
        "status": "available",
        "evidence_id": "R12",
        "message": "The Ipswich Hospital trust's press release of 10 August 2019 (publication "
        "details and a summary written for this record).",
    },
]


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
    parser.add_argument("--report", action="store_true", help="print the build report")
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
        print(f"OK: {len(outputs)} outputs match ({report['rows']})")
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
