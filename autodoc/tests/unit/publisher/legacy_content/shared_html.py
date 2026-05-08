"""
Shared HTML fixtures for legacy_content unit tests.

Import the constants you need directly:

    from autodoc.tests.unit.publisher.legacy_content.shared_html import (
        TAB_HTML_SINGLE,
        TAB_HTML_MULTI,
        ...
    )
"""

# ---------------------------------------------------------------------------
# Single-tab HTML
# ---------------------------------------------------------------------------

# Minimal HTML with a single "Platform 2.0" tab
TAB_HTML_SINGLE: str = (
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">Platform 2.0</ac:parameter>'
    "<ac:rich-text-body><p>Content 2.0</p></ac:rich-text-body>"
    "</ac:structured-macro>"
)

# ---------------------------------------------------------------------------
# Multi-tab HTML
# ---------------------------------------------------------------------------

# HTML with two tabs: Platform 2.0 and Platform 2.1
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

# ---------------------------------------------------------------------------
# Nested rich-text-body
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Legacy h1-header format
# ---------------------------------------------------------------------------

# HTML with h1 headers in legacy format
H1_HTML: str = (
    "<h1>Platform 2.0</h1><p>Legacy content 2.0</p>"
    "<h1>Platform 2.1</h1><p>Legacy content 2.1</p>"
)

# ---------------------------------------------------------------------------
# Already-tabbed (tabs-group wrapper)
# ---------------------------------------------------------------------------

# HTML with tabs-group macro (template already manages tabs)
TABS_GROUP_HTML: str = (
    '<ac:structured-macro ac:name="tabs-group"><ac:rich-text-body>'
    "some content"
    "</ac:rich-text-body></ac:structured-macro>"
)

# ---------------------------------------------------------------------------
# Edge-case fixtures (extractor-specific)
# ---------------------------------------------------------------------------

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
# Edge-case fixtures (merger-specific)
# ---------------------------------------------------------------------------

# HTML with h2 version header (vX.Y fallback)
H2_VERSION_HTML: str = "<h2>v1.2</h2>\n<p>content for v1.2</p>"

# ---------------------------------------------------------------------------
# Edge-case fixtures (service-specific)
# ---------------------------------------------------------------------------

# Three tabs: Platform 2.0, CustomOS 2.0 (also ends in "2.0"), Platform 2.1
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
