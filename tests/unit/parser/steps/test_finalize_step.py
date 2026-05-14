"""Юнит-тесты для autodoc/parser/steps/finalize_step.py."""

import pytest

from autodoc.exceptions import ParsingError
from autodoc.models.component import Component
from autodoc.models.conan_variant import ConanVariant, ProfileBuild
from autodoc.models.profile_definition import ProfileDefinition
from autodoc.models.release import Release
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.steps.finalize_step import FinalizeStep

NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
REAL_PACKAGE_ID: str = "575ea8086554107ae2c0fdbb4909d62390c52b77"


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _null_variant() -> ConanVariant:
    """Создаёт ConanVariant с нулевым (только заголовок) package_id."""
    return ConanVariant(
        package_id=NULL_PACKAGE_ID, build_url="", build_date="", options_ref="1"
    )


def _real_variant() -> ConanVariant:
    """Создаёт ConanVariant с ненулевым package_id."""
    return ConanVariant(
        package_id=REAL_PACKAGE_ID,
        build_url="https://art.example.com/pkg",
        build_date="2024-01-01",
        options_ref="1",
    )


def _make_release(profile_builds: list[ProfileBuild]) -> Release:
    """Строит минимальный Release с заданными profile_builds."""
    return Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        git_url="DEP/_git/lib",
        profile_builds=profile_builds,
    )


def _make_component(name: str, release: Release) -> Component:
    """Строит минимальный Component, оборачивающий один Release."""
    return Component(name=name, git_project="DEP", git_repo=name, releases=[release])


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


def test_finalize_step_sets_header_only_true(
    parser_pipeline_context,
) -> None:
    """is_header_only равен True, когда все варианты всех профилей имеют нулевой package_id."""
    pb1 = ProfileBuild(
        profile_name="profile_a", exists=True, variants=[_null_variant()]
    )
    pb2 = ProfileBuild(
        profile_name="profile_b", exists=True, variants=[_null_variant()]
    )
    release = _make_release([pb1, pb2])
    parser_pipeline_context.components = [_make_component("mylib", release)]
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert release.is_header_only is True


def test_finalize_step_sets_header_only_false_on_mixed(
    parser_pipeline_context,
) -> None:
    """is_header_only равен False, когда хотя бы один вариант имеет реальный package_id."""
    pb = ProfileBuild(
        profile_name="profile_a",
        exists=True,
        variants=[_null_variant(), _real_variant()],
    )
    release = _make_release([pb])
    parser_pipeline_context.components = [_make_component("mylib", release)]
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert release.is_header_only is False


def test_finalize_step_sets_header_only_false_on_no_variants(
    parser_pipeline_context,
) -> None:
    """is_header_only равен False, когда у релиза нет вариантов вообще."""
    pb = ProfileBuild(profile_name="profile_a", exists=True, variants=[])
    release = _make_release([pb])
    parser_pipeline_context.components = [_make_component("mylib", release)]
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert release.is_header_only is False


def test_finalize_step_removes_profile_build_with_exists_false(
    parser_pipeline_context,
) -> None:
    """FinalizeStep removes ProfileBuild entries where exists=False.

    Setup: 1 live profile + 1 dead profile → only 1 remains.
    Note: test_finalize_step_removes_non_existing_profiles below covers the same
    behaviour with 2 live profiles + 1 dead, verifying the filter is non-destructive
    to surviving entries — a meaningfully different scenario, so both are kept.
    """
    pb_live = ProfileBuild(profile_name="live", exists=True, variants=[])
    pb_dead = ProfileBuild(profile_name="dead", exists=False, variants=[])
    release = _make_release([pb_live, pb_dead])
    parser_pipeline_context.components = [_make_component("mylib", release)]
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert len(release.profile_builds) == 1
    assert release.profile_builds[0].profile_name == "live"


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


def test_finalize_step_deduplicates_profile_definitions(
    parser_pipeline_context,
) -> None:
    """Записи ProfileDefinition с одинаковым profile_name дедуплицируются (побеждает последняя запись)."""
    pd1 = ProfileDefinition(profile_name="my-profile", docker_image="image:v1")
    pd2 = ProfileDefinition(profile_name="my-profile", docker_image="image:v2")
    parser_pipeline_context.profile_definitions = [pd1, pd2]
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert len(parser_pipeline_context.profile_definitions) == 1
    assert parser_pipeline_context.profile_definitions[0].docker_image == "image:v2"


