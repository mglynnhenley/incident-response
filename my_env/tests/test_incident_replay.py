"""Replay: byte-equivalent deterministic calls, recorded Python, tamper detection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from incident_helpers import make_bundle, make_config, rehash, valid_submission

from environment.incident.episode import Episode, read_trace
from environment.incident.replay import replay_episode


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    return make_bundle(tmp_path / "src")


def run_reference_episode(config) -> Episode:
    ep = Episode(config)
    ep.reset()
    ep.list_documents()
    ep.list_documents(category="generator_records")
    ep.request_document("R01")
    ep.request_document("R03")
    ep.request_document("R02")  # UNKNOWN_ID
    ep.run_python(
        "import os, pandas as pd\n"
        "df = pd.read_csv(os.path.join(os.environ['EVIDENCE_DIR'], 'R01', 'series.csv'))\n"
        "print(df['frequency_hz'].min())\n"
    )
    ep.submit_findings(valid_submission(variant_id="wrong"))  # VALIDATION_FAILED
    ep.submit_findings(valid_submission())
    ep.request_document("S01")  # EPISODE_CLOSED
    return ep


def test_replay_reproduces_every_deterministic_call(tmp_path: Path, bundle: Path):
    pytest.importorskip("pandas")
    ep = run_reference_episode(make_config(tmp_path, bundle))
    report = replay_episode(ep.episode_dir, bundle_dir=bundle)
    assert report.ok, report.summary_text()
    statuses = [item.status for item in report.items]
    assert statuses == ["match"] * 5 + ["recorded"] + ["match"] * 3
    assert all(item.integrity_ok for item in report.items)
    assert all(i.recorded_sha256 == i.replayed_sha256 for i in report.items)
    assert report.replayed_state["frozen"] is True
    assert report.replayed_state["calls_used"] == 8
    assert "replay OK" in report.summary_text()


def test_replay_can_rerun_python(tmp_path: Path, bundle: Path):
    ep = Episode(make_config(tmp_path, bundle))
    ep.reset()
    ep.request_document("R01")
    ep.run_python("print(sum(range(10)))")
    report = replay_episode(ep.episode_dir, bundle_dir=bundle, rerun_python=True)
    assert report.ok, report.summary_text()
    assert [i.status for i in report.items] == ["match", "rerun_match"]


def test_replay_preserves_budget_refusals(tmp_path: Path, bundle: Path):
    ep = Episode(make_config(tmp_path, bundle, max_tool_calls=2))
    ep.reset()
    ep.list_documents()
    ep.run_python("print('x')")
    ep.request_document("R01")  # BUDGET_EXCEEDED
    report = replay_episode(ep.episode_dir, bundle_dir=bundle)
    assert report.ok, report.summary_text()
    assert [i.outcome_code for i in report.items] == ["OK", "OK", "BUDGET_EXCEEDED"]
    assert report.replayed_state["budget_exhausted"] is True


def test_replay_reproduces_preflight_failures(tmp_path: Path, bundle: Path):
    config = make_config(tmp_path, bundle)
    Episode(config).reset()
    Episode(config).list_documents()
    good = (bundle / "S01" / "S01.txt").read_text()
    (bundle / "S01" / "S01.txt").write_text("tampered\n")
    assert Episode(config).list_documents().error_code == "INTERNAL_ERROR"
    (bundle / "S01" / "S01.txt").write_text(good)
    Episode(config).request_document("R03")
    report = replay_episode(config.episode_dir, bundle_dir=bundle)
    assert report.ok, report.summary_text()
    assert [i.outcome_code for i in report.items] == ["OK", "INTERNAL_ERROR", "OK"]


def test_tampered_trace_is_detected(tmp_path: Path, bundle: Path):
    ep = Episode(make_config(tmp_path, bundle))
    ep.reset()
    ep.request_document("R03")
    ep.list_documents()
    records = read_trace(ep.episode_dir)
    records[0]["envelope"]["data"]["content"] = "rewritten history\n"
    ep.trace_path.write_text("".join(json.dumps(r) + "\n" for r in records))
    report = replay_episode(ep.episode_dir, bundle_dir=bundle)
    assert not report.ok
    assert report.items[0].integrity_ok is False
    assert (
        report.items[0].status == "match"
    )  # the replayed text equals the original hash
    assert "integrity check failed" in report.summary_text()


def test_changed_bundle_is_detected(tmp_path: Path, bundle: Path):
    ep = Episode(make_config(tmp_path, bundle))
    ep.reset()
    ep.list_documents()
    ep.request_document("S04")
    other = make_bundle(tmp_path / "other")
    path = other / "S04" / "S04.txt"
    path.write_text(path.read_text().replace("placeholder", "different"))
    rehash(other)
    report = replay_episode(ep.episode_dir, bundle_dir=other)
    assert not report.ok
    assert [i.status for i in report.items] == ["match", "mismatch"]
    assert any("bundle differs" in p for p in report.problems)


def test_state_and_submission_tampering_is_detected(tmp_path: Path, bundle: Path):
    ep = Episode(make_config(tmp_path, bundle))
    ep.reset()
    ep.submit_findings(valid_submission())
    assert replay_episode(ep.episode_dir, bundle_dir=bundle).ok
    state = json.loads(ep.state_path.read_text())
    state["calls_used"] = 7
    ep.state_path.write_text(json.dumps(state))
    report = replay_episode(ep.episode_dir, bundle_dir=bundle)
    assert any("state.calls_used" in p for p in report.problems) and not report.ok
    state["calls_used"] = 1
    ep.state_path.write_text(json.dumps(state))
    ep.submission_path.write_text("{}")
    report = replay_episode(ep.episode_dir, bundle_dir=bundle)
    assert not report.ok
    assert any("submission" in p for p in report.problems)


def test_replay_uses_recorded_configuration(tmp_path: Path, bundle: Path):
    ep = Episode(make_config(tmp_path, bundle, max_tool_calls=7, list_page_size=2))
    ep.reset()
    ep.list_documents()
    report = replay_episode(ep.episode_dir, bundle_dir=bundle)
    assert report.ok, report.summary_text()


def test_python_handler_crash_is_replayed_from_the_recording(
    tmp_path: Path, bundle: Path, monkeypatch
):
    ep = Episode(make_config(tmp_path, bundle))
    ep.reset()

    def broken_runner(self):
        raise RuntimeError("runner exploded")

    monkeypatch.setattr(Episode, "python_runner", broken_runner)
    crashed = ep.run_python("print('side effect')")
    assert crashed.error_code == "INTERNAL_ERROR" and crashed.counted
    assert crashed.record["deterministic"] is False
    monkeypatch.undo()
    report = replay_episode(ep.episode_dir, bundle_dir=bundle)
    assert report.ok, report.summary_text()
    assert [i.status for i in report.items] == ["recorded"]
