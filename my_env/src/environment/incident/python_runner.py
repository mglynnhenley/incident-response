"""Sandboxed execution of agent-supplied Python (the ``run_python`` tool).

The code is fed on stdin to ``python -I -B -X utf8 -`` with ``cwd`` = the scratch
directory and a minimal environment (``EVIDENCE_DIR``, ``SCRATCH_DIR``, ``HOME`` =
scratch, ``LANG``, ``TZ``, single-thread BLAS variables). Nothing else is inherited, so
harness credentials never reach the child.

Isolation is injected by the caller:

* ``launcher(argv) -> (argv, preexec)`` wraps the command. The Karotte adapter passes
  ``karotte.subprocess.student_session_command(argv, 0, 1, 2, disable_networking=...)``
  in the container (run as the unprivileged student, in its own network namespace where
  the sandbox allows one). The default identity launcher is local development mode:
  isolation is NOT enforced, and ``limits`` says so.
* ``network_mode`` (a string or a callable returning one) says how the network is cut
  off, and is reported in ``limits``: ``namespace`` (own network namespace, no
  interfaces), ``karotte_firewall`` (no namespace could be created; only the sandbox's
  student firewall restricts the network) or ``not_isolated`` (development mode).
* ``cleanup()`` runs after every execution (the adapter passes
  ``karotte.kill_processes(STUDENT_UID)``), so nothing the code started survives the
  call. If it fails, the call fails closed: it is reported as ``INTERNAL_ERROR``, the
  scratch directory is not inspected beside processes that may still be alive, and the
  failure is returned in ``cleanup_error`` (the episode records it and runs the cleanup
  again before the next execution).

Resource limits are applied in the child's ``preexec`` BEFORE the launcher's preexec
(which drops privileges): ``RLIMIT_AS`` (memory, Linux only — macOS cannot lower it),
``RLIMIT_CORE`` = 0 and ``RLIMIT_FSIZE``. The wall-clock timeout kills the whole process
group; code that closes its stdout and stderr keeps running until it exits or the
timeout. stdout and stderr are drained concurrently and capped in memory; anything
beyond ``max_output_chars`` is replaced by an explicit truncation notice.

Root-side work after a run is bounded: the scratch directory walk stops after
``_MAX_WALK_ENTRIES`` entries, ``_MAX_WALK_DEPTH`` levels or ``_WALK_TIME_BUDGET_S``
seconds, and only the listed files are hashed, up to ``_MAX_HASH_TOTAL_BYTES`` in total
per call (beyond that ``sha256`` is null and ``hash_skipped`` is true).
"""

from __future__ import annotations

import hashlib
import os
import resource
import selectors
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

__all__ = [
    "Cleanup",
    "Launcher",
    "NETWORK_FIREWALL",
    "NETWORK_NAMESPACE",
    "NETWORK_NOT_ISOLATED",
    "PythonRunResult",
    "PythonRunner",
    "identity_launcher",
    "minimal_env",
]

Preexec = Callable[[], None]
Launcher = Callable[[list[str]], tuple[list[str], Preexec | None]]
Cleanup = Callable[[], None]
NetworkMode = str | Callable[[], str] | None

DEFAULT_TIMEOUT_S = 30.0
DEFAULT_MEMORY_BYTES = 1 << 30
DEFAULT_FILE_SIZE_BYTES = 64 << 20
DEFAULT_MAX_OUTPUT_CHARS = 20_000

NETWORK_NAMESPACE = "namespace"
NETWORK_FIREWALL = "karotte_firewall"
NETWORK_NOT_ISOLATED = "not_isolated"
NETWORK_UNREPORTED = "unreported"

_DRAIN_GRACE_S = 2.0
_MAX_LISTED_FILES = 100
_MAX_WALK_ENTRIES = 5_000
_MAX_WALK_DEPTH = 8
_WALK_TIME_BUDGET_S = 2.0
_MAX_HASHED_FILES = _MAX_LISTED_FILES
_MAX_HASH_TOTAL_BYTES = 64 << 20
_HASH_TIME_BUDGET_S = 2.0

THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}


def identity_launcher(argv: list[str]) -> tuple[list[str], Preexec | None]:
    """Local development launcher: run the command as-is (no isolation)."""
    return list(argv), None


def minimal_env(python_executable: str, evidence_dir: Path, scratch_dir: Path) -> dict:
    """The complete environment of the child process (nothing is inherited)."""
    path_dirs = [
        str(Path(python_executable).parent),
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
    ]
    return {
        "EVIDENCE_DIR": str(evidence_dir),
        "SCRATCH_DIR": str(scratch_dir),
        "HOME": str(scratch_dir),
        "LANG": "C.UTF-8",
        "TZ": "UTC",
        "PATH": os.pathsep.join(dict.fromkeys(path_dirs)),
        "MALLOC_ARENA_MAX": "2",
        "MPLBACKEND": "Agg",
        **THREAD_ENV,
    }


@dataclass
class PythonRunResult:
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    stdout_bytes: int
    stderr_bytes: int
    duration_s: float
    files: list[dict[str, Any]] = field(default_factory=list)
    files_truncated: bool = False
    limits: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    notes: list[str] = field(default_factory=list)
    cleanup_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error_code is None


class _Entry(NamedTuple):
    kind: str
    size: int
    mtime_ns: int
    ino: int


def _kind(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "dir"
    if stat.S_ISLNK(mode):
        return "symlink"
    return "other"


def display_path(rel: str) -> str:
    """``rel`` as valid Unicode: undecodable filename bytes (which Python holds as
    lone surrogates) are shown as ``\\udcXX`` escapes."""
    try:
        rel.encode("utf-8")
    except UnicodeEncodeError:
        return rel.encode("utf-8", "backslashreplace").decode("utf-8")
    return rel


def _walk(
    root: Path, *, time_budget_s: float = _WALK_TIME_BUDGET_S
) -> tuple[dict[str, _Entry], bool]:
    """Snapshot ``root`` (metadata only) without following symlinks; dir-fd based.

    Bounded by ``_MAX_WALK_ENTRIES`` entries (also per directory listing, so a huge
    directory is never read in full), ``_MAX_WALK_DEPTH`` levels and ``time_budget_s``.
    Returns ``(entries, truncated)``; ``truncated`` means the snapshot is incomplete.
    """
    deadline = time.monotonic() + time_budget_s
    entries: dict[str, _Entry] = {}
    truncated = False
    stopped = False
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    stack: list[tuple[int, str, int]] = [(root_fd, "", 0)]
    try:
        while stack and not stopped:
            dir_fd, prefix, depth = stack.pop()
            try:
                children = []
                with os.scandir(dir_fd) as listing:
                    for child in listing:
                        if len(entries) + len(children) >= _MAX_WALK_ENTRIES:
                            stopped = True
                            break
                        children.append(child)
                children.sort(key=lambda e: e.name)
                for child in children:
                    if time.monotonic() > deadline:
                        stopped = True
                        break
                    rel = f"{prefix}{child.name}"
                    try:
                        info = child.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    kind = _kind(info.st_mode)
                    entries[rel] = _Entry(
                        kind, info.st_size, info.st_mtime_ns, info.st_ino
                    )
                    if kind != "dir":
                        continue
                    if depth + 1 >= _MAX_WALK_DEPTH:
                        truncated = True
                        continue
                    try:
                        sub_fd = os.open(
                            child.name,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=dir_fd,
                        )
                    except OSError:
                        continue
                    stack.append((sub_fd, f"{rel}/", depth + 1))
            finally:
                if dir_fd != root_fd:
                    os.close(dir_fd)
    finally:
        for leftover_fd, _, _ in stack:
            if leftover_fd != root_fd:
                os.close(leftover_fd)
        os.close(root_fd)
    return entries, truncated or stopped


def _diff(
    before: dict[str, _Entry], after: dict[str, _Entry], *, deletions: bool = True
) -> list[tuple[str, dict[str, Any]]]:
    """``(rel, change)`` pairs for every non-directory that changed, by path.

    ``deletions=False`` (when ``after`` is incomplete) leaves out entries that are
    merely absent from ``after``. ``sha256`` is filled in later (``_hash_listed``).
    """
    changes: list[tuple[str, dict[str, Any]]] = []
    for rel in sorted(set(before) | set(after)):
        old, new = before.get(rel), after.get(rel)
        if (new is not None and new.kind == "dir") or (
            new is None and old is not None and old.kind == "dir"
        ):
            continue
        if new is None:
            if not deletions:
                continue
            change = "deleted"
        elif old is None:
            change = "created"
        elif old != new:
            change = "modified"
        else:
            continue
        entry: dict[str, Any] = {
            "path": display_path(rel),
            "bytes": new.size if new is not None and new.kind == "file" else None,
            "sha256": None,
            "change": change,
        }
        kind = (new or old).kind  # type: ignore[union-attr]
        if kind != "file":
            entry["type"] = kind
        changes.append((rel, entry))
    return changes


def _open_file_beneath(root_fd: int, rel: str) -> int:
    """Open ``root/rel`` read-only, refusing a symlink at every component."""
    parts = rel.split("/")
    opened: list[int] = []
    try:
        dir_fd = root_fd
        for part in parts[:-1]:
            dir_fd = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd
            )
            opened.append(dir_fd)
        return os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd
        )
    finally:
        for fd in opened:
            os.close(fd)


