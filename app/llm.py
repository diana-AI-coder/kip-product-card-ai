"""Универсальный клиент LLM через OpenAI-compatible API."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from openai import (
    APIConnectionError,
    APIStatusError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from .config import Settings
from .schemas import CARD_JSON_SCHEMA


class LLMError(RuntimeError):
    """Ошибка обращения к LLM или разбора её ответа."""


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        raise LLMError("модель вернула ответ без JSON-объекта")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"не удалось разобрать JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise LLMError("JSON-ответ модели не является объектом")
    return data


class LLMClient:
    """Клиент, работающий с любым провайдером OpenAI-compatible API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url or None,
            timeout=settings.timeout,
            max_retries=2,
        )

    def _modes(self) -> tuple[str, ...]:
        if self.settings.json_mode == "auto":
            return ("schema", "object", "prompt")
        return (self.settings.json_mode,)

    def complete_json(
        self, system_prompt: str, user_prompt: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Возвращает (JSON-ответ модели, метаданные вызова)."""
        problems: list[str] = []
        modes = self._modes()
        for index, mode in enumerate(modes):
            try:
                return self._call(system_prompt, user_prompt, mode)
            except LLMError as exc:
                problems.append(f"{mode}: {exc}")
                if index == len(modes) - 1:
                    raise LLMError(
                        "не удалось получить корректный JSON ни в одном режиме: "
                        + "; ".join(problems)
                    ) from exc
            except BadRequestError as exc:
                message = (exc.message or str(exc)).strip()
                supports_fallback = mode != "prompt" and any(
                    token in message.lower()
                    for token in ("response_format", "json_schema", "structured")
                )
                if not supports_fallback:
                    raise LLMError(f"LLM API отклонил запрос: {message}") from exc
                problems.append(f"{mode}: {message}")
                if index == len(modes) - 1:
                    raise LLMError(
                        "провайдер не поддерживает ни один режим JSON: "
                        + "; ".join(problems)
                    ) from exc
            except (APIConnectionError, RateLimitError) as exc:
                raise LLMError(
                    f"LLM API недоступен или ограничил запросы: {exc}"
                ) from exc
            except APIStatusError as exc:
                raise LLMError(
                    f"LLM API вернул ошибку {exc.status_code}: {exc.message}"
                ) from exc
        raise LLMError("не удалось выполнить запрос к LLM")

    def _call(
        self, system_prompt: str, user_prompt: str, mode: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
        }
        if mode == "schema":
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "product_card",
                    "strict": True,
                    "schema": CARD_JSON_SCHEMA,
                },
            }
        elif mode == "object":
            kwargs["response_format"] = {"type": "json_object"}
        else:
            user_prompt = (
                user_prompt
                + "\n\nВерни ТОЛЬКО JSON-объект. Без markdown, без пояснений."
            )
            kwargs["messages"][1]["content"] = user_prompt

        response = self._client.chat.completions.create(**kwargs)
        message = response.choices[0].message.content or ""
        if not message.strip():
            raise LLMError("модель вернула пустой ответ")
        data = _extract_json(message)
        usage = response.usage
        meta = {
            "mode": mode,
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
        }
        return data, meta


def base_url_host(base_url: str) -> str:
    """Домен провайдера без ключей и пути — только для метаданных."""
    parsed = urlparse(base_url or "")
    return parsed.netloc or parsed.path or "unknown"
