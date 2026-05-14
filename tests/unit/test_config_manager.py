"""Unit tests for autodoc/config/manager.py.

ConfigManager loads and validates JSON/YAML config files.
Tests cover format detection, schema validation, and error wrapping.
All file I/O uses tmp_path — no real configs are read from disk.
"""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from autodoc.config.manager import ConfigManager
from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import ConfigError

_PLATFORM_VERSION: str = "2.0"

# Minimal valid configs matching the exact fields used in the existing conftest fixtures.
_VALID_PARSER_CONFIG: dict[str, Any] = {
    "platform_version": _PLATFORM_VERSION,
    "platform_branch_name": "develop",
    "platform_ref_type": "branch",
    "username": "testuser",
    "tfs_token": "test-tfs-pat-token",
    "artifactory_token": "test-art-token",
    "tfs_collection_url": "https://tfs.example.com",
    "manifests_remotes_path": "/platform/manifests",
    "conan_config_url": "https://art.example.com/conan-config.zip",
}

_VALID_CONFLUENCE_CONFIG: dict[str, Any] = {
    "url": "https://confluence.example.com",
    "token": "test-token-abc123",
    "space": "TEST",
    "verify_ssl": False,
    "confluence_request_timeout": 30,
    "publish_batch_size": 10,
    "publish_batch_delay_seconds": 0.0,
    "target_release_version": "Platform 2.0",
}

_PARSER_CONFIG_FILENAME: str = "parser_config.json"
_CONFLUENCE_CONFIG_FILENAME: str = "confluence_config.json"


# ---------------------------------------------------------------------------
# T4A.3.1 — loads a valid JSON parser config
# ---------------------------------------------------------------------------


def test_config_manager_loads_valid_json(tmp_path: Path) -> None:
    """ConfigManager successfully loads a valid parser config from a .json file.

    Verifies the happy-path for JSON format detection and schema validation.
    """
    config_file: Path = tmp_path / _PARSER_CONFIG_FILENAME
    config_file.write_text(json.dumps(_VALID_PARSER_CONFIG), encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.load_parser_config(_PARSER_CONFIG_FILENAME)

    assert result is not None


# ---------------------------------------------------------------------------
# T4A.3.2 — loads a valid YAML parser config (.yaml extension)
# ---------------------------------------------------------------------------


def test_config_manager_loads_valid_yaml(tmp_path: Path) -> None:
    """ConfigManager successfully loads a valid parser config from a .yaml file.

    Verifies that YAML format detection works alongside JSON.
    """
    config_file: Path = tmp_path / "parser_config.yaml"
    config_file.write_text(yaml.dump(_VALID_PARSER_CONFIG), encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.load_parser_config("parser_config.yaml")

    assert result is not None


# ---------------------------------------------------------------------------
# T4A.3.3 — loads a valid YAML parser config (.yml extension)
# ---------------------------------------------------------------------------


def test_config_manager_loads_valid_yml_extension(tmp_path: Path) -> None:
    """ConfigManager successfully loads a valid parser config from a .yml file.

    Both .yaml and .yml must be accepted as valid YAML extensions.
    """
    config_file: Path = tmp_path / "parser_config.yml"
    config_file.write_text(yaml.dump(_VALID_PARSER_CONFIG), encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.load_parser_config("parser_config.yml")

    assert result is not None


# ---------------------------------------------------------------------------
# T4A.3.4 — ConfigError raised on invalid schema, not raw ValidationError
# ---------------------------------------------------------------------------


def test_config_manager_raises_config_error_on_invalid_schema(
    tmp_path: Path,
) -> None:
    """_validate() wraps pydantic.ValidationError in ConfigError for invalid data.

    ConfigManager must never let pydantic internals leak to callers;
    every validation failure must surface as ConfigError so consumers
    can catch a single, stable exception type.
    """
    manager = ConfigManager(configs_dir=tmp_path)
    incomplete_data: dict[str, Any] = {"platform_version": _PLATFORM_VERSION}

    with pytest.raises(ConfigError):
        manager._validate(incomplete_data, ParserConfigSchema)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# T4A.3.5 — ConfigError raised for a nonexistent configs directory
# ---------------------------------------------------------------------------


def test_config_manager_raises_on_nonexistent_configs_dir(tmp_path: Path) -> None:
    """load_raw() raises ConfigError when configs_dir does not exist.

    ConfigManager defers directory validation to the first operation that
    needs the directory, and it must propagate ConfigError consistently so
    callers can rely on one exception type for all configuration failures.
    """
    nonexistent_dir: Path = tmp_path / "nonexistent"
    manager = ConfigManager(configs_dir=nonexistent_dir)

    with pytest.raises(ConfigError):
        manager.load_raw("parser_config")


# ---------------------------------------------------------------------------
# T4A.3.6 — ConfigError raised when configs_dir points to a file
# ---------------------------------------------------------------------------


def test_config_manager_raises_on_file_as_configs_dir(tmp_path: Path) -> None:
    """load_raw() raises ConfigError when configs_dir is a file, not a directory.

    Passing a file path where a directory is expected must fail with ConfigError
    rather than a bare OSError or AttributeError.
    """
    not_a_dir: Path = tmp_path / "not_a_dir.json"
    not_a_dir.write_text("{}", encoding="utf-8")
    manager = ConfigManager(configs_dir=not_a_dir)

    with pytest.raises(ConfigError):
        manager.load_raw("parser_config")


# ---------------------------------------------------------------------------
# T4A.3.7 — load_parser_config returns a ParserConfigSchema instance
# ---------------------------------------------------------------------------


def test_config_manager_load_parser_config_returns_correct_type(
    tmp_path: Path,
) -> None:
    """load_parser_config() returns a ParserConfigSchema instance on success.

    Guards against the loader returning a plain dict or a wrong schema class,
    which would break all callers that use attribute access on the config.
    """
    config_file: Path = tmp_path / _PARSER_CONFIG_FILENAME
    config_file.write_text(json.dumps(_VALID_PARSER_CONFIG), encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.load_parser_config(_PARSER_CONFIG_FILENAME)

    assert isinstance(result, ParserConfigSchema)


# ---------------------------------------------------------------------------
# T4A.3.8 — load_confluence_config returns a ConfluenceConfigSchema instance
# ---------------------------------------------------------------------------


def test_config_manager_load_confluence_config_returns_correct_type(
    tmp_path: Path,
) -> None:
    """load_confluence_config() returns a ConfluenceConfigSchema instance on success.

    Guards against the loader returning a plain dict or a wrong schema class,
    which would break all callers that use attribute access on the config.
    """
    config_file: Path = tmp_path / _CONFLUENCE_CONFIG_FILENAME
    config_file.write_text(json.dumps(_VALID_CONFLUENCE_CONFIG), encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.load_confluence_config(_CONFLUENCE_CONFIG_FILENAME)

    assert isinstance(result, ConfluenceConfigSchema)
