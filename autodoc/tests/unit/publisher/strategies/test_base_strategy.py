"""
Tests for:
- autodoc.publisher.strategies.base.BasePublishStrategy (registry, _minify_html, _publish_single_page)
- autodoc.publisher.strategies.base.PublishReport
"""
from __future__ import annotations

from typing import Any

import pytest

from autodoc.publisher.strategies.base import BasePublishStrategy, PublishReport

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STUB_TYPE: str = "__test_stub__"
_PAGE_TITLE: str = "Test Page"
_TEMPLATE_NAME: str = "test_template.jinja2"
_PARENT_ID: str = "parent-001"
_PAGE_ID: str = "page-001"

# ---------------------------------------------------------------------------
# Module-level stub strategy (must be at module level for registry population)
# ---------------------------------------------------------------------------


class _StubStrategy(BasePublishStrategy, strategy_type=_STUB_TYPE):
    """Minimal concrete strategy used to test registry and _publish_single_page."""

    def execute(self) -> PublishReport:
        """Executes a no-op strategy returning a success report."""
        return PublishReport(success=True, pages_published=1)


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestRegistry:
    """Tests for BasePublishStrategy registry and factory."""

    def test_create_raises_on_unknown_strategy_type(self) -> None:
        """create() with an unknown key raises ValueError."""
        with pytest.raises(ValueError, match="__nonexistent__"):
            BasePublishStrategy.create("__nonexistent__")

    def test_create_returns_instance_of_registered_class(
        self,
        publisher_confluence_client: Any,
        publisher_document_builder: Any,
        publisher_parsed_result: Any,
    ) -> None:
        """create() with a registered key returns the correct subclass instance."""
        instance = BasePublishStrategy.create(
            _STUB_TYPE,
            confluence_client=publisher_confluence_client,
            document_builder=publisher_document_builder,
            parsed_data=publisher_parsed_result,
            space="TEST",
        )
        assert isinstance(instance, _StubStrategy)

    def test_available_strategies_returns_sorted_list(self) -> None:
        """available_strategies() contains the stub key and is sorted."""
        strategies = BasePublishStrategy.available_strategies()
        assert _STUB_TYPE in strategies
        assert strategies == sorted(strategies)

    def test_create_calls_make_transformer_if_defined(
        self,
        publisher_confluence_client: Any,
        publisher_document_builder: Any,
        publisher_parsed_result: Any,
        mocker: Any,
    ) -> None:
        """If the strategy declares _make_transformer, create() calls it."""
        sentinel = object()

        class _TransformerStrategy(BasePublishStrategy, strategy_type="__test_transformer__"):
            """Strategy with _make_transformer for testing create() factory logic."""

            def __init__(self, transformer: Any = None, **kwargs: Any) -> None:
                super().__init__(**kwargs)
                self._transformer = transformer

            @classmethod
            def _make_transformer(cls, kwargs: dict) -> Any:
                return sentinel

            def execute(self) -> PublishReport:
                return PublishReport(success=True, pages_published=0)

        instance = BasePublishStrategy.create(
            "__test_transformer__",
            confluence_client=publisher_confluence_client,
            document_builder=publisher_document_builder,
            parsed_data=publisher_parsed_result,
            space="TEST",
        )
        assert instance._transformer is sentinel


# ---------------------------------------------------------------------------
# _minify_html tests
# ---------------------------------------------------------------------------


class TestMinifyHtml:
    """Tests for BasePublishStrategy._minify_html static method."""

    def test_minify_html_removes_html_comments(self) -> None:
        """HTML comments are stripped from the output."""
        result = BasePublishStrategy._minify_html("<!-- comment --><p>text</p>")
        assert result == "<p>text</p>"

    def test_minify_html_collapses_whitespace_between_tags(self) -> None:
        """Whitespace between tags is collapsed to nothing."""
        result = BasePublishStrategy._minify_html("><    <")
        assert "  " not in result
        assert ">  <" not in result

    def test_minify_html_collapses_multiple_spaces(self) -> None:
        """Multiple consecutive spaces in text content are reduced to one."""
        result = BasePublishStrategy._minify_html("two  spaces")
        assert result == "two spaces"

    def test_minify_html_strips_result(self) -> None:
        """Leading and trailing whitespace is removed from the result."""
        result = BasePublishStrategy._minify_html("  <p>text</p>  ")
        assert result == "<p>text</p>"

    def test_minify_html_empty_string_returns_empty(self) -> None:
        """An empty string input produces an empty string output."""
        result = BasePublishStrategy._minify_html("")
        assert result == ""


# ---------------------------------------------------------------------------
# PublishReport tests
# ---------------------------------------------------------------------------


