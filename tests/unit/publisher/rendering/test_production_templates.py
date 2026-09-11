"""
Тесты для production Jinja2-шаблонов в autodoc/publisher/rendering/.

Каждый тест рендерит шаблон и проверяет, что рендеринг не бросает исключение,
а вывод непуст. Часть тестов дополнительно проверяет конкретное содержимое
вывода (имя компонента, conan-референс, маркеры макросов os_style/docker_note,
CSS-классы из _styles_base.jinja2/_styles_passport.jinja2) — как на
минимальном самодельном контексте, так и на реальном выводе
ComponentCentricConverter/ProfileCentricConverter. Реальное подключение к
Confluence не выполняется.
"""

from pathlib import Path
from typing import Any

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.parsed_result import ParsedResult
from autodoc.models.release import Release
from autodoc.publisher.converters.component_centric_converter import ComponentCentricConverter
from autodoc.publisher.converters.kit_fixed_converter import KitFixedConverter
from autodoc.publisher.converters.kit_latest_converter import KitLatestConverter
from autodoc.publisher.converters.passport_converter import PassportConverter
from autodoc.publisher.converters.profile_converter import ProfileCentricConverter
from autodoc.publisher.rendering.document_builder import DocumentBuilder

# Корень директории рендеринга (templates/, styles/, macros/).
_RENDERING_DIR: Path = Path(__file__).parents[4] / "autodoc" / "publisher" / "rendering"

_RELEASE_DOC_TEMPLATE: str = "release_doc.jinja2"

# Устойчивые строковые маркеры для проверки в отрендеренном выводе.
_STYLES_BASE_MARKER: str = "autodoc-badge"  # присутствует в _styles_base.jinja2
_STYLES_PP_MARKER: str = "autodoc-page-header"  # присутствует в _styles_passport.jinja2
_OS_BADGE_MARKER: str = "autodoc-os-badge"  # результат работы макроса os_style()


def _make_parsed_result(component_name: str = "testlib") -> ParsedResult:
    """
    Строит минимальный ParsedResult с одним именованным компонентом для рендеринга шаблонов.

    Args:
        component_name: Имя единственного компонента результата.

    Returns:
        ParsedResult с одним компонентом без релизов.
    """
    component = Component(name=component_name, releases=[])
    return ParsedResult(
        generated_at="2024-01-15T12:00:00",
        platform_version="2.0",
        profile_definitions=[],
        components=[component],
    )


@pytest.fixture()
def builder() -> DocumentBuilder:
    """DocumentBuilder, указывающий на реальную директорию рендеринга."""
    return DocumentBuilder(_RENDERING_DIR)


@pytest.mark.integration
def test_macros_template_renders_without_error(
    builder: DocumentBuilder, publisher_parsed_result: ParsedResult
) -> None:
    """release_doc.jinja2 рендерится без ошибок и действительно вызывает макросы os_style/docker_note на непустом релизе."""
    ghost_pb = ProfileBuild(profile_name="ghost-profile", exists=True, variants=[])
    original_comp = publisher_parsed_result.components[0]
    original_rel = original_comp.releases[0]
    patched_rel = original_rel.model_copy(
        update={"profile_builds": original_rel.profile_builds + [ghost_pb]}
    )
    patched_comp = original_comp.model_copy(update={"releases": [patched_rel]})
    patched_result = publisher_parsed_result.model_copy(update={"components": [patched_comp]})

    view_model: dict[str, Any] = ComponentCentricConverter(include_passport_links=False).convert(
        patched_result
    )
    output: str = builder.build(_RELEASE_DOC_TEMPLATE, view_model)

    assert output.strip(), "Отрендеренный вывод release_doc.jinja2 пуст"
    assert _OS_BADGE_MARKER in output, "В выводе не найден результат работы макроса os_style()"
    assert (
        "autodoc-italic-note" in output
    ), "В выводе не найден результат работы макроса docker_note()"


@pytest.mark.infrastructure
def test_styles_base_template_renders_without_error(
    builder: DocumentBuilder,
) -> None:
    """_styles_base.jinja2 подключается через release_doc.jinja2 и должен рендериться без ошибок."""
    view_model: dict[str, Any] = _make_parsed_result().model_dump()
    output: str = builder.build(_RELEASE_DOC_TEMPLATE, view_model)
    assert output.strip(), "Отрендеренный вывод пуст"
    assert (
        _STYLES_BASE_MARKER in output
    ), f"Ожидался маркер '{_STYLES_BASE_MARKER}' в выводе (из _styles_base.jinja2)"


@pytest.mark.integration
def test_styles_passport_template_renders_without_error(
    builder: DocumentBuilder,
) -> None:
    """_styles_passport.jinja2 подключается через component_passport.jinja2 и должен рендериться без ошибок."""
    component = Component(
        name="testlib",
        description="A test library",
        git_url="https://tfs.example.com/_git/testlib",
        is_header_only=False,
        releases=[
            Release(
                version="1.0.0",
                platform="2.0",
                channel="fast",
                profile_builds=[],
            )
        ],
    )
    parsed_result = ParsedResult(
        generated_at="2024-01-15T12:00:00",
        platform_version="2.0",
        profile_definitions=[],
        components=[component],
    )
    view_model: dict[str, Any] = PassportConverter("testlib", "1.0.0").convert(parsed_result)
    # PassportConverter намеренно не устанавливает legacy_contents — это делает
    # PassportsStrategy перед вызовом builder.build() (см. test_passport_converter.py:
    # "legacy_contents не должен устанавливаться конвертером"). Шаблон ожидает
    # этот ключ, поэтому воспроизводим здесь то же внедрение вручную.
    view_model["legacy_contents"] = {}
    output: str = builder.build("component_passport.jinja2", view_model)
    assert output.strip(), "Отрендеренный вывод component_passport.jinja2 пуст"
    assert (
        _STYLES_PP_MARKER in output
    ), f"Ожидался маркер '{_STYLES_PP_MARKER}' в выводе (из _styles_passport.jinja2)"


