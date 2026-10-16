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
from autodoc.publisher.strategies.publish_plan import parent_key_of, plan_keys

_ROOT_PAGE_ID: str = "root-001"
_RELEASE_PAGE_TITLE: str = "Platform 2.0 Release"
_RELEASE_TEMPLATE: str = "release_doc.jinja2"
_KIT_PINNED_TITLE: str = "Kit Pinned Page"
_KIT_LATEST_TITLE: str = "Kit Latest Page"


_PARENT_SECTIONS: dict[str, dict[str, str]] = {
    "passports": {"root_parent_name": "passports parent"},
    "release": {"root_parent_name": "release parent", "page_title": _RELEASE_PAGE_TITLE},
    "kit_pinned": {"root_parent_name": "kit_pinned parent", "page_title": _KIT_PINNED_TITLE},
    "kit_latest": {"root_parent_name": "kit_latest parent", "page_title": _KIT_LATEST_TITLE},
}
"""Секции ``strategies`` с родителями и заголовками для всех типов ``publish all``."""


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
) -> MagicMock:
    """
    Подменяет ``resolve_parent`` в ``RootPageResolver`` паблишера.

    Args:
        mocker: Фикстура pytest-mock для патчинга.
        publisher: Паблишер, чей резолвер подменяется.

    Returns:
        Мок ``resolve_parent``: любой ключ типа резолвится в ``"<тип стратегии>-parent"``.
    """
    return mocker.patch.object(
        publisher._page_resolver,
        "resolve_parent",
        side_effect=lambda strategy_type, name, page_id: f"{strategy_type}-parent",
    )


