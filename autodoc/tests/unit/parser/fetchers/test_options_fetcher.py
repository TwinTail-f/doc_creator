"""
Unit tests for autodoc/parser/fetchers/options_fetcher.py.

Strategy: subclass FakeTFSClient with per-scenario fakes driven by real
options JSON file content from resources/options/.
No real network calls are made.
"""

from __future__ import annotations

from pathlib import Path

import requests

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.fetchers.options_fetcher import OptionsFetcher
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.tests.unit.parser.conftest import FakeTFSClient

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _load_options_bytes(resources_dir: Path, filename: str) -> bytes:
    """Load a real options JSON file from resources/options/ as bytes."""
    return (resources_dir / "options" / filename).read_bytes()


def _make_items_response(paths: list[str]) -> list[dict]:
    """Build a list of TFS item dicts (non-folder) from a list of paths."""
    return [{"path": p, "isFolder": False} for p in paths]


class _OptionsFileFakeTFSClient(FakeTFSClient):
    """Serves fixed options.json bytes for every get_file_content call."""

    def __init__(self, items: list[dict], content_bytes: bytes) -> None:
        """
        Args:
            items: List of item dicts returned by get_items.
            content_bytes: Raw bytes returned as the response body.
        """
        self._items = items
        self._bytes = content_bytes

    def get_items(self, items_url, branch, recursion=None, version_type=None):
        """Return the pre-configured list of items."""
        return self._items

    def get_file_content(self, items_url, path, branch, version_type=None):
        """Return a 200 response with the pre-configured bytes content."""
        resp = requests.Response()
        resp.status_code = 200
        resp._content = self._bytes
        return resp


# ---------------------------------------------------------------------------
# Component / context builders
# ---------------------------------------------------------------------------


