"""Reference analysis of R01, as a reference investigator would send it to run_python.

It reads the retrieved CSV from ``$EVIDENCE_DIR/R01/`` with pandas, checks the series
(explicit offsets, strictly increasing 1-second steps, no duplicates or gaps) and prints
the frequency landmarks and the time strictly below 49 Hz under a zero-order hold.
Windows are half-open ``[start, end)`` in BST (UTC+01:00), matching the grader's
reference analysis in ``environment.incident.frequency``.

Grader-side file: the scripted fake agent sends its text through ``run_python``; it is
never shown to the evaluated agent.
"""

import os

import pandas as pd

CSV = os.path.join(
    os.environ["EVIDENCE_DIR"], "R01", "frequency_2019-08-09_1640-1745_BST.csv"
)
DAY = "2019-08-09T"
OFFSET = "+01:00"


def at(hms):
    return pd.Timestamp(DAY + hms + OFFSET)


raw = pd.read_csv(CSV, dtype={"timestamp": str, "frequency_hz": float})
if not raw["timestamp"].str.match(r".*([+-]\d{2}:\d{2}|Z)$").all():
    raise SystemExit("some timestamps lack an explicit UTC offset")
ts = pd.to_datetime(raw["timestamp"])  # offset-aware, offsets kept as given
df = pd.DataFrame({"t": ts, "f": raw["frequency_hz"]})
steps = df["t"].diff().dropna().dt.total_seconds()
print(
    f"rows {len(df)}; first {df['t'].iloc[0].isoformat()}; last {df['t'].iloc[-1].isoformat()}"
)
print(
    f"strictly increasing {bool((steps > 0).all())}; duplicates "
    f"{int(df['t'].duplicated().sum())}; steps other than 1 s {int((steps != 1).sum())}; "
    f"offsets {sorted(set(raw['timestamp'].str[-6:]))}"
)


def window(start, end):
    return df[(df["t"] >= at(start)) & (df["t"] < at(end))]


def lowest(start, end):
    w = window(start, end)
    row = w.loc[w["f"].idxmin()]  # idxmin returns the first (earliest) minimum
    return row


first = lowest("16:52:45", "16:53:10")
event = lowest("16:53:20", "16:54:30")
after = df[(df["t"] > event["t"]) & (df["f"] >= 50.0)].iloc[0]
print(
    f"first post-fault minimum (16:52:45-16:53:10): {first['f']:.3f} Hz at {first['t'].isoformat()}"
)
print(
    f"event minimum (16:53:20-16:54:30): {event['f']:.3f} Hz at {event['t'].isoformat()}"
)
print(
    f"first sample >= 50 Hz after the event minimum: {after['f']:.3f} Hz at {after['t'].isoformat()}"
)

# Zero-order hold: each sample holds until the next one (never across a gap > 1 s);
# strictly below 49 Hz; window 16:52:30-16:58:00.
w = window("16:52:30", "16:58:00").copy()
nxt = w["t"].shift(-1)
hold = (nxt - w["t"]).dt.total_seconds()
hold = hold.where(hold <= 1.0, 1.0).fillna(1.0)
end_clip = (at("16:58:00") - w["t"]).dt.total_seconds()
hold = hold.where(hold <= end_clip, end_clip)
below = w["f"] < 49.0
covered = float(hold.sum())
span = (at("16:58:00") - at("16:52:30")).total_seconds()
print(
    f"samples strictly below 49 Hz: {int(below.sum())}, first {w.loc[below, 't'].iloc[0].isoformat()}, "
    f"last {w.loc[below, 't'].iloc[-1].isoformat()}"
)
print(
    f"time below 49 Hz (zero-order hold, 1-s samples): {float(hold[below].sum()):.0f} s; "
    f"missing data in window: {span - covered:.0f} s"
)
# Sensitivity to the convention: the same hold with "at or below", and linear
# interpolation between consecutive samples (time with the interpolated value < 49 Hz).
at_or_below = w["f"] <= 49.0
print(
    f"time at or below 49 Hz (zero-order hold): {float(hold[at_or_below].sum()):.0f} s"
)
f0, f1 = w["f"].to_numpy()[:-1], w["f"].shift(-1).to_numpy()[:-1]
step = hold.to_numpy()[:-1]
interp = 0.0
for a, b, dt in zip(f0, f1, step):
    if a < 49.0 and b < 49.0:
        interp += dt
    elif a < 49.0 <= b:  # rising through 49 Hz
        interp += dt * (49.0 - a) / (b - a)
    elif b < 49.0 <= a:  # falling through 49 Hz
        interp += dt * (1 - (a - 49.0) / (a - b))
print(f"time below 49 Hz (linear interpolation between samples): {interp:.3f} s")
print(
    "samples at the boundaries: "
    + ", ".join(
        f"{t.strftime('%H:%M:%S')} {f:.3f}"
        for t, f in df[
            (df["t"] >= at("16:53:39")) & (df["t"] <= at("16:53:42"))
        ].itertuples(index=False)
    )
    + " | "
    + ", ".join(
        f"{t.strftime('%H:%M:%S')} {f:.3f}"
        for t, f in df[
            (df["t"] >= at("16:54:12")) & (df["t"] <= at("16:54:15"))
        ].itertuples(index=False)
    )
)
