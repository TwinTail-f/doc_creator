"""
Фикстуры для autodoc/tests/unit/parser/enrichment/.

manifest_component и manifest_release наследуются из родительского
tests/unit/parser/conftest.py и доступны здесь автоматически.
"""

import pytest

from autodoc.models.component import ConanVariant


@pytest.fixture
def conan_variant() -> ConanVariant:
    """Минимальный ConanVariant для использования в тестах apply_conan_results."""
    return ConanVariant(
        package_id="575ea8086554107ae2c0fdbb4909d62390c52b77",
        build_url="https://art.example.com/package/575ea808",
        build_date="2024-01-15T10:00:00+00:00",
        options_ref="1",
    )
