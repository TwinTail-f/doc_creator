"""
Tests for autodoc.publisher.strategies.release_strategy.ReleasePageStrategy.

Testing strategy:
- ReleasePageStrategy delegates to _publish_single_page (tested via outcome).
- PassportPageRegistry.load() is mocked when include_passport_links=True.
- FakeConfluenceClient / FakeDocumentBuilder provide deterministic I/O.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from autodoc.exceptions import ConfluenceError
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.models.page_result import PageResult
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.strategies.base_publish_strategy import BasePublishStrategy
from autodoc.publisher.strategies.registry import available_strategies, create_strategy
from autodoc.publisher.strategies.release_strategy import ReleasePageStrategy
from autodoc.publisher.converters.full_release_converter import FullReleaseConverter
from tests.unit.publisher.conftest import (
    FakeConfluenceClient,
    FakeDocumentBuilder,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SPACE: str = "TEST"
_PAGE_TITLE: str = "Platform 2.0 Release Docs"
_TEMPLATE_NAME: str = "release_doc.jinja2"
_PARENT_ID: str = "parent-001"

# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------


def make_release_strategy(
    client: FakeConfluenceClient,
    builder: FakeDocumentBuilder,
    data: ParsedResult,
    tmp_path: Path,
    include_passport_links: bool = True,
) -> ReleasePageStrategy:
    """Create a ReleasePageStrategy with sensible defaults for unit tests."""
    return ReleasePageStrategy(
        confluence_client=client,
        document_builder=builder,
        parsed_data=data,
        space=_SPACE,
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        parent_id=_PARENT_ID,
        include_passport_links=include_passport_links,
        data_dir=tmp_path,
    )


# ---------------------------------------------------------------------------
# execute() tests
# ---------------------------------------------------------------------------


class TestReleaseStrategyExecute:
    """Tests for ReleasePageStrategy.execute() behaviour."""

    @pytest.mark.infrastructure
    def test_release_strategy_execute_calls_publish_single_page(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """execute() ultimately calls client.publish_page with the correct title."""
        mocker.patch.object(PassportPageRegistry, "load", return_value={})
        strategy = make_release_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_parsed_result,
            tmp_path,
        )
        strategy.execute()
        publish_calls = [
            c for c in publisher_confluence_client.calls if c["method"] == "publish_page"
        ]
        assert len(publish_calls) == 1
        assert publish_calls[0]["title"] == _PAGE_TITLE

    @pytest.mark.business_logic
    def test_release_strategy_execute_returns_success_report(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """A successful execute() returns report.success=True and pages_published=1."""
        mocker.patch.object(PassportPageRegistry, "load", return_value={})
        strategy = make_release_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_parsed_result,
            tmp_path,
        )
        report = strategy.execute()
        assert report.success is True
        assert report.pages_published == 1

    @pytest.mark.business_logic
    def test_release_strategy_loads_registry_when_include_links_true(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """When include_passport_links=True, PassportPageRegistry.load() is called once."""
        mock_load = mocker.patch.object(PassportPageRegistry, "load", return_value={})
        strategy = make_release_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_parsed_result,
            tmp_path,
            include_passport_links=True,
        )
        strategy.execute()
        mock_load.assert_called_once()

    @pytest.mark.business_logic
    def test_release_strategy_skips_registry_load_when_include_links_false(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """When include_passport_links=False, PassportPageRegistry.load() is never called."""
        mock_load = mocker.patch.object(PassportPageRegistry, "load", return_value={})
        strategy = make_release_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_parsed_result,
            tmp_path,
            include_passport_links=False,
        )
        strategy.execute()
        mock_load.assert_not_called()

    @pytest.mark.business_logic
    def test_release_strategy_execute_returns_failure_on_client_error(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """If publish_page raises ConfluenceError, report.success is False."""
        mocker.patch.object(PassportPageRegistry, "load", return_value={})

        def raise_confluence_error(*args: Any, **kwargs: Any) -> None:
            raise ConfluenceError("connection refused")

        publisher_confluence_client.publish_page = raise_confluence_error

        strategy = make_release_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_parsed_result,
            tmp_path,
        )
        report = strategy.execute()
        assert report.success is False


# ---------------------------------------------------------------------------
# _make_converter / registry tests
# ---------------------------------------------------------------------------


class TestReleaseStrategyConverter:
    """Tests for ReleasePageStrategy factory and converter wiring."""

    @pytest.mark.contract
    def test_release_make_converter_creates_full_release_converter(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
    ) -> None:
        """create_strategy('release', ...) wires a FullReleaseConverter."""
        strategy = create_strategy(
            "release",
            confluence_client=publisher_confluence_client,
            document_builder=publisher_document_builder,
            parsed_data=publisher_parsed_result,
            space=_SPACE,
            page_title=_PAGE_TITLE,
            template_name=_TEMPLATE_NAME,
            data_dir=tmp_path,
            include_passport_links=False,
        )
        assert isinstance(strategy._converter, FullReleaseConverter)

    @pytest.mark.business_logic
    def test_release_strategy_registered_as_release(self) -> None:
        """'release' is present in available_strategies()."""
        assert "release" in available_strategies()


# ---------------------------------------------------------------------------
# Part-3 BL additions: BL-RS-01…05
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_publishes_exactly_one_page(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-RS-01
    Business Rule: ReleasePageStrategy publishes exactly one Confluence page per execution.

    Preconditions:
        - PassportPageRegistry.load is stubbed to return an empty map.

    Steps:
        1. Construct ReleasePageStrategy with include_passport_links=False.
        2. Call execute().

    Expected Result:
        report.pages_published == 1.
        Exactly one publish_page call is recorded on the client.
    """
    mocker.patch.object(PassportPageRegistry, "load", return_value={})
    strategy = make_release_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
        include_passport_links=False,
    )
    report = strategy.execute()

    assert (
        report.pages_published == 1
    ), f"ReleasePageStrategy must publish exactly 1 page, published: {report.pages_published}"
    publish_calls = [c for c in publisher_confluence_client.calls if c["method"] == "publish_page"]
    assert (
        len(publish_calls) == 1
    ), f"publish_page must be called exactly 1 time, called: {len(publish_calls)}"