def _hash_file(root_fd: int, rel: str, expected: _Entry) -> str | None:
    """SHA-256 of the regular file ``rel`` if it is still the file in ``expected``."""
    try:
        fd = _open_file_beneath(root_fd, rel)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or (
            info.st_size,
            info.st_mtime_ns,
            info.st_ino,
        ) != (expected.size, expected.mtime_ns, expected.ino):
            return None
        digest = hashlib.sha256()
        remaining = expected.size
        while remaining > 0:
            chunk = os.read(fd, min(remaining, 1 << 20))
            if not chunk:
                return None
            digest.update(chunk)
            remaining -= len(chunk)
        return digest.hexdigest()
    except OSError:
        return None
    finally:
        os.close(fd)


def _hash_listed(
    root: Path, listed: list[tuple[str, dict[str, Any]]], after: dict[str, _Entry]
) -> None:
    """Fill in ``sha256`` for listed regular files within the per-call hash budget;
    files past the budget (or that cannot be read safely) get ``hash_skipped``."""
    budget = _MAX_HASH_TOTAL_BYTES
    hashed = 0
    deadline = time.monotonic() + _HASH_TIME_BUDGET_S
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for rel, entry in listed:
            new = after.get(rel)
            if entry["change"] == "deleted" or new is None or new.kind != "file":
                continue
            digest = None
            if (
                hashed < _MAX_HASHED_FILES
                and new.size <= budget
                and time.monotonic() < deadline
            ):
                digest = _hash_file(root_fd, rel, new)
            if digest is None:
                entry["hash_skipped"] = True
                continue
            entry["sha256"] = digest
            hashed += 1
            budget -= new.size
    finally:
        os.close(root_fd)


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


