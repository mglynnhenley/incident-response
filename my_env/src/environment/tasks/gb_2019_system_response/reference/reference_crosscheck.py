"""Reference cross-checks for the system-response task, as sent to run_python.

Runs after R02 and R07 have been retrieved (their CSV files are then under
``$EVIDENCE_DIR``). It checks the reported records against real public data and does the
arithmetic the reference submission relies on:

* Elexon B1610 metered volumes per BM unit (MWh per settlement period, x 2 = average MW)
  for Hornsea One's three units and Little Barford, before and after the event, and the
  Maximum Export Limits declared around it;
* the Elexon demand control instruction record against the 5-minute demand summary;
* the Little Barford sequence-of-events offsets converted to BST with the datum
  T = 16:52:34 +/- 0.5 s, and the Hornsea log's UTC times converted to BST;
* ESO's Table 2 components summed (the derived-sum rule: within 1 MW).

The record values typed in below are transcribed from the retrieved documents (S03, S12)
and are labelled as such in the output.

Grader-side file: the scripted fake agent sends its text through ``run_python``; it is
never shown to the evaluated agent.
"""

import os
from datetime import datetime, timedelta, timezone

import pandas as pd

EV = os.environ["EVIDENCE_DIR"]
BST = timezone(timedelta(hours=1))

# -- Elexon B1610: metered volume per unit and settlement period ------------------------
b1610 = pd.read_csv(
    os.path.join(EV, "R02", "R02_elexon_b1610_selected_units_20190809.csv")
)
units = ["T_HOWAO-1", "T_HOWAO-2", "T_HOWAO-3", "T_LBAR-1"]
sel = b1610[b1610["bmUnit"].isin(units) & b1610["settlementPeriod"].between(32, 36)]
table = sel.pivot(index="settlementPeriod", columns="bmUnit", values="quantity")
print("B1610 average MW (MWh x 2) by settlement period (SP34 = 16:30-17:00 BST):")
print((table * 2).round(1).to_string())
avg = table * 2
hornsea = avg[["T_HOWAO-1", "T_HOWAO-2", "T_HOWAO-3"]].sum(axis=1)
print(
    f"Hornsea One total: SP33 {hornsea[33]:.1f} MW, SP34 {hornsea[34]:.1f} MW, "
    f"SP35 {hornsea[35]:.1f} MW; SP33 - SP35 = {hornsea[33] - hornsea[35]:.1f} MW"
)
for unit in units:
    print(
        f"  {unit}: SP33 {avg.loc[33, unit]:.1f} MW -> SP35 {avg.loc[35, unit]:.1f} MW"
    )
# SP34 holds the event: 22.56 min before the de-load (15:30:00Z-15:52:33.7Z) and 7.44 min
# after. Reported levels (S01): 799 MW before, 62 MW after.
pre_share = (22 * 60 + 33.728) / 1800
expected = pre_share * 799 + (1 - pre_share) * 62
print(
    f"Hornsea SP34 if 799 MW until 16:52:33.728 BST and 62 MW after: {expected:.1f} MW "
    f"(metered {hornsea[34]:.1f} MW)"
)
mels = pd.read_csv(
    os.path.join(EV, "R02", "R02_elexon_mels_selected_units_20190809.csv")
)
near = mels[
    (mels["timeFrom"] >= "2019-08-09T15:00") & (mels["timeFrom"] < "2019-08-09T17:00")
]
print("MEL records 15:00-17:00Z (limits declared by the operator, not output):")
print(
    near[["bmUnit", "timeFrom", "timeTo", "levelFrom", "levelTo"]]
    .sort_values(["bmUnit", "timeFrom"])
    .to_string(index=False)
)

# -- demand control instruction vs the 5-minute demand summary ---------------------------
dci = pd.read_csv(os.path.join(EV, "R07", "R07_elexon_dci_201908.csv"))
print(
    "DCI record(s):",
    dci[["timeFrom", "timeTo", "volume", "demandControlEventFlag"]].to_dict("records"),
)
demand = pd.read_csv(
    os.path.join(EV, "R07", "R07_elexon_demand_outturn_summary_5min_20190809.csv")
)
demand["t"] = pd.to_datetime(demand["startTime"])
win = demand[
    (demand["startTime"] >= "2019-08-09T15:40")
    & (demand["startTime"] <= "2019-08-09T16:45")
]
print(win[["startTime", "demand"]].to_string(index=False))
before = demand.loc[demand["startTime"] == "2019-08-09T15:50:00Z", "demand"].iloc[0]
low = win.loc[win["demand"].idxmin()]
print(
    f"5-min demand summary: {before} MW at 15:50Z, low {low['demand']} MW at "
    f"{low['startTime']}, drop {before - low['demand']} MW; first value >= {before} MW "
    f"after the low: "
    + str(win[(win["t"] > low["t"]) & (win["demand"] >= before)]["startTime"].iloc[0])
)

# -- clocks -------------------------------------------------------------------------------
T = datetime(2019, 8, 9, 16, 52, 34, tzinfo=BST)  # S03 datum, +/- 0.5 s, read as BST
soe = {  # transcribed from S03 Part 2 (offsets from T, seconds)
    "E3 ST control system shutdown initiated": 0.253,
    "E5 ST generator breaker open feedback": 1.185,
    "E6 GT1A auto shutdown command": 56.583,
    "E7 GT1A breaker open feedback": 57.620,
    "E8 GT1B manual shutdown command": 83.897,
    "E9 GT1B breaker open feedback": 84.613,
}
for name, offset in soe.items():
    t = T + timedelta(seconds=offset)
    print(
        f"S03 {name}: T + {offset} s = {t.isoformat(timespec='milliseconds')} +/- 0.5 s"
    )
print(
    f"GT1B breaker after GT1A breaker: {soe['E9 GT1B breaker open feedback'] - soe['E7 GT1A breaker open feedback']:.3f} s"
)
for label, utc in (
    ("de-load starts", "15:52:33.728"),
    ("de-load complete", "15:52:33.835"),
):
    t = datetime.fromisoformat(f"2019-08-09T{utc}+00:00").astimezone(BST)
    print(f"S01 Hornsea {label}: {utc}Z = {t.isoformat(timespec='milliseconds')}")
fault = datetime(2019, 8, 9, 16, 52, 33, 490000, tzinfo=BST)
print(
    f"Hornsea de-load start after fault inception: {(datetime.fromisoformat('2019-08-09T15:52:33.728+00:00') - fault).total_seconds():.3f} s"
)

# -- ESO Table 2 (transcribed from S12 A1) -------------------------------------------------
components = {
    "ST1C": 244,
    "Hornsea": 737,
    "VS (est.)": 150,
    "RoCoF (est.)": 350,
    "GT1A": 210,
    "GT1B": 187,
}
running = 0
for name, mw in components.items():
    running += mw
    print(f"Table 2 cumulative after {name}: {running} MW")
print(f"six-component sum {sum(components.values())} MW (printed: 1,878 MW)")
print(f"Little Barford units: {244 + 210 + 187} MW (printed: 641 MW)")
print(f"Hornsea loss: 799 - 62 = {799 - 62} MW")
