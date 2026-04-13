"""Тесты ConfigManager и схем конфигурации."""

import json
import os
from pathlib import Path

import pytest

from autodoc.config.manager import ConfigManager
from autodoc.config.schemas import ParserConfigSchema
from autodoc.tests.unit.conftest import VALID_PARSER_CONFIG


class TestConfigManagerInit:
    def test_returns_manager_even_if_dir_not_exists(self, tmp_path: Path) -> None:
        """ConfigManager не бросает исключение при отсутствующей директории."""
        manager = ConfigManager(str(tmp_path / "nonexistent"))
        assert manager is not None

    def test_load_returns_none_if_dir_not_exists(self, tmp_path: Path) -> None:
        """load_parser_config возвращает None, если директория недоступна."""
        manager = ConfigManager(str(tmp_path / "nonexistent"))
        assert manager.load_parser_config() is None

    def test_initializes_with_valid_dir(self, tmp_path: Path) -> None:
        manager = ConfigManager(str(tmp_path))
        assert manager.configs_dir == tmp_path


class TestLoadParserConfig:
    def test_loads_valid_json(self, tmp_path: Path) -> None:
        (tmp_path / "parser_config.json").write_text(json.dumps(VALID_PARSER_CONFIG))
        config = ConfigManager(str(tmp_path)).load_parser_config()
        assert isinstance(config, ParserConfigSchema)
        assert config.platform_version == "2.0"

    def test_returns_none_on_invalid_json(self, tmp_path: Path) -> None:
        """Невалидный JSON → None, не исключение."""
        (tmp_path / "parser_config.json").write_text("{not valid json}")
        config = ConfigManager(str(tmp_path)).load_parser_config()
        assert config is None

    def test_returns_none_if_file_not_found(self, tmp_path: Path) -> None:
        """Файл конфига отсутствует → None, не исключение."""
        config = ConfigManager(str(tmp_path)).load_parser_config()
        assert config is None

    def test_loads_extra_fields_without_error(self, tmp_path: Path) -> None:
        config_data = {**VALID_PARSER_CONFIG, "unknown_future_field": "value"}
        (tmp_path / "parser_config.json").write_text(json.dumps(config_data))
        config = ConfigManager(str(tmp_path)).load_parser_config()
        assert config is not None
        assert config.platform_version == "2.0"

    def test_default_values_applied(self, tmp_path: Path) -> None:
        (tmp_path / "parser_config.json").write_text(json.dumps(VALID_PARSER_CONFIG))
        config = ConfigManager(str(tmp_path)).load_parser_config()
        assert config is not None
        assert config.max_retries == 3
        assert config.tfs_request_timeout == 15
        assert config.excluded_components == []


class TestParserConfigSchemaMissingRequiredFields:
    @pytest.mark.parametrize(
        "missing_field",
        [
            "platform_version",
            "platform_branch_name",
            "tfs_token",
            "tfs_dep_components_url",
            "manifests_remotes_path",
        ],
    )
    def test_missing_required_field_returns_none(
        self, missing_field: str, tmp_path: Path
    ) -> None:
        """Невалидная схема → None, не исключение."""
        config_data = {
            k: v for k, v in VALID_PARSER_CONFIG.items() if k != missing_field
        }
        (tmp_path / "parser_config.json").write_text(json.dumps(config_data))
        config = ConfigManager(str(tmp_path)).load_parser_config()
        assert config is None


class TestAutoDiscovery:
    def test_finds_yaml_when_no_json(self, tmp_path: Path) -> None:
        import yaml

        (tmp_path / "parser_config.yaml").write_text(yaml.dump(VALID_PARSER_CONFIG))
        config = ConfigManager(str(tmp_path)).load_parser_config()
        assert config is not None
        assert config.platform_version == "2.0"

    def test_prefers_json_over_yaml(self, tmp_path: Path) -> None:
        import yaml

        json_data = {**VALID_PARSER_CONFIG, "platform_version": "from_json"}
        yaml_data = {**VALID_PARSER_CONFIG, "platform_version": "from_yaml"}
        (tmp_path / "parser_config.json").write_text(json.dumps(json_data))
        (tmp_path / "parser_config.yaml").write_text(yaml.dump(yaml_data))
        config = ConfigManager(str(tmp_path)).load_parser_config()
        assert config is not None
        assert config.platform_version == "from_json"


class TestArtifactoryToken:
    """Тесты заполнения artifactory_token из конфига или env ART_TOKEN."""

    def test_token_from_config(self, tmp_path: Path) -> None:
        config_data = {**VALID_PARSER_CONFIG, "artifactory_token": "my-art-pat"}
        (tmp_path / "parser_config.json").write_text(json.dumps(config_data))
        config = ConfigManager(str(tmp_path)).load_parser_config()
        assert config is not None
        assert config.artifactory_token == "my-art-pat"

    def test_token_from_env_when_not_in_config(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        config_without_token = {
            k: v for k, v in VALID_PARSER_CONFIG.items() if k != "artifactory_token"
        }
        (tmp_path / "parser_config.json").write_text(json.dumps(config_without_token))
        monkeypatch.setenv("ART_TOKEN", "env-art-token")
        config = ConfigManager(str(tmp_path)).load_parser_config()
        assert config is not None
        assert config.artifactory_token == "env-art-token"

    def test_returns_none_when_token_missing_and_no_env(self, tmp_path: Path) -> None:
        """Отсутствие токена и env → None, не исключение."""
        config_without_token = {
            k: v for k, v in VALID_PARSER_CONFIG.items() if k != "artifactory_token"
        }
        (tmp_path / "parser_config.json").write_text(json.dumps(config_without_token))
        os.environ.pop("ART_TOKEN", None)
        config = ConfigManager(str(tmp_path)).load_parser_config()
        assert config is None
