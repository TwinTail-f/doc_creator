"""Юнит-тесты для autodoc.models.
"""

import pytest

from autodoc.models.options import ConanInputOptions, _parse_option_str


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "option_str, expected",
    [
        # обычный префикс пакета удаляется из каждого ключа
        pytest.param(
            "mylib:shared=True,mylib:fPIC=False",
            {"shared": "True", "fPIC": "False"},
            id="strips-package-prefix",
        ),
        # пустая строка -> пустой словарь
        pytest.param("", {}, id="empty-string"),
        # ключи без префикса пакета принимаются как есть
        pytest.param("shared=True", {"shared": "True"}, id="no-prefix"),
        # префикс с символом подстановки (mylib/*:key) тоже удаляется целиком
        pytest.param("mylib/*:shared=True", {"shared": "True"}, id="wildcard-prefix"),
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
        pytest.param(
            "pkg:shared=True,pkg:fPIC=False",
            None,
            {"shared": "True", "fPIC": "False"},
            id="auto-filled",
        ),
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
    """
    kwargs: dict[str, object] = {"id": "1", "options": options_str}
    if explicit_parsed is not None:
        kwargs["parsed_options"] = explicit_parsed
    instance = ConanInputOptions(**kwargs)
    assert instance.parsed_options == expected

