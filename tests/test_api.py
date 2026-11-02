from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main_module
from app.schemas import CardDraft, CommercialBlock, KeySpec, Meta


def _draft() -> CardDraft:
    return CardDraft(
        seo_title="Манометр DM 02",
        seo_description="Манометр DM 02 предназначен для измерения давления.",
        key_specs=[KeySpec(name="Диапазон", value="0–1,6 МПа", source_key="диапазон измерений")],
        search_queries=["манометр dm 02", "манометр 1,6 мпа", "манометр манотомь"],
        commercial_block=CommercialBlock(text="Подходит для измерения давления.", basis=["диапазон измерений"]),
        missing_fields=["питание"],
        meta=Meta(
            model="fake-model",
            base_url_host="example.test",
            generated_at="2026-01-01T00:00:00+00:00",
            latency_ms=10,
        ),
    )


PRODUCT_BODY = {
    "name": "Манометр DM 02",
    "manufacturer": "Манотомь",
    "specs": {"диапазон измерений": "0–1,6 МПа"},
}


def test_index_page_renders_example(monkeypatch) -> None:
    client = TestClient(main_module.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "AI-помощник" in response.text
    assert "payload" in response.text


def test_api_generate_returns_draft(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "generate_card", lambda product: _draft())
    client = TestClient(main_module.app)
    response = client.post("/api/generate", json=PRODUCT_BODY)
    assert response.status_code == 200
    data = response.json()
    assert data["seo_title"] == "Манометр DM 02"
    assert data["key_specs"][0]["source_key"] == "диапазон измерений"


def test_api_rejects_invalid_input() -> None:
    client = TestClient(main_module.app)
    response = client.post("/api/generate", json={"name": "Без характеристик"})
    assert response.status_code == 422
