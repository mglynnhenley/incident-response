"""Per-topic judge scoping shows the findings that would lower a topic's credit, not
only those that earn it (decision 52 follow-up; docs/DECISIONS.md, increment B grading
outcome).

A judge criterion whose value is 0 (or capped) when an error is stated anywhere in the
submission (T15.04: communications presented as a cause of the outage; T14.04/T14.05:
an enforcement outcome or legal finding; T10.01, T11.03, T05.03, T06.05, ...) must see
the finding that states it, even when that finding is mainly about another topic. The
recall check of the credited findings (``test_judge_scope.py``) never measured this.
Measured here on the real full-investigation pilot (``tests/fixtures/fi_live``) with
the request plan alone (the automated grade is not redone, so the error is not also
picked up by a contradiction pre-screen): each error sentence is added to every finding
of another topic in turn.

* the key's own error examples of the screened criteria (25 sentences, 1,115
  placements): 751 shown before the error screen (67%), all 1,115 after;
* ten hand-written paraphrases in other words than the rules (445 placements): 145
  before (33%), 409 after (92%). The one paraphrase still missed is a counterfactual
  without communications wording ("Had the ESO briefed the DNOs earlier, fewer
  customers would have lost supply"), which T15 sees only as a gist.
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

import fi_grading_support as fi
import pytest

from environment.incident import fi_grading
from environment.incident.grading import _as_submission
from environment.incident.judge import build_units, load_config, load_rubric
from environment.incident.judge import scope as topic_scope

PILOT = Path(__file__).resolve().parent / "fixtures" / "fi_live" / "fi-pilot-opus55-001"
FI_TASK = "gb-2019-full-investigation"

PARAPHRASES = [
    (
        "T15",
        "The communications breakdown between the ESO and the DNOs is what made the "
        "demand disconnection as large as it was.",
    ),
    (
        "T15",
        "Had the ESO briefed the DNOs earlier, fewer customers would have lost supply.",
    ),
    (
        "T10",
        "The Thameslink trains halted because the railway's power supply dropped out.",
    ),
    (
        "T05",
        "Rail services and the rest of the affected services were back to normal at the "
        "same time as customers were reconnected.",
    ),
    ("T14", "Ofgem determined that Hornsea One breached the Grid Code."),
    ("T14", "The generators were penalised by the regulator."),
    ("T11", "The Stanlow refinery shut down because LFDD disconnected its supply."),
    ("T06", "The Hornsea wind farm's DRC caused the de-load."),
    (
        "T16",
        "The transmission protection failed to operate correctly and caused the event.",
    ),
    ("T07", "Little Barford's trip was due to a defective speed probe."),
]
KNOWN_MISS = PARAPHRASES[1][1]


@lru_cache(maxsize=1)
def pilot() -> tuple[dict, dict]:
    text = (PILOT / "submission.json").read_text(encoding="utf-8")
    report = fi_grading.grade_submission(text, fi.catalogue(), fi.key())
    sub, _ = _as_submission(text, fi.catalogue())
    return sub, report


def scope(error_screen: bool = True):
    base = load_config(task=FI_TASK).scope
    return base.model_copy(update={"error_screen": error_screen})


def screened_examples() -> list[tuple[str, str]]:
    """(task, sentence) of every one-finding error example (content 0) of a judge
    criterion that an error bounds."""
    out = []
    for crit in fi.key()["criteria"]:
        auto = crit.get("auto") or {}
        if crit["assessment_mode"] != "judge" or not (
            auto.get("contradictions") or auto.get("severe_flags_zero")
        ):
            continue
        for ex in crit["examples"]["negative"]:
            if ex.get("content") != 0 or "findings" in ex or ex.get("report_summary"):
                continue
            out.append((crit["task"], ex["statement"]))
    return out


def shown_hosts(task: str, sentence: str, error_screen: bool = True) -> dict[str, bool]:
    """For every finding of another topic: whether the topic's request shows it in
    full once ``sentence`` is added to its statement."""
    sub, report = pilot()
    dims = {
        a["assertion_id"]: a["dimension"]
        for a in report["assertion_quality"]["assertions"]
    }
    sc = scope(error_screen)
    vocab = topic_scope.build_vocabulary(fi.key())
    out = {}
    for f in sub["findings"]:
        host = f["finding_id"]
        if dims[host] == task:
            continue
        mutated = copy.deepcopy(sub)
        target = next(x for x in mutated["findings"] if x["finding_id"] == host)
        target["statement"] = target["statement"].rstrip() + " " + sentence
        ids = [x["finding_id"] for x in mutated["findings"]]
        sentences = topic_scope.report_sentences(mutated, ids)
        ranking = topic_scope.rank_topics(mutated, sentences, vocab, sc)
        plan = topic_scope.plan_topic(
            task,
            sub=mutated,
            report=report,
            key=fi.key(),
            scope=sc,
            ranking=ranking,
            sentences=sentences,
            classify=[],
        )
        out[host] = host in plan.focal
    return out


def test_the_pilot_fixture_is_the_real_run():
    runs = json.loads((PILOT.parent / "runs.json").read_text(encoding="utf-8"))["runs"]
    # the panel run joined the pilot in decision 77; the measurements here use the pilot
    assert PILOT.name in [r["run_id"] for r in runs]
    pilot = next(r for r in runs if r["run_id"] == PILOT.name)
    assert (
        pilot["source"] == "out/fi_pilot/gb2019-fi-pilot-opus55-001_artifacts/episode"
    )


def test_every_screened_criterion_has_error_examples():
    tasks = {task for task, _ in screened_examples()}
    assert {"T05", "T06", "T10", "T11", "T14", "T15", "T16"} <= tasks
    assert len(screened_examples()) == 25


@pytest.mark.parametrize(("task", "sentence"), screened_examples())
def test_a_keyed_error_in_any_finding_is_shown_to_its_topic(task, sentence):
    hosts = shown_hosts(task, sentence)
    assert hosts and all(hosts.values()), [h for h, ok in hosts.items() if not ok]


def test_paraphrased_errors_recall_and_the_known_miss():
    shown = total = 0
    missed: set[str] = set()
    for task, sentence in PARAPHRASES:
        for ok in shown_hosts(task, sentence).values():
            total += 1
            shown += ok
            if not ok:
                missed.add(sentence)
    assert (shown, total) == (409, 445)
    assert missed == {KNOWN_MISS}


def test_without_the_error_screen_recall_was_lower():
    """The baseline the screen is measured against (whole-finding vocabulary only)."""
    task, sentence = "T15", PARAPHRASES[0][1]
    before = shown_hosts(task, sentence, error_screen=False)
    after = shown_hosts(task, sentence)
    assert sum(after.values()) == len(after)
    assert sum(before.values()) < 0.5 * len(before)


def test_the_mutated_pilot_shows_f21_to_t15_with_its_reason():
    """The review's probe: F21 (response) gains a causal communications claim. With the
    'media' wording the pre-screen excuses it (no contradiction, F21 is not matched), but
    the error screen still shows F21 to T15 in full."""
    sub, _ = pilot()
    text = (PILOT / "submission.json").read_text(encoding="utf-8")
    data = json.loads(text)
    for f in data["findings"]:
        if f["finding_id"] == "F21":
            f["statement"] += (
                " Late and uncoordinated ESO communications with the DNOs and the media "
                "contributed to the scale of the demand disconnection."
            )
    report = fi_grading.grade_submission(data, fi.catalogue(), fi.key())
    t1504 = next(r for r in report["criteria"] if r["criterion_id"] == "T15.04")
    assert t1504["layers"]["caps"] == []  # "media" is a non-assertion of the rule
    config = load_config(task=FI_TASK)
    mutated, _ = _as_submission(data, fi.catalogue())
    inputs = build_units(
        mutated,
        report,
        fi.key(),
        fi.catalogue(),
        config,
        load_rubric(config.rubric_path()),
    )
    unit = next(u for u in inputs.units if u.unit_id == "T15")
    assert "F21" in unit.shown_finding_ids
    assert "error_screen" in unit.selection["F21"]
    assert "F21" not in unit.finding_ids  # shown, not classified by T15
    assert sub["findings"][20]["finding_id"] == "F21"


def test_the_screen_ignores_rule_exclusions_and_reads_severe_flags():
    screens = topic_scope.error_screen(
        [c for c in fi.key()["criteria"] if c["task"] == "T14"], fi.key()
    )
    names = [name for name, _ in screens]
    assert "SF3" in names and "SF1" in names
    assert any(name.startswith("T14.04:legal_finding_asserted") for name in names)
    hits = topic_scope.screen_hits(
        "Ofgem was not able to establish breach; RWE and Orsted paid £4.5m.", screens
    )
    assert "SF3" in hits  # the flag's own exclusions ("not ... establish") are ignored
