"""Юнит-тесты для autodoc.publisher.rendering.document_builder.DocumentBuilder."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest
from jinja2 import TemplateError, TemplateNotFound

from autodoc.publisher.rendering.document_builder import DocumentBuilder

SIMPLE_TEMPLATE_NAME: str = "simple.jinja2"
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
def test_init_succeeds_with_valid_dir(tmp_path: Path) -> None:
    """DocumentBuilder инициализируется без ошибок, если rendering_dir существует."""
    rendering_dir = make_rendering_dir(tmp_path, {})
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    assert builder is not None


@pytest.mark.infrastructure
def test_build_renders_template_with_data(tmp_path: Path) -> None:
    """build() подставляет поля view_model в шаблон корректно."""
    rendering_dir = make_rendering_dir(tmp_path, {TITLE_TEMPLATE_NAME: TITLE_TEMPLATE_CONTENT})
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    result = builder.build(TITLE_TEMPLATE_NAME, {"title": "Hello"})
    assert result == "Hello"


@pytest.mark.contract
def test_build_returns_string(tmp_path: Path) -> None:
    """build() всегда возвращает экземпляр str."""
    rendering_dir = make_rendering_dir(tmp_path, {STATIC_TEMPLATE_NAME: STATIC_TEMPLATE_CONTENT})
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    result = builder.build(STATIC_TEMPLATE_NAME, {})
    assert isinstance(result, str)


@pytest.mark.infrastructure
def test_build_raises_template_not_found(tmp_path: Path) -> None:
    """build() бросает TemplateNotFound, если запрошенный шаблон не существует."""
    rendering_dir = make_rendering_dir(tmp_path, {})
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    with pytest.raises(TemplateNotFound):
        builder.build(BAD_TEMPLATE_NAME, {})


@pytest.mark.infrastructure
def test_build_passes_view_model_as_data(tmp_path: Path) -> None:
    """Переменная шаблона 'data' содержит словарь view_model, переданный в build()."""
    rendering_dir = make_rendering_dir(tmp_path, {KEY_TEMPLATE_NAME: KEY_TEMPLATE_CONTENT})
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    result = builder.build(KEY_TEMPLATE_NAME, {"key": "expected_value"})
    assert result == "expected_value"


@pytest.mark.infrastructure
def test_build_with_empty_view_model(tmp_path: Path) -> None:
    """build() корректно рендерит статический шаблон, когда view_model пуст."""
    rendering_dir = make_rendering_dir(tmp_path, {STATIC_TEMPLATE_NAME: STATIC_TEMPLATE_CONTENT})
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    result = builder.build(STATIC_TEMPLATE_NAME, {})
    assert result == "static"


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
