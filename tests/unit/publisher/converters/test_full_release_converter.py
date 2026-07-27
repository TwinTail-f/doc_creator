"""Юнит-тесты для FullReleaseConverter."""

import pytest

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.parsed_result import ParsedResult, ProfileDefinition
from autodoc.publisher.converters.full_release_converter import FullReleaseConverter
from tests.unit.publisher.conftest import COMPONENT_NAME as COMP_NAME

UNKNOWN_PROFILE: str = "ghost"
UNKNOWN_OPTIONS_REF: str = "UNKNOWN_REF"


@pytest.fixture
def multi_result_with_unknown_profile(
    publisher_multi_component_result: ParsedResult,
) -> ParsedResult:
    """ParsedResult, где openssl 1.0.0 содержит дополнительный ProfileBuild с UNKNOWN_PROFILE."""
    ghost_pb = ProfileBuild(profile_name=UNKNOWN_PROFILE, exists=True, variants=[])
    original_rel = publisher_multi_component_result.components[0].releases[0]
    patched_rel = original_rel.model_copy(
        update={"profile_builds": original_rel.profile_builds + [ghost_pb]}
    )
    original_comp = publisher_multi_component_result.components[0]
    patched_comp = original_comp.model_copy(update={"releases": [patched_rel]})
    components = [patched_comp] + list(publisher_multi_component_result.components[1:])
    return publisher_multi_component_result.model_copy(update={"components": components})


