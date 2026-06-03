"""Direct unit tests for _html_utils.py.

Covers extract_rich_text_body, find_h1_sections, and extract_tab_sections.
"""

from __future__ import annotations
import pytest

from autodoc.publisher.legacy_content._html_utils import (
    _RICH_TEXT_BODY_CLOSE,
    _RICH_TEXT_BODY_OPEN,
    extract_rich_text_body,
    extract_tab_sections,
    find_h1_sections,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OPEN = _RICH_TEXT_BODY_OPEN
_CLOSE = _RICH_TEXT_BODY_CLOSE


def _wrap(content: str) -> str:
    """Wrap content in a single <ac:rich-text-body> pair."""
    return f"{_OPEN}{content}{_CLOSE}"


# ---------------------------------------------------------------------------
# extract_rich_text_body tests
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_extract_rich_text_body_single_non_nested_returns_content() -> None:
    """Returns correct content for a single non-nested tag."""
    html = _wrap("<p>hello</p>")
    content, _ = extract_rich_text_body(html, 0)
    assert content == "<p>hello</p>"


@pytest.mark.infrastructure
def test_extract_rich_text_body_depth_2_nesting() -> None:
    """Correctly handles one level of nesting (depth 2)."""
    inner = _wrap("<p>inner</p>")
    html = f"{_OPEN}{inner}<p>outer</p>{_CLOSE}"
    content, _ = extract_rich_text_body(html, 0)
    assert "<p>inner</p>" in content
    assert "<p>outer</p>" in content


@pytest.mark.infrastructure
def test_extract_rich_text_body_missing_close_returns_empty() -> None:
    """Returns ('', ...) when there is no closing tag."""
    html = f"{_OPEN}<p>no close"
    content, _ = extract_rich_text_body(html, 0)
    assert content == ""


@pytest.mark.infrastructure
def test_extract_rich_text_body_end_idx_is_after_close_tag() -> None:
    """end_idx points to the position immediately after the closing tag."""
    suffix = "AFTER"
    html = _wrap("<p>x</p>") + suffix
    _, end_idx = extract_rich_text_body(html, 0)
    assert html[end_idx : end_idx + len(suffix)] == suffix


# ---------------------------------------------------------------------------
# find_h1_sections tests
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_find_h1_sections_empty_when_no_h1() -> None:
    """Returns an empty list when there are no <h1> tags."""
    result = find_h1_sections("<p>no headings here</p>")
    assert result == []


@pytest.mark.infrastructure
def test_find_h1_sections_returns_tag_start_tag_end_and_text() -> None:
    """Returns correct tag_start, tag_end, and text for each heading."""
    html = "<h1>Platform 2.0</h1><p>body</p><h1>Platform 2.1</h1>"
    sections = find_h1_sections(html)

    assert len(sections) == 2

    assert sections[0].text == "Platform 2.0"
    assert html[sections[0].tag_start] == "<"
    assert html[sections[0].tag_start : sections[0].tag_start + 4] == "<h1>"
    assert html[sections[0].tag_end - 5 : sections[0].tag_end] == "</h1>"

    assert sections[1].text == "Platform 2.1"


@pytest.mark.infrastructure
def test_find_h1_sections_strips_inner_html_tags() -> None:
    """text field has inner HTML tags removed."""
    html = "<h1><strong>Bold Title</strong></h1>"
    sections = find_h1_sections(html)
    assert len(sections) == 1
    assert sections[0].text == "Bold Title"


@pytest.mark.infrastructure
def test_find_h1_sections_skips_h1_with_no_closing_tag() -> None:
    """A <h1> with no matching </h1> is not included in results."""
    html = "<h1>Unclosed heading"
    result = find_h1_sections(html)
    assert result == []


# ---------------------------------------------------------------------------
# extract_tab_sections tests
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_extract_tab_sections_empty_string_returns_empty_dict() -> None:
    """Returns {} on empty string input."""
    assert extract_tab_sections("") == {}


@pytest.mark.business_logic
def test_extract_tab_sections_deduplicates_identical_names_first_wins() -> None:
    """First occurrence wins when two tabs share the same name."""
    _TAB = '<ac:structured-macro ac:name="tab">'
    html = (
        _TAB
        + '<ac:parameter ac:name="name">Alpha</ac:parameter>'
        + "<ac:rich-text-body><p>First</p></ac:rich-text-body>"
        + _TAB
        + '<ac:parameter ac:name="name">Alpha</ac:parameter>'
        + "<ac:rich-text-body><p>Second</p></ac:rich-text-body>"
    )
    result = extract_tab_sections(html)
    assert list(result.keys()).count("Alpha") == 1
    assert "First" in result["Alpha"]


@pytest.mark.infrastructure
def test_extract_tab_sections_ignores_title_attribute() -> None:
    """ac:name="title" is not recognised as a tab name — only ac:name="name" is supported.

    The title= attribute belongs to expand macros, not tabs. Treating it as a
    tab name caused false positives during fallback section parsing, so it is
    intentionally excluded from _TAB_NAME_RE.
    """
    html = (
        '<ac:structured-macro ac:name="tab">'
        '<ac:parameter ac:name="title">My Tab</ac:parameter>'
        "<ac:rich-text-body><p>title content</p></ac:rich-text-body>"
    )
    result = extract_tab_sections(html)
    assert "My Tab" not in result


@pytest.mark.business_logic
def test_extract_tab_sections_skips_tab_with_no_rich_text_body() -> None:
    """A tab whose <ac:rich-text-body> is missing is not included."""
    html = '<ac:parameter ac:name="name">Ghost</ac:parameter>'
    result = extract_tab_sections(html)
    assert "Ghost" not in result
