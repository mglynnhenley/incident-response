"""Judge configuration: defaults (decision 25), the example config, model families and
the refusal of a judge from the evaluated model's family."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from environment.incident.judge import (
    DEFAULT_JUDGE_MODEL,
    JudgeConfig,
    JudgeConfigError,
    api_model_id,
    check_family,
    load_config,
    model_family,
)
from environment.incident.paths import SYSTEM_RESPONSE_PRIVATE_DIR

EXAMPLE = Path(__file__).resolve().parents[1] / "configs" / "judge.example.json"


def test_defaults_follow_decision_25():
    cfg = JudgeConfig()
    assert cfg.judge_model == DEFAULT_JUDGE_MODEL == "openai/gpt-6.1-sol"
    assert cfg.temperature == 0
    assert cfg.modes == ["judge", "auto_assisted_human"]
    assert cfg.allow_same_family is False
    assert (cfg.price_per_million_input_usd, cfg.price_per_million_output_usd) == (
        2,
        10,
    )
    assert cfg.rubric_path() == SYSTEM_RESPONSE_PRIVATE_DIR / "judge_rubric_v1.md"
    assert cfg.rubric_path().is_file()
    assert "api_key" not in json.dumps(cfg.model_dump()).lower()


def test_example_config_loads_and_matches_defaults():
    cfg = load_config(EXAMPLE)
    assert cfg == JudgeConfig()
    raw = json.loads(EXAMPLE.read_text())
    assert not any("key" in k.lower() and not k.startswith("_") for k in raw)
    assert "sk-" not in EXAMPLE.read_text()


def test_overrides_and_errors(tmp_path: Path):
    cfg = load_config(
        EXAMPLE, judge_model="google/gemini-4-pro", allow_same_family=None
    )
    assert cfg.judge_model == "google/gemini-4-pro" and cfg.allow_same_family is False
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"judge_model": "x/y", "api_key": "sk-123"}))
    with pytest.raises(JudgeConfigError, match="invalid judge config"):
        load_config(bad)
    with pytest.raises(JudgeConfigError, match="never sent"):
        load_config(modes=["auto_numeric"])
    with pytest.raises(JudgeConfigError):
        load_config(modes=[])
    with pytest.raises(JudgeConfigError, match="cannot read"):
        load_config(tmp_path / "missing.json")


@pytest.mark.parametrize(
    "model, family",
    [
        ("openai/gpt-6.1-sol", "openai"),
        ("openrouter/openai/gpt-6.1-sol", "openai"),
        ("openai/o3-mini", "openai"),
        ("anthropic/claude-opus-5.5", "anthropic"),
        ("openrouter/anthropic/claude-haiku-4.5", "anthropic"),
        ("claude-sonnet-5.5", "anthropic"),
        ("bedrock/anthropic.claude-3-opus", "anthropic"),
        ("google/gemini-4-pro", "google"),
        ("meta-llama/llama-4-maverick", "meta"),
        ("mistralai/mistral-large", "mistral"),
        ("x-ai/grok-5", "xai"),
        ("deepseek/deepseek-r2", "deepseek"),
        ("qwen/qwen3-max", "qwen"),
        ("somevendor/unknown-model", None),
        ("", None),
        (None, None),
    ],
)
def test_model_family(model, family):
    assert model_family(model) == family


def test_api_model_id():
    assert api_model_id("openrouter/openai/gpt-6.1-sol") == "openai/gpt-6.1-sol"
    assert api_model_id(" openai/gpt-6.1-sol ") == "openai/gpt-6.1-sol"


def test_same_family_is_refused_unless_overridden():
    with pytest.raises(JudgeConfigError, match="evaluated model's family"):
        check_family(
            "anthropic/claude-opus-5.5", "openrouter/anthropic/claude-haiku-4.5"
        )
    with pytest.raises(JudgeConfigError, match="evaluated model's family"):
        check_family("openrouter/openai/gpt-6.1-sol", "openai/gpt-5")
    record = check_family(
        "anthropic/claude-opus-5.5",
        "openrouter/anthropic/claude-haiku-4.5",
        allow_same_family=True,
    )
    assert record == {
        "judge_model_family": "anthropic",
        "run_model_family": "anthropic",
        "run_model_known": True,
        "same_family": True,
        "allow_same_family": True,
    }
    ok = check_family(DEFAULT_JUDGE_MODEL, "openrouter/anthropic/claude-opus-5.5")
    assert ok["same_family"] is False and ok["judge_model_family"] == "openai"
    # the evaluated model's ID is never recorded, only its family
    assert "claude" not in json.dumps(ok)


def test_unknown_evaluated_model_is_refused():
    with pytest.raises(JudgeConfigError, match="evaluated model is unknown"):
        check_family(DEFAULT_JUDGE_MODEL, None)
    with pytest.raises(JudgeConfigError, match="cannot tell the model family"):
        check_family(DEFAULT_JUDGE_MODEL, "fake")
    record = check_family(DEFAULT_JUDGE_MODEL, None, allow_same_family=True)
    assert record["run_model_known"] is False
