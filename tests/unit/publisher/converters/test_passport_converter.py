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


@pytest.mark.business_logic
def test_passport_transform_raises_on_unknown_component(publisher_parsed_result: ParsedResult
) -> None:
    """transform() raises ValueError when the requested component does not exist."""
    converter = PassportConverter(UNKNOWN_COMPONENT, RELEASE_VERSION)

    with pytest.raises(ValueError):
        converter.transform(publisher_parsed_result)


@pytest.mark.business_logic
def test_passport_transform_raises_on_unknown_version(publisher_parsed_result: ParsedResult
) -> None:
    """transform() raises ValueError when the release version is not found."""
    converter = PassportConverter(COMP_NAME, UNKNOWN_VERSION)

    with pytest.raises(ValueError):
        converter.transform(publisher_parsed_result)


@pytest.mark.contract
def test_passport_transform_returns_platform_version(publisher_parsed_result: ParsedResult
) -> None:
    """result['platform_version'] matches the platform_version of the ParsedResult."""
    result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
        publisher_parsed_result
    )

    assert result["platform_version"] == PLATFORM_VERSION


@pytest.mark.contract
def test_passport_transform_returns_component_fields(publisher_parsed_result: ParsedResult
) -> None:
    """result['component'] contains the component's name and description."""
    result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
        publisher_parsed_result
    )

    assert result["component"]["name"] == COMP_NAME
    assert result["component"]["description"] == COMP_DESCRIPTION


@pytest.mark.contract
def test_passport_transform_returns_release_version(publisher_parsed_result: ParsedResult
) -> None:
    """result['release']['version'] matches the requested release version."""
    result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
        publisher_parsed_result
    )

    assert result["release"]["version"] == RELEASE_VERSION


@pytest.mark.contract
def test_passport_transform_returns_release_channel(publisher_parsed_result: ParsedResult
) -> None:
    """result['release']['channel'] matches the release's channel."""
    result = PassportConverter(COMP_NAME, RELEASE_VERSION).transform(
        publisher_parsed_result
    )

    assert result["release"]["channel"] == CHANNEL_TECH



# ---------------------------------------------------------------------------
# BL-PC-01 … BL-PC-10  (Part 1 of the Publisher BL test plan)
# ---------------------------------------------------------------------------

from autodoc.models.conan_variant import ConanVariant
from autodoc.models.options import TotalOptionsSet


@pytest.mark.business_logic
def test_variant_options_linked_by_options_ref_id(
    publisher_parsed_result: ParsedResult,
) -> None:
    """
    BL-PC-01
    Business Rule: ConanVariant.options_ref is used to find the matching
    TotalOptionsSet by id.  If they match the variant in the view model
    contains the correct conan_options.

    Preconditions:
        - publisher_parsed_result has release with variant.options_ref == "opt-set-1"
        - TotalOptionsSet(id="opt-set-1", options={"shared": "True", "fPIC": "True"})

    Steps:
        1. Create PassportConverter for openssl / 1.0.0
        2. Call transform()
        3. Inspect variants[0].conan_options

    Expected Result:
        variants[0].conan_options == {"shared": "True", "fPIC": "True"}
    """
    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.transform(publisher_parsed_result)

    profile_builds = view["release"]["profile_builds"]
    assert len(profile_builds) == 1, "There should be one profile_build"
    variants = profile_builds[0]["variants"]
    assert len(variants) == 1, "There should be one variant"

    variant_view = variants[0]
    assert variant_view.conan_options == {
        "shared": "True",
        "fPIC": "True",
    }, "Variant conan_options must correspond to the TotalOptionsSet with matching id"


@pytest.mark.business_logic
def test_variant_with_unknown_options_ref_has_empty_options(
    publisher_parsed_result: ParsedResult,
) -> None:
    """
    BL-PC-02
    Business Rule: If options_ref is not found in total_option_sets,
    conan_options={}; no exception should be raised.

    Preconditions:
        - publisher_parsed_result with one variant whose options_ref is replaced
          with a string not present in any TotalOptionsSet.

    Steps:
        1. Build a patched ParsedResult where variant.options_ref == "NONEXISTENT_REF"
        2. Create PassportConverter and call transform()
        3. Inspect variants[0].conan_options

    Expected Result:
        variants[0].conan_options == {}  (no exception raised)
    """
    variant_unknown = ConanVariant(
        package_id="abc123",
        build_url="https://ci.example.com/build/42",
        build_date="2024-01-15",
        options_ref="NONEXISTENT_REF",
    )
    orig_pb = publisher_parsed_result.components[0].releases[0].profile_builds[0]
    patched_pb = orig_pb.model_copy(update={"variants": [variant_unknown]})
    orig_rel = publisher_parsed_result.components[0].releases[0]
    patched_rel = orig_rel.model_copy(update={"profile_builds": [patched_pb]})
    orig_comp = publisher_parsed_result.components[0]
    patched_comp = orig_comp.model_copy(update={"releases": [patched_rel]})
    patched_result = publisher_parsed_result.model_copy(
        update={"components": [patched_comp]}
    )

    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.transform(patched_result)

    variants = view["release"]["profile_builds"][0]["variants"]
    assert len(variants) == 1
    assert (
        variants[0].conan_options == {}
    ), "Unknown options_ref should result in empty conan_options, not an exception"


