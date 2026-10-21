"""Shared helpers for the LLM-judge tests (``test_sr_judge_*.py``).

No network and no paid API calls: :class:`FakeJudge` stands in for the OpenRouter
client. It reads the request exactly as the judge would (the submission JSON and the
span blocks in the user message) and answers with a response built from what it was
shown, so quotes are real unless a test makes them up on purpose.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sr_grading_support import catalogue, finding, key, submission

from environment.incident import sr_grading
from environment.incident.judge import ChatResponse, JudgeConfig

RUN_MODEL = "openrouter/anthropic/claude-opus-5.5"
SERVED_MODEL = "openai/gpt-6.1-sol-20261001"

_SPAN = re.compile(
    r'<span id="(?P<id>[CK]\d+)" evidence_id="(?P<ev>[^"]+)" locator="(?P<loc>[^"]+)"'
    r"[^>]*>\n(?P<text>.*?)\n</span>",
    re.S,
)
_UNIT = re.compile(r"^Unit (\S+): ", re.M)
_LIST = r'^"{name}": exactly one entry for each of: (.*)\.$'


def small_submission(extra_report: str = "") -> dict[str, Any]:
    """Five findings on the real bundle: F1 (T06, cited twice), F2 (Ofgem's total as
    ESO's: accounting cap on T02.06), F3 (uncited), F4 (R01 sample), F5 (hypothesis,
    never classified). The report names the model that wrote it (blinding)."""
    return submission(
        [
            finding(
                "F1",
                "Ørsted's investigation report concludes that the de-load was caused "
                "by an insufficiently damped electrical resonance in the "
                "sub-synchronous frequency range of the wind farm control system, "
                "triggered by the initial event.",
                "reported",
                [("S01", "L54-L58"), ("S09", "response:S09-ORS-04")],
            ),
            finding(
                "F2",
                "ESO's total generation lost was at least 1,990 MW.",
                "reported",
                [("S12", "L39-L42")],
            ),
            finding("F3", "Hornsea's internal network was weak.", "inferred"),
            finding(
                "F4",
                "The minimum 1-s sample was 48.787 Hz at 16:53:49 BST.",
                "observed",
                [("R01", "row:830")],
            ),
            finding(
                "F5",
                "The ST1C speed discrepancy may have been caused by the lightning "
                "disturbance.",
                "hypothesis",
                [("S03", "L20")],
            ),
        ],
        report=(
            "This report was prepared by Claude Opus 5.5 (Anthropic). Hornsea One "
            "de-loaded [F1]. The DRC was cleared by the operator. Totals [F2] [F3] "
            "[F4] [F5]." + extra_report
        ),
    )


def base_report(sub: dict[str, Any]) -> dict[str, Any]:
    return sr_grading.grade_submission(sub, catalogue(), key())


def config(**overrides: Any) -> JudgeConfig:
    return JudgeConfig(**overrides)


@dataclass
class Request:
    """What a fake judge read from one request."""

    payload: dict[str, Any]
    unit_id: str
    criteria: list[str]
    findings: list[str]
    spans: dict[str, dict[str, str]]
    submission: dict[str, Any]

    @property
    def user(self) -> str:
        return self.payload["messages"][1]["content"]

    def first_line(self, span_id: str) -> str:
        text = self.spans[span_id]["text"]
        line = text.split("\n")[0]
        return re.sub(r"^\[L\d+\] ", "", line)

    def cited_by(self, fid: str) -> list[str]:
        for f in self.submission["findings"]:
            if f["finding_id"] == fid:
                return [c["span"] for c in f["citations"] if c["span"]]
        return []

    def quote_for(self, fid: str) -> dict[str, str] | None:
        """A real quote from the first span ``fid`` cites (``None`` if uncited)."""
        for sid in self.cited_by(fid):
            span = self.spans[sid]
            return {
                "evidence_id": span["ev"],
                "locator": span["loc"],
                "quote": self.first_line(sid)[:120],
            }
        return None


def parse_request(payload: dict[str, Any]) -> Request:
    user = payload["messages"][1]["content"]

    def ids(name: str) -> list[str]:
        match = re.search(_LIST.format(name=name), user, re.M)
        assert match, name
        text = match.group(1)
        return [] if text.startswith("(none") else text.split(", ")

    spans = {
        m["id"]: {"ev": m["ev"], "loc": m["loc"], "text": m["text"]}
        for m in _SPAN.finditer(user)
    }
    sub_text = user.split("<submission>\n", 1)[1].split("\n</submission>", 1)[0]
    return Request(
        payload=payload,
        unit_id=_UNIT.search(user).group(1),
        criteria=ids("criteria"),
        findings=ids("assertions"),
        spans=spans,
        submission=json.loads(sub_text),
    )


def default_response(req: Request) -> dict[str, Any]:
    """Every criterion content 1 on F1 (evidence 1 with a real quote from a span F1
    cites); every finding supported with a real quote from its own citations (or
    unsupported when uncited)."""
    quote = req.quote_for("F1")
    criteria = [
        {
            "criterion_id": cid,
            "content": 1,
            "evidence_support": 1 if quote else 0,
            "finding_ids": ["F1"] if quote else [],
            "supporting_spans": [quote] if quote else [],
            "rationale": f"{cid}: F1 states it",
            "confidence": "high",
        }
        for cid in req.criteria
    ]
    assertions = []
    for fid in req.findings:
        q = req.quote_for(fid)
        assertions.append(
            {
                "finding_id": fid,
                "verdict": "supported" if q else "unsupported",
                "spans": [q] if q else [],
                "rationale": f"{fid} checked",
                "confidence": "medium",
            }
        )
    return {
        "criteria": criteria,
        "assertions": assertions,
        "report_assertions": [],
        "severe_flag_suggestions": [],
    }


@dataclass
class FakeJudge:
    """A mocked chat client. ``respond(request) -> dict | str`` builds each reply (a
    dict is serialised as JSON); ``usage`` is reported per call."""

    respond: Callable[[Request], Any] = default_response
    usage: Callable[[Request, int], dict[str, Any]] | None = None
    calls: list[Request] = field(default_factory=list)
    finish_reason: str = "stop"

    def complete(self, payload: dict[str, Any]) -> ChatResponse:
        req = parse_request(copy.deepcopy(dict(payload)))
        self.calls.append(req)
        reply = self.respond(req)
        content = reply if isinstance(reply, str) else json.dumps(reply)
        chars = sum(len(m["content"]) for m in payload["messages"])
        usage = (
            self.usage(req, chars)
            if self.usage
            else {
                "prompt_tokens": chars // 4,
                "completion_tokens": 400,
                "total_tokens": chars // 4 + 400,
                "cost": 0.0125,
            }
        )
        return ChatResponse(
            content=content,
            usage=usage,
            model=SERVED_MODEL,
            provider="OpenAI",
            finish_reason=self.finish_reason,
            response_id=f"gen-{len(self.calls)}",
            latency_s=0.01,
        )


def no_client() -> Any:
    raise AssertionError("the judge model must not be called")
