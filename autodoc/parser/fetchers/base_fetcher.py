"""
Интерфейс двухфазового фетчера.
"""

from abc import ABC, abstractmethod
from typing import Any

from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.pipeline.context_protocol import PipelineContextProtocol

_NOT_CONFIGURED_MSG: str = (
    "fetch() called before configure(). Call configure(ctx) first."
)


class FetcherBase[T](ABC):
    """
    Интерфейс двухфазового фетчера: ``configure()`` → ``fetch()``.

    Разделение на две фазы позволяет внедрять зависимости через ``configure(ctx)``
    без прямой передачи контекста в ``fetch()``, что упрощает тестирование.
    """

    def __init__(self) -> None:
        """Инициализирует фетчер; ``_configured`` выставляется в True в ``configure()``."""
        self._configured: bool = False

    @abstractmethod
    def configure(self, ctx: PipelineContextProtocol) -> None:
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

        Raises:
            RuntimeError: Если вызван до ``configure()``.
        """

    def _assert_configured(self) -> None:
        """Вспомогательный метод для подклассов: бросает ``RuntimeError``, если ``fetch()``
        вызван до ``configure()``.

        Подклассы должны вызывать его в начале своей реализации ``fetch()``,
        чтобы соблюдать контракт двухфазового взаимодействия ``configure()`` → ``fetch()``.

        Raises:
            RuntimeError: Если ``configure()`` ещё не был вызван.
        """
        if not self._configured:
            raise RuntimeError(_NOT_CONFIGURED_MSG)
