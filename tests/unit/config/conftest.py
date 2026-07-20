"""
Общие фикстуры для tests/unit/config/.

Путь к tests/unit/config/resources/ (канонические valid_parser_config.*,
valid_confluence_config.*) уже даёт фикстура ``config_resources_dir`` из
корневого tests/conftest.py — отдельной локальной фикстуры на тот же самый
каталог здесь специально не заводим, чтобы не иметь двух имён для одного и
того же пути.
"""

from pathlib import Path

import pytest


@pytest.fixture(params=["nonexistent-dir", "file-instead-of-dir"])
def bad_configs_dir(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """Путь к ``configs_dir``, который не является валидной директорией.

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
def parser_config_file(
    request: pytest.FixtureRequest, tmp_path: Path, config_resources_dir: Path
) -> Path:
    """Копия канонического parser-конфига во временной директории в одном
    из поддерживаемых форматов.

    Вместо пути dict -> сериализация -> файл копирует уже готовый файл
    ``resources/valid_parser_config.<fmt>`` (при этом .yml использует тот же
    исходник, что и .yaml, — расширения ``.yaml``/``.yml`` эквивалентны и
    отдельного ресурса для .yml не заводилось). pytest сам развернёт по
    одному тесту на каждое значение ``params``.
    """
    fmt = request.param
    source_fmt = "yaml" if fmt == "yml" else fmt
    source = config_resources_dir / f"valid_parser_config.{source_fmt}"
    dest = tmp_path / f"parser_config.{fmt}"
    dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return dest
