"""The judge's structured response: JSON schema (sent as ``response_format``) and a
small validator for the subset of JSON Schema it uses (no third-party dependency).

The schema is strict-mode compatible (every property required, no additional
properties, no unsupported keywords); limits the provider cannot enforce (counts,
lengths, which IDs are allowed) are checked after parsing by the runner.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

__all__ = [
    "CONFIDENCE",
    "CONTENT",
    "EVIDENCE",
    "FINDING_VERDICTS",
    "REPORT_VERDICTS",
    "RESPONSE_SCHEMA",
    "RESPONSE_SCHEMA_ID",
    "validate",
]

RESPONSE_SCHEMA_ID = "gb2019-sr-judge-response/1"
CONTENT = (1, 0.5, 0)
EVIDENCE = (1, 0)
FINDING_VERDICTS = ("supported", "unsupported", "contradicted", "not_factual")
REPORT_VERDICTS = ("supported", "unsupported", "contradicted")
CONFIDENCE = ("high", "medium", "low")

_SPAN: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["evidence_id", "locator", "quote"],
    "properties": {
        "evidence_id": {"type": "string"},
        "locator": {"type": "string"},
        "quote": {"type": "string"},
    },
}
_IDS: dict[str, Any] = {"type": "array", "items": {"type": "string"}}
_SPANS: dict[str, Any] = {"type": "array", "items": _SPAN}

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "criteria",
        "assertions",
        "report_assertions",
        "severe_flag_suggestions",
    ],
    "properties": {
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "criterion_id",
                    "content",
                    "evidence_support",
                    "finding_ids",
                    "supporting_spans",
                    "rationale",
                    "confidence",
                ],
                "properties": {
                    "criterion_id": {"type": "string"},
                    "content": {"type": "number", "enum": list(CONTENT)},
                    "evidence_support": {"type": "integer", "enum": list(EVIDENCE)},
                    "finding_ids": _IDS,
                    "supporting_spans": _SPANS,
                    "rationale": {"type": "string"},
                    "confidence": {"type": "string", "enum": list(CONFIDENCE)},
                },
            },
        },
        "assertions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "finding_id",
                    "verdict",
                    "spans",
                    "rationale",
                    "confidence",
                ],
                "properties": {
                    "finding_id": {"type": "string"},
                    "verdict": {"type": "string", "enum": list(FINDING_VERDICTS)},
                    "spans": _SPANS,
                    "rationale": {"type": "string"},
                    "confidence": {"type": "string", "enum": list(CONFIDENCE)},
                },
            },
        },
        "report_assertions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "verdict", "spans", "rationale", "confidence"],
                "properties": {
                    "text": {"type": "string"},
                    "verdict": {"type": "string", "enum": list(REPORT_VERDICTS)},
                    "spans": _SPANS,
                    "rationale": {"type": "string"},
                    "confidence": {"type": "string", "enum": list(CONFIDENCE)},
                },
            },
        },
        "severe_flag_suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["flag_id", "finding_ids", "report_quote", "rationale"],
                "properties": {
                    "flag_id": {"type": "string"},
                    "finding_ids": _IDS,
                    "report_quote": {"type": "string"},
                    "rationale": {"type": "string"},
                },
            },
        },
    },
}

_TYPES: dict[str, Any] = {
    "object": lambda v: isinstance(v, Mapping),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: (
        isinstance(v, int)
        and not isinstance(v, bool)
        or (isinstance(v, float) and v.is_integer())
    ),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate(
    instance: Any, schema: Mapping[str, Any] = RESPONSE_SCHEMA, path: str = "$"
) -> list[str]:
    """Errors of ``instance`` against ``schema`` (``type``, ``enum``, ``properties``,
    ``required``, ``additionalProperties: false``, ``items``, ``minItems``,
    ``maxItems``, ``maxLength``); an empty list when it is valid."""
    errors: list[str] = []
    types = schema.get("type")
    if types is not None:
        names: Sequence[str] = [types] if isinstance(types, str) else list(types)
        if not any(_TYPES[name](instance) for name in names):
            return [f"{path}: expected {' or '.join(names)}"]
    if "enum" in schema and not any(
        instance == option and type(instance) is not bool for option in schema["enum"]
    ):
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    if isinstance(instance, Mapping):
        props = schema.get("properties") or {}
        for name in schema.get("required") or []:
            if name not in instance:
                errors.append(f"{path}: missing property {name!r}")
        if schema.get("additionalProperties") is False:
            for name in instance:
                if name not in props:
                    errors.append(f"{path}: unexpected property {name!r}")
        for name, sub in props.items():
            if name in instance:
                errors += validate(instance[name], sub, f"{path}.{name}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for index, item in enumerate(instance):
                errors += validate(item, schema["items"], f"{path}[{index}]")
    if (
        isinstance(instance, str)
        and "maxLength" in schema
        and len(instance) > schema["maxLength"]
    ):
        errors.append(f"{path}: longer than {schema['maxLength']} characters")
    return errors
