"""Тесты для autodoc.cli.app.cli (корневая группа команд)."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from autodoc.cli.app import cli
from autodoc.cli.constants import VERSION

_EXIT_CONFIG_ERROR: int = 1


@pytest.mark.infrastructure
def test_cli_exits_with_error_when_configs_dir_missing(tmp_path: Path) -> None:
    missing_configs_dir = tmp_path / "configs"  # намеренно не создаём
    result = CliRunner().invoke(
        cli, ["--base-dir", str(tmp_path), "--configs-dir", str(missing_configs_dir), "info"],
    )
    assert result.exit_code == _EXIT_CONFIG_ERROR
    assert str(missing_configs_dir) in result.output
    assert VERSION not in result.output  # подтверждаем, что до тела подкоманды не дошли