class PythonRunner:
    """Runs agent code in a fresh interpreter with limits; see the module docstring."""

    def __init__(
        self,
        *,
        python_executable: str,
        evidence_dir: Path,
        scratch_dir: Path,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        memory_bytes: int = DEFAULT_MEMORY_BYTES,
        file_size_bytes: int = DEFAULT_FILE_SIZE_BYTES,
        max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
        launcher: Launcher | None = None,
        cleanup: Cleanup | None = None,
        isolated: bool = False,
        network_mode: NetworkMode = None,
    ) -> None:
        self.python_executable = python_executable
        self.evidence_dir = Path(evidence_dir)
        self.scratch_dir = Path(scratch_dir)
        self.timeout_s = float(timeout_s)
        self.memory_bytes = int(memory_bytes)
        self.file_size_bytes = int(file_size_bytes)
        self.max_output_chars = int(max_output_chars)
        self.launcher: Launcher = launcher or identity_launcher
        self.cleanup = cleanup
        self.isolated = isolated
        self._network_mode = network_mode
        # macOS refuses to lower RLIMIT_AS below the (huge) current mapping size.
        self.memory_limit_enforced = sys.platform.startswith("linux")

    # -- description -----------------------------------------------------------
    def network_mode(self) -> str:
        """How the child's network is cut off (see the module docstring)."""
        mode: Any = self._network_mode
        if callable(mode):
            try:
                mode = mode()
            except Exception:  # noqa: BLE001 - reported, never guessed
                mode = NETWORK_UNREPORTED
        if mode is None:
            mode = NETWORK_UNREPORTED if self.isolated else NETWORK_NOT_ISOLATED
        return str(mode)

    def limits(self) -> dict[str, Any]:
        """Deterministic description of the limits that apply to every call."""
        network = self.network_mode()
        if not self.isolated:
            isolation = (
                "NOT enforced: local development mode (no user switch, network "
                "not disabled)"
            )
        elif network == NETWORK_NAMESPACE:
            isolation = (
                "enforced: runs as the unprivileged student user without network "
                "access (own network namespace)"
            )
        elif network == NETWORK_FIREWALL:
            isolation = (
                "enforced: runs as the unprivileged student user; no network namespace "
                "could be created, so network access is restricted only by the "
                "sandbox's student firewall"
            )
        else:
            isolation = (
                "enforced: runs as the unprivileged student user (network isolation "
                f"{network})"
            )
        return {
            "wall_timeout_s": self.timeout_s,
            "memory_bytes": self.memory_bytes,
            "memory_limit_enforced": self.memory_limit_enforced,
            "file_size_bytes": self.file_size_bytes,
            "max_output_chars": self.max_output_chars,
            "isolation": isolation,
            "network": network,
        }

    def build_env(self) -> dict[str, str]:
        return minimal_env(self.python_executable, self.evidence_dir, self.scratch_dir)

    def _make_preexec(self, launcher_preexec: Preexec | None) -> Preexec:
        memory = self.memory_bytes
        fsize = self.file_size_bytes
        limit_memory = self.memory_limit_enforced
        set_limit = resource.setrlimit
        rlimit_as, rlimit_core, rlimit_fsize = (
            resource.RLIMIT_AS,
            resource.RLIMIT_CORE,
            resource.RLIMIT_FSIZE,
        )
        setsid = os.setsid

        def _preexec() -> None:
            # Limits first, while still privileged; the launcher's preexec then drops
            # to the student, who can no longer raise them.
            if limit_memory:
                set_limit(rlimit_as, (memory, memory))
            set_limit(rlimit_core, (0, 0))
            set_limit(rlimit_fsize, (fsize, fsize))
            if launcher_preexec is not None:
                launcher_preexec()  # Karotte's preexec calls setsid() itself.
            else:
                setsid()

        return _preexec

    # -- execution -------------------------------------------------------------
    def _not_run(
        self,
        start: float,
        notes: list[str],
        message: str,
        cleanup_error: str | None = None,
    ) -> PythonRunResult:
        return PythonRunResult(
            exit_code=None,
            timed_out=False,
            stdout="",
            stderr="",
            stdout_truncated=False,
            stderr_truncated=False,
            stdout_bytes=0,
            stderr_bytes=0,
            duration_s=round(time.monotonic() - start, 3),
            limits=self.limits(),
            error_code="INTERNAL_ERROR",
            error_message=message,
            notes=notes,
            cleanup_error=cleanup_error,
        )

    def run(self, code: str, *, precleanup: bool = False) -> PythonRunResult:
        """Execute ``code``. ``precleanup`` first runs the cleanup hook (after an
        earlier cleanup failed) and refuses to run the code if it fails again."""
        code_bytes = code.encode("utf-8", errors="replace")
        argv = [self.python_executable, "-I", "-B", "-X", "utf8", "-"]
        notes: list[str] = []
        start = time.monotonic()
        if precleanup:
            failure = self._run_cleanup()
            if failure is not None:
                notes.append(f"cleanup failed: {failure}")
                return self._not_run(
                    start,
                    notes,
                    "Processes left by an earlier run_python call could not be "
                    "stopped, so this code was not run.",
                    failure,
                )
        before: dict[str, _Entry] = {}
        before_truncated = False
        try:
            before, before_truncated = _walk(self.scratch_dir)
        except OSError as exc:
            notes.append(f"scratch snapshot unavailable: {exc}")

        start = time.monotonic()
        try:
            launched_argv, launcher_preexec = self.launcher(argv)
            proc = subprocess.Popen(
                launched_argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.scratch_dir,
                env=self.build_env(),
                preexec_fn=self._make_preexec(launcher_preexec),
                close_fds=True,
            )
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            failure = self._run_cleanup()
            if failure is not None:
                notes.append(f"cleanup failed: {failure}")
            return self._not_run(
                start,
                notes,
                f"could not start Python: {type(exc).__name__}: {exc}",
                failure,
            )

        cleanup_error: str | None = None
        try:
            out, out_total, err, err_total, timed_out = self._communicate(
                proc, code_bytes, start + self.timeout_s
            )
        finally:
            if proc.poll() is None:
                _kill_group(proc.pid)
                proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                notes.append("the Python process could not be reaped")
            cleanup_error = self._run_cleanup()
        duration = round(time.monotonic() - start, 3)

        stdout, stdout_truncated = self._finish(out, out_total, "stdout")
        stderr, stderr_truncated = self._finish(err, err_total, "stderr")

        files: list[dict[str, Any]] = []
        files_truncated = False
        if cleanup_error is not None:
            notes.append(f"cleanup failed: {cleanup_error}")
            notes.append(
                "files not listed: processes started by this code may still be running"
            )
        else:
            try:
                after, after_truncated = _walk(self.scratch_dir)
                changes = _diff(before, after, deletions=not after_truncated)
                listed = changes[:_MAX_LISTED_FILES]
                _hash_listed(self.scratch_dir, listed, after)
                files = [entry for _, entry in listed]
                files_truncated = (
                    before_truncated
                    or after_truncated
                    or len(changes) > _MAX_LISTED_FILES
                )
            except OSError as exc:
                notes.append(f"file listing unavailable: {exc}")

        exit_code = proc.returncode
        error_code, error_message = self._classify(exit_code, timed_out, err)
        if cleanup_error is not None:
            error_code = "INTERNAL_ERROR"
            error_message = (
                "The environment could not confirm that every process started by this "
                "code has stopped, so the call is reported as failed (Python exited "
                f"with status {exit_code}{', after the time limit' if timed_out else ''}"
                "). Do not leave processes running in the background."
            )
        return PythonRunResult(
            exit_code=exit_code,
            timed_out=timed_out,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            stdout_bytes=out_total,
            stderr_bytes=err_total,
            duration_s=duration,
            files=files,
            files_truncated=files_truncated,
            limits=self.limits(),
            error_code=error_code,
            error_message=error_message,
            notes=notes,
            cleanup_error=cleanup_error,
        )

    def _run_cleanup(self) -> str | None:
        """Run the cleanup hook; return the failure as text (None on success)."""
        if self.cleanup is None:
            return None
        try:
            self.cleanup()
        except Exception as exc:  # noqa: BLE001 - fails the call closed (see run)
            return display_path(f"{type(exc).__name__}: {exc}")
        return None

    def _communicate(
        self, proc: subprocess.Popen, code: bytes, deadline: float
    ) -> tuple[bytes, int, bytes, int, bool]:
        keep = self.max_output_chars * 4 + 16
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        totals = {"stdout": 0, "stderr": 0}
        assert proc.stdin and proc.stdout and proc.stderr
        streams = {proc.stdout.fileno(): "stdout", proc.stderr.fileno(): "stderr"}
        stdin_fd = proc.stdin.fileno()
        pending = memoryview(code)

        selector = selectors.DefaultSelector()
        for fd in (*streams, stdin_fd):
            os.set_blocking(fd, False)
        for fd in streams:
            selector.register(fd, selectors.EVENT_READ)
        stdin_open = True
        if pending:
            selector.register(stdin_fd, selectors.EVENT_WRITE)
        else:
            proc.stdin.close()
            stdin_open = False

        timed_out = False
        ended_at: float | None = None
        try:
            while True:
                now = time.monotonic()
                if ended_at is None:
                    if proc.poll() is not None:
                        # Main process finished: stop its leftovers, then drain.
                        _kill_group(proc.pid)
                        ended_at = now
                    elif now >= deadline:
                        timed_out = True
                        _kill_group(proc.pid)
                        ended_at = now
                registered = selector.get_map()
                streams_open = any(fd in registered for fd in streams)
                if ended_at is not None and (
                    not streams_open or now - ended_at > _DRAIN_GRACE_S
                ):
                    break  # drained, or something outside the group holds the pipes
                wait = (
                    0.05 if ended_at is not None else min(0.2, max(0.0, deadline - now))
                )
                if not registered:
                    # The code closed stdout and stderr but is still running: let it
                    # finish (or reach the time limit) instead of killing it early.
                    try:
                        proc.wait(timeout=wait)
                    except subprocess.TimeoutExpired:
                        pass
                    continue
                for key, _ in selector.select(wait):
                    fd = key.fd
                    if fd == stdin_fd:
                        try:
                            written = os.write(fd, pending[:65536])
                            pending = pending[written:]
                        except BlockingIOError:
                            continue
                        except OSError:
                            pending = pending[:0]
                        if not pending:
                            selector.unregister(fd)
                            proc.stdin.close()
                            stdin_open = False
                        continue
                    name = streams[fd]
                    try:
                        chunk = os.read(fd, 65536)
                    except BlockingIOError:
                        continue
                    except OSError:
                        chunk = b""
                    if not chunk:
                        selector.unregister(fd)
                        continue
                    totals[name] += len(chunk)
                    room = keep - len(buffers[name])
                    if room > 0:
                        buffers[name] += chunk[:room]
        finally:
            selector.close()
            if stdin_open:
                try:
                    proc.stdin.close()
                except OSError:
                    pass
            for handle in (proc.stdout, proc.stderr):
                try:
                    handle.close()
                except OSError:
                    pass
        return (
            bytes(buffers["stdout"]),
            totals["stdout"],
            bytes(buffers["stderr"]),
            totals["stderr"],
            timed_out,
        )

    def _finish(self, data: bytes, total: int, name: str) -> tuple[str, bool]:
        text = data.decode("utf-8", errors="replace")
        truncated = total > len(data) or len(text) > self.max_output_chars
        if truncated:
            text = text[: self.max_output_chars] + (
                f"\n[... {name} truncated by the environment: showing the first "
                f"{self.max_output_chars} characters of {total} bytes ...]"
            )
        return text, truncated

    def _classify(
        self, exit_code: int | None, timed_out: bool, stderr: bytes
    ) -> tuple[str | None, str | None]:
        """Error code for a finished run.

        The environment only SIGKILLs a still-running main process when the wall
        clock runs out (``timed_out``; also when its stdout and stderr are closed, it
        is left to run until then), so a SIGKILL exit without a timeout came from
        elsewhere — in practice the kernel's out-of-memory killer.
        """
        if timed_out:
            return (
                "TIMEOUT",
                f"Python exceeded the {self.timeout_s:g} s wall-clock limit and was "
                "killed; output produced before that is shown.",
            )
        if exit_code == 0:
            return None, None
        tail = stderr[-4000:].decode("utf-8", errors="replace")
        resource_signals = {-signal.SIGKILL}
        if hasattr(signal, "SIGXFSZ"):
            resource_signals.add(-signal.SIGXFSZ)
        if (
            exit_code in resource_signals
            or "MemoryError" in tail
            or "File too large" in tail
        ):
            return (
                "RESOURCE_LIMIT",
                "Python hit a resource limit (memory "
                f"{self.memory_bytes} bytes, file size {self.file_size_bytes} bytes) "
                f"and exited with status {exit_code}.",
            )
        return "PYTHON_ERROR", f"Python exited with status {exit_code}; see stderr."
