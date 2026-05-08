"""Промежуточный базовый класс для стратегий, публикующих одну страницу Confluence."""

from abc import abstractmethod
from pathlib import Path
from typing import Any

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.confluence_client_protocol import IConfluenceClient
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.rendering.document_builder_protocol import IDocumentBuilder
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
        confluence_client: IConfluenceClient,
        document_builder: IDocumentBuilder,
        parsed_data: ParsedResult,
        space: str,
        page_title: str,
        template_name: str,
        parent_id: str | None = None,
        include_passport_links: bool = True,
        data_dir: Path | None = None,
    ) -> None:
        super().__init__(confluence_client, document_builder, parsed_data, space)
        self._page_title = page_title
        self._template_name = template_name
        self._parent_id = parent_id
        self._include_passport_links = include_passport_links
        self._registry = PassportPageRegistry(data_dir)

    @abstractmethod
    def _build_view_model(self) -> dict[str, Any]:
        """Трансформирует данные парсера в view-model для шаблона."""

    @abstractmethod
    def _inject_passport_links(
        self, view_model: dict[str, Any], passport_pages: dict[str, Any]
    ) -> None:
        """Вставляет ссылки на паспорта в view-model на месте."""

    def execute(self) -> PublishReport:
        """
        Трансформирует данные, опционально вставляет ссылки на паспорта,
        рендерит и публикует одну страницу.

        Returns:
            ``PublishReport`` с результатом публикации одной страницы.
        """
        from autodoc.common.logger import logger

        logger.info(f"Публикация {self._page_title}")

        inject_fn = None
        if self._include_passport_links:
            passport_pages = self._registry.load()

            def inject_fn(vm: dict[str, Any]) -> None:
                self._inject_passport_links(vm, passport_pages)

        return self._publish_single_page(
            page_title=self._page_title,
            template_name=self._template_name,
            transform_fn=self._build_view_model,
            parent_id=self._parent_id or "",
            inject_links=inject_fn,
        )
