"""Тесты для autodoc/cli/commands/info.py и autodoc/cli/commands/logs.py."""

from pathlib import Path

import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture

from autodoc.cli.app import cli
from autodoc.cli.constants import VERSION

_EXIT_SUCCESS: int = 0
_LOGS_MODULE = "autodoc.cli.commands.logs"


def _invoke(tmp_path: Path, configs_dir: Path, *args: str):
    """
    Вызывает cli с переданными дополнительными аргументами командной строки.

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


@pytest.mark.infrastructure
def test_info_exits_zero_and_shows_version(tmp_path: Path, configs_dir: Path) -> None:
    """info завершается с кодом 0 и выводит версию / список возможностей."""
    result = _invoke(tmp_path, configs_dir, "info")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    assert VERSION in result.output


@pytest.mark.infrastructure
@pytest.mark.parametrize(
    ("filenames", "expected_substring"),
    [
        # непустой список удалённых путей — в выводе показывается их количество
        pytest.param(["parser-2024.log", "publisher-2024.log"], "2", id="files-deleted"),
        # пустой список — выводится сообщение о том, что удалять нечего
        pytest.param([], "нет файлов", id="nothing-to-delete"),
    ],
)
def test_logs_clear_yes_shows_result_message(
    tmp_path: Path,
    configs_dir: Path,
    mocker: MockerFixture,
    filenames: list[str],
    expected_substring: str,
) -> None:
    """
    logs clear --yes завершается с кодом 0 и показывает количество удалённых файлов либо
    сообщение о том, что удалять нечего — в зависимости от результата clear_logs_dir."""
    deleted = [tmp_path / "logs" / name for name in filenames]
    mocker.patch(f"{_LOGS_MODULE}.clear_logs_dir", return_value=deleted)

    result = _invoke(tmp_path, configs_dir, "logs", "clear", "--yes")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    assert expected_substring in result.output.lower()


@pytest.mark.infrastructure
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
