"""CLI: python -m app.cli data/p1_manometr.json --format md"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from .config import ConfigError, load_settings
from .generator import GenerationError, generate_card
from .llm import LLMError
from .render import to_json, to_markdown, to_text
from .schemas import ProductInput
from .validator import detect_missing_fields

RENDERERS = {"json": to_json, "md": to_markdown, "txt": to_text}


def _read_product(path: Path) -> ProductInput:
    text = path.read_text(encoding="utf-8-sig")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("входной JSON должен быть объектом")
    return ProductInput.model_validate(data)


def _print_validation_error(exc: PydanticValidationError) -> None:
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())) or "вход"
        print(f"Ошибка входных данных: {location}: {error.get('msg')}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Генерация черновика карточки товара КИП через LLM.",
    )
    parser.add_argument("input", type=Path, help="путь к JSON с данными о товаре")
    parser.add_argument(
        "--format", "-f", choices=sorted(RENDERERS), default="md", help="формат вывода"
    )
    parser.add_argument("--out", "-o", type=Path, help="записать результат в файл")
    parser.add_argument(
        "--check",
        action="store_true",
        help="только проверить входные данные, без обращения к LLM",
    )
    args = parser.parse_args(argv)

    try:
        product = _read_product(args.input)
    except FileNotFoundError:
        print(f"Файл не найден: {args.input}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"Некорректный JSON: {exc.msg} (строка {exc.lineno})", file=sys.stderr)
        return 2
    except (ValueError, PydanticValidationError) as exc:
        if isinstance(exc, PydanticValidationError):
            _print_validation_error(exc)
        else:
            print(f"Ошибка входных данных: {exc}", file=sys.stderr)
        return 2

    if args.check:
        summary = {
            "name": product.name,
            "manufacturer": product.manufacturer,
            "specs_count": len(product.specs),
            "missing_fields": detect_missing_fields(product),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Ошибка конфигурации: {exc}", file=sys.stderr)
        return 3

    try:
        draft = generate_card(product, settings=settings)
    except (LLMError, GenerationError) as exc:
        print(f"Ошибка генерации: {exc}", file=sys.stderr)
        return 4

    rendered = RENDERERS[args.format](draft)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
        print(f"Готово: {args.out}", file=sys.stderr)
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
