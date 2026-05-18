"""Smoke tests for autodoc/common/logger.py.

Verifies the project logger is importable and has the expected configuration.
"""

import pytest

import logging

from autodoc.common.logger import logger

_EXPECTED_NAME_PREFIX: str = "doc_parser"


@pytest.mark.infrastructure
def test_logger_is_importable() -> None:
    """Importing autodoc.common.logger raises no ImportError.

    Reaching this line proves the import at the top of the file succeeded.
    """
    assert logger is not None


@pytest.mark.infrastructure
def test_logger_name_starts_with_doc_parser() -> None:
    """The project logger name must start with 'doc_parser'.

    Guards against the logger being renamed to a generic name that
    would pollute third-party logging output or collide with other loggers.
    """
    assert logger.name.startswith(_EXPECTED_NAME_PREFIX)


@pytest.mark.infrastructure
def test_logger_is_standard_logger_instance() -> None:
    """The exported logger must be a standard logging.Logger instance.

    Ensures downstream code can use the full logging.Logger API without
    surprises from a proxy or adapter object.
    """
    assert isinstance(logger, logging.Logger)
