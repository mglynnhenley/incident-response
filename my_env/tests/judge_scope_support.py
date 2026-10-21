"""Shared helpers for the per-topic judge scoping tests (decision 52).

No network and no paid API calls (mocked judges only). The synthetic full-investigation
submission is built from real model output where it exists: increment A's real Opus 5.5
submission (``tests/fixtures/sr_live/sr80k-opus55-001``, valid on the full-investigation
bundle, whose increment-A documents are byte-identical) supplies the system-response
findings and report; the full-investigation key's first positive example of each new
criterion supplies the findings for the new topics (T04.02, T10, T11, T13-T15, T18-T20),
each restated in a report section with its reference, as real reports do.
"""

from __future__ import annotations

import copy
import functools
import json
import re
from pathlib import Path
from typing import Any

import fi_grading_support as fi

from environment.incident import fi_grading, sr_grading
from environment.incident.catalogue import Catalogue
from environment.incident.judge import load_config
from environment.incident.paths import SYSTEM_RESPONSE_BUNDLE_DIR

ENV_ROOT = Path(__file__).resolve().parents[1]
SR_LIVE = ENV_ROOT / "tests" / "fixtures" / "sr_live"
SNAPSHOT = ENV_ROOT / "tests" / "fixtures" / "judge_scope" / "sr_requests.json"
FI_CONFIG = ENV_ROOT / "configs" / "judge.fi.example.json"
SR_CONFIG = ENV_ROOT / "configs" / "judge.example.json"
BASE_RUN = "sr80k-opus55-001"
RUN_MODEL = "openrouter/anthropic/claude-opus-5.5"


@functools.cache
def sr_runs() -> dict[str, dict[str, Any]]:
    data = json.loads((SR_LIVE / "runs.json").read_text(encoding="utf-8"))
    return {run["run_id"]: run for run in data["runs"]}


@functools.cache
def sr_key() -> dict[str, Any]:
    return sr_grading.load_key()


@functools.cache
def sr_catalogue() -> Catalogue:
    return Catalogue.load(SYSTEM_RESPONSE_BUNDLE_DIR)


def sr_text(run_id: str) -> str:
    return (SR_LIVE / run_id / "submission.json").read_text(encoding="utf-8")


@functools.cache
def sr_base_report(run_id: str) -> dict[str, Any]:
    """The automated grade the judge starts from: ``grade_episode`` for a complete run,
    ``grade_submission`` with the episode's trace for an incomplete one (diagnostic)."""
    run = sr_runs()[run_id]
    if run["outcome"] == "complete":
        summary = json.loads(
            (SR_LIVE / run_id / "run_summary.json").read_text(encoding="utf-8")
        )
        return sr_grading.grade_episode(
            SR_LIVE / run_id, summary, key=sr_key(), catalogue=sr_catalogue()
        )
    return sr_grading.grade_submission(
        sr_text(run_id),
        sr_catalogue(),
        sr_key(),
        sr_grading.trace_info_from_episode(SR_LIVE / run_id),
    )


def fi_config(**overrides: Any):
    return load_config(FI_CONFIG, **overrides)


def _first_sentence(text: str) -> str:
    match = re.match(r"(.+?[.!?])(?:\s|$)", text.strip())
    return (match.group(1) if match else text.strip()).rstrip(".!?")


@functools.cache
def _synthetic() -> dict[str, Any]:
    base = json.loads(sr_text(BASE_RUN))
    key = fi.key()
    new = set(key["new_criteria"])
    titles = {d["dimension_id"]: d["title"] for d in key["dimensions"]}
    findings = list(base["findings"])
    by_task: dict[str, list[str]] = {}
    sections: list[dict[str, str]] = []
    summaries: list[str] = []
    n = 0
    for crit in key["criteria"]:
        if crit["criterion_id"] not in new:
            continue
        example = crit["examples"]["positive"][0]
        items = example["findings"] if "findings" in example else [example]
        primary = [
            v for v in crit["visible_evidence"] if v.get("role", "primary") == "primary"
        ][:2]
        ids: dict[str, str] = {}
        for i, item in enumerate(items, 1):
            n += 1
            fid = f"B{n:02d}"
            ids[f"X{i}"] = fid
            f = fi.finding(
                fid,
                item["statement"],
                item["status"],
                [(v["evidence_id"], v["locator"]) for v in primary],
            )
            if "quantity" in item:
                f["quantity"] = {"basis": "key example", **item["quantity"]}
            for name in ("event_time", "derivation"):
                if name in item:
                    f[name] = item[name]
            findings.append(f)
            by_task.setdefault(crit["task"], []).append(fid)

        def renumber(text: str, ids: dict[str, str] = ids) -> str:
            return re.sub(r"\bX\d+\b", lambda m: ids.get(m.group(0), m.group(0)), text)

        if example.get("report_summary"):
            summaries.append(renumber(example["report_summary"]))
        for section in example.get("report_sections") or []:
            sections.append(
                {"heading": section["heading"], "body": renumber(section["body"])}
            )
    statements = {f["finding_id"]: f["statement"] for f in findings}
    topic_sections = [
        {
            "heading": titles[task],
            "body": " ".join(
                f"{_first_sentence(statements[fid])} [{fid}]." for fid in fids
            ),
        }
        for task, fids in by_task.items()
        if task not in ("T18", "T19", "T20")
    ]
    sub = copy.deepcopy(base)
    sub["findings"] = findings
    sub["report"]["sections"] = (
        list(base["report"]["sections"]) + topic_sections + sections
    )
    # the executive summary stays within 600 words: increment A's summary, cut at a
    # sentence, then the T20 examples' summary text
    extra = " ".join(summaries)
    budget = 590 - len(extra.split())
    kept: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", base["report"]["executive_summary"]):
        if len(" ".join([*kept, sentence]).split()) > budget:
            break
        kept.append(sentence)
    sub["report"]["executive_summary"] = (" ".join(kept) + " " + extra).strip()
    return sub


def synthetic_fi_submission() -> dict[str, Any]:
    """A realistic-size full-investigation submission (see the module docstring)."""
    return copy.deepcopy(_synthetic())


@functools.cache
def fi_report(name: str) -> dict[str, Any]:
    sub = synthetic_fi_submission() if name == "synthetic" else fi.oracle_submission()
    return fi_grading.grade_submission(sub, fi.catalogue(), fi.key())


def fi_submission(name: str) -> dict[str, Any]:
    return synthetic_fi_submission() if name == "synthetic" else fi.oracle_submission()


def chars(units: Any) -> int:
    return sum(len(m["content"]) for u in units for m in u.messages)
