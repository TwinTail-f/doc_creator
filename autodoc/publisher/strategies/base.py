"""
Базовый класс стратегий публикации с Registry-паттерном и PublishReport.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Type

if TYPE_CHECKING:  # 3.8 — импорты только для аннотаций, без циклических зависимостей
    from autodoc.models.parsed_result import ParsedResult
    from autodoc.publisher.confluence.confluence_client import ConfluenceClient
    from autodoc.publisher.rendering.document_builder import DocumentBuilder

from autodoc.infrastructure.logger import logger


@dataclass
class PublishReport:
    """
    Типизированный результат выполнения стратегии публикации.

    Заменяет ``Dict[str, Any]`` — контракт проверяется статически.
    """

    success: bool
    pages_published: int
    errors: List[str] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)


class BasePublishStrategy(ABC):
    """
    Абстрактная стратегия публикации с Registry-паттерном.

    3.7 Трансформер передаётся через ``transformer_cls`` в ``__init_subclass__``
    — прямая запись в ``_transformer_map`` снаружи устранена.
    ``_transformer_map`` убран; трансформер хранится прямо в классе стратегии.

    3.8 ``__init__`` аннотирован через ``TYPE_CHECKING`` — нет ``Any``.
    """

    _registry: ClassVar[Dict[str, Type[BasePublishStrategy]]] = {}

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
        transformer_cls: Optional[type] = None,  # 3.7 трансформер прямо в объявлении
        **kwargs: Any,
    ) -> None:
        super().__init_subclass__(**kwargs)
        if strategy_type:
            BasePublishStrategy._registry[strategy_type] = cls
            # 3.7 Трансформер хранится как атрибут класса стратегии — не в _transformer_map
            if transformer_cls is not None:
                cls._transformer_cls = transformer_cls
            logger.debug(
                'BasePublishStrategy: зарегистрирована "%s" → %s',
                strategy_type, cls.__name__,
            )

    @classmethod
    def create(cls, strategy_type: str, **kwargs: Any) -> BasePublishStrategy:
        """
        Создаёт экземпляр стратегии по типу через Registry.

        3.7 Трансформер создаётся из ``_transformer_cls`` атрибута класса
        — без отдельного ``_transformer_map``.

        Args:
            strategy_type: Ключ стратегии.
            **kwargs: Аргументы конструктора.

        Raises:
            ValueError: Если ``strategy_type`` не зарегистрирован.
        """
        if strategy_type not in cls._registry:
            raise ValueError(
                'Неизвестная стратегия "%s". Доступные: %s'
                % (strategy_type, sorted(cls._registry))
            )

        strategy_cls = cls._registry[strategy_type]

        # 3.7 Трансформер берётся из атрибута класса, а не из _transformer_map
        transformer_cls = getattr(strategy_cls, '_transformer_cls', None)
        if transformer_cls is not None and 'transformer' not in kwargs:
            kwargs['transformer'] = transformer_cls(
                include_passport_links=kwargs.pop('include_passport_links', True),
                passport_page_pattern=kwargs.pop('passport_page_pattern', None),
            )

        logger.debug(
            'BasePublishStrategy.create: %s для типа "%s"',
            strategy_cls.__name__, strategy_type,
        )
        return strategy_cls(**kwargs)

    @classmethod
    def available_strategies(cls) -> list:
        """Возвращает список зарегистрированных типов стратегий."""
        return sorted(cls._registry)

    @abstractmethod
    def execute(self) -> PublishReport:
        """
        Выполняет стратегию публикации.

        Returns:
            ``PublishReport`` с результатами.
        """
