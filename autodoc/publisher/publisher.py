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

# Импорт модулей стратегий регистрирует их в BasePublishStrategy._registry
# через __init_subclass__.
from autodoc.publisher.strategies import (
    passports_strategy,
    profile_strategy,
    release_strategy,
)  # noqa: F401

_RENDERING_DIR: Path = Path(__file__).resolve().parent / "rendering"
"""Путь к директории rendering/ внутри установленного пакета publisher."""


class DocumentPublisher:
    """
    Оркестрирует публикацию документации компонентов в Confluence.

    Принимает конфигурацию, выбирает стратегию по типу и делегирует
    создание и обновление страниц выбранной стратегии.
    """

    def __init__(
        self,
        confluence_config: ConfluenceConfigSchema,
        rendering_dir: Path = _RENDERING_DIR,
        data_dir: Path | None = None,
    ) -> None:
        """
        Args:
            confluence_config: Валидированная конфигурация Confluence.
            rendering_dir: Путь к директории ``rendering/`` (содержит
                ``templates/``, ``styles/``, ``macros/``). По умолчанию
                вычисляется относительно расположения установленного
                пакета ``publisher``, а не текущей рабочей директории.
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
            return page.id
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

    def _resolve_passports_root(
        self,
        name: str | None,
        page_id: str | None,
    ) -> str | None:
        """
        Резолвит ID корневой страницы иерархии паспортов.

        Если ``name``/``page_id`` не заданы — берёт значения из конфигурации
        Confluence как запасной вариант.

        Args:
            name: Название корневой страницы паспортов, введённое пользователем.
            page_id: ID корневой страницы паспортов, введённый пользователем.

        Returns:
            ID корневой страницы паспортов.

        Raises:
            ConfigError: Если страница не найдена ни по имени, ни по ID,
                         ни в конфигурации.
        """
        return self.resolve_page_id(
            name or self._config.passports_root_parent_name,
            page_id or self._config.passports_root_parent_id,
            "passports_root_parent",
        )

    def _resolve_release_parent(
        self,
        name: str | None,
        page_id: str | None,
    ) -> str | None:
        """
        Резолвит ID родительской страницы для релизной документации.

        Если ``name``/``page_id`` не заданы — берёт значения из конфигурации
        Confluence как запасной вариант. В отличие от паспортов, родитель
        не обязателен — публикация допускается без родительской страницы.

        Args:
            name: Название родительской страницы, введённое пользователем.
            page_id: ID родительской страницы, введённый пользователем.

        Returns:
            ID родительской страницы или ``None``, если ни одно из значений
            не настроено.

        Raises:
            ConfigError: Если ``name`` задан, но страница не найдена в Confluence.
        """
        return self.resolve_page_id(
            name or self._config.release_docs_root_parent_name,
            page_id or self._config.release_docs_root_parent_id,
            "release_docs_root_parent",
            required=False,
        )

    def _resolve_profile_parent(
        self,
        name: str | None,
        page_id: str | None,
    ) -> str | None:
        """
        Резолвит ID родительской страницы для профиль-центричной документации.

        Если ``name``/``page_id`` не заданы — берёт значения из конфигурации
        Confluence (``profile_docs_root_parent_name`` / ``profile_docs_root_parent_id``)
        как запасной вариант. Родитель не обязателен — публикация допускается
        без родительской страницы.

        Args:
            name: Название родительской страницы, введённое пользователем.
            page_id: ID родительской страницы, введённый пользователем.

        Returns:
            ID родительской страницы или ``None``, если ни одно из значений
            не настроено.

        Raises:
            ConfigError: Если ``name`` задан, но страница не найдена в Confluence.
        """
        return self.resolve_page_id(
            name or self._config.profile_docs_root_parent_name,
            page_id or self._config.profile_docs_root_parent_id,
            "profile_docs_root_parent",
            required=False,
        )

    def _resolve_single_page_parent(
        self,
        strategy_type: str,
        name: str | None,
        page_id: str | None,
    ) -> str | None:
        """
        Резолвит родительскую страницу для публикации одной страницы.

        Выбирает конфигурационный запасной вариант в зависимости от типа стратегии.

        Args:
            strategy_type: Тип стратегии (``'release'`` или ``'profile_centric'``).
            name: Название родительской страницы, введённое пользователем.
            page_id: ID родительской страницы, введённый пользователем.

        Returns:
            ID родительской страницы или ``None``, если ни одно из значений
            не настроено.

        Raises:
            ConfigError: Если ``name`` задан, но страница не найдена в Confluence.
        """
        if strategy_type == "profile_centric":
            return self._resolve_profile_parent(name, page_id)
        return self._resolve_release_parent(name, page_id)

    def _resolve_root_pages(
        self,
        passports_root_parent_name: str | None,
        passports_root_parent_id: str | None,
        release_root_page_name: str | None,
        release_root_page_id: str | None,
    ) -> tuple[str | None, str | None]:
        """
        Резолвит ID корневых страниц для паспортов и релизной документации.

        Args:
            passports_root_parent_name: Название корневой страницы паспортов
                                        или ``None`` для поиска по конфигурации.
            passports_root_parent_id: ID корневой страницы паспортов
                                      или ``None`` для поиска по конфигурации.
            release_root_page_name: Название родительской страницы релиза
                                    или ``None`` для поиска по конфигурации.
            release_root_page_id: ID родительской страницы релиза
                                 или ``None`` для поиска по конфигурации.

        Returns:
            Кортеж ``(resolved_passports_root, resolved_release_parent)``.

        Raises:
            ConfigError: Если корневая страница паспортов не найдена
                         и не задана в конфигурации.
        """
        resolved_root = self._resolve_passports_root(
            passports_root_parent_name, passports_root_parent_id
        )
        resolved_release_parent = self._resolve_release_parent(
            release_root_page_name, release_root_page_id
        )
        return resolved_root, resolved_release_parent

    def publish_passports(
        self,
        parsed_data: ParsedResult,
        template_name: str,
        passports_root_parent_name: str | None = None,
        passports_root_parent_id: str | None = None,
    ) -> PublishReport:
        """
        Резолвит корневую страницу и публикует коллекцию паспортов компонентов.

        Args:
            parsed_data: Данные парсера.
            template_name: Имя Jinja2-шаблона паспортов.
            passports_root_parent_name: Название корневой страницы паспортов,
                                        введённое пользователем.
            passports_root_parent_id: ID корневой страницы паспортов,
                                      введённый пользователем.

        Returns:
            ``PublishReport`` с результатами публикации паспортов.
        """
        root_page_id = self._resolve_passports_root(
            passports_root_parent_name, passports_root_parent_id
        )
        return self.publish(
            strategy_type="passports",
            parsed_data=parsed_data,
            root_page_id=root_page_id,
            template_name=template_name,
            batch_size=self._config.publish_batch_size,
            batch_delay_seconds=self._config.publish_batch_delay_seconds,
            target_release_version=self._config.target_release_version,
        )

    def publish_single_page(
        self,
        strategy_type: str,
        parsed_data: ParsedResult,
        page_title: str,
        template_name: str,
        root_page_name: str | None = None,
        root_page_id: str | None = None,
        include_passport_links: bool = True,
    ) -> PublishReport:
        """
        Резолвит родительскую страницу и публикует страницу release/profile.

        Args:
            strategy_type: Тип стратегии (``'release'`` или ``'profile_centric'``).
            parsed_data: Данные парсера.
            page_title: Заголовок публикуемой страницы.
            template_name: Имя Jinja2-шаблона.
            root_page_name: Название родительской страницы, введённое пользователем.
            root_page_id: ID родительской страницы, введённый пользователем.
            include_passport_links: Вставлять ли ссылки на паспорта компонентов.

        Returns:
            ``PublishReport`` с результатом публикации одной страницы.

        Note:
            Запасной вариант родительской страницы (если ``root_page_name``/
            ``root_page_id`` не заданы) берётся из конфигурации Confluence
            и зависит от ``strategy_type``: для ``'release'`` — это
            ``release_docs_root_parent_name``/``release_docs_root_parent_id``,
            для ``'profile_centric'`` — ``profile_docs_root_parent_name``/
            ``profile_docs_root_parent_id``.
        """
        parent_id = self._resolve_single_page_parent(strategy_type, root_page_name, root_page_id)
        return self.publish(
            strategy_type=strategy_type,
            parsed_data=parsed_data,
            page_title=page_title,
            template_name=template_name,
            parent_id=parent_id,
            include_passport_links=include_passport_links,
        )

    def publish_profile_page(
        self,
        parsed_data: ParsedResult,
        profile_title: str,
        profile_template_name: str,
        release_report: PublishReport,
        include_passport_links: bool = True,
    ) -> PublishReport:
        """
        Публикует профильную страницу как дочернюю к странице релиза.

        Args:
            parsed_data: Данные парсера.
            profile_title: Заголовок профильной страницы.
            profile_template_name: Имя Jinja2-шаблона для профильной страницы.
            release_report: Отчёт о публикации релизной страницы — используется
                            для извлечения ID родительской страницы.
            include_passport_links: Вставлять ли ссылки на паспорта компонентов.

        Returns:
            ``PublishReport`` с результатом публикации профильной страницы.
        """
        profile_parent_id = (
            str(release_report.details[0]["page_id"]) if release_report.details else None
        )
        if profile_parent_id is None:
            logger.warning(
                "Релизная страница не была опубликована; "
                "профильная страница будет опубликована без родителя."
            )
        return self.publish(
            strategy_type="profile_centric",
            parsed_data=parsed_data,
            page_title=profile_title,
            template_name=profile_template_name,
            parent_id=profile_parent_id,
            include_passport_links=include_passport_links,
        )

    def publish_all(
        self,
        parsed_data: ParsedResult,
        release_page_title: str,
        release_template_name: str,
        passports_root_parent_name: str | None = None,
        passports_root_parent_id: str | None = None,
        release_root_page_name: str | None = None,
        release_root_page_id: str | None = None,
        passport_template_name: str = passports_strategy.PassportsStrategy.DEFAULT_TEMPLATE,
        include_passport_links: bool = True,
        profile_title: str | None = None,
        profile_template_name: str | None = None,
    ) -> PublishReport:
        """Публикует паспорта, страницу релизной документации и (опционально)
        профильную страницу за один вызов.

        Args:
            parsed_data: Данные парсера.
            release_page_title: Заголовок страницы релизной документации.
            release_template_name: Имя Jinja2-шаблона для страницы релиза.
            passports_root_parent_name: Название корневой страницы иерархии
                                        паспортов, введённое пользователем.
                                        Если не указано — берётся из конфигурации.
            passports_root_parent_id: ID корневой страницы иерархии паспортов,
                                      введённый пользователем. Если не указан —
                                      берётся из конфигурации.
            release_root_page_name: Название родительской страницы для страницы
                                    релиза, введённое пользователем.
            release_root_page_id: ID родительской страницы для страницы релиза,
                                 введённый пользователем.
            passport_template_name: Имя Jinja2-шаблона паспортов.
            include_passport_links: Если ``True``, в страницу релиза вставляются
                                    ссылки на опубликованные паспорта.
            profile_title: Заголовок дополнительной профильной страницы.
                           Если задан вместе с ``profile_template_name``, профильная
                           страница публикуется как дочерняя к странице релиза.
            profile_template_name: Имя Jinja2-шаблона для профильной страницы.
                                   Обязателен при указании ``profile_title``.

        Returns:
            Агрегированный ``PublishReport`` по всем опубликованным страницам.
        """
        logger.info("Публикация паспортов + релиза")

        resolved_root, resolved_release_parent = self._resolve_root_pages(
            passports_root_parent_name,
            passports_root_parent_id,
            release_root_page_name,
            release_root_page_id,
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

        # Профильная страница публикуется здесь, пока release_report ещё не смешан
        # с отчётом паспортов — это гарантирует, что details[0] будет именно
        # страницей релиза, а не первым паспортом компонента.
        reports: list[PublishReport] = [passports_report, release_report]
        if profile_title and profile_template_name:
            profile_report = self.publish_profile_page(
                parsed_data=parsed_data,
                profile_title=profile_title,
                profile_template_name=profile_template_name,
                release_report=release_report,
                include_passport_links=include_passport_links,
            )
            reports.append(profile_report)

        return PublishReport.merge(*reports)
