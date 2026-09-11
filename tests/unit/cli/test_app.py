"""Тесты для autodoc.cli.app.cli (корневая группа команд)."""

import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from autodoc.cli.app import cli
from autodoc.cli.constants import VERSION

_EXIT_CONFIG_ERROR: int = 1

# Rich-консоль при длинных путях (например, глубокие временные каталоги pytest на
# Windows) переносит строку по ширине терминала и подсвечивает числа внутри пути
# ANSI-последовательностями. Из-за этого литеральный str(path) может не встретиться
# в выводе как непрерывная подстрока. Чтобы сравнение было устойчивым к переносу
# строк и подсветке, ANSI-коды вырезаются, а перенесённые строки склеиваются обратно.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    """Убирает ANSI-последовательности и склеивает перенесённые Rich строки."""
    return _ANSI_RE.sub("", text).replace("\n", "")


@pytest.mark.infrastructure
def test_cli_exits_with_error_when_configs_dir_missing(tmp_path: Path) -> None:
    missing_configs_dir = tmp_path / "configs"  # намеренно не создаём
    result = CliRunner().invoke(
        cli,
        ["--base-dir", str(tmp_path), "--configs-dir", str(missing_configs_dir), "info"],
    )
    plain_output = _plain(result.output)
    assert result.exit_code == _EXIT_CONFIG_ERROR
    assert str(missing_configs_dir) in plain_output
    assert VERSION not in plain_output  # подтверждаем, что до тела подкоманды не дошли
