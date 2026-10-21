"""Image checks for the GB 2019 incident task, run by ``karotte check``.

``environment.check_permissions`` discovers every ``environment.*_checks`` module and
calls its ``check()`` during the image build. The checks only make sense inside the
container (they need ``runuser`` and the student account), so ``check()`` returns
immediately elsewhere.

Both shipped bundles must load and verify: the frozen MVP bundle and the system-response
bundle (``bundles/system_response``, task ``gb-2019-system-response``).

As the student (``runuser``), assert that:
* neither evidence bundle (manifests, documents, the system-response asset/control logs,
  witness cards, every document directory including the data-return-only S05/S06) nor
  either private grading directory (including the system-response key, review checklist
  and every provenance file) can be read or listed;
* ``ROOT_DATA_DIR`` (which holds the episode ledger) cannot be listed;
* the student venv imports numpy and pandas;
* the evidence directory is absent or a root-owned directory the student cannot write.

Then, for each task's tool configuration (MVP ``IncidentToolConfig`` and
``SystemResponseToolConfig``), drive a real episode (student launcher + cleanup) in a
temporary directory: materialise a document with ``request_document`` and, through
``run_python``, assert that the code runs as the student, cannot read any bundle, private
or episode path above, and cannot write, create, delete, replace, rename, symlink or
chmod anything in the materialised evidence directory (whose copy stays intact).

Then, in a fresh system-response episode (:func:`sr_materialisation_report`): log
queries and witness answers write nothing under the evidence directory; a data return
(S05) and ``query_frequency`` (R01) materialise exactly those documents; through
``run_python`` the student sees exactly what was obtained, can read it, cannot modify the
data return, and still cannot read the unrequested data return (S06), the logs, the
witness cards, the key or the provenance files.

The full investigation (task ``gb-2019-full-investigation``, increment B): its bundle
and private directories (every subdirectory, the manifest, the data-return-only documents
and every private file) are part of :func:`protected_paths` whenever they exist, so the
bash check above and every task's ``run_python`` probe cover them. Its runner checks
(:func:`full_investigation_checks`: the bundle must load and verify, fail closed; its
episode is driven like the others; the materialisation checks run on it, extended to
every data-return-only document of its manifest and every file of
``private/full_investigation``) are run by the separate image-check module
``environment.incident_fi_checks``, so that this module's ``check()`` keeps increment A's
behaviour.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

# Every attempt must fail with OSError for the student. The chmods come last: as the
# OWNER (a local, non-root test) they succeed and would unlock what follows.
EVIDENCE_WRITE_ATTEMPTS = (
    "overwrite_file",
    "append_file",
    "create_in_doc_dir",
    "create_in_evidence_root",
    "unlink_file",
    "replace_file",
    "rename_file",
    "rename_doc_dir",
    "symlink_in_doc_dir",
    "symlink_in_evidence_root",
    "mkdir_in_evidence_root",
    "chmod_file",
    "chmod_doc_dir",
)


def evidence_write_probe_code(doc_id: str, file_name: str) -> str:
    """Python (run in ``run_python``) that tries to modify ``EVIDENCE_DIR/doc_id`` and
    prints ``{"uid", "results": {attempt: "DENIED"|"ALLOWED"}, "readable"}``."""
    return f"""\
import json, os
doc_id, name = {json.dumps(doc_id)}, {json.dumps(file_name)}
root = os.environ["EVIDENCE_DIR"]
doc = os.path.join(root, doc_id)
target = os.path.join(doc, name)
with open("decoy.txt", "w") as handle:
    handle.write("decoy")
decoy = os.path.join(os.getcwd(), "decoy.txt")
try:
    with open(target, "rb") as handle:
        readable = bool(handle.read(64))
except OSError:
    readable = False
