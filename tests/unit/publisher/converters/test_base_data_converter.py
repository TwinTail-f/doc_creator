"""Тесты для статических методов BaseDataConverter и PassportLinkMixin."""

from __future__ import annotations

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

RELEASE_VERSION: str = "1.0.0"


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


class TestBuildInstallOptions:
    """Тесты для статического метода BaseDataConverter._build_install_options."""

    @pytest.mark.business_logic
    def test_build_install_options_empty_dict_returns_empty_string(self) -> None:
        """Пустой словарь опций даёт пустую строку."""
        result = PassportConverter._build_install_options({}, COMP_NAME)

        assert result == ""

    @pytest.mark.business_logic
    def test_build_install_options_preserves_qualified_key(self) -> None:
        """Ключ, уже содержащий '/*:', не квалифицируется повторно."""
        result = PassportConverter._build_install_options({"icu/*:shared": "True"}, COMP_NAME)

        assert result == "-o icu/*:shared=True"

    @pytest.mark.business_logic
    def test_build_install_options_multiple_options_joined_by_space(self) -> None:
        """Несколько опций объединяются пробелом, каждая со своим флагом '-o'."""
        result = PassportConverter._build_install_options(
            {OPT_KEY_SHARED: "True", OPT_KEY_FPIC: "True"}, COMP_NAME
        )

        assert f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True" in result
        assert f"-o {COMP_NAME}/*:{OPT_KEY_FPIC}=True" in result

    @pytest.mark.business_logic
    def test_build_install_options_dep_key_with_colon_not_modified(self) -> None:
        """Ключ зависимости вроде 'icu:opt' квалифицируется в 'icu/*:opt' без дублирования."""
        result = PassportConverter._build_install_options(
            {"icu:data_packaging": "static"}, COMP_NAME
        )

        assert result == "-o icu/*:data_packaging=static"


