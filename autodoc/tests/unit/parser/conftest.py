"""
Shared test fixtures and fakes for autodoc/tests/unit/parser/.

FakeTFSClient is a no-op stand-in for the real TFSClient.  Individual test
modules subclass it and override only the methods they need, keeping the
test surface minimal and explicit.
"""

import unittest.mock as mock
from pathlib import Path

import pytest
import requests

from autodoc.config.schemas import ParserConfigSchema
from autodoc.models.component import (
    ConanVariant,
    Component,
    ProfileBuild,
    Release,
)
from autodoc.parser.pipeline.context import PipelineContext

# ---------------------------------------------------------------------------
# Config / path fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def parser_config() -> ParserConfigSchema:
    """Minimal valid ParserConfigSchema for unit tests (no real network calls)."""
    return ParserConfigSchema(
        platform_version="2.0",
        platform_branch_name="develop",
        platform_ref_type="branch",
        username="testuser",
        tfs_token="test-tfs-pat-token",
        artifactory_token="test-art-token",
        tfs_dep_components_url="https://tfs.example.com/DEP_Components",
        manifests_remotes_path="/platform/manifests",
        conan_config_url="https://art.example.com/conan-config.zip",
    )


@pytest.fixture
def resources_dir() -> Path:
    """Path to the shared test-resource files under tests/unit/parser/resources/."""
    return Path(__file__).parent / "resources"


# ---------------------------------------------------------------------------
# Pipeline context fixture (used by steps/ and test_pipeline.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def parser_pipeline_context(
    parser_config: ParserConfigSchema, tmp_path: Path
) -> PipelineContext:
    """A fully-initialised PipelineContext backed by parser_config and a tmp_path."""
    return PipelineContext(config=parser_config, tmp_dir=tmp_path)


# ---------------------------------------------------------------------------
# Component / Release fixtures (shared across steps/, enrichment/, test_pipeline.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def manifest_release() -> Release:
    """A Release for openssl 1.0.0 on platform 2.0 / channel 'tech'."""
    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    return Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        git_url="DEP_Components/_git/contrib_openssl",
        profile_builds=[pb],
    )


@pytest.fixture
def manifest_component(manifest_release: Release) -> Component:
    """A Component named 'openssl' that wraps manifest_release."""
    return Component(name="openssl", releases=[manifest_release])


# ---------------------------------------------------------------------------
# Fake Artifactory client (used by validation_step tests)
# ---------------------------------------------------------------------------


class _FakeArtifactoryClient:
    """Minimal Artifactory client stub that records head() calls."""

    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.called_urls: list[str] = []

    def head(self, url: str) -> requests.Response:
        self.called_urls.append(url)
        resp = requests.Response()
        resp.status_code = self.status_code
        return resp


@pytest.fixture
def artifactory_client() -> _FakeArtifactoryClient:
    """Default 200-OK fake Artifactory client; tests use .__class__(status_code=N) for variants."""
    return _FakeArtifactoryClient(status_code=200)


class FakeTFSClient:
    """
    No-op fake for TFSClient.

    Every method returns a safe, empty default so that subclasses only need
    to override the one or two methods relevant to the test being written.

    Method signatures mirror the real TFSClient so that type-checked code
    can use FakeTFSClient as a drop-in replacement in tests.
    """

    def get_file_content(
        self,
        items_url: str,
        path: str,
        branch: str,
        version_type=None,
    ) -> requests.Response:
        """Return an empty 200 response by default."""
        resp = mock.MagicMock(spec=requests.Response)
        resp.status_code = 200
        resp.content = b""
        resp.text = ""
        resp.raise_for_status.return_value = None
        return resp

    def get_items(
        self,
        items_url: str,
        branch: str,
        recursion=None,
        version_type=None,
    ) -> list:
        """Return an empty item list by default."""
        return []

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
        version_type=None,
    ) -> None:
        """Do nothing by default (no files written)."""
