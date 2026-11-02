from __future__ import annotations

import json
from pathlib import Path

from app.cli import main


def test_check_mode_validates_without_llm(tmp_path: Path, capsys) -> None:
    source = Path(__file__).resolve().parent.parent / "data" / "p1_manometr.json"
    target = tmp_path / "product.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    exit_code = main([str(target), "--check"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["name"].startswith("Манометр")
    assert "питание" in output["missing_fields"]


def test_invalid_json_returns_code_2(tmp_path: Path, capsys) -> None:
    target = tmp_path / "broken.json"
    target.write_text("{ не json", encoding="utf-8")

    assert main([str(target), "--check"]) == 2
    assert "Некорректный JSON" in capsys.readouterr().err


def test_missing_file_returns_code_2(tmp_path: Path) -> None:
    assert main([str(tmp_path / "absent.json"), "--check"]) == 2
