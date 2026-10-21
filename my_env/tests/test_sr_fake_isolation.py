"""Container checks for the system-response task (environment.incident_checks).

The checks run only in the container (``karotte check``), as the student. Here: the
protected paths name every system-response document directory (including the
data-return-only S05/S06), the key, checklist and provenance files; the image check
drives the system-response materialisation check; and that check's report, taken on a
local episode (development mode: the student is the current user, so private paths are
readable here by design), shows that log queries and witness answers materialise nothing
and that only obtained documents appear in the evidence directory.
"""

from __future__ import annotations

import shlex
from pathlib import Path

import pytest
from sr_grading_support import episode_config

from environment import incident_checks
from environment.incident.episode import Episode
from environment.incident.paths import (
    SYSTEM_RESPONSE_BUNDLE_DIR,
    SYSTEM_RESPONSE_PRIVATE_DIR,
)


def test_protected_paths_cover_every_system_response_path():
    directories, files = incident_checks.protected_paths()
    sr = SYSTEM_RESPONSE_BUNDLE_DIR
    for name in ("R01", "R02", "R05", "R07", "S05", "S06", "S07", "S12"):
        assert sr / name in directories, name
    for folder in (sr / "logs" / "assets", sr / "logs" / "control", sr / "witnesses"):
        assert folder in directories
    assert SYSTEM_RESPONSE_PRIVATE_DIR in directories
    for name in incident_checks.SR_PRIVATE_FILES:
        assert SYSTEM_RESPONSE_PRIVATE_DIR / name in files, name
    assert sr / "S05" / "S05.txt" in files and sr / "S06" / "S06.txt" in files
    assert all(p.exists() for p in (*directories, *files))
    script = incident_checks.bash_check_script()
    targets = incident_checks.probe_targets()
    for path in (*directories, *files):
        assert shlex.quote(str(path)) in script, path
        assert str(path) in targets, path


def test_runner_checks_include_the_materialisation_check(monkeypatch):
    calls = []
    monkeypatch.setattr(
        incident_checks, "_episode_checks", lambda task_id, cls: calls.append(task_id)
    )
    monkeypatch.setattr(
        incident_checks, "_sr_materialisation_checks", lambda: calls.append("sr")
    )
    incident_checks._runner_checks()
    assert calls == ["gb-2019-electrical-disturbance", "gb-2019-system-response", "sr"]


def test_unobtained_targets_name_the_key_logs_and_the_unrequested_return():
    targets = incident_checks.sr_unobtained_targets(
        SYSTEM_RESPONSE_BUNDLE_DIR, SYSTEM_RESPONSE_PRIVATE_DIR
    )
    assert str(SYSTEM_RESPONSE_BUNDLE_DIR / "S06" / "S06.txt") in targets
    assert str(SYSTEM_RESPONSE_PRIVATE_DIR / "answer_key.json") in targets
    assert str(SYSTEM_RESPONSE_BUNDLE_DIR / "witnesses") in targets
    code = incident_checks.materialisation_probe_code(["S05/S05.txt"], targets)
    compile(code, "materialisation-probe", "exec")


def test_materialisation_report_on_a_local_episode(tmp_path: Path):
    episode = Episode(episode_config(tmp_path))
    episode.reset()
    report = incident_checks.sr_materialisation_report(episode)
    assert report["after_reset"] == []
    assert report["after_queries"] == []  # log rows and witness answers: no files
    assert report["obtained"] == report["after_obtaining"] == ["R01", "S05"]
    python = report["python"]
    assert python["listing"] == ["R01", "S05"]
    assert python["readable"] == {
        "R01/frequency_2019-08-09_1640-1745_BST.csv": True,
        "S05/S05.txt": True,
    }
    assert set(python["denied"]) == set(
        incident_checks.sr_unobtained_targets(
            SYSTEM_RESPONSE_BUNDLE_DIR, SYSTEM_RESPONSE_PRIVATE_DIR
        )
    )
    assert list(report["write"]["results"]) == list(
        incident_checks.EVIDENCE_WRITE_ATTEMPTS
    )
    assert report["calls"] == [
        "query_asset_log",
        "query_control_log",
        "interview_witness",
        "request_data_return",
        "query_frequency",
    ]


@pytest.mark.parametrize(
    "broken,message",
    [
        ({"after_queries": ["logs"]}, "log queries or witness answers materialised"),
        ({"after_obtaining": ["R01", "S05", "S06"]}, "'S06'"),
        ({"python": {"listing": ["R01", "S05", "S06"]}}, "'S06'"),
        ({"python": {"uid": 0}}, "run_python ran as uid 0"),
        ({"python": {"denied": {"/x": "READABLE"}}}, "can read unobtained or private"),
        (
            {"write": {"results": {"unlink_file": "ALLOWED"}}},
            "can modify a data return",
        ),
    ],
)
def test_materialisation_check_fails_closed(monkeypatch, broken, message):
    """The container assertion accepts a clean report and rejects each kind of leak
    (the report is patched here; the real one is taken above)."""
    import environment.tasks.gb_2019_electrical_disturbance as mvp_task

    good = {
        "after_reset": [],
        "after_queries": [],
        "obtained": ["R01", "S05"],
        "after_obtaining": ["R01", "S05"],
        "python": {
            "uid": 1000,
            "listing": ["R01", "S05"],
            "readable": {"S05/S05.txt": True},
            "denied": {"/x": "DENIED"},
        },
        "write": {"results": {"unlink_file": "DENIED"}},
    }

    def bad_report(episode):
        report = dict(good)
        for name, value in broken.items():
            report[name] = {**good[name], **value} if isinstance(value, dict) else value
        return report

    class FakeEpisode:
        def reset(self):
            return {"network_mode": "namespace"}

    monkeypatch.setattr(mvp_task, "make_episode", lambda config: FakeEpisode())
    monkeypatch.setattr("environment.STUDENT_UID", 1000)
    monkeypatch.setattr(incident_checks, "sr_materialisation_report", lambda e: good)
    incident_checks._sr_materialisation_checks()
    monkeypatch.setattr(incident_checks, "sr_materialisation_report", bad_report)
    with pytest.raises(AssertionError, match=message):
        incident_checks._sr_materialisation_checks()
