"""Дымовые тесты для autodoc/common/logger.py.

Проверяет, что логгер проекта импортируется и имеет ожидаемую конфигурацию.
"""

import pytest

from autodoc.common.logger import logger

_EXPECTED_NAME_PREFIX: str = "doc_parser"


@pytest.mark.infrastructure
def test_logger_name_starts_with_doc_parser() -> None:
    """Имя логгера проекта должно начинаться с 'doc_parser'.

    Защита от переименования логгера на универсальное имя, которое
    могло бы загрязнить вывод логирования третьей стороны или столкнуться с другими логгерами.
    """
    assert logger.name.startswith(_EXPECTED_NAME_PREFIX)

