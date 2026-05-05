"""Unit tests for LegacyContentExtractor.

Covers:
- extract_by_platform_tab() returns content for an existing tab.
- extract_by_platform_tab() returns "" for a missing tab.
- extract_by_platform_tab() returns "" on empty HTML.
- extract_by_platform_tab() handles nested <ac:rich-text-body> correctly.
- extract_platform_versions() returns all tab names as dict keys.
- extract_platform_versions() returns {} on empty HTML.
- extract_platform_versions() falls back to h1-header format when no tabs found.
- extract_platform_versions() skips tabs that have no extractable content.
- extract_platform_versions() de-duplicates tabs with identical names.
"""
from __future__ import annotations

from autodoc.publisher.legacy_content.legacy_extractor import LegacyContentExtractor

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

# Tab with no body content (only a parameter, no rich-text-body)
TAB_HTML_NO_BODY: str = (
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">Platform 9.9</ac:parameter>'
    "</ac:structured-macro>"
)

# HTML with two identical tab names
TAB_HTML_DUPLICATE_NAMES: str = (
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">Platform 2.0</ac:parameter>'
    "<ac:rich-text-body><p>First</p></ac:rich-text-body>"
    "</ac:structured-macro>"
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">Platform 2.0</ac:parameter>'
    "<ac:rich-text-body><p>Second</p></ac:rich-text-body>"
    "</ac:structured-macro>"
)

# ---------------------------------------------------------------------------
# extract_by_platform_tab() tests
# ---------------------------------------------------------------------------


def test_extract_by_platform_tab_returns_content_for_existing_tab() -> None:
    """Returns the inner HTML for a tab that exists in the document."""
    result = LegacyContentExtractor.extract_by_platform_tab(
        TAB_HTML_SINGLE, "Platform 2.0"
    )

    assert "<p>Content 2.0</p>" in result


def test_extract_by_platform_tab_returns_empty_for_missing_tab() -> None:
    """Returns "" when the requested platform name is not present."""
    result = LegacyContentExtractor.extract_by_platform_tab(
        TAB_HTML_SINGLE, "Platform 9.9"
    )

    assert result == ""


def test_extract_by_platform_tab_empty_html_returns_empty() -> None:
    """Returns "" when the input HTML is an empty string."""
    result = LegacyContentExtractor.extract_by_platform_tab("", "Platform 2.0")

    assert result == ""


def test_extract_by_platform_tab_handles_nested_rich_text_body() -> None:
    """Depth-balanced extraction does not stop at a nested rich-text-body tag."""
    result = LegacyContentExtractor.extract_by_platform_tab(
        TAB_HTML_NESTED, "Platform 2.0"
    )

    # Both nested and outer content must be present in the result
    assert "<p>inner</p>" in result
    assert "<p>outer</p>" in result


# ---------------------------------------------------------------------------
# extract_platform_versions() tests
# ---------------------------------------------------------------------------


def test_extract_platform_versions_returns_all_tabs() -> None:
    """Returns a dict with one key per distinct tab name found in the HTML."""
    result = LegacyContentExtractor.extract_platform_versions(TAB_HTML_MULTI)

    assert set(result.keys()) == {"Platform 2.0", "Platform 2.1"}


def test_extract_platform_versions_empty_html_returns_empty_dict() -> None:
    """Returns {} on empty HTML input."""
    result = LegacyContentExtractor.extract_platform_versions("")

    assert result == {}


def test_extract_platform_versions_fallback_to_h1_when_no_tabs() -> None:
    """Falls back to h1-header parsing when no tab markers are present."""
    result = LegacyContentExtractor.extract_platform_versions(H1_HTML)

    assert "Platform 2.0" in result
    assert "Platform 2.1" in result


def test_extract_platform_versions_skips_tabs_with_no_content() -> None:
    """Tabs that have no extractable body content are excluded from the result."""
    result = LegacyContentExtractor.extract_platform_versions(TAB_HTML_NO_BODY)

    assert "Platform 9.9" not in result


def test_extract_platform_versions_no_duplicate_names() -> None:
    """HTML with two identically-named tabs produces only one entry in the result."""
    result = LegacyContentExtractor.extract_platform_versions(TAB_HTML_DUPLICATE_NAMES)

    # The key appears exactly once regardless of how many duplicate tabs exist
    keys = list(result.keys())
    assert keys.count("Platform 2.0") == 1
