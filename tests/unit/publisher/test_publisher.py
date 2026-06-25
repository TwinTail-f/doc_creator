"""
Tests for autodoc.publisher.publisher.DocumentPublisher.

Testing strategy:
- ConfluenceClient and DocumentBuilder constructors are mocked so no real HTTP
  session or filesystem is needed.
- BasePublishStrategy.create is mocked to isolate the publisher from strategies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.publisher import DocumentPublisher
from autodoc.publisher.strategies.models.publish_report import PublishReport

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SPACE: str = "TEST"
_ROOT_PAGE_ID: str = "root-001"
_RELEASE_PAGE_TITLE: str = "Platform 2.0 Release"
_RELEASE_TEMPLATE: str = "release_doc.jinja2"

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def publisher_document_publisher(
    minimal_confluence_config: dict,
    tmp_path: Path,
    mocker: MockerFixture,
) -> DocumentPublisher:
    """DocumentPublisher with mocked infrastructure dependencies."""
    config = ConfluenceConfigSchema(**minimal_confluence_config)
    mocker.patch("autodoc.publisher.publisher.ConfluenceClient")
    mocker.patch("autodoc.publisher.publisher.DocumentBuilder")
    rendering_dir = tmp_path / "rendering"
    rendering_dir.mkdir()
    return DocumentPublisher(
        confluence_config=config,
        rendering_dir=rendering_dir,
        data_dir=tmp_path,
    )


def _mock_strategy(report: PublishReport, mocker: MockerFixture) -> MagicMock:
    """Create a mock strategy whose execute() returns the given report."""
    mock = mocker.MagicMock()
    mock.execute.return_value = report
    return mock


# ---------------------------------------------------------------------------
# publish() tests
# ---------------------------------------------------------------------------


class TestDocumentPublisherPublish:
    """Tests for DocumentPublisher.publish()."""

    @pytest.mark.business_logic
    def test_publisher_publish_delegates_to_strategy_execute(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """publish() calls strategy.execute() exactly once."""
        expected_report = PublishReport(success=True, pages_published=1)
        mock_strategy = _mock_strategy(expected_report, mocker)
        mocker.patch(
            "autodoc.publisher.publisher.BasePublishStrategy.create",
            return_value=mock_strategy,
        )
        publisher_document_publisher.publish("release", publisher_parsed_result)
        mock_strategy.execute.assert_called_once()

    @pytest.mark.business_logic
    def test_publisher_publish_passes_space_from_config(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """publish() forwards space from config to BasePublishStrategy.create()."""
        mock_create = mocker.patch(
            "autodoc.publisher.publisher.BasePublishStrategy.create",
            return_value=_mock_strategy(PublishReport(success=True, pages_published=1), mocker),
        )
        publisher_document_publisher.publish("release", publisher_parsed_result)
        _, kwargs = mock_create.call_args
        assert kwargs["space"] == _SPACE

    @pytest.mark.infrastructure
    def test_publisher_publish_passes_data_dir(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """publish() forwards data_dir to BasePublishStrategy.create()."""
        mock_create = mocker.patch(
            "autodoc.publisher.publisher.BasePublishStrategy.create",
            return_value=_mock_strategy(PublishReport(success=True, pages_published=1), mocker),
        )
        publisher_document_publisher.publish("release", publisher_parsed_result)
        _, kwargs = mock_create.call_args
        assert kwargs["data_dir"] == tmp_path

    @pytest.mark.business_logic
    def test_publisher_publish_returns_strategy_report(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """publish() returns exactly the PublishReport from strategy.execute()."""
        expected = PublishReport(success=True, pages_published=5)
        mocker.patch(
            "autodoc.publisher.publisher.BasePublishStrategy.create",
            return_value=_mock_strategy(expected, mocker),
        )
        result = publisher_document_publisher.publish("release", publisher_parsed_result)
        assert result is expected


# ---------------------------------------------------------------------------
# publish_all() tests
# ---------------------------------------------------------------------------


class TestDocumentPublisherPublishAll:
    """Tests for DocumentPublisher.publish_all()."""

    def _patch_create(
        self,
        mocker: MockerFixture,
        passports_report: PublishReport,
        release_report: PublishReport,
    ) -> None:
        """Patch BasePublishStrategy.create to return two strategies in order."""
        call_order: list[str] = []

        passports_mock = mocker.MagicMock()

        def passports_execute() -> PublishReport:
            call_order.append("passports")
            return passports_report

        passports_mock.execute.side_effect = passports_execute

        release_mock = mocker.MagicMock()

        def release_execute() -> PublishReport:
            call_order.append("release")
            return release_report

        release_mock.execute.side_effect = release_execute

        strategies = iter([passports_mock, release_mock])
        mocker.patch(
            "autodoc.publisher.publisher.BasePublishStrategy.create",
            side_effect=lambda *a, **kw: next(strategies),
        )
        # Expose call_order for order verification
        mocker.call_order = call_order  # type: ignore[attr-defined]

    @pytest.mark.business_logic
    def test_publisher_publish_all_runs_passports_then_release(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """publish_all() executes passports strategy before release strategy."""
        call_order: list[str] = []

        passports_mock = mocker.MagicMock()
        passports_mock.execute.side_effect = lambda: call_order.append(
            "passports"
        ) or PublishReport(success=True, pages_published=1)

        release_mock = mocker.MagicMock()
        release_mock.execute.side_effect = lambda: call_order.append("release") or PublishReport(
            success=True, pages_published=1
        )

        strategies = iter([passports_mock, release_mock])
        mocker.patch(
            "autodoc.publisher.publisher.BasePublishStrategy.create",
            side_effect=lambda *a, **kw: next(strategies),
        )

        publisher_document_publisher.publish_all(
            parsed_data=publisher_parsed_result,
            passports_root_page_id=_ROOT_PAGE_ID,
            release_page_title=_RELEASE_PAGE_TITLE,
            release_template_name=_RELEASE_TEMPLATE,
        )
        assert call_order == ["passports", "release"]

    @pytest.mark.business_logic
    def test_publisher_publish_all_merges_reports(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """Merged report sums pages_published from both strategies."""
        passports_report = PublishReport(success=True, pages_published=3)
        release_report = PublishReport(success=True, pages_published=1)

        strategies = iter(
            [
                _mock_strategy(passports_report, mocker),
                _mock_strategy(release_report, mocker),
            ]
        )
        mocker.patch(
            "autodoc.publisher.publisher.BasePublishStrategy.create",
            side_effect=lambda *a, **kw: next(strategies),
        )

        result = publisher_document_publisher.publish_all(
            parsed_data=publisher_parsed_result,
            passports_root_page_id=_ROOT_PAGE_ID,
            release_page_title=_RELEASE_PAGE_TITLE,
            release_template_name=_RELEASE_TEMPLATE,
        )
        assert result.pages_published == 4

    @pytest.mark.business_logic
    def test_publisher_publish_all_success_false_if_any_strategy_fails(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """If either strategy report has success=False, the merged report is False."""
        passports_report = PublishReport(success=False, pages_published=0, errors=["fail"])
        release_report = PublishReport(success=True, pages_published=1)

        strategies = iter(
            [
                _mock_strategy(passports_report, mocker),
                _mock_strategy(release_report, mocker),
            ]
        )
        mocker.patch(
            "autodoc.publisher.publisher.BasePublishStrategy.create",
            side_effect=lambda *a, **kw: next(strategies),
        )

        result = publisher_document_publisher.publish_all(
            parsed_data=publisher_parsed_result,
            passports_root_page_id=_ROOT_PAGE_ID,
            release_page_title=_RELEASE_PAGE_TITLE,
            release_template_name=_RELEASE_TEMPLATE,
        )
        assert result.success is False

    @pytest.mark.business_logic
    def test_publisher_publish_all_merges_errors_lists(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """Errors from both strategies are combined in the merged report."""
        passports_report = PublishReport(success=False, pages_published=0, errors=["err1"])
        release_report = PublishReport(success=False, pages_published=0, errors=["err2"])

        strategies = iter(
            [
                _mock_strategy(passports_report, mocker),
                _mock_strategy(release_report, mocker),
            ]
        )
        mocker.patch(
            "autodoc.publisher.publisher.BasePublishStrategy.create",
            side_effect=lambda *a, **kw: next(strategies),
        )

        result = publisher_document_publisher.publish_all(
            parsed_data=publisher_parsed_result,
            passports_root_page_id=_ROOT_PAGE_ID,
            release_page_title=_RELEASE_PAGE_TITLE,
            release_template_name=_RELEASE_TEMPLATE,
        )
        assert "err1" in result.errors
        assert "err2" in result.errors
