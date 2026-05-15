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
    """is_header_only равен True на компоненте, когда все варианты всех профилей имеют нулевой package_id."""
    pb1 = ProfileBuild(
        profile_name="profile_a", exists=True, variants=[_null_variant()]
    )
    pb2 = ProfileBuild(
        profile_name="profile_b", exists=True, variants=[_null_variant()]
    )
    release = _make_release([pb1, pb2])
    comp = _make_component("mylib", release)
    parser_pipeline_context.components = [comp]
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert comp.is_header_only is True


def test_finalize_step_sets_header_only_false_on_mixed(
    parser_pipeline_context,
) -> None:
    """is_header_only равен False на компоненте, когда хотя бы один вариант имеет реальный package_id."""
    pb = ProfileBuild(
        profile_name="profile_a",
        exists=True,
        variants=[_null_variant(), _real_variant()],
    )
    release = _make_release([pb])
    comp = _make_component("mylib", release)
    parser_pipeline_context.components = [comp]
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert comp.is_header_only is False


def test_finalize_step_sets_header_only_false_on_no_variants(
    parser_pipeline_context,
) -> None:
    """is_header_only равен False на компоненте, когда нет вариантов вообще."""
    pb = ProfileBuild(profile_name="profile_a", exists=True, variants=[])
    release = _make_release([pb])
    comp = _make_component("mylib", release)
    parser_pipeline_context.components = [comp]
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert comp.is_header_only is False


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
        profile_builds=[pb],
    )
    comp = Component(name="nlohmann_json", releases=[rel])
    parser_pipeline_context.components = [comp]

    FinalizeStep().execute(parser_pipeline_context)

    assert parser_pipeline_context.result is not None
    result_comp = parser_pipeline_context.result.components[0]
    assert result_comp.is_header_only is True


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
            profile_builds=[pb],
        )

    comp = Component(
        name="patchelf", releases=[_make_rel("0.16.1"), _make_rel("0.18.0")]
    )
    parser_pipeline_context.components = [comp]

    FinalizeStep().execute(parser_pipeline_context)

    result_comp = parser_pipeline_context.result.components[0]
    assert len(result_comp.releases) == 2
    assert not result_comp.is_header_only


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
        profile_builds=[pb_live1, pb_live2, pb_dead],
    )
    comp = Component(name="somelib", releases=[rel])
    parser_pipeline_context.components = [comp]

    FinalizeStep().execute(parser_pipeline_context)

    assert len(rel.profile_builds) == 2
    remaining_names = {pb.profile_name for pb in rel.profile_builds}
    assert "hw-linux-armv7-gcc10_2" not in remaining_names


# ===========================================================================
# Part-1 additions: BL-FS-01 … BL-FS-07
# ===========================================================================
#
# The factories and NULL_PACKAGE_ID sentinel are imported from the shared
# parser conftest so the same values are reused consistently across the suite.

from tests.unit.parser.conftest import (  # noqa: E402
    make_conan_variant,
    NULL_PACKAGE_ID as _NULL_PACKAGE_ID,
)


