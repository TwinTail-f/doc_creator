"""Юнит-тесты для autodoc/parser/steps/finalize_step.py."""

import pytest

from autodoc.exceptions import ParsingError
from autodoc.models.component import Component
from autodoc.models.conan_variant import ConanVariant, ProfileBuild
from autodoc.models.profile_definition import ProfileDefinition
from autodoc.models.release import Release
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.steps.finalize_step import FinalizeStep

from tests.unit.parser.conftest import (
    make_conan_variant,
    NULL_PACKAGE_ID as _NULL_PACKAGE_ID,
)

NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
REAL_PACKAGE_ID: str = "575ea8086554107ae2c0fdbb4909d62390c52b77"


def _null_variant() -> ConanVariant:
    """Создаёт ConanVariant с нулевым (header-only) package_id."""
    return ConanVariant(package_id=NULL_PACKAGE_ID, build_url="", build_date="", options_ref="1")


def _real_variant() -> ConanVariant:
    """Создаёт ConanVariant с ненулевым package_id."""
    return ConanVariant(
        package_id=REAL_PACKAGE_ID,
        build_url="https://art.example.com/pkg",
        build_date="2024-01-01",
        options_ref="1",
    )


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


def _bl_make_variant() -> ConanVariant:
    """Возвращает минимальный ConanVariant с ненулевым package_id."""
    return ConanVariant(
        package_id="575ea8086554107ae2c0fdbb4909d62390c52b77",
        build_url="",
        build_date="",
        options_ref="1",
    )


def _bl_make_release(profile_builds: list | None = None) -> Release:
    """Возвращает минимальный Release; profile_builds по умолчанию пуст.

    Args:
        profile_builds: Список ProfileBuild или None для пустого списка.

    Returns:
        Собранный объект Release.
    """
    return Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        profile_builds=profile_builds if profile_builds is not None else [],
    )


def _bl_make_component(name: str = "lib", releases: list | None = None) -> Component:
    """Возвращает минимальный Component с заданным списком релизов.

    Args:
        name: Имя компонента.
        releases: Список релизов или None для пустого списка.

    Returns:
        Собранный объект Component.
    """
    return Component(
        name=name,
        git_project="DEP",
        git_repo=name,
        releases=releases if releases is not None else [],
    )


@pytest.mark.business_logic
def test_finalize_step_sets_header_only_true(
    parser_pipeline_context,
) -> None:
    """is_header_only равен True, когда все варианты всех профилей имеют нулевой package_id."""
    pb1 = ProfileBuild(profile_name="profile_a", exists=True, variants=[_null_variant()])
    pb2 = ProfileBuild(profile_name="profile_b", exists=True, variants=[_null_variant()])
    release = _make_release([pb1, pb2])
    comp = _make_component("mylib", release)
    parser_pipeline_context.components = [comp]
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert comp.is_header_only is True


@pytest.mark.business_logic
def test_finalize_step_removes_profile_build_with_exists_false(
    parser_pipeline_context,
) -> None:
    """FinalizeStep удаляет ProfileBuild с exists=False, сохраняя живой профиль."""
    pb_live = ProfileBuild(profile_name="live", exists=True, variants=[])
    pb_dead = ProfileBuild(profile_name="dead", exists=False, variants=[])
    release = _make_release([pb_live, pb_dead])
    parser_pipeline_context.components = [_make_component("mylib", release)]
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert len(release.profile_builds) == 1
    assert release.profile_builds[0].profile_name == "live"


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
def test_finalize_step_raises_parsing_error_on_validation_failure(
    parser_pipeline_context,
    mocker,
) -> None:
    """FinalizeStep оборачивает реальный Pydantic ValidationError в ParsingError."""
    from pydantic import ValidationError as PydanticValidationError  # noqa: F401

    def _force_validation_error(ctx):  # noqa: ANN001
        # Передаём None в обязательное строковое поле — вызывает реальный ValidationError.
        return ParsedResult(
            generated_at=None,  # type: ignore[arg-type]
            platform_version="2.0",
            components=[],
            profile_definitions=[],
        )

    # Патчим на классе — Python передаёт self первым аргументом,
    # поэтому side_effect должен принимать (self, ctx), а не только (ctx).
    mocker.patch.object(FinalizeStep, "_build_result", side_effect=_force_validation_error)
    parser_pipeline_context.components = []
    step = FinalizeStep()

    with pytest.raises(ParsingError):
        step.execute(parser_pipeline_context)


