"""Unit tests for BaseDataConverter static helpers and PassportLinkMixin."""

from __future__ import annotations

import pytest

from autodoc.models.conan_variant import ConanVariant
from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.converters.passport_link_mixin import _VariantOpts
from autodoc.publisher.converters.passport_converter import PassportConverter
from autodoc.publisher.converters.full_release_converter import FullReleaseConverter
from autodoc.publisher.view_models.passports import ConanVariantView

# ── Constants ─────────────────────────────────────────────────────────────────

COMP_NAME: str = "openssl"
OPT_KEY_SHARED: str = "shared"
OPT_KEY_FPIC: str = "fPIC"

RELEASE_VERSION: str = "1.0.0"
PASSPORT_PATTERN: str = "/pages/{component_name}/{release_version}"

VARIANT_PKG_ID: str = "abc"
VARIANT_BUILD_URL: str = "https://ci/1"
VARIANT_BUILD_DATE: str = "2024-01-01"
VARIANT_OPT_REF: str = "r1"

INSTALL_OVERRIDE: str = "-o pkg/*:x=1"


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


# ── BaseDataConverter ────────────────────────────────────────────────────────


class TestBuildInstallOptions:
    """Tests for BaseDataConverter._build_install_options static method."""

    def test_build_install_options_empty_dict_returns_empty_string(self) -> None:
        """Empty options dict produces an empty string."""
        result = PassportConverter._build_install_options({}, COMP_NAME)

        assert result == ""

    def test_build_install_options_qualifies_bare_key_with_component_name(
        self,
    ) -> None:
        """A bare key without ':' is qualified as 'component_name/*:key=val'."""
        result = PassportConverter._build_install_options(
            {OPT_KEY_SHARED: "True"}, COMP_NAME
        )

        assert result == f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"

    def test_build_install_options_preserves_qualified_key(self) -> None:
        """A key already containing '/*:' is not double-qualified."""
        result = PassportConverter._build_install_options(
            {"icu/*:shared": "True"}, COMP_NAME
        )

        assert result == "-o icu/*:shared=True"

    def test_build_install_options_multiple_options_joined_by_space(self) -> None:
        """Multiple options are joined by a single space, each with its own '-o' flag."""
        result = PassportConverter._build_install_options(
            {OPT_KEY_SHARED: "True", OPT_KEY_FPIC: "True"}, COMP_NAME
        )

        assert f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True" in result
        assert f"-o {COMP_NAME}/*:{OPT_KEY_FPIC}=True" in result

    def test_build_install_options_dep_key_with_colon_not_modified(self) -> None:
        """A dependency key like 'icu:opt' is qualified to 'icu/*:opt' without duplication."""
        result = PassportConverter._build_install_options(
            {"icu:data_packaging": "static"}, COMP_NAME
        )

        assert result == "-o icu/*:data_packaging=static"


