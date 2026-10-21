"""The image check's evidence-write probe, exercised locally against a read-only tree.

In the container ``incident_checks._runner_checks`` runs the probe as the student
inside a real materialised evidence directory (root-owned, 0555/0444). Here the probe
runs as the tree's OWNER, for whom the mode bits still deny every write except chmod.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from environment import incident_checks
from environment.incident_checks import (
    EVIDENCE_WRITE_ATTEMPTS,
    evidence_write_probe_code,
)


def _read_only_tree(tmp_path: Path) -> tuple[Path, Path]:
    evidence = tmp_path / "evidence"
    scratch = tmp_path / "scratch"
    doc = evidence / "R01"
    doc.mkdir(parents=True)
    scratch.mkdir()
    (doc / "R01.txt").write_text("DOCUMENT R01\n")
    os.chmod(doc / "R01.txt", 0o444)
    os.chmod(doc, 0o555)
    os.chmod(evidence, 0o555)
    return evidence, scratch


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores mode bits")
def test_probe_reports_every_write_attempt(tmp_path: Path):
    evidence, scratch = _read_only_tree(tmp_path)
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", evidence_write_probe_code("R01", "R01.txt")],
            cwd=scratch,
            env={"EVIDENCE_DIR": str(evidence), "PATH": os.environ.get("PATH", "")},
            capture_output=True,
            text=True,
            check=True,
        )
        report = json.loads(result.stdout.strip().splitlines()[-1])
        assert list(report["results"]) == list(EVIDENCE_WRITE_ATTEMPTS)
        owner_may = {"chmod_file", "chmod_doc_dir"}  # the student is not the owner
        assert {
            op: verdict
            for op, verdict in report["results"].items()
            if op not in owner_may
        } == {op: "DENIED" for op in EVIDENCE_WRITE_ATTEMPTS if op not in owner_may}
        assert report["readable"] is True and report["uid"] == os.getuid()
        assert (evidence / "R01" / "R01.txt").read_text() == "DOCUMENT R01\n"
        assert sorted(os.listdir(evidence)) == ["R01"]
    finally:
        for path in (evidence, evidence / "R01"):
            os.chmod(path, stat.S_IRWXU)


def test_probe_detects_a_writable_evidence_dir(tmp_path: Path):
    evidence = tmp_path / "evidence"
    (evidence / "R01").mkdir(parents=True)
    (evidence / "R01" / "R01.txt").write_text("text\n")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    result = subprocess.run(
        [sys.executable, "-I", "-c", evidence_write_probe_code("R01", "R01.txt")],
        cwd=scratch,
        env={"EVIDENCE_DIR": str(evidence), "PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["results"]["create_in_doc_dir"] == "ALLOWED"
    assert report["results"]["mkdir_in_evidence_root"] == "ALLOWED"


def test_check_is_a_no_op_outside_the_container(monkeypatch):
    monkeypatch.delenv("KAROTTE_CONTAINERIZED", raising=False)

    def fail():
        raise AssertionError("must not run outside the container")

    monkeypatch.setattr(incident_checks, "_bash_checks", fail)
    monkeypatch.setattr(incident_checks, "_runner_checks", fail)
    incident_checks.check()


# -- both tasks' bundles are covered (system response included) -------------------------
def test_protected_paths_cover_both_bundles_and_private_dirs():
    from environment.incident.paths import (
        DEFAULT_BUNDLE_DIR,
        DEFAULT_PRIVATE_DIR,
        SYSTEM_RESPONSE_BUNDLE_DIR,
        SYSTEM_RESPONSE_PRIVATE_DIR,
    )

    directories, files = incident_checks.protected_paths()
    for folder in (
        DEFAULT_BUNDLE_DIR,
        DEFAULT_PRIVATE_DIR,
        SYSTEM_RESPONSE_BUNDLE_DIR,
        SYSTEM_RESPONSE_BUNDLE_DIR / "logs" / "assets",
        SYSTEM_RESPONSE_BUNDLE_DIR / "logs" / "control",
        SYSTEM_RESPONSE_BUNDLE_DIR / "witnesses",
        SYSTEM_RESPONSE_PRIVATE_DIR,
    ):
        assert folder in directories, folder
    names = {(p.parent.name, p.name) for p in files}
    assert ("system_response", "manifest.json") in names
    assert ("system_response", "provenance.json") in names
    assert any(p.parent.name == "assets" and p.suffix == ".jsonl" for p in files)
    assert any(p.parent.name == "control" and p.suffix == ".jsonl" for p in files)
    assert any(p.parent.name == "witnesses" and p.suffix == ".json" for p in files)
    assert all(p.exists() for p in (*directories, *files))


def test_bash_script_and_python_probe_name_every_protected_path():
    import shlex

    directories, files = incident_checks.protected_paths()
    script = incident_checks.bash_check_script()
    for path in (*directories, *files):
        assert shlex.quote(str(path)) in script, path
    targets = incident_checks.probe_targets()
    code = incident_checks.private_path_probe_code(targets)
    compile(code, "probe", "exec")
    for path in (*directories, *files):
        assert str(path) in targets


def test_runner_checks_drive_both_tasks():
    from environment.tasks.gb_2019_electrical_disturbance import IncidentToolConfig
    from environment.tasks.gb_2019_system_response import SystemResponseToolConfig

    configs = dict(incident_checks.task_tool_configs())
    assert configs == {
        "gb-2019-electrical-disturbance": IncidentToolConfig,
        "gb-2019-system-response": SystemResponseToolConfig,
    }


def test_check_loads_both_shipped_bundles(monkeypatch):
    monkeypatch.setenv("KAROTTE_CONTAINERIZED", "1")
    calls = []
    monkeypatch.setattr(incident_checks, "_bash_checks", lambda: calls.append("bash"))
    monkeypatch.setattr(
        incident_checks, "_runner_checks", lambda: calls.append("runner")
    )
    incident_checks.check()
    assert calls == ["bash", "runner"]
    from environment.incident.catalogue import Catalogue

    assert incident_checks.load_shipped_bundles() == [
        Catalogue.load().bundle_id,
        "gb-2019-08-09-system-response",
    ]


def test_check_fails_closed_on_a_broken_system_response_bundle(monkeypatch, tmp_path):
    import shutil as _shutil

    from environment.incident import paths
    from environment.incident.catalogue import CatalogueError

    broken = tmp_path / "system_response"
    _shutil.copytree(paths.SYSTEM_RESPONSE_BUNDLE_DIR, broken)
    card = next((broken / "witnesses").iterdir())
    card.write_text(card.read_text(encoding="utf-8") + " ", encoding="utf-8")
    monkeypatch.setattr(paths, "SYSTEM_RESPONSE_BUNDLE_DIR", broken)
    with pytest.raises(CatalogueError):
        incident_checks.load_shipped_bundles()
