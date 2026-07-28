"""
Тесты для autodoc.publisher.strategies.passports_strategy.PassportsStrategy.

Стратегия тестирования:
- PageHierarchyManager.ensure_hierarchy_exists мокается, возвращает стабильный ID страницы.
- PassportConverter.convert мокается, возвращает предсказуемый view_model.
- FakeConfluenceClient / FakeDocumentBuilder используются для ввода-вывода.
- execute() — единственная публичная точка входа, покрываемая тестами
  (без _try_publish_item/_publish_one напрямую).
"""

from pathlib import Path
from typing import Any, Callable

import pytest

from autodoc.exceptions import ConfluenceError
from autodoc.models.component import Component
from autodoc.models.parsed_result import ParsedResult, ProfileDefinition
from autodoc.publisher.converters.passport_converter import PassportConverter
from autodoc.publisher.page_manager.hierarchy_manager import PageHierarchyManager
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.strategies.passports_strategy import PassportsStrategy
from tests.unit.publisher.conftest import FakeConfluenceClient
from tests.unit.publisher.strategies.conftest import (
    FakeDocumentBuilder,
    RecordingConfluenceClient,
)

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


@pytest.fixture
def make_passports_strategy() -> Callable[..., PassportsStrategy]:
    """Фабрика PassportsStrategy с нулевой задержкой между пакетами для быстрых тестов."""

    def _factory(
        client: FakeConfluenceClient,
        builder: FakeDocumentBuilder,
        data: ParsedResult,
        tmp_path: Path,
    ) -> PassportsStrategy:
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

    return _factory


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "space, root_page_id, expected_match",
    [
        # пустой space — ValueError с упоминанием space
        pytest.param("", _ROOT_PAGE_ID, "space", id="empty-space"),
        # пустой root_page_id — ValueError с упоминанием root_page_id
        pytest.param(_SPACE, "", "root_page_id", id="empty-root-page-id"),
    ],
)
def test_passports_strategy_init_raises_on_empty_required_field(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    space: str,
    root_page_id: str,
    expected_match: str,
) -> None:
    """Пустая строка space или root_page_id вызывает ValueError с указанием на пустое поле."""
    with pytest.raises(ValueError, match=expected_match):
        PassportsStrategy(
            confluence_client=publisher_confluence_client,
            document_builder=publisher_document_builder,
            parsed_data=publisher_parsed_result,
            space=space,
            root_page_id=root_page_id,
            data_dir=tmp_path,
        )