def test_finalize_step_populates_ctx_result(
    parser_pipeline_context,
) -> None:
    """ctx.result заполняется корректным ParsedResult после execute."""
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.result is not None
    assert isinstance(parser_pipeline_context.result, ParsedResult)
    assert parser_pipeline_context.result.platform_version == "2.0"


def test_finalize_step_raises_parsing_error_on_validation_failure(
    parser_pipeline_context,
    mocker,
) -> None:
    """FinalizeStep wraps a real Pydantic ValidationError in ParsingError.

    ParsedResult constructor raises ValidationError when required fields are
    invalid. FinalizeStep must catch this and re-raise as ParsingError so
    callers never see raw Pydantic internals.
    """
    from pydantic import ValidationError as PydanticValidationError

    def _force_validation_error(ctx):  # noqa: ANN001
        # Pass None for a required str field — triggers a real ValidationError.
        return ParsedResult(
            generated_at=None,  # type: ignore[arg-type]
            platform_version="2.0",
            components=[],
            profile_definitions=[],
        )

    # Patch on the class — Python passes `self` as the first argument,
    # so the side_effect must accept (self, ctx), not just (ctx).
    mocker.patch.object(
        FinalizeStep, "_build_result", side_effect=_force_validation_error
    )
    parser_pipeline_context.components = []
    step = FinalizeStep()

    with pytest.raises(ParsingError):
        step.execute(parser_pipeline_context)


# ---------------------------------------------------------------------------
# Real-data tests added in Part 3
# ---------------------------------------------------------------------------

_SHARED_PROFILE: str = "linux_x64_gcc12"
_IMAGE_V1: str = "registry.example.com/builder:v1"
_IMAGE_V2: str = "registry.example.com/builder:v2"


def test_finalize_step_deduplication_last_occurrence_wins(
    parser_pipeline_context,
) -> None:
    """_deduplicate_profile_definitions retains the last duplicate, not the first.

    Two ProfileDefinition objects with the same profile_name but different
    docker_image values are provided; the last one must survive.
    """
    first = ProfileDefinition(profile_name=_SHARED_PROFILE, docker_image=_IMAGE_V1)
    last = ProfileDefinition(profile_name=_SHARED_PROFILE, docker_image=_IMAGE_V2)
    parser_pipeline_context.profile_definitions = [first, last]
    parser_pipeline_context.components = []

    FinalizeStep().execute(parser_pipeline_context)

    survivors = [
        pd
        for pd in parser_pipeline_context.profile_definitions
        if pd.profile_name == _SHARED_PROFILE
    ]
    assert len(survivors) == 1
    assert survivors[0].docker_image == _IMAGE_V2, "Last occurrence must win"


def test_finalize_step_sets_header_only_for_nlohmann_json(
    parser_pipeline_context,
) -> None:
    """
    A component whose every ProfileBuild has a single variant with NULL_PACKAGE_ID
    must have is_header_only=True after FinalizeStep.
    Mirrors: nlohmann_json 3.9.1/slow with package_id=da39a3ee...
    """
    pb = ProfileBuild(
        profile_name="hw-linux-x86_64-gcc10_2",
        exists=True,
        variants=[
            ConanVariant(
                package_id=NULL_PACKAGE_ID, build_url="", build_date="", options_ref="1"
            )
        ],
    )
    rel = Release(
        version="3.9.1",
        platform="2.0",
        channel="slow",
        git_url="DEP/_git/contrib_nlohmann_json",
        profile_builds=[pb],
    )
    comp = Component(name="nlohmann_json", releases=[rel])
    parser_pipeline_context.components = [comp]

    FinalizeStep().execute(parser_pipeline_context)

    assert parser_pipeline_context.result is not None
    result_comp = parser_pipeline_context.result.components[0]
    assert result_comp.releases[0].is_header_only is True


