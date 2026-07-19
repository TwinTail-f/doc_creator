"""
Общие фикстуры для tests/unit/config/.

resources_dir — путь к tests/unit/config/resources/, где лежат канонические
valid_parser_config.json/.yaml и valid_confluence_config.json/.yaml.
"""

from pathlib import Path

import pytest


@pytest.fixture
def resources_dir() -> Path:
    """Путь к общим тестовым ресурсам в tests/unit/config/resources/."""
    return Path(__file__).parent / "resources"
