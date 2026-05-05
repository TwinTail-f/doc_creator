"""
Tests for autodoc.publisher.strategies.passports_strategy.PassportsStrategy.

Testing strategy:
- PageHierarchyManager.ensure_hierarchy_exists is mocked to return a stable page ID.
- PassportTransformer.transform is mocked to return a predictable view_model.
- FakeConfluenceClient / FakeDocumentBuilder are used for I/O.
- execute() is the only public entry point tested (no _try_publish_item/_publish_one).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from autodoc.models.component import Component, ProfileBuild, Release
from autodoc.models.parsed_result import ParsedResult, ProfileDefinition
from autodoc.publisher.page_manager.hierarchy_manager import PageHierarchyManager
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.strategies.passports_strategy import PassportsStrategy
from autodoc.publisher.transformers.passport_transformer import PassportTransformer
from autodoc.tests.unit.publisher.conftest import FakeConfluenceClient, FakeDocumentBuilder

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SPACE: str = "TEST"
_ROOT_PAGE_ID: str = "root-001"
_VERSION_PAGE_ID: str = "ver-page-001"
_REGISTRY_FILENAME: str = "passport_pages.json"

_STUB_TRANSFORM_RESULT: dict[str, Any] = {
    "platform_version": "2.0",
    "component": {"name": "openssl"},
    "release": {"version": "1.0.0"},
    "legacy_contents": {},
}

# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------


def make_passports_strategy(
    client: FakeConfluenceClient,
    builder: FakeDocumentBuilder,
    data: ParsedResult,
    tmp_path: Path,
) -> PassportsStrategy:
    """Create a PassportsStrategy instance with zero batch delay for fast tests."""
    return PassportsStrategy(
        confluence_client=client,
        document_builder=builder,
        parsed_data=data,
        space=_SPACE,
        root_page_id=_ROOT_PAGE_ID,
        data_dir=tmp_path,
        batch_size=10,
        batch_delay_seconds=0.0,
    )


# ---------------------------------------------------------------------------
# Initialisation tests
# ---------------------------------------------------------------------------


class TestPassportsStrategyInit:
    """Tests for PassportsStrategy.__init__ validation."""

    def test_passports_strategy_init_raises_on_empty_space(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
    ) -> None:
        """An empty space string raises ValueError."""
        with pytest.raises(ValueError, match="space"):
            PassportsStrategy(
                confluence_client=publisher_confluence_client,
                document_builder=publisher_document_builder,
                parsed_data=publisher_parsed_result,
                space="",
                root_page_id=_ROOT_PAGE_ID,
                data_dir=tmp_path,
            )

    def test_passports_strategy_init_raises_on_empty_root_page_id(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
    ) -> None:
        """An empty root_page_id string raises ValueError."""
        with pytest.raises(ValueError, match="root_page_id"):
            PassportsStrategy(
                confluence_client=publisher_confluence_client,
                document_builder=publisher_document_builder,
                parsed_data=publisher_parsed_result,
                space=_SPACE,
                root_page_id="",
                data_dir=tmp_path,
            )


# ---------------------------------------------------------------------------
# execute() tests
# ---------------------------------------------------------------------------


class TestPassportsStrategyExecute:
    """Tests for PassportsStrategy.execute() behaviour."""

    def test_passports_strategy_execute_publishes_one_page_per_component_release(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """At least one publish_page call is made for a single-component result."""
        mocker.patch.object(
            PageHierarchyManager,
            "ensure_hierarchy_exists",
            return_value=_VERSION_PAGE_ID,
        )
        mocker.patch.object(
            PassportTransformer,
            "transform",
            return_value=dict(_STUB_TRANSFORM_RESULT),
        )
        strategy = make_passports_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_parsed_result,
            tmp_path,
        )
        strategy.execute()
        publish_calls = [c for c in publisher_confluence_client.calls if c["method"] == "publish_page"]
        assert len(publish_calls) >= 1

    def test_passports_strategy_execute_report_success_when_no_errors(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """report.success is True when all pages are published without errors."""
        mocker.patch.object(
            PageHierarchyManager,
            "ensure_hierarchy_exists",
            return_value=_VERSION_PAGE_ID,
        )
        mocker.patch.object(
            PassportTransformer,
            "transform",
            return_value=dict(_STUB_TRANSFORM_RESULT),
        )
        strategy = make_passports_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_parsed_result,
            tmp_path,
        )
        report = strategy.execute()
        assert report.success is True

    def test_passports_strategy_execute_records_failed_component_without_releases(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_profile_definition: ProfileDefinition,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """Components with no releases are recorded as errors in the report."""
        empty_component = Component(
            name="no-release-lib",
            description="Component without releases",
            git_project="DEP",
            git_repo="contrib_empty",
            releases=[],
        )
        data = ParsedResult(
            generated_at="2024-01-15T12:00:00",
            platform_version="2.0",
            profile_definitions=[publisher_profile_definition],
            components=[empty_component],
        )
        strategy = make_passports_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            data,
            tmp_path,
        )
        report = strategy.execute()
        assert any("no-release-lib" in err for err in report.errors)

    def test_passports_strategy_execute_continues_after_single_failure(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_multi_component_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """A failure on one page does not prevent other pages from being published."""
        mocker.patch.object(
            PageHierarchyManager,
            "ensure_hierarchy_exists",
            return_value=_VERSION_PAGE_ID,
        )
        call_count: list[int] = [0]

        def transform_side_effect(*args: Any, **kwargs: Any) -> dict:
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("simulated first failure")
            return dict(_STUB_TRANSFORM_RESULT)

        mocker.patch.object(PassportTransformer, "transform", side_effect=transform_side_effect)
        strategy = make_passports_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_multi_component_result,
            tmp_path,
        )
        report = strategy.execute()
        assert report.pages_failed >= 1
        assert report.pages_published >= 1

    def test_passports_strategy_execute_saves_registry_after_publish(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """After execute(), passport_pages.json exists in data_dir."""
        mocker.patch.object(
            PageHierarchyManager,
            "ensure_hierarchy_exists",
            return_value=_VERSION_PAGE_ID,
        )
        mocker.patch.object(
            PassportTransformer,
            "transform",
            return_value=dict(_STUB_TRANSFORM_RESULT),
        )
        strategy = make_passports_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_parsed_result,
            tmp_path,
        )
        strategy.execute()
        assert (tmp_path / _REGISTRY_FILENAME).exists()

    def test_passports_strategy_execute_report_contains_details(
        self,
        publisher_confluence_client: FakeConfluenceClient,
        publisher_document_builder: FakeDocumentBuilder,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: Any,
    ) -> None:
        """A successful publish produces at least one detail entry with page_title and page_id."""
        mocker.patch.object(
            PageHierarchyManager,
            "ensure_hierarchy_exists",
            return_value=_VERSION_PAGE_ID,
        )
        mocker.patch.object(
            PassportTransformer,
            "transform",
            return_value=dict(_STUB_TRANSFORM_RESULT),
        )
        strategy = make_passports_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_parsed_result,
            tmp_path,
        )
        report = strategy.execute()
        assert len(report.details) >= 1
        detail = report.details[0]
        assert "page_title" in detail
        assert "page_id" in detail


# ---------------------------------------------------------------------------
# Static / utility method tests
# ---------------------------------------------------------------------------


class TestPassportsStrategyUtils:
    """Tests for PassportsStrategy static helper methods."""

    def test_passports_strategy_page_title_format(self) -> None:
        """_make_page_title returns the expected formatted string."""
        title = PassportsStrategy._make_page_title("openssl", "1.0.0")
        assert "openssl" in title
        assert "1.0.0" in title

    def test_passports_strategy_build_pages_map_structure(self) -> None:
        """_build_pages_map produces the nested {comp: {version: {...}}} structure."""
        details = [
            {
                "component_name": "openssl",
                "release_version": "1.0.0",
                "page_title": "T",
                "page_id": "p-1",
                "version": 1,
                "status": "created",
            }
        ]
        result = PassportsStrategy._build_pages_map(details)
        assert "openssl" in result
        assert "1.0.0" in result["openssl"]
        entry = result["openssl"]["1.0.0"]
        assert entry["page_id"] == "p-1"
        assert entry["page_title"] == "T"
        assert entry["version"] == 1
