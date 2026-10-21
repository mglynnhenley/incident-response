"""Episode ledger: envelopes, budget, freeze, repair, materialisation, safety, trace."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import threading
from pathlib import Path

import pytest
from incident_helpers import DOCS, make_bundle, make_config, valid_submission

from environment.incident.catalogue import CATEGORIES
from environment.incident.episode import (
    MAX_ARGUMENT_DEPTH,
    Episode,
    EpisodeState,
    HandlerOutcome,
    build_transcript_summary,
    read_state,
    read_trace,
    render,
    sha256_text,
)
from environment.incident.replay import replay_episode


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    return make_bundle(tmp_path / "src")


@pytest.fixture
def episode(tmp_path: Path, bundle: Path) -> Episode:
    ep = Episode(make_config(tmp_path, bundle))
    ep.reset()
    return ep


def test_reset_creates_fresh_state(tmp_path: Path, bundle: Path):
    config = make_config(tmp_path, bundle)
    config.scratch_dir.mkdir(parents=True)
    (config.scratch_dir / "leftover.txt").write_text("old")
    ep = Episode(config)
    meta = ep.reset()
    assert meta["bundle_id"] == "synthetic-test-bundle"
    assert meta["documents"] == sorted(DOCS)
    assert meta["budgets"]["max_tool_calls"] == 50
    assert len(meta["bundle_sha256"]) == 64
    assert not (config.scratch_dir / "leftover.txt").exists()
    assert config.evidence_dir.is_dir() and os.listdir(config.evidence_dir) == []
    state = json.loads((config.episode_dir / "state.json").read_text())
    assert state == {
        "schema": 1,
        "bundle_version": "1.0.0-test",
        "calls_used": 0,
        "seq": 0,
        "retrieved": [],
        "frozen": False,
        "frozen_at_request_id": None,
        "submission_sha256": None,
        "budget_exhausted": False,
        "invalid_submission_attempts": 0,
        "python_calls": 0,
        "cleanup_failures": 0,
    }
    assert (config.episode_dir / "trace.jsonl").read_text() == ""
    snapshot = json.loads((config.episode_dir / "episode_config.json").read_text())
    assert snapshot["bundle_sha256"] == meta["bundle_sha256"]
    assert snapshot["config"]["max_tool_calls"] == 50
    assert snapshot["isolated"] is False and snapshot["network_mode"] == "not_isolated"
    assert meta["network_mode"] == "not_isolated"
    assert stat.S_IMODE(os.stat(config.episode_dir).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(config.scratch_dir).st_mode) == 0o700


def test_list_documents_envelope(episode: Episode):
    result = episode.list_documents()
    env = result.envelope
    assert (
        env["ok"] and env["request_id"] == "req-001" and env["tool"] == "list_documents"
    )
    assert (
        env["error"] is None
        and env["next_cursor"] is None
        and env["evidence_ids"] == []
    )
    assert env["budget"] == {
        "tool_calls_used": 1,
        "tool_calls_limit": 50,
        "tool_calls_remaining": 49,
    }
    assert [d["doc_id"] for d in env["data"]["documents"]] == sorted(DOCS)
    assert set(env["data"]["documents"][0]) == {
        "doc_id",
        "title",
        "owner",
        "date",
        "category",
    }
    assert env["data"]["categories"] == list(CATEGORIES)
    assert result.text == render(env)
    assert result.text_sha256 == sha256_text(result.text)
    assert "recorded_at" not in result.text


def test_list_documents_filters_and_errors(episode: Episode):
    result = episode.list_documents(category="generator_records")
    assert [d["doc_id"] for d in result.envelope["data"]["documents"]] == ["S01", "S03"]
    # blank optional arguments mean "not given"
    assert len(episode.list_documents(category="  ").envelope["data"]["documents"]) == 5
    bad = episode.list_documents(category="rail")
    assert bad.error_code == "INVALID_ARGUMENT" and bad.counted
    assert "measurement_data" in bad.envelope["error"]["message"]
    assert bad.envelope["error"]["details"][0]["valid"] == list(CATEGORIES)
    assert episode.list_documents(cursor="garbage").error_code == "INVALID_ARGUMENT"
    assert (
        episode.call("list_documents", {"category": 3}).error_code == "INVALID_ARGUMENT"
    )
    assert episode.call("list_documents", {"page": 2}).error_code == "INVALID_ARGUMENT"
    assert episode.state().calls_used == 6


def test_pagination_through_the_ledger(tmp_path: Path, bundle: Path):
    ep = Episode(make_config(tmp_path, bundle, list_page_size=2))
    ep.reset()
    ids, cursor = [], None
    while True:
        env = ep.list_documents(cursor=cursor).envelope
        assert env["ok"]
        ids.extend(d["doc_id"] for d in env["data"]["documents"])
        cursor = env["next_cursor"]
        if cursor is None:
            break
    assert ids == sorted(DOCS)
    wrong = ep.list_documents(
        category="generator_records", cursor=ep.list_documents().envelope["next_cursor"]
    )
    assert wrong.error_code == "INVALID_ARGUMENT"


def test_request_document_returns_numbered_text_and_materialises(episode: Episode):
    result = episode.request_document(" R03 ")
    env = result.envelope
    assert env["ok"] and env["evidence_ids"] == ["R03"]
    data = env["data"]
    assert data["doc_id"] == "R03" and data["line_count"] == DOCS["R03"][2]
    assert data["text_file"] == "R03/R03.txt"
    assert data["artifacts"][0]["path"] == "R03/R03.txt"
    assert "L12" in data["citation_help"] and "EVIDENCE_DIR" in data["citation_help"]
    assert data["content"].startswith("DOCUMENT R03")
    # the model sees a compact header without the content, then numbered lines
    header, body = result.text.split("\n\n", 1)
    assert "content" not in json.loads(header)["data"]
    assert "   1 | DOCUMENT R03 - Synthetic network record" in body
    assert body.splitlines()[-1] == "  30 | R03 placeholder line 30"
    copy = episode.config.evidence_dir / "R03" / "R03.txt"
    assert copy.read_text() == data["content"]
    assert stat.S_IMODE(os.stat(copy).st_mode) == 0o444
    assert episode.state().retrieved == ["R03"]


def test_request_document_with_time_series(episode: Episode):
    env = episode.request_document("R01").envelope
    csv_artifact = env["data"]["artifacts"][1]
    assert csv_artifact["path"] == "R01/series.csv"
    assert csv_artifact["timeseries"]["rows"] == 20
    assert "time:<ISO-8601" in env["data"]["citation_help"]
    csv = episode.config.evidence_dir / "R01" / "series.csv"
    assert hashlib.sha256(csv.read_bytes()).hexdigest() == csv_artifact["sha256"]


def test_request_document_errors(episode: Episode):
    unknown = episode.request_document("R02")
    assert unknown.error_code == "UNKNOWN_ID" and unknown.counted
    assert "R01, R03, S01, S03, S04" in unknown.envelope["error"]["message"]
    assert episode.request_document("r03").error_code == "UNKNOWN_ID"  # exact IDs only
    assert episode.request_document("../R03").error_code == "UNKNOWN_ID"
    assert episode.request_document().error_code == "INVALID_ARGUMENT"
    assert episode.request_document("").error_code == "INVALID_ARGUMENT"
    assert episode.state().calls_used == 5 and episode.state().retrieved == []


def test_materialisation_is_idempotent_and_self_repairing(episode: Episode):
    first = episode.request_document("S01")
    target = episode.config.evidence_dir / "S01" / "S01.txt"
    inode = os.stat(target).st_ino
    second = episode.request_document("S01")
    assert os.stat(target).st_ino == inode  # untouched
    assert first.envelope["data"] == second.envelope["data"]
    # tamper with the copy (as the owner could locally) -> replaced on next request
    os.chmod(target, 0o644)
    target.write_text("tampered")
    episode.request_document("S01")
    assert target.read_text().startswith("DOCUMENT S01")
    # a symlink planted in place of the document directory is replaced, not followed
    outside = episode.config.evidence_dir.parent / "outside"
    outside.mkdir()
    victim = outside / "S01.txt"
    victim.write_text("keep")
    doc_dir = episode.config.evidence_dir / "S01"
    for p in doc_dir.iterdir():
        p.unlink()
    doc_dir.rmdir()
    os.symlink(outside, doc_dir)
    episode.request_document("S01")
    assert not os.path.islink(doc_dir) and victim.read_text() == "keep"
    assert episode.state().retrieved == ["S01"]
    leftovers = [
        n for n in os.listdir(episode.config.evidence_dir) if n.startswith(".")
    ]
    assert leftovers == []


def test_budget_boundary_at_fifty(episode: Episode):
    for i in range(1, 51):
        result = episode.list_documents()
        assert result.ok and result.counted
        assert result.envelope["budget"]["tool_calls_used"] == i
    assert episode.state().budget_exhausted is False
    over = episode.list_documents()
    assert over.error_code == "BUDGET_EXCEEDED" and not over.counted
    assert over.envelope["request_id"] == "req-051"
    assert over.envelope["budget"] == {
        "tool_calls_used": 50,
        "tool_calls_limit": 50,
        "tool_calls_remaining": 0,
    }
    state = episode.state()
    assert state.calls_used == 50 and state.seq == 51 and state.budget_exhausted
    # every tool is refused, including submission
    assert episode.submit_findings(valid_submission()).error_code == "BUDGET_EXCEEDED"
    assert not episode.state().frozen


def test_invalid_calls_count_against_the_budget(tmp_path: Path, bundle: Path):
    ep = Episode(make_config(tmp_path, bundle, max_tool_calls=3))
    ep.reset()
    assert ep.request_document("nope").counted
    assert ep.run_python("").counted
    assert ep.submit_findings({"bad": True}).counted
    final = ep.request_document("R03")
    assert final.error_code == "BUDGET_EXCEEDED" and not final.counted
    assert ep.state().calls_used == 3


def test_freeze_and_episode_closed(episode: Episode):
    episode.request_document("R03")
    result = episode.submit_findings(valid_submission())
    env = result.envelope
    assert env["ok"] and env["data"]["status"] == "accepted_and_frozen"
    assert env["data"]["findings_count"] == 2
    assert "end your turn" in env["data"]["message"]
    assert env["evidence_ids"] == ["R01", "R03"]
    state = episode.state()
    assert state.frozen and state.frozen_at_request_id == "req-002"
    saved = episode.submission_path.read_text(encoding="utf-8")
    assert saved == json.dumps(
        valid_submission(), sort_keys=True, indent=2, ensure_ascii=False
    )
    assert hashlib.sha256(saved.encode()).hexdigest() == state.submission_sha256
    assert env["data"]["submission_sha256"] == state.submission_sha256
    for call in (
        lambda: episode.list_documents(),
        lambda: episode.request_document("R01"),
        lambda: episode.run_python("print(1)"),
        lambda: episode.submit_findings(valid_submission()),
    ):
        closed = call()
        assert closed.error_code == "EPISODE_CLOSED" and not closed.counted
        assert "req-002" in closed.envelope["error"]["message"]
    state = episode.state()
    assert state.calls_used == 2 and state.seq == 6 and state.python_calls == 0
    assert episode.submission_path.read_text(encoding="utf-8") == saved


def test_invalid_submission_can_be_repaired(episode: Episode):
    bad = valid_submission(variant_id="other")
    bad["findings"][0]["citations"][0]["locator"] = "L99"
    rejected = episode.submit_findings(bad)
    assert rejected.error_code == "VALIDATION_FAILED" and rejected.counted
    details = rejected.envelope["error"]["details"]
    assert {d["path"] for d in details} == {
        "variant_id",
        "findings[0].citations[0].locator",
    }
    assert "(49 tool calls remain)" in rejected.envelope["error"]["message"]
    assert not episode.submission_path.exists()
    missing = episode.submit_findings()
    assert missing.error_code == "INVALID_ARGUMENT"
    accepted = episode.submit_findings(json.dumps(valid_submission()))
    assert accepted.ok
    state = episode.state()
    assert (
        state.frozen
        and state.invalid_submission_attempts == 2
        and state.calls_used == 3
    )


def test_trace_records(episode: Episode):
    episode.list_documents()
    episode.request_document("nope")
    episode.run_python("print('traced')")
    records = read_trace(episode.episode_dir)
    assert [r["seq"] for r in records] == [1, 2, 3]
    assert [r["outcome_code"] for r in records] == ["OK", "UNKNOWN_ID", "OK"]
    assert [r["deterministic"] for r in records] == [True, True, False]
    for record in records:
        assert set(record) >= {
            "seq",
            "request_id",
            "tool",
            "args",
            "args_sha256",
            "counted",
            "outcome_code",
            "envelope",
            "rendered_text_sha256",
            "deterministic",
        }
        assert record["rendered_text_sha256"] == sha256_text(render(record["envelope"]))
    assert records[0]["args"] == {}  # None arguments are dropped
    assert records[1]["args"] == {"doc_id": "nope"}
    py = records[2]["python"]
    assert py["code"] == "print('traced')"
    assert py["code_sha256"] == sha256_text("print('traced')")
    assert py["stdout"] == "traced\n" and py["exit_code"] == 0
    assert isinstance(py["duration_s"], float)
    assert episode.state().python_calls == 1


def test_run_python_through_the_ledger(episode: Episode):
    episode.request_document("R01")
    result = episode.run_python(
        "import os\nprint(sorted(os.listdir(os.environ['EVIDENCE_DIR'])))\n"
        "open('note.txt','w').write('n')\n"
    )
    env = result.envelope
    assert env["ok"] and env["data"]["exit_code"] == 0
    assert env["data"]["stdout"] == "['R01']\n"
    assert env["data"]["files"][0]["path"] == "note.txt"
    assert "--- stdout ---\n['R01']\n--- stderr ---\n(empty)" in result.text
    header = json.loads(result.text.split("\n\n", 1)[0])
    assert "stdout" not in header["data"] and "limits" in header["data"]
    failing = episode.run_python("raise SystemExit(2)")
    assert (
        failing.error_code == "PYTHON_ERROR"
        and failing.envelope["data"]["exit_code"] == 2
    )
    too_long = Episode(episode.config.model_copy(update={"max_code_chars": 5}))
    assert too_long.run_python("print(12345)").error_code == "INVALID_ARGUMENT"


def test_rendering_is_deterministic_across_episodes(tmp_path: Path, bundle: Path):
    texts = []
    for name in ("a", "b"):
        ep = Episode(make_config(tmp_path / name, bundle))
        ep.reset()
        texts.append(
            [
                ep.list_documents().text,
                ep.request_document("R01").text,
                ep.request_document("missing").text,
                ep.submit_findings({"schema_version": "3.0"}).text,
                ep.submit_findings(valid_submission()).text,
                ep.list_documents().text,
            ]
        )
    assert texts[0] == texts[1]


def test_unsafe_directories_are_repaired_before_any_handler(
    episode: Episode, tmp_path: Path
):
    scratch = episode.config.scratch_dir
    target = tmp_path / "target_dir"
    target.mkdir()
    (target / "keep.txt").write_text("keep")
    os.rmdir(scratch)
    os.symlink(target, scratch)
    result = episode.run_python("open('x.txt','w').write('x')")
    assert result.ok
    assert scratch.is_dir() and not scratch.is_symlink()
    assert (scratch / "x.txt").exists()
    assert sorted(os.listdir(target)) == ["keep.txt"]
    # evidence dir replaced by a file
    evidence = episode.config.evidence_dir
    os.rmdir(evidence)
    evidence.write_text("not a directory")
    assert episode.request_document("S04").ok
    assert evidence.is_dir() and (evidence / "S04" / "S04.txt").exists()


def test_tampered_bundle_fails_closed_and_is_not_counted(tmp_path: Path, bundle: Path):
    config = make_config(tmp_path, bundle)
    Episode(config).reset()
    (bundle / "S01" / "S01.txt").write_text("tampered\n")
    fresh = Episode(config)
    result = fresh.list_documents()
    assert result.error_code == "INTERNAL_ERROR" and not result.counted
    assert "integrity" in result.envelope["error"]["message"]
    assert fresh.state().calls_used == 0 and fresh.state().seq == 1


def test_tamper_after_load_is_detected_at_materialisation(episode: Episode):
    episode.list_documents()  # catalogue loaded and verified
    (episode.config.bundle_dir / "S03" / "S03.txt").write_text("changed\n")
    result = episode.request_document("S03")
    assert result.error_code == "INTERNAL_ERROR" and result.counted
    assert not (episode.config.evidence_dir / "S03").exists()


def test_state_is_shared_between_episode_instances(tmp_path: Path, bundle: Path):
    config = make_config(tmp_path, bundle)
    a, b = Episode(config), Episode(config)
    a.reset()
    a.list_documents()
    assert b.request_document("R03").envelope["request_id"] == "req-002"
    assert a.list_documents().envelope["budget"]["tool_calls_used"] == 3
    assert read_state(config.episode_dir).retrieved == ["R03"]


def test_episode_starts_without_explicit_reset(tmp_path: Path, bundle: Path):
    ep = Episode(make_config(tmp_path, bundle))
    assert ep.list_documents().envelope["request_id"] == "req-001"
    assert (ep.episode_dir / "episode_config.json").exists()


def test_unknown_tool_and_handler_crash(episode: Episode):
    assert episode.call("delete_everything", {}).error_code == "INVALID_ARGUMENT"

    def crash(state, args, request_id):
        raise RuntimeError("bug")

    result = episode.call("list_documents", {}, crash)
    assert result.error_code == "INTERNAL_ERROR" and result.counted
    assert "RuntimeError: bug" in result.envelope["error"]["message"]

    def custom(state, args, request_id):
        return HandlerOutcome(ok=True, data={"echo": args, "rid": request_id})

    echoed = episode.call("list_documents", {"x": 1, "y": None}, custom)
    assert echoed.envelope["data"] == {"echo": {"x": 1}, "rid": "req-003"}


def test_concurrent_calls_are_serialised(episode: Episode):
    def worker():
        for _ in range(5):
            episode.list_documents()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    records = read_trace(episode.episode_dir)
    assert [r["seq"] for r in records] == list(range(1, 21))
    assert episode.state().calls_used == 20


# -- arguments and results that cannot be recorded as they are ------------------------
def test_unencodable_arguments_are_counted_invalid_and_traced(episode: Episode):
    results = [
        episode.run_python('open("ran.txt", "w").write("x")  # \ud800'),
        episode.request_document("R0\ud8001"),
        episode.list_documents(category="x\udc80"),
        episode.submit_findings(valid_submission(variant_id="b\ud800")),
    ]
    for result in results:
        assert result.error_code == "INVALID_ARGUMENT" and result.counted
        assert "not valid Unicode" in result.envelope["error"]["message"]
        result.text.encode("utf-8")  # what the model sees always encodes
    assert results[3].envelope["error"]["details"] == [
        {
            "path": "submission.variant_id",
            "message": "contains text that is not valid Unicode (a lone surrogate "
            "code point)",
        }
    ]
    state = episode.state()
    assert state.calls_used == 4 and state.seq == 4
    assert state.python_calls == 0 and state.invalid_submission_attempts == 1
    assert not (episode.config.scratch_dir / "ran.txt").exists()  # never executed
    records = read_trace(episode.episode_dir)
    assert len(records) == 4
    # the trace keeps the exact arguments (ASCII-escaped JSON round-trips them)
    assert records[1]["args"] == {"doc_id": "R0\ud8001"}
    assert records[0]["rendered_text_sha256"] == results[0].text_sha256
    report = replay_episode(episode.episode_dir)
    assert report.ok, report.summary_text()


def test_deeply_nested_arguments_are_rejected(episode: Episode):
    nested: dict = {}
    cursor = nested
    for _ in range(MAX_ARGUMENT_DEPTH + 5):
        cursor["a"] = {}
        cursor = cursor["a"]
    result = episode.submit_findings(nested)
    assert result.error_code == "INVALID_ARGUMENT" and result.counted
    assert "levels deep" in result.envelope["error"]["message"]
    deep = "x"
    for _ in range(5000):
        deep = [deep]
    assert episode.call("list_documents", {"category": deep}).counted
    assert episode.state().calls_used == 2
    assert len(read_trace(episode.episode_dir)) == 2


def test_unencodable_handler_output_is_escaped(episode: Episode):
    name = os.fsdecode(b"g\xff")

    def handler(state, args, request_id):
        return HandlerOutcome(ok=True, data={"files": [{"path": name}]})

    result = episode.call("list_documents", {}, handler)
    assert result.ok and result.envelope["data"]["files"][0]["path"] == "g\\udcff"
    assert read_trace(episode.episode_dir)[0]["envelope"] == result.envelope


def test_unrecordable_result_is_still_counted_and_traced(episode: Episode):
    def handler(state, args, request_id):
        return HandlerOutcome(ok=True, data={"value": object()})

    result = episode.call("list_documents", {}, handler)
    assert result.error_code == "INTERNAL_ERROR" and result.counted
    assert "could not be recorded" in result.envelope["error"]["message"]
    records = read_trace(episode.episode_dir)
    assert len(records) == 1 and records[0]["deterministic"] is False
    assert records[0]["outcome_code"] == "INTERNAL_ERROR"
    assert episode.state().calls_used == 1 and episode.state().seq == 1


# -- run_python isolation reporting ---------------------------------------------------
class _Unreapable(RuntimeError):
    pass


def test_cleanup_failure_is_recorded_and_fails_closed(tmp_path: Path, bundle: Path):
    failures = {"left": 2}  # after the first call, and the pre-clean of the second

    def cleanup():
        if failures["left"]:
            failures["left"] -= 1
            raise _Unreapable("processes were still alive")

    config = make_config(tmp_path, bundle)
    ep = Episode(config, cleanup=cleanup)
    ep.reset()
    first = ep.run_python("print('one')")
    assert first.error_code == "INTERNAL_ERROR" and first.counted
    assert first.envelope["data"]["stdout"] == "one\n"
    assert ep.state().cleanup_failures == 1
    record = read_trace(config.episode_dir)[-1]
    assert (
        record["python"]["cleanup_error"] == "_Unreapable: processes were still alive"
    )
    refused = ep.run_python("open('second.txt', 'w').write('x')")
    assert refused.error_code == "INTERNAL_ERROR"
    assert "was not run" in refused.envelope["error"]["message"]
    assert not (config.scratch_dir / "second.txt").exists()
    third = ep.run_python("print('three')")  # leftovers stopped: runs again
    assert third.ok and third.envelope["data"]["stdout"] == "three\n"
    state = ep.state()
    assert state.cleanup_failures == 2 and state.python_calls == 3
    summary = build_transcript_summary(config.episode_dir, None)
    assert summary["isolation"]["python_cleanup_failures"] == 2
    report = replay_episode(config.episode_dir)
    assert report.ok, report.summary_text()


def test_network_mode_is_reported_everywhere(tmp_path: Path, bundle: Path):
    config = make_config(tmp_path, bundle)
    ep = Episode(config, isolated=True, network_mode=lambda: "karotte_firewall")
    meta = ep.reset()
    assert meta["network_mode"] == "karotte_firewall" and meta["isolated"] is True
    snapshot = json.loads((config.episode_dir / "episode_config.json").read_text())
    assert snapshot["network_mode"] == "karotte_firewall"
    limits = ep.run_python("print(1)").envelope["data"]["limits"]
    assert limits["network"] == "karotte_firewall"
    assert "without network access" not in limits["isolation"]
    summary = build_transcript_summary(config.episode_dir, [])
    assert summary["isolation"] == {
        "isolated": True,
        "network_mode": "karotte_firewall",
        "python_cleanup_failures": 0,
    }


def test_old_state_files_without_cleanup_failures_still_load():
    raw = EpisodeState(bundle_version="v").to_dict()
    del raw["cleanup_failures"]
    assert EpisodeState.from_dict(raw).cleanup_failures == 0


def test_wrong_typed_code_is_invalid_not_missing(episode: Episode):
    result = episode.call("run_python", {"code": ["print(1)"]})
    assert result.error_code == "INVALID_ARGUMENT" and result.counted
    assert (
        result.envelope["error"]["message"] == "code must be a string of Python source"
    )
