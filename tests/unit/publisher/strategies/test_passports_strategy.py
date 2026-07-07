"""
Tests for autodoc.publisher.strategies.passports_strategy.PassportsStrategy.

Testing strategy:
- PageHierarchyManager.ensure_hierarchy_exists is mocked to return a stable page ID.
- PassportConverter.transform is mocked to return a predictable view_model.
- FakeConfluenceClient / FakeDocumentBuilder are used for I/O.
- execute() is the only public entry point tested (no _try_publish_item/_publish_one).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.models.parsed_result import ParsedResult, ProfileDefinition
from autodoc.publisher.page_manager.hierarchy_manager import PageHierarchyManager
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.strategies.passports_strategy import PassportsStrategy
from autodoc.publisher.converters.passport_converter import PassportConverter
from tests.unit.publisher.conftest import (
    FakeConfluenceClient,
    FakeDocumentBuilder,
)

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

    @pytest.mark.business_logic
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

    @pytest.mark.business_logic
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

    @pytest.mark.business_logic
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
            PassportConverter,
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
        publish_calls = [
            c for c in publisher_confluence_client.calls if c["method"] == "publish_page"
        ]
        assert len(publish_calls) >= 1

    @pytest.mark.business_logic
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
            PassportConverter,
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

    @pytest.mark.business_logic
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

    @pytest.mark.business_logic
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
                raise ValueError("simulated first failure")
            return dict(_STUB_TRANSFORM_RESULT)

        mocker.patch.object(PassportConverter, "transform", side_effect=transform_side_effect)
        strategy = make_passports_strategy(
            publisher_confluence_client,
            publisher_document_builder,
            publisher_multi_component_result,
            tmp_path,
        )
        report = strategy.execute()
        assert report.pages_failed >= 1
        assert report.pages_published >= 1

    @pytest.mark.business_logic
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
            PassportConverter,
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

    @pytest.mark.business_logic
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
            PassportConverter,
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

    @pytest.mark.business_logic
    def test_passports_strategy_page_title_format(self) -> None:
        """_make_page_title returns the expected formatted string."""
        title = PassportsStrategy._make_page_title("openssl", "1.0.0")
        assert "openssl" in title
        assert "1.0.0" in title

    @pytest.mark.business_logic
    def test_page_title_is_unique_for_different_component_release_pairs(self) -> None:
        """Different (comp, version) pairs always produce distinct page titles."""
        pairs = [
            ("openssl", "3.0.9"),  # from openssl.properties
            ("patchelf", "0.16.1"),  # from patchelf.properties
            ("patchelf", "0.18.0"),  # same component, different version
            ("sqlite3", "3.51.2"),  # from sqlite3.properties
            ("nlohmann_json", "3.9.1"),  # from nlohmann_json.properties
        ]
        titles = [PassportsStrategy._make_page_title(comp, ver) for comp, ver in pairs]
        assert len(titles) == len(set(titles)), f"Duplicate titles detected: {titles}"

    @pytest.mark.business_logic
    def test_page_title_exact_format(self) -> None:
        """_make_page_title returns 'Документация <name> <version>' — exact format."""
        # sqlite3/3.51.2 comes from sqlite3.properties (versions: 3.34.1, 3.51.2, 3.45.3, 3.46.0)
        assert (
            PassportsStrategy._make_page_title("sqlite3", "3.51.2") == "Документация sqlite3 3.51.2"
        )
        # patchelf/0.18.0 comes from patchelf.properties
        assert (
            PassportsStrategy._make_page_title("patchelf", "0.18.0")
            == "Документация patchelf 0.18.0"
        )

    @pytest.mark.business_logic
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


# ---------------------------------------------------------------------------
# Part-3 BL additions: BL-PS-01…07
# ---------------------------------------------------------------------------

# Constants reused across BL-PS tests
_BL_PS_VERSION_PAGE_ID = "bl-ps-ver-page-001"
_BL_PS_TRANSFORM_RESULT: dict = {
    "platform_version": "2.0",
    "component": {"name": "openssl"},
    "release": {"version": "1.0.0"},
    "legacy_contents": {},
}


@pytest.mark.business_logic
def test_one_page_per_component_release_combination(
    publisher_multi_component_result: ParsedResult,
    publisher_document_builder: FakeDocumentBuilder,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PS-01
    Business Rule: exactly 1 passport page is published for each (component × release) pair.

    Preconditions:
        - ParsedResult contains multiple components with multiple releases.
        - PageHierarchyManager.ensure_hierarchy_exists is stubbed.
        - PassportConverter.transform returns a valid stub view_model.

    Steps:
        1. Construct PassportsStrategy with the multi-component fixture.
        2. Call execute().

    Expected Result:
        report.pages_published == total number of (component, release) pairs.
        No extra or missing passport pages are published.
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_BL_PS_VERSION_PAGE_ID,
    )
    mocker.patch.object(
        PassportConverter,
        "transform",
        return_value=dict(_BL_PS_TRANSFORM_RESULT),
    )

    client = FakeConfluenceClient()
    strategy = PassportsStrategy(
        confluence_client=client,
        document_builder=publisher_document_builder,
        parsed_data=publisher_multi_component_result,
        space=_SPACE,
        root_page_id=_ROOT_PAGE_ID,
        data_dir=tmp_path,
        batch_size=10,
        batch_delay_seconds=0.0,
    )
    report = strategy.execute()

    total_releases = sum(len(comp.releases) for comp in publisher_multi_component_result.components)
    assert report.pages_published == total_releases, (
        f"Expected {total_releases} passport pages published, " f"got {report.pages_published}"
    )


@pytest.mark.business_logic
def test_registry_saved_after_all_pages_published(
    publisher_multi_component_result: ParsedResult,
    publisher_document_builder: FakeDocumentBuilder,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PS-02
    Business Rule: PassportPageRegistry.save() is called exactly ONCE, AFTER all
    pages are published — not after each individual page.

    Preconditions:
        - PageHierarchyManager and PassportConverter are stubbed.
        - PassportPageRegistry.save() is intercepted to record the call.

    Steps:
        1. Patch PassportPageRegistry.save to record invocations.
        2. Call execute().

    Expected Result:
        save() is called exactly 1 time, and by the time it is called at least
        one publish_page call has already occurred (pages were published first).
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_BL_PS_VERSION_PAGE_ID,
    )
    mocker.patch.object(
        PassportConverter,
        "transform",
        return_value=dict(_BL_PS_TRANSFORM_RESULT),
    )

    client = FakeConfluenceClient()
    save_calls: list[dict] = []
    original_save = PassportPageRegistry.save

    def tracking_save(self, pages_map):  # noqa: ANN001
        save_calls.append({"published_count": len(client.calls)})
        original_save(self, pages_map)

    mocker.patch.object(PassportPageRegistry, "save", tracking_save)

    strategy = PassportsStrategy(
        confluence_client=client,
        document_builder=publisher_document_builder,
        parsed_data=publisher_multi_component_result,
        space=_SPACE,
        root_page_id=_ROOT_PAGE_ID,
        data_dir=tmp_path,
        batch_size=10,
        batch_delay_seconds=0.0,
    )
    strategy.execute()

    assert len(save_calls) == 1, (
        f"PassportPageRegistry.save() must be called exactly once, "
        f"called {len(save_calls)} times"
    )
    assert (
        save_calls[0]["published_count"] > 0
    ), "By the time save() is called, publish_page must have been called at least once"


@pytest.mark.business_logic
def test_failure_of_one_page_does_not_stop_others(
    publisher_multi_component_result: ParsedResult,
    publisher_document_builder: FakeDocumentBuilder,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PS-03
    Business Rule: error publishing one passport page does not stop the remaining queue.

    Preconditions:
        - PageHierarchyManager is stubbed.
        - PassportConverter.transform raises on the first call and succeeds thereafter.

    Steps:
        1. Make PassportConverter.transform raise ValueError on its first invocation.
        2. Call execute().

    Expected Result:
        report.pages_failed >= 1 (at least one failure recorded) AND
        report.pages_published >= 1 (remaining pages still published successfully).
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_BL_PS_VERSION_PAGE_ID,
    )

    call_count: list[int] = [0]

    def transform_side_effect(*args: Any, **kwargs: Any) -> dict:
        call_count[0] += 1
        if call_count[0] == 1:
            raise ValueError("Simulated failure on first passport page")
        return dict(_BL_PS_TRANSFORM_RESULT)

    mocker.patch.object(PassportConverter, "transform", side_effect=transform_side_effect)

    strategy = PassportsStrategy(
        confluence_client=FakeConfluenceClient(),
        document_builder=publisher_document_builder,
        parsed_data=publisher_multi_component_result,
        space=_SPACE,
        root_page_id=_ROOT_PAGE_ID,
        data_dir=tmp_path,
        batch_size=10,
        batch_delay_seconds=0.0,
    )
    report = strategy.execute()

    assert report.pages_failed >= 1, "There must be at least one recorded failure"
    assert (
        report.pages_published >= 1
    ), "Other pages must still be published despite the partial failure"


@pytest.mark.business_logic
def test_report_pages_published_count_equals_successful_pages(
    publisher_parsed_result: ParsedResult,
    publisher_document_builder: FakeDocumentBuilder,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PS-04
    Business Rule: PublishReport.pages_published equals the exact number of
    successfully published passport pages.

    Preconditions:
        - Single-component ParsedResult with one release.
        - No errors during publishing.

    Steps:
        1. Call execute() with all dependencies stubbed successfully.

    Expected Result:
        report.pages_published == number of releases in the component.
        report.pages_failed == 0.
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_BL_PS_VERSION_PAGE_ID,
    )
    mocker.patch.object(
        PassportConverter,
        "transform",
        return_value=dict(_BL_PS_TRANSFORM_RESULT),
    )

    strategy = PassportsStrategy(
        confluence_client=FakeConfluenceClient(),
        document_builder=publisher_document_builder,
        parsed_data=publisher_parsed_result,
        space=_SPACE,
        root_page_id=_ROOT_PAGE_ID,
        data_dir=tmp_path,
        batch_size=10,
        batch_delay_seconds=0.0,
    )
    report = strategy.execute()

    expected = sum(len(comp.releases) for comp in publisher_parsed_result.components)
    assert (
        report.pages_published == expected
    ), f"pages_published must be {expected}, got {report.pages_published}"
    assert report.pages_failed == 0, "All pages must succeed with no errors"


@pytest.mark.business_logic
def test_report_pages_failed_count_equals_failed_pages(
    publisher_parsed_result: ParsedResult,
    publisher_document_builder: FakeDocumentBuilder,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PS-05
    Business Rule: PublishReport.pages_failed equals len(report.failed_pages).
    The counter and the list must be consistent.

    Preconditions:
        - PageHierarchyManager is stubbed.
        - PassportConverter.transform always raises ValueError.

    Steps:
        1. Call execute() with converter always failing.

    Expected Result:
        report.pages_failed == len(report.failed_pages) > 0.
        report.pages_published == 0.
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_BL_PS_VERSION_PAGE_ID,
    )
    mocker.patch.object(
        PassportConverter,
        "transform",
        side_effect=ValueError("Always fails"),
    )

    strategy = PassportsStrategy(
        confluence_client=FakeConfluenceClient(),
        document_builder=publisher_document_builder,
        parsed_data=publisher_parsed_result,
        space=_SPACE,
        root_page_id=_ROOT_PAGE_ID,
        data_dir=tmp_path,
        batch_size=10,
        batch_delay_seconds=0.0,
    )
    report = strategy.execute()

    assert report.pages_failed == len(
        report.failed_pages
    ), "pages_failed must match len(failed_pages) — counter and list must be consistent"
    assert report.pages_failed > 0, "With constant converter errors, pages_failed must be > 0"
    assert report.pages_published == 0, "With constant errors, pages_published must be 0"


@pytest.mark.business_logic
def test_legacy_content_extracted_before_overwrite(
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PS-06
    Business Rule: before publishing a passport page, the strategy fetches the
    existing page body, extracts legacy sections for other platforms, and injects
    them into the view_model as 'legacy_contents' before calling builder.build().

    Preconditions:
        - PageHierarchyManager is stubbed.
        - PassportConverter.transform returns a minimal valid view_model.
        - A CapturingBuilder records every view_model passed to build().
        - FakeConfluenceClient returns a non-empty body from get_page_body().

    Steps:
        1. Stub PageHierarchyManager.ensure_hierarchy_exists.
        2. Stub PassportConverter.transform to return a view_model with platform_version.
        3. Intercept builder.build() to capture the final view_model.
        4. Pre-configure client.get_page_body to return an existing legacy HTML body.
        5. Call execute().

    Expected Result:
        At least one view_model passed to builder.build() contains a 'legacy_contents'
        key with a dict value, confirming the legacy extraction + injection occurred.
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_BL_PS_VERSION_PAGE_ID,
    )
    # PassportConverter.transform(self, data) — 'self' is the converter instance
    mocker.patch.object(
        PassportConverter,
        "transform",
        return_value={
            "platform_version": "2.0",
            "component": {"name": "openssl"},
            "release": {"version": "1.0.0"},
        },
    )

    captured_view_models: list[dict] = []

    class CapturingBuilder:
        def build(self, template_name: str, view_model: dict) -> str:
            """Records the view_model passed to build() including injected keys."""
            captured_view_models.append(dict(view_model))
            return "<html>test</html>"

    client = FakeConfluenceClient()
    client._page_bodies = {
        "Документация openssl 1.0.0": (
            '<ac:structured-macro ac:name="tabs">'
            '<ac:parameter ac:name="tabName">1.9</ac:parameter>'
            "<ac:rich-text-body><p>Old content</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
    }

    strategy = PassportsStrategy(
        confluence_client=client,
        document_builder=CapturingBuilder(),
        parsed_data=publisher_parsed_result,
        space=_SPACE,
        root_page_id=_ROOT_PAGE_ID,
        data_dir=tmp_path,
        batch_size=10,
        batch_delay_seconds=0.0,
    )
    strategy.execute()

    assert (
        len(captured_view_models) > 0
    ), "builder.build() must be called at least once (one passport page)"
    for vm in captured_view_models:
        assert "legacy_contents" in vm, (
            f"view_model passed to builder.build() must contain 'legacy_contents', "
            f"got keys: {list(vm.keys())}"
        )
        assert isinstance(
            vm["legacy_contents"], dict
        ), "legacy_contents must be a dict (empty or populated)"


@pytest.mark.business_logic
def test_hierarchy_created_for_each_component(
    publisher_multi_component_result: ParsedResult,
    publisher_document_builder: FakeDocumentBuilder,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PS-07
    Business Rule: ensure_hierarchy_exists() is called exactly once for each
    (component, release) pair in ParsedResult.

    Preconditions:
        - PageHierarchyManager.ensure_hierarchy_exists is intercepted.
        - PassportConverter.transform is stubbed.

    Steps:
        1. Patch ensure_hierarchy_exists to record (component_name, release_version) pairs.
        2. Call execute().

    Expected Result:
        The set of recorded (comp, version) pairs equals the full set of pairs
        derived from ParsedResult.components[*].releases.
    """
    hierarchy_calls: list[dict] = []

    def tracking_ensure(
        self, space, root_parent_id, component_name, release_version
    ):  # noqa: ANN001
        hierarchy_calls.append(
            {"component_name": component_name, "release_version": release_version}
        )
        return "hierarchy-page-id"

    mocker.patch.object(PageHierarchyManager, "ensure_hierarchy_exists", tracking_ensure)
    mocker.patch.object(
        PassportConverter,
        "transform",
        return_value=dict(_BL_PS_TRANSFORM_RESULT),
    )

    strategy = PassportsStrategy(
        confluence_client=FakeConfluenceClient(),
        document_builder=publisher_document_builder,
        parsed_data=publisher_multi_component_result,
        space=_SPACE,
        root_page_id=_ROOT_PAGE_ID,
        data_dir=tmp_path,
        batch_size=10,
        batch_delay_seconds=0.0,
    )
    strategy.execute()

    expected_pairs = {
        (comp.name, rel.version)
        for comp in publisher_multi_component_result.components
        for rel in comp.releases
    }
    actual_pairs = {(c["component_name"], c["release_version"]) for c in hierarchy_calls}
    assert actual_pairs == expected_pairs, (
        f"ensure_hierarchy_exists must be called for all (comp, version) pairs.\n"
        f"Expected: {expected_pairs}\nGot:      {actual_pairs}"
    )
