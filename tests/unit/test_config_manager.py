"""Тесты для autodoc/config/manager.py.

ConfigManager загружает и валидирует конфиги в форматах JSON/YAML. Тесты
покрывают определение формата, валидацию по схеме и оборачивание ошибок.
Весь файловый ввод-вывод идёт через tmp_path — реальные конфиги с диска
не читаются.
"""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError as PydanticValidationError

from autodoc.config.manager import ConfigManager
from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import ConfigError

_PLATFORM_VERSION: str = "2.0"

# Минимальные валидные конфиги, повторяющие набор полей из фикстур в conftest.
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

_PARSER_CONFIG_YAML: str = "parser_config.yaml"
_PARSER_CONFIG_JSON: str = "parser_config.json"
_CONFLUENCE_CONFIG_YAML: str = "confluence_config.yaml"


def _dump(fmt: str, data: dict) -> str:
    """Сериализует *data* в текст указанного формата (``json``/``yaml``/``yml``)."""
    if fmt == "json":
        return json.dumps(data)
    return yaml.dump(data)


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "filename, fmt",
    [
        pytest.param(_PARSER_CONFIG_JSON, "json", id="json"),
        pytest.param(_PARSER_CONFIG_YAML, "yaml", id="yaml"),
        pytest.param("parser_config.yml", "yaml", id="yml"),
    ],
)
def test_config_manager_loads_valid_config_by_extension(
    tmp_path: Path, filename: str, fmt: str
) -> None:
    """ConfigManager успешно загружает и валидирует парсер-конфиг из любого
    поддерживаемого расширения (.json, .yaml, .yml), возвращая экземпляр
    ParserConfigSchema, а не «сырой» dict.
    """
    config_file: Path = tmp_path / filename
    config_file.write_text(_dump(fmt, _VALID_PARSER_CONFIG), encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.load_parser_config(filename)

    assert isinstance(result, ParserConfigSchema)


@pytest.mark.business_logic
def test_config_manager_raises_config_error_on_invalid_schema(
    tmp_path: Path,
) -> None:
    """_validate() оборачивает pydantic.ValidationError в ConfigError для невалидных данных.

    ConfigManager никогда не должен пропускать внутренние исключения pydantic наружу —
    каждая ошибка валидации должна проявляться как ConfigError, чтобы вызывающий код
    мог ловить один стабильный тип исключения.
    """
    manager = ConfigManager(configs_dir=tmp_path)
    incomplete_data: dict[str, Any] = {"platform_version": _PLATFORM_VERSION}

    with pytest.raises(ConfigError):
        manager._validate(incomplete_data, ParserConfigSchema)  # type: ignore[attr-defined]


@pytest.mark.business_logic
def test_config_manager_raises_on_nonexistent_configs_dir(tmp_path: Path) -> None:
    """load_raw() поднимает ConfigError, если configs_dir не существует.

    ConfigManager откладывает проверку директории до первой операции, которой
    она реально нужна, но при этом должен стабильно пробрасывать ConfigError,
    чтобы вызывающий код мог полагаться на единый тип исключения для всех
    ошибок конфигурации.
    """
    nonexistent_dir: Path = tmp_path / "nonexistent"
    manager = ConfigManager(configs_dir=nonexistent_dir)

    with pytest.raises(ConfigError):
        manager.load_raw("parser_config")


@pytest.mark.business_logic
def test_config_manager_raises_on_file_as_configs_dir(tmp_path: Path) -> None:
    """load_raw() поднимает ConfigError, если configs_dir указывает на файл, а не директорию.

    Передача пути к файлу там, где ожидается директория, должна завершаться
    ConfigError, а не «сырым» OSError или AttributeError.
    """
    not_a_dir: Path = tmp_path / "not_a_dir.json"
    not_a_dir.write_text("{}", encoding="utf-8")
    manager = ConfigManager(configs_dir=not_a_dir)

    with pytest.raises(ConfigError):
        manager.load_raw("parser_config")


@pytest.mark.contract
def test_config_manager_load_confluence_config_returns_correct_type(
    tmp_path: Path,
) -> None:
    """load_confluence_config() при успехе возвращает экземпляр ConfluenceConfigSchema.

    Защищает от случая, когда загрузчик вернёт обычный dict или схему не того
    класса, что сломает весь код, обращающийся к конфигу через атрибуты.
    """
    config_file: Path = tmp_path / _CONFLUENCE_CONFIG_YAML
    config_file.write_text(yaml.dump(_VALID_CONFLUENCE_CONFIG), encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.load_confluence_config(_CONFLUENCE_CONFIG_YAML)

    assert isinstance(result, ConfluenceConfigSchema)


@pytest.mark.business_logic
def test_config_manager_prefers_yaml_over_json_when_both_exist(tmp_path: Path) -> None:
    """При наличии обоих файлов (yaml + json) загружается YAML-версия.

    Гарантирует, что SUPPORTED_FORMATS=['.yaml', ...] применяется корректно
    и YAML побеждает JSON при автопоиске по базовому имени.
    """
    yaml_file = tmp_path / "parser_config.yaml"
    yaml_data = {**_VALID_PARSER_CONFIG, "platform_version": "yaml_wins"}
    yaml_file.write_text(yaml.dump(yaml_data), encoding="utf-8")

    json_file = tmp_path / "parser_config.json"
    json_data = {**_VALID_PARSER_CONFIG, "platform_version": "json_loses"}
    json_file.write_text(json.dumps(json_data), encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.load_parser_config()  # без явного имени → автопоиск

    assert result is not None
    assert result.platform_version == "yaml_wins", (
        "Ожидался YAML (yaml_wins), но загружен JSON (json_loses). "
        "SUPPORTED_FORMATS должен ставить YAML перед JSON."
    )


@pytest.mark.business_logic
def test_list_available_configs_excludes_examples_subdir(tmp_path: Path) -> None:
    """list_available_configs() не включает файлы из подпапки examples/.

    Примеры — это отдельная категория; смешивать их с рабочими конфигами нельзя.
    """
    (tmp_path / "parser_config.yaml").write_text(yaml.dump(_VALID_PARSER_CONFIG), encoding="utf-8")
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    (examples_dir / "parser_config.yaml").write_text(
        yaml.dump(_VALID_PARSER_CONFIG), encoding="utf-8"
    )

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.list_available_configs()

    assert result["yaml"] == ["parser_config.yaml"], (
        "list_available_configs() должен возвращать ровно один файл (рабочий), "
        "а не два (рабочий + пример из examples/)."
    )


@pytest.mark.business_logic
def test_list_example_configs_returns_files_from_examples_subdir(
    tmp_path: Path,
) -> None:
    """list_example_configs() возвращает файлы из configs/examples/.

    Проверяет, что метод корректно читает подпапку examples/ и возвращает
    файлы, сгруппированные по формату.
    """
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    (examples_dir / "parser_config.yaml").write_text(
        yaml.dump(_VALID_PARSER_CONFIG), encoding="utf-8"
    )
    (examples_dir / "parser_config.json").write_text(
        json.dumps(_VALID_PARSER_CONFIG), encoding="utf-8"
    )

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.list_example_configs()

    assert "parser_config.yaml" in result["yaml"]
    assert "parser_config.json" in result["json"]


@pytest.mark.business_logic
def test_list_example_configs_returns_empty_when_no_examples_dir(
    tmp_path: Path,
) -> None:
    """list_example_configs() возвращает пустые списки, если examples/ отсутствует."""
    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.list_example_configs()

    assert all(files == [] for files in result.values()), (
        "Ожидались пустые списки при отсутствии examples/, " f"получено: {result}"
    )


@pytest.mark.business_logic
def test_config_manager_still_loads_json_for_backward_compatibility(
    tmp_path: Path,
) -> None:
    """Конфиг в формате JSON без соседнего YAML успешно находится и загружается.

    YAML в SUPPORTED_FORMATS стоит перед JSON (см.
    test_config_manager_prefers_yaml_over_json_when_both_exist), но это не должно
    означать, что автопоиск отказывается работать с JSON, когда YAML-файла попросту
    нет: проекты с существующими .json-конфигами не должны ломаться.
    """
    config_file = tmp_path / "parser_config.json"
    config_file.write_text(json.dumps(_VALID_PARSER_CONFIG), encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.load_parser_config()  # автопоиск — найдёт .json

    assert result is not None
    assert isinstance(result, ParserConfigSchema)


@pytest.mark.business_logic
def test_parse_file_wraps_yaml_syntax_error_in_config_error(tmp_path: Path) -> None:
    """_parse_file() оборачивает yaml.YAMLError в ConfigError вместо того, чтобы
    пропускать исключение PyYAML наружу как есть."""
    config_file = tmp_path / "parser_config.yaml"
    # Несбалансированные скобки-флоу — гарантированно ломают YAML-парсер.
    config_file.write_text("platform_version: [unclosed\n", encoding="utf-8")
    manager = ConfigManager(configs_dir=tmp_path)

    with pytest.raises(ConfigError, match="Некорректный YAML"):
        manager._parse_file(config_file)  # type: ignore[attr-defined]


@pytest.mark.business_logic
def test_parse_file_wraps_os_error_in_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_parse_file() оборачивает OSError при чтении файла в ConfigError."""
    config_file = tmp_path / "parser_config.yaml"
    config_file.write_text(yaml.dump(_VALID_PARSER_CONFIG), encoding="utf-8")

    def _raise_os_error(self, *args, **kwargs):
        raise OSError("disk error")

    monkeypatch.setattr(Path, "open", _raise_os_error)
    manager = ConfigManager(configs_dir=tmp_path)

    with pytest.raises(ConfigError, match="Ошибка чтения"):
        manager._parse_file(config_file)  # type: ignore[attr-defined]


@pytest.mark.business_logic
def test_parse_file_raises_when_content_is_not_a_dict(tmp_path: Path) -> None:
    """_parse_file() поднимает ConfigError, если верхнеуровневое содержимое файла — не dict."""
    config_file = tmp_path / "parser_config.yaml"
    config_file.write_text("- 1\n- 2\n", encoding="utf-8")  # верхний уровень — список
    manager = ConfigManager(configs_dir=tmp_path)

    with pytest.raises(ConfigError, match="должен содержать объект"):
        manager._parse_file(config_file)  # type: ignore[attr-defined]


@pytest.mark.business_logic
def test_parse_file_raises_when_path_is_not_a_file(tmp_path: Path) -> None:
    """_parse_file() поднимает ConfigError, если переданный путь не указывает на файл."""
    manager = ConfigManager(configs_dir=tmp_path)
    missing = tmp_path / "does_not_exist.yaml"

    with pytest.raises(ConfigError, match="не указывает на файл"):
        manager._parse_file(missing)  # type: ignore[attr-defined]


@pytest.mark.business_logic
def test_validate_config_file_raises_on_unsupported_extension(tmp_path: Path) -> None:
    """validate_config_file() поднимает ConfigError для расширений вне SUPPORTED_FORMATS."""
    config_file = tmp_path / "parser_config.toml"
    config_file.write_text("platform_version = '2.0'\n", encoding="utf-8")
    manager = ConfigManager(configs_dir=tmp_path)

    with pytest.raises(ConfigError, match="Неподдерживаемый формат"):
        manager.validate_config_file(str(config_file))


@pytest.mark.business_logic
def test_confluence_config_normalize_url_rejects_empty_url() -> None:
    """ConfluenceConfigSchema._normalize_url отклоняет пустой (или состоящий из
    пробелов) url именно со своим сообщением об ошибке — это подтверждает, что
    отказ идёт из проверки непустоты внутри _normalize_url, а не из какого-то
    другого механизма валидации (например, обязательности поля)."""
    data = {**_VALID_CONFLUENCE_CONFIG, "url": "   "}

    with pytest.raises(PydanticValidationError, match="url не может быть пустым"):
        ConfluenceConfigSchema(**data)


@pytest.mark.business_logic
def test_confluence_config_normalize_url_strips_trailing_slash() -> None:
    """ConfluenceConfigSchema._normalize_url убирает завершающий слеш у валидного url."""
    data = {**_VALID_CONFLUENCE_CONFIG, "url": "https://confluence.example.com/"}

    config = ConfluenceConfigSchema(**data)

    assert config.url == "https://confluence.example.com"


@pytest.mark.business_logic
def test_parser_config_tfs_token_not_empty_rejects_empty_string() -> None:
    """ParserConfigSchema.tfs_token_not_empty отклоняет пустую строку именно со
    своим сообщением об ошибке — подтверждает, что отказ приходит из проверки
    непустоты внутри tfs_token_not_empty, а не из общей обязательности поля."""
    data = {**_VALID_PARSER_CONFIG, "tfs_token": ""}

    with pytest.raises(PydanticValidationError, match="tfs_token не может быть пустой строкой"):
        ParserConfigSchema(**data)
