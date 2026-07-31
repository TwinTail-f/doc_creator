"""Юнит-тесты для autodoc/parser/steps/finalize_step.py."""

import pytest
from pydantic import ValidationError as PydanticValidationError
from pytest_mock import MockerFixture

from autodoc.exceptions import ParsingError
from autodoc.models.component import Component
from autodoc.models.conan_variant import ConanVariant, ProfileBuild
from autodoc.models.parsed_result import ParsedResult
from autodoc.models.profile_definition import ProfileDefinition
from autodoc.models.release import Release
from autodoc.parser.steps.finalize_step import FinalizeStep
from tests.unit.parser.conftest import make_conan_variant, NULL_PACKAGE_ID


def _null_variant() -> ConanVariant:
    """Создаёт ConanVariant с нулевым (header-only) package_id."""
    return ConanVariant(package_id=NULL_PACKAGE_ID, build_url="", build_date="", options_ref="1")


def _make_release(profile_builds: list[ProfileBuild]) -> Release:
    """Строит минимальный Release с заданными profile_builds.

    Args:
        profile_builds: Список ProfileBuild, которые нужно поместить в релиз.

    Returns:
        Собранный объект Release, готовый к использованию в тестах.
    """
    return Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        profile_builds=profile_builds,
    )


def _make_component(name: str, release: Release) -> Component:
    """Строит минимальный Component, оборачивающий один Release.

    Args:
        name: Имя компонента.
        release: Единственный релиз, который будет привязан к компоненту.

    Returns:
        Собранный объект Component.
    """
    return Component(name=name, git_project="DEP", git_repo=name, releases=[release])


def _make_comp_with_variant(name: str, package_id: str) -> Component:
    """Строит компонент с одним релизом, одним профилем и одним вариантом.

    Используется для тестов, где is_header_only зависит только от переданного
    package_id.

    Args:
        name: Имя и идентификатор отображения компонента.
        package_id: Значение package_id для единственного ConanVariant.

    Returns:
        Полностью собранный Component, готовый для FinalizeStep.execute().
    """
    pb = ProfileBuild(
        profile_name="hw-linux-x86_64",
        exists=True,
        variants=[
            ConanVariant(package_id=package_id, build_url="", build_date="", options_ref="1")
        ],
    )
    release = Release(
        version="1.0",
        platform="2.2",
        channel="fast",
        conan_reference="",
        artifactory_url="",
        profile_builds=[pb],
    )
    return Component(
        name=name,
        description="",
        git_project="P",
        git_repo="r",
        git_url="",
        is_header_only=False,
        releases=[release],
    )


def _minimal_all_null_component() -> Component:
    """Компонент "mylib" с 2 профилями, у каждого единственный вариант с нулевым package_id."""
    pb1 = ProfileBuild(profile_name="profile_a", exists=True, variants=[_null_variant()])
    pb2 = ProfileBuild(profile_name="profile_b", exists=True, variants=[_null_variant()])
    release = _make_release([pb1, pb2])
    return _make_component("mylib", release)


def _real_nlohmann_json_component() -> Component:
    """Реальный компонент nlohmann_json/3.9.1 с единственным вариантом нулевого package_id."""
    pb = ProfileBuild(
        profile_name="hw-linux-x86_64-gcc10_2",
        exists=True,
        variants=[
            ConanVariant(package_id=NULL_PACKAGE_ID, build_url="", build_date="", options_ref="1")
        ],
    )
    rel = Release(
        version="3.9.1",
        platform="2.0",
        channel="slow",
        profile_builds=[pb],
    )
    return Component(name="nlohmann_json", releases=[rel])


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "component_factory",
    [_minimal_all_null_component, _real_nlohmann_json_component],
    ids=["synthetic", "nlohmann_json"],
)
def test_finalize_step_sets_header_only_true(
    parser_pipeline_context,
    component_factory,
) -> None:
    """Если у всех вариантов профиля package_id нулевой (header-only признак),
    FinalizeStep выставляет is_header_only=True — как на синтетических
    данных, так и на реальном компоненте nlohmann_json."""
    comp = component_factory()
    parser_pipeline_context.components = [comp]
    FinalizeStep().execute(parser_pipeline_context)
    assert comp.is_header_only is True


