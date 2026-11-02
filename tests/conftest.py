from __future__ import annotations

import pytest

from app.schemas import ProductInput


@pytest.fixture
def product() -> ProductInput:
    return ProductInput(
        name="Манометр показывающий DM 02",
        manufacturer="Манотомь",
        specs={
            "диапазон измерений": "0–1,6 МПа",
            "класс точности": "1,5",
            "присоединение": "G1/2",
            "диаметр корпуса": "100 мм",
            "степень защиты": "IP65",
            "материал корпуса": "сталь",
        },
        description="Манометр предназначен для измерения избыточного давления.",
    )