class TestPublishReport:
    """Tests for PublishReport dataclass behaviour."""

    def test_publish_report_success_true_if_no_errors(self) -> None:
        """A report constructed with success=True has success == True."""
        report = PublishReport(success=True, pages_published=1)
        assert report.success is True

    def test_publish_report_success_false_if_errors_present(self) -> None:
        """A report constructed with success=False has success == False."""
        report = PublishReport(success=False, pages_published=0)
        assert report.success is False

    def test_publish_report_defaults(self) -> None:
        """Optional fields have correct defaults when not supplied."""
        report = PublishReport(success=True, pages_published=0)
        assert report.pages_failed == 0
        assert report.errors == []
        assert report.failed_pages == []
        assert report.details == []


# ---------------------------------------------------------------------------
# _publish_single_page tests (exercised via _StubStrategy instance)
# ---------------------------------------------------------------------------


@pytest.fixture
def strategy_stub(
    publisher_confluence_client: Any,
    publisher_document_builder: Any,
    publisher_parsed_result: Any,
) -> _StubStrategy:
    """A concrete _StubStrategy wired with fake dependencies."""
    return _StubStrategy(
        confluence_client=publisher_confluence_client,
        document_builder=publisher_document_builder,
        parsed_data=publisher_parsed_result,
        space="TEST",
    )


class TestPublishSinglePage:
    """Tests for BasePublishStrategy._publish_single_page via _StubStrategy."""

    def test_publish_single_page_returns_success_report(
        self,
        strategy_stub: _StubStrategy,
        publisher_confluence_client: Any,
        publisher_document_builder: Any,
    ) -> None:
        """A successful flow returns PublishReport(success=True, pages_published=1)."""
        report = strategy_stub._publish_single_page(
            page_title=_PAGE_TITLE,
            template_name=_TEMPLATE_NAME,
            transform_fn=lambda: {"key": "val"},
            parent_id=_PARENT_ID,
        )
        assert report.success is True
        assert report.pages_published == 1

    def test_publish_single_page_adds_space_to_view_model(
        self,
        strategy_stub: _StubStrategy,
        publisher_document_builder: Any,
    ) -> None:
        """The strategy injects its _space key into the view_model before building."""
        strategy_stub._publish_single_page(
            page_title=_PAGE_TITLE,
            template_name=_TEMPLATE_NAME,
            transform_fn=lambda: {"key": "val"},
            parent_id=_PARENT_ID,
        )
        assert publisher_document_builder.last_call is not None
        assert publisher_document_builder.last_call["view_model"]["space"] == "TEST"

    def test_publish_single_page_calls_inject_links_if_provided(
        self,
        strategy_stub: _StubStrategy,
    ) -> None:
        """inject_links callable is called exactly once with the view_model."""
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

    def test_publish_single_page_calls_builder_build(
        self,
        strategy_stub: _StubStrategy,
        publisher_document_builder: Any,
    ) -> None:
        """DocumentBuilder.build is called with the correct template_name."""
        strategy_stub._publish_single_page(
            page_title=_PAGE_TITLE,
            template_name=_TEMPLATE_NAME,
            transform_fn=lambda: {"key": "val"},
            parent_id=_PARENT_ID,
        )
        assert publisher_document_builder.last_call is not None
        assert publisher_document_builder.last_call["template_name"] == _TEMPLATE_NAME

    def test_publish_single_page_calls_client_publish_page(
        self,
        strategy_stub: _StubStrategy,
        publisher_confluence_client: Any,
    ) -> None:
        """ConfluenceClient.publish_page is called with the correct title."""
        strategy_stub._publish_single_page(
            page_title=_PAGE_TITLE,
            template_name=_TEMPLATE_NAME,
            transform_fn=lambda: {"key": "val"},
            parent_id=_PARENT_ID,
        )
        publish_calls = [c for c in publisher_confluence_client.calls if c["method"] == "publish_page"]
        assert len(publish_calls) == 1
        assert publish_calls[0]["title"] == _PAGE_TITLE

    def test_publish_single_page_returns_failure_on_transform_exception(
        self,
        strategy_stub: _StubStrategy,
    ) -> None:
        """If transform_fn raises, the result is a failure report."""
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

    def test_publish_single_page_returns_failure_on_client_exception(
        self,
        strategy_stub: _StubStrategy,
        publisher_confluence_client: Any,
    ) -> None:
        """If publish_page raises RuntimeError, result is a failure report."""
        def raise_runtime(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("network error")

        publisher_confluence_client.publish_page = raise_runtime

        report = strategy_stub._publish_single_page(
            page_title=_PAGE_TITLE,
            template_name=_TEMPLATE_NAME,
            transform_fn=lambda: {"key": "val"},
            parent_id=_PARENT_ID,
        )
        assert report.success is False

    def test_publish_single_page_returns_failure_if_transform_returns_empty(
        self,
        strategy_stub: _StubStrategy,
    ) -> None:
        """If transform_fn returns an empty dict, result is a failure report."""
        report = strategy_stub._publish_single_page(
            page_title=_PAGE_TITLE,
            template_name=_TEMPLATE_NAME,
            transform_fn=lambda: {},
            parent_id=_PARENT_ID,
        )
        assert report.success is False
