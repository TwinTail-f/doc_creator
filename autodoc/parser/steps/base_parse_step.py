"""
Базовые типы шагов пайплайна парсера: контекст и абстрактный шаг.

Абстракции фетчеров (``FetchResult``, ``IFetcher``, ``BaseTFSFetcher``) намеренно
вынесены в ``autodoc.parser.fetchers.base`` — они относятся к слою загрузки данных,
а не к слою шагов.
"""

from abc import ABC, abstractmethod
from typing import Any

from autodoc.parser.pipeline.context_protocol import IPipelineContext


class BaseParseStep(ABC):
    """
    Базовый шаг пайплайна парсера.

    ``name`` объявлен как class-атрибут. ``__init_subclass__`` проверяет его
    наличие при объявлении класса — ошибка конфигурации проявляется до запуска
    программы, а не во время выполнения пайплайна.
    """

    name: str = ""
    is_critical: bool = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            raise TypeError(f"{cls.__name__} должен определить атрибут name")

    @abstractmethod
    def execute(self, ctx: IPipelineContext) -> None:
        """
        Выполняет логику шага.

        Args:
            ctx: Контекст пайплайна. Шаг читает нужные данные и записывает результат.
        """
