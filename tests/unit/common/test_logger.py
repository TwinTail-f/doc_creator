"""Дымовые тесты для autodoc/common/logger.py.

Проверяет, что логгер проекта импортируется и имеет ожидаемую конфигурацию.
"""

import pytest

import logging

from autodoc.common.logger import logger

_EXPECTED_NAME_PREFIX: str = "doc_parser"


@pytest.mark.infrastructure
def test_logger_is_importable() -> None:
    """Импорт autodoc.common.logger не вызывает ImportError.

    Достижение этой строки доказывает, что импорт в начале файла прошёл успешно.
    """
    assert logger is not None


@pytest.mark.infrastructure
def test_logger_name_starts_with_doc_parser() -> None:
    """Имя логгера проекта должно начинаться с 'doc_parser'.

    Защита от переименования логгера на универсальное имя, которое
    могло бы загрязнить вывод логирования третьей стороны или столкнуться с другими логгерами.
    """
    assert logger.name.startswith(_EXPECTED_NAME_PREFIX)


@pytest.mark.infrastructure
def test_logger_is_standard_logger_instance() -> None:
    """Экспортируемый логгер должен быть стандартным экземпляром logging.Logger.

    Гарантирует, что код ниже по потоку может использовать полный API logging.Logger без
    неожиданностей от объекта-прокси или адаптера.
    """
    assert isinstance(logger, logging.Logger)
