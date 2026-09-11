"""
Тесты для autodoc.publisher.converters.kit_latest_converter.KitLatestConverter.

Стратегия тестирования: зеркалит test_kit_fixed_converter.py, но с акцентом
на отличия KitLatestConverter — литеральный диапазон [,include_prerelease]
и дедупликация по имени компонента (а не по паре компонент+версия).
"""

import pytest

from autodoc.models.component import Component
from autodoc.models.parsed_result import ParsedResult
from autodoc.models.release import Release
from autodoc.publisher.converters.kit_latest_converter import KitLatestConverter


def _release(version: str, channel: str, conan_reference: str = "") -> Release:
    return Release(
        version=version, platform="2.0", channel=channel, conan_reference=conan_reference
    )


@pytest.mark.business_logic
def test_convert_builds_include_prerelease_reference_ignoring_conan_reference() -> None:
    """
    Ссылка строится как name/[,include_prerelease]@platform-{version}/{channel},
    независимо от реального conan_reference релиза (версия не фиксируется)."""
    comp = Component(
        name="openssl",
        releases=[_release("3.5.6.1074", "trusted", "openssl/3.5.6.1074@platform-2.0/trusted")],
    )
    data = ParsedResult(
        generated_at="2024-01-01T00:00:00", platform_version="2.0", components=[comp]
    )

    view_model = KitLatestConverter().convert(data)

    trusted = next(c for c in view_model["channels"] if c["name"] == "trusted")
    assert trusted["references"] == ["openssl/[,include_prerelease]@platform-2.0/trusted"]


@pytest.mark.business_logic
def test_convert_dedupes_multiple_versions_of_same_component_into_one_row() -> None:
    """
    Несколько версий одного компонента в одном канале схлопываются в одну строку
    (в отличие от KitFixedConverter)."""
    comp = Component(
        name="patchelf",
        releases=[
            _release("0.16.1.38", "tech", "patchelf/0.16.1.38@platform-2.0/tech"),
            _release("0.18.0.39", "tech", "patchelf/0.18.0.39@platform-2.0/tech"),
        ],
    )
    data = ParsedResult(
        generated_at="2024-01-01T00:00:00", platform_version="2.0", components=[comp]
    )

    view_model = KitLatestConverter().convert(data)

    tech = next(c for c in view_model["channels"] if c["name"] == "tech")
    assert tech["references"] == ["patchelf/[,include_prerelease]@platform-2.0/tech"]


@pytest.mark.business_logic
def test_convert_same_component_in_different_channels_gets_separate_rows() -> None:
    """
    Один и тот же компонент в разных каналах — отдельная строка в каждом канале
    (дедупликация работает только внутри канала)."""
    comp = Component(
        name="nginx",
        releases=[
            _release("1.18.0", "slow", "nginx/1.18.0@platform-2.0/slow"),
            _release("1.30.2", "trusted", "nginx/1.30.2@platform-2.0/trusted"),
        ],
    )
    data = ParsedResult(
        generated_at="2024-01-01T00:00:00", platform_version="2.0", components=[comp]
    )

    view_model = KitLatestConverter().convert(data)

    channels_by_name = {c["name"]: c["references"] for c in view_model["channels"]}
    assert channels_by_name["slow"] == ["nginx/[,include_prerelease]@platform-2.0/slow"]
    assert channels_by_name["trusted"] == ["nginx/[,include_prerelease]@platform-2.0/trusted"]


@pytest.mark.business_logic
def test_convert_orders_known_channels_tech_trusted_slow_fast() -> None:
    """Известные каналы выводятся в фиксированном порядке, как и в KitFixedConverter."""
    comps = [
        Component(name="a", releases=[_release("1.0", "fast")]),
        Component(name="b", releases=[_release("1.0", "slow")]),
        Component(name="c", releases=[_release("1.0", "trusted")]),
        Component(name="d", releases=[_release("1.0", "tech")]),
    ]
    data = ParsedResult(
        generated_at="2024-01-01T00:00:00", platform_version="2.0", components=comps
    )

    view_model = KitLatestConverter().convert(data)

    assert [c["name"] for c in view_model["channels"]] == ["tech", "trusted", "slow", "fast"]


@pytest.mark.business_logic
def test_convert_preserves_component_order_within_channel() -> None:
    """Строки внутри канала сохраняют порядок ParsedResult.components — без сортировки."""
    comps = [
        Component(name="benchmark", releases=[_release("1.9.5", "tech")]),
        Component(name="gtest", releases=[_release("1.17.0", "tech")]),
        Component(name="cmake", releases=[_release("4.2.2", "tech")]),
    ]
    data = ParsedResult(
        generated_at="2024-01-01T00:00:00", platform_version="2.0", components=comps
    )

    view_model = KitLatestConverter().convert(data)

    tech = next(c for c in view_model["channels"] if c["name"] == "tech")
    assert tech["references"] == [
        "benchmark/[,include_prerelease]@platform-2.0/tech",
        "gtest/[,include_prerelease]@platform-2.0/tech",
        "cmake/[,include_prerelease]@platform-2.0/tech",
    ]


@pytest.mark.contract
def test_convert_sets_version_column_title_and_platform_version() -> None:
    """view-model содержит заголовок колонки и версию платформы верхнего уровня."""
    data = ParsedResult(generated_at="2024-01-01T00:00:00", platform_version="2.2", components=[])

    view_model = KitLatestConverter().convert(data)

    assert view_model["version_column_title"] == "Последняя сборка"
    assert view_model["platform_version"] == "2.2"
    assert view_model["channels"] == []
