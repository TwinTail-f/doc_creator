"""Точка входа паблишера документации компонентов платформы."""

from pathlib import Path
from typing import Any

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.common.logger import logger
from autodoc.exceptions import ConfigError
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.confluence_client import ConfluenceClient
from autodoc.publisher.page_manager.root_page_resolver import RootPageResolver
from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.strategies import passports_strategy
from autodoc.publisher.strategies.models.publish_report import PublishReport
from autodoc.publisher.strategies.profile_centric_strategy import ProfileCentricPageStrategy
from autodoc.publisher.strategies.registry import create_strategy

_RENDERING_DIR: Path = Path(__file__).resolve().parent / "rendering"
"""Путь к директории rendering/ внутри установленного пакета publisher."""


class DocumentPublisher:
    """
    Оркестрирует публикацию документации компонентов в Confluence.

    Принимает конфигурацию, резолвит родительские страницы через
    ``RootPageResolver`` и делегирует создание и обновление страниц
    стратегии, выбранной по типу.
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
        self._client: ConfluenceClient = ConfluenceClient(confluence_config)
        self._builder: DocumentBuilder = DocumentBuilder(rendering_dir)
        self._page_resolver: RootPageResolver = RootPageResolver(self._client, confluence_config)
        self._data_dir: Path = data_dir or Path("data")
        logger.info(
            "DocumentPublisher инициализирован: space=%s, confluence_url=%s, data_dir=%s",
            confluence_config.space,
            confluence_config.url,
            self._data_dir,
        )

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
        strategy = create_strategy(
            strategy_type,
            confluence_client=self._client,
            document_builder=self._builder,
            parsed_data=parsed_data,
            space=self._config.space,
            data_dir=self._data_dir,
            **kwargs,
        )
        return strategy.execute()

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
        root_page_id = self._page_resolver.resolve_passports_root(
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
            ``strategies.release.root_parent_name``/``strategies.release.root_parent_id``,
            для ``'profile_centric'`` — ``strategies.profile_centric.root_parent_name``/
            ``strategies.profile_centric.root_parent_id``.
        """
        parent_id = self._page_resolver.resolve_single_page_parent(
            strategy_type, root_page_name, root_page_id
        )
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
            ``PublishReport`` с результатом публикации профильной страницы,
            либо отчёт о неудаче, если родительская (релизная) страница
            недоступна.
        """
        if not release_report.details:
            reason = (
                f"Профильная страница {profile_title!r} не опубликована: "
                "страница релиза не была опубликована, родитель недоступен"
            )
            logger.error(reason)
            return PublishReport(
                success=False,
                pages_published=0,
                pages_failed=1,
                errors=[reason],
                failed_pages=[{"page_title": profile_title, "reason": reason}],
            )
        profile_parent_id = str(release_report.details[0]["page_id"])
        return self.publish(
            strategy_type="profile_centric",
            parsed_data=parsed_data,
            page_title=profile_title,
            template_name=profile_template_name,
            parent_id=profile_parent_id,
            include_passport_links=include_passport_links,
        )

    def publish_all(self, parsed_data: ParsedResult) -> PublishReport:
        """
        Публикует типы из ``publish_all.targets`` конфига в фиксированном порядке.

        Порядок: паспорта, релиз, профили (дочерняя страница релиза), kit-pinned,
        kit-latest. Родительские страницы и заголовки берутся из конфигурации;
        родители проверяются до начала публикации, чтобы ошибка конфига не оставила
        часть страниц опубликованной.

        Args:
            parsed_data: Данные парсера.

        Returns:
            Агрегированный ``PublishReport`` по всем опубликованным страницам.

        Raises:
            ConfigError: Если у выбранного типа не задан родитель в конфигурации
                либо родительская страница не найдена в Confluence.
        """
        targets = self._config.publish_all.targets
        logger.info(f"Публикация типов: {', '.join(targets)}")

        error = self._config.missing_root_parents_error()
        if error:
            raise ConfigError(error)

        strategies = self._config.strategies
        passports_root_id = (
            self._page_resolver.resolve_passports_root(None, None)
            if "passports" in targets
            else None
        )
        parent_ids = {
            target: self._page_resolver.resolve_single_page_parent(target, None, None)
            for target in ("release", "kit_pinned", "kit_latest")
            if target in targets
        }

        reports: list[PublishReport] = []
        if passports_root_id is not None:
            reports.append(
                self.publish(
                    strategy_type="passports",
                    parsed_data=parsed_data,
                    root_page_id=passports_root_id,
                    template_name=passports_strategy.PassportsStrategy.DEFAULT_TEMPLATE,
                    batch_size=self._config.publish_batch_size,
                    batch_delay_seconds=self._config.publish_batch_delay_seconds,
                    target_release_version=self._config.target_release_version,
                )
            )
        if "release" in targets:
            release_report = self.publish(
                strategy_type="release",
                parsed_data=parsed_data,
                page_title=strategies.release.page_title,
                parent_id=parent_ids["release"],
            )
            reports.append(release_report)
            # Профильная страница публикуется здесь, пока release_report ещё не смешан
            # с остальными отчётами: это гарантирует, что details[0] будет именно
            # страницей релиза, а не первым паспортом компонента.
            if "profile_centric" in targets:
                reports.append(
                    self.publish_profile_page(
                        parsed_data=parsed_data,
                        profile_title=strategies.profile_centric.page_title,
                        profile_template_name=ProfileCentricPageStrategy.DEFAULT_TEMPLATE,
                        release_report=release_report,
                    )
                )
        if "kit_pinned" in targets:
            reports.append(
                self.publish(
                    strategy_type="kit_pinned",
                    parsed_data=parsed_data,
                    page_title=strategies.kit_pinned.page_title,
                    parent_id=parent_ids["kit_pinned"],
                )
            )
        if "kit_latest" in targets:
            reports.append(
                self.publish(
                    strategy_type="kit_latest",
                    parsed_data=parsed_data,
                    page_title=strategies.kit_latest.page_title,
                    parent_id=parent_ids["kit_latest"],
                )
            )

        return PublishReport.merge(*reports)
