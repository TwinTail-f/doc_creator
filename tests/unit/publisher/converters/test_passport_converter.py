"""Юнит-тесты для PassportConverter."""
import pytest

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.converters.passport_converter import PassportConverter
from autodoc.publisher.view_models.passports import ConanVariantView
from tests.unit.publisher.conftest import CI_BUILD_URL

COMP_NAME: str = "openssl"
RELEASE_VERSION: str = "1.0.0"
CHANNEL_TECH: str = "tech"
PLATFORM_VERSION: str = "2.0"
COMP_DESCRIPTION: str = "OpenSSL TLS/SSL library"
UNKNOWN_COMPONENT: str = "nonexistent"
UNKNOWN_VERSION: str = "9.9.9"


@pytest.fixture
def converter_parsed_result_missing_profile(
    publisher_parsed_result: ParsedResult,
) -> ParsedResult:
    """ParsedResult, где один ProfileBuild ссылается на profile_name, отсутствующий в profile_definitions."""
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


@pytest.mark.business_logic
def test_passport_convert_raises_on_unknown_component(
    publisher_parsed_result: ParsedResult,
) -> None:
    """convert() бросает ValueError, если запрошенный компонент не существует."""
    converter = PassportConverter(UNKNOWN_COMPONENT, RELEASE_VERSION)

    with pytest.raises(ValueError):
        converter.convert(publisher_parsed_result)


@pytest.mark.business_logic
def test_passport_convert_raises_on_unknown_version(
    publisher_parsed_result: ParsedResult,
) -> None:
    """convert() бросает ValueError, если версия релиза не найдена."""
    converter = PassportConverter(COMP_NAME, UNKNOWN_VERSION)

    with pytest.raises(ValueError):
        converter.convert(publisher_parsed_result)


@pytest.mark.contract
def test_passport_convert_returns_platform_version(
    publisher_parsed_result: ParsedResult,
) -> None:
    """result['platform_version'] соответствует platform_version исходного ParsedResult."""
    result = PassportConverter(COMP_NAME, RELEASE_VERSION).convert(publisher_parsed_result)

    assert result["platform_version"] == PLATFORM_VERSION


@pytest.mark.contract
def test_passport_convert_returns_component_fields(
    publisher_parsed_result: ParsedResult,
) -> None:
    """result['component'] содержит name и description компонента."""
    result = PassportConverter(COMP_NAME, RELEASE_VERSION).convert(publisher_parsed_result)

    assert result["component"]["name"] == COMP_NAME
    assert result["component"]["description"] == COMP_DESCRIPTION


@pytest.mark.contract
def test_passport_convert_returns_release_version(
    publisher_parsed_result: ParsedResult,
) -> None:
    """result['releases'][0]['version'] соответствует запрошенной версии релиза."""
    result = PassportConverter(COMP_NAME, RELEASE_VERSION).convert(publisher_parsed_result)

    assert result["releases"][0]["version"] == RELEASE_VERSION


@pytest.mark.contract
def test_passport_convert_returns_release_channel(
    publisher_parsed_result: ParsedResult,
) -> None:
    """result['releases'][0]['channel'] соответствует каналу релиза."""
    result = PassportConverter(COMP_NAME, RELEASE_VERSION).convert(publisher_parsed_result)

    assert result["releases"][0]["channel"] == CHANNEL_TECH


from autodoc.models.conan_variant import ConanVariant
from autodoc.models.options import TotalOptionsSet


