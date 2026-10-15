"""Тесты для autodoc/cli/commands/publish/all.py."""

from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture

from autodoc.cli.app import cli
from autodoc.cli.constants import (
    DEFAULT_KIT_LATEST_PAGE_TITLE,
    DEFAULT_KIT_PINNED_PAGE_TITLE,
    DEFAULT_PROFILE_PAGE_TITLE,
    DEFAULT_RELEASE_PAGE_TITLE,
)
from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfigError
from tests.unit.cli.utils import (
    make_confluence_config,
    make_parsed_result,
    make_publish_report,
    strategy_override,
)

_EXIT_SUCCESS: int = 0
_EXIT_FAILURE: int = 1


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


def _mock_collaborators(mocker: MockerFixture, publish_report=None, confluence_config=None):
    """
    Подменяет make_publisher и load_parsed_data для `publish all` и возвращает поддельный publisher.

    Args:
        mocker: Фикстура pytest-mock для создания подмен.
        publish_report: Отчёт о публикации, который вернёт publish_all
            (по умолчанию — успешный отчёт).
        confluence_config: Конфиг Confluence, возвращаемый make_publisher
            (по умолчанию — минимальный валидный конфиг).

    Returns:
        Поддельный объект publisher с настроенным publish_all.
    """
    mock_publisher = mocker.MagicMock()
    mock_publisher.publish_all.return_value = publish_report or make_publish_report()
    mocker.patch(
        "autodoc.cli.commands.publish.all.make_publisher",
        return_value=(mock_publisher, confluence_config or make_confluence_config()),
    )
    mocker.patch(
        "autodoc.cli.commands.publish.all.load_parsed_data",
        return_value=make_parsed_result(),
    )
    return mock_publisher


def _config_with_titles(titles: dict[str, str | None]) -> ConfluenceConfigSchema:
    """
    Создаёт конфиг Confluence с заданными ``page_title`` в указанных секциях ``strategies``.

    Args:
        titles: Соответствие «ключ секции стратегии → заголовок страницы».

    Returns:
        Провалидированный конфиг, в котором перечисленные секции имеют валидного родителя.
    """
    strategies: dict[str, Any] = {}
    for section, title in titles.items():
        strategies.update(strategy_override(section, page_title=title)["strategies"])
    return make_confluence_config(strategies=strategies)


@pytest.mark.business_logic
def test_publish_all_takes_all_titles_from_config(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """
    Заголовки всех страниц берутся из секции ``strategies`` конфига Confluence.

    В конфиге заданы собственные заголовки release, profile_centric, kit_pinned и kit_latest.
    Команда запускается без аргументов и должна передать в ``publisher.publish_all()``
    именно их, а ничего другого (значения по умолчанию) не подставлять.
    """
    confluence_config = _config_with_titles(
        {
            "release": "Release Title",
            "profile_centric": "Profile Title",
            "kit_pinned": "Pinned Title",
            "kit_latest": "Latest Title",
        }
    )
    mock_publisher = _mock_collaborators(mocker, confluence_config=confluence_config)

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    mock_publisher.publish_all.assert_called_once()
    kwargs = mock_publisher.publish_all.call_args.kwargs
    assert kwargs["release_page_title"] == "Release Title"
    assert kwargs["profile_page_title"] == "Profile Title"
    assert kwargs["kit_pinned_page_title"] == "Pinned Title"
    assert kwargs["kit_latest_page_title"] == "Latest Title"


@pytest.mark.business_logic
@pytest.mark.parametrize(
    ("strategy_type", "kwarg_name", "default_title"),
    [
        pytest.param("release", "release_page_title", DEFAULT_RELEASE_PAGE_TITLE, id="release"),
        pytest.param(
            "profile_centric", "profile_page_title", DEFAULT_PROFILE_PAGE_TITLE, id="profile"
        ),
        pytest.param(
            "kit_pinned", "kit_pinned_page_title", DEFAULT_KIT_PINNED_PAGE_TITLE, id="kit-pinned"
        ),
        pytest.param(
            "kit_latest", "kit_latest_page_title", DEFAULT_KIT_LATEST_PAGE_TITLE, id="kit-latest"
        ),
    ],
)
def test_publish_all_falls_back_to_default_title_when_config_title_is_empty(
    tmp_path: Path,
    configs_dir: Path,
    mocker: MockerFixture,
    strategy_type: str,
    kwarg_name: str,
    default_title: str,
) -> None:
    """
    Если ``page_title`` секции в конфиге не задан (``None``), используется заголовок по умолчанию.

    Проверяется для каждой из четырёх одностраничных публикаций: для каждой в
    ``autodoc.cli.constants`` есть собственное значение по умолчанию.
    """
    confluence_config = _config_with_titles({strategy_type: None})
    mock_publisher = _mock_collaborators(mocker, confluence_config=confluence_config)

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_all.call_args.kwargs
    assert kwargs[kwarg_name] == default_title


@pytest.mark.business_logic
def test_publish_all_prints_targets_selected_in_config(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
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
    _mock_collaborators(mocker, confluence_config=confluence_config)

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
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture, removed_flag: str
) -> None:
    """
    ``publish all`` не принимает флаги, которые раньше переопределяли конфиг.

    Click отклоняет неизвестную опцию с ненулевым кодом возврата, и публикация не
    запускается: молча проигнорированный флаг привёл бы к публикации не туда, куда
    рассчитывал пользователь.
    """
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir, removed_flag)

    assert result.exit_code != _EXIT_SUCCESS
    assert "No such option" in result.output
    mock_publisher.publish_all.assert_not_called()


@pytest.mark.infrastructure
def test_publish_all_domain_error_exits_nonzero_cleanly(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """ConfigError, возникающая в make_publisher, завершает команду с кодом 1 и понятным сообщением, без трейсбека."""
    mocker.patch(
        "autodoc.cli.commands.publish.all.make_publisher",
        side_effect=ConfigError("Confluence config invalid"),
    )
    mocker.patch(
        "autodoc.cli.commands.publish.all.load_parsed_data",
        return_value=make_parsed_result(),
    )

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_FAILURE
    assert "Traceback" not in result.output
    assert "Confluence config invalid" in result.output


@pytest.mark.business_logic
def test_publish_all_partial_failure_exits_nonzero_with_error_text(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """Неуспешный PublishReport (success=False) завершает команду с кодом 1 и печатает каждое сообщение об ошибке."""
    report = make_publish_report(success=False, pages_published=0, errors=["some page failed"])
    _mock_collaborators(mocker, publish_report=report)

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_FAILURE
    assert "some page failed" in result.output


@pytest.mark.business_logic
def test_publish_all_zero_pages_published_exits_nonzero(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """Успешный отчёт с pages_published=0 всё равно завершается кодом 1 (случай «публиковать нечего»)."""
    report = make_publish_report(success=True, pages_published=0)
    _mock_collaborators(mocker, publish_report=report)

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_FAILURE
