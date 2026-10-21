"""PythonRunner: output, errors, timeouts, truncation, files, limits and environment."""

from __future__ import annotations

import json
import os
import resource
import sys
import time
from pathlib import Path

import pytest
from incident_helpers import CSV_NAME, series_csv

import environment.incident.python_runner as runner_module
from environment.incident.python_runner import (
    PythonRunner,
    _diff,
    _Entry,
    _walk,
    minimal_env,
)


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    evidence = tmp_path / "evidence"
    scratch = tmp_path / "scratch"
    (evidence / "R01").mkdir(parents=True)
    scratch.mkdir()
    (evidence / "R01" / CSV_NAME).write_text(series_csv())
    return evidence, scratch


def make_runner(dirs, **kwargs) -> PythonRunner:
    evidence, scratch = dirs
    kwargs.setdefault("timeout_s", 20)
    return PythonRunner(
        python_executable=sys.executable,
        evidence_dir=evidence,
        scratch_dir=scratch,
        **kwargs,
    )


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover
        return True
    return True


def _wait_dead(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.05)
    return not _alive(pid)


def test_stdout_and_success(dirs):
    result = make_runner(dirs).run(
        "print('hello')\nimport sys; print('warn', file=sys.stderr)"
    )
    assert result.ok and result.exit_code == 0 and not result.timed_out
    assert result.stdout == "hello\n"
    assert result.stderr == "warn\n"
    assert result.error_code is None
    assert not result.stdout_truncated and not result.stderr_truncated


def test_error_exit_is_python_error(dirs):
    result = make_runner(dirs).run("print('before')\nraise ValueError('boom')")
    assert not result.ok
    assert result.error_code == "PYTHON_ERROR"
    assert result.exit_code == 1
    assert "ValueError: boom" in result.stderr
    assert result.stdout == "before\n"
    assert "status 1" in result.error_message


def test_syntax_error(dirs):
    result = make_runner(dirs).run("def broken(:\n")
    assert result.error_code == "PYTHON_ERROR" and "SyntaxError" in result.stderr


def test_timeout_kills_process_group(dirs):
    _, scratch = dirs
    code = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "open('child.pid', 'w').write(str(child.pid))\n"
        "print('started', flush=True)\n"
        "time.sleep(60)\n"
    )
    start = time.monotonic()
    result = make_runner(dirs, timeout_s=1.5).run(code)
    elapsed = time.monotonic() - start
    assert result.timed_out and result.error_code == "TIMEOUT"
    assert not result.ok
    assert "started" in result.stdout
    assert "1.5 s" in result.error_message
    assert elapsed < 10
    child = int((scratch / "child.pid").read_text())
    assert _wait_dead(child), "child process survived the timeout"


def test_background_children_do_not_survive_a_finished_call(dirs):
    _, scratch = dirs
    code = (
        "import subprocess, sys\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "open('bg.pid', 'w').write(str(child.pid))\n"
    )
    start = time.monotonic()
    result = make_runner(dirs).run(code)
    assert result.ok
    assert time.monotonic() - start < 10
    assert _wait_dead(int((scratch / "bg.pid").read_text()))


def test_cleanup_hook_runs_after_every_call(dirs):
    calls = []
    runner = make_runner(dirs, cleanup=lambda: calls.append("cleanup"))
    runner.run("print(1)")
    runner.run("raise SystemExit(3)")
    assert calls == ["cleanup", "cleanup"]


class _Unreapable(RuntimeError):
    """Stands in for karotte.UnreapableCohortError (the core must not import karotte)."""


def test_cleanup_failure_fails_the_call_closed(dirs):
    _, scratch = dirs

    def boom():
        raise _Unreapable("processes were still alive")

    result = make_runner(dirs, cleanup=boom).run(
        "print('hi')\nopen('made.txt', 'w').write('x')"
    )
    assert not result.ok and result.error_code == "INTERNAL_ERROR"
    assert result.cleanup_error == "_Unreapable: processes were still alive"
    assert "could not confirm that every process" in result.error_message
    assert result.exit_code == 0 and result.stdout == "hi\n"  # output still shown
    # scratch is not inspected beside processes that may still be alive
    assert result.files == [] and (scratch / "made.txt").exists()
    assert result.notes[0] == "cleanup failed: _Unreapable: processes were still alive"


