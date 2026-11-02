"""Проверки результата: лимиты, привязка к входным данным, анти-галлюцинации."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .schemas import CardPayload, KeySpec, ProductInput

TITLE_LIMIT = 70
DESC_MIN = 800
DESC_MAX = 1200
QUERIES_MIN = 3
QUERIES_MAX = 5

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
UNIT_RE = re.compile(
    r"(?<=\d)\s?(?:мПа|МПа|кПа|Па|бар|psi|атм|мм|см|мА|мВ|кВт|Вт|кВ|В|°C|°С|%|Гц|кг|шт|ч|м|с)(?![\w])"
)
IP_RE = re.compile(r"\bip\s?\d{2}\b")

EXPECTED_GROUPS: dict[str, tuple[str, ...]] = {
    "диапазон измерений": ("диапазон", "пределы измерений"),
    "класс точности": ("класс точности", "точность"),
    "питание": ("питание", "напряжение"),
    "тип корпуса": ("корпус",),
    "степень защиты": ("степень защиты",),
    "интерфейсы": ("интерфейс", "выходной сигнал", "протокол"),
    "присоединение": ("присоединение", "резьба", "штуцер"),
}

HALLUCINATION_MARKERS: tuple[str, ...] = (
    "нержаве",
    "взрывозащ",
    "сертифи",
    "гаранти",
    "алюмини",
    "латун",
    "титан",
    "чугун",
    "пвх",
    "полипропилен",
    "фторопласт",
    "поверк",
    "надежн",
    "долговечн",
    "безотказн",
    "превосход",
)

CONTRADICTION_WORDS: tuple[str, ...] = (
    "агрессивн",
    "герметичн",
    "взрывоопасн",
    "горюч",
)

PLACEHOLDER_MARKERS: tuple[str, ...] = (
    "?",
    "уточн",
    "н/д",
    "нет данных",
    "не указан",
    "не указано",
    "tbd",
    "по запросу",
    "см. паспорт",
    "см паспорт",
)


@dataclass
class ValidationResult:
    """Итог проверки: блокирующие нарушения, предупреждения, очищенные данные."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    key_specs: list[KeySpec] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    basis: list[str] = field(default_factory=list)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("ё", "е").replace("Ё", "Е").strip().lower())


def _numbers(text: str) -> set[float]:
    return {float(match.replace(",", ".")) for match in NUMBER_RE.findall(text)}


def _units(text: str) -> set[str]:
    return {
        match.strip().lower().replace("°с", "°c") for match in UNIT_RE.findall(text)
    }


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:g}".replace(".", ",")


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _has_unnegated(text: str, word: str) -> bool:
    """Ищет слово без отрицания рядом: «не…», «не являются …», «неагрессивн»."""
    for match in re.finditer(re.escape(word), text):
        prefix = text[max(0, match.start() - 30) : match.start()]
        if prefix.endswith("не"):
            continue
        if re.search(r"(?<![а-яёa-z])не(?![а-яёa-z])", prefix):
            continue
        return True
    return False


def _input_text(product: ProductInput) -> str:
    parts = [product.name, product.manufacturer, product.description]
    for key, value in product.specs.items():
        parts.extend([key, value])
    return "\n".join(parts)


def _match_source_key(source_key: str, keys: list[str]) -> str | None:
    norm = _norm(source_key)
    if not norm:
        return None
    for key in keys:
        key_norm = _norm(key)
        if norm == key_norm or norm in key_norm or key_norm in norm:
            return key
    return None


def detect_missing_fields(product: ProductInput) -> list[str]:
    """Определяет разделы, которых нет во входных данных."""
    haystack = _norm(_input_text(product))
    missing: list[str] = []
    for group, synonyms in EXPECTED_GROUPS.items():
        if group == "степень защиты":
            covered = "степень защиты" in haystack or IP_RE.search(haystack) is not None
        else:
            covered = any(_norm(synonym) in haystack for synonym in synonyms)
        if not covered:
            missing.append(group)
    return missing


def detect_clarifications(product: ProductInput) -> list[str]:
    """Находит значения, которые есть во входе, но требуют уточнения."""
    clarifications: list[str] = []
    for key, value in product.specs.items():
        norm = _norm(value)
        if norm in ("", "-", "—", "–", "n/a", "na"):
            clarifications.append(f"{key}: пустое значение")
            continue
        marker = next((item for item in PLACEHOLDER_MARKERS if item in norm), None)
        if marker:
            clarifications.append(f"{key}: значение требует уточнения («{value}»)")
    description_norm = _norm(product.description)
    if any(
        marker in description_norm
        for marker in ("уточнить", "уточняется", "см. паспорт", "см паспорт")
    ):
        clarifications.append(
            "description: содержит отсылку к паспорту или пометку об уточнении"
        )
    return clarifications