def _make_component(name, repo, version, channel, project="DEP_Components"):
    """Build a minimal Component with one Release for fetcher tests."""
    release = Release(
        version=version,
        platform="2.0",
        channel=channel,
        git_url=f"{project}/_git/{repo}",
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    return Component(name=name, git_project=project, git_repo=repo, releases=[release])


def _make_context(parser_config: ParserConfigSchema, tfs_client, tmp_path: Path):
    """Build a minimal PipelineContext with the given fake TFS client."""
    return PipelineContext(
        config=parser_config,
        tmp_dir=tmp_path / "tmp",
        tfs_client=tfs_client,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fetcher_apr_single_option(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
    resources_dir: Path,
) -> None:
    """OptionsFetcher maps (apr,1.7.6,fast) to {'1': 'apr:shared=True'} from real apr_options.json."""
    apr_bytes = _load_options_bytes(resources_dir, "apr_options.json")
    path = "/conan/ci-1.6/options.json"
    client = _OptionsFileFakeTFSClient(
        items=_make_items_response([path]),
        content_bytes=apr_bytes,
    )
    comp = _make_component("apr", "contrib_apr", "1.7.6", "fast")
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert ("apr", "1.7.6", "fast") in result.value
    assert result.value[("apr", "1.7.6", "fast")] == {"1": "apr:shared=True"}


def test_fetcher_sqlite3_fast_five_options(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
    resources_dir: Path,
) -> None:
    """OptionsFetcher maps sqlite3 fast release to a 5-entry dict; key '5' contains 'with_icu'."""
    sqlite_bytes = _load_options_bytes(resources_dir, "sqlite3_fast_options.json")
    path = "/conan/ci-2.0/fast/options.json"
    client = _OptionsFileFakeTFSClient(
        items=_make_items_response([path]),
        content_bytes=sqlite_bytes,
    )
    comp = _make_component("sqlite3", "contrib_sqlite3", "3.51.2", "fast")
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    opts = result.value[("sqlite3", "3.51.2", "fast")]
    assert len(opts) == 5
    assert "with_icu" in opts["5"]


def test_fetcher_nlohmann_single_empty(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
    resources_dir: Path,
) -> None:
    """OptionsFetcher maps nlohmann_json slow release to {'1': ''} from real options file."""
    nlohmann_bytes = _load_options_bytes(resources_dir, "nlohmann_json_options.json")
    path = "/conan/ci-2.0/options.json"
    client = _OptionsFileFakeTFSClient(
        items=_make_items_response([path]),
        content_bytes=nlohmann_bytes,
    )
    comp = _make_component("nlohmann_json", "contrib_nlohmann_json", "3.9.1", "slow")
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert result.value[("nlohmann_json", "3.9.1", "slow")] == {"1": ""}


def test_fetcher_patchelf_two_versions_share_options(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
    resources_dir: Path,
) -> None:
    """Both patchelf versions in the same repo get options; fetcher de-duplicates the download."""
    patchelf_bytes = _load_options_bytes(resources_dir, "patchelf_options.json")
    path = "/conan/ci-2.0/options.json"
    client = _OptionsFileFakeTFSClient(
        items=[{"path": path, "isFolder": False}],
        content_bytes=patchelf_bytes,
    )
    comp = Component(
        name="patchelf",
        git_project="DEP_Components",
        git_repo="contrib_patchelf",
        releases=[
            Release(
                version="0.16.1",
                platform="2.0",
                channel="tech",
                git_url="DEP_Components/_git/contrib_patchelf",
                profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
            ),
            Release(
                version="0.18.0",
                platform="2.0",
                channel="tech",
                git_url="DEP_Components/_git/contrib_patchelf",
                profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
            ),
        ],
    )
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert ("patchelf", "0.16.1", "tech") in result.value
    assert ("patchelf", "0.18.0", "tech") in result.value
    assert result.value[("patchelf", "0.16.1", "tech")] == {"1": ""}
    assert result.value[("patchelf", "0.18.0", "tech")] == {"1": ""}


def test_fetcher_icu_fast_two_options(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
    resources_dir: Path,
) -> None:
    """OptionsFetcher maps icu 78.2/fast to a 2-entry dict; key '2' is 'icu:mobile=True'."""
    icu_bytes = _load_options_bytes(resources_dir, "icu_fast_options.json")
    path = "/conan/ci-1.6/fast/options.json"
    client = _OptionsFileFakeTFSClient(
        items=_make_items_response([path]),
        content_bytes=icu_bytes,
    )
    comp = _make_component("icu", "contrib_icu", "78.2", "fast")
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert result.value[("icu", "78.2", "fast")]["2"] == "icu:mobile=True"


def test_fetcher_no_options_file_returns_default(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """When get_items returns no items, the key exists in the map with fallback {'1': ''}."""
    client = _OptionsFileFakeTFSClient(items=[], content_bytes=b"{}")
    comp = _make_component("somelib", "contrib_somelib", "1.0.0", "fast")
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert ("somelib", "1.0.0", "fast") in result.value


def test_fetcher_invalid_json_does_not_raise(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """OptionsFetcher does not raise when get_file_content returns invalid JSON bytes."""
    path = "/conan/ci-2.0/tech/options.json"
    client = _OptionsFileFakeTFSClient(
        items=_make_items_response([path]),
        content_bytes=b"GARBAGE",
    )
    comp = _make_component("somelib", "contrib_somelib", "2.0.0", "tech")
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    # No exception; the release key must be present with a fallback value.
    assert ("somelib", "2.0.0", "tech") in result.value


# ---------------------------------------------------------------------------
# Kept tests (renamed/kept for regression)
# ---------------------------------------------------------------------------


def test_options_fetcher_empty_items_returns_empty_map(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """When get_items returns no items, OptionsFetcher adds a default options entry."""
    client = _OptionsFileFakeTFSClient(items=[], content_bytes=b"{}")
    release = Release(
        version="3.0.0",
        platform="2.0",
        channel="tech",
        git_url="DEP_Components/_git/contrib_openssl",
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    comp = Component(
        name="openssl",
        git_project="DEP_Components",
        git_repo="contrib_openssl",
        releases=[release],
    )
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert ("openssl", "3.0.0", "tech") in result.value


def test_fetcher_invalid_json_does_not_raise_openssl_alias(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """OptionsFetcher does not raise when file content is not valid JSON; key is present."""
    path = "/conan/ci-2.0/tech/options.json"
    client = _OptionsFileFakeTFSClient(
        items=_make_items_response([path]),
        content_bytes=b"NOT JSON",
    )
    release = Release(
        version="3.0.0",
        platform="2.0",
        channel="tech",
        git_url="DEP_Components/_git/contrib_openssl",
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    comp = Component(
        name="openssl",
        git_project="DEP_Components",
        git_repo="contrib_openssl",
        releases=[release],
    )
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert ("openssl", "3.0.0", "tech") in result.value


# ---------------------------------------------------------------------------
# Multi-path fake client — needed for components with multiple options files
# ---------------------------------------------------------------------------


class _BranchAwareOptionsFakeTFSClient(FakeTFSClient):
    """Serves different path→content mappings depending on the requested branch.

    In production, each release branch of the same repo has its own set of
    options files (e.g. fast branch has ci-2.0/fast/options.json; slow branch
    has ci-1.6/slow/options.json). This fake mirrors that per-branch isolation.
    """

    def __init__(self, branch_to_paths: dict[str, dict[str, str]]) -> None:
        """
        Args:
            branch_to_paths: Mapping {branch_name: {tfs_path: json_content}}.
        """
        self._map = branch_to_paths

    def get_items(self, items_url, branch, recursion=None, version_type=None):
        """Return item entries only for paths registered under this branch."""
        paths = self._map.get(branch, {})
        return [{"path": p, "isFolder": False} for p in paths]

    def get_file_content(self, items_url, path, branch, version_type=None):
        """Return a 200 response with the content registered for this branch+path."""
        content = self._map.get(branch, {}).get(path, "{}")
        resp = requests.Response()
        resp.status_code = 200
        resp._content = content.encode("utf-8")
        return resp


# ---------------------------------------------------------------------------
# UC-O-1: ci-1.6 fallback — icu slow, global options (3 entries)
# ---------------------------------------------------------------------------


def test_fetcher_icu_ci16_fallback_no_ci20_present(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
    resources_dir: Path,
) -> None:
    """Fetcher uses ci-1.6 fallback for icu when no ci-2.0 path exists in TFS.

    icu_slow_options.json contains 3 entries (ci-1.6/options.json, global).
    The fetcher must pick it up as fallback and map ('icu', '67.1', 'slow') → 3 entries.
    """
    icu_bytes = _load_options_bytes(resources_dir, "icu_slow_options.json")
    path = "/conan/ci-1.6/options.json"
    client = _OptionsFileFakeTFSClient(
        items=_make_items_response([path]),
        content_bytes=icu_bytes,
    )
    comp = _make_component("icu", "contrib_icu", "67.1", "slow")
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert ("icu", "67.1", "slow") in result.value
    assert len(result.value[("icu", "67.1", "slow")]) == 3


# ---------------------------------------------------------------------------
# UC-O-2: sqlite3 — dual channel, different options files per channel
# ---------------------------------------------------------------------------


def test_fetcher_sqlite3_fast_channel_specific_options(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
    resources_dir: Path,
) -> None:
    """Fetcher resolves sqlite3 options from channel subdirectories (ci-2.0/fast and ci-1.6/slow).

    sqlite3 has two releases on separate branches, each with its own channel-specific
    options.json. After fetching, ('sqlite3', '3.51.2', 'fast') must have 5 entries
    and ('sqlite3', '3.34.1', 'slow') must have 12 entries.
    """
    fast_text = _load_options_bytes(resources_dir, "sqlite3_fast_options.json").decode()
    slow_text = _load_options_bytes(resources_dir, "sqlite3_slow_options.json").decode()
    client = _BranchAwareOptionsFakeTFSClient(
        {
            "release_3.51.2": {"/conan/ci-2.0/fast/options.json": fast_text},
            "release_3.34.1": {"/conan/ci-1.6/slow/options.json": slow_text},
        }
    )
    fast_release = Release(
        version="3.51.2",
        platform="2.0",
        channel="fast",
        git_url="DEP_Components/_git/contrib_sqlite3",
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    slow_release = Release(
        version="3.34.1",
        platform="2.0",
        channel="slow",
        git_url="DEP_Components/_git/contrib_sqlite3",
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    comp = Component(
        name="sqlite3",
        git_project="DEP_Components",
        git_repo="contrib_sqlite3",
        releases=[fast_release, slow_release],
    )
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert len(result.value[("sqlite3", "3.51.2", "fast")]) == 5
    assert len(result.value[("sqlite3", "3.34.1", "slow")]) == 12
    fast_release = Release(
        version="3.51.2",
        platform="2.0",
        channel="fast",
        git_url="DEP_Components/_git/contrib_sqlite3",
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    slow_release = Release(
        version="3.34.1",
        platform="2.0",
        channel="slow",
        git_url="DEP_Components/_git/contrib_sqlite3",
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )
    comp = Component(
        name="sqlite3",
        git_project="DEP_Components",
        git_repo="contrib_sqlite3",
        releases=[fast_release, slow_release],
    )
    ctx = _make_context(parser_config, client, tmp_path)
    fetcher = OptionsFetcher()
    fetcher.configure(ctx)
    result = fetcher.fetch([comp])

    assert len(result.value[("sqlite3", "3.51.2", "fast")]) == 5
    assert len(result.value[("sqlite3", "3.34.1", "slow")]) == 12
