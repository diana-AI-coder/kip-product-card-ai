"""Рендеринг черновика карточки в Markdown и обычный текст."""

from __future__ import annotations

from .schemas import CardDraft


def to_markdown(draft: CardDraft) -> str:
    lines: list[str] = [f"# {draft.seo_title}", ""]

    lines += ["## SEO-заголовок", "", draft.seo_title, ""]
    lines += ["## SEO-описание", "", draft.seo_description, ""]

    lines += ["## Ключевые характеристики", ""]
    if draft.key_specs:
        for spec in draft.key_specs:
            lines.append(f"- **{spec.name}:** {spec.value}")
    else:
        lines.append("- данных нет")
    lines.append("")

    lines += ["## Поисковые запросы", ""]
    if draft.search_queries:
        lines += [f"{index}. {query}" for index, query in enumerate(draft.search_queries, 1)]
    else:
        lines.append("- данных нет")
    lines.append("")

    lines += ["## Коммерческий блок", "", draft.commercial_block.text, ""]
    if draft.commercial_block.basis:
        lines += ["_Основание: " + ", ".join(draft.commercial_block.basis) + "_", ""]

    lines += ["## Недостающие данные", ""]
    if draft.missing_fields:
        lines += [f"- {field}: данных нет" for field in draft.missing_fields]
    else:
        lines.append("- нет")
    lines.append("")

    lines += ["## Требует уточнения", ""]
    if draft.needs_clarification:
        lines += [f"- {item}" for item in draft.needs_clarification]
    else:
        lines.append("- нет")
    lines.append("")

    if draft.warnings:
        lines += ["## Предупреждения", ""]
        lines += [f"- {warning}" for warning in draft.warnings]
        lines.append("")

    lines += [
        "---",
        (
            f"_schema {draft.schema_version} · {draft.meta.model} · "
            f"{draft.meta.generated_at} · repair: {draft.meta.repair_attempts} · "
            f"{draft.meta.latency_ms} мс_"
        ),
        (
            f"_title: {len(draft.seo_title)}/70 · "
            f"description: {len(draft.seo_description)}/800–1200 · "
            f"queries: {len(draft.search_queries)}/3–5_"
        ),
    ]
    return "\n".join(lines) + "\n"


def to_text(draft: CardDraft) -> str:
    specs = (
        "\n".join(f"{spec.name}: {spec.value}" for spec in draft.key_specs)
        or "данных нет"
    )
    queries = (
        "\n".join(f"{index}. {query}" for index, query in enumerate(draft.search_queries, 1))
        or "данных нет"
    )
    missing = "\n".join(f"- {field}: данных нет" for field in draft.missing_fields) or "- нет"
    clarifications = (
        "\n".join(f"- {item}" for item in draft.needs_clarification) or "- нет"
    )
    warnings = "\n".join(f"- {warning}" for warning in draft.warnings)
    parts = [
        "SEO-ЗАГОЛОВОК",
        draft.seo_title,
        "",
        "SEO-ОПИСАНИЕ",
        draft.seo_description,
        "",
        "КЛЮЧЕВЫЕ ХАРАКТЕРИСТИКИ",
        specs,
        "",
        "ПОИСКОВЫЕ ЗАПРОСЫ",
        queries,
        "",
        "КОММЕРЧЕСКИЙ БЛОК",
        draft.commercial_block.text,
        "",
        "НЕДОСТАЮЩИЕ ДАННЫЕ",
        missing,
        "",
        "ТРЕБУЕТ УТОЧНЕНИЯ",
        clarifications,
    ]
    if warnings:
        parts += ["", "ПРЕДУПРЕЖДЕНИЯ", warnings]
    return "\n".join(parts) + "\n"


def to_json(draft: CardDraft) -> str:
    return draft.model_dump_json(indent=2)
