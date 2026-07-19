"""Прямые unit-тесты для html_utils.py.

Покрывает find_h1_sections, extract_platform_h1_sections, extract_tab_sections
и parse_page_sections — публичный API модуля, построенного поверх bs4
(BeautifulSoup).
"""
from pathlib import Path

import pytest
from bs4 import BeautifulSoup, Tag

from autodoc.publisher.legacy_content.html_utils import (
    extract_platform_h1_sections,
    extract_tab_sections,
    find_h1_sections,
    parse_page_sections,
)

# tests/unit/publisher/resources/html/
_HTML_DIR = Path(__file__).resolve().parents[1] / "resources" / "html"


def _html(filename: str) -> str:
    """Читает HTML-фикстуру из tests/unit/publisher/resources/html/<filename>."""
    return (_HTML_DIR / filename).read_text(encoding="utf-8").strip("\n")


H1_HTML = _html("h1_sections.html")
H2_VERSION_HTML = _html("h2_version.html")
TAB_HTML_DUPLICATE_NAMES = _html("tab_duplicate_names.html")
TAB_HTML_MULTI = _html("tab_multi.html")
TAB_HTML_NESTED = _html("tab_nested.html")
TAB_HTML_NO_BODY = _html("tab_no_body.html")
TAB_HTML_SINGLE = _html("tab_single.html")
TAB_HTML_TITLE_ATTRIBUTE = _html("tab_title_attribute.html")
TAB_HTML_BLANK_NAME = _html("tab_blank_name.html")
TABS_GROUP_HTML = _html("tabs_group.html")


# find_h1_sections
@pytest.mark.infrastructure
def test_find_h1_sections_empty_when_no_h1() -> None:
    """Возвращает пустой список при отсутствии тегов <h1>."""
    assert find_h1_sections("<p>no headings here</p>") == []


@pytest.mark.infrastructure
def test_find_h1_sections_returns_tags_in_document_order() -> None:
    """Возвращает теги <h1> в порядке их появления в документе."""
    html = "<h1>Platform 2.0</h1><p>body</p><h1>Platform 2.1</h1>"
    sections = find_h1_sections(html)

    assert len(sections) == 2
    assert all(isinstance(tag, Tag) for tag in sections)
    assert [tag.get_text() for tag in sections] == ["Platform 2.0", "Platform 2.1"]


@pytest.mark.infrastructure
def test_find_h1_sections_strips_inner_html_tags_from_text() -> None:
    """get_text() тега h1 не содержит вложенную разметку, только текст."""
    html = "<h1><strong>Bold Title</strong></h1>"
    sections = find_h1_sections(html)

    assert len(sections) == 1
    assert sections[0].get_text() == "Bold Title"


@pytest.mark.infrastructure
def test_find_h1_sections_accepts_beautifulsoup_instance_directly() -> None:
    """Принимает уже созданный объект BeautifulSoup, а не только строку."""
    soup = BeautifulSoup("<h1>Platform 2.0</h1>", "html.parser")
    sections = find_h1_sections(soup)

    assert len(sections) == 1
    assert sections[0].get_text() == "Platform 2.0"


# extract_platform_h1_sections
@pytest.mark.business_logic
def test_extract_platform_h1_sections_returns_content_by_platform_version() -> None:
    """Разбивает документ на секции по заголовкам h1 вида 'Platform X.Y'."""
    result = extract_platform_h1_sections(H1_HTML)

    assert set(result.keys()) == {"Platform 2.0", "Platform 2.1"}
    assert "Legacy content 2.0" in result["Platform 2.0"]
    assert "Legacy content 2.1" in result["Platform 2.1"]


@pytest.mark.business_logic
def test_extract_platform_h1_sections_last_section_runs_to_end_of_document() -> None:
    """Последняя секция включает весь контент до конца документа."""
    html = "<h1>Platform 2.0</h1><p>first</p><h1>Platform 2.1</h1><p>second</p><p>tail</p>"
    result = extract_platform_h1_sections(html)

    assert "second" in result["Platform 2.1"]
    assert "tail" in result["Platform 2.1"]


@pytest.mark.business_logic
def test_extract_platform_h1_sections_ignores_h1_without_platform_pattern() -> None:
    """Заголовки h1, не соответствующие шаблону 'Platform X.Y', игнорируются."""
    result = extract_platform_h1_sections("<h1>Random Title</h1><p>x</p>")

    assert result == {}


@pytest.mark.business_logic
def test_extract_platform_h1_sections_skips_section_with_no_content() -> None:
    """Секция без контента между заголовками h1 не попадает в результат."""
    html = "<h1>Platform 2.0</h1><h1>Platform 2.1</h1><p>only content</p>"
    result = extract_platform_h1_sections(html)

    assert "Platform 2.0" not in result
    assert "Platform 2.1" in result


# extract_tab_sections
@pytest.mark.infrastructure
def test_extract_tab_sections_empty_string_returns_empty_dict() -> None:
    """Возвращает {} на пустой строке."""
    assert extract_tab_sections("") == {}


@pytest.mark.business_logic
def test_extract_tab_sections_returns_content_for_single_tab() -> None:
    """Возвращает содержимое единственной вкладки по её имени."""
    result = extract_tab_sections(TAB_HTML_SINGLE)

    assert result == {"Platform 2.0": "<p>Content 2.0</p>"}


