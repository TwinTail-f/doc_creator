"""Точка входа паблишера документации компонентов платформы."""

from pathlib import Path
from typing import Any

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.common.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.confluence_client import ConfluenceClient
from autodoc.publisher.clients.confluence_client_protocol import IConfluenceClient
from autodoc.publisher.rendering.document_builder_protocol import IDocumentBuilder
from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.strategies.base_publish_strategy import BasePublishStrategy
from autodoc.publisher.strategies.models.publish_report import PublishReport
from autodoc.publisher.strategies import (
    passports_strategy,
    profile_strategy,
    release_strategy,
)

_DEFAULT_DATA_DIR: Path = Path("data")
_DEFAULT_PASSPORT_TEMPLATE: str = "component_passport.jinja2"


class DocumentPublisher:
    """
    Верхний уровень бизнес-логики паблишера.

    Создаёт ``ConfluenceClient`` и ``DocumentBuilder``, выбирает стратегию
    через Registry и запускает публикацию. Все стратегии получают одни и те же
    инфраструктурные зависимости — клиент, рендерер и директорию данных.
    Параметры пакетной публикации читаются из конфигурации и автоматически
    передаются стратегии ``passports``.

    Attributes:
        _client: ``IConfluenceClient`` — клиент Confluence API.
        _builder: ``IDocumentBuilder`` — рендерер Jinja2-шаблонов.
    """

    def __init__(
        self,
        confluence_config: ConfluenceConfigSchema,
        rendering_dir: Path,
        data_dir: Path | None = None,
    ) -> None:
        """
        Args:
            confluence_config: Валидированная конфигурация Confluence.
            rendering_dir: Путь к директории ``rendering/`` (содержит
                ``templates/``, ``styles/``, ``macros/``).
            data_dir: Рабочая директория для ``passport_pages.json``.
                      По умолчанию ``Path('data')``.
        """
        self._config: ConfluenceConfigSchema = confluence_config
        self._client: IConfluenceClient = ConfluenceClient(confluence_config)
        self._builder: IDocumentBuilder = DocumentBuilder(rendering_dir)
        self._data_dir: Path = data_dir if data_dir is not None else _DEFAULT_DATA_DIR
        logger.info("Инициализирован")

    def publish(
        self,
        strategy_type: str,
        parsed_data: ParsedResult,
        **kwargs: Any,
    ) -> PublishReport:
        """
        Публикует документацию согласно выбранной стратегии.

        Создаёт стратегию через ``BasePublishStrategy.create()``, передавая
        инфраструктурные зависимости и ``data_dir``. Дополнительные аргументы,
        специфичные для конкретной стратегии, передаются через ``kwargs``.

        Args:
            strategy_type: Тип стратегии (``'passports'``, ``'release'``,
                           ``'profile_centric'``).
            parsed_data: Данные парсера.
            **kwargs: Аргументы конструктора стратегии.

        Returns:
            ``PublishReport`` с результатами публикации.
        """
        logger.info(f"Публикация стратегии {strategy_type}")
        strategy = BasePublishStrategy.create(
            strategy_type,
            confluence_client=self._client,
            document_builder=self._builder,
            parsed_data=parsed_data,
            space=self._config.space,
            data_dir=self._data_dir,
            **kwargs,
        )
        return strategy.execute()

    def publish_all(
        self,
        parsed_data: ParsedResult,
        passports_root_page_id: str,
        release_page_title: str,
        release_template_name: str,
        release_parent_id: str | None = None,
        passport_template_name: str = _DEFAULT_PASSPORT_TEMPLATE,
        include_passport_links: bool = True,
    ) -> PublishReport:
        """
        Публикует паспорта и итоговую страницу релиза за один вызов.

        Порядок выполнения намеренно фиксирован: сначала паспорта (записывают
        ``passport_pages.json``), затем релиз (читает этот файл для вставки
        ссылок). Это гарантирует актуальность ссылок на паспорта.

        Параметры пакетной публикации (``publish_batch_size`` и
        ``publish_batch_delay_seconds``) берутся из конфигурации Confluence
        и автоматически передаются стратегии ``passports``.

        Args:
            parsed_data: Данные парсера.
            passports_root_page_id: ID корневой страницы иерархии паспортов.
            release_page_title: Заголовок итоговой страницы релиза.
            release_template_name: Имя Jinja2-шаблона для страницы релиза.
            release_parent_id: ID родителя страницы релиза. Если ``None`` —
                               без родителя.
            passport_template_name: Имя Jinja2-шаблона паспортов.
                                    По умолчанию ``component_passport.jinja2``.
            include_passport_links: Если ``True``, на странице релиза будут
                                    ссылки на опубликованные паспорта.

        Returns:
            Агрегированный ``PublishReport``: поля ``success``, ``pages_published``,
            ``pages_failed``, ``errors``, ``failed_pages`` и ``details``
            объединяются из обоих отчётов.
        """
        logger.info("Публикация паспортов + релиза")

        passports_report = self.publish(
            strategy_type="passports",
            parsed_data=parsed_data,
            root_page_id=passports_root_page_id,
            template_name=passport_template_name,
            batch_size=self._config.publish_batch_size,
            batch_delay_seconds=self._config.publish_batch_delay_seconds,
            target_release_version=self._config.target_release_version,
        )

        release_report = self.publish(
            strategy_type="release",
            parsed_data=parsed_data,
            page_title=release_page_title,
            template_name=release_template_name,
            parent_id=release_parent_id,
            include_passport_links=include_passport_links,
            target_release_version=self._config.target_release_version,
        )

        return PublishReport(
            success=passports_report.success and release_report.success,
            pages_published=passports_report.pages_published
            + release_report.pages_published,
            pages_failed=passports_report.pages_failed + release_report.pages_failed,
            errors=passports_report.errors + release_report.errors,
            failed_pages=passports_report.failed_pages + release_report.failed_pages,
            details=passports_report.details + release_report.details,
        )
