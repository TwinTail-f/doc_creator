"""Unit tests for ProfileCentricConverter."""

from __future__ import annotations

import pytest

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.converters.profile_converter import ProfileCentricConverter

# ── Constants ─────────────────────────────────────────────────────────────────

COMP_NAME: str = "openssl"
RELEASE_VERSION: str = "1.0.0"
CHANNEL_TECH: str = "tech"
PLATFORM_VERSION: str = "2.0"
DOCKER_IMAGE: str = "registry.example.com/build/linux-gcc10:latest"
OS_LINUX: str = "Linux"
PASSPORT_PATTERN_SHORT: str = "/p/{component_name}/{release_version}"


# ── Local fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def result_with_header_only_unique_profile(
    publisher_multi_component_result: ParsedResult,
) -> ParsedResult:
    """ParsedResult where a header-only release references an otherwise-absent profile."""
    header_pb = ProfileBuild(
        profile_name="header-only-exclusive-profile",
        exists=False,
        variants=[],
    )
    original_comp = publisher_multi_component_result.components[0]
    header_only_release = original_comp.releases[1]  # 2.0.0 stable, is_header_only=True
    patched_header = header_only_release.model_copy(
        update={"profile_builds": [header_pb]}
    )
    patched_comp = original_comp.model_copy(
        update={"releases": [original_comp.releases[0], patched_header]}
    )
    components = [patched_comp] + list(publisher_multi_component_result.components[1:])
    return publisher_multi_component_result.model_copy(
        update={"components": components}
    )


# ── ProfileCentricConverter ─────────────────────────────────────────────────


class TestProfileCentricConverter:
    """Tests for ProfileCentricConverter.transform()."""

    def test_profile_centric_transform_returns_profiles_list(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """result['profiles'] is a non-empty list."""
        result = ProfileCentricConverter().transform(publisher_multi_component_result)

        assert len(result["profiles"]) > 0

    def test_profile_centric_transform_profile_has_required_fields(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """Each profile entry contains all mandatory keys."""
        result = ProfileCentricConverter().transform(publisher_multi_component_result)

        profile = result["profiles"][0]
        required_keys = {
            "profile_name",
            "os",
            "arch",
            "compiler",
            "compiler_version",
            "docker_url",
            "channels",
        }
        assert required_keys.issubset(profile.keys())

    def test_profile_centric_transform_profile_os_from_conan_settings(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """profile['os'] is read from conan_settings['os'] of the matching ProfileDefinition."""
        result = ProfileCentricConverter().transform(publisher_multi_component_result)

        assert result["profiles"][0]["os"] == OS_LINUX

    def test_profile_centric_transform_profile_docker_url(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """profile['docker_url'] matches the docker_image of the matching ProfileDefinition."""
        result = ProfileCentricConverter().transform(publisher_multi_component_result)

        assert result["profiles"][0]["docker_url"] == DOCKER_IMAGE

    def test_profile_centric_transform_channels_grouped_by_channel(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """Both openssl and zlib appear under the 'tech' channel of the profile."""
        result = ProfileCentricConverter().transform(publisher_multi_component_result)

        channels = result["profiles"][0]["channels"]
        assert len(channels[CHANNEL_TECH]) == 2

    def test_profile_centric_transform_components_sorted_by_name_in_channel(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """Components within a channel are sorted alphabetically by name."""
        result = ProfileCentricConverter().transform(publisher_multi_component_result)

        tech_entries = result["profiles"][0]["channels"][CHANNEL_TECH]
        names = [e["name"] for e in tech_entries]
        assert names == sorted(names)

    def test_profile_centric_transform_comp_entry_has_reference_and_url(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """Each component entry includes 'reference' and 'url' fields."""
        result = ProfileCentricConverter().transform(publisher_multi_component_result)

        comp_entry = result["profiles"][0]["channels"][CHANNEL_TECH][0]
        assert "reference" in comp_entry
        assert "url" in comp_entry

    def test_profile_centric_transform_passport_link_is_none_without_pattern(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """passport_link is None when no passport_page_pattern is configured."""
        result = ProfileCentricConverter().transform(publisher_multi_component_result)

        comp_entry = result["profiles"][0]["channels"][CHANNEL_TECH][0]
        assert comp_entry["passport_link"] is None

    def test_profile_centric_transform_passport_link_formatted_with_pattern(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """passport_link is built from the pattern when include_passport_links=True."""
        converter = ProfileCentricConverter(
            include_passport_links=True,
            passport_page_pattern=PASSPORT_PATTERN_SHORT,
        )
        result = converter.transform(publisher_multi_component_result)

        tech_entries = result["profiles"][0]["channels"][CHANNEL_TECH]
        openssl_entry = next(e for e in tech_entries if e["name"] == COMP_NAME)
        assert openssl_entry["passport_link"] == f"/p/{COMP_NAME}/{RELEASE_VERSION}"

    def test_profile_centric_transform_skips_header_only_for_profile_meta(
        self, result_with_header_only_unique_profile: ParsedResult
    ) -> None:
        """A profile referenced only from header-only releases is absent from result['profiles']."""
        result = ProfileCentricConverter().transform(
            result_with_header_only_unique_profile
        )

        profile_names = {p["profile_name"] for p in result["profiles"]}
        assert "header-only-exclusive-profile" not in profile_names

    def test_profile_centric_transform_include_links_flag_in_result(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """result['include_passport_links'] reflects the constructor parameter."""
        result = ProfileCentricConverter(include_passport_links=False).transform(
            publisher_multi_component_result
        )

        assert result["include_passport_links"] is False
