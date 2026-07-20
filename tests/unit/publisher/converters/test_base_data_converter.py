"""Тесты для статических методов BaseDataConverter и PassportLinkMixin."""

from typing import Any

import pytest

from autodoc.models.conan_variant import ConanVariant
from autodoc.publisher.converters.base_data_converter import _VariantOpts
from autodoc.publisher.converters.full_release_converter import FullReleaseConverter
from autodoc.publisher.converters.passport_converter import PassportConverter

COMP_NAME: str = "openssl"
OPT_KEY_SHARED: str = "shared"
OPT_KEY_FPIC: str = "fPIC"
INSTALL_OVERRIDE: str = "-o pkg/*:x=1"
_MULTI_OPTION_RESULT: str = (
    f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True" f" -o {COMP_NAME}/*:{OPT_KEY_FPIC}=True"
)


class _MinimalParsedResult:
    """Минимальная замена ParsedResult, экспонирующая только то, что читает _base_view_model."""

    platform_version: str = "2.0"


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
def test_build_install_options(conan_options: dict[str, str], expected: str) -> None:
    """_build_install_options форматирует опции варианта в флаги '-o' по правилам квалификации ключей."""
    result = PassportConverter._build_install_options(conan_options, COMP_NAME)

    assert result == expected


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
    ],
)
def test_build_install_options_from_string(options_str: str, expected: str) -> None:
    """_build_install_options_from_string парсит строку опций конфига в флаги '-o'."""
    result = PassportConverter._build_install_options_from_string(options_str)

    assert result == expected


@pytest.mark.contract
def test_build_variant_view_maps_fields_from_variant(
    publisher_conan_variant: ConanVariant,
) -> None:
    """package_id и build_url из ConanVariant попадают в итоговое представление."""
    view = PassportConverter._build_variant_view(publisher_conan_variant, COMP_NAME)

    assert view.package_id == publisher_conan_variant.package_id
    assert view.build_url == publisher_conan_variant.build_url


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "opts, expected_conan_options",
    [
        # opts не задан (None) — conan_options view-model пуст
        pytest.param(None, {}, id="no-opts-defaults-to-empty"),
        # opts задан — conan_options передаются без изменений (чистый passthrough)
        pytest.param(
            _VariantOpts(conan_options={OPT_KEY_SHARED: "True"}),
            {OPT_KEY_SHARED: "True"},
            id="opts-conan-options-passthrough",
        ),
    ],
)
def test_build_variant_view_conan_options(
    publisher_conan_variant: ConanVariant,
    opts: _VariantOpts | None,
    expected_conan_options: dict[str, str],
) -> None:
    """conan_options view-model: пустой словарь, если opts не задан, иначе — значение из opts.conan_options без изменений."""
    view = PassportConverter._build_variant_view(publisher_conan_variant, COMP_NAME, opts)

    assert view.conan_options == expected_conan_options


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "conan_options, install_options_override, expected_install_options",
    [
        # override задан явно — используется дословно, conan_options игнорируются
        pytest.param({}, INSTALL_OVERRIDE, INSTALL_OVERRIDE, id="override-used-directly"),
        # override не задан (None) — install_options строится из conan_options
        pytest.param(
            {OPT_KEY_SHARED: "True"},
            None,
            f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True",
            id="built-from-conan-options-if-no-override",
        ),
    ],
)
def test_build_variant_view_install_options_priority(
    publisher_conan_variant: ConanVariant,
    conan_options: dict[str, str],
    install_options_override: str | None,
    expected_install_options: str,
) -> None:
    """Правило приоритета: install_options_override, если задан, используется дословно; иначе install_options строится из conan_options."""
    opts = _VariantOpts(
        conan_options=conan_options, install_options_override=install_options_override
    )
    view = PassportConverter._build_variant_view(publisher_conan_variant, COMP_NAME, opts)

    assert view.install_options == expected_install_options


# Тесты для PassportConverter._classify_option_badge (конкретная реализация
# BaseDataConverter._classify_option_badge).
@pytest.mark.business_logic
@pytest.mark.parametrize(
    "value,default_value,has_default,expected_badge",
    [
        ("True", "True", True, "autodoc-badge-def"),
        (True, False, True, "autodoc-badge-n"),
        (False, True, True, "autodoc-badge-n"),
        ("static", "shared", True, "autodoc-badge-n"),
        ("True", "True", False, "autodoc-badge-n"),
    ],
    ids=[
        "test_classify_option_badge_matches_default_is_default",
        "test_classify_option_badge_differs_bool_true_is_neutral",
        "test_classify_option_badge_differs_bool_false_is_neutral",
        "test_classify_option_badge_differs_non_boolean_is_neutral",
        "test_classify_option_badge_no_default_known_is_neutral",
    ],
)
def test_classify_option_badge(
    value: Any,
    default_value: Any,
    has_default: bool,
    expected_badge: str,
) -> None:
    """Возвращает корректный CSS-класс бейджа для сочетания значения/дефолта/наличия дефолта."""
    result = PassportConverter._classify_option_badge(value, default_value, has_default)

    assert result == expected_badge


# Тесты передачи include_passport_links из BaseReleaseConverter в view-model.
@pytest.mark.contract
@pytest.mark.parametrize("flag", [False, True])
def test_include_passport_links_is_forwarded(flag: bool) -> None:
    """view['include_passport_links'] равен переданному в конструктор значению."""
    converter = FullReleaseConverter(include_passport_links=flag)
    # _base_view_model требует ParsedResult только ради platform_version;
    # минимальной заглушки достаточно, поскольку читается только этот атрибут.
    view = converter._base_view_model(_MinimalParsedResult())

    assert view["include_passport_links"] is flag
