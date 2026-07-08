"""
Тесты для autodoc.publisher.publisher.DocumentPublisher.

Стратегия тестирования:
- Конструкторы ConfluenceClient и DocumentBuilder мокаются, поэтому реальная
  HTTP-сессия или файловая система не требуются.
- create_strategy мокается, чтобы изолировать паблишер от стратегий.
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

_SPACE: str = "TEST"
_ROOT_PAGE_ID: str = "root-001"
_RELEASE_PAGE_TITLE: str = "Platform 2.0 Release"
_RELEASE_TEMPLATE: str = "release_doc.jinja2"


@pytest.fixture
def publisher_document_publisher(
    minimal_confluence_config: dict,
    tmp_path: Path,
    mocker: MockerFixture,
) -> DocumentPublisher:
    """DocumentPublisher с замоканными инфраструктурными зависимостями."""
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
    """Создаёт мок стратегии, чей execute() возвращает заданный отчёт."""
    mock = mocker.MagicMock()
    mock.execute.return_value = report
    return mock


class TestDocumentPublisherPublish:
    """Тесты для DocumentPublisher.publish()."""

    @pytest.mark.contract
    def test_publisher_publish_delegates_to_strategy_execute(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """publish() вызывает strategy.execute() ровно один раз."""
        expected_report = PublishReport(success=True, pages_published=1)
        mock_strategy = _mock_strategy(expected_report, mocker)
        mocker.patch(
            "autodoc.publisher.publisher.create_strategy",
            return_value=mock_strategy,
        )
        publisher_document_publisher.publish("release", publisher_parsed_result)
        mock_strategy.execute.assert_called_once()

    @pytest.mark.contract
    def test_publisher_publish_passes_space_from_config(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """publish() передаёт space из конфигурации в create_strategy()."""
        mock_create = mocker.patch(
            "autodoc.publisher.publisher.create_strategy",
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
        """publish() передаёт data_dir в create_strategy()."""
        mock_create = mocker.patch(
            "autodoc.publisher.publisher.create_strategy",
            return_value=_mock_strategy(PublishReport(success=True, pages_published=1), mocker),
        )
        publisher_document_publisher.publish("release", publisher_parsed_result)
        _, kwargs = mock_create.call_args
        assert kwargs["data_dir"] == tmp_path

    @pytest.mark.contract
    def test_publisher_publish_returns_strategy_report(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """publish() возвращает именно тот PublishReport, что вернул strategy.execute()."""
        expected = PublishReport(success=True, pages_published=5)
        mocker.patch(
            "autodoc.publisher.publisher.create_strategy",
            return_value=_mock_strategy(expected, mocker),
        )
        result = publisher_document_publisher.publish("release", publisher_parsed_result)
        assert result is expected


class TestDocumentPublisherPublishAll:
    """Тесты для DocumentPublisher.publish_all()."""

    def _patch_create(
        self,
        mocker: MockerFixture,
        passports_report: PublishReport,
        release_report: PublishReport,
    ) -> list[str]:
        """
        Подменяет create_strategy, чтобы вернуть по порядку две стратегии.

        Args:
            mocker: Фикстура pytest-mock для патчинга.
            passports_report: Отчёт, который вернёт мок стратегии паспортов.
            release_report: Отчёт, который вернёт мок стратегии релиза.

        Returns:
            Список, в который будет записываться порядок вызова execute()
            каждой из стратегий (``"passports"`` / ``"release"``).
        """
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
            "autodoc.publisher.publisher.create_strategy",
            side_effect=lambda *a, **kw: next(strategies),
        )
        return call_order

    @pytest.mark.business_logic
    def test_publisher_publish_all_runs_passports_then_release(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """publish_all() выполняет стратегию паспортов раньше стратегии релиза."""
        call_order = self._patch_create(
            mocker,
            PublishReport(success=True, pages_published=1),
            PublishReport(success=True, pages_published=1),
        )

        publisher_document_publisher.publish_all(
            parsed_data=publisher_parsed_result,
            passports_root_parent_id=_ROOT_PAGE_ID,
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
        """Итоговый отчёт суммирует pages_published обеих стратегий."""
        self._patch_create(
            mocker,
            PublishReport(success=True, pages_published=3),
            PublishReport(success=True, pages_published=1),
        )

        result = publisher_document_publisher.publish_all(
            parsed_data=publisher_parsed_result,
            passports_root_parent_id=_ROOT_PAGE_ID,
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
        """Если отчёт хотя бы одной стратегии имеет success=False, итоговый отчёт тоже False."""
        self._patch_create(
            mocker,
            PublishReport(success=False, pages_published=0, errors=["fail"]),
            PublishReport(success=True, pages_published=1),
        )

        result = publisher_document_publisher.publish_all(
            parsed_data=publisher_parsed_result,
            passports_root_parent_id=_ROOT_PAGE_ID,
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
        """Ошибки обеих стратегий объединяются в итоговом отчёте."""
        self._patch_create(
            mocker,
            PublishReport(success=False, pages_published=0, errors=["err1"]),
            PublishReport(success=False, pages_published=0, errors=["err2"]),
        )

        result = publisher_document_publisher.publish_all(
            parsed_data=publisher_parsed_result,
            passports_root_parent_id=_ROOT_PAGE_ID,
            release_page_title=_RELEASE_PAGE_TITLE,
            release_template_name=_RELEASE_TEMPLATE,
        )
        assert "err1" in result.errors
        assert "err2" in result.errors

    @pytest.mark.business_logic
    def test_publisher_publish_all_with_profile_merges_three_reports(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """
        publish_all() с profile_title/profile_template_name публикует и объединяет три отчёта.

        Также проверяет гарантию порядка: к моменту чтения publish_profile_page()
        details[0] релизного отчёта всё ещё указывает на страницу релиза, а не
        на смешанный/объединённый отчёт.
        """
        passports_report = PublishReport(success=True, pages_published=2)
        release_report = PublishReport(
            success=True,
            pages_published=1,
            details=[{"page_id": "release-page-1"}],
        )
        profile_report = PublishReport(success=True, pages_published=1)

        strategies = iter(
            [
                _mock_strategy(passports_report, mocker),
                _mock_strategy(release_report, mocker),
            ]
        )
        mocker.patch(
            "autodoc.publisher.publisher.create_strategy",
            side_effect=lambda *a, **kw: next(strategies),
        )
        mock_publish_profile_page = mocker.patch.object(
            publisher_document_publisher,
            "publish_profile_page",
            return_value=profile_report,
        )

        result = publisher_document_publisher.publish_all(
            parsed_data=publisher_parsed_result,
            passports_root_parent_id=_ROOT_PAGE_ID,
            release_page_title=_RELEASE_PAGE_TITLE,
            release_template_name=_RELEASE_TEMPLATE,
            profile_title="Profile Page",
            profile_template_name="profile_doc.jinja2",
        )

        mock_publish_profile_page.assert_called_once()
        _, call_kwargs = mock_publish_profile_page.call_args
        assert call_kwargs["release_report"] is release_report
        assert call_kwargs["release_report"].details[0]["page_id"] == "release-page-1"
        assert result.pages_published == 4


class TestDocumentPublisherPublishPassports:
    """Тесты для DocumentPublisher.publish_passports()."""

    @pytest.mark.contract
    def test_publisher_publish_passports_resolves_root_and_delegates(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """publish_passports() резолвит корневую страницу и делегирует стратегии паспортов."""
        mocker.patch.object(
            publisher_document_publisher._page_resolver,
            "resolve_passports_root",
            return_value=_ROOT_PAGE_ID,
        )
        expected_report = PublishReport(success=True, pages_published=2)
        mock_create = mocker.patch(
            "autodoc.publisher.publisher.create_strategy",
            return_value=_mock_strategy(expected_report, mocker),
        )

        result = publisher_document_publisher.publish_passports(
            parsed_data=publisher_parsed_result,
            template_name="component_passport.jinja2",
            passports_root_parent_name="Passports Root",
        )

        args, kwargs = mock_create.call_args
        assert args[0] == "passports"
        assert kwargs["root_page_id"] == _ROOT_PAGE_ID
        assert result is expected_report


class TestDocumentPublisherPublishSinglePage:
    """Тесты для DocumentPublisher.publish_single_page()."""

    @pytest.mark.contract
    def test_publisher_publish_single_page_resolves_parent_and_delegates(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """publish_single_page() резолвит родительскую страницу и делегирует выбранной стратегии."""
        mocker.patch.object(
            publisher_document_publisher._page_resolver,
            "resolve_single_page_parent",
            return_value=_ROOT_PAGE_ID,
        )
        expected_report = PublishReport(success=True, pages_published=1)
        mock_create = mocker.patch(
            "autodoc.publisher.publisher.create_strategy",
            return_value=_mock_strategy(expected_report, mocker),
        )

        result = publisher_document_publisher.publish_single_page(
            strategy_type="release",
            parsed_data=publisher_parsed_result,
            page_title=_RELEASE_PAGE_TITLE,
            template_name=_RELEASE_TEMPLATE,
        )

        args, kwargs = mock_create.call_args
        assert args[0] == "release"
        assert kwargs["parent_id"] == _ROOT_PAGE_ID
        assert result is expected_report


class TestDocumentPublisherPublishProfilePage:
    """Тесты для DocumentPublisher.publish_profile_page()."""

    @pytest.mark.business_logic
    def test_publisher_publish_profile_page_uses_release_page_id_as_parent(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """publish_profile_page() использует ID страницы релиза как parent_id."""
        release_report = PublishReport(
            success=True,
            pages_published=1,
            details=[{"page_id": "release-page-1"}],
        )
        expected_report = PublishReport(success=True, pages_published=1)
        mock_create = mocker.patch(
            "autodoc.publisher.publisher.create_strategy",
            return_value=_mock_strategy(expected_report, mocker),
        )

        result = publisher_document_publisher.publish_profile_page(
            parsed_data=publisher_parsed_result,
            profile_title="Profile Page",
            profile_template_name="profile_doc.jinja2",
            release_report=release_report,
        )

        args, kwargs = mock_create.call_args
        assert args[0] == "profile_centric"
        assert kwargs["parent_id"] == "release-page-1"
        assert result is expected_report

    @pytest.mark.business_logic
    def test_publisher_publish_profile_page_warns_and_publishes_without_parent_when_release_failed(
        self,
        publisher_document_publisher: DocumentPublisher,
        publisher_parsed_result: ParsedResult,
        mocker: MockerFixture,
    ) -> None:
        """
        Если релизная страница не была опубликована, profile_parent_id становится None,
        логируется предупреждение, и профильная страница всё равно публикуется без родителя.
        """
        release_report = PublishReport(success=False, pages_published=0, errors=["fail"])
        expected_report = PublishReport(success=True, pages_published=1)
        mock_create = mocker.patch(
            "autodoc.publisher.publisher.create_strategy",
            return_value=_mock_strategy(expected_report, mocker),
        )
        mock_logger_warning = mocker.patch("autodoc.publisher.publisher.logger.warning")

        result = publisher_document_publisher.publish_profile_page(
            parsed_data=publisher_parsed_result,
            profile_title="Profile Page",
            profile_template_name="profile_doc.jinja2",
            release_report=release_report,
        )

        mock_logger_warning.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs["parent_id"] is None
        assert result is expected_report