@pytest.mark.business_logic
def test_extract_tab_sections_returns_one_entry_per_tab() -> None:
    """Возвращает словарь с одним ключом на каждую отдельную вкладку в HTML."""
    result = extract_tab_sections(TAB_HTML_MULTI)

    assert set(result.keys()) == {"Platform 2.0", "Platform 2.1"}


@pytest.mark.business_logic
def test_extract_tab_sections_deduplicates_identical_names_first_wins() -> None:
    """При совпадении имён двух вкладок побеждает первая по порядку."""
    result = extract_tab_sections(TAB_HTML_DUPLICATE_NAMES)

    assert list(result.keys()).count("Platform 2.0") == 1
    assert "First" in result["Platform 2.0"]


@pytest.mark.business_logic
def test_extract_tab_sections_ignores_title_attribute() -> None:
    """ac:name="title" не распознаётся как имя вкладки — поддерживается только ac:name="name".

    Атрибут title= принадлежит expand-макросам, а не вкладкам. Его ошибочное
    распознавание как имени вкладки приводило к ложным срабатываниям при
    fallback-разборе секций, поэтому имя вкладки ищется строго через
    <ac:parameter ac:name="name">.
    """
    result = extract_tab_sections(TAB_HTML_TITLE_ATTRIBUTE)

    assert "My Tab" not in result


@pytest.mark.business_logic
def test_extract_tab_sections_skips_tab_with_no_rich_text_body() -> None:
    """Вкладка без <ac:rich-text-body> не включается в результат."""
    result = extract_tab_sections(TAB_HTML_NO_BODY)

    assert "Platform 9.9" not in result


@pytest.mark.business_logic
def test_extract_tab_sections_does_not_treat_tabs_group_as_tab() -> None:
    """Макрос "tabs-group" не должен ошибочно распознаваться как макрос "tab"."""
    result = extract_tab_sections(TABS_GROUP_HTML)

    assert result == {}


@pytest.mark.business_logic
def test_extract_tab_sections_preserves_nested_rich_text_body() -> None:
    """Вложенный <ac:rich-text-body> (например, внутри таблицы) не обрезает контент вкладки.

    Ищется только прямой (не рекурсивный) дочерний <ac:rich-text-body>
    макроса вкладки, но его содержимое включает вложенные rich-text-body
    целиком, как есть.
    """
    result = extract_tab_sections(TAB_HTML_NESTED)

    assert "inner" in result["Platform 2.0"]
    assert "outer" in result["Platform 2.0"]


@pytest.mark.business_logic
def test_extract_tab_sections_skips_pane_with_blank_name() -> None:
    """Вкладка с пустым (после strip) именем не включается в результат."""
    result = extract_tab_sections(TAB_HTML_BLANK_NAME)

    assert result == {}


# parse_page_sections
@pytest.mark.business_logic
def test_parse_page_sections_empty_html_returns_empty_dict() -> None:
    """Возвращает {} на пустом HTML — отсутствие контента означает отсутствие секций."""
    assert parse_page_sections("") == {}


@pytest.mark.business_logic
def test_parse_page_sections_prefers_tabs_over_h1_and_h2() -> None:
    """Вкладки Confluence имеют наивысший приоритет среди стратегий разбора."""
    result = parse_page_sections(TAB_HTML_MULTI)

    assert set(result.keys()) == {"Platform 2.0", "Platform 2.1"}


@pytest.mark.business_logic
def test_parse_page_sections_falls_back_to_h1_when_no_tabs() -> None:
    """Переключается на разбор заголовков h1 Platform, если вкладки не найдены."""
    result = parse_page_sections(H1_HTML)

    assert set(result.keys()) == {"Platform 2.0", "Platform 2.1"}


@pytest.mark.business_logic
def test_parse_page_sections_falls_back_to_h2_h3_when_no_tabs_or_h1() -> None:
    """Переключается на разбор заголовков h2/h3 с версией, если нет ни вкладок, ни h1 Platform."""
    result = parse_page_sections(H2_VERSION_HTML)

    assert "v1.2" in result
    assert "content for v1.2" in result["v1.2"]


@pytest.mark.business_logic
def test_parse_page_sections_h2_fallback_keeps_preamble_under_unknown_key() -> None:
    """Контент до первого версионного заголовка сохраняется под ключом 'unknown'."""
    html = "<p>Intro text</p><h2>v1.0</h2><p>c1</p>"
    result = parse_page_sections(html)

    assert "unknown" in result
    assert "Intro text" in result["unknown"]
    assert "v1.0" in result


@pytest.mark.business_logic
def test_parse_page_sections_returns_empty_dict_when_nothing_matches() -> None:
    """Возвращает {}, если ни одна из стратегий разбора не дала результата.

    ``_parse_h2_version_sections`` в этом случае возвращает документ целиком
    под ключом 'unknown', поэтому пустой результат возможен только когда
    сам HTML пуст (см. test_parse_page_sections_empty_html_returns_empty_dict).
    """
    result = parse_page_sections("<p>plain paragraph, no headings at all</p>")

    assert result == {"unknown": "<p>plain paragraph, no headings at all</p>"}