def _two_profiles_one_missing() -> Release:
    """Релиз с 2 профилями: один живой, один exists=False."""
    pb_live = ProfileBuild(profile_name="live", exists=True, variants=[])
    pb_dead = ProfileBuild(profile_name="dead", exists=False, variants=[])
    return _make_release([pb_live, pb_dead])


def _three_profiles_one_missing() -> Release:
    """Релиз с 3 профилями: два живых, один exists=False."""
    pb_live1 = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2", exists=True, variants=[])
    pb_live2 = ProfileBuild(profile_name="crypto_alpine_gcc_x86_64.jinja", exists=True, variants=[])
    pb_dead = ProfileBuild(profile_name="hw-linux-armv7-gcc10_2", exists=False, variants=[])
    return Release(
        version="1.0.0",
        platform="2.0",
        channel="slow",
        profile_builds=[pb_live1, pb_live2, pb_dead],
    )


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "release_factory",
    [_two_profiles_one_missing, _three_profiles_one_missing],
    ids=["two-profiles", "three-profiles"],
)
def test_finalize_step_removes_non_existing_profiles(
    parser_pipeline_context,
    release_factory,
) -> None:
    """ProfileBuild с exists=False удаляется из итогового результата,
    ProfileBuild с exists=True остаётся — независимо от общего числа
    профилей на входе."""
    release = release_factory()
    total_before = len(release.profile_builds)
    dead_names_before = {pb.profile_name for pb in release.profile_builds if not pb.exists}
    parser_pipeline_context.components = [_make_component("somelib", release)]
    FinalizeStep().execute(parser_pipeline_context)
    assert len(release.profile_builds) == total_before - len(dead_names_before)
    remaining_names = {pb.profile_name for pb in release.profile_builds}
    assert remaining_names.isdisjoint(dead_names_before)


@pytest.mark.business_logic
def test_finalize_step_sorts_components_by_name(
    parser_pipeline_context,
) -> None:
    """Компоненты сортируются алфавитно по имени (без учёта регистра) после финализации."""
    zlib_component = _make_component("Zlib", _make_release([]))
    apache_component = _make_component("apache", _make_release([]))
    parser_pipeline_context.components = [zlib_component, apache_component]
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.components[0].name == "apache"


@pytest.mark.business_logic
def test_finalize_step_populates_ctx_result(
    parser_pipeline_context,
) -> None:
    """ctx.result заполняется корректным ParsedResult после execute."""
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.result is not None
    assert isinstance(parser_pipeline_context.result, ParsedResult)
    assert parser_pipeline_context.result.platform_version == "2.0"


@pytest.mark.business_logic
def test_finalize_step_raises_parsing_error_on_invalid_platform_version(
    parser_pipeline_context,
) -> None:
    """FinalizeStep оборачивает реальный Pydantic ValidationError в ParsingError.

    platform_version — единственное обязательное строковое поле ParsedResult,
    заполняемое напрямую из конфига, а не из данных, накопленных пайплайном.
    """
    parser_pipeline_context.components = []
    # platform_version — обязательное строковое поле ParsedResult; None здесь
    # эмулирует ситуацию, когда конфиг оказался повреждён к моменту финализации.
    object.__setattr__(parser_pipeline_context.config, "platform_version", None)
    step = FinalizeStep()

    with pytest.raises(ParsingError):
        step.execute(parser_pipeline_context)


@pytest.mark.business_logic
def test_finalize_step_execute_wraps_validation_error_from_build_result(
    parser_pipeline_context,
    mocker: MockerFixture,
) -> None:
    """execute() оборачивает в ParsingError PydanticValidationError, долетевший
    из _build_result напрямую (в обход её собственного except) — это внешний
    try/except в execute, отдельный от уже покрытого внутреннего в _build_result."""
    validation_error = PydanticValidationError.from_exception_data("ParsedResult", [])
    mocker.patch.object(FinalizeStep, "_build_result", side_effect=validation_error)

    with pytest.raises(ParsingError, match="Валидация результата не прошла"):
        FinalizeStep().execute(parser_pipeline_context)


