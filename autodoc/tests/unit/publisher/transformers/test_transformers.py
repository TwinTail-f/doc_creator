"""Unit tests for all publisher transformers.

Covers:
- BaseDataTransformer static helpers
- PassportLinkMixin
- PassportTransformer
- FullReleaseTransformer
- ProfileCentricTransformer
"""

from __future__ import annotations

import pytest

from autodoc.models.component import (
    ConanVariant,
    ProfileBuild,
    Release,
    Component,
    TotalOptionsSet,
    ConanInputOptions,
)
from autodoc.models.parsed_result import ParsedResult, ProfileDefinition
from autodoc.publisher.transformers.base_transformer import (
    BaseDataTransformer,
    _VariantOpts,
)
from autodoc.publisher.transformers.passport_transformer import PassportTransformer
from autodoc.publisher.transformers.release_transformer import FullReleaseTransformer
from autodoc.publisher.transformers.profile_transformer import ProfileCentricTransformer
from autodoc.publisher.view_models.passports import ConanVariantView

# ── Constants ─────────────────────────────────────────────────────────────────

COMP_NAME: str = "openssl"
OPT_KEY_SHARED: str = "shared"
OPT_KEY_FPIC: str = "fPIC"

PLATFORM_VERSION: str = "2.0"
RELEASE_VERSION: str = "1.0.0"
CHANNEL_TECH: str = "tech"
CHANNEL_STABLE: str = "stable"
PROFILE_NAME: str = "hw-linux-x86_64-gcc10"
DOCKER_IMAGE: str = "registry.example.com/build/linux-gcc10:latest"

COMP_ZLIB: str = "zlib"
COMP_DESCRIPTION: str = "OpenSSL TLS/SSL library"

VARIANT_PKG_ID: str = "abc"
VARIANT_BUILD_URL: str = "https://ci/1"
VARIANT_BUILD_DATE: str = "2024-01-01"
VARIANT_OPT_REF: str = "r1"

INSTALL_OVERRIDE: str = "-o pkg/*:x=1"
PASSPORT_PATTERN: str = "/pages/{component_name}/{release_version}"
PASSPORT_PATTERN_SHORT: str = "/p/{component_name}/{release_version}"

UNKNOWN_PROFILE: str = "ghost"
UNKNOWN_COMPONENT: str = "nonexistent"
UNKNOWN_VERSION: str = "9.9.9"

OS_LINUX: str = "Linux"
ARCH_X86_64: str = "x86_64"
COMPILER_GCC: str = "gcc"
COMPILER_VERSION_10: str = "10"

OPT_SET_ID: str = "opt-set-1"
OPT_SET_ID_MULTI: str = "opt-1"
BUILD_OPTS_STR: str = "openssl/*:shared=True, openssl/*:fPIC=True"


# ── Local fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def sample_variant() -> ConanVariant:
    """A ConanVariant with all fields set, used across multiple static helper tests."""
    return ConanVariant(
        package_id=VARIANT_PKG_ID,
        build_url=VARIANT_BUILD_URL,
        build_date=VARIANT_BUILD_DATE,
        options_ref=VARIANT_OPT_REF,
    )


@pytest.fixture
def transformer_parsed_result_missing_profile(
    publisher_parsed_result: ParsedResult,
) -> ParsedResult:
    """ParsedResult where one ProfileBuild references a profile_name absent from profile_definitions.

    Used to verify that PassportTransformer gracefully returns docker_image=""
    and conan_settings={} instead of raising KeyError.
    """
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
    patched_comp = original_comp.model_copy(
        update={"releases": [patched_release]}
    )
    return publisher_parsed_result.model_copy(
        update={"components": [patched_comp]}
    )


@pytest.fixture
def multi_result_with_unknown_profile(
    publisher_multi_component_result: ParsedResult,
) -> ParsedResult:
    """ParsedResult where openssl 1.0.0 has an extra ProfileBuild with UNKNOWN_PROFILE.

    Used to verify FullReleaseTransformer returns empty docker_image and conan_settings
    for profiles not present in profile_definitions.
    """
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