attempts = {{
    "overwrite_file": lambda: open(target, "r+b").close(),
    "append_file": lambda: open(target, "ab").close(),
    "create_in_doc_dir": lambda: open(os.path.join(doc, "new.txt"), "x").close(),
    "create_in_evidence_root": lambda: open(os.path.join(root, "new.txt"), "x").close(),
    "unlink_file": lambda: os.unlink(target),
    "replace_file": lambda: os.replace(decoy, target),
    "rename_file": lambda: os.rename(target, os.path.join(doc, "moved.txt")),
    "rename_doc_dir": lambda: os.rename(doc, os.path.join(root, "moved")),
    "symlink_in_doc_dir": lambda: os.symlink("/etc/hostname", os.path.join(doc, "l")),
    "symlink_in_evidence_root": lambda: os.symlink("/etc", os.path.join(root, "l")),
    "mkdir_in_evidence_root": lambda: os.mkdir(os.path.join(root, "newdir")),
    "chmod_file": lambda: os.chmod(target, 0o666),
    "chmod_doc_dir": lambda: os.chmod(doc, 0o777),
}}
assert list(attempts) == {json.dumps(list(EVIDENCE_WRITE_ATTEMPTS))}
results = {{}}
for attempt, action in attempts.items():
    try:
        action()
        results[attempt] = "ALLOWED"
    except OSError:
        results[attempt] = "DENIED"
print(json.dumps({{"uid": os.getuid(), "results": results, "readable": readable}}))
"""


#: Files the system-response checks name explicitly (when present): the key, the review
#: checklist, every provenance file and the data-return-only documents. The bash check
#: also globs every file of every protected directory.
SR_PRIVATE_FILES = (
    "answer_key.json",
    "REVIEW_CHECKLIST.md",
    "provenance.json",
    "provenance_real.json",
    "provenance_recon.json",
    "provenance_R05.json",
)
SR_DATA_RETURN_ONLY_FILES = ("S05/S05.txt", "S06/S06.txt")


def protected_paths() -> tuple[list[Path], list[Path]]:
    """(directories, files) the student must not list or read, for every task.

    Directories: both bundles, both private directories and, for the system-response
    bundle, its log and witness directories and every document directory (including the
    data-return-only S05 and S06 and R05 with its calibration file). Files: both
    manifests, the system-response key, checklist and provenance files
    (:data:`SR_PRIVATE_FILES`), the data-return-only texts and one asset log, one control
    log and one witness card when present (the bash check also globs every file in each
    directory). The full investigation's paths (:func:`fi_protected_paths`) follow.
    """
    from environment.incident.paths import (
        DEFAULT_BUNDLE_DIR,
        DEFAULT_PRIVATE_DIR,
        SYSTEM_RESPONSE_BUNDLE_DIR,
        SYSTEM_RESPONSE_PRIVATE_DIR,
    )

    sr = SYSTEM_RESPONSE_BUNDLE_DIR
    directories = [
        DEFAULT_BUNDLE_DIR,
        DEFAULT_PRIVATE_DIR,
        sr,
        sr / "logs",
        sr / "logs" / "assets",
        sr / "logs" / "control",
        sr / "witnesses",
        SYSTEM_RESPONSE_PRIVATE_DIR,
    ]
    if sr.is_dir():
        directories += sorted(
            p
            for p in sr.iterdir()
            if p.is_dir() and p.name not in ("logs", "witnesses")
        )
    files = [
        DEFAULT_BUNDLE_DIR / "manifest.json",
        sr / "manifest.json",
    ]
    files += [
        SYSTEM_RESPONSE_PRIVATE_DIR / name
        for name in SR_PRIVATE_FILES
        if (SYSTEM_RESPONSE_PRIVATE_DIR / name).is_file()
    ]
    files += [sr / rel for rel in SR_DATA_RETURN_ONLY_FILES if (sr / rel).is_file()]
    for folder in (sr / "logs" / "assets", sr / "logs" / "control", sr / "witnesses"):
        if folder.is_dir():
            found = sorted(p for p in folder.iterdir() if p.is_file())
            files += found[:1]
    fi_directories, fi_files = fi_protected_paths()
    return directories + fi_directories, files + fi_files


def data_return_only_files(bundle_dir: Path) -> list[Path]:
    """Every artifact of the documents a v2 manifest marks ``access: "data_return"``
    (read from the manifest; an unreadable manifest yields none here, and the bundle
    then fails its own verification)."""
    try:
        manifest = json.loads((bundle_dir / "manifest.json").read_text("utf-8"))
        documents = list(manifest.get("documents") or [])
    except (OSError, UnicodeDecodeError, ValueError, AttributeError, TypeError):
        return []
    found: list[Path] = []
    for doc in documents:
        if not isinstance(doc, dict) or doc.get("access") != "data_return":
            continue
        for artifact in doc.get("artifacts") or []:
            rel = artifact.get("file") if isinstance(artifact, dict) else None
            if isinstance(rel, str) and (bundle_dir / rel).is_file():
                found.append(bundle_dir / rel)
    return sorted(set(found))


def fi_protected_paths() -> tuple[list[Path], list[Path]]:
    """(directories, files) of the full investigation the student must not list or read.

    Only what exists is named (the bundle and the private directory are built
    separately): both roots and every directory below them; the manifest; every
    artifact of a data-return-only document; one asset log, one control log and one
    witness card; and every file of the private directory (key, checklist, rubric,
    provenance). The bash check also globs every file of each directory.
    """
    from environment.incident.paths import (
        FULL_INVESTIGATION_BUNDLE_DIR,
        FULL_INVESTIGATION_PRIVATE_DIR,
    )

    bundle, private = FULL_INVESTIGATION_BUNDLE_DIR, FULL_INVESTIGATION_PRIVATE_DIR
    directories: list[Path] = []
    for root in (bundle, private):
        if root.is_dir() and not root.is_symlink():
            directories.append(root)
            directories += sorted(p for p in root.rglob("*") if p.is_dir())
    files: list[Path] = []
    if (bundle / "manifest.json").is_file():
        files.append(bundle / "manifest.json")
    files += data_return_only_files(bundle)
    for folder in (
        bundle / "logs" / "assets",
        bundle / "logs" / "control",
        bundle / "witnesses",
    ):
        if folder.is_dir():
            found = sorted(p for p in folder.iterdir() if p.is_file())
            files += found[:1]
    if private.is_dir():
        files += sorted(p for p in private.rglob("*") if p.is_file())
    return directories, list(dict.fromkeys(files))


def bash_check_script() -> str:
    """The bash run (as root) by :func:`_bash_checks`; each probe uses ``runuser``."""
    from environment.paths import ROOT_DATA_DIR, STUDENT_WORKDIR

    directories, files = protected_paths()
    dirs = " ".join(shlex.quote(str(d)) for d in directories)
    readable = " ".join(shlex.quote(str(f)) for f in files)
    root_data = shlex.quote(str(ROOT_DATA_DIR))
    evidence = shlex.quote(str(STUDENT_WORKDIR / "evidence"))
    student_python = shlex.quote(str(STUDENT_WORKDIR / ".venv" / "bin" / "python"))

    return f"""