@pytest.mark.contract
def test_finalize_step_execute_applies_steps_in_order(
    parser_pipeline_context,
    mocker,
) -> None:
    """execute() применяет фильтрацию, дедупликацию и сборку результата в этом порядке."""
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


_SHARED_PROFILE: str = "linux_x64_gcc12"
_IMAGE_V1: str = "registry.example.com/builder:v1"
_IMAGE_V2: str = "registry.example.com/builder:v2"


@pytest.mark.business_logic
def test_finalize_step_sets_header_only_for_nlohmann_json(
    parser_pipeline_context,
) -> None:
    """Компонент, все варианты которого имеют NULL_PACKAGE_ID, получает is_header_only=True."""
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
    comp = Component(name="nlohmann_json", releases=[rel])
    parser_pipeline_context.components = [comp]

    FinalizeStep().execute(parser_pipeline_context)

    assert parser_pipeline_context.result is not None
    result_comp = parser_pipeline_context.result.components[0]
    assert result_comp.is_header_only is True


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
def test_finalize_step_removes_non_existing_profiles(
    parser_pipeline_context,
) -> None:
    """FinalizeStep удаляет только профили с exists=False, остальные остаются нетронутыми."""
    pb_live1 = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2", exists=True, variants=[])
    pb_live2 = ProfileBuild(profile_name="crypto_alpine_gcc_x86_64.jinja", exists=True, variants=[])
    pb_dead = ProfileBuild(profile_name="hw-linux-armv7-gcc10_2", exists=False, variants=[])
    rel = Release(
        version="1.0.0",
        platform="2.0",
        channel="slow",
        profile_builds=[pb_live1, pb_live2, pb_dead],
    )
    comp = Component(name="somelib", releases=[rel])
    parser_pipeline_context.components = [comp]

    FinalizeStep().execute(parser_pipeline_context)

    assert len(rel.profile_builds) == 2
    remaining_names = {pb.profile_name for pb in rel.profile_builds}
    assert "hw-linux-armv7-gcc10_2" not in remaining_names


