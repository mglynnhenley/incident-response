"""Asset-log and control-log row fragments derived from this track's documents.

Rows restate entries of bundle documents; they add no fact of their own. Each row names the
document line(s) it restates (``provenance.doc_lines``, resolved from a unique line prefix) and
carries the source references of the provenance segment that covers those lines.

Time fields (decision 23): ``recorded_time`` is the time exactly as the document records it
and ``clock_basis`` says how to read it; ``index_time_utc`` is an absolute instant used only for
filtering, and the true instant lies within +/- ``index_uncertainty_s`` of it:

- printed to the minute -> the printed minute, +/- 60 s; to the second -> +/- 1 s; to the
  millisecond -> +/- 0.001 s; "Approx" times -> +/- 300 s;
- a printed range -> its start, +/- the range length plus the printed precision;
- Little Barford SOE offsets -> T (16:52:34 BST) + offset, +/- 0.5 s for the datum plus the
  offset's printed precision;
- unlabelled source clocks are read as BST (UTC+01:00), as each document's clock line states.

Rows of the asset logs: ESW-400 (R03), HORNSEA-ONE (S01), LITTLE-BARFORD (S03).
Rows of the control logs: ESO-ENCC (S07, R08). Party identifiers used in ``from``/``to``:
ESO-ENCC, NGET-TNCC, DNO-<area> (areas as printed in ESO Table 7 / Appendix J), DNOS (all or
unnamed DNOs), SCOT-SP, SCOT-SHETL.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

BST = timedelta(hours=1)
DAY = "2019-08-09"

# ESO Table 7 / Appendix M answer-33 column labels -> party IDs (as printed, no mapping to
# licence names is asserted).
AREA_IDS = {
    "SSE": "DNO-SSE",
    "SPED": "DNO-SPED",
    "ENW": "DNO-ENW",
    "NPG North East": "DNO-NPG-NE",
    "NPG Yorkshire": "DNO-NPG-YORKS",
    "UKPN SPN": "DNO-UKPN-SPN",
    "UKPN EPN": "DNO-UKPN-EPN",
    "UKPN LPN": "DNO-UKPN-LPN",
    "WPD South West": "DNO-WPD-SW",
    "WPD SW": "DNO-WPD-SW",
    "WPD South Wales": "DNO-WPD-SWALES",
    "WPD West Midland": "DNO-WPD-WMID",
    "WPD East Midland": "DNO-WPD-EMID",
}
UKPN_ALL = ["UKPN SPN", "UKPN EPN", "UKPN LPN"]
WPD_ALL = ["WPD South West", "WPD South Wales", "WPD West Midland", "WPD East Midland"]
WPD_SW_SWALES = ["WPD South West", "WPD South Wales"]


def utc_from_bst(hms: str) -> datetime:
    """'16:52:33.490' / '16:52:26' / '16:52' (BST) -> aware UTC datetime."""
    parts = hms.split(":")
    hour, minute = int(parts[0]), int(parts[1])
    seconds = float(parts[2]) if len(parts) > 2 else 0.0
    whole = int(seconds)
    micro = round((seconds - whole) * 1_000_000)
    local = datetime(2019, 8, 9, hour, minute, whole, micro, tzinfo=UTC)
    return local - BST


def utc_from_z(hms: str) -> datetime:
    parts = hms.split(":")
    seconds = float(parts[2]) if len(parts) > 2 else 0.0
    whole = int(seconds)
    micro = round((seconds - whole) * 1_000_000)
    return datetime(2019, 8, 9, int(parts[0]), int(parts[1]), whole, micro, tzinfo=UTC)


def iso_z(when: datetime) -> str:
    return (
        when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.")
        + f"{when.microsecond // 1000:03d}Z"
    )


def precision(hms: str) -> float:
    parts = hms.split(":")
    if len(parts) == 2:
        return 60.0
    if "." in parts[2]:
        return 10.0 ** -len(parts[2].split(".")[1])
    return 1.0


# --------------------------------------------------------------------------- asset rows

# Signal names are public (the catalogue lists each log's signals), so they name the kind of
# record only; what happened is stated in the row text, which restates the document line.
EVENT_SIGNAL = "event"
SOE_SIGNAL = "sequence-of-events entry"

S01_CLOCK = (
    "UTC (explicit Z) as rendered in reconstructed log S01; the operator's published timeline "
    "uses local time"
)
R03_CLOCK = "BST (UTC+01:00) as written in R03; the source does not label the clock and R03 reads it as BST"
S03_CLOCK = (
    "offset from the station SOE datum T; the operator gives T = 16:52:34 +/- 0.5 s without a clock "
    "basis (S03 reads it as BST) and states T is not yet aligned with the ESO datum"
)


def _asset(
    event_id: str,
    doc: str,
    anchor: str,
    asset_id: str,
    recorded_time: str,
    clock_basis: str,
    index: datetime,
    uncertainty: float,
    signal: str,
    value: float | None,
    unit: str | None,
    value_status: str,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "evidence_id": doc,
        "anchor": anchor,
        "asset_id": asset_id,
        "recorded_time": recorded_time,
        "clock_basis": clock_basis,
        "index_time_utc": iso_z(index),
        "index_uncertainty_s": round(uncertainty, 6),
        "signal": signal,
        "value": value,
        "unit": unit,
        "value_status": value_status,
    }


def s01_rows() -> list[dict[str, Any]]:
    a = "HORNSEA-ONE"
    rows = [
        _asset(
            "S01-EV01",
            "S01",
            "~15:42Z [estimated]",
            a,
            "~15:42Z",
            S01_CLOCK,
            utc_from_z("15:42"),
            300.0,
            "reactive power",
            None,
            None,
            "estimated",
        ),
        _asset(
            "S01-EV02",
            "S01",
            "15:52:33.000Z-.490Z [reported]",
            a,
            "15:52:33.000Z-.490Z",
            S01_CLOCK,
            utc_from_z("15:52:33.000"),
            0.491,
            "NETS 400 kV substation voltage",
            400,
            "kV",
            "reported",
        ),
        _asset(
            "S01-EV03",
            "S01",
            "15:52:33.490Z [estimated]",
            a,
            "15:52:33.490Z",
            S01_CLOCK,
            utc_from_z("15:52:33.490"),
            60.0,
            "TIP voltage",
            None,
            None,
            "estimated",
        ),
        _asset(
            "S01-EV04a",
            "S01",
            "15:52:33.490Z-.700Z [reported]  Reactive",
            a,
            "15:52:33.490Z-.700Z",
            S01_CLOCK,
            utc_from_z("15:52:33.490"),
            0.211,
            "reactive power",
            None,
            None,
            "reported",
        ),
        _asset(
            "S01-EV04b",
            "S01",
            "15:52:33.490Z-.700Z [reported]  Reactive",
            a,
            "15:52:33.490Z-.700Z",
            S01_CLOCK,
            utc_from_z("15:52:33.490"),
            0.211,
            "NETS and Hornsea One system voltage",
            394,
            "kV",
            "reported",
        ),
        _asset(
            "S01-EV05",
            "S01",
            "15:52:33.490Z-.700Z [reported]  Active",
            a,
            "15:52:33.490Z-.700Z",
            S01_CLOCK,
            utc_from_z("15:52:33.490"),
            0.211,
            "active power",
            None,
            None,
            "reported",
        ),
        _asset(
            "S01-EV06a",
            "S01",
            "15:52:33.531Z [reported]",
            a,
            "15:52:33.531Z",
            S01_CLOCK,
            utc_from_z("15:52:33.531"),
            0.001,
            "active power",
            799,
            "MW",
            "reported",
        ),
        _asset(
            "S01-EV06b",
            "S01",
            "15:52:33.531Z [reported]",
            a,
            "15:52:33.531Z",
            S01_CLOCK,
            utc_from_z("15:52:33.531"),
            0.001,
            "reactive power (absorbing)",
            0.4,
            "MVAr",
            "reported",
        ),
        _asset(
            "S01-EV07",
            "S01",
            "15:52:33.700Z [reported]",
            a,
            "15:52:33.700Z",
            S01_CLOCK,
            utc_from_z("15:52:33.700"),
            0.001,
            "reactive power (absorbing)",
            560,
            "MVAr",
            "reported",
        ),
        _asset(
            "S01-EV08",
            "S01",
            "15:52:33.700Z-.835Z [estimated]",
            a,
            "15:52:33.700Z-.835Z",
            S01_CLOCK,
            utc_from_z("15:52:33.700"),
            0.136,
            "34 kV collection system voltage",
            20,
            "kV",
            "estimated",
        ),
        _asset(
            "S01-EV09",
            "S01",
            "15:52:33.728Z [reported]",
            a,
            "15:52:33.728Z",
            S01_CLOCK,
            utc_from_z("15:52:33.728"),
            0.001,
            EVENT_SIGNAL,
            None,
            None,
            "reported",
        ),
        _asset(
            "S01-EV10a",
            "S01",
            "15:52:33.835Z [reported]",
            a,
            "15:52:33.835Z",
            S01_CLOCK,
            utc_from_z("15:52:33.835"),
            0.001,
            EVENT_SIGNAL,
            107,
            "ms after de-load start",
            "reported",
        ),
        _asset(
            "S01-EV10b",
            "S01",
            "15:52:33.835Z [reported]",
            a,
            "15:52:33.835Z",
            S01_CLOCK,
            utc_from_z("15:52:33.835"),
            0.001,
            "active power (site)",
            62,
            "MW",
            "reported",
        ),
        _asset(
            "S01-EV10c",
            "S01",
            "15:52:33.835Z [reported]",
            a,
            "15:52:33.835Z",
            S01_CLOCK,
            utc_from_z("15:52:33.835"),
            0.001,
            "reactive power (injecting)",
            21,
            "MVAr",
            "reported",
        ),
    ]
    return rows


SOE = [
    ("E1", "T = 0 ms", 0.0, 0.001, "110 V AC UPS -B- general fault alarm"),
    ("E2", "+3 ms", 0.003, 0.001, "110 V AC UPS -A- general fault alarm"),
    ("E3", "+253 ms", 0.253, 0.001, "Initiation of ST control system shutdown"),
    ("E4", "+1.16 s", 1.16, 0.01, "ST generator breaker open command"),
    ("E5", "+1.185 s", 1.185, 0.001, "ST generator breaker open feedback"),
    ("E6", "+56.583 s", 56.583, 0.001, "GT1A auto shutdown command"),
    ("E7", "+57.620 s", 57.62, 0.001, "GT1A breaker open feedback"),
    ("E8", "+83.897 s", 83.897, 0.001, "GT1B manual shutdown command"),
    ("E9", "+84.613 s", 84.613, 0.001, "GT1B breaker open feedback"),
]


def s03_rows() -> list[dict[str, Any]]:
    datum = utc_from_bst("16:52:34")
    rows = []
    for label, printed, offset, prec, _event in SOE:
        recorded = printed if printed.startswith("T") else f"T {printed}"
        rows.append(
            _asset(
                f"S03-SOE-{label}",
                "S03",
                f"{label}   ",
                "LITTLE-BARFORD",
                recorded,
                S03_CLOCK,
                datum + timedelta(seconds=offset),
                0.5 + prec,
                SOE_SIGNAL,
                offset,
                "s after T",
                "reported",
            )
        )
    return rows


def r03_rows() -> list[dict[str, Any]]:
    a = "ESW-400"
    fault = utc_from_bst("16:52:33.490")
    return [
        _asset(
            "R03-B3",
            "R03",
            "B3  ",
            a,
            "2019-08-09T16:52:33+01:00",
            R03_CLOCK,
            utc_from_bst("16:52:33"),
            1.0,
            EVENT_SIGNAL,
            None,
            None,
            "reported",
        ),
        _asset(
            "R03-C1",
            "R03",
            "C1  ",
            a,
            "2019-08-09T16:52:33.490+01:00",
            R03_CLOCK,
            fault,
            0.001,
            EVENT_SIGNAL,
            None,
            None,
            "reported",
        ),
        _asset(
            "R03-C3a",
            "R03",
            "C3  ",
            a,
            "during the fault (from 2019-08-09T16:52:33.490+01:00)",
            R03_CLOCK,
            fault,
            0.074,
            "current (Wymondley Main end, RMS)",
            21,
            "kA",
            "reported",
        ),
        _asset(
            "R03-C3b",
            "R03",
            "C3  ",
            a,
            "during the fault (from 2019-08-09T16:52:33.490+01:00)",
            R03_CLOCK,
            fault,
            0.074,
            "current (Eaton Socon end, RMS)",
            7,
            "kA",
            "reported",
        ),
        _asset(
            "R03-C4",
            "R03",
            "C4  ",
            a,
            "during the fault (from 2019-08-09T16:52:33.490+01:00)",
            R03_CLOCK,
            fault,
            0.1,
            "voltage change",
            50,
            "%",
            "reported",
        ),
        _asset(
            "R03-C5",
            "R03",
            "C5  ",
            a,
            "2019-08-09T16:52:33.560+01:00",
            R03_CLOCK,
            utc_from_bst("16:52:33.560"),
            0.001,
            "protection timing (Wymondley Main end)",
            70,
            "ms after fault inception",
            "reported",
        ),
        _asset(
            "R03-C6",
            "R03",
            "C6  ",
            a,
            "2019-08-09T16:52:33.564+01:00",
            R03_CLOCK,
            utc_from_bst("16:52:33.564"),
            0.001,
            "protection timing (Eaton Socon end)",
            74,
            "ms after fault inception",
            "reported",
        ),
        _asset(
            "R03-C8",
            "R03",
            "C8  ",
            a,
            "2019-08-09T16:52:53+01:00",
            R03_CLOCK,
            utc_from_bst("16:52:53"),
            1.0,
            EVENT_SIGNAL,
            None,
            None,
            "reported",
        ),
    ]


# --------------------------------------------------------------------------- control rows

S07_CLOCK = "hh:mm[:ss] as printed by ESO; no clock labelled, read as BST (UTC+01:00)"
R08_CLOCK = "hh:mm as printed on ESO's Appendix J call diagram; no clock labelled, read as BST (UTC+01:00)"


def _control(
    entry_id: str,
    doc: str,
    anchor: str,
    recorded_time: str,
    clock_basis: str,
    index: datetime,
    uncertainty: float,
    sender: str | None,
    receiver: str | None,
    channel: str,
    text: str | None = None,
) -> dict[str, Any]:
    return {
        "entry_id": entry_id,
        "evidence_id": doc,
        "anchor": anchor,
        "room_id": "ESO-ENCC",
        "recorded_time": recorded_time,
        "clock_basis": clock_basis,
        "index_time_utc": iso_z(index),
        "index_uncertainty_s": round(uncertainty, 6),
        "from": sender,
        "to": receiver,
        "channel": channel,
        "text": text,
        "value_status": "reported",
    }


S07_TIMELINE = [
    ("E01", "16:52:26", None, "ESO-ENCC", None, "timeline entry"),
    ("E02", "16:52:34", None, "ESO-ENCC", None, "timeline entry"),
    ("E03", "16:52:44", None, "ESO-ENCC", None, "timeline entry"),
    ("E04", "16:52:58", None, "ESO-ENCC", None, "timeline entry"),
    ("E05", "16:52", None, "ESO-ENCC", None, "timeline entry"),
    ("E06", "16:53:04", None, "ESO-ENCC", None, "timeline entry"),
    ("E07", "Since 16:53", "16:53", "ESO-ENCC", None, "timeline entry"),
    ("E08", "16:53:18", None, "ESO-ENCC", None, "timeline entry"),
    ("E09", "16:53:31", None, "ESO-ENCC", None, "timeline entry"),
    ("E10", "16:54:20", None, "ESO-ENCC", None, "timeline entry"),
    ("E11", "16:57:15", None, "ESO-ENCC", None, "timeline entry"),
    ("E12", "16:58 – 17:16", "16:58-17:16", "ESO-ENCC", "DNOS", "instruction (range)"),
    ("E13", "17:37", None, "DNOS", "ESO-ENCC", "confirmation"),
    ("K1", "16:56", None, "DNOS", "ESO-ENCC", "report"),
    ("K2", "16:58 to 17:16", "16:58-17:16", "ESO-ENCC", "DNOS", "instruction (range)"),
    ("K3", "17:23", None, "DNOS", "ESO-ENCC", "request"),
    ("K4", "17:32", None, "ESO-ENCC", "NGET-TNCC", "report"),
    ("K5", "17:34", None, "DNOS", "ESO-ENCC", "report"),
    ("K6", "18:34 and beyond", "18:34", "DNOS", "ESO-ENCC", "report"),
    ("M1", "16:56", None, "DNOS", "ESO-ENCC", "report"),
    ("M2", "17:00", None, "ESO-ENCC", "DNOS", "instruction"),
    ("M3", "17:19", None, "ESO-ENCC", "DNO-WPD-EMID", "instruction"),
    ("M4", "17:22", None, "ESO-ENCC", "NGET-TNCC", "report"),
    ("M5", "17:36", None, "DNOS", "ESO-ENCC", "report"),
    ("M6", "18:34", None, "DNOS", "ESO-ENCC", "report"),
]


def _index_for(stamp: str) -> tuple[datetime, float]:
    if "-" in stamp:
        start, end = stamp.split("-")
        begin = utc_from_bst(start)
        return begin, (utc_from_bst(end) - begin).total_seconds() + precision(end)
    return utc_from_bst(stamp), precision(stamp)


def s07_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, printed, index_stamp, sender, receiver, channel in S07_TIMELINE:
        index, unc = _index_for(index_stamp or printed)
        pad = " " * (5 - len(label))
        rows.append(
            _control(
                f"S07-{label}",
                "S07",
                f"{label}{pad}",
                printed,
                S07_CLOCK,
                index,
                unc,
                sender,
                receiver,
                channel,
            )
        )
    rows.extend(_table_rows())
    return rows


# Table 7 (final report) and answer-33 table (earlier account): one row per printed cell.
T7 = [
    # label, area, informed, instructed, complete; None = shared cell printed at another row
    ("T01", "SSE", "17:01", "17:06", "17:07"),
    ("T02", "SPED", "17:01", "17:13", "17:17"),
    ("T03", "ENW", "17:01", "17:10", "17:17"),
    ("T04", "NPG North East", "17:01", "17:08", "17:18"),
    ("T05", "NPG Yorkshire", "17:01", "17:10", "17:12"),
    ("T06", "UKPN SPN", "17:04", "17:13", ("17:37", UKPN_ALL)),
    ("T07", "UKPN EPN", "17:04", "17:14", None),
    ("T08", "UKPN LPN", "16:58", "16:58", None),
    (
        "T09",
        "WPD South West",
        ("16:56", WPD_SW_SWALES),
        ("17:08", WPD_SW_SWALES),
        ("17:30", WPD_ALL),
    ),
    ("T10", "WPD South Wales", None, None, None),
    ("T11", "WPD West Midland", "17:02", "17:05", None),
    ("T12", "WPD East Midland", "16:57", "17:16", None),
]
Q33 = [
    # label, area, informed of LFDD, instructed, complete, ESO informed complete
    ("Q01", "SSE", "17:00", "17:06", "17:07", "18:30"),
    ("Q02", "SPED", "17:01", "17:13", "17:17", "17:36"),
    ("Q03", "ENW", "17:01", "17:11", "17:17", "18:30"),
    ("Q04", "NPG North East", "17:01", "17:08", "17:18", "18:18"),
    ("Q05", "NPG Yorkshire", "17:01", "17:11", "17:12", "18:22"),
    ("Q06", "UKPN SPN", "17:04", "17:12", ("Approx. 17:40", UKPN_ALL), "18:34"),
    ("Q07", "UKPN EPN", "17:04", "17:14", None, "18:33"),
    ("Q08", "UKPN LPN", "Approx 17:00", "Approx 17:00", None, "18:34"),
    (
        "Q09",
        "WPD SW",
        ("16:56", ["WPD SW", "WPD South Wales"]),
        ("17:07", ["WPD SW", "WPD South Wales"]),
        (
            "17:30",
            ["WPD SW", "WPD South Wales", "WPD West Midland", "WPD East Midland"],
        ),
        (
            "18:30",
            ["WPD SW", "WPD South Wales", "WPD West Midland", "WPD East Midland"],
        ),
    ),
    ("Q10", "WPD South Wales", None, None, None, None),
    ("Q11", "WPD West Midland", "blank", "17:18", None, None),
    ("Q12", "WPD East Midland", "17:05", "17.19", None, None),
]

T7_COLUMNS = [
    ("informed", "ESO informed of demand loss", "to_eso", "report"),
    ("instructed", "ESO instructed restoration", "from_eso", "instruction"),
    ("complete", "restoration completed", "dno", "completion time"),
]
Q33_COLUMNS = [
    ("informed", "ESO informed of LFDD", "to_eso", "report"),
    ("instructed", "ESO instructed restoration", "from_eso", "instruction"),
    ("complete", "restoration complete", "dno", "completion time"),
    ("informed-complete", "ESO informed restoration complete", "to_eso", "report"),
]


def _cell_time(printed: str) -> tuple[str, float]:
    if printed.lower().startswith("approx"):
        return printed.split()[-1], 300.0
    if printed == "17.19":
        return "17:19", 60.0
    return printed, precision(printed)


def _table_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table, columns, source_label in (
        (T7, T7_COLUMNS, "technical report Table 7"),
        (Q33, Q33_COLUMNS, "answer 33 table (data available on 28 August 2019)"),
    ):
        for entry in table:
            label, area = entry[0], entry[1]
            for (suffix, meaning, direction, channel), cell in zip(columns, entry[2:]):
                if cell is None or cell == "blank":
                    continue
                printed, areas = (cell, [area]) if isinstance(cell, str) else cell
                stamp, unc = _cell_time(printed)
                parties = "; ".join(AREA_IDS[x] for x in areas)
                shared = (
                    f" (one cell printed across {', '.join(areas)})"
                    if len(areas) > 1
                    else ""
                )
                text = f"ESO {source_label}, {area}: {meaning}: {printed} [reported]{shared}"
                if direction == "to_eso":
                    sender, receiver = parties, "ESO-ENCC"
                elif direction == "from_eso":
                    sender, receiver = "ESO-ENCC", parties
                else:
                    sender, receiver = parties, None
                rows.append(
                    _control(
                        f"S07-{label}-{suffix}",
                        "S07",
                        f"{label}  ",
                        printed,
                        S07_CLOCK,
                        utc_from_bst(stamp),
                        unc,
                        sender,
                        receiver,
                        channel,
                        text,
                    )
                )
    return rows


def r08_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        index = utc_from_bst(record["time"])
        if record["kind"] == "summary":
            rows.append(
                _control(
                    f"R08-{record['label']}",
                    "R08",
                    f"{record['label']}  ",
                    record["time"],
                    R08_CLOCK,
                    index,
                    60.0,
                    None,
                    None,
                    "summary note",
                )
            )
        else:
            rows.append(
                _control(
                    f"R08-{record['label']}",
                    "R08",
                    f"{record['label']}  ",
                    record["time"],
                    R08_CLOCK,
                    index,
                    60.0,
                    "; ".join(record["from"]),
                    "; ".join(record["to"]),
                    "operational call (arrow as drawn)",
                )
            )
    return rows
