"""Тесты для autodoc/cli/commands/publish/quote_hint.py.

QuoteHintCommand проверяется напрямую через реальную команду `publish release`
(самую простую из декорированных этим классом), а не через замоканные
внутренности Click.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from autodoc.cli.app import cli
from tests.unit.cli.conftest import make_confluence_config, make_parsed_result, make_publish_report

_EXIT_SUCCESS: int = 0

_MODULE = "autodoc.cli.commands.publish.single_page"


def _mock_collaborators(mocker) -> None:
    """Подменяет make_publisher и load_parsed_data, чтобы `publish release` не обращалась к реальным зависимостям.

    Args:
        mocker: Фикстура pytest-mock для создания подмен.
    """
    mock_publisher = mocker.MagicMock()
    mock_publisher.publish_single_page.return_value = make_publish_report()
    mocker.patch(f"{_MODULE}.make_publisher", return_value=(mock_publisher, make_confluence_config()))
    mocker.patch(f"{_MODULE}.load_parsed_data", return_value=make_parsed_result())


@pytest.mark.contract
def test_unquoted_multiword_name_value_triggers_quote_hint(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Неэкранированное значение --root-page-name из нескольких слов добавляет подсказку поверх исходной ошибки."""
    _mock_collaborators(mocker)

    result = CliRunner().invoke(
        cli,
        [
            "--base-dir", str(tmp_path),
            "--configs-dir", str(configs_dir),
            "publish", "release",
            "--root-page-name", "My", "Page",
        ],
    )

    assert result.exit_code != _EXIT_SUCCESS
    assert "unexpected extra argument" in result.output.lower()
    assert "💡" in result.output
    assert "--root-page-name" in result.output


@pytest.mark.contract
def test_name_flag_not_passed_does_not_appear_in_hint(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Флаг с суффиксом -name, который фактически не был передан, отсутствует в сгенерированных примерах подсказки."""
    _mock_collaborators(mocker)

    result = CliRunner().invoke(
        cli,
        [
            "--base-dir", str(tmp_path),
            "--configs-dir", str(configs_dir),
            "publish", "release",
            "--root-page-id", "123", "extra-token",
        ],
    )

    assert result.exit_code != _EXIT_SUCCESS
    assert "unexpected extra argument" in result.output.lower()
    assert "--page-title" not in result.output
    assert "--root-page-name" not in result.output


@pytest.mark.contract
def test_unrelated_usage_error_passes_through_unchanged(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """UsageError, не связанная с 'unexpected extra argument' (require_exclusive), не получает подсказку."""
    _mock_collaborators(mocker)

    result = CliRunner().invoke(
        cli,
        [
            "--base-dir", str(tmp_path),
            "--configs-dir", str(configs_dir),
            "publish", "release",
            "--root-page-id", "123", "--root-page-name", "Foo",
        ],
    )

    assert result.exit_code != _EXIT_SUCCESS
    assert "unexpected extra argument" not in result.output.lower()
    assert "💡" not in result.output


@pytest.mark.contract
def test_no_name_flags_present_reraises_original_error_unchanged(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Настоящая ошибка о лишнем аргументе без единого -name-флага пробрасывает исходную UsageError без изменений."""
    _mock_collaborators(mocker)

    result = CliRunner().invoke(
        cli,
        [
            "--base-dir", str(tmp_path),
            "--configs-dir", str(configs_dir),
            "publish", "release",
            "--root-page-id", "123", "extra-token",
        ],
    )

    assert result.exit_code != _EXIT_SUCCESS
    assert "unexpected extra argument" in result.output.lower()
    assert "💡" not in result.output
