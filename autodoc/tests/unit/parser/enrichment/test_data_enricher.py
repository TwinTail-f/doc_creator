"""
Unit tests for autodoc/parser/enrichment/data_enricher.py.

Covers DataEnricher.apply_options(), apply_docker_links(), and
apply_conan_results(). Uses fixtures from unit/parser/conftest.py where
available; component-level fixtures are built inline for clarity.
"""

import pytest

from autodoc.models.component import (
    ConanInputOptions,
    ConanVariant,
    Component,
    ProfileBuild,
    ProfileDefinition,
    Release,
    TotalOptionsSet,
)
from autodoc.models.conan_result import (
    ConanEnrichmentResult,
    ProfileConanData,
    ReleaseConanData,
)
from autodoc.parser.enrichment.data_enricher import DataEnricher

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _release(
    name: str = "openssl",
    version: str = "1.0.0",
    channel: str = "tech",
    profile: str = "hw-linux-x86_64-gcc10_2",
) -> tuple[Component, Release, ProfileBuild]:
    """Return a (Component, Release, ProfileBuild) triple for enrichment tests."""
    pb = ProfileBuild(profile_name=profile)
    rel = Release(
        version=version,
        platform="2.0",
        channel=channel,
        git_url="DEP_Components/_git/contrib_openssl",
        profile_builds=[pb],
    )
    comp = Component(name=name, releases=[rel])
    return comp, rel, pb


def _minimal_enrich_result(
    comp: Component,
    release: Release,
    pb: ProfileBuild,
    base_ref: str = "",
    conan_settings: dict | None = None,
    variants: list[ConanVariant] | None = None,
    exists: bool = True,
) -> ConanEnrichmentResult:
    """Build a ConanEnrichmentResult that covers the given component/release/pb."""
    result = ConanEnrichmentResult()
    key = (comp.name, release.version, release.channel)
    result.release_data[key] = ReleaseConanData(
        base_ref=base_ref
        or f"{comp.name}/{release.version}@platform-2.0/{release.channel}",
        rrev="abc123",
        full_version=release.version,
        default_options=[],
        total_options=[],
        patches=[],
        dependencies=[],
        artifactory_url="",
    )
    result.profile_data[id(pb)] = ProfileConanData(
        conan_settings=conan_settings or {},
        exists=exists,
        variants=variants or [],
    )
    return result


# ---------------------------------------------------------------------------
# apply_options — 4.1
# ---------------------------------------------------------------------------


def test_apply_options_sets_build_option_sets(
    manifest_component: Component, manifest_release: Release
) -> None:
    """apply_options() sets _build_option_sets_internal and build_option_sets."""
    key = ("openssl", manifest_release.version, manifest_release.channel)
    options_map = {key: {"1": "shared=True"}}

    DataEnricher.apply_options([manifest_component], options_map)

    assert manifest_release._build_option_sets_internal == {"1": "shared=True"}
    assert len(manifest_release.build_option_sets) == 1
    assert manifest_release.build_option_sets[0].id == "1"


# ---------------------------------------------------------------------------
# 4.2
# ---------------------------------------------------------------------------


def test_apply_options_ignores_missing_key(
    manifest_component: Component, manifest_release: Release
) -> None:
    """apply_options() with an empty options_map leaves build_option_sets unchanged."""
    DataEnricher.apply_options([manifest_component], {})

    assert manifest_release.build_option_sets == []


# ---------------------------------------------------------------------------
# 4.3
# ---------------------------------------------------------------------------


def test_apply_options_multiple_sets(
    manifest_component: Component, manifest_release: Release
) -> None:
    """apply_options() with two option sets creates two ConanInputOptions entries."""
    key = ("openssl", manifest_release.version, manifest_release.channel)
    options_map = {key: {"1": "shared=True", "2": "shared=False"}}

    DataEnricher.apply_options([manifest_component], options_map)

    assert len(manifest_release.build_option_sets) == 2


# ---------------------------------------------------------------------------
# apply_docker_links — 4.4
# ---------------------------------------------------------------------------


def test_apply_docker_links_creates_profile_definition() -> None:
    """apply_docker_links() appends a new ProfileDefinition when none exists."""
    comp, rel, pb = _release(profile="hw-linux-x86_64-gcc10_2")
    docker_links = {"hw-linux-x86_64-gcc10_2": "harbor.example.com/img:tag"}
    profile_definitions: list[ProfileDefinition] = []

    DataEnricher.apply_docker_links([comp], docker_links, profile_definitions)

    assert len(profile_definitions) == 1
    assert profile_definitions[0].docker_image == "harbor.example.com/img:tag"


