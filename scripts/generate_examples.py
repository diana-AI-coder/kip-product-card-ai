"""Генерирует примеры карточек для двух тестовых товаров (JSON + Markdown).

Запуск: python -m scripts.generate_examples  (нужен настроенный .env)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.config import ConfigError, load_settings
from app.generator import GenerationError, generate_card
from app.llm import LLMError
from app.render import to_json, to_markdown
from app.schemas import ProductInput

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ("p1_manometr", "p2_metran")


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Ошибка конфигурации: {exc}", file=sys.stderr)
        return 3

    examples_dir = ROOT / "examples"
    examples_dir.mkdir(exist_ok=True)

    for stem in PRODUCTS:
        source = ROOT / "data" / f"{stem}.json"
        product = ProductInput.model_validate(
            json.loads(source.read_text(encoding="utf-8"))
        )
        try:
            draft = generate_card(product, settings=settings)
        except (LLMError, GenerationError) as exc:
            print(f"{stem}: ошибка генерации: {exc}", file=sys.stderr)
            return 4

        (examples_dir / f"{stem}.json").write_text(to_json(draft), encoding="utf-8")
        (examples_dir / f"{stem}.md").write_text(to_markdown(draft), encoding="utf-8")
        print(
            f"{stem}: готово (repair={draft.meta.repair_attempts}, "
            f"warnings={len(draft.warnings)}, {draft.meta.latency_ms} мс)"
        )
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