@pytest.mark.infrastructure
def test_main_component_template_contains_component_name(
    builder: DocumentBuilder,
) -> None:
    """release_doc.jinja2 должен содержать имя компонента в отрендеренном выводе."""
    _COMPONENT_NAME: str = "my_sentinel_component"
    view_model: dict[str, Any] = _make_parsed_result(_COMPONENT_NAME).model_dump()
    output: str = builder.build(_RELEASE_DOC_TEMPLATE, view_model)
    assert (
        _COMPONENT_NAME in output
    ), f"Имя компонента '{_COMPONENT_NAME}' не найдено в отрендеренном выводе release_doc"


@pytest.mark.integration
def test_release_doc_template_renders_component_centric_converter_output_with_real_release(
    builder: DocumentBuilder, publisher_parsed_result: ParsedResult
) -> None:
    """release_doc.jinja2 рендерит реальный вывод ComponentCentricConverter.convert() над непустым релизом с профилями и вариантами."""
    view_model: dict[str, Any] = ComponentCentricConverter(include_passport_links=False).convert(
        publisher_parsed_result
    )

    output: str = builder.build(_RELEASE_DOC_TEMPLATE, view_model)

    comp = publisher_parsed_result.components[0]
    release = comp.releases[0]
    assert output.strip(), "Отрендеренный вывод release_doc.jinja2 пуст"
    assert comp.name in output, "Имя компонента из реальных данных релиза не найдено в выводе"
    assert (
        release.conan_reference in output
    ), "Conan-референс из реальных данных релиза не найден в выводе"
    assert (
        _OS_BADGE_MARKER in output
    ), "Путь пер-профильного рендеринга (os_style) не был задействован"


@pytest.mark.integration
def test_profile_centric_template_renders_without_error(
    builder: DocumentBuilder, publisher_multi_channel_result: ParsedResult
) -> None:
    """profile_centric.jinja2 рендерится без ошибок на реальном профиль-центричном виде."""
    view_model: dict[str, Any] = ProfileCentricConverter(include_passport_links=False).convert(
        publisher_multi_channel_result
    )

    output: str = builder.build("profile_centric.jinja2", view_model)

    assert output.strip(), "Отрендеренный вывод profile_centric.jinja2 пуст"


_EMBEDDING_KIT_TEMPLATE: str = "embedding_kit.jinja2"


@pytest.mark.integration
def test_embedding_kit_template_renders_kit_fixed_converter_output(
    builder: DocumentBuilder, publisher_multi_component_result: ParsedResult
) -> None:
    """
    embedding_kit.jinja2 рендерит реальный вывод KitFixedConverter: точные Conan-ссылки,
    сгруппированные по каналам, с заголовком колонки 'Фиксированная версия'.
    """
    view_model: dict[str, Any] = KitFixedConverter().convert(publisher_multi_component_result)

    output: str = builder.build(_EMBEDDING_KIT_TEMPLATE, view_model)

    assert output.strip(), "Отрендеренный вывод embedding_kit.jinja2 пуст"
    assert "Фиксированная версия" in output
    assert "openssl/1.0.0@platform/2.0-tech" in output
    assert "zlib/1.2.11@platform/2.0-tech" in output
    assert "Канал tech" in output
    assert "Канал stable" in output


@pytest.mark.integration
def test_embedding_kit_template_renders_kit_latest_converter_output(
    builder: DocumentBuilder, publisher_multi_component_result: ParsedResult
) -> None:
    """
    embedding_kit.jinja2 рендерит реальный вывод KitLatestConverter: диапазонные
    ссылки [,include_prerelease], сгруппированные по каналам, с заголовком колонки
    'Последняя сборка'.
    """
    view_model: dict[str, Any] = KitLatestConverter().convert(publisher_multi_component_result)

    output: str = builder.build(_EMBEDDING_KIT_TEMPLATE, view_model)

    assert output.strip(), "Отрендеренный вывод embedding_kit.jinja2 пуст"
    assert "Последняя сборка" in output
    assert "openssl/[,include_prerelease]@platform-2.0/tech" in output
    assert "zlib/[,include_prerelease]@platform-2.0/tech" in output
    assert (
        "1.0.0" not in output
    ), "Страница последних сборок не должна содержать пиннированных версий"


@pytest.mark.infrastructure
def test_embedding_kit_template_renders_without_error_on_empty_channels(
    builder: DocumentBuilder,
) -> None:
    """
    embedding_kit.jinja2 не падает и возвращает пустой (без таблиц) вывод, если
    channels пуст — например, для ParsedResult без компонентов.
    """
    view_model: dict[str, Any] = {
        "platform_version": "2.0",
        "version_column_title": "Фиксированная версия",
        "channels": [],
    }
    output: str = builder.build(_EMBEDDING_KIT_TEMPLATE, view_model)
    assert output.strip() == "", "При отсутствии каналов таблиц быть не должно"
