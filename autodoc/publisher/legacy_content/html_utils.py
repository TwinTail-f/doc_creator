"""Утилиты парсинга HTML-контента Confluence."""

import re
from collections.abc import Iterable
from itertools import chain, takewhile, zip_longest

from bs4 import BeautifulSoup, Tag
from bs4.element import PageElement

from autodoc.common.logger import logger

_PARSER = "html.parser"

_PLATFORM_VERSION_RE: re.Pattern[str] = re.compile(r"Platform\s+[\d.]+")
_VERSION_RE: re.Pattern[str] = re.compile(r"[vV][\d.]+")
_UNKNOWN_SECTION_KEY: str = "unknown"

# Имена macro, которыми Confluence оформляет отдельную вкладку
_TAB_MACRO_NAMES: frozenset[str] = frozenset({"tab", "tab-pane"})

HtmlOrSoup = str | BeautifulSoup


def _to_bs_obj(html: HtmlOrSoup) -> BeautifulSoup:
    """Преобразует строку в объект BeautifulSoup или возвращает переданный объект.

    Args:
        html: Строка с HTML-разметкой или уже созданный объект BeautifulSoup.

    Returns:
        Объект BeautifulSoup для дальнейшего анализа.
    """
    return html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, _PARSER)


def _html_until(nodes: Iterable[PageElement], stop: Tag | None) -> str:
    """Объединяет строковые представления элементов до указанного тега.

    Args:
        nodes: Последовательность элементов страницы для сериализации.
        stop: Тег, на котором следует прекратить сбор содержимого (не включается).

    Returns:
        Строка с объединенным HTML-контентом.
    """
    content_nodes = takewhile(lambda node: node is not stop, nodes)
    return "".join(str(node) for node in content_nodes).strip()


def find_h1_sections(html: HtmlOrSoup) -> list[Tag]:
    """Находит все теги заголовков h1 в документе.

    Args:
        html: Строка с HTML-разметкой или объект BeautifulSoup.

    Returns:
        Список найденных тегов h1 в порядке их появления.
    """
    return _to_bs_obj(html).find_all("h1")


def extract_platform_h1_sections(html: HtmlOrSoup) -> dict[str, str]:
    """Извлекает секции версий платформы по заголовкам h1.

    Args:
        html: Строка с HTML-разметкой или объект BeautifulSoup.

    Returns:
        Словарь, где ключами являются версии платформы, а значениями — их содержимое.
    """
    h1_list = find_h1_sections(html)
    result: dict[str, str] = {}

    for h1, next_h1 in zip_longest(h1_list, h1_list[1:], fillvalue=None):
        if match := _PLATFORM_VERSION_RE.search(h1.get_text()):
            if content := _html_until(h1.next_siblings, next_h1):
                result[match.group(0)] = content

    return result


def extract_tab_sections(html: HtmlOrSoup) -> dict[str, str]:
    """Извлекает контент из вкладок Confluence.

    Args:
        html: Строка с HTML-разметкой или объект BeautifulSoup.

    Returns:
        Словарь, связывающий названия вкладок с их HTML-содержимым.
    """
    if not html:
        return {}

    soup = _to_bs_obj(html)
    result: dict[str, str] = {}

    for pane in soup.find_all("ac:structured-macro"):
        if pane.get("ac:name") not in _TAB_MACRO_NAMES:
            continue

        name_param = pane.find("ac:parameter", attrs={"ac:name": "name"}, recursive=False)
        name = name_param.get_text().strip() if name_param else ""
        if not name or name in result:
            continue

        body = pane.find("ac:rich-text-body", recursive=False)
        if body and (content := body.decode_contents().strip()):
            result[name] = content

    return result


def _parse_h2_version_sections(html: HtmlOrSoup) -> dict[str, str]:
    """Извлекает секции версий по заголовкам h2 и h3.

    Args:
        html: Строка с HTML-разметкой или объект BeautifulSoup.

    Returns:
        Словарь, где ключами являются найденные версии, а значениями — их содержимое.
    """
    soup = _to_bs_obj(html)
    headers = [
        (h, m.group(0))
        for h in soup.find_all(["h2", "h3"])
        if (m := _VERSION_RE.search(h.get_text()))
    ]

    sections: dict[str, str] = {}

    # Извлекаем преамбулу до первого найденного заголовка версии
    first_header = headers[0][0] if headers else None
    if preamble := _html_until(soup.contents, first_header):
        sections[_UNKNOWN_SECTION_KEY] = preamble

    # Находим контент между заголовками версий
    for (header, version), (next_header, _) in zip_longest(headers, headers[1:], fillvalue=(None, None)):
        if content := _html_until(chain([header], header.next_siblings), next_header):
            sections[version] = content

    return sections


def parse_page_sections(html: str) -> dict[str, str]:
    """Разбирает страницу Confluence на именованные секции.

    Args:
        html: Исходный HTML-код страницы.

    Returns:
        Словарь с содержимым найденных секций.
    """
    if not html:
        return {}

    soup = _to_bs_obj(html)

    if result := extract_tab_sections(soup):
        logger.debug(f"Разобрано {len(result)} секций из вкладок")
        return result

    if result := extract_platform_h1_sections(soup):
        logger.debug(f"Разобрано {len(result)} секций из заголовков h1 Platform")
        return result

    if result := _parse_h2_version_sections(soup):
        logger.debug(f"Разобрано {len(result)} секций из заголовков h2/h3")
        return result

    return {}
