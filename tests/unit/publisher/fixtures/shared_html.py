"""
Общие HTML-фикстуры для юнит-тестов legacy_content.

Импортируйте нужные константы напрямую:

    from tests.unit.publisher.fixtures.shared_html import (
        TAB_HTML_SINGLE,
        TAB_HTML_MULTI,
        ...
    )
"""


# Минимальный HTML с одной вкладкой "Platform 2.0"
TAB_HTML_SINGLE: str = (
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">Platform 2.0</ac:parameter>'
    "<ac:rich-text-body><p>Content 2.0</p></ac:rich-text-body>"
    "</ac:structured-macro>"
)


# HTML с двумя вкладками: Platform 2.0 и Platform 2.1
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


# HTML со вложенным rich-text-body (таблица внутри вкладки)
TAB_HTML_NESTED: str = (
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">Platform 2.0</ac:parameter>'
    "<ac:rich-text-body>"
    "<table><ac:rich-text-body><p>inner</p></ac:rich-text-body></table>"
    "<p>outer</p>"
    "</ac:rich-text-body>"
    "</ac:structured-macro>"
)


# HTML с заголовками h1 в устаревшем формате
H1_HTML: str = (
    "<h1>Platform 2.0</h1><p>Legacy content 2.0</p>"
    "<h1>Platform 2.1</h1><p>Legacy content 2.1</p>"
)


# HTML с макросом tabs-group (шаблон уже управляет вкладками)
TABS_GROUP_HTML: str = (
    '<ac:structured-macro ac:name="tabs-group"><ac:rich-text-body>'
    "some content"
    "</ac:rich-text-body></ac:structured-macro>"
)


# Вкладка без содержимого тела (только параметр, без rich-text-body)
TAB_HTML_NO_BODY: str = (
    '<ac:structured-macro ac:name="tab">'
    '<ac:parameter ac:name="name">Platform 9.9</ac:parameter>'
    "</ac:structured-macro>"
)

# HTML с двумя одинаковыми именами вкладок
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


# HTML с заголовком версии h2 (запасной вариант vX.Y)
H2_VERSION_HTML: str = "<h2>v1.2</h2>\n<p>content for v1.2</p>"


# Три вкладки: Platform 2.0, CustomOS 2.0 (тоже заканчивается на "2.0"), Platform 2.1
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
