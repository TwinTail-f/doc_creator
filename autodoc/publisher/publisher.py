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
from autodoc.publisher.strategies import registry
from autodoc.publisher.strategies.models.publish_report import PublishReport
from autodoc.publisher.strategies.publish_plan import PUBLISH_PLAN, PublishNode
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
            strategy_type: Ключ стратегии из ``registry.STRATEGIES``.
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

    def _publish_target(
        self,
        key: str,
        parsed_data: ParsedResult,
        parent_id: str,
        **overrides: Any,
    ) -> PublishReport:
        """
        Публикует страницу типа ``key`` под страницей ``parent_id``.

        Args:
            key: Ключ стратегии из ``registry.STRATEGIES``.
            parsed_data: Данные парсера.
            parent_id: ID родительской страницы.
            **overrides: Аргументы стратегии, переопределяющие значения из конфигурации.

        Returns:
            ``PublishReport`` с результатом публикации.
        """
        strategy_cls = registry.STRATEGIES[key]
        kwargs = {**strategy_cls.kwargs_from_config(self._config, key), **overrides}
        return self.publish(key, parsed_data, parent_id=parent_id, **kwargs)

    def publish_passports(
        self,
        parsed_data: ParsedResult,
        template_name: str,
        passports_root_parent_name: str | None = None,
        passports_root_parent_id: str | None = None,
    ) -> PublishReport:
        """
        Публикует коллекцию паспортов компонентов.

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
        parent_id = self._page_resolver.resolve_parent(
            "passports", passports_root_parent_name, passports_root_parent_id
        )
        return self._publish_target(
            "passports", parsed_data, parent_id, template_name=template_name
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
        Публикует одностраничную стратегию.

        Args:
            strategy_type: Ключ одностраничной стратегии из ``registry.STRATEGIES``.
            parsed_data: Данные парсера.
            page_title: Заголовок публикуемой страницы.
            template_name: Имя Jinja2-шаблона.
            root_page_name: Название родительской страницы, введённое пользователем.
            root_page_id: ID родительской страницы, введённый пользователем.
            include_passport_links: Вставлять ли ссылки на паспорта компонентов.

        Returns:
            ``PublishReport`` с результатом публикации одной страницы.

        Raises:
            ConfigError: Если ``strategy_type`` не одностраничная стратегия.
        """
        if not registry.is_single_page_strategy(strategy_type):
            raise ConfigError(
                f"Стратегия {strategy_type!r} не поддерживает резолвинг родительской "
                "страницы одностраничной публикации (не зарегистрирована в "
                "registry.STRATEGIES либо IS_SINGLE_PAGE=False)"
            )
        parent_id = self._page_resolver.resolve_parent(strategy_type, root_page_name, root_page_id)
        return self._publish_target(
            strategy_type,
            parsed_data,
            parent_id,
            page_title=page_title,
            template_name=template_name,
            include_passport_links=include_passport_links,
        )

    def publish_all(self, parsed_data: ParsedResult) -> PublishReport:
        """
        Публикует типы страниц, выбранные в ``publish_all.targets``.

        Args:
            parsed_data: Данные парсера.

        Returns:
            Агрегированный ``PublishReport`` по всем выбранным типам.

        Raises:
            ConfigError: Если родительская страница не задана или не найдена.
        """
        targets = self._config.publish_all.targets
        logger.info(f"Публикация типов: {', '.join(targets)}")

        error = self._config.missing_root_parents_error()
        if error:
            raise ConfigError(error)

        selected = [node for node in PUBLISH_PLAN if node.key in targets]
        parent_ids = {
            node.key: self._page_resolver.resolve_parent(node.key, None, None)
            for node in selected
            if node.parent_from is None
        }

        reports: dict[str, PublishReport] = {}
        for node in selected:
            if node.parent_from is None:
                parent_id = parent_ids[node.key]
            else:
                parent_id = self._page_id_from(reports.get(node.parent_from))
                if parent_id is None:
                    reports[node.key] = self._skipped_report(node)
                    continue
            reports[node.key] = self._publish_target(node.key, parsed_data, parent_id)

        return PublishReport.merge(*reports.values())

    @staticmethod
    def _page_id_from(report: PublishReport | None) -> str | None:
        """
        Возвращает ID опубликованной страницы из отчёта.

        Args:
            report: Отчёт публикации или ``None``.

        Returns:
            ID страницы или ``None``, если страница не опубликована.
        """
        if report is None or not report.details:
            return None
        return str(report.details[0]["page_id"])

    def _skipped_report(self, node: PublishNode) -> PublishReport:
        """
        Формирует отчёт о пропущенном типе, чей родитель не опубликован.

        Args:
            node: Узел плана пропущенного типа.

        Returns:
            ``PublishReport`` с одной неудавшейся страницей.
        """
        title = getattr(self._config.strategies, node.key).page_title
        reason = (
            f"Страница {title!r} не опубликована: родительская страница "
            f"{node.parent_from!r} не была опубликована, родитель недоступен"
        )
        logger.error(reason)
        return PublishReport(
            success=False,
            pages_published=0,
            pages_failed=1,
            errors=[reason],
            failed_pages=[{"page_title": title, "reason": reason}],
        )
