"""
Unit tests for autodoc/parser/fetchers/docker_fetcher.py.

Strategy: provide a fake TFS client whose get_file_content returns controlled
YAML content. DockerParser is NOT mocked — the full DockerFetcher → DockerParser
chain is exercised.
"""

from pathlib import Path
from unittest.mock import MagicMock

import requests
import yaml

from autodoc.config.schemas import ParserConfigSchema
from autodoc.parser.fetchers.docker_fetcher import DockerFetcher
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.tests.unit.parser.conftest import FakeTFSClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# A well-formed TFS URL that contains /_git/ so DockerFetcher does not skip it.
# query parameters: path (YAML file path) and version (branch prefixed with GB).
_PROFILE_URL: str = (
    "https://tfs.example.com/DEP_Components/_git/platform-profiles"
    "?path=/profiles.yaml&version=GBdevelop"
)

YAML_CONTENT: str = """
archs:
  linux-x86_64-gcc10_2:
    revision: 1
    profile_host: linux-x86_64-gcc10_2
    profile_build: linux-x86_64-gcc10_2
    docker: harbor.example.com/debian11:components
"""


# ---------------------------------------------------------------------------
# Local fake TFS client
# ---------------------------------------------------------------------------


class _ContentFakeTFSClient(FakeTFSClient):
    """FakeTFSClient that returns a configurable response from get_file_content."""

    def __init__(self, content: bytes, status_code: int = 200) -> None:
        """
        Args:
            content: Bytes returned as the response body.
            status_code: HTTP status code of the response.
        """
        self._content = content
        self._status_code = status_code

    def get_file_content(
        self, items_url: str, path: str, branch: str, version_type=None
    ) -> requests.Response:
        """Return a response with the configured status code and content."""
        resp = requests.Response()
        resp.status_code = self._status_code
        resp._content = self._content
        return resp


class _RaisingFakeTFSClient(FakeTFSClient):
    """FakeTFSClient whose get_file_content raises requests.ConnectionError."""

    def get_file_content(
        self, items_url: str, path: str, branch: str, version_type=None
    ) -> requests.Response:
        """Simulate a network-level failure (caught by DockerFetcher)."""
        raise requests.ConnectionError("simulated connection error")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_context(
    parser_config: ParserConfigSchema,
    tfs_client: FakeTFSClient,
    tmp_path: Path,
) -> PipelineContext:
    """Build a minimal PipelineContext with the given fake TFS client."""
    return PipelineContext(
        config=parser_config,
        tmp_dir=tmp_path / "tmp",
        tfs_client=tfs_client,
    )


# ---------------------------------------------------------------------------
# 6.1 — Happy path: Docker links extracted from YAML
# ---------------------------------------------------------------------------


def test_docker_fetcher_extracts_links_from_yaml(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """DockerFetcher returns a docker link for each profile found in the YAML."""
    tfs_client = _ContentFakeTFSClient(content=YAML_CONTENT.encode())
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[_PROFILE_URL], target_platform="2.0")

    assert (
        result.value["linux-x86_64-gcc10_2"] == "harbor.example.com/debian11:components"
    )


# ---------------------------------------------------------------------------
# 6.2 — Empty URLs list returns empty links
# ---------------------------------------------------------------------------


def test_docker_fetcher_empty_urls_returns_empty_links(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """DockerFetcher.fetch with an empty URL list returns an empty links map."""
    tfs_client = FakeTFSClient()
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[], target_platform="2.0")

    assert result.value == {}


# ---------------------------------------------------------------------------
# 6.3 — Failed fetch (RequestException) produces empty result
# ---------------------------------------------------------------------------


def test_docker_fetcher_failed_url_produces_warning(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """
    DockerFetcher skips a URL when get_file_content raises a RequestException.

    The exception is caught internally; the result is an empty links map and
    the fetcher does not propagate the error.
    """
    ctx = _make_context(parser_config, _RaisingFakeTFSClient(), tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[_PROFILE_URL], target_platform="2.0")

    assert result.value == {}


# ---------------------------------------------------------------------------
# 6.4 — Invalid YAML content produces empty result
# ---------------------------------------------------------------------------


def test_docker_fetcher_invalid_yaml_produces_warning(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """
    DockerFetcher skips a URL when the response body is not valid YAML.

    The YAMLError is caught internally; the result is an empty links map and
    the fetcher does not propagate the error.
    """
    invalid_yaml: bytes = b"[unclosed: mapping: {"
    tfs_client = _ContentFakeTFSClient(content=invalid_yaml)
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = DockerFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(urls=[_PROFILE_URL], target_platform="2.0")

    assert result.value == {}
