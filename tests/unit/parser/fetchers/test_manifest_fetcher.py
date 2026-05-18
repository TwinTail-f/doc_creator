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
from tests.unit.parser.conftest import CopyingAllFakeTFSClient, FakeTFSClient

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


@pytest.mark.integration
def test_manifest_fetcher_returns_patchelf_with_two_releases(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """Real patchelf.properties via CopyingFakeTFSClient yields exactly 1 component with 2 releases."""
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(real_manifests_dir / "patchelf.properties"),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(
        tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude"
    )

    # Only assert flow-through: correct top-level count, correct release count, no exception.
    assert len(result.value) == 1
    assert len(result.value[0].releases) == 2
    assert result.warnings == []


@pytest.mark.integration
def test_manifest_fetcher_returns_nlohmann_json(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """Real nlohmann_json.properties via CopyingFakeTFSClient yields exactly 1 component."""
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(real_manifests_dir / "nlohmann_json.properties"),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(
        tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude"
    )

    # Only assert flow-through: correct top-level count, no exception.
    assert len(result.value) == 1
    assert result.warnings == []


@pytest.mark.integration
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

    result = fetcher.fetch(
        tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude"
    )

    assert len(result.value) >= 5


@pytest.mark.integration
def test_manifest_fetcher_libnetfilter_queue_prg_quant(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """libnetfilter_queue.properties yields exactly 1 component without error."""
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(real_manifests_dir / "libnetfilter_queue.properties"),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(
        tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude"
    )

    # Only assert flow-through: correct top-level count, no exception.
    assert len(result.value) == 1
    assert result.warnings == []


@pytest.mark.integration
def test_manifest_fetcher_include_filter(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """component_names=['apr'], filter_mode='include' with all files returns exactly 1 component."""
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

    # Only assert flow-through: correct top-level count, no exception.
    assert len(result.value) == 1
    assert result.warnings == []


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.contract
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


# ---------------------------------------------------------------------------
# UC-M-1: [Section B] Single version, single fast channel
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_manifest_fetcher_single_version_single_channel_fast(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """Fetcher returns 1 component / 1 release for nlohmann_json_fast_only fixture.

    Uses the synthetic nlohmann_json_fast_only.properties written in Step 0.
    Confirms the fetcher-parser integration handles the simplest header-only manifest structure.
    Specific field values (channel, version) are covered by test_manifest_parser.py.
    """
    fixture = real_manifests_dir / "nlohmann_json_fast_only.properties"
    ctx = _make_context(
        parser_config,
        WritingFakeTFSClient(
            content=fixture.read_text(), filename="nlohmann_json_fast_only.properties"
        ),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(
        tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude"
    )
    components = result.value

    # Only assert flow-through: correct top-level count, correct release count, no exception.
    assert len(components) == 1
    assert len(components[0].releases) == 1
    assert result.warnings == []


# ---------------------------------------------------------------------------
# UC-M-3: [Section B] Multiple versions, single tech channel
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_manifest_fetcher_patchelf_two_versions_one_channel(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """Fetcher returns 1 component / 2 releases for patchelf.

    Covers UC-M-3: multiple versions in a single non-fast/slow channel.
    Specific channel values are covered by test_manifest_parser.py.
    """
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(real_manifests_dir / "patchelf.properties"),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(
        tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude"
    )
    components = result.value

    # Only assert flow-through: correct top-level count, correct release count, no exception.
    assert len(components) == 1
    assert len(components[0].releases) == 2
    assert result.warnings == []


# ---------------------------------------------------------------------------
# UC-M-5: [Section B] Component from external TFS project (PRG_Quant)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_manifest_fetcher_external_project_no_error(
    parser_config: ParserConfigSchema,
    real_manifests_dir: Path,
    tmp_path: Path,
) -> None:
    """Fetcher handles libnetfilter_queue (external TFS project) without errors or warnings.

    Covers UC-M-5: manifest from an external TFS project; the fetcher must not raise
    or produce unexpected warnings just because the git project is not DEP_Components.
    Specific field values (git_project) are covered by test_manifest_parser.py.
    """
    ctx = _make_context(
        parser_config,
        CopyingFakeTFSClient(real_manifests_dir / "libnetfilter_queue.properties"),
        tmp_path,
    )
    fetcher = ManifestFetcher()
    fetcher.configure(ctx)

    result = fetcher.fetch(
        tmp_dir=ctx.tmp_dir, component_names=[], filter_mode="exclude"
    )
    components = result.value

    # Only assert flow-through: correct top-level count, no exception, no unexpected warnings.
    assert len(components) == 1
    assert result.warnings == []
