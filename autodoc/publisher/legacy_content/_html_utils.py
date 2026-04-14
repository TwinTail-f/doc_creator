"""
Shared HTML parsing utilities for legacy Confluence content processing.

Contains compiled regex patterns and the common h1-section extraction
algorithm used by both LegacyContentExtractor and LegacyContentMerger.
"""

import re
from typing import NamedTuple

# Compiled patterns shared across extractor and merger
H1_OPEN_RE: re.Pattern[str] = re.compile(r"<h1\b[^>]*>")
INNER_TAG_RE: re.Pattern[str] = re.compile(r"<[^>]+>")
PLATFORM_VERSION_RE: re.Pattern[str] = re.compile(r"Platform\s+[\d.]+")


class _H1Section(NamedTuple):
    """Internal record of one parsed h1 element."""

    tag_start: int   # index of the opening <h1...> tag
    tag_end: int     # index just after the closing </h1>
    text: str        # inner text of the h1 (tags stripped)


def find_h1_sections(html: str) -> list[_H1Section]:
    """
    Scans *html* and returns metadata for every ``<h1>`` element found.

    Args:
        html: Full HTML document in Confluence Storage Format.

    Returns:
        List of ``_H1Section`` tuples in document order.
        Empty list if no ``<h1>`` elements are present.
    """
    sections: list[_H1Section] = []
    for m in H1_OPEN_RE.finditer(html):
        close_pos = html.find("</h1>", m.end())
        if close_pos == -1:
            continue
        inner = html[m.end() : close_pos]
        text = INNER_TAG_RE.sub("", inner).strip()
        sections.append(_H1Section(m.start(), close_pos + len("</h1>"), text))
    return sections


def extract_platform_h1_sections(html: str) -> dict[str, str]:
    """
    Extracts ``Platform X.Y`` sections from pages using ``<h1>`` headings.

    Identifies h1 elements whose text matches ``Platform X.Y``, then
    collects everything between that heading's closing ``</h1>`` and the
    start of the next ``<h1>`` as the section content.

    Args:
        html: Full HTML document in Confluence Storage Format.

    Returns:
        Dictionary ``{platform_name: html_content}``.
        Empty dict if no matching headings are found.
    """
    h1_list = find_h1_sections(html)
    result: dict[str, str] = {}

    for i, section in enumerate(h1_list):
        match = PLATFORM_VERSION_RE.search(section.text)
        if not match:
            continue
        platform_name = match.group(0)
        content_end = h1_list[i + 1].tag_start if i + 1 < len(h1_list) else len(html)
        content = html[section.tag_end : content_end].strip()
        if content:
            result[platform_name] = content

    return result