@pytest.mark.business_logic
def test_install_options_built_from_build_option_sets_not_total(
    publisher_parsed_result: ParsedResult,
) -> None:
    """
    BL-PC-03
    Business Rule: install_options string is built from build_option_sets
    (what the user passes), not from total_option_sets.

    Preconditions:
        - publisher_parsed_result with build_option_sets[0].options ==
          "openssl/*:shared=True, openssl/*:fPIC=True"

    Steps:
        1. Create PassportConverter and call transform()
        2. Inspect variants[0].install_options

    Expected Result:
        install_options contains "-o" and "shared" and "openssl"
    """
    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.transform(publisher_parsed_result)

    variant_view = view["release"]["profile_builds"][0]["variants"][0]
    install_opts = variant_view.install_options

    assert "-o" in install_opts, "install_options must contain the -o flag"
    assert "shared" in install_opts, "install_options must contain the key 'shared'"
    assert (
        "openssl" in install_opts
    ), "install_options must use the component name from build_option_sets"


@pytest.mark.contract
def test_variants_are_conan_variant_view_namedtuples(
    publisher_parsed_result: ParsedResult,
) -> None:
    """
    BL-PC-04
    Business Rule: Each variant in the view model is a ConanVariantView
    (dataclass), not the original ConanVariant.

    Preconditions:
        - publisher_parsed_result with one variant in the release.

    Steps:
        1. Create PassportConverter and call transform()
        2. Check type of each variant in profile_builds

    Expected Result:
        isinstance(variant, ConanVariantView) is True;
        variant has fields: package_id, build_url, conan_options, install_options.
    """
    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.transform(publisher_parsed_result)

    for pb in view["release"]["profile_builds"]:
        for variant in pb["variants"]:
            assert isinstance(
                variant, ConanVariantView
            ), f"Expected ConanVariantView, got {type(variant).__name__}"
            assert hasattr(variant, "package_id")
            assert hasattr(variant, "build_url")
            assert hasattr(variant, "conan_options")
            assert hasattr(variant, "install_options")


@pytest.mark.business_logic
def test_profile_build_enriched_with_conan_settings_from_profile_definition(
    publisher_parsed_result: ParsedResult,
    publisher_profile_definition,
) -> None:
    """
    BL-PC-05
    Business Rule: conan_settings is taken from ProfileDefinition (by matching
    profile_name), not from the ProfileBuild itself.

    Preconditions:
        - publisher_parsed_result includes ProfileDefinition for
          "hw-linux-x86_64-gcc10" with conan_settings.

    Steps:
        1. Create PassportConverter and call transform()
        2. Check profile_builds[0]["conan_settings"]

    Expected Result:
        profile_builds[0]["conan_settings"] == publisher_profile_definition.conan_settings
    """
    assert any(
        pd.profile_name == "hw-linux-x86_64-gcc10"
        for pd in publisher_parsed_result.profile_definitions
    ), "Fixture must contain ProfileDefinition for hw-linux-x86_64-gcc10"

    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.transform(publisher_parsed_result)

    pb_view = view["release"]["profile_builds"][0]
    assert pb_view["profile_name"] == "hw-linux-x86_64-gcc10"
    assert (
        pb_view["conan_settings"] == publisher_profile_definition.conan_settings
    ), "conan_settings must be taken from ProfileDefinition, not from ProfileBuild"


@pytest.mark.business_logic
def test_profile_build_enriched_with_docker_image_from_profile_definition(
    publisher_parsed_result: ParsedResult,
    publisher_profile_definition,
) -> None:
    """
    BL-PC-06
    Business Rule: docker_image is taken from ProfileDefinition.

    Preconditions:
        - publisher_parsed_result includes ProfileDefinition with docker_image set.

    Steps:
        1. Create PassportConverter and call transform()
        2. Check profile_builds[0]["docker_image"]

    Expected Result:
        profile_builds[0]["docker_image"] == publisher_profile_definition.docker_image
        and it is non-empty.
    """
    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.transform(publisher_parsed_result)

    pb_view = view["release"]["profile_builds"][0]
    assert (
        pb_view["docker_image"] == publisher_profile_definition.docker_image
    ), "docker_image must be taken from ProfileDefinition"
    assert pb_view["docker_image"] != "", "docker_image must not be empty"