@pytest.mark.business_logic
def test_header_only_requires_all_profiles_to_have_null_package_id(
    parser_pipeline_context,
) -> None:
    """Хотя бы один вариант с ненулевым package_id делает весь компонент не header-only."""
    null_id = _NULL_PACKAGE_ID
    pb1 = ProfileBuild(
        profile_name="p1",
        exists=True,
        variants=[ConanVariant(package_id=null_id, build_url="", build_date="", options_ref="")],
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
    comp_a = _make_comp_with_variant("compA", package_id=_NULL_PACKAGE_ID)
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
def test_header_only_with_no_profile_builds_is_false(
    parser_pipeline_context,
) -> None:
    """Релиз без единого профиля даёт is_header_only=False."""
    release = Release(
        version="1.0",
        platform="2.2",
        channel="fast",
        conan_reference="",
        artifactory_url="",
        profile_builds=[],
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
def test_header_only_with_empty_variants_per_profile_is_false(
    parser_pipeline_context,
) -> None:
    """Профиль без вариантов не даёт доказательств header-only — итоговый флаг False."""
    pb = ProfileBuild(profile_name="hw-linux-x86_64", exists=True, variants=[])
    release = Release(
        version="1.0",
        platform="2.2",
        channel="fast",
        conan_reference="",
        artifactory_url="",
        profile_builds=[pb],
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
def test_filter_empty_profiles_removes_only_false_profiles(
    parser_pipeline_context,
) -> None:
    """После финализации в profile_builds остаются только профили с exists=True."""
    pb_exists = ProfileBuild(profile_name="p1", exists=True, variants=[make_conan_variant()])
    pb_exists2 = ProfileBuild(profile_name="p2", exists=True, variants=[make_conan_variant()])
    pb_missing = ProfileBuild(profile_name="p3", exists=False, variants=[])

    release = Release(
        version="1.0",
        platform="2.2",
        channel="fast",
        conan_reference="",
        artifactory_url="",
        profile_builds=[pb_exists, pb_missing, pb_exists2],
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

    remaining_names = {pb.profile_name for pb in release.profile_builds}
    assert remaining_names == {"p1", "p2"}
    assert "p3" not in remaining_names


@pytest.mark.business_logic
def test_filter_empty_profiles_count_matches_actual_removed() -> None:
    """_filter_empty_profiles возвращает точное число удалённых профилей на большем наборе данных."""
    pbs_false = [ProfileBuild(profile_name=f"profile-{i}", exists=False) for i in range(5)]
    pb_true = ProfileBuild(
        profile_name="hw-linux-x86_64", exists=True, variants=[_bl_make_variant()]
    )

    release = _bl_make_release()
    release.profile_builds = pbs_false + [pb_true]
    comp = _bl_make_component(releases=[release])

    step = FinalizeStep()
    removed = step._filter_empty_profiles([comp])

    assert removed == 5


@pytest.mark.business_logic
def test_filter_empty_profiles_release_with_all_false_stays_in_component() -> None:
    """Release остаётся в компоненте, даже если все его ProfileBuild были удалены."""
    pb_bad = ProfileBuild(profile_name="hw-linux-x86_64", exists=False)
    release = _bl_make_release()
    release.profile_builds = [pb_bad]
    comp = _bl_make_component(releases=[release])

    step = FinalizeStep()
    step._filter_empty_profiles([comp])

    assert len(comp.releases) == 1
    assert comp.releases[0].profile_builds == []


@pytest.mark.business_logic
def test_filter_empty_profiles_accumulates_count_across_components() -> None:
    """_filter_empty_profiles суммирует число удалённых профилей по всем компонентам."""

    def _make_comp_with_mixed_pbs(name: str) -> Component:
        """Строит компонент с одним живым и одним мёртвым ProfileBuild."""
        good = ProfileBuild(
            profile_name="hw-linux-x86_64",
            exists=True,
            variants=[_bl_make_variant()],
        )
        bad = ProfileBuild(profile_name="hw-linux-armv8", exists=False)
        r = _bl_make_release()
        r.profile_builds = [good, bad]
        return _bl_make_component(name=name, releases=[r])

    comps = [_make_comp_with_mixed_pbs(f"lib{i}") for i in range(3)]

    step = FinalizeStep()
    removed = step._filter_empty_profiles(comps)

    assert removed == 3


@pytest.mark.business_logic
def test_dedup_profile_definitions_last_write_wins() -> None:
    """При совпадении profile_name побеждает последняя запись в списке."""
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

    step = FinalizeStep()
    result = step._deduplicate_profile_definitions([pd_early, pd_late])

    assert len(result) == 1
    assert result[0].docker_image == "harbor.example.com/late:2"
    assert result[0].conan_settings == {"os": "Linux"}


@pytest.mark.business_logic
def test_dedup_profile_definitions_unique_names_all_preserved() -> None:
    """Записи ProfileDefinition с уникальными именами сохраняются все без исключения."""
    pds = [
        ProfileDefinition(profile_name=f"hw-linux-{arch}", docker_image="", conan_settings={})
        for arch in ["x86_64", "armv8", "rpi4"]
    ]

    step = FinalizeStep()
    result = step._deduplicate_profile_definitions(pds)

    assert len(result) == 3
    names = {pd.profile_name for pd in result}
    assert names == {"hw-linux-x86_64", "hw-linux-armv8", "hw-linux-rpi4"}


@pytest.mark.business_logic
def test_dedup_profile_definitions_empty_input_returns_empty() -> None:
    """Пустой входной список не вызывает исключений и возвращает пустой список."""
    step = FinalizeStep()
    result = step._deduplicate_profile_definitions([])
    assert result == []
