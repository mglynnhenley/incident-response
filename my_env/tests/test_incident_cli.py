"""CLI: list, inspect, replay, validate, grade and review-template."""

from __future__ import annotations

import io
import json
import sys
import types
from pathlib import Path

import pytest
from incident_helpers import make_bundle, make_config, valid_submission

from environment.incident import cli
from environment.incident.episode import Episode


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    return make_bundle(tmp_path / "src")


@pytest.fixture
def episode(tmp_path: Path, bundle: Path) -> Episode:
    ep = Episode(make_config(tmp_path, bundle))
    ep.reset()
    ep.list_documents()
    ep.request_document("R03")
    ep.submit_findings(valid_submission())
    return ep


def test_list(bundle: Path, capsys):
    assert cli.main(["list", "--bundle", str(bundle)]) == 0
    out = capsys.readouterr().out
    assert "all artifact hashes verified" in out
    assert "R03" in out and "network_records" in out
    assert (
        cli.main(
            [
                "list",
                "--bundle",
                str(bundle),
                "--json",
                "--category",
                "generator_records",
            ]
        )
        == 0
    )
    data = json.loads(capsys.readouterr().out)
    assert [d["doc_id"] for d in data["documents"]] == ["S01", "S03"]


def test_list_fails_closed_on_tampered_bundle(bundle: Path, capsys):
    (bundle / "S01" / "S01.txt").write_text("x\n")
    assert cli.main(["list", "--bundle", str(bundle)]) == 1
    assert "sha256 mismatch" in capsys.readouterr().err


def test_inspect(episode: Episode, capsys):
    assert cli.main(["inspect", str(episode.episode_dir)]) == 0
    out = capsys.readouterr().out
    assert '"frozen": true' in out and "req-002 request_document" in out
    assert cli.main(["inspect", str(episode.episode_dir), "--seq", "2"]) == 0
    shown = capsys.readouterr().out
    assert "   1 | DOCUMENT R03" in shown
    assert cli.main(["inspect", str(episode.episode_dir), "--seq", "99"]) == 1
    assert cli.main(["inspect", str(episode.episode_dir), "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)["trace"]) == 3


def test_replay(episode: Episode, bundle: Path, capsys):
    assert cli.main(["replay", str(episode.episode_dir), "--bundle", str(bundle)]) == 0
    assert "replay OK" in capsys.readouterr().out
    episode.submission_path.write_text("{}")
    assert (
        cli.main(
            ["replay", str(episode.episode_dir), "--bundle", str(bundle), "--json"]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_validate(tmp_path: Path, bundle: Path, capsys, monkeypatch):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(valid_submission()))
    assert cli.main(["validate", str(good), "--bundle", str(bundle)]) == 0
    assert capsys.readouterr().out.startswith("valid: 2 findings")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(valid_submission(schema_version="2.0")))
    assert cli.main(["validate", str(bad), "--bundle", str(bundle)]) == 1
    assert "schema_version: must be '3.0'" in capsys.readouterr().out
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(valid_submission())))
    assert cli.main(["validate", "-", "--bundle", str(bundle), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_grade_without_grading_module(episode: Episode, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_load_grading", lambda: None)
    assert cli.main(["grade", str(episode.episode_dir)]) == 2
    assert "not installed" in capsys.readouterr().err
    assert cli.main(["review-template", str(episode.episode_dir)]) == 2


def test_grade_and_review_template_with_grading_module(
    episode: Episode, tmp_path: Path, monkeypatch, capsys
):
    seen = {}
    fake = types.ModuleType("environment.incident.grading")

    def grade_episode(episode_dir, transcript_summary):
        seen["args"] = (episode_dir, transcript_summary)
        return {"provisional": True, "dimensions": {}}

    fake.grade_episode = grade_episode
    fake.review_template = lambda episode_dir: "# Review\n"
    monkeypatch.setitem(sys.modules, "environment.incident.grading", fake)
    out = tmp_path / "grade.json"
    assert cli.main(["grade", str(episode.episode_dir), "--out", str(out)]) == 0
    assert json.loads(out.read_text()) == {"dimensions": {}, "provisional": True}
    episode_dir, summary = seen["args"]
    assert episode_dir == episode.episode_dir
    assert summary["outcome"] == "complete" and summary["transcript_available"] is False
    capsys.readouterr()
    assert cli.main(["review-template", str(episode.episode_dir)]) == 0
    assert capsys.readouterr().out == "# Review\n\n"


def test_grade_with_transcript(episode: Episode, tmp_path: Path, monkeypatch, capsys):
    fake = types.ModuleType("environment.incident.grading")
    fake.grade_episode = lambda d, s: {"summary": s}
    monkeypatch.setitem(sys.modules, "environment.incident.grading", fake)
    transcript = tmp_path / "t.json"
    transcript.write_text(
        json.dumps(
            {
                "run_id": "x",
                "events": [
                    {"type": "token_usage", "input_tokens": 10, "output_tokens": 5},
                    {
                        "type": "message_added",
                        "message": {"role": "assistant", "content": "done"},
                    },
                ],
            }
        )
    )
    assert (
        cli.main(["grade", str(episode.episode_dir), "--transcript", str(transcript)])
        == 0
    )
    summary = json.loads(capsys.readouterr().out)["summary"]
    assert summary["output_tokens_total"] == 5 and summary["outcome"] == "complete"
