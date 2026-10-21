"""Witness fact cards (manifest v2) and deterministic interviews.

A card is a fixed set of approved fact blocks; ``interview_witness`` never generates
text. The agent-visible card is::

    {persona_id, role, organisation, evidence_id, unknown_response, status?,
     blocks: [{response_id, topics: [...], response_text}]}

``status`` is the card's STATUS label; without one the reconstruction label of the MVP
synthesised records applies (witness accounts are reconstructions). Private provenance
must be stripped before a card enters the bundle; a card that still carries it is
refused. Matching is :func:`environment.incident.matching.match_topics`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from environment.incident.catalogue import CatalogueError
from environment.incident.matching import TopicMatch, match_topics
from environment.incident.schema_v2 import (
    EVIDENCE_ID_RE,
    NAME_ID_RE,
    RECORD_ID_RE,
    check_keys,
    optional_str,
    require_id,
    require_str,
    require_str_list,
    strict_json_loads,
)

__all__ = [
    "DEFAULT_WITNESS_STATUS",
    "WitnessBlock",
    "WitnessCard",
    "parse_witness_card",
]

DEFAULT_WITNESS_STATUS = (
    "STATUS: SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE. Reconstructed from "
    "published investigation material for this exercise; wording, layout and record "
    "structure are reconstructions."
)
CARD_KEYS = (
    "persona_id",
    "role",
    "organisation",
    "evidence_id",
    "unknown_response",
    "blocks",
)
BLOCK_KEYS = ("response_id", "topics", "response_text")


@dataclass(frozen=True)
class WitnessBlock:
    response_id: str
    topics: tuple[str, ...]
    response_text: str


@dataclass(frozen=True)
class WitnessCard:
    persona_id: str
    role: str
    organisation: str
    evidence_id: str
    unknown_response: str
    status: str
    blocks: tuple[WitnessBlock, ...]
    file: str
    sha256: str

    def summary(self) -> dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "role": self.role,
            "organisation": self.organisation,
            "evidence_id": self.evidence_id,
        }

    def interview(self, question: str) -> TopicMatch:
        return match_topics(question, [block.topics for block in self.blocks])


def parse_witness_card(
    entry: Mapping[str, Any], data: bytes, sha256: str, where: str
) -> WitnessCard:
    persona_id = require_id(entry, "persona_id", where, NAME_ID_RE)
    card = check_keys(
        strict_json_loads(data, f"{where} {entry['file']}"),
        f"{where} card",
        CARD_KEYS,
        ("status",),
    )
    for key in ("persona_id", "role", "organisation", "evidence_id"):
        if card.get(key) != entry.get(key):
            raise CatalogueError(
                f"{where}: card {key} {card.get(key)!r} does not match the manifest "
                f"({entry.get(key)!r})"
            )
    evidence_id = require_id(card, "evidence_id", where, EVIDENCE_ID_RE)
    raw_blocks = card.get("blocks")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise CatalogueError(f"{where}: 'blocks' must be a non-empty list")
    blocks: list[WitnessBlock] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_blocks):
        at = f"{where} blocks[{index}]"
        block = check_keys(raw, at, BLOCK_KEYS)
        response_id = require_id(block, "response_id", at, RECORD_ID_RE)
        if response_id in seen:
            raise CatalogueError(f"{at}: duplicate response_id {response_id!r}")
        seen.add(response_id)
        blocks.append(
            WitnessBlock(
                response_id=response_id,
                topics=require_str_list(block, "topics", at),
                response_text=require_str(block, "response_text", at),
            )
        )
    return WitnessCard(
        persona_id=persona_id,
        role=require_str(card, "role", where),
        organisation=require_str(card, "organisation", where),
        evidence_id=evidence_id,
        unknown_response=require_str(card, "unknown_response", where),
        status=optional_str(card, "status", where) or DEFAULT_WITNESS_STATUS,
        blocks=tuple(blocks),
        file=str(entry["file"]),
        sha256=sha256,
    )
