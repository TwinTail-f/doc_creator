"""
Общие фикстуры для tests/unit/config/.

Путь к tests/unit/config/resources/ (канонические valid_parser_config.*,
valid_confluence_config.*) — это константа ``CONFIG_RESOURCES_DIR`` из
корневого tests/conftest.py. У неё одно константное значение, поэтому она
используется как обычный модульный импорт, а не заворачивается в фикстуру
ради самого факта наличия фикстуры.
"""

import shutil
from pathlib import Path

import pytest

from tests.conftest import CONFIG_RESOURCES_DIR


@pytest.fixture(params=["nonexistent-dir", "file-instead-of-dir"])
def bad_configs_dir(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """
    Путь к ``configs_dir``, который не является валидной директорией.

    Параметризовано двумя вариантами того, что значит "плохой путь":
    ``nonexistent-dir`` — путь, которого никогда не было на диске, и
    ``file-instead-of-dir`` — путь, указывающий на существующий файл, а не
    на каталог. ConfigManager обязан одинаково отвергать оба случая.
    """
    if request.param == "nonexistent-dir":
        return tmp_path / "nonexistent"

    not_a_dir = tmp_path / "not_a_dir.json"
    not_a_dir.write_text("{}", encoding="utf-8")
    return not_a_dir


@pytest.fixture(params=["json", "yaml", "yml"])
def parser_config_file(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """
    Копия канонического parser-конфига во временной директории в одном
    из поддерживаемых форматов.

    Вместо пути dict -> сериализация -> файл копирует уже готовый файл
    ``resources/valid_parser_config.<fmt>`` (при этом .yml использует тот же
    исходник, что и .yaml, — расширения ``.yaml``/``.yml`` эквивалентны и
    отдельного ресурса для .yml не заводилось). pytest сам развернёт по
    одному тесту на каждое значение ``params``.
    """
    fmt = request.param
    source_fmt = "yaml" if fmt == "yml" else fmt
    source = CONFIG_RESOURCES_DIR / f"valid_parser_config.{source_fmt}"
    dest = tmp_path / f"parser_config.{fmt}"
    shutil.copy(source, dest)
    return dest
