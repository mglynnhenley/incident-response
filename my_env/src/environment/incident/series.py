"""The measured frequency series served by ``query_frequency`` (R01).

Parsed strictly from the hash-verified CSV: every timestamp carries an explicit
offset, timestamps strictly increase (no duplicates, monotonic), every value is a
finite number, and the sample spacing is reported (gaps are counted, never filled).
Values are served exactly as written in the CSV: no smoothing, interpolation or
resampling.
"""

from __future__ import annotations

import bisect
import csv
import io
import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from environment.incident.catalogue import CatalogueError, Document
from environment.incident.locators import LocatorError, parse_iso_instant

__all__ = ["FREQUENCY_DOC_ID", "FrequencySeries", "parse_frequency_series"]

FREQUENCY_DOC_ID = "R01"


@dataclass(frozen=True)
class FrequencySeries:
    doc_id: str
    artifact_name: str
    time_column: str
    value_column: str
    unit: str
    interval_s: float
    times: tuple[datetime, ...]
    stamps: tuple[str, ...]
    values: tuple[str, ...]
    gaps: int

    @property
    def first(self) -> datetime:
        return self.times[0]

    @property
    def last(self) -> datetime:
        return self.times[-1]

    @property
    def coverage_end(self) -> datetime:
        """End of the period the samples cover (exclusive): last + one interval."""
        return self.last + timedelta(seconds=self.interval_s)

    def __len__(self) -> int:
        return len(self.times)

    def window(self, start: datetime, end: datetime) -> tuple[int, int]:
        """Indices ``[lo, hi)`` of the samples with ``start <= t < end``."""
        return (
            bisect.bisect_left(self.times, start),
            bisect.bisect_left(self.times, end),
        )


def parse_frequency_series(doc: Document, data: bytes) -> FrequencySeries:
    series = doc.timeseries
    where = f"document {doc.doc_id} time series"
    if series is None:
        raise CatalogueError(f"{where}: missing")
    artifact = next(a for a in doc.artifacts if a.timeseries is series)
    reader = csv.reader(io.StringIO(data.decode("utf-8")))
    header = next(reader)
    t_index = header.index(series.time_column)
    v_index = header.index(series.value_column)
    times: list[datetime] = []
    stamps: list[str] = []
    values: list[str] = []
    gaps = 0
    step = timedelta(seconds=series.interval_s)
    for number, row in enumerate((r for r in reader if r), 1):
        try:
            stamp, value = row[t_index], row[v_index]
            when = parse_iso_instant(stamp)
            number_value = float(value)
        except (IndexError, LocatorError, ValueError) as exc:
            raise CatalogueError(f"{where}: row {number} unreadable: {exc}") from None
        if not math.isfinite(number_value):
            raise CatalogueError(f"{where}: row {number} value is not finite")
        if times:
            if when <= times[-1]:
                raise CatalogueError(
                    f"{where}: row {number} timestamp {stamp} does not increase "
                    "(duplicate or out of order)"
                )
            if when - times[-1] != step:
                if when - times[-1] < step:
                    raise CatalogueError(
                        f"{where}: row {number} is closer than the "
                        f"{series.interval_s:g} s interval to the previous sample"
                    )
                gaps += 1
        times.append(when)
        stamps.append(stamp)
        values.append(value)
    return FrequencySeries(
        doc_id=doc.doc_id,
        artifact_name=artifact.name,
        time_column=series.time_column,
        value_column=series.value_column,
        unit=series.unit,
        interval_s=series.interval_s,
        times=tuple(times),
        stamps=tuple(stamps),
        values=tuple(values),
        gaps=gaps,
    )