@pytest.mark.infrastructure
def test_finalize_step_execute_applies_steps_in_order(
    parser_pipeline_context,
    mocker: MockerFixture,
) -> None:
    """execute() применяет фильтрацию, дедупликацию и сборку результата в этом порядке.

    Порядок не наблюдаем одним ассертом через публичный API: обёртки-шпионы
    вокруг приватных методов сохраняют оригинальное поведение (вызывают
    original_*) и лишь протоколируют порядок вызовов — осознанный компромисс,
    а не проверка деталей реализации вместо результата.
    """
    call_order: list[str] = []

    original_filter = FinalizeStep._filter_empty_profiles
    original_dedup = FinalizeStep._deduplicate_profile_definitions
    original_build = FinalizeStep._build_result

    def _tracked_filter(self, components):  # noqa: ANN001
        call_order.append("_filter_empty_profiles")
        return original_filter(self, components)

    def _tracked_dedup(self, definitions):  # noqa: ANN001
        call_order.append("_deduplicate_profile_definitions")
        return original_dedup(self, definitions)

    def _tracked_build(self, ctx):  # noqa: ANN001
        call_order.append("_build_result")
        return original_build(self, ctx)

    mocker.patch.object(FinalizeStep, "_filter_empty_profiles", _tracked_filter)
    mocker.patch.object(FinalizeStep, "_deduplicate_profile_definitions", _tracked_dedup)
    mocker.patch.object(FinalizeStep, "_build_result", _tracked_build)

    step = FinalizeStep()
    step.execute(parser_pipeline_context)

    assert call_order == [
        "_filter_empty_profiles",
        "_deduplicate_profile_definitions",
        "_build_result",
    ]


@pytest.mark.business_logic
def test_finalize_step_patchelf_two_versions_not_header_only(
    parser_pipeline_context,
) -> None:
    """Компонент с двумя релизами и реальными package_id не помечается header-only, оба релиза сохраняются."""
    REAL_PKG = "461534fe50686ce31d073dc24f005bd12e08c9fd"

    def _make_rel(version: str) -> Release:
        pb = ProfileBuild(
            profile_name="hw-linux-x86_64-gcc10_2",
            exists=True,
            variants=[
                ConanVariant(package_id=REAL_PKG, build_url="", build_date="", options_ref="1")
            ],
        )
        return Release(
            version=version,
            platform="2.0",
            channel="tech",
            profile_builds=[pb],
        )

    comp = Component(name="patchelf", releases=[_make_rel("0.16.1"), _make_rel("0.18.0")])
    parser_pipeline_context.components = [comp]

    FinalizeStep().execute(parser_pipeline_context)

    result_comp = parser_pipeline_context.result.components[0]
    assert len(result_comp.releases) == 2
    assert not result_comp.is_header_only


@pytest.mark.business_logic
def test_finalize_step_preserves_prg_quant_component(
    parser_pipeline_context,
) -> None:
    """Компонент из нестандартного git_project сохраняется и корректно сортируется по имени."""
    pb = ProfileBuild(
        profile_name="hw-linux-armv7-gcc10_2",
        exists=True,
        variants=[
            ConanVariant(
                package_id="46bf0ba807876c7591c702abfa2ba19d3133f1af",
                build_url="",
                build_date="",
                options_ref="1",
            )
        ],
    )
    rel = Release(
        version="1.0.5",
        platform="2.0",
        channel="slow",
        profile_builds=[pb],
    )
    comp_lfq = Component(name="libnetfilter_queue", git_project="PRG_Quant", releases=[rel])
    comp_apr = Component(name="apr", releases=[])
    parser_pipeline_context.components = [comp_lfq, comp_apr]

    FinalizeStep().execute(parser_pipeline_context)

    names = [c.name for c in parser_pipeline_context.result.components]
    assert "libnetfilter_queue" in names
    assert names.index("apr") < names.index("libnetfilter_queue")


@pytest.mark.business_logic
def test_finalize_step_sqlite3_dependencies_preserved(
    parser_pipeline_context,
) -> None:
    """Список dependencies релиза остаётся неизменным после FinalizeStep."""
    pb = ProfileBuild(
        profile_name="crypto_default_gcc_armv7hf.jinja",
        exists=True,
        variants=[
            ConanVariant(
                package_id="8c7b3c7905519eea8fda5ff9dde7fbefec90da76",
                build_url="",
                build_date="",
                options_ref="1",
            )
        ],
    )
    rel = Release(
        version="3.51.2",
        platform="2.0",
        channel="fast",
        profile_builds=[pb],
    )
    rel.dependencies = ["icu", "tcl"]
    comp = Component(name="sqlite3", releases=[rel])
    parser_pipeline_context.components = [comp]

    FinalizeStep().execute(parser_pipeline_context)

    result_rel = parser_pipeline_context.result.components[0].releases[0]
    assert result_rel.dependencies == ["icu", "tcl"]


