"""Стратегия публикации профиль-центричной документации в Confluence."""

from pathlib import Path
from typing import Any

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.confluence_client import ConfluenceClient
from autodoc.publisher.passport_registry import PassportPageRegistry
from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.strategies.base import BasePublishStrategy, PublishReport
from autodoc.publisher.transformers.profile_transformer import ProfileCentricTransformer

_DEFAULT_TEMPLATE: str = "profile_centric.jinja2"


class ProfileCentricStrategy(BasePublishStrategy, strategy_type="profile_centric"):
    """
    Публикует профиль-центричную документацию релиза на одной странице Confluence.

    Реорганизует данные по схеме Профиль → Канал → Компонент.
    Ссылки на паспорта компонентов инжектируются в ``execute()`` через
    ``PassportPageRegistry.inject_links_for_profiles()`` — идентично тому,
    как ``ReleasePageStrategy`` делает это для стандартного вида через
    ``PassportPageRegistry.inject_links()``.
    ``ProfileCentricTransformer`` генерирует ``passport_link`` через
    ``PassportLinkMixin._passport_link()``; реальное значение
    ``/spaces/{space}/pages/{page_id}`` подставляется после шага инжекции.
    """

    def __init__(
        self,
        confluence_client: ConfluenceClient,
        document_builder: DocumentBuilder,
        parsed_data: ParsedResult,
        space: str,
        page_title: str,
        transformer: ProfileCentricTransformer | None = None,
        template_name: str = _DEFAULT_TEMPLATE,
        parent_id: str | None = None,
        include_passport_links: bool = True,
        passport_page_pattern: str | None = None,
        data_dir: Path | None = None,
    ) -> None:
        """
        Args:
            confluence_client: Клиент Confluence API.
            document_builder: Рендерер Jinja2-шаблонов.
            parsed_data: Данные парсера.
            space: Ключ Space в Confluence.
            page_title: Заголовок страницы.
            transformer: Готовый экземпляр ``ProfileCentricTransformer``.
                         Если ``None`` — создаётся автоматически из
                         ``include_passport_links`` и ``passport_page_pattern``.
                         Передача готового экземпляра упрощает тестирование.
            template_name: Имя Jinja2-шаблона. По умолчанию ``profile_centric.jinja2``.
            parent_id: ID родительской страницы. Если ``None`` — без родителя.
            include_passport_links: Если ``True``, ссылки на паспорта
                                    инжектируются из ``passport_pages.json``
                                    после трансформации.
            passport_page_pattern: Шаблон URL паспорта для трансформера.
                                   Используется только при автоматическом
                                   создании трансформера.
            data_dir: Директория для ``passport_pages.json``.
                      По умолчанию ``Path('data')``.

        Raises:
            ValueError: Если ``space`` или ``page_title`` пустые.
        """
        if not space:
            raise ValueError("space cannot be empty")
        if not page_title:
            raise ValueError("page_title cannot be empty")

        super().__init__(confluence_client, document_builder, parsed_data, space)
        self._page_title: str = page_title
        self._template_name: str = template_name
        self._parent_id: str | None = parent_id
        self._include_passport_links: bool = include_passport_links
        self._registry: PassportPageRegistry = PassportPageRegistry(data_dir)
        self._transformer: ProfileCentricTransformer = transformer or (
            ProfileCentricTransformer(
                include_passport_links=include_passport_links,
                passport_page_pattern=passport_page_pattern,
            )
        )

    @classmethod
    def _make_transformer(cls, kwargs: dict) -> ProfileCentricTransformer:
        """
        Строит ``ProfileCentricTransformer`` из kwargs перед вызовом ``__init__``.

        Оба ключа читаются через ``.get()`` и остаются в ``kwargs``, чтобы
        стратегия и трансформер использовали одни и те же значения:
        ``include_passport_links`` управляет как генерацией ссылок в трансформере,
        так и шагом инжекции в ``execute()``;
        ``passport_page_pattern`` остаётся доступным конструктору стратегии
        для передачи трансформеру при прямом инстанцировании.

        Args:
            kwargs: Прямая ссылка на словарь аргументов из ``create()``.

        Returns:
            Готовый ``ProfileCentricTransformer``.
        """
        return ProfileCentricTransformer(
            include_passport_links=kwargs.get("include_passport_links", True),
            passport_page_pattern=kwargs.get("passport_page_pattern", None),
        )

    def execute(self) -> PublishReport:
        """
        Трансформирует данные, рендерит шаблон и публикует страницу.

        Если трансформер вернул пустой результат — публикация прерывается
        и возвращается отчёт с ошибкой. Любое другое исключение также
        перехватывается, логируется и отражается в ``PublishReport``.

        Returns:
            ``PublishReport`` с результатом публикации одной страницы.
        """
        logger.info(f"Публикация {self._page_title}")
        errors: list[str] = []
        details: list[dict[str, Any]] = []

        try:
            view_model = self._transformer.transform(self._data)
            if not view_model:
                raise ValueError("трансформер вернул пустой результат")

            view_model["space"] = self._space

            if self._include_passport_links:
                passport_pages = self._registry.load()
                PassportPageRegistry.inject_links_for_profiles(view_model, passport_pages)

            html_body = self._builder.build(self._template_name, view_model)
            result = self._client.publish_page(
                space=self._space,
                parent_id=self._parent_id or "",
                title=self._page_title,
                body_html=html_body,
            )

            details.append(
                {
                    "page_title": self._page_title,
                    "page_id": result["id"],
                    "version": result["version"],
                    "status": result["status"],
                    "template": self._template_name,
                }
            )
            logger.info(f"{self._page_title} {result['status']} (ID: {result['id']})")
            return PublishReport(success=True, pages_published=1, details=details)

        except Exception as e:
            reason = str(e)
            errors.append(reason)
            logger.error(f"Ошибка публикации {self._page_title}: {reason}")
            return PublishReport(
                success=False,
                pages_published=0,
                pages_failed=1,
                errors=errors,
                failed_pages=[{"page_title": self._page_title, "reason": reason}],
                details=details,
            )
