"""Reference analysis of the R01 system-frequency extract (pure Python, grader side).

This module recomputes, from the frozen bundle CSV, the frequency landmarks the answer
key scores (dimension D3). It uses only the standard library so the grader never
depends on the student's numerical stack, and it reproduces the handoff's
``verification/frequency_checks.json`` exactly (see :func:`handoff_checks`).

Conventions (from the handoff's numeric rules):

* timestamps must carry an explicit UTC offset; they are parsed as given, never as
  naive UTC;
* the series must be strictly increasing at a 1-second interval with no duplicate or
  missing seconds (:func:`check_series` reports any problem rather than repairing it);
* analysis windows are half-open, ``[start, end)``, expressed in BST (UTC+01:00) on
  9 August 2019, like the handoff's own extraction script;
* "first post-fault local minimum" is the lowest sample in 16:52:45-16:53:10 and the
  "event minimum" the lowest sample in 16:53:20-16:54:30 (earliest sample on ties); the
  recovery landmark is the first sample at or above 50 Hz after the event minimum;
* time below 49 Hz is STRICTLY below (a sample of exactly 49.0 Hz is not below) under
  a zero-order hold: each sample holds its value until the next sample, but never for
  longer than the nominal interval, so a gap larger than one second is not bridged.
  :func:`duration_below` returns the covered duration below the threshold and the
  missing (uncovered) duration of the window separately. One-second samples say
  nothing about sub-second threshold crossings.

This module must not import ``karotte``.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "BST",
    "DurationResult",
    "FrequencyError",
    "Sample",
    "SeriesCheck",
    "bst",
    "check_series",
    "duration_below",
    "first_at_or_above",
    "handoff_checks",
    "is_local_minimum",
    "load_series",
    "parse_series",
    "reference_landmarks",
    "window_minimum",
]

BST = timezone(timedelta(hours=1))
EVENT_DATE = (2019, 8, 9)

# Analysis windows (BST, half-open) used by the handoff's extraction script and the key.
FIRST_MIN_WINDOW = ("16:52:45", "16:53:10")
EVENT_MIN_WINDOW = ("16:53:20", "16:54:30")
BELOW_49_WINDOW = ("16:52:30", "16:58:00")
SLICE = ("16:40:00", "17:45:00")
THRESHOLD_HZ = 49.0
RECOVERY_HZ = 50.0

HANDOFF_TIMEZONE_NOTE = (
    "Parsed explicit +0100 offsets; UTC is local time minus one hour. Report event "
    "alignment checked; no publisher clarification obtained."
)


class FrequencyError(ValueError):
    """The frequency CSV cannot be parsed or analysed as required."""


@dataclass(frozen=True)
class Sample:
    """One data row: 1-based ``row`` (header excluded), aware ``time``, ``value`` in Hz."""

    row: int
    time: datetime
    value: float

    def as_pair(self) -> list[Any]:
        return [self.time.isoformat(), self.value]


@dataclass
class SeriesCheck:
    rows: int
    first: datetime | None
    last: datetime | None
    interval_s: float
    strictly_increasing: bool
    duplicates: list[str] = field(default_factory=list)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    missing_seconds: int = 0
    offsets: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            self.rows > 0
            and self.strictly_increasing
            and not self.duplicates
            and not self.gaps
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "rows": self.rows,
            "first": self.first.isoformat() if self.first else None,
            "last": self.last.isoformat() if self.last else None,
            "interval_s": self.interval_s,
            "strictly_increasing": self.strictly_increasing,
            "duplicates": list(self.duplicates),
            "gaps": list(self.gaps),
            "missing_seconds": self.missing_seconds,
            "offsets": list(self.offsets),
        }


@dataclass
class DurationResult:
    """Zero-order-hold time strictly below ``threshold`` within ``[start, end)``."""

    threshold: float
    start: datetime
    end: datetime
    covered_below_s: float
    missing_s: float
    covered_s: float
    samples_below: int
    first_below: Sample | None
    last_below: Sample | None
    runs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "threshold_hz": self.threshold,
            "comparison": "strictly below",
            "window": [self.start.isoformat(), self.end.isoformat()],
            "covered_below_s": self.covered_below_s,
            "missing_s": self.missing_s,
            "covered_s": self.covered_s,
            "samples_below": self.samples_below,
            "first_below": self.first_below.as_pair() if self.first_below else None,
            "last_below": self.last_below.as_pair() if self.last_below else None,
            "runs": list(self.runs),
        }


def bst(hms: str, *, date: tuple[int, int, int] = EVENT_DATE) -> datetime:
    """``"16:52:59"`` (optionally with a fraction) on 9 August 2019 at UTC+01:00."""
    parts = hms.split(":")
    if len(parts) != 3:
        raise FrequencyError(f"expected HH:MM:SS, got {hms!r}")
    seconds = float(parts[2])
    whole = int(math.floor(seconds))
    micro = int(round((seconds - whole) * 1_000_000))
    year, month, day = date
    return datetime(
        year, month, day, int(parts[0]), int(parts[1]), whole, micro, tzinfo=BST
    )


def _offset_text(when: datetime) -> str:
    offset = when.utcoffset() or timedelta(0)
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    return f"{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"


def _parse_time(text: str, row: int) -> datetime:
    value = text.strip()
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise FrequencyError(f"row {row}: unreadable timestamp {text!r}") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FrequencyError(
            f"row {row}: timestamp {text!r} has no explicit UTC offset; naive times are "
            "not accepted"
        )
    return parsed


def _parse_value(text: str, row: int) -> float:
    try:
        value = float(text)
    except ValueError:
        raise FrequencyError(f"row {row}: unreadable frequency {text!r}") from None
    if not math.isfinite(value):
        raise FrequencyError(f"row {row}: frequency {text!r} is not finite")
    return value


def parse_series(
    text: str, *, time_column: str = "timestamp", value_column: str = "frequency_hz"
) -> list[Sample]:
    """Parse CSV text (LF or CRLF) into samples, keeping the explicit offsets."""
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration:
        raise FrequencyError("CSV is empty") from None
    if time_column not in header or value_column not in header:
        raise FrequencyError(
            f"CSV header {header} lacks {time_column!r} or {value_column!r}"
        )
    t_index, v_index = header.index(time_column), header.index(value_column)
    samples: list[Sample] = []
    for row_number, row in enumerate((r for r in reader if r), 1):
        try:
            t_text, v_text = row[t_index], row[v_index]
        except IndexError:
            raise FrequencyError(f"row {row_number}: too few columns") from None
        samples.append(
            Sample(
                row=row_number,
                time=_parse_time(t_text, row_number),
                value=_parse_value(v_text, row_number),
            )
        )
    if not samples:
        raise FrequencyError("CSV has no data rows")
    return samples


def load_series(path: Path | str) -> list[Sample]:
    """Read and parse a frequency CSV file."""
    with open(path, encoding="utf-8", newline="") as handle:
        return parse_series(handle.read())


def check_series(samples: Sequence[Sample], *, interval_s: float = 1.0) -> SeriesCheck:
    """Monotonicity, duplicates and gaps of a series with a nominal ``interval_s``."""
    check = SeriesCheck(
        rows=len(samples),
        first=samples[0].time if samples else None,
        last=samples[-1].time if samples else None,
        interval_s=interval_s,
        strictly_increasing=True,
    )
    check.offsets = sorted({_offset_text(s.time) for s in samples})
    nominal = timedelta(seconds=interval_s)
    for previous, current in zip(samples, samples[1:]):
        step = current.time - previous.time
        if step == timedelta(0):
            check.duplicates.append(current.time.isoformat())
            check.strictly_increasing = False
        elif step < timedelta(0):
            check.strictly_increasing = False
        elif step != nominal:
            gap_s = step.total_seconds()
            check.gaps.append(
                {
                    "after": previous.time.isoformat(),
                    "before": current.time.isoformat(),
                    "step_s": gap_s,
                }
            )
            if step > nominal:
                check.missing_seconds += int(round(gap_s / interval_s)) - 1
    return check


def _in_window(sample: Sample, start: datetime, end: datetime) -> bool:
    return start <= sample.time < end


def window_minimum(samples: Sequence[Sample], start: datetime, end: datetime) -> Sample:
    """Lowest sample in ``[start, end)``; the earliest one on ties."""
    best: Sample | None = None
    for sample in samples:
        if _in_window(sample, start, end) and (
            best is None or sample.value < best.value
        ):
            best = sample
    if best is None:
        raise FrequencyError(f"no samples in [{start.isoformat()}, {end.isoformat()})")
    return best


def is_local_minimum(samples: Sequence[Sample], sample: Sample) -> bool:
    """Whether ``sample`` is no higher than its immediate neighbours."""
    index = sample.row - 1
    if not (0 <= index < len(samples)) or samples[index] != sample:
        index = samples.index(sample)
    neighbours = [samples[i] for i in (index - 1, index + 1) if 0 <= i < len(samples)]
    return all(sample.value <= other.value for other in neighbours)


def first_at_or_above(
    samples: Sequence[Sample], after: datetime, threshold: float = RECOVERY_HZ
) -> Sample:
    """First sample strictly after ``after`` whose value is at or above ``threshold``."""
    for sample in samples:
        if sample.time > after and sample.value >= threshold:
            return sample
    raise FrequencyError(
        f"no sample at or above {threshold} Hz after {after.isoformat()}"
    )


def duration_below(
    samples: Sequence[Sample],
    threshold: float = THRESHOLD_HZ,
    *,
    start: datetime,
    end: datetime,
    interval_s: float = 1.0,
    max_gap_s: float = 1.0,
) -> DurationResult:
    """Zero-order-hold duration strictly below ``threshold`` within ``[start, end)``.

    Each sample holds its value from its own time until the next sample, but for at
    most ``interval_s`` when the step to the next sample exceeds ``max_gap_s`` (gaps
    are not bridged); the last sample holds for ``interval_s``. Holds are clipped to
    the window. Time in the window that no hold covers is reported as ``missing_s``.
    """
    if end <= start:
        raise FrequencyError("the duration window must have end > start")
    nominal = timedelta(seconds=interval_s)
    max_gap = timedelta(seconds=max_gap_s)
    covered = timedelta(0)
    below = timedelta(0)
    count = 0
    first: Sample | None = None
    last: Sample | None = None
    runs: list[dict[str, Any]] = []
    run_start: Sample | None = None
    run_last: Sample | None = None
    run_length = timedelta(0)

    def close_run() -> None:
        nonlocal run_start, run_last, run_length
        if run_start is not None and run_last is not None:
            runs.append(
                {
                    "first_sample": run_start.time.isoformat(),
                    "last_sample": run_last.time.isoformat(),
                    "duration_s": run_length.total_seconds(),
                }
            )
        run_start = run_last = None
        run_length = timedelta(0)

    for index, sample in enumerate(samples):
        nxt = samples[index + 1].time if index + 1 < len(samples) else None
        hold_end = nxt if nxt is not None and nxt - sample.time <= max_gap else None
        if hold_end is None:
            hold_end = sample.time + nominal
        lo = max(sample.time, start)
        hi = min(hold_end, end)
        held = hi - lo if hi > lo else timedelta(0)
        covered += held
        is_below = sample.value < threshold
        bridged = hold_end == nxt
        if is_below and held > timedelta(0):
            below += held
            count += 1
            first = first or sample
            last = sample
            if run_start is None:
                run_start = sample
            run_last = sample
            run_length += held
        elif run_start is not None:
            close_run()
        if run_start is not None and not bridged:
            close_run()
    close_run()
    window = end - start
    return DurationResult(
        threshold=threshold,
        start=start,
        end=end,
        covered_below_s=below.total_seconds(),
        missing_s=(window - covered).total_seconds(),
        covered_s=covered.total_seconds(),
        samples_below=count,
        first_below=first,
        last_below=last,
        runs=runs,
    )


def reference_landmarks(samples: Sequence[Sample]) -> dict[str, Any]:
    """The four D3 landmarks plus the series checks, as a JSON-ready dict."""
    check = check_series(samples)
    first_min = window_minimum(
        samples, bst(FIRST_MIN_WINDOW[0]), bst(FIRST_MIN_WINDOW[1])
    )
    event_min = window_minimum(
        samples, bst(EVENT_MIN_WINDOW[0]), bst(EVENT_MIN_WINDOW[1])
    )
    recovery = first_at_or_above(samples, event_min.time, RECOVERY_HZ)
    below = duration_below(
        samples,
        THRESHOLD_HZ,
        start=bst(BELOW_49_WINDOW[0]),
        end=bst(BELOW_49_WINDOW[1]),
    )
    return {
        "series": check.to_dict(),
        "first_local_minimum": {
            "window_bst": list(FIRST_MIN_WINDOW),
            "time": first_min.time.isoformat(),
            "value_hz": first_min.value,
            "row": first_min.row,
            "is_local_minimum": is_local_minimum(samples, first_min),
        },
        "event_minimum": {
            "window_bst": list(EVENT_MIN_WINDOW),
            "time": event_min.time.isoformat(),
            "value_hz": event_min.value,
            "row": event_min.row,
            "is_local_minimum": is_local_minimum(samples, event_min),
        },
        "first_at_or_above_50_after_minimum": {
            "time": recovery.time.isoformat(),
            "value_hz": recovery.value,
            "row": recovery.row,
        },
        "below_49": below.to_dict(),
    }


def handoff_checks(
    samples: Sequence[Sample], *, source_sha256: str | None = None
) -> dict[str, Any]:
    """The handoff's ``verification/frequency_checks.json`` recomputed from ``samples``.

    ``source_sha256`` is the hash of the NESO archive the slice came from (it cannot be
    derived from the slice itself); everything else is computed here.
    """
    check = check_series(samples)
    if not check.ok:
        raise FrequencyError(f"series fails its checks: {check.to_dict()}")
    landmarks = reference_landmarks(samples)
    below = landmarks["below_49"]
    if below["missing_s"]:
        raise FrequencyError("the below-49 Hz window has missing data")
    seconds = below["covered_below_s"]
    first_min = landmarks["first_local_minimum"]
    event_min = landmarks["event_minimum"]
    recovery = landmarks["first_at_or_above_50_after_minimum"]
    return {
        "source_sha256": source_sha256,
        "rows": check.rows,
        "interval": f"[{SLICE[0]},{SLICE[1]}) BST",
        "missing_seconds": check.missing_seconds,
        "first_nadir": [first_min["time"], first_min["value_hz"]],
        "second_nadir": [event_min["time"], event_min["value_hz"]],
        "return_ge_50": [recovery["time"], recovery["value_hz"]],
        "below_49_seconds_zero_order_hold": int(seconds)
        if float(seconds).is_integer()
        else seconds,
        "below_49_first_sample": below["first_below"][0],
        "below_49_last_sample": below["last_below"][0],
        "timezone": HANDOFF_TIMEZONE_NOTE,
    }
