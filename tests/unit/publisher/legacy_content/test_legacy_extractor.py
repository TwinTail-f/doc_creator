"""Unit tests for legacy_extractor functions.

Covers:
- extract_platform_versions() returns all tab names as dict keys.
- extract_platform_versions() returns {} on empty HTML.
- extract_platform_versions() falls back to h1-header format when no tabs found.
- extract_platform_versions() skips tabs that have no extractable content.
- extract_platform_versions() de-duplicates tabs with identical names.

NOTE: extract_by_platform_tab() tests were removed — that function no longer
exists in autodoc.publisher.legacy_content.legacy_extractor (codebase has
diverged from this test suite).
"""

from __future__ import annotations
import pytest

from autodoc.publisher.legacy_content.legacy_extractor import (
    extract_platform_versions,
)
from tests.unit.publisher.fixtures.shared_html import (
    H1_HTML,
    TAB_HTML_DUPLICATE_NAMES,
    TAB_HTML_MULTI,
    TAB_HTML_NO_BODY,
)

# ---------------------------------------------------------------------------
# extract_platform_versions() tests
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_extract_platform_versions_returns_all_tabs() -> None:
    """Returns a dict with one key per distinct tab name found in the HTML."""
    result = extract_platform_versions(TAB_HTML_MULTI)

    assert set(result.keys()) == {"Platform 2.0", "Platform 2.1"}


@pytest.mark.infrastructure
def test_extract_platform_versions_empty_html_returns_empty_dict() -> None:
    """Returns {} on empty HTML input."""
    result = extract_platform_versions("")

    assert result == {}


@pytest.mark.business_logic
def test_extract_platform_versions_fallback_to_h1_when_no_tabs() -> None:
    """Falls back to h1-header parsing when no tab markers are present."""
    result = extract_platform_versions(H1_HTML)

    assert "Platform 2.0" in result
    assert "Platform 2.1" in result


@pytest.mark.business_logic
def test_extract_platform_versions_skips_tabs_with_no_content() -> None:
    """Tabs that have no extractable body content are excluded from the result."""
    result = extract_platform_versions(TAB_HTML_NO_BODY)

    assert "Platform 9.9" not in result


@pytest.mark.business_logic
def test_extract_platform_versions_no_duplicate_names() -> None:
    """HTML with two identically-named tabs produces only one entry in the result."""
    result = extract_platform_versions(TAB_HTML_DUPLICATE_NAMES)

    # The key appears exactly once regardless of how many duplicate tabs exist
    keys = list(result.keys())
    assert keys.count("Platform 2.0") == 1
