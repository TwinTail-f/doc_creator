"""Unit tests for PassportConverter."""

from __future__ import annotations

import pytest

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.converters.passport_converter import PassportConverter
from autodoc.publisher.view_models.passports import ConanVariantView

# ── Constants ─────────────────────────────────────────────────────────────────

COMP_NAME: str = "openssl"
RELEASE_VERSION: str = "1.0.0"
CHANNEL_TECH: str = "tech"
PLATFORM_VERSION: str = "2.0"
DOCKER_IMAGE: str = "registry.example.com/build/linux-gcc10:latest"
COMP_DESCRIPTION: str = "OpenSSL TLS/SSL library"
OPT_KEY_SHARED: str = "shared"
OPT_KEY_FPIC: str = "fPIC"
OS_LINUX: str = "Linux"
UNKNOWN_COMPONENT: str = "nonexistent"
UNKNOWN_VERSION: str = "9.9.9"


# ── Local fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def converter_parsed_result_missing_profile(
    publisher_parsed_result: ParsedResult,
) -> ParsedResult:
    """ParsedResult where one ProfileBuild references a profile_name absent from profile_definitions."""
    unknown_pb = ProfileBuild(
        profile_name="unknown-profile",
        exists=True,
        variants=[],
    )
    original_release = publisher_parsed_result.components[0].releases[0]
    patched_release = original_release.model_copy(
        update={"profile_builds": original_release.profile_builds + [unknown_pb]}
    )
    original_comp = publisher_parsed_result.components[0]
    patched_comp = original_comp.model_copy(update={"releases": [patched_release]})
    return publisher_parsed_result.model_copy(update={"components": [patched_comp]})


# ── PassportConverter ───────────────────────────────────────────────────────


class TestPassportConverter:
    """Tests for PassportConverter.transform()."""

    def test_passport_transform_raises_on_unknown_component(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """transform() raises ValueError when the requested component does not exist."""
        converter = PassportConverter(UNKNOWN_COMPONENT, RELEASE_VERSION)

        with pytest.raises(ValueError):
            converter.transform(publisher_parsed_result)

    def test_passport_transform_raises_on_unknown_version(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """transform() raises ValueError when the release version is not found."""
        converter = PassportConverter(COMP_NAME, UNKNOWN_VERSION)

        with pytest.raises(ValueError):
            converter.transform(publisher_parsed_result)

    def test_passport_transform_returns_platform_version(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """result['platform_version'] matches the platform_version of the ParsedResult."""
        result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert result["platform_version"] == PLATFORM_VERSION

    def test_passport_transform_returns_component_fields(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """result['component'] contains the component's name and description."""
        result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert result["component"]["name"] == COMP_NAME
        assert result["component"]["description"] == COMP_DESCRIPTION

    def test_passport_transform_returns_release_version(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """result['release']['version'] matches the requested release version."""
        result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert result["release"]["version"] == RELEASE_VERSION

    def test_passport_transform_returns_release_channel(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """result['release']['channel'] matches the release's channel."""
        result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert result["release"]["channel"] == CHANNEL_TECH

    def test_passport_transform_legacy_contents_is_empty_dict(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """result['legacy_contents'] is always an empty dict from the converter."""
        result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert result["legacy_contents"] == {}

    def test_passport_transform_profile_builds_enriched_with_docker_image(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """Profile builds are enriched with docker_image from ProfileDefinition."""
        result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert result["release"]["profile_builds"][0]["docker_image"] == DOCKER_IMAGE

    def test_passport_transform_profile_builds_enriched_with_conan_settings(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """Profile builds are enriched with conan_settings from ProfileDefinition."""
        result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert (
            result["release"]["profile_builds"][0]["conan_settings"]["os"] == OS_LINUX
        )

    def test_passport_transform_variants_are_conan_variant_views(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """Each variant in profile_builds is a ConanVariantView instance."""
        result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        variant = result["release"]["profile_builds"][0]["variants"][0]
        assert isinstance(variant, ConanVariantView)

    def test_passport_transform_variant_options_resolved_from_total_option_sets(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """Variant conan_options are resolved via options_ref → TotalOptionsSet.options."""
        result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        variant = result["release"]["profile_builds"][0]["variants"][0]
        assert variant.conan_options == {OPT_KEY_SHARED: "True", OPT_KEY_FPIC: "True"}

    def test_passport_transform_variant_install_options_from_build_option_sets(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """Variant install_options are built from the matching ConanInputOptions entry."""
        result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        variant = result["release"]["profile_builds"][0]["variants"][0]
        assert f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True" in variant.install_options

    def test_passport_transform_profile_build_missing_profile_definition(
        self, converter_parsed_result_missing_profile: ParsedResult
    ) -> None:
        """A ProfileBuild with an absent profile_name yields docker_image='' and conan_settings={}."""
        result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
            converter_parsed_result_missing_profile
        )

        unknown_pb = next(
            pb
            for pb in result["release"]["profile_builds"]
            if pb["profile_name"] == "unknown-profile"
        )
        assert unknown_pb["docker_image"] == ""
        assert unknown_pb["conan_settings"] == {}
