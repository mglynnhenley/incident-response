"""Copy the small open-licensed raw inputs of build_real.py into builder/system_response/raw/.

Builder-only. The mirror keeps the relative layout of ``GB_REAL_DATA_DIR`` so that
``GB_REAL_DATA_DIR=builder/system_response/raw`` reproduces the real-data parts of R02, R04,
R06 and R07 byte for byte without ``.context``. Every mirrored file is listed in
``raw/RAW_MANIFEST.json`` with the original sha256, the mirror sha256, licence and source URL.
Large files are mirrored as slices (rule recorded); inputs that are not openly licensed or are
only used for quote checks (``mirror: none``) are not copied.

    uv run --frozen python builder/system_response/real/sync_raw.py          # write the mirror
    uv run --frozen python builder/system_response/real/sync_raw.py --check  # verify the mirror
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from real_common import (  # noqa: E402
    RAW_MANIFEST_PATH,
    RAW_MIRROR_DIR,
    BuildError,
    json_bytes,
    real_data_dir,
    require,
    sha256_bytes,
)
from real_sources import MEL_UNITS, SOURCES  # noqa: E402

NOTE = (
    "Sparse mirror of the open-licensed real-data inputs of builder/system_response/real/"
    "build_real.py, laid out like GB_REAL_DATA_DIR (.context/real_data). 'copy' files are "
    "byte-identical to the originals; 'slice' files keep only the rows the builder uses (rule "
    "given). Inputs marked mirror 'none' in real_sources.py (NESO .docx documentation, the derived "
    "communications timeline whose post text is not openly licensed) are not copied; with this "
    "mirror the builder skips only the quote checks that need them. No report PDF and no NESO "
    "website document is copied. Written by builder/system_response/real/sync_raw.py."
)


def _slice(key: str, data: bytes) -> bytes:
    if key == "elexon_ref_bmunits":
        records = json.loads(gzip.decompress(data).decode("utf-8"))
        keep = [r for r in records if r.get("elexonBmUnit") in MEL_UNITS]
        require(len(keep) == len(MEL_UNITS), "BM unit slice")
        body = json.dumps(keep, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        return gzip.compress(body, compresslevel=9, mtime=0)
    if key in ("neso_historic_demand", "neso_inertia"):
        dates = (
            ("08-AUG-2019", "09-AUG-2019", "10-AUG-2019")
            if key == "neso_historic_demand"
            else ("2019-08-08", "2019-08-09", "2019-08-10")
        )
        lines = data.decode("utf-8").splitlines(keepends=True)
        keep = [lines[0]] + [line for line in lines[1:] if line.split(",")[0] in dates]
        require(len(keep) == 145, f"{key} slice rows {len(keep) - 1}")
        return "".join(keep).encode("utf-8")
    raise BuildError(f"no slice rule coded for {key}")


def build_mirror() -> tuple[dict[str, bytes], dict[str, Any]]:
    root = real_data_dir()
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
        data = original if mode == "copy" else _slice(key, original)
        files[spec["rel"]] = data
        entry = {
            "rel": spec["rel"],
            "source_id": key,
            "mode": mode,
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
        if "slice_rule" in spec:
            entry["slice_rule"] = spec["slice_rule"]
        entries.append(entry)
    manifest = {
        "schema": "gb-2019-system-response/raw-mirror/1",
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
                same_body = rel.endswith(".gz") and gzip.decompress(
                    path.read_bytes()
                ) == (gzip.decompress(data))
                if not same_body:
                    problems.append(f"differs {rel}")
        if not RAW_MANIFEST_PATH.is_file():
            problems.append("missing RAW_MANIFEST.json")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
