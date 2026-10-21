"""Mirror the open-licensed raw inputs of fi_build_real.py into builder/full_investigation/raw/.

Builder-only. The mirror keeps the relative layout of ``GB_REAL_DATA_DIR`` so that
``GB_REAL_DATA_DIR=builder/full_investigation/raw`` reproduces R09, R11 and R12 byte for byte
without ``.context``. Every mirrored file is listed in ``raw/RAW_MANIFEST.json`` with the original
sha256, the mirror sha256, licence and source URL. Modes (``fi_sources.py``): ``copy``, ``slice``
(same format, fewer rows), ``extract`` (another format holding only what the builder reads, at
``mirror_rel``). Sources that are not openly licensed or only quoted (``mirror: none``) are never
copied; with this mirror the builder skips only the checks that need them.

The Network Rail explanation PDF extract is made with PyMuPDF, which the project environment does
not provide: when ``fitz`` cannot be imported the committed extract is kept and only its recorded
hashes are checked (run once with a Python that has PyMuPDF to regenerate it).

    uv run --frozen python builder/full_investigation/real/fi_sync_raw.py          # write
    uv run --frozen python builder/full_investigation/real/fi_sync_raw.py --check  # verify
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fi_r11  # noqa: E402
from fi_real_common import (  # noqa: E402
    RAW_MANIFEST_PATH,
    RAW_MIRROR_DIR,
    BuildError,
    FiInputs,
    json_bytes,
    mirror_manifest,
    real_data_dir,
    require,
    sha256_bytes,
)
from fi_sources import SOURCES  # noqa: E402

NOTE = (
    "Sparse mirror of the open-licensed real-data inputs of builder/full_investigation/real/"
    "fi_build_real.py (R09, R11, R12), laid out like GB_REAL_DATA_DIR (.context/real_data). "
    "'copy' files are byte-identical to the originals; 'slice' files keep only the rows the builder "
    "uses (rule given); 'extract' files hold, in another format, only what the builder reads from "
    "an original it cannot parse with the standard library (rule given). Inputs marked mirror "
    "'none' in fi_sources.py (posts, web pages, NESO website statements and the quoted GOV.UK and "
    "Ofgem pages) are not copied. No report PDF is copied. Written by "
    "builder/full_investigation/real/fi_sync_raw.py."
)
EXTRACT_RULES = {"nr_glossary", "nr_explanation"}


def _pdf_text(data: bytes) -> bytes | None:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError:
        return None
    document = fitz.open(stream=data, filetype="pdf")
    parts = [
        f"=== page {n} ===\n" + page.get_text() for n, page in enumerate(document, 1)
    ]
    return "".join(parts).encode("utf-8")


def build_mirror() -> tuple[dict[str, bytes], dict[str, Any]]:
    root = real_data_dir()
    inputs = FiInputs(real_dir=root)
    committed = mirror_manifest()
    files: dict[str, bytes] = {}
    entries = []
    for key in sorted(SOURCES):
        spec = SOURCES[key]
        mode = spec.get("mirror", "none")
        if mode == "none":
            continue
        original = (root / spec["rel"]).read_bytes()
        require(
            sha256_bytes(original) == spec["sha256"],
            f"{key}: {root / spec['rel']} is not the recorded original",
        )
        rel = spec["rel"]
        if mode == "copy":
            data = original
        elif mode == "slice":
            require(key == "nr_delays_p05", f"no slice rule coded for {key}")
            data = gzip.compress(fi_r11.slice_lines(original), compresslevel=9, mtime=0)
        else:
            require(key in EXTRACT_RULES, f"no extract rule coded for {key}")
            rel = spec["mirror_rel"]
            if key == "nr_glossary":
                data = fi_r11.glossary_extract(inputs)
            else:
                extracted = _pdf_text(original)
                if extracted is None:
                    entry = committed.get(rel)
                    require(
                        entry is not None,
                        f"{key}: PyMuPDF unavailable and no extract held",
                    )
                    data = (RAW_MIRROR_DIR / rel).read_bytes()
                    require(
                        sha256_bytes(data) == entry["mirror_sha256"],
                        f"{key}: committed extract does not match its manifest entry",
                    )
                else:
                    data = extracted
        files[rel] = data
        entry = {
            "rel": rel,
            "source_id": key,
            "mode": mode,
            "original_rel": spec["rel"],
            "original_sha256": spec["sha256"],
            "mirror_sha256": sha256_bytes(data),
            "bytes": len(data),
            "publisher": spec["publisher"],
            "url": spec["url"],
            "retrieved_utc": spec["retrieved_utc"],
            "licence": spec["licence"],
            "licence_text": spec["licence_text"],
            "attribution": spec["attribution"],
        }
        for field in ("slice_rule", "extract_rule"):
            if field in spec:
                entry[field] = spec[field]
        entries.append(entry)
    manifest = {
        "schema": "gb-2019-full-investigation/raw-mirror/1",
        "note": NOTE,
        "files": entries,
    }
    return files, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="verify the mirror, write nothing"
    )
    args = parser.parse_args(argv)
    try:
        files, manifest = build_mirror()
    except (BuildError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    manifest_bytes = json_bytes(manifest)
    if args.check:
        problems = []
        for rel, data in files.items():
            path = RAW_MIRROR_DIR / rel
            if not path.is_file():
                problems.append(f"missing {rel}")
            elif path.read_bytes() != data:
                same = rel.endswith(".gz") and gzip.decompress(path.read_bytes()) == (
                    gzip.decompress(data)
                )
                if not same:
                    problems.append(f"differs {rel}")
        if (
            not RAW_MANIFEST_PATH.is_file()
            or RAW_MANIFEST_PATH.read_bytes() != manifest_bytes
        ):
            problems.append("RAW_MANIFEST.json differs")
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        if problems:
            return 1
        print(f"OK: {len(files)} mirrored files match")
        return 0
    for rel, data in files.items():
        path = RAW_MIRROR_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    RAW_MANIFEST_PATH.write_bytes(manifest_bytes)
    for path in sorted(RAW_MIRROR_DIR.rglob("*"), reverse=True):
        rel = str(path.relative_to(RAW_MIRROR_DIR))
        if path.is_file() and rel not in files and path != RAW_MANIFEST_PATH:
            path.unlink()
            print(f"removed stale {rel}")
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    total = sum(len(d) for d in files.values())
    print(f"mirrored {len(files)} files ({total} bytes) into {RAW_MIRROR_DIR}")
    print(
        json.dumps(
            {e["rel"]: e["mirror_sha256"][:12] for e in manifest["files"]}, indent=1
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
