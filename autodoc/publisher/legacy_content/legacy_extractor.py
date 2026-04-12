"""Извлечение legacy-контента из Confluence Storage Format."""

import re

from autodoc.infrastructure.logger import logger

_H1_OPEN_RE = re.compile(r"<h1\b[^>]*>")
_INNER_TAG_RE = re.compile(r"<[^>]+>")
_PLATFORM_VERSION_RE = re.compile(r"Platform\s+[\d.]+")


class LegacyContentExtractor:
    """
    Извлекает legacy-контент из HTML Confluence Storage Format.

    Поддерживает два формата:
    - Формат вкладок (``ac:tab``, ``ac:tab-pane``) — страницы, сгенерированные
      текущим инструментом.
    - Формат заголовков ``<h1>Platform X.Y</h1>`` — устаревшие страницы,
      написанные вручную. Контент каждой платформы определяется как всё,
      что находится между закрывающим тегом ``</h1>`` заголовка платформы
      и открывающим тегом следующего ``<h1>`` (включая «Уязвимости»
      как естественную границу секции).
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

        tab_marker = '<ac:parameter ac:name="name">%s</ac:parameter>' % platform_name
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
        ``_find_platform_h1_sections``, который разбирает устаревшие страницы
        по заголовкам ``<h1>Platform X.Y</h1>``.

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
        return LegacyContentExtractor._find_platform_h1_sections(html)

    @staticmethod
    def _find_platform_h1_sections(html: str) -> dict[str, str]:
        """
        Извлекает секции платформ из страниц с заголовками ``<h1>Platform X.Y</h1>``.

        Находит все теги ``<h1>`` в документе, определяет их текстовое
        содержимое (вложенные теги удаляются), проверяет совпадение
        с паттерном ``Platform X.Y``. Контент каждой платформенной секции —
        всё от закрывающего ``</h1>`` заголовка до открывающего ``<h1>``
        следующего раздела (раздел «Уязвимости» служит естественной границей).

        Пример входного формата::

            <h1>Platform 1.6<ac:structured-macro .../></h1>
            <h2>Бинарная совместимость</h2>
            ...
            <h1>Уязвимости</h1>
            ...
            <h1>Platform 2.0<ac:structured-macro .../></h1>
            ...

        Args:
            html: HTML страницы в Confluence Storage Format.

        Returns:
            Словарь ``{имя_платформы: html_контент}``, например
            ``{'Platform 1.6': '...', 'Platform 2.0': '...'}``.
        """
        # Собираем позиции всех h1: (начало тега, конец закрывающего </h1>, текст)
        h1_positions: list[tuple[int, int, str]] = []
        for m in _H1_OPEN_RE.finditer(html):
            close_pos = html.find("</h1>", m.end())
            if close_pos == -1:
                continue
            inner = html[m.end() : close_pos]
            text = _INNER_TAG_RE.sub("", inner).strip()
            h1_positions.append((m.start(), close_pos + len("</h1>"), text))

        sections: dict[str, str] = {}
        for i, (_, h1_after, text) in enumerate(h1_positions):
            platform_match = _PLATFORM_VERSION_RE.search(text)
            if not platform_match:
                continue
            platform_name = platform_match.group(0)  # e.g. "Platform 1.6"

            # Контент: от конца этого h1 до начала следующего h1
            content_end = (
                h1_positions[i + 1][0] if i + 1 < len(h1_positions) else len(html)
            )
            content = html[h1_after:content_end].strip()
            if content:
                sections[platform_name] = content

        if sections:
            logger.debug(
                f"Извлечено {len(sections)} секций из заголовков h1 Platform"
            )
        return sections