from __future__ import annotations

import pytest

from app.config import ConfigError, load_settings

ENV_KEYS = (
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_BASE_URL",
    "LLM_JSON_MODE",
    "LLM_TIMEOUT",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
    "LLM_MAX_REPAIRS",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_missing_api_key_raises(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    with pytest.raises(ConfigError, match="LLM_API_KEY не задан"):
        load_settings()


def test_placeholder_api_key_raises(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-your-key-here")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    with pytest.raises(ConfigError, match="заглушку"):
        load_settings()


def test_missing_model_raises(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    with pytest.raises(ConfigError, match="LLM_MODEL не задан"):
        load_settings()


def test_invalid_json_mode_raises(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_JSON_MODE", "magic")
    with pytest.raises(ConfigError, match="не поддерживается"):
        load_settings()


def test_valid_settings_are_parsed(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_TIMEOUT", "30")
    monkeypatch.setenv("LLM_MAX_REPAIRS", "2")
    settings = load_settings()
    assert settings.api_key == "sk-test"
    assert settings.timeout == 30.0
    assert settings.max_repairs == 2
    assert settings.json_mode == "auto"
