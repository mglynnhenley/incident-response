"""The ledger with a v2 bundle: tool set, budget, freeze, determinism and replay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from incident_helpers import make_bundle, make_config
from sr_helpers import SR_TOOLS, make_sr_bundle, rehash, sr_config, sr_submission

from environment.incident.episode import (
    SYSTEM_RESPONSE_TOOL_NAMES,
    TOOL_NAMES,
    Episode,
    build_transcript_summary,
    read_state,
    read_trace,
)
from environment.incident.replay import replay_episode

DAY = {"start": "2019-08-09T00:00:00Z", "end": "2019-08-10T00:00:00Z"}

# One call of every tool, including refusals; all deterministic except run_python.
SCRIPT: list[tuple[str, dict]] = [
    ("list_documents", {}),
    ("request_document", {"doc_id": "R03"}),
    (
        "request_document",
        {"party": "System Operator", "description": "synthetic record"},
    ),
    (
        "request_document",
        {"party": "System Operator", "description": "engineering analysis"},
    ),
    (
        "query_frequency",
        {"start": "2019-08-09T16:40:00+01:00", "end": "2019-08-09T17:10:00+01:00"},
    ),
    ("query_asset_log", {"asset_id": "PLANT-A", **DAY}),
    ("query_asset_log", {"asset_id": "ESW-400", **DAY, "signal": "circuit state"}),
    ("query_control_log", {"room": "SO-CONTROL", **DAY}),
    (
        "interview_witness",
        {"persona_id": "so-engineer", "question": "How was demand restored?"},
    ),
    ("interview_witness", {"persona_id": "so-engineer", "question": "frequency?"}),
    ("interview_witness", {"persona_id": "dno-engineer", "question": "lunch"}),
    ("request_data_return", {"party": "Synthetic DNO A", "data_type": "relay returns"}),
    (
        "request_data_return",
        {"party": "Synthetic DNO A", "data_type": "relay timing logs"},
    ),
    (
        "request_data_return",
        {"party": "Synthetic Generator B", "data_type": "control system logs"},
    ),
    (
        "query_frequency",
        {"start": "2019-08-09T12:00:00Z", "end": "2019-08-09T13:00:00Z"},
    ),
    (
        "run_python",
        {"code": "import os\nprint(sorted(os.listdir(os.environ['EVIDENCE_DIR'])))"},
    ),
]
EXPECTED_CODES = [
    "OK",
    "OK",
    "AMBIGUOUS_REQUEST",
    "OK",
    "OK",
    "OK",
    "OK",
    "OK",
    "OK",
    "AMBIGUOUS_REQUEST",
    "OK",
    "OK",
    "NOT_HELD",
    "REFUSED",
    "OUT_OF_RANGE",
    "OK",
]


@pytest.fixture
def config(tmp_path: Path):
    return sr_config(tmp_path, make_sr_bundle(tmp_path / "src"))


def _play(ep: Episode) -> list:
    return [ep.call(tool, args) for tool, args in SCRIPT]


def test_v2_episode_serves_nine_tools(config):
    ep = Episode(config)
    meta = ep.reset()
    assert ep.tool_names == SYSTEM_RESPONSE_TOOL_NAMES == SR_TOOLS
    assert meta["tool_names"] == list(SR_TOOLS) and meta["manifest_version"] == 2
    assert meta["budgets"]["max_tool_calls"] == 150
    assert meta["budgets"]["frequency_page_size"] == 1000
    assert meta["budgets"]["log_page_size"] == 200
    snapshot = json.loads((config.episode_dir / "episode_config.json").read_text())
    assert snapshot["tool_names"] == list(SR_TOOLS)
    assert snapshot["config"]["tool_profile"] == "system_response"
    unknown = ep.call("bash", {"cmd": "ls"})
    assert unknown.error_code == "INVALID_ARGUMENT" and unknown.counted
    assert "query_frequency" in unknown.envelope["error"]["message"]


def test_v1_episode_keeps_the_four_mvp_tools(tmp_path: Path):
    ep = Episode(make_config(tmp_path, make_bundle(tmp_path / "src")))
    ep.reset()
    assert ep.tool_names == TOOL_NAMES
    for tool in ("query_frequency", "interview_witness", "request_data_return"):
        result = ep.call(tool, {"persona_id": "x"})
        assert result.error_code == "INVALID_ARGUMENT"
        assert result.envelope["error"]["message"].endswith(", ".join(TOOL_NAMES))
    described = ep.call("request_document", {"party": "x", "description": "y"})
    assert described.error_code == "INVALID_ARGUMENT"
    assert "this tool accepts: doc_id" in described.envelope["error"]["message"]


def test_every_tool_goes_through_the_ledger(config):
    ep = Episode(config)
    ep.reset()
    results = _play(ep)
    assert [r.record["outcome_code"] for r in results] == EXPECTED_CODES
    assert all(r.counted for r in results)
    assert [r.envelope["request_id"] for r in results][-1] == f"req-{len(SCRIPT):03d}"
    state = read_state(config.episode_dir)
    assert state.calls_used == len(SCRIPT) and state.python_calls == 1
    assert state.retrieved == ["R03", "S12", "R01", "S05"]
    stdout = results[-1].envelope["data"]["stdout"]
    assert stdout == "['R01', 'R03', 'S05', 'S12']\n"
    trace = read_trace(config.episode_dir)
    assert [r["deterministic"] for r in trace] == [True] * (len(SCRIPT) - 1) + [False]


def test_deterministic_tools_render_identically_across_episodes(tmp_path: Path):
    bundle = make_sr_bundle(tmp_path / "src")
    texts = []
    for name in ("a", "b"):
        ep = Episode(sr_config(tmp_path / name, bundle))
        ep.reset()
        texts.append([r.text for r in _play(ep)[:-1]])
    assert texts[0] == texts[1]


def test_replay_reproduces_every_deterministic_call(config):
    ep = Episode(config)
    ep.reset()
    _play(ep)
    assert ep.submit_findings(sr_submission()).ok
    assert ep.call("query_frequency", DAY).error_code == "EPISODE_CLOSED"
    report = replay_episode(config.episode_dir)
    assert report.ok, report.summary_text()
    counts = report.counts()
    assert counts["match"] == len(SCRIPT) + 1 and counts["recorded"] == 1


def test_replay_detects_a_changed_bundle(config, tmp_path: Path):
    ep = Episode(config)
    ep.reset()
    _play(ep)
    other = make_sr_bundle(tmp_path / "other")
    card = other / "witnesses" / "so-engineer.json"
    card.write_text(card.read_text().replace("about restoration", "about restoring"))
    rehash(other)
    report = replay_episode(config.episode_dir, bundle_dir=other)
    assert not report.ok
    # The changed witness answer, plus every call that issued a cursor: cursors carry an
    # integrity field keyed by the bundle sha256, so they are bound to the exact bundle.
    paged = {
        r["request_id"]
        for r in read_trace(config.episode_dir)
        if r["envelope"].get("next_cursor")
    }
    assert paged, "the script should include paginated calls"
    witness = [i for i in report.mismatches if i.tool == "interview_witness"]
    assert [i.request_id for i in witness] == ["req-009"]
    others = {i.request_id for i in report.mismatches if i.tool != "interview_witness"}
    assert others == paged
    assert any("bundle differs" in problem for problem in report.problems)


def test_budget_of_150_and_freeze(tmp_path: Path):
    config = sr_config(tmp_path, make_sr_bundle(tmp_path / "src"), max_tool_calls=3)
    ep = Episode(config)
    ep.reset()
    for _ in range(3):
        assert ep.call(
            "interview_witness", {"persona_id": "nobody", "question": "x"}
        ).counted
    over = ep.call("query_frequency", DAY)
    assert over.error_code == "BUDGET_EXCEEDED" and not over.counted
    assert read_state(config.episode_dir).budget_exhausted
    assert sr_config(tmp_path, tmp_path).max_tool_calls == 150


def test_transcript_summary_counts_the_nine_tools(config):
    ep = Episode(config)
    ep.reset()
    ep.call("query_frequency", DAY)
    events = [
        {"type": "tool_call_started", "tool_call": {"function": {"name": name}}}
        for name in ("query_frequency", "interview_witness", "bash")
    ]
    summary = build_transcript_summary(config.episode_dir, events)
    assert summary["tool_calls_episode_tools"] == 2  # tool names from the snapshot
    assert summary["budgets"]["tool_calls_limit"] == 150
    mvp_view = build_transcript_summary(
        config.episode_dir, events, tool_names=TOOL_NAMES
    )
    assert mvp_view["tool_calls_episode_tools"] == 0


# -- replay of a container run (recorded bundle path absent on this host) --------------
def _shipped_sr_episode(tmp_path: Path) -> Episode:
    from environment.incident.episode import EpisodeConfig
    from environment.incident.paths import SYSTEM_RESPONSE_BUNDLE_DIR

    ep = Episode(
        EpisodeConfig(
            episode_dir=tmp_path / "episode",
            evidence_dir=tmp_path / "evidence",
            scratch_dir=tmp_path / "scratch",
            bundle_dir=SYSTEM_RESPONSE_BUNDLE_DIR,
            max_tool_calls=150,
            tool_profile="system_response",
        )
    )
    ep.reset()
    return ep


def _record_container_path(episode_dir: Path, recorded: str) -> None:
    path = episode_dir / "episode_config.json"
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    snapshot["config"]["bundle_dir"] = recorded
    path.write_text(json.dumps(snapshot), encoding="utf-8")


@pytest.mark.parametrize(
    "recorded",
    [
        # the container's package path (the review probe p9)
        "/root/.venv/lib/python3.12/site-packages/environment/incident/bundles/"
        "system_response",
        # a path with no package tail: found by the recorded bundle_sha256
        "/nonexistent/somewhere/else/system_response",
    ],
)
def test_replay_finds_the_installed_system_response_bundle(tmp_path: Path, recorded):
    ep = _shipped_sr_episode(tmp_path)
    assert ep.call("list_documents", {}).ok
    assert ep.call(
        "query_frequency",
        {"start": "2019-08-09T16:52:00+01:00", "end": "2019-08-09T16:53:00+01:00"},
    ).ok
    assert ep.call(
        "interview_witness",
        {"persona_id": "eso-control-engineer", "question": "inertia"},
    ).ok
    _record_container_path(ep.episode_dir, recorded)
    report = replay_episode(ep.episode_dir)
    assert report.ok, report.summary_text()
    assert report.counts() == {"match": 3}


def test_resolve_recorded_bundle_rules(tmp_path: Path):
    from environment.incident.catalogue import Catalogue
    from environment.incident.paths import (
        DEFAULT_BUNDLE_DIR,
        SYSTEM_RESPONSE_BUNDLE_DIR,
    )
    from environment.incident.replay import resolve_recorded_bundle

    sr_sha = Catalogue.load(SYSTEM_RESPONSE_BUNDLE_DIR).bundle_sha256
    mvp_sha = Catalogue.load(DEFAULT_BUNDLE_DIR).bundle_sha256
    container = "/root/.venv/lib/python3.12/site-packages/environment/incident"
    assert resolve_recorded_bundle(str(tmp_path), None) == tmp_path  # exists here
    assert (
        resolve_recorded_bundle(f"{container}/bundles/system_response", sr_sha)
        == SYSTEM_RESPONSE_BUNDLE_DIR
    )
    assert resolve_recorded_bundle(f"{container}/bundle", mvp_sha) == DEFAULT_BUNDLE_DIR
    assert resolve_recorded_bundle("/elsewhere/x", sr_sha) == SYSTEM_RESPONSE_BUNDLE_DIR
    # a mapped path whose hash differs is not taken; the hash decides
    assert (
        resolve_recorded_bundle(f"{container}/bundle", sr_sha)
        == SYSTEM_RESPONSE_BUNDLE_DIR
    )
    # nothing matches: the MVP default (the replay then reports the bundle difference)
    assert resolve_recorded_bundle("/elsewhere/x", "0" * 64) == DEFAULT_BUNDLE_DIR
