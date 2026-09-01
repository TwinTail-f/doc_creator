"""Абстрактный базовый класс конвертеров документации релиза."""

from typing import Any

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.converters.base_data_converter import BaseDataConverter


class BaseReleaseConverter(BaseDataConverter):
    """
    Базовый класс конвертеров документации релиза.

    Конкретные виды реализуют ``convert()`` и, при необходимости,
    ``enrich_with_passport_links()`` — обе формы релиза (полная и
    профиль-центричная) показывают ссылки на паспорта компонентов, но в
    разных по структуре view-model, поэтому каждая сама решает, как их
    вставить. Общие для обеих форм хелперы лукапа/URL паспорта вынесены сюда.
    """

    def __init__(
        self,
        include_passport_links: bool = True,
    ) -> None:
        """
        Args:
            include_passport_links: Включать ли ссылки на паспорта компонентов —
                                    и в view-model шаблона (флаг отображения),
                                    и при вызове ``enrich_with_passport_links()``.
        """
        self._include_passport_links: bool = include_passport_links

    @property
    def wants_passport_links(self) -> bool:
        """Отражает ``include_passport_links``, переданный в конструктор."""
        return self._include_passport_links

    def _base_view_model(self, data: ParsedResult) -> dict[str, Any]:
        """Строит общие для всех видов релиза поля view-model.

        Args:
            data: Полный набор данных парсера.

        Returns:
            Словарь с полями ``platform_version`` и ``include_passport_links``.
        """
        return {
            "platform_version": data.platform_version,
            "include_passport_links": self._include_passport_links,
        }

    @staticmethod
    def _lookup_passport_entry(
        passport_pages: dict[str, Any],
        comp_name: str,
        version: str,
    ) -> dict[str, Any] | None:
        """Возвращает запись реестра паспортов для компонента и версии или None.

        Args:
            passport_pages: Реестр страниц паспортов.
            comp_name: Имя компонента.
            version: Версия компонента.

        Returns:
            Запись реестра или None, если компонент или версия не найдены.
        """
        return passport_pages.get(comp_name, {}).get(version)

    @staticmethod
    def _build_passport_url(space: str, page_id: str) -> str:
        """
        Строит относительный URL страницы паспорта в Confluence.

        Args:
            space: Ключ Space в Confluence.
            page_id: ID страницы паспорта.

        Returns:
            Относительный путь вида ``/spaces/{space}/pages/{page_id}``.
        """
        return f"/spaces/{space}/pages/{page_id}"