@pytest.fixture
def result_with_header_only_unique_profile(
    publisher_multi_component_result: ParsedResult,
) -> ParsedResult:
    """ParsedResult where a header-only release references an otherwise-absent profile.

    Used to verify _collect_profile_meta does not register a profile that appears
    only in header-only releases.
    """
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
    components = [patched_comp] + list(
        publisher_multi_component_result.components[1:]
    )
    return publisher_multi_component_result.model_copy(
        update={"components": components}
    )


# ── BaseDataTransformer ────────────────────────────────────────────────────────


class TestBuildInstallOptions:
    """Tests for BaseDataTransformer._build_install_options static method."""

    def test_build_install_options_empty_dict_returns_empty_string(self) -> None:
        """Empty options dict produces an empty string."""
        result = PassportTransformer._build_install_options({}, COMP_NAME)

        assert result == ""

    def test_build_install_options_qualifies_bare_key_with_component_name(
        self,
    ) -> None:
        """A bare key without ':' is qualified as 'component_name/*:key=val'."""
        result = PassportTransformer._build_install_options(
            {OPT_KEY_SHARED: "True"}, COMP_NAME
        )

        assert result == f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"

    def test_build_install_options_preserves_qualified_key(self) -> None:
        """A key already containing '/*:' is not double-qualified."""
        result = PassportTransformer._build_install_options(
            {"icu/*:shared": "True"}, COMP_NAME
        )

        assert result == "-o icu/*:shared=True"

    def test_build_install_options_multiple_options_joined_by_space(self) -> None:
        """Multiple options are joined by a single space, each with its own '-o' flag."""
        result = PassportTransformer._build_install_options(
            {OPT_KEY_SHARED: "True", OPT_KEY_FPIC: "True"}, COMP_NAME
        )

        assert f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True" in result
        assert f"-o {COMP_NAME}/*:{OPT_KEY_FPIC}=True" in result

    def test_build_install_options_dep_key_with_colon_not_modified(self) -> None:
        """A dependency key like 'icu:opt' is qualified to 'icu/*:opt' without duplication."""
        result = PassportTransformer._build_install_options(
            {"icu:data_packaging": "static"}, COMP_NAME
        )

        assert result == "-o icu/*:data_packaging=static"


class TestBuildInstallOptionsFromString:
    """Tests for BaseDataTransformer._build_install_options_from_string static method."""

    def test_build_install_options_from_string_empty_returns_empty(self) -> None:
        """An empty string input produces an empty string."""
        result = PassportTransformer._build_install_options_from_string("")

        assert result == ""

    def test_build_install_options_from_string_whitespace_returns_empty(self) -> None:
        """A whitespace-only string produces an empty string."""
        result = PassportTransformer._build_install_options_from_string("   ")

        assert result == ""

    def test_build_install_options_from_string_single_option(self) -> None:
        """A single 'pkg/*:key=val' entry is wrapped with a single '-o' flag."""
        result = PassportTransformer._build_install_options_from_string(
            f"{COMP_NAME}/*:{OPT_KEY_SHARED}=True"
        )

        assert result == f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"

    def test_build_install_options_from_string_multiple_options(self) -> None:
        """Multiple comma-separated options produce space-separated '-o' flags."""
        options = (
            f"{COMP_NAME}/*:{OPT_KEY_SHARED}=True, {COMP_NAME}/*:{OPT_KEY_FPIC}=True"
        )
        result = PassportTransformer._build_install_options_from_string(options)

        assert result == (
            f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"
            f" -o {COMP_NAME}/*:{OPT_KEY_FPIC}=True"
        )

    def test_build_install_options_from_string_qualifies_unqualified_key(
        self,
    ) -> None:
        """An option with 'pkg:key=val' (no '/*') is qualified to 'pkg/*:key=val'."""
        result = PassportTransformer._build_install_options_from_string(
            f"{COMP_NAME}:{OPT_KEY_SHARED}=True"
        )

        assert result == f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"

    def test_build_install_options_from_string_strips_whitespace_between_options(
        self,
    ) -> None:
        """Leading/trailing whitespace around each option token is stripped correctly."""
        options = (
            f"  {COMP_NAME}/*:{OPT_KEY_SHARED}=True  ,"
            f"  {COMP_NAME}/*:{OPT_KEY_FPIC}=True  "
        )
        result = PassportTransformer._build_install_options_from_string(options)

        assert result == (
            f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"
            f" -o {COMP_NAME}/*:{OPT_KEY_FPIC}=True"
        )


