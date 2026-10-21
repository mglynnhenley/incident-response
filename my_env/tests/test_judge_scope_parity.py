"""Increment A's judge requests are unchanged by per-topic scoping (decision 52).

``tests/fixtures/judge_scope/sr_requests.json`` was built with the judge package as it
was before scoping existed (``build_sr_request_snapshot.py --write``). For the six real
system-response runs, the valid builder fixtures, the key oracle and the small judge-test
submission it records every unit's criteria, classified findings, ``messages_sha256``
and cache key under ``configs/judge.example.json``, the prompt template sha256 and the
sha256 of the whole judge output a mocked judge produces. Here the current code must
reproduce every value byte for byte: same prompts, same cache keys (so cached
responses stay valid), same judge outputs. No model is called.
"""

from __future__ import annotations

import importlib.util
import json

import pytest
from judge_scope_support import SNAPSHOT, SR_CONFIG, SR_LIVE, sr_key

from environment.incident.judge import (
    JudgeScope,
    load_config,
    prompt_template_sha256,
    prompt_version,
    resolve_scope,
)
from environment.incident.judge.prompt import PROMPT_VERSION

SNAP = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
_spec = importlib.util.spec_from_file_location(
    "build_sr_request_snapshot", SNAPSHOT.parent / "build_sr_request_snapshot.py"
)
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)


@pytest.fixture(scope="module")
def targets():
    return {
        name: (sub, report, model) for name, sub, report, model in builder.targets()
    }


def test_snapshot_covers_the_six_real_runs_and_the_fixtures():
    names = set(SNAP["targets"])
    runs = json.loads((SR_LIVE / "runs.json").read_text())["runs"]
    assert {f"sr_live/{r['run_id']}" for r in runs} <= names
    assert {"sr/correct", "sr/uncited", "sr/incorrect", "oracle", "small"} <= names
    assert SNAP["key_sha256"] == builder.sr_grading.key_sha256(sr_key())


@pytest.mark.parametrize("name", sorted(SNAP["targets"]))
def test_sr_requests_cache_keys_and_outputs_are_byte_identical(name, targets):
    sub, report, model = targets[name]
    assert builder.snapshot_one(sub, report, model) == SNAP["targets"][name]


def test_the_prompt_template_hash_is_unchanged():
    assert prompt_template_sha256() == SNAP["prompt_template_sha256"]
    # an explicit whole-submission scope is the same request
    assert prompt_template_sha256(JudgeScope()) == SNAP["prompt_template_sha256"]
    assert prompt_version(JudgeScope()) == PROMPT_VERSION
    # the live judge outputs were produced with the same template
    for run in ("sr80k-opus55-001", "sr80k-sonnet55-001", "sr80k-haiku45-001"):
        recorded = json.loads((SR_LIVE / run / "judge_output.json").read_text())
        assert recorded["prompt_template_sha256"] == SNAP["prompt_template_sha256"]
        assert "scope" not in recorded and "scope" not in recorded["config"]


def test_increment_a_does_not_opt_in():
    """Neither increment A's key nor its example config asks for a scope."""
    assert "scope" not in sr_key()["judge"]
    config = load_config(SR_CONFIG)
    assert config.scope is None and "scope" not in config.public()
    assert resolve_scope(config, sr_key()).mode == "submission"
    assert load_config(SR_CONFIG, task="gb-2019-system-response") == config
