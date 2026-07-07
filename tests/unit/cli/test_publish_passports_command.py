"""Тесты для autodoc/cli/commands/publish/passports.py.

Команда `publish passports` проверяется целиком через CliRunner. Приоритет
между --passports-root-parent-name и --passports-root-parent-id — зона
ответственности RootPageResolver (покрыта в части 2), а не этой команды,
поэтому здесь проверяется только передача обоих значений без изменений,
а не их приоритет.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from autodoc.cli.app import cli
from autodoc.cli.constants import PASSPORT_TEMPLATE
from tests.unit.cli.conftest import make_confluence_config, make_parsed_result, make_publish_report

_EXIT_SUCCESS: int = 0
_EXIT_FAILURE: int = 1

_MODULE = "autodoc.cli.commands.publish.passports"


def _invoke(tmp_path: Path, configs_dir: Path, *args: str):
    """Вызывает `publish passports` с переданными дополнительными аргументами командной строки.

    Args:
        tmp_path: Базовая директория проекта.
        configs_dir: Директория конфигов.
        *args: Дополнительные аргументы, передаваемые команде `publish passports`.

    Returns:
        Результат выполнения команды (``click.testing.Result``).
    """
    return CliRunner().invoke(
        cli,
        [
            "--base-dir", str(tmp_path),
            "--configs-dir", str(configs_dir),
            "publish", "passports",
            *args,
        ],
    )


def _mock_collaborators(mocker, publish_report=None, parsed_ok=True):
    """Подменяет make_publisher и load_parsed_data для `publish passports`.

    Args:
        mocker: Фикстура pytest-mock для создания подмен.
        publish_report: Отчёт о публикации, который вернёт publish_passports
            (по умолчанию — успешный отчёт).
        parsed_ok: Признак того, нужно ли подменять load_parsed_data
            валидным результатом (False имитирует отсутствие parsed_data.json).

    Returns:
        Поддельный объект publisher с настроенным publish_passports.
    """
    mock_publisher = mocker.MagicMock()
    mock_publisher.publish_passports.return_value = publish_report or make_publish_report()
    mocker.patch(
        f"{_MODULE}.make_publisher",
        return_value=(mock_publisher, make_confluence_config()),
    )
    if parsed_ok:
        mocker.patch(f"{_MODULE}.load_parsed_data", return_value=make_parsed_result())
    return mock_publisher


@pytest.mark.business_logic
def test_publish_passports_happy_path_neither_flag_set(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Без установленных root-parent флагов publish_passports вызывается с None для обоих значений."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_passports.call_args.kwargs
    assert kwargs["template_name"] == PASSPORT_TEMPLATE
    assert kwargs["passports_root_parent_name"] is None
    assert kwargs["passports_root_parent_id"] is None


@pytest.mark.business_logic
def test_publish_passports_root_parent_name_passed_through(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """--passports-root-parent-name передаётся в publish_passports без изменений."""
    mock_publisher = _mock_collaborators(mocker)

    result = _invoke(tmp_path, configs_dir, "--passports-root-parent-name", "Passports Root")

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_passports.call_args.kwargs
    assert kwargs["passports_root_parent_name"] == "Passports Root"
    assert kwargs["passports_root_parent_id"] is None


@pytest.mark.contract
def test_publish_passports_name_and_id_both_given_raises(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Совместное указание --passports-root-parent-name и --passports-root-parent-id приводит к UsageError."""
    _mock_collaborators(mocker)

    result = _invoke(
        tmp_path, configs_dir,
        "--passports-root-parent-name", "Foo",
        "--passports-root-parent-id", "123",
    )

    assert result.exit_code != _EXIT_SUCCESS
    assert "--passports-root-parent-name" in result.output
    assert "--passports-root-parent-id" in result.output


@pytest.mark.business_logic
def test_publish_passports_publisher_failure_report_exits_nonzero(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Неуспешный PublishReport от publish_passports завершает команду с кодом 1."""
    report = make_publish_report(success=False, pages_published=0, errors=["passport boom"])
    _mock_collaborators(mocker, publish_report=report)

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_FAILURE
    assert "passport boom" in result.output


@pytest.mark.business_logic
def test_publish_passports_missing_parsed_data_exits_nonzero_cleanly(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Отсутствующий parsed_data.json завершает команду с кодом 1 и понятным сообщением."""
    _mock_collaborators(mocker, parsed_ok=False)
    # data/parsed_data.json intentionally never written.

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_FAILURE
    assert "Traceback" not in result.output
    assert "parse" in result.output.lower()
