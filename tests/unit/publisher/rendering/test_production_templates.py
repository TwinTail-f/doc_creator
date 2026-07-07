"""Smoke tests for production Jinja2 templates in autodoc/publisher/rendering/.

Each test renders one template with a minimal valid context and asserts
the output is non-empty and raises no exception.
No live Confluence connection is made.
"""

from pathlib import Path
from typing import Any

import pytest

from autodoc.models.component import Component
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.rendering.document_builder import DocumentBuilder

# Root of the rendering directory (templates/, styles/, macros/).
_RENDERING_DIR: Path = Path(__file__).parents[4] / "autodoc" / "publisher" / "rendering"

# Stable string markers to assert inside rendered outputs.
_STYLES_BASE_MARKER: str = "autodoc-badge"  # present in _styles_base.jinja2
_STYLES_PP_MARKER: str = "autodoc-page-header"  # present in _styles_passport.jinja2


def _make_parsed_result(component_name: str = "testlib") -> ParsedResult:
    """Build a minimal ParsedResult with one named component for template rendering."""
    component = Component(name=component_name, releases=[])
    return ParsedResult(
        generated_at="2024-01-15T12:00:00",
        platform_version="2.0",
        profile_definitions=[],
        components=[component],
    )


@pytest.fixture()
def builder() -> DocumentBuilder:
    """A DocumentBuilder pointed at the real rendering directory."""
    return DocumentBuilder(_RENDERING_DIR)


@pytest.fixture()
def minimal_view_model() -> dict[str, Any]:
    """Minimal view model accepted by all main templates."""
    parsed = _make_parsed_result()
    return parsed.model_dump()


@pytest.mark.infrastructure
def test_macros_template_renders_without_error(builder: DocumentBuilder) -> None:
    """Rendering _macros.jinja2 via the main release template produces non-empty output.

    Macros are included by every main template; any syntax error in the macros file
    would surface here before deployment to a live Confluence instance.
    """
    view_model: dict[str, Any] = _make_parsed_result().model_dump()
    output: str = builder.build("release_doc.jinja2", view_model)
    assert output.strip(), "Rendered output from release_doc.jinja2 is empty"


@pytest.mark.infrastructure
def test_styles_base_template_renders_without_error(
    builder: DocumentBuilder,
) -> None:
    """_styles_base.jinja2 is included by release_doc.jinja2 and must render cleanly.

    The rendered output must contain the stable CSS class marker 'autodoc-badge',
    confirming that the stylesheet was actually included and not silently skipped.
    """
    view_model: dict[str, Any] = _make_parsed_result().model_dump()
    output: str = builder.build("release_doc.jinja2", view_model)
    assert output.strip(), "Rendered output is empty"
    assert (
        _STYLES_BASE_MARKER in output
    ), f"Expected '{_STYLES_BASE_MARKER}' in rendered output (from _styles_base.jinja2)"


@pytest.mark.infrastructure
def test_styles_passport_template_renders_without_error(
    builder: DocumentBuilder,
) -> None:
    """_styles_passport.jinja2 is included by component_passport.jinja2; must render.

    Verifies that the passport stylesheet is syntactically valid and that the
    'autodoc-page-header' marker from _styles_passport.jinja2 appears in the output.
    """
    from autodoc.models.release import Release

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
    assert output.strip(), "Rendered output from component_passport.jinja2 is empty"
    assert (
        _STYLES_PP_MARKER in output
    ), f"Expected '{_STYLES_PP_MARKER}' in rendered output (from _styles_passport.jinja2)"


@pytest.mark.business_logic
def test_main_component_template_contains_component_name(
    builder: DocumentBuilder,
) -> None:
    """The release_doc template must include the component name in its rendered output.

    Ensures that data flows from the view model into the template correctly:
    a component name present in the model must appear in the HTML output.
    """
    _COMPONENT_NAME: str = "my_sentinel_component"
    view_model: dict[str, Any] = _make_parsed_result(_COMPONENT_NAME).model_dump()
    output: str = builder.build("release_doc.jinja2", view_model)
    assert (
        _COMPONENT_NAME in output
    ), f"Component name '{_COMPONENT_NAME}' not found in rendered release_doc output"
