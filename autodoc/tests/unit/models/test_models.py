"""Unit tests for autodoc.models.component.

Covers: _parse_option_str, ConanInputOptions, ProfileBuild, Release, Component.
"""

from __future__ import annotations

import pytest

from autodoc.models.component import (
    _parse_option_str,
    ConanInputOptions,
    Component,
    ProfileBuild,
    Release,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

OPTION_STR_WITH_PREFIX: str = "mylib:shared=True,mylib:fPIC=False"
OPTION_STR_NO_PREFIX: str = "shared=True"
OPTION_STR_WILDCARD: str = "mylib/*:shared=True"
OPTION_STR_PKG: str = "pkg:shared=True,pkg:fPIC=False"

MINIMAL_RELEASE_KWARGS: dict = {
    "version": "1.0.0",
    "platform": "2.0",
    "channel": "tech",
    "git_url": "PROJ/_git/repo",
}


# ===========================================================================
# 1.1 — _parse_option_str: happy path with package prefix
# ===========================================================================


def test_parse_option_str_strips_package_prefix() -> None:
    """_parse_option_str removes the package prefix from every key."""
    result = _parse_option_str(OPTION_STR_WITH_PREFIX)
    assert result == {"shared": "True", "fPIC": "False"}


# ===========================================================================
# 1.2 — _parse_option_str: empty string
# ===========================================================================


def test_parse_option_str_empty_string_returns_empty_dict() -> None:
    """_parse_option_str returns an empty dict for an empty input string."""
    result = _parse_option_str("")
    assert result == {}


# ===========================================================================
# 1.3 — _parse_option_str: no prefix
# ===========================================================================


def test_parse_option_str_no_prefix() -> None:
    """_parse_option_str accepts keys that carry no package prefix."""
    result = _parse_option_str(OPTION_STR_NO_PREFIX)
    assert result == {"shared": "True"}


# ===========================================================================
# 1.4 — _parse_option_str: wildcard prefix is stripped
# ===========================================================================


def test_parse_option_str_wildcard_prefix_stripped() -> None:
    """_parse_option_str strips the wildcard prefix (mylib/*:key) and keeps the bare key."""
    result = _parse_option_str(OPTION_STR_WILDCARD)
    assert "shared" in result


# ===========================================================================
# 1.5 — ConanInputOptions: parsed_options auto-filled from options
# ===========================================================================


def test_conan_input_options_auto_fills_parsed_options() -> None:
    """ConanInputOptions.parsed_options is auto-populated from the options string on construction."""
    instance = ConanInputOptions(id="1", options=OPTION_STR_PKG)
    assert instance.parsed_options == {"shared": "True", "fPIC": "False"}


# ===========================================================================
# 1.6 — ConanInputOptions: empty options → parsed_options stays empty
# ===========================================================================


def test_conan_input_options_empty_options_parsed_options_empty() -> None:
    """ConanInputOptions.parsed_options remains empty when options is an empty string."""
    instance = ConanInputOptions(id="1", options="")
    assert instance.parsed_options == {}


# ===========================================================================
# 1.7 — ConanInputOptions: explicit parsed_options not overwritten (parametrized)
# ===========================================================================


@pytest.mark.parametrize(
    "options_str, explicit_parsed",
    [
        ("pkg:shared=True", {"custom": "val"}),
        ("pkg:fPIC=False", {"override": "yes", "extra": "no"}),
    ],
)
def test_conan_input_options_explicit_parsed_options_not_overwritten(
    options_str: str,
    explicit_parsed: dict[str, str],
) -> None:
    """ConanInputOptions.parsed_options is not overwritten when it is explicitly provided."""
    instance = ConanInputOptions(
        id="1",
        options=options_str,
        parsed_options=explicit_parsed,
    )
    assert instance.parsed_options == explicit_parsed


# ===========================================================================
# 1.8 — ProfileBuild: default exists is False
# ===========================================================================


def test_profile_build_default_exists_is_false() -> None:
    """ProfileBuild.exists defaults to False when not explicitly set."""
    instance = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    assert instance.exists is False


# ===========================================================================
# 1.9 — Release: default collections are empty
# ===========================================================================


def test_release_defaults_are_empty_collections() -> None:
    """Release.build_option_sets and profile_builds default to [] and is_header_only to False."""
    instance = Release(**MINIMAL_RELEASE_KWARGS)
    assert instance.build_option_sets == []
    assert instance.profile_builds == []
    assert instance.is_header_only is False


# ===========================================================================
# 1.10 — Component: round-trip serialization via model_dump / model_validate
# ===========================================================================


def test_component_roundtrip_serialization() -> None:
    """Component round-trips correctly through model_dump and model_validate."""
    original = Component(name="openssl", description="TLS library")
    data = original.model_dump()
    restored = Component.model_validate(data)
    assert restored.name == original.name
