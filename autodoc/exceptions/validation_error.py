"""Исключение валидации данных."""

from autodoc.exceptions.base import DocGeneratorError


class ValidationError(DocGeneratorError):
    """Ошибка валидации данных (Pydantic или пользовательская)."""
