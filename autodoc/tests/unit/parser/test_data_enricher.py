"""
Unit-тесты DataEnricher.

Покрывают все три статических метода:
- apply_options      — запись опций в Release
- apply_docker_links — запись docker_image в ProfileDefinition
- apply_conan_results — применение ConanEnrichmentResult к Release и ProfileBuild
"""

import pytest

from autodoc.models.component import (
    ConanInputOptions,
    ConanVariant,
    Component,
    DefaultOptionsSet,
    ProfileBuild,
    ProfileDefinition,
    Release,
)
from autodoc.models.conan_result import (
    ConanEnrichmentResult,
    ProfileConanData,
    ReleaseConanData,
)
from autodoc.parser.enrichment.data_enricher import DataEnricher

# ---------------------------------------------------------------------------
# Фабрики тестовых объектов
# ---------------------------------------------------------------------------


def _make_release(version="1.0.0", channel="stable") -> Release:
    return Release(
        version=version,
        platform="2.0",
        channel=channel,
        git_url="https://tfs.example.com/repo",
    )


def _make_pb(profile_name="linux_x86_64") -> ProfileBuild:
    return ProfileBuild(profile_name=profile_name)


def _make_component(name="my_lib", release: Release | None = None) -> Component:
    r = release or _make_release()
    return Component(name=name, releases=[r])


# ---------------------------------------------------------------------------
# apply_options
# ---------------------------------------------------------------------------


class TestApplyOptions:
    def test_options_written_to_release(self) -> None:
        release = _make_release()
        comp = _make_component(release=release)
        options_map = {("my_lib", "1.0.0", "stable"): {"1": "shared=True"}}

        DataEnricher.apply_options([comp], options_map)

        assert release._build_option_sets_internal == {"1": "shared=True"}

    def test_build_option_sets_populated(self) -> None:
        release = _make_release()
        comp = _make_component(release=release)
        options_map = {
            ("my_lib", "1.0.0", "stable"): {"1": "shared=True", "2": "shared=False"}
        }

        DataEnricher.apply_options([comp], options_map)

        ids = {bs.id for bs in release.build_option_sets}
        assert ids == {"1", "2"}

    def test_missing_key_leaves_release_unchanged(self) -> None:
        release = _make_release()
        comp = _make_component(release=release)
        DataEnricher.apply_options([comp], {})

        assert release._build_option_sets_internal == {}
        assert release.build_option_sets == []

    def test_multiple_components_independent(self) -> None:
        r1 = _make_release()
        r2 = _make_release()
        c1 = _make_component(name="lib_a", release=r1)
        c2 = _make_component(name="lib_b", release=r2)
        options_map = {("lib_a", "1.0.0", "stable"): {"1": "opt=True"}}

        DataEnricher.apply_options([c1, c2], options_map)

        assert r1._build_option_sets_internal == {"1": "opt=True"}
        assert r2._build_option_sets_internal == {}

    def test_empty_options_string_stored_as_empty(self) -> None:
        release = _make_release()
        comp = _make_component(release=release)
        DataEnricher.apply_options([comp], {("my_lib", "1.0.0", "stable"): {"1": ""}})

        assert release._build_option_sets_internal == {"1": ""}
        assert release.build_option_sets[0].options == ""


# ---------------------------------------------------------------------------
# apply_docker_links
# ---------------------------------------------------------------------------
# docker_image lives in ProfileDefinition (removed from ProfileBuild in Task 1).
# apply_docker_links now takes list[Component] + profile_definitions kwarg;
# it resolves the docker URL for each profile_build and writes it into the
# matching ProfileDefinition entry.
# ---------------------------------------------------------------------------


class TestApplyDockerLinks:
    def test_docker_image_filled_for_matching_profile(self) -> None:
        pd = ProfileDefinition(profile_name="linux_x86_64")
        pb = _make_pb("linux_x86_64")
        release = _make_release()
        release.profile_builds = [pb]
        comp = _make_component(release=release)

        DataEnricher.apply_docker_links(
            [comp],
            {"linux_x86_64": "registry.example.com/builder:1.0"},
            [pd],
        )

        assert pd.docker_image == "registry.example.com/builder:1.0"

    def test_unknown_profile_gets_empty_string(self) -> None:
        pd = ProfileDefinition(profile_name="unknown_profile")
        pb = _make_pb("unknown_profile")
        release = _make_release()
        release.profile_builds = [pb]
        comp = _make_component(release=release)

        DataEnricher.apply_docker_links([comp], {"linux_x86_64": "registry/img:1"}, [pd])

        assert pd.docker_image == ""

    def test_multiple_profiles_each_get_own_image(self) -> None:
        pd1 = ProfileDefinition(profile_name="linux_x86_64")
        pd2 = ProfileDefinition(profile_name="linux_aarch64")
        pb1 = _make_pb("linux_x86_64")
        pb2 = _make_pb("linux_aarch64")
        r1 = _make_release()
        r2 = _make_release()
        r1.profile_builds = [pb1]
        r2.profile_builds = [pb2]
        c1 = _make_component(name="lib_a", release=r1)
        c2 = _make_component(name="lib_b", release=r2)

        DataEnricher.apply_docker_links(
            [c1, c2],
            {
                "linux_x86_64": "registry/img:x86",
                "linux_aarch64": "registry/img:arm",
            },
            [pd1, pd2],
        )

        assert pd1.docker_image == "registry/img:x86"
        assert pd2.docker_image == "registry/img:arm"

    def test_empty_links_map_leaves_all_empty(self) -> None:
        pd = ProfileDefinition(profile_name="linux_x86_64")
        pb = _make_pb("linux_x86_64")
        release = _make_release()
        release.profile_builds = [pb]
        comp = _make_component(release=release)

        DataEnricher.apply_docker_links([comp], {}, [pd])

        assert pd.docker_image == ""