def test_precleanup_refuses_to_run_while_leftovers_cannot_be_stopped(dirs):
    _, scratch = dirs
    calls = []

    def still_failing():
        calls.append("cleanup")
        raise _Unreapable("still alive")

    result = make_runner(dirs, cleanup=still_failing).run(
        "open('ran.txt', 'w').write('x')", precleanup=True
    )
    assert result.error_code == "INTERNAL_ERROR" and result.exit_code is None
    assert "was not run" in result.error_message
    assert result.cleanup_error == "_Unreapable: still alive"
    assert calls == ["cleanup"] and not (scratch / "ran.txt").exists()


def test_precleanup_success_runs_the_code(dirs):
    calls = []
    result = make_runner(dirs, cleanup=lambda: calls.append("cleanup")).run(
        "print(1)", precleanup=True
    )
    assert result.ok and result.cleanup_error is None
    assert calls == ["cleanup", "cleanup"]  # before and after


def test_launcher_is_injected_and_limits_apply_before_its_preexec(dirs, tmp_path):
    record = tmp_path / "preexec.json"
    seen_argv = []

    def launcher(argv):
        seen_argv.append(list(argv))

        def preexec():
            fsize = resource.getrlimit(resource.RLIMIT_FSIZE)
            core = resource.getrlimit(resource.RLIMIT_CORE)
            fd = os.open(record, os.O_WRONLY | os.O_CREAT, 0o600)
            os.write(fd, json.dumps({"fsize": fsize, "core": core}).encode())
            os.close(fd)
            os.setsid()  # what Karotte's preexec does

        return ["/usr/bin/env", *argv], preexec

    result = make_runner(dirs, launcher=launcher, file_size_bytes=12345).run(
        "print('ok')"
    )
    assert result.ok and result.stdout == "ok\n"
    assert seen_argv == [[sys.executable, "-I", "-B", "-X", "utf8", "-"]]
    limits = json.loads(record.read_text())
    assert limits["fsize"] == [12345, 12345]
    assert limits["core"] == [0, 0]


def test_output_truncation_is_explicit(dirs):
    result = make_runner(dirs, max_output_chars=1000).run(
        "import sys\nprint('x' * 50000)\nsys.stderr.write('e' * 3000)"
    )
    assert result.ok
    assert result.stdout_truncated and result.stderr_truncated
    assert result.stdout.startswith("x" * 1000)
    assert "[... stdout truncated by the environment" in result.stdout
    assert "50001 bytes" in result.stdout
    assert len(result.stdout) < 1200
    assert result.stdout_bytes == 50001


def test_huge_output_is_drained_without_buffering_it_all(dirs):
    result = make_runner(dirs, max_output_chars=100).run(
        "import sys\nchunk = 'y' * 65536\nfor _ in range(320):\n    sys.stdout.write(chunk)\n"
    )
    assert result.ok
    assert result.stdout_bytes == 65536 * 320
    assert len(result.stdout) < 300


def test_files_listing(dirs):
    runner = make_runner(dirs)
    first = runner.run(
        "import os\nos.makedirs('sub/deeper', exist_ok=True)\n"
        "open('a.txt','w').write('alpha')\nopen('sub/deeper/b.csv','w').write('1,2\\n')\n"
        "open('gone.txt','w').write('x')\n"
    )
    assert first.ok
    by_path = {f["path"]: f for f in first.files}
    assert set(by_path) == {"a.txt", "gone.txt", "sub/deeper/b.csv"}
    assert by_path["a.txt"]["change"] == "created" and by_path["a.txt"]["bytes"] == 5
    assert len(by_path["a.txt"]["sha256"]) == 64
    second = runner.run(
        "import os\nopen('a.txt','w').write('alpha, longer')\nos.remove('gone.txt')\n"
    )
    by_path = {f["path"]: f for f in second.files}
    assert by_path["a.txt"]["change"] == "modified" and by_path["a.txt"]["bytes"] == 13
    assert by_path["gone.txt"] == {
        "path": "gone.txt",
        "bytes": None,
        "sha256": None,
        "change": "deleted",
    }
    assert "sub/deeper/b.csv" not in by_path  # unchanged
    assert runner.run("print('nothing')").files == []


