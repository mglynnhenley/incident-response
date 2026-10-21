"""The judge on real system-response episodes and through the command line
(``python -m environment.incident.judge``), with a mocked client: transcript
discovery, the merged grade, dry runs, cache-only re-runs, refusals and exit codes."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from incident_helpers import transcript_for
from sr_grading_support import episode_config, row, run_calls
from sr_judge_support import (
    RUN_MODEL,
    FakeJudge,
    config,
    default_response,
    small_submission,
)

from environment.incident import sr_grading
from environment.incident.judge import __main__ as cli
from environment.incident.judge import runner
from environment.incident.judge.runner import (
    find_transcript,
    judge_episode,
    load_transcript,
)

RUN_ID = "gb2019-sr-test-001"


def _episode(tmp_path: Path, submit: bool = True) -> Path:
    """A run saved as ``karotte run`` saves it: ``<out>/<run>_artifacts/episode`` and
    ``<out>/transcript.json``."""
    cfg = episode_config(tmp_path / "live")
    calls = [("request_document", {"doc_id": "S01"})]
    if submit:
        calls.append(("submit_findings", {"submission": small_submission()}))
    results = run_calls(cfg, calls)
    out = tmp_path / "out"
    episode = out / f"{RUN_ID}_artifacts" / "episode"
    shutil.copytree(cfg.episode_dir, episode)
    events = [
        e.model_dump(mode="json")
        for e in transcript_for([(t, a, r) for t, a, r in results]).events
    ]
    events.insert(
        0,
        {"type": "task_started", "run_id": RUN_ID, "model": RUN_MODEL, "n_steps": 1},
    )
    (out / "transcript.json").write_text(
        json.dumps({"run_id": RUN_ID, "events": events}), encoding="utf-8"
    )
    return episode


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test here may reach OpenRouter, whatever the environment holds."""

    def refuse(*args, **kwargs):
        raise AssertionError("network access in a test")

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    # setenv first so that teardown restores the original state even when a test
    # sets the variable itself (as --env-file does)
    monkeypatch.setenv("OPENROUTER_API_KEY", "unset")
    monkeypatch.delenv("OPENROUTER_API_KEY")


@pytest.fixture
def episode(tmp_path: Path) -> Path:
    return _episode(tmp_path)


@pytest.fixture
def fake(monkeypatch) -> FakeJudge:
    judge = FakeJudge()
    monkeypatch.setattr(runner, "_default_client_factory", lambda cfg: lambda: judge)
    return judge


def test_transcript_discovery(episode: Path, tmp_path: Path):
    path = find_transcript(episode)
    assert path == tmp_path / "out" / "transcript.json"
    events, model = load_transcript(path)
    assert model == RUN_MODEL and events
    # a transcript of another run is not used
    data = json.loads(path.read_text())
    data["run_id"] = "another-run"
    path.write_text(json.dumps(data))
    assert find_transcript(episode) is None


def test_judge_episode_writes_the_merged_grade(episode: Path):
    fake = FakeJudge()
    result = judge_episode(episode, config=config(), client=fake)
    assert result.status == "judged"
    out = episode / "judge"
    assert set(result.files) == {"judge_output", "judge_run", "grade"}
    assert (out / "judge_output.json").is_file() and (out / "cache").is_dir()
    grade = json.loads((out / "grade.json").read_text())
    assert grade["grade_schema"] == sr_grading.GRADE_SCHEMA
    assert grade["run"]["outcome"] == "complete"
    assert grade["run"]["transcript_available"] is True
    assert grade["judge"]["judge_model"] == "openai/gpt-6.1-sol"
    assert row(grade, "T06.01")["content"]["source"] == "judge"
    assert grade["status"] == "provisional"
    # the citations not obtained during the episode are marked for the judge
    user = fake.calls[0].user
    assert 'note="not obtained during the episode"' in user
    # nothing about the run reaches the judge
    sent = json.dumps([c.payload for c in fake.calls])
    for secret in (RUN_ID, str(episode), "claude", "anthropic", "opus"):
        assert secret.lower() not in sent.lower(), secret
    log = json.loads((out / "judge_run.json").read_text())
    assert log["status"] == "judged" and log["api_calls"] == len(fake.calls)
    assert log["transcript"].endswith("transcript.json")


