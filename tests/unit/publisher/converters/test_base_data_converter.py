"""Тесты для статических методов BaseDataConverter и PassportLinkMixin."""
import pytest

from autodoc.models.conan_variant import ConanVariant
from autodoc.publisher.converters.base_data_converter import BaseDataConverter, _VariantOpts
from autodoc.publisher.converters.passport_converter import PassportConverter
from autodoc.publisher.converters.full_release_converter import FullReleaseConverter
from autodoc.publisher.view_models.passports import ConanVariantView
import dataclasses
from typing import Any

COMP_NAME: str = "openssl"
OPT_KEY_SHARED: str = "shared"
OPT_KEY_FPIC: str = "fPIC"


class _MinimalParsedResult:
    """Минимальная замена ParsedResult, экспонирующая только то, что читает _base_view_model."""

    platform_version: str = "2.0"

VARIANT_PKG_ID: str = "abc"
VARIANT_BUILD_URL: str = "https://ci/1"
VARIANT_BUILD_DATE: str = "2024-01-01"
VARIANT_OPT_REF: str = "r1"

INSTALL_OVERRIDE: str = "-o pkg/*:x=1"


@pytest.fixture
def sample_variant() -> ConanVariant:
    """ConanVariant со всеми заполненными полями, используется в нескольких тестах статических методов."""
    return ConanVariant(
        package_id=VARIANT_PKG_ID,
        build_url=VARIANT_BUILD_URL,
        build_date=VARIANT_BUILD_DATE,
        options_ref=VARIANT_OPT_REF,
    )


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
    ],
)
def test_build_install_options(conan_options: dict[str, str], expected: str) -> None:
    """_build_install_options форматирует опции варианта в флаги '-o' по правилам квалификации ключей."""
    result = PassportConverter._build_install_options(conan_options, COMP_NAME)

    assert result == expected


@pytest.mark.business_logic
def test_build_install_options_multiple_options_joined_by_space() -> None:
    """Несколько опций объединяются пробелом, каждая со своим флагом '-o'."""
    result = PassportConverter._build_install_options(
        {OPT_KEY_SHARED: "True", OPT_KEY_FPIC: "True"}, COMP_NAME
    )

    assert f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True" in result
    assert f"-o {COMP_NAME}/*:{OPT_KEY_FPIC}=True" in result


_MULTI_OPTION_RESULT: str = (
    f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True" f" -o {COMP_NAME}/*:{OPT_KEY_FPIC}=True"
)


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
def test_variant_opts_is_frozen_dataclass() -> None:
    """_VariantOpts заморожен (frozen=True) — присвоение поля после создания поднимает ошибку."""
    opts = _VariantOpts(conan_options={})

    with pytest.raises(dataclasses.FrozenInstanceError):
        opts.conan_options = {"x": "1"}


@pytest.mark.business_logic
def test_variant_opts_default_options_default_is_not_shared_between_instances() -> None:
    """default_options по умолчанию — независимый dict на каждый экземпляр, а не общий объект.
    """
    opts_a = _VariantOpts(conan_options={})
    opts_b = _VariantOpts(conan_options={})

    assert opts_a.default_options is not opts_b.default_options

    opts_a.default_options["shared"] = "True"

    assert opts_b.default_options == {}


@pytest.mark.contract
def test_build_variant_view_maps_fields_from_variant(sample_variant: ConanVariant) -> None:
    """package_id и build_url из ConanVariant попадают в итоговое представление."""
    view = PassportConverter._build_variant_view(sample_variant, COMP_NAME)

    assert view.package_id == VARIANT_PKG_ID
    assert view.build_url == VARIANT_BUILD_URL


@pytest.mark.contract
def test_build_variant_view_uses_conan_options_from_opts(sample_variant: ConanVariant) -> None:
    """conan_options из _VariantOpts передаются в view-model без изменений (чистый passthrough)."""
    opts = _VariantOpts(conan_options={OPT_KEY_SHARED: "True"})
    view = PassportConverter._build_variant_view(sample_variant, COMP_NAME, opts)

    assert view.conan_options == {OPT_KEY_SHARED: "True"}


@pytest.mark.business_logic
def test_build_variant_view_no_opts_gives_empty_conan_options(sample_variant: ConanVariant) -> None:
    """Если opts равен None, conan_options view-model — пустой словарь."""
    view = PassportConverter._build_variant_view(sample_variant, COMP_NAME, None)

    assert view.conan_options == {}


@pytest.mark.business_logic
def test_build_variant_view_install_options_override_used_directly(
    sample_variant: ConanVariant,
) -> None:
    """install_options_override записывается в view.install_options дословно."""
    opts = _VariantOpts(conan_options={}, install_options_override=INSTALL_OVERRIDE)
    view = PassportConverter._build_variant_view(sample_variant, COMP_NAME, opts)

    assert view.install_options == INSTALL_OVERRIDE


@pytest.mark.business_logic
def test_build_variant_view_builds_install_options_from_conan_options_if_no_override(
    sample_variant: ConanVariant,
) -> None:
    """Если override равен None, install_options строится из conan_options."""
    opts = _VariantOpts(conan_options={OPT_KEY_SHARED: "True"}, install_options_override=None)
    view = PassportConverter._build_variant_view(sample_variant, COMP_NAME, opts)

    assert view.install_options == f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"


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
        "test_classify_option_badge_matches_default_is_neutral",
        "test_classify_option_badge_differs_true_is_green",
        "test_classify_option_badge_differs_false_is_red",
        "test_classify_option_badge_differs_non_boolean_is_yellow",
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


@pytest.mark.contract
def test_conan_variant_view_defaults() -> None:
    """Необязательные поля ConanVariantView по умолчанию — пустая строка / пустой словарь."""
    view = ConanVariantView(
        package_id="pkg-abc",
        build_url="https://ci.example.com/build/1",
        build_date="2024-03-10",
    )
    assert view.options_ref == ""
    assert view.conan_options == {}
    assert view.install_options == ""


@pytest.mark.contract
def test_conan_variant_view_custom_values() -> None:
    """ConanVariantView корректно хранит все переданные значения полей."""
    opts: dict[str, Any] = {"shared": "True", "fPIC": "False"}
    view = ConanVariantView(
        package_id="deadbeef",
        build_url="https://ci.example.com/build/99",
        build_date="2024-06-01",
        options_ref="opt-set-7",
        conan_options=opts,
        install_options="-o pkg/*:shared=True -o pkg/*:fPIC=False",
    )
    assert view.package_id == "deadbeef"
    assert view.build_url == "https://ci.example.com/build/99"
    assert view.build_date == "2024-06-01"
    assert view.options_ref == "opt-set-7"
    assert view.conan_options == opts
    assert view.install_options == "-o pkg/*:shared=True -o pkg/*:fPIC=False"
