"""Слияние legacy-контента платформ с новым сгенерированным контентом."""
import re
from typing import Dict

from autodoc.infrastructure.logger import logger

_VERSION_HEADER_PATTERN: str = r'<h[2-3]>.*?([vV][\d.]+).*?</h[2-3]>'
_UNKNOWN_SECTION_KEY: str = 'unknown'

_TAG_TAB: str = '<ac:structured-macro ac:name="tab">'
_TAG_TAB_PANE: str = '<ac:structured-macro ac:name="tab-pane">'
_TAG_TABS_GROUP: str = '<ac:structured-macro ac:name="tabs-group">'
_TAG_PARAM_NAME_OPEN: str = '<ac:parameter ac:name="name">'
_TAG_PARAM_CLOSE: str = '</ac:parameter>'
_TAG_BODY_OPEN: str = '<ac:rich-text-body>'
_TAG_BODY_CLOSE: str = '</ac:rich-text-body>'

# Шаг смещения при пропуске нераспознанного фрагмента в цикле разбора вкладок.
_PARSE_SKIP_STEP: int = 10


class LegacyContentMerger:
    """
    Объединяет legacy-контент платформ с новым сгенерированным контентом.

    Сохраняет разделы старых платформ и добавляет раздел новой платформы
    в финальный вывод. Организация через вкладки Confluence (tabs-group/tab).

    Все методы статические — объект не хранит состояния.
    """

    @staticmethod
    def parse_page_content_into_sections(html: str) -> Dict[str, str]:
        """
        Разбирает HTML существующей страницы на секции по версиям платформы.

        Сначала пробует формат вкладок (``ac:structured-macro ac:name="tab"``
        или ``"tab-pane"``). Если вкладки не найдены — fallback на заголовки
        h2/h3 с версионным маркером вида ``v1.2`` или ``V1.2``.

        Балансировка вложенных тегов ``<ac:rich-text-body>`` выполняется
        счётчиком глубины ``depth``, что позволяет корректно извлекать
        контент вкладок, содержащих вложенные макросы.

        Args:
            html: HTML страницы Confluence (Confluence Storage Format).

        Returns:
            Словарь ``{имя_версии: html_контент}``.
        """
        logger.debug('LegacyContentMerger: разбор страницы на секции версий')
        sections: Dict[str, str] = {}

        if _TAG_TAB_PANE in html or _TAG_TAB in html:
            sections = LegacyContentMerger._parse_tab_sections(html)
            if sections:
                return sections

        return LegacyContentMerger._parse_header_sections(html)

    @staticmethod
    def _parse_tab_sections(html: str) -> Dict[str, str]:
        """
        Разбирает HTML на секции по вкладкам Confluence.

        Ищет вкладки формата ``ac:tab`` и ``ac:tab-pane``, извлекает
        имя вкладки и её rich-text-body с учётом вложенности.

        Args:
            html: HTML страницы в Confluence Storage Format.

        Returns:
            Словарь ``{имя_вкладки: html_контент}`` или пустой словарь,
            если вкладки не удалось распознать.
        """
        logger.debug('LegacyContentMerger: обнаружены вкладки, разбор по вкладкам')
        sections: Dict[str, str] = {}
        curr_idx = 0

        while curr_idx < len(html):
            idx_tab = html.find(_TAG_TAB, curr_idx)
            idx_pane = html.find(_TAG_TAB_PANE, curr_idx)
            candidates = [i for i in (idx_tab, idx_pane) if i != -1]
            if not candidates:
                break
            start_idx = min(candidates)

            name_start = html.find(_TAG_PARAM_NAME_OPEN, start_idx)
            if name_start == -1:
                curr_idx = start_idx + _PARSE_SKIP_STEP
                continue
            name_end = html.find(_TAG_PARAM_CLOSE, name_start)
            if name_end == -1:
                curr_idx = start_idx + _PARSE_SKIP_STEP
                continue

            platform_name = html[name_start + len(_TAG_PARAM_NAME_OPEN):name_end].strip()

            body_start = html.find(_TAG_BODY_OPEN, name_end)
            if body_start == -1:
                curr_idx = name_end
                continue

            content, search_idx = LegacyContentMerger._extract_body_content(
                html, body_start
            )

            if content and platform_name:
                sections[platform_name] = content

            curr_idx = search_idx if search_idx > body_start else body_start + _PARSE_SKIP_STEP

        if sections:
            logger.debug(
                'LegacyContentMerger: разобрано %d секций из вкладок', len(sections)
            )
        return sections

    @staticmethod
    def _extract_body_content(html: str, body_start: int) -> tuple[str, int]:
        """
        Извлекает содержимое ``<ac:rich-text-body>`` с учётом вложенности.

        Использует счётчик глубины ``depth`` для корректной балансировки
        вложенных тегов ``<ac:rich-text-body>`` / ``</ac:rich-text-body>``.

        Args:
            html: Полный HTML документа.
            body_start: Индекс открывающего тега ``<ac:rich-text-body>``.

        Returns:
            Кортеж ``(content, end_idx)``:
            - ``content``: строка содержимого без обрамляющих тегов,
              пустая строка если найти границы не удалось.
            - ``end_idx``: индекс за закрывающим тегом, используется как
              следующая позиция поиска в вызывающем цикле.
        """
        depth = 0
        search_idx = body_start

        while search_idx < len(html):
            next_open = html.find(_TAG_BODY_OPEN, search_idx)
            next_close = html.find(_TAG_BODY_CLOSE, search_idx)

            if next_close == -1:
                break

            if next_open != -1 and next_open < next_close:
                depth += 1
                search_idx = next_open + len(_TAG_BODY_OPEN)
            else:
                depth -= 1
                search_idx = next_close + len(_TAG_BODY_CLOSE)
                if depth == 0:
                    content = html[body_start + len(_TAG_BODY_OPEN):next_close].strip()
                    return content, search_idx

        return '', search_idx

    @staticmethod
    def _parse_header_sections(html: str) -> Dict[str, str]:
        """
        Разбирает HTML на секции по заголовкам h2/h3 с версионным маркером.

        Fallback-метод: применяется когда в HTML нет вкладок Confluence.
        Определяет границы секций по строкам вида
        ``<h2>... v1.2 ...</h2>`` или ``<h3>... V2.0 ...</h3>``.

        Пустая секция ``'unknown'`` (контент до первого версионного заголовка)
        из результата удаляется.

        Args:
            html: HTML страницы в Confluence Storage Format.

        Returns:
            Словарь ``{версия: html_контент}``.
        """
        logger.debug('LegacyContentMerger: вкладки не найдены, разбор по заголовкам h2/h3')
        sections: Dict[str, str] = {}
        current_version = _UNKNOWN_SECTION_KEY
        current_content: list[str] = []

        for line in html.split('\n'):
            version_match = re.search(_VERSION_HEADER_PATTERN, line)
            if version_match:
                if current_content:
                    sections[current_version] = '\n'.join(current_content).strip()
                    current_content = []
                current_version = version_match.group(1)
            current_content.append(line)

        if current_content:
            sections[current_version] = '\n'.join(current_content).strip()

        if _UNKNOWN_SECTION_KEY in sections and not sections[_UNKNOWN_SECTION_KEY].strip():
            del sections[_UNKNOWN_SECTION_KEY]

        logger.debug(
            'LegacyContentMerger: разобрано %d секций из заголовков', len(sections)
        )
        return sections

    @staticmethod
    def merge_by_tabs(
        new_html: str,
        legacy_contents: Dict[str, str],
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
            logger.debug('LegacyContentMerger: нет legacy-контента, возврат нового HTML')
            return new_html

        if _TAG_TABS_GROUP in new_html:
            logger.info(
                'LegacyContentMerger: шаблон уже содержит tabs-group, пропуск оборачивания'
            )
            return new_html

        tabs_html = _TAG_TABS_GROUP + '\n'
        tabs_html += LegacyContentMerger._render_tab(current_platform, new_html)

        for version_name, content in sorted(legacy_contents.items(), reverse=True):
            if version_name.lower() != current_platform.lower():
                tabs_html += LegacyContentMerger._render_tab(version_name, content)

        tabs_html += '</ac:structured-macro>'
        logger.info(
            'LegacyContentMerger: объединено %d legacy-секций с новым контентом',
            len(legacy_contents),
        )
        return tabs_html

    @staticmethod
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
            '    <ac:parameter ac:name="name">%s</ac:parameter>\n'
            '    <ac:rich-text-body>\n      %s\n    </ac:rich-text-body>\n'
            '  </ac:structured-macro>\n'
        ) % (name, content)
