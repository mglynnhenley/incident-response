"""Write ``bundle/manifest.json`` (catalogue metadata plus sha256 of every artifact).

Builder-only tool. Titles are neutral: they identify each record, never its conclusion.
Run after any change to a bundle document or to the R01 CSV::

    uv run --frozen python builder/build_manifest.py
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any

ENV_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ENV_ROOT / "src" / "environment" / "incident" / "bundle"
MANIFEST_PATH = BUNDLE_DIR / "manifest.json"

BUNDLE_ID = "gb-2019-08-09-electrical-mvp"
BUNDLE_VERSION = "1.1.0"
R01_CSV = "R01/frequency_2019-08-09_1640-1745_BST.csv"
TEXT_DESCRIPTION = (
    "Readable record text; line numbers shown on retrieval are the citation locators."
)

DOCUMENTS: list[dict[str, Any]] = [
    {
        "doc_id": "R01",
        "title": "System frequency record, 9 August 2019, 16:40-17:45 BST",
        "owner": "National Grid ESO (NESO published dataset)",
        "date": "2019-08-09",
        "category": "measurement_data",
        "text_file": "R01/R01.txt",
        "artifacts": [
            {
                "file": "R01/R01.txt",
                "media_type": "text/plain",
                "description": "Metadata note for the frequency extract: source dataset, slice, "
                "units, sampling interval, time basis, file format and citation help.",
            },
            {
                "file": R01_CSV,
                "media_type": "text/csv",
                "description": "One-second system frequency samples; columns timestamp "
                "(ISO-8601 with explicit +01:00 offset) and frequency_hz (Hz).",
                "timeseries": {
                    "time_column": "timestamp",
                    "value_column": "frequency_hz",
                    "unit": "Hz",
                    "first": "2019-08-09T16:40:00+01:00",
                    "last": "2019-08-09T17:44:59+01:00",
                    "rows": 3900,
                    "interval_s": 1,
                },
            },
        ],
    },
    {
        "doc_id": "R03",
        "title": "Transmission fault and protection records, 9 August 2019",
        "owner": "National Grid Electricity Transmission (NGET); lightning data MeteoGroup",
        "date": "2019-08-09",
        "category": "network_records",
        "text_file": "R03/R03.txt",
        "artifacts": [
            {
                "file": "R03/R03.txt",
                "media_type": "text/plain",
                "description": TEXT_DESCRIPTION,
            }
        ],
    },
    {
        "doc_id": "S01",
        "title": "Hornsea One offshore wind farm event log, 9 August 2019",
        "owner": "Ørsted (Hornsea One operator)",
        "date": "2019-08-09",
        "category": "generator_records",
        "text_file": "S01/S01.txt",
        "artifacts": [
            {
                "file": "S01/S01.txt",
                "media_type": "text/plain",
                "description": TEXT_DESCRIPTION,
            }
        ],
    },
    {
        "doc_id": "S03",
        "title": "Little Barford power station alarm and sequence-of-events records, 9 August 2019",
        "owner": "RWE Generation (Little Barford power station)",
        "date": "2019-08-09",
        "category": "generator_records",
        "text_file": "S03/S03.txt",
        "artifacts": [
            {
                "file": "S03/S03.txt",
                "media_type": "text/plain",
                "description": TEXT_DESCRIPTION,
            }
        ],
    },
    {
        "doc_id": "S04",
        "title": "Little Barford power station shift account, 9 August 2019",
        "owner": "RWE Generation (Little Barford station operating staff)",
        "date": "2019-08-09",
        "category": "personnel_accounts",
        "text_file": "S04/S04.txt",
        "artifacts": [
            {
                "file": "S04/S04.txt",
                "media_type": "text/plain",
                "description": TEXT_DESCRIPTION,
            }
        ],
    },
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_timeseries(artifact: dict[str, Any]) -> None:
    meta = artifact["timeseries"]
    text = (BUNDLE_DIR / artifact["file"]).read_text(encoding="utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    header, data = rows[0], rows[1:]
    if header != [meta["time_column"], meta["value_column"]]:
        raise SystemExit(f"CSV header {header} does not match manifest columns")
    if (
        len(data) != meta["rows"]
        or data[0][0] != meta["first"]
        or data[-1][0] != meta["last"]
    ):
        raise SystemExit(
            "CSV rows/first/last do not match the manifest timeseries metadata"
        )


def build() -> dict[str, Any]:
    documents = []
    for template in DOCUMENTS:
        doc = json.loads(json.dumps(template))  # deep copy
        hashes = {}
        for artifact in doc["artifacts"]:
            path = BUNDLE_DIR / artifact["file"]
            if not path.is_file():
                raise SystemExit(f"missing artifact {path}")
            hashes[artifact["file"]] = sha256_file(path)
            if "timeseries" in artifact:
                check_timeseries(artifact)
        header = (
            (BUNDLE_DIR / doc["text_file"])
            .read_text(encoding="utf-8")
            .split("\n", 1)[0]
        )
        if header != f"DOCUMENT {doc['doc_id']} — {doc['title']}":
            raise SystemExit(
                f"{doc['doc_id']}: first line does not match the manifest title"
            )
        doc["sha256"] = hashes
        documents.append(doc)
    return {
        "bundle_id": BUNDLE_ID,
        "bundle_version": BUNDLE_VERSION,
        "documents": documents,
    }


def main() -> int:
    manifest = build()
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    MANIFEST_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {MANIFEST_PATH.relative_to(ENV_ROOT)}")
    for doc in manifest["documents"]:
        for name, digest in doc["sha256"].items():
            print(f"  {digest}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
