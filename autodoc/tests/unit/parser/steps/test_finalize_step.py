"""Unit tests for autodoc/parser/steps/finalize_step.py."""

import pytest

from autodoc.exceptions import ParsingError
from autodoc.models.component import (
    Component,
    ConanVariant,
    ProfileBuild,
    ProfileDefinition,
    Release,
)
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.steps.finalize_step import FinalizeStep

NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
REAL_PACKAGE_ID: str = "575ea8086554107ae2c0fdbb4909d62390c52b77"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _null_variant() -> ConanVariant:
    """Create a ConanVariant with the null (header-only) package_id."""
    return ConanVariant(
        package_id=NULL_PACKAGE_ID, build_url="", build_date="", options_ref="1"
    )


def _real_variant() -> ConanVariant:
    """Create a ConanVariant with a non-null package_id."""
    return ConanVariant(
        package_id=REAL_PACKAGE_ID,
        build_url="https://art.example.com/pkg",
        build_date="2024-01-01",
        options_ref="1",
    )


def _make_release(profile_builds: list[ProfileBuild]) -> Release:
    """Build a minimal Release with the given profile_builds."""
    return Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        git_url="DEP/_git/lib",
        profile_builds=profile_builds,
    )


def _make_component(name: str, release: Release) -> Component:
    """Build a minimal Component wrapping a single Release."""
    return Component(name=name, git_project="DEP", git_repo=name, releases=[release])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_finalize_step_sets_header_only_true(
    parser_pipeline_context,
) -> None:
    """is_header_only is True when all variants across all profiles have the null package_id."""
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
    """is_header_only is False when at least one variant has a real package_id."""
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
    """is_header_only is False when a release has no variants at all."""
    pb = ProfileBuild(profile_name="profile_a", exists=True, variants=[])
    release = _make_release([pb])
    parser_pipeline_context.components = [_make_component("mylib", release)]
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert release.is_header_only is False


def test_finalize_step_removes_profile_build_with_exists_false(
    parser_pipeline_context,
) -> None:
    """ProfileBuild entries with exists=False are removed during finalization."""
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
    """Components are sorted alphabetically by name (case-insensitive) after finalization."""
    zlib_component = _make_component("Zlib", _make_release([]))
    apache_component = _make_component("apache", _make_release([]))
    parser_pipeline_context.components = [zlib_component, apache_component]
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.components[0].name == "apache"


def test_finalize_step_deduplicates_profile_definitions(
    parser_pipeline_context,
) -> None:
    """ProfileDefinition entries with the same profile_name are deduplicated (last-write-wins)."""
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
    """ctx.result is populated with a valid ParsedResult after execute."""
    step = FinalizeStep()
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.result is not None
    assert isinstance(parser_pipeline_context.result, ParsedResult)
    assert parser_pipeline_context.result.platform_version == "2.0"


def test_finalize_step_raises_parsing_error_on_validation_failure(
    mocker,
    parser_pipeline_context,
) -> None:
    """_build_result wraps a Pydantic ValidationError into a ParsingError."""
    from pydantic import BaseModel, ValidationError

    class _Dummy(BaseModel):
        x: int

    # Create a real pydantic.ValidationError instance to use as side_effect
    try:
        _Dummy(x="not-an-int")  # type: ignore[arg-type]
    except ValidationError as exc:
        real_ve = exc

    mocker.patch(
        "autodoc.parser.steps.finalize_step.ParsedResult",
        side_effect=real_ve,
    )
    step = FinalizeStep()
    with pytest.raises(ParsingError):
        step.execute(parser_pipeline_context)
