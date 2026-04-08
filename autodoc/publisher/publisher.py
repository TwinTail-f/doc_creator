"""Точка входа паблишера документации компонентов платформы."""

from pathlib import Path
from typing import Any

from autodoc.config.schemas import ConfluenceConfigSchema
from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.confluence_client import ConfluenceClient
from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.strategies.base import BasePublishStrategy, PublishReport

_DEFAULT_DATA_DIR: Path = Path("data")
_DEFAULT_PASSPORT_TEMPLATE: str = "component_passport.jinja2"


class DocumentPublisher:
    """
    Верхний уровень бизнес-логики паблишера.

    Создаёт ``ConfluenceClient`` и ``DocumentBuilder``, выбирает стратегию
    через Registry и запускает публикацию. Все стратегии получают одни и те же
    инфраструктурные зависимости — клиент, рендерер и директорию данных.
    """

    def __init__(
        self,
        confluence_config: ConfluenceConfigSchema,
        templates_dir: Path,
        data_dir: Path | None = None,
    ) -> None:
        """
        Args:
            confluence_config: Валидированная конфигурация Confluence.
            templates_dir: Путь к директории с Jinja2-шаблонами.
            data_dir: Рабочая директория для ``passport_pages.json``.
                      По умолчанию ``Path('data')``.
        """
        self._config: ConfluenceConfigSchema = confluence_config
        self._client: ConfluenceClient = ConfluenceClient(confluence_config)
        self._builder: DocumentBuilder = DocumentBuilder(templates_dir)
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
        logger.info(f"Публикация стратегии {strategy_type!r}")
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
            ``errors`` и ``details`` объединяются из обоих отчётов.
        """
        logger.info("Публикация паспортов + релиза")

        passports_report = self.publish(
            strategy_type="passports",
            parsed_data=parsed_data,
            root_page_id=passports_root_page_id,
            template_name=passport_template_name,
        )

        release_report = self.publish(
            strategy_type="release",
            parsed_data=parsed_data,
            page_title=release_page_title,
            template_name=release_template_name,
            parent_id=release_parent_id,
            include_passport_links=include_passport_links,
        )

        return PublishReport(
            success=passports_report.success and release_report.success,
            pages_published=passports_report.pages_published
            + release_report.pages_published,
            errors=passports_report.errors + release_report.errors,
            details=passports_report.details + release_report.details,
        )
