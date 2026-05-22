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
    second_release = original_comp.releases[1]  # 2.0.0 stable
    patched_header = second_release.model_copy(update={"profile_builds": [header_pb]})
    patched_comp = original_comp.model_copy(
        update={
            "releases": [original_comp.releases[0], patched_header],
            "is_header_only": True,
        }
    )
    components = [patched_comp] + list(publisher_multi_component_result.components[1:])
    return publisher_multi_component_result.model_copy(
        update={"components": components}
    )


# ── ProfileCentricConverter ─────────────────────────────────────────────────


# ---------------------------------------------------------------------------
# BL-PCC-01 … BL-PCC-06  (Part 1 of the Publisher BL test plan)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_profile_centric_transform_returns_profiles_list(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """result['profiles'] is a non-empty list."""
    result = ProfileCentricConverter().transform(publisher_multi_component_result)

    assert len(result["profiles"]) > 0


@pytest.mark.contract
def test_profile_centric_transform_profile_has_required_fields(
    publisher_multi_component_result: ParsedResult,
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


@pytest.mark.business_logic
def test_profile_centric_transform_profile_os_from_conan_settings(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """profile['os'] is read from conan_settings['os'] of the matching ProfileDefinition."""
    result = ProfileCentricConverter().transform(publisher_multi_component_result)

    assert result["profiles"][0]["os"] == OS_LINUX


@pytest.mark.business_logic
def test_profile_centric_transform_profile_docker_url(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """profile['docker_url'] matches the docker_image of the matching ProfileDefinition."""
    result = ProfileCentricConverter().transform(publisher_multi_component_result)

    assert result["profiles"][0]["docker_url"] == DOCKER_IMAGE


@pytest.mark.business_logic
def test_profile_centric_transform_channels_grouped_by_channel(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """Both openssl and zlib appear under the 'tech' channel of the profile."""
    result = ProfileCentricConverter().transform(publisher_multi_component_result)

    channels = result["profiles"][0]["channels"]
    assert len(channels[CHANNEL_TECH]) == 2


@pytest.mark.business_logic
def test_profile_centric_transform_comp_entry_has_reference_and_url(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """Each component entry includes 'reference' and 'url' fields."""
    result = ProfileCentricConverter().transform(publisher_multi_component_result)

    comp_entry = result["profiles"][0]["channels"][CHANNEL_TECH][0]
    assert "reference" in comp_entry
    assert "url" in comp_entry


@pytest.mark.business_logic
def test_profile_centric_transform_include_links_flag_in_result(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """result['include_passport_links'] reflects the constructor parameter."""
    result = ProfileCentricConverter(include_passport_links=False).transform(
        publisher_multi_component_result
    )

    assert result["include_passport_links"] is False


@pytest.mark.business_logic
def test_profile_centric_converter_profile_with_no_components_does_not_raise() -> None:
    """ProfileDefinition with no matching ProfileBuilds produces no crash."""
    from autodoc.models.parsed_result import ParsedResult, ProfileDefinition
    from autodoc.models.component import Component
    from autodoc.models.release import Release
    from autodoc.models.conan_variant import ProfileBuild

    # Profile in definitions but not referenced by any component's ProfileBuild
    orphan_profile = ProfileDefinition(profile_name="hw-linux-riscv64-gcc12")

    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")  # different name
    release = Release(
        version="3.0.9",  # from openssl.properties
        platform="2.0",
        channel="tech",
        profile_builds=[pb],
    )
    component = Component(name="openssl", releases=[release])

    parsed = ParsedResult(
        generated_at="2024-01-01T00:00:00",
        platform_version="2.0",
        profile_definitions=[orphan_profile],
        components=[component],
    )

    converter = ProfileCentricConverter()
    view_model = converter.transform(parsed)  # must not raise

    assert view_model is not None
    # The orphan profile has no matching ProfileBuilds from non-header-only components,
    # so it must be absent from the profiles list (not cause a crash or spurious entry)
    profile_names = {p["profile_name"] for p in view_model["profiles"]}
    assert "hw-linux-riscv64-gcc12" not in profile_names


@pytest.mark.business_logic
def test_data_restructured_from_component_to_profile_axis(
    publisher_multi_channel_result,
) -> None:
    """
    BL-PCC-01
    Business Rule: ProfileCentricConverter converts the input structure
    Component→Release→Profile into Profile→channels dict→[components].

    Preconditions:
        - publisher_multi_channel_result with comp_alpha and comp_beta.

    Steps:
        1. Create ProfileCentricConverter(include_passport_links=False).
        2. Call transform().
        3. Inspect view["profiles"] structure.

    Expected Result:
        view contains "profiles" list; each profile has "profile_name" and
        "channels" (dict); each channel maps to a non-empty list of components.
    """
    converter = ProfileCentricConverter(include_passport_links=False)
    view = converter.transform(publisher_multi_channel_result)

    assert "profiles" in view, "view_model must contain key 'profiles'"
    assert len(view["profiles"]) > 0, "profiles must not be empty"

    profile = view["profiles"][0]
    assert "profile_name" in profile, "Each profile must have profile_name"
    assert "channels" in profile, "Each profile must have channels"
    channels = profile["channels"]
    assert isinstance(channels, dict), "channels must be a dict keyed by channel name"
    assert len(channels) > 0, "channels dict must not be empty"

    first_channel = next(iter(channels))
    components_list = channels[first_channel]
    assert isinstance(components_list, list), "Each channel value must be a list"
    assert len(components_list) > 0, "Channel must contain at least one component entry"
    comp_entry = components_list[0]
    assert "name" in comp_entry, "Component entry must have 'name'"
    assert "version" in comp_entry, "Component entry must have 'version'"


@pytest.mark.business_logic
def test_header_only_components_excluded_from_profile_metadata(
    publisher_multi_channel_result,
    publisher_profile_definition,
) -> None:
    """
    BL-PCC-02
    Business Rule: is_header_only on Component means these components are
    NOT used to determine profile conan_settings / docker_url.

    Preconditions:
        - publisher_multi_channel_result: comp_alpha (is_header_only=False)
          and comp_beta (is_header_only=True).

    Steps:
        1. Create ProfileCentricConverter and call transform().
        2. Find profile "hw-linux-x86_64-gcc10" in view["profiles"].
        3. Check conan_settings and docker_url.

    Expected Result:
        conan_settings matches publisher_profile_definition.conan_settings
        (sourced from comp_alpha only); value is non-empty.
    """
    converter = ProfileCentricConverter(include_passport_links=False)
    view = converter.transform(publisher_multi_channel_result)

    profile = next(
        (p for p in view["profiles"] if p["profile_name"] == "hw-linux-x86_64-gcc10"),
        None,
    )
    assert profile is not None, "Profile hw-linux-x86_64-gcc10 must be present"
    assert (
        profile["os"] == publisher_profile_definition.conan_settings["os"]
    ), "Profile os must come from the non-header-only component's ProfileDefinition"
    assert profile["os"] != "", "conan_settings['os'] must not be empty"


@pytest.mark.business_logic
def test_channels_within_profile_sorted_consistently(
    publisher_multi_channel_result,
) -> None:
    """
    BL-PCC-03
    Business Rule: Channels within a profile have a stable, alphabetical order
    to ensure identical HTML output on re-publication.

    Preconditions:
        - publisher_multi_channel_result has channels "fast" and "stable"
          for profile "hw-linux-x86_64-gcc10".

    Steps:
        1. Create ProfileCentricConverter and call transform().
        2. For each profile, extract the ordered channel names from the dict.

    Expected Result:
        list(channels.keys()) == sorted(list(channels.keys()))
    """
    converter = ProfileCentricConverter(include_passport_links=False)
    view = converter.transform(publisher_multi_channel_result)

    for profile in view["profiles"]:
        channel_names = list(profile["channels"].keys())
        assert channel_names == sorted(channel_names), (
            f"Channels in profile '{profile['profile_name']}' must be sorted, "
            f"got: {channel_names}"
        )


@pytest.mark.business_logic
def test_components_within_channel_sorted_by_name(
    publisher_multi_channel_result,
) -> None:
    """
    BL-PCC-04
    Business Rule: Components within a channel are sorted by name for
    deterministic output in Confluence.

    Preconditions:
        - publisher_multi_channel_result: channel "fast" has both alpha
          and beta listed; alpha < beta alphabetically.

    Steps:
        1. Create ProfileCentricConverter and call transform().
        2. For each profile and channel, check component name order.

    Expected Result:
        comp_names == sorted(comp_names) for every channel in every profile.
    """
    converter = ProfileCentricConverter(include_passport_links=False)
    view = converter.transform(publisher_multi_channel_result)

    for profile in view["profiles"]:
        for channel_name, comp_entries in profile["channels"].items():
            comp_names = [c["name"] for c in comp_entries]
            assert comp_names == sorted(comp_names), (
                f"Components in channel '{channel_name}' of profile "
                f"'{profile['profile_name']}' must be sorted: "
                f"expected {sorted(comp_names)}, got {comp_names}"
            )


@pytest.mark.business_logic
def test_passport_link_none_without_pattern(publisher_multi_channel_result) -> None:
    """
    BL-PCC-05
    Business Rule: Without a passport_page_pattern, passport_link is None
    for each component in every channel.

    Preconditions:
        - ProfileCentricConverter created with include_passport_links=False
          (or True with no pattern).

    Steps:
        1. Create ProfileCentricConverter(include_passport_links=False).
        2. Call transform().
        3. Check passport_link for all component entries.

    Expected Result:
        All passport_link values are None or "".
    """
    converter = ProfileCentricConverter(include_passport_links=False)
    view = converter.transform(publisher_multi_channel_result)

    for profile in view["profiles"]:
        for channel_name, comp_entries in profile["channels"].items():
            for comp_entry in comp_entries:
                link = comp_entry.get("passport_link")
                assert link is None or link == "", (
                    f"Without include_links=True, passport_link should be None/empty, "
                    f"got: {link!r}"
                )


@pytest.mark.business_logic
def test_passport_link_formatted_per_component_version(
    publisher_multi_channel_result,
) -> None:
    """
    BL-PCC-06
    Business Rule: With a pattern, each component in a channel receives a
    passport_link containing its name and version so that
    PassportPageRegistry.inject_links_for_profiles() can replace it.

    Preconditions:
        - publisher_multi_channel_result with comp_alpha (non-header-only).

    Steps:
        1. Create ProfileCentricConverter(include_passport_links=True,
           passport_page_pattern="/p/{component_name}/{release_version}").
        2. Call transform().
        3. Check that each comp_entry["passport_link"] contains name and version.

    Expected Result:
        At least one passport_link is non-None; every non-None link contains
        the entry's name and version.
    """
    converter = ProfileCentricConverter(
        include_passport_links=True,
        passport_page_pattern="/p/{component_name}/{release_version}",
    )
    view = converter.transform(publisher_multi_channel_result)

    found_any_link = False
    for profile in view["profiles"]:
        for channel_name, comp_entries in profile["channels"].items():
            for comp_entry in comp_entries:
                assert (
                    "passport_link" in comp_entry
                ), "When include_links=True, each component must have key passport_link"
                link = comp_entry["passport_link"]
                if link:
                    assert (
                        comp_entry["name"] in link
                    ), f"passport_link must contain component name '{comp_entry['name']}'"
                    assert (
                        comp_entry["version"] in link
                    ), f"passport_link must contain version '{comp_entry['version']}'"
                    found_any_link = True
    assert (
        found_any_link
    ), "At least one component should receive a non-empty passport_link"
