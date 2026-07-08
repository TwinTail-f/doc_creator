"""
Общие утилиты разбора HTML для обработки legacy-контента Confluence.

Содержит скомпилированные regex-паттерны, depth-balanced экстрактор
rich-text-body и общие алгоритмы извлечения секций, используемые
legacy_extractor.

Публичное API модуля:
    extract_rich_text_body       — depth-balanced извлечение <ac:rich-text-body>
    extract_tab_sections         — парсинг вкладок Confluence в {name: content}
    extract_platform_h1_sections — парсинг секций Platform X.Y по <h1>
    find_h1_sections             — сканирование всех <h1> в документе
    parse_page_sections          — единый парсер с fallback (вкладки → h1 → h2/h3)
"""

import re
from typing import NamedTuple

from autodoc.common.logger import logger

H1_OPEN_RE: re.Pattern[str] = re.compile(r"<h1\b[^>]*>")
INNER_TAG_RE: re.Pattern[str] = re.compile(r"<[^>]+>")

# Используется только внутри модуля для фильтрации Platform-заголовков.
_PLATFORM_VERSION_RE: re.Pattern[str] = re.compile(r"Platform\s+[\d.]+")

# Находит имя вкладки через <ac:parameter ac:name="name">.
# Намеренно не матчит ac:name="title" — это атрибут expand-макросов, а не вкладок.
_TAB_NAME_RE: re.Pattern[str] = re.compile(r'<ac:parameter ac:name="name">([^<]+)</ac:parameter>')

# Маркеры настоящих tab-макросов Confluence (используются в guard-проверке).
# Не содержат закрывающего '>' — Confluence при сохранении добавляет атрибуты
# ac:schema-version и ac:macro-id, поэтому полное совпадение с '>' не работает.
_TAG_TAB: str = '<ac:structured-macro ac:name="tab"'
_TAG_TAB_PANE: str = '<ac:structured-macro ac:name="tab-pane"'

_RICH_TEXT_BODY_OPEN: str = "<ac:rich-text-body>"
_RICH_TEXT_BODY_CLOSE: str = "</ac:rich-text-body>"


class _H1Section(NamedTuple):
    """Внутренняя запись одного разобранного элемента h1."""

    tag_start: int  # индекс открывающего тега <h1...>
    tag_end: int  # индекс сразу после закрывающего </h1>
    text: str  # внутренний текст h1 (теги удалены)


def find_h1_sections(html: str) -> list[_H1Section]:
    """
    Сканирует *html* и возвращает метаданные каждого найденного элемента ``<h1>``.

    Args:
        html: Полный HTML-документ в Confluence Storage Format.

    Returns:
        Список кортежей ``_H1Section`` в порядке документа.
        Пустой список, если элементов ``<h1>`` нет.
    """
    sections: list[_H1Section] = []
    for m in H1_OPEN_RE.finditer(html):
        close_pos = html.find("</h1>", m.end())
        if close_pos == -1:
            continue
        inner = html[m.end() : close_pos]
        text = INNER_TAG_RE.sub("", inner).strip()
        sections.append(_H1Section(m.start(), close_pos + len("</h1>"), text))
    return sections


def extract_platform_h1_sections(html: str) -> dict[str, str]:
    """
    Извлекает секции ``Platform X.Y`` из страниц по заголовкам ``<h1>``.

    Args:
        html: Полный HTML-документ в Confluence Storage Format.

    Returns:
        Словарь ``{имя_платформы: html_контент}``.
        Пустой словарь, если подходящих заголовков не найдено.
    """
    h1_list = find_h1_sections(html)
    result: dict[str, str] = {}

    for i, section in enumerate(h1_list):
        match = _PLATFORM_VERSION_RE.search(section.text)
        if not match:
            continue
        platform_name = match.group(0)
        content_end = h1_list[i + 1].tag_start if i + 1 < len(h1_list) else len(html)
        content = html[section.tag_end : content_end].strip()
        if content:
            result[platform_name] = content

    return result


