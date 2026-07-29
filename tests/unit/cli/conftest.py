"""Общие fixtures для тестов пакета tests/unit/cli.

Область видимости этих fixtures ограничена пакетом tests/unit/cli.
Обычные фабрики-функции и константы для тестов см. в tests/unit/cli/utils.py.
"""

from pathlib import Path

import pytest


@pytest.fixture()
def configs_dir(tmp_path: Path) -> Path:
    """Создаёт пустую директорию конфигов внутри tmp_path.

    Требуется, так как корневая команда ``cli`` завершается с кодом 1, если
    директория, переданная в ``--configs-dir``, не существует.

    Args:
        tmp_path: Встроенная pytest-фикстура с временной директорией.

    Returns:
        Путь к пустой директории конфигов.
    """
    directory = tmp_path / "configs"
    directory.mkdir()
    return directory
