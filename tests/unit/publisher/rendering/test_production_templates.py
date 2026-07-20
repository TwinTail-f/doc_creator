"""Тесты для production Jinja2-шаблонов в autodoc/publisher/rendering/.

Каждый тест рендерит шаблон и проверяет, что рендеринг не бросает исключение,
а вывод непуст. Часть тестов дополнительно проверяет конкретное содержимое
вывода (имя компонента, conan-референс, маркеры макросов os_style/docker_note,
CSS-классы из _styles_base.jinja2/_styles_passport.jinja2) — как на
минимальном самодельном контексте, так и на реальном выводе
FullReleaseConverter/ProfileCentricConverter. Реальное подключение к
Confluence не выполняется.
"""

from pathlib import Path
from typing import Any

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.parsed_result import ParsedResult
from autodoc.models.release import Release
from autodoc.publisher.converters.full_release_converter import FullReleaseConverter
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
    """Строит минимальный ParsedResult с одним именованным компонентом для рендеринга шаблонов.

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

    view_model: dict[str, Any] = FullReleaseConverter(include_passport_links=False).convert(
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


@pytest.mark.infrastructure
def test_styles_passport_template_renders_without_error(
    builder: DocumentBuilder,
) -> None:
    """_styles_passport.jinja2 подключается через component_passport.jinja2 и должен рендериться без ошибок."""
    GIT_URL = "https://tfs.example.com/_git/testlib"
    component = Component(
        name="testlib",
        description="A test library",
        git_url=GIT_URL,
        is_header_only=False,
        releases=[],
    )
    release = Release(
        version="1.0.0",
        platform="2.0",
        channel="fast",
        profile_builds=[],
    )
    release_dict = release.model_dump()
    release_dict["git_url"] = component.git_url
    release_dict["git_repo_base_url"] = component.git_url
    release_dict["git_branch_version"] = f"GBrelease_{release.version}"
    release_dict["is_header_only"] = component.is_header_only
    view_model: dict[str, Any] = {
        "target_platform": "2.0",
        "component": component.model_dump(),
        "releases": [release_dict],
        "profile_definitions": [],
        "legacy_contents": {},
    }
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
def test_release_doc_template_renders_full_release_converter_output_with_real_release(
    builder: DocumentBuilder, publisher_parsed_result: ParsedResult
) -> None:
    """release_doc.jinja2 рендерит реальный вывод FullReleaseConverter.convert() над непустым релизом с профилями и вариантами."""
    view_model: dict[str, Any] = FullReleaseConverter(include_passport_links=False).convert(
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
