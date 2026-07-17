"""Unit-тесты для функций legacy_extractor.

Покрывает:
- extract_platform_versions() возвращает все имена вкладок в качестве ключей словаря.
- extract_platform_versions() возвращает {} на пустом HTML.
- extract_platform_versions() переключается на формат заголовков h1, если вкладки не найдены.
- extract_platform_versions() пропускает вкладки без извлекаемого содержимого.
- extract_platform_versions() убирает дубликаты вкладок с одинаковыми именами.
"""
from pathlib import Path

import pytest

from autodoc.publisher.legacy_content.legacy_extractor import (
    extract_platform_versions,
)

# tests/unit/publisher/resources/html/
_HTML_DIR = Path(__file__).resolve().parents[1] / "resources" / "html"


def _html(filename: str) -> str:
    """Читает HTML-фикстуру из tests/unit/publisher/resources/html/<filename>."""
    return (_HTML_DIR / filename).read_text(encoding="utf-8").strip("\n")


H1_HTML = _html("h1_sections.html")
TAB_HTML_DUPLICATE_NAMES = _html("tab_duplicate_names.html")
TAB_HTML_MULTI = _html("tab_multi.html")
TAB_HTML_NO_BODY = _html("tab_no_body.html")


@pytest.mark.business_logic
def test_extract_platform_versions_returns_all_tabs() -> None:
    """Возвращает словарь с одним ключом на каждое отдельное имя вкладки в HTML."""
    result = extract_platform_versions(TAB_HTML_MULTI)

    assert set(result.keys()) == {"Platform 2.0", "Platform 2.1"}


@pytest.mark.business_logic
def test_extract_platform_versions_empty_html_returns_empty_dict() -> None:
    """Возвращает {} на пустом HTML — отсутствие контента означает отсутствие платформ."""
    result = extract_platform_versions("")

    assert result == {}


@pytest.mark.business_logic
def test_extract_platform_versions_fallback_to_h1_when_no_tabs() -> None:
    """Переключается на разбор заголовков h1, если маркеры вкладок отсутствуют."""
    result = extract_platform_versions(H1_HTML)

    assert "Platform 2.0" in result
    assert "Platform 2.1" in result


@pytest.mark.business_logic
def test_extract_platform_versions_skips_tabs_with_no_content() -> None:
    """Вкладки без извлекаемого содержимого тела исключаются из результата."""
    result = extract_platform_versions(TAB_HTML_NO_BODY)

    assert "Platform 9.9" not in result


@pytest.mark.business_logic
def test_extract_platform_versions_no_duplicate_names() -> None:
    """HTML с двумя одноимёнными вкладками даёт только одну запись в результате."""
    result = extract_platform_versions(TAB_HTML_DUPLICATE_NAMES)

    # Ключ встречается ровно один раз независимо от числа дублирующих вкладок
    keys = list(result.keys())
    assert keys.count("Platform 2.0") == 1
