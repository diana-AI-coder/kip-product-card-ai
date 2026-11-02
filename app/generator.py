"""Оркестрация: вход → промпт → LLM → проверка → repair → черновик карточки."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from .config import Settings, load_settings
from .llm import LLMClient, base_url_host
from .prompts import SYSTEM_PROMPT, build_repair_prompt, build_user_prompt
from .schemas import (
    CardDraft,
    CardPayload,
    CommercialBlock,
    KeySpec,
    Meta,
    ProductInput,
)
from .validator import (
    DESC_MAX,
    DESC_MIN,
    QUERIES_MAX,
    TITLE_LIMIT,
    ValidationResult,
    detect_clarifications,
    detect_missing_fields,
    validate_payload,
)


class GenerationError(RuntimeError):
    """Модель не смогла вернуть пригодный ответ."""


SERIOUS_WARNING_PREFIXES = (
    "похоже на домысел",
    "возможное искажение",
    "число",
    "единица",
    "commercial_block: основание",
    "commercial_block: не указано основание",
)


def _needs_repair(result: ValidationResult) -> bool:
    if result.errors:
        return True
    return any(
        warning.startswith(SERIOUS_WARNING_PREFIXES) for warning in result.warnings
    )


def _parse_payload(raw: dict[str, Any]) -> tuple[CardPayload | None, list[str]]:
    try:
        return CardPayload.model_validate(raw), []
    except PydanticValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", ())) or "ответ"
        return None, [f"ответ модели не соответствует схеме ({location}): {first.get('msg', '')}"]


def _fit_title(title: str) -> tuple[str, str | None]:
    """Детерминированно укладывает заголовок в лимит по границе слова."""
    if len(title) <= TITLE_LIMIT:
        return title, None
    cut = title[:TITLE_LIMIT]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    cut = cut.rstrip(" ,;:—–-")
    if not cut:
        cut = title[:TITLE_LIMIT].rstrip()
    return cut, f"seo_title сокращён автоматически до {len(cut)} символов"


def _fit_description(text: str) -> tuple[str, str | None]:
    """Обрезает слишком длинное описание по границе предложения или слова."""
    if len(text) <= DESC_MAX:
        return text, None
    cut = text[:DESC_MAX]
    boundary = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if boundary + 1 >= DESC_MIN:
        cut = cut[: boundary + 1]
    else:
        space = cut.rfind(" ")
        if space > 0:
            cut = cut[:space]
    cut = cut.rstrip()
    return cut, f"seo_description сокращён автоматически до {len(cut)} символов"


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in queries:
        query = raw.strip()
        if not query or query.lower() in seen:
            continue
        seen.add(query.lower())
        result.append(query)
    return result


def _normalize_payload(payload: CardPayload) -> tuple[CardPayload, list[str]]:
    notes: list[str] = []

    title, note = _fit_title(payload.seo_title.strip())
    if note:
        notes.append(note)

    description, note = _fit_description(payload.seo_description.strip())
    if note:
        notes.append(note)

    queries = _dedupe_queries(payload.search_queries)
    if len(queries) > QUERIES_MAX:
        queries = queries[:QUERIES_MAX]
        notes.append(f"search_queries усечён автоматически до {QUERIES_MAX}")

    normalized = payload.model_copy(
        update={
            "seo_title": title,
            "seo_description": description,
            "search_queries": queries,
        }
    )
    return normalized, notes


def _complete_key_specs(specs: list[KeySpec], product: ProductInput) -> list[KeySpec]:
    """Дополняет список характеристик всем, что есть во входных specs."""
    covered = {spec.source_key for spec in specs}
    completed = list(specs)
    for key, value in product.specs.items():
        if key not in covered:
            completed.append(KeySpec(name=key, value=value, source_key=key))
    return completed


def generate_card(
    product: ProductInput,
    settings: Settings | None = None,
    client: LLMClient | Any | None = None,
) -> CardDraft:
    """Генерирует черновик карточки товара.

    ``client`` принимается для тестов: достаточно объекта с методом
    ``complete_json(system, user) -> (dict, dict)``.
    """
    if settings is None:
        settings = load_settings()
    llm = client or LLMClient(settings)

    missing_fields = detect_missing_fields(product)
    user_prompt = build_user_prompt(product, missing_fields)

    started = time.perf_counter()
    attempts = 0

    raw, call_meta = llm.complete_json(SYSTEM_PROMPT, user_prompt)
    payload, schema_errors = _parse_payload(raw)
    if payload is None:
        result = ValidationResult(errors=schema_errors)
    else:
        result = validate_payload(payload, product)

    while _needs_repair(result) and attempts < settings.max_repairs:
        attempts += 1
        repair_prompt = build_repair_prompt(
            product, raw, result.errors, result.warnings
        )
        raw, call_meta = llm.complete_json(SYSTEM_PROMPT, repair_prompt)
        payload, schema_errors = _parse_payload(raw)
        if payload is None:
            result = ValidationResult(errors=schema_errors)
        else:
            result = validate_payload(payload, product)

    if payload is None:
        raise GenerationError(
            "модель не вернула корректный JSON после повторной попытки: "
            + "; ".join(result.errors)
        )

    payload, auto_fixes = _normalize_payload(payload)
    result = validate_payload(payload, product)
    key_specs = _complete_key_specs(result.key_specs, product)

    warnings = auto_fixes + list(result.warnings)
    if result.errors:
        warnings.extend(f"не устранено после repair: {error}" for error in result.errors)

    meta = Meta(
        model=settings.model,
        base_url_host=base_url_host(settings.base_url),
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        latency_ms=int((time.perf_counter() - started) * 1000),
        prompt_tokens=call_meta.get("prompt_tokens"),
        completion_tokens=call_meta.get("completion_tokens"),
        repair_attempts=attempts,
        json_mode_used=str(call_meta.get("mode", "unknown")),
    )

    return CardDraft(
        seo_title=payload.seo_title,
        seo_description=payload.seo_description,
        key_specs=key_specs,
        search_queries=result.queries or _dedupe_queries(payload.search_queries),
        commercial_block=CommercialBlock(
            text=payload.commercial_block.text.strip(),
            basis=result.basis,
        ),
        missing_fields=missing_fields,
        needs_clarification=detect_clarifications(product),
        warnings=warnings,
        meta=meta,
    )
