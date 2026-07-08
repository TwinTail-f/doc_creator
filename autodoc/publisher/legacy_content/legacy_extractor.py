"""Извлечение legacy-контента из Confluence Storage Format."""

from autodoc.publisher.legacy_content.html_utils import parse_page_sections


def extract_platform_versions(html: str) -> dict[str, str]:
    """
    Определяет все платформенные версии в HTML и извлекает их контент.

    Args:
        html: HTML страницы Confluence с вкладками или заголовками h1.

    Returns:
        Словарь ``{имя_платформы: контент}``. Платформы без контента
        в результат не включаются.
    """
    if not html:
        return {}

    return parse_page_sections(html)
