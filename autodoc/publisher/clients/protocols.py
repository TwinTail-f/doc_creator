"""
Abstract interfaces (Protocols) for publisher infrastructure dependencies.

Using ``typing.Protocol`` (structural subtyping) means neither
``ConfluenceClient`` nor ``DocumentBuilder`` requires any code change —
they satisfy these interfaces implicitly.

Strategies, page managers, and tests depend on these Protocols,
not on the concrete infrastructure classes.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IConfluenceClient(Protocol):
    """
    Read/write interface to Confluence pages used by publisher strategies.

    Covers only the methods actually called by business-logic code.
    ``ConfluenceClient`` satisfies this interface structurally.
    """

    def publish_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> dict[str, Any]:
        """Create or update a Confluence page and return its metadata."""
        ...

    def get_or_create_page(
        self,
        space: str,
        title: str,
        parent_id: str | None = None,
        body: str = "",
    ) -> str:
        """Return the ID of an existing page or create a new one."""
        ...

    def find_page(
        self,
        title: str,
        space: str | None = None,
        expand: str = "",
    ) -> dict[str, Any] | None:
        """Search for a page by title; return its data dict or None."""
        ...

    def get_page(
        self,
        page_id: str,
        expand: str = "",
    ) -> dict[str, Any]:
        """Load a page by ID."""
        ...

    def get_page_body(self, space: str, title: str) -> str:
        """Return the page body in Confluence Storage Format, or empty string."""
        ...


@runtime_checkable
class IDocumentBuilder(Protocol):
    """
    Interface for rendering Jinja2 templates to HTML.

    ``DocumentBuilder`` satisfies this interface structurally.
    """

    def build(self, template_name: str, view_model: dict[str, Any]) -> str:
        """Render *template_name* with *view_model* and return the HTML string."""
        ...
