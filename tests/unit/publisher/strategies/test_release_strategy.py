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

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.strategies.base_publish_strategy import BasePublishStrategy
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
            c
            for c in publisher_confluence_client.calls
            if c["method"] == "publish_page"
        ]
        assert len(publish_calls) == 1
        assert publish_calls[0]["title"] == _PAGE_TITLE

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

    def test_release_strategy_execute_returns_failure_on_client_error(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """If publish_page raises RuntimeError, report.success is False."""
        mocker.patch.object(PassportPageRegistry, "load", return_value={})

        def raise_runtime(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("connection refused")

        publisher_confluence_client.publish_page = raise_runtime

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

    def test_release_make_converter_creates_full_release_converter(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
    ) -> None:
        """BasePublishStrategy.create('release', ...) wires a FullReleaseConverter."""
        strategy = BasePublishStrategy.create(
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

    def test_release_strategy_registered_as_release(self) -> None:
        """'release' is present in available_strategies()."""
        assert "release" in BasePublishStrategy.available_strategies()
