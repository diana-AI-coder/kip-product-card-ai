from __future__ import annotations

from app.prompts import SYSTEM_PROMPT, build_repair_prompt, build_user_prompt
from app.schemas import ProductInput


def _product() -> ProductInput:
    return ProductInput(
        name="Манометр DM 02",
        manufacturer="Манотомь",
        specs={"диапазон измерений": "0–1,6 МПа", "класс точности": "1,5"},
        description="Прибор для измерения давления.",
    )


def test_system_prompt_contains_grounding_rules() -> None:
    for phrase in (
        "Единственный источник фактов",
        "Не конвертируй",
        "не придумывай замену",
        "commercial_block.basis",
    ):
        assert phrase in SYSTEM_PROMPT


def test_user_prompt_contains_all_input_specs() -> None:
    prompt = build_user_prompt(_product(), ["питание"])
    assert "диапазон измерений" in prompt
    assert "класс точности" in prompt
    assert "питание" in prompt


def test_repair_prompt_lists_violations_and_previous_answer() -> None:
    prompt = build_repair_prompt(
        _product(),
        {"seo_title": "старый ответ"},
        ["seo_title: 80 символов, лимит 70"],
        ["похоже на домысел: нержаве"],
    )
    assert "seo_title: 80 символов" in prompt
    assert "похоже на домысел" in prompt
    assert "старый ответ" in prompt