@pytest.mark.business_logic
def test_variant_options_linked_by_options_ref_id(
    publisher_parsed_result: ParsedResult,
) -> None:
    """
    BL-PC-01
    Бизнес-правило: ConanVariant.options_ref используется для поиска
    соответствующего TotalOptionsSet по id. При совпадении вариант
    в view-model содержит корректный conan_options.

    Предусловия:
        - publisher_parsed_result содержит релиз с variant.options_ref == "opt-set-1"
        - TotalOptionsSet(id="opt-set-1", options={"shared": "True", "fPIC": "True"})

    Шаги:
        1. Создать PassportConverter для openssl / 1.0.0
        2. Вызвать convert()
        3. Проверить variants[0].conan_options

    Ожидаемый результат:
        variants[0].conan_options == {"shared": "True", "fPIC": "True"}
    """
    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.convert(publisher_parsed_result)

    profile_builds = view["releases"][0]["profile_builds"]
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
    Бизнес-правило: если options_ref не найден в total_option_sets,
    conan_options={}; исключение не должно бросаться.

    Предусловия:
        - publisher_parsed_result с одним вариантом, у которого options_ref
          заменён на строку, отсутствующую в любом TotalOptionsSet.

    Шаги:
        1. Построить патченный ParsedResult, где variant.options_ref == "NONEXISTENT_REF"
        2. Создать PassportConverter и вызвать convert()
        3. Проверить variants[0].conan_options

    Ожидаемый результат:
        variants[0].conan_options == {}  (исключение не бросается)
    """
    variant_unknown = ConanVariant(
        package_id="abc123",
        build_url=CI_BUILD_URL,
        build_date="2024-01-15",
        options_ref="NONEXISTENT_REF",
    )
    orig_pb = publisher_parsed_result.components[0].releases[0].profile_builds[0]
    patched_pb = orig_pb.model_copy(update={"variants": [variant_unknown]})
    orig_rel = publisher_parsed_result.components[0].releases[0]
    patched_rel = orig_rel.model_copy(update={"profile_builds": [patched_pb]})
    orig_comp = publisher_parsed_result.components[0]
    patched_comp = orig_comp.model_copy(update={"releases": [patched_rel]})
    patched_result = publisher_parsed_result.model_copy(update={"components": [patched_comp]})

    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.convert(patched_result)

    variants = view["releases"][0]["profile_builds"][0]["variants"]
    assert len(variants) == 1
    assert (
        variants[0].conan_options == {}
    ), "Unknown options_ref should result in empty conan_options, not an exception"


@pytest.mark.business_logic
def test_install_options_built_from_build_option_sets_not_total(
    publisher_parsed_result: ParsedResult,
) -> None:
    """
    Бизнес-правило: строка install_options строится из build_option_sets
    (то, что передал пользователь), а не из total_option_sets.

    Предусловия:
        - publisher_parsed_result с build_option_sets[0].options ==
          "openssl/*:shared=True, openssl/*:fPIC=True"

    Шаги:
        1. Создать PassportConverter и вызвать convert()
        2. Проверить variants[0].install_options

    Ожидаемый результат:
        install_options содержит "-o", "shared" и "openssl"
    """
    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.convert(publisher_parsed_result)

    variant_view = view["releases"][0]["profile_builds"][0]["variants"][0]
    install_opts = variant_view.install_options

    assert "-o" in install_opts, "install_options must contain the -o flag"
    assert "shared" in install_opts, "install_options must contain the key 'shared'"
    assert (
        "openssl" in install_opts
    ), "install_options must use the component name from build_option_sets"


@pytest.mark.contract
def test_variants_are_conan_variant_view_dataclasses(
    publisher_parsed_result: ParsedResult,
) -> None:
    """
    Бизнес-правило: каждый вариант в view-model — это ConanVariantView
    (dataclass), а не исходный ConanVariant.

    Предусловия:
        - publisher_parsed_result с одним вариантом в релизе.

    Шаги:
        1. Создать PassportConverter и вызвать convert()
        2. Проверить тип каждого варианта в profile_builds

    Ожидаемый результат:
        isinstance(variant, ConanVariantView) is True (гарантирует и наличие
        полей package_id, build_url, conan_options, install_options — они
        часть самого dataclass).
    """
    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.convert(publisher_parsed_result)

    for pb in view["releases"][0]["profile_builds"]:
        for variant in pb["variants"]:
            assert isinstance(
                variant, ConanVariantView
            ), f"Expected ConanVariantView, got {type(variant).__name__}"


@pytest.mark.business_logic
def test_profile_build_enriched_with_conan_settings_from_profile_definition(
    publisher_parsed_result: ParsedResult,
    publisher_profile_definition,
) -> None:
    """
    Бизнес-правило: conan_settings берётся из ProfileDefinition (по
    совпадению profile_name), а не из самого ProfileBuild.

    Предусловия:
        - publisher_parsed_result включает ProfileDefinition для
          "hw-linux-x86_64-gcc10" с conan_settings.

    Шаги:
        1. Создать PassportConverter и вызвать convert()
        2. Проверить profile_builds[0]["conan_settings"]

    Ожидаемый результат:
        profile_builds[0]["conan_settings"] == publisher_profile_definition.conan_settings
    """
    assert any(
        pd.profile_name == "hw-linux-x86_64-gcc10"
        for pd in publisher_parsed_result.profile_definitions
    ), "Fixture must contain ProfileDefinition for hw-linux-x86_64-gcc10"

    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.convert(publisher_parsed_result)

    pb_view = view["releases"][0]["profile_builds"][0]
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
    Бизнес-правило: docker_image берётся из ProfileDefinition.

    Предусловия:
        - publisher_parsed_result включает ProfileDefinition с заданным docker_image.

    Шаги:
        1. Создать PassportConverter и вызвать convert()
        2. Проверить profile_builds[0]["docker_image"]

    Ожидаемый результат:
        profile_builds[0]["docker_image"] == publisher_profile_definition.docker_image,
        и оно непустое.
    """
    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.convert(publisher_parsed_result)

    pb_view = view["releases"][0]["profile_builds"][0]
    assert (
        pb_view["docker_image"] == publisher_profile_definition.docker_image
    ), "docker_image must be taken from ProfileDefinition"
    assert pb_view["docker_image"] != "", "docker_image must not be empty"


