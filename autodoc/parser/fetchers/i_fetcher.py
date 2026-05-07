"""
Интерфейс двухфазового фетчера.
"""

from abc import ABC, abstractmethod
from typing import Any

from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.pipeline.context_protocol import IPipelineContext


class IFetcher[T](ABC):
    """
    Интерфейс двухфазового фетчера: ``configure()`` → ``fetch()``.

    Разделение на две фазы позволяет внедрять зависимости через ``configure(ctx)``
    без прямой передачи контекста в ``fetch()``, что упрощает тестирование.
    """

    @abstractmethod
    def configure(self, ctx: IPipelineContext) -> None:
        """
        Инициализирует фетчер данными из контекста пайплайна.

        Должен вызываться перед ``fetch()``. Реализация сохраняет нужные
        поля из ``ctx.config``.

        Args:
            ctx: Контекст пайплайна с конфигурацией и состоянием.
        """

    @abstractmethod
    def fetch(self, *args: Any, **kwargs: Any) -> FetchResult[T]:
        """
        Загружает данные. Должен вызываться после ``configure()``.

        Args:
            *args: Аргументы, специфичные для конкретного фетчера.
            **kwargs: Именованные аргументы, специфичные для конкретного фетчера.

        Returns:
            ``FetchResult`` с загруженными данными и предупреждениями.
        """
