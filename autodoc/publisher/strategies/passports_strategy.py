"""Стратегия публикации коллекции паспортов компонентов в Confluence."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.protocols import IConfluenceClient, IDocumentBuilder
from autodoc.publisher.legacy_content.legacy_service import extract_for_platform
from autodoc.publisher.page_manager.hierarchy_manager import PageHierarchyManager
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.utils.publish_queue import PublishQueue
from autodoc.publisher.strategies.base import BasePublishStrategy, PublishReport
from autodoc.publisher.transformers.passport_transformer import PassportTransformer

_DEFAULT_TEMPLATE: str = "component_passport.jinja2"
_DEFAULT_BATCH_SIZE: int = 2
_DEFAULT_BATCH_DELAY: float = 5.0


@dataclass
class _PagePublishResult:
    """Внутренний результат попытки публикации одной страницы паспорта."""

    detail: dict[str, Any] | None = None
    error: str | None = None
    failed_page: dict[str, str] | None = None

    @property
    def success(self) -> bool:
        return self.detail is not None


class PassportsStrategy(BasePublishStrategy, strategy_type="passports"):
    """
    Публикует паспорта компонентов как иерархию страниц Confluence.

    Для каждой пары компонент × релиз выполняет:
      1. Обеспечивает существование иерархии (Корень → Компонент → Версия).
      2. Получает и фильтрует legacy-контент существующей страницы.
      3. Трансформирует данные через ``PassportTransformer``.
      4. Рендерит Jinja2-шаблон (legacy-секции передаются в view-model).
      5. Публикует страницу.

    Публикация выполняется пакетами через ``PublishQueue`` для предотвращения
    перегрузки сервера Confluence. После обработки всех компонентов сохраняет
    карту ID страниц через ``PassportPageRegistry``, чтобы ``ReleasePageStrategy``
    смогла вставить ссылки на паспорта в отдельном запуске.
    """

    def __init__(
        self,
        confluence_client: IConfluenceClient,
        document_builder: IDocumentBuilder,
        parsed_data: ParsedResult,
        space: str,
        root_page_id: str,
        template_name: str = _DEFAULT_TEMPLATE,
        data_dir: Path | None = None,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        batch_delay_seconds: float = _DEFAULT_BATCH_DELAY,
        target_release_version: str = "",
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
                        По умолчанию ``2``.
            batch_delay_seconds: Задержка в секундах между пакетами.
                                 По умолчанию ``0`` (без задержки).
            target_release_version: Подпись текущего релиза (например ``"Platform 2.2"``).
                                    Отображается в заголовке паспорта и метке вкладки.
                                    Если пустая строка — формируется автоматически из
                                    ``platform_version`` данных парсера.

        Raises:
            ValueError: Если ``space`` или ``root_page_id`` пустые.
        """
        if not space:
            raise ValueError("space не может быть пустым")
        if not root_page_id:
            raise ValueError("root_page_id не может быть пустым")

        super().__init__(confluence_client, document_builder, parsed_data, space)
        self._root_page_id: str = root_page_id
        self._template_name: str = template_name
        self._target_release_version: str = target_release_version
        self._hierarchy: PageHierarchyManager = PageHierarchyManager(confluence_client)
        self._page_registry: PassportPageRegistry = PassportPageRegistry(data_dir)
        self._queue: PublishQueue = PublishQueue(
            batch_size=batch_size,
            batch_delay_seconds=batch_delay_seconds,
        )

    def execute(self) -> PublishReport:
        """
        Публикует паспорта для всех компонентов и всех релизов.

        Итерирует по всем компонентам из ``ParsedResult``. Компоненты без
        релизов пропускаются с записью в список ошибок. Публикация выполняется
        пакетами через ``PublishQueue``. Ошибки отдельных страниц логируются,
        фиксируются в ``failed_pages`` и не прерывают обработку остальных.

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

        results = self._queue.process(work_items, self._try_publish_item)

        details = [r.detail for r in results if r.success]
        failed_pages = [r.failed_page for r in results if not r.success]
        page_errors = [r.error for r in results if r.error is not None]
        errors.extend(page_errors)

        pages_published = len(details)
        pages_failed = len(failed_pages)

        pages_map = self._build_pages_map(details)
        self._page_registry.save(pages_map)

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
        # Сознательно ловим все исключения: любая ошибка одного паспорта (сеть, API,
        # рендеринг шаблона, отсутствие данных) должна быть изолирована, чтобы
        # остальные паспорта публиковались без сбоев.
        except Exception as e:
            reason = str(e)
            msg = f"Ошибка паспорта {comp_name} v{release_version}: {reason}"
            logger.error(msg)
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

        Последовательность:
          1. Обеспечивает иерархию страниц через ``PageHierarchyManager``.
          2. Получает текущее тело страницы (пустая строка при первой публикации).
          3. Трансформирует данные, извлекает legacy-секции других платформ.
          4. Рендерит шаблон и публикует страницу.

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
        existing_html = self._fetch_existing_body(page_title)

        transformer = PassportTransformer(comp_name, release_version)
        view_model = transformer.transform(self._data)
        platform_version = view_model.get("platform_version", "")

        # Извлекаем legacy-секции других платформ, чтобы не потерять их
        # при обновлении страницы для текущей платформы.
        legacy_contents = extract_for_platform(existing_html, platform_version)
        target_platform = (
            self._target_release_version
            if self._target_release_version
            else f"Платформа {platform_version}"
        )
        view_model["target_platform"] = target_platform
        view_model["legacy_contents"] = legacy_contents

        html_body = self._minify_html(
            self._builder.build(self._template_name, view_model)
        )
        result = self._client.publish_page(
            space=self._space,
            parent_id=version_page_id,
            title=page_title,
            body_html=html_body,
        )
        return result["id"], result["version"], result["status"]

    def _fetch_existing_body(self, page_title: str) -> str:
        """
        Возвращает текущее тело страницы или пустую строку при любой ошибке.

        Ошибки при получении тела страницы не критичны: в худшем случае
        legacy-контент других платформ будет потерян при следующей публикации,
        но сам паспорт опубликуется корректно.

        Args:
            page_title: Заголовок страницы в Confluence.

        Returns:
            HTML тело страницы или пустая строка.
        """
        try:
            return self._client.get_page_body(space=self._space, title=page_title)
        # Сознательно ловим все исключения: невозможность получить текущее тело
        # страницы некритична — паспорт будет опубликован без сохранения
        # legacy-контента, что допустимо.
        except Exception as e:
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
