from __future__ import annotations

from app.schemas import CardPayload, CommercialBlock, KeySpec, ProductInput
from app.validator import (
    _numbers,
    _units,
    detect_clarifications,
    detect_missing_fields,
    validate_payload,
)


def _payload(**overrides) -> CardPayload:
    base = {
        "seo_title": "Манометр DM 02 0–1,6 МПа",
        "seo_description": "Манометр DM 02 предназначен для измерения давления. " * 18,
        "key_specs": [
            KeySpec(name="Диапазон измерений", value="0–1,6 МПа", source_key="диапазон измерений")
        ],
        "search_queries": [
            "манометр dm 02",
            "манометр 1,6 мпа",
            "манометр манотомь",
        ],
        "commercial_block": CommercialBlock(
            text="Подходит для измерения давления до 1,6 МПа.",
            basis=["диапазон измерений"],
        ),
    }
    base.update(overrides)
    return CardPayload(**base)


def test_number_extraction_handles_comma_and_range() -> None:
    assert _numbers("0–1,6 МПа и 100 мм") == {0.0, 1.6, 100.0}


def test_unit_extraction_prefers_longest_unit() -> None:
    assert _units("0–1,6 МПа, 100 мм, 24 В") == {"мпа", "мм", "в"}


def test_units_require_preceding_number() -> None:
    assert _units("работает с давлением и в условиях") == set()
    assert _units("от −40 до +60 °C") == {"°c"}


def test_title_over_limit_is_error(product: ProductInput) -> None:
    result = validate_payload(_payload(seo_title="М" * 71), product)
    assert any("seo_title" in error for error in result.errors)


def test_description_out_of_range_is_error(product: ProductInput) -> None:
    result = validate_payload(_payload(seo_description="коротко"), product)
    assert any("seo_description" in error for error in result.errors)


def test_queries_are_deduped_and_counted(product: ProductInput) -> None:
    result = validate_payload(
        _payload(search_queries=["манометр dm 02", "Манометр DM 02", "манометр манотомь"]),
        product,
    )
    assert result.queries == ["манометр dm 02", "манометр манотомь"]
    assert any("search_queries" in error for error in result.errors)


def test_unknown_source_key_drops_spec(product: ProductInput) -> None:
    result = validate_payload(
        _payload(
            key_specs=[KeySpec(name="Масса", value="2 кг", source_key="масса прибора")]
        ),
        product,
    )
    assert result.key_specs == []
    assert any("source_key" in warning for warning in result.warnings)


def test_invented_number_drops_spec(product: ProductInput) -> None:
    result = validate_payload(
        _payload(
            key_specs=[
                KeySpec(name="Диапазон", value="0–2,5 МПа", source_key="диапазон измерений")
            ]
        ),
        product,
    )
    assert result.key_specs == []
    assert any("нет в" in warning for warning in result.warnings)


def test_hallucinated_material_drops_spec(product: ProductInput) -> None:
    result = validate_payload(
        _payload(
            key_specs=[
                KeySpec(
                    name="Материал корпуса",
                    value="нержавеющая сталь",
                    source_key="материал корпуса",
                )
            ]
        ),
        product,
    )
    assert result.key_specs == []
    assert any("домысел" in warning for warning in result.warnings)


def test_hallucination_marker_in_prose_is_warning(product: ProductInput) -> None:
    result = validate_payload(
        _payload(
            commercial_block=CommercialBlock(
                text="Корпус из нержавеющей стали, давление до 1,6 МПа.",
                basis=["диапазон измерений"],
            )
        ),
        product,
    )
    assert any("нержаве" in warning for warning in result.warnings)


def test_missing_fields_reports_absent_groups(product: ProductInput) -> None:
    missing = detect_missing_fields(product)
    assert "питание" in missing
    assert "интерфейсы" in missing
    assert "диапазон измерений" not in missing


def test_clarifications_detect_placeholder_values(product: ProductInput) -> None:
    ambiguous = product.model_copy(
        update={
            "specs": {**product.specs, "питание": "уточнить у производителя"},
            "description": "Часть данных уточняется по паспорту.",
        }
    )
    items = detect_clarifications(ambiguous)
    assert any("питание" in item for item in items)
    assert any("description" in item for item in items)
    assert detect_clarifications(product) == []


def test_basis_is_validated_against_spec_keys(product: ProductInput) -> None:
    result = validate_payload(
        _payload(
            commercial_block=CommercialBlock(
                text="Подходит для измерения давления до 1,6 МПа.",
                basis=["specs", "диапазон измерений"],
            )
        ),
        product,
    )
    assert result.basis == ["диапазон измерений"]
    assert any("основание" in warning for warning in result.warnings)


def test_negated_word_in_output_is_flagged(product: ProductInput) -> None:
    negated = product.model_copy(
        update={"description": "Прибор для неагрессивных жидкостей и газов."}
    )
    result = validate_payload(
        _payload(
            seo_description=(
                "Манометр подходит для агрессивных сред и измерения давления. " * 14
            )
        ),
        negated,
    )
    assert any("искажение" in warning for warning in result.warnings)


def test_split_negation_is_not_flagged(product: ProductInput) -> None:
    negated = product.model_copy(
        update={"description": "Среда не является агрессивной."}
    )
    result = validate_payload(
        _payload(
            seo_description=(
                "Манометр для сред, которые не являются агрессивными к сплавам. " * 12
            )
        ),
        negated,
    )
    assert not any("искажение" in warning for warning in result.warnings)
