"""Юнит-тесты для autodoc.models.component.

Охватывает: _parse_option_str, ConanInputOptions, ProfileBuild, Release, Component.
"""

from __future__ import annotations

from typing import Any

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.options import _parse_option_str, ConanInputOptions
from autodoc.models.parsed_result import ParsedResult
from autodoc.models.profile_definition import ProfileDefinition
from autodoc.models.release import Release

# Константы уровня модуля
OPTION_STR_WITH_PREFIX: str = "mylib:shared=True,mylib:fPIC=False"
OPTION_STR_NO_PREFIX: str = "shared=True"
OPTION_STR_WILDCARD: str = "mylib/*:shared=True"
OPTION_STR_PKG: str = "pkg:shared=True,pkg:fPIC=False"

MINIMAL_RELEASE_KWARGS: dict = {
    "version": "1.0.0",
    "platform": "2.0",
    "channel": "tech",
}


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "option_str, expected",
    [
        # обычный префикс пакета удаляется из каждого ключа
        pytest.param(
            OPTION_STR_WITH_PREFIX, {"shared": "True", "fPIC": "False"}, id="strips-package-prefix"
        ),
        # пустая строка -> пустой словарь
        pytest.param("", {}, id="empty-string"),
        # ключи без префикса пакета принимаются как есть
        pytest.param(OPTION_STR_NO_PREFIX, {"shared": "True"}, id="no-prefix"),
        # префикс с символом подстановки (mylib/*:key) тоже удаляется целиком
        pytest.param(OPTION_STR_WILDCARD, {"shared": "True"}, id="wildcard-prefix"),
    ],
)
def test_parse_option_str(option_str: str, expected: dict[str, str]) -> None:
    """_parse_option_str удаляет префикс пакета из ключей строки опций."""
    assert _parse_option_str(option_str) == expected


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "options_str, explicit_parsed, expected",
    [
        # explicit не задан -> parsed_options вычисляется из options
        pytest.param(OPTION_STR_PKG, None, {"shared": "True", "fPIC": "False"}, id="auto-filled"),
        # options — пустая строка и explicit не задан -> parsed_options остаётся пустым
        pytest.param("", None, {}, id="auto-filled-empty-options"),
        # explicit значение задано -> не перезаписывается автозаполнением
        pytest.param("pkg:shared=True", {"custom": "val"}, {"custom": "val"}, id="explicit-wins"),
        pytest.param(
            "pkg:fPIC=False",
            {"override": "yes", "extra": "no"},
            {"override": "yes", "extra": "no"},
            id="explicit-wins-multiple-keys",
        ),
    ],
)
def test_conan_input_options_parsed_options_priority(
    options_str: str,
    explicit_parsed: dict[str, str] | None,
    expected: dict[str, str],
) -> None:
    """ConanInputOptions.parsed_options: явное значение имеет приоритет над
    автозаполнением из options; без явного значения parsed_options
    вычисляется из строки options (а пустая options даёт пустой словарь).

    В кейсах ``explicit-*`` ``options_str`` и ``explicit_parsed`` намеренно не
    согласованы друг с другом: если бы валидатор безусловно перепарсивал
    ``options`` и подменял ``parsed_options``, итоговое значение отличалось бы
    от ``explicit_parsed`` и тест бы упал. Так проверяется именно условность
    автозаполнения, а не факт, что pydantic хранит переданное в конструктор
    значение.
    """
    kwargs: dict[str, object] = {"id": "1", "options": options_str}
    if explicit_parsed is not None:
        kwargs["parsed_options"] = explicit_parsed
    instance = ConanInputOptions(**kwargs)
    assert instance.parsed_options == expected


@pytest.mark.contract
def test_profile_build_default_exists_is_false() -> None:
    """ProfileBuild.exists по умолчанию равен False, если не задан явно."""
    instance = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    assert instance.exists is False


@pytest.mark.contract
def test_release_defaults_are_empty_collections() -> None:
    """Release.build_option_sets и profile_builds по умолчанию []."""
    instance = Release(**MINIMAL_RELEASE_KWARGS)
    assert instance.build_option_sets == []
    assert instance.profile_builds == []


@pytest.mark.contract
def test_component_defaults_is_header_only_false() -> None:
    """Component.is_header_only по умолчанию False, git_url по умолчанию пустая строка."""
    instance = Component(name="mylib")
    assert instance.is_header_only is False
    assert instance.git_url == ""


_PROFILE_NAME: str = "linux_x64_gcc12"
_DOCKER_IMAGE: str = "registry.example.com/builder:v1"
_GENERATED_AT: str = "2024-01-01T00:00:00"
_PLATFORM_VERSION: str = "2.0"


@pytest.mark.contract
@pytest.mark.parametrize(
    "extra_kwargs, expected_docker_image, expected_conan_settings",
    [
        # только обязательное поле -> применяются дефолты
        pytest.param({}, "", {}, id="minimal-uses-defaults"),
        # все дополнительные поля переданы явно -> сохраняются как есть
        pytest.param(
            {"docker_image": _DOCKER_IMAGE, "conan_settings": {"os": "Linux"}},
            _DOCKER_IMAGE,
            {"os": "Linux"},
            id="full-construction",
        ),
    ],
)
def test_profile_definition_construction(
    extra_kwargs: dict[str, Any],
    expected_docker_image: str,
    expected_conan_settings: dict[str, str],
) -> None:
    """ProfileDefinition строится как с одними обязательными полями (тогда docker_image/
    conan_settings берут значения по умолчанию), так и с полным набором полей (тогда
    переданные значения сохраняются без изменений)."""
    pd = ProfileDefinition(profile_name=_PROFILE_NAME, **extra_kwargs)
    assert pd.profile_name == _PROFILE_NAME
    assert pd.docker_image == expected_docker_image
    assert pd.conan_settings == expected_conan_settings


@pytest.mark.contract
def test_parsed_result_minimal_construction() -> None:
    """ParsedResult можно построить с обязательными полями; значения по умолчанию для списков пусты."""
    result = ParsedResult(
        generated_at=_GENERATED_AT,
        platform_version=_PLATFORM_VERSION,
    )
    assert result.generated_at == _GENERATED_AT
    assert result.components == []
    assert result.profile_definitions == []
