"""Тесты для autodoc/cli/commands/publish/all.py."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from autodoc.cli.app import cli
from autodoc.exceptions import ConfigError
from tests.unit.cli.utils import (
    make_confluence_config,
    make_publish_report,
    strategy_override,
)

_EXIT_SUCCESS: int = 0
_EXIT_FAILURE: int = 1

_MODULE = "autodoc.cli.commands.publish.all"


def _invoke(tmp_path: Path, configs_dir: Path, *args: str):
    """
    Вызывает `publish all` с переданными дополнительными аргументами командной строки.

    Args:
        tmp_path: Базовая директория проекта.
        configs_dir: Директория конфигов.
        *args: Дополнительные аргументы, передаваемые команде `publish all`.

    Returns:
        Результат выполнения команды (``click.testing.Result``).
    """
    return CliRunner().invoke(
        cli,
        [
            "--base-dir",
            str(tmp_path),
            "--configs-dir",
            str(configs_dir),
            "publish",
            "all",
            *args,
        ],
    )


@pytest.fixture()
def command_module() -> str:
    """Модуль команды, в котором подменяются ``make_publisher`` и ``load_parsed_data``."""
    return _MODULE


@pytest.mark.contract
def test_publish_all_passes_only_parsed_data_to_publisher(
    tmp_path: Path, configs_dir: Path, mock_publisher: MagicMock
) -> None:
    """
    ``publish all`` передаёт паблишеру только данные парсера, без заголовков и родителей.

    Заголовки страниц и родительские страницы паблишер берёт из конфига сам (там же они
    проверяются), поэтому команда без аргументов не должна подставлять никаких значений
    по умолчанию из CLI.
    """
    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    mock_publisher.publish_all.assert_called_once()
    assert set(mock_publisher.publish_all.call_args.kwargs) == {"parsed_data"}


@pytest.mark.business_logic
def test_publish_all_config_error_from_publisher_exits_nonzero_cleanly(
    tmp_path: Path, configs_dir: Path, mock_publisher: MagicMock
) -> None:
    """
    ``ConfigError`` из ``publisher.publish_all()`` (у выбранного типа не задан родитель)
    завершает команду с кодом 1 и понятным сообщением, без трейсбека.

    В тексте ошибки нет скобок и кавычек: Rich подсвечивает их отдельными ANSI-кодами, и
    сравнение строки целиком зависело бы от того, цветной ли у терминала вывод.
    """
    mock_publisher.publish_all.side_effect = ConfigError(
        "не задан родитель для strategies.kit_pinned"
    )

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_FAILURE
    assert "Traceback" not in result.output
    assert "не задан родитель для strategies.kit_pinned" in result.output


@pytest.mark.business_logic
def test_publish_all_prints_targets_selected_in_config(
    tmp_path: Path,
    configs_dir: Path,
    mock_publisher: MagicMock,
    make_publisher_mock: MagicMock,
) -> None:
    """
    Команда сообщает, какие типы публикации выбраны в ``publish_all.targets``.

    В конфиге выбраны только release и kit_latest (с родителями), поэтому в выводе должны
    быть именно они, а остальные типы не упоминаются.
    """
    confluence_config = make_confluence_config(
        strategies={
            **strategy_override("release")["strategies"],
            **strategy_override("kit_latest")["strategies"],
        },
        publish_all={"targets": ["release", "kit_latest"]},
    )
    make_publisher_mock.return_value = (mock_publisher, confluence_config)

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    assert "release, kit_latest" in result.output
    assert "passports" not in result.output


@pytest.mark.contract
@pytest.mark.parametrize(
    "removed_flag",
    [
        pytest.param("--passports-root-parent-name", id="passports-root-parent-name"),
        pytest.param("--passports-root-parent-id", id="passports-root-parent-id"),
        pytest.param("--release-root-page-name", id="release-root-page-name"),
        pytest.param("--release-root-page-id", id="release-root-page-id"),
        pytest.param("--release-doc-page-name", id="release-doc-page-name"),
        pytest.param("--with-additional-page-profile", id="with-additional-page-profile"),
        pytest.param("--additional-page-profile-name", id="additional-page-profile-name"),
        pytest.param("--no-passport-links", id="no-passport-links"),
    ],
)
def test_publish_all_rejects_removed_flags(
    tmp_path: Path, configs_dir: Path, mock_publisher: MagicMock, removed_flag: str
) -> None:
    """
    ``publish all`` не принимает флаги, которые раньше переопределяли конфиг.

    Click отклоняет неизвестную опцию с ненулевым кодом возврата, и публикация не
    запускается: молча проигнорированный флаг привёл бы к публикации не туда, куда
    рассчитывал пользователь.
    """
    result = _invoke(tmp_path, configs_dir, removed_flag)

    assert result.exit_code != _EXIT_SUCCESS
    assert "No such option" in result.output
    mock_publisher.publish_all.assert_not_called()


@pytest.mark.infrastructure
def test_publish_all_domain_error_exits_nonzero_cleanly(
    tmp_path: Path, configs_dir: Path, make_publisher_mock: MagicMock
) -> None:
    """ConfigError, возникающая в make_publisher, завершает команду с кодом 1 и понятным сообщением, без трейсбека."""
    make_publisher_mock.side_effect = ConfigError("Confluence config invalid")

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_FAILURE
    assert "Traceback" not in result.output
    assert "Confluence config invalid" in result.output


@pytest.mark.business_logic
def test_publish_all_partial_failure_exits_nonzero_with_error_text(
    tmp_path: Path, configs_dir: Path, mock_publisher: MagicMock
) -> None:
    """Неуспешный PublishReport (success=False) завершает команду с кодом 1 и печатает каждое сообщение об ошибке."""
    mock_publisher.publish_all.return_value = make_publish_report(
        success=False, pages_published=0, errors=["some page failed"]
    )

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_FAILURE
    assert "some page failed" in result.output


@pytest.mark.business_logic
def test_publish_all_zero_pages_published_exits_nonzero(
    tmp_path: Path, configs_dir: Path, mock_publisher: MagicMock
) -> None:
    """Успешный отчёт с pages_published=0 всё равно завершается кодом 1 (случай «публиковать нечего»)."""
    mock_publisher.publish_all.return_value = make_publish_report(
        success=True, pages_published=0
    )

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_FAILURE
