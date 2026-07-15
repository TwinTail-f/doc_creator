"""
Тесты для:
- autodoc.publisher.strategies.base.BasePublishStrategy (_minify_html, _publish_single_page)
- autodoc.publisher.strategies.base.PublishReport

ПРИМЕЧАНИЕ: тесты, связанные с реестром (BasePublishStrategy.create(), .available_strategies(),
и самрегистрирующийся kwarg __init_subclass__ `strategy_type=`), были удалены —
кодовая база с тех пор перешла на явный реестр на основе словаря
(autodoc.publisher.strategies.registry.STRATEGIES / create_strategy()).
"""

from __future__ import annotations

from typing import Any

import pytest

from autodoc.exceptions import ConfluenceError
from autodoc.publisher.strategies.base_publish_strategy import BasePublishStrategy
from autodoc.publisher.strategies.models.publish_report import PublishReport

_PAGE_TITLE: str = "Test Page"
_TEMPLATE_NAME: str = "test_template.jinja2"
_PARENT_ID: str = "parent-001"
_PAGE_ID: str = "page-001"


class _StubStrategy(BasePublishStrategy):
    """Минимальная конкретная стратегия для тестирования _publish_single_page."""

    def execute(self) -> PublishReport:
        """Выполняет фиктивную стратегию, возвращающую успешный отчёт."""
        return PublishReport(success=True, pages_published=1)


# _minify_html
@pytest.mark.infrastructure
def test_minify_html_removes_html_comments() -> None:
    """HTML-комментарии удаляются из результата."""
    result = BasePublishStrategy._minify_html("<!-- comment --><p>text</p>")
    assert result == "<p>text</p>"


@pytest.mark.infrastructure
def test_minify_html_collapses_whitespace_between_tags() -> None:
    """Пробелы между тегами схлопываются полностью."""
    result = BasePublishStrategy._minify_html("><    <")
    assert "  " not in result
    assert ">  <" not in result


@pytest.mark.infrastructure
def test_minify_html_collapses_multiple_spaces() -> None:
    """Несколько подряд идущих пробелов в тексте сжимаются до одного."""
    result = BasePublishStrategy._minify_html("two  spaces")
    assert result == "two spaces"


@pytest.mark.infrastructure
def test_minify_html_strips_result() -> None:
    """Начальные и конечные пробелы удаляются из результата."""
    result = BasePublishStrategy._minify_html("  <p>text</p>  ")
    assert result == "<p>text</p>"


@pytest.mark.infrastructure
def test_minify_html_empty_string_returns_empty() -> None:
    """Пустая строка на входе даёт пустую строку на выходе."""
    result = BasePublishStrategy._minify_html("")
    assert result == ""


@pytest.mark.infrastructure
def test_minify_html_preserves_cdata_content_untouched() -> None:
    """Содержимое блоков CDATA (например, тела макросов Confluence) не изменяется минификацией."""
    html = '<ac:parameter><![CDATA[  raw   <b>markup</b>  <!-- not a comment -->  ]]></ac:parameter>'
    result = BasePublishStrategy._minify_html(html)
    assert "<![CDATA[  raw   <b>markup</b>  <!-- not a comment -->  ]]>" in result


# PublishReport
@pytest.mark.contract
def test_publish_report_defaults() -> None:
    """Опциональные поля имеют корректные значения по умолчанию, если не заданы."""
    report = PublishReport(success=True, pages_published=0)
    assert report.pages_failed == 0
    assert report.errors == []
    assert report.failed_pages == []
    assert report.details == []


@pytest.mark.business_logic
def test_publish_report_merge_concatenates_failed_pages_and_details() -> None:
    """merge() объединяет списки failed_pages и details нескольких отчётов, как это используется в publisher.py."""
    report_a = PublishReport(
        success=False,
        pages_published=1,
        pages_failed=1,
        details=[{"page_title": "A", "page_id": "1"}],
        failed_pages=[{"page_title": "B", "reason": "boom"}],
    )
    report_b = PublishReport(
        success=True,
        pages_published=1,
        details=[{"page_title": "C", "page_id": "2"}],
    )

    merged = PublishReport.merge(report_a, report_b)

    assert merged.failed_pages == [{"page_title": "B", "reason": "boom"}]
    assert merged.details == [
        {"page_title": "A", "page_id": "1"},
        {"page_title": "C", "page_id": "2"},
    ]


