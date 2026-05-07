"""
Tests for autodoc.publisher.strategies.profile_strategy.ProfileCentricStrategy.

Testing strategy:
- ProfileCentricStrategy delegates to _publish_single_page (tested via outcome).
- PassportPageRegistry.load() is mocked when include_passport_links=True.
- FakeConfluenceClient / FakeDocumentBuilder provide deterministic I/O.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.interfaces.base_publish_strategy import BasePublishStrategy
from autodoc.publisher.strategies.profile_strategy import ProfileCentricStrategy
from autodoc.tests.unit.publisher.conftest import (
    FakeConfluenceClient,
    FakeDocumentBuilder,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SPACE: str = "TEST"
_PAGE_TITLE: str = "Platform 2.0 Profile-Centric Docs"
_TEMPLATE_NAME: str = "profile_centric.jinja2"
_PARENT_ID: str = "parent-001"

# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------


def make_profile_strategy(
    client: FakeConfluenceClient,
    builder: FakeDocumentBuilder,
    data: ParsedResult,
    tmp_path: Path,
    include_passport_links: bool = True,
) -> ProfileCentricStrategy:
    """Create a ProfileCentricStrategy with sensible defaults for unit tests."""
    return ProfileCentricStrategy(
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


class TestProfileCentricStrategyExecute:
    """Tests for ProfileCentricStrategy.execute() behaviour."""

    def test_profile_centric_strategy_execute_returns_success_report(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """A successful execute() returns report.success=True and pages_published=1."""
        mocker.patch.object(PassportPageRegistry, "load", return_value={})
        strategy = make_profile_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_parsed_result,
            tmp_path,
        )
        report = strategy.execute()
        assert report.success is True
        assert report.pages_published == 1

    def test_profile_centric_strategy_loads_registry_when_include_links_true(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """When include_passport_links=True, PassportPageRegistry.load() is called once."""
        mock_load = mocker.patch.object(PassportPageRegistry, "load", return_value={})
        strategy = make_profile_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_parsed_result,
            tmp_path,
            include_passport_links=True,
        )
        strategy.execute()
        mock_load.assert_called_once()

    def test_profile_centric_strategy_skips_registry_when_include_links_false(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """When include_passport_links=False, PassportPageRegistry.load() is never called."""
        mock_load = mocker.patch.object(PassportPageRegistry, "load", return_value={})
        strategy = make_profile_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_parsed_result,
            tmp_path,
            include_passport_links=False,
        )
        strategy.execute()
        mock_load.assert_not_called()

    def test_profile_centric_strategy_execute_calls_publish_page(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """execute() triggers exactly one publish_page call with the expected title."""
        mocker.patch.object(PassportPageRegistry, "load", return_value={})
        strategy = make_profile_strategy(
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

    def test_profile_centric_strategy_execute_returns_failure_on_client_error(
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
            raise RuntimeError("timeout")

        publisher_confluence_client.publish_page = raise_runtime

        strategy = make_profile_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_parsed_result,
            tmp_path,
        )
        report = strategy.execute()
        assert report.success is False


# ---------------------------------------------------------------------------
# Registry test
# ---------------------------------------------------------------------------


class TestProfileCentricStrategyRegistry:
    """Tests for ProfileCentricStrategy registration."""

    def test_profile_centric_strategy_registered_as_profile_centric(self) -> None:
        """'profile_centric' is present in available_strategies()."""
        assert "profile_centric" in BasePublishStrategy.available_strategies()