# ---------------------------------------------------------------------------
# apply_conan_results
# ---------------------------------------------------------------------------


def _make_conan_result(
    release_data: dict | None = None,
    profile_data: dict | None = None,
) -> ConanEnrichmentResult:
    result = ConanEnrichmentResult()
    if release_data:
        result.release_data = release_data
    if profile_data:
        result.profile_data = profile_data
    return result


class TestApplyConanResults:
    def test_release_fields_populated(self) -> None:
        pb = _make_pb()
        release = _make_release()
        release.profile_builds = [pb]
        comp = _make_component(release=release)

        rel_data = ReleaseConanData(
            base_ref="my_lib/1.0.0@platform-2.0/stable",
            rrev="rev001",
            full_version="1.0.0",
            default_options=[
                DefaultOptionsSet(name="shared", type="bool", default_value=False)
            ],
            total_options=[],
            patches=["fix.patch"],
            dependencies=["zlib"],
            artifactory_url="https://art.example.com/pkg",
        )
        conan_result = _make_conan_result(
            release_data={("my_lib", "1.0.0", "stable"): rel_data}
        )

        DataEnricher.apply_conan_results([comp], conan_result)

        assert release.conan_reference == "my_lib/1.0.0@platform-2.0/stable"
        assert release.artifactory_url == "https://art.example.com/pkg"
        assert release.patches == ["fix.patch"]
        assert release.dependencies == ["zlib"]
        assert isinstance(release.default_options[0], DefaultOptionsSet)

    def test_profile_build_fields_populated(self) -> None:
        pb = _make_pb()
        release = _make_release()
        release.profile_builds = [pb]
        comp = _make_component(release=release)
        # conan_settings теперь хранится в ProfileDefinition, не в ProfileBuild
        pd_def = ProfileDefinition(profile_name=pb.profile_name)

        pb_data = ProfileConanData(
            conan_settings={"os": "Linux", "arch": "x86_64"},
            exists=True,
            variants=[
                ConanVariant(
                    package_id="abc123",
                    build_url="https://art.example.com/build",
                    build_date="2026-01-01T00:00:00+00:00",
                    options_ref="1",  # conan_options убрано из ConanVariant в Task 1
                )
            ],
        )
        conan_result = _make_conan_result(profile_data={id(pb): pb_data})

        DataEnricher.apply_conan_results([comp], conan_result, [pd_def])

        assert pb.exists is True
        # conan_settings теперь проверяем через ProfileDefinition из контекста
        assert pd_def.conan_settings == {"os": "Linux", "arch": "x86_64"}
        assert len(pb.variants) == 1
        assert isinstance(pb.variants[0], ConanVariant)
        assert pb.variants[0].package_id == "abc123"

    def test_missing_release_key_leaves_release_unchanged(self) -> None:
        release = _make_release()
        comp = _make_component(release=release)
        conan_result = _make_conan_result()

        DataEnricher.apply_conan_results([comp], conan_result)

        assert release.conan_reference == ""
        assert release.patches == []

    def test_missing_profile_key_leaves_pb_unchanged(self) -> None:
        pb = _make_pb()
        release = _make_release()
        release.profile_builds = [pb]
        comp = _make_component(release=release)

        DataEnricher.apply_conan_results([comp], _make_conan_result())

        assert pb.exists is False
        assert pb.variants == []

    def test_multiple_components_enriched_independently(self) -> None:
        pb1 = _make_pb("linux_x86_64")
        pb2 = _make_pb("linux_aarch64")
        r1 = _make_release(version="1.0.0")
        r2 = _make_release(version="2.0.0")
        r1.profile_builds = [pb1]
        r2.profile_builds = [pb2]
        c1 = _make_component(name="lib_a", release=r1)
        c2 = _make_component(name="lib_b", release=r2)

        pd1 = ProfileConanData(conan_settings={}, exists=True, variants=[])
        pd2 = ProfileConanData(conan_settings={}, exists=False, variants=[])
        conan_result = _make_conan_result(profile_data={id(pb1): pd1, id(pb2): pd2})

        DataEnricher.apply_conan_results([c1, c2], conan_result)

        assert pb1.exists is True
        assert pb2.exists is False

    def test_empty_components_list_no_error(self) -> None:
        DataEnricher.apply_conan_results([], _make_conan_result())
