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


@pytest.fixture()
def command_module() -> str:
    """
    Возвращает путь модуля команды, в котором подменяются ``make_publisher`` и ``load_parsed_data``.

    Подмены должны попасть в тот модуль, где команда их импортирует. Тестовый модуль
    переопределяет эту фикстуру и возвращает путь своей команды.

    Returns:
        Полный путь модуля, например ``"autodoc.cli.commands.publish.passports"``.

    Raises:
        NotImplementedError: Если тестовый модуль не переопределил фикстуру.
    """
    raise NotImplementedError("Переопределите фикстуру command_module в тестовом модуле")


@pytest.fixture()
def make_publisher_mock(mocker: MockerFixture, command_module: str) -> MagicMock:
    """
    Подменяет ``make_publisher`` в модуле команды и возвращает эту подмену.

    Возвращаемое значение настраивает фикстура ``mock_publisher``. Тесты, которым нужен другой
    конфиг Confluence, переопределяют ``return_value`` подмены, а тесты на ошибку при создании
    паблишера задают ``side_effect``.

    Args:
        mocker: Фикстура pytest-mock для создания подмен.
        command_module: Путь модуля команды.

    Returns:
        Подмена ``make_publisher``.
    """
    return mocker.patch(f"{command_module}.make_publisher")


@pytest.fixture()
def load_parsed_data_mock(mocker: MockerFixture, command_module: str) -> MagicMock:
    """
    Подменяет ``load_parsed_data`` в модуле команды: возвращает валидный результат парсера.

    Тест, проверяющий отсутствие ``parsed_data.json``, эту фикстуру не запрашивает —
    тогда выполняется настоящая загрузка из пустой директории.

    Args:
        mocker: Фикстура pytest-mock для создания подмен.
        command_module: Путь модуля команды.

    Returns:
        Подмена ``load_parsed_data``.
    """
    return mocker.patch(f"{command_module}.load_parsed_data", return_value=make_parsed_result())


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
