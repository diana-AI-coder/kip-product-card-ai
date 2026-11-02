"""Конфигурация приложения из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

VALID_JSON_MODES = ("auto", "schema", "object", "prompt")


class ConfigError(RuntimeError):
    """Конфигурация LLM отсутствует или задана неверно."""


@dataclass(frozen=True)
class Settings:
    """Параметры подключения к LLM. Провайдер задаётся только через env."""

    base_url: str
    api_key: str
    model: str
    timeout: float = 60.0
    temperature: float = 0.0
    max_tokens: int = 2000
    json_mode: str = "auto"
    max_repairs: int = 1


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} должно быть числом, получено {raw!r}") from exc


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} должно быть целым числом, получено {raw!r}") from exc


def load_settings() -> Settings:
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        raise ConfigError(
            "LLM_API_KEY не задан. Скопируйте .env.example в .env и укажите ключ провайдера."
        )
    if api_key in {"sk-your-key-here", "your-key-here"} or api_key.startswith("sk-your-"):
        raise ConfigError(
            "LLM_API_KEY содержит заглушку из .env.example — замените её на реальный ключ."
        )
    model = os.getenv("LLM_MODEL", "").strip()
    if not model:
        raise ConfigError(
            "LLM_MODEL не задан. Укажите модель, например gpt-4o-mini, для Ollama — llama3.1."
        )
    json_mode = os.getenv("LLM_JSON_MODE", "auto").strip().lower()
    if json_mode not in VALID_JSON_MODES:
        raise ConfigError(
            f"LLM_JSON_MODE={json_mode!r} не поддерживается. Допустимо: {', '.join(VALID_JSON_MODES)}."
        )
    return Settings(
        base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip(),
        api_key=api_key,
        model=model,
        timeout=_float_env("LLM_TIMEOUT", 60.0),
        temperature=_float_env("LLM_TEMPERATURE", 0.0),
        max_tokens=_int_env("LLM_MAX_TOKENS", 2000),
        json_mode=json_mode,
        max_repairs=_int_env("LLM_MAX_REPAIRS", 1),
    )
