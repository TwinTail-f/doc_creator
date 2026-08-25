"""Тесты для autodoc/cli/commands/publish/single_page.py.

И `publish release`, и `publish profile` проходят через общий
`run_single_page_command`. Полный набор сценариев проверяется один раз на
`publish release`; `publish profile` получает небольшой, неповторяющийся
набор тестов, проверяющий только то, что реально отличается между двумя
командами (strategy_type, источник заголовка по умолчанию и template_name)
"""

from pathlib import Path

import click
import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture

from autodoc.cli.app import cli
from autodoc.cli.commands.publish.single_page import run_single_page_command
from autodoc.cli.constants import (
    DEFAULT_PROFILE_PAGE_TITLE,
    DEFAULT_RELEASE_PAGE_TITLE,
    PROFILE_TEMPLATE,
    RELEASE_TEMPLATE,
)
from autodoc.cli.context import CliCtx
from tests.unit.cli.utils import (
    make_confluence_config,
    make_parsed_result,
    make_publish_report,
    strategy_override,
)

_EXIT_SUCCESS: int = 0
_EXIT_FAILURE: int = 1
_SINGLE_PAGE_MODULE = "autodoc.cli.commands.publish.single_page"


def _invoke(tmp_path: Path, configs_dir: Path, command: str, *args: str):
    """Вызывает `publish <command>` с переданными дополнительными аргументами командной строки.

    Args:
        tmp_path: Базовая директория проекта.
        configs_dir: Директория конфигов.
        command: Имя подкоманды publish (например, "release" или "profile").
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
    """Подменяет make_publisher и load_parsed_data в модуле single-page команды.

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
@pytest.mark.parametrize(
    ("cli_title", "config_title", "expected"),
    [
        pytest.param("CLI Title", "Config Title", "CLI Title", id="cli-flag-wins"),
        pytest.param(None, "Config Title", "Config Title", id="config-field-wins"),
        pytest.param(None, None, DEFAULT_RELEASE_PAGE_TITLE, id="default-wins"),
    ],
)
def test_publish_release_page_title_precedence(
    tmp_path: Path,
    configs_dir: Path,
    mocker: MockerFixture,
    cli_title: str | None,
    config_title: str | None,
    expected: str,
) -> None:
    """Приоритет источников заголовка страницы для release: флаг CLI > поле конфига > значение по умолчанию."""
    confluence_config = make_confluence_config(**strategy_override("release", page_title=config_title))
    mock_publisher = _mock_collaborators(mocker, confluence_config=confluence_config)

    args = ["--page-title", cli_title] if cli_title else []
    result = _invoke(tmp_path, configs_dir, "release", *args)

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["page_title"] == expected


