from __future__ import annotations

from app.config import Settings
from app.generator import generate_card
from app.schemas import ProductInput


class FakeClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.calls: list[str] = []

    def complete_json(self, system_prompt: str, user_prompt: str):
        self.calls.append(user_prompt)
        payload = self.payloads.pop(0)
        return payload, {
            "mode": "schema",
            "prompt_tokens": 100,
            "completion_tokens": 200,
        }


def _settings(max_repairs: int = 1) -> Settings:
    return Settings(
        base_url="https://api.example.test/v1",
        api_key="test-key",
        model="fake-model",
        max_repairs=max_repairs,
    )


def _payload(**overrides) -> dict:
    base = {
        "seo_title": "Манометр DM 02 0–1,6 МПа",
        "seo_description": "Манометр DM 02 предназначен для измерения давления. " * 18,
        "key_specs": [
            {
                "name": "Диапазон измерений",
                "value": "0–1,6 МПа",
                "source_key": "диапазон измерений",
            }
        ],
        "search_queries": ["манометр dm 02", "манометр 1,6 мпа", "манометр манотомь"],
        "commercial_block": {
            "text": "Подходит для измерения давления до 1,6 МПа.",
            "basis": ["диапазон измерений"],
        },
    }
    base.update(overrides)
    return base


def test_generate_returns_grounded_draft(product: ProductInput) -> None:
    client = FakeClient([_payload()])
    draft = generate_card(product, settings=_settings(), client=client)
    assert draft.seo_title.startswith("Манометр")
    assert draft.meta.repair_attempts == 0
    assert draft.meta.json_mode_used == "schema"
    assert draft.key_specs[0].source_key == "диапазон измерений"
    assert "питание" in draft.missing_fields
    assert len(client.calls) == 1


def test_short_description_triggers_single_repair(product: ProductInput) -> None:
    client = FakeClient([_payload(seo_description="слишком коротко"), _payload()])
    draft = generate_card(product, settings=_settings(), client=client)
    assert len(client.calls) == 2
    assert draft.meta.repair_attempts == 1
    assert 800 <= len(draft.seo_description) <= 1200


def test_invented_spec_is_dropped_with_warning(product: ProductInput) -> None:
    payload = _payload(
        key_specs=[
            {
                "name": "Материал корпуса",
                "value": "нержавеющая сталь",
                "source_key": "материал корпуса",
            }
        ]
    )
    draft = generate_card(product, settings=_settings(max_repairs=0), client=FakeClient([payload]))
    assert all("нержаве" not in spec.value for spec in draft.key_specs)
    material = [spec for spec in draft.key_specs if spec.source_key == "материал корпуса"]
    assert material and material[0].value == "сталь"
    assert any("домысел" in warning for warning in draft.warnings)


def test_key_specs_are_completed_from_input(product: ProductInput) -> None:
    draft = generate_card(
        product, settings=_settings(max_repairs=0), client=FakeClient([_payload()])
    )
    assert len(draft.key_specs) == len(product.specs)
    assert {spec.source_key for spec in draft.key_specs} == set(product.specs)


def test_title_is_trimmed_to_limit(product: ProductInput) -> None:
    long_title = "Манометр показывающий DM 02 Манотомь для измерения давления " + "очень " * 4
    draft = generate_card(
        product,
        settings=_settings(max_repairs=0),
        client=FakeClient([_payload(seo_title=long_title)]),
    )
    assert len(draft.seo_title) <= 70
    assert any("сокращён автоматически" in warning for warning in draft.warnings)


def test_queries_are_capped_to_five(product: ProductInput) -> None:
    queries = [f"манометр dm 02 вариант {index}" for index in range(7)]
    draft = generate_card(
        product,
        settings=_settings(max_repairs=0),
        client=FakeClient([_payload(search_queries=queries)]),
    )
    assert len(draft.search_queries) == 5
    assert any("усечён автоматически" in warning for warning in draft.warnings)


def test_overlong_description_is_trimmed(product: ProductInput) -> None:
    draft = generate_card(
        product,
        settings=_settings(max_repairs=0),
        client=FakeClient([_payload(seo_description="а" * 1300)]),
    )
    assert len(draft.seo_description) <= 1200
    assert any("сокращён автоматически" in warning for warning in draft.warnings)


def test_needs_clarification_is_reported(product: ProductInput) -> None:
    ambiguous = product.model_copy(
        update={"specs": {**product.specs, "питание": "уточнить у производителя"}}
    )
    draft = generate_card(
        ambiguous,
        settings=_settings(max_repairs=0),
        client=FakeClient([_payload()]),
    )
    assert any("питание" in item for item in draft.needs_clarification)


def test_schema_violation_then_repair(product: ProductInput) -> None:
    broken = _payload()
    broken["key_specs"] = "не список"
    client = FakeClient([broken, _payload()])
    draft = generate_card(product, settings=_settings(), client=client)
    assert len(client.calls) == 2
    assert draft.meta.repair_attempts == 1
