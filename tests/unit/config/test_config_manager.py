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

from autodoc.config.manager import ConfigManager
from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import ConfigError

_PLATFORM_VERSION: str = "2.0"

_PARSER_CONFIG_YAML: str = "parser_config.yaml"
_PARSER_CONFIG_YML: str = "parser_config.yml"
_PARSER_CONFIG_JSON: str = "parser_config.json"
_CONFLUENCE_CONFIG_YAML: str = "confluence_config.yaml"
_CONFLUENCE_CONFIG_YML: str = "confluence_config.yml"
_CONFLUENCE_CONFIG_JSON: str = "confluence_config.json"


def _dump(fmt: str, data: dict) -> str:
    """Сериализует *data* в текст указанного формата (``json``/``yaml``/``yml``)."""
    if fmt == "json":
        return json.dumps(data)
    return yaml.dump(data)


@pytest.mark.contract
@pytest.mark.parametrize(
    "filename, fmt",
    [
        pytest.param(_PARSER_CONFIG_JSON, "json", id="json"),
        pytest.param(_PARSER_CONFIG_YAML, "yaml", id="yaml"),
        pytest.param(_PARSER_CONFIG_YML, "yaml", id="yml"),
    ],
)
def test_config_manager_loads_valid_config_by_extension(
    tmp_path: Path, filename: str, fmt: str, valid_parser_config: dict
) -> None:
    """ConfigManager успешно загружает и валидирует парсер-конфиг из любого
    поддерживаемого расширения (.json, .yaml, .yml), возвращая экземпляр
    ParserConfigSchema, а не «сырой» dict.
    """
    config_file: Path = tmp_path / filename
    config_file.write_text(_dump(fmt, valid_parser_config), encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.load_parser_config(filename)

    assert isinstance(result, ParserConfigSchema)


@pytest.mark.contract
def test_config_manager_loads_real_parser_config_resource_files(resources_dir: Path) -> None:
    """ConfigManager грузит настоящие файлы из tests/unit/config/resources/ напрямую.

    В отличие от остальных тестов этого модуля, здесь не создаётся временный
    файл через tmp_path и yaml.dump/json.dumps — configs_dir указывает прямо
    на committed-ресурсы репозитория (valid_parser_config.json/.yaml), как
    это делается для conan/manifests/options-фикстур в tests/unit/parser/.
    Это подтверждает, что сами ресурсные файлы валидны и пригодны к использованию,
    а не только словари, полученные через фикстуру valid_parser_config.
    """
    manager = ConfigManager(configs_dir=resources_dir)

    json_result = manager.load_parser_config("valid_parser_config.json")
    yaml_result = manager.load_parser_config("valid_parser_config.yaml")

    assert isinstance(json_result, ParserConfigSchema)
    assert isinstance(yaml_result, ParserConfigSchema)
    assert json_result == yaml_result, (
        "valid_parser_config.json и valid_parser_config.yaml должны описывать "
        "один и тот же конфиг в двух форматах."
    )


@pytest.mark.contract
def test_config_manager_loads_real_confluence_config_resource_files(resources_dir: Path) -> None:
    """Аналог test_config_manager_loads_real_parser_config_resource_files для Confluence-конфига."""
    manager = ConfigManager(configs_dir=resources_dir)

    json_result = manager.load_confluence_config("valid_confluence_config.json")
    yaml_result = manager.load_confluence_config("valid_confluence_config.yaml")

    assert isinstance(json_result, ConfluenceConfigSchema)
    assert isinstance(yaml_result, ConfluenceConfigSchema)
    assert json_result == yaml_result, (
        "valid_confluence_config.json и valid_confluence_config.yaml должны описывать "
        "один и тот же конфиг в двух форматах."
    )


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
@pytest.mark.parametrize(
    "filename, fmt",
    [
        pytest.param(_CONFLUENCE_CONFIG_JSON, "json", id="json"),
        pytest.param(_CONFLUENCE_CONFIG_YAML, "yaml", id="yaml"),
        pytest.param(_CONFLUENCE_CONFIG_YML, "yaml", id="yml"),
    ],
)
def test_config_manager_load_confluence_config_returns_correct_type(
    tmp_path: Path, filename: str, fmt: str, valid_confluence_config: dict,
) -> None:
    """load_confluence_config() при успехе возвращает экземпляр ConfluenceConfigSchema
    независимо от расширения файла (.json, .yaml, .yml) — симметрично
    test_config_manager_loads_valid_config_by_extension для парсер-конфига.

    Если загрузчик вернёт обычный dict или схему не того класса, весь код,
    обращающийся к конфигу через атрибуты, сломается.
    """
    config_file: Path = tmp_path / filename
    config_file.write_text(_dump(fmt, valid_confluence_config), encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.load_confluence_config(filename)

    assert isinstance(result, ConfluenceConfigSchema)


@pytest.mark.contract
@pytest.mark.parametrize(
    "present_formats, expected_marker",
    [
        # оба файла есть -> автопоиск по SUPPORTED_FORMATS должен предпочесть YAML
        pytest.param(("yaml", "json"), "yaml_wins", id="yaml-and-json-yaml-wins"),
        # YAML-файла нет вовсе -> автопоиск не должен отказывать, а найти JSON
        pytest.param(("json",), "json_only", id="json-only-backward-compat"),
    ],
)
def test_config_manager_autodiscover_prefers_yaml_but_falls_back_to_json(
    tmp_path: Path,
    valid_parser_config: dict,
    present_formats: tuple[str, ...],
    expected_marker: str,
) -> None:
    """Автопоиск конфига по базовому имени (без явного расширения):
    при наличии обоих файлов побеждает YAML (SUPPORTED_FORMATS ставит его
    перед JSON), а если YAML-файла нет вовсе — автопоиск не ломается и
    находит JSON, чтобы существующие проекты с .json-конфигами не пострадали.

    Это парный кейс формата "приоритет vs обратная совместимость": оба
    сценария бьют по одному и тому же коду автопоиска, поэтому собраны в один
    параметризованный тест, а не в два похожих отдельных.

    Помечено как ``contract`` (а не ``business_logic``): порядок разбора
    расширений конфигов — это деталь механики загрузки, а не правило
    предметной области.
    """
    if "yaml" in present_formats:
        yaml_data = {**valid_parser_config, "platform_version": "yaml_wins"}
        (tmp_path / "parser_config.yaml").write_text(yaml.dump(yaml_data), encoding="utf-8")
    if "json" in present_formats:
        # Когда YAML тоже присутствует, JSON-файл намеренно несёт другой маркер
        # ("json_loses"), чтобы assert ниже провалился, если бы автопоиск на
        # самом деле выбрал JSON, а не YAML.
        json_marker = "json_loses" if "yaml" in present_formats else "json_only"
        json_data = {**valid_parser_config, "platform_version": json_marker}
        (tmp_path / "parser_config.json").write_text(json.dumps(json_data), encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.load_parser_config()  # без явного имени → автопоиск

    assert result.platform_version == expected_marker


@pytest.mark.contract
def test_list_available_configs_excludes_examples_subdir(
    tmp_path: Path, valid_parser_config: dict
) -> None:
    """list_available_configs() не включает файлы из подпапки examples/.

    Примеры — это отдельная категория; смешивать их с рабочими конфигами нельзя.
    """
    (tmp_path / "parser_config.yaml").write_text(yaml.dump(valid_parser_config), encoding="utf-8")
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    (examples_dir / "parser_config.yaml").write_text(
        yaml.dump(valid_parser_config), encoding="utf-8"
    )

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.list_available_configs()

    assert result["yaml"] == ["parser_config.yaml"], (
        "list_available_configs() должен возвращать ровно один файл (рабочий), "
        "а не два (рабочий + пример из examples/)."
    )


@pytest.mark.contract
def test_list_example_configs_returns_files_from_examples_subdir(
    tmp_path: Path, valid_parser_config: dict,
) -> None:
    """list_example_configs() возвращает файлы из configs/examples/.

    Проверяет, что метод корректно читает подпапку examples/ и возвращает
    файлы, сгруппированные по формату.
    """
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    (examples_dir / "parser_config.yaml").write_text(
        yaml.dump(valid_parser_config), encoding="utf-8"
    )
    (examples_dir / "parser_config.json").write_text(
        json.dumps(valid_parser_config), encoding="utf-8"
    )

    manager = ConfigManager(configs_dir=tmp_path)
    result = manager.list_example_configs()

    assert "parser_config.yaml" in result["yaml"]
    assert "parser_config.json" in result["json"]


@pytest.mark.contract
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
def test_config_manager_wraps_yaml_error_in_config_error(tmp_path: Path) -> None:
    """_parse_file() оборачивает yaml.YAMLError в ConfigError с именем файла в сообщении."""
    config_file = tmp_path / "parser_config.yaml"
    config_file.write_text("key: [unbalanced", encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    with pytest.raises(ConfigError, match="parser_config.yaml"):
        manager.load_raw("parser_config.yaml")


@pytest.mark.infrastructure
def test_config_manager_wraps_oserror_in_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, valid_parser_config: dict,
) -> None:
    """_parse_file() оборачивает OSError при чтении файла в ConfigError."""
    config_file = tmp_path / "parser_config.json"
    config_file.write_text(json.dumps(valid_parser_config), encoding="utf-8")

    import autodoc.config.manager as manager_module

    original_open = Path.open

    def _raise_oserror(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.name == "parser_config.json":
            raise OSError("permission denied")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(manager_module.Path, "open", _raise_oserror)

    manager = ConfigManager(configs_dir=tmp_path)
    with pytest.raises(ConfigError, match="parser_config.json"):
        manager.load_raw("parser_config.json")


@pytest.mark.business_logic
def test_config_manager_rejects_non_dict_content(tmp_path: Path) -> None:
    """_parse_file() поднимает ConfigError, если верхний уровень содержимого — не dict
    (например список), даже если сам файл синтаксически валиден."""
    config_file = tmp_path / "parser_config.json"
    config_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    with pytest.raises(ConfigError, match="dict"):
        manager.load_raw("parser_config.json")


@pytest.mark.business_logic
def test_config_manager_validate_config_file_rejects_unsupported_extension(
    tmp_path: Path,
) -> None:
    """validate_config_file() поднимает ConfigError для расширения вне SUPPORTED_FORMATS,
    не пытаясь прочитать и разобрать содержимое файла."""
    config_file = tmp_path / "parser_config.toml"
    config_file.write_text("key = 'value'", encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    with pytest.raises(ConfigError, match="Неподдерживаемый формат"):
        manager.validate_config_file(str(config_file))


@pytest.mark.business_logic
def test_config_manager_validate_config_file_missing_file(tmp_path: Path) -> None:
    """validate_config_file() поднимает ConfigError, если файл по указанному пути не существует."""
    manager = ConfigManager(configs_dir=tmp_path)
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(ConfigError, match="Файл не найден"):
        manager.validate_config_file(str(missing))
