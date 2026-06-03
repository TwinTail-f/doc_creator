"""
Интерфейс двухфазового фетчера.
"""

from abc import ABC, abstractmethod
from typing import Any

from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.pipeline.context_protocol import PipelineContextProtocol

_NOT_CONFIGURED_MSG: str = (
    "fetch() вызван до configure(). Сначала вызовите configure(ctx)."
)


class BaseFetcher[T](ABC):
    """
    Интерфейс двухфазового фетчера: ``configure()`` → ``fetch()``.

    Разделение на две фазы позволяет внедрять зависимости через ``configure(ctx)``
    без прямой передачи контекста в ``fetch()``, что упрощает тестирование.

    Порядок вызова и инвариант полностью контролируются базовым классом:
    - ``configure()`` делегирует ``_configure()`` и выставляет ``_configured = True``.
    - ``fetch()`` проверяет ``_configured`` и делегирует ``_fetch()``.

    Подклассы реализуют только ``_configure()`` и ``_fetch()``.
    """

    def __init__(self) -> None:
        """Инициализирует фетчер; ``_configured`` выставляется в True в ``configure()``."""
        self._configured: bool = False

    @abstractmethod
    def _configure(self, ctx: PipelineContextProtocol) -> None:
        """
        Реализует инициализацию фетчера из контекста пайплайна.

        Вызывается из ``configure()`` до выставления ``_configured = True``.

        Args:
            ctx: Контекст пайплайна с конфигурацией и состоянием.
        """

    @abstractmethod
    def _fetch(self, *args: Any, **kwargs: Any) -> FetchResult[T]:
        """
        Реализует логику загрузки данных.

        Вызывается из ``fetch()`` после проверки инварианта ``configure()`` → ``fetch()``.

        Args:
            *args: Аргументы, специфичные для конкретного фетчера.
            **kwargs: Именованные аргументы, специфичные для конкретного фетчера.

        Returns:
            ``FetchResult`` с загруженными данными и предупреждениями.
        """

    def configure(self, ctx: PipelineContextProtocol) -> None:
        """
        Делегирует инициализацию ``_configure()``, затем выставляет ``_configured = True``.

        Args:
            ctx: Контекст пайплайна с конфигурацией и состоянием.
        """
        self._configure(ctx)
        self._configured = True

    def fetch(self, *args: Any, **kwargs: Any) -> FetchResult[T]:
        """
        Проверяет инвариант ``configure()`` → ``fetch()`` и делегирует ``_fetch()``.

        Args:
            *args: Аргументы, специфичные для конкретного фетчера.
            **kwargs: Именованные аргументы, специфичные для конкретного фетчера.

        Returns:
            ``FetchResult`` с загруженными данными и предупреждениями.

        Raises:
            AssertionError: Если ``configure()`` не был вызван до ``fetch()``.
        """
        assert self._configured is True, _NOT_CONFIGURED_MSG
        return self._fetch(*args, **kwargs)
