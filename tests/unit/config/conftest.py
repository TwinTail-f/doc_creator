"""
Общие фикстуры для tests/unit/config/.

resources_dir — путь к tests/unit/config/resources/, где лежат канонические
valid_parser_config.json/.yaml и valid_confluence_config.json/.yaml. Названа
так же, как аналогичная фикстура в tests/unit/parser/conftest.py, чтобы
тестовые модули этого пакета могли обращаться к реальным файлам ресурсов
напрямую (а не только через словарные фикстуры valid_parser_config /
valid_confluence_config из корневого tests/conftest.py).
"""

from pathlib import Path

import pytest


@pytest.fixture
def resources_dir() -> Path:
    """Путь к общим тестовым ресурсам в tests/unit/config/resources/."""
    return Path(__file__).parent / "resources"
