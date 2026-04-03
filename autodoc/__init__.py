"""Пакет автоматической генерации документации компонентов платформы."""

from autodoc.config.manager import ConfigManager
from autodoc.parser.parser import ComponentParser
from autodoc.publisher.publisher import DocumentPublisher

__all__ = [
    "ConfigManager",
    "ComponentParser",
    "DocumentPublisher",
]