def extract_rich_text_body(html: str, body_start: int) -> tuple[str, int]:
    """
    Извлекает содержимое ``<ac:rich-text-body>`` с учётом вложенности.

    Args:
        html: Полный HTML документа.
        body_start: Индекс открывающего тега ``<ac:rich-text-body>``.

    Returns:
        Кортеж ``(content, end_idx)``:

        - ``content`` — строка содержимого без обрамляющих тегов;
          пустая строка, если найти границы не удалось.
        - ``end_idx`` — индекс за закрывающим тегом; используется как
          следующая позиция поиска в вызывающем коде.
    """
    depth = 0
    search_idx = body_start

    while search_idx < len(html):
        next_open = html.find(_RICH_TEXT_BODY_OPEN, search_idx)
        next_close = html.find(_RICH_TEXT_BODY_CLOSE, search_idx)

        if next_close == -1:
            break

        if next_open != -1 and next_open < next_close:
            depth += 1
            search_idx = next_open + len(_RICH_TEXT_BODY_OPEN)
        else:
            depth -= 1
            search_idx = next_close + len(_RICH_TEXT_BODY_CLOSE)
            if depth == 0:
                content = html[body_start + len(_RICH_TEXT_BODY_OPEN) : next_close].strip()
                return content, search_idx

    return "", search_idx


def extract_tab_sections(html: str) -> dict[str, str]:
    """
    Разбирает HTML с вкладками Confluence в словарь ``{имя_вкладки: контент}``.

    Args:
        html: HTML страницы Confluence в Storage Format.

    Returns:
        Словарь ``{имя_вкладки: html_контент}`` в порядке документа.
        Пустой словарь, если вкладок нет или ``html`` пуст.
    """
    if not html:
        return {}

    # Guard: не обрабатывать как вкладки, если в HTML нет настоящих tab-макросов.
    # Без этой проверки другие макросы с <ac:parameter ac:name="title"> (например
    # expand) ложно распознаются как вкладки и мешают fallback на h1-секции.
    if _TAG_TAB not in html and _TAG_TAB_PANE not in html:
        return {}

    # Один проход: собираем уникальные имена вкладок в порядке документа
    seen: dict[str, int] = {}
    for match in _TAB_NAME_RE.finditer(html):
        name = match.group(1).strip()
        if name and name not in seen:
            seen[name] = match.start()

    result: dict[str, str] = {}
    for name, start_idx in seen.items():
        body_start = html.find(_RICH_TEXT_BODY_OPEN, start_idx)
        if body_start == -1:
            continue
        content, _ = extract_rich_text_body(html, body_start)
        if content:
            result[name] = content

    return result


_VERSION_HEADER_PATTERN: str = r"<h[2-3]>.*?([vV][\d.]+).*?</h[2-3]>"
_UNKNOWN_SECTION_KEY: str = "unknown"


def _parse_h2_version_sections(html: str) -> dict[str, str]:
    """
    Исторический fallback: разбирает HTML по заголовкам h2/h3 с маркером vX.Y.

    Args:
        html: HTML страницы в Confluence Storage Format.

    Returns:
        Словарь ``{версия: контент}``.
    """
    sections: dict[str, str] = {}
    current_version = _UNKNOWN_SECTION_KEY
    current_content: list[str] = []

    for line in html.split("\n"):
        version_match = re.search(_VERSION_HEADER_PATTERN, line)
        if version_match:
            if current_content:
                sections[current_version] = "\n".join(current_content).strip()
                current_content = []
            current_version = version_match.group(1)
        current_content.append(line)

    if current_content:
        sections[current_version] = "\n".join(current_content).strip()

    if _UNKNOWN_SECTION_KEY in sections and not sections[_UNKNOWN_SECTION_KEY].strip():
        del sections[_UNKNOWN_SECTION_KEY]

    return sections


def parse_page_sections(html: str) -> dict[str, str]:
    """
    Разбирает страницу Confluence на секции ``{имя_платформы: контент}``.

    Сначала пробует формат вкладок; если не найдено — заголовки ``<h1>Platform X.Y</h1>``;
    затем заголовки h2/h3 с маркерами vX.Y (исторический fallback).
    Возвращает пустой словарь, если ``html`` пуст или секции не найдены.

    Args:
        html: HTML страницы Confluence в Storage Format.

    Returns:
        Словарь ``{имя_секции: html_контент}``.
    """
    if not html:
        return {}
    result = extract_tab_sections(html)
    if result:
        logger.debug(f"Разобрано {len(result)} секций из вкладок")
        return result
    result = extract_platform_h1_sections(html)
    if result:
        logger.debug(f"Разобрано {len(result)} секций из заголовков h1 Platform")
        return result
    result = _parse_h2_version_sections(html)
    if result:
        logger.debug(f"Разобрано {len(result)} секций из заголовков h2/h3")
    return result