class TestBuildInstallOptionsFromString:
    """Tests for BaseDataConverter._build_install_options_from_string static method."""

    def test_build_install_options_from_string_empty_returns_empty(self) -> None:
        """An empty string input produces an empty string."""
        result = PassportConverter._build_install_options_from_string("")

        assert result == ""

    def test_build_install_options_from_string_whitespace_returns_empty(self) -> None:
        """A whitespace-only string produces an empty string."""
        result = PassportConverter._build_install_options_from_string("   ")

        assert result == ""

    def test_build_install_options_from_string_single_option(self) -> None:
        """A single 'pkg/*:key=val' entry is wrapped with a single '-o' flag."""
        result = PassportConverter._build_install_options_from_string(
            f"{COMP_NAME}/*:{OPT_KEY_SHARED}=True"
        )

        assert result == f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"

    def test_build_install_options_from_string_multiple_options(self) -> None:
        """Multiple comma-separated options produce space-separated '-o' flags."""
        options = (
            f"{COMP_NAME}/*:{OPT_KEY_SHARED}=True, {COMP_NAME}/*:{OPT_KEY_FPIC}=True"
        )
        result = PassportConverter._build_install_options_from_string(options)

        assert result == (
            f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"
            f" -o {COMP_NAME}/*:{OPT_KEY_FPIC}=True"
        )

    def test_build_install_options_from_string_qualifies_unqualified_key(
        self,
    ) -> None:
        """An option with 'pkg:key=val' (no '/*') is qualified to 'pkg/*:key=val'."""
        result = PassportConverter._build_install_options_from_string(
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
        result = PassportConverter._build_install_options_from_string(options)

        assert result == (
            f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"
            f" -o {COMP_NAME}/*:{OPT_KEY_FPIC}=True"
        )


class TestBuildVariantView:
    """Tests for BaseDataConverter._build_variant_view static method."""

    def test_build_variant_view_maps_fields_from_variant(
        self, sample_variant: ConanVariant
    ) -> None:
        """package_id and build_url from ConanVariant appear in the resulting view."""
        view = PassportConverter._build_variant_view(sample_variant, COMP_NAME)

        assert view.package_id == VARIANT_PKG_ID
        assert view.build_url == VARIANT_BUILD_URL

    def test_build_variant_view_uses_conan_options_from_opts(
        self, sample_variant: ConanVariant
    ) -> None:
        """conan_options from _VariantOpts are passed through to the view model."""
        opts = _VariantOpts(conan_options={OPT_KEY_SHARED: "True"})
        view = PassportConverter._build_variant_view(sample_variant, COMP_NAME, opts)

        assert view.conan_options == {OPT_KEY_SHARED: "True"}

    def test_build_variant_view_no_opts_gives_empty_conan_options(
        self, sample_variant: ConanVariant
    ) -> None:
        """When opts is None the view model's conan_options is an empty dict."""
        view = PassportConverter._build_variant_view(sample_variant, COMP_NAME, None)

        assert view.conan_options == {}

    def test_build_variant_view_install_options_override_used_directly(
        self, sample_variant: ConanVariant
    ) -> None:
        """install_options_override is written verbatim to view.install_options."""
        opts = _VariantOpts(conan_options={}, install_options_override=INSTALL_OVERRIDE)
        view = PassportConverter._build_variant_view(sample_variant, COMP_NAME, opts)

        assert view.install_options == INSTALL_OVERRIDE

    def test_build_variant_view_builds_install_options_from_conan_options_if_no_override(
        self, sample_variant: ConanVariant
    ) -> None:
        """When override is None, install_options is built from conan_options."""
        opts = _VariantOpts(
            conan_options={OPT_KEY_SHARED: "True"}, install_options_override=None
        )
        view = PassportConverter._build_variant_view(sample_variant, COMP_NAME, opts)

        assert view.install_options == f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"


# ── PassportLinkMixin ─────────────────────────────────────────────────────────


class TestPassportLinkMixin:
    """Tests for PassportLinkMixin via FullReleaseConverter (concrete subclass)."""

    def test_passport_link_returns_none_if_include_links_false(self) -> None:
        """_passport_link returns None when include_passport_links=False."""
        converter = FullReleaseConverter(
            include_passport_links=False,
            passport_page_pattern=PASSPORT_PATTERN,
        )

        assert converter._passport_link(COMP_NAME, RELEASE_VERSION) is None

    def test_passport_link_returns_none_if_pattern_is_none(self) -> None:
        """_passport_link returns None when passport_page_pattern is None."""
        converter = FullReleaseConverter(
            include_passport_links=True,
            passport_page_pattern=None,
        )

        assert converter._passport_link(COMP_NAME, RELEASE_VERSION) is None

    def test_passport_link_formats_pattern_with_component_and_version(self) -> None:
        """_passport_link substitutes component_name and release_version into the pattern."""
        converter = FullReleaseConverter(
            include_passport_links=True,
            passport_page_pattern=PASSPORT_PATTERN,
        )

        assert (
            converter._passport_link(COMP_NAME, RELEASE_VERSION)
            == f"/pages/{COMP_NAME}/{RELEASE_VERSION}"
        )

    def test_passport_link_replaces_spaces_with_plus(self) -> None:
        """Spaces in component name and version are replaced with '+' in the link."""
        converter = FullReleaseConverter(
            include_passport_links=True,
            passport_page_pattern=PASSPORT_PATTERN,
        )

        result = converter._passport_link("my lib", "1.0 beta")

        assert result == "/pages/my+lib/1.0+beta"
