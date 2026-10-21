"""Reference analysis of R01 for the full-investigation task, as sent to run_python.

The reference investigator retrieves R01 with ``request_document`` (which places the R01
CSV under ``$EVIDENCE_DIR/R01/``) and reads the samples around the 49 Hz crossing with
``query_frequency``. This code checks the series (explicit offsets, strictly increasing
1-second steps, no duplicates or gaps), prints the frequency landmarks with their data-row
numbers (the citation locators ``row:<n>``), and the time strictly below 49 Hz under a
zero-order hold, with the sensitivity to the convention (at or below 49 Hz; linear
interpolation). It also prints the two samples that bracket the first fall below 49 Hz:
the rail accounts' "within 200 ms" of 49 Hz falls between them, so the 1-s record cannot
show it. Windows are half-open ``[start, end)`` in BST (UTC+01:00), as in the grader's
reference analysis (``environment.incident.frequency``).

Increment A's analysis (``gb_2019_system_response/reference/reference_analysis.py``)
with the bracketing samples added; that file is frozen with its task.

Grader-side file: the scripted fake agent sends its code (without this docstring) through
``run_python``; it is never shown to the evaluated agent.
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
df = pd.DataFrame({"t": ts, "f": raw["frequency_hz"], "row": range(1, len(raw) + 1)})
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
    return w.loc[w["f"].idxmin()]  # idxmin returns the first (earliest) minimum


def show(label, row):
    print(
        f"{label}: {row['f']:.3f} Hz at {row['t'].isoformat()} (row {int(row['row'])})"
    )


first = lowest("16:52:45", "16:53:10")
event = lowest("16:53:20", "16:54:30")
after = df[(df["t"] > event["t"]) & (df["f"] >= 50.0)].iloc[0]
show("first post-fault minimum (16:52:45-16:53:10)", first)
show("event minimum (16:53:20-16:54:30)", event)
show("first sample >= 50 Hz after the event minimum", after)
pre = window("16:52:00", "16:52:33")
print(
    f"pre-fault 16:52:00-16:52:33: mean {pre['f'].mean():.3f} Hz, "
    f"range {pre['f'].min():.3f}-{pre['f'].max():.3f} Hz"
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
rows_below = w.loc[below, "row"]
print(
    f"samples strictly below 49 Hz: {int(below.sum())}, first "
    f"{w.loc[below, 't'].iloc[0].isoformat()} (row {int(rows_below.iloc[0])}), last "
    f"{w.loc[below, 't'].iloc[-1].isoformat()} (row {int(rows_below.iloc[-1])})"
)
print(
    f"time below 49 Hz (zero-order hold, 1-s samples): {float(hold[below].sum()):.0f} s; "
    f"missing data in window: {span - covered:.0f} s"
)
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
        for t, f, _ in df[
            (df["t"] >= at("16:53:39")) & (df["t"] <= at("16:53:42"))
        ].itertuples(index=False)
    )
    + " | "
    + ", ".join(
        f"{t.strftime('%H:%M:%S')} {f:.3f}"
        for t, f, _ in df[
            (df["t"] >= at("16:54:12")) & (df["t"] <= at("16:54:15"))
        ].itertuples(index=False)
    )
)
# Below the LFDD stage-1 setting: the 1-s samples cannot time the 16:53:49.398 trigger.
lfdd = window("16:53:40", "16:54:00")
print(
    "samples below 48.8 Hz: "
    + ", ".join(
        f"{t.strftime('%H:%M:%S')} {f:.3f}"
        for t, f, _ in lfdd[lfdd["f"] < 48.8].itertuples(index=False)
    )
)
print(
    f"16:57:15 sample: {df.loc[df['t'] == at('16:57:15'), 'f'].iloc[0]:.3f} Hz "
    "(ESO timeline: back to 50 Hz at 16:57:15)"
)
# The rail accounts' protection response ("within 200 ms" of 49 Hz) is a reported design
# figure: the crossing lies between two 1-s samples and cannot be timed from R01.
cross = df[(df["t"] >= at("16:53:30")) & (df["f"] < 49.0)].iloc[0]
prev = df[df["row"] == cross["row"] - 1].iloc[0]
print(
    f"first fall below 49 Hz lies between {prev['t'].strftime('%H:%M:%S')} "
    f"({prev['f']:.3f} Hz, row {int(prev['row'])}) and {cross['t'].strftime('%H:%M:%S')} "
    f"({cross['f']:.3f} Hz, row {int(cross['row'])}); a 200 ms response cannot be resolved "
    "from 1-s samples"
)
