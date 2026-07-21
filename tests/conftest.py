"""
Корневые фикстуры, общие для всего тестового набора autodoc.

Единственный источник "минимального валидного конфига" парсера/Confluence —
tests/unit/config/resources/*.json (там же лежат эквивалентные *.yaml,
подтверждающие, что ConfigManager одинаково успешно грузит оба формата).
"""

import json
from pathlib import Path
from typing import Any

import pytest

CONFIG_RESOURCES_DIR: Path = Path(__file__).parent / "unit" / "config" / "resources"
"""Путь к каноническим ресурсам конфигов: tests/unit/config/resources/.

Значение константное для всего тестового набора, поэтому это обычный
модульный импорт (``from tests.conftest import CONFIG_RESOURCES_DIR``),
а не фикстура — заводить фикстуру ради одного константного значения избыточно.
"""


@pytest.fixture
def valid_parser_config() -> dict[str, Any]:
    """Минимальный словарь, удовлетворяющий обязательным полям ParserConfigSchema."""
    return json.loads((CONFIG_RESOURCES_DIR / "valid_parser_config.json").read_text())


@pytest.fixture
def valid_confluence_config() -> dict[str, Any]:
    """Минимальный словарь, удовлетворяющий обязательным полям ConfluenceConfigSchema."""
    return json.loads((CONFIG_RESOURCES_DIR / "valid_confluence_config.json").read_text())