@pytest.mark.business_logic
def test_header_only_requires_all_profiles_to_have_null_package_id(
    parser_pipeline_context,
) -> None:
    """Хотя бы один вариант с ненулевым package_id делает весь компонент не header-only."""
    pb1 = ProfileBuild(
        profile_name="p1",
        exists=True,
        variants=[
            ConanVariant(package_id=NULL_PACKAGE_ID, build_url="", build_date="", options_ref="")
        ],
    )
    pb2 = ProfileBuild(
        profile_name="p2",
        exists=True,
        variants=[
            ConanVariant(package_id="regular_id", build_url="", build_date="", options_ref="")
        ],
    )
    release = Release(
        version="1.0",
        platform="2.2",
        channel="fast",
        conan_reference="",
        artifactory_url="",
        profile_builds=[pb1, pb2],
    )
    comp = Component(
        name="mylib",
        description="",
        git_project="P",
        git_repo="r",
        git_url="",
        is_header_only=False,
        releases=[release],
    )

    ctx = parser_pipeline_context
    ctx.components = [comp]
    FinalizeStep().execute(ctx)

    assert comp.is_header_only is False


@pytest.mark.business_logic
def test_header_only_evaluated_per_component_independently(
    parser_pipeline_context,
) -> None:
    """is_header_only вычисляется независимо для каждого компонента в одном запуске."""
    comp_a = _make_comp_with_variant("compA", package_id=NULL_PACKAGE_ID)
    comp_b = _make_comp_with_variant("compB", package_id="regular_id")

    ctx = parser_pipeline_context
    ctx.components = [comp_a, comp_b]
    FinalizeStep().execute(ctx)

    assert comp_a.is_header_only is True
    assert comp_b.is_header_only is False


@pytest.mark.business_logic
def test_header_only_null_package_id_exact_sha1_value(
    parser_pipeline_context,
) -> None:
    """Только точное значение NULL_PACKAGE_ID считается нулевым — отличие даже в одном символе даёт False."""
    almost_null = "da39a3ee5e6b4b0d3255bfef95601890afd80700"  # Изменён последний символ.
    comp = _make_comp_with_variant("mylib", package_id=almost_null)

    ctx = parser_pipeline_context
    ctx.components = [comp]
    FinalizeStep().execute(ctx)

    assert comp.is_header_only is False


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "profile_builds",
    [
        # у релиза вообще нет профилей
        pytest.param([], id="no-profile-builds"),
        # профиль есть, но у него нет ни одного варианта
        pytest.param(
            [ProfileBuild(profile_name="hw-linux-x86_64", exists=True, variants=[])],
            id="profile-with-empty-variants",
        ),
    ],
)
def test_header_only_without_evidence_is_false(
    parser_pipeline_context,
    profile_builds: list[ProfileBuild],
) -> None:
    """Без вариантов, доказывающих header-only (нет профилей вовсе, либо
    профиль есть, но у него пустой variants), итоговый флаг остаётся
    False — при отсутствии профилей и при профиле без вариантов это одно
    и то же бизнес-правило "нет доказательств -> False"."""
    release = Release(
        version="1.0",
        platform="2.2",
        channel="fast",
        conan_reference="",
        artifactory_url="",
        profile_builds=profile_builds,
    )
    comp = Component(
        name="mylib",
        description="",
        git_project="P",
        git_repo="r",
        git_url="",
        is_header_only=False,
        releases=[release],
    )

    ctx = parser_pipeline_context
    ctx.components = [comp]
    FinalizeStep().execute(ctx)

    assert comp.is_header_only is False


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "make_profile_builds",
    [
        # большинство профилей живые, один мёртвый
        pytest.param(
            lambda: [
                ProfileBuild(profile_name="p1", exists=True, variants=[make_conan_variant()]),
                ProfileBuild(profile_name="p3", exists=False, variants=[]),
                ProfileBuild(profile_name="p2", exists=True, variants=[make_conan_variant()]),
            ],
            id="mixed-majority-alive",
        ),
        # большинство профилей мёртвые, один живой
        pytest.param(
            lambda: [ProfileBuild(profile_name=f"profile-{i}", exists=False) for i in range(5)]
            + [
                ProfileBuild(
                    profile_name="hw-linux-x86_64", exists=True, variants=[make_conan_variant()]
                )
            ],
            id="mixed-majority-dead",
        ),
        # все профили мёртвые -> release остаётся в компоненте с пустым profile_builds
        pytest.param(
            lambda: [ProfileBuild(profile_name="hw-linux-x86_64", exists=False)],
            id="all-dead",
        ),
    ],
)
def test_filter_empty_profiles(
    parser_pipeline_context,
    make_profile_builds,
) -> None:
    """FinalizeStep удаляет из release.profile_builds все записи с exists=False,
    сохраняя записи с exists=True в исходном порядке и точном составе —
    независимо от соотношения живых и мёртвых профилей, в том числе когда
    живых не остаётся вовсе (Release при этом остаётся в компоненте)."""
    profile_builds = make_profile_builds()
    expected_alive_pbs = [pb for pb in profile_builds if pb.exists]
    release = _make_release(profile_builds)
    comp = _make_component("lib", release)

    ctx = parser_pipeline_context
    ctx.components = [comp]
    FinalizeStep().execute(ctx)

    assert release.profile_builds == expected_alive_pbs
    assert len(comp.releases) == 1


