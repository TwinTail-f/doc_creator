"""
Извлечение legacy-контента из Confluence Storage Format.
"""
import re
from typing import Dict, List, Optional

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

        Args:
            html: HTML в Confluence Storage Format.
            platform_name: Имя платформы (например ``'Platform 2.0'``).

        Returns:
            Содержимое вкладки или пустая строка.
        """
        if not html:
            return ''

        tab_marker = f'<ac:parameter ac:name="name">{platform_name}</ac:parameter>'
        start_idx = html.find(tab_marker)
        if start_idx == -1:
            return ''

        try:
            body_start = html.find('<ac:rich-text-body>', start_idx)
            if body_start == -1:
                return ''

            open_tag = '<ac:rich-text-body>'
            close_tag = '</ac:rich-text-body>'
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

        except Exception as e:
            logger.warning(f'ошибка извлечения вкладки: {e}')
        return ''

    @staticmethod
    def extract_platform_versions(html: str) -> Dict[str, str]:
        """
        Автоматически определяет все платформенные версии в HTML и извлекает их контент.

        Args:
            html: HTML страницы Confluence с вкладками.

        Returns:
            Словарь ``{имя_платформы: контент}``.
        """
        if not html:
            return {}

        pattern = r'<ac:parameter ac:name="(?:name|title)">([^<]+)</ac:parameter>'
        platform_names: List[str] = []
        for match in re.finditer(pattern, html):
            name = match.group(1).strip()
            if name and name not in platform_names:
                platform_names.append(name)

        result: Dict[str, str] = {}
        for name in platform_names:
            content = LegacyContentExtractor.extract_by_platform_tab(html, name)
            if content:
                result[name] = content

        return result
