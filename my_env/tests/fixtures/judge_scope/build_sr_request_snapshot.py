"""Snapshot of every judge request increment A's task sends (decision 52 parity).

It was run with ``--write`` BEFORE per-topic scoping was added to
``environment.incident.judge`` (2026-10-20), from ``my_env``:

    uv run --frozen --extra test python tests/fixtures/judge_scope/build_sr_request_snapshot.py --write

Without ``--write`` it only compares the current code's requests with the snapshot
(exit status 1 on a difference). The snapshot, ``sr_requests.json``, holds for the six real system-response runs
(``tests/fixtures/sr_live``), the valid builder fixtures (``tests/fixtures/sr``), the key
oracle and the small judge-test submission, every unit's criteria, classified findings,
``messages_sha256`` and cache key under the default configuration
(``configs/judge.example.json``), the prompt template sha256, and the sha256 of the
complete judge output a mocked judge produces. ``tests/test_judge_scope_parity.py``
recomputes all of it with the current code and requires byte-identical values. Do not
regenerate it to make that test pass: a difference means increment A's judge requests
or cache keys changed, which is not allowed (its task is frozen).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE.parents[1]
ENV_ROOT = TESTS.parent
sys.path.insert(0, str(TESTS))

from sr_grading_support import catalogue, key, oracle_submission  # noqa: E402
from sr_judge_support import FakeJudge, small_submission  # noqa: E402

from environment.incident import grading as mvp  # noqa: E402
from environment.incident import sr_grading  # noqa: E402
from environment.incident.judge import (  # noqa: E402
    cache_key,
    judge_submission,
    load_config,
    prompt_template_sha256,
)
from environment.incident.judge.runner import _prepare  # noqa: E402

LIVE = TESTS / "fixtures" / "sr_live"
SR_FIXTURES = TESTS / "fixtures" / "sr" / "submissions"
VALID_FIXTURES = ("correct", "incomplete", "incorrect", "uncertain", "uncited")
OPUS = "openrouter/anthropic/claude-opus-5.5"


def canonical_sha(obj) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def targets():
    """(name, submission text or object, base report, run model)."""
    runs = json.loads((LIVE / "runs.json").read_text(encoding="utf-8"))["runs"]
    for run in runs:
        rid = run["run_id"]
        text = (LIVE / rid / "submission.json").read_text(encoding="utf-8")
        summary = json.loads((LIVE / rid / "run_summary.json").read_text("utf-8"))
        if run["outcome"] == "complete":
            report = sr_grading.grade_episode(
                LIVE / rid, summary, key=key(), catalogue=catalogue()
            )
        else:
            report = sr_grading.grade_submission(
                text,
                catalogue(),
                key(),
                sr_grading.trace_info_from_episode(LIVE / rid),
            )
        yield f"sr_live/{rid}", text, report, run["model"]
    for name in VALID_FIXTURES:
        text = (SR_FIXTURES / f"{name}.json").read_text(encoding="utf-8")
        yield (
            f"sr/{name}",
            text,
            sr_grading.grade_submission(text, catalogue(), key()),
            OPUS,
        )
    for name, sub in (("oracle", oracle_submission()), ("small", small_submission())):
        yield name, sub, sr_grading.grade_submission(sub, catalogue(), key()), OPUS


def snapshot_one(sub, report, run_model) -> dict:
    config = load_config(ENV_ROOT / "configs" / "judge.example.json")
    prep = _prepare(sub, report, key(), catalogue(), config, run_model, None)
    units = []
    for unit in prep.inputs.units:
        material = prep.material(unit)
        units.append(
            {
                "unit_id": unit.unit_id,
                "criteria": unit.criterion_ids,
                "findings_classified": unit.finding_ids,
                "messages_sha256": unit.messages_sha256,
                "cache_key": cache_key(material),
                "prompt_chars": sum(len(m["content"]) for m in unit.messages),
            }
        )
    result = judge_submission(
        sub,
        report,
        key=key(),
        catalogue=catalogue(),
        config=config,
        run_model=run_model,
        client=FakeJudge(),
    )
    parsed, _ = mvp._as_submission(sub, catalogue())
    return {
        "submission_sha256": report["submission"]["sha256"],
        "findings": len(parsed["findings"]),
        "units": units,
        "judge_output_sha256": canonical_sha(result.judge_output),
        "judge_output_cache_key": result.judge_output["cache_key"],
        "prompt_chars_total": sum(u["prompt_chars"] for u in units),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--write",
        action="store_true",
        help="overwrite sr_requests.json (only for a deliberate change of "
        "increment A's judge requests)",
    )
    args = parser.parse_args()
    out = {
        "_note": (
            "Judge requests of increment A's task before per-topic scoping "
            "(decision 52). Built by build_sr_request_snapshot.py; never regenerate "
            "to make the parity test pass."
        ),
        "key_version": key()["key_version"],
        "key_sha256": sr_grading.key_sha256(key()),
        "bundle_sha256": catalogue().bundle_sha256,
        "prompt_template_sha256": prompt_template_sha256(),
        "config": "configs/judge.example.json",
        "targets": {},
    }
    for name, sub, report, run_model in targets():
        out["targets"][name] = snapshot_one(sub, report, run_model)
        print(name, len(out["targets"][name]["units"]), "units", flush=True)
    path = HERE / "sr_requests.json"
    text = json.dumps(out, indent=1, sort_keys=True) + "\n"
    if args.write:
        path.write_text(text, encoding="utf-8")
        print("wrote", path)
        return 0
    same = path.is_file() and path.read_text(encoding="utf-8") == text
    print("identical to the snapshot" if same else "DIFFERS from the snapshot")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
