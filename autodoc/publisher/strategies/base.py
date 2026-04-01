from __future__ import annotations

"""
Базовый класс стратегий публикации с Registry-паттерном и PublishReport.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from autodoc.models.parsed_result import ParsedResult
    from autodoc.publisher.confluence.confluence_client import ConfluenceClient
    from autodoc.publisher.rendering.document_builder import DocumentBuilder

from autodoc.infrastructure.logger import logger


@dataclass
class PublishReport:
    """
    Типизированный результат выполнения стратегии публикации.

    Заменяет ``dict[str, Any]`` — контракт проверяется статически.
    """

    success: bool
    pages_published: int
    errors: list[str] = field(default_factory=list)
    details: list[dict[str, Any]] = field(default_factory=list)


class BasePublishStrategy(ABC):
    """
    Абстрактная стратегия публикации с Registry-паттерном.

    Подклассы регистрируются автоматически через ``__init_subclass__``
    при объявлении ``strategy_type``. Фабричный метод ``create()`` создаёт
    нужный подкласс по строковому ключу.

    Четыре базовых атрибута — ``_client``, ``_builder``, ``_data``,
    ``_space`` — инициализируются в ``__init__`` и доступны всем подклассам.
    Подклассы не должны их переопределять.

    **Контракт построения трансформера.**
    Стратегия, которой нужен трансформер, создаваемый фабрикой, объявляет
    classmethod ``_make_transformer(cls, kwargs: dict)``. Метод получает
    прямую ссылку на ``kwargs`` и может:

    - ``pop()`` ключи, которые нужны только трансформеру и не принимаются
      ``__init__`` стратегии;
    - ``get()`` ключи, которые должны попасть и в трансформер, и в стратегию
      (они остаются в ``kwargs``).

    Стратегии без ``_make_transformer`` получают ``kwargs`` без изменений.
    """

    _registry: ClassVar[dict[str, type[BasePublishStrategy]]] = {}

    def __init__(
        self,
        confluence_client: ConfluenceClient,
        document_builder: DocumentBuilder,
        parsed_data: ParsedResult,
        space: str,
    ) -> None:
        """
        Инициализирует общие зависимости всех стратегий.

        Args:
            confluence_client: Клиент Confluence API.
            document_builder: Рендерер Jinja2-шаблонов.
            parsed_data: Данные парсера (ParsedResult).
            space: Ключ Space в Confluence.
        """
        self._client = confluence_client
        self._builder = document_builder
        self._data = parsed_data
        self._space = space

    def __init_subclass__(
        cls,
        strategy_type: str = '',
        **kwargs: Any,
    ) -> None:
        """
        Регистрирует подкласс в реестре стратегий при объявлении класса.

        Args:
            strategy_type: Строковый ключ стратегии (например ``'release'``).
                           Если не задан — класс в реестр не добавляется.
            **kwargs: Передаётся в ``super().__init_subclass__``.
        """
        super().__init_subclass__(**kwargs)
        if strategy_type:
            BasePublishStrategy._registry[strategy_type] = cls
            logger.debug(
                'BasePublishStrategy: зарегистрирована "%s" → %s',
                strategy_type, cls.__name__,
            )

    @classmethod
    def create(cls, strategy_type: str, **kwargs: Any) -> 'BasePublishStrategy':
        """
        Создаёт экземпляр стратегии по типу через Registry.

        Если стратегия объявляет classmethod ``_make_transformer(cls, kwargs)``,
        и ``transformer`` ещё не передан в ``kwargs``, вызывает его для
        построения трансформера. Метод получает прямую ссылку на ``kwargs``
        и может удалять из него ключи, которые не нужны конструктору стратегии.

        Для стратегий без ``_make_transformer`` ``kwargs`` передаётся
        в конструктор без изменений.

        Args:
            strategy_type: Ключ стратегии из реестра.
            **kwargs: Аргументы конструктора стратегии.

        Returns:
            Готовый экземпляр стратегии.

        Raises:
            ValueError: Если ``strategy_type`` не зарегистрирован.
        """
        if strategy_type not in cls._registry:
            raise ValueError(
                'Неизвестная стратегия "%s". Доступные: %s'
                % (strategy_type, sorted(cls._registry))
            )

        strategy_cls = cls._registry[strategy_type]

        make_transformer = getattr(strategy_cls, '_make_transformer', None)
        if make_transformer is not None and 'transformer' not in kwargs:
            kwargs['transformer'] = make_transformer(kwargs)

        logger.debug(
            'BasePublishStrategy.create: %s для типа "%s"',
            strategy_cls.__name__, strategy_type,
        )
        return strategy_cls(**kwargs)

    @classmethod
    def available_strategies(cls) -> list[str]:
        """Возвращает отсортированный список зарегистрированных типов стратегий."""
        return sorted(cls._registry)

    @abstractmethod
    def execute(self) -> PublishReport:
        """
        Выполняет стратегию публикации.

        Returns:
            ``PublishReport`` с результатами выполнения.
        """
