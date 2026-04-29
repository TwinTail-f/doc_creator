"""
Unit tests for autodoc/parser/fetchers/manifest_fetcher.py.

Strategy: provide fake TFS clients that write real-looking .properties content
into tmp_dir without network I/O. ManifestParser is NOT mocked — the full
ManifestFetcher → ManifestParser chain is exercised.
"""

import shutil
from pathlib import Path

import pytest

from autodoc.config.schemas import ParserConfigSchema
from autodoc.exceptions import ParsingError
from autodoc.parser.fetchers.manifest_fetcher import ManifestFetcher
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.tests.unit.parser.conftest import FakeTFSClient

# ---------------------------------------------------------------------------
# Shared properties content (platform 2.0-tech, component "openssl")
# ---------------------------------------------------------------------------

_VALID_PROPERTIES: str = """\
name= openssl
description= Test OpenSSL component
versions.component= 1.0.0
versions.platform= 2.0-tech
profiles-1.0.0-2.0-tech= hw-linux-x86_64-gcc10_2
tfs_git_project= DEP_Components
git_repo_name= contrib_openssl
"""


# ---------------------------------------------------------------------------
# Local fake clients — defined here, NOT in conftest (per ownership rules)
# ---------------------------------------------------------------------------


class WritingFakeTFSClient(FakeTFSClient):
    """FakeTFSClient that writes a .properties file into output_dir on download_properties."""

    def __init__(self, content: str, filename: str = "test.properties") -> None:
        """
        Args:
            content: Text to write into the .properties file.
            filename: Name of the file created inside output_dir.
        """
        self._content = content
        self._filename = filename

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
        version_type=None,
    ) -> None:
        """Write the configured content into output_dir as a .properties file."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / self._filename).write_text(self._content, encoding="utf-8")


class CopyingFakeTFSClient(FakeTFSClient):
    """FakeTFSClient that copies a real .properties file into output_dir."""

    def __init__(self, source_file: Path) -> None:
        """
        Args:
            source_file: Path to the real .properties file to copy.
        """
        self._source = source_file

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
        version_type=None,
    ) -> None:
        """Copy the source file into output_dir, preserving its filename."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy(self._source, out / self._source.name)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_context(
    parser_config: ParserConfigSchema,
    tfs_client: FakeTFSClient,
    tmp_path: Path,
) -> PipelineContext:
    """Build a PipelineContext with the given fake TFS client."""
    return PipelineContext(
        config=parser_config,
        tmp_dir=tmp_path / "tmp",
        tfs_client=tfs_client,
    )


# ---------------------------------------------------------------------------
# 4.1 — Happy path: fetcher returns component from valid .properties content
# ---------------------------------------------------------------------------


def test_manifest_fetcher_returns_component_on_valid_properties(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """ManifestFetcher returns exactly one component when given valid .properties content."""
    ctx = _make_context(
        parser_config,
        WritingFakeTFSClient(content=_VALID_PROPERTIES),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, excluded=[])

    assert len(result.value) == 1
    assert result.value[0].name == "openssl"


# ---------------------------------------------------------------------------
# 4.2 — Excluded component is not returned
# ---------------------------------------------------------------------------


def test_manifest_fetcher_excludes_named_component(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """ManifestFetcher returns no components when the component name is excluded."""
    ctx = _make_context(
        parser_config,
        WritingFakeTFSClient(content=_VALID_PROPERTIES),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, excluded=["openssl"])

    assert result.value == []


# ---------------------------------------------------------------------------
# 4.3 — configure stores tfs_client in the fetcher
# ---------------------------------------------------------------------------


def test_manifest_fetcher_configure_sets_tfs_client(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """After configure(), the fetcher's internal _tfs reference is not None."""
    fake_client = WritingFakeTFSClient(content=_VALID_PROPERTIES)
    ctx = _make_context(parser_config, fake_client, tmp_path)
    fetcher = ManifestFetcher()

    fetcher.configure(ctx)

    assert fetcher._tfs is not None


# ---------------------------------------------------------------------------
# 4.4 — No .properties files in tmp_dir raises ParsingError
# ---------------------------------------------------------------------------


def test_manifest_fetcher_no_files_returns_empty(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """
    ManifestFetcher raises ParsingError when download_properties writes no files.

    The underlying FakeTFSClient (no-op) produces an empty directory, which the
    fetcher treats as a fatal configuration or network problem.
    """
    ctx = _make_context(
        parser_config,
        FakeTFSClient(),  # no-op: writes nothing
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    with pytest.raises(ParsingError):
        fetcher.fetch(tmp_dir=ctx.tmp_dir, excluded=[])


# ---------------------------------------------------------------------------
# 4.5 — Real patchelf.properties file (uses resources_dir fixture)
# ---------------------------------------------------------------------------


def test_manifest_fetcher_with_real_properties_file(
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """ManifestFetcher returns components when given a real .properties file."""
    source = resources_dir / "manifests" / "patchelf.properties"
    ctx = PipelineContext(
        config=parser_config,
        tmp_dir=tmp_path / "tmp",
        tfs_client=CopyingFakeTFSClient(source_file=source),
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, excluded=[])

    names = [c.name for c in result.value]
    assert "patchelf" in names
