"""Исключение конфигурации."""

from autodoc.exceptions.base import DocGeneratorError


class ConfigError(DocGeneratorError):
    """Ошибка конфигурации: отсутствует поле, неверный тип или файл не найден."""
