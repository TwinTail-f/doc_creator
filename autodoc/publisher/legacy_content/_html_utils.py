"""
Общие утилиты разбора HTML для обработки legacy-контента Confluence.

Содержит скомпилированные regex-паттерны и общий алгоритм извлечения
h1-секций, используемый LegacyContentExtractor и LegacyContentMerger.
"""

import re
from typing import NamedTuple

# Compiled patterns shared across extractor and merger
H1_OPEN_RE: re.Pattern[str] = re.compile(r"<h1\b[^>]*>")
INNER_TAG_RE: re.Pattern[str] = re.compile(r"<[^>]+>")
PLATFORM_VERSION_RE: re.Pattern[str] = re.compile(r"Platform\s+[\d.]+")


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

    Находит элементы h1, текст которых соответствует ``Platform X.Y``,
    затем собирает всё между закрывающим ``</h1>`` этого заголовка и
    началом следующего ``<h1>`` как содержимое секции.

    Args:
        html: Полный HTML-документ в Confluence Storage Format.

    Returns:
        Словарь ``{имя_платформы: html_контент}``.
        Пустой словарь, если подходящих заголовков не найдено.
    """
    h1_list = find_h1_sections(html)
    result: dict[str, str] = {}

    for i, section in enumerate(h1_list):
        match = PLATFORM_VERSION_RE.search(section.text)
        if not match:
            continue
        platform_name = match.group(0)
        content_end = h1_list[i + 1].tag_start if i + 1 < len(h1_list) else len(html)
        content = html[section.tag_end : content_end].strip()
        if content:
            result[platform_name] = content

    return result
