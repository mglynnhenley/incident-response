"""Full-investigation reconstruction track: the five new S09 witness cards (no builder inputs).

The agent-visible cards are parsed with the runtime parser; every first topic must select its
own block under the runtime matcher; persona and response IDs must not collide with increment
A's cards; answers carry only valid value tags, name roles not people, and say "not known"
outside their blocks. Documented disagreements stay attributed inside a card.
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
INCIDENT = ENV_ROOT / "src" / "environment" / "incident"
FI_WITNESSES = INCIDENT / "bundles" / "full_investigation" / "witnesses"
SR_WITNESSES = INCIDENT / "bundles" / "system_response" / "witnesses"
PROVENANCE = json.loads(
    (INCIDENT / "private" / "full_investigation" / "provenance_recon.json").read_text(
        "utf-8"
    )
)
META = json.loads(
    (
        ENV_ROOT / "builder" / "full_investigation" / "recon" / "documents.json"
    ).read_text("utf-8")
)
PERSONAS = [
    "eso-communications-lead",
    "gtr-fleet-engineer",
    "hospital-estates-manager",
    "network-rail-control-manager",
    "ukpn-epn-spn-control-engineer",
]
TAGS = {"measured", "reported", "estimated", "modelled", "digitised", "illustrative"}


def card_bytes(persona_id: str) -> bytes:
    return (FI_WITNESSES / f"{persona_id}.json").read_bytes()


def card(persona_id: str) -> dict:
    return json.loads(card_bytes(persona_id))


def parsed(persona_id: str):
    data = card_bytes(persona_id)
    raw = json.loads(data)
    entry = {k: raw[k] for k in ("persona_id", "role", "organisation", "evidence_id")}
    entry["file"] = f"witnesses/{persona_id}.json"
    return parse_witness_card(entry, data, hashlib.sha256(data).hexdigest(), persona_id)


def answer(persona_id: str, question: str) -> str | None:
    result = parsed(persona_id).interview(question)
    if result.kind != "match":
        return None
    return parsed(persona_id).blocks[result.blocks[0]].response_text


@pytest.mark.parametrize("persona_id", PERSONAS)
def test_card_parses_and_topics_select_their_own_block(persona_id: str) -> None:
    witness = parsed(persona_id)
    assert witness.evidence_id == "S09"
    assert witness.status.startswith("STATUS: SYNTHESISED FOR EVALUATION")
    assert "not known" in witness.unknown_response.casefold()
    topics = [block.topics for block in witness.blocks]
    for index, block in enumerate(witness.blocks):
        result = match_topics(block.topics[0], topics)
        assert result.kind == "match" and result.blocks == (index,), block.response_id
        assert set(re.findall(r"\[([a-z]+)\]", block.response_text)) <= TAGS


@pytest.mark.parametrize("persona_id", PERSONAS)
def test_visible_card_has_no_provenance_and_matches_meta(persona_id: str) -> None:
    raw = card(persona_id)
    assert all(
        set(b) == {"response_id", "topics", "response_text"} for b in raw["blocks"]
    )
    entry = next(w for w in META["witnesses"] if w["persona_id"] == persona_id)
    assert entry["sha256"] == hashlib.sha256(card_bytes(persona_id)).hexdigest()
    blocks = PROVENANCE["witnesses"][persona_id]["blocks"]
    assert sorted(blocks) == sorted(b["response_id"] for b in raw["blocks"])
    assert all(b["sources"] for b in blocks.values())


def test_ids_do_not_collide_with_increment_a() -> None:
    sr = [json.loads(p.read_text("utf-8")) for p in sorted(SR_WITNESSES.glob("*.json"))]
    assert not {c["persona_id"] for c in sr} & set(PERSONAS)
    ids = [b["response_id"] for c in sr for b in c["blocks"]]
    ids += [b["response_id"] for p in PERSONAS for b in card(p)["blocks"]]
    assert len(ids) == len(set(ids))
    assert (
        sorted(p.stem for p in FI_WITNESSES.glob("*.json") if p.stem in PERSONAS)
        == PERSONAS
    )


def test_unrelated_question_gets_not_known() -> None:
    result = parsed("gtr-fleet-engineer").interview("What was the inertia estimate?")
    assert result.kind == "none"
    result = parsed("hospital-estates-manager").interview("When was the breaker reset?")
    assert result.kind != "match"


def test_gtr_engineer_keeps_own_and_orr_counts_apart() -> None:
    own = answer("gtr-fleet-engineer", "battery reset")
    assert own and "27 [reported]" in own and "28 [reported]" not in own
    orr = answer("gtr-fleet-engineer", "ORR figures")
    assert orr and orr.startswith("ORR's report")
    assert "22 [reported]" in orr and "7 [reported]" in orr
    versions = answer("gtr-fleet-engineer", "software versions")
    assert versions and "3.27 or above" in versions and "3.25 or below" in versions
    # APP F gives the 28 in its cause section, beside the software levels.
    assert "28 [reported]" in versions


def test_gtr_engineer_does_not_point_out_count_conflicts() -> None:
    """Decisions 9, 20, 30, 31: the cards restate each count in its source's place and never
    compare counts in the builder's words (the agent finds the inconsistencies)."""
    comparative = re.compile(
        r"different counts|differ(?:s|ent)? from|same review|in its cause section|"
        r"inconsisten|conflict|discrepan|whereas our|unlike our|compared with",
        re.IGNORECASE,
    )
    for persona in PERSONAS:
        for block in card(persona)["blocks"]:
            hit = comparative.search(block["response_text"])
            assert hit is None, (block["response_id"], hit.group(0) if hit else "")
    orr = answer("gtr-fleet-engineer", "ORR figures")
    assert orr and "our review" not in orr
    frequency = answer("gtr-fleet-engineer", "supply frequency information")
    assert frequency and "16 seconds [reported]" in frequency


def test_eso_communications_lead_gives_both_ofgem_times() -> None:
    text = answer("eso-communications-lead", "Ofgem contact")
    assert text and "17:51 [reported]" in text and "18:00 [reported]" in text
    assert "just after" in text
    beis = answer("eso-communications-lead", "BEIS contact")
    assert beis and "17:41 [reported]" in beis and "17:40 [reported]" in beis
    hornsea = answer("eso-communications-lead", "Hornsea notification")
    assert hornsea and hornsea.startswith("Ofgem's report states")


def test_ukpn_engineer_attributes_the_reconnection_finding() -> None:
    text = answer("ukpn-epn-spn-control-engineer", "reconnection")
    assert text and text.startswith("Ofgem reports")
    assert "do not appear to have technically met" in text
    returns = answer("ukpn-epn-spn-control-engineer", "UKPN returns")
    assert returns and "16:56 [reported]" in returns
    times = answer("ukpn-epn-spn-control-engineer", "communication times")
    assert times and "17:14 [reported]" in times and "Approx. 17:40" in times


def test_hospital_card_does_not_link_the_unnamed_hospital_to_ipswich() -> None:
    other = answer("hospital-estates-manager", "other hospitals")
    assert other and "not named" in other and "Ipswich" not in other
    statement = answer("hospital-estates-manager", "standby generators")
    assert statement and "summarised here rather than quoted" in statement
    assert "gives no times" in statement


def test_cards_name_roles_not_people() -> None:
    for persona_id in PERSONAS:
        body = card_bytes(persona_id).decode("utf-8")
        for name in ("Julian Leslie", "Kwarteng", "Moloney", "Bousso", "Fenton"):
            assert name not in body
        assert not re.search(r"(?<![\w.])@[A-Za-z0-9_]{2,}", body)
        assert "£" not in body
