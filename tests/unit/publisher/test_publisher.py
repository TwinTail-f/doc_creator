"""
Тесты для autodoc.publisher.publisher.DocumentPublisher.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.publisher import DocumentPublisher
from autodoc.publisher.strategies.models.publish_report import PublishReport

_ROOT_PAGE_ID: str = "root-001"
_RELEASE_PAGE_TITLE: str = "Platform 2.0 Release"
_RELEASE_TEMPLATE: str = "release_doc.jinja2"
_PROFILE_TITLE: str = "Profile Page"
_PROFILE_TEMPLATE: str = "profile_doc.jinja2"


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


@pytest.mark.business_logic
def test_publisher_publish_delegates_to_strategy_and_returns_its_report(
    publisher_document_publisher: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
) -> None:
    """publish() вызывает strategy.execute() ровно один раз и возвращает именно тот PublishReport, что она вернула."""
    expected_report = PublishReport(success=True, pages_published=5)
    mock_strategy = _mock_strategy(expected_report, mocker)
    mocker.patch(
        "autodoc.publisher.publisher.create_strategy",
        return_value=mock_strategy,
    )
    result = publisher_document_publisher.publish("release", publisher_parsed_result)
    mock_strategy.execute.assert_called_once()
    assert result is expected_report


@pytest.mark.contract
def test_publisher_publish_passes_space_and_data_dir_from_config(
    publisher_document_publisher: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """publish() передаёт space из конфигурации и data_dir в create_strategy()."""
    mock_create = mocker.patch(
        "autodoc.publisher.publisher.create_strategy",
        return_value=_mock_strategy(PublishReport(success=True, pages_published=1), mocker),
    )
    publisher_document_publisher.publish("release", publisher_parsed_result)
    _, kwargs = mock_create.call_args
    assert kwargs["space"] == "TEST"
    assert kwargs["data_dir"] == tmp_path


def _patch_publish_all_strategies(
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
    publisher_document_publisher: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
) -> None:
    """
    publish_all() выполняет стратегию паспортов раньше стратегии релиза.

    Порядок важен не сам по себе: ReleasePageStrategy при рендеринге читает
    passport_pages.json, записанный предшествующим запуском PassportsStrategy,
    чтобы вставить ссылки на паспорта компонентов (см. докстринг
    ReleasePageStrategy и link_injector/inject_links). Без порядка
    "паспорта → релиз" релизная страница будет опубликована без ссылок на
    паспорта или со ссылками на несуществующие/устаревшие страницы.
    """
    mocker.patch.object(
        publisher_document_publisher._page_resolver,
        "resolve_root_pages",
        return_value=(_ROOT_PAGE_ID, _ROOT_PAGE_ID),
    )
    call_order = _patch_publish_all_strategies(
        mocker,
        PublishReport(success=True, pages_published=1),
        PublishReport(success=True, pages_published=1),
    )

    publisher_document_publisher.publish_all(
        parsed_data=publisher_parsed_result,
        passports_root_parent_id=_ROOT_PAGE_ID,
        release_page_title=_RELEASE_PAGE_TITLE,
        release_template_name=_RELEASE_TEMPLATE,
        release_root_page_id=_ROOT_PAGE_ID,
    )
    assert call_order == ["passports", "release"]


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "passports_report, release_report, expected",
    [
        # обе стратегии успешны — pages_published суммируется
        pytest.param(
            PublishReport(success=True, pages_published=3),
            PublishReport(success=True, pages_published=1),
            {"success": True, "pages_published": 4, "errors": []},
            id="both-success-sums-pages",
        ),
        # хотя бы одна стратегия провалилась — итоговый success тоже False
        pytest.param(
            PublishReport(success=False, pages_published=0, errors=["fail"]),
            PublishReport(success=True, pages_published=1),
            {"success": False, "pages_published": 1, "errors": ["fail"]},
            id="any-failure-propagates",
        ),
        # ошибки обеих стратегий объединяются в один список
        pytest.param(
            PublishReport(success=False, pages_published=0, errors=["err1"]),
            PublishReport(success=False, pages_published=0, errors=["err2"]),
            {"success": False, "pages_published": 0, "errors": ["err1", "err2"]},
            id="errors-merged",
        ),
    ],
)
def test_publisher_publish_all_aggregates_reports_via_publish_report_merge(
    publisher_document_publisher: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
    passports_report: PublishReport,
    release_report: PublishReport,
    expected: dict[str, Any],
) -> None:
    """Итоговый отчёт publish_all() агрегирует success/pages_published/errors обеих стратегий."""
    mocker.patch.object(
        publisher_document_publisher._page_resolver,
        "resolve_root_pages",
        return_value=(_ROOT_PAGE_ID, _ROOT_PAGE_ID),
    )
    _patch_publish_all_strategies(mocker, passports_report, release_report)

    result = publisher_document_publisher.publish_all(
        parsed_data=publisher_parsed_result,
        passports_root_parent_id=_ROOT_PAGE_ID,
        release_page_title=_RELEASE_PAGE_TITLE,
        release_template_name=_RELEASE_TEMPLATE,
        release_root_page_id=_ROOT_PAGE_ID,
    )
    assert result.success == expected["success"]
    assert result.pages_published == expected["pages_published"]
    assert result.errors == expected["errors"]


@pytest.mark.business_logic
def test_publisher_publish_all_with_profile_merges_three_reports(
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

    mocker.patch.object(
        publisher_document_publisher._page_resolver,
        "resolve_root_pages",
        return_value=(_ROOT_PAGE_ID, _ROOT_PAGE_ID),
    )
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
        release_root_page_id=_ROOT_PAGE_ID,
        profile_title=_PROFILE_TITLE,
        profile_template_name=_PROFILE_TEMPLATE,
    )

    mock_publish_profile_page.assert_called_once()
    _, call_kwargs = mock_publish_profile_page.call_args
    assert call_kwargs["release_report"] is release_report
    assert call_kwargs["release_report"].details[0]["page_id"] == "release-page-1"
    assert result.pages_published == 4


@pytest.mark.contract
def test_publisher_publish_passports_resolves_root_and_delegates(
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


@pytest.mark.contract
def test_publisher_publish_single_page_resolves_parent_and_delegates(
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


@pytest.mark.business_logic
def test_publisher_publish_profile_page_uses_release_page_id_as_parent(
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
        profile_title=_PROFILE_TITLE,
        profile_template_name=_PROFILE_TEMPLATE,
        release_report=release_report,
    )

    args, kwargs = mock_create.call_args
    assert args[0] == "profile_centric"
    assert kwargs["parent_id"] == "release-page-1"
    assert result is expected_report


@pytest.mark.business_logic
def test_publisher_publish_profile_page_fails_without_publishing_when_release_failed(
    publisher_document_publisher: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
) -> None:
    """
    Если релизная страница не была опубликована (в отчёте нет details), профильная
    страница не публикуется вовсе: create_strategy не вызывается, ошибка логируется,
    а результат — отчёт о неудаче с указанием причины.
    """
    release_report = PublishReport(success=False, pages_published=0, errors=["fail"])
    mock_create = mocker.patch("autodoc.publisher.publisher.create_strategy")
    mock_logger_error = mocker.patch("autodoc.publisher.publisher.logger.error")

    result = publisher_document_publisher.publish_profile_page(
        parsed_data=publisher_parsed_result,
        profile_title=_PROFILE_TITLE,
        profile_template_name=_PROFILE_TEMPLATE,
        release_report=release_report,
    )

    mock_logger_error.assert_called_once()
    mock_create.assert_not_called()
    assert result.success is False
    assert result.pages_published == 0
    assert result.pages_failed == 1
    assert result.failed_pages == [
        {
            "page_title": _PROFILE_TITLE,
            "reason": (
                f"Профильная страница {_PROFILE_TITLE!r} не опубликована: "
                "страница релиза не была опубликована, родитель недоступен"
            ),
        }
    ]