@pytest.mark.business_logic
def test_passport_registry_loaded_when_include_links_true(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-RS-02
    Business Rule: PassportPageRegistry.load() is called when include_passport_links=True.

    Preconditions:
        - PassportPageRegistry.load is patched to track invocations.

    Steps:
        1. Construct strategy with include_passport_links=True.
        2. Call execute().

    Expected Result:
        PassportPageRegistry.load() is called at least once to retrieve passport links.
    """
    mock_load = mocker.patch.object(PassportPageRegistry, "load", return_value={})
    strategy = make_release_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
        include_passport_links=True,
    )
    strategy.execute()

    mock_load.assert_called_once_with()


@pytest.mark.business_logic
def test_passport_registry_not_loaded_when_include_links_false(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-RS-03
    Business Rule: PassportPageRegistry.load() must NOT be called when
    include_passport_links=False — extra file reads violate the contract.

    Preconditions:
        - PassportPageRegistry.load is patched to track invocations.

    Steps:
        1. Construct strategy with include_passport_links=False.
        2. Call execute().

    Expected Result:
        PassportPageRegistry.load() is never called.
    """
    mock_load = mocker.patch.object(PassportPageRegistry, "load", return_value={})
    strategy = make_release_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
        include_passport_links=False,
    )
    strategy.execute()

    mock_load.assert_not_called()


@pytest.mark.business_logic
def test_links_injected_into_view_model_from_registry(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-RS-04
    Business Rule: after loading the registry, passport links are injected into the
    view-model so the template can render clickable links to each passport page.

    Preconditions:
        - PassportPageRegistry.load returns a non-empty pages_map for 'openssl'.
        - A capturing builder records all view_models passed to build().

    Steps:
        1. Patch registry.load to return a pages_map with openssl/1.0.0.
        2. Use a CapturingBuilder instead of the default FakeDocumentBuilder.
        3. Call execute() with include_passport_links=True.

    Expected Result:
        builder.build() is called exactly once.
        The view_model for the 'openssl' component contains a non-empty
        'passport_versions' entry sourced from the registry.
    """
    pages_map = {
        "openssl": {
            "1.0.0": {
                "page_id": "123",
                "page_title": "Документация openssl 1.0.0",
                "version": 1,
            }
        }
    }
    mocker.patch.object(PassportPageRegistry, "load", return_value=pages_map)

    captured_view_models: list[dict] = []

    class CapturingBuilder:
        def build(self, template_name: str, view_model: dict) -> str:
            captured_view_models.append(view_model)
            return "<html>test</html>"

    strategy = ReleasePageStrategy(
        confluence_client=publisher_confluence_client,
        document_builder=CapturingBuilder(),
        parsed_data=publisher_parsed_result,
        space=_SPACE,
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        parent_id=_PARENT_ID,
        include_passport_links=True,
        data_dir=tmp_path,
    )
    strategy.execute()

    assert len(captured_view_models) == 1, "builder.build() must be called exactly once"
    view = captured_view_models[0]
    openssl_view = next(
        (c for c in view.get("components", []) if c.get("name") == "openssl"),
        None,
    )
    assert openssl_view is not None, "openssl component must be present in the view_model"
    passport_versions = openssl_view.get("passport_versions", {})
    assert (
        len(passport_versions) > 0
    ), "passport_versions must be injected from the registry when include_passport_links=True"


@pytest.mark.business_logic
def test_client_error_returns_failure_report(
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """
    BL-RS-05
    Business Rule: if ConfluenceClient.publish_page() raises an exception,
    ReleasePageStrategy returns PublishReport(success=False) instead of propagating.

    Preconditions:
        - A FailingClient whose publish_page always raises RuntimeError.

    Steps:
        1. Construct ReleasePageStrategy with the FailingClient and include_passport_links=False.
        2. Call execute().

    Expected Result:
        report.success is False.
        No exception propagates to the caller.
    """

    class FailingClient:
        def publish_page(self, space, parent_id, title, body_html):
            raise ConfluenceError("Confluence unavailable")

        def find_page(self, title, space=None, expand=None):
            return None

        def get_page(self, page_id, expand=None):
            return None

        def get_page_body(self, space, title, parent_id=None):
            return " "

        def resolve_existing_page_id(self, space, parent_id, title):
            return None

        def create_page(self, space, parent_id, title, body_html):
            return PageResult(id="page-id", version=1, status="created", message="")

    strategy = ReleasePageStrategy(
        confluence_client=FailingClient(),
        document_builder=publisher_document_builder,
        parsed_data=publisher_parsed_result,
        space=_SPACE,
        page_title=_PAGE_TITLE,
        template_name=_TEMPLATE_NAME,
        parent_id=_PARENT_ID,
        include_passport_links=False,
        data_dir=tmp_path,
    )
    report = strategy.execute()

    assert (
        report.success is False
    ), "PublishReport.success must be False when publish_page raises an exception"
