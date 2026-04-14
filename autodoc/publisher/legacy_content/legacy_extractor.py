"""Извлечение legacy-контента из Confluence Storage Format."""

import re

from autodoc.infrastructure.logger import logger
from autodoc.publisher.legacy_content._html_utils import (
    PLATFORM_VERSION_RE,
    extract_platform_h1_sections,
)


class LegacyContentExtractor:
    """
    Извлекает legacy-контент из HTML Confluence Storage Format.

    Поддерживает два формата:
    - Формат вкладок (``ac:tab``, ``ac:tab-pane``) — страницы, сгенерированные
      текущим инструментом.
    - Формат заголовков ``<h1>Platform X.Y</h1>`` — устаревшие страницы,
      написанные вручную.
    Все методы статические.
    """

    @staticmethod
    def extract_by_platform_tab(html: str, platform_name: str) -> str:
        """
        Извлекает содержимое вкладки для указанной платформы.

        Алгоритм: находит маркер вкладки по имени платформы, затем с помощью
        счётчика глубины ``depth`` балансирует теги ``<ac:rich-text-body>``
        и ``</ac:rich-text-body>``, чтобы корректно обработать вложенные
        rich-text-body (например, внутри таблиц или панелей).

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

        open_tag = "<ac:rich-text-body>"
        close_tag = "</ac:rich-text-body>"

        body_start = html.find(open_tag, start_idx)
        if body_start == -1:
            return ""

        depth = 0
        curr_idx = body_start

        while curr_idx < len(html):
            next_open = html.find(open_tag, curr_idx)
            next_close = html.find(close_tag, curr_idx)

            if next_close == -1:
                break

            if next_open != -1 and next_open < next_close:
                depth += 1
                curr_idx = next_open + len(open_tag)
            else:
                depth -= 1
                curr_idx = next_close + len(close_tag)
                if depth == 0:
                    return html[body_start + len(open_tag) : next_close].strip()

        return ""

    @staticmethod
    def extract_platform_versions(html: str) -> dict[str, str]:
        """
        Автоматически определяет все платформенные версии в HTML и извлекает их контент.

        Сначала пробует формат вкладок: ищет имена через тег
        ``<ac:parameter ac:name="name|title">`` и вызывает
        ``extract_by_platform_tab`` для каждого найденного имени.

        Если вкладочный формат не даёт результата — переходит к fallback:
        ``extract_platform_h1_sections`` из ``_html_utils``, который разбирает
        устаревшие страницы по заголовкам ``<h1>Platform X.Y</h1>``.

        Args:
            html: HTML страницы Confluence с вкладками или заголовками h1.

        Returns:
            Словарь ``{имя_платформы: контент}``. Платформы без контента
            в результат не включаются.
        """
        if not html:
            return {}

        tab_name_pattern = (
            r'<ac:parameter ac:name="(?:name|title)">([^<]+)</ac:parameter>'
        )
        platform_names: list[str] = []
        for match in re.finditer(tab_name_pattern, html):
            name = match.group(1).strip()
            if name and name not in platform_names:
                platform_names.append(name)

        result: dict[str, str] = {}
        for name in platform_names:
            content = LegacyContentExtractor.extract_by_platform_tab(html, name)
            if content:
                result[name] = content

        if result:
            return result

        # Fallback: устаревший формат с заголовками <h1>Platform X.Y</h1>
        sections = extract_platform_h1_sections(html)
        if sections:
            logger.debug(f"Извлечено {len(sections)} секций из заголовков h1 Platform")
        return sections
