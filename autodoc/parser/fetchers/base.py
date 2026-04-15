"""
Базовые абстракции для фетчеров пайплайна парсера.

Содержит:
- ``FetchResult`` — обёртка результата с предупреждениями;
- ``IFetcher`` — интерфейс двухфазового фетчера;
- ``BaseTFSFetcher`` — базовый класс с доступом к ``TFSClient``-синглтону.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from autodoc.parser.clients.tfs_client import TFSClient

if TYPE_CHECKING:
    # PipelineContext живёт в steps/base.py, который сам импортирует fetchers/base —
    # прямой импорт здесь образует цикл, поэтому используем TYPE_CHECKING.
    from autodoc.parser.steps.base import PipelineContext

# Параметр типа для обобщённых классов FetchResult и IFetcher/BaseTFSFetcher:
# конкретизируется в каждом фетчере (например, _T = list[Component]).
_T = TypeVar("_T")


@dataclass
class FetchResult(Generic[_T]):
    """
    Тонкая обёртка над результатом fetch — значение и список предупреждений.

    Позволяет шагам пайплайна получить дополнительный контекст о нештатных
    ситуациях, не бросая исключений.

    Attributes:
        value: Основной результат операции загрузки.
        warnings: Накопленный список предупреждений, возникших в ходе загрузки.
    """

    value: _T
    warnings: list[str] = field(default_factory=list)


class IFetcher(ABC, Generic[_T]):
    """
    Интерфейс двухфазового фетчера: ``configure()`` → ``fetch()``.

    Разделение на две фазы позволяет внедрять зависимости через ``configure(ctx)``
    без прямой передачи контекста в ``fetch()``, что упрощает тестирование.
    """

    @abstractmethod
    def configure(self, ctx: "PipelineContext") -> None:
        """
        Инициализирует фетчер данными из контекста пайплайна.

        Должен вызываться перед ``fetch()``. Реализация сохраняет нужные
        поля из ``ctx.config``.

        Args:
            ctx: Контекст пайплайна с конфигурацией и состоянием.
        """

    @abstractmethod
    def fetch(self, *args: Any, **kwargs: Any) -> "FetchResult[_T]":
        """
        Загружает данные. Должен вызываться после ``configure()``.

        Args:
            *args: Аргументы, специфичные для конкретного фетчера.
            **kwargs: Именованные аргументы, специфичные для конкретного фетчера.

        Returns:
            ``FetchResult`` с загруженными данными и предупреждениями.
        """


class BaseTFSFetcher(IFetcher[_T]):
    """
    Базовый фетчер с отложенным доступом к ``TFSClient``-синглтону.

    Весь доступ к конфигурации и синглтону — в ``configure(ctx)``.
    """

    def __init__(self) -> None:
        """Инициализирует фетчер; ``_tfs`` заполняется в методе ``configure()``."""
        self._tfs: TFSClient | None = None

    @abstractmethod
    def configure(self, ctx: "PipelineContext") -> None: ...
