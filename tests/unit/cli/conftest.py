"""
Общие fixtures для тестов пакета tests/unit/cli.

Область видимости этих fixtures ограничена пакетом tests/unit/cli.
Обычные фабрики-функции и константы для тестов см. в tests/unit/cli/utils.py.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from tests.unit.cli.utils import make_confluence_config, make_parsed_result, make_publish_report


@pytest.fixture()
def configs_dir(tmp_path: Path) -> Path:
    """
    Создаёт пустую директорию конфигов внутри tmp_path.

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


_PUBLISH_COMMAND_MODULES: tuple[str, ...] = (
    "autodoc.cli.commands.publish.passports",
    "autodoc.cli.commands.publish.single_page",
    "autodoc.cli.commands.publish.targets",
)
"""
Модули команд публикации, которые импортируют ``make_publisher`` и ``load_parsed_data``.

Подмена должна попасть в модуль, где команда импортировала имя, а не в ``autodoc.cli.helpers``.
Новая команда, которая вызывает эти функции, должна быть добавлена сюда: иначе её тесты упадут
на настоящем ``make_publisher``.
"""


def _patch_in_command_modules(mocker: MockerFixture, name: str, replacement: MagicMock) -> None:
    """Подменяет ``name`` одним и тем же объектом во всех модулях команд публикации."""
    for module_path in _PUBLISH_COMMAND_MODULES:
        mocker.patch(f"{module_path}.{name}", new=replacement)


@pytest.fixture()
def make_publisher_mock(mocker: MockerFixture) -> MagicMock:
    """
    Подменяет ``make_publisher`` во всех командах публикации и возвращает эту подмену.

    Возвращаемое значение настраивает фикстура ``mock_publisher``. Тесты, которым нужен другой
    конфиг Confluence, переопределяют ``return_value`` подмены, а тесты на ошибку при создании
    паблишера задают ``side_effect``.

    Args:
        mocker: Фикстура pytest-mock для создания подмен.

    Returns:
        Подмена ``make_publisher``.
    """
    replacement = mocker.MagicMock(name="make_publisher")
    _patch_in_command_modules(mocker, "make_publisher", replacement)
    return replacement


@pytest.fixture()
def load_parsed_data_mock(mocker: MockerFixture) -> MagicMock:
    """
    Подменяет ``load_parsed_data`` во всех командах публикации: возвращает валидный результат.

    Тест, проверяющий отсутствие ``parsed_data.json``, эту фикстуру не запрашивает —
    тогда выполняется настоящая загрузка из пустой директории.

    Args:
        mocker: Фикстура pytest-mock для создания подмен.

    Returns:
        Подмена ``load_parsed_data``.
    """
    replacement = mocker.MagicMock(name="load_parsed_data", return_value=make_parsed_result())
    _patch_in_command_modules(mocker, "load_parsed_data", replacement)
    return replacement


@pytest.fixture()
def mock_publisher(
    mocker: MockerFixture,
    make_publisher_mock: MagicMock,
    load_parsed_data_mock: MagicMock,
) -> MagicMock:
    """
    Создаёт поддельный паблишер с успешным отчётом и отдаёт его из ``make_publisher``.

    Все методы публикации (``publish_passports``, ``publish_single_page``, ``publish_targets``)
    по умолчанию возвращают успешный отчёт; другой отчёт тест задаёт через
    ``mock_publisher.<метод>.return_value``. Конфиг Confluence по умолчанию — минимальный
    валидный. Загрузка данных парсера подменяется вместе с паблишером.

    Args:
        mocker: Фикстура pytest-mock для создания подмен.
        make_publisher_mock: Подмена ``make_publisher``.
        load_parsed_data_mock: Подмена ``load_parsed_data``.

    Returns:
        Поддельный объект паблишера.
    """
    publisher = mocker.MagicMock()
    report = make_publish_report()
    publisher.publish_passports.return_value = report
    publisher.publish_single_page.return_value = report
    publisher.publish_targets.return_value = report
    make_publisher_mock.return_value = (publisher, make_confluence_config())
    return publisher