def _make_comp_with_variant(name: str, package_id: str) -> Component:
    """Build a single-release, single-profile component with one ConanVariant.

    Used by BL-FS-02/03 to quickly construct components whose
    ``is_header_only`` flag depends solely on the supplied ``package_id``.

    Args:
        name: ``Component.name`` and display identifier.
        package_id: The ``ConanVariant.package_id`` to attach to the sole
            ``ProfileBuild`` of the component's release.

    Returns:
        A fully-constructed ``Component`` ready for ``FinalizeStep.execute()``.
    """
    pb = ProfileBuild(
        profile_name="hw-linux-x86_64",
        exists=True,
        variants=[
            ConanVariant(
                package_id=package_id, build_url="", build_date="", options_ref="1"
            )
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


# ---------------------------------------------------------------------------
# BL-FS-01
# ---------------------------------------------------------------------------


def test_header_only_requires_all_profiles_to_have_null_package_id(
    parser_pipeline_context,
) -> None:
    """Verify that a single non-null variant makes the whole component non-header-only.

    Business Rule (BL-FS-01): If at least ONE variant across ALL profiles of
    the component has a non-null ``package_id``, then
    ``component.is_header_only`` must be ``False``.

    Preconditions:
        - Component with two profiles:
          * First profile — variants with ``NULL_PACKAGE_ID``.
          * Second profile — variants with a regular (non-null) ``package_id``.

    Steps:
        1. Construct the component with the two contrasting profiles.
        2. Assign it to ``ctx.components`` and call ``FinalizeStep().execute(ctx)``.

    Expected Result:
        - ``component.is_header_only is False`` (at least one non-null variant
          disqualifies the whole component).
    """
    null_id = _NULL_PACKAGE_ID
    pb1 = ProfileBuild(
        profile_name="p1",
        exists=True,
        variants=[
            ConanVariant(package_id=null_id, build_url="", build_date="", options_ref="")
        ],
    )
    pb2 = ProfileBuild(
        profile_name="p2",
        exists=True,
        variants=[
            ConanVariant(
                package_id="regular_id", build_url="", build_date="", options_ref=""
            )
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


# ---------------------------------------------------------------------------
# BL-FS-02
# ---------------------------------------------------------------------------


def test_header_only_evaluated_per_component_independently(
    parser_pipeline_context,
) -> None:
    """Verify that ``is_header_only`` is computed independently for each component.

    Business Rule (BL-FS-02): The flag is evaluated per-component, not
    globally.  Two components in the same run can have different values.

    Preconditions:
        - Component A: all variants have ``NULL_PACKAGE_ID`` → ``is_header_only=True``.
        - Component B: variants have a regular ``package_id`` → ``is_header_only=False``.

    Steps:
        1. Build comp_a and comp_b via ``_make_comp_with_variant``.
        2. Assign both to ``ctx.components``.
        3. Execute ``FinalizeStep``.

    Expected Result:
        - ``comp_a.is_header_only is True``.
        - ``comp_b.is_header_only is False``.
    """
    comp_a = _make_comp_with_variant("compA", package_id=_NULL_PACKAGE_ID)
    comp_b = _make_comp_with_variant("compB", package_id="regular_id")

    ctx = parser_pipeline_context
    ctx.components = [comp_a, comp_b]
    FinalizeStep().execute(ctx)

    assert comp_a.is_header_only is True
    assert comp_b.is_header_only is False


# ---------------------------------------------------------------------------
# BL-FS-03
# ---------------------------------------------------------------------------


def test_header_only_null_package_id_exact_sha1_value(
    parser_pipeline_context,
) -> None:
    """Verify that the header-only check uses the exact NULL_PACKAGE_ID SHA-1 value.

    Business Rule (BL-FS-03): Only the exact SHA-1 of the empty string
    (``da39a3ee5e6b4b0d3255bfef95601890afd80709``) qualifies a variant as
    null.  A string that differs by even one character must NOT be treated as
    null, resulting in ``is_header_only=False``.

    Preconditions:
        - Component whose sole variant has ``package_id`` that differs from
          ``NULL_PACKAGE_ID`` only in the last hex character (``9`` → ``0``).

    Expected Result:
        - ``comp.is_header_only is False``.
    """
    almost_null = "da39a3ee5e6b4b0d3255bfef95601890afd80700"  # Last char changed.
    comp = _make_comp_with_variant("mylib", package_id=almost_null)

    ctx = parser_pipeline_context
    ctx.components = [comp]
    FinalizeStep().execute(ctx)

    assert comp.is_header_only is False


# ---------------------------------------------------------------------------
# BL-FS-04
# ---------------------------------------------------------------------------


def test_header_only_with_no_profile_builds_is_false(
    parser_pipeline_context,
) -> None:
    """Verify that a release with no profiles yields ``is_header_only=False``.

    Business Rule (BL-FS-04): A component whose release contains an empty
    ``profile_builds`` list has no variants to check.  The absence of all-null
    evidence means the flag defaults to ``False``.

    Steps:
        1. Build a ``Release`` with ``profile_builds=[]``.
        2. Wrap it in a ``Component`` and assign to ``ctx.components``.
        3. Execute ``FinalizeStep``.

    Expected Result:
        - ``comp.is_header_only is False``.
    """
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


# ---------------------------------------------------------------------------
# BL-FS-05
# ---------------------------------------------------------------------------


def test_header_only_with_empty_variants_per_profile_is_false(
    parser_pipeline_context,
) -> None:
    """Verify that a profile with no variants yields ``is_header_only=False``.

    Business Rule (BL-FS-05): A ``ProfileBuild`` with ``variants=[]`` contributes
    no package_id evidence.  When ALL profiles have empty variants the aggregate
    variant list is empty, so the component is NOT header-only.

    Steps:
        1. Build a ``ProfileBuild`` with ``exists=True`` and ``variants=[]``.
        2. Wrap it into a component and run ``FinalizeStep``.

    Expected Result:
        - ``comp.is_header_only is False``.
    """
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


# ---------------------------------------------------------------------------
# BL-FS-06
# ---------------------------------------------------------------------------


def test_filter_empty_profiles_removes_only_false_profiles(
    parser_pipeline_context,
) -> None:
    """Verify that FinalizeStep retains only profiles with ``exists=True``.

    Business Rule (BL-FS-06): After finalization, ``release.profile_builds``
    must contain ONLY ``ProfileBuild`` entries whose ``exists`` flag is
    ``True``.  Entries with ``exists=False`` are removed.

    Preconditions:
        - Three profiles: ``"p1"`` (exists=True), ``"p2"`` (exists=True),
          and ``"p3"`` (exists=False).

    Steps:
        1. Build a release with all three profiles.
        2. Assign the component to ``ctx.components``.
        3. Execute ``FinalizeStep``.

    Expected Result:
        - Exactly two profiles remain: ``{"p1", "p2"}``.
        - ``"p3"`` is absent from ``release.profile_builds``.
    """
    pb_exists = ProfileBuild(
        profile_name="p1", exists=True, variants=[make_conan_variant()]
    )
    pb_exists2 = ProfileBuild(
        profile_name="p2", exists=True, variants=[make_conan_variant()]
    )
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


# ---------------------------------------------------------------------------
# BL-FS-07
# ---------------------------------------------------------------------------


def test_filter_empty_profiles_count_returned() -> None:
    """Verify that ``_filter_empty_profiles`` returns the exact count of removed profiles.

    Business Rule (BL-FS-07): The internal helper
    ``FinalizeStep._filter_empty_profiles`` must return an integer equal to the
    number of ``ProfileBuild`` entries removed (``exists=False`` count).  This
    count is used for diagnostic logging.

    Note: Testing an internal method is intentional — the counting logic is
    used for pipeline diagnostics and must be independently verified.

    Steps:
        1. Build a release with 1 live profile and 2 dead profiles.
        2. Call ``step._filter_empty_profiles([comp])`` directly.

    Expected Result:
        - Return value is ``2``.
        - ``len(release.profile_builds) == 1`` (only the live profile remains).
    """
    pb_ok = ProfileBuild(
        profile_name="p1", exists=True, variants=[make_conan_variant()]
    )
    pb_gone1 = ProfileBuild(profile_name="p2", exists=False, variants=[])
    pb_gone2 = ProfileBuild(profile_name="p3", exists=False, variants=[])

    release = Release(
        version="1.0",
        platform="2.2",
        channel="fast",
        conan_reference="",
        artifactory_url="",
        profile_builds=[pb_ok, pb_gone1, pb_gone2],
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

    step = FinalizeStep()
    removed_count = step._filter_empty_profiles([comp])

    assert removed_count == 2
    assert len(release.profile_builds) == 1


# ===========================================================================
# BL-FS-08 … BL-FS-14  (Part 2 of the test plan)
# ---------------------------------------------------------------------------
# Helper factories scoped to this block to keep tests self-contained
# ---------------------------------------------------------------------------

def _bl_make_variant() -> ConanVariant:
    """Return a minimal ConanVariant with a non-null package_id."""
    return ConanVariant(
        package_id="575ea8086554107ae2c0fdbb4909d62390c52b77",
        build_url="",
        build_date="",
        options_ref="1",
    )


def _bl_make_release(profile_builds: list | None = None) -> Release:
    """Return a minimal Release.  profile_builds defaults to an empty list."""
    return Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        profile_builds=profile_builds if profile_builds is not None else [],
    )


def _bl_make_component(name: str = "lib", releases: list | None = None) -> Component:
    """Return a minimal Component with the given releases list."""
    return Component(
        name=name,
        git_project="DEP",
        git_repo=name,
        releases=releases if releases is not None else [],
    )


# ---------------------------------------------------------------------------
# BL-FS-08
# ---------------------------------------------------------------------------


def test_filter_empty_profiles_removes_only_false_exists() -> None:
    """Verify that _filter_empty_profiles removes only ProfileBuilds with exists=False.

    Business Rule: _filter_empty_profiles must remove every ProfileBuild whose
    ``exists`` flag is ``False`` and keep all entries with ``exists=True``.
    It must not perform any extraneous saves or removals.

    Preconditions:
        - Release has two ProfileBuilds: ``pb_ok`` (exists=True) and ``pb_bad``
          (exists=False).

    Steps:
        1. Build a release with both profiles.
        2. Wrap it in a Component and call ``step._filter_empty_profiles([comp])``.

    Expected Result:
        - Return value is ``1`` (exactly one entry removed).
        - ``release.profile_builds`` contains only ``pb_ok``.
    """
    pb_ok = ProfileBuild(
        profile_name="hw-linux-x86_64", exists=True, variants=[_bl_make_variant()]
    )
    pb_bad = ProfileBuild(profile_name="hw-linux-armv8", exists=False)
    release = _bl_make_release()
    release.profile_builds = [pb_ok, pb_bad]
    comp = _bl_make_component(releases=[release])

    step = FinalizeStep()
    removed = step._filter_empty_profiles([comp])

    assert removed == 1
    assert len(release.profile_builds) == 1
    assert release.profile_builds[0].profile_name == "hw-linux-x86_64"


# ---------------------------------------------------------------------------
# BL-FS-09
# ---------------------------------------------------------------------------


def test_filter_empty_profiles_count_matches_actual_removed() -> None:
    """Verify that the return value of _filter_empty_profiles is the exact removal count.

    Business Rule: The integer returned by ``_filter_empty_profiles`` equals
    the number of ``ProfileBuild`` entries whose ``exists`` flag was ``False``.
    This value is emitted to the pipeline log for observability.

    Preconditions:
        - Release has 5 profiles with exists=False and 1 with exists=True.

    Steps:
        1. Build a release with 6 profiles (5 dead, 1 alive).
        2. Call ``step._filter_empty_profiles([comp])`` directly.

    Expected Result:
        - Return value is exactly ``5``.
    """
    pbs_false = [
        ProfileBuild(profile_name=f"profile-{i}", exists=False) for i in range(5)
    ]
    pb_true = ProfileBuild(
        profile_name="hw-linux-x86_64", exists=True, variants=[_bl_make_variant()]
    )

    release = _bl_make_release()
    release.profile_builds = pbs_false + [pb_true]
    comp = _bl_make_component(releases=[release])

    step = FinalizeStep()
    removed = step._filter_empty_profiles([comp])

    assert removed == 5


# ---------------------------------------------------------------------------
# BL-FS-10
# ---------------------------------------------------------------------------


def test_filter_empty_profiles_release_with_all_false_stays_in_component() -> None:
    """Verify that a Release remains in the Component even when all its ProfileBuilds are removed.

    Business Rule: ``_filter_empty_profiles`` removes ProfileBuild entries, not
    Release objects.  A Release whose ``profile_builds`` list becomes empty after
    filtering is intentionally kept in ``comp.releases`` — removing empty releases
    is a separate concern handled elsewhere in the pipeline.

    Preconditions:
        - Component has one Release with a single ProfileBuild (exists=False).

    Steps:
        1. Call ``step._filter_empty_profiles([comp])`` directly.

    Expected Result:
        - ``len(comp.releases) == 1``  (Release object is NOT removed).
        - ``comp.releases[0].profile_builds == []``  (all builds were stripped).
    """
    pb_bad = ProfileBuild(profile_name="hw-linux-x86_64", exists=False)
    release = _bl_make_release()
    release.profile_builds = [pb_bad]
    comp = _bl_make_component(releases=[release])

    step = FinalizeStep()
    step._filter_empty_profiles([comp])

    assert len(comp.releases) == 1
    assert comp.releases[0].profile_builds == []


# ---------------------------------------------------------------------------
# BL-FS-11
# ---------------------------------------------------------------------------


def test_filter_empty_profiles_accumulates_count_across_components() -> None:
    """Verify that _filter_empty_profiles sums removed profiles across all components.

    Business Rule: The returned count is the aggregate of all removed ProfileBuilds
    from every Component and every Release in the input list — not per-component.
    This enables a single summary log line for the whole pipeline run.

    Preconditions:
        - Three components, each with one Release containing one exists=True profile
          and one exists=False profile.

    Steps:
        1. Build three components using a factory helper.
        2. Call ``step._filter_empty_profiles(comps)`` once.

    Expected Result:
        - Return value is ``3`` (one removal per component).
    """

    def _make_comp_with_mixed_pbs(name: str) -> Component:
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


# ---------------------------------------------------------------------------
# BL-FS-12
# ---------------------------------------------------------------------------


def test_dedup_profile_definitions_last_write_wins() -> None:
    """Verify that when two ProfileDefinitions share a name, the last one in the list wins.

    Business Rule: ``_deduplicate_profile_definitions`` retains the LAST occurrence
    of each ``profile_name``.  Pipeline steps are ordered so that later steps
    (e.g. Conan) produce more complete data than earlier steps (e.g. Docker);
    the last-write-wins policy ensures the richer record survives.

    Preconditions:
        - Two ProfileDefinition objects with identical ``profile_name``; the later
          one has a different ``docker_image`` and non-empty ``conan_settings``.

    Steps:
        1. Pass ``[pd_early, pd_late]`` to ``_deduplicate_profile_definitions``.

    Expected Result:
        - Result list has length 1.
        - The surviving entry's ``docker_image`` matches ``pd_late``.
        - ``conan_settings`` matches ``pd_late``.
    """
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


# ---------------------------------------------------------------------------
# BL-FS-13
# ---------------------------------------------------------------------------


def test_dedup_profile_definitions_unique_names_all_preserved() -> None:
    """Verify that ProfileDefinitions with unique names are all preserved after deduplication.

    Business Rule: ``_deduplicate_profile_definitions`` must not discard any entry
    whose ``profile_name`` is unique across the input list.  Only genuine
    duplicates (same name) are collapsed.

    Preconditions:
        - Three ProfileDefinition objects each with a different ``profile_name``.

    Steps:
        1. Pass the list to ``_deduplicate_profile_definitions``.

    Expected Result:
        - Result length is 3.
        - All three names are present in the result.
    """
    pds = [
        ProfileDefinition(
            profile_name=f"hw-linux-{arch}", docker_image="", conan_settings={}
        )
        for arch in ["x86_64", "armv8", "rpi4"]
    ]

    step = FinalizeStep()
    result = step._deduplicate_profile_definitions(pds)

    assert len(result) == 3
    names = {pd.profile_name for pd in result}
    assert names == {"hw-linux-x86_64", "hw-linux-armv8", "hw-linux-rpi4"}


# ---------------------------------------------------------------------------
# BL-FS-14
# ---------------------------------------------------------------------------


def test_dedup_profile_definitions_empty_input_returns_empty() -> None:
    """Verify that _deduplicate_profile_definitions returns [] for an empty input.

    Business Rule (edge case): Passing an empty list must not raise an exception
    and must return an empty list.  This handles the first-run scenario where no
    profile definitions have been collected yet.

    Preconditions:
        - Input list is empty: ``[]``.

    Steps:
        1. Call ``step._deduplicate_profile_definitions([])``.

    Expected Result:
        - Return value is ``[]``.
    """
    step = FinalizeStep()
    result = step._deduplicate_profile_definitions([])
    assert result == []
