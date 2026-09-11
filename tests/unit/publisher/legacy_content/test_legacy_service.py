"""
Unit-тесты для extract_for_platform (legacy_service).

Покрывает:
- Возвращает {} при пустом existing_html.
- Исключает любую секцию, чьё имя оканчивается на строку версии (совпадение по суффиксу).
- Возвращает все секции, кроме текущей платформы.
- Возвращает {} если присутствует только секция текущей платформы.
- Корректно работает с legacy-форматом заголовков h1.
"""

from pathlib import Path

import pytest

from autodoc.publisher.legacy_content.legacy_service import extract_for_platform

# tests/unit/publisher/resources/html/
_HTML_DIR = Path(__file__).resolve().parents[1] / "resources" / "html"


def _html(filename: str) -> str:
    """Читает HTML-фикстуру из tests/unit/publisher/resources/html/<filename>."""
    return (_HTML_DIR / filename).read_text(encoding="utf-8").strip("\n")


H1_HTML = _html("h1_sections.html")
H2_VERSION_HTML = _html("h2_version.html")
TAB_HTML_CUSTOM_OS = _html("tab_custom_os.html")
TAB_HTML_MULTI = _html("tab_multi.html")
TAB_HTML_SINGLE = _html("tab_single.html")
TAB_HTML_SHARED_SUFFIX = _html("tab_shared_suffix.html")


@pytest.mark.business_logic
def test_extract_for_platform_returns_empty_on_empty_html() -> None:
    """Возвращает {} при пустой строке existing_html — явное правило раннего выхода."""
    result = extract_for_platform("", "2.0")

    assert result == {}


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "current_platform_version, expected_excluded, expected_included",
    [
        # Текущая версия "2.0" — исключается вкладка с этим именем, "2.1" остаётся.
        pytest.param("2.0", "Platform 2.0", "Platform 2.1", id="current-2.0"),
        # Зеркальный случай: текущая версия "2.1" — исключается уже она, "2.0" остаётся.
        pytest.param("2.1", "Platform 2.1", "Platform 2.0", id="current-2.1"),
    ],
)
def test_extract_for_platform_excludes_only_current_platform(
    current_platform_version: str, expected_excluded: str, expected_included: str
) -> None:
    """Исключает вкладку, чьё имя оканчивается на переданную текущую версию; остальные возвращаются."""
    result = extract_for_platform(TAB_HTML_MULTI, current_platform_version)

    assert expected_excluded not in result
    assert expected_included in result


@pytest.mark.business_logic
def test_extract_for_platform_excludes_all_tabs_ending_in_version() -> None:
    """Исключает каждую вкладку, чьё имя оканчивается на версию, а не только 'Platform X.Y'."""
    result = extract_for_platform(TAB_HTML_CUSTOM_OS, "2.0")

    # Обе вкладки, оканчивающиеся на "2.0", должны быть исключены
    assert "Platform 2.0" not in result
    assert "CustomOS 2.0" not in result


@pytest.mark.business_logic
def test_extract_for_platform_returns_empty_if_only_current() -> None:
    """Возвращает {}, если присутствует только секция текущей платформы."""
    result = extract_for_platform(TAB_HTML_SINGLE, "2.0")

    assert result == {}


@pytest.mark.business_logic
def test_extract_for_platform_does_not_exclude_version_with_shared_suffix() -> None:
    """Фильтрация по '2.0' должна сохранить 'Platform 12.0' и исключить только 'Platform 2.0'."""
    result = extract_for_platform(TAB_HTML_SHARED_SUFFIX, "2.0")

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
