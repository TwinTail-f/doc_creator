"""Юнит-тесты для ProfileCentricConverter."""

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.parsed_result import ParsedResult, ProfileDefinition
from autodoc.models.release import Release
from autodoc.publisher.converters.profile_converter import ProfileCentricConverter

CHANNEL_TECH: str = "tech"
DOCKER_IMAGE: str = "registry.example.com/build/linux-gcc10:latest"
OS_LINUX: str = "Linux"
EXCLUSIVE_PROFILE_NAME: str = "header-only-exclusive-profile"


@pytest.fixture
def result_with_header_only_unique_profile(
    publisher_multi_component_result: ParsedResult,
) -> ParsedResult:
    """ParsedResult, где header-only релиз ссылается на профиль, больше нигде не встречающийся."""
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
    return publisher_multi_component_result.model_copy(update={"components": components})


@pytest.mark.contract
def test_profile_centric_convert_profile_has_required_fields(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """Каждая запись профиля содержит все обязательные ключи."""
    result = ProfileCentricConverter().convert(publisher_multi_component_result)

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
def test_profile_centric_convert_profile_os_from_conan_settings(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """profile['os'] читается из conan_settings['os'] соответствующего ProfileDefinition."""
    result = ProfileCentricConverter().convert(publisher_multi_component_result)

    assert result["profiles"][0]["os"] == OS_LINUX


@pytest.mark.business_logic
def test_profile_centric_convert_profile_docker_url(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """profile['docker_url'] соответствует docker_image соответствующего ProfileDefinition."""
    result = ProfileCentricConverter().convert(publisher_multi_component_result)

    assert result["profiles"][0]["docker_url"] == DOCKER_IMAGE


@pytest.mark.business_logic
def test_profile_centric_convert_channels_grouped_by_channel(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """И openssl, и zlib присутствуют в канале 'tech' профиля."""
    result = ProfileCentricConverter().convert(publisher_multi_component_result)

    channels = result["profiles"][0]["channels"]
    assert len(channels[CHANNEL_TECH]) == 2


@pytest.mark.contract
def test_profile_centric_convert_comp_entry_has_reference_and_url(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """Каждая запись компонента включает поля 'reference' и 'url'."""
    result = ProfileCentricConverter().convert(publisher_multi_component_result)

    comp_entry = result["profiles"][0]["channels"][CHANNEL_TECH][0]
    assert "reference" in comp_entry
    assert "url" in comp_entry


@pytest.mark.business_logic
def test_profile_centric_converter_profile_with_no_components_does_not_raise() -> None:
    """ProfileDefinition без совпадающих ProfileBuild не приводит к падению."""
    # Профиль присутствует в definitions, но не упомянут ни в одном ProfileBuild компонентов
    orphan_profile = ProfileDefinition(profile_name="hw-linux-riscv64-gcc12")

    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")  # другое имя
    release = Release(
        version="3.0.9",
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
    view_model = converter.convert(parsed)  # не должно бросить исключение

    # У осиротевшего профиля нет ProfileBuild от не-header-only компонентов,
    # поэтому он должен отсутствовать в списке profiles (не вызывать падение
    # и не создавать фиктивную запись)
    profile_names = {p["profile_name"] for p in view_model["profiles"]}
    assert "hw-linux-riscv64-gcc12" not in profile_names


@pytest.mark.business_logic
def test_data_restructured_from_component_to_profile_axis(
    publisher_multi_channel_result,
) -> None:
    """
    Бизнес-правило: ProfileCentricConverter преобразует входную структуру
    Компонент→Релиз→Профиль в Профиль→словарь каналов→[компоненты].

    Предусловия:
        - publisher_multi_channel_result: comp_alpha с релизами в каналах
          'fast' и 'stable', оба под профилем 'hw-linux-x86_64-gcc10'.

    Шаги:
        1. Создать ProfileCentricConverter(include_passport_links=False).
        2. Вызвать convert().
        3. Проверить, что комponент alpha оказался под обоими каналами
           одного и того же профиля (реструктуризация по оси
           профиль→канал→компонент), а не просто что у профиля есть ключи
           (это уже проверяется test_profile_centric_convert_profile_has_required_fields
           и test_profile_centric_convert_comp_entry_has_reference_and_url).

    Ожидаемый результат:
        Оба канала 'fast' и 'stable' профиля 'hw-linux-x86_64-gcc10' содержат
        запись компонента 'alpha'.
    """
    converter = ProfileCentricConverter(include_passport_links=False)
    view = converter.convert(publisher_multi_channel_result)

    profile = next(
        p for p in view["profiles"] if p["profile_name"] == "hw-linux-x86_64-gcc10"
    )
    channels = profile["channels"]
    for channel_name in ("fast", "stable"):
        names_in_channel = {entry["name"] for entry in channels[channel_name]}
        assert "alpha" in names_in_channel


@pytest.mark.business_logic
def test_header_only_components_excluded_from_profile_metadata(
    publisher_multi_channel_result,
    publisher_profile_definition,
) -> None:
    """
    Бизнес-правило: is_header_only у компонента означает, что такие
    компоненты НЕ используются для определения conan_settings / docker_url
    профиля.

    Предусловия:
        - publisher_multi_channel_result: comp_alpha (is_header_only=False)
          и comp_beta (is_header_only=True).

    Шаги:
        1. Создать ProfileCentricConverter и вызвать convert().
        2. Найти профиль "hw-linux-x86_64-gcc10" в view["profiles"].
        3. Проверить conan_settings и docker_url.

    Ожидаемый результат:
        conan_settings совпадает с publisher_profile_definition.conan_settings
        (источник — только comp_alpha); значение непустое.
    """
    converter = ProfileCentricConverter(include_passport_links=False)
    view = converter.convert(publisher_multi_channel_result)

    profile = next(
        (p for p in view["profiles"] if p["profile_name"] == "hw-linux-x86_64-gcc10"),
        None,
    )
    assert profile is not None, "Профиль hw-linux-x86_64-gcc10 должен присутствовать"
    assert (
        profile["os"] == publisher_profile_definition.conan_settings["os"]
    ), "profile['os'] должен браться из ProfileDefinition не-header-only компонента"
    assert profile["os"] != "", "conan_settings['os'] не должен быть пустым"


@pytest.mark.business_logic
def test_channels_within_profile_sorted_consistently(
    publisher_multi_channel_result,
) -> None:
    """
    Бизнес-правило: каналы внутри профиля имеют стабильный алфавитный
    порядок, чтобы обеспечить идентичный HTML-вывод при повторной публикации.

    Предусловия:
        - publisher_multi_channel_result имеет каналы "fast" и "stable" для
          профиля "hw-linux-x86_64-gcc10". Релизы comp_alpha патчатся так,
          чтобы канал "stable" физически шёл в данных раньше канала "fast" —
          иначе тест не отличает настоящую сортировку от порядка вставки,
          случайно совпадающего с алфавитным в исходной фикстуре.

    Шаги:
        1. Поменять местами релизы comp_alpha, чтобы "stable" оказался
           раньше "fast" в списке releases.
        2. Создать ProfileCentricConverter и вызвать convert().
        3. Для каждого профиля извлечь упорядоченные имена каналов из словаря.

    Ожидаемый результат:
        list(channels.keys()) == sorted(list(channels.keys())), несмотря на
        то, что в исходных данных канал "stable" идёт раньше "fast".
    """
    comp_alpha = publisher_multi_channel_result.components[0]
    reversed_comp_alpha = comp_alpha.model_copy(
        update={"releases": list(reversed(comp_alpha.releases))}
    )
    patched_result = publisher_multi_channel_result.model_copy(
        update={
            "components": [reversed_comp_alpha]
            + list(publisher_multi_channel_result.components[1:])
        }
    )

    converter = ProfileCentricConverter(include_passport_links=False)
    view = converter.convert(patched_result)

    for profile in view["profiles"]:
        channel_names = list(profile["channels"].keys())
        assert channel_names == sorted(channel_names), (
            f"Каналы в профиле '{profile['profile_name']}' должны быть отсортированы, "
            f"получено: {channel_names}"
        )


@pytest.mark.business_logic
def test_components_within_channel_sorted_by_name(
    publisher_multi_channel_result,
) -> None:
    """
    Бизнес-правило: компоненты внутри канала отсортированы по имени для
    детерминированного вывода в Confluence.

    Предусловия:
        - publisher_multi_channel_result: канал "fast" содержит и alpha,
          и beta; alpha < beta по алфавиту.

    Шаги:
        1. Создать ProfileCentricConverter и вызвать convert().
        2. Для каждого профиля и канала проверить порядок имён компонентов.

    Ожидаемый результат:
        comp_names == sorted(comp_names) для каждого канала в каждом профиле.
    """
    converter = ProfileCentricConverter(include_passport_links=False)
    view = converter.convert(publisher_multi_channel_result)

    for profile in view["profiles"]:
        for channel_name, comp_entries in profile["channels"].items():
            comp_names = [c["name"] for c in comp_entries]
            assert comp_names == sorted(comp_names), (
                f"Компоненты в канале '{channel_name}' профиля "
                f"'{profile['profile_name']}' должны быть отсортированы: "
                f"ожидалось {sorted(comp_names)}, получено {comp_names}"
            )


@pytest.mark.business_logic
@pytest.mark.parametrize("include_passport_links", [False, True])
def test_passport_link_reflects_include_passport_links_flag(
    publisher_multi_channel_result, include_passport_links: bool
) -> None:
    """
    Бизнес-правило: значение passport_link у каждой не-header-only записи
    компонента зависит от include_passport_links, переданного в конструктор.

    При include_passport_links=False ключ passport_link отсутствует или
    равен None/"" для каждого компонента в каждом канале.

    При include_passport_links=True каждая запись получает ключ
    "passport_link", инициализированный None (сам конвертер не форматирует
    строку ссылки — реальный URL заполняется позже в
    PassportPageRegistry.inject_links_for_profiles(), см. test_passport_registry.py).

    Предусловия:
        - publisher_multi_channel_result с comp_alpha (не header-only).

    Шаги:
        1. Создать ProfileCentricConverter(include_passport_links=<флаг>).
        2. Вызвать convert().
        3. Проверить passport_link для всех записей компонентов.
    """
    converter = ProfileCentricConverter(include_passport_links=include_passport_links)
    view = converter.convert(publisher_multi_channel_result)

    checked_any = False
    for profile in view["profiles"]:
        for _, comp_entries in profile["channels"].items():
            for comp_entry in comp_entries:
                if include_passport_links:
                    assert (
                        "passport_link" in comp_entry
                    ), "При include_links=True у каждого компонента должен быть ключ passport_link"
                    assert comp_entry["passport_link"] is None, (
                        "Конвертер должен оставлять passport_link равным None; "
                        "реальные ссылки добавляются позже через PassportPageRegistry"
                    )
                else:
                    link = comp_entry.get("passport_link")
                    assert link is None or link == "", (
                        f"Без include_links=True passport_link должен быть None/пустым, "
                        f"получено: {link!r}"
                    )
                checked_any = True
    assert checked_any, "Должна была быть проверена хотя бы одна запись компонента"


@pytest.mark.business_logic
def test_header_only_component_with_exclusive_profile_is_dropped_from_view(
    result_with_header_only_unique_profile: ParsedResult,
) -> None:
    """Header-only компонент, чей единственный профиль больше нигде не используется, полностью пропадает из результата."""
    result = ProfileCentricConverter().convert(result_with_header_only_unique_profile)

    profile_names = {p["profile_name"] for p in result["profiles"]}
    assert EXCLUSIVE_PROFILE_NAME not in profile_names


@pytest.mark.business_logic
def test_profile_centric_convert_all_header_only_gives_empty_profiles(
    publisher_multi_component_result: ParsedResult,
) -> None:
    """Если все компоненты header-only, метаданные профилей не собираются и profiles == []."""
    header_only_components = [
        comp.model_copy(update={"is_header_only": True})
        for comp in publisher_multi_component_result.components
    ]
    patched_result = publisher_multi_component_result.model_copy(
        update={"components": header_only_components}
    )

    result = ProfileCentricConverter().convert(patched_result)

    assert result["profiles"] == []
