"""Unit tests for extract_for_platform (legacy_service).

Covers:
- Returns {} when existing_html is empty.
- Excludes the section whose label equals 'Platform <version>' exactly.
- Excludes any section whose name ends with the version string (suffix match).
- Returns all sections except the current platform.
- Returns {} when only the current platform section exists.
- Works correctly with the h1-header legacy format.
"""
from __future__ import annotations

from autodoc.publisher.legacy_content.legacy_service import extract_for_platform

# ---------------------------------------------------------------------------
# HTML constants
# ---------------------------------------------------------------------------

# Minimal HTML with a single "Platform 2.0" tab
TAB_HTML_SINGLE: str = (
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">Platform 2.0</ac:parameter>'
    "<ac:rich-text-body><p>Content 2.0</p></ac:rich-text-body>"
    "</ac:structured-macro>"
)

# HTML with two tabs
TAB_HTML_MULTI: str = (
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">Platform 2.0</ac:parameter>'
    "<ac:rich-text-body><p>Content 2.0</p></ac:rich-text-body>"
    "</ac:structured-macro>"
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">Platform 2.1</ac:parameter>'
    "<ac:rich-text-body><p>Content 2.1</p></ac:rich-text-body>"
    "</ac:structured-macro>"
)

# HTML with nested rich-text-body (table inside a tab)
TAB_HTML_NESTED: str = (
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">Platform 2.0</ac:parameter>'
    "<ac:rich-text-body>"
    "<table><ac:rich-text-body><p>inner</p></ac:rich-text-body></table>"
    "<p>outer</p>"
    "</ac:rich-text-body>"
    "</ac:structured-macro>"
)

# HTML with h1 headers in legacy format
H1_HTML: str = (
    "<h1>Platform 2.0</h1><p>Legacy content 2.0</p>"
    "<h1>Platform 2.1</h1><p>Legacy content 2.1</p>"
)

# HTML with tabs-group (template already manages tabs)
TABS_GROUP_HTML: str = (
    '<ac:structured-macro ac:name="tabs-group"><ac:rich-text-body>'
    "some content"
    "</ac:rich-text-body></ac:structured-macro>"
)

# HTML with an alternative OS name also ending in the version string
TAB_HTML_CUSTOM_OS: str = (
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">Platform 2.0</ac:parameter>'
    "<ac:rich-text-body><p>Content 2.0</p></ac:rich-text-body>"
    "</ac:structured-macro>"
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">CustomOS 2.0</ac:parameter>'
    "<ac:rich-text-body><p>CustomOS content</p></ac:rich-text-body>"
    "</ac:structured-macro>"
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">Platform 2.1</ac:parameter>'
    "<ac:rich-text-body><p>Content 2.1</p></ac:rich-text-body>"
    "</ac:structured-macro>"
)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_extract_for_platform_returns_empty_on_empty_html() -> None:
    """Returns {} when existing_html is an empty string."""
    result = extract_for_platform("", "2.0")

    assert result == {}


def test_extract_for_platform_excludes_current_platform_full_label() -> None:
    """Excludes the tab whose name matches 'Platform <version>' exactly."""
    result = extract_for_platform(TAB_HTML_MULTI, "2.0")

    assert "Platform 2.0" not in result
    assert "Platform 2.1" in result


def test_extract_for_platform_excludes_current_by_version_suffix() -> None:
    """Excludes any tab whose name ends with the given version string."""
    result = extract_for_platform(TAB_HTML_CUSTOM_OS, "2.0")

    # Both tabs ending in "2.0" must be excluded
    assert "Platform 2.0" not in result
    assert "CustomOS 2.0" not in result


def test_extract_for_platform_returns_all_other_platforms() -> None:
    """All tabs except the current platform are returned."""
    result = extract_for_platform(TAB_HTML_MULTI, "2.1")

    assert "Platform 2.0" in result
    assert "Platform 2.1" not in result


def test_extract_for_platform_returns_empty_if_only_current() -> None:
    """Returns {} when only the current platform section is present."""
    result = extract_for_platform(TAB_HTML_SINGLE, "2.0")

    assert result == {}


def test_extract_for_platform_h1_format() -> None:
    """Works with h1-header legacy format as well as tab format."""
    result = extract_for_platform(H1_HTML, "2.1")

    assert "Platform 2.0" in result
    assert "Platform 2.1" not in result
