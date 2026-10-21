"""Shared helpers for the full-investigation grading tests (``test_fi_grading_*.py``).

Everything here runs on the real ``bundles/full_investigation`` bundle and the private
full-investigation answer key. No network and no paid API calls: judge outputs are built
locally (a mocked judge).
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from environment.incident import fi_grading
from environment.incident.catalogue import Catalogue
from environment.incident.episode import Episode, EpisodeConfig
from environment.incident.paths import FULL_INVESTIGATION_BUNDLE_DIR

ENV_ROOT = Path(__file__).resolve().parents[1]
HANDOFF_DIR = Path(
    os.environ.get(
        "GB_HANDOFF_DIR",
        str(ENV_ROOT.parent / ".context" / "handoff" / "GB_power_cut_handoff"),
    )
)
TEXT_DIR = Path(os.environ.get("GB_TEXT_DIR", str(HANDOFF_DIR.parent / "text")))
KEY_BUILDER_DIR = ENV_ROOT.parent / ".context" / "fi_key_builder"
SR_LIVE_DIR = Path(__file__).resolve().parent / "fixtures" / "sr_live"


@lru_cache(maxsize=1)
def key() -> dict[str, Any]:
    return fi_grading.load_key()


@lru_cache(maxsize=1)
def catalogue() -> Catalogue:
    return Catalogue.load(FULL_INVESTIGATION_BUNDLE_DIR)


def criteria() -> dict[str, dict[str, Any]]:
    return {c["criterion_id"]: c for c in key()["criteria"]}


def new_criteria() -> list[str]:
    return list(key()["new_criteria"])


_DASHES = "‐‑‒–—―−﹘﹣－"
_TRANSLATE = {ord(c): "-" for c in _DASHES}
_TRANSLATE.update({ord(c): '"' for c in "“”„‟″«»"})
_TRANSLATE.update({ord(c): "'" for c in "‘’‚‛′´`"})
_TRANSLATE[0x00AD] = None


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATE).casefold()
    return re.sub(r"\s+", " ", text).strip()


def page_texts(source_id: str) -> dict[int, str]:
    raw = (TEXT_DIR / f"{source_id}.txt").read_text(encoding="utf-8")
    marker = re.compile(rf"^=== {re.escape(source_id)} PDF page (\d+) ===$", re.M)
    parts = marker.split(raw)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


def submission(
    findings: list[dict[str, Any]],
    report: str = "",
    *,
    summary: str = "Summary.",
    sections: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    body = [{"heading": "Notes", "body": report}] if report else []
    return {
        "schema_version": "3.0",
        "variant_id": "baseline",
        "report": {
            "executive_summary": summary,
            "sections": body + list(sections or []),
        },
        "findings": findings,
    }


def finding(
    fid: str,
    statement: str,
    status: str = "reported",
    citations: list[tuple[str, str]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    out = {
        "finding_id": fid,
        "statement": statement,
        "status": status,
        "citations": [
            {"evidence_id": e, "locator": loc} for e, loc in (citations or [])
        ],
    }
    out.update(extra)
    return out


def _primary(crit: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        v for v in crit["visible_evidence"] if v.get("role", "primary") == "primary"
    ]


def example_submission(crit: dict[str, Any], example: dict[str, Any]) -> dict[str, Any]:
    """A submission made of one key example (one or several findings X1, X2, ...),
    each finding citing the criterion's first primary visible-evidence span; the
    example's ``report_summary`` is the executive summary and ``report_sections`` are
    report sections (the builder's ``check_examples.py`` does the same)."""
    keyed = _primary(crit)[0]
    items = example["findings"] if "findings" in example else [example]
    findings = []
    for i, item in enumerate(items, 1):
        f = finding(
            f"X{i}",
            item["statement"],
            item["status"],
            [(keyed["evidence_id"], keyed["locator"])],
        )
        if "quantity" in item:
            f["quantity"] = {"basis": "key example", **item["quantity"]}
        for name in ("event_time", "derivation"):
            if name in item:
                f[name] = item[name]
        findings.append(f)
    return submission(
        findings,
        example.get("report", ""),
        summary=example.get("report_summary", "Key example."),
        sections=example.get("report_sections"),
    )


def oracle_submission() -> dict[str, Any]:
    """An oracle built from the first positive example of every criterion, each
    finding citing the criterion's first two primary visible-evidence spans; the
    examples' summaries and report sections are joined, with their references
    renumbered to the oracle's findings."""
    findings: list[dict[str, Any]] = []
    summaries: list[str] = []
    sections: list[dict[str, str]] = []
    for crit in key()["criteria"]:
        example = crit["examples"]["positive"][0]
        items = example["findings"] if "findings" in example else [example]
        primary = _primary(crit)[:2]
        ids = {}
        for i, item in enumerate(items, 1):
            fid = f"F{len(findings) + 1:03d}"
            ids[f"X{i}"] = fid
            f = finding(
                fid,
                item["statement"],
                item["status"],
                [(v["evidence_id"], v["locator"]) for v in primary],
            )
            if "quantity" in item:
                f["quantity"] = {"basis": "oracle", **item["quantity"]}
            for name in ("event_time", "derivation"):
                if name in item:
                    f[name] = item[name]
            findings.append(f)

        def renumber(text: str, ids: dict[str, str] = ids) -> str:
            return re.sub(r"\bX\d+\b", lambda m: ids.get(m.group(0), m.group(0)), text)

        if example.get("report_summary"):
            summaries.append(renumber(example["report_summary"]))
        for section in example.get("report_sections") or []:
            sections.append(
                {"heading": section["heading"], "body": renumber(section["body"])}
            )
    refs = ", ".join(f["finding_id"] for f in findings)
    return submission(
        findings,
        f"Oracle findings [{refs}].",
        summary=" ".join(summaries),
        sections=sections,
    )


def grade(sub: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return fi_grading.grade_submission(sub, catalogue(), key(), **kwargs)


def row(report: dict[str, Any], cid: str) -> dict[str, Any]:
    return next(r for r in report["criteria"] if r["criterion_id"] == cid)


def auto(report: dict[str, Any], cid: str) -> Any:
    return row(report, cid)["content"]["auto_proposal"]


def episode_config(tmp_path: Path, **overrides: Any) -> EpisodeConfig:
    values: dict[str, Any] = dict(
        episode_dir=tmp_path / "root_data" / "episode",
        evidence_dir=tmp_path / "workdir" / "evidence",
        scratch_dir=tmp_path / "workdir" / "scratch",
        bundle_dir=FULL_INVESTIGATION_BUNDLE_DIR,
        python_executable=sys.executable,
        python_timeout_s=60,
        max_tool_calls=150,
        tool_profile="system_response",
    )
    values.update(overrides)
    return EpisodeConfig(**values)


def run_calls(config: EpisodeConfig, calls: list[tuple[str, dict[str, Any]]]):
    """Reset an episode and send ``calls`` through the ledger; returns the results."""
    episode = Episode(config)
    episode.reset()
    return [(tool, args, episode.call(tool, args)) for tool, args in calls]


def judge_output(report: dict[str, Any], **sections: Any) -> dict[str, Any]:
    """A mocked judge output bound to ``report`` (no model is called)."""
    out = {
        "judge_schema": fi_grading.JUDGE_SCHEMA,
        "judge_model": "test/mock-judge",
        "rubric_version": "test-rubric-0",
        "prompt_sha256": "0" * 64,
        "binding": {
            "submission_sha256": report["submission"]["sha256"],
            "key_version": report["key"]["key_version"],
            "key_sha256": report["key"]["key_sha256"],
            "bundle_sha256": report["bundle"]["bundle_sha256"],
        },
        "criteria": {},
        "assertions": {},
        "severe_flags": [],
    }
    out.update(copy.deepcopy(sections))
    return out


def decisions_for(
    report: dict[str, Any], key_obj: dict[str, Any], **sections: Any
) -> dict[str, Any]:
    out = {
        "decisions_schema": fi_grading.DECISIONS_SCHEMA,
        "decisions_version": "1",
        "builder_fixture": False,
        "reviewer": "test reviewer",
        "date": "2026-10-20",
        "binding": {
            "submission_sha256": report["submission"]["sha256"],
            "key_version": key_obj["key_version"],
            "key_sha256": fi_grading.key_sha256(key_obj),
            "bundle_sha256": report["bundle"]["bundle_sha256"],
        },
        "criteria": {},
        "assertions": {},
        "severe_flags": [],
        "explanation_quality": {"notes": "Reviewed.", "by_dimension": {}},
    }
    out.update(copy.deepcopy(sections))
    return out


def live_runs() -> list[str]:
    return sorted(p.name for p in SR_LIVE_DIR.iterdir() if p.is_dir())


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)
