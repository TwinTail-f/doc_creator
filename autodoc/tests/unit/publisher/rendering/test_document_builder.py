"""
Tests for:
- autodoc.publisher.rendering.document_builder.DocumentBuilder
- autodoc.publisher.view_models.passports.ConanVariantView
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest
from jinja2 import TemplateNotFound

from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.view_models.passports import ConanVariantView

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIMPLE_TEMPLATE_NAME: str = "simple.jinja2"
TITLE_TEMPLATE_NAME: str = "title.jinja2"
KEY_TEMPLATE_NAME: str = "key.jinja2"
STATIC_TEMPLATE_NAME: str = "static.jinja2"
BAD_TEMPLATE_NAME: str = "nonexistent.jinja2"

TITLE_TEMPLATE_CONTENT: str = "{{ data.title }}"
KEY_TEMPLATE_CONTENT: str = "{{ data.key }}"
STATIC_TEMPLATE_CONTENT: str = "static"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def make_rendering_dir(tmp_path: Path, templates: dict[str, str]) -> Path:
    """Creates the rendering_dir/templates/ structure with the given templates."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir(parents=True)
    for name, content in templates.items():
        (templates_dir / name).write_text(content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# DocumentBuilder — initialisation
# ---------------------------------------------------------------------------


def test_init_raises_if_dir_not_exists(tmp_path: Path) -> None:
    """DocumentBuilder raises FileNotFoundError when rendering_dir does not exist."""
    missing = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError):
        DocumentBuilder(rendering_dir=missing)


def test_init_succeeds_with_valid_dir(tmp_path: Path) -> None:
    """DocumentBuilder initialises without error when rendering_dir exists."""
    rendering_dir = make_rendering_dir(tmp_path, {})
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    assert builder is not None


# ---------------------------------------------------------------------------
# DocumentBuilder — build
# ---------------------------------------------------------------------------


def test_build_renders_template_with_data(tmp_path: Path) -> None:
    """build() substitutes view_model fields into the template correctly."""
    rendering_dir = make_rendering_dir(
        tmp_path, {TITLE_TEMPLATE_NAME: TITLE_TEMPLATE_CONTENT}
    )
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    result = builder.build(TITLE_TEMPLATE_NAME, {"title": "Hello"})
    assert result == "Hello"


def test_build_returns_string(tmp_path: Path) -> None:
    """build() always returns a str instance."""
    rendering_dir = make_rendering_dir(
        tmp_path, {STATIC_TEMPLATE_NAME: STATIC_TEMPLATE_CONTENT}
    )
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    result = builder.build(STATIC_TEMPLATE_NAME, {})
    assert isinstance(result, str)


def test_build_raises_template_not_found(tmp_path: Path) -> None:
    """build() raises TemplateNotFound when the requested template does not exist."""
    rendering_dir = make_rendering_dir(tmp_path, {})
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    with pytest.raises(TemplateNotFound):
        builder.build(BAD_TEMPLATE_NAME, {})


def test_build_passes_view_model_as_data(tmp_path: Path) -> None:
    """The template variable 'data' contains the view_model dict passed to build()."""
    rendering_dir = make_rendering_dir(
        tmp_path, {KEY_TEMPLATE_NAME: KEY_TEMPLATE_CONTENT}
    )
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    result = builder.build(KEY_TEMPLATE_NAME, {"key": "expected_value"})
    assert result == "expected_value"


def test_build_with_empty_view_model(tmp_path: Path) -> None:
    """build() renders a static template correctly when view_model is empty."""
    rendering_dir = make_rendering_dir(
        tmp_path, {STATIC_TEMPLATE_NAME: STATIC_TEMPLATE_CONTENT}
    )
    builder = DocumentBuilder(rendering_dir=rendering_dir)
    result = builder.build(STATIC_TEMPLATE_NAME, {})
    assert result == "static"


# ---------------------------------------------------------------------------
# ConanVariantView — dataclass contract
# ---------------------------------------------------------------------------


def test_conan_variant_view_is_dataclass() -> None:
    """ConanVariantView is a Python dataclass."""
    assert dataclasses.is_dataclass(ConanVariantView)


def test_conan_variant_view_required_fields() -> None:
    """ConanVariantView can be created with the three required positional fields."""
    view = ConanVariantView(
        package_id="pkg-abc",
        build_url="https://ci.example.com/build/1",
        build_date="2024-03-10",
    )
    assert view.package_id == "pkg-abc"


def test_conan_variant_view_defaults() -> None:
    """ConanVariantView optional fields default to empty string / empty dict."""
    view = ConanVariantView(
        package_id="pkg-abc",
        build_url="https://ci.example.com/build/1",
        build_date="2024-03-10",
    )
    assert view.option_ref == ""
    assert view.conan_options == {}
    assert view.install_options == ""


def test_conan_variant_view_custom_values() -> None:
    """ConanVariantView stores all custom field values correctly."""
    opts: dict[str, Any] = {"shared": "True", "fPIC": "False"}
    view = ConanVariantView(
        package_id="deadbeef",
        build_url="https://ci.example.com/build/99",
        build_date="2024-06-01",
        option_ref="opt-set-7",
        conan_options=opts,
        install_options="-o pkg/*:shared=True -o pkg/*:fPIC=False",
    )
    assert view.package_id == "deadbeef"
    assert view.build_url == "https://ci.example.com/build/99"
    assert view.build_date == "2024-06-01"
    assert view.option_ref == "opt-set-7"
    assert view.conan_options == opts
    assert view.install_options == "-o pkg/*:shared=True -o pkg/*:fPIC=False"