def test_incomplete_runs_are_not_judged(tmp_path: Path):
    episode = _episode(tmp_path, submit=False)
    result = judge_episode(episode, config=config(), client=FakeJudge())
    assert result.status == "not_judged" and result.judge_output is None
    assert "nothing to judge" in result.run_log["reason"]
    assert not (episode / "judge").exists()


def test_cli_run_dry_run_cache_only_and_merge(episode: Path, fake, capsys):
    assert cli.main(["run", str(episode), "--dry-run"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["dry_run"] is True and fake.calls == []
    assert plan["requests_to_send"] == len(plan["units"]) > 0
    assert plan["approx_cost_usd"]["input"] > 0
    assert plan["family_check"]["run_model_family"] == "anthropic"
    assert not (episode / "judge" / "judge_output.json").exists()

    assert cli.main(["run", str(episode)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "judged" and summary["api_calls"] == len(fake.calls)
    assert summary["cost_this_run"]["cost_usd"] > 0
    first = (episode / "judge" / "judge_output.json").read_bytes()

    calls = len(fake.calls)
    assert cli.main(["run", str(episode), "--cache-only"]) == 0
    again = json.loads(capsys.readouterr().out)
    assert len(fake.calls) == calls and again["api_calls"] == 0
    assert again["cache_hits"] == len(plan["units"])
    assert (episode / "judge" / "judge_output.json").read_bytes() == first

    assert cli.main(["run", str(episode), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["requests_to_send"] == 0

    out = episode.parent / "remerged.json"
    assert (
        cli.main(
            [
                "merge",
                str(episode),
                "--judge-output",
                str(episode / "judge" / "judge_output.json"),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    capsys.readouterr()
    merged = json.loads(out.read_text())
    stored = json.loads((episode / "judge" / "grade.json").read_text())
    assert merged["criteria"] == stored["criteria"]


def test_cli_refuses_a_same_family_judge(episode: Path, fake, capsys):
    code = cli.main(
        ["run", str(episode), "--judge-model", "anthropic/claude-sonnet-5.5"]
    )
    assert code == 2
    assert "refused" in capsys.readouterr().err
    assert fake.calls == []
    code = cli.main(
        [
            "run",
            str(episode),
            "--judge-model",
            "anthropic/claude-sonnet-5.5",
            "--allow-same-family",
        ]
    )
    assert code == 0
    jo = json.loads((episode / "judge" / "judge_output.json").read_text())
    assert jo["family_check"]["allow_same_family"] is True
    assert jo["judge_model"] == "anthropic/claude-sonnet-5.5"


def test_cli_needs_the_evaluated_model(tmp_path: Path, fake, capsys):
    sub = tmp_path / "submission.json"
    sub.write_text(json.dumps(small_submission()))
    assert cli.main(["run", str(sub), "--out-dir", str(tmp_path / "j")]) == 2
    assert "evaluated model is unknown" in capsys.readouterr().err
    code = cli.main(
        ["run", str(sub), "--out-dir", str(tmp_path / "j"), "--run-model", RUN_MODEL]
    )
    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "judged"
    grade = json.loads((tmp_path / "j" / "grade.json").read_text())
    assert any("no episode trace" in r for r in grade["provisional_reasons"])
    assert cli.main(["run", str(sub), "--run-model", RUN_MODEL]) == 1
    assert "--out-dir is required" in capsys.readouterr().err


def test_cli_partial_run_exit_code(episode: Path, monkeypatch, capsys):
    judge = FakeJudge(
        lambda req: "nope" if req.unit_id == "T07" else default_response(req)
    )
    monkeypatch.setattr(runner, "_default_client_factory", lambda cfg: lambda: judge)
    assert cli.main(["run", str(episode)]) == 3
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "partial" and summary["failed_units"] == ["T07"]


def test_cli_missing_api_key_fails_units_cleanly(episode: Path, capsys):
    assert cli.main(["run", str(episode)]) == 3
    summary = json.loads(capsys.readouterr().out)
    assert set(summary["errors"].values()) == {
        "OPENROUTER_API_KEY is not set: the judge needs an OpenRouter API key in the "
        "environment"
    }


def test_cli_env_file_sets_only_the_key(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OTHER_SECRET", "unset")
    monkeypatch.delenv("OTHER_SECRET")
    env = tmp_path / ".env"
    env.write_text("# keys\nOTHER_SECRET=x\nexport OPENROUTER_API_KEY='sk-or-test'\n")
    cli._load_env_file(str(env))
    assert os.environ["OPENROUTER_API_KEY"] == "sk-or-test"
    assert "OTHER_SECRET" not in os.environ


def test_cli_prompt_shows_what_is_sent(episode: Path, capsys):
    assert cli.main(["prompt", str(episode)]) == 0
    units = json.loads(capsys.readouterr().out)
    assert [u["unit_id"] for u in units][:2] == ["T01", "T02"]
    assert cli.main(["prompt", str(episode), "--unit", "T06"]) == 0
    text = capsys.readouterr().out
    assert text.startswith("===== system =====\n---\nrubric_id: gb2019-sr-judge-rubric")
    assert "Unit T06: Hornsea mechanism" in text
    assert "claude" not in text.lower()
    assert cli.main(["prompt", str(episode), "--unit", "T99"]) == 1
    assert "unknown unit" in capsys.readouterr().err


def test_default_judge_config_is_used(episode: Path, fake):
    result = judge_episode(episode, config=config(max_report_assertions=0))
    assert result.judge_output["config"]["max_report_assertions"] == 0
    assert all('"report_assertions_allowed": 0' in c.user for c in fake.calls)


def test_real_client_end_to_end_never_writes_the_key(
    episode: Path, monkeypatch, capsys
):
    """The default OpenRouter client over a fake transport: the key is only in the
    Authorization header; no output file, log or message contains it."""
    import io
    import urllib.error

    secret = "sk-or-v1-sentinel-do-not-log-42"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    judge = FakeJudge()
    seen = {"auth": set(), "temperature": []}

    class Response(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def transport(request, timeout=None):
        seen["auth"].add(request.get_header("Authorization"))
        if request.get_method() == "GET":
            listing = {
                "data": [
                    {
                        "id": "openai/gpt-6.1-sol",
                        "supported_parameters": ["max_tokens", "response_format"],
                    }
                ]
            }
            return Response(json.dumps(listing).encode())
        payload = json.loads(request.data)
        seen["temperature"].append("temperature" in payload)
        reply = judge.complete(payload)
        if payload["messages"][1]["content"].count("Unit T09:"):
            raise urllib.error.HTTPError(
                request.full_url, 401, "no", {}, io.BytesIO(f"bad {secret}".encode())
            )
        body = {
            "id": "gen-x",
            "model": reply.model,
            "choices": [
                {"message": {"content": reply.content}, "finish_reason": "stop"}
            ],
            "usage": reply.usage,
        }
        return Response(json.dumps(body).encode())

    monkeypatch.setattr("urllib.request.urlopen", transport)
    assert cli.main(["run", str(episode)]) == 3  # T09 failed with HTTP 401
    out = capsys.readouterr()
    assert seen["auth"] == {f"Bearer {secret}"}
    assert seen["temperature"] and not any(seen["temperature"])
    assert secret not in out.out + out.err
    assert "[redacted]" in out.out  # the 401 body echoed the key
    for path in (episode / "judge").rglob("*"):
        if path.is_file():
            assert secret not in path.read_text(encoding="utf-8"), path
    jo = json.loads((episode / "judge" / "judge_output.json").read_text())
    assert all(u["temperature_sent"] is False for u in jo["units"] if u["attempts"])
