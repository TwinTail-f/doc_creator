from __future__ import annotations

"""
Базовый класс стратегий публикации с Registry-паттерном и PublishReport.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, ClassVar

if TYPE_CHECKING:
    from autodoc.models.parsed_result import ParsedResult
    from autodoc.publisher.clients.confluence_client import ConfluenceClient
    from autodoc.publisher.rendering.document_builder import DocumentBuilder

from autodoc.infrastructure.logger import logger


@dataclass
class PublishReport:
    """
    Типизированный результат выполнения стратегии публикации.

    Заменяет ``dict[str, Any]`` — контракт проверяется статически.

    Attributes:
        success: ``True`` если публикация завершилась без ошибок.
        pages_published: Количество успешно опубликованных страниц.
        pages_failed: Количество страниц, публикация которых завершилась ошибкой.
        errors: Список текстовых сообщений об ошибках.
        failed_pages: Структурированная информация о каждой неудавшейся странице
                      в формате ``{'page_title': str, 'reason': str}``.
        details: Подробные записи об успешно опубликованных страницах.
    """

    success: bool
    pages_published: int
    pages_failed: int = 0
    errors: list[str] = field(default_factory=list)
    failed_pages: list[dict[str, Any]] = field(default_factory=list)
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
        strategy_type: str = "",
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
            logger.debug(f"Зарегистрирована {strategy_type} → {cls.__name__}")

    @classmethod
    def create(cls, strategy_type: str, **kwargs: Any) -> "BasePublishStrategy":
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
                f"Неизвестная стратегия {strategy_type}. Доступные: {sorted(cls._registry)}"
            )

        strategy_cls = cls._registry[strategy_type]

        make_transformer = getattr(strategy_cls, "_make_transformer", None)
        if make_transformer is not None and "transformer" not in kwargs:
            kwargs["transformer"] = make_transformer(kwargs)

        logger.debug(f"Создаём {strategy_cls.__name__} для типа {strategy_type}")
        return strategy_cls(**kwargs)

    @classmethod
    def available_strategies(cls) -> list[str]:
        """Возвращает отсортированный список зарегистрированных типов стратегий."""
        return sorted(cls._registry)

    def _publish_single_page(
        self,
        page_title: str,
        template_name: str,
        transform_fn: Callable[[], dict[str, Any]],
        parent_id: str,
        inject_links: Callable[[dict[str, Any]], None] | None = None,
    ) -> PublishReport:
        """
        Encapsulates the common single-page publish flow used by release and
        profile-centric strategies.

        Steps:
        1. Call ``transform_fn`` to produce the view-model.
        2. Validate that the view-model is non-empty.
        3. Inject the Space key into the view-model.
        4. Optionally call ``inject_links`` to insert passport URLs.
        5. Render the Jinja2 template.
        6. Publish the page via ``ConfluenceClient``.
        7. Return a ``PublishReport``.

        Any exception raised during steps 1–6 is caught, logged, and returned
        as a failed ``PublishReport``.

        Args:
            page_title: Title of the Confluence page to create or update.
            template_name: Name of the Jinja2 template file.
            transform_fn: Zero-argument callable that produces the view-model
                          dict (typically ``lambda: transformer.transform(data)``).
                          Called inside the try block so transformer errors are
                          captured in the returned ``PublishReport``.
            parent_id: ID of the parent Confluence page (empty string = no parent).
            inject_links: Optional callable that mutates the view-model in-place
                          to add passport page links. Receives the view-model dict.

        Returns:
            ``PublishReport`` reflecting the outcome of the publish attempt.
        """
        errors: list[str] = []
        details: list[dict[str, Any]] = []

        try:
            view_model = transform_fn()
            if not view_model:
                raise ValueError("трансформер вернул пустой результат")

            view_model["space"] = self._space

            if inject_links is not None:
                inject_links(view_model)

            html_body = self._builder.build(template_name, view_model)
            result = self._client.publish_page(
                space=self._space,
                parent_id=parent_id,
                title=page_title,
                body_html=html_body,
            )

            details.append(
                {
                    "page_title": page_title,
                    "page_id": result["id"],
                    "version": result["version"],
                    "status": result["status"],
                    "template": template_name,
                }
            )
            logger.info(f"{page_title} {result['status']} (ID: {result['id']})")
            return PublishReport(success=True, pages_published=1, details=details)

        # Broad catch is intentional: any error (network, rendering, API) during
        # single-page publication must be isolated and reported without crashing
        # the entire publish workflow.
        except Exception as e:
            reason = str(e)
            errors.append(reason)
            logger.error(f"Ошибка публикации {page_title}: {reason}")
            return PublishReport(
                success=False,
                pages_published=0,
                pages_failed=1,
                errors=errors,
                failed_pages=[{"page_title": page_title, "reason": reason}],
                details=details,
            )

    @abstractmethod
    def execute(self) -> PublishReport:
        """
        Выполняет стратегию публикации.

        Returns:
            ``PublishReport`` с результатами выполнения.
        """
