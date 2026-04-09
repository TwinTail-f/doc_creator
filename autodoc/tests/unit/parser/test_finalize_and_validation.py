"""
Unit-тесты FinalizeStep и ArtifactoryValidationStep.

FinalizeStep:
  - _compute_header_only_flags
  - _filter_empty_profiles
  - _build_result / execute (полный путь через PipelineContext)

ArtifactoryValidationStep:
  - _collect_variants
  - _remove_dead_variants
  - execute (с мок-клиентом Artifactory)
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from autodoc.config.schemas import ParserConfigSchema
from autodoc.models.component import (
    ConanVariant,
    Component,
    ProfileBuild,
    Release,
)
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.steps.base import PipelineContext
from autodoc.parser.steps.finalize_step import FinalizeStep
from autodoc.parser.steps.validation_step import ArtifactoryValidationStep

_MINIMAL_CONFIG = ParserConfigSchema(
    platform_version="2.0",
    platform_branch_name="develop",
    tfs_username="robot",
    tfs_token="secret",
    tfs_dep_components_url="https://tfs.example.com/DEP",
    manifests_remotes_path="/remotes/manifests",
    artifactory_token="art-token",
)


# ---------------------------------------------------------------------------
# Фабрики
# ---------------------------------------------------------------------------


def _make_release(version="1.0.0", channel="stable") -> Release:
    return Release(
        version=version, platform="2.0", channel=channel, git_url="https://tfs.example.com"
    )


def _make_pb(profile_name="p1", exists=True) -> ProfileBuild:
    return ProfileBuild(profile_name=profile_name, exists=exists)


def _make_variant(url="https://art.example.com/build/pkg") -> ConanVariant:
    return ConanVariant(package_id="abc", build_url=url, build_date="")


def _make_component(name="lib", pbs=None) -> Component:
    r = _make_release()
    r.profile_builds = pbs or []
    return Component(name=name, releases=[r])


def _make_ctx(components=None, tmp_path=None) -> PipelineContext:
    ctx = PipelineContext(
        config=_MINIMAL_CONFIG,
        tmp_dir=tmp_path or Path("/tmp/test_finalize"),
    )
    ctx.components = components or []
    return ctx


# ---------------------------------------------------------------------------
# FinalizeStep._compute_header_only_flags
# ---------------------------------------------------------------------------


class TestComputeHeaderOnlyFlags:
    def test_no_profile_builds_is_not_header_only(self) -> None:
        r = _make_release()
        r.profile_builds = []
        comp = Component(name="lib", releases=[r])
        FinalizeStep._compute_header_only_flags([comp])
        assert r.is_header_only is False

    def test_all_empty_settings_and_empty_options_is_header_only(self) -> None:
        variant = ConanVariant(package_id="x", build_url="", build_date="", conan_options={})
        pb = ProfileBuild(profile_name="p", conan_settings={}, variants=[variant])
        r = _make_release()
        r.profile_builds = [pb]
        comp = Component(name="lib", releases=[r])

        FinalizeStep._compute_header_only_flags([comp])

        assert r.is_header_only is True

    def test_non_empty_settings_not_header_only(self) -> None:
        variant = ConanVariant(package_id="x", build_url="", build_date="", conan_options={})
        pb = ProfileBuild(
            profile_name="p",
            conan_settings={"os": "Linux"},
            variants=[variant],
        )
        r = _make_release()
        r.profile_builds = [pb]
        comp = Component(name="lib", releases=[r])

        FinalizeStep._compute_header_only_flags([comp])

        assert r.is_header_only is False

    def test_non_empty_conan_options_not_header_only(self) -> None:
        variant = ConanVariant(
            package_id="x", build_url="", build_date="", conan_options={"shared": "True"}
        )
        pb = ProfileBuild(profile_name="p", conan_settings={}, variants=[variant])
        r = _make_release()
        r.profile_builds = [pb]
        comp = Component(name="lib", releases=[r])

        FinalizeStep._compute_header_only_flags([comp])

        assert r.is_header_only is False


# ---------------------------------------------------------------------------
# FinalizeStep._filter_empty_profiles
# ---------------------------------------------------------------------------


class TestFilterEmptyProfiles:
    def test_removes_profiles_with_exists_false(self) -> None:
        pb_ok = _make_pb(exists=True)
        pb_dead = _make_pb("p2", exists=False)
        r = _make_release()
        r.profile_builds = [pb_ok, pb_dead]
        comp = Component(name="lib", releases=[r])

        removed = FinalizeStep._filter_empty_profiles([comp])

        assert removed == 1
        assert pb_ok in r.profile_builds
        assert pb_dead not in r.profile_builds

    def test_no_dead_profiles_returns_zero(self) -> None:
        pb = _make_pb(exists=True)
        r = _make_release()
        r.profile_builds = [pb]
        comp = Component(name="lib", releases=[r])

        assert FinalizeStep._filter_empty_profiles([comp]) == 0

    def test_all_dead_profiles_cleared(self) -> None:
        r = _make_release()
        r.profile_builds = [_make_pb("p1", False), _make_pb("p2", False)]
        comp = Component(name="lib", releases=[r])

        removed = FinalizeStep._filter_empty_profiles([comp])

        assert removed == 2
        assert r.profile_builds == []


# ---------------------------------------------------------------------------
# FinalizeStep.execute — полный путь
# ---------------------------------------------------------------------------


class TestFinalizeStepExecute:
    def test_result_set_in_context(self, tmp_path: Path) -> None:
        ctx = _make_ctx(tmp_path=tmp_path)
        FinalizeStep().execute(ctx)
        assert isinstance(ctx.result, ParsedResult)

    def test_components_sorted_by_name(self, tmp_path: Path) -> None:
        comps = [
            _make_component("zz_lib"),
            _make_component("aa_lib"),
            _make_component("mm_lib"),
        ]
        ctx = _make_ctx(components=comps, tmp_path=tmp_path)
        FinalizeStep().execute(ctx)
        names = [c.name for c in ctx.components]
        assert names == sorted(names, key=str.lower)

    def test_platform_version_in_result(self, tmp_path: Path) -> None:
        ctx = _make_ctx(tmp_path=tmp_path)
        FinalizeStep().execute(ctx)
        assert ctx.result.platform_version == "2.0"


# ---------------------------------------------------------------------------
# ArtifactoryValidationStep._collect_variants
# ---------------------------------------------------------------------------


class TestCollectVariants:
    def test_collects_variants_with_build_url(self) -> None:
        variant = _make_variant("https://art.example.com/ui/repos/tree/General/pkg/1")
        pb = _make_pb()
        pb.variants = [variant]
        comp = _make_component(pbs=[pb])

        items = ArtifactoryValidationStep._collect_variants([comp])

        assert len(items) == 1
        _, v, url = items[0]
        assert v is variant
        # URL должен быть переведён в API-формат
        assert "/artifactory/" in url

    def test_variants_without_url_skipped(self) -> None:
        variant = ConanVariant(package_id="x", build_url="", build_date="")
        pb = _make_pb()
        pb.variants = [variant]
        comp = _make_component(pbs=[pb])

        items = ArtifactoryValidationStep._collect_variants([comp])
        assert items == []

    def test_ui_url_converted_to_api_url(self) -> None:
        ui_url = "https://art.example.com/ui/repos/tree/General/pkg/1"
        variant = _make_variant(ui_url)
        pb = _make_pb()
        pb.variants = [variant]
        comp = _make_component(pbs=[pb])

        _, _, api_url = ArtifactoryValidationStep._collect_variants([comp])[0]
        assert api_url == "https://art.example.com/artifactory/pkg/1"

    def test_multiple_variants_all_collected(self) -> None:
        v1 = _make_variant("https://art.example.com/ui/repos/tree/General/a")
        v2 = _make_variant("https://art.example.com/ui/repos/tree/General/b")
        pb = _make_pb()
        pb.variants = [v1, v2]
        comp = _make_component(pbs=[pb])

        items = ArtifactoryValidationStep._collect_variants([comp])
        assert len(items) == 2


# ---------------------------------------------------------------------------
# ArtifactoryValidationStep._remove_dead_variants
# ---------------------------------------------------------------------------


class TestRemoveDeadVariants:
    def test_removes_variant_from_profile_build(self) -> None:
        variant = _make_variant()
        pb = _make_pb()
        pb.variants = [variant]

        ArtifactoryValidationStep._remove_dead_variants([(pb, variant)])

        assert variant not in pb.variants

    def test_only_dead_variant_removed(self) -> None:
        v_alive = _make_variant("https://art.example.com/alive")
        v_dead = _make_variant("https://art.example.com/dead")
        pb = _make_pb()
        pb.variants = [v_alive, v_dead]

        ArtifactoryValidationStep._remove_dead_variants([(pb, v_dead)])

        assert v_alive in pb.variants
        assert v_dead not in pb.variants

    def test_empty_dead_list_no_change(self) -> None:
        variant = _make_variant()
        pb = _make_pb()
        pb.variants = [variant]

        ArtifactoryValidationStep._remove_dead_variants([])

        assert variant in pb.variants


# ---------------------------------------------------------------------------
# ArtifactoryValidationStep.execute — интеграция с мок-клиентом
# ---------------------------------------------------------------------------


class TestArtifactoryValidationStepExecute:
    def _make_ctx_with_variant(self, url="https://art.example.com/ui/repos/tree/General/pkg"):
        variant = _make_variant(url)
        pb = _make_pb()
        pb.variants = [variant]
        comp = _make_component(pbs=[pb])
        ctx = PipelineContext(config=_MINIMAL_CONFIG, tmp_dir=Path("/tmp"))
        ctx.components = [comp]
        ctx.artifactory_client = MagicMock()
        return ctx, pb, variant

    def test_404_variant_removed(self) -> None:
        ctx, pb, variant = self._make_ctx_with_variant()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        ctx.artifactory_client.head.return_value = mock_resp

        ArtifactoryValidationStep().execute(ctx)

        assert variant not in pb.variants

    def test_200_variant_kept(self) -> None:
        ctx, pb, variant = self._make_ctx_with_variant()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        ctx.artifactory_client.head.return_value = mock_resp

        ArtifactoryValidationStep().execute(ctx)

        assert variant in pb.variants

    def test_network_error_variant_kept(self) -> None:
        ctx, pb, variant = self._make_ctx_with_variant()
        ctx.artifactory_client.head.side_effect = requests.RequestException("timeout")

        ArtifactoryValidationStep().execute(ctx)

        assert variant in pb.variants

    def test_no_variants_no_head_calls(self) -> None:
        ctx = PipelineContext(config=_MINIMAL_CONFIG, tmp_dir=Path("/tmp"))
        ctx.components = [_make_component(pbs=[])]
        ctx.artifactory_client = MagicMock()

        ArtifactoryValidationStep().execute(ctx)

        ctx.artifactory_client.head.assert_not_called()