def test_symlinks_in_scratch_are_listed_but_never_followed(dirs, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("do not hash me")
    result = make_runner(dirs).run(f"import os\nos.symlink({str(secret)!r}, 'link')\n")
    assert result.files == [
        {
            "path": "link",
            "bytes": None,
            "sha256": None,
            "change": "created",
            "type": "symlink",
        }
    ]


def test_pandas_reads_an_evidence_csv(dirs):
    pytest.importorskip("pandas")
    code = (
        "import os, pandas as pd\n"
        "df = pd.read_csv(os.path.join(os.environ['EVIDENCE_DIR'], 'R01', 'series.csv'))\n"
        "print(len(df), round(df['frequency_hz'].min(), 3), df['timestamp'].iloc[0])\n"
    )
    result = make_runner(dirs).run(code)
    assert result.ok, result.stderr
    assert result.stdout.strip() == "20 49.81 2019-08-09T16:52:30+01:00"


def test_environment_is_minimal_and_secret_free(dirs, monkeypatch):
    evidence, scratch = dirs
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "nope")
    monkeypatch.setenv("PYTHONPATH", "/somewhere/else")
    code = (
        "import json, os, sys\n"
        "print(json.dumps({'env': dict(os.environ), 'cwd': os.getcwd(),"
        " 'isolated': sys.flags.isolated, 'path0': sys.path[0]}))\n"
    )
    result = make_runner(dirs).run(code)
    assert result.ok, result.stderr
    info = json.loads(result.stdout)
    env = info["env"]
    expected = minimal_env(sys.executable, evidence, scratch)
    assert {k: v for k, v in env.items() if k in expected} == expected
    assert "ANTHROPIC_API_KEY" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "PYTHONPATH" not in env
    assert "sk-should-not-leak" not in result.stdout
    assert env["EVIDENCE_DIR"] == str(evidence)
    assert env["SCRATCH_DIR"] == str(scratch) == env["HOME"]
    assert env["TZ"] == "UTC" and env["OMP_NUM_THREADS"] == "1"
    assert os.path.realpath(info["cwd"]) == os.path.realpath(scratch)
    assert info["isolated"] == 1


def test_file_size_limit(dirs):
    result = make_runner(dirs, file_size_bytes=1 << 20).run(
        "open('big.bin', 'wb').write(b'x' * (3 << 20))\n"
    )
    assert result.error_code == "RESOURCE_LIMIT"
    assert "File too large" in result.stderr


@pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="RLIMIT_AS is Linux-only"
)
def test_memory_limit_linux(dirs):
    result = make_runner(dirs, memory_bytes=256 << 20).run("x = bytearray(512 << 20)\n")
    assert result.error_code == "RESOURCE_LIMIT"


def test_limits_are_described(dirs):
    runner = make_runner(dirs)
    limits = runner.limits()
    assert limits["wall_timeout_s"] == 20 and limits["memory_bytes"] == 1 << 30
    assert limits["memory_limit_enforced"] is sys.platform.startswith("linux")
    assert "NOT enforced" in limits["isolation"]
    assert limits["network"] == "not_isolated"
    assert (
        "enforced: runs as the unprivileged student"
        in make_runner(dirs, isolated=True).limits()["isolation"]
    )


def test_limits_report_the_actual_network_isolation(dirs):
    namespace = make_runner(dirs, isolated=True, network_mode="namespace").limits()
    assert namespace["network"] == "namespace"
    assert "without network access" in namespace["isolation"]
    firewall = make_runner(
        dirs, isolated=True, network_mode=lambda: "karotte_firewall"
    ).limits()
    assert firewall["network"] == "karotte_firewall"
    assert "without network access" not in firewall["isolation"]
    assert "student firewall" in firewall["isolation"]

    def broken_probe():
        raise OSError("probe failed")

    unknown = make_runner(dirs, isolated=True, network_mode=broken_probe).limits()
    assert unknown["network"] == "unreported"
    assert "without network access" not in unknown["isolation"]
    assert make_runner(dirs, isolated=True).limits()["network"] == "unreported"


def test_unstartable_interpreter_is_internal_error(dirs):
    evidence, scratch = dirs
    runner = PythonRunner(
        python_executable="/nonexistent/python",
        evidence_dir=evidence,
        scratch_dir=scratch,
    )
    result = runner.run("print(1)")
    assert (
        result.error_code == "INTERNAL_ERROR"
        and "could not start Python" in result.error_message
    )


def test_large_code_is_delivered_completely(dirs):
    code = "x = 0\n" + "x += 1\n" * 30000 + "print(x)\n"
    assert len(code) > 200_000
    result = make_runner(dirs).run(code)
    assert result.ok and result.stdout == "30000\n"


def test_code_reading_stdin_sees_eof(dirs):
    result = make_runner(dirs).run("import sys\nprint(repr(sys.stdin.read()))")
    assert result.ok and result.stdout == "''\n"


