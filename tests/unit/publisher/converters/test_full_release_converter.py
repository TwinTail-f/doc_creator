"""Юнит-тесты для FullReleaseConverter."""

from __future__ import annotations

import pytest

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

COMP_NAME: str = "openssl"
COMP_ZLIB: str = "zlib"
COMP_DESCRIPTION: str = "TLS library"
COMP_ZLIB_DESCRIPTION: str = "Compression library"
PLATFORM_VERSION: str = "2.0"
DOCKER_IMAGE: str = "registry.example.com/build/linux-gcc10:latest"
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


from autodoc.models.parsed_result import ParsedResult as _ParsedResult


@pytest.mark.contract
def test_full_release_convert_returns_platform_version(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """result['platform_version'] соответствует platform_version исходного ParsedResult."""
    result = FullReleaseConverter().convert(publisher_multi_component_result)

    assert result["platform_version"] == PLATFORM_VERSION


@pytest.mark.business_logic
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
    assert descriptions_by_name[COMP_NAME] == COMP_DESCRIPTION
    assert descriptions_by_name[COMP_ZLIB] == COMP_ZLIB_DESCRIPTION


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
) -> None:
    """Сборки профиля обогащаются docker_image из соответствующего ProfileDefinition."""
    result = FullReleaseConverter().convert(publisher_multi_component_result)

    openssl_entry = next(c for c in result["components"] if c["name"] == COMP_NAME)
    first_release = openssl_entry["releases"][0]
    assert first_release["profile_builds"][0]["docker_image"] == DOCKER_IMAGE


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
    """
    Бизнес-правило: у компонента с is_header_only=True в view-model для всех
    его релизов profile_builds=[] (поле перенесено с Release на Component).

    Предусловия:
        - publisher_header_only_component имеет is_header_only=True;
          его вложенный релиз содержит непустой profile_builds.

    Шаги:
        1. Построить ParsedResult с header-only компонентом.
        2. Создать FullReleaseConverter(include_passport_links=False).
        3. Вызвать convert() и проверить view["components"][0]["releases"].

    Ожидаемый результат:
        Каждый release_view["profile_builds"] == [].
    """
    from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

    parsed = _ParsedResult(
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
    """
    Бизнес-правило: у компонента с is_header_only=False непустой profile_builds
    в view-model (если у релиза есть ProfileBuild).

    Предусловия:
        - publisher_parsed_result: компонент openssl с is_header_only=False
          и одним ProfileBuild.

    Шаги:
        1. Создать FullReleaseConverter и вызвать convert().
        2. Проверить release_view["profile_builds"] для openssl.

    Ожидаемый результат:
        len(release_view["profile_builds"]) > 0.
    """
    from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

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
    """
    Бизнес-правило: компоненты в view-model отсортированы по имени в алфавитном порядке.

    Предусловия:
        - publisher_multi_component_result содержит компоненты openssl и zlib.

    Шаги:
        1. Создать FullReleaseConverter и вызвать convert().
        2. Извлечь имена компонентов из view["components"].

    Ожидаемый результат:
        names == sorted(names).
    """
    from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

    converter = FullReleaseConverter(include_passport_links=False)
    view = converter.convert(publisher_multi_component_result)

    names = [c["name"] for c in view["components"]]
    assert names == sorted(
        names
    ), f"Components must be sorted alphabetically: expected {sorted(names)}, got {names}"


@pytest.mark.parametrize("flag", [True, False])
@pytest.mark.contract
def test_include_links_flag_propagated_to_view_model(publisher_parsed_result, flag: bool) -> None:
    """
    Бизнес-правило: значение include_passport_links, переданное в конструктор
    FullReleaseConverter, появляется без изменений в
    view_model["include_passport_links"].

    Предусловия:
        - доступен publisher_parsed_result.

    Шаги:
        1. Создать FullReleaseConverter(include_passport_links=flag).
        2. Вызвать convert().
        3. Проверить view["include_passport_links"].

    Ожидаемый результат:
        view["include_passport_links"] is flag (True или False в зависимости от параметра).
    """
    from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

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
    """
    Бизнес-правило: FullReleaseConverter.convert() сам по себе не добавляет
    поле passport_link / passport_versions ни в release_view, ни в comp_view,
    независимо от include_passport_links. Согласно докстрингу
    BaseReleaseConverter, эта ответственность полностью лежит на
    autodoc.publisher.page_manager.passport_link_injector.inject_links(),
    который применяется позже слоем стратегии и проверяется в
    tests/unit/publisher/page_manager/test_passport_registry.py.

    Предусловия:
        - publisher_parsed_result с одним компонентом и одним релизом.

    Шаги:
        1. Создать FullReleaseConverter(include_passport_links=True).
        2. Вызвать convert().
        3. Проверить, что ни "passport_link", ни "passport_versions" не
           встречаются в release_view или comp_view.

    Ожидаемый результат:
        Ни один из ключей не присутствует нигде в исходном выводе convert().
    """
    from autodoc.publisher.converters.full_release_converter import FullReleaseConverter

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