# PassportsStrategy.execute()
@pytest.mark.business_logic
def test_passports_strategy_execute_records_failed_component_without_releases(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_profile_definition: ProfileDefinition,
    tmp_path: Path,
    make_passports_strategy: Callable[..., PassportsStrategy],
) -> None:
    """Компоненты без релизов фиксируются как ошибки в отчёте."""
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
def test_passports_strategy_execute_saves_registry_after_publish(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
    make_passports_strategy: Callable[..., PassportsStrategy],
) -> None:
    """После execute() файл passport_pages.json существует в data_dir.

    Более строгая проверка семантики save() (вызван ровно один раз, после
    публикации всех страниц) — в test_registry_saved_after_all_pages_published
    (BL-PS-02). Этот тест не является его дубликатом: он собирает стратегию
    через хелпер make_passports_strategy, тогда как BL-PS-02 — через прямой
    конструктор PassportsStrategy(...), поэтому оба сохранены.
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_VERSION_PAGE_ID,
    )
    mocker.patch.object(
        PassportConverter,
        "convert",
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


@pytest.mark.contract
def test_passports_strategy_execute_report_contains_details(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
    make_passports_strategy: Callable[..., PassportsStrategy],
) -> None:
    """Успешная публикация создаёт минимум одну запись details с page_title и page_id."""
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_VERSION_PAGE_ID,
    )
    mocker.patch.object(
        PassportConverter,
        "convert",
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


@pytest.mark.business_logic
def test_publish_one_continues_when_get_page_body_raises(
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
    make_passports_strategy: Callable[..., PassportsStrategy],
) -> None:
    """Если получение тела существующей страницы падает с ConfluenceError,
    публикация паспорта всё равно продолжается и завершается успешно
    (устойчивость _fetch_existing_body: страница публикуется без legacy-контента)."""
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_VERSION_PAGE_ID,
    )
    mocker.patch.object(
        PassportConverter,
        "convert",
        return_value=dict(_STUB_TRANSFORM_RESULT),
    )

    class FailingBodyClient(FakeConfluenceClient):
        def get_page_body(self, space, title, parent_id=None):
            raise ConfluenceError("не удалось получить тело страницы")

    strategy = make_passports_strategy(
        FailingBodyClient(),
        publisher_document_builder,
        publisher_parsed_result,
        tmp_path,
    )
    report = strategy.execute()

    assert report.pages_failed == 0, "сбой get_page_body не должен приводить к неудаче публикации"
    assert report.pages_published >= 1


# _make_page_title / _build_pages_map (статические хелперы)
@pytest.mark.business_logic
@pytest.mark.parametrize(
    "name, version, expected",
    [
        pytest.param("openssl", "1.0.0", "Документация openssl 1.0.0", id="openssl"),
        pytest.param("sqlite3", "3.51.2", "Документация sqlite3 3.51.2", id="sqlite3"),
        pytest.param("patchelf", "0.18.0", "Документация patchelf 0.18.0", id="patchelf"),
    ],
)
def test_page_title_exact_format(name: str, version: str, expected: str) -> None:
    """_make_page_title возвращает 'Документация <name> <version>' — точный формат."""
    assert PassportsStrategy._make_page_title(name, version) == expected


@pytest.mark.contract
def test_passports_strategy_build_pages_map_structure() -> None:
    """_build_pages_map строит вложенную структуру {comp: {version: {...}}}."""
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


@pytest.mark.business_logic
def test_one_page_per_component_release_combination(
    publisher_multi_component_result: ParsedResult,
    publisher_document_builder: FakeDocumentBuilder,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PS-01, BL-PS-04
    Бизнес-правило: ровно 1 страница паспорта публикуется для каждой пары
    (компонент × релиз), и при отсутствии ошибок report.pages_published
    равен точному числу таких пар, а report.pages_failed равен 0.

    Предусловия:
        - ParsedResult содержит несколько компонентов с разным числом релизов.
        - PageHierarchyManager.ensure_hierarchy_exists застаблен.
        - PassportConverter.convert возвращает корректный заглушечный view_model.

    Шаги:
        1. Создать PassportsStrategy с фикстурой из нескольких компонентов.
        2. Вызвать execute().

    Ожидаемый результат:
        report.pages_published == общему числу пар (компонент, релиз).
        report.pages_failed == 0.
        Не публикуются лишние или пропущенные страницы паспортов.
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_VERSION_PAGE_ID,
    )
    mocker.patch.object(
        PassportConverter,
        "convert",
        return_value=dict(_STUB_TRANSFORM_RESULT),
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
        f"Ожидалось {total_releases} опубликованных страниц паспортов, "
        f"получено {report.pages_published}"
    )
    assert report.pages_failed == 0, "Все страницы должны быть опубликованы успешно, без ошибок"


@pytest.mark.business_logic
def test_registry_saved_after_all_pages_published(
    publisher_multi_component_result: ParsedResult,
    publisher_document_builder: FakeDocumentBuilder,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PS-02
    Бизнес-правило: PassportPageRegistry.save() вызывается ровно ОДИН раз,
    ПОСЛЕ публикации всех страниц — не после каждой отдельной страницы.

    Предусловия:
        - PageHierarchyManager и PassportConverter застаблены.
        - PassportPageRegistry.save() перехватывается для фиксации вызова.

    Шаги:
        1. Патчим PassportPageRegistry.save, чтобы фиксировать вызовы.
        2. Вызвать execute().

    Ожидаемый результат:
        save() вызывается ровно 1 раз, и к моменту его вызова уже произошёл
        как минимум один вызов publish_page (страницы были опубликованы раньше).
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_VERSION_PAGE_ID,
    )
    mocker.patch.object(
        PassportConverter,
        "convert",
        return_value=dict(_STUB_TRANSFORM_RESULT),
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
        f"PassportPageRegistry.save() должен вызываться ровно один раз, "
        f"вызван {len(save_calls)} раз(а)"
    )
    assert (
        save_calls[0]["published_count"] > 0
    ), "К моменту вызова save() publish_page должен был быть вызван хотя бы один раз"


@pytest.mark.business_logic
def test_failure_of_one_page_does_not_stop_others(
    publisher_multi_component_result: ParsedResult,
    publisher_document_builder: FakeDocumentBuilder,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PS-03
    Бизнес-правило: ошибка публикации одной страницы паспорта не останавливает
    оставшуюся очередь.

    Предусловия:
        - PageHierarchyManager застаблен.
        - PassportConverter.convert выбрасывает исключение при первом вызове
          и завершается успешно в остальных.

    Шаги:
        1. Сделать так, чтобы PassportConverter.convert выбрасывал ValueError
           при первом вызове.
        2. Вызвать execute().

    Ожидаемый результат:
        report.pages_failed >= 1 (зафиксирована как минимум одна ошибка) И
        report.pages_published >= 1 (остальные страницы всё же опубликованы успешно).
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_VERSION_PAGE_ID,
    )

    call_count: list[int] = [0]

    def convert_side_effect(*args: Any, **kwargs: Any) -> dict:
        call_count[0] += 1
        if call_count[0] == 1:
            raise ValueError("Simulated failure on first passport page")
        return dict(_STUB_TRANSFORM_RESULT)

    mocker.patch.object(PassportConverter, "convert", side_effect=convert_side_effect)

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

    assert report.pages_failed >= 1, "Должна быть зафиксирована как минимум одна ошибка"
    assert (
        report.pages_published >= 1
    ), "Остальные страницы всё равно должны быть опубликованы, несмотря на частичный сбой"


@pytest.mark.business_logic
def test_one_passport_publish_failure_isolated_from_others(
    publisher_multi_component_result: ParsedResult,
    publisher_document_builder: FakeDocumentBuilder,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    Бизнес-правило: если ConfluenceError выбрасывается на этапе самой публикации
    страницы (а не при трансформации конвертером), это не мешает опубликовать
    остальные паспорта — _try_publish_item изолирует ошибку публикации так же,
    как и ошибку конвертера.
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_VERSION_PAGE_ID,
    )
    mocker.patch.object(
        PassportConverter,
        "convert",
        return_value=dict(_STUB_TRANSFORM_RESULT),
    )

    call_count: list[int] = [0]
    real_publish_page = FakeConfluenceClient.publish_page

    class FlakyClient(FakeConfluenceClient):
        def publish_page(self, space, parent_id, title, body_html):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConfluenceError("сбой публикации первой страницы")
            return real_publish_page(self, space, parent_id, title, body_html)

    strategy = PassportsStrategy(
        confluence_client=FlakyClient(),
        document_builder=publisher_document_builder,
        parsed_data=publisher_multi_component_result,
        space=_SPACE,
        root_page_id=_ROOT_PAGE_ID,
        data_dir=tmp_path,
        batch_size=10,
        batch_delay_seconds=0.0,
    )
    report = strategy.execute()

    assert (
        report.pages_failed >= 1
    ), "ошибка publish_page для одной страницы должна быть зафиксирована"
    assert (
        report.pages_published >= 1
    ), "остальные паспорта должны быть опубликованы, несмотря на сбой одной страницы"


@pytest.mark.business_logic
def test_report_pages_failed_count_equals_failed_pages(
    publisher_parsed_result: ParsedResult,
    publisher_document_builder: FakeDocumentBuilder,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PS-05
    Бизнес-правило: PublishReport.pages_failed равен len(report.failed_pages).
    Счётчик и список должны быть согласованы.

    Предусловия:
        - PageHierarchyManager застаблен.
        - PassportConverter.convert всегда выбрасывает ValueError.

    Шаги:
        1. Вызвать execute() с всегда падающим конвертером.

    Ожидаемый результат:
        report.pages_failed == len(report.failed_pages) > 0.
        report.pages_published == 0.
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_VERSION_PAGE_ID,
    )
    mocker.patch.object(
        PassportConverter,
        "convert",
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
    ), "pages_failed должен совпадать с len(failed_pages) — счётчик и список должны быть согласованы"
    assert report.pages_failed > 0, "При постоянных ошибках конвертера pages_failed должен быть > 0"
    assert report.pages_published == 0, "При постоянных ошибках pages_published должен быть равен 0"


@pytest.mark.business_logic
def test_legacy_content_extracted_before_overwrite(
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
    mocker: Any,
    publisher_capturing_document_builder: Any,
) -> None:
    """
    BL-PS-06
    Бизнес-правило: перед публикацией страницы паспорта стратегия получает тело
    существующей страницы, извлекает legacy-секции для других платформ и
    внедряет их в view_model как 'legacy_contents' перед вызовом builder.build().

    Предусловия:
        - PageHierarchyManager застаблен.
        - PassportConverter.convert возвращает минимальный корректный view_model.
        - CapturingBuilder фиксирует каждый view_model, переданный в build().
        - FakeConfluenceClient возвращает непустое тело из get_page_body().

    Шаги:
        1. Застабить PageHierarchyManager.ensure_hierarchy_exists.
        2. Застабить PassportConverter.convert, чтобы вернуть view_model
           с platform_version.
        3. Перехватить builder.build(), чтобы зафиксировать итоговый view_model.
        4. Предварительно настроить client.get_page_body на возврат существующего
           legacy HTML-тела.
        5. Вызвать execute().

    Ожидаемый результат:
        как минимум один view_model, переданный в builder.build(), содержит ключ
        'legacy_contents' со значением-словарём, подтверждая, что извлечение
        и внедрение legacy-контента произошло.
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value=_VERSION_PAGE_ID,
    )
    # PassportConverter.convert(self, data) — 'self' здесь это экземпляр конвертера
    mocker.patch.object(
        PassportConverter,
        "convert",
        return_value={k: v for k, v in _STUB_TRANSFORM_RESULT.items() if k != "legacy_contents"},
    )

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
        document_builder=publisher_capturing_document_builder,
        parsed_data=publisher_parsed_result,
        space=_SPACE,
        root_page_id=_ROOT_PAGE_ID,
        data_dir=tmp_path,
        batch_size=10,
        batch_delay_seconds=0.0,
    )
    strategy.execute()

    captured_view_models = publisher_capturing_document_builder.captured_view_models
    assert (
        len(captured_view_models) > 0
    ), "builder.build() должен быть вызван хотя бы один раз (одна страница паспорта)"
    for vm in captured_view_models:
        assert "legacy_contents" in vm, (
            f"view_model, переданный в builder.build(), должен содержать 'legacy_contents', "
            f"получены ключи: {list(vm.keys())}"
        )
        assert isinstance(
            vm["legacy_contents"], dict
        ), "legacy_contents должен быть словарём (пустым или заполненным)"


