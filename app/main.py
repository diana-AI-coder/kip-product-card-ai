"""Веб-форма и JSON API на FastAPI."""

from __future__ import annotations

import html
import json
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import ValidationError as PydanticValidationError

from .config import ConfigError
from .generator import GenerationError, generate_card
from .llm import LLMError
from .render import to_json, to_markdown, to_text
from .schemas import ProductInput

app = FastAPI(
    title="AI-помощник: карточки товаров КИП",
    version="1.0.0",
    description="Генерирует черновик карточки товара по JSON с характеристиками прибора.",
)

RENDERERS = {"json": to_json, "md": to_markdown, "txt": to_text}
EXAMPLE_PATH = Path(__file__).resolve().parent.parent / "data" / "p1_manometr.json"

INDEX_TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI-помощник · карточки товаров КИП</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 0; background: #f5f6f8; color: #1c1e21; }
  main { max-width: 1100px; margin: 0 auto; padding: 24px 16px 48px; }
  h1 { font-size: 22px; margin: 0 0 6px; }
  p.hint { margin: 0 0 20px; color: #5b6270; font-size: 14px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 860px) { .grid { grid-template-columns: 1fr; } }
  .panel { background: #fff; border: 1px solid #dfe3e8; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; }
  label { font-size: 13px; font-weight: 600; margin-bottom: 6px; }
  textarea { width: 100%; min-height: 380px; resize: vertical; font-family: ui-monospace, Consolas, monospace; font-size: 12.5px; line-height: 1.5; padding: 10px; border: 1px solid #cfd5dd; border-radius: 8px; box-sizing: border-box; }
  .row { display: flex; gap: 10px; align-items: center; margin-top: 10px; flex-wrap: wrap; }
  select, button { font: inherit; padding: 8px 12px; border-radius: 8px; border: 1px solid #cfd5dd; background: #fff; }
  button.primary { background: #1f6feb; border-color: #1f6feb; color: #fff; cursor: pointer; }
  button.primary:disabled { opacity: .6; cursor: progress; }
  button.ghost { cursor: pointer; }
  .error { background: #fdecec; border: 1px solid #f3b7b7; color: #8a1f1f; padding: 10px 12px; border-radius: 8px; margin-bottom: 12px; font-size: 14px; }
  .meta { color: #5b6270; font-size: 12px; margin-top: 8px; }
</style>
</head>
<body>
<main>
  <h1>AI-помощник для карточек товаров КИП</h1>
  <p class="hint">Вставьте JSON с данными о приборе. Модель использует только эти данные и помечает отсутствующие сведения.</p>
  __ERROR__
  <form method="post" action="/generate" class="grid">
    <div class="panel">
      <label for="payload">Входной JSON</label>
      <textarea id="payload" name="payload" spellcheck="false">__FORM__</textarea>
      <div class="row">
        <select name="fmt" aria-label="Формат результата">__SELECT__</select>
        <button class="primary" type="submit">Сгенерировать</button>
      </div>
    </div>
    <div class="panel">
      <label for="result">Результат</label>
      <textarea id="result" spellcheck="false" readonly>__RESULT__</textarea>
      <div class="row">
        <button class="ghost" type="button" onclick="copyResult()">Копировать</button>
      </div>
      <div class="meta">API: <code>POST /api/generate</code> с JSON товара возвращает структурированный результат.</div>
    </div>
  </form>
</main>
<script>
function copyResult() {
  const area = document.getElementById('result');
  if (!area || !area.value) return;
  navigator.clipboard.writeText(area.value).then(() => {
    const button = event.target;
    const text = button.textContent;
    button.textContent = 'Скопировано';
    setTimeout(() => { button.textContent = text; }, 1200);
  });
}
</script>
</body>
</html>
"""


def _example_json() -> str:
    try:
        return EXAMPLE_PATH.read_text(encoding="utf-8")
    except OSError:
        return json.dumps(
            {"name": "Манометр", "manufacturer": "Производитель", "specs": {"диапазон": "0–1 МПа"}},
            ensure_ascii=False,
            indent=2,
        )


def _select_options(current: str) -> str:
    labels = {"md": "Markdown", "json": "JSON", "txt": "Текст"}
    return "".join(
        f'<option value="{value}"{" selected" if value == current else ""}>{label}</option>'
        for value, label in labels.items()
    )


def _page(result: str = "", form_json: str = "", error: str = "", fmt: str = "md") -> str:
    return (
        INDEX_TEMPLATE.replace("__ERROR__", f'<div class="error">{html.escape(error)}</div>' if error else "")
        .replace("__FORM__", html.escape(form_json or _example_json()))
        .replace("__RESULT__", html.escape(result))
        .replace("__SELECT__", _select_options(fmt))
    )


def _error_code(exc: Exception) -> int:
    if isinstance(exc, (ValueError, PydanticValidationError)):
        return 400
    if isinstance(exc, ConfigError):
        return 503
    return 502


def _describe(exc: Exception) -> str:
    if isinstance(exc, PydanticValidationError):
        parts = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", ())) or "вход"
            parts.append(f"{location}: {error.get('msg')}")
        return "; ".join(parts)
    if isinstance(exc, ConfigError):
        return f"Не настроен доступ к LLM: {exc}"
    if isinstance(exc, (LLMError, GenerationError)):
        return f"Ошибка генерации: {exc}"
    return str(exc)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _page()


@app.post("/generate", response_class=HTMLResponse)
def generate_form(payload: str = Form(...), fmt: str = Form("md")) -> HTMLResponse:
    fmt = fmt if fmt in RENDERERS else "md"
    try:
        product = ProductInput.model_validate(json.loads(payload))
        draft = generate_card(product)
    except Exception as exc:  # noqa: BLE001 - форма показывает любую ошибку пользователю
        return HTMLResponse(
            _page(form_json=payload, error=_describe(exc), fmt=fmt),
            status_code=_error_code(exc),
        )
    return HTMLResponse(_page(result=RENDERERS[fmt](draft), form_json=payload, fmt=fmt))


@app.post("/api/generate")
def generate_api(body: dict) -> dict:
    try:
        product = ProductInput.model_validate(body)
        draft = generate_card(product)
    except PydanticValidationError as exc:
        raise HTTPException(status_code=422, detail=_describe(exc)) from exc
    except ConfigError as exc:
        raise HTTPException(status_code=503, detail=_describe(exc)) from exc
    except (LLMError, GenerationError) as exc:
        raise HTTPException(status_code=502, detail=_describe(exc)) from exc
    return draft.model_dump(mode="json")
