"""
Protocol (structural interface) for document builder used by publisher strategies.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IDocumentBuilder(Protocol):
    """
    Интерфейс рендеринга Jinja2-шаблонов в HTML.

    ``DocumentBuilder`` удовлетворяет этому интерфейсу структурно.
    """

    def build(self, template_name: str, view_model: dict[str, Any]) -> str:
        """Рендерит *template_name* с *view_model* и возвращает HTML-строку."""
        ...