@pytest.mark.contract
def test_publish_release_root_id_and_name_both_given_forwarded_unchanged(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """--root-page-id и --root-page-name можно указывать вместе — CLI пробрасывает оба значения
    в publish_single_page как есть; решение о приоритете и конфликте между ними принимает
    RootPageResolver, а не эта команда."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(
        tmp_path,
        configs_dir,
        "release",
        "--root-page-id",
        "123",
        "--root-page-name",
        "Foo",
    )

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["root_page_name"] == "Foo"
    assert kwargs["root_page_id"] == "123"


@pytest.mark.business_logic
def test_publish_release_no_passport_links_disables_links(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """--no-passport-links устанавливает include_passport_links=False для release."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir, "release", "--no-passport-links")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["include_passport_links"] is False


@pytest.mark.business_logic
def test_publish_release_passes_release_strategy_type(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """publish release передаёт strategy_type='release' и RELEASE_TEMPLATE в publish_single_page."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir, "release")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["strategy_type"] == "release"
    assert kwargs["template_name"] == RELEASE_TEMPLATE


@pytest.mark.infrastructure
def test_publish_release_missing_parsed_data_exits_nonzero_cleanly(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """Отсутствующий parsed_data.json (DocGeneratorError из load_parsed_data) завершает команду с кодом 1 без ошибок вывода."""
    _mock_collaborators(mocker, parsed_ok=False)
    # data/parsed_data.json намеренно не записывается в tmp_path, поэтому
    # реальный load_parsed_data() вызывает DocGeneratorError.

    result = _invoke(tmp_path, configs_dir, "release")

    assert result.exit_code == _EXIT_FAILURE
    assert "Traceback" not in result.output
    assert "parse" in result.output.lower()


@pytest.mark.business_logic
def test_publish_release_publisher_failure_report_exits_nonzero(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """Неуспешный PublishReport от publish_single_page завершает команду с кодом 1 для release."""
    report = make_publish_report(success=False, pages_published=0, errors=["boom"])
    _mock_collaborators(mocker, publish_report=report)

    result = _invoke(tmp_path, configs_dir, "release")

    assert result.exit_code == _EXIT_FAILURE
    assert "boom" in result.output


@pytest.mark.business_logic
def test_publish_profile_passes_profile_centric_strategy_type(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
) -> None:
    """publish profile передаёт strategy_type='profile_centric' и PROFILE_TEMPLATE."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir, "profile")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["strategy_type"] == "profile_centric"
    assert kwargs["template_name"] == PROFILE_TEMPLATE


@pytest.mark.business_logic
@pytest.mark.parametrize(
    ("config_title", "expected_title"),
    [
        # заголовок берётся из strategies.profile_centric.page_title конфига, а не как у release
        pytest.param("Profile Config Title", "Profile Config Title", id="config-field-wins"),
        # ни флага, ни поля конфига нет — используется DEFAULT_PROFILE_PAGE_TITLE
        pytest.param(None, DEFAULT_PROFILE_PAGE_TITLE, id="default-wins"),
    ],
)
def test_publish_profile_title_source(
    tmp_path: Path,
    configs_dir: Path,
    mocker: MockerFixture,
    config_title: str | None,
    expected_title: str,
) -> None:
    """Источником заголовка по умолчанию для profile служит
    confluence_config.strategies.profile_centric.page_title (а не
    confluence_config.strategies.release.page_title, как у release); при его отсутствии
    используется DEFAULT_PROFILE_PAGE_TITLE."""
    confluence_config = make_confluence_config(
        **strategy_override("profile_centric", page_title=config_title)
    )
    mock_publisher = _mock_collaborators(mocker, confluence_config=confluence_config)

    result = _invoke(tmp_path, configs_dir, "profile")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["page_title"] == expected_title


@pytest.mark.contract
@pytest.mark.parametrize(
    "bad_strategy_type",
    [
        # опечатка/несуществующий тип — не зарегистрирован в registry.STRATEGIES вообще
        pytest.param("not_a_real_strategy", id="unregistered-in-registry"),
        # зарегистрирован в registry.STRATEGIES, но не поддерживает single-page (нет заголовка)
        pytest.param("passports", id="registered-but-not-single-page"),
    ],
)
def test_run_single_page_command_rejects_invalid_strategy_type(
    tmp_path: Path,
    configs_dir: Path,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
    bad_strategy_type: str,
) -> None:
    """Некорректный strategy_type останавливает публикацию с понятной ошибкой,
    вместо того чтобы молча выбрать один из известных режимов через else-фоллбек
    (это баг в коде, вызывающем run_single_page_command, а не ошибка пользователя).

    Покрывает оба случая валидации: strategy_type вообще не зарегистрирован в
    ``autodoc.publisher.strategies.registry.STRATEGIES``, и strategy_type
    зарегистрирован, но не поддерживает одностраничную публикацию (``passports``).
    """
    mock_publisher = _mock_collaborators(mocker)
    cli_ctx = CliCtx(base_dir=tmp_path, configs_dir=configs_dir, verbose=False)
    ctx = click.Context(click.Command("test"))
    ctx.obj = cli_ctx

    with pytest.raises(SystemExit) as exc_info:
        run_single_page_command(
            ctx,
            strategy_type=bad_strategy_type,
            template_name="irrelevant.jinja2",
            default_title="Default",
            panel_header="Test Panel",
            page_title=None,
            cli_root_page_id=None,
            cli_root_page_name=None,
            no_passport_links=False,
        )

    assert exc_info.value.code == _EXIT_FAILURE
    output = capsys.readouterr().out
    assert bad_strategy_type in output
    # Публикация не должна была даже начаться.
    mock_publisher.publish_single_page.assert_not_called()
