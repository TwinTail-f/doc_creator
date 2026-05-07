"""Unit tests for LegacyContentMerger.

Covers merge_by_tabs():
- Returns new_html unchanged when legacy_contents is empty.
- Returns new_html unchanged when it already contains a tabs-group macro.
- Wraps result in a tabs-group macro when legacy content is present.
- Current platform tab is positioned first in the output.
- Legacy tabs are ordered in reverse alphabetical order after the current tab.
- Current platform is not duplicated when it also appears in legacy_contents.

Covers parse_page_content_into_sections():
- Parses tabs-format HTML into a dict with one key per tab.
- Falls back to h1-header parsing when no tabs are present.
- Returns {} on empty HTML.
- Falls back to h2/h3-header parsing with vX.Y version markers.
"""

from __future__ import annotations

from autodoc.publisher.legacy_content.legacy_merger import LegacyContentMerger

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

# HTML with h2 version header
H2_VERSION_HTML: str = "<h2>v1.2</h2>\n<p>content for v1.2</p>"

# Marker present in every tabs-group macro
_TABS_GROUP_MARKER: str = 'ac:name="tabs-group"'

# ---------------------------------------------------------------------------
# merge_by_tabs() tests
# ---------------------------------------------------------------------------


def test_merge_by_tabs_returns_new_html_if_no_legacy() -> None:
    """Returns new_html unchanged when legacy_contents is empty."""
    new_html = "<p>new content</p>"

    result = LegacyContentMerger.merge_by_tabs(new_html, {}, "Platform 2.1")

    assert result == new_html


def test_merge_by_tabs_returns_new_html_if_already_has_tabs_group() -> None:
    """Returns new_html unchanged when it already contains a tabs-group macro."""
    legacy = {"Platform 2.0": "<p>old</p>"}

    result = LegacyContentMerger.merge_by_tabs(TABS_GROUP_HTML, legacy, "Platform 2.1")

    assert result == TABS_GROUP_HTML


def test_merge_by_tabs_wraps_in_tabs_group_macro() -> None:
    """Wraps the combined output in a Confluence tabs-group macro."""
    legacy = {"Platform 2.0": "<p>old</p>"}
    new_html = "<p>new</p>"

    result = LegacyContentMerger.merge_by_tabs(new_html, legacy, "Platform 2.1")

    assert _TABS_GROUP_MARKER in result


def test_merge_by_tabs_current_platform_tab_is_first() -> None:
    """Current platform tab must appear before all legacy tabs."""
    legacy = {"Platform 2.0": "<p>old</p>"}
    current_platform = "Platform 2.1"
    new_html = "<p>new</p>"

    result = LegacyContentMerger.merge_by_tabs(new_html, legacy, current_platform)

    idx_current = result.index(f">{current_platform}<")
    idx_legacy = result.index(">Platform 2.0<")
    assert idx_current < idx_legacy


def test_merge_by_tabs_legacy_tabs_in_reverse_alphabetical_order() -> None:
    """Legacy tabs follow the current tab in reverse alphabetical order."""
    legacy = {"Platform 2.0": "a", "Platform 2.1": "b"}
    current_platform = "Platform 2.2"
    new_html = "<p>new</p>"

    result = LegacyContentMerger.merge_by_tabs(new_html, legacy, current_platform)

    idx_21 = result.index(">Platform 2.1<")
    idx_20 = result.index(">Platform 2.0<")
    # 2.1 must appear before 2.0 (reverse alphabetical)
    assert idx_21 < idx_20


def test_merge_by_tabs_does_not_duplicate_current_platform() -> None:
    """Current platform is not duplicated even if it appears in legacy_contents."""
    current_platform = "Platform 2.1"
    legacy = {current_platform: "<p>old 2.1</p>", "Platform 2.0": "<p>old 2.0</p>"}
    new_html = "<p>new 2.1</p>"

    result = LegacyContentMerger.merge_by_tabs(new_html, legacy, current_platform)

    # Tab with current platform name must appear exactly once
    assert result.count(f">{current_platform}<") == 1


# ---------------------------------------------------------------------------
# parse_page_content_into_sections() tests
# ---------------------------------------------------------------------------


def test_parse_page_content_into_sections_from_tabs() -> None:
    """Parses multi-tab HTML into a dict with one key per tab."""
    result = LegacyContentMerger.parse_page_content_into_sections(TAB_HTML_MULTI)

    assert set(result.keys()) == {"Platform 2.0", "Platform 2.1"}


def test_parse_page_content_into_sections_from_h1_headers() -> None:
    """Falls back to h1-header parsing when no tabs are present."""
    result = LegacyContentMerger.parse_page_content_into_sections(H1_HTML)

    assert "Platform 2.0" in result
    assert "Platform 2.1" in result


def test_parse_page_content_into_sections_empty_html() -> None:
    """Returns {} when the input HTML is empty."""
    result = LegacyContentMerger.parse_page_content_into_sections("")

    assert result == {}


def test_parse_page_content_into_sections_h2_fallback() -> None:
    """Falls back to h2/h3 parsing for vX.Y-style version markers."""
    result = LegacyContentMerger.parse_page_content_into_sections(H2_VERSION_HTML)

    assert "v1.2" in result
