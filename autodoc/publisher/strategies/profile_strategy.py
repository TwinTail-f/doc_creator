"""Стратегия публикации профиль-центричной документации в Confluence."""

from typing import Any

from pathlib import Path

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.confluence_client_protocol import IConfluenceClient
from autodoc.publisher.rendering.document_builder_protocol import IDocumentBuilder
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.strategies.single_page_strategy import SinglePagePublishStrategy
from autodoc.publisher.strategies.models.publish_report import PublishReport
from autodoc.publisher.converters.profile_converter import ProfileCentricConverter

_DEFAULT_TEMPLATE: str = "profile_centric.jinja2"


class ProfileCentricStrategy(
    SinglePagePublishStrategy, strategy_type="profile_centric"
):
    """
    Публикует профиль-центричную документацию релиза на одной странице Confluence.

    Реорганизует данные по схеме Профиль → Канал → Компонент.
    """

    def __init__(
        self,
        confluence_client: IConfluenceClient,
        document_builder: IDocumentBuilder,
        parsed_data: ParsedResult,
        space: str,
        page_title: str,
        converter: ProfileCentricConverter | None = None,
        template_name: str = _DEFAULT_TEMPLATE,
        parent_id: str | None = None,
        include_passport_links: bool = True,
        passport_page_pattern: str | None = None,
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
        self._converter: ProfileCentricConverter = converter or (
            ProfileCentricConverter(
                include_passport_links=include_passport_links,
                passport_page_pattern=passport_page_pattern,
            )
        )

    @staticmethod
    def _make_converter(kwargs: dict[str, Any]) -> ProfileCentricConverter:
        return ProfileCentricConverter(
            include_passport_links=kwargs.get("include_passport_links", True),
            passport_page_pattern=kwargs.get("passport_page_pattern", None),
        )

    def _build_view_model(self) -> dict[str, Any]:
        """Трансформирует данные парсера в view-model для профиль-центричного шаблона."""
        return self._converter.transform(self._data)

    def _inject_passport_links(
        self,
        view_model: dict[str, Any],
        passport_pages: dict[str, Any],
    ) -> None:
        """Вставляет ссылки на паспорта в profile view-model на месте."""
        PassportPageRegistry.inject_links_for_profiles(view_model, passport_pages)
