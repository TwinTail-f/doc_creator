"""Промежуточный базовый класс для стратегий, публикующих одну страницу Confluence."""

from abc import abstractmethod
from functools import partial
from pathlib import Path
from typing import Any, ClassVar

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
    (convert → enrich → publish), который разделяют ReleasePageStrategy,
    ProfileCentricPageStrategy, KitFixedPageStrategy и KitLatestPageStrategy.
    Обогащение ссылками на паспорта (``enrich_with_passport_links()``)
    вызывается всегда — сам конвертер решает, есть ли у него что вставлять
    (см. ``BaseDataConverter.enrich_with_passport_links``).
    """

    IS_SINGLE_PAGE: ClassVar[bool] = True

    def __init__(
        self,
        *,
        confluence_client: ConfluenceClient,
        document_builder: DocumentBuilder,
        parsed_data: ParsedResult,
        space: str,
        page_title: str,
        converter: BaseDataConverter,
        template_name: str,
        parent_id: str | None = None,
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
            converter: Конвертер данных парсера во view-model для шаблона. Сам решает
                       (через ``enrich_with_passport_links()``), нужны ли ему вообще
                       ссылки на паспорта — стратегии об этом знать не обязательно.
            template_name: Имя Jinja2-шаблона.
            parent_id: ID родительской страницы. ``None`` означает отсутствие родителя.
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
        self._parent_id: str | None = parent_id
        self._passport_page_registry: PassportPageRegistry = PassportPageRegistry(data_dir)

    @staticmethod
    @abstractmethod
    def _make_converter(include_passport_links: bool = True) -> BaseDataConverter:
        """
        Создаёт конвертер данных из аргументов конструктора.

        Args:
            include_passport_links: Включать ли ссылки на паспорта компонентов.
                Конвертеры, у которых нет такого понятия, значение игнорируют.

        Returns:
            Готовый экземпляр ``BaseDataConverter``.
        """

    def _build_view_model(self) -> dict[str, Any]:
        """
        Трансформирует данные парсера во view-model для шаблона.

        Returns:
            Словарь view-model, готовый для рендеринга шаблона.
        """
        return self._converter.convert(self._data)

    def execute(self) -> PublishReport:
        """
        Трансформирует данные, обогащает view-model ссылками на паспорта
        (если конвертер это поддерживает), рендерит и публикует одну страницу.

        Returns:
            ``PublishReport`` с результатом публикации одной страницы.
        """
        logger.info(f"Публикация {self._page_title}")

        passport_pages = (
            self._passport_page_registry.load() if self._converter.wants_passport_links else {}
        )

        return self._publish_single_page(
            page_title=self._page_title,
            template_name=self._template_name,
            transform_fn=self._build_view_model,
            parent_id=self._parent_id or "",
            inject_links=partial(
                self._converter.enrich_with_passport_links, passport_pages=passport_pages
            ),
        )