# -- bounded root-side post-processing ----------------------------------------------
def _sparse_files_supported(directory: Path) -> bool:
    probe = directory / "sparse-probe"
    with open(probe, "wb") as handle:
        handle.truncate(64 << 20)
    try:
        return os.stat(probe).st_blocks * 512 < (1 << 20)
    finally:
        probe.unlink()


def test_sparse_files_do_not_stall_root_side_processing(dirs, tmp_path):
    if not _sparse_files_supported(tmp_path):
        pytest.skip("filesystem without sparse files")
    code = (
        "for i in range(300):\n"
        "    with open(f'f{i:03d}', 'wb') as handle:\n"
        "        handle.truncate(64 * 1024 * 1024 - 1)\n"
    )
    start = time.monotonic()
    result = make_runner(dirs).run(code)
    elapsed = time.monotonic() - start
    assert result.ok, result.stderr
    # previously every file (~19 GiB of zero pages) was hashed after the run
    assert elapsed - result.duration_s < 5, elapsed
    assert len(result.files) == 100 and result.files_truncated
    hashed = [f for f in result.files if f["sha256"]]
    skipped = [f for f in result.files if f.get("hash_skipped")]
    assert len(hashed) == 1 and len(skipped) == 99
    assert all(f["sha256"] is None for f in skipped)


def test_hashing_stops_at_the_per_call_byte_budget(dirs, monkeypatch):
    monkeypatch.setattr(runner_module, "_MAX_HASH_TOTAL_BYTES", 10)
    result = make_runner(dirs).run(
        "open('a.txt', 'w').write('123456')\nopen('b.txt', 'w').write('123456')\n"
    )
    by_path = {f["path"]: f for f in result.files}
    assert by_path["a.txt"]["sha256"] and "hash_skipped" not in by_path["a.txt"]
    assert by_path["b.txt"] == {
        "path": "b.txt",
        "bytes": 6,
        "sha256": None,
        "change": "created",
        "hash_skipped": True,
    }


def test_walk_is_bounded_by_entries_and_time(tmp_path, monkeypatch):
    for i in range(50):
        (tmp_path / f"f{i:02d}").write_text("x")
    monkeypatch.setattr(runner_module, "_MAX_WALK_ENTRIES", 10)
    entries, truncated = _walk(tmp_path)
    assert len(entries) == 10 and truncated
    monkeypatch.setattr(runner_module, "_MAX_WALK_ENTRIES", 5000)
    entries, truncated = _walk(tmp_path, time_budget_s=-1)
    assert entries == {} and truncated
    entries, truncated = _walk(tmp_path)
    assert len(entries) == 50 and not truncated


def test_incomplete_snapshot_reports_no_false_deletions():
    before = {"a": _Entry("file", 1, 1, 1), "b": _Entry("file", 1, 1, 2)}
    after = {"a": _Entry("file", 2, 2, 1)}
    assert [c["change"] for _, c in _diff(before, after)] == ["modified", "deleted"]
    assert [c["change"] for _, c in _diff(before, after, deletions=False)] == [
        "modified"
    ]


def test_undecodable_filenames_are_listed_as_valid_unicode():
    name = os.fsdecode(b"g\xff")  # how Python names a non-UTF-8 file on Linux
    changes = _diff({}, {name: _Entry("file", 1, 1, 1)})
    path = changes[0][1]["path"]
    assert path == "g\\udcff"
    path.encode("utf-8")  # does not raise
    assert changes[0][0] == name  # the real name is kept for hashing


# -- code that closes its own stdout and stderr -------------------------------------
def test_code_that_closes_stdio_keeps_running(dirs):
    _, scratch = dirs
    start = time.monotonic()
    result = make_runner(dirs).run(
        "import os, time\nos.close(1)\nos.close(2)\ntime.sleep(1)\n"
        "open('done.txt', 'w').write('ok')\n"
    )
    assert result.ok and result.exit_code == 0 and not result.timed_out
    assert result.error_code is None
    assert (scratch / "done.txt").read_text() == "ok"
    assert [f["path"] for f in result.files] == ["done.txt"]
    assert time.monotonic() - start >= 1


def test_code_that_closes_stdio_still_times_out(dirs):
    start = time.monotonic()
    result = make_runner(dirs, timeout_s=1.5).run(
        "import os, time\nos.dup2(os.open(os.devnull, os.O_WRONLY), 1)\n"
        "os.dup2(os.open(os.devnull, os.O_WRONLY), 2)\ntime.sleep(60)\n"
    )
    assert result.timed_out and result.error_code == "TIMEOUT"
    assert time.monotonic() - start < 10
