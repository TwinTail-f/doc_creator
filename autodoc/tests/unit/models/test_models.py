"""Юнит-тесты для autodoc.models.component.

Охватывает: _parse_option_str, ConanInputOptions, ProfileBuild, Release, Component.
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
# Константы уровня модуля
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
# _parse_option_str: успешный путь с префиксом пакета
# ===========================================================================


def test_parse_option_str_strips_package_prefix() -> None:
    """_parse_option_str удаляет префикс пакета из каждого ключа."""
    result = _parse_option_str(OPTION_STR_WITH_PREFIX)
    assert result == {"shared": "True", "fPIC": "False"}


# ===========================================================================
# _parse_option_str: пустая строка
# ===========================================================================


def test_parse_option_str_empty_string_returns_empty_dict() -> None:
    """_parse_option_str возвращает пустой словарь для пустой входной строки."""
    result = _parse_option_str("")
    assert result == {}


# ===========================================================================
# _parse_option_str: без префикса
# ===========================================================================


def test_parse_option_str_no_prefix() -> None:
    """_parse_option_str принимает ключи без префикса пакета."""
    result = _parse_option_str(OPTION_STR_NO_PREFIX)
    assert result == {"shared": "True"}


# ===========================================================================
# _parse_option_str: символ подстановки удаляется
# ===========================================================================


def test_parse_option_str_wildcard_prefix_stripped() -> None:
    """_parse_option_str удаляет префикс с символом подстановки (mylib/*:key) и оставляет чистый ключ."""
    result = _parse_option_str(OPTION_STR_WILDCARD)
    assert "shared" in result


# ===========================================================================
# ConanInputOptions: parsed_options автоматически заполняется из options
# ===========================================================================


def test_conan_input_options_auto_fills_parsed_options() -> None:
    """ConanInputOptions.parsed_options автоматически заполняется из строки options при создании."""
    instance = ConanInputOptions(id="1", options=OPTION_STR_PKG)
    assert instance.parsed_options == {"shared": "True", "fPIC": "False"}


# ===========================================================================
# ConanInputOptions: пустые options → parsed_options остаётся пустым
# ===========================================================================


def test_conan_input_options_empty_options_parsed_options_empty() -> None:
    """ConanInputOptions.parsed_options остаётся пустым, если options — пустая строка."""
    instance = ConanInputOptions(id="1", options="")
    assert instance.parsed_options == {}


# ===========================================================================
# ConanInputOptions: явно заданный parsed_options не перезаписывается (параметризованный)
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
    """ConanInputOptions.parsed_options не перезаписывается, если он задан явно."""
    instance = ConanInputOptions(
        id="1",
        options=options_str,
        parsed_options=explicit_parsed,
    )
    assert instance.parsed_options == explicit_parsed


# ===========================================================================
# ProfileBuild: exists по умолчанию равен False
# ===========================================================================


def test_profile_build_default_exists_is_false() -> None:
    """ProfileBuild.exists по умолчанию равен False, если не задан явно."""
    instance = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    assert instance.exists is False


# ===========================================================================
# Release: коллекции по умолчанию пусты
# ===========================================================================


def test_release_defaults_are_empty_collections() -> None:
    """Release.build_option_sets и profile_builds по умолчанию [], is_header_only — False."""
    instance = Release(**MINIMAL_RELEASE_KWARGS)
    assert instance.build_option_sets == []
    assert instance.profile_builds == []
    assert instance.is_header_only is False


# ===========================================================================
# Component: сериализация туда и обратно через model_dump / model_validate
# ===========================================================================


def test_component_roundtrip_serialization() -> None:
    """Component корректно проходит сериализацию и десериализацию через model_dump и model_validate."""
    original = Component(name="openssl", description="TLS library")
    data = original.model_dump()
    restored = Component.model_validate(data)
    assert restored.name == original.name
