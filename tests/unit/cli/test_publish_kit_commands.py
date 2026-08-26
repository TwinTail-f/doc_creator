"""Тесты для autodoc/cli/commands/publish/kit_fixed.py и kit_latest.py.

Обе команды проходят через общий `run_kit_page_command` (аналог
`run_single_page_command`, но без `--no-passport-links` — у страниц
комплекта встраивания нет понятия ссылок на паспорта). Полный набор
сценариев проверяется на `publish kit-fixed`; `publish kit-latest` получает
компактный набор тестов на то, что реально отличается (strategy_type,
шаблон и заголовок по умолчанию).
"""

from pathlib import Path

import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture

from autodoc.cli.app import cli
from autodoc.cli.constants import (
    DEFAULT_KIT_FIXED_PAGE_TITLE,
    DEFAULT_KIT_LATEST_PAGE_TITLE,
    KIT_FIXED_TEMPLATE,
    KIT_LATEST_TEMPLATE,
)
from tests.unit.cli.utils import (
    make_confluence_config,
    make_parsed_result,
    make_publish_report,
    strategy_override,
)

_EXIT_SUCCESS: int = 0
_EXIT_FAILURE: int = 1
_KIT_FIXED_MODULE = "autodoc.cli.commands.publish.kit_fixed"
_SINGLE_PAGE_MODULE = "autodoc.cli.commands.publish.single_page"


def _invoke(tmp_path: Path, configs_dir: Path, command: str, *args: str):
    """Вызывает `publish <command>` с переданными дополнительными аргументами командной строки.

    Args:
        tmp_path: Базовая директория проекта.
        configs_dir: Директория конфигов.
        command: Имя подкоманды publish (``"kit-fixed"`` или ``"kit-latest"``).
        *args: Дополнительные аргументы, передаваемые команде.

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
            command,
            *args,
        ],
    )


def _mock_collaborators(
    mocker: MockerFixture,
    publish_report=None,
    confluence_config=None,
    parsed_ok=True,
):
    """Подменяет make_publisher и load_parsed_data в модуле single-page команды
    (обе команды kit-* используют те же коллабораторы через single_page.py).

    Args:
        mocker: Фикстура pytest-mock для создания подмен.
        publish_report: Отчёт о публикации, который вернёт publish_single_page
            (по умолчанию — успешный отчёт).
        confluence_config: Конфиг Confluence, возвращаемый make_publisher
            (по умолчанию — минимальный валидный конфиг).
        parsed_ok: Признак того, нужно ли подменять load_parsed_data
            валидным результатом (False имитирует отсутствие parsed_data.json).

    Returns:
        Поддельный объект publisher с настроенным publish_single_page.
    """
    mock_publisher = mocker.MagicMock()
    mock_publisher.publish_single_page.return_value = publish_report or make_publish_report()
    mocker.patch(
        f"{_SINGLE_PAGE_MODULE}.make_publisher",
        return_value=(mock_publisher, confluence_config or make_confluence_config()),
    )
    if parsed_ok:
        mocker.patch(f"{_SINGLE_PAGE_MODULE}.load_parsed_data", return_value=make_parsed_result())
    return mock_publisher


@pytest.mark.business_logic
def test_publish_kit_fixed_passes_strategy_type_and_template(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """publish kit-fixed передаёт strategy_type='kit_fixed' и KIT_FIXED_TEMPLATE."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir, "kit-fixed")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["strategy_type"] == "kit_fixed"
    assert kwargs["template_name"] == KIT_FIXED_TEMPLATE


