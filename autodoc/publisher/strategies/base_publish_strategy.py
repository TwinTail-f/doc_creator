"""Abstract base class for publish strategies with Registry pattern."""

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, ClassVar

from autodoc.models.parsed_result import ParsedResult

from autodoc.publisher.clients.confluence_client_protocol import IConfluenceClient
from autodoc.publisher.rendering.document_builder_protocol import IDocumentBuilder
from autodoc.publisher.strategies.models.publish_report import PublishReport

from autodoc.common.logger import logger


class BasePublishStrategy(ABC):
    """
    Абстрактная стратегия публикации с Registry-паттерном.

    Подклассы регистрируются автоматически через ``__init_subclass__``
    при объявлении ``strategy_type``. Фабричный метод ``create()`` создаёт
    нужный подкласс по строковому ключу.

    Четыре базовых атрибута — ``_client``, ``_builder``, ``_data``,
    ``_space`` — инициализируются в ``__init__`` и доступны всем подклассам.
    Подклассы не должны их переопределять.

    **Контракт построения конвертера.**
    Стратегия, которой нужен конвертер, создаваемый фабрикой, объявляет
    classmethod ``_make_converter(cls, kwargs: dict)``. Метод получает
    прямую ссылку на ``kwargs`` и может:

    - ``pop()`` ключи, которые нужны только трансформеру и не принимаются
      ``__init__`` стратегии;
    - ``get()`` ключи, которые должны попасть и в трансформер, и в стратегию
      (они остаются в ``kwargs``).

    Стратегии без ``_make_converter`` получают ``kwargs`` без изменений.
    """

    _registry: ClassVar[dict[str, type["BasePublishStrategy"]]] = {}

    def __init__(
        self,
        confluence_client: IConfluenceClient,
        document_builder: IDocumentBuilder,
        parsed_data: ParsedResult,
        space: str,
    ) -> None:
        """
        Инициализирует общие зависимости всех стратегий.

        Args:
            confluence_client: Реализация ``IConfluenceClient`` (обычно ``ConfluenceClient``).
            document_builder: Реализация ``IDocumentBuilder`` (обычно ``DocumentBuilder``).
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

        Если стратегия объявляет classmethod ```_make_converter```,
        и ``converter`` ещё не передан в ``kwargs``, вызывает его для
        построения трансформера. Метод получает прямую ссылку на ``kwargs``
        и может удалять из него ключи, которые не нужны конструктору стратегии.

        Для стратегий без ``_make_converter`` ``kwargs`` передаётся
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

        make_converter = getattr(strategy_cls, "_make_converter", None)
        if make_converter is not None and "converter" not in kwargs:
            kwargs["converter"] = make_converter(kwargs)

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
        Инкапсулирует общий поток публикации одной страницы для стратегий
        release и profile-centric.

        Args:
            page_title: Заголовок страницы Confluence для создания или обновления.
            template_name: Имя файла Jinja2-шаблона.
            transform_fn: Callable без аргументов, возвращающий словарь view-model.
            parent_id: ID родительской страницы Confluence (пустая строка = без родителя).
            inject_links: Опциональный callable, мутирующий view-model на месте.

        Returns:
            ``PublishReport`` с результатом попытки публикации.
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

            html_body = self._minify_html(
                self._builder.build(template_name, view_model)
            )
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

    @staticmethod
    def _minify_html(html: str) -> str:
        """
        Минимизирует HTML-разметку перед публикацией в Confluence.

        Args:
            html: Исходный HTML-текст шаблона.

        Returns:
            Минимизированный HTML без лишних пробелов и комментариев.
        """
        html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
        html = re.sub(r">\s+<", "><", html)
        html = re.sub(r"\s{2,}", " ", html)
        return html.strip()

    @abstractmethod
    def execute(self) -> PublishReport:
        """
        Выполняет стратегию публикации.

        Returns:
            ``PublishReport`` с результатами выполнения.
        """
