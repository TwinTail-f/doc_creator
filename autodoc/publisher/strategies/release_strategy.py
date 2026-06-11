"""Стратегия публикации релизной документации на одной странице Confluence."""

from typing import Any

from pathlib import Path

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.confluence_client_protocol import ConfluenceClientProtocol
from autodoc.publisher.rendering.document_builder_protocol import DocumentBuilderProtocol
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.strategies.single_page_strategy import SinglePagePublishStrategy
from autodoc.publisher.strategies.models.publish_report import PublishReport
from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

_DEFAULT_TEMPLATE: str = "release_doc.jinja2"


class ReleasePageStrategy(SinglePagePublishStrategy, strategy_type="release"):
    """
    Публикует документацию релиза (вид от компонентов) на одной странице Confluence.

    Опционально вставляет ссылки на индивидуальные паспорта компонентов,
    если файл ``passport_pages.json`` был создан предшествующим запуском
    ``PassportsStrategy``.
    """

    def __init__(
        self,
        confluence_client: ConfluenceClientProtocol,
        document_builder: DocumentBuilderProtocol,
        parsed_data: ParsedResult,
        space: str,
        page_title: str,
        converter: BaseDataConverter | None = None,
        template_name: str = _DEFAULT_TEMPLATE,
        parent_id: str | None = None,
        include_passport_links: bool = True,
        data_dir: Path | None = None,
    ) -> None:
        if not space:
            raise ValueError("space не может быть пустым")
        if not page_title:
            raise ValueError("page_title не может быть пустым")

        super().__init__(
            confluence_client=confluence_client,
            document_builder=document_builder,
            parsed_data=parsed_data,
            space=space,
            page_title=page_title,
            template_name=template_name,
            parent_id=parent_id,
            include_passport_links=include_passport_links,
            data_dir=data_dir,
        )
        self._converter: BaseDataConverter = converter or FullReleaseConverter(
            include_passport_links=include_passport_links,
        )

    @staticmethod
    def _make_converter(kwargs: dict[str, Any]) -> BaseDataConverter:
        return FullReleaseConverter(
            include_passport_links=kwargs.get("include_passport_links", True),
            passport_page_pattern=kwargs.pop("passport_page_pattern", None),
        )

    def _build_view_model(self) -> dict[str, Any]:
        """Трансформирует данные парсера в view-model для шаблона релиза."""
        return self._converter.transform(self._data)

    def _inject_passport_links(
        self,
        view_model: dict[str, Any],
        passport_pages: dict[str, Any],
    ) -> None:
        """Вставляет ссылки на паспорта в release view-model на месте."""
        PassportPageRegistry.inject_links(view_model, passport_pages)
