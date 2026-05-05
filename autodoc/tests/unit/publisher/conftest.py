"""
Publisher-specific fixtures and stubs.
Do not touch for the Parser agent. Do not duplicate minimal_confluence_config from tests/conftest.py.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from autodoc.publisher.clients.protocols import IConfluenceClient, IDocumentBuilder


# ---------------------------------------------------------------------------
# Fake classes (implement Protocol interfaces without inheritance)
# ---------------------------------------------------------------------------


class FakeConfluenceClient:
    """
    Test stub for IConfluenceClient with predictable behavior.

    All write methods record calls in self.calls for later verification.
    Return values of publish_page are configurable via self.publish_responses.
    By default returns page_id='page-001', version=1, status='updated'.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.publish_responses: list[dict[str, Any]] = []
        self._page_bodies: dict[str, str] = {}
        self._pages: dict[str, dict[str, Any]] = {}

    def _default_publish_response(self, title: str) -> dict[str, Any]:
        return {"id": "page-001", "version": 1, "status": "updated", "title": title}

    def publish_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> dict[str, Any]:
        """Records the call; returns the next response from publish_responses or the default."""
        self.calls.append(
            {
                "method": "publish_page",
                "space": space,
                "parent_id": parent_id,
                "title": title,
                "body_html": body_html,
            }
        )
        if self.publish_responses:
            return self.publish_responses.pop(0)
        return self._default_publish_response(title)

    def get_or_create_page(
        self,
        space: str,
        title: str,
        parent_id: str | None = None,
        body: str = "",
    ) -> str:
        """Returns 'page-001' or the value from _pages[title]['id']."""
        self.calls.append(
            {"method": "get_or_create_page", "space": space, "title": title}
        )
        return self._pages.get(title, {}).get("id", "page-001")

    def find_page(
        self,
        title: str,
        space: str | None = None,
        expand: str = "",
    ) -> dict[str, Any] | None:
        """Returns page from _pages or None."""
        return self._pages.get(title)

    def get_page(self, page_id: str, expand: str = "") -> dict[str, Any]:
        """Returns a stub page by ID."""
        return {"id": page_id, "version": {"number": 1}, "title": "stub"}

    def get_page_body(self, space: str, title: str) -> str:
        """Returns page body from _page_bodies or empty string."""
        self.calls.append({"method": "get_page_body", "space": space, "title": title})
        return self._page_bodies.get(title, "")


class FakeDocumentBuilder:
    """
    Test stub for IDocumentBuilder.

    By default returns the string '<html>{template_name}</html>'.
    The last build() call is stored in self.last_call for argument verification.
    """

    def __init__(self) -> None:
        self.last_call: dict[str, Any] | None = None
        self.build_responses: list[str] = []

    def build(self, template_name: str, view_model: dict[str, Any]) -> str:
        """Returns the next build_responses entry or the default HTML."""
        self.last_call = {"template_name": template_name, "view_model": view_model}
        if self.build_responses:
            return self.build_responses.pop(0)
        return f"<html>{template_name}</html>"


# ---------------------------------------------------------------------------
# Import domain models
# ---------------------------------------------------------------------------

from autodoc.models.component import (
    ConanVariant,
    ConanInputOptions,
    Component,
    DefaultOptionsSet,
    ProfileBuild,
    Release,
    TotalOptionsSet,
)
from autodoc.models.parsed_result import ParsedResult, ProfileDefinition


PUBLISHER_RESOURCES_DIR: Path = (
    Path(__file__).parent.parent.parent / "resources" / "parsed_data"
)


# ---------------------------------------------------------------------------
# Infrastructure fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def publisher_resources_dir() -> Path:
    """Path to publisher resources (parsed_data/)."""
    return PUBLISHER_RESOURCES_DIR


@pytest.fixture
def publisher_confluence_client() -> FakeConfluenceClient:
    """Fresh FakeConfluenceClient for each test."""
    return FakeConfluenceClient()


@pytest.fixture
def publisher_document_builder() -> FakeDocumentBuilder:
    """Fresh FakeDocumentBuilder for each test."""
    return FakeDocumentBuilder()


# ---------------------------------------------------------------------------
# Domain model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def publisher_conan_variant() -> ConanVariant:
    """A single ConanVariant with populated fields."""
    return ConanVariant(
        package_id="abc123",
        build_url="https://ci.example.com/build/42",
        build_date="2024-01-15",
        options_ref="opt-set-1",
    )