@pytest.mark.business_logic
def test_missing_profile_definition_gives_empty_settings_not_error(
    publisher_parsed_result: ParsedResult,
) -> None:
    """
    Бизнес-правило: если ProfileDefinition отсутствует для профиля,
    conan_settings={} и docker_image=""; исключение не бросается.

    Предусловия:
        - ParsedResult с profile_definitions=[]

    Шаги:
        1. Патчить ParsedResult, убрав все ProfileDefinition
        2. Создать PassportConverter и вызвать convert()
        3. Проверить profile_builds[0]

    Ожидаемый результат:
        conan_settings == {} и docker_image == "" без KeyError или AttributeError.
    """
    patched_result = publisher_parsed_result.model_copy(update={"profile_definitions": []})

    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.convert(patched_result)

    pb_view = view["releases"][0]["profile_builds"][0]
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
    Бизнес-правило: profile_builds в view-model упорядочены по имени профиля
    в алфавитном порядке, независимо от порядка их следования в Release.

    Предусловия:
        - publisher_two_profile_parsed_result содержит pb_x86 (hw-linux-x86_64-gcc10)
          и pb_arm (hw-linux-arm64-gcc10), добавленные в порядке x86 / arm.

    Шаги:
        1. Создать PassportConverter(component_name="mylib", release_version="1.0.0")
        2. Вызвать convert()
        3. Извлечь список profile_name из profile_builds

    Ожидаемый результат:
        profile_names == sorted(profile_names) и profile_names[0] начинается с
        "hw-linux-arm64" (arm64 идёт раньше x86_64 по алфавиту).
    """
    converter = PassportConverter(component_name="mylib", release_version="1.0.0")
    view = converter.convert(publisher_two_profile_parsed_result)

    names = [pb["profile_name"] for pb in view["releases"][0]["profile_builds"]]
    assert names == sorted(names), f"profile_builds must be sorted by name, got: {names}"
    assert (
        names[0] == "hw-linux-arm64-gcc10"
    ), "arm64 should be first (alphabetically before x86_64)"


@pytest.mark.contract
def test_legacy_contents_key_absent_from_view(
    publisher_parsed_result: ParsedResult,
) -> None:
    """
    Бизнес-правило: PassportConverter.convert() сам не устанавливает
    legacy_contents; данные legacy добавляются СНАРУЖИ, стратегией
    PassportsStrategy (см. passports_strategy.py: view_model["legacy_contents"] =
    extract_for_platform(...)), а не конвертером.

    Предусловия:
        - Стандартный publisher_parsed_result (без предварительной инъекции legacy).

    Шаги:
        1. Создать PassportConverter и вызвать convert()
        2. Проверить view на наличие ключа "legacy_contents".

    Ожидаемый результат:
        Ключ "legacy_contents" отсутствует при обычном вызове convert().
    """
    converter = PassportConverter(component_name="openssl", release_version="1.0.0")
    view = converter.convert(publisher_parsed_result)

    assert "legacy_contents" not in view, (
        "legacy_contents must NOT be set by the converter; "
        "it is injected later by PassportsStrategy"
    )


@pytest.mark.business_logic
def test_passport_convert_returns_one_entry_per_channel_for_same_version(
    publisher_parsed_result: ParsedResult,
) -> None:
    """Несколько релизов одной версии в разных каналах дают отдельную запись releases на каждый канал."""
    original_comp = publisher_parsed_result.components[0]
    original_rel = original_comp.releases[0]
    slow_rel = original_rel.model_copy(update={"channel": "slow"})
    patched_comp = original_comp.model_copy(update={"releases": [original_rel, slow_rel]})
    patched_result = publisher_parsed_result.model_copy(update={"components": [patched_comp]})

    converter = PassportConverter(component_name=COMP_NAME, release_version=RELEASE_VERSION)
    view = converter.convert(patched_result)

    channels = {r["channel"] for r in view["releases"]}
    assert len(view["releases"]) == 2
    assert channels == {CHANNEL_TECH, "slow"}


@pytest.mark.business_logic
def test_git_repo_base_url_strips_query_string(publisher_parsed_result: ParsedResult) -> None:
    """git_repo_base_url отбрасывает query-string, оставляя только базовый URL репозитория."""
    original_comp = publisher_parsed_result.components[0]
    base_url = original_comp.git_url
    patched_comp = original_comp.model_copy(update={"git_url": f"{base_url}?version=GBmain"})
    patched_result = publisher_parsed_result.model_copy(update={"components": [patched_comp]})

    converter = PassportConverter(component_name=COMP_NAME, release_version=RELEASE_VERSION)
    view = converter.convert(patched_result)

    assert view["releases"][0]["git_repo_base_url"] == base_url