@pytest.mark.business_logic
def test_publish_kit_fixed_include_passport_links_always_false(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """publish kit-fixed всегда передаёт include_passport_links=False — у команды
    нет флага, управляющего этим (в отличие от release/profile)."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir, "kit-fixed")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["include_passport_links"] is False


@pytest.mark.contract
def test_publish_kit_fixed_has_no_passport_links_flag(
    tmp_path: Path, configs_dir: Path
) -> None:
    """--no-passport-links не является опцией kit-fixed (в отличие от release/profile)."""
    result = _invoke(tmp_path, configs_dir, "kit-fixed", "--no-passport-links")
    assert result.exit_code != _EXIT_SUCCESS
    assert "no-passport-links" in result.output.lower() or "no such option" in result.output.lower()


@pytest.mark.business_logic
@pytest.mark.parametrize(
    ("cli_title", "config_title", "expected"),
    [
        pytest.param("CLI Title", "Config Title", "CLI Title", id="cli-flag-wins"),
        pytest.param(None, "Config Title", "Config Title", id="config-field-wins"),
        pytest.param(None, None, DEFAULT_KIT_FIXED_PAGE_TITLE, id="default-wins"),
    ],
)
def test_publish_kit_fixed_page_title_precedence(
    tmp_path: Path,
    configs_dir: Path,
    mocker: MockerFixture,
    cli_title: str | None,
    config_title: str | None,
    expected: str,
) -> None:
    """Приоритет источников заголовка страницы для kit-fixed: флаг CLI > поле
    конфига > значение по умолчанию (аналогично release/profile)."""
    confluence_config = make_confluence_config(
        **strategy_override("kit_fixed", page_title=config_title)
    )
    mock_publisher = _mock_collaborators(mocker, confluence_config=confluence_config)

    args = ["--page-title", cli_title] if cli_title else []
    result = _invoke(tmp_path, configs_dir, "kit-fixed", *args)

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["page_title"] == expected


@pytest.mark.contract
def test_publish_kit_fixed_root_id_and_name_both_given_forwarded_unchanged(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """--root-page-id и --root-page-name пробрасываются в publish_single_page как есть."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(
        tmp_path,
        configs_dir,
        "kit-fixed",
        "--root-page-id",
        "123",
        "--root-page-name",
        "Foo",
    )

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["root_page_name"] == "Foo"
    assert kwargs["root_page_id"] == "123"


@pytest.mark.infrastructure
def test_publish_kit_fixed_missing_parsed_data_exits_nonzero_cleanly(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """Отсутствующий parsed_data.json завершает команду с кодом 1 без трейсбека."""
    _mock_collaborators(mocker, parsed_ok=False)

    result = _invoke(tmp_path, configs_dir, "kit-fixed")

    assert result.exit_code == _EXIT_FAILURE
    assert "Traceback" not in result.output
    assert "parse" in result.output.lower()


@pytest.mark.business_logic
def test_publish_kit_fixed_publisher_failure_report_exits_nonzero(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """Неуспешный PublishReport от publish_single_page завершает команду с кодом 1."""
    report = make_publish_report(success=False, pages_published=0, errors=["boom"])
    _mock_collaborators(mocker, publish_report=report)

    result = _invoke(tmp_path, configs_dir, "kit-fixed")

    assert result.exit_code == _EXIT_FAILURE
    assert "boom" in result.output


@pytest.mark.business_logic
def test_publish_kit_latest_passes_strategy_type_and_template(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """publish kit-latest передаёт strategy_type='kit_latest' и KIT_LATEST_TEMPLATE."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir, "kit-latest")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["strategy_type"] == "kit_latest"
    assert kwargs["template_name"] == KIT_LATEST_TEMPLATE


@pytest.mark.business_logic
@pytest.mark.parametrize(
    ("config_title", "expected_title"),
    [
        pytest.param("Latest Config Title", "Latest Config Title", id="config-field-wins"),
        pytest.param(None, DEFAULT_KIT_LATEST_PAGE_TITLE, id="default-wins"),
    ],
)
def test_publish_kit_latest_title_source(
    tmp_path: Path,
    configs_dir: Path,
    mocker: MockerFixture,
    config_title: str | None,
    expected_title: str,
) -> None:
    """Источником заголовка по умолчанию для kit-latest служит
    confluence_config.strategies.kit_latest.page_title, а не kit_fixed."""
    confluence_config = make_confluence_config(
        **strategy_override("kit_latest", page_title=config_title)
    )
    mock_publisher = _mock_collaborators(mocker, confluence_config=confluence_config)

    result = _invoke(tmp_path, configs_dir, "kit-latest")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["page_title"] == expected_title
