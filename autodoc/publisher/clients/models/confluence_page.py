"""Доменная модель страницы Confluence."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConfluencePage:
    """
    Доменное представление страницы Confluence.

    Attributes:
        id:           ID страницы.
        title:        Заголовок страницы.
        version:      Номер текущей версии (``0``, если не запрошен через ``expand``).
        ancestor_ids: ID предков по дереву (пусто, если ``ancestors`` не запрошен).
        body_html:    Тело в Storage Format (пусто, если ``body.storage`` не запрошен).
    """

    id: str
    title: str
    version: int = 0
    ancestor_ids: tuple[str, ...] = field(default_factory=tuple)
    body_html: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "ConfluencePage":
        """
        Строит ``ConfluencePage`` из JSON-объекта страницы Confluence REST API v1.

        Args:
            data: Сырой JSON-объект страницы из ответа Confluence API.

        Returns:
            Экземпляр ``ConfluencePage`` с данными из переданного JSON.
        """
        ancestors = data.get("ancestors") or []
        version_block = data.get("version") or {}
        storage = (data.get("body") or {}).get("storage") or {}
        try:
            version_number = int(version_block.get("number", 0))
        except (TypeError, ValueError):
            version_number = 0
        return cls(
            id=str(data["id"]),
            title=str(data.get("title", "")),
            version=version_number,
            ancestor_ids=tuple(str(a.get("id")) for a in ancestors),
            body_html=str(storage.get("value", "")),
        )

    def is_descendant_of(self, parent_id: str) -> bool:
        """Проверяет, есть ли ``parent_id`` среди предков страницы."""
        return parent_id in self.ancestor_ids
