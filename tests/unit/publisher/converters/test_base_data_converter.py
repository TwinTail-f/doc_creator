"""Тесты для статических методов BaseDataConverter (через публичный PassportConverter.convert())."""

from typing import Any

import pytest

from autodoc.models.options import ConanInputOptions, DefaultOptionsSet, TotalOptionsSet
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.converters.base_data_converter import BadgeClass
from autodoc.publisher.converters.passport_converter import PassportConverter
from tests.unit.publisher.converters.conftest import COMPONENT_NAME as COMP_NAME

OPT_KEY_SHARED: str = "shared"
OPT_KEY_FPIC: str = "fPIC"
_MULTI_OPTION_RESULT: str = (
    f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True" f" -o {COMP_NAME}/*:{OPT_KEY_FPIC}=True"
)
_OPTS_REF: str = "opt-set-1"


def _convert_with_total_options(
    publisher_parsed_result: ParsedResult, options: dict[str, Any]
) -> Any:
    """
    Патчит total_option_sets[0].options единственного релиза и вызывает convert().

    build_option_sets намеренно очищается, чтобы install_options строился из
    conan_options (fallback-путь ``_build_install_options``), а не из строки
    конфига (``_build_install_options_from_string``).
    """
    comp = publisher_parsed_result.components[0]
    rel = comp.releases[0]
    patched_rel = rel.model_copy(
        update={
            "total_option_sets": [TotalOptionsSet(id=_OPTS_REF, options=options)],
            "build_option_sets": [],
        }
    )
    patched_comp = comp.model_copy(update={"releases": [patched_rel]})
    patched_result = publisher_parsed_result.model_copy(update={"components": [patched_comp]})

    converter = PassportConverter(component_name=comp.name, release_version=rel.version)
    view = converter.convert(patched_result)
    return view["releases"][0]["profile_builds"][0]["variants"][0]


def _convert_with_build_option_string(
    publisher_parsed_result: ParsedResult, options_str: str
) -> Any:
    """Патчит build_option_sets[0].options (строка конфига) единственного релиза и вызывает convert()."""
    comp = publisher_parsed_result.components[0]
    rel = comp.releases[0]
    patched_rel = rel.model_copy(
        update={"build_option_sets": [ConanInputOptions(id=_OPTS_REF, options=options_str)]}
    )
    patched_comp = comp.model_copy(update={"releases": [patched_rel]})
    patched_result = publisher_parsed_result.model_copy(update={"components": [patched_comp]})

    converter = PassportConverter(component_name=comp.name, release_version=rel.version)
    view = converter.convert(patched_result)
    return view["releases"][0]["profile_builds"][0]["variants"][0]


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "conan_options, expected",
    [
        # словарь опций пуст — строка флагов пуста
        pytest.param({}, "", id="empty-dict-returns-empty-string"),
        # ключ уже содержит '/*:' — повторной квалификации не происходит
        pytest.param(
            {"icu/*:shared": "True"}, "-o icu/*:shared=True", id="preserves-qualified-key"
        ),
        # ключ зависимости вида 'icu:opt' квалифицируется в 'icu/*:opt' без дублирования
        pytest.param(
            {"icu:data_packaging": "static"},
            "-o icu/*:data_packaging=static",
            id="dep-key-with-colon-not-modified",
        ),
        # несколько опций объединяются пробелом, каждая со своим флагом '-o'
        pytest.param(
            {OPT_KEY_SHARED: "True", OPT_KEY_FPIC: "True"},
            _MULTI_OPTION_RESULT,
            id="multiple-options-joined-by-space",
        ),
    ],
)
def test_install_options_from_conan_options(
    publisher_parsed_result: ParsedResult,
    conan_options: dict[str, str],
    expected: str,
) -> None:
    """
    install_options варианта форматирует опции из total_option_sets в флаги '-o' по правилам квалификации ключей.

    Покрывает ``BaseDataConverter._build_install_options`` (используется как fallback,
    когда для варианта нет соответствующего build_option_sets) через публичный
    ``PassportConverter.convert()``, а не прямым вызовом приватного метода.
    """
    variant_view = _convert_with_total_options(publisher_parsed_result, conan_options)

    assert variant_view.install_options == expected


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "options_str, expected",
    [
        # пустая строка на входе даёт пустую строку
        pytest.param("", "", id="empty-returns-empty"),
        # строка только из пробелов даёт пустую строку
        pytest.param("   ", "", id="whitespace-returns-empty"),
        # одна запись 'pkg/*:key=val' оборачивается одним флагом '-o'
        pytest.param(
            f"{COMP_NAME}/*:{OPT_KEY_SHARED}=True",
            f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True",
            id="single-option",
        ),
        # несколько опций через запятую дают флаги '-o', разделённые пробелом
        pytest.param(
            f"{COMP_NAME}/*:{OPT_KEY_SHARED}=True, {COMP_NAME}/*:{OPT_KEY_FPIC}=True",
            _MULTI_OPTION_RESULT,
            id="multiple-options",
        ),
        # опция вида 'pkg:key=val' (без '/*') квалифицируется в 'pkg/*:key=val'
        pytest.param(
            f"{COMP_NAME}:{OPT_KEY_SHARED}=True",
            f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True",
            id="qualifies-unqualified-key",
        ),
        # ведущие/замыкающие пробелы вокруг каждого токена опции корректно обрезаются
        pytest.param(
            f"  {COMP_NAME}/*:{OPT_KEY_SHARED}=True  ," f"  {COMP_NAME}/*:{OPT_KEY_FPIC}=True  ",
            _MULTI_OPTION_RESULT,
            id="strips-whitespace-between-options",
        ),
        # токен без ':' возвращается как есть, без квалификации пакета
        pytest.param(
            "just-a-flag",
            "-o just-a-flag",
            id="token-without-colon-returned-as-is",
        ),
    ],
)
def test_install_options_from_build_option_string(
    publisher_parsed_result: ParsedResult,
    options_str: str,
    expected: str,
) -> None:
    """
    install_options варианта парсит строку опций конфига (build_option_sets) в флаги '-o'.

    Покрывает ``BaseDataConverter._build_install_options_from_string`` через
    публичный ``PassportConverter.convert()``.
    """
    variant_view = _convert_with_build_option_string(publisher_parsed_result, options_str)

    assert variant_view.install_options == expected


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "value, default_value, has_default, expected_badge",
    [
        ("True", "True", True, BadgeClass.DEFAULT.value),
        (True, False, True, BadgeClass.NEUTRAL.value),
        (False, True, True, BadgeClass.NEUTRAL.value),
        ("static", "shared", True, BadgeClass.NEUTRAL.value),
        ("True", "True", False, BadgeClass.NEUTRAL.value),
    ],
    ids=[
        "matches_default_is_default",
        "differs_bool_true_is_neutral",
        "differs_bool_false_is_neutral",
        "differs_non_boolean_is_neutral",
        "no_default_known_is_neutral",
    ],
)
def test_option_badge_classification(
    publisher_parsed_result: ParsedResult,
    value: Any,
    default_value: Any,
    has_default: bool,
    expected_badge: str,
) -> None:
    """
    option_badges варианта отражает CSS-класс бейджа по сочетанию значения/дефолта/наличия дефолта.

    Покрывает ``PassportConverter._classify_option_badge`` через публичный
    ``PassportConverter.convert()``: значение опции берётся из total_option_sets,
    дефолт (если есть) — из default_options релиза.
    """
    option_name = "some_option"
    comp = publisher_parsed_result.components[0]
    rel = comp.releases[0]
    default_options = (
        [DefaultOptionsSet(name=option_name, type="string", default_value=default_value)]
        if has_default
        else []
    )
    patched_rel = rel.model_copy(
        update={
            "total_option_sets": [TotalOptionsSet(id=_OPTS_REF, options={option_name: value})],
            "build_option_sets": [],
            "default_options": default_options,
        }
    )
    patched_comp = comp.model_copy(update={"releases": [patched_rel]})
    patched_result = publisher_parsed_result.model_copy(update={"components": [patched_comp]})

    converter = PassportConverter(component_name=comp.name, release_version=rel.version)
    view = converter.convert(patched_result)
    variant_view = view["releases"][0]["profile_builds"][0]["variants"][0]

    assert variant_view.option_badges[option_name] == expected_badge
