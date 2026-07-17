"""
Корневые фикстуры, общие для всего тестового набора autodoc.

Единственный источник "минимального валидного конфига" парсера/Confluence —
tests/unit/config/resources/*.json (там же лежат эквивалентные *.yaml,
подтверждающие, что ConfigManager одинаково успешно грузит оба формата).
Ресурсы физически живут рядом с их основным владельцем — tests/unit/config/ —
по тому же принципу, что и tests/unit/parser/resources/ или
tests/unit/publisher/resources/. Локальные копии одних и тех же словарей были
разбросаны по conftest.py и тестовым модулям в parser/, cli/, publisher/ и
test_config_manager.py; эти фикстуры — канонический источник, остальные
места переиспользуют их вместо повторного набора полей.
"""

import json
from pathlib import Path
from typing import Any

import pytest

_CONFIG_RESOURCES_DIR: Path = Path(__file__).parent / "unit" / "config" / "resources"


@pytest.fixture
def config_resources_dir() -> Path:
    """Путь к каноническим ресурсам конфигов: tests/unit/config/resources/."""
    return _CONFIG_RESOURCES_DIR


@pytest.fixture
def valid_parser_config() -> dict[str, Any]:
    """Минимальный словарь, удовлетворяющий обязательным полям ParserConfigSchema."""
    return json.loads((_CONFIG_RESOURCES_DIR / "valid_parser_config.json").read_text())


@pytest.fixture
def valid_confluence_config() -> dict[str, Any]:
    """Минимальный словарь, удовлетворяющий обязательным полям ConfluenceConfigSchema."""
    return json.loads((_CONFIG_RESOURCES_DIR / "valid_confluence_config.json").read_text())
