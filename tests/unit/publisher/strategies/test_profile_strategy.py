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
from autodoc.publisher.strategies.base_publish_strategy import BasePublishStrategy
from autodoc.publisher.strategies.profile_strategy import ProfileCentricStrategy
from tests.unit.publisher.conftest import (
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

    @pytest.mark.business_logic
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

    @pytest.mark.business_logic
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

    @pytest.mark.business_logic
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

    @pytest.mark.infrastructure
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

    @pytest.mark.business_logic
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

    @pytest.mark.business_logic
    def test_profile_centric_strategy_registered_as_profile_centric(self) -> None:
        """'profile_centric' is present in available_strategies()."""
        assert "profile_centric" in BasePublishStrategy.available_strategies()


# ---------------------------------------------------------------------------
# Part-3 BL additions: BL-PCS-01…04
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
    BL-PCS-01
    Business Rule: ProfileCentricStrategy.execute() publishes exactly one Confluence page.

    Preconditions:
        - PassportPageRegistry.load is stubbed (no actual file I/O).

    Steps:
        1. Construct ProfileCentricStrategy with include_passport_links=False.
        2. Call execute().

    Expected Result:
        report.pages_published == 1.
    """
    mocker.patch.object(PassportPageRegistry, "load", return_value={})
    strategy = make_profile_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
        include_passport_links=False,
    )
    report = strategy.execute()

    assert (
        report.pages_published == 1
    ), f"ProfileCentricStrategy must publish 1 page, got: {report.pages_published}"


@pytest.mark.business_logic
def test_registered_as_profile_centric_type() -> None:
    """
    BL-PCS-02
    Business Rule: ProfileCentricStrategy is registered under 'profile_centric'
    in the BasePublishStrategy registry, enabling `publish profile` CLI command.

    Preconditions:
        - BasePublishStrategy registry is populated at import time.

    Steps:
        1. Call BasePublishStrategy.available_strategies().

    Expected Result:
        'profile_centric' is present in the returned list of strategy types.
    """
    available = BasePublishStrategy.available_strategies()
    assert (
        "profile_centric" in available
    ), f"'profile_centric' must be in available_strategies, got: {available}"


@pytest.mark.business_logic
def test_registry_loaded_when_include_links_true(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PCS-03
    Business Rule: when include_passport_links=True, ProfileCentricStrategy must
    load the passport registry to inject links into the view-model.

    Preconditions:
        - PassportPageRegistry.load is patched to track invocations.

    Steps:
        1. Construct strategy with include_passport_links=True.
        2. Call execute().

    Expected Result:
        PassportPageRegistry.load() is called at least once.
    """
    mock_load = mocker.patch.object(PassportPageRegistry, "load", return_value={})
    strategy = make_profile_strategy(
        publisher_confluence_client,
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
        include_passport_links=True,
    )
    strategy.execute()

    mock_load.assert_called_once_with()


@pytest.mark.business_logic
def test_registry_skipped_when_include_links_false(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PCS-04
    Business Rule: when include_passport_links=False, ProfileCentricStrategy must
    NOT load the registry — unnecessary file reads are avoided.

    Preconditions:
        - PassportPageRegistry.load is patched to track invocations.

    Steps:
        1. Construct strategy with include_passport_links=False.
        2. Call execute().

    Expected Result:
        PassportPageRegistry.load() is never called.
    """
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
