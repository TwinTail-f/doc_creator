"""Unit-тесты для функций legacy_extractor.

extract_platform_versions() — тонкая обёртка над parse_page_sections()
(html_utils): вся логика разбора вкладок/заголовков уже покрыта тестами
tests/unit/publisher/legacy_content/test_html_utils.py. Здесь проверяется
только собственная логика обёртки — ранний выход на пустом HTML — и один
happy-path тест, фиксирующий факт делегирования в parse_page_sections().

Покрывает:
- extract_platform_versions() возвращает {} на пустом HTML.
- extract_platform_versions() возвращает все имена вкладок в качестве ключей словаря
  (подтверждение делегирования в parse_page_sections()).
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


TAB_HTML_MULTI = _html("tab_multi.html")


@pytest.mark.business_logic
def test_extract_platform_versions_returns_all_tabs() -> None:
    """Возвращает словарь с одним ключом на каждое отдельное имя вкладки в HTML
    (делегирует разбор в parse_page_sections())."""
    result = extract_platform_versions(TAB_HTML_MULTI)

    assert set(result.keys()) == {"Platform 2.0", "Platform 2.1"}


@pytest.mark.business_logic
def test_extract_platform_versions_empty_html_returns_empty_dict() -> None:
    """Возвращает {} на пустом HTML — отсутствие контента означает отсутствие платформ."""
    result = extract_platform_versions("")

    assert result == {}
