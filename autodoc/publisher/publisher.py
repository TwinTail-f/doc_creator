"""
Точка входа паблишера документации компонентов платформы.
"""
from pathlib import Path
from typing import Any, Optional

from autodoc.config.schemas import ConfluenceConfigSchema
from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.confluence.confluence_client import ConfluenceClient
from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.strategies.base import BasePublishStrategy, PublishReport

# Импорт стратегий активирует их регистрацию в Registry
import autodoc.publisher.strategies.release_strategy    # noqa: F401
import autodoc.publisher.strategies.passports_strategy  # noqa: F401


class DocumentPublisher:
    """
    Верхний уровень бизнес-логики паблишера.

    Создаёт ``ConfluenceClient`` и ``DocumentBuilder``, выбирает стратегию
    через Registry и запускает публикацию.
    """

    def __init__(
        self,
        confluence_config: ConfluenceConfigSchema,
        templates_dir: Path,
        data_dir: Optional[Path] = None,  # 3.9 для передачи стратегиям
    ) -> None:
        """
        Args:
            confluence_config: Валидированная конфигурация Confluence.
            templates_dir: Путь к директории с Jinja2-шаблонами.
            data_dir: Рабочая директория. Используется для чтения/записи
                ``passport_pages.json``. По умолчанию ``Path('data')``.
        """
        self._config = confluence_config
        self._client = ConfluenceClient(confluence_config)
        self._builder = DocumentBuilder(templates_dir)
        self._data_dir = data_dir or Path('data')
        logger.info('DocumentPublisher инициализирован')

    def publish(
        self,
        strategy_type: str,
        parsed_data: ParsedResult,
        **kwargs: Any,
    ) -> PublishReport:
        """
        Публикует документацию согласно выбранной стратегии.

        Args:
            strategy_type: Тип стратегии.
            parsed_data: Данные парсера.
            **kwargs: Аргументы, специфичные для стратегии.

        Returns:
            ``PublishReport`` с результатами.
        """
        logger.info('DocumentPublisher: публикация стратегии "%s"', strategy_type)

        # 3.9 data_dir передаётся стратегиям
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
        release_parent_id: Optional[str] = None,
        passport_template_name: str = 'component_passport.jinja2',
        include_passport_links: bool = True,
    ) -> PublishReport:
        """
        Публикует паспорта и итоговую страницу релиза.

        Returns:
            Агрегированный ``PublishReport``.
        """
        logger.info('DocumentPublisher: publish_all — паспорта + релиз')

        passports_report = self.publish(
            strategy_type='passports',
            parsed_data=parsed_data,
            root_page_id=passports_root_page_id,
            template_name=passport_template_name,
        )

        release_report = self.publish(
            strategy_type='full_release',
            parsed_data=parsed_data,
            page_title=release_page_title,
            template_name=release_template_name,
            parent_id=release_parent_id,
            include_passport_links=include_passport_links,
        )

        return PublishReport(
            success=passports_report.success and release_report.success,
            pages_published=passports_report.pages_published + release_report.pages_published,
            errors=passports_report.errors + release_report.errors,
            details=passports_report.details + release_report.details,
        )