@pytest.mark.contract
def test_full_release_convert_returns_platform_version(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """result['platform_version'] соответствует platform_version исходного ParsedResult."""
    result = FullReleaseConverter().convert(publisher_multi_component_result)

    assert result["platform_version"] == publisher_multi_component_result.platform_version


@pytest.mark.contract
def test_full_release_convert_contains_all_components(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """result['components'] содержит по одной записи для каждого компонента входных данных."""
    result = FullReleaseConverter().convert(publisher_multi_component_result)

    assert len(result["components"]) == 2


@pytest.mark.contract
def test_full_release_convert_component_has_name_and_description(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """Каждая запись компонента содержит поля name и description."""
    result = FullReleaseConverter().convert(publisher_multi_component_result)

    descriptions_by_name = {c["name"]: c["description"] for c in result["components"]}
    for component in publisher_multi_component_result.components:
        assert descriptions_by_name[component.name] == component.description


@pytest.mark.contract
def test_full_release_convert_component_has_releases(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """Запись компонента openssl содержит оба его релиза."""
    result = FullReleaseConverter().convert(publisher_multi_component_result)

    openssl_entry = next(c for c in result["components"] if c["name"] == COMP_NAME)
    assert len(openssl_entry["releases"]) == 2


@pytest.mark.business_logic
def test_full_release_convert_profile_build_has_docker_image(
    publisher_multi_component_result: ParsedResult,
    publisher_profile_definition: ProfileDefinition,
) -> None:
    """Сборки профиля обогащаются docker_image из соответствующего ProfileDefinition."""
    result = FullReleaseConverter().convert(publisher_multi_component_result)

    openssl_entry = next(c for c in result["components"] if c["name"] == COMP_NAME)
    first_release = openssl_entry["releases"][0]
    assert (
        first_release["profile_builds"][0]["docker_image"]
        == publisher_profile_definition.docker_image
    )


@pytest.mark.business_logic
def test_full_release_convert_profile_build_unknown_profile_gives_empty_fields(
    multi_result_with_unknown_profile: ParsedResult,
) -> None:
    """ProfileBuild с отсутствующим profile_name даёт docker_image='' и conan_settings={}."""
    result = FullReleaseConverter().convert(multi_result_with_unknown_profile)

    openssl_entry = next(c for c in result["components"] if c["name"] == COMP_NAME)
    ghost_pb = next(
        pb
        for pb in openssl_entry["releases"][0]["profile_builds"]
        if pb["profile_name"] == UNKNOWN_PROFILE
    )
    assert ghost_pb["docker_image"] == ""
    assert ghost_pb["conan_settings"] == {}


@pytest.mark.business_logic
def test_full_release_convert_header_only_flag_comes_from_component(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """is_header_only в каждой view-model релиза берётся из флага компонента-владельца."""
    # Помечаем компонент openssl как header-only
    original_comp = publisher_multi_component_result.components[0]
    patched_comp = original_comp.model_copy(update={"is_header_only": True})
    patched_result = publisher_multi_component_result.model_copy(
        update={
            "components": [patched_comp] + list(publisher_multi_component_result.components[1:])
        }
    )
    result = FullReleaseConverter().convert(patched_result)

    openssl_entry = next(c for c in result["components"] if c["name"] == COMP_NAME)
    # Все релизы header-only компонента несут is_header_only=True
    assert all(r["is_header_only"] for r in openssl_entry["releases"])


@pytest.mark.business_logic
def test_full_release_convert_release_with_no_profile_builds_has_empty_list(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """Релиз без profile_builds даёт пустой список profile_builds в view-model."""
    result = FullReleaseConverter().convert(publisher_multi_component_result)

    openssl_entry = next(c for c in result["components"] if c["name"] == COMP_NAME)
    empty_pb_release = next(r for r in openssl_entry["releases"] if not r["profile_builds"])
    assert empty_pb_release["profile_builds"] == []


@pytest.mark.business_logic
def test_header_only_component_has_no_profile_builds_in_view(
    publisher_header_only_component,
    publisher_profile_definition,
) -> None:
    """У компонента с is_header_only=True все его релизы получают profile_builds=[]
    в view-model, даже если у вложенного release они непустые: это поле по смыслу
    принадлежит Component, а не Release."""
    parsed = ParsedResult(
        generated_at="2024-01-15T12:00:00",
        platform_version="2.0",
        profile_definitions=[publisher_profile_definition],
        components=[publisher_header_only_component],
    )

    converter = FullReleaseConverter(include_passport_links=False)
    view = converter.convert(parsed)

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
    """У компонента с is_header_only=False profile_builds в view-model остаётся
    непустым, если у соответствующего release есть хотя бы один ProfileBuild."""
    comp = publisher_parsed_result.components[0]
    assert comp.is_header_only is False, "Fixture must have is_header_only=False"
    assert len(comp.releases[0].profile_builds) > 0, "Fixture must have non-empty profile_builds"

    converter = FullReleaseConverter(include_passport_links=False)
    view = converter.convert(publisher_parsed_result)

    comp_view = view["components"][0]
    release_view = comp_view["releases"][0]
    assert (
        len(release_view["profile_builds"]) > 0
    ), "Non-header-only component must have non-empty profile_builds in view"


@pytest.mark.business_logic
def test_components_sorted_alphabetically_in_view(
    publisher_multi_component_result,
) -> None:
    """Компоненты в view-model отсортированы по имени в алфавитном порядке. Входные
    данные предварительно переставляются в обратном порядке, иначе тест не отличит
    настоящую сортировку от порядка вставки, случайно совпадающего с алфавитным."""
    reversed_result = publisher_multi_component_result.model_copy(
        update={"components": list(reversed(publisher_multi_component_result.components))}
    )
    converter = FullReleaseConverter(include_passport_links=False)
    view = converter.convert(reversed_result)

    names = [c["name"] for c in view["components"]]
    assert names == sorted(
        names
    ), f"Components must be sorted alphabetically: expected {sorted(names)}, got {names}"


@pytest.mark.parametrize("flag", [True, False])
@pytest.mark.contract
def test_include_links_flag_propagated_to_view_model(publisher_parsed_result, flag: bool) -> None:
    """view['include_passport_links'] равен значению include_passport_links, переданному в конструктор FullReleaseConverter."""
    converter = FullReleaseConverter(include_passport_links=flag)
    view = converter.convert(publisher_parsed_result)

    assert "include_passport_links" in view, "view_model must contain key include_passport_links"
    assert (
        view["include_passport_links"] is flag
    ), f"include_passport_links should be {flag}, got {view['include_passport_links']}"


@pytest.mark.business_logic
def test_no_passport_link_field_added_by_converter_itself(
    publisher_parsed_result,
) -> None:
    """FullReleaseConverter.convert() сам по себе не добавляет поле passport_link /
    passport_versions ни в release_view, ни в comp_view, даже при
    include_passport_links=True: согласно докстрингу BaseReleaseConverter, эта
    ответственность полностью лежит на inject_links(), который применяется позже
    слоем стратегии (см. tests/unit/publisher/page_manager/test_passport_registry.py)."""
    converter = FullReleaseConverter(include_passport_links=True)
    view = converter.convert(publisher_parsed_result)

    for comp_view in view["components"]:
        assert "passport_versions" not in comp_view, (
            "passport_versions must NOT be set by the converter; "
            "it is injected later by inject_links()"
        )
        for release_view in comp_view["releases"]:
            assert "passport_link" not in release_view, (
                "passport_link must NOT be set by the converter; "
                "it is injected later by inject_links()"
            )


@pytest.mark.business_logic
def test_full_release_convert_variant_with_unknown_options_ref_has_empty_conan_options(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """Вариант со options_ref, отсутствующим в total_option_sets, получает пустой conan_options."""
    original_comp = publisher_multi_component_result.components[0]
    original_rel = original_comp.releases[0]
    original_pb = original_rel.profile_builds[0]
    original_variant = original_pb.variants[0]
    unknown_variant = original_variant.model_copy(update={"options_ref": UNKNOWN_OPTIONS_REF})
    patched_pb = original_pb.model_copy(update={"variants": [unknown_variant]})
    patched_rel = original_rel.model_copy(update={"profile_builds": [patched_pb]})
    patched_comp = original_comp.model_copy(
        update={"releases": [patched_rel] + list(original_comp.releases[1:])}
    )
    components = [patched_comp] + list(publisher_multi_component_result.components[1:])
    patched_result = publisher_multi_component_result.model_copy(update={"components": components})

    result = FullReleaseConverter().convert(patched_result)

    openssl_entry = next(c for c in result["components"] if c["name"] == COMP_NAME)
    variant_view = openssl_entry["releases"][0]["profile_builds"][0]["variants"][0]
    assert variant_view.conan_options == {}


@pytest.mark.business_logic
def test_full_release_convert_empty_components_gives_empty_list(publisher_parsed_result) -> None:
    """Пустой список компонентов даёт пустой список components в результирующей view-model."""
    patched = publisher_parsed_result.model_copy(update={"components": []})

    result = FullReleaseConverter().convert(patched)

    assert result["components"] == []
