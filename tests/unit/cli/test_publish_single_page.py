"""Тесты для autodoc/cli/commands/publish/single_page.py.

И `publish release`, и `publish profile` проходят через общий
`run_single_page_command`. Полный набор сценариев проверяется один раз на
`publish release`; `publish profile` получает небольшой, неповторяющийся
набор тестов, проверяющий только то, что реально отличается между двумя
командами (strategy_type, источник заголовка по умолчанию и template_name) —
повторная проверка взаимоисключающих флагов или общих путей отказа для
`profile` лишь заново подтвердила бы ту же общую логику, уже покрытую через
`release`.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from autodoc.cli.app import cli
from autodoc.cli.constants import (
    DEFAULT_PROFILE_PAGE_TITLE,
    DEFAULT_RELEASE_PAGE_TITLE,
    PROFILE_TEMPLATE,
    RELEASE_TEMPLATE,
)
from tests.unit.cli.conftest import make_confluence_config, make_parsed_result, make_publish_report

_EXIT_SUCCESS: int = 0
_EXIT_FAILURE: int = 1


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
            "--base-dir", str(tmp_path),
            "--configs-dir", str(configs_dir),
            "publish", command,
            *args,
        ],
    )


def _mock_collaborators(mocker, module: str, publish_report=None, conf_config=None, parsed_ok=True):
    """Подменяет make_publisher и load_parsed_data для заданного модуля single-page команды.

    Args:
        mocker: Фикстура pytest-mock для создания подмен.
        module: Полный путь модуля команды, в котором нужно подменить зависимости.
        publish_report: Отчёт о публикации, который вернёт publish_single_page
            (по умолчанию — успешный отчёт).
        conf_config: Конфиг Confluence, возвращаемый make_publisher
            (по умолчанию — минимальный валидный конфиг).
        parsed_ok: Признак того, нужно ли подменять load_parsed_data
            валидным результатом (False имитирует отсутствие parsed_data.json).

    Returns:
        Поддельный объект publisher с настроенным publish_single_page.
    """
    mock_publisher = mocker.MagicMock()
    mock_publisher.publish_single_page.return_value = publish_report or make_publish_report()
    mocker.patch(
        f"{module}.make_publisher",
        return_value=(mock_publisher, conf_config or make_confluence_config()),
    )
    if parsed_ok:
        mocker.patch(f"{module}.load_parsed_data", return_value=make_parsed_result())
    return mock_publisher


_SINGLE_PAGE_MODULE = "autodoc.cli.commands.publish.single_page"


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
    mocker,
    cli_title: str | None,
    config_title: str | None,
    expected: str,
) -> None:
    """Приоритет источников заголовка страницы для release: флаг CLI > поле конфига > значение по умолчанию."""
    conf_config = make_confluence_config(release_docs_page_title=config_title)
    mock_publisher = _mock_collaborators(mocker, _SINGLE_PAGE_MODULE, conf_config=conf_config)

    args = ["--page-title", cli_title] if cli_title else []
    result = _invoke(tmp_path, configs_dir, "release", *args)

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["page_title"] == expected


@pytest.mark.contract
def test_publish_release_root_id_and_name_both_given_raises(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Совместное указание --root-page-id и --root-page-name приводит к UsageError через require_exclusive."""
    _mock_collaborators(mocker, _SINGLE_PAGE_MODULE)

    result = _invoke(
        tmp_path, configs_dir, "release",
        "--root-page-id", "123", "--root-page-name", "Foo",
    )

    assert result.exit_code != _EXIT_SUCCESS
    assert "--root-page-id" in result.output
    assert "--root-page-name" in result.output


@pytest.mark.business_logic
def test_publish_release_no_passport_links_disables_links(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """--no-passport-links устанавливает include_passport_links=False для release."""
    mock_publisher = _mock_collaborators(mocker, _SINGLE_PAGE_MODULE)

    result = _invoke(tmp_path, configs_dir, "release", "--no-passport-links")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["include_passport_links"] is False


@pytest.mark.business_logic
def test_publish_release_passes_release_strategy_type(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """publish release передаёт strategy_type='release' и RELEASE_TEMPLATE в publish_single_page."""
    mock_publisher = _mock_collaborators(mocker, _SINGLE_PAGE_MODULE)

    result = _invoke(tmp_path, configs_dir, "release")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["strategy_type"] == "release"
    assert kwargs["template_name"] == RELEASE_TEMPLATE


@pytest.mark.business_logic
def test_publish_release_missing_parsed_data_exits_nonzero_cleanly(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Отсутствующий parsed_data.json (DocGeneratorError из load_parsed_data) завершает команду с кодом 1 без ошибок вывода."""
    _mock_collaborators(mocker, _SINGLE_PAGE_MODULE, parsed_ok=False)
    # data/parsed_data.json is intentionally never written to tmp_path, so
    # the real load_parsed_data() raises DocGeneratorError.

    result = _invoke(tmp_path, configs_dir, "release")

    assert result.exit_code == _EXIT_FAILURE
    assert "Traceback" not in result.output
    assert "parse" in result.output.lower()


@pytest.mark.business_logic
def test_publish_release_publisher_failure_report_exits_nonzero(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Неуспешный PublishReport от publish_single_page завершает команду с кодом 1 для release."""
    report = make_publish_report(success=False, pages_published=0, errors=["boom"])
    _mock_collaborators(mocker, _SINGLE_PAGE_MODULE, publish_report=report)

    result = _invoke(tmp_path, configs_dir, "release")

    assert result.exit_code == _EXIT_FAILURE
    assert "boom" in result.output


@pytest.mark.business_logic
def test_publish_profile_passes_profile_centric_strategy_type(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """publish profile передаёт strategy_type='profile_centric' и PROFILE_TEMPLATE."""
    mock_publisher = _mock_collaborators(mocker, _SINGLE_PAGE_MODULE)

    result = _invoke(tmp_path, configs_dir, "profile")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["strategy_type"] == "profile_centric"
    assert kwargs["template_name"] == PROFILE_TEMPLATE


@pytest.mark.business_logic
def test_publish_profile_title_falls_back_to_profile_docs_page_title(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Источником заголовка по умолчанию для profile служит conf_config.profile_docs_page_title, а не как у release."""
    conf_config = make_confluence_config(profile_docs_page_title="Profile Config Title")
    mock_publisher = _mock_collaborators(mocker, _SINGLE_PAGE_MODULE, conf_config=conf_config)

    result = _invoke(tmp_path, configs_dir, "profile")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["page_title"] == "Profile Config Title"


@pytest.mark.business_logic
def test_publish_profile_title_falls_back_to_default_profile_page_title(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Если не задан ни флаг, ни поле конфига, profile использует DEFAULT_PROFILE_PAGE_TITLE."""
    conf_config = make_confluence_config(profile_docs_page_title=None)
    mock_publisher = _mock_collaborators(mocker, _SINGLE_PAGE_MODULE, conf_config=conf_config)

    result = _invoke(tmp_path, configs_dir, "profile")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_single_page.call_args.kwargs
    assert kwargs["page_title"] == DEFAULT_PROFILE_PAGE_TITLE
