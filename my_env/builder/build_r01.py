"""Build the R01 frequency extract for the agent bundle from the NESO archive.

Builder-only tool (excluded from the image). It reproduces the handoff extraction in
``verification/check_frequency.py`` exactly:

* reads ``f 2019 8.csv`` from ``builder_only/sources/NESO_frequency_august_2019.zip``;
* parses the ``dtm`` column with its explicit ``+0100`` offsets (never as naive UTC);
* keeps the half-open slice [2019-08-09T16:40:00+01:00, 2019-08-09T17:45:00+01:00);
* asserts 3900 rows at a strict 1-second interval (no gaps, no duplicates);
* writes ``timestamp,frequency_hz`` rows with ``csv.writer`` (CRLF line endings, values as
  ``float`` reprs, timestamps as ISO-8601 with ``+01:00``).

It then asserts the written file is byte-identical to the handoff's
``data/frequency_2019-08-09_1640-1745_BST.csv`` and that every landmark in
``verification/frequency_checks.json`` is reproduced from the written file.

Usage (from the environment root)::

    GB_HANDOFF_DIR=/path/to/GB_power_cut_handoff uv run --frozen python builder/build_r01.py
    uv run --frozen python builder/build_r01.py --check   # verify only, write nothing

The handoff directory defaults to ``<workspace>/.context/handoff/GB_power_cut_handoff``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

ENV_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ENV_ROOT.parent
DEFAULT_HANDOFF_DIR = WORKSPACE_ROOT / ".context" / "handoff" / "GB_power_cut_handoff"
BUNDLE_DIR = ENV_ROOT / "src" / "environment" / "incident" / "bundle"

CSV_NAME = "frequency_2019-08-09_1640-1745_BST.csv"
OUTPUT_CSV = BUNDLE_DIR / "R01" / CSV_NAME
ZIP_RELPATH = "builder_only/sources/NESO_frequency_august_2019.zip"
ZIP_MEMBER = "f 2019 8.csv"
HANDOFF_CSV_RELPATH = f"data/{CSV_NAME}"
CHECKS_RELPATH = "verification/frequency_checks.json"

SLICE_START = datetime.fromisoformat("2019-08-09T16:40:00+01:00")
SLICE_END = datetime.fromisoformat("2019-08-09T17:45:00+01:00")  # exclusive
EXPECTED_ROWS = 3900
EXPECTED_OFFSET = timedelta(hours=1)
ONE_SECOND = timedelta(seconds=1)

Row = tuple[datetime, float]


def handoff_dir() -> Path:
    return Path(os.environ.get("GB_HANDOFF_DIR", str(DEFAULT_HANDOFF_DIR))).resolve()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_slice(zip_path: Path) -> list[Row]:
    """Read the incident slice exactly as the handoff's check_frequency.py does."""
    rows: list[Row] = []
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(ZIP_MEMBER) as raw:
            for record in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8")):
                if not record["dtm"].startswith("2019-08-09"):
                    continue
                stamp = datetime.strptime(record["dtm"], "%Y-%m-%d %H:%M:%S %z")
                if SLICE_START <= stamp < SLICE_END:
                    rows.append((stamp, float(record["f"])))
    return rows


def check_structure(rows: list[Row]) -> None:
    if len(rows) != EXPECTED_ROWS:
        raise AssertionError(f"expected {EXPECTED_ROWS} rows, got {len(rows)}")
    if rows[0][0] != SLICE_START:
        raise AssertionError(f"first timestamp {rows[0][0].isoformat()} != slice start")
    if rows[-1][0] != SLICE_END - ONE_SECOND:
        raise AssertionError(
            f"last timestamp {rows[-1][0].isoformat()} != slice end - 1 s"
        )
    for stamp, _ in rows:
        if stamp.utcoffset() != EXPECTED_OFFSET:
            raise AssertionError(f"unexpected UTC offset at {stamp.isoformat()}")
    stamps = [stamp for stamp, _ in rows]
    if len(set(stamps)) != len(stamps):
        raise AssertionError("duplicate timestamps in slice")
    for previous, current in zip(stamps, stamps[1:]):
        if current - previous != ONE_SECOND:
            raise AssertionError(f"gap or disorder between {previous} and {current}")


