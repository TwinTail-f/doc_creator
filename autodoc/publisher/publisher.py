"""Точка входа паблишера документации компонентов платформы."""

from pathlib import Path
from typing import Any

from autodoc.exceptions import ConfigError
from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.common.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.confluence_client import ConfluenceClient
from autodoc.publisher.clients.confluence_client_protocol import ConfluenceClientProtocol
from autodoc.publisher.rendering.document_builder_protocol import DocumentBuilderProtocol
from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.strategies.base_publish_strategy import BasePublishStrategy
from autodoc.publisher.strategies.models.publish_report import PublishReport
# Imported for side effects: each import triggers __init_subclass__ on the
# strategy class, which registers it in BasePublishStrategy._registry.
# Do NOT remove these imports even though the names are not used directly.
import autodoc.publisher.strategies.passports_strategy  # noqa: F401
import autodoc.publisher.strategies.profile_strategy    # noqa: F401
import autodoc.publisher.strategies.release_strategy    # noqa: F401

_DEFAULT_PASSPORT_TEMPLATE: str = "component_passport.jinja2"
_DEFAULT_PROFILE_TEMPLATE: str = "profile_centric.jinja2"


class DocumentPublisher:
    """
    Оркестрирует публикацию документации компонентов в Confluence.

    Принимает конфигурацию, выбирает стратегию по типу и делегирует
    создание и обновление страниц выбранной стратегии.
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
        self._client: ConfluenceClientProtocol = ConfluenceClient(confluence_config)
        self._builder: DocumentBuilderProtocol = DocumentBuilder(rendering_dir)
        self._data_dir: Path = data_dir or Path("data")
        logger.info("Инициализирован")

    def resolve_page_id(
        self,
        name: str | None,
        page_id: str | None,
        field_label: str,
        required: bool = True,
    ) -> str | None:
        """
        Разрешает ссылку на страницу Confluence в её идентификатор.

        Args:
            name: Название страницы для поиска в настроенном Space.
            page_id: Запасной ID страницы, если ``name`` не задан или пуст.
            field_label: Имя поля конфигурации для сообщений об ошибках
                         (например ``'release_docs_root_parent'``).
            required: Если ``True`` и ни ``name``, ни ``page_id`` не заданы,
                      генерирует ``ConfigError``. Если ``False`` — возвращает ``None``.

        Returns:
            Строка с ID страницы или ``None``, если ``required=False``
            и ни имя, ни ID не настроены.

        Raises:
            ConfigError: Если ``name`` задан, но страница не найдена в Confluence,
                         или если ``required=True`` и оба параметра отсутствуют.
        """
        if name:
            page = self._client.find_page(name, space=self._config.space)
            if not page:
                raise ConfigError(
                    f"Страница '{name}' не найдена в пространстве '{self._config.space}'"
                    f" (параметр конфигурации: {field_label}_name)"
                )
            return str(page["id"])
        if page_id:
            return page_id
        if required:
            raise ConfigError(
                f"Необходимо указать '{field_label}_name' или '{field_label}'"
                f" в конфигурации Confluence"
            )
        return None

    def publish(
        self,
        strategy_type: str,
        parsed_data: ParsedResult,
        **kwargs: Any,
    ) -> PublishReport:
        """
        Публикует документацию согласно выбранной стратегии.

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
        release_page_title: str,
        release_template_name: str,
        passports_root_page_id: str | None = None,
        release_parent_id: str | None = None,
        passport_template_name: str = _DEFAULT_PASSPORT_TEMPLATE,
        include_passport_links: bool = True,
        with_additional_page_profile: bool = False,
        additional_page_profile_name: str | None = None,
        profile_template_name: str = _DEFAULT_PROFILE_TEMPLATE,
    ) -> PublishReport:
        """Публикует паспорта, страницу релизной документации и опционально страницу профилей за один вызов.

        Args:
            parsed_data: Данные парсера.
            release_page_title: Заголовок страницы релизной документации.
            release_template_name: Имя Jinja2-шаблона для страницы релиза.
            passports_root_page_id: ID корневой страницы иерархии паспортов.
                                    Если не указан — берётся из конфигурации
                                    (``passports_root_parent_name`` > ``passports_root_parent_id``).
            release_parent_id: ID родительской страницы для страницы релиза.
                               Если не указан — берётся из конфигурации.
            passport_template_name: Имя Jinja2-шаблона паспортов.
            include_passport_links: Если ``True``, в страницу релиза вставляются
                                    ссылки на опубликованные паспорта.
            with_additional_page_profile: Если ``True``, после публикации страницы релиза
                                          публикуется дополнительная профильная страница
                                          как её дочерняя страница.
            additional_page_profile_name: Заголовок профильной страницы.
                                          Используется только при ``with_additional_page_profile=True``.
            profile_template_name: Имя Jinja2-шаблона для профильной страницы.

        Returns:
            Агрегированный ``PublishReport`` по всем опубликованным страницам.
        """
        logger.info("Публикация паспортов + релиза")

        resolved_root = passports_root_page_id or self.resolve_page_id(
            self._config.passports_root_parent_name,
            self._config.passports_root_parent_id,
            "passports_root_parent",
        )
        resolved_release_parent = release_parent_id or self.resolve_page_id(
            self._config.release_docs_root_parent_name,
            self._config.release_docs_root_parent_id,
            "release_docs_root_parent",
            required=False,
        )

        passports_report = self.publish(
            strategy_type="passports",
            parsed_data=parsed_data,
            root_page_id=resolved_root,
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
            parent_id=resolved_release_parent,
            include_passport_links=include_passport_links,
        )

        if with_additional_page_profile:
            profile_title = additional_page_profile_name or "Документация от профилей"
            # Find the just-published release page to use as parent.
            profile_parent_page = self._client.find_page(
                release_page_title, space=self._config.space
            )
            if profile_parent_page is None:
                logger.warning(
                    f"Страница '{release_page_title}' не найдена после публикации; "
                    "профильная страница будет опубликована без родителя."
                )
            profile_parent_id = (
                str(profile_parent_page["id"]) if profile_parent_page else None
            )

            profile_report = self.publish(
                strategy_type="profile_centric",
                parsed_data=parsed_data,
                page_title=profile_title,
                template_name=profile_template_name,
                parent_id=profile_parent_id,
                include_passport_links=include_passport_links,
            )

            return PublishReport(
                success=(
                    passports_report.success
                    and release_report.success
                    and profile_report.success
                ),
                pages_published=(
                    passports_report.pages_published
                    + release_report.pages_published
                    + profile_report.pages_published
                ),
                pages_failed=(
                    passports_report.pages_failed
                    + release_report.pages_failed
                    + profile_report.pages_failed
                ),
                errors=(
                    passports_report.errors + release_report.errors + profile_report.errors
                ),
                failed_pages=(
                    passports_report.failed_pages
                    + release_report.failed_pages
                    + profile_report.failed_pages
                ),
                details=(
                    passports_report.details + release_report.details + profile_report.details
                ),
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
