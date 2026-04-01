"""Извлечение legacy-контента из Confluence Storage Format."""
import re

from autodoc.infrastructure.logger import logger


class LegacyContentExtractor:
    """
    Извлекает legacy-контент из HTML Confluence Storage Format.

    Поддерживает формат вкладок (``ac:tab``, ``ac:tab-pane``)
    и заголовочный формат (``h2``/``h3``).
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
            return ''

        tab_marker = '<ac:parameter ac:name="name">%s</ac:parameter>' % platform_name
        start_idx = html.find(tab_marker)
        if start_idx == -1:
            return ''

        open_tag = '<ac:rich-text-body>'
        close_tag = '</ac:rich-text-body>'

        body_start = html.find(open_tag, start_idx)
        if body_start == -1:
            return ''

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
                    return html[body_start + len(open_tag):next_close].strip()

        return ''

    @staticmethod
    def extract_platform_versions(html: str) -> dict[str, str]:
        """
        Автоматически определяет все платформенные версии в HTML и извлекает их контент.

        Находит все имена вкладок через регулярное выражение по тегу
        ``<ac:parameter ac:name="name|title">``, затем для каждого имени
        вызывает ``extract_by_platform_tab``.

        Args:
            html: HTML страницы Confluence с вкладками.

        Returns:
            Словарь ``{имя_платформы: контент}``. Платформы без контента
            в результат не включаются.
        """
        if not html:
            return {}

        tab_name_pattern = r'<ac:parameter ac:name="(?:name|title)">([^<]+)</ac:parameter>'
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

        return result
