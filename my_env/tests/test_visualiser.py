import hashlib
import importlib.util
import json
import sys
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "viz" / "serve.py"
_spec = importlib.util.spec_from_file_location("visualiser_server", _SCRIPT)
assert _spec and _spec.loader
serve = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = serve
_spec.loader.exec_module(serve)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def write_run(out_dir, folder="live", run_id="test-run"):
    path = out_dir / folder / "transcript.json"
    write_json(
        path,
        {
            "run_id": run_id,
            "events": [
                {
                    "type": "task_started",
                    "model": "fake/agent",
                    "task_id": "incident",
                    "timestamp": "2026-10-20T05:46:10Z",
                },
                {"type": "task_completed"},
            ],
        },
    )
    return path


@pytest.fixture
def local_server(tmp_path):
    servers = []

    def start(*, live=False):
        out_dir = tmp_path / "out"
        out_dir.mkdir(exist_ok=True)
        html_file = tmp_path / "agent_world.html"
        html_file.write_text("<!doctype html><title>Agent world</title>")
        episode_dir = tmp_path / "episode"
        server = serve.make_server(
            0,
            out_dir=out_dir,
            episode_dir=episode_dir if live else None,
            html_file=html_file,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return f"http://127.0.0.1:{server.server_port}", out_dir, episode_dir

    yield start
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def get_json(base, path):
    with urlopen(base + path, timeout=5) as response:
        return json.load(response)


def test_discovers_nested_runs_and_sibling_grade(tmp_path):
    out_dir = tmp_path / "out"
    write_run(out_dir)
    grade = {"flags": {"uncited_findings": ["F02"]}}
    write_json(out_dir / "live" / "test-run_artifacts" / "grade.json", grade)
    write_run(out_dir, "nested/repair", "repair")
    (out_dir / "transcript.json").write_text('{"events":')
    runs = serve.discover_runs(out_dir)
    assert {run["path"] for run in runs} == {
        "live/transcript.json",
        "nested/repair/transcript.json",
    }
    run = next(run for run in runs if run["run_id"] == "test-run")
    assert run["model"] == "fake/agent"
    assert run["task_id"] == "incident"
    assert run["event_count"] == 2
    assert run["grade"] == grade
    assert run["grade_path"] == "live/test-run_artifacts/grade.json"


def test_discovery_does_not_follow_external_transcript_or_grade(tmp_path):
    out_dir = tmp_path / "out"
    transcript = write_run(out_dir)
    external = tmp_path / "external.json"
    external.write_bytes(transcript.read_bytes())
    (out_dir / "transcript.json").symlink_to(external)
    artifacts = out_dir / "live" / "test-run_artifacts"
    artifacts.mkdir()
    (artifacts / "grade.json").symlink_to(external)
    runs = serve.discover_runs(out_dir)
    assert len(runs) == 1
    assert runs[0]["grade"] is None
    assert runs[0]["grade_path"] is None


def test_http_serves_nested_run_and_configuration(local_server):
    base, out_dir, _ = local_server()
    write_run(out_dir)
    assert get_json(base, "/api/config")["mode"] == "replay"
    run = get_json(base, "/api/runs")["runs"][0]
    transcript = get_json(base, "/api/file?" + urlencode({"path": run["path"]}))
    assert transcript["run_id"] == "test-run"
    with urlopen(base, timeout=5) as response:
        assert response.headers["Cache-Control"] == "no-store"
        assert b"Agent world" in response.read()


@pytest.mark.parametrize("kind", ["traversal", "absolute", "file_link", "dir_link"])
def test_http_rejects_files_outside_output(local_server, tmp_path, kind):
    base, out_dir, _ = local_server()
    secret_dir = tmp_path / "private"
    secret_dir.mkdir()
    secret = secret_dir / "secret.json"
    secret.write_text('{"secret": true}')
    if kind == "traversal":
        path = "../private/secret.json"
    elif kind == "absolute":
        path = str(secret)
    elif kind == "file_link":
        (out_dir / "secret.json").symlink_to(secret)
        path = "secret.json"
    else:
        (out_dir / "private").symlink_to(secret_dir, target_is_directory=True)
        path = "private/secret.json"
    with pytest.raises(HTTPError) as error:
        get_json(base, "/api/file?" + urlencode({"path": path}))
    assert error.value.code == 403
    assert b'"secret": true' not in error.value.read()


def test_http_missing_path_and_unknown_route(local_server):
    base, _, _ = local_server()
    for path, status in [
        ("/api/file", 400),
        ("/api/file?path=absent.json", 404),
        ("/api/live", 404),
        ("/state.json", 404),
    ]:
        with pytest.raises(HTTPError) as error:
            get_json(base, path)
        assert error.value.code == status


def test_live_waits_for_trace_and_returns_atomic_state(local_server):
    base, _, episode = local_server(live=True)
    result = get_json(base, "/api/live?offset=0")
    assert result["waiting"]
    assert result["records"] == []
    assert result["offset"] == 0
    assert result["state"] is None
    write_json(episode / "state.json", {"calls_used": 1})
    (episode / "trace.jsonl").touch()
    result = get_json(base, "/api/live?offset=0")
    assert result["state"] == {"calls_used": 1}
    assert get_json(base, "/api/config")["live"] is True


def test_live_tails_complete_lines_with_byte_offsets_and_utf8(local_server):
    base, _, episode = local_server(live=True)
    episode.mkdir()
    first = {"tool": "list_documents", "args": {"category": "Ørsted"}}
    second = {"tool": "request_document", "args": {"doc_id": "R01"}}
    first_bytes = json.dumps(first, ensure_ascii=False).encode("utf-8") + b"\n"
    second_bytes = json.dumps(second).encode() + b"\n"
    trace = episode / "trace.jsonl"
    # Split inside a UTF-8 character; even this incomplete prefix must be retained.
    split = first_bytes.index("Ø".encode()) + 1
    trace.write_bytes(first_bytes[:split])
    initial = get_json(base, "/api/live?offset=0")
    assert initial["offset"] == 0
    assert initial["records"] == []
    with trace.open("ab") as file:
        file.write(first_bytes[split:] + second_bytes[:-1])
    result = get_json(
        base, "/api/live?" + urlencode({"offset": 0, "cursor": initial["cursor"]})
    )
    assert result["records"] == [first]
    assert result["offset"] == len(first_bytes)
    assert result["reset"] is False
    with trace.open("ab") as file:
        file.write(b"\n")
    next_result = get_json(
        base,
        "/api/live?"
        + urlencode({"offset": result["offset"], "cursor": result["cursor"]}),
    )
    assert next_result["records"] == [second]
    assert next_result["offset"] == len(first_bytes + second_bytes)
    assert next_result["reset"] is False
    assert get_json(base, f"/api/live?offset={next_result['offset']}")["records"] == []


@pytest.mark.parametrize("rotation", ["replace", "truncate", "rewrite"])
def test_live_resets_when_trace_is_replaced_or_rewritten(tmp_path, rotation):
    episode = tmp_path / "episode"
    episode.mkdir()
    trace = episode / "trace.jsonl"
    trace.write_bytes(b'{"tool":"old_tool_name"}\n')
    tail = serve.LiveTail(episode)
    previous = tail.read()
    record = {"tool": "new_tool_name"}
    replacement = json.dumps(record, separators=(",", ":")).encode() + b"\n"
    if rotation == "replace":
        new_trace = episode / "new.jsonl"
        new_trace.write_bytes(replacement)
        new_trace.replace(trace)
    elif rotation == "truncate":
        trace.write_bytes(b"{}\n")
        record = {}
    else:
        # Same inode and length: size-only rotation detection would miss this.
        trace.write_bytes(replacement)
    result = tail.read(previous["offset"], previous["cursor"])
    assert result["reset"]
    assert result["records"] == [record]


def test_live_offset_only_handles_rotation_and_missing_file(tmp_path):
    trace = tmp_path / "trace.jsonl"
    trace.write_bytes(b'{"tool":"old"}\n')
    tail = serve.LiveTail(tmp_path)
    previous = tail.read()
    trace.write_bytes(b'{"tool":"new"}\n')
    current = tail.read(previous["offset"])
    assert current["reset"]
    assert current["records"] == [{"tool": "new"}]
    trace.unlink()
    missing = tail.read(current["offset"], current["cursor"])
    assert missing["reset"]
    assert missing["waiting"]
    assert missing["offset"] == 0


def test_live_skips_corrupt_complete_record_without_stalling(tmp_path):
    trace = tmp_path / "trace.jsonl"
    trace.write_bytes(b'broken json\n{"tool":"list_documents"}\n{"tool":')
    result = serve.LiveTail(tmp_path).read()
    assert result["records"] == [{"tool": "list_documents"}]
    assert len(result["errors"]) == 1
    assert result["offset"] == len(b'broken json\n{"tool":"list_documents"}\n')


@pytest.mark.parametrize("offset", ["-1", "oops", ""])
def test_live_rejects_invalid_offsets(local_server, offset):
    base, _, _ = local_server(live=True)
    with pytest.raises(HTTPError) as error:
        get_json(base, "/api/live?" + urlencode({"offset": offset}))
    assert error.value.code == 400


def test_live_offers_only_replay_with_matching_trace(local_server):
    base, out_dir, episode = local_server(live=True)
    write_run(out_dir)
    episode.mkdir()
    live_bytes = b'{"tool":"list_documents"}\n'
    (episode / "trace.jsonl").write_bytes(live_bytes)
    assert get_json(base, "/api/live")["replay"] is None
    archived = out_dir / "live" / "test-run_artifacts" / "episode" / "trace.jsonl"
    archived.parent.mkdir(parents=True)
    archived.write_bytes(b'{"tool":"other_run"}\n')
    assert get_json(base, "/api/live")["replay"] is None
    archived.write_bytes(live_bytes)
    assert get_json(base, "/api/live")["replay"]["run_id"] == "test-run"


def sr_grade(**extra):
    """A system-response grade with the bulky sections the run list must drop."""
    return {
        "grade_schema": "gb2019-sr-grade/1",
        "status": "provisional",
        "provisional_reasons": ["answer key review status is 'pending_domain_review'"],
        "key": {"review_status": "pending_domain_review"},
        "flags": {"accounting_traps": [{"figure_id": "LFDD"}], "uncited_findings": []},
        "citations": [{"finding_id": f"F{i:02d}"} for i in range(300)],
        "criteria": [{"criterion_id": f"T01.{i:02d}"} for i in range(60)],
        "content_coverage": {
            "by_task": {
                "T01": {
                    "sources": {"T01.01": "auto", "T01.02": "pending"},
                    "auto_proposals": {},
                },
                "T02": {"sources": {"T02.01a": "judge"}},
            }
        },
        "evidence_support": {"by_task": {"T01": {"sources": {"T01.01": "pending"}}}},
        "assertion_quality": {
            "assertions": [{"assertion_id": "F01"}] * 40,
            "counts_all_tasks": {"pending": 40, "by_source": {"judge": 0}},
        },
        **extra,
    }


def test_run_list_summarizes_grades_by_decision_source():
    summary = serve.summarize_grade(
        sr_grade(
            judge={
                "judge_model": "judge/model",
                "rubric_version": "1.0.0",
                "criteria_applied": ["T06.01", "T06.02"],
                "severe_flag_suggestions": [],
            }
        )
    )
    assert "citations" not in summary and "criteria" not in summary
    assert summary["status"] == "provisional"
    assert summary["flags"]["accounting_traps"] == [{"figure_id": "LFDD"}]
    assert summary["content_coverage"] == {
        "sources": {"T01.01": "auto", "T01.02": "pending", "T02.01a": "judge"}
    }
    assert summary["evidence_support"] == {"sources": {"T01.01": "pending"}}
    assert summary["assertion_quality"]["counts"]["pending"] == 40
    assert summary["judge"]["criteria_applied"] == 2
    assert summary["judge"]["judge_model"] == "judge/model"
    # MVP grades group criteria by dimension and count assertions per dimension.
    mvp = serve.summarize_grade(
        {
            "content_coverage": {
                "by_dimension": {"D1": {"sources": {"D1.1": "pending"}}}
            },
            "assertion_quality": {"counts_all_dimensions": {"pending": 18}},
        }
    )
    assert mvp["content_coverage"]["sources"] == {"D1.1": "pending"}
    assert mvp["assertion_quality"]["counts"] == {"pending": 18}
    assert serve.summarize_grade(None) is None
    # An incomplete run's grade keeps its explanation and no content measures.
    incomplete = serve.summarize_grade(
        {
            "content_coverage": None,
            "measures_note": "run outcome is 'incomplete_submission'",
            "flags": {},
        }
    )
    assert incomplete == {
        "measures_note": "run outcome is 'incomplete_submission'",
        "flags": {},
    }


def test_discovers_judge_proposals_beside_the_grade(tmp_path):
    out_dir = tmp_path / "out"
    write_run(out_dir, "panel_sr80k/opus", "sr-run")
    artifacts = out_dir / "panel_sr80k" / "opus" / "sr-run_artifacts"
    write_json(artifacts / "grade.json", sr_grade(judge=None))
    judge_dir = artifacts / "episode" / "judge"
    write_json(
        judge_dir / "judge_run.json",
        {
            "status": "judged",
            "units": 13,
            "failed_units": [],
            "errors": {},
            "api_calls": 13,
            "cache_hits": 0,
        },
    )
    write_json(
        judge_dir / "grade.json",
        sr_grade(
            judge={
                "judge_model": "openai/gpt-6.1-sol",
                "rubric_version": "1.0.0",
                "note": "proposals",
                "criteria_applied": ["T06.01"],
                "severe_flag_suggestions": [],
            }
        ),
    )
    run = serve.discover_runs(out_dir)[0]
    assert run["grade"]["judge"] is None
    judge = run["judge"]
    assert judge["status"] == "judged"
    assert judge["units"] == 13
    assert judge["failed_units"] == 0
    assert judge["judge_model"] == "openai/gpt-6.1-sol"
    assert judge["grade"]["content_coverage"]["sources"]["T02.01a"] == "judge"
    assert judge["path"] == "panel_sr80k/opus/sr-run_artifacts/episode/judge/grade.json"
    assert len(json.dumps(run)) < 5000


def test_judge_outputs_outside_output_are_ignored(tmp_path):
    out_dir = tmp_path / "out"
    write_run(out_dir)
    external = tmp_path / "judge_run.json"
    external.write_text(json.dumps({"status": "judged", "units": 99}))
    judge_dir = out_dir / "live" / "test-run_artifacts" / "episode" / "judge"
    judge_dir.mkdir(parents=True)
    (judge_dir / "judge_run.json").symlink_to(external)
    assert serve.discover_runs(out_dir)[0]["judge"] is None


def test_live_reports_episode_tools_and_tool_budget(local_server):
    base, _, episode = local_server(live=True)
    assert get_json(base, "/api/live")["episode"] is None
    episode.mkdir()
    (episode / "episode_config.json").write_text('{"tool_names": ["list_')
    assert get_json(base, "/api/live")["episode"] is None, (
        "a half-written config is ignored"
    )
    write_json(
        episode / "episode_config.json",
        {
            "bundle_version": "0.1.0",
            "tool_names": [
                "list_documents",
                "interview_witness",
                "request_data_return",
            ],
            "config": {
                "max_tool_calls": 150,
                "frequency_page_size": 1000,
                "log_page_size": 200,
            },
        },
    )
    (episode / "trace.jsonl").write_text(
        json.dumps(
            {
                "tool": "request_data_return",
                "outcome_code": "NOT_HELD",
                "envelope": {
                    "ok": False,
                    "tool": "request_data_return",
                    "error": {"code": "NOT_HELD", "message": "Not held"},
                },
            }
        )
        + "\n"
    )
    result = get_json(base, "/api/live")
    assert result["episode"]["tool_names"] == [
        "list_documents",
        "interview_witness",
        "request_data_return",
    ]
    assert result["episode"]["budgets"]["tool_calls_limit"] == 150
    assert result["records"][0]["outcome_code"] == "NOT_HELD"


FI_TASK = "gb-2019-full-investigation"


def fi_grade(**extra):
    """A full-investigation grade: 20 tasks, the executive-summary word count in its
    flags, and the bulky sections (about 2 MB on a reference run) the run list drops."""
    return sr_grade(
        grade_schema="gb2019-fi-grade/1",
        task_id=FI_TASK,
        builds_on={"grader": "environment.incident.sr_grading"},
        tasks=[{"task_id": f"T{i:02d}"} for i in range(1, 21)],
        flags={
            "needs_human_review": [f"T10.0{i}" for i in range(1, 6)],
            "executive_summary": {"words": 570, "limit": 600, "within_limit": True},
            "uncited_findings": [],
        },
        content_coverage={
            "by_task": {
                f"T{i:02d}": {"sources": {f"T{i:02d}.01": "pending"}}
                for i in range(1, 21)
            },
            "by_handoff_criterion": {"T10.02": {"fields": ["a", "b", "c"]}},
        },
        **extra,
    )


def test_full_investigation_grade_summary_keeps_task_and_summary_count():
    summary = serve.summarize_grade(fi_grade())
    assert summary["grade_schema"] == "gb2019-fi-grade/1"
    assert summary["task_id"] == FI_TASK
    assert summary["flags"]["executive_summary"] == {
        "words": 570,
        "limit": 600,
        "within_limit": True,
    }
    assert len(summary["content_coverage"]["sources"]) == 20
    for bulky in ("tasks", "citations", "criteria", "builds_on"):
        assert bulky not in summary
    assert len(json.dumps(summary)) < 5000


def test_discovers_full_investigation_runs_with_grade_and_topic_judge(tmp_path):
    out_dir = tmp_path / "out"
    path = out_dir / "fi" / "reference" / "transcript.json"
    write_json(
        path,
        {
            "run_id": "fi-ref",
            "events": [
                {"type": "task_started", "task_id": FI_TASK, "model": "fake"},
                {
                    "type": "scoring",
                    # The runner caps a metadata value at 1 MiB: the grade is text.
                    "scoring": {"metadata": {"grading": "{'status': 'graded' ..."}},
                },
            ],
        },
    )
    artifacts = out_dir / "fi" / "reference" / "fi-ref_artifacts"
    write_json(artifacts / "grade.json", fi_grade(judge=None))
    judge_dir = artifacts / "episode" / "judge"
    write_json(judge_dir / "judge_run.json", {"status": "judged", "units": 20})
    write_json(
        judge_dir / "judge_output.json",
        {"scope": {"mode": "topic", "topics": ["T10", "T15"]}, "criteria": {}},
    )
    write_json(
        judge_dir / "grade.json",
        fi_grade(judge={"judge_model": "openai/gpt-6.1-sol", "criteria_applied": []}),
    )
    (run,) = serve.discover_runs(out_dir)
    assert run["task_id"] == FI_TASK
    assert run["path"] == "fi/reference/transcript.json"
    assert run["grade_path"] == "fi/reference/fi-ref_artifacts/grade.json"
    assert run["grade"]["flags"]["executive_summary"]["words"] == 570
    assert run["judge"]["scope"] == "topic"
    assert run["judge"]["units"] == 20
    assert run["judge"]["grade"]["task_id"] == FI_TASK
    # Increment A's judge outputs record no scope; a malformed output is ignored.
    (judge_dir / "judge_output.json").write_text('{"scope": "topic"')
    assert serve.discover_runs(out_dir)[0]["judge"]["scope"] is None


def test_judge_output_outside_output_is_not_read(tmp_path):
    out_dir = tmp_path / "out"
    write_run(out_dir)
    judge_dir = out_dir / "live" / "test-run_artifacts" / "episode" / "judge"
    write_json(judge_dir / "judge_run.json", {"status": "judged", "units": 20})
    external = tmp_path / "judge_output.json"
    external.write_text(json.dumps({"scope": {"mode": "topic"}}))
    (judge_dir / "judge_output.json").symlink_to(external)
    judge = serve.discover_runs(out_dir)[0]["judge"]
    assert judge["units"] == 20
    assert judge["scope"] is None


_FI_OUT = serve.OUT_DIR / "fi"


@pytest.mark.skipif(
    not (_FI_OUT / "reference" / "transcript.json").is_file(),
    reason="the full-investigation fake runs are not in out/fi",
)
def test_saved_full_investigation_runs_are_listed_with_compact_grades():
    runs = {
        run["path"]: run
        for run in serve.discover_runs(serve.OUT_DIR)
        if run["path"].startswith("fi/")
    }
    reference = runs["fi/reference/transcript.json"]
    assert reference["task_id"] == FI_TASK
    assert reference["grade"]["grade_schema"] == "gb2019-fi-grade/1"
    assert reference["grade"]["flags"]["executive_summary"]["limit"] == 600
    # The full grade (about 2 MB) stays behind /api/file; the list stays small.
    assert len(json.dumps(reference)) < 50_000
    full = json.loads((serve.OUT_DIR / reference["grade_path"]).read_text())
    assert full["task_id"] == FI_TASK
    no_submission = runs.get("fi/no_submission/transcript.json")
    if no_submission:
        assert no_submission["grade"]["measures_note"].startswith(
            "run outcome is 'incomplete_submission'"
        )


# -- Results: evidence drawer, compare summaries ----------------------------------------
# The evidence endpoint resolves a citation from the bundle a run used (matched by the
# manifest sha256), reading only manifest-listed files and never private/.

BUNDLES = {
    "mvp": serve.INCIDENT_DIR / "bundle",
    "system_response": serve.INCIDENT_DIR / "bundles" / "system_response",
    "full_investigation": serve.INCIDENT_DIR / "bundles" / "full_investigation",
}


def bundle_of(name):
    return serve.EvidenceBundle(BUNDLES[name])


def manifest_of(name):
    return json.loads((BUNDLES[name] / "manifest.json").read_text(encoding="utf-8"))


def data_rows(name, doc_id="R01"):
    doc = next(d for d in manifest_of(name)["documents"] if d["doc_id"] == doc_id)
    artifact = next(a for a in doc["artifacts"] if a.get("timeseries"))
    lines = (BUNDLES[name] / artifact["file"]).read_text(encoding="utf-8").splitlines()
    return lines[1:]


@pytest.mark.parametrize("name", list(BUNDLES))
def test_evidence_resolves_lines_rows_and_times_on_each_bundle(name):
    bundle = bundle_of(name)
    text = (BUNDLES[name] / "R03" / "R03.txt").read_text(encoding="utf-8")
    lines = text[:-1].split("\n") if text.endswith("\n") else text.split("\n")
    resolved = serve.resolve_citation(bundle, "R03", "L3-L5", context=2)
    assert resolved["resolved"] and resolved["kind"] == "lines"
    assert [line["n"] for line in resolved["lines"]] == [1, 2, 3, 4, 5, 6, 7]
    assert [line["text"] for line in resolved["lines"] if line["cited"]] == lines[2:5]
    assert resolved["line_count"] == len(lines)
    assert resolved["document"]["title"]
    out_of_range = serve.resolve_citation(bundle, "R03", f"L{len(lines) + 1}")
    assert not out_of_range["resolved"]
    assert "out of range" in out_of_range["error"]
    rows = data_rows(name)
    by_rows = serve.resolve_citation(bundle, "R01", "rows:2-4")
    assert [r["text"] for r in by_rows["rows"]] == rows[1:4]
    assert serve.resolve_citation(bundle, "R01", "row:1")["rows"][0]["n"] == 1
    # A time locator in UTC selects the samples by instant, as the grader does.
    minimum = serve.resolve_citation(bundle, "R01", "time:2019-08-09T15:53:49Z")
    assert minimum["normalized"] == "time:2019-08-09T15:53:49+00:00"
    assert [r["text"] for r in minimum["rows"]] == ["2019-08-09T16:53:49+01:00,48.787"]
    window = serve.resolve_citation(
        bundle, "R01", "time:2019-08-09T16:52:33+01:00/2019-08-09T16:52:36+01:00"
    )
    assert [r["n"] for r in window["rows"]] == [754, 755, 756, 757]
    outside = serve.resolve_citation(bundle, "R01", "time:2019-08-09T18:00:00+01:00")
    assert not outside["resolved"] and "outside the R01 series" in outside["error"]
    assert not serve.resolve_citation(bundle, "R03", "rows:1-2")["resolved"]
    assert not serve.resolve_citation(bundle, "R99", "L1")["resolved"]
    assert not serve.resolve_citation(bundle, "R03", "L0")["resolved"]


def first_record(name, section, key):
    entry = manifest_of(name)[section][0]
    path = BUNDLES[name] / entry["file"]
    if section == "witnesses":
        card = json.loads(path.read_text(encoding="utf-8"))
        return card["evidence_id"], card["blocks"][0][key], card["blocks"][0]
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    return row["evidence_id"], row[key], row


@pytest.mark.parametrize("name", ["system_response", "full_investigation"])
@pytest.mark.parametrize(
    "kind,section,key",
    [
        ("event", "asset_logs", "event_id"),
        ("entry", "control_logs", "entry_id"),
        ("response", "witnesses", "response_id"),
    ],
)
def test_evidence_resolves_records_on_manifest_v2_bundles(name, kind, section, key):
    bundle = bundle_of(name)
    owner, record_id, raw = first_record(name, section, key)
    resolved = serve.resolve_citation(bundle, owner, f"{kind}:{record_id}")
    assert resolved["resolved"], resolved["error"]
    record = resolved["record"]
    assert record["kind"] == kind and record["id"] == record_id
    text_key = "response_text" if kind == "response" else "text"
    assert record["fields"][text_key] == raw[text_key]
    assert record["source"].get("status", "").startswith("STATUS")
    wrong_owner = "R01" if owner != "R01" else "R02"
    misowned = serve.resolve_citation(bundle, wrong_owner, f"{kind}:{record_id}")
    assert not misowned["resolved"]
    assert f"belongs to evidence {owner}" in misowned["error"]
    absent = serve.resolve_citation(bundle, owner, f"{kind}:NO-SUCH-RECORD")
    assert not absent["resolved"]


def test_the_mvp_bundle_has_no_records():
    resolved = serve.resolve_citation(bundle_of("mvp"), "R03", "event:R03-C1")
    assert not resolved["resolved"]
    assert "no asset-log event" in resolved["error"]


@pytest.fixture
def evidence_server(tmp_path):
    servers = []

    def start(bundle_dirs=tuple(BUNDLES.values())):
        out_dir = tmp_path / "out"
        out_dir.mkdir(exist_ok=True)
        server = serve.make_server(
            0,
            out_dir=out_dir,
            html_file=tmp_path / "agent_world.html",
            bundle_dirs=bundle_dirs,
        )
        (tmp_path / "agent_world.html").write_text(
            "<!doctype html><title>Agent world</title>"
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return f"http://127.0.0.1:{server.server_port}", out_dir

    yield start
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def evidence_url(sha, evidence_id, locator, **extra):
    query = {"bundle": sha, "evidence_id": evidence_id, "locator": locator, **extra}
    return "/api/evidence?" + urlencode(query)


def http_error(base, path):
    with pytest.raises(HTTPError) as error:
        get_json(base, path)
    return error.value.code, error.value.read()


def test_evidence_endpoint_resolves_by_the_runs_bundle_hash(evidence_server):
    base, _ = evidence_server()
    available = get_json(base, "/api/bundles")["bundles"]
    assert {b["bundle_id"] for b in available} == {
        "gb-2019-08-09-electrical-mvp",
        "gb-2019-08-09-system-response",
        "gb-2019-08-09-full-investigation",
    }
    sr = bundle_of("system_response").sha256
    result = get_json(base, evidence_url(sr, "R03", "event:R03-C1"))
    assert result["resolved"]
    assert result["bundle"]["bundle_sha256"] == sr
    assert "fault inception" in result["record"]["fields"]["text"]
    lines = get_json(base, evidence_url(sr, "R03", "L10", context="99"))
    assert len(lines["lines"]) <= 1 + 2 * serve.MAX_CONTEXT
    # A run from a bundle that is not on disk (the MVP's 1.0.0) is told so.
    code, body = http_error(base, evidence_url("5" * 64, "R03", "L1"))
    assert code == 404
    assert json.loads(body)["available"]


@pytest.mark.parametrize(
    "query",
    [
        {"evidence_id": "R03", "locator": "L1"},
        {"bundle": "not-a-hash", "evidence_id": "R03", "locator": "L1"},
        {"bundle": "a" * 64, "evidence_id": "", "locator": "L1"},
        {"bundle": "a" * 64, "evidence_id": "R03", "locator": ""},
    ],
)
def test_evidence_endpoint_rejects_incomplete_requests(evidence_server, query):
    base, _ = evidence_server()
    code, _ = http_error(base, "/api/evidence?" + urlencode(query))
    assert code == 400


@pytest.mark.parametrize(
    "evidence_id",
    ["../private/answer_key", "../../private", "R03/../../private", "/etc/passwd"],
)
def test_evidence_ids_cannot_name_paths(evidence_server, evidence_id):
    base, _ = evidence_server()
    sha = bundle_of("full_investigation").sha256
    code, body = http_error(base, evidence_url(sha, evidence_id, "L1"))
    assert code == 400
    assert b"answer_key" not in body and b"criteria" not in body


def test_locators_cannot_name_paths(evidence_server):
    base, _ = evidence_server()
    sha = bundle_of("full_investigation").sha256
    for locator in ("L1/../../private/answer_key.json", "../private", "event:../x"):
        result = get_json(base, evidence_url(sha, "R03", locator))
        assert not result["resolved"]
        assert "answer" not in json.dumps(result.get("lines") or [])


def make_bundle(root, *, text_file="D01/D01.txt", extra_docs=()):
    """A small manifest-v1 bundle: one document whose text file may be redirected."""
    (root / "D01").mkdir(parents=True, exist_ok=True)
    (root / "D01" / "D01.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    (root / "D01" / "unlisted.txt").write_text(
        "not in the manifest\n", encoding="utf-8"
    )

    def doc(doc_id, path, data):
        return {
            "doc_id": doc_id,
            "title": f"{doc_id} record",
            "owner": "owner",
            "date": "2019-08-09",
            "category": "network_records",
            "text_file": path,
            "artifacts": [{"file": path, "media_type": "text/plain"}],
            "sha256": {path: hashlib.sha256(data).hexdigest()},
        }

    target = (root / text_file).resolve() if ".." in text_file else root / text_file
    data = target.read_bytes() if target.exists() else b""
    documents = [doc("D01", text_file, data)]
    for doc_id, path in extra_docs:
        documents.append(doc(doc_id, path, (root / path).read_bytes()))
    manifest = {
        "bundle_id": "test-bundle",
        "bundle_version": "0.0.1",
        "documents": documents,
    }
    data = json.dumps(manifest).encode()
    (root / "manifest.json").write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def test_evidence_reads_only_manifest_listed_files(tmp_path):
    sha = make_bundle(tmp_path / "bundle")
    bundle = serve.EvidenceBundle(tmp_path / "bundle")
    assert bundle.sha256 == sha
    resolved = serve.resolve_citation(bundle, "D01", "L2")
    assert [line["text"] for line in resolved["lines"] if line["cited"]] == ["beta"]
    with pytest.raises(serve.EvidenceRefused):
        bundle.read("D01/unlisted.txt")
    with pytest.raises(serve.EvidenceRefused):
        bundle.read("manifest.json")
    # A file changed after the manifest pinned it is not shown as the run's evidence.
    (tmp_path / "bundle" / "D01" / "D01.txt").write_text("changed\n")
    with pytest.raises(serve.EvidenceRefused):
        serve.EvidenceBundle(tmp_path / "bundle").read("D01/D01.txt")


@pytest.mark.parametrize(
    "kind", ["parent_private", "inner_private", "file_link", "dir_link"]
)
def test_evidence_never_serves_private_or_linked_files(evidence_server, tmp_path, kind):
    private = tmp_path / "private"
    private.mkdir()
    (private / "answer_key.json").write_text('{"secret": "answer key"}\n')
    root = tmp_path / "bundle"
    root.mkdir()
    if kind == "parent_private":
        sha = make_bundle(root, text_file="../private/answer_key.json")
    elif kind == "inner_private":
        (root / "private").mkdir()
        (root / "private" / "answer_key.json").write_text('{"secret": "answer key"}\n')
        sha = make_bundle(root, text_file="private/answer_key.json")
    elif kind == "file_link":
        (root / "D01").mkdir()
        (root / "D01" / "link.txt").symlink_to(private / "answer_key.json")
        sha = make_bundle(root, text_file="D01/link.txt")
    else:
        (root / "linked").symlink_to(private, target_is_directory=True)
        sha = make_bundle(root, text_file="linked/answer_key.json")
    base, _ = evidence_server((root,))
    code, body = http_error(base, evidence_url(sha, "D01", "L1"))
    assert code == 403
    assert b"answer key" not in body and b"secret" not in body


def test_bundles_inside_private_or_behind_links_are_not_loaded(tmp_path):
    private = tmp_path / "private"
    make_bundle(private)
    assert serve.EvidenceLibrary([private]).bundles() == []
    real = tmp_path / "real"
    make_bundle(real)
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "manifest.json").symlink_to(real / "manifest.json")
    assert serve.EvidenceLibrary([linked]).bundles() == []
    assert serve.is_private(serve.INCIDENT_DIR / "private" / "answer_key.json")


def fi_full_grade(criteria=106, judged=False):
    """A full-investigation grade with the bulky per-criterion detail the compare page
    must not receive."""
    items = []
    for i in range(criteria):
        topic = f"T{1 + i % 20:02d}"
        judge = judged and i % 2 == 0
        items.append(
            {
                "criterion_id": f"{topic}.{i:02d}",
                "task": topic,
                "dimension": topic,
                "assessment_mode": "judge" if i % 2 == 0 else "auto_assisted_human",
                "title": f"Criterion {i} of {topic}: " + "a long title " * 6,
                "content": {
                    "value": 1.0 if judge else None,
                    "source": "judge" if judge else "pending",
                    "auto_proposal": 0.5,
                    "judge_proposal": 1 if judge else None,
                    "basis": "judge proposal: " + "rationale " * 40,
                },
                "evidence_support": {
                    "value": None,
                    "source": "pending",
                    "auto_proposal": 1,
                },
                "auto_checks": {"elements": [{"detail": "x" * 2000}] * 3},
                "layers": {"judge": {"rationale": "y" * 1500, "supporting_spans": []}},
                "matched_finding_ids": ["F01", "F02"],
            }
        )
    return {
        "grade_schema": "gb2019-fi-grade/1",
        "task_id": FI_TASK,
        "status": "provisional",
        "tasks": [f"T{i:02d}" for i in range(1, 21)],
        "key": {"key_version": "0.1.0", "review_status": "pending_domain_review"},
        "run": {"outcome": "complete", "budgets": {"tool_calls_limit": 150}},
        "criteria": items,
        "citations": [{"finding_id": "F01", "detail": "z" * 500}] * 200,
        "assertion_quality": {
            "assertions": [
                {
                    "assertion_id": f"F{i:02d}",
                    "dimension": "T01",
                    "kind": "finding",
                    "source": "judge" if judged else "pending",
                    "verdict": "supported" if judged else None,
                    "layers": {"judge": {"rationale": "w" * 800}},
                }
                for i in range(50)
            ]
        },
        "judge": {"judge_model": "judge/model", "criteria_applied": ["T01.00"] * 53}
        if judged
        else None,
    }


def write_full_run(out_dir, folder="panel_fi/opus", run_id="fi-run"):
    path = out_dir / folder / "transcript.json"
    write_json(
        path,
        {
            "run_id": run_id,
            "events": [
                {
                    "type": "task_started",
                    "model": "openrouter/test/model",
                    "task_id": FI_TASK,
                },
                {
                    "type": "task_pre_hook_completed",
                    "metadata": {
                        "bundle_id": "gb-2019-08-09-full-investigation",
                        "bundle_version": "0.1.0",
                        "bundle_sha256": "f" * 64,
                        "budgets": {
                            "max_tool_calls": 150,
                            "output_token_budget": 80000,
                            "context_cap_tokens": 200000,
                        },
                    },
                },
                {"type": "tool_call_completed", "tool_call_id": "a"},
                {"type": "token_usage", "input_tokens": 1200, "output_tokens": 30},
                {"type": "token_usage", "input_tokens": 9000, "output_tokens": 70},
                {"type": "tool_call_completed", "tool_call_id": "b"},
            ],
        },
    )
    artifacts = out_dir / folder / f"{run_id}_artifacts"
    write_json(artifacts / "grade.json", fi_full_grade())
    write_json(
        artifacts / "episode" / "submission.json", {"findings": [], "report": {}}
    )
    write_json(
        artifacts / "episode" / "episode_config.json",
        {
            "bundle_id": "gb-2019-08-09-full-investigation",
            "bundle_version": "0.1.0",
            "bundle_sha256": bundle_of("full_investigation").sha256,
        },
    )
    return artifacts


def test_runs_name_their_submission_bundle_and_budgets(tmp_path):
    out_dir = tmp_path / "out"
    write_full_run(out_dir)
    (run,) = serve.discover_runs(out_dir)
    assert run["submission_path"] == (
        "panel_fi/opus/fi-run_artifacts/episode/submission.json"
    )
    # The episode configuration names the bundle the run used; it wins over the
    # transcript's copy.
    assert run["bundle"]["bundle_sha256"] == bundle_of("full_investigation").sha256
    assert run["metrics"] == {
        "outcome": None,
        "incomplete_reason": None,
        "tool_calls": 2,
        "tool_calls_limit": 150,
        "peak_input_tokens": 9000,
        "context_cap_tokens": 200000,
        "output_tokens": 100,
        "output_token_budget": 80000,
    }


def test_results_are_compact_and_the_judged_grade_supersedes(tmp_path):
    out_dir = tmp_path / "out"
    artifacts = write_full_run(out_dir)
    (run,) = discover_results_runs(out_dir)
    assert run["grade_source"] == "run"
    write_json(artifacts / "episode" / "judge" / "judge_run.json", {"status": "judged"})
    write_json(
        artifacts / "episode" / "judge" / "grade.json", fi_full_grade(judged=True)
    )
    results = serve.discover_results(out_dir)
    (run,) = results["runs"]
    assert run["grade_source"] == "judge"
    assert (
        run["grade_path"] == "panel_fi/opus/fi-run_artifacts/episode/judge/grade.json"
    )
    grade = run["grade"]
    assert len(grade["criteria"]) == 106
    first = grade["criteria"][0]
    assert first["content"] == {
        "value": 1.0,
        "source": "judge",
        "auto_proposal": 0.5,
        "judge_proposal": 1,
    }
    assert set(first) == {
        "criterion_id",
        "task",
        "dimension",
        "assessment_mode",
        "content",
        "evidence_support",
    }
    assert grade["assertion_quality"]["assertions"][0] == {
        "assertion_id": "F00",
        "dimension": "T01",
        "kind": "finding",
        "source": "judge",
        "verdict": "supported",
    }
    for bulky in ("citations", "flags", "layers", "auto_checks", "title", "basis"):
        assert f'"{bulky}"' not in json.dumps(grade)
    assert results["topic_hints"][FI_TASK]["T01"].startswith("Criterion 0 of T01")
    full = (artifacts / "episode" / "judge" / "grade.json").stat().st_size
    assert len(json.dumps(run)) < min(40_000, full / 10)


def discover_results_runs(out_dir):
    return serve.discover_results(out_dir)["runs"]


def test_http_serves_results_and_the_compare_route(local_server):
    base, out_dir, _ = local_server()
    write_full_run(out_dir)
    results = get_json(base, "/api/results")
    assert results["runs"][0]["metrics"]["peak_input_tokens"] == 9000
    with urlopen(base + "/compare", timeout=5) as response:
        assert b"Agent world" in response.read()
    with urlopen(base + "/compare/", timeout=5) as response:
        assert response.status == 200


# Saved runs: every citation the grader checked resolves (or fails) the same way here,
# for each bundle and each locator kind the runs use.
_SAVED_GRADES = {
    "mvp": "panel/opus55-002/gb2019-v2-opus55-002_artifacts/grade.json",
    "system_response": "panel_sr80k/opus55-001/gb2019-sr80k-opus55-001_artifacts/grade.json",
    "full_investigation": "fi/reference/gb2019-fi-fake-reference_artifacts/grade.json",
    "full_investigation_pilot": (
        "fi_pilot/gb2019-fi-pilot-opus55-001_artifacts/episode/judge/grade.json"
    ),
}


@pytest.mark.parametrize("name,relative", list(_SAVED_GRADES.items()))
def test_saved_citations_resolve_as_the_grader_resolved_them(name, relative):
    path = serve.OUT_DIR / relative
    if not path.is_file():
        pytest.skip(f"saved run absent: {relative}")
    grade = json.loads(path.read_text(encoding="utf-8"))
    bundle = serve.EvidenceLibrary().find(grade["bundle"]["bundle_sha256"])
    assert bundle is not None, "the run's bundle is on disk"
    kinds = set()
    for check in grade["citations"]:
        result = serve.resolve_citation(bundle, check["evidence_id"], check["locator"])
        assert result["resolved"] == check["resolvable"], (check, result["error"])
        if check["resolvable"]:
            assert result["normalized"] == check["normalized"]
            kinds.add(result["kind"])
    assert kinds >= {"lines"}
    if name == "full_investigation":
        assert kinds == {"lines", "time", "rows", "event", "entry", "response"}


@pytest.mark.skipif(
    not (serve.OUT_DIR / "live" / "transcript.json").is_file(),
    reason="the MVP live run is not in out/live",
)
def test_saved_mvp_run_from_bundle_1_0_0_is_not_resolved_against_1_1_0():
    (run,) = [r for r in serve.discover_runs() if r["path"] == "live/transcript.json"]
    assert run["bundle"]["bundle_version"] == "1.0.0"
    assert serve.EvidenceLibrary().find(run["bundle"]["bundle_sha256"]) is None


@pytest.mark.skipif(
    not (serve.OUT_DIR / "panel_sr80k").is_dir(),
    reason="the system-response panel is not in out/panel_sr80k",
)
def test_saved_results_use_judged_grades_and_stay_small():
    runs = {run["path"]: run for run in serve.discover_results()["runs"]}
    opus = runs["panel_sr80k/opus55-001/transcript.json"]
    assert opus["grade_source"] == "judge"
    assert opus["metrics"]["peak_input_tokens"] == 160959
    assert len(opus["grade"]["criteria"]) == 60
    pilot = runs.get("fi_pilot/transcript.json")
    if pilot:
        # The pilot has only a judged grade; its scoring-time grading failed.
        assert pilot["grade_source"] == "judge"
        assert len(pilot["grade"]["criteria"]) == 106
    for run in runs.values():
        assert len(json.dumps(run)) < 50_000, run["path"]
    incomplete = runs.get("panel_sr_30k/opus55-001/transcript.json")
    if incomplete:
        assert incomplete["metrics"]["outcome"] == "incomplete_submission"
        assert incomplete["grade"]["criteria"] == []