class TestBuildVariantView:
    """Tests for BaseDataTransformer._build_variant_view static method."""

    def test_build_variant_view_maps_fields_from_variant(
        self, sample_variant: ConanVariant
    ) -> None:
        """package_id and build_url from ConanVariant appear in the resulting view."""
        view = PassportTransformer._build_variant_view(sample_variant, COMP_NAME)

        assert view.package_id == VARIANT_PKG_ID
        assert view.build_url == VARIANT_BUILD_URL

    def test_build_variant_view_uses_conan_options_from_opts(
        self, sample_variant: ConanVariant
    ) -> None:
        """conan_options from _VariantOpts are passed through to the view model."""
        opts = _VariantOpts(conan_options={OPT_KEY_SHARED: "True"})
        view = PassportTransformer._build_variant_view(sample_variant, COMP_NAME, opts)

        assert view.conan_options == {OPT_KEY_SHARED: "True"}

    def test_build_variant_view_no_opts_gives_empty_conan_options(
        self, sample_variant: ConanVariant
    ) -> None:
        """When opts is None the view model's conan_options is an empty dict."""
        view = PassportTransformer._build_variant_view(sample_variant, COMP_NAME, None)

        assert view.conan_options == {}

    def test_build_variant_view_install_options_override_used_directly(
        self, sample_variant: ConanVariant
    ) -> None:
        """install_options_override is written verbatim to view.install_options."""
        opts = _VariantOpts(conan_options={}, install_options_override=INSTALL_OVERRIDE)
        view = PassportTransformer._build_variant_view(sample_variant, COMP_NAME, opts)

        assert view.install_options == INSTALL_OVERRIDE

    def test_build_variant_view_builds_install_options_from_conan_options_if_no_override(
        self, sample_variant: ConanVariant
    ) -> None:
        """When override is None, install_options is built from conan_options."""
        opts = _VariantOpts(
            conan_options={OPT_KEY_SHARED: "True"}, install_options_override=None
        )
        view = PassportTransformer._build_variant_view(sample_variant, COMP_NAME, opts)

        assert view.install_options == f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"


# ── PassportLinkMixin ─────────────────────────────────────────────────────────


class TestPassportLinkMixin:
    """Tests for PassportLinkMixin via FullReleaseTransformer (concrete subclass)."""

    def test_passport_link_returns_none_if_include_links_false(self) -> None:
        """_passport_link returns None when include_passport_links=False."""
        transformer = FullReleaseTransformer(
            include_passport_links=False,
            passport_page_pattern=PASSPORT_PATTERN,
        )

        assert transformer._passport_link(COMP_NAME, RELEASE_VERSION) is None

    def test_passport_link_returns_none_if_pattern_is_none(self) -> None:
        """_passport_link returns None when passport_page_pattern is None."""
        transformer = FullReleaseTransformer(
            include_passport_links=True,
            passport_page_pattern=None,
        )

        assert transformer._passport_link(COMP_NAME, RELEASE_VERSION) is None

    def test_passport_link_formats_pattern_with_component_and_version(self) -> None:
        """_passport_link substitutes component_name and release_version into the pattern."""
        transformer = FullReleaseTransformer(
            include_passport_links=True,
            passport_page_pattern=PASSPORT_PATTERN,
        )

        assert (
            transformer._passport_link(COMP_NAME, RELEASE_VERSION)
            == f"/pages/{COMP_NAME}/{RELEASE_VERSION}"
        )

    def test_passport_link_replaces_spaces_with_plus(self) -> None:
        """Spaces in component name and version are replaced with '+' in the link."""
        transformer = FullReleaseTransformer(
            include_passport_links=True,
            passport_page_pattern=PASSPORT_PATTERN,
        )

        result = transformer._passport_link("my lib", "1.0 beta")

        assert result == "/pages/my+lib/1.0+beta"