@pytest.fixture
def publisher_profile_build(publisher_conan_variant: ConanVariant) -> ProfileBuild:
    """ProfileBuild for profile 'hw-linux-x86_64-gcc10' with one variant."""
    return ProfileBuild(
        profile_name="hw-linux-x86_64-gcc10",
        exists=True,
        variants=[publisher_conan_variant],
    )


@pytest.fixture
def publisher_release(publisher_profile_build: ProfileBuild) -> Release:
    """Release '1.0.0' for platform 2.0 with one ProfileBuild."""
    total_opts = TotalOptionsSet(
        id="opt-set-1", options={"shared": "True", "fPIC": "True"}
    )
    build_opts = ConanInputOptions(
        id="opt-set-1",
        options="openssl/*:shared=True, openssl/*:fPIC=True",
    )
    return Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        git_url="https://tfs.example.com/DEP_Components/_git/contrib_openssl",
        conan_reference="openssl/1.0.0@platform/2.0-tech",
        artifactory_url="https://art.example.com/conan/openssl/1.0.0",
        is_header_only=False,
        profile_builds=[publisher_profile_build],
        total_option_sets=[total_opts],
        build_option_sets=[build_opts],
    )


@pytest.fixture
def publisher_component(publisher_release: Release) -> Component:
    """Component 'openssl' with one Release."""
    return Component(
        name="openssl",
        description="OpenSSL TLS/SSL library",
        git_project="DEP_Components",
        git_repo="contrib_openssl",
        releases=[publisher_release],
    )


@pytest.fixture
def publisher_profile_definition() -> ProfileDefinition:
    """ProfileDefinition for profile 'hw-linux-x86_64-gcc10'."""
    return ProfileDefinition(
        profile_name="hw-linux-x86_64-gcc10",
        conan_settings={
            "os": "Linux",
            "arch": "x86_64",
            "compiler": "gcc",
            "compiler.version": "10",
        },
        docker_image="registry.example.com/build/linux-gcc10:latest",
    )


@pytest.fixture
def publisher_parsed_result(
    publisher_component: Component,
    publisher_profile_definition: ProfileDefinition,
) -> ParsedResult:
    """Minimal ParsedResult with one component and one profile."""
    return ParsedResult(
        generated_at="2024-01-15T12:00:00",
        platform_version="2.0",
        profile_definitions=[publisher_profile_definition],
        components=[publisher_component],
    )


@pytest.fixture
def publisher_multi_component_result(
    publisher_profile_definition: ProfileDefinition,
) -> ParsedResult:
    """ParsedResult with two components and multiple releases — for strategies."""
    total_opts = TotalOptionsSet(id="opt-1", options={"shared": "True"})
    rel1 = Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        git_url="https://tfs.example.com/repo1",
        conan_reference="openssl/1.0.0@platform/2.0-tech",
        artifactory_url="https://art.example.com/openssl",
        is_header_only=False,
        profile_builds=[
            ProfileBuild(
                profile_name="hw-linux-x86_64-gcc10",
                exists=True,
                variants=[
                    ConanVariant(
                        package_id="p1",
                        build_url="https://ci/1",
                        build_date="2024-01-01",
                        options_ref="opt-1",
                    )
                ],
            )
        ],
        total_option_sets=[total_opts],
    )
    rel2 = Release(
        version="2.0.0",
        platform="2.0",
        channel="stable",
        git_url="https://tfs.example.com/repo1",
        conan_reference="openssl/2.0.0@platform/2.0-stable",
        artifactory_url="https://art.example.com/openssl2",
        is_header_only=True,
        profile_builds=[],
        total_option_sets=[],
    )
    comp1 = Component(
        name="openssl",
        description="TLS library",
        git_project="DEP",
        git_repo="contrib_openssl",
        releases=[rel1, rel2],
    )
    comp2 = Component(
        name="zlib",
        description="Compression library",
        git_project="DEP",
        git_repo="contrib_zlib",
        releases=[
            Release(
                version="1.2.11",
                platform="2.0",
                channel="tech",
                git_url="https://tfs.example.com/repo2",
                conan_reference="zlib/1.2.11@platform/2.0-tech",
                artifactory_url="https://art.example.com/zlib",
                is_header_only=False,
                profile_builds=[
                    ProfileBuild(
                        profile_name="hw-linux-x86_64-gcc10",
                        exists=True,
                        variants=[],
                    )
                ],
                total_option_sets=[],
            )
        ],
    )
    return ParsedResult(
        generated_at="2024-01-15T12:00:00",
        platform_version="2.0",
        profile_definitions=[publisher_profile_definition],
        components=[comp1, comp2],
    )