set -e

echo "Running test: student cannot read the evidence bundles or private grading data"
for d in {dirs}; do
  if runuser -u student -- ls "$d" >/dev/null 2>&1; then
    echo "FAIL: student can list $d"; exit 1
  fi
  for f in "$d"/*; do
    if [ -f "$f" ] && runuser -u student -- cat "$f" >/dev/null 2>&1; then
      echo "FAIL: student can read $f"; exit 1
    fi
  done
done
for f in {readable}; do
  if runuser -u student -- cat "$f" >/dev/null 2>&1; then
    echo "FAIL: student can read $f"; exit 1
  fi
done
echo "PASS: student cannot read the evidence bundles or private grading data"

echo "Running test: student cannot list {root_data}"
if runuser -u student -- ls {root_data} >/dev/null 2>&1; then
  echo "FAIL: student can list {root_data}"; exit 1
fi
echo "PASS: student cannot list {root_data}"

echo "Running test: student venv imports numpy and pandas"
runuser -u student -- {student_python} -I -c "import numpy, pandas"
echo "PASS: student venv imports numpy and pandas"

echo "Running test: evidence dir is absent or root-owned and read-only for the student"
if [ -L {evidence} ]; then
  echo "FAIL: {evidence} is a symlink"; exit 1
fi
if [ -e {evidence} ]; then
  owner=$(stat -c '%u' {evidence})
  if [ "$owner" != "0" ]; then
    echo "FAIL: {evidence} is owned by uid $owner"; exit 1
  fi
  if runuser -u student -- touch {evidence}/.write_probe 2>/dev/null; then
    rm -f {evidence}/.write_probe
    echo "FAIL: student can write to {evidence}"; exit 1
  fi
fi
echo "PASS: evidence dir is absent or root-owned and read-only for the student"

echo "All incident checks passed!"
"""


def _bash_checks() -> None:
    from karotte.trusted_bin import trusted_binary

    result = subprocess.run(
        [trusted_binary("bash"), "-c", bash_check_script()],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Incident checks failed with exit code {result.returncode}:\n"
        f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
    )


def private_path_probe_code(targets: list[str]) -> str:
    """Python (run in ``run_python``) that tries to read or list each target and prints
    ``{"uid", "seen": {target: "READABLE"|"DENIED"}}``."""
    return (
        "import json, os\n"
        f"targets = {json.dumps(targets)}\n"
        "seen = {}\n"
        "for t in targets:\n"
        "    try:\n"
        "        if os.path.isdir(t):\n"
        "            os.listdir(t)\n"
        "        else:\n"
        "            open(t, 'rb').read(1)\n"
        "        seen[t] = 'READABLE'\n"
        "    except OSError:\n"
        "        seen[t] = 'DENIED'\n"
        "import numpy, pandas\n"
        "print(json.dumps({'uid': os.getuid(), 'seen': seen}))\n"
    )


def probe_targets() -> list[str]:
    """Every path ``run_python`` must not reach (both bundles, both private dirs, the
    system-response logs and witness cards, and ``ROOT_DATA_DIR``)."""
    from environment.paths import ROOT_DATA_DIR

    directories, files = protected_paths()
    return [str(p) for p in (*files, *directories, ROOT_DATA_DIR)]


def _python_report(result, what: str) -> dict:
    data = result.envelope["data"]
    assert result.ok, (
        f"run_python {what} failed: {result.envelope['error']}\n"
        f"stdout:\n{data.get('stdout')}\nstderr:\n{data.get('stderr')}\n"
        f"notes: {data.get('notes')}"
    )
    return json.loads(data["stdout"].strip().splitlines()[-1])


def task_tool_configs() -> list[tuple[str, type]]:
    """(task ID, tool-config class) of every task whose episode the image checks drive."""
    from environment.tasks.gb_2019_electrical_disturbance import IncidentToolConfig
    from environment.tasks.gb_2019_system_response import (
        TASK_ID as SR_TASK_ID,
    )
    from environment.tasks.gb_2019_system_response import (
        SystemResponseToolConfig,
    )

    return [
        ("gb-2019-electrical-disturbance", IncidentToolConfig),
        (SR_TASK_ID, SystemResponseToolConfig),
    ]


def fi_task_tool_configs() -> list[tuple[str, type]]:
    """(task ID, tool-config class) of the full investigation (increment B), driven by
    :func:`full_investigation_checks`."""
    from environment.tasks.gb_2019_full_investigation import (
        TASK_ID as FI_TASK_ID,
    )
    from environment.tasks.gb_2019_full_investigation import (
        FullInvestigationToolConfig,
    )

    return [(FI_TASK_ID, FullInvestigationToolConfig)]


def _runner_checks() -> None:
    for task_id, config_class in task_tool_configs():
        _episode_checks(task_id, config_class)
    _sr_materialisation_checks()


def _episode_checks(task_id: str, config_class: type) -> None:
    from environment import STUDENT_UID
    from environment.tasks.gb_2019_electrical_disturbance import make_episode

    base = Path(tempfile.mkdtemp(prefix="incident-check-"))
    try:
        os.chmod(base, 0o711)
        evidence = base / "evidence"
        config = config_class(
            episode_dir=base / "episode",
            evidence_dir=evidence,
            scratch_dir=base / "scratch",
            python_timeout_s=60,
        )
        episode = make_episode(config)
        meta = episode.reset()  # evidence root-owned 0555, scratch the student's
        print(f"[{task_id}] run_python network isolation: {meta['network_mode']}")
        # In a network namespace on gVisor the student's uid is not mapped (Karotte
        # omits --map-current-user there), so the code sees the overflow uid.
        student_uids = {STUDENT_UID}
        if meta["network_mode"] == "namespace":
            student_uids.add(65534)
        doc_id = episode.catalogue.listed_ids()[0]
        fetched = episode.request_document(doc_id)
        assert fetched.ok, f"request_document({doc_id}) failed: {fetched.envelope}"
        artifacts = fetched.envelope["data"]["artifacts"]
        report = _python_report(
            episode.run_python(private_path_probe_code(probe_targets())),
            f"[{task_id}] private-path probe",
        )
        assert report["uid"] in student_uids, f"run_python ran as uid {report['uid']}"
        leaked = [t for t, v in report["seen"].items() if v != "DENIED"]
        assert not leaked, f"[{task_id}] run_python can read private paths: {leaked}"
        print(
            f"PASS [{task_id}]: run_python runs as the student and cannot read private "
            "paths"
        )

        file_name = artifacts[0]["path"].split("/", 1)[1]
        report = _python_report(
            episode.run_python(evidence_write_probe_code(doc_id, file_name)),
            f"[{task_id}] evidence-write probe",
        )
        assert report["uid"] in student_uids, f"run_python ran as uid {report['uid']}"
        allowed = [op for op, v in report["results"].items() if v != "DENIED"]
        assert not allowed, f"the student can modify the evidence directory: {allowed}"
        assert report["readable"], "the student cannot read a retrieved document"
        for artifact in artifacts:
            copy = evidence / artifact["path"]
            digest = hashlib.sha256(copy.read_bytes()).hexdigest()
            assert digest == artifact["sha256"], f"{copy} changed"
        print(
            f"PASS [{task_id}]: the student cannot modify a materialised evidence directory"
        )
    finally:
        shutil.rmtree(base, ignore_errors=True)


# -- system response: only what was obtained is materialised ------------------------------
#: Tool calls that must not write anything under EVIDENCE_DIR (log rows and witness
#: answers are returned in the tool result only).
SR_NON_MATERIALISING_CALLS: tuple[tuple[str, dict], ...] = (
    (
        "query_asset_log",
        {
            "asset_id": "HORNSEA-ONE",
            "start": "2019-08-09T15:50:00Z",
            "end": "2019-08-09T15:55:00Z",
        },
    ),
    (
        "query_control_log",
        {
            "room": "ESO-ENCC",
            "start": "2019-08-09T15:52:00Z",
            "end": "2019-08-09T15:58:00Z",
        },
    ),
    (
        "interview_witness",
        {
            "persona_id": "nget-protection-engineer",
            "question": "What was the fault type and which phase faulted?",
        },
    ),
)
#: Calls that materialise exactly one document each: a data return (S05) and the
#: frequency record (R01, through query_frequency).
SR_MATERIALISING_CALLS: tuple[tuple[str, dict, str], ...] = (
    (
        "request_data_return",
        {"party": "DNO", "data_type": "lfdd_disconnection_and_restoration_returns"},
        "S05",
    ),
    (
        "query_frequency",
        {"start": "2019-08-09T16:52:30+01:00", "end": "2019-08-09T16:53:30+01:00"},
        "R01",
    ),
)


def materialisation_probe_code(readable: list[str], denied: list[str]) -> str:
    """Python (run in ``run_python``) that lists ``EVIDENCE_DIR`` and tries to read each
    path; prints ``{"uid", "listing", "readable": {relative path under EVIDENCE_DIR:
    true|false}, "denied": {absolute path: "DENIED"|"READABLE"}}``."""
    return (
        "import json, os\n"
        f"readable = {json.dumps(readable)}\n"
        f"denied = {json.dumps(denied)}\n"
        "root = os.environ['EVIDENCE_DIR']\n"
        "listing = sorted(e for e in os.listdir(root) if not e.startswith('.'))\n"
        "ok = {}\n"
        "for rel in readable:\n"
        "    try:\n"
        "        with open(os.path.join(root, rel), 'rb') as handle:\n"
        "            ok[rel] = bool(handle.read(64))\n"
        "    except OSError:\n"
        "        ok[rel] = False\n"
        "seen = {}\n"
        "for t in denied:\n"
        "    try:\n"
        "        if os.path.isdir(t):\n"
        "            os.listdir(t)\n"
        "        else:\n"
        "            open(t, 'rb').read(1)\n"
        "        seen[t] = 'READABLE'\n"
        "    except OSError:\n"
        "        seen[t] = 'DENIED'\n"
        "print(json.dumps({'uid': os.getuid(), 'listing': listing, 'readable': ok, "
        "'denied': seen}))\n"
    )


def sr_unobtained_targets(bundle_dir: Path, private_dir: Path) -> list[str]:
    """Paths the student must not read even after obtaining evidence: the bundle's
    data return that was not asked for (S06), its logs and witness cards, and the
    system-response key and provenance files."""
    targets = [
        bundle_dir / "S06" / "S06.txt",
        bundle_dir / "logs" / "assets",
        bundle_dir / "logs" / "control",
        bundle_dir / "witnesses",
        private_dir,
    ]
    targets += [private_dir / name for name in SR_PRIVATE_FILES]
    return [str(p) for p in targets]


def sr_materialisation_report(episode, private_dir: Path | None = None) -> dict:
    """Drive a fresh system-response episode and record what is materialised.

    Returns ``{"after_reset", "after_queries", "after_obtaining", "obtained", "calls",
    "python": <materialisation probe report>, "write": <evidence-write probe report>}``.
    Listings are taken from the harness side; the probes run as the student through
    ``run_python``. Raises AssertionError when a call itself fails."""
    evidence = Path(episode.config.evidence_dir)

    def listing() -> list[str]:
        if not evidence.exists():
            return []
        return sorted(e for e in os.listdir(evidence) if not e.startswith("."))

    report: dict = {"after_reset": listing(), "calls": []}
    for tool, args in SR_NON_MATERIALISING_CALLS:
        result = episode.call(tool, args)
        assert result.ok, f"{tool} failed: {result.envelope['error']}"
        report["calls"].append(tool)
    report["after_queries"] = listing()
    obtained: list[str] = []
    files: dict[str, str] = {}
    for tool, args, doc_id in SR_MATERIALISING_CALLS:
        result = episode.call(tool, args)
        assert result.ok, f"{tool} failed: {result.envelope['error']}"
        report["calls"].append(tool)
        obtained.append(doc_id)
        doc = episode.catalogue.get(doc_id)
        files[doc_id] = (
            doc.text_file
            if doc_id != "R01"
            else next(a.file for a in doc.artifacts if a.timeseries is not None)
        )
    report["obtained"] = sorted(obtained)
    report["after_obtaining"] = listing()
    bundle = Path(episode.config.bundle_dir)
    if private_dir is None:
        from environment.incident.paths import SYSTEM_RESPONSE_PRIVATE_DIR

        private_dir = SYSTEM_RESPONSE_PRIVATE_DIR
    report["python"] = _python_report(
        episode.run_python(
            materialisation_probe_code(
                sorted(files.values()), sr_unobtained_targets(bundle, private_dir)
            )
        ),
        "system-response materialisation probe",
    )
    name = files["S05"].split("/", 1)[1]
    report["write"] = _python_report(
        episode.run_python(evidence_write_probe_code("S05", name)),
        "system-response data-return write probe",
    )
    return report


def _sr_materialisation_checks() -> None:
    """In the container: only obtained evidence is materialised for the student; logs,
    witness answers and unrequested data returns never are; data returns are read-only;
    the key and provenance stay unreadable after retrieval."""
    from environment import STUDENT_UID
    from environment.tasks.gb_2019_electrical_disturbance import make_episode
    from environment.tasks.gb_2019_system_response import SystemResponseToolConfig

    base = Path(tempfile.mkdtemp(prefix="incident-check-sr-"))
    try:
        os.chmod(base, 0o711)
        config = SystemResponseToolConfig(
            episode_dir=base / "episode",
            evidence_dir=base / "evidence",
            scratch_dir=base / "scratch",
            python_timeout_s=60,
        )
        episode = make_episode(config)
        meta = episode.reset()
        student_uids = {STUDENT_UID}
        if meta["network_mode"] == "namespace":
            student_uids.add(65534)
        report = sr_materialisation_report(episode)
        assert report["after_reset"] == [], report["after_reset"]
        assert report["after_queries"] == [], (
            f"log queries or witness answers materialised files: {report['after_queries']}"
        )
        assert report["after_obtaining"] == report["obtained"], report
        python = report["python"]
        assert python["uid"] in student_uids, f"run_python ran as uid {python['uid']}"
        assert python["listing"] == report["obtained"], python["listing"]
        assert all(python["readable"].values()), python["readable"]
        leaked = [t for t, v in python["denied"].items() if v != "DENIED"]
        assert not leaked, f"run_python can read unobtained or private paths: {leaked}"
        allowed = [op for op, v in report["write"]["results"].items() if v != "DENIED"]
        assert not allowed, f"the student can modify a data return: {allowed}"
        print(
            "PASS [gb-2019-system-response]: only obtained evidence is materialised; "
            "data returns are read-only; key and provenance stay unreadable"
        )
    finally:
        shutil.rmtree(base, ignore_errors=True)


def fi_unobtained_targets(
    bundle_dir: Path, private_dir: Path, obtained: list[str]
) -> list[str]:
    """Full-investigation paths the student must not read after obtaining ``obtained``:
    every artifact of a data-return-only document that was not obtained, and every file
    of the private directory (in addition to :func:`sr_unobtained_targets`)."""
    targets = [
        p
        for p in data_return_only_files(bundle_dir)
        if p.relative_to(bundle_dir).parts[0] not in obtained
    ]
    if private_dir.is_dir():
        targets += sorted(p for p in private_dir.rglob("*") if p.is_file())
    return [str(p) for p in targets]


def full_investigation_checks() -> None:
    """In the container (called by ``environment.incident_fi_checks.check``): the
    full-investigation bundle ships and verifies (fail closed); an episode under its tool
    configuration is driven like the other tasks' (:func:`_episode_checks`); and only
    obtained evidence is materialised, with every unrequested data return and private
    file still unreadable."""
    from environment import STUDENT_UID
    from environment.incident.paths import FULL_INVESTIGATION_PRIVATE_DIR
    from environment.tasks.gb_2019_electrical_disturbance import make_episode
    from environment.tasks.gb_2019_full_investigation import (
        TASK_ID,
        FullInvestigationToolConfig,
    )

    load_full_investigation_bundle()
    for task_id, config_class in fi_task_tool_configs():
        _episode_checks(task_id, config_class)

    base = Path(tempfile.mkdtemp(prefix="incident-check-fi-"))
    try:
        os.chmod(base, 0o711)
        config = FullInvestigationToolConfig(
            episode_dir=base / "episode",
            evidence_dir=base / "evidence",
            scratch_dir=base / "scratch",
            python_timeout_s=60,
        )
        episode = make_episode(config)
        meta = episode.reset()
        student_uids = {STUDENT_UID}
        if meta["network_mode"] == "namespace":
            student_uids.add(65534)
        report = sr_materialisation_report(episode, FULL_INVESTIGATION_PRIVATE_DIR)
        assert report["after_reset"] == [], report["after_reset"]
        assert report["after_queries"] == [], (
            f"log queries or witness answers materialised files: {report['after_queries']}"
        )
        assert report["after_obtaining"] == report["obtained"], report
        python = report["python"]
        assert python["uid"] in student_uids, f"run_python ran as uid {python['uid']}"
        assert python["listing"] == report["obtained"], python["listing"]
        assert all(python["readable"].values()), python["readable"]
        leaked = [t for t, v in python["denied"].items() if v != "DENIED"]
        assert not leaked, f"run_python can read unobtained or private paths: {leaked}"
        allowed = [op for op, v in report["write"]["results"].items() if v != "DENIED"]
        assert not allowed, f"the student can modify a data return: {allowed}"
        extra = _python_report(
            episode.run_python(
                private_path_probe_code(
                    fi_unobtained_targets(
                        Path(config.bundle_dir),
                        FULL_INVESTIGATION_PRIVATE_DIR,
                        report["obtained"],
                    )
                )
            ),
            "full-investigation unobtained-evidence probe",
        )
        leaked = [t for t, v in extra["seen"].items() if v != "DENIED"]
        assert not leaked, f"run_python can read unobtained or private paths: {leaked}"
        print(
            f"PASS [{TASK_ID}]: only obtained evidence is materialised; data returns "
            "are read-only; unrequested returns, key and provenance stay unreadable"
        )
    finally:
        shutil.rmtree(base, ignore_errors=True)


def load_full_investigation_bundle() -> str:
    """Load and verify the full-investigation bundle (fail closed); its bundle ID."""
    from environment.incident.catalogue import Catalogue
    from environment.incident.paths import FULL_INVESTIGATION_BUNDLE_DIR

    catalogue = Catalogue.load(FULL_INVESTIGATION_BUNDLE_DIR)
    catalogue.verify()
    return catalogue.bundle_id


def load_shipped_bundles() -> list[str]:
    """Load and verify both shipped bundles (fail closed); their bundle IDs."""
    from environment.incident.catalogue import Catalogue
    from environment.incident.paths import (
        DEFAULT_BUNDLE_DIR,
        SYSTEM_RESPONSE_BUNDLE_DIR,
    )

    loaded = []
    for bundle in (DEFAULT_BUNDLE_DIR, SYSTEM_RESPONSE_BUNDLE_DIR):
        catalogue = Catalogue.load(bundle)
        catalogue.verify()
        loaded.append(catalogue.bundle_id)
    return loaded


def check() -> None:
    """Container-only image checks (no-op elsewhere)."""
    if "KAROTTE_CONTAINERIZED" not in os.environ:
        return
    load_shipped_bundles()  # both shipped bundles must verify (fail closed)
    _bash_checks()
    _runner_checks()