@pytest.fixture
def strategy_stub(
    publisher_confluence_client: Any,
    publisher_document_builder: Any,
    publisher_parsed_result: Any,
) -> _StubStrategy:
    """Конкретный _StubStrategy, оснащённый фиктивными зависимостями."""
    return _StubStrategy(
        confluence_client=publisher_confluence_client,
        document_builder=publisher_document_builder,
        parsed_data=publisher_parsed_result,
        space="TEST",
    )


# _publish_single_page (через _StubStrategy)
@pytest.mark.business_logic
def test_publish_single_page_returns_success_report(
    strategy_stub: _StubStrategy,
    publisher_confluence_client: Any,
    publisher_document_builder: Any,
) -> None:
    """Успешный сценарий возвращает PublishReport(success=True, pages_published=1)."""
    report = strategy_stub._publish_single_page(
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        transform_fn=lambda: {"key": "val"},
        parent_id=_PARENT_ID,
    )
    assert report.success is True
    assert report.pages_published == 1


@pytest.mark.contract
def test_publish_single_page_adds_space_to_view_model(
    strategy_stub: _StubStrategy,
    publisher_document_builder: Any,
) -> None:
    """Стратегия добавляет ключ _space в view_model перед построением документа."""
    strategy_stub._publish_single_page(
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        transform_fn=lambda: {"key": "val"},
        parent_id=_PARENT_ID,
    )
    assert publisher_document_builder.last_call is not None
    assert publisher_document_builder.last_call["view_model"]["space"] == "TEST"


@pytest.mark.contract
def test_publish_single_page_calls_inject_links_if_provided(
    strategy_stub: _StubStrategy,
) -> None:
    """Callable inject_links вызывается ровно один раз с view_model."""
    calls: list[dict] = []

    def inject_links(vm: dict) -> None:
        calls.append(vm)

    strategy_stub._publish_single_page(
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        transform_fn=lambda: {"key": "val"},
        parent_id=_PARENT_ID,
        inject_links=inject_links,
    )
    assert len(calls) == 1
    assert "key" in calls[0]


@pytest.mark.infrastructure
def test_publish_single_page_calls_builder_build(
    strategy_stub: _StubStrategy,
    publisher_document_builder: Any,
) -> None:
    """DocumentBuilder.build вызывается с корректным template_name."""
    strategy_stub._publish_single_page(
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        transform_fn=lambda: {"key": "val"},
        parent_id=_PARENT_ID,
    )
    assert publisher_document_builder.last_call is not None
    assert publisher_document_builder.last_call["template_name"] == _TEMPLATE_NAME


@pytest.mark.infrastructure
def test_publish_single_page_calls_client_publish_page(
    strategy_stub: _StubStrategy,
    publisher_confluence_client: Any,
) -> None:
    """ConfluenceClient.publish_page вызывается с корректным заголовком."""
    strategy_stub._publish_single_page(
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        transform_fn=lambda: {"key": "val"},
        parent_id=_PARENT_ID,
    )
    publish_calls = [
        c for c in publisher_confluence_client.calls if c["method"] == "publish_page"
    ]
    assert len(publish_calls) == 1
    assert publish_calls[0]["title"] == _PAGE_TITLE


@pytest.mark.business_logic
def test_publish_single_page_returns_failure_on_transform_exception(
    strategy_stub: _StubStrategy,
) -> None:
    """Если transform_fn выбрасывает исключение, результатом является отчёт о неудаче."""

    def bad_transform() -> dict:
        raise ValueError("transform failed")

    report = strategy_stub._publish_single_page(
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        transform_fn=bad_transform,
        parent_id=_PARENT_ID,
    )
    assert report.success is False
    assert report.pages_failed == 1


@pytest.mark.business_logic
def test_publish_single_page_returns_failure_on_client_exception(
    strategy_stub: _StubStrategy,
    publisher_confluence_client: Any,
) -> None:
    """Если publish_page выбрасывает ConfluenceError, результатом является отчёт о неудаче."""

    def raise_confluence_error(*args: Any, **kwargs: Any) -> None:
        raise ConfluenceError("network error")

    publisher_confluence_client.publish_page = raise_confluence_error

    report = strategy_stub._publish_single_page(
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        transform_fn=lambda: {"key": "val"},
        parent_id=_PARENT_ID,
    )
    assert report.success is False


@pytest.mark.business_logic
def test_publish_single_page_returns_failure_if_transform_returns_empty(
    strategy_stub: _StubStrategy,
) -> None:
    """Если transform_fn возвращает пустой словарь, результатом является отчёт о неудаче."""
    report = strategy_stub._publish_single_page(
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        transform_fn=lambda: {},
        parent_id=_PARENT_ID,
    )
    assert report.success is False
