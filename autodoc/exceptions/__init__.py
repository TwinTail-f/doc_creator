"""
Public API пакета autodoc.exceptions.

Re-export всех публичных исключений — обратная совместимость:
``from autodoc.exceptions import ComponentParsingError`` продолжает работать.
"""

from autodoc.exceptions.base import DocGeneratorError
from autodoc.exceptions.config_error import ConfigError
from autodoc.exceptions.network_errors import NetworkError, RetryExhaustedError
from autodoc.exceptions.parsing_errors import ComponentParsingError, ParsingError
from autodoc.exceptions.publish_error import PublishError
from autodoc.exceptions.validation_error import ValidationError

__all__ = [
    "DocGeneratorError",
    "ConfigError",
    "NetworkError",
    "RetryExhaustedError",
    "ParsingError",
    "ComponentParsingError",
    "PublishError",
    "ValidationError",
]
