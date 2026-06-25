"""Unit tests for legacy_merger functions.

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

import pytest

from autodoc.publisher.legacy_content.legacy_merger import (
    merge_by_tabs,
    parse_page_content_into_sections,
)
from tests.unit.publisher.fixtures.shared_html import (
    H1_HTML,
    H2_VERSION_HTML,
    TAB_HTML_MULTI,
    TABS_GROUP_HTML,
)

# Marker present in every tabs-group macro
_TABS_GROUP_MARKER: str = 'ac:name="tabs-group"'

# ---------------------------------------------------------------------------
# merge_by_tabs() tests
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_merge_by_tabs_returns_new_html_if_no_legacy() -> None:
    """Returns new_html unchanged when legacy_contents is empty."""
    new_html = "<p>new content</p>"

    result = merge_by_tabs(new_html, {}, "Platform 2.1")

    assert result == new_html


@pytest.mark.business_logic
def test_merge_by_tabs_returns_new_html_if_already_has_tabs_group() -> None:
    """Returns new_html unchanged when it already contains a tabs-group macro."""
    legacy = {"Platform 2.0": "<p>old</p>"}

    result = merge_by_tabs(TABS_GROUP_HTML, legacy, "Platform 2.1")

    assert result == TABS_GROUP_HTML


@pytest.mark.business_logic
def test_merge_by_tabs_wraps_in_tabs_group_macro() -> None:
    """Wraps the combined output in a Confluence tabs-group macro."""
    legacy = {"Platform 2.0": "<p>old</p>"}
    new_html = "<p>new</p>"

    result = merge_by_tabs(new_html, legacy, "Platform 2.1")

    assert _TABS_GROUP_MARKER in result


@pytest.mark.business_logic
def test_merge_by_tabs_current_platform_tab_is_first() -> None:
    """Current platform tab must appear before all legacy tabs."""
    legacy = {"Platform 2.0": "<p>old</p>"}
    current_platform = "Platform 2.1"
    new_html = "<p>new</p>"

    result = merge_by_tabs(new_html, legacy, current_platform)

    idx_current = result.index(f">{current_platform}<")
    idx_legacy = result.index(">Platform 2.0<")
    assert idx_current < idx_legacy


@pytest.mark.business_logic
def test_merge_by_tabs_legacy_tabs_in_reverse_alphabetical_order() -> None:
    """Legacy tabs follow the current tab in reverse alphabetical order."""
    legacy = {"Platform 2.0": "a", "Platform 2.1": "b"}
    current_platform = "Platform 2.2"
    new_html = "<p>new</p>"

    result = merge_by_tabs(new_html, legacy, current_platform)

    idx_21 = result.index(">Platform 2.1<")
    idx_20 = result.index(">Platform 2.0<")
    # 2.1 must appear before 2.0 (reverse alphabetical)
    assert idx_21 < idx_20


@pytest.mark.business_logic
def test_merge_by_tabs_legacy_tabs_numeric_order_with_double_digit_versions() -> None:
    """'Platform 2.10' must appear before 'Platform 2.9' in the output."""
    legacy = {"Platform 2.9": "<p>v2.9</p>", "Platform 2.10": "<p>v2.10</p>"}
    current_platform = "Platform 2.11"
    new_html = "<p>new</p>"

    result = merge_by_tabs(new_html, legacy, current_platform)

    idx_210 = result.index(">Platform 2.10<")
    idx_29 = result.index(">Platform 2.9<")
    assert idx_210 < idx_29


@pytest.mark.business_logic
def test_merge_by_tabs_does_not_duplicate_current_platform() -> None:
    """Current platform is not duplicated even if it appears in legacy_contents."""
    current_platform = "Platform 2.1"
    legacy = {current_platform: "<p>old 2.1</p>", "Platform 2.0": "<p>old 2.0</p>"}
    new_html = "<p>new 2.1</p>"

    result = merge_by_tabs(new_html, legacy, current_platform)

    # Tab with current platform name must appear exactly once
    assert result.count(f">{current_platform}<") == 1


# ---------------------------------------------------------------------------
# parse_page_content_into_sections() tests
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_parse_page_content_into_sections_from_tabs() -> None:
    """Parses multi-tab HTML into a dict with one key per tab."""
    result = parse_page_content_into_sections(TAB_HTML_MULTI)

    assert set(result.keys()) == {"Platform 2.0", "Platform 2.1"}


@pytest.mark.business_logic
def test_parse_page_content_into_sections_from_h1_headers() -> None:
    """Falls back to h1-header parsing when no tabs are present."""
    result = parse_page_content_into_sections(H1_HTML)

    assert "Platform 2.0" in result
    assert "Platform 2.1" in result


@pytest.mark.infrastructure
def test_parse_page_content_into_sections_empty_html() -> None:
    """Returns {} when the input HTML is empty."""
    result = parse_page_content_into_sections("")

    assert result == {}


@pytest.mark.business_logic
def test_parse_page_content_into_sections_h2_fallback() -> None:
    """Falls back to h2/h3 parsing for vX.Y-style version markers."""
    result = parse_page_content_into_sections(H2_VERSION_HTML)

    assert "v1.2" in result


@pytest.mark.business_logic
def test_merge_by_tabs_three_platform_versions_all_tabs_present() -> None:
    """merge_by_tabs with 2 legacy versions: current first, then 1.6, then 1.0."""
    new_html = "<p>platform 2.0 content</p>"
    legacy_contents = {
        "1.0": "<p>platform 1.0 content</p>",
        "1.6": "<p>platform 1.6 content</p>",
    }

    result = merge_by_tabs(new_html, legacy_contents, "2.0")

    assert ">2.0<" in result
    assert ">1.6<" in result
    assert ">1.0<" in result

    pos_current = result.index(">2.0<")
    pos_1_6 = result.index(">1.6<")
    pos_1_0 = result.index(">1.0<")
    assert (
        pos_current < pos_1_6 < pos_1_0
    ), f"Expected order 2.0 < 1.6 < 1.0, got positions {pos_current}, {pos_1_6}, {pos_1_0}"


@pytest.mark.business_logic
def test_merge_by_tabs_current_version_not_duplicated_with_multiple_legacy_versions() -> None:
    """Current version appears exactly once even if legacy block has a stale entry for it."""
    new_html = "<p>current content</p>"
    legacy_contents = {
        "2.0": "<p>stale 2.0 entry</p>",
        "1.6": "<p>platform 1.6</p>",
    }

    result = merge_by_tabs(new_html, legacy_contents, "2.0")

    # Tab name marker appears exactly once (stale legacy entry for current version is skipped)
    tab_occurrences = result.count(">2.0<")
    assert tab_occurrences == 1, f"Expected exactly 1 tab marker '>2.0<', found {tab_occurrences}"