@pytest.mark.business_logic
def test_filter_empty_profiles_accumulates_count_across_components(
    parser_pipeline_context,
) -> None:
    """Фильтрация exists=False применяется независимо к каждому компоненту в одном запуске."""

    def _make_comp_with_mixed_pbs(name: str) -> Component:
        """Строит компонент с одним живым и одним мёртвым ProfileBuild."""
        good = ProfileBuild(
            profile_name="hw-linux-x86_64",
            exists=True,
            variants=[make_conan_variant()],
        )
        bad = ProfileBuild(profile_name="hw-linux-armv8", exists=False)
        r = _make_release([good, bad])
        return _make_component(name, r)

    comps = [_make_comp_with_mixed_pbs(f"lib{i}") for i in range(3)]

    ctx = parser_pipeline_context
    ctx.components = comps
    FinalizeStep().execute(ctx)

    for comp in comps:
        assert len(comp.releases[0].profile_builds) == 1
        assert comp.releases[0].profile_builds[0].exists is True


@pytest.mark.business_logic
def test_dedup_profile_definitions_last_write_wins(parser_pipeline_context) -> None:
    """При совпадении profile_name в итоговом ctx.profile_definitions побеждает последняя запись."""
    pd_early = ProfileDefinition(
        profile_name="hw-linux-x86_64",
        docker_image="harbor.example.com/early:1",
        conan_settings={},
    )
    pd_late = ProfileDefinition(
        profile_name="hw-linux-x86_64",
        docker_image="harbor.example.com/late:2",
        conan_settings={"os": "Linux"},
    )

    ctx = parser_pipeline_context
    ctx.profile_definitions = [pd_early, pd_late]
    FinalizeStep().execute(ctx)

    assert len(ctx.profile_definitions) == 1
    assert ctx.profile_definitions[0].docker_image == "harbor.example.com/late:2"
    assert ctx.profile_definitions[0].conan_settings == {"os": "Linux"}


@pytest.mark.business_logic
def test_dedup_profile_definitions_unique_names_all_preserved(parser_pipeline_context) -> None:
    """Записи ProfileDefinition с уникальными именами сохраняются все без исключения."""
    pds = [
        ProfileDefinition(profile_name=f"hw-linux-{arch}", docker_image="", conan_settings={})
        for arch in ["x86_64", "armv8", "rpi4"]
    ]

    ctx = parser_pipeline_context
    ctx.profile_definitions = pds
    FinalizeStep().execute(ctx)

    assert len(ctx.profile_definitions) == 3
    names = {pd.profile_name for pd in ctx.profile_definitions}
    assert names == {"hw-linux-x86_64", "hw-linux-armv8", "hw-linux-rpi4"}


@pytest.mark.business_logic
def test_dedup_profile_definitions_empty_input_returns_empty(parser_pipeline_context) -> None:
    """Пустой ctx.profile_definitions не вызывает исключений и остаётся пустым списком."""
    ctx = parser_pipeline_context
    ctx.profile_definitions = []
    FinalizeStep().execute(ctx)

    assert ctx.profile_definitions == []
