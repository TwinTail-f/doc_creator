"""
Unit tests for autodoc/parser/fetchers/options_fetcher.py.

Strategy: subclass FakeTFSClient to control what get_items and
get_file_content return, then verify the OptionsMap built by the fetcher.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import requests

from autodoc.config.schemas import ParserConfigSchema
from autodoc.models.component import Component, ProfileBuild, Release
from autodoc.parser.fetchers.options_fetcher import OptionsFetcher
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.tests.unit.parser.conftest import FakeTFSClient

# ---------------------------------------------------------------------------
# Path constants that satisfy OptionsParser's path filters:
#   - must end with "options.json"
#   - must contain "/conan/"
#   - must contain "/ci-2.0/" for the CI-prefix selection
# ---------------------------------------------------------------------------

_OPTIONS_PATH: str = "/conan/ci-2.0/tech/options.json"


# ---------------------------------------------------------------------------
# Local fake TFS clients
# ---------------------------------------------------------------------------


class _ItemsAndContentFakeTFSClient(FakeTFSClient):
    """
    FakeTFSClient whose get_items and get_file_content return configurable data.

    Useful for testing the full OptionsFetcher pipeline.
    """

    def __init__(self, items: list, content: bytes) -> None:
        """
        Args:
            items: List of item dicts returned by get_items.
            content: Raw bytes returned as response body by get_file_content.
        """
        self._items = items
        self._content = content

    def get_items(
        self, items_url: str, branch: str, recursion=None, version_type=None
    ) -> list:
        """Return the pre-configured item list."""
        return self._items

    def get_file_content(
        self, items_url: str, path: str, branch: str, version_type=None
    ):
        """Return a 200 response with the pre-configured content."""
        resp = requests.Response()
        resp.status_code = 200
        resp._content = self._content
        return resp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_component(
    name: str = "openssl",
    git_repo: str = "contrib_openssl",
    version: str = "3.0.0",
    channel: str = "tech",
) -> Component:
    """Build a minimal Component with one Release."""
    release = Release(
        version=version,
        platform="2.0",
        channel=channel,
        git_url="DEP_Components/_git/contrib_openssl",
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    return Component(
        name=name,
        description="Test component",
        git_project="DEP_Components",
        git_repo=git_repo,
        releases=[release],
    )


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
# 5.1 — Happy path: options extracted for a component release
# ---------------------------------------------------------------------------


def test_options_fetcher_extracts_options_for_release(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """OptionsFetcher maps (name, version, channel) → parsed options on success."""
    component = _make_component()
    tfs_client = _ItemsAndContentFakeTFSClient(
        items=[{"path": _OPTIONS_PATH, "isFolder": False}],
        content=json.dumps({"1": "shared=True"}).encode(),
    )
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch([component])

    key = ("openssl", "3.0.0", "tech")
    assert key in result.value
    assert result.value[key] == {"1": "shared=True"}


# ---------------------------------------------------------------------------
# 5.2 — get_items returns empty list → default options in map
# ---------------------------------------------------------------------------


def test_options_fetcher_empty_items_returns_empty_map(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """
    When get_items returns no items, OptionsFetcher inserts a default options entry.

    The OptionsParser.pick_options fallback returns {"1": ""} when no channel-
    specific or global options are available.
    """
    component = _make_component()
    tfs_client = _ItemsAndContentFakeTFSClient(items=[], content=b"{}")
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch([component])

    # No crash; the key exists with the default fallback value.
    assert ("openssl", "3.0.0", "tech") in result.value


# ---------------------------------------------------------------------------
# 5.3 — Unparseable JSON content is silently skipped
# ---------------------------------------------------------------------------


def test_options_fetcher_skips_on_invalid_json(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """
    OptionsFetcher does not raise when get_file_content returns invalid JSON.

    The OptionsParser logs a warning internally and returns an empty options dict.
    The fetcher continues and returns the default fallback for that release.
    """
    component = _make_component()
    tfs_client = _ItemsAndContentFakeTFSClient(
        items=[{"path": _OPTIONS_PATH, "isFolder": False}],
        content=b"NOT JSON",
    )
    ctx = _make_context(parser_config, tfs_client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch([component])

    # Fetcher must not raise; the release key must still be present.
    assert ("openssl", "3.0.0", "tech") in result.value