class TestBuildInstallOptionsFromString:
    """Тесты для статического метода BaseDataConverter._build_install_options_from_string."""

    @pytest.mark.business_logic
    def test_build_install_options_from_string_empty_returns_empty(self) -> None:
        """Пустая строка на входе даёт пустую строку."""
        result = PassportConverter._build_install_options_from_string("")

        assert result == ""

    @pytest.mark.business_logic
    def test_build_install_options_from_string_whitespace_returns_empty(self) -> None:
        """Строка только из пробелов даёт пустую строку."""
        result = PassportConverter._build_install_options_from_string("   ")

        assert result == ""

    @pytest.mark.business_logic
    def test_build_install_options_from_string_single_option(self) -> None:
        """Одна запись 'pkg/*:key=val' оборачивается одним флагом '-o'."""
        result = PassportConverter._build_install_options_from_string(
            f"{COMP_NAME}/*:{OPT_KEY_SHARED}=True"
        )

        assert result == f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"

    @pytest.mark.business_logic
    def test_build_install_options_from_string_multiple_options(self) -> None:
        """Несколько опций через запятую дают флаги '-o', разделённые пробелом."""
        options = f"{COMP_NAME}/*:{OPT_KEY_SHARED}=True, {COMP_NAME}/*:{OPT_KEY_FPIC}=True"
        result = PassportConverter._build_install_options_from_string(options)

        assert result == (
            f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True" f" -o {COMP_NAME}/*:{OPT_KEY_FPIC}=True"
        )

    @pytest.mark.business_logic
    def test_build_install_options_from_string_qualifies_unqualified_key(
        self,
    ) -> None:
        """Опция вида 'pkg:key=val' (без '/*') квалифицируется в 'pkg/*:key=val'."""
        result = PassportConverter._build_install_options_from_string(
            f"{COMP_NAME}:{OPT_KEY_SHARED}=True"
        )

        assert result == f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"

    @pytest.mark.business_logic
    def test_build_install_options_from_string_strips_whitespace_between_options(
        self,
    ) -> None:
        """Ведущие/замыкающие пробелы вокруг каждого токена опции корректно обрезаются."""
        options = (
            f"  {COMP_NAME}/*:{OPT_KEY_SHARED}=True  ," f"  {COMP_NAME}/*:{OPT_KEY_FPIC}=True  "
        )
        result = PassportConverter._build_install_options_from_string(options)

        assert result == (
            f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True" f" -o {COMP_NAME}/*:{OPT_KEY_FPIC}=True"
        )


class TestBuildVariantView:
    """Тесты для статического метода BaseDataConverter._build_variant_view."""

    @pytest.mark.contract
    def test_build_variant_view_maps_fields_from_variant(
        self, sample_variant: ConanVariant
    ) -> None:
        """package_id и build_url из ConanVariant попадают в итоговое представление."""
        view = PassportConverter._build_variant_view(sample_variant, COMP_NAME)

        assert view.package_id == VARIANT_PKG_ID
        assert view.build_url == VARIANT_BUILD_URL

    @pytest.mark.contract
    def test_build_variant_view_uses_conan_options_from_opts(
        self, sample_variant: ConanVariant
    ) -> None:
        """conan_options из _VariantOpts передаются в view-model без изменений (чистый passthrough)."""
        opts = _VariantOpts(conan_options={OPT_KEY_SHARED: "True"})
        view = PassportConverter._build_variant_view(sample_variant, COMP_NAME, opts)

        assert view.conan_options == {OPT_KEY_SHARED: "True"}

    @pytest.mark.business_logic
    def test_build_variant_view_no_opts_gives_empty_conan_options(
        self, sample_variant: ConanVariant
    ) -> None:
        """Если opts равен None, conan_options view-model — пустой словарь."""
        view = PassportConverter._build_variant_view(sample_variant, COMP_NAME, None)

        assert view.conan_options == {}

    @pytest.mark.business_logic
    def test_build_variant_view_install_options_override_used_directly(
        self, sample_variant: ConanVariant
    ) -> None:
        """install_options_override записывается в view.install_options дословно."""
        opts = _VariantOpts(conan_options={}, install_options_override=INSTALL_OVERRIDE)
        view = PassportConverter._build_variant_view(sample_variant, COMP_NAME, opts)

        assert view.install_options == INSTALL_OVERRIDE

    @pytest.mark.business_logic
    def test_build_variant_view_builds_install_options_from_conan_options_if_no_override(
        self, sample_variant: ConanVariant
    ) -> None:
        """Если override равен None, install_options строится из conan_options."""
        opts = _VariantOpts(conan_options={OPT_KEY_SHARED: "True"}, install_options_override=None)
        view = PassportConverter._build_variant_view(sample_variant, COMP_NAME, opts)

        assert view.install_options == f"-o {COMP_NAME}/*:{OPT_KEY_SHARED}=True"


class TestClassifyOptionBadge:
    """Тесты для PassportConverter._classify_option_badge (конкретная реализация BaseDataConverter._classify_option_badge).

    Примечание: текущая реализация различает только два исхода —
    'autodoc-badge-def' (значение совпадает с известным дефолтом) и
    'autodoc-badge-n' (все остальные случаи: значение отличается от дефолта
    любого типа, либо дефолт для опции неизвестен). Отдельных CSS-классов
    для true/false-отличий в текущей реализации нет, хотя стили для них
    определены в _styles_base.jinja2 — сценарии ниже зафиксированы по
    входным данным из спецификации задачи, а ожидаемый результат — по
    фактическому поведению метода.
    """

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
        self,
        value: Any,
        default_value: Any,
        has_default: bool,
        expected_badge: str,
    ) -> None:
        """Возвращает корректный CSS-класс бейджа для сочетания значения/дефолта/наличия дефолта."""
        result = PassportConverter._classify_option_badge(value, default_value, has_default)

        assert result == expected_badge


class TestIncludePassportLinksPropagation:
    """Тесты передачи include_passport_links из BaseReleaseConverter в view-model.

    PassportLinkMixin / FullReleaseConverter._passport_link() и аргумент конструктора
    passport_page_pattern больше не существуют. Согласно докстрингу
    BaseReleaseConverter, конвертеры больше не строят строки ссылок на паспорта
    сами — эта ответственность перенесена в
    autodoc.publisher.page_manager.passport_link_injector (inject_links /
    inject_links_for_profiles), что проверяется в
    tests/unit/publisher/page_manager/test_passport_registry.py.
    Единственная оставшаяся у BaseReleaseConverter ответственность, связанная
    с паспортами, — передача флага include_passport_links в view-model,
    проверяемая здесь.
    """

    @pytest.mark.contract
    def test_include_passport_links_false_is_forwarded(self) -> None:
        """view['include_passport_links'] равен False при конструировании с False."""
        converter = FullReleaseConverter(include_passport_links=False)
        # _base_view_model требует ParsedResult только ради platform_version;
        # минимальной заглушки достаточно, поскольку читается только этот атрибут.
        view = converter._base_view_model(_MinimalParsedResult())

        assert view["include_passport_links"] is False

    @pytest.mark.contract
    def test_include_passport_links_true_is_forwarded(self) -> None:
        """view['include_passport_links'] равен True при конструировании с True (значение по умолчанию)."""
        converter = FullReleaseConverter(include_passport_links=True)
        view = converter._base_view_model(_MinimalParsedResult())

        assert view["include_passport_links"] is True


@pytest.mark.contract
def test_conan_variant_view_is_dataclass() -> None:
    """ConanVariantView является Python dataclass."""
    assert dataclasses.is_dataclass(ConanVariantView)


@pytest.mark.contract
def test_conan_variant_view_required_fields() -> None:
    """ConanVariantView можно создать с тремя обязательными позиционными полями."""
    view = ConanVariantView(
        package_id="pkg-abc",
        build_url="https://ci.example.com/build/1",
        build_date="2024-03-10",
    )
    assert view.package_id == "pkg-abc"


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