# ---------------------------------------------------------------------------
# 4.5
# ---------------------------------------------------------------------------


def test_apply_docker_links_updates_existing_definition() -> None:
    """apply_docker_links() updates docker_image on an existing ProfileDefinition."""
    comp, rel, pb = _release(profile="hw-linux-x86_64-gcc10_2")
    existing = ProfileDefinition(
        profile_name="hw-linux-x86_64-gcc10_2", docker_image="old"
    )
    profile_definitions: list[ProfileDefinition] = [existing]
    docker_links = {"hw-linux-x86_64-gcc10_2": "harbor.example.com/img:tag"}

    DataEnricher.apply_docker_links([comp], docker_links, profile_definitions)

    assert existing.docker_image == "harbor.example.com/img:tag"
    assert len(profile_definitions) == 1  # no duplicate created


# ---------------------------------------------------------------------------
# 4.6
# ---------------------------------------------------------------------------


def test_apply_docker_links_profile_not_in_links_unchanged() -> None:
    """apply_docker_links() with empty docker_links creates a ProfileDefinition with
    an empty docker_image — the profile is registered but no URL is set."""
    comp, rel, pb = _release(profile="hw-linux-x86_64-gcc10_2")
    profile_definitions: list[ProfileDefinition] = []

    DataEnricher.apply_docker_links([comp], {}, profile_definitions)

    # The profile entry is always upserted; docker_image is empty when the
    # profile name is absent from docker_links.
    assert len(profile_definitions) == 1
    assert profile_definitions[0].docker_image == ""


# ---------------------------------------------------------------------------
# apply_conan_results — 4.7
# ---------------------------------------------------------------------------


def test_apply_conan_results_sets_conan_reference() -> None:
    """apply_conan_results() writes base_ref into release.conan_reference."""
    comp, rel, pb = _release()
    expected_ref = "openssl/3.0@platform-2.0/tech"
    result = _minimal_enrich_result(comp, rel, pb, base_ref=expected_ref)

    DataEnricher.apply_conan_results([comp], result)

    assert rel.conan_reference == expected_ref


# ---------------------------------------------------------------------------
# 4.8
# ---------------------------------------------------------------------------


def test_apply_conan_results_sets_profile_build_exists_and_variants(
    conan_variant: ConanVariant,
) -> None:
    """apply_conan_results() sets pb.exists=True and populates pb.variants."""
    comp, rel, pb = _release()
    result = _minimal_enrich_result(
        comp, rel, pb, exists=True, variants=[conan_variant]
    )

    DataEnricher.apply_conan_results([comp], result)

    assert pb.exists is True
    assert len(pb.variants) == 1


# ---------------------------------------------------------------------------
# 4.9
# ---------------------------------------------------------------------------


def test_apply_conan_results_upserts_conan_settings() -> None:
    """apply_conan_results() creates a new ProfileDefinition with conan_settings."""
    comp, rel, pb = _release(profile="hw-linux-x86_64-gcc10_2")
    result = _minimal_enrich_result(comp, rel, pb, conan_settings={"os": "Linux"})
    profile_definitions: list[ProfileDefinition] = []

    DataEnricher.apply_conan_results([comp], result, profile_definitions)

    assert len(profile_definitions) == 1
    assert profile_definitions[0].conan_settings.get("os") == "Linux"


# ---------------------------------------------------------------------------
# 4.10
# ---------------------------------------------------------------------------


def test_apply_conan_results_does_not_overwrite_with_empty_settings() -> None:
    """Non-empty conan_settings on an existing ProfileDefinition are not erased by empty data."""
    comp, rel, pb = _release(profile="hw-linux-x86_64-gcc10_2")
    existing_pd = ProfileDefinition(
        profile_name="hw-linux-x86_64-gcc10_2",
        conan_settings={"os": "Linux"},
    )
    # New profile_data carries empty conan_settings
    result = _minimal_enrich_result(comp, rel, pb, conan_settings={})
    profile_definitions: list[ProfileDefinition] = [existing_pd]

    DataEnricher.apply_conan_results([comp], result, profile_definitions)

    assert existing_pd.conan_settings == {"os": "Linux"}


# ---------------------------------------------------------------------------
# 4.11
# ---------------------------------------------------------------------------


def test_apply_conan_results_missing_release_key_unchanged() -> None:
    """apply_conan_results() leaves conan_reference empty when release_data has no match."""
    comp, rel, pb = _release()
    empty_result = ConanEnrichmentResult()

    DataEnricher.apply_conan_results([comp], empty_result)

    assert rel.conan_reference == ""
