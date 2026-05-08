"""Извлечение legacy-контента из Confluence Storage Format."""

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
