"""Стратегия публикации коллекции паспортов компонентов в Confluence."""
from pathlib import Path
from typing import Any

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.confluence_client import ConfluenceClient
from autodoc.publisher.legacy_content.legacy_service import LegacyContentService
from autodoc.publisher.page_manager.hierarchy_manager import PageHierarchyManager
from autodoc.publisher.passport_registry import PassportPageRegistry
from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.strategies.base import BasePublishStrategy, PublishReport
from autodoc.publisher.transformers.passport_transformer import PassportTransformer

_DEFAULT_TEMPLATE: str = "component_passport.jinja2"


class PassportsStrategy(BasePublishStrategy, strategy_type="passports"):
    """
    Публикует паспорта компонентов как иерархию страниц Confluence.

    Для каждой пары компонент × релиз выполняет:
      1. Обеспечивает существование иерархии (Корень → Компонент → Версия).
      2. Получает и фильтрует legacy-контент существующей страницы.
      3. Трансформирует данные через ``PassportTransformer``.
      4. Рендерит Jinja2-шаблон (legacy-секции передаются в view-model).
      5. Публикует страницу.

    После обработки всех компонентов сохраняет карту ID страниц через
    ``PassportPageRegistry``, чтобы ``ReleasePageStrategy`` смогла вставить
    ссылки на паспорта в отдельном запуске.
    """

    def __init__(
        self,
        confluence_client: ConfluenceClient,
        document_builder: DocumentBuilder,
        parsed_data: ParsedResult,
        space: str,
        root_page_id: str,
        template_name: str = _DEFAULT_TEMPLATE,
        data_dir: Path | None = None,
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

        Raises:
            ValueError: Если ``space`` или ``root_page_id`` пустые.
        """
        if not space:
            raise ValueError("space cannot be empty")
        if not root_page_id:
            raise ValueError("root_page_id cannot be empty")

        super().__init__(confluence_client, document_builder, parsed_data, space)
        self._root_page_id: str = root_page_id
        self._template_name: str = template_name
        self._hierarchy: PageHierarchyManager = PageHierarchyManager(confluence_client)
        self._legacy_svc: LegacyContentService = LegacyContentService()
        self._registry: PassportPageRegistry = PassportPageRegistry(data_dir)

    def execute(self) -> PublishReport:
        """
        Публикует паспорта для всех компонентов и всех релизов.

        Итерирует по всем компонентам из ``ParsedResult``. Компоненты без
        релизов пропускаются с записью в список ошибок. Ошибки отдельных
        страниц логируются, но не прерывают обработку остальных.

        Returns:
            ``PublishReport`` с итоговым статусом, числом опубликованных
            страниц, списком ошибок и детальными записями по каждой странице.
        """
        logger.info("старт публикации паспортов")
        errors: list[str] = []
        details: list[dict[str, Any]] = []
        pages_published: int = 0

        for comp in self._data.components:
            if not comp.releases:
                errors.append(f"Нет релизов для компонента {comp.name!r}")
                continue

            for release in comp.releases:
                try:
                    page_id, version, status = self._publish_one(
                        comp.name, release.version
                    )
                    pages_published += 1
                    details.append({
                        "component_name": comp.name,
                        "release_version": release.version,
                        "page_title": self._make_page_title(comp.name, release.version),
                        "page_id": page_id,
                        "version": version,
                        "status": status,
                    })
                except Exception as e:
                    msg = f"Ошибка паспорта {comp.name} v{release.version}: {e}"
                    errors.append(msg)
                    logger.error(msg)

        pages_map = self._build_pages_map(details)
        self._registry.save(pages_map)

        logger.info(f"завершено — {pages_published} опубликовано, {len(errors)} ошибок")
        return PublishReport(
            success=len(errors) == 0,
            pages_published=pages_published,
            errors=errors,
            details=details,
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
        legacy_contents = self._legacy_svc.extract_for_platform(
            existing_html, platform_version
        )
        view_model["target_platform"] = f"Платформа {platform_version}"
        view_model["legacy_contents"] = legacy_contents

        html_body = self._builder.build(self._template_name, view_model)
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
        except Exception as e:
            logger.warning(f"Не удалось получить тело страницы {page_title!r}: {e}")
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
