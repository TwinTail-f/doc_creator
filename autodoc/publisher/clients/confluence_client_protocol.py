"""
Протокол (структурный интерфейс) Confluence-клиента, используемого стратегиями паблишера.
"""

from typing import Any, Protocol


class ConfluenceClientProtocol(Protocol):
    """
    Интерфейс чтения/записи страниц Confluence для стратегий паблишера.

    Охватывает только методы, реально вызываемые бизнес-логикой.
    ``ConfluenceClient`` удовлетворяет этому интерфейсу структурно.
    """

    def publish_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> dict[str, Any]:
        """Создаёт или обновляет страницу Confluence и возвращает её метаданные."""

    def ensure_page_exists(
        self,
        space: str,
        title: str,
        parent_id: str | None = None,
        body: str = "",
    ) -> str:
        """Обеспечивает существование страницы и возвращает её ID."""

    def find_page(
        self,
        title: str,
        space: str | None = None,
        expand: str = "",
    ) -> dict[str, Any] | None:
        """Ищет страницу по заголовку; возвращает словарь данных или None."""

    def get_page(
        self,
        page_id: str,
        expand: str = "",
    ) -> dict[str, Any]:
        """Загружает страницу по ID."""

    def get_page_body(self, space: str, title: str) -> str:
        """Возвращает тело страницы в Confluence Storage Format или пустую строку."""
