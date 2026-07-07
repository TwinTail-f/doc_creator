"""Тесты для autodoc/cli/commands/info.py и autodoc/cli/commands/logs.py.

Обзор тестового покрытия отдельно отмечает, что команды `info` и `logs`
"ни разу не вызываются через CliRunner ни в одном тесте". Это лёгкий
smoke-набор, не претендующий на исчерпывающий перечень сценариев.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from autodoc.cli.app import cli
from autodoc.cli.constants import VERSION

_EXIT_SUCCESS: int = 0
_LOGS_MODULE = "autodoc.cli.commands.logs"


def _invoke(tmp_path: Path, configs_dir: Path, *args: str):
    """Вызывает cli с переданными дополнительными аргументами командной строки.

    Args:
        tmp_path: Базовая директория проекта.
        configs_dir: Директория конфигов.
        *args: Дополнительные аргументы, передаваемые команде cli.

    Returns:
        Результат выполнения команды (``click.testing.Result``).
    """
    return CliRunner().invoke(
        cli,
        ["--base-dir", str(tmp_path), "--configs-dir", str(configs_dir), *args],
    )


@pytest.mark.business_logic
def test_info_exits_zero_and_shows_version(tmp_path: Path, configs_dir: Path) -> None:
    """info завершается с кодом 0 и выводит версию / список возможностей."""
    result = _invoke(tmp_path, configs_dir, "info")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    assert VERSION in result.output


@pytest.mark.business_logic
def test_logs_clear_yes_with_deleted_files_shows_count(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """logs clear --yes с непустым списком удалённых путей завершается с кодом 0 и показывает их количество."""
    deleted = [tmp_path / "logs" / "parser-2024.log", tmp_path / "logs" / "publisher-2024.log"]
    mocker.patch(f"{_LOGS_MODULE}.clear_logs_dir", return_value=deleted)

    result = _invoke(tmp_path, configs_dir, "logs", "clear", "--yes")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    assert "2" in result.output


@pytest.mark.business_logic
def test_logs_clear_yes_with_nothing_to_delete_shows_message(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """logs clear --yes с пустым списком удалённых путей завершается с кодом 0 и сообщением, что удалять нечего."""
    mocker.patch(f"{_LOGS_MODULE}.clear_logs_dir", return_value=[])

    result = _invoke(tmp_path, configs_dir, "logs", "clear", "--yes")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    assert "нет файлов" in result.output.lower() or "nothing" in result.output.lower()


@pytest.mark.contract
def test_logs_clear_without_yes_aborts_on_declined_confirmation(
    tmp_path: Path, configs_dir: Path
) -> None:
    """logs clear без --yes прерывает выполнение команды при отклонённом подтверждении."""
    result = CliRunner().invoke(
        cli,
        ["--base-dir", str(tmp_path), "--configs-dir", str(configs_dir), "logs", "clear"],
        input="n\n",
    )

    assert result.exit_code != _EXIT_SUCCESS
