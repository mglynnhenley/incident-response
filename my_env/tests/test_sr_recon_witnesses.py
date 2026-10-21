"""Reconstruction track: S09 witness fact cards.

Cards are parsed with the runtime's parser after provenance is stripped (as the integration
step does); topics must select their own block under the runtime matcher; every number in an
answer must occur in the block's own source quotes; personas stay within their own records.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from environment.incident.matching import match_topics
from environment.incident.witness import parse_witness_card

ENV_ROOT = Path(__file__).resolve().parents[1]
# Source cards with provenance (the agent-visible copies are written by build_bundle.py).
WITNESSES = ENV_ROOT / "builder" / "system_response" / "rows" / "witnesses"
PROVENANCE = json.loads(
    (
        ENV_ROOT
        / "src"
        / "environment"
        / "incident"
        / "private"
        / "system_response"
        / "provenance_recon.json"
    ).read_text("utf-8")
)
PERSONAS = [
    "dno-control-engineer",
    "eso-control-engineer",
    "nget-protection-engineer",
    "orsted-hornsea-operations-engineer",
    "rwe-lb-shift-charge-engineer",
]
NUMBER = re.compile(r"(?<![A-Za-z0-9])\d(?:[\d,]*\d)?(?:[.:]\d+)*")


def card(persona: str) -> dict:
    return json.loads((WITNESSES / f"{persona}.json").read_text("utf-8"))


def numbers(text: str) -> set[str]:
    out = set()
    text = re.sub(r"\[[a-z]+\]", " ", text)
    for token in NUMBER.findall(text.replace("–", "-")):
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", token):
            token = token.replace(",", "")
        out.add(str(int(token)) if token.isdigit() else token)
    return out


def test_five_cards() -> None:
    assert sorted(p.stem for p in WITNESSES.glob("*.json")) == PERSONAS


@pytest.mark.parametrize("persona", PERSONAS)
def test_card_parses_with_runtime_after_stripping_provenance(persona: str) -> None:
    source = card(persona)
    visible = {
        **source,
        "blocks": [
            {k: v for k, v in b.items() if k != "provenance"} for b in source["blocks"]
        ],
    }
    data = json.dumps(visible, ensure_ascii=False, sort_keys=True).encode()
    entry = {
        k: source[k] for k in ("persona_id", "role", "organisation", "evidence_id")
    }
    entry["file"] = f"witnesses/{persona}.json"
    parsed = parse_witness_card(entry, data, hashlib.sha256(data).hexdigest(), "test")
    assert parsed.evidence_id == "S09"
    assert parsed.status.startswith(
        "STATUS: SYNTHESISED FOR EVALUATION — NOT REAL EVIDENCE."
    )
    assert "not known" in parsed.unknown_response.casefold()


@pytest.mark.parametrize("persona", PERSONAS)
def test_every_block_has_provenance_kept_privately(persona: str) -> None:
    private = PROVENANCE["witnesses"][persona]["blocks"]
    for block in card(persona)["blocks"]:
        assert block["provenance"], block["response_id"]
        assert private[block["response_id"]]["sources"] == block["provenance"]
        for ref in block["provenance"]:
            assert ref["source_id"] in {"ESO", "APP", "OFG", "E3C", "E3C-I"}
            assert len(ref["quote"].split()) >= 3


@pytest.mark.parametrize("persona", PERSONAS)
def test_numbers_in_answers_come_from_their_quotes(persona: str) -> None:
    for block in card(persona)["blocks"]:
        pool: set[str] = set()
        for ref in block["provenance"]:
            pool |= numbers(ref["quote"]) | numbers(ref["section"])
        missing = numbers(block["response_text"]) - pool
        assert not missing, (block["response_id"], sorted(missing))


@pytest.mark.parametrize("persona", PERSONAS)
def test_topics_select_their_own_block(persona: str) -> None:
    blocks = card(persona)["blocks"]
    topics = [b["topics"] for b in blocks]
    for index, block in enumerate(blocks):
        result = match_topics(block["topics"][0], topics)
        assert (result.kind, result.blocks) == ("match", (index,)), block["response_id"]


@pytest.mark.parametrize("persona", PERSONAS)
def test_unrelated_question_is_not_known(persona: str) -> None:
    topics = [b["topics"] for b in card(persona)["blocks"]]
    assert (
        match_topics("What was the weather in Paris that weekend?", topics).kind
        == "none"
    )


def test_response_ids_unique() -> None:
    ids = [b["response_id"] for p in PERSONAS for b in card(p)["blocks"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    ("persona", "forbidden"),
    [
        ("nget-protection-engineer", ["Hornsea", "Little Barford", "RWE", "Ørsted"]),
        ("rwe-lb-shift-charge-engineer", ["Hornsea", "Ørsted", "bypass valve"]),
        ("orsted-hornsea-operations-engineer", ["Little Barford", "RWE"]),
        ("dno-control-engineer", ["Hornsea", "Little Barford"]),
        ("eso-control-engineer", ["root cause", "speed signal", "resonance"]),
    ],
)
def test_witnesses_stay_within_their_records(
    persona: str, forbidden: list[str]
) -> None:
    body = " ".join(b["response_text"] for b in card(persona)["blocks"])
    for term in forbidden:
        assert term not in body, (persona, term)


def test_little_barford_root_causes_stay_unestablished() -> None:
    body = " ".join(
        b["response_text"] for b in card("rwe-lb-shift-charge-engineer")["blocks"]
    )
    assert "For reasons presently unknown" in body
    assert "has not been determined" in body
    assert "still unknown" in body
    assert "Our hypothesis is" in body


def test_no_frequency_landmarks_on_cards() -> None:
    for persona in PERSONAS:
        body = json.dumps(card(persona), ensure_ascii=False)
        for value in ("48.787", "49.083", "50.001"):
            assert value not in body
