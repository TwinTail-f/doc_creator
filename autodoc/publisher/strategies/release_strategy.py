"""Стратегия публикации релизной документации на одной странице Confluence."""

from pathlib import Path
from typing import Any

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.confluence_client import ConfluenceClient
from autodoc.publisher.passport_registry import PassportPageRegistry
from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.strategies.base import BasePublishStrategy, PublishReport
from autodoc.publisher.transformers.base_transformer import BaseDataTransformer
from autodoc.publisher.transformers.release_transformer import FullReleaseTransformer

_DEFAULT_TEMPLATE: str = "release_doc.jinja2"


class ReleasePageStrategy(BasePublishStrategy, strategy_type="release"):
    """
    Публикует документацию релиза (вид от компонентов) на одной странице Confluence.

    Опционально вставляет ссылки на индивидуальные паспорта компонентов,
    если файл ``passport_pages.json`` был создан предшествующим запуском
    ``PassportsStrategy``.

    Трансформер строится фабрикой через ``_make_transformer``. Значение
    ``include_passport_links`` попадает и в трансформер (управляет
    генерацией URL-паттернов), и в стратегию (управляет загрузкой реестра
    и инжекцией ссылок из ``passport_pages.json``).
    """

    def __init__(
        self,
        confluence_client: ConfluenceClient,
        document_builder: DocumentBuilder,
        parsed_data: ParsedResult,
        space: str,
        page_title: str,
        transformer: BaseDataTransformer | None = None,
        template_name: str = _DEFAULT_TEMPLATE,
        parent_id: str | None = None,
        include_passport_links: bool = True,
        data_dir: Path | None = None,
    ) -> None:
        """
        Args:
            confluence_client: Клиент Confluence API.
            document_builder: Рендерер Jinja2-шаблонов.
            parsed_data: Данные парсера.
            space: Ключ Space в Confluence.
            page_title: Заголовок страницы релиза.
            transformer: Экземпляр трансформера данных. Если ``None`` —
                         создаётся автоматически как ``FullReleaseTransformer``
                         с учётом ``include_passport_links``.
                         Передача готового экземпляра упрощает тестирование.
            template_name: Имя Jinja2-шаблона. По умолчанию ``release_doc.jinja2``.
            parent_id: ID родительской страницы. Если ``None`` — страница
                       создаётся без родителя.
            include_passport_links: Если ``True``, вставляет ссылки на паспорта
                                    компонентов из ``passport_pages.json``.
                                    Должно совпадать со значением, переданным
                                    в трансформер — ``_make_transformer`` это гарантирует.
            data_dir: Директория для ``passport_pages.json``. По умолчанию ``Path('data')``.

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
        self._transformer: BaseDataTransformer = transformer or FullReleaseTransformer(
            include_passport_links=include_passport_links,
        )

    @classmethod
    def _make_transformer(cls, kwargs: dict) -> BaseDataTransformer:
        """
        Строит ``FullReleaseTransformer`` из kwargs перед вызовом ``__init__``.

        ``passport_page_pattern`` извлекается (pop) — стратегия его не принимает.
        ``include_passport_links`` читается через ``.get()`` и остаётся в kwargs,
        чтобы стратегия и трансформер использовали одно и то же значение:
        трансформер контролирует генерацию URL-паттернов, стратегия —
        загрузку реестра и инжекцию ссылок из ``passport_pages.json``.

        Args:
            kwargs: Прямая ссылка на словарь аргументов из ``create()``.

        Returns:
            Готовый ``FullReleaseTransformer``.
        """
        return FullReleaseTransformer(
            include_passport_links=kwargs.get("include_passport_links", True),
            passport_page_pattern=kwargs.pop("passport_page_pattern", None),
        )

    def execute(self) -> PublishReport:
        """
        Трансформирует данные, опционально вставляет ссылки на паспорта, рендерит и публикует.

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
                PassportPageRegistry.inject_links(view_model, passport_pages)

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
