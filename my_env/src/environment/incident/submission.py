"""Submission format v3: pydantic models and validation.

``validate_submission`` accepts the object the agent passed to ``submit_findings`` (a
dict, or a JSON string encoding one) and returns a :class:`ValidationResult`. Invalid
submissions are rejected with a list of ``{"path", "message"}`` problems the agent can
repair; a valid submission is returned with its canonical JSON (``sort_keys=True,
indent=2, ensure_ascii=False``) and that text's SHA-256.

Format::

    {
      "schema_version": "3.0",
      "variant_id": "baseline",
      "report": {
        "executive_summary": "<= 600 whitespace-separated words; may reference [F01]",
        "sections": [{"heading": "...", "body": "markdown referencing [F03] [F04]"}]
      },
      "findings": [
        {"finding_id": "F01", "statement": "...",
         "status": "observed|reported|inferred|hypothesis|unknown",
         "citations": [{"evidence_id": "R03", "locator": "L14-L16"}],
         "quantity": {"value": 1.0, "unit": "Hz", "basis": "..."},     (optional)
         "event_time": "<ISO-8601 with offset>",                       (optional)
         "derivation": "..."}                                           (optional)
      ]
    }
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
)

from environment.incident.locators import (
    LocatorError,
    parse_iso_instant,
    parse_locator,
    validate_locator,
)

__all__ = [
    "SCHEMA_VERSION",
    "MAX_FINDINGS",
    "STATUSES",
    "FINDING_ID_PATTERN",
    "REFERENCE_RE",
    "Citation",
    "Finding",
    "Quantity",
    "Report",
    "ReportSection",
    "Submission",
    "ValidationResult",
    "canonical_json",
    "extract_references",
    "validate_submission",
    "word_count",
]

SCHEMA_VERSION = "3.0"
MAX_FINDINGS = 200
MAX_SUBMISSION_CHARS = 2_000_000
MAX_REPORTED_ERRORS = 100
STATUSES = ("observed", "reported", "inferred", "hypothesis", "unknown")
FINDING_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$"
REFERENCE_RE = re.compile(
    r"\[([A-Za-z0-9][A-Za-z0-9_.-]{0,39})"
    r"(?:\s*,\s*[A-Za-z0-9][A-Za-z0-9_.-]{0,39})*\]"
)
_ID_IN_REFERENCE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}")


def _non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty or whitespace only")
    return value


Text = Annotated[str, AfterValidator(_non_blank)]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Citation(_StrictModel):
    evidence_id: Text
    locator: Text


class Quantity(_StrictModel):
    value: Annotated[float, Field(allow_inf_nan=False)]
    unit: Text
    basis: Text


class Finding(_StrictModel):
    finding_id: Annotated[str, Field(pattern=FINDING_ID_PATTERN)]
    statement: Text
    status: Literal["observed", "reported", "inferred", "hypothesis", "unknown"]
    citations: list[Citation]
    quantity: Quantity | None = None
    event_time: str | None = None
    derivation: Text | None = None


class ReportSection(_StrictModel):
    heading: Text
    body: Text


class Report(_StrictModel):
    executive_summary: Text
    sections: list[ReportSection]


class Submission(_StrictModel):
    schema_version: str
    variant_id: Text
    report: Report
    findings: list[Finding]


@dataclass
class ValidationResult:
    ok: bool
    errors: list[dict[str, str]] = field(default_factory=list)
    submission: Submission | None = None
    canonical_json: str | None = None
    sha256: str | None = None

    @property
    def findings_count(self) -> int:
        return len(self.submission.findings) if self.submission else 0


def word_count(text: str) -> int:
    """Whitespace-separated words."""
    return len(text.split())


def extract_references(text: str) -> list[str]:
    """Finding IDs referenced as ``[F01]`` or ``[F01, F02]`` in report text, in order."""
    found: list[str] = []
    for match in REFERENCE_RE.finditer(text):
        found.extend(_ID_IN_REFERENCE_RE.findall(match.group(0)))
    return found


def canonical_json(obj: Any) -> str:
    return json.dumps(
        obj, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    )


def _format_path(loc: tuple[Any, ...]) -> str:
    path = ""
    for part in loc:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}" if path else str(part)
    return path or "submission"


def _pydantic_errors(exc: ValidationError) -> list[dict[str, str]]:
    problems = []
    for err in exc.errors(include_url=False):
        loc = tuple(err.get("loc", ()))
        kind = err.get("type", "")
        if kind == "extra_forbidden":
            message = (
                f"unexpected field '{loc[-1] if loc else '?'}'; it is not part of the "
                "v3 submission format"
            )
        elif kind == "missing":
            message = "required field is missing"
        elif kind == "string_pattern_mismatch":
            message = (
                "must start with a letter or digit and contain only letters, digits, "
                "'_', '.' or '-' (at most 40 characters), e.g. 'F01'"
            )
        elif kind == "literal_error" and loc and loc[-1] == "status":
            message = f"must be one of: {', '.join(STATUSES)}"
        else:
            message = str(err.get("msg", "invalid value"))
            if message.startswith("Value error, "):
                message = message[len("Value error, ") :]
        problems.append({"path": _format_path(loc), "message": message})
    return problems


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not allowed in JSON")


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


_TOO_DEEP = "JSON nested too deeply; a v3 submission needs only a few levels of nesting"


def _parse_raw(raw: Any) -> tuple[Any, list[dict[str, str]]]:
    if raw is None:
        return None, [{"path": "submission", "message": "no submission was provided"}]
    if isinstance(raw, str):
        if len(raw) > MAX_SUBMISSION_CHARS:
            return None, [
                {
                    "path": "submission",
                    "message": f"submission is larger than {MAX_SUBMISSION_CHARS} characters",
                }
            ]
        try:
            raw = json.loads(
                raw,
                object_pairs_hook=_no_duplicate_keys,
                parse_constant=_reject_constant,
            )
        except RecursionError:
            return None, [{"path": "submission", "message": _TOO_DEEP}]
        except (json.JSONDecodeError, ValueError) as exc:
            return None, [{"path": "submission", "message": f"not valid JSON: {exc}"}]
    if not isinstance(raw, dict):
        return None, [
            {
                "path": "submission",
                "message": f"must be a JSON object, got {type(raw).__name__}",
            }
        ]
    try:
        text = canonical_json(raw)
    except RecursionError:
        return None, [{"path": "submission", "message": _TOO_DEEP}]
    except (TypeError, ValueError) as exc:
        return None, [
            {"path": "submission", "message": f"not representable as JSON: {exc}"}
        ]
    if len(text) > MAX_SUBMISSION_CHARS:
        return None, [
            {
                "path": "submission",
                "message": f"submission is larger than {MAX_SUBMISSION_CHARS} characters",
            }
        ]
    return raw, []


def _semantic_errors(
    sub: Submission,
    catalogue: Any,
    word_limit: int,
    variant_id: str,
) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []

    def add(path: str, message: str) -> None:
        problems.append({"path": path, "message": message})

    if sub.schema_version != SCHEMA_VERSION:
        add(
            "schema_version", f"must be '{SCHEMA_VERSION}' (got {sub.schema_version!r})"
        )
    if sub.variant_id != variant_id:
        add("variant_id", f"must be '{variant_id}' (got {sub.variant_id!r})")
    if len(sub.findings) > MAX_FINDINGS:
        add(
            "findings",
            f"has {len(sub.findings)} findings; at most {MAX_FINDINGS} are allowed",
        )

    words = word_count(sub.report.executive_summary)
    if words > word_limit:
        add(
            "report.executive_summary",
            f"has {words} words; the limit is {word_limit} whitespace-separated words",
        )

    first_seen: dict[str, int] = {}
    for index, finding in enumerate(sub.findings):
        if finding.finding_id in first_seen:
            add(
                f"findings[{index}].finding_id",
                f"duplicate finding_id '{finding.finding_id}' (already used by "
                f"findings[{first_seen[finding.finding_id]}])",
            )
        else:
            first_seen[finding.finding_id] = index

    texts = [("report.executive_summary", sub.report.executive_summary)]
    for index, section in enumerate(sub.report.sections):
        texts.append((f"report.sections[{index}].heading", section.heading))
        texts.append((f"report.sections[{index}].body", section.body))
    for path, text in texts:
        reported: set[str] = set()
        for ref in extract_references(text):
            if ref not in first_seen and ref not in reported:
                reported.add(ref)
                add(
                    path,
                    f"references [{ref}] but no finding has finding_id '{ref}'; square "
                    "brackets in the report are reserved for finding IDs such as [F01]",
                )

    # A manifest-v2 catalogue resolves evidence IDs to documents and/or records
    # (events, entries, witness responses); a v1 catalogue to documents only.
    target_of = getattr(catalogue, "citation_target", None) or catalogue.get
    citable = getattr(catalogue, "citable_ids", None) or catalogue.ids
    valid_ids = ", ".join(citable())
    for index, finding in enumerate(sub.findings):
        base = f"findings[{index}]"
        if finding.event_time is not None:
            try:
                parse_iso_instant(finding.event_time)
            except LocatorError as exc:
                add(f"{base}.event_time", str(exc))
        if finding.derivation is not None and not finding.citations:
            add(
                f"{base}.citations",
                "a finding with a derivation must cite the evidence it was derived from",
            )
        for c_index, citation in enumerate(finding.citations):
            c_path = f"{base}.citations[{c_index}]"
            doc = target_of(citation.evidence_id)
            if doc is None:
                add(
                    f"{c_path}.evidence_id",
                    f"unknown evidence_id '{citation.evidence_id}'; valid IDs: {valid_ids}",
                )
                continue
            try:
                validate_locator(parse_locator(citation.locator), doc)
            except LocatorError as exc:
                add(f"{c_path}.locator", str(exc))
    return problems


def _cap(problems: list[dict[str, str]]) -> list[dict[str, str]]:
    if len(problems) <= MAX_REPORTED_ERRORS:
        return problems
    extra = len(problems) - MAX_REPORTED_ERRORS
    return problems[:MAX_REPORTED_ERRORS] + [
        {"path": "submission", "message": f"... and {extra} more problems not shown"}
    ]


def validate_submission(
    raw: Any,
    catalogue: Any,
    word_limit: int = 600,
    variant_id: str = "baseline",
) -> ValidationResult:
    """Validate a v3 submission against the schema, the catalogue and the episode rules."""
    obj, problems = _parse_raw(raw)
    if problems:
        return ValidationResult(ok=False, errors=problems)
    try:
        submission = Submission.model_validate(obj)
    except ValidationError as exc:
        return ValidationResult(ok=False, errors=_cap(_pydantic_errors(exc)))
    problems = _semantic_errors(submission, catalogue, word_limit, variant_id)
    if problems:
        return ValidationResult(ok=False, errors=_cap(problems), submission=None)
    text = canonical_json(obj)
    return ValidationResult(
        ok=True,
        errors=[],
        submission=submission,
        canonical_json=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
