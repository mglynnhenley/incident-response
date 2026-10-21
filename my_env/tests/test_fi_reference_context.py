"""Context growth of the full-investigation reference investigation (decision 53).

The reference scenario is played through Karotte's runner; its transcript holds every
message the model would see. The input context of each turn is estimated from the
transcript's characters with the fit measured on the task's Opus 5.5 pilot
(``fi_fake_support.PILOT_FIT``: 5,057 + 0.3857 tokens per character, largest residual
1.7k tokens over 24 turns). The fake model reports no token usage, so this estimate is
the measurement.

Measured on bundle 0.1.0 (this file records it; the tests fail if it drifts by more than
3%): 41 calls before the submission, 42 with it; the peak input, at the final turn after
the submission is accepted, is about 157,700 tokens (79% of the 200,000-token cap): tool
results about 104,500, the submission's own message about 31,500, the other assistant
turns about 10,800, the instructions and system prompt about 5,800, and 5,057 of fixed
framing. It reads 12 of the 20 listed documents (R09 and R11 only through narrow log
windows); reading the eight it leaves unread in full would add about 66,000 tokens and
take the run past the cap. The ``repair`` scenario, whose first (rejected) submission is
as long as the reference, peaks at about 190,000 tokens (95% of the cap): at this depth
one rejected submission leaves almost no room.
"""

from __future__ import annotations

import json
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

import pytest
from fi_fake_support import (
    BUNDLE,
    CONTEXT_CAP_TOKENS,
    PILOT_FIT,
    PILOT_TRANSCRIPT,
    context_profile,
    fit_pilot,
    run_through_karotte,
)

from environment import fake_model_fi
from environment.incident.episode import Episode, EpisodeConfig

#: Recorded on bundle 0.1.0 (see the module docstring).
REFERENCE_PEAK_TOKENS = 157_660
REFERENCE_TOOL_RESULT_CHARS = 270_890
REFERENCE_SUBMISSION_MESSAGE_CHARS = 81_752
REPAIR_PEAK_TOKENS = 190_050
TOLERANCE = 0.03


@pytest.fixture(scope="module")
def profile(tmp_path_factory):
    monkeypatch = pytest.MonkeyPatch()
    try:
        _, scoring, transcript = run_through_karotte(
            tmp_path_factory.mktemp("fi-context"), monkeypatch, "reference"
        )
    finally:
        monkeypatch.undo()
    assert scoring.score == 1.0
    return context_profile(transcript), transcript


def test_reference_is_well_within_the_call_budget(profile):
    turns, _ = profile
    calls = len(fake_model_fi.fi_reference_steps()) + 1
    assert len(turns) == calls + 1  # one turn per call, then the final message
    assert calls <= 60 <= 150


def test_context_grows_monotonically_and_peaks_at_the_last_turn(profile):
    turns, _ = profile
    chars = [t["chars"] for t in turns]
    assert chars == sorted(chars)
    assert turns[-1]["estimated_tokens"] == max(t["estimated_tokens"] for t in turns)


def test_peak_context_stays_inside_the_cap_as_recorded(profile):
    turns, _ = profile
    peak = turns[-1]
    assert peak["estimated_tokens"] <= 0.8 * CONTEXT_CAP_TOKENS
    assert peak["estimated_tokens"] == pytest.approx(
        REFERENCE_PEAK_TOKENS, rel=TOLERANCE
    )
    assert peak["by_role"]["tool"] == pytest.approx(
        REFERENCE_TOOL_RESULT_CHARS, rel=TOLERANCE
    )


def test_the_submission_is_the_largest_single_message(profile):
    _, transcript = profile
    sizes = []
    for event in transcript["events"]:
        if event["type"] != "message_added":
            continue
        message = event["message"]
        names = [c["function"]["name"] for c in message.get("tool_calls") or []]
        sizes.append((len(json.dumps(message, ensure_ascii=False)), names))
    largest = max(sizes)
    assert largest[1] == ["submit_findings"]
    assert largest[0] == pytest.approx(
        REFERENCE_SUBMISSION_MESSAGE_CHARS, rel=TOLERANCE
    )
    others = sorted(size for size, names in sizes if names != ["submit_findings"])
    assert others[-1] < 30_000  # no single tool result above 30k characters


@lru_cache(maxsize=1)
def _unread_documents() -> dict[str, int]:
    """Rendered characters of the listed documents the reference does not request."""
    read: set[str] = set()
    root = Path(tempfile.mkdtemp())
    episode = Episode(
        EpisodeConfig(
            episode_dir=root / "episode",
            evidence_dir=root / "evidence",
            scratch_dir=root / "scratch",
            bundle_dir=BUNDLE,
            python_executable=sys.executable,
            max_tool_calls=300,
            tool_profile="system_response",
        )
    )
    episode.reset()
    for _, tool, args in fake_model_fi.fi_reference_steps():
        if tool in ("request_document", "request_data_return"):
            result = episode.call(tool, args)
            read.update(result.envelope["evidence_ids"])
    listed = episode.catalogue.ids()
    sizes = {}
    for doc_id in listed:
        if doc_id in read:
            continue
        result = episode.call("request_document", {"doc_id": doc_id})
        assert result.ok, doc_id
        sizes[doc_id] = len(result.text)
    return sizes


def test_reading_the_unread_documents_in_full_would_pass_the_cap(profile):
    """Decision 53: the reference reads selectively; the rest of the listed documents
    would not fit (their rendered text, JSON-escaped in the transcript, at the pilot fit)."""
    turns, _ = profile
    unread = _unread_documents()
    assert set(unread) == {"R02", "R04", "R05", "R07", "R08", "R09", "R11", "R12"}
    # transcript characters per rendered character (escaping), measured on this run
    extra_tokens = PILOT_FIT[1] * 1.08 * sum(unread.values())
    assert turns[-1]["estimated_tokens"] + extra_tokens > CONTEXT_CAP_TOKENS
    assert extra_tokens == pytest.approx(65_700, rel=0.05)


def test_pilot_fit_reproduces_the_recorded_coefficients():
    """The fit used here, re-measured on the pilot transcript when it is present (it is a
    local artifact under out/, so the test skips without it)."""
    if not PILOT_TRANSCRIPT.exists():
        pytest.skip("out/fi_pilot/transcript.json not present")
    a, b, residual = fit_pilot(json.loads(PILOT_TRANSCRIPT.read_text("utf-8")))
    assert a == pytest.approx(PILOT_FIT[0], abs=5)
    assert b == pytest.approx(PILOT_FIT[1], abs=5e-4)
    assert residual < 2_000


def test_one_rejected_submission_takes_the_run_close_to_the_cap(tmp_path, monkeypatch):
    """The repair scenario keeps its rejected submission in the conversation."""
    _, scoring, transcript = run_through_karotte(tmp_path, monkeypatch, "repair")
    assert scoring.score == 1.0
    peak = context_profile(transcript)[-1]["estimated_tokens"]
    assert 0.9 * CONTEXT_CAP_TOKENS < peak < CONTEXT_CAP_TOKENS
    assert peak == pytest.approx(REPAIR_PEAK_TOKENS, rel=TOLERANCE)
