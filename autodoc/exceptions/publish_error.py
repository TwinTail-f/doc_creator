"""Исключение публикации."""

from autodoc.exceptions.base import DocGeneratorError


class PublishError(DocGeneratorError):
    """Ошибка публикации страницы в Confluence."""