def validate_payload(payload: CardPayload, product: ProductInput) -> ValidationResult:
    """Проверяет ответ модели и отбрасывает незаземлённые характеристики."""
    errors: list[str] = []
    warnings: list[str] = []

    title = payload.seo_title.strip()
    if len(title) > TITLE_LIMIT:
        errors.append(f"seo_title: {len(title)} символов, лимит {TITLE_LIMIT}")

    description = payload.seo_description.strip()
    if not DESC_MIN <= len(description) <= DESC_MAX:
        errors.append(
            f"seo_description: {len(description)} символов, нужно {DESC_MIN}–{DESC_MAX}"
        )

    queries: list[str] = []
    seen_queries: set[str] = set()
    for raw in payload.search_queries:
        query = raw.strip()
        if not query or query.lower() in seen_queries:
            continue
        seen_queries.add(query.lower())
        queries.append(query)
    if not QUERIES_MIN <= len(queries) <= QUERIES_MAX:
        errors.append(
            f"search_queries: {len(queries)} шт., нужно {QUERIES_MIN}–{QUERIES_MAX}"
        )

    input_text = _input_text(product)
    input_numbers = _numbers(input_text)
    input_units = _units(input_text)

    for label, text in (
        ("seo_title", title),
        ("seo_description", description),
        ("commercial_block", payload.commercial_block.text),
    ):
        for number in sorted(_numbers(text) - input_numbers):
            warnings.append(
                f"{label}: число {_format_number(number)} отсутствует во входных данных"
            )
        for unit in sorted(_units(text) - input_units):
            warnings.append(
                f"{label}: единица «{unit}» отсутствует во входных данных"
            )

    spec_keys = list(product.specs)
    kept_specs: list[KeySpec] = []
    for spec in payload.key_specs:
        matched = _match_source_key(spec.source_key, spec_keys)
        if not matched:
            warnings.append(
                f"key_specs: «{spec.name}» отброшено — source_key "
                f"«{spec.source_key}» отсутствует во входных данных"
            )
            continue
        source_value = product.specs[matched]
        value = spec.value.strip()
        if not value:
            warnings.append(f"key_specs: «{spec.name}» отброшено — пустое значение")
            continue
        bad_numbers = sorted(_numbers(value) - _numbers(source_value))
        if bad_numbers:
            warnings.append(
                f"key_specs: «{spec.name}» отброшено — значения "
                f"{', '.join(_format_number(n) for n in bad_numbers)} нет в «{matched}»"
            )
            continue
        bad_units = sorted(_units(value) - _units(source_value))
        if bad_units:
            warnings.append(
                f"key_specs: «{spec.name}» отброшено — единицы "
                f"{', '.join(bad_units)} нет в «{matched}»"
            )
            continue
        source_norm = _norm(source_value)
        invented = [m for m in HALLUCINATION_MARKERS if m in _norm(value) and m not in source_norm]
        if invented:
            warnings.append(
                f"key_specs: «{spec.name}» отброшено — похоже на домысел "
                f"({', '.join(invented)}…)"
            )
            continue
        kept_specs.append(
            KeySpec(name=spec.name.strip(), value=value, source_key=matched)
        )

    output_norm = _norm(
        " ".join(
            [title, description, payload.commercial_block.text]
            + [spec.value for spec in payload.key_specs]
        )
    )
    input_norm = _norm(input_text)
    for marker in HALLUCINATION_MARKERS:
        if marker in output_norm and marker not in input_norm:
            warnings.append(
                f"похоже на домысел: упоминание «{marker}…» отсутствует во входных данных"
            )

    input_without_negation = input_norm
    for word in CONTRADICTION_WORDS:
        input_without_negation = input_without_negation.replace("не" + word, "")
    for word in CONTRADICTION_WORDS:
        if _has_unnegated(output_norm, word) and word not in input_without_negation:
            warnings.append(
                f"возможное искажение: «{word}…» во входных данных указано с отрицанием"
            )

    basis: list[str] = []
    for item in payload.commercial_block.basis:
        if _norm(item) in ("description", "описание"):
            basis.append("description")
            continue
        matched_basis = _match_source_key(item, spec_keys)
        if matched_basis:
            basis.append(matched_basis)
        else:
            warnings.append(
                f"commercial_block: основание «{item}» отсутствует во входных данных"
            )
    if not basis and payload.commercial_block.text.strip():
        warnings.append("commercial_block: не указано основание для утверждений")

    return ValidationResult(
        errors=_dedupe(errors),
        warnings=_dedupe(warnings),
        key_specs=kept_specs,
        queries=queries,
        basis=_dedupe(basis),
    )
