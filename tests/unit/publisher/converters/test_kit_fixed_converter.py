"""
Тесты для autodoc.publisher.converters.kit_fixed_converter.KitFixedConverter.

Стратегия тестирования:
- Вход строится вручную (не через фикстуры release-конвертеров), так как
  конвертеру нужны только name/version/channel/conan_reference.
- Проверяются: порядок каналов, сохранение порядка компонентов внутри
  канала, отсутствие дедупликации разных версий одного компонента,
  запасной вариант ссылки при пустом conan_reference.
"""

import pytest

from autodoc.models.component import Component
from autodoc.models.parsed_result import ParsedResult
from autodoc.models.release import Release
from autodoc.publisher.converters.kit_fixed_converter import KitFixedConverter


def _release(version: str, channel: str, conan_reference: str = "") -> Release:
    return Release(version=version, platform="2.0", channel=channel, conan_reference=conan_reference)


@pytest.mark.business_logic
def test_convert_groups_references_by_channel() -> None:
    """Каждый релиз попадает в список своего канала, а не общий список."""
    comps = [
        Component(
            name="openssl",
            releases=[_release("3.5.6", "trusted", "openssl/3.5.6@platform-2.0/trusted")],
        ),
        Component(
            name="boost", releases=[_release("1.74.0", "slow", "boost/1.74.0@platform-2.0/slow")]
        ),
    ]
    data = ParsedResult(generated_at="2024-01-01T00:00:00", platform_version="2.0", components=comps)

    view_model = KitFixedConverter().convert(data)

    channels_by_name = {c["name"]: c["references"] for c in view_model["channels"]}
    assert channels_by_name["trusted"] == ["openssl/3.5.6@platform-2.0/trusted"]
    assert channels_by_name["slow"] == ["boost/1.74.0@platform-2.0/slow"]


@pytest.mark.business_logic
def test_convert_orders_known_channels_tech_trusted_slow_fast() -> None:
    """Известные каналы выводятся в фиксированном порядке tech, trusted, slow, fast,
    независимо от порядка их появления в данных."""
    comps = [
        Component(name="a", releases=[_release("1.0", "fast", "a/1.0@platform-2.0/fast")]),
        Component(name="b", releases=[_release("1.0", "slow", "b/1.0@platform-2.0/slow")]),
        Component(name="c", releases=[_release("1.0", "trusted", "c/1.0@platform-2.0/trusted")]),
        Component(name="d", releases=[_release("1.0", "tech", "d/1.0@platform-2.0/tech")]),
    ]
    data = ParsedResult(generated_at="2024-01-01T00:00:00", platform_version="2.0", components=comps)

    view_model = KitFixedConverter().convert(data)

    assert [c["name"] for c in view_model["channels"]] == ["tech", "trusted", "slow", "fast"]


@pytest.mark.business_logic
def test_convert_unknown_channel_appended_after_known_ones_sorted() -> None:
    """Каналы вне CHANNEL_ORDER выводятся после известных, в алфавитном порядке."""
    comps = [
        Component(name="a", releases=[_release("1.0", "zeta", "a/1.0@platform-2.0/zeta")]),
        Component(name="b", releases=[_release("1.0", "fast", "b/1.0@platform-2.0/fast")]),
        Component(name="c", releases=[_release("1.0", "alpha", "c/1.0@platform-2.0/alpha")]),
    ]
    data = ParsedResult(generated_at="2024-01-01T00:00:00", platform_version="2.0", components=comps)

    view_model = KitFixedConverter().convert(data)

    assert [c["name"] for c in view_model["channels"]] == ["fast", "alpha", "zeta"]


@pytest.mark.business_logic
def test_convert_preserves_component_order_within_channel() -> None:
    """Строки внутри канала сохраняют порядок ParsedResult.components — без сортировки."""
    comps = [
        Component(name="benchmark", releases=[_release("1.9.5", "tech", "benchmark/1.9.5@platform-2.0/tech")]),
        Component(name="gtest", releases=[_release("1.17.0", "tech", "gtest/1.17.0@platform-2.0/tech")]),
        Component(name="cmake", releases=[_release("4.2.2", "tech", "cmake/4.2.2@platform-2.0/tech")]),
    ]
    data = ParsedResult(generated_at="2024-01-01T00:00:00", platform_version="2.0", components=comps)

    view_model = KitFixedConverter().convert(data)

    tech = next(c for c in view_model["channels"] if c["name"] == "tech")
    assert tech["references"] == [
        "benchmark/1.9.5@platform-2.0/tech",
        "gtest/1.17.0@platform-2.0/tech",
        "cmake/4.2.2@platform-2.0/tech",
    ]


@pytest.mark.business_logic
def test_convert_keeps_every_version_of_same_component_in_same_channel() -> None:
    """Несколько версий одного компонента в одном канале — каждая своя строка (без дедупликации)."""
    comp = Component(
        name="patchelf",
        releases=[
            _release("0.16.1", "tech", "patchelf/0.16.1@platform-2.0/tech"),
            _release("0.18.0", "tech", "patchelf/0.18.0@platform-2.0/tech"),
        ],
    )
    data = ParsedResult(
        generated_at="2024-01-01T00:00:00", platform_version="2.0", components=[comp]
    )

    view_model = KitFixedConverter().convert(data)

    tech = next(c for c in view_model["channels"] if c["name"] == "tech")
    assert tech["references"] == [
        "patchelf/0.16.1@platform-2.0/tech",
        "patchelf/0.18.0@platform-2.0/tech",
    ]


@pytest.mark.business_logic
def test_convert_falls_back_to_built_reference_when_conan_reference_empty() -> None:
    """Если conan_reference не заполнен (пустая строка) — ссылка строится по шаблону
    name/version@platform-{platform_version}/channel."""
    comp = Component(name="zlib", releases=[_release("1.2.11", "slow", conan_reference="")])
    data = ParsedResult(
        generated_at="2024-01-01T00:00:00", platform_version="2.0", components=[comp]
    )

    view_model = KitFixedConverter().convert(data)

    slow = next(c for c in view_model["channels"] if c["name"] == "slow")
    assert slow["references"] == ["zlib/1.2.11@platform-2.0/slow"]


@pytest.mark.contract
def test_convert_sets_version_column_title_and_platform_version() -> None:
    """view-model содержит заголовок колонки и версию платформы верхнего уровня."""
    data = ParsedResult(generated_at="2024-01-01T00:00:00", platform_version="2.2", components=[])

    view_model = KitFixedConverter().convert(data)

    assert view_model["version_column_title"] == "Фиксированная версия"
    assert view_model["platform_version"] == "2.2"
    assert view_model["channels"] == []
