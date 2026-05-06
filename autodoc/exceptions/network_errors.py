"""Сетевые исключения."""

from autodoc.exceptions.base import DocGeneratorError


class NetworkError(DocGeneratorError):
    """Ошибка сетевой операции (TFS, Artifactory, Confluence)."""


class RetryExhaustedError(NetworkError):
    """Retry-попытки исчерпаны после N попыток."""
