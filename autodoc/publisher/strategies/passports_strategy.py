"""Стратегия публикации коллекции паспортов компонентов в Confluence."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import TemplateError, TemplateNotFound

from autodoc.common.logger import logger
from autodoc.common.parallel_executor import ParallelExecutor
from autodoc.exceptions import ConfluenceError
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.confluence_client import ConfluenceClient
from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.legacy_content.legacy_service import extract_for_platform
from autodoc.publisher.page_manager.hierarchy_manager import PageHierarchyManager
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.strategies.base_publish_strategy import BasePublishStrategy
from autodoc.publisher.strategies.models.publish_report import PublishReport
from autodoc.publisher.converters.passport_converter import PassportConverter

_DEFAULT_EXECUTOR_MAX_WORKERS: int = 1
_DEFAULT_EXECUTOR_LOG_INTERVAL: int = 50


@dataclass
class _PagePublishResult:
    """Внутренний результат попытки публикации одной страницы паспорта."""

    detail: dict[str, Any] | None = None
    error: str | None = None
    failed_page: dict[str, str] | None = None

    @property
    def success(self) -> bool:
        return self.detail is not None


class PassportsStrategy(BasePublishStrategy):
    """
    Публикует паспорта компонентов как иерархию страниц Confluence.

    Для каждой пары компонент × релиз создаёт или обновляет страницу паспорта
    в иерархии Корень → Компонент → Версия. Публикация выполняется пакетами
    для предотвращения перегрузки сервера. По завершении сохраняет карту ID
    страниц, которая используется стратегиями релиза для вставки ссылок.
    """

    DEFAULT_TEMPLATE: str = "component_passport.jinja2"

    def __init__(
        self,
        confluence_client: ConfluenceClient,
        document_builder: DocumentBuilder,
        parsed_data: ParsedResult,
        space: str,
        root_page_id: str,
        template_name: str = "component_passport.jinja2",
        data_dir: Path | None = None,
        batch_size: int = 10,
        batch_delay_seconds: float = 0.0,
        target_release_version: str = "",
        converter_factory: Callable[[str, str], BaseDataConverter] = PassportConverter,
    ) -> None:
        """
        Args:
            confluence_client: Клиент Confluence API.
            document_builder: Рендерер Jinja2-шаблонов.
            parsed_data: Данные парсера.
            space: Ключ Space в Confluence.
            root_page_id: ID корневой страницы иерархии паспортов.
            template_name: Имя Jinja2-шаблона. По умолчанию ``component_passport.jinja2``.
            data_dir: Директория для ``passport_pages.json``. По умолчанию ``Path('data')``.
            batch_size: Количество страниц, публикуемых в одном пакете.
                        По умолчанию ``10``.
            batch_delay_seconds: Задержка в секундах между пакетами.
                                 По умолчанию ``0`` (без задержки).
            target_release_version: Подпись текущего релиза (например ``"Platform 2.2"``).
                                    Отображается в заголовке паспорта и метке вкладки.
                                    Если пустая строка — формируется автоматически из
                                    ``platform_version`` данных парсера.
            converter_factory: Фабрика конвертеров паспортов. Принимает
                                ``(comp_name, release_version)`` и возвращает
                                ``BaseDataConverter``. По умолчанию ``PassportConverter``.

        Raises:
            ValueError: Если ``root_page_id`` пустой.
        """
        if not root_page_id:
            raise ValueError("root_page_id не может быть пустым")

        super().__init__(confluence_client, document_builder, parsed_data, space)
        self._root_page_id: str = root_page_id
        self._template_name: str = template_name
        self._target_release_version: str = target_release_version
        self._converter_factory: Callable[[str, str], BaseDataConverter] = converter_factory
        self._hierarchy: PageHierarchyManager = PageHierarchyManager(confluence_client)
        self._page_registry: PassportPageRegistry = PassportPageRegistry(data_dir)
        self._executor: ParallelExecutor = ParallelExecutor(
            max_workers=_DEFAULT_EXECUTOR_MAX_WORKERS,
            log_progress_interval=_DEFAULT_EXECUTOR_LOG_INTERVAL,
            batch_size=batch_size,
            batch_delay=batch_delay_seconds,
        )

    def execute(self) -> PublishReport:
        """
        Публикует паспорта для всех компонентов и всех релизов.

        Ошибки отдельных страниц фиксируются в отчёте и не прерывают
        публикацию остальных.

        Returns:
            ``PublishReport`` с итоговым статусом, числом опубликованных
            и неудавшихся страниц, списком ошибок и детальными записями
            по каждой странице.
        """
        logger.info("Старт публикации паспортов")
        errors: list[str] = []

        work_items: list[tuple[str, str]] = []
        for comp in self._data.components:
            if not comp.releases:
                errors.append(f"Нет релизов для компонента {comp.name}")
                continue
            for release in comp.releases:
                work_items.append((comp.name, release.version))

        raw_results = self._executor.execute(
            self._try_publish_item,
            work_items,
            task_label="паспортов",
        )
        results: list[_PagePublishResult] = [
            (
                r
                if r is not None
                else _PagePublishResult(
                    error="Неожиданная ошибка выполнения задачи",
                    failed_page={"page_title": "неизвестно", "reason": "None result"},
                )
            )
            for r in raw_results
        ]

        details = [r.detail for r in results if r.success]
        failed_pages = [r.failed_page for r in results if not r.success]
        page_errors = [r.error for r in results if r.error is not None]
        errors.extend(page_errors)

        pages_published = len(details)
        pages_failed = len(failed_pages)

        pages_map = self._build_pages_map(details)
        self._page_registry.upsert(pages_map)

        logger.info(
            f"Завершено — {pages_published} опубликовано, "
            f"{pages_failed} не опубликовано, {len(errors)} ошибок"
        )
        return PublishReport(
            success=len(errors) == 0,
            pages_published=pages_published,
            pages_failed=pages_failed,
            errors=errors,
            failed_pages=failed_pages,
            details=details,
        )

    def _try_publish_item(self, item: tuple[str, str]) -> _PagePublishResult:
        """
        Пытается опубликовать одну страницу паспорта, перехватывая ошибки.

        Args:
            item: Кортеж ``(comp_name, release_version)``.

        Returns:
            ``_PagePublishResult`` с деталями публикации или информацией об ошибке.
        """
        comp_name, release_version = item
        page_title = self._make_page_title(comp_name, release_version)
        try:
            page_id, version, status = self._publish_one(comp_name, release_version)
            return _PagePublishResult(
                detail={
                    "component_name": comp_name,
                    "release_version": release_version,
                    "page_title": page_title,
                    "page_id": page_id,
                    "version": version,
                    "status": status,
                }
            )
        # Перехватываем только ожидаемые ошибки операционного домена (сеть,
        # API Confluence, шаблоны, некорректные данные): любая такая ошибка
        # одного паспорта должна быть изолирована, чтобы остальные паспорта
        # публиковались без сбоев. Программные ошибки (AttributeError,
        # TypeError и т.п.) пробрасываются дальше с полным traceback.
        except (ConfluenceError, TemplateError, TemplateNotFound, ValueError, KeyError) as e:
            reason = str(e)
            msg = f"Ошибка паспорта {comp_name} v{release_version}: {reason}"
            logger.exception(msg)
            return _PagePublishResult(
                error=msg,
                failed_page={"page_title": page_title, "reason": reason},
            )

    def _publish_one(
        self,
        comp_name: str,
        release_version: str,
    ) -> tuple[str, int, str]:
        """
        Публикует одну страницу паспорта.

        Args:
            comp_name: Имя компонента.
            release_version: Версия релиза.

        Returns:
            Кортеж ``(page_id, version, status)``.
        """
        version_page_id = self._hierarchy.ensure_hierarchy_exists(
            space=self._space,
            root_parent_id=self._root_page_id,
            component_name=comp_name,
            release_version=release_version,
        )

        page_title = self._make_page_title(comp_name, release_version)
        existing_html = self._fetch_existing_body(page_title, parent_id=version_page_id)

        converter = self._converter_factory(comp_name, release_version)
        view_model = converter.transform(self._data)
        platform_version = view_model.get("platform_version", "")

        # Извлекаем legacy-секции других платформ, чтобы не потерять их
        # при обновлении страницы для текущей платформы.
        legacy_contents = extract_for_platform(existing_html, platform_version)
        target_platform = (
            self._target_release_version
            if self._target_release_version
            else f"Platform {platform_version}"
        )
        view_model["target_platform"] = target_platform
        # legacy_contents намеренно внедряется здесь, на уровне стратегии,
        # а не в PassportConverter.transform() — секции других платформ
        # извлекаются из существующей страницы Confluence и недоступны конвертеру.
        view_model["legacy_contents"] = legacy_contents

        result = self._render_and_publish(
            page_title=page_title,
            template_name=self._template_name,
            view_model=view_model,
            parent_id=version_page_id,
        )
        return result.id, result.version, result.status

    def _fetch_existing_body(self, page_title: str, parent_id: str) -> str:
        """
        Возвращает текущее тело страницы или пустую строку при любой ошибке.

        Лукап безопасен относительно дерева (через ``parent_id``): страница
        с тем же заголовком, но в другой части иерархии паспортов, не будет
        случайно прочитана как "существующий" контент текущего паспорта.

        Args:
            page_title: Заголовок страницы в Confluence.
            parent_id:  ID страницы версии — ожидаемый родитель страницы паспорта.

        Returns:
            HTML тело страницы или пустая строка.
        """
        try:
            return self._client.get_page_body(
                space=self._space, title=page_title, parent_id=parent_id
            )
        # Ошибка получения тела страницы (сеть, API Confluence) некритична —
        # паспорт будет опубликован без сохранения legacy-контента, что допустимо.
        except ConfluenceError as e:
            logger.warning(f"Не удалось получить тело страницы {page_title}: {e}")
            return ""

    @staticmethod
    def _make_page_title(comp_name: str, release_version: str) -> str:
        """
        Формирует заголовок страницы паспорта.

        Args:
            comp_name: Имя компонента.
            release_version: Версия релиза.

        Returns:
            Строка вида ``'Документация <comp_name> <release_version>'``.
        """
        return f"Документация {comp_name} {release_version}"

    @staticmethod
    def _build_pages_map(details: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Строит карту ID страниц из списка деталей публикации.

        Результирующая структура передаётся в ``PassportPageRegistry.save()``
        и позволяет ``ReleasePageStrategy`` найти страницу паспорта по имени
        компонента и версии релиза.

        Args:
            details: Список записей из ``execute()`` — по одной на каждую
                     успешно опубликованную страницу.

        Returns:
            Словарь вида ``{comp_name: {version: {page_id, page_title, version}}}``.
        """
        pages_map: dict[str, Any] = {}
        for d in details:
            pages_map.setdefault(d["component_name"], {})[str(d["release_version"])] = {
                "page_id": d["page_id"],
                "page_title": d["page_title"],
                "version": d["version"],
            }
        return pages_map
