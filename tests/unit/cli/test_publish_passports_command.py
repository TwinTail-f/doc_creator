"""Тесты для autodoc/cli/commands/publish/passports.py."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from autodoc.cli.app import cli
from autodoc.cli.constants import PASSPORT_TEMPLATE
from tests.unit.cli.utils import make_confluence_config, make_publish_report

_EXIT_SUCCESS: int = 0
_EXIT_FAILURE: int = 1


def _invoke(tmp_path: Path, configs_dir: Path, *args: str):
    """
    Вызывает `publish passports` с переданными дополнительными аргументами командной строки.

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
            "--base-dir",
            str(tmp_path),
            "--configs-dir",
            str(configs_dir),
            "publish",
            "passports",
            *args,
        ],
    )


@pytest.mark.business_logic
@pytest.mark.parametrize(
    ("cli_name", "expected_name"),
    [
        # ни один root-parent флаг не задан — оба значения уходят как None
        pytest.param(None, None, id="no-root-parent-name"),
        # --passports-root-parent-name передаётся в publish_passports без изменений
        pytest.param("Passports Root", "Passports Root", id="root-parent-name-given"),
    ],
)
def test_publish_passports_root_parent_name_forwarded(
    tmp_path: Path,
    configs_dir: Path,
    mock_publisher: MagicMock,
    cli_name: str | None,
    expected_name: str | None,
) -> None:
    """
    --passports-root-parent-name передаётся в publish_passports без изменений;
    без флага уходит None (наравне с passports_root_parent_id).
    """
    args = ["--passports-root-parent-name", cli_name] if cli_name else []
    result = _invoke(tmp_path, configs_dir, *args)

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_passports.call_args.kwargs
    assert kwargs["template_name"] == PASSPORT_TEMPLATE
    assert kwargs["passports_root_parent_name"] == expected_name
    assert kwargs["passports_root_parent_id"] is None


@pytest.mark.contract
def test_publish_passports_name_and_id_both_given_forwarded_unchanged(
    tmp_path: Path, configs_dir: Path, mock_publisher: MagicMock
) -> None:
    """
    --passports-root-parent-name и --passports-root-parent-id можно указывать вместе —
    CLI пробрасывает оба значения в publish_passports без изменений и без проверки
    конфликта (это делает RootPageResolver).
    """
    result = _invoke(
        tmp_path,
        configs_dir,
        "--passports-root-parent-name",
        "Foo",
        "--passports-root-parent-id",
        "123",
    )

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    kwargs = mock_publisher.publish_passports.call_args.kwargs
    assert kwargs["passports_root_parent_name"] == "Foo"
    assert kwargs["passports_root_parent_id"] == "123"


@pytest.mark.business_logic
def test_publish_passports_publisher_failure_report_exits_nonzero(
    tmp_path: Path, configs_dir: Path, mock_publisher: MagicMock
) -> None:
    """Неуспешный PublishReport от publish_passports завершает команду с кодом 1."""
    mock_publisher.publish_passports.return_value = make_publish_report(success=False, pages_published=0, errors=["passport boom"])

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_FAILURE
    assert "passport boom" in result.output


@pytest.mark.infrastructure
def test_publish_passports_missing_parsed_data_exits_nonzero_cleanly(
    tmp_path: Path, configs_dir: Path, make_publisher_mock: MagicMock
) -> None:
    """Отсутствующий parsed_data.json завершает команду с кодом 1 и понятным сообщением."""
    make_publisher_mock.return_value = (MagicMock(), make_confluence_config())
    # data/parsed_data.json намеренно не записывается.

    result = _invoke(tmp_path, configs_dir)

    assert result.exit_code == _EXIT_FAILURE
    assert "Traceback" not in result.output
    assert "parse" in result.output.lower()
