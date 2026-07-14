"""Тесты для autodoc/cli/commands/config.py.

Тесты вызывают команду ``config`` через CliRunner — без реального subprocess,
без обращения к сети; конфиги пишутся во временную директорию.
"""

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from autodoc.cli.app import cli
from tests.unit.cli.conftest import VALID_PARSER_CONFIG

_EXIT_SUCCESS: int = 0


def _write_json(directory: Path, filename: str, data: dict) -> Path:
    """Записывает *data* в виде JSON в *directory / filename* и возвращает путь."""
    p: Path = directory / filename
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _write_yaml(directory: Path, filename: str, data: dict) -> Path:
    """Записывает *data* в виде YAML в *directory / filename* и возвращает путь."""
    p: Path = directory / filename
    p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return p


@pytest.mark.business_logic
def test_cli_config_validate_exits_zero_on_valid_config(
    configs_dir: Path,
) -> None:
    """Подкоманда validate завершается с кодом 0, если файл — синтаксически валидный YAML.

    Защита от падения команды validate на корректных входных данных.
    """
    _write_yaml(configs_dir, "parser_config.yaml", VALID_PARSER_CONFIG)
    result = CliRunner().invoke(
        cli,
        ["--configs-dir", str(configs_dir), "config", "validate", "parser_config.yaml"],
    )
    assert result.exit_code == _EXIT_SUCCESS, (
        f"Ожидался код выхода 0 для валидного конфига, получено {result.exit_code}.\n"
        f"вывод: {result.output}\nисключение: {result.exception}"
    )


@pytest.mark.business_logic
def test_cli_config_validate_exits_zero_on_valid_json_config(
    configs_dir: Path,
) -> None:
    """validate принимает .json файл (обратная совместимость).

    Проекты с существующими .json конфигами не должны ломаться.
    """
    _write_json(configs_dir, "parser_config.json", VALID_PARSER_CONFIG)
    result = CliRunner().invoke(
        cli,
        ["--configs-dir", str(configs_dir), "config", "validate", "parser_config.json"],
    )
    assert result.exit_code == _EXIT_SUCCESS, (
        f"Ожидался код выхода 0 для валидного JSON-конфига, получено {result.exit_code}.\n"
        f"вывод: {result.output}\nисключение: {result.exception}"
    )


@pytest.mark.business_logic
def test_cli_config_validate_exits_nonzero_on_invalid_config(
    configs_dir: Path,
) -> None:
    """Подкоманда validate завершается с ненулевым кодом, если файл — невалидный JSON.

    Гарантирует, что CLI показывает ошибку вызывающей стороне, а не проглатывает её.
    """
    invalid_path: Path = configs_dir / "bad.json"
    invalid_path.write_bytes(b"{not valid json")  # намеренно сломанный JSON
    result = CliRunner().invoke(
        cli,
        ["--configs-dir", str(configs_dir), "config", "validate", "bad.json"],
    )
    assert result.exit_code != _EXIT_SUCCESS, (
        f"Ожидался ненулевой код выхода для невалидного JSON, получено {result.exit_code}"
    )


@pytest.mark.business_logic
def test_cli_config_validate_error_is_human_readable(
    configs_dir: Path,
) -> None:
    """Вывод ошибки подкоманды validate не должен содержать «сырой» Python-трейсбек.

    Трейсбек в пользовательском выводе — это UX-дефект: сообщение об ошибке
    должно быть понятной диагностикой, а не внутренним стеком вызовов.
    """
    # Полностью сломанный JSON, чтобы гарантированно попасть в реальную ветку ошибки.
    broken: Path = configs_dir / "broken.json"
    broken.write_bytes(b"this is not json at all")
    result = CliRunner().invoke(
        cli,
        ["--configs-dir", str(configs_dir), "config", "validate", "broken.json"],
    )
    assert "Traceback" not in result.output, (
        "В выводе CLI обнаружен сырой Python-трейсбек — "
        "ошибка должна быть дружелюбной к пользователю."
    )
    assert 'File "' not in result.output, (
        "В выводе CLI обнаружена ссылка на файл Python — "
        "ошибка должна быть дружелюбной к пользователю."
    )


@pytest.mark.business_logic
def test_cli_config_list_shows_config_filenames(
    configs_dir: Path,
) -> None:
    """Подкоманда config list печатает имена всех JSON-файлов конфигов из configs_dir.

    Проверяет, что команда list находит файлы и показывает их имена пользователю.
    """
    _write_json(configs_dir, "config_a.json", VALID_PARSER_CONFIG)
    _write_json(configs_dir, "config_b.json", VALID_PARSER_CONFIG)
    result = CliRunner().invoke(
        cli,
        ["--configs-dir", str(configs_dir), "config", "list"],
    )
    assert result.exit_code == _EXIT_SUCCESS, (
        f"Ожидался код выхода 0 от config list, получено {result.exit_code}.\n"
        f"вывод: {result.output}\nисключение: {result.exception}"
    )
    assert "config_a.json" in result.output, "config_a.json отсутствует в выводе list"
    assert "config_b.json" in result.output, "config_b.json отсутствует в выводе list"


@pytest.mark.business_logic
def test_cli_config_list_on_empty_dir_exits_zero(
    configs_dir: Path,
) -> None:
    """Подкоманда config list завершается с кодом 0, даже если конфигов нет.

    Пустая директория конфигов — валидное состояние (первый запуск); CLI не должен падать.
    """
    result = CliRunner().invoke(
        cli,
        ["--configs-dir", str(configs_dir), "config", "list"],
    )
    assert result.exit_code == _EXIT_SUCCESS, (
        f"Ожидался код выхода 0 для пустой директории конфигов, получено {result.exit_code}.\n"
        f"вывод: {result.output}\nисключение: {result.exception}"
    )


@pytest.mark.business_logic
def test_cli_config_list_shows_yaml_config_filenames(configs_dir: Path) -> None:
    """config list отображает .yaml файлы в выводе."""
    _write_yaml(configs_dir, "parser_config.yaml", VALID_PARSER_CONFIG)
    result = CliRunner().invoke(cli, ["--configs-dir", str(configs_dir), "config", "list"])
    assert result.exit_code == _EXIT_SUCCESS
    assert "parser_config.yaml" in result.output


@pytest.mark.business_logic
def test_cli_config_list_shows_examples_section(configs_dir: Path) -> None:
    """config list показывает секцию примеров, если examples/ существует."""
    examples_dir = configs_dir / "examples"
    examples_dir.mkdir()
    _write_yaml(examples_dir, "parser_config.yaml", VALID_PARSER_CONFIG)

    result = CliRunner().invoke(cli, ["--configs-dir", str(configs_dir), "config", "list"])
    assert result.exit_code == _EXIT_SUCCESS
    assert "examples" in result.output.lower()
