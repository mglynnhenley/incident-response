"""Reference cross-checks for the full-investigation task, as sent to run_python.

Runs after S01, S03, S05, S08 and S12 have been retrieved (their text files are then
under ``$EVIDENCE_DIR``). It reads the numbered records from those files and does the
arithmetic and clock conversions the reference submission relies on:

* ESO's Table 2 components (S12 section A) summed, with the cumulative column checked
  (the derived-sum rule: within 1 MW);
* ORR's Table 1 of rail cancellations, part cancellations and delay minutes (S08 part 3)
  summed by route against its printed total, and ORR's lock-out counts added up
  (technician resets plus driver resets; locked-out trains plus the trapped Class 387s);
* the LFDD returns as tabulated by the ESO and by the E3C (S05 parts 1 and 2) summed
  by area, and the areas where the two tables differ;
* the Little Barford sequence-of-events offsets (S03 part 2) converted to BST with the
  datum T = 16:52:34 +/- 0.5 s;
* UTC record times converted to BST (UTC+01:00): the Hornsea One log, the ESO's first
  public post (decoded post identifier) and the first Little Barford REMIT message.

Every record value is parsed from the retrieved files, except two UTC times of the last
item, which are transcribed from the log rows that returned them (the ESO-COMMS row and
the REMIT asset-log row; log rows write no files) and are labelled as such.

Grader-side file: the scripted fake agent sends its code (without this docstring) through
``run_python``; it is never shown to the evaluated agent.
"""

import os
import re
from datetime import datetime, timedelta, timezone

EV = os.environ["EVIDENCE_DIR"]
BST = timezone(timedelta(hours=1))


def lines(doc_id):
    path = os.path.join(EV, doc_id, doc_id + ".txt")
    with open(path, encoding="utf-8") as handle:
        return handle.read().splitlines()


def number(text):
    return int(text.replace(",", ""))


# -- ESO Table 2 (S12 section A, lines 16-24) --------------------------------------------
s12 = lines("S12")
pairs = [
    (number(a), number(b))
    for line in s12[15:24]
    for a, b in re.findall(r"([\d,]+) MW \[\w+\] \| ([\d,]+) MW \[reported\]", line)
]
infeed = [a for a, _ in pairs]
cumulative = [b for _, b in pairs]
running = [sum(infeed[: i + 1]) for i in range(len(infeed))]
print(
    "ESO Table 2 (S12 L16-L24): components "
    + " + ".join(str(v) for v in infeed)
    + f" = {sum(infeed)} MW; printed cumulative {cumulative[-1]} MW; "
    f"running sums match the cumulative column: {running == cumulative}"
)
print(
    f"cumulative after the RoCoF trips (fourth row): {running[3]} MW "
    f"(= {' + '.join(str(v) for v in infeed[:4])})"
)

# -- ORR Table 1 (S08 lines 155-165) and ORR's counts -----------------------------------
s08 = lines("S08")
routes = []
total = None
for line in s08:
    m = re.match(
        r"T\d\s+(.+?) \| (\d+) \[reported\] \| (\d+) \[reported\] \| (\d+) \[reported\]",
        line,
    )
    if m:
        row = (m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)))
        if row[0] == "TOTAL":
            total = row
        else:
            routes.append(row)
