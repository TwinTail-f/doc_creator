"""Unit tests for extract_for_platform (legacy_service).

Covers:
- Returns {} when existing_html is empty.
- Excludes any section whose name ends with the version string (suffix match).
- Returns all sections except the current platform.
- Returns {} when only the current platform section exists.
- Works correctly with the h1-header legacy format.
"""

from __future__ import annotations
import pytest

from autodoc.publisher.legacy_content.legacy_service import extract_for_platform
from tests.unit.publisher.fixtures.shared_html import (
    H1_HTML,
    TAB_HTML_CUSTOM_OS,
    TAB_HTML_MULTI,
    TAB_HTML_SINGLE,
)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_extract_for_platform_returns_empty_on_empty_html() -> None:
    """Returns {} when existing_html is an empty string."""
    result = extract_for_platform("", "2.0")

    assert result == {}


@pytest.mark.business_logic
def test_extract_for_platform_excludes_current_by_version_suffix() -> None:
    """Excludes the tab whose name ends with the given version string."""
    result = extract_for_platform(TAB_HTML_MULTI, "2.0")

    assert "Platform 2.0" not in result
    assert "Platform 2.1" in result


@pytest.mark.business_logic
def test_extract_for_platform_excludes_all_tabs_ending_in_version() -> None:
    """Excludes every tab whose name ends with the version string, not just 'Platform X.Y'."""
    result = extract_for_platform(TAB_HTML_CUSTOM_OS, "2.0")

    # Both tabs ending in "2.0" must be excluded
    assert "Platform 2.0" not in result
    assert "CustomOS 2.0" not in result


@pytest.mark.business_logic
def test_extract_for_platform_returns_all_other_platforms() -> None:
    """All tabs except the current platform are returned."""
    result = extract_for_platform(TAB_HTML_MULTI, "2.1")

    assert "Platform 2.0" in result
    assert "Platform 2.1" not in result


@pytest.mark.business_logic
def test_extract_for_platform_returns_empty_if_only_current() -> None:
    """Returns {} when only the current platform section is present."""
    result = extract_for_platform(TAB_HTML_SINGLE, "2.0")

    assert result == {}


@pytest.mark.business_logic
def test_extract_for_platform_does_not_exclude_version_with_shared_suffix() -> None:
    """Filtering by '2.0' must keep 'Platform 12.0' and exclude only 'Platform 2.0'."""
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
    """Works with h1-header legacy format as well as tab format."""
    result = extract_for_platform(H1_HTML, "2.1")

    assert "Platform 2.0" in result
    assert "Platform 2.1" not in result
