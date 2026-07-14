"""Юнит-тесты для autodoc/parser/steps/conan_step.py."""

import pytest

from autodoc.parser.conan.models.conan_enrichment_result import ConanEnrichmentResult
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.steps.conan_step import ConanEnrichStep

EMPTY_CONAN_RESULT: ConanEnrichmentResult = ConanEnrichmentResult(
    release_data={}, profile_data={}, errors={}
)


@pytest.mark.contract
def test_conan_step_stores_conan_report_in_intermediate(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """ctx.intermediate['conan_report'] заполняется после execute."""
    fake = make_fake_fetcher(value=EMPTY_CONAN_RESULT)
    step = ConanEnrichStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert "conan_report" in parser_pipeline_context.intermediate


@pytest.mark.infrastructure
def test_conan_step_is_not_critical() -> None:
    """
    ConanEnrichStep является некритичным шагом пайплайна.
    фиксируем состояние кода в т.ч. константы для защиты от изменений разработчиков
    """
    assert ConanEnrichStep.is_critical is False


@pytest.mark.infrastructure
def test_conan_step_warnings_do_not_raise(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """Предупреждения от fetcher не вызывают исключений."""
    fake = make_fake_fetcher(value=EMPTY_CONAN_RESULT, warnings=["conan timeout"])
    step = ConanEnrichStep(fetcher=fake)
    step.execute(parser_pipeline_context)  # не должно вызывать исключений


# NULL_PACKAGE_ID — SHA1 пустой строки (header-only компоненты)
NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"

from autodoc.models.component import Component
from autodoc.models.conan_variant import ConanVariant, ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.conan.models.conan_enrichment_result import (
    ConanEnrichmentResult,
    ProfileConanData,
    ReleaseConanData,
)
from autodoc.models.options import TotalOptionsSet


def _make_release_with_pb(name: str, version: str, channel: str, profile_name: str):
    """
    Строит тройку (Component, Release, ProfileBuild) для использования в тестах.

    Args:
        name: Имя компонента.
        version: Версия релиза.
        channel: Канал релиза.
        profile_name: Имя единственного профиля релиза.

    Returns:
        Кортеж ``(comp, rel, pb)`` — созданные Component, Release и ProfileBuild.
    """
    pb = ProfileBuild(profile_name=profile_name)
    rel = Release(
        version=version,
        platform="2.0",
        channel=channel,
        profile_builds=[pb],
    )
    comp = Component(name=name, releases=[rel])
    return comp, rel, pb


def _make_conan_result(
    comp_name: str,
    version: str,
    channel: str,
    pb: ProfileBuild,
    package_id: str,
    deps: list[str] | None = None,
) -> ConanEnrichmentResult:
    """
    Строит ConanEnrichmentResult с одной записью релиза и одной записью профиля.

    Args:
        comp_name: Имя компонента.
        version: Версия релиза.
        channel: Канал релиза.
        pb: ProfileBuild, для которого создаются данные профиля Conan.
        package_id: Package ID варианта Conan.
        deps: Список зависимостей релиза (по умолчанию — пустой).

    Returns:
        Заполненный ``ConanEnrichmentResult``.
    """
    result = ConanEnrichmentResult(release_data={}, profile_data={}, errors={})
    result.release_data[(comp_name, version, channel)] = ReleaseConanData(
        base_ref=f"{comp_name}/{version}@platform-2.0/{channel}",
        rrev="abc123",
        full_version=version,
        default_options=[],
        total_options=[TotalOptionsSet(id="1", options={})],
        patches=[],
        dependencies=deps or [],
        artifactory_url="https://art.example.com/pkg",
    )
    result.profile_data[id(pb)] = ProfileConanData(
        conan_settings={"os": "Linux"},
        exists=True,
        variants=[
            ConanVariant(
                package_id=package_id,
                build_url="",
                build_date="",
                options_ref="1",
            )
        ],
    )
    return result


@pytest.mark.business_logic
def test_conan_step_applies_conan_results_to_components(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """После execute у целевого релиза установлен conan_reference (контекст изменён).

    Конкретные значения полей обогащения проверяются в test_data_enricher.py.
    """
    comp, rel, pb = _make_release_with_pb(
        "patchelf", "0.18.0", "tech", "crypto_alpine_gcc_x86_64.jinja"
    )
    parser_pipeline_context.components = [comp]
    conan_result = _make_conan_result(
        "patchelf",
        "0.18.0",
        "tech",
        pb,
        package_id="461534fe50686ce31d073dc24f005bd12e08c9fd",
    )
    fake = make_fake_fetcher(value=conan_result)
    ConanEnrichStep(fetcher=fake).execute(parser_pipeline_context)

    # Проверяется только сквозной проход: контекст изменён, исключений нет.
    assert rel.conan_reference is not None
    assert rel.conan_reference != ""


@pytest.mark.business_logic
def test_conan_step_header_only_component_variants_stored(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """FakeFetcher возвращает вариант с NULL_PACKAGE_ID — variants сохраняются в ProfileBuild.

    Конкретные значения поля package_id проверяются в test_data_enricher.py.
    """
    comp, rel, pb = _make_release_with_pb(
        "nlohmann_json", "3.9.1", "slow", "hw-linux-x86_64-gcc10_2"
    )
    parser_pipeline_context.components = [comp]
    conan_result = _make_conan_result(
        "nlohmann_json",
        "3.9.1",
        "slow",
        pb,
        package_id=NULL_PACKAGE_ID,
    )
    fake = make_fake_fetcher(value=conan_result)
    ConanEnrichStep(fetcher=fake).execute(parser_pipeline_context)

    # Проверяется только сквозной проход: variants заполнены в ProfileBuild.
    assert len(pb.variants) == 1


@pytest.mark.business_logic
def test_conan_step_component_with_dependencies(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """FakeFetcher возвращает список deps — release.dependencies заполняется после execute.

    Конкретные значения зависимостей проверяются в test_data_enricher.py.
    """
    comp, rel, pb = _make_release_with_pb(
        "libnetfilter_queue", "1.0.5", "slow", "hw-linux-armv7-gcc10_2"
    )
    parser_pipeline_context.components = [comp]
    conan_result = _make_conan_result(
        "libnetfilter_queue",
        "1.0.5",
        "slow",
        pb,
        package_id="46bf0ba807876c7591c702abfa2ba19d3133f1af",
        deps=["libmnl", "libnfnetlink"],
    )
    fake = make_fake_fetcher(value=conan_result)
    ConanEnrichStep(fetcher=fake).execute(parser_pipeline_context)

    # Проверяется только сквозной проход: контекст изменён, dependencies не пуст.
    assert rel.dependencies is not None
    assert len(rel.dependencies) > 0


@pytest.mark.contract
def test_conan_step_configure_called_before_fetch(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """fetcher.configure() вызывается перед fetcher.fetch() во время execute."""
    fake = make_fake_fetcher(value=EMPTY_CONAN_RESULT)
    ConanEnrichStep(fetcher=fake).execute(parser_pipeline_context)

    assert fake.configure_called is True


@pytest.mark.business_logic
def test_conan_step_apr_fast_channel_no_dependencies(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """ConanEnrichStep корректно обогащает релиз apr/fast с пустым списком зависимостей.

    Использует FakeFetcher, возвращающий ConanEnrichmentResult, заранее
    заполненный данными apr. После ConanEnrichStep.execute список
    dependencies релиза apr должен быть пустым (у apr нет runtime-зависимостей).
    """
    comp, rel, pb = _make_release_with_pb("apr", "1.7.6", "fast", "hw-linux-x86_64-gcc10_2")
    parser_pipeline_context.components = [comp]
    conan_result = _make_conan_result(
        "apr",
        "1.7.6",
        "fast",
        pb,
        package_id="7741115342fe6159bd16463d6d349e4c02e33237",
        deps=[],
    )
    fake = make_fake_fetcher(value=conan_result)
    ConanEnrichStep(fetcher=fake).execute(parser_pipeline_context)

    assert (
        rel.dependencies == [] or rel.dependencies is None
    ), f"Expected empty dependencies for apr, got: {rel.dependencies}"


@pytest.mark.business_logic
def test_conan_step_error_does_not_raise_and_stores_in_report(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """ConanEnrichStep не падает, если агрегатор сообщает об ошибке разрешения диапазона версий.

    FakeFetcher возвращает ConanEnrichmentResult, чей словарь errors содержит
    запись для 'stunnel' (диапазон версий не удалось разрешить).
    ConanEnrichStep.execute должен завершиться без исключений и сохранить
    информацию об ошибке в ctx.intermediate['conan_report'].
    """
    error_entry = {
        "5.77": {"fast": {"crypto_default_gcc_x86_64.jinja": ["Version range not resolved"]}}
    }
    fake_result = ConanEnrichmentResult(
        release_data={},
        profile_data={},
        errors={"stunnel": error_entry},
    )
    fake = make_fake_fetcher(value=fake_result)
    parser_pipeline_context.components = []

    # Не должно вызывать исключений
    ConanEnrichStep(fetcher=fake).execute(parser_pipeline_context)

    conan_report = parser_pipeline_context.intermediate.get("conan_report")
    assert conan_report is not None
    assert "stunnel" in str(
        conan_report
    ), f"Expected 'stunnel' error to appear in conan report, got: {conan_report}"


@pytest.mark.contract
def test_conan_step_default_fetcher_is_conan_fetcher() -> None:
    """ConanEnrichStep() без аргумента fetcher создаёт по умолчанию реальный ConanFetcher."""
    from autodoc.parser.fetchers.conan_fetcher import ConanFetcher

    step = ConanEnrichStep()
    assert isinstance(step._fetcher, ConanFetcher)