def test_finalize_step_patchelf_two_versions_not_header_only(
    parser_pipeline_context,
) -> None:
    """
    patchelf has two releases in the tech channel. Neither should be header-only
    (they have real package_ids). FinalizeStep keeps both releases.
    """
    REAL_PKG = "461534fe50686ce31d073dc24f005bd12e08c9fd"

    def _make_rel(version: str) -> Release:
        pb = ProfileBuild(
            profile_name="hw-linux-x86_64-gcc10_2",
            exists=True,
            variants=[
                ConanVariant(
                    package_id=REAL_PKG, build_url="", build_date="", options_ref="1"
                )
            ],
        )
        return Release(
            version=version,
            platform="2.0",
            channel="tech",
            git_url="DEP/_git/contrib_patchelf",
            profile_builds=[pb],
        )

    comp = Component(
        name="patchelf", releases=[_make_rel("0.16.1"), _make_rel("0.18.0")]
    )
    parser_pipeline_context.components = [comp]

    FinalizeStep().execute(parser_pipeline_context)

    result_comp = parser_pipeline_context.result.components[0]
    assert len(result_comp.releases) == 2
    assert all(not r.is_header_only for r in result_comp.releases)


def test_finalize_step_preserves_prg_quant_component(
    parser_pipeline_context,
) -> None:
    """
    libnetfilter_queue (git_project=PRG_Quant) is a non-standard component.
    FinalizeStep must preserve it and sort it alphabetically with others.
    """
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
        git_url="PRG_Quant/_git/contrib_libnetfilter_queue",
        profile_builds=[pb],
    )
    comp_lfq = Component(
        name="libnetfilter_queue", git_project="PRG_Quant", releases=[rel]
    )
    comp_apr = Component(name="apr", releases=[])
    parser_pipeline_context.components = [comp_lfq, comp_apr]

    FinalizeStep().execute(parser_pipeline_context)

    names = [c.name for c in parser_pipeline_context.result.components]
    assert "libnetfilter_queue" in names
    # Sorted: apr < libnetfilter_queue
    assert names.index("apr") < names.index("libnetfilter_queue")


def test_finalize_step_sqlite3_dependencies_preserved(
    parser_pipeline_context,
) -> None:
    """Dependencies set on a release are preserved unchanged after FinalizeStep."""
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
        git_url="DEP/_git/contrib_sqlite3",
        profile_builds=[pb],
    )
    rel.dependencies = ["icu", "tcl"]
    comp = Component(name="sqlite3", releases=[rel])
    parser_pipeline_context.components = [comp]

    FinalizeStep().execute(parser_pipeline_context)

    result_rel = parser_pipeline_context.result.components[0].releases[0]
    assert result_rel.dependencies == ["icu", "tcl"]


def test_finalize_step_removes_non_existing_profiles(
    parser_pipeline_context,
) -> None:
    """FinalizeStep removes only exists=False entries, leaving all exists=True entries intact.

    Setup: 2 live profiles + 1 dead profile → exactly 2 remain.
    This complements test_finalize_step_removes_profile_build_with_exists_false (1+1 setup)
    by verifying the filter preserves multiple surviving entries correctly — a meaningfully
    different scenario that catches off-by-one or first-only removal bugs.
    """
    pb_live1 = ProfileBuild(
        profile_name="hw-linux-x86_64-gcc10_2", exists=True, variants=[]
    )
    pb_live2 = ProfileBuild(
        profile_name="crypto_alpine_gcc_x86_64.jinja", exists=True, variants=[]
    )
    pb_dead = ProfileBuild(
        profile_name="hw-linux-armv7-gcc10_2", exists=False, variants=[]
    )
    rel = Release(
        version="1.0.0",
        platform="2.0",
        channel="slow",
        git_url="DEP/_git/repo",
        profile_builds=[pb_live1, pb_live2, pb_dead],
    )
    comp = Component(name="somelib", releases=[rel])
    parser_pipeline_context.components = [comp]

    FinalizeStep().execute(parser_pipeline_context)

    assert len(rel.profile_builds) == 2
    remaining_names = {pb.profile_name for pb in rel.profile_builds}
    assert "hw-linux-armv7-gcc10_2" not in remaining_names