sums = [sum(r[i] for r in routes) for i in (1, 2, 3)]
print(
    f"ORR Table 1 (S08 L155-L165): {len(routes)} routes sum to {sums[0]} cancelled, "
    f"{sums[1]} part-cancelled, {sums[2]} delay minutes; printed TOTAL "
    f"{total[1]} | {total[2]} | {total[3]}; match: {tuple(sums) == total[1:]}"
)
orr = " ".join(" ".join(s08[119:127]).split())  # O02, ORR 1.0
counts = {
    name: int(re.search(pattern, orr).group(1))
    for name, pattern in (
        ("stranded", r"(\d+) \[reported\] trains were stranded"),
        ("locked out", r"lock-out of (\d+) \[reported\] trains"),
        ("technician", r"(\d+) \[reported\] trains were permanently locked out"),
        ("driver", r"while (\d+) \[reported\] trains were restored"),
        ("detrained", r"from (\d+) \[reported\] trains to a place of safety"),
    )
}
print(
    f"ORR 1.0 (S08 L120-L127): technician {counts['technician']} + driver "
    f"{counts['driver']} = {counts['technician'] + counts['driver']} "
    f"(locked out {counts['locked out']}); locked out {counts['locked out']} + 2 "
    f"Class 387 = {counts['locked out'] + 2} (stranded {counts['stranded']}); "
    f"detrained from {counts['detrained']} trains"
)

# -- LFDD returns (S05 parts 1 and 2) ---------------------------------------------------
s05 = lines("S05")


def table(prefix, first, last):
    """(label, MW or None) per area, in printed order."""
    text = "\n".join(s05[first - 1 : last])
    rows = []
    for m in re.finditer(
        rf"^{prefix}(\d\d)\s+(.+?) \| (.+?) \| (\d+ MW|not given)", text, re.M
    ):
        area = "" if m.group(3) in ("not given", "-") else " " + m.group(3)
        value = None if m.group(4) == "not given" else int(m.group(4)[:-3])
        rows.append((m.group(2) + area, value))
    return rows


eso = table("D", 16, 34)
e3c = table("F", 39, 57)
eso_sum = sum(v for _, v in eso if v is not None)
e3c_sum = sum(v for _, v in e3c if v is not None)
print(
    f"LFDD returns: ESO Table 6 (S05 L16-L35) {len(eso)} areas sum to {eso_sum} MW; "
    f"E3C Table 1 (S05 L39-L58) {len(e3c)} areas sum to {e3c_sum} MW; difference "
    f"{e3c_sum - eso_sum} MW"
)
for (label, value), (_, other) in zip(eso, e3c):
    if other != value:
        shown = [f"{v} MW" if v is not None else "not given" for v in (value, other)]
        print(f"  differs: {label}: ESO {shown[0]}, E3C {shown[1]}")

# -- Little Barford SOE offsets (S03 part 2) to BST -------------------------------------
s03 = lines("S03")
datum = datetime(2019, 8, 9, 16, 52, 34, tzinfo=BST)
print("Little Barford SOE (S03 L21-L29), T = 16:52:34 +/- 0.5 s read as BST:")
for line in s03[20:29]:
    m = re.match(r"(E\d)\s+(.+?)\s{2,}(?:T = )?([+]?[\d.]+) (ms|s) \[reported\]", line)
    offset = float(m.group(3)) / (1000 if m.group(4) == "ms" else 1)
    at = datum + timedelta(seconds=offset)
    print(
        f"  {m.group(1)} {m.group(2)}: T + {offset:.3f} s = {at.strftime('%H:%M:%S.%f')[:-3]} BST"
    )

# -- UTC record times to BST -----------------------------------------------------------
s01 = " ".join(lines("S01")[40:41])  # S01 L41: de-load start (log times are UTC, Z)
deload = re.match(r"(\d\d:\d\d:\d\d\.\d+)Z", s01).group(1)
for label, utc in (
    ("Hornsea One de-load start (S01 L41, UTC)", f"2019-08-09T{deload}+00:00"),
    # transcribed from the tool results that returned these rows
    (
        "ESO first public post (ESO-COMMS row R09-E13, decoded identifier, UTC)",
        "2019-08-09T17:27:46.703+00:00",
    ),
    (
        "T_LBAR-1 REMIT first revision published (asset-log row R09-REMIT-00056773-r1, UTC)",
        "2019-08-09T16:54:44+00:00",
    ),
):
    print(f"{label}: {utc} = {datetime.fromisoformat(utc).astimezone(BST).isoformat()}")