def render_csv(rows: list[Row]) -> bytes:
    """Serialise rows exactly like the handoff script (csv.writer, CRLF, float repr)."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["timestamp", "frequency_hz"])
    writer.writerows((stamp.isoformat(), value) for stamp, value in rows)
    return buffer.getvalue().encode("utf-8")


def parse_bundle_csv(data: bytes) -> list[Row]:
    reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""))
    header = next(reader)
    if header != ["timestamp", "frequency_hz"]:
        raise AssertionError(f"unexpected header {header!r}")
    return [(datetime.fromisoformat(stamp), float(value)) for stamp, value in reader]


def landmarks(rows: list[Row]) -> dict[str, object]:
    """Recompute the handoff landmarks (same windows and conventions as check_frequency.py)."""

    def window(start: str, end: str) -> list[Row]:
        return [(t, v) for t, v in rows if start <= t.strftime("%H:%M:%S") < end]

    first = min(window("16:52:45", "16:53:10"), key=lambda item: item[1])
    second = min(window("16:53:20", "16:54:30"), key=lambda item: item[1])
    recovered = next((t, v) for t, v in rows if t > second[0] and v >= 50)
    below = [(t, v) for t, v in window("16:52:30", "16:58:00") if v < 49]
    return {
        "rows": len(rows),
        "first_nadir": [first[0].isoformat(), first[1]],
        "second_nadir": [second[0].isoformat(), second[1]],
        "return_ge_50": [recovered[0].isoformat(), recovered[1]],
        "below_49_seconds_zero_order_hold": len(below),
        "below_49_first_sample": below[0][0].isoformat(),
        "below_49_last_sample": below[-1][0].isoformat(),
    }


def compare_landmarks(
    computed: dict[str, object], checks: dict[str, object]
) -> list[str]:
    problems = []
    for key, value in computed.items():
        if checks.get(key) != value:
            problems.append(f"{key}: computed {value!r} != handoff {checks.get(key)!r}")
    return problems


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temp = Path(handle.name)
    temp.chmod(
        0o644
    )  # NamedTemporaryFile creates 0600; bundle files are world-readable
    temp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the existing bundle CSV against the archive without writing",
    )
    args = parser.parse_args(argv)

    root = handoff_dir()
    zip_path = root / ZIP_RELPATH
    handoff_csv = root / HANDOFF_CSV_RELPATH
    checks_path = root / CHECKS_RELPATH
    for required in (zip_path, handoff_csv, checks_path):
        if not required.is_file():
            print(f"FAIL: missing handoff file {required}", file=sys.stderr)
            return 2

    checks = json.loads(checks_path.read_text(encoding="utf-8"))
    zip_sha = sha256_file(zip_path)
    if zip_sha != checks["source_sha256"]:
        print(
            f"FAIL: archive sha256 {zip_sha} != frequency_checks.json", file=sys.stderr
        )
        return 1

    rows = read_slice(zip_path)
    check_structure(rows)
    data = render_csv(rows)

    if data != handoff_csv.read_bytes():
        print(
            "FAIL: rebuilt CSV is not byte-identical to the handoff CSV",
            file=sys.stderr,
        )
        return 1

    if args.check:
        if not OUTPUT_CSV.is_file() or OUTPUT_CSV.read_bytes() != data:
            print(
                f"FAIL: {OUTPUT_CSV} missing or differs from the rebuilt CSV",
                file=sys.stderr,
            )
            return 1
    else:
        write_atomic(OUTPUT_CSV, data)

    written = OUTPUT_CSV.read_bytes()
    reparsed = parse_bundle_csv(written)
    check_structure(reparsed)
    problems = compare_landmarks(landmarks(reparsed), checks)
    if problems:
        for problem in problems:
            print(f"FAIL: landmark mismatch: {problem}", file=sys.stderr)
        return 1

    report = {
        "archive": str(zip_path),
        "archive_sha256": zip_sha,
        "member": ZIP_MEMBER,
        "slice": "[2019-08-09T16:40:00+01:00, 2019-08-09T17:45:00+01:00)",
        "rows": len(reparsed),
        "first": reparsed[0][0].isoformat(),
        "last": reparsed[-1][0].isoformat(),
        "output": str(OUTPUT_CSV.relative_to(ENV_ROOT)),
        "output_sha256": hashlib.sha256(written).hexdigest(),
        "byte_identical_to_handoff_csv": True,
        "landmarks_match_frequency_checks_json": True,
        "mode": "check" if args.check else "write",
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
