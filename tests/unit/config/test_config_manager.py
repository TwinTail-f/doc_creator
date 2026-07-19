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

def _dump(fmt: str, data: dict) -> str:
    """Сериализует *data* в текст указанного формата (``json``/``yaml``/``yml``)."""
    if fmt == "json":
        return json.dumps(data)
    return yaml.dump(data)


@pytest.mark.contract
@pytest.mark.parametrize(
    "filename, fmt",
    [
        pytest.param("parser_config.json", "json", id="json"),
        pytest.param("parser_config.yaml", "yaml", id="yaml"),
        pytest.param("parser_config.yml", "yaml", id="yml"),
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
@pytest.mark.parametrize(
    "loader_name, schema_class, stem",
    [
        pytest.param("load_parser_config", ParserConfigSchema, "valid_parser_config", id="parser"),
        pytest.param(
            "load_confluence_config", ConfluenceConfigSchema, "valid_confluence_config", id="confluence"
        ),
    ],
)
def test_config_manager_loads_real_resource_files_json_and_yaml_agree(
    resources_dir: Path, loader_name: str, schema_class: type, stem: str
) -> None:
    """ConfigManager грузит настоящие файлы из tests/unit/config/resources/ напрямую —
    и для парсер-, и для confluence-конфига одним и тем же способом.
    """
    manager = ConfigManager(configs_dir=resources_dir)
    loader = getattr(manager, loader_name)

    json_result = loader(f"{stem}.json")
    yaml_result = loader(f"{stem}.yaml")

    assert isinstance(json_result, schema_class)
    assert isinstance(yaml_result, schema_class)
    assert json_result == yaml_result, (
        f"{stem}.json и {stem}.yaml должны описывать один и тот же конфиг в двух форматах."
    )


@pytest.mark.business_logic
def test_config_manager_raises_config_error_on_invalid_schema(
    tmp_path: Path,
) -> None:
    """_validate() оборачивает pydantic.ValidationError в ConfigError для невалидных данных.
    """
    manager = ConfigManager(configs_dir=tmp_path)
    incomplete_data: dict[str, Any] = {"platform_version": "2.0"}

    with pytest.raises(ConfigError):
        manager._validate(incomplete_data, ParserConfigSchema)  # type: ignore[attr-defined]


def _make_nonexistent_dir(tmp_path: Path) -> Path:
    """Путь, который никогда не создавался на диске."""
    return tmp_path / "nonexistent"


def _make_file_instead_of_dir(tmp_path: Path) -> Path:
    """Существующий файл — валидный Path, но не директория."""
    not_a_dir = tmp_path / "not_a_dir.json"
    not_a_dir.write_text("{}", encoding="utf-8")
    return not_a_dir


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "make_bad_configs_dir",
    [
        pytest.param(_make_nonexistent_dir, id="nonexistent-dir"),
        pytest.param(_make_file_instead_of_dir, id="file-instead-of-dir"),
    ],
)
def test_config_manager_raises_on_invalid_configs_dir(
    tmp_path: Path, make_bad_configs_dir
) -> None:
    """load_raw() поднимает ConfigError, если configs_dir не указывает на существующую
    директорию — будь то отсутствующий путь или путь, указывающий на файл.
    """
    bad_configs_dir = make_bad_configs_dir(tmp_path)
    manager = ConfigManager(configs_dir=bad_configs_dir)

    with pytest.raises(ConfigError):
        manager.load_raw("parser_config")


@pytest.mark.contract
@pytest.mark.parametrize(
    "filename, fmt",
    [
        pytest.param("confluence_config.json", "json", id="json"),
        pytest.param("confluence_config.yaml", "yaml", id="yaml"),
        pytest.param("confluence_config.yml", "yaml", id="yml"),
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
    перед JSON), а если YAML-файла нет вовсе - автопоиск не ломается и
    находит JSON.
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
@pytest.mark.parametrize("examples_dir_exists", [True, False], ids=["present", "missing"])
def test_list_example_configs_reflects_examples_subdir_presence(
    tmp_path: Path, valid_parser_config: dict, examples_dir_exists: bool
) -> None:
    """list_example_configs() возвращает файлы из configs/examples/, если она есть
    и заполнена, и пустые списки по каждому формату, если её нет вовсе."""
    if examples_dir_exists:
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

    if examples_dir_exists:
        assert "parser_config.yaml" in result["yaml"]
        assert "parser_config.json" in result["json"]
    else:
        assert all(files == [] for files in result.values()), (
            "Ожидались пустые списки при отсутствии examples/, " f"получено: {result}"
        )


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "filename, content, match",
    [
        # синтаксически невалидный YAML -> сообщение об ошибке содержит имя файла
        pytest.param(
            "parser_config.yaml", "key: [unbalanced", "parser_config.yaml", id="malformed-yaml-syntax"
        ),
        # синтаксически валидный JSON, но верхний уровень — не dict (список)
        pytest.param("parser_config.json", json.dumps([1, 2, 3]), "dict", id="non-dict-top-level"),
    ],
)
def test_config_manager_wraps_malformed_content_in_config_error(
    tmp_path: Path, filename: str, content: str, match: str
) -> None:
    """_parse_file() оборачивает разные виды «плохого» содержимого файла в ConfigError
    с сообщением: синтаксически невалидный YAML — с именем файла в
    тексте ошибки, а структурно невалидный (не-dict) контент — с явным
    упоминанием "dict", а не пропускает исходное исключение PyYAML/json наружу как есть.
    """
    config_file = tmp_path / filename
    config_file.write_text(content, encoding="utf-8")

    manager = ConfigManager(configs_dir=tmp_path)
    with pytest.raises(ConfigError, match=match):
        manager.load_raw(filename)


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
@pytest.mark.parametrize(
    "create_unsupported_file, match",
    [
        # файл существует, но расширение вне SUPPORTED_FORMATS
        pytest.param(True, "Неподдерживаемый формат", id="unsupported-extension"),
        # расширение поддерживается, но по пути ничего нет
        pytest.param(False, "Файл не найден", id="missing-file"),
    ],
)
def test_config_manager_validate_config_file_rejects_bad_path(
    tmp_path: Path, create_unsupported_file: bool, match: str
) -> None:
    """validate_config_file() поднимает ConfigError для двух разных «плохих путей» —
    неподдерживаемого расширения и отсутствующего файла - каждый раз со своим,
    специфичным для причины сообщением, не пытаясь прочитать и разобрать
    содержимое там, где в этом нет смысла.
    """
    if create_unsupported_file:
        target_file = tmp_path / "parser_config.toml"
        target_file.write_text("key = 'value'", encoding="utf-8")
    else:
        target_file = tmp_path / "does_not_exist.yaml"

    manager = ConfigManager(configs_dir=tmp_path)
    with pytest.raises(ConfigError, match=match):
        manager.validate_config_file(str(target_file))