@pytest.mark.business_logic
def test_hierarchy_created_for_each_component(
    publisher_multi_component_result: ParsedResult,
    publisher_document_builder: FakeDocumentBuilder,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    BL-PS-07
    Бизнес-правило: ensure_hierarchy_exists() вызывается ровно один раз для
    каждой пары (компонент, релиз) в ParsedResult.

    Предусловия:
        - PageHierarchyManager.ensure_hierarchy_exists перехватывается.
        - PassportConverter.convert застаблен.

    Шаги:
        1. Патчим ensure_hierarchy_exists, чтобы фиксировать пары
           (имя_компонента, версия_релиза).
        2. Вызвать execute().

    Ожидаемый результат:
        Набор зафиксированных пар (компонент, версия) равен полному набору пар,
        полученных из ParsedResult.components[*].releases.
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
        "convert",
        return_value=dict(_STUB_TRANSFORM_RESULT),
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
        f"ensure_hierarchy_exists должен вызываться для всех пар (компонент, версия).\n"
        f"Ожидалось: {expected_pairs}\nПолучено: {actual_pairs}"
    )


@pytest.mark.business_logic
def test_passport_page_republished_once_per_channel_sharing_same_version(
    publisher_multi_channel_result: ParsedResult,
    publisher_document_builder: FakeDocumentBuilder,
    tmp_path: Path,
    mocker: Any,
) -> None:
    """
    Бизнес-правило (текущее поведение — задокументировано, чтобы будущее изменение
    было осознанным решением, а не случайной регрессией):

    PassportsStrategy.execute() формирует список работы исключительно из пар
    (имя_компонента, версия_релиза), по одной на каждый объект Release
    (см. цикл work_items в execute()) — без дедупликации по каналам.
    Компонент, опубликованный через несколько каналов под ОДНОЙ и той же версией
    (comp_alpha в publisher_multi_channel_result: 'fast' и 'stable', обе '2.0.0'),
    поэтому ставится в очередь дважды для того, что PassportConverter рендерит
    как совершенно одинаковую страницу (PassportConverter._find_releases уже
    группирует каждый канал с одинаковой версией в одну страницу — см. его
    собственный docstring). Второй элемент работы не падает и не пропускается:
    он повторно находит только что созданную страницу и republish'ит её,
    увеличивая версию Confluence с идентичным содержимым.

    Предусловия:
        - publisher_multi_channel_result: comp_alpha имеет два релиза, оба версии
          '2.0.0' (каналы 'fast'/'stable'); comp_beta имеет один релиз, версии '1.0.0'.
        - PageHierarchyManager.ensure_hierarchy_exists застаблен (создание иерархии
          само по себе покрывается отдельно в test_hierarchy_manager.py).

    Шаги:
        1. Выполнить PassportsStrategy с RecordingConfluenceClient.
        2. Сравнить число зафиксированных вызовов publish_page с числом
           *различных* (компонент, версия) страниц.

    Ожидаемый результат (текущее поведение):
        report.pages_published == 3 (по одному на элемент работы: alpha/fast,
        alpha/stable, beta/fast), хотя различных страниц только 2.
        Оба вызова публикации alpha нацелены на идентичный заголовок страницы.
    """
    mocker.patch.object(
        PageHierarchyManager,
        "ensure_hierarchy_exists",
        return_value="version-page-fixed-id",
    )
    client = RecordingConfluenceClient()

    strategy = PassportsStrategy(
        confluence_client=client,
        document_builder=publisher_document_builder,
        parsed_data=publisher_multi_channel_result,
        space=_SPACE,
        root_page_id=_ROOT_PAGE_ID,
        data_dir=tmp_path,
        batch_size=10,
        batch_delay_seconds=0.0,
    )
    report = strategy.execute()

    work_item_count = sum(len(comp.releases) for comp in publisher_multi_channel_result.components)
    distinct_pages = {
        (comp.name, rel.version)
        for comp in publisher_multi_channel_result.components
        for rel in comp.releases
    }
    assert work_item_count == 3, "Проверка корректности фикстуры: 2 канала alpha + 1 канал beta"
    assert (
        len(distinct_pages) == 2
    ), "Проверка корректности: 2 канала alpha схлопываются в 1 уникальную версию"

    assert report.pages_published == work_item_count, (
        "Текущее поведение: republish происходит по одному разу на каждый рабочий "
        f"элемент канала, а не на уникальную страницу: ожидалось {work_item_count} "
        f"вызовов publish, отчёт сообщает {report.pages_published}"
    )
    assert len(client.published_pages) == work_item_count

    alpha_title = PassportsStrategy._make_page_title("alpha", "2.0.0")
    alpha_calls = [p for p in client.published_pages if p["title"] == alpha_title]
    assert len(alpha_calls) == 2, (
        "единственная уникальная страница alpha должна публиковаться/обновляться "
        "дважды (по разу на рабочий элемент канала) при текущем "
        "(без дедупликации) поведении"
    )

    # Ни один из вызовов publish_page (даже republish одной и той же страницы) не
    # сталкивается по page_id: счётчик RecordingConfluenceClient должен выдавать
    # уникальные ID.
    page_ids = [d["page_id"] for d in report.details if d and d.get("page_id")]
    assert len(page_ids) == len(
        set(page_ids)
    ), "Каждая публикация должна получать уникальный page_id"
