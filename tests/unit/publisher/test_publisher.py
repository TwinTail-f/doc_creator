"""
Тесты для autodoc.publisher.publisher.DocumentPublisher.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfigError
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.publisher import DocumentPublisher
from autodoc.publisher.strategies.models.publish_report import PublishReport

_ROOT_PAGE_ID: str = "root-001"
_RELEASE_PAGE_TITLE: str = "Platform 2.0 Release"
_RELEASE_TEMPLATE: str = "release_doc.jinja2"
_PROFILE_TITLE: str = "Profile Page"
_PROFILE_TEMPLATE: str = "profile_doc.jinja2"
_KIT_PINNED_TITLE: str = "Kit Pinned Page"
_KIT_LATEST_TITLE: str = "Kit Latest Page"


_PARENT_SECTIONS: dict[str, dict[str, str]] = {
    section: {"root_parent_name": f"{section} parent"}
    for section in ("passports", "release", "kit_pinned", "kit_latest")
}
"""Секции ``strategies`` с родителями для всех типов, у которых ``publish all`` берёт родителя из конфига."""


def _make_publisher(
    config_dict: dict[str, Any],
    tmp_path: Path,
    mocker: MockerFixture,
) -> DocumentPublisher:
    """``DocumentPublisher`` с замоканными инфраструктурными зависимостями."""
    mocker.patch("autodoc.publisher.publisher.ConfluenceClient")
    mocker.patch("autodoc.publisher.publisher.DocumentBuilder")
    rendering_dir = tmp_path / "rendering"
    rendering_dir.mkdir(exist_ok=True)
    return DocumentPublisher(
        confluence_config=ConfluenceConfigSchema(**config_dict),
        rendering_dir=rendering_dir,
        data_dir=tmp_path,
    )


@pytest.fixture
def publisher_document_publisher(
    minimal_confluence_config: dict,
    tmp_path: Path,
    mocker: MockerFixture,
) -> DocumentPublisher:
    """DocumentPublisher с замоканными инфраструктурными зависимостями."""
    return _make_publisher(minimal_confluence_config, tmp_path, mocker)


@pytest.fixture
def publisher_all_parents(
    minimal_confluence_config: dict,
    tmp_path: Path,
    mocker: MockerFixture,
) -> DocumentPublisher:
    """DocumentPublisher, в конфиге которого заданы родители для всех типов ``publish all``."""
    config_dict = {**minimal_confluence_config, "strategies": _PARENT_SECTIONS}
    return _make_publisher(config_dict, tmp_path, mocker)


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


_ALL_STRATEGY_TYPES: tuple[str, ...] = (
    "passports",
    "release",
    "profile_centric",
    "kit_pinned",
    "kit_latest",
)
_RELEASE_PAGE_ID: str = "release-page-1"


def _all_reports(**overrides: PublishReport) -> dict[str, PublishReport]:
    """
    Собирает успешные отчёты для всех стратегий ``publish_all()``.

    Args:
        **overrides: Отчёты, заменяющие отчёты по умолчанию (ключ — тип стратегии).

    Returns:
        Словарь «тип стратегии → отчёт»; отчёт релиза содержит ``page_id`` страницы релиза.
    """
    reports = {
        strategy_type: PublishReport(success=True, pages_published=1)
        for strategy_type in _ALL_STRATEGY_TYPES
    }
    reports["release"] = PublishReport(
        success=True,
        pages_published=1,
        details=[{"page_id": _RELEASE_PAGE_ID}],
    )
    reports.update(overrides)
    return reports


def _patch_create_strategy(
    mocker: MockerFixture,
    reports: dict[str, PublishReport],
) -> list[tuple[str, dict[str, Any]]]:
    """
    Подменяет ``create_strategy``: каждая стратегия возвращает отчёт, заданный для её типа.

    Args:
        mocker: Фикстура pytest-mock для патчинга.
        reports: Отчёты по типам стратегий.

    Returns:
        Список вызовов ``create_strategy`` в порядке их выполнения: пары
        ``(тип стратегии, переданные аргументы)``.
    """
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_create(strategy_type: str, **kwargs: Any) -> MagicMock:
        calls.append((strategy_type, kwargs))
        return _mock_strategy(reports[strategy_type], mocker)

    mocker.patch("autodoc.publisher.publisher.create_strategy", side_effect=fake_create)
    return calls


def _patch_resolver(
    mocker: MockerFixture,
    publisher: DocumentPublisher,
) -> tuple[MagicMock, MagicMock]:
    """
    Подменяет методы резолва родительских страниц в ``RootPageResolver`` паблишера.

    Args:
        mocker: Фикстура pytest-mock для патчинга.
        publisher: Паблишер, чей резолвер подменяется.

    Returns:
        Пара моков: ``resolve_passports_root`` и ``resolve_single_page_parent``.
        Корень паспортов резолвится в ``"passports-root"``, родитель одностраничной
        стратегии — в ``"<тип стратегии>-parent"``.
    """
    passports_mock = mocker.patch.object(
        publisher._page_resolver,
        "resolve_passports_root",
        return_value="passports-root",
    )
    single_page_mock = mocker.patch.object(
        publisher._page_resolver,
        "resolve_single_page_parent",
        side_effect=lambda strategy_type, name, page_id: f"{strategy_type}-parent",
    )
    return passports_mock, single_page_mock


def _publish_all(publisher: DocumentPublisher, parsed_data: ParsedResult) -> PublishReport:
    """Вызывает ``publish_all()`` с заголовками, достаточными для всех страниц."""
    return publisher.publish_all(
        parsed_data=parsed_data,
        release_page_title=_RELEASE_PAGE_TITLE,
        profile_page_title=_PROFILE_TITLE,
        kit_pinned_page_title=_KIT_PINNED_TITLE,
        kit_latest_page_title=_KIT_LATEST_TITLE,
    )


@pytest.mark.business_logic
def test_publisher_publish_all_runs_strategies_in_documented_order(
    publisher_all_parents: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
) -> None:
    """
    publish_all() выполняет стратегии в порядке: паспорта, релиз, профили, kit-pinned, kit-latest.

    Порядок «паспорта → релиз» важен: ReleasePageStrategy при рендеринге читает
    passport_pages.json, записанный предшествующим запуском PassportsStrategy, чтобы вставить
    ссылки на паспорта компонентов (см. докстринг ReleasePageStrategy и
    ComponentCentricConverter.enrich_with_passport_links). Профильная страница публикуется
    дочерней к странице релиза, поэтому обязана идти после неё.
    """
    _patch_resolver(mocker, publisher_all_parents)
    calls = _patch_create_strategy(mocker, _all_reports())

    _publish_all(publisher_all_parents, publisher_parsed_result)

    assert [strategy_type for strategy_type, _ in calls] == list(_ALL_STRATEGY_TYPES)


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "overrides, expected",
    [
        # все стратегии успешны — pages_published суммируется
        pytest.param(
            {"passports": PublishReport(success=True, pages_published=3)},
            {"success": True, "pages_published": 7, "errors": []},
            id="all-success-sums-pages",
        ),
        # провал страницы комплекта делает итоговый success False
        pytest.param(
            {"kit_latest": PublishReport(success=False, pages_published=0, errors=["fail"])},
            {"success": False, "pages_published": 4, "errors": ["fail"]},
            id="kit-failure-propagates",
        ),
        # ошибки разных стратегий объединяются в один список в порядке публикации
        pytest.param(
            {
                "passports": PublishReport(success=False, pages_published=0, errors=["err1"]),
                "kit_pinned": PublishReport(success=False, pages_published=0, errors=["err2"]),
            },
            {"success": False, "pages_published": 3, "errors": ["err1", "err2"]},
            id="errors-merged",
        ),
    ],
)
def test_publisher_publish_all_aggregates_reports_of_all_strategies(
    publisher_all_parents: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
    overrides: dict[str, PublishReport],
    expected: dict[str, Any],
) -> None:
    """
    Итоговый отчёт publish_all() агрегирует success, pages_published и errors всех пяти стратегий.

    Каждая стратегия по умолчанию публикует по одной странице; ``overrides`` заменяют
    отчёты отдельных стратегий.
    """
    _patch_resolver(mocker, publisher_all_parents)
    _patch_create_strategy(mocker, _all_reports(**overrides))

    result = _publish_all(publisher_all_parents, publisher_parsed_result)

    assert result.success == expected["success"]
    assert result.pages_published == expected["pages_published"]
    assert result.errors == expected["errors"]


@pytest.mark.business_logic
def test_publisher_publish_all_publishes_profile_page_under_release_page(
    publisher_all_parents: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
) -> None:
    """
    Профильная страница публикуется дочерней к странице релиза, а не к корню из конфига.

    ``page_id`` страницы релиза берётся из ``details[0]`` её отчёта; этот отчёт ещё не
    должен быть смешан с отчётом паспортов (иначе в ``details[0]`` окажется паспорт).
    """
    _patch_resolver(mocker, publisher_all_parents)
    calls = _patch_create_strategy(mocker, _all_reports())

    _publish_all(publisher_all_parents, publisher_parsed_result)

    profile_kwargs = dict(calls)["profile_centric"]
    assert profile_kwargs["parent_id"] == _RELEASE_PAGE_ID


@pytest.mark.contract
def test_publisher_publish_all_uses_config_parents_and_given_titles(
    publisher_all_parents: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
) -> None:
    """
    Родители страниц резолвятся только по конфигу (без CLI-значений) и передаются стратегиям.

    Резолвер вызывается с ``None`` вместо названия и ID страницы, то есть источником
    служит секция ``strategies`` конфига. Результат резолва уходит в ``root_page_id``
    паспортов и ``parent_id`` каждой одностраничной стратегии вместе с заданным заголовком.
    """
    passports_mock, single_page_mock = _patch_resolver(mocker, publisher_all_parents)
    calls = _patch_create_strategy(mocker, _all_reports())

    _publish_all(publisher_all_parents, publisher_parsed_result)

    passports_mock.assert_called_once_with(None, None)
    assert [c.args for c in single_page_mock.call_args_list] == [
        ("release", None, None),
        ("kit_pinned", None, None),
        ("kit_latest", None, None),
    ]
    by_type = dict(calls)
    assert by_type["passports"]["root_page_id"] == "passports-root"
    assert (by_type["release"]["parent_id"], by_type["release"]["page_title"]) == (
        "release-parent",
        _RELEASE_PAGE_TITLE,
    )
    assert (by_type["kit_pinned"]["parent_id"], by_type["kit_pinned"]["page_title"]) == (
        "kit_pinned-parent",
        _KIT_PINNED_TITLE,
    )
    assert (by_type["kit_latest"]["parent_id"], by_type["kit_latest"]["page_title"]) == (
        "kit_latest-parent",
        _KIT_LATEST_TITLE,
    )
    assert by_type["profile_centric"]["page_title"] == _PROFILE_TITLE


@pytest.mark.business_logic
def test_publisher_publish_all_config_error_stops_before_any_publication(
    publisher_all_parents: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
) -> None:
    """
    Ошибка резолва родителя последней страницы (kit-latest) не оставляет часть страниц опубликованной.

    Резолвер подменён так, что родитель ``kit_latest`` не находится и бросает ``ConfigError``.
    Родители резолвятся до первой публикации, поэтому ``create_strategy`` не должен быть
    вызван ни разу: иначе паспорта и релиз уже были бы опубликованы к моменту ошибки.
    """
    _patch_resolver(mocker, publisher_all_parents)

    def resolve_single_page_parent(
        strategy_type: str, name: str | None, page_id: str | None
    ) -> str:
        if strategy_type == "kit_latest":
            raise ConfigError("родитель kit_latest не задан")
        return f"{strategy_type}-parent"

    mocker.patch.object(
        publisher_all_parents._page_resolver,
        "resolve_single_page_parent",
        side_effect=resolve_single_page_parent,
    )
    mock_create = mocker.patch("autodoc.publisher.publisher.create_strategy")

    with pytest.raises(ConfigError, match="kit_latest"):
        _publish_all(publisher_all_parents, publisher_parsed_result)

    mock_create.assert_not_called()


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "targets, expected_order",
    [
        pytest.param(["kit_pinned"], ["kit_pinned"], id="single-kit"),
        pytest.param(
            ["kit_latest", "passports"],
            ["passports", "kit_latest"],
            id="order-in-config-does-not-matter",
        ),
        pytest.param(
            ["release", "profile_centric"],
            ["release", "profile_centric"],
            id="release-with-profile",
        ),
    ],
)
def test_publisher_publish_all_runs_only_selected_targets(
    minimal_confluence_config: dict,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: MockerFixture,
    targets: list[str],
    expected_order: list[str],
) -> None:
    """
    publish_all() публикует только типы из ``publish_all.targets`` и в фиксированном порядке.

    Порядок элементов в конфиге на порядок публикации не влияет. Родители резолвятся
    только для выбранных одностраничных типов: резолвер не вызывается для остальных.
    """
    config_dict = {
        **minimal_confluence_config,
        "strategies": _PARENT_SECTIONS,
        "publish_all": {"targets": targets},
    }
    publisher = _make_publisher(config_dict, tmp_path, mocker)
    passports_mock, single_page_mock = _patch_resolver(mocker, publisher)
    calls = _patch_create_strategy(mocker, _all_reports())

    _publish_all(publisher, publisher_parsed_result)

    assert [strategy_type for strategy_type, _ in calls] == expected_order
    assert passports_mock.called == ("passports" in targets)
    resolved_types = [c.args[0] for c in single_page_mock.call_args_list]
    assert resolved_types == [t for t in ("release", "kit_pinned", "kit_latest") if t in targets]


@pytest.mark.business_logic
def test_publisher_publish_all_missing_parents_raise_one_error_before_publication(
    publisher_document_publisher: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
) -> None:
    """
    Недостающие родители выбранных типов дают одну ``ConfigError`` до начала публикации.

    В конфиге нет секций с родителями, а выбраны все типы по умолчанию. Ошибка перечисляет
    сразу все недостающие секции (а не только первую), резолвер в Confluence не обращается,
    ``create_strategy`` не вызывается.
    """
    passports_mock, single_page_mock = _patch_resolver(mocker, publisher_document_publisher)
    mock_create = mocker.patch("autodoc.publisher.publisher.create_strategy")

    with pytest.raises(
        ConfigError,
        match="strategies.passports, strategies.release, strategies.kit_pinned, strategies.kit_latest",
    ):
        _publish_all(publisher_document_publisher, publisher_parsed_result)

    mock_create.assert_not_called()
    passports_mock.assert_not_called()
    single_page_mock.assert_not_called()


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