# ── PassportTransformer ───────────────────────────────────────────────────────


class TestPassportTransformer:
    """Tests for PassportTransformer.transform()."""

    def test_passport_transform_raises_on_unknown_component(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """transform() raises ValueError when the requested component does not exist."""
        transformer = PassportTransformer(UNKNOWN_COMPONENT, RELEASE_VERSION)

        with pytest.raises(ValueError):
            transformer.transform(publisher_parsed_result)

    def test_passport_transform_raises_on_unknown_version(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """transform() raises ValueError when the release version is not found."""
        transformer = PassportTransformer(COMP_NAME, UNKNOWN_VERSION)

        with pytest.raises(ValueError):
            transformer.transform(publisher_parsed_result)

    def test_passport_transform_returns_platform_version(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """result['platform_version'] matches the platform_version of the ParsedResult."""
        result = PassportTransformer(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert result["platform_version"] == PLATFORM_VERSION

    def test_passport_transform_returns_component_fields(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """result['component'] contains the component's name and description."""
        result = PassportTransformer(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert result["component"]["name"] == COMP_NAME
        assert result["component"]["description"] == COMP_DESCRIPTION

    def test_passport_transform_returns_release_version(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """result['release']['version'] matches the requested release version."""
        result = PassportTransformer(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert result["release"]["version"] == RELEASE_VERSION

    def test_passport_transform_returns_release_channel(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """result['release']['channel'] matches the release's channel."""
        result = PassportTransformer(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert result["release"]["channel"] == CHANNEL_TECH

    def test_passport_transform_legacy_contents_is_empty_dict(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """result['legacy_contents'] is always an empty dict from the transformer."""
        result = PassportTransformer(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert result["legacy_contents"] == {}

    def test_passport_transform_profile_builds_enriched_with_docker_image(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """Profile builds are enriched with docker_image from ProfileDefinition."""
        result = PassportTransformer(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert result["release"]["profile_builds"][0]["docker_image"] == DOCKER_IMAGE

    def test_passport_transform_profile_builds_enriched_with_conan_settings(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """Profile builds are enriched with conan_settings from ProfileDefinition."""
        result = PassportTransformer(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        assert result["release"]["profile_builds"][0]["conan_settings"]["os"] == OS_LINUX

    def test_passport_transform_variants_are_conan_variant_views(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """Each variant in profile_builds is a ConanVariantView instance."""
        result = PassportTransformer(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        variant = result["release"]["profile_builds"][0]["variants"][0]
        assert isinstance(variant, ConanVariantView)

    def test_passport_transform_variant_options_resolved_from_total_option_sets(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """Variant conan_options are resolved via options_ref → TotalOptionsSet.options."""
        result = PassportTransformer(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        variant = result["release"]["profile_builds"][0]["variants"][0]
        assert variant.conan_options == {OPT_KEY_SHARED: "True", OPT_KEY_FPIC: "True"}

    def test_passport_transform_variant_install_options_from_build_option_sets(
        self, publisher_parsed_result: ParsedResult
    ) -> None:
        """Variant install_options are built from the matching ConanInputOptions entry."""
        result = PassportTransformer(COMP_NAME, RELEASE_VERSION).transform(
            publisher_parsed_result
        )

        variant = result["release"]["profile_builds"][0]["variants"][0]
        assert f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True" in variant.install_options

    def test_passport_transform_profile_build_missing_profile_definition(
        self, transformer_parsed_result_missing_profile: ParsedResult
    ) -> None:
        """A ProfileBuild with an absent profile_name yields docker_image='' and conan_settings={}."""
        result = PassportTransformer(COMP_NAME, RELEASE_VERSION).transform(
            transformer_parsed_result_missing_profile
        )

        unknown_pb = next(
            pb
            for pb in result["release"]["profile_builds"]
            if pb["profile_name"] == "unknown-profile"
        )
        assert unknown_pb["docker_image"] == ""
        assert unknown_pb["conan_settings"] == {}


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


# ── ProfileCentricTransformer ─────────────────────────────────────────────────


class TestProfileCentricTransformer:
    """Tests for ProfileCentricTransformer.transform()."""

    def test_profile_centric_transform_returns_profiles_list(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """result['profiles'] is a non-empty list."""
        result = ProfileCentricTransformer().transform(
            publisher_multi_component_result
        )

        assert len(result["profiles"]) > 0

    def test_profile_centric_transform_profile_has_required_fields(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """Each profile entry contains all mandatory keys."""
        result = ProfileCentricTransformer().transform(
            publisher_multi_component_result
        )

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
        result = ProfileCentricTransformer().transform(
            publisher_multi_component_result
        )

        assert result["profiles"][0]["os"] == OS_LINUX

    def test_profile_centric_transform_profile_docker_url(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """profile['docker_url'] matches the docker_image of the matching ProfileDefinition."""
        result = ProfileCentricTransformer().transform(
            publisher_multi_component_result
        )

        assert result["profiles"][0]["docker_url"] == DOCKER_IMAGE

    def test_profile_centric_transform_channels_grouped_by_channel(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """Both openssl and zlib appear under the 'tech' channel of the profile."""
        result = ProfileCentricTransformer().transform(
            publisher_multi_component_result
        )

        channels = result["profiles"][0]["channels"]
        assert len(channels[CHANNEL_TECH]) == 2

    def test_profile_centric_transform_components_sorted_by_name_in_channel(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """Components within a channel are sorted alphabetically by name."""
        result = ProfileCentricTransformer().transform(
            publisher_multi_component_result
        )

        tech_entries = result["profiles"][0]["channels"][CHANNEL_TECH]
        names = [e["name"] for e in tech_entries]
        assert names == sorted(names)

    def test_profile_centric_transform_comp_entry_has_reference_and_url(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """Each component entry includes 'reference' and 'url' fields."""
        result = ProfileCentricTransformer().transform(
            publisher_multi_component_result
        )

        comp_entry = result["profiles"][0]["channels"][CHANNEL_TECH][0]
        assert "reference" in comp_entry
        assert "url" in comp_entry

    def test_profile_centric_transform_passport_link_is_none_without_pattern(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """passport_link is None when no passport_page_pattern is configured."""
        result = ProfileCentricTransformer().transform(
            publisher_multi_component_result
        )

        comp_entry = result["profiles"][0]["channels"][CHANNEL_TECH][0]
        assert comp_entry["passport_link"] is None

    def test_profile_centric_transform_passport_link_formatted_with_pattern(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """passport_link is built from the pattern when include_passport_links=True."""
        transformer = ProfileCentricTransformer(
            include_passport_links=True,
            passport_page_pattern=PASSPORT_PATTERN_SHORT,
        )
        result = transformer.transform(publisher_multi_component_result)

        tech_entries = result["profiles"][0]["channels"][CHANNEL_TECH]
        openssl_entry = next(e for e in tech_entries if e["name"] == COMP_NAME)
        assert openssl_entry["passport_link"] == f"/p/{COMP_NAME}/{RELEASE_VERSION}"

    def test_profile_centric_transform_skips_header_only_for_profile_meta(
        self, result_with_header_only_unique_profile: ParsedResult
    ) -> None:
        """A profile referenced only from header-only releases is absent from result['profiles']."""
        result = ProfileCentricTransformer().transform(
            result_with_header_only_unique_profile
        )

        profile_names = {p["profile_name"] for p in result["profiles"]}
        assert "header-only-exclusive-profile" not in profile_names

    def test_profile_centric_transform_include_links_flag_in_result(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """result['include_passport_links'] reflects the constructor parameter."""
        result = ProfileCentricTransformer(include_passport_links=False).transform(
            publisher_multi_component_result
        )

        assert result["include_passport_links"] is False