@pytest.mark.business_logic
def test_missing_profile_definition_gives_empty_settings_not_error(
    publisher_parsed_result: ParsedResult,
) -> None:
    """
    BL-PC-07
    Business Rule: If ProfileDefinition is missing for a profile,
    conan_settings={} and docker_image=""; no exception is raised.

    Preconditions:
        - ParsedResult with profile_definitions=[]

    Steps:
        1. Patch ParsedResult removing all ProfileDefinitions
        2. Create PassportConverter and call transform()
        3. Inspect profile_builds[0]

    Expected Result:
        conan_settings == {} and docker_image == "" without KeyError or AttributeError.
    """
    patched_result = publisher_parsed_result.model_copy(
        update={"profile_definitions": []}
    )

    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.transform(patched_result)

    pb_view = view["release"]["profile_builds"][0]
    assert (
        pb_view["conan_settings"] == {}
    ), "Missing ProfileDefinition should result in conan_settings={}"
    assert (
        pb_view["docker_image"] == ""
    ), "Missing ProfileDefinition should result in docker_image=''"


@pytest.mark.business_logic
def test_profile_builds_ordered_by_profile_name(
    publisher_two_profile_parsed_result: ParsedResult,
) -> None:
    """
    BL-PC-08
    Business Rule: profile_builds in the view model are ordered alphabetically
    by profile name, regardless of the order they appear in Release.

    Preconditions:
        - publisher_two_profile_parsed_result has pb_x86 (hw-linux-x86_64-gcc10)
          and pb_arm (hw-linux-arm64-gcc10) added in x86 / arm order.

    Steps:
        1. Create PassportConverter(component_name="mylib", release_version="1.0.0")
        2. Call transform()
        3. Extract profile_name list from profile_builds

    Expected Result:
        profile_names == sorted(profile_names) and profile_names[0] starts with
        "hw-linux-arm64" (arm64 sorts before x86_64).
    """
    converter = PassportConverter(component_name="mylib", release_version="1.0.0")
    view = converter.transform(publisher_two_profile_parsed_result)

    names = [pb["profile_name"] for pb in view["release"]["profile_builds"]]
    assert names == sorted(
        names
    ), f"profile_builds must be sorted by name, got: {names}"
    assert (
        names[0] == "hw-linux-arm64-gcc10"
    ), "arm64 should be first (alphabetically before x86_64)"


@pytest.mark.business_logic
def test_legacy_contents_initially_empty_dict(
    publisher_parsed_result: ParsedResult,
) -> None:
    """
    BL-PC-09
    Business Rule: On first publication legacy_contents={}; no inherited content.
    The converter returns legacy_contents={} — legacy data is injected OUTSIDE
    by the strategy, not by the converter.

    Preconditions:
        - Standard publisher_parsed_result (no prior legacy injection).

    Steps:
        1. Create PassportConverter and call transform()
        2. Inspect view["legacy_contents"]

    Expected Result:
        "legacy_contents" key present and value == {}.
    """
    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.transform(publisher_parsed_result)

    assert "legacy_contents" in view, "legacy_contents field must be present"
    assert (
        view["legacy_contents"] == {}
    ), "Without injection, legacy_contents must be an empty dict"


@pytest.mark.business_logic
def test_legacy_contents_key_is_platform_version_string(
    publisher_parsed_result: ParsedResult,
) -> None:
    """
    BL-PC-10
    Business Rule: Keys in legacy_contents are platform version strings
    (e.g. "2.1", "2.0").

    Preconditions:
        - converter.transform() ran successfully; view["legacy_contents"] == {}.

    Steps:
        1. Create PassportConverter and call transform()
        2. Simulate strategy injection: set view["legacy_contents"] to a
           dict with string keys like "2.1", "1.9"
        3. Verify each key is a str containing a digit.

    Expected Result:
        All keys are str and contain at least one digit character.
    """
    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.transform(publisher_parsed_result)

    legacy = {
        "2.1": "<p>Legacy content for platform 2.1</p>",
        "1.9": "<p>Legacy content for platform 1.9</p>",
    }
    view["legacy_contents"] = legacy

    for key in view["legacy_contents"]:
        assert isinstance(
            key, str
        ), f"Key of legacy_contents must be a string, got {type(key)}"
        assert any(
            c.isdigit() for c in key
        ), f"Key '{key}' must contain a platform version digit"
