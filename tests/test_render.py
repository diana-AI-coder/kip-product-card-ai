from __future__ import annotations

from app.render import to_json, to_markdown, to_text
from app.schemas import CardDraft, CommercialBlock, KeySpec, Meta


def _draft() -> CardDraft:
    return CardDraft(
        seo_title="Манометр DM 02 0–1,6 МПа",
        seo_description="Манометр DM 02 предназначен для измерения давления.",
        key_specs=[KeySpec(name="Диапазон", value="0–1,6 МПа", source_key="диапазон измерений")],
        search_queries=["манометр dm 02", "манометр 1,6 мпа", "манометр манотомь"],
        commercial_block=CommercialBlock(text="Подходит для измерения давления.", basis=["диапазон измерений"]),
        missing_fields=["питание"],
        warnings=["seo_title: пример предупреждения"],
        meta=Meta(
            model="fake-model",
            base_url_host="example.test",
            generated_at="2026-01-01T00:00:00+00:00",
            latency_ms=123,
        ),
    )


def test_markdown_has_required_sections() -> None:
    markdown = to_markdown(_draft())
    for section in (
        "## SEO-заголовок",
        "## SEO-описание",
        "## Ключевые характеристики",
        "## Поисковые запросы",
        "## Коммерческий блок",
        "## Недостающие данные",
        "## Требует уточнения",
    ):
        assert section in markdown
    assert "fake-model" in markdown


def test_text_output_contains_commercial_block() -> None:
    text = to_text(_draft())
    assert "КОММЕРЧЕСКИЙ БЛОК" in text
    assert "Подходит для измерения давления." in text


def test_json_output_is_valid_json() -> None:
    import json

    data = json.loads(to_json(_draft()))
    assert data["schema_version"] == "1.1"
    assert data["meta"]["model"] == "fake-model"