def _publish_all(publisher: DocumentPublisher, parsed_data: ParsedResult) -> PublishReport:
    """Вызывает ``publish_all()``; заголовки и родители берутся из конфига паблишера."""
    return publisher.publish_all(parsed_data=parsed_data)


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

    ``page_id`` страницы релиза берётся из ``details[0]`` собственного отчёта родителя,
    который никогда не смешивается с отчётами других типов (например, паспортов).
    """
    _patch_resolver(mocker, publisher_all_parents)
    calls = _patch_create_strategy(mocker, _all_reports())

    _publish_all(publisher_all_parents, publisher_parsed_result)

    profile_kwargs = dict(calls)["profile_centric"]
    assert profile_kwargs["parent_id"] == _RELEASE_PAGE_ID


@pytest.mark.contract
def test_publisher_publish_all_uses_parents_and_titles_from_config(
    publisher_all_parents: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
) -> None:
    """
    Родители и заголовки страниц берутся только из конфига и передаются стратегиям.

        Резолвер вызывается с ``None`` вместо названия и ID страницы, то есть источником
        служит секция ``strategies`` конфига. Результат резолва уходит в ``parent_id``
        каждой стратегии; у одностраничных — вместе с ``page_title`` из той же секции.
        У профильной страницы заголовок — значение по умолчанию из схемы.
    """
    resolver_mock = _patch_resolver(mocker, publisher_all_parents)
    calls = _patch_create_strategy(mocker, _all_reports())

    _publish_all(publisher_all_parents, publisher_parsed_result)

    assert [c.args for c in resolver_mock.call_args_list] == [
        ("passports", None, None),
        ("release", None, None),
        ("kit_pinned", None, None),
        ("kit_latest", None, None),
    ]
    by_type = dict(calls)
    assert by_type["passports"]["parent_id"] == "passports-parent"
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
    assert (
        by_type["profile_centric"]["page_title"]
        == publisher_all_parents._config.strategies.profile_centric.page_title
    )
    assert by_type["profile_centric"]["page_title"]


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
    def resolve_parent(strategy_type: str, name: str | None, page_id: str | None) -> str:
        if strategy_type == "kit_latest":
            raise ConfigError("родитель kit_latest не задан")
        return f"{strategy_type}-parent"

    mocker.patch.object(
        publisher_all_parents._page_resolver,
        "resolve_parent",
        side_effect=resolve_parent,
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
    publish_all() публикует только типы из ``publish_all.targets`` и в порядке плана.

    Порядок элементов в конфиге на порядок публикации не влияет. Родители резолвятся
    только для выбранных типов с собственным родителем: резолвер не вызывается для
    невыбранных типов и для типов, чей родитель — страница другого типа.
    """
    config_dict = {
        **minimal_confluence_config,
        "strategies": _PARENT_SECTIONS,
        "publish_all": {"targets": targets},
    }
    publisher = _make_publisher(config_dict, tmp_path, mocker)
    resolver_mock = _patch_resolver(mocker, publisher)
    calls = _patch_create_strategy(mocker, _all_reports())

    _publish_all(publisher, publisher_parsed_result)

    assert [strategy_type for strategy_type, _ in calls] == expected_order
    resolved_types = [c.args[0] for c in resolver_mock.call_args_list]
    assert resolved_types == [
        t for t in plan_keys() if t in targets and parent_key_of(t) is None
    ]


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
    ``create_strategy`` не вызывается. Профильная страница родителя не требует.
    """
    resolver_mock = _patch_resolver(mocker, publisher_document_publisher)
    mock_create = mocker.patch("autodoc.publisher.publisher.create_strategy")

    with pytest.raises(ConfigError) as exc_info:
        _publish_all(publisher_document_publisher, publisher_parsed_result)

    message = str(exc_info.value)
    assert (
        "strategies.passports, strategies.release, strategies.kit_pinned, strategies.kit_latest"
        in message
    )
    assert "strategies.profile_centric" not in message
    mock_create.assert_not_called()
    resolver_mock.assert_not_called()


@pytest.mark.contract
def test_publisher_publish_passports_resolves_root_and_delegates(
    publisher_document_publisher: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
) -> None:
    """publish_passports() резолвит корневую страницу и делегирует стратегии паспортов."""
    mocker.patch.object(
        publisher_document_publisher._page_resolver,
        "resolve_parent",
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
    assert kwargs["parent_id"] == _ROOT_PAGE_ID
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
        "resolve_parent",
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
def test_publisher_publish_all_skips_child_when_parent_not_published(
    publisher_all_parents: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
) -> None:
    """
    Потомок пропускается при непубликации родителя, остальные типы публикуются.

    Отчёт релиза — неудача без ``details``, то есть ID родительской страницы взять негде.
    Профильная страница не должна публиковаться (``create_strategy`` для неё не вызывается),
    но паспорта и обе страницы комплекта публикуются как раньше. В итоговом отчёте профиль
    учтён как неудавшаяся страница, а причина записана в лог ровно один раз.
    """
    _patch_resolver(mocker, publisher_all_parents)
    reports = _all_reports(
        release=PublishReport(success=False, pages_published=0, errors=["fail"])
    )
    calls = _patch_create_strategy(mocker, reports)
    mock_logger_error = mocker.patch("autodoc.publisher.publisher.logger.error")

    result = _publish_all(publisher_all_parents, publisher_parsed_result)

    assert [strategy_type for strategy_type, _ in calls] == [
        "passports",
        "release",
        "kit_pinned",
        "kit_latest",
    ]
    profile_title = publisher_all_parents._config.strategies.profile_centric.page_title
    assert result.success is False
    assert result.pages_failed == 1
    assert [p["page_title"] for p in result.failed_pages] == [profile_title]
    mock_logger_error.assert_called_once()


@pytest.mark.business_logic
def test_publisher_publish_all_child_parent_id_comes_from_parent_report(
    publisher_all_parents: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
) -> None:
    """
    Потомок получает ``parent_id`` из собственного отчёта родителя, а не из паспортов.

    Паспорта возвращают отчёт с ``details`` раньше релиза; при слиянии отчётов первой
    записью оказался бы паспорт. Профильная страница обязана получить ID страницы релиза.
    Это регрессионный тест на прежнюю причину существования порядка «релиз → профиль»
    внутри одного блока.
    """
    _patch_resolver(mocker, publisher_all_parents)
    reports = _all_reports(
        passports=PublishReport(
            success=True, pages_published=1, details=[{"page_id": "passport-page-1"}]
        ),
        release=PublishReport(
            success=True, pages_published=1, details=[{"page_id": "release-page-1"}]
        ),
    )
    calls = _patch_create_strategy(mocker, reports)

    _publish_all(publisher_all_parents, publisher_parsed_result)

    assert dict(calls)["profile_centric"]["parent_id"] == "release-page-1"


@pytest.mark.business_logic
def test_publisher_publish_all_resolves_only_own_parents_before_first_publication(
    publisher_all_parents: DocumentPublisher,
    publisher_parsed_result: ParsedResult,
    mocker: MockerFixture,
) -> None:
    """
    Фаза 1 резолвит только типы с собственным родителем, в порядке плана, до публикаций.

    Выбраны все типы. Все вызовы резолвера и ``create_strategy`` пишутся в один общий
    журнал: резолв идёт для passports, release, kit_pinned, kit_latest (но не для
    profile_centric, чей родитель — страница релиза) и целиком предшествует первой
    публикации, поэтому ошибка резолва не оставляет частично опубликованного состояния.
    """
    journal: list[tuple[str, str]] = []

    def fake_resolve(strategy_type: str, name: str | None, page_id: str | None) -> str:
        journal.append(("resolve", strategy_type))
        return f"{strategy_type}-parent"

    mocker.patch.object(
        publisher_all_parents._page_resolver, "resolve_parent", side_effect=fake_resolve
    )
    reports = _all_reports()

    def fake_create(strategy_type: str, **kwargs: Any) -> MagicMock:
        journal.append(("create", strategy_type))
        return _mock_strategy(reports[strategy_type], mocker)

    mocker.patch("autodoc.publisher.publisher.create_strategy", side_effect=fake_create)

    _publish_all(publisher_all_parents, publisher_parsed_result)

    assert journal[:4] == [
        ("resolve", "passports"),
        ("resolve", "release"),
        ("resolve", "kit_pinned"),
        ("resolve", "kit_latest"),
    ]
    assert all(action == "create" for action, _ in journal[4:])
    assert len(journal) == 4 + len(_ALL_STRATEGY_TYPES)
