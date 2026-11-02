"""Схемы входных и выходных данных, JSON-схема для structured output."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProductInput(BaseModel):
    """Входные данные о товаре."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str
    manufacturer: str
    specs: dict[str, str] = Field(default_factory=dict)
    description: str = ""
    sku: str | None = None

    @field_validator("name", "manufacturer")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("поле обязательно и не может быть пустым")
        return value

    @field_validator("specs", mode="before")
    @classmethod
    def _coerce_specs(cls, value: Any) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError(
                'specs должен быть объектом вида {"характеристика": "значение"}'
            )
        result: dict[str, str] = {}
        for key, raw in value.items():
            key_str = str(key).strip()
            if not key_str:
                raise ValueError("ключ характеристики не может быть пустым")
            if raw is None:
                continue
            raw_str = ("да" if raw else "нет") if isinstance(raw, bool) else str(raw).strip()
            if raw_str:
                result[key_str] = raw_str
        return result

    @field_validator("description", "sku", mode="before")
    @classmethod
    def _str_or_empty(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @model_validator(mode="after")
    def _minimum_data(self) -> ProductInput:
        if not self.specs:
            raise ValueError(
                "нужен хотя бы один пункт в specs — без характеристик карточка не строится"
            )
        return self


class KeySpec(BaseModel):
    """Характеристика в карточке со ссылкой на исходный ключ."""

    name: str
    value: str
    source_key: str


class CommercialBlock(BaseModel):
    """Коммерческий блок для менеджера."""

    text: str
    basis: list[str] = Field(default_factory=list)


class CardPayload(BaseModel):
    """То, что возвращает LLM. meta/missing_fields считаются на нашей стороне."""

    seo_title: str
    seo_description: str
    key_specs: list[KeySpec] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    commercial_block: CommercialBlock


class Meta(BaseModel):
    """Метаданные генерации для воспроизводимости примеров."""

    model: str
    base_url_host: str
    generated_at: str
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    repair_attempts: int = 0
    json_mode_used: str = "unknown"


class CardDraft(BaseModel):
    """Готовый черновик карточки товара."""

    schema_version: str = "1.1"
    seo_title: str
    seo_description: str
    key_specs: list[KeySpec]
    search_queries: list[str]
    commercial_block: CommercialBlock
    missing_fields: list[str] = Field(default_factory=list)
    needs_clarification: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    meta: Meta


CARD_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "seo_title",
        "seo_description",
        "key_specs",
        "search_queries",
        "commercial_block",
    ],
    "properties": {
        "seo_title": {
            "type": "string",
            "description": "SEO-заголовок, не длиннее 70 символов с пробелами",
        },
        "seo_description": {
            "type": "string",
            "description": "SEO-описание, 800–1200 символов с пробелами, сплошной текст",
        },
        "key_specs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "value", "source_key"],
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "string"},
                    "source_key": {
                        "type": "string",
                        "description": "точное имя ключа из INPUT specs",
                    },
                },
            },
        },
        "search_queries": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 5,
        },
        "commercial_block": {
            "type": "object",
            "additionalProperties": False,
            "required": ["text", "basis"],
            "properties": {
                "text": {"type": "string"},
                "basis": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ключи INPUT specs, на которые опираются утверждения",
                },
            },
        },
    },
}
