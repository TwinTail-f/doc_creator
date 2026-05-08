"""Слияние legacy-контента платформ с новым сгенерированным контентом."""

    """Converts version string segments to ints for correct numeric ordering."""
    return [int(x) for x in _VERSION_SORT_RE.findall(item[0])]


def parse_page_content_into_sections(html: str) -> dict[str, str]:
    """
    Разбирает HTML существующей страницы на секции по версиям платформы.

    Delegates to ``parse_page_sections`` from ``_html_utils``,
    which tries tab format first, then ``<h1>Platform X.Y</h1>`` headers,
    then h2/h3 headers with ``vX.Y`` markers as a final fallback.

    Args:
        html: HTML страницы Confluence (Confluence Storage Format).

    Returns:
        Словарь ``{имя_версии: html_контент}``.
    """
    if not html:
        return {}

    logger.debug("Разбор страницы на секции версий")

    sections = parse_page_sections(html)
    if sections:
        logger.debug(f"Разобрано {len(sections)} секций")
    return sections


def merge_by_tabs(
    new_html: str,
    legacy_contents: dict[str, str],
    current_platform: str,
) -> str:
    """
    Объединяет новый контент с legacy-секциями платформ через вкладки Confluence.

    Если новый HTML уже содержит макрос ``tabs-group`` (т.е. Jinja2-шаблон
    сам управляет вкладками), возвращает ``new_html`` без изменений во
    избежание двойного оборачивания.

    Порядок вкладок: текущая платформа идёт первой, остальные — в обратном
    алфавитном порядке (чтобы более новые версии шли раньше).

    Args:
        new_html: Свежеотрендеренный HTML для текущей платформы.
        legacy_contents: Словарь ``{имя_платформы: html}`` для старых платформ.
        current_platform: Отображаемое имя вкладки текущей платформы
                          (например ``'Платформа 2.2'``).

    Returns:
        HTML со всеми платформами, обёрнутый в макрос ``tabs-group``,
        или ``new_html`` без изменений если вкладки уже есть в шаблоне.
    """
    if not legacy_contents:
        logger.debug("Нет legacy-контента, возврат нового HTML")
        return new_html

    if _TAG_TABS_GROUP in new_html:
        logger.info("Шаблон уже содержит tabs-group, пропуск оборачивания")
        return new_html

    tabs_html = _TAG_TABS_GROUP + "\n"
    tabs_html += _render_tab(current_platform, new_html)

    for version_name, content in sorted(
        legacy_contents.items(), key=_version_sort_key, reverse=True
    ):
        if version_name.lower() != current_platform.lower():
            tabs_html += _render_tab(version_name, content)

    tabs_html += "</ac:structured-macro>"
    logger.info(f"Объединено {len(legacy_contents)} legacy-секций с новым контентом")
    return tabs_html


def _render_tab(name: str, content: str) -> str:
    """
    Формирует HTML одной вкладки Confluence.

    Args:
        name: Отображаемое имя вкладки.
        content: HTML-содержимое вкладки.

    Returns:
        Строка с разметкой вкладки ``ac:structured-macro ac:name="tab"``.
    """
    return (
        '  <ac:structured-macro ac:name="tab">\n'
        f'    <ac:parameter ac:name="name">{name}</ac:parameter>\n'
        f"    <ac:rich-text-body>\n      {content}\n    </ac:rich-text-body>\n"
        "  </ac:structured-macro>\n"
    )
