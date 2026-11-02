from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import ProductInput

BASE = {
    "name": "Манометр DM 02",
    "manufacturer": "Манотомь",
    "specs": {"диапазон измерений": "0–1,6 МПа"},
}


def test_empty_description_is_allowed() -> None:
    product = ProductInput.model_validate({**BASE, "description": ""})
    assert product.description == ""


def test_none_spec_values_are_skipped() -> None:
    product = ProductInput.model_validate(
        {**BASE, "specs": {"диапазон измерений": "0–1,6 МПа", "масса": None}}
    )
    assert product.specs == {"диапазон измерений": "0–1,6 МПа"}


def test_numeric_spec_values_are_coerced_to_string() -> None:
    product = ProductInput.model_validate(
        {**BASE, "specs": {"класс точности": 1.5, "интерфейс": True}}
    )
    assert product.specs == {"класс точности": "1.5", "интерфейс": "да"}


def test_extra_fields_are_ignored() -> None:
    product = ProductInput.model_validate({**BASE, "price": 1000, "unknown": "x"})
    assert not hasattr(product, "price")


def test_missing_specs_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductInput.model_validate({"name": "Манометр", "manufacturer": "Манотомь", "specs": {}})


def test_non_object_specs_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductInput.model_validate({**BASE, "specs": ["диапазон", "0–1,6 МПа"]})


def test_empty_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductInput.model_validate({**BASE, "name": "   "})
