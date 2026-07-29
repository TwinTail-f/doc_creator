"""Тесты для autodoc/cli/commands/publish/all.py."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from autodoc.cli.app import cli
from autodoc.cli.constants import (
    DEFAULT_PROFILE_PAGE_TITLE,
    DEFAULT_RELEASE_PAGE_TITLE,
    PASSPORT_TEMPLATE,
    PROFILE_TEMPLATE,
    RELEASE_TEMPLATE,
)
from autodoc.exceptions import ConfigError
from tests.unit.cli.utils import (
    make_confluence_config,
    make_parsed_result,
    make_publish_report,
)

_EXIT_SUCCESS: int = 0
_EXIT_FAILURE: int = 1


def _invoke(tmp_path: Path, configs_dir: Path, *args: str):
    """Вызывает `publish all` с переданными дополнительными аргументами командной строки.

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


def _mock_collaborators(mocker, publish_report=None, conf_config=None):
    """Подменяет make_publisher и load_parsed_data для `publish all` и возвращает поддельный publisher.

    Args:
        mocker: Фикстура pytest-mock для создания подмен.
        publish_report: Отчёт о публикации, который вернёт publish_all
            (по умолчанию — успешный отчёт).
        conf_config: Конфиг Confluence, возвращаемый make_publisher
            (по умолчанию — минимальный валидный конфиг).

    Returns:
        Поддельный объект publisher с настроенным publish_all.
    """
    mock_publisher = mocker.MagicMock()
    mock_publisher.publish_all.return_value = publish_report or make_publish_report()
    mocker.patch(
        "autodoc.cli.commands.publish.all.make_publisher",
        return_value=(mock_publisher, conf_config or make_confluence_config()),
    )
    mocker.patch(
        "autodoc.cli.commands.publish.all.load_parsed_data",
        return_value=make_parsed_result(),
    )
    return mock_publisher


@pytest.mark.business_logic
def test_publish_all_happy_path_minimal_flags(tmp_path: Path, configs_dir: Path, mocker) -> None:
    """Без дополнительных флагов publish_all вызывается с документированными значениями по умолчанию."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    mock_publisher.publish_all.assert_called_once()
    kwargs = mock_publisher.publish_all.call_args.kwargs
    assert kwargs["release_template_name"] == RELEASE_TEMPLATE
    assert kwargs["passport_template_name"] == PASSPORT_TEMPLATE
    assert kwargs["profile_title"] is None
    assert kwargs["profile_template_name"] is None
    assert kwargs["include_passport_links"] is True


@pytest.mark.business_logic
@pytest.mark.parametrize(
    ("cli_title", "config_title", "expected"),
    [
        pytest.param("CLI Title", "Config Title", "CLI Title", id="cli-flag-wins"),
        pytest.param(None, "Config Title", "Config Title", id="config-field-wins"),
        pytest.param(None, None, DEFAULT_RELEASE_PAGE_TITLE, id="default-wins"),
    ],
)
def test_publish_all_release_page_title_precedence(
    tmp_path: Path,
    configs_dir: Path,
    mocker,
    cli_title: str | None,
    config_title: str | None,
    expected: str,
) -> None:
    """Приоритет источников заголовка релиза: флаг CLI > поле конфига > значение по умолчанию."""
    conf_config = make_confluence_config(release_docs_page_title=config_title)
    mock_publisher = _mock_collaborators(mocker, conf_config=conf_config)

    args = ["--release-doc-page-name", cli_title] if cli_title else []
    result = _invoke(tmp_path, configs_dir, *args)

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_all.call_args.kwargs
    assert kwargs["release_page_title"] == expected


@pytest.mark.business_logic
@pytest.mark.parametrize(
    ("extra_args", "expected_profile_title"),
    [
        # без пользовательского имени — используется заголовок профиля по умолчанию
        pytest.param([], DEFAULT_PROFILE_PAGE_TITLE, id="default-name"),
        # --additional-page-profile-name переопределяет заголовок по умолчанию
        pytest.param(["--additional-page-profile-name", "X"], "X", id="custom-name"),
    ],
)
def test_publish_all_with_additional_page_profile_title(
    tmp_path: Path,
    configs_dir: Path,
    mocker,
    extra_args: list[str],
    expected_profile_title: str,
) -> None:
    """--with-additional-page-profile использует заголовок профиля по умолчанию, если
    --additional-page-profile-name не задан, и переопределённое значение, если задан;
    шаблон профиля в обоих случаях — PROFILE_TEMPLATE."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir, "--with-additional-page-profile", *extra_args)

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_all.call_args.kwargs
    assert kwargs["profile_title"] == expected_profile_title
    assert kwargs["profile_template_name"] == PROFILE_TEMPLATE


@pytest.mark.business_logic
def test_publish_all_profile_name_without_flag_raises_usage_error(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """--additional-page-profile-name без --with-additional-page-profile приводит к UsageError."""
    _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir, "--additional-page-profile-name", "X")

    assert result.exit_code != _EXIT_SUCCESS
    assert "--with-additional-page-profile" in result.output


@pytest.mark.contract
@pytest.mark.parametrize(
    "name_flag, id_flag, name_kwarg, id_kwarg",
    [
        # пара для паспортов
        pytest.param(
            "--passports-root-parent-name",
            "--passports-root-parent-id",
            "passports_root_parent_name",
            "passports_root_parent_id",
            id="passports",
        ),
        # пара для релизной документации
        pytest.param(
            "--release-root-page-name",
            "--release-root-page-id",
            "release_root_page_name",
            "release_root_page_id",
            id="release",
        ),
    ],
)
def test_publish_all_root_name_and_id_both_given_forwarded_to_publisher(
    tmp_path: Path,
    configs_dir: Path,
    mocker,
    name_flag: str,
    id_flag: str,
    name_kwarg: str,
    id_kwarg: str,
) -> None:
    """Название и ID родительской страницы (для паспортов и отдельно для релиза) можно
    указывать вместе: CLI их не проверяет и не отклоняет, а просто пробрасывает оба
    значения дальше без изменений. Приоритет между названием и id страницы CLI не
    определяет — это происходит позже, при резолве родительской страницы
    (RootPageResolver._resolve_root_parent)."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir, name_flag, "Foo", id_flag, "123")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_all.call_args.kwargs
    assert kwargs[name_kwarg] == "Foo"
    assert kwargs[id_kwarg] == "123"


@pytest.mark.business_logic
def test_publish_all_no_passport_links_disables_links(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """--no-passport-links устанавливает include_passport_links=False."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir, "--no-passport-links")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_all.call_args.kwargs
    assert kwargs["include_passport_links"] is False


@pytest.mark.infrastructure
def test_publish_all_domain_error_exits_nonzero_cleanly(
    tmp_path: Path, configs_dir: Path, mocker
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
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Неуспешный PublishReport (success=False) завершает команду с кодом 1 и печатает каждое сообщение об ошибке."""
    report = make_publish_report(success=False, pages_published=0, errors=["some page failed"])
    _mock_collaborators(mocker, publish_report=report)

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_FAILURE
    assert "some page failed" in result.output


@pytest.mark.business_logic
def test_publish_all_zero_pages_published_exits_nonzero(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Успешный отчёт с pages_published=0 всё равно завершается кодом 1 (случай «публиковать нечего»)."""
    report = make_publish_report(success=True, pages_published=0)
    _mock_collaborators(mocker, publish_report=report)

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_FAILURE
