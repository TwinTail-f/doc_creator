"""Извлечение legacy-контента из Confluence Storage Format."""

__all__ = ["extract_by_platform_tab", "extract_platform_versions"]

from autodoc.publisher.legacy_content._html_utils import (
    _RICH_TEXT_BODY_OPEN,
    extract_rich_text_body,
    parse_page_sections,
)


def extract_by_platform_tab(html: str, platform_name: str) -> str:
    """
    Извлекает содержимое вкладки для указанной платформы.

    Находит маркер вкладки по имени платформы, затем с помощью
    ``extract_rich_text_body`` depth-balanced извлекает тело вкладки,
    корректно обрабатывая вложенные ``<ac:rich-text-body>``
    (например, внутри таблиц или панелей).

    Args:
        html: HTML в Confluence Storage Format.
        platform_name: Имя платформы (например ``'Platform 2.0'``).

    Returns:
        Содержимое вкладки или пустая строка, если вкладка не найдена.
    """
    if not html:
        return ""

    tab_marker = f'<ac:parameter ac:name="name">{platform_name}</ac:parameter>'
    start_idx = html.find(tab_marker)
    if start_idx == -1:
        return ""

    body_start = html.find(_RICH_TEXT_BODY_OPEN, start_idx)
    if body_start == -1:
        return ""

    content, _ = extract_rich_text_body(html, body_start)
    return content


def extract_platform_versions(html: str) -> dict[str, str]:
    """
    Автоматически определяет все платформенные версии в HTML и извлекает их контент.

    Delegates to ``parse_page_sections`` from ``_html_utils``,
    which tries tab format first, then ``<h1>Platform X.Y</h1>`` headers,
    then h2/h3 headers with ``vX.Y`` markers as a final fallback.

    Args:
        html: HTML страницы Confluence с вкладками или заголовками h1.

    Returns:
        Словарь ``{имя_платформы: контент}``. Платформы без контента
        в результат не включаются.
    """
    if not html:
        return {}

    return parse_page_sections(html)
