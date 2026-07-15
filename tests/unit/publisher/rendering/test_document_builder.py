"""Юнит-тесты для autodoc.publisher.rendering.document_builder.DocumentBuilder."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from jinja2 import TemplateError, TemplateNotFound

from autodoc.publisher.rendering.document_builder import DocumentBuilder

TITLE_TEMPLATE_NAME: str = "title.jinja2"
KEY_TEMPLATE_NAME: str = "key.jinja2"
STATIC_TEMPLATE_NAME: str = "static.jinja2"
BAD_TEMPLATE_NAME: str = "nonexistent.jinja2"
XMLATTR_TEMPLATE_NAME: str = "xmlattr.jinja2"
SYNTAX_ERROR_TEMPLATE_NAME: str = "syntax_error.jinja2"

TITLE_TEMPLATE_CONTENT: str = "{{ data.title }}"
KEY_TEMPLATE_CONTENT: str = "{{ data.key }}"
STATIC_TEMPLATE_CONTENT: str = "static"
XMLATTR_TEMPLATE_CONTENT: str = '<a title="{{ data.value | xmlattr }}"></a>'
SYNTAX_ERROR_TEMPLATE_CONTENT: str = "{% if data.flag %}unclosed"


def make_rendering_dir(tmp_path: Path, templates: dict[str, str]) -> Path:
    """Создаёт структуру rendering_dir/templates/ с заданными шаблонами.

    Args:
        tmp_path: Временная директория, используемая как rendering_dir.
        templates: Отображение {имя_файла: содержимое} создаваемых шаблонов.

    Returns:
        Путь к rendering_dir (совпадает с tmp_path).
    """
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir(parents=True)
    for name, content in templates.items():
        (templates_dir / name).write_text(content, encoding="utf-8")
    return tmp_path


@pytest.mark.infrastructure
def test_init_raises_if_dir_not_exists(tmp_path: Path) -> None:
    """DocumentBuilder бросает FileNotFoundError, если rendering_dir не существует."""
    missing = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError):
        DocumentBuilder(rendering_dir=missing)


@pytest.mark.infrastructure
@pytest.mark.parametrize(
    "template_name, template_content, view_model, expected",
    [
        # build() подставляет поле view_model в шаблон через 'data.<поле>'
        pytest.param(
            TITLE_TEMPLATE_NAME, TITLE_TEMPLATE_CONTENT, {"title": "Hello"}, "Hello",
            id="substitutes-field-from-view-model",
        ),
        # переменная шаблона 'data' — это именно тот словарь, что передан в build()
        pytest.param(
            KEY_TEMPLATE_NAME, KEY_TEMPLATE_CONTENT, {"key": "expected_value"}, "expected_value",
            id="data-variable-is-passed-view-model",
        ),
        # пустой view_model не ломает рендеринг шаблона, не обращающегося к data
        pytest.param(
            STATIC_TEMPLATE_NAME, STATIC_TEMPLATE_CONTENT, {}, "static",
            id="empty-view-model",
        ),
    ],
)
def test_build_renders_template_with_view_model(
    tmp_path: Path,
    template_name: str,
    template_content: str,
    view_model: dict[str, Any],
    expected: str,
) -> None:
    """build() рендерит шаблон, подставляя переданный view_model в переменную 'data'."""
    rendering_dir = make_rendering_dir(tmp_path, {template_name: template_content})
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    result = builder.build(template_name, view_model)
    assert result == expected


@pytest.mark.infrastructure
def test_build_raises_template_not_found(tmp_path: Path) -> None:
    """build() бросает TemplateNotFound, если запрошенный шаблон не существует."""
    rendering_dir = make_rendering_dir(tmp_path, {})
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    with pytest.raises(TemplateNotFound):
        builder.build(BAD_TEMPLATE_NAME, {})


@pytest.mark.infrastructure
def test_build_xmlattr_filter_escapes_special_chars(tmp_path: Path) -> None:
    """Фильтр xmlattr экранирует '&' и '"', не удваивая экранирование."""
    rendering_dir = make_rendering_dir(tmp_path, {XMLATTR_TEMPLATE_NAME: XMLATTR_TEMPLATE_CONTENT})
    builder = DocumentBuilder(rendering_dir=rendering_dir)

    result = builder.build(XMLATTR_TEMPLATE_NAME, {"value": 'Tom & Jerry "Show"'})

    assert result == '<a title="Tom &amp; Jerry &quot;Show&quot;"></a>'
    assert "&amp;amp;" not in result
    assert "&quot;quot;" not in result


@pytest.mark.infrastructure
def test_build_raises_template_error_on_syntax_error(tmp_path: Path) -> None:
    """build() бросает TemplateError при синтаксической ошибке Jinja2 в шаблоне."""
    rendering_dir = make_rendering_dir(
        tmp_path, {SYNTAX_ERROR_TEMPLATE_NAME: SYNTAX_ERROR_TEMPLATE_CONTENT}
    )
    builder = DocumentBuilder(rendering_dir=rendering_dir)

    with pytest.raises(TemplateError):
        builder.build(SYNTAX_ERROR_TEMPLATE_NAME, {"flag": True})
