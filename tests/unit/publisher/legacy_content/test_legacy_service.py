"""Unit-тесты для extract_for_platform (legacy_service).

Покрывает:
- Возвращает {} при пустом existing_html.
- Исключает любую секцию, чьё имя оканчивается на строку версии (совпадение по суффиксу).
- Возвращает все секции, кроме текущей платформы.
- Возвращает {} если присутствует только секция текущей платформы.
- Корректно работает с legacy-форматом заголовков h1.
"""

from __future__ import annotations
import pytest

from autodoc.publisher.legacy_content.legacy_service import extract_for_platform
from tests.unit.publisher.fixtures.shared_html import (
    H1_HTML,
    H2_VERSION_HTML,
    TAB_HTML_CUSTOM_OS,
    TAB_HTML_MULTI,
    TAB_HTML_SINGLE,
)


@pytest.mark.business_logic
def test_extract_for_platform_returns_empty_on_empty_html() -> None:
    """Возвращает {} при пустой строке existing_html — явное правило раннего выхода."""
    result = extract_for_platform("", "2.0")

    assert result == {}


@pytest.mark.business_logic
def test_extract_for_platform_excludes_current_by_version_suffix() -> None:
    """Исключает вкладку, чьё имя оканчивается на переданную версию."""
    result = extract_for_platform(TAB_HTML_MULTI, "2.0")

    assert "Platform 2.0" not in result
    assert "Platform 2.1" in result


@pytest.mark.business_logic
def test_extract_for_platform_excludes_all_tabs_ending_in_version() -> None:
    """Исключает каждую вкладку, чьё имя оканчивается на версию, а не только 'Platform X.Y'."""
    result = extract_for_platform(TAB_HTML_CUSTOM_OS, "2.0")

    # Обе вкладки, оканчивающиеся на "2.0", должны быть исключены
    assert "Platform 2.0" not in result
    assert "CustomOS 2.0" not in result


@pytest.mark.business_logic
def test_extract_for_platform_returns_all_other_platforms() -> None:
    """Все вкладки, кроме текущей платформы, возвращаются."""
    result = extract_for_platform(TAB_HTML_MULTI, "2.1")

    assert "Platform 2.0" in result
    assert "Platform 2.1" not in result


@pytest.mark.business_logic
def test_extract_for_platform_returns_empty_if_only_current() -> None:
    """Возвращает {}, если присутствует только секция текущей платформы."""
    result = extract_for_platform(TAB_HTML_SINGLE, "2.0")

    assert result == {}


@pytest.mark.business_logic
def test_extract_for_platform_does_not_exclude_version_with_shared_suffix() -> None:
    """Фильтрация по '2.0' должна сохранить 'Platform 12.0' и исключить только 'Platform 2.0'."""
    html = (
        '<ac:structured-macro ac:name="tab">'
        '<ac:parameter ac:name="name">Platform 2.0</ac:parameter>'
        "<ac:rich-text-body><p>Content 2.0</p></ac:rich-text-body>"
        "</ac:structured-macro>"
        '<ac:structured-macro ac:name="tab">'
        '<ac:parameter ac:name="name">Platform 12.0</ac:parameter>'
        "<ac:rich-text-body><p>Content 12.0</p></ac:rich-text-body>"
        "</ac:structured-macro>"
    )

    result = extract_for_platform(html, "2.0")

    assert "Platform 2.0" not in result
    assert "Platform 12.0" in result


@pytest.mark.business_logic
def test_extract_for_platform_h1_format() -> None:
    """Работает с legacy-форматом заголовков h1, как и с форматом вкладок."""
    result = extract_for_platform(H1_HTML, "2.1")

    assert "Platform 2.0" in result
    assert "Platform 2.1" not in result


@pytest.mark.business_logic
def test_extract_for_platform_falls_back_to_h2_version_headers() -> None:
    """Разбирает страницы в устаревшем формате заголовков h2/h3 с версией (fallback)."""
    result = extract_for_platform(H2_VERSION_HTML, "2.0")

    assert "v1.2" in result
