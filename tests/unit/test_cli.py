"""Unit tests for autodoc/cli.py.

Tests invoke the Click CLI via CliRunner — no subprocess, no real config
files required unless created with tmp_path.
"""

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from autodoc.cli.app import cli

_EXIT_SUCCESS: int = 0

# Minimal valid parser config — satisfies all required ParserConfigSchema fields.
_VALID_CONFIG: dict = {
    "platform_version": "2.0",
    "platform_branch_name": "develop",
    "username": "testuser",
    "tfs_token": "test-tfs-pat-token",
    "tfs_collection_url": "https://tfs.example.com",
    "manifests_remotes_path": "/platform/manifests",
    "conan_config_url": "https://art.example.com/conan-config.zip",
}

# A config missing all required fields — guaranteed to fail Pydantic validation.
_INVALID_CONFIG: dict = {}


@pytest.fixture()
def configs_dir(tmp_path: Path) -> Path:
    """An empty configs directory inside tmp_path.

    Required because the CLI root command exits 1 if --configs-dir does not exist.
    """
    d: Path = tmp_path / "configs"
    d.mkdir()
    return d


def _write_json(directory: Path, filename: str, data: dict) -> Path:
    """Write *data* as JSON to *directory / filename* and return the path."""
    p: Path = directory / filename
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _write_yaml(directory: Path, filename: str, data: dict) -> Path:
    """Write *data* as YAML to *directory / filename* and return the path."""
    p: Path = directory / filename
    p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return p


@pytest.mark.business_logic
def test_cli_config_validate_exits_zero_on_valid_config(
    configs_dir: Path,
) -> None:
    """validate sub-command exits 0 when the file is syntactically valid YAML.

    Guards against the validate command crashing on valid input.
    """
    _write_yaml(configs_dir, "parser_config.yaml", _VALID_CONFIG)
    result = CliRunner().invoke(
        cli,
        ["--configs-dir", str(configs_dir), "config", "validate", "parser_config.yaml"],
    )
    assert result.exit_code == _EXIT_SUCCESS, (
        f"Expected exit 0 for valid config, got {result.exit_code}.\n"
        f"output: {result.output}\nexc: {result.exception}"
    )


@pytest.mark.business_logic
def test_cli_config_validate_exits_zero_on_valid_json_config(
    configs_dir: Path,
) -> None:
    """validate принимает .json файл (обратная совместимость).

    Проекты с существующими .json конфигами не должны ломаться.
    """
    _write_json(configs_dir, "parser_config.json", _VALID_CONFIG)
    result = CliRunner().invoke(
        cli,
        ["--configs-dir", str(configs_dir), "config", "validate", "parser_config.json"],
    )
    assert result.exit_code == _EXIT_SUCCESS, (
        f"Expected exit 0 for valid JSON config, got {result.exit_code}.\n"
        f"output: {result.output}\nexc: {result.exception}"
    )


@pytest.mark.business_logic
def test_cli_config_validate_exits_nonzero_on_invalid_config(
    configs_dir: Path,
) -> None:
    """validate sub-command exits non-zero when the file is invalid JSON.

    Ensures the CLI surfaces the error to the caller rather than swallowing it.
    """
    invalid_path: Path = configs_dir / "bad.json"
    invalid_path.write_bytes(b"{not valid json")  # intentionally broken JSON
    result = CliRunner().invoke(
        cli,
        ["--configs-dir", str(configs_dir), "config", "validate", "bad.json"],
    )
    assert (
        result.exit_code != _EXIT_SUCCESS
    ), f"Expected non-zero exit for invalid JSON, got {result.exit_code}"


@pytest.mark.business_logic
def test_cli_config_validate_error_is_human_readable(
    configs_dir: Path,
) -> None:
    """validate sub-command error output must not contain a raw Python traceback.

    A traceback in user-facing output is a UX defect: the error message must be
    a clean diagnostic, not an internal stack trace.
    """
    # An empty JSON object passes syntax check but will trigger schema warnings.
    # Write a completely broken JSON to trigger a real error path.
    broken: Path = configs_dir / "broken.json"
    broken.write_bytes(b"this is not json at all")
    result = CliRunner().invoke(
        cli,
        ["--configs-dir", str(configs_dir), "config", "validate", "broken.json"],
    )
    assert (
        "Traceback" not in result.output
    ), "Raw Python traceback found in CLI output — error must be user-friendly."
    assert (
        'File "' not in result.output
    ), "Python file reference found in CLI output — error must be user-friendly."


@pytest.mark.business_logic
def test_cli_config_list_shows_config_filenames(
    configs_dir: Path,
) -> None:
    """config list sub-command prints all JSON config filenames present in configs_dir.

    Verifies that the list command discovers and surfaces filenames to the user.
    """
    _write_json(configs_dir, "config_a.json", _VALID_CONFIG)
    _write_json(configs_dir, "config_b.json", _VALID_CONFIG)
    result = CliRunner().invoke(
        cli,
        ["--configs-dir", str(configs_dir), "config", "list"],
    )
    assert result.exit_code == _EXIT_SUCCESS, (
        f"Expected exit 0 from config list, got {result.exit_code}.\n"
        f"output: {result.output}\nexc: {result.exception}"
    )
    assert "config_a.json" in result.output, "config_a.json missing from list output"
    assert "config_b.json" in result.output, "config_b.json missing from list output"


@pytest.mark.business_logic
def test_cli_config_list_on_empty_dir_exits_zero(
    configs_dir: Path,
) -> None:
    """config list sub-command exits 0 even when no configs are present.

    An empty configs directory is a valid state (first run); the CLI must not crash.
    """
    result = CliRunner().invoke(
        cli,
        ["--configs-dir", str(configs_dir), "config", "list"],
    )
    assert result.exit_code == _EXIT_SUCCESS, (
        f"Expected exit 0 on empty configs dir, got {result.exit_code}.\n"
        f"output: {result.output}\nexc: {result.exception}"
    )


@pytest.mark.business_logic
def test_cli_config_list_shows_yaml_config_filenames(configs_dir: Path) -> None:
    """config list отображает .yaml файлы в выводе."""
    _write_yaml(configs_dir, "parser_config.yaml", _VALID_CONFIG)
    result = CliRunner().invoke(cli, ["--configs-dir", str(configs_dir), "config", "list"])
    assert result.exit_code == _EXIT_SUCCESS
    assert "parser_config.yaml" in result.output


@pytest.mark.business_logic
def test_cli_config_list_shows_examples_section(configs_dir: Path) -> None:
    """config list показывает секцию примеров, если examples/ существует."""
    examples_dir = configs_dir / "examples"
    examples_dir.mkdir()
    _write_yaml(examples_dir, "parser_config.yaml", _VALID_CONFIG)

    result = CliRunner().invoke(cli, ["--configs-dir", str(configs_dir), "config", "list"])
    assert result.exit_code == _EXIT_SUCCESS
    assert "examples" in result.output.lower()
