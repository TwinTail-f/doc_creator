"""Unit tests for autodoc/parser/fetchers/manifest_fetcher.py.

Strategy: fake TFS clients copy real .properties files into tmp_dir without
any network I/O. ManifestParser is NOT mocked — the full
ManifestFetcher → ManifestParser chain is exercised.
"""

import shutil
from pathlib import Path

import pytest

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import ParsingError
from autodoc.parser.fetchers.manifest_fetcher import ManifestFetcher
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.tests.unit.parser.conftest import CopyingAllFakeTFSClient, FakeTFSClient

# ---------------------------------------------------------------------------
# Local fake clients — defined here per local-ownership convention
# ---------------------------------------------------------------------------


class WritingFakeTFSClient(FakeTFSClient):
    """FakeTFSClient that writes a single .properties file into output_dir."""

    def __init__(self, content: str, filename: str = "test.properties") -> None:
        """
        Args:
            content: Text to write into the .properties file.
            filename: Filename to create inside output_dir.
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
        """Writes configured content into output_dir as a .properties file."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / self._filename).write_text(self._content, encoding="utf-8")


class CopyingFakeTFSClient(FakeTFSClient):
    """FakeTFSClient that copies a single real .properties file into output_dir."""

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
        """Copies the source file into output_dir preserving its filename."""
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
# Tests using real .properties files
# ---------------------------------------------------------------------------


def test_manifest_fetcher_returns_patchelf_with_two_releases(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """Real patchelf.properties via CopyingFakeTFSClient yields a component with 2 releases."""
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(real_manifests_dir / "patchelf.properties"),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")

    assert len(result.value) == 1
    comp = result.value[0]
    assert comp.name == "patchelf"
    assert len(comp.releases) == 2


def test_manifest_fetcher_returns_nlohmann_json(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """Real nlohmann_json.properties via CopyingFakeTFSClient yields a component named 'nlohmann_json'."""
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(real_manifests_dir / "nlohmann_json.properties"),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")

    names = [c.name for c in result.value]
    assert "nlohmann_json" in names


def test_manifest_fetcher_all_five_components(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """All real .properties files via CopyingAllFakeTFSClient yield at least 5 components."""
    ctx = _make_context(
        parser_config,
        CopyingAllFakeTFSClient(real_manifests_dir),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")

    assert len(result.value) >= 5


def test_manifest_fetcher_libnetfilter_queue_prg_quant(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """libnetfilter_queue.properties yields a component with git_project=='PRG_Quant'."""
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(real_manifests_dir / "libnetfilter_queue.properties"),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")

    assert len(result.value) == 1
    assert result.value[0].git_project == "PRG_Quant"


def test_manifest_fetcher_include_filter(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """component_names=['apr'], filter_mode='include' with all files returns only apr."""
    ctx = _make_context(
        parser_config,
        CopyingAllFakeTFSClient(real_manifests_dir),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(
        tmp_dir=ctx.tmp_dir, component_names=["apr"], filter_mode="include"
    )

    assert len(result.value) == 1
    assert result.value[0].name == "apr"


def test_manifest_fetcher_exclude_filter(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """component_names=['apr'], filter_mode='exclude' with all files omits apr from results."""
    ctx = _make_context(
        parser_config,
        CopyingAllFakeTFSClient(real_manifests_dir),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(
        tmp_dir=ctx.tmp_dir, component_names=["apr"], filter_mode="exclude"
    )

    names = [c.name for c in result.value]
    assert "apr" not in names


# ---------------------------------------------------------------------------
# Tests to KEEP (unchanged)
# ---------------------------------------------------------------------------


def test_manifest_fetcher_no_files_returns_empty(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """ManifestFetcher raises ParsingError when download_properties writes no files."""
    ctx = _make_context(
        parser_config,
        FakeTFSClient(),  # stub: writes nothing
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    with pytest.raises(ParsingError):
        fetcher.fetch(tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude")


def test_manifest_fetcher_configure_sets_tfs_client(
    parser_config: ParserConfigSchema,
    tmp_path: Path,
) -> None:
    """After configure(), the fetcher's internal _tfs reference is not None."""
    fake_client = WritingFakeTFSClient(
        content=(
            "name= openssl\n"
            "versions.component= 1.0.0\n"
            "versions.platform= 2.0-tech\n"
            "profiles-1.0.0-2.0-tech= hw-linux-x86_64-gcc10_2\n"
        )
    )
    ctx = _make_context(parser_config, fake_client, tmp_path)
    fetcher = ManifestFetcher()

    fetcher.configure(ctx)

    assert fetcher._tfs is not None
