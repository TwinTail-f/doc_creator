"""Unit tests for FullReleaseTransformer."""

from __future__ import annotations

import pytest

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.transformers.full_release_transformer import FullReleaseTransformer

# ── Constants ─────────────────────────────────────────────────────────────────

COMP_NAME: str = "openssl"
COMP_ZLIB: str = "zlib"
PLATFORM_VERSION: str = "2.0"
DOCKER_IMAGE: str = "registry.example.com/build/linux-gcc10:latest"
UNKNOWN_PROFILE: str = "ghost"


# ── Local fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def multi_result_with_unknown_profile(
    publisher_multi_component_result: ParsedResult,
) -> ParsedResult:
    """ParsedResult where openssl 1.0.0 has an extra ProfileBuild with UNKNOWN_PROFILE."""
    ghost_pb = ProfileBuild(profile_name=UNKNOWN_PROFILE, exists=True, variants=[])
    original_rel = publisher_multi_component_result.components[0].releases[0]
    patched_rel = original_rel.model_copy(
        update={"profile_builds": original_rel.profile_builds + [ghost_pb]}
    )
    original_comp = publisher_multi_component_result.components[0]
    patched_comp = original_comp.model_copy(
        update={"releases": [patched_rel]}
    )
    components = [patched_comp] + list(
        publisher_multi_component_result.components[1:]
    )
    return publisher_multi_component_result.model_copy(
        update={"components": components}
    )


# ── FullReleaseTransformer ────────────────────────────────────────────────────


class TestFullReleaseTransformer:
    """Tests for FullReleaseTransformer.transform()."""

    def test_full_release_transform_returns_platform_version(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """result['platform_version'] matches the ParsedResult platform_version."""
        result = FullReleaseTransformer().transform(publisher_multi_component_result)

        assert result["platform_version"] == PLATFORM_VERSION

    def test_full_release_transform_contains_all_components(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """result['components'] contains one entry for each component in the data."""
        result = FullReleaseTransformer().transform(publisher_multi_component_result)

        assert len(result["components"]) == 2

    def test_full_release_transform_component_has_name_and_description(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """Each component entry carries its name and description fields."""
        result = FullReleaseTransformer().transform(publisher_multi_component_result)

        names = {c["name"] for c in result["components"]}
        assert COMP_NAME in names
        assert COMP_ZLIB in names

    def test_full_release_transform_component_has_releases(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """The openssl component entry exposes both of its releases."""
        result = FullReleaseTransformer().transform(publisher_multi_component_result)

        openssl_entry = next(
            c for c in result["components"] if c["name"] == COMP_NAME
        )
        assert len(openssl_entry["releases"]) == 2

    def test_full_release_transform_include_links_false(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """result['include_passport_links'] is False when the transformer is created with False."""
        result = FullReleaseTransformer(include_passport_links=False).transform(
            publisher_multi_component_result
        )

        assert result["include_passport_links"] is False

    def test_full_release_transform_include_links_true_by_default(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """result['include_passport_links'] is True when using the default constructor."""
        result = FullReleaseTransformer().transform(publisher_multi_component_result)

        assert result["include_passport_links"] is True

    def test_full_release_transform_profile_build_has_docker_image(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """Profile builds are enriched with docker_image from the matching ProfileDefinition."""
        result = FullReleaseTransformer().transform(publisher_multi_component_result)

        openssl_entry = next(
            c for c in result["components"] if c["name"] == COMP_NAME
        )
        first_release = openssl_entry["releases"][0]
        assert first_release["profile_builds"][0]["docker_image"] == DOCKER_IMAGE

    def test_full_release_transform_profile_build_unknown_profile_gives_empty_fields(
        self, multi_result_with_unknown_profile: ParsedResult
    ) -> None:
        """A ProfileBuild with an absent profile_name yields docker_image='' and conan_settings={}."""
        result = FullReleaseTransformer().transform(multi_result_with_unknown_profile)

        openssl_entry = next(
            c for c in result["components"] if c["name"] == COMP_NAME
        )
        ghost_pb = next(
            pb
            for pb in openssl_entry["releases"][0]["profile_builds"]
            if pb["profile_name"] == UNKNOWN_PROFILE
        )
        assert ghost_pb["docker_image"] == ""
        assert ghost_pb["conan_settings"] == {}

    def test_full_release_transform_header_only_release_has_empty_profile_builds(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """A header-only release has an empty profile_builds list in the view model."""
        result = FullReleaseTransformer().transform(publisher_multi_component_result)

        openssl_entry = next(
            c for c in result["components"] if c["name"] == COMP_NAME
        )
        header_only = next(
            r for r in openssl_entry["releases"] if r["is_header_only"]
        )
        assert header_only["profile_builds"] == []
