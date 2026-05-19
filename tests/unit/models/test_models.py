"""Юнит-тесты для autodoc.models.component.

Охватывает: _parse_option_str, ConanInputOptions, ProfileBuild, Release, Component.
"""

from __future__ import annotations

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.options import _parse_option_str, ConanInputOptions
from autodoc.models.release import Release

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
}


# ===========================================================================
# _parse_option_str: успешный путь с префиксом пакета
# ===========================================================================


@pytest.mark.business_logic
def test_parse_option_str_strips_package_prefix() -> None:
    """_parse_option_str удаляет префикс пакета из каждого ключа."""
    result = _parse_option_str(OPTION_STR_WITH_PREFIX)
    assert result == {"shared": "True", "fPIC": "False"}


# ===========================================================================
# _parse_option_str: пустая строка
# ===========================================================================


@pytest.mark.business_logic
def test_parse_option_str_empty_string_returns_empty_dict() -> None:
    """_parse_option_str возвращает пустой словарь для пустой входной строки."""
    result = _parse_option_str("")
    assert result == {}


# ===========================================================================
# _parse_option_str: без префикса
# ===========================================================================


@pytest.mark.business_logic
def test_parse_option_str_no_prefix() -> None:
    """_parse_option_str принимает ключи без префикса пакета."""
    result = _parse_option_str(OPTION_STR_NO_PREFIX)
    assert result == {"shared": "True"}


# ===========================================================================
# _parse_option_str: символ подстановки удаляется
# ===========================================================================


@pytest.mark.business_logic
def test_parse_option_str_wildcard_prefix_stripped() -> None:
    """_parse_option_str удаляет префикс с символом подстановки (mylib/*:key) и оставляет чистый ключ."""
    result = _parse_option_str(OPTION_STR_WILDCARD)
    assert "shared" in result


# ===========================================================================
# ConanInputOptions: parsed_options автоматически заполняется из options
# ===========================================================================


@pytest.mark.business_logic
def test_conan_input_options_auto_fills_parsed_options() -> None:
    """ConanInputOptions.parsed_options автоматически заполняется из строки options при создании."""
    instance = ConanInputOptions(id="1", options=OPTION_STR_PKG)
    assert instance.parsed_options == {"shared": "True", "fPIC": "False"}


# ===========================================================================
# ConanInputOptions: пустые options → parsed_options остаётся пустым
# ===========================================================================


@pytest.mark.business_logic
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
@pytest.mark.business_logic
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


@pytest.mark.contract
def test_profile_build_default_exists_is_false() -> None:
    """ProfileBuild.exists по умолчанию равен False, если не задан явно."""
    instance = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    assert instance.exists is False


# ===========================================================================
# Release: коллекции по умолчанию пусты
# ===========================================================================


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


# ===========================================================================
# Component: сериализация туда и обратно через model_dump / model_validate
# ===========================================================================


@pytest.mark.contract
def test_component_roundtrip_serialization() -> None:
    """Component корректно проходит сериализацию и десериализацию через model_dump и model_validate."""
    original = Component(name="openssl", description="TLS library")
    data = original.model_dump()
    restored = Component.model_validate(data)
    assert restored.name == original.name


# ---------------------------------------------------------------------------
# T3.10 — тесты моделей ProfileDefinition и ParsedResult
# ---------------------------------------------------------------------------

import pytest
from pydantic import ValidationError as PydanticValidationError

from autodoc.models.profile_definition import ProfileDefinition
from autodoc.models.parsed_result import ParsedResult

_PROFILE_NAME: str = "linux_x64_gcc12"
_DOCKER_IMAGE: str = "registry.example.com/builder:v1"
_GENERATED_AT: str = "2024-01-01T00:00:00"
_PLATFORM_VERSION: str = "2.0"


class TestProfileDefinition:
    """Модульные тесты для модели Pydantic ProfileDefinition."""

    @pytest.mark.contract
    def test_minimal_construction(self) -> None:
        """ProfileDefinition можно построить только с profile_name; применяются значения по умолчанию."""
        pd = ProfileDefinition(profile_name=_PROFILE_NAME)
        assert pd.profile_name == _PROFILE_NAME
        assert pd.docker_image == ""
        assert pd.conan_settings == {}

    @pytest.mark.contract
    def test_full_construction(self) -> None:
        """ProfileDefinition принимает все дополнительные поля."""
        pd = ProfileDefinition(
            profile_name=_PROFILE_NAME,
            docker_image=_DOCKER_IMAGE,
            conan_settings={"os": "Linux"},
        )
        assert pd.docker_image == _DOCKER_IMAGE

    @pytest.mark.contract
    def test_missing_profile_name_raises(self) -> None:
        """Пропуск обязательного profile_name должен вызвать ValidationError."""
        with pytest.raises(PydanticValidationError):
            ProfileDefinition()  # type: ignore[call-arg]


class TestParsedResult:
    """Модульные тесты для модели Pydantic ParsedResult."""

    @pytest.mark.contract
    def test_minimal_construction(self) -> None:
        """ParsedResult можно построить с обязательными полями; значения по умолчанию для списков пусты."""
        result = ParsedResult(
            generated_at=_GENERATED_AT,
            platform_version=_PLATFORM_VERSION,
        )
        assert result.generated_at == _GENERATED_AT
        assert result.components == []
        assert result.profile_definitions == []

    @pytest.mark.contract
    def test_missing_generated_at_raises(self) -> None:
        """Пропуск generated_at должен вызвать ValidationError."""
        with pytest.raises(PydanticValidationError):
            ParsedResult(platform_version=_PLATFORM_VERSION)  # type: ignore[call-arg]

    @pytest.mark.contract
    def test_missing_platform_version_raises(self) -> None:
        """Пропуск platform_version должен вызвать ValidationError."""
        with pytest.raises(PydanticValidationError):
            ParsedResult(generated_at=_GENERATED_AT)  # type: ignore[call-arg]
