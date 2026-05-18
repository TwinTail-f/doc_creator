"""Unit tests for FullReleaseConverter."""

from __future__ import annotations

import pytest

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

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
    patched_comp = original_comp.model_copy(update={"releases": [patched_rel]})
    components = [patched_comp] + list(publisher_multi_component_result.components[1:])
    return publisher_multi_component_result.model_copy(
        update={"components": components}
    )


# ── FullReleaseConverter ────────────────────────────────────────────────────


class TestFullReleaseConverter:
    """Tests for FullReleaseConverter.transform()."""

    @pytest.mark.contract
    def test_full_release_transform_returns_platform_version(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """result['platform_version'] matches the ParsedResult platform_version."""
        result = FullReleaseConverter().transform(publisher_multi_component_result)

        assert result["platform_version"] == PLATFORM_VERSION

    @pytest.mark.business_logic
    def test_full_release_transform_contains_all_components(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """result['components'] contains one entry for each component in the data."""
        result = FullReleaseConverter().transform(publisher_multi_component_result)

        assert len(result["components"]) == 2

    @pytest.mark.contract
    def test_full_release_transform_component_has_name_and_description(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """Each component entry carries its name and description fields."""
        result = FullReleaseConverter().transform(publisher_multi_component_result)

        names = {c["name"] for c in result["components"]}
        assert COMP_NAME in names
        assert COMP_ZLIB in names

    @pytest.mark.contract
    def test_full_release_transform_component_has_releases(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """The openssl component entry exposes both of its releases."""
        result = FullReleaseConverter().transform(publisher_multi_component_result)

        openssl_entry = next(c for c in result["components"] if c["name"] == COMP_NAME)
        assert len(openssl_entry["releases"]) == 2

    @pytest.mark.business_logic
    def test_full_release_transform_include_links_false(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """result['include_passport_links'] is False when the converter is created with False."""
        result = FullReleaseConverter(include_passport_links=False).transform(
            publisher_multi_component_result
        )

        assert result["include_passport_links"] is False

    @pytest.mark.business_logic
    def test_full_release_transform_include_links_true_by_default(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """result['include_passport_links'] is True when using the default constructor."""
        result = FullReleaseConverter().transform(publisher_multi_component_result)

        assert result["include_passport_links"] is True

    @pytest.mark.business_logic
    def test_full_release_transform_profile_build_has_docker_image(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """Profile builds are enriched with docker_image from the matching ProfileDefinition."""
        result = FullReleaseConverter().transform(publisher_multi_component_result)

        openssl_entry = next(c for c in result["components"] if c["name"] == COMP_NAME)
        first_release = openssl_entry["releases"][0]
        assert first_release["profile_builds"][0]["docker_image"] == DOCKER_IMAGE

    @pytest.mark.business_logic
    def test_full_release_transform_profile_build_unknown_profile_gives_empty_fields(
        self, multi_result_with_unknown_profile: ParsedResult
    ) -> None:
        """A ProfileBuild with an absent profile_name yields docker_image='' and conan_settings={}."""
        result = FullReleaseConverter().transform(multi_result_with_unknown_profile)

        openssl_entry = next(c for c in result["components"] if c["name"] == COMP_NAME)
        ghost_pb = next(
            pb
            for pb in openssl_entry["releases"][0]["profile_builds"]
            if pb["profile_name"] == UNKNOWN_PROFILE
        )
        assert ghost_pb["docker_image"] == ""
        assert ghost_pb["conan_settings"] == {}

    @pytest.mark.business_logic
    def test_full_release_transform_header_only_flag_comes_from_component(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """is_header_only in each release view model reflects the parent component's flag."""
        # Mark openssl component as header-only
        original_comp = publisher_multi_component_result.components[0]
        patched_comp = original_comp.model_copy(update={"is_header_only": True})
        patched_result = publisher_multi_component_result.model_copy(
            update={
                "components": [patched_comp]
                + list(publisher_multi_component_result.components[1:])
            }
        )
        result = FullReleaseConverter().transform(patched_result)

        openssl_entry = next(c for c in result["components"] if c["name"] == COMP_NAME)
        # All releases of a header-only component carry is_header_only=True
        assert all(r["is_header_only"] for r in openssl_entry["releases"])

    @pytest.mark.business_logic
    def test_full_release_transform_release_with_no_profile_builds_has_empty_list(
        self, publisher_multi_component_result: ParsedResult
    ) -> None:
        """A release with no profile_builds produces an empty profile_builds list in the view model."""
        result = FullReleaseConverter().transform(publisher_multi_component_result)

        openssl_entry = next(c for c in result["components"] if c["name"] == COMP_NAME)
        empty_pb_release = next(
            r for r in openssl_entry["releases"] if not r["profile_builds"]
        )
        assert empty_pb_release["profile_builds"] == []


# ---------------------------------------------------------------------------
# BL-FRC-01 … BL-FRC-07  (Part 1 of the Publisher BL test plan)
# ---------------------------------------------------------------------------

from autodoc.models.component import Component
from autodoc.models.parsed_result import ParsedResult as _ParsedResult

_PASSPORT_PATTERN = "/pages/{component_name}/{release_version}"


@pytest.mark.business_logic
def test_header_only_component_has_no_profile_builds_in_view(
    publisher_header_only_component,
    publisher_profile_definition,
) -> None:
    """
    BL-FRC-01
    Business Rule: Component with is_header_only=True has profile_builds=[]
    in the view model for all its releases (field moved from Release to Component).

    Preconditions:
        - publisher_header_only_component has is_header_only=True;
          its embedded release contains non-empty profile_builds.

    Steps:
        1. Build ParsedResult with the header-only component.
        2. Create FullReleaseConverter(include_passport_links=False).
        3. Call transform() and inspect view["components"][0]["releases"].

    Expected Result:
        Every release_view["profile_builds"] == [].
    """
    from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

    parsed = _ParsedResult(
        generated_at="2024-01-15T12:00:00",
        platform_version="2.0",
        profile_definitions=[publisher_profile_definition],
        components=[publisher_header_only_component],
    )

    converter = FullReleaseConverter(include_passport_links=False)
    view = converter.transform(parsed)

    comp_view = view["components"][0]
    assert comp_view["name"] == "eigen"
    for release_view in comp_view["releases"]:
        assert (
            release_view["profile_builds"] == []
        ), "header-only component must not have profile_builds in view model"


@pytest.mark.business_logic
def test_non_header_only_component_has_profile_builds(
    publisher_parsed_result,
) -> None:
    """
    BL-FRC-02
    Business Rule: Component with is_header_only=False has non-empty
    profile_builds in the view model (when the release has a ProfileBuild).

    Preconditions:
        - publisher_parsed_result: openssl component with is_header_only=False
          and one ProfileBuild.

    Steps:
        1. Create FullReleaseConverter and call transform().
        2. Check release_view["profile_builds"] for openssl.

    Expected Result:
        len(release_view["profile_builds"]) > 0.
    """
    from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

    comp = publisher_parsed_result.components[0]
    assert comp.is_header_only is False, "Fixture must have is_header_only=False"
    assert (
        len(comp.releases[0].profile_builds) > 0
    ), "Fixture must have non-empty profile_builds"

    converter = FullReleaseConverter(include_passport_links=False)
    view = converter.transform(publisher_parsed_result)

    comp_view = view["components"][0]
    release_view = comp_view["releases"][0]
    assert (
        len(release_view["profile_builds"]) > 0
    ), "Non-header-only component must have non-empty profile_builds in view"


@pytest.mark.business_logic
def test_components_sorted_alphabetically_in_view(
    publisher_multi_component_result,
) -> None:
    """
    BL-FRC-03
    Business Rule: Components in view model are sorted alphabetically by name.

    Preconditions:
        - publisher_multi_component_result has openssl and zlib components.

    Steps:
        1. Create FullReleaseConverter and call transform().
        2. Extract component names from view["components"].

    Expected Result:
        names == sorted(names).
    """
    from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

    converter = FullReleaseConverter(include_passport_links=False)
    view = converter.transform(publisher_multi_component_result)

    names = [c["name"] for c in view["components"]]
    assert names == sorted(
        names
    ), f"Components must be sorted alphabetically: expected {sorted(names)}, got {names}"


@pytest.mark.parametrize("flag", [True, False])
@pytest.mark.business_logic
def test_include_links_flag_propagated_to_view_model(
    publisher_parsed_result, flag: bool
) -> None:
    """
    BL-FRC-04
    Business Rule: The include_passport_links value passed to the
    FullReleaseConverter constructor appears exactly in
    view_model["include_passport_links"].

    Preconditions:
        - publisher_parsed_result available.

    Steps:
        1. Create FullReleaseConverter(include_passport_links=flag).
        2. Call transform().
        3. Check view["include_passport_links"].

    Expected Result:
        view["include_passport_links"] is flag (True or False depending on param).
    """
    from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

    converter = FullReleaseConverter(include_passport_links=flag)
    view = converter.transform(publisher_parsed_result)

    assert (
        "include_passport_links" in view
    ), "view_model must contain key include_passport_links"
    assert (
        view["include_passport_links"] is flag
    ), f"include_passport_links should be {flag}, got {view['include_passport_links']}"


@pytest.mark.business_logic
def test_passport_link_placeholder_present_when_include_links_true(
    publisher_parsed_result,
) -> None:
    """
    BL-FRC-05
    Business Rule: When include_links=True each release has a passport_link
    key (may be None if pattern is unset, but the key must exist).

    Preconditions:
        - publisher_parsed_result with one component and one release.

    Steps:
        1. Create FullReleaseConverter(include_passport_links=True).
        2. Call transform().
        3. Check that "passport_link" key is present in each release_view.

    Expected Result:
        "passport_link" in release_view for every component/release.
    """
    from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

    converter = FullReleaseConverter(include_passport_links=True)
    view = converter.transform(publisher_parsed_result)

    for comp_view in view["components"]:
        for release_view in comp_view["releases"]:
            assert (
                "passport_link" in release_view
            ), "When include_links=True, passport_link key must be present in release_view"


@pytest.mark.business_logic
def test_no_passport_link_when_include_links_false(publisher_parsed_result) -> None:
    """
    BL-FRC-06
    Business Rule: When include_links=False the passport_link field is None.

    Preconditions:
        - publisher_parsed_result available.

    Steps:
        1. Create FullReleaseConverter(include_passport_links=False).
        2. Call transform().
        3. Check passport_link value in each release_view.

    Expected Result:
        release_view["passport_link"] is None or "" for every release.
    """
    from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

    converter = FullReleaseConverter(include_passport_links=False)
    view = converter.transform(publisher_parsed_result)

    for comp_view in view["components"]:
        for release_view in comp_view["releases"]:
            passport_link = release_view.get("passport_link")
            assert (
                passport_link is None or passport_link == ""
            ), "When include_links=False, passport_link should be None or empty"


@pytest.mark.business_logic
def test_passport_link_formatted_with_component_name_and_version(
    publisher_parsed_result,
) -> None:
    """
    BL-FRC-07
    Business Rule: When a passport_page_pattern is provided, the placeholder
    link contains the component name and version so that
    PassportPageRegistry.inject_links() can match and replace it.

    Preconditions:
        - publisher_parsed_result with openssl / 1.0.0.
        - FullReleaseConverter configured with include_passport_links=True
          and a known passport_page_pattern.

    Steps:
        1. Create FullReleaseConverter with include_passport_links=True and
           passport_page_pattern="/pages/{component_name}/{release_version}".
        2. Call transform().
        3. Extract passport_link from openssl release_view.

    Expected Result:
        passport_link contains "openssl" and "1.0.0".
    """
    from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

    converter = FullReleaseConverter(
        include_passport_links=True,
        passport_page_pattern=_PASSPORT_PATTERN,
    )
    view = converter.transform(publisher_parsed_result)

    comp = publisher_parsed_result.components[0]
    comp_view = next(c for c in view["components"] if c["name"] == comp.name)
    release_view = comp_view["releases"][0]

    assert "passport_link" in release_view
    link = release_view["passport_link"]
    assert (
        link is not None
    ), "With a pattern and include_links=True, link must not be None"
    assert comp.name in link, f"passport_link must contain component name '{comp.name}'"
    assert (
        comp.releases[0].version in link
    ), f"passport_link must contain version '{comp.releases[0].version}'"
