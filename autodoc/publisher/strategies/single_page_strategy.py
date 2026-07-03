"""Промежуточный базовый класс для стратегий, публикующих одну страницу Confluence."""

from abc import abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from autodoc.common.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.confluence_client import ConfluenceClient
from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.strategies.base_publish_strategy import BasePublishStrategy
from autodoc.publisher.strategies.models.publish_report import PublishReport


class SinglePagePublishStrategy(BasePublishStrategy):
    """
    Промежуточный базовый класс для стратегий, публикующих одну страницу Confluence.

    Управляет общими атрибутами и шаблонным потоком выполнения
    (inject → publish), который разделяют ReleasePageStrategy
    и ProfileCentricStrategy.
    """

    def __init__(
        self,
        *,
        confluence_client: ConfluenceClient,
        document_builder: DocumentBuilder,
        parsed_data: ParsedResult,
        space: str,
        page_title: str,
        converter: BaseDataConverter,
        link_injector: Callable[[dict[str, Any], dict[str, Any]], None],
        template_name: str,
        parent_id: str | None = None,
        include_passport_links: bool = True,
        data_dir: Path | None = None,
    ) -> None:
        """
        Инициализирует общие атрибуты стратегий публикации одной страницы.

        Args:
            confluence_client: Клиент Confluence, используемый для чтения и публикации страниц.
            document_builder: Строитель документов, используемый для рендеринга Jinja2-шаблонов.
            parsed_data: Данные парсера.
            space: Ключ Space в Confluence.
            page_title: Заголовок публикуемой страницы Confluence.
            converter: Конвертер данных парсера в view-model для шаблона.
            link_injector: Callable, вставляющий ссылки на паспорта в view-model.
            template_name: Имя Jinja2-шаблона.
            parent_id: ID родительской страницы. ``None`` означает отсутствие родителя.
            include_passport_links: Вставлять ли ссылки на паспорта компонентов.
            data_dir: Директория для ``passport_pages.json``.

        Raises:
            ValueError: Если ``page_title`` пустой.
        """
        super().__init__(confluence_client, document_builder, parsed_data, space)
        if not page_title:
            raise ValueError("page_title не может быть пустым")
        self._page_title: str = page_title
        self._template_name: str = template_name
        self._converter: BaseDataConverter = converter
        self._link_injector: Callable[[dict[str, Any], dict[str, Any]], None] = link_injector
        self._parent_id: str | None = parent_id
        self._include_passport_links: bool = include_passport_links
        self._passport_page_registry: PassportPageRegistry = PassportPageRegistry(data_dir)

    @staticmethod
    @abstractmethod
    def _make_converter(kwargs: dict[str, Any]) -> BaseDataConverter:
        """
        Создаёт конвертер данных из аргументов конструктора.

        Args:
            kwargs: Словарь с параметрами для инициализации конвертера.

        Returns:
            Готовый экземпляр ``BaseDataConverter``.
        """

    def _build_view_model(self) -> dict[str, Any]:
        """
        Трансформирует данные парсера в view-model для шаблона.

        Returns:
            Словарь view-model, готовый для рендеринга шаблона.
        """
        return self._converter.transform(self._data)

    def _inject_passport_links(
        self, view_model: dict[str, Any], passport_pages: dict[str, Any]
    ) -> None:
        """
        Вставляет ссылки на паспорта в view-model на месте.

        Args:
            view_model: Словарь view-model для мутации.
            passport_pages: Карта страниц паспортов из реестра.
        """
        self._link_injector(view_model, passport_pages)

    def execute(self) -> PublishReport:
        """
        Трансформирует данные, опционально вставляет ссылки на паспорта,
        рендерит и публикует одну страницу.

        Returns:
            ``PublishReport`` с результатом публикации одной страницы.
        """
        logger.info(f"Публикация {self._page_title}")

        inject_fn = None
        if self._include_passport_links:
            passport_pages = self._passport_page_registry.load()

            def inject_fn(vm: dict[str, Any]) -> None:
                self._inject_passport_links(vm, passport_pages)

        return self._publish_single_page(
            page_title=self._page_title,
            template_name=self._template_name,
            transform_fn=self._build_view_model,
            parent_id=self._parent_id or "",
            inject_links=inject_fn,
        )
