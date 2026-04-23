"""
Абстрактные интерфейсы (Protocol) для инфраструктурных зависимостей паблишера.

Использование ``typing.Protocol`` (структурная типизация) означает, что ни
``ConfluenceClient``, ни ``DocumentBuilder`` не требуют изменений в коде —
они удовлетворяют этим интерфейсам неявно.

Стратегии, менеджеры страниц и тесты зависят от этих Protocol-ов,
а не от конкретных инфраструктурных классов.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IConfluenceClient(Protocol):
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
        ...

    def get_or_create_page(
        self,
        space: str,
        title: str,
        parent_id: str | None = None,
        body: str = "",
    ) -> str:
        """Возвращает ID существующей страницы или создаёт новую."""
        ...

    def find_page(
        self,
        title: str,
        space: str | None = None,
        expand: str = "",
    ) -> dict[str, Any] | None:
        """Ищет страницу по заголовку; возвращает словарь данных или None."""
        ...

    def get_page(
        self,
        page_id: str,
        expand: str = "",
    ) -> dict[str, Any]:
        """Загружает страницу по ID."""
        ...

    def get_page_body(self, space: str, title: str) -> str:
        """Возвращает тело страницы в Confluence Storage Format или пустую строку."""
        ...


@runtime_checkable
class IDocumentBuilder(Protocol):
    """
    Интерфейс рендеринга Jinja2-шаблонов в HTML.

    ``DocumentBuilder`` удовлетворяет этому интерфейсу структурно.
    """

    def build(self, template_name: str, view_model: dict[str, Any]) -> str:
        """Рендерит *template_name* с *view_model* и возвращает HTML-строку."""
        ...
