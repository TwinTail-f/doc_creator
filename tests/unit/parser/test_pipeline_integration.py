"""Integration tests for the full autodoc parser pipeline.

Wires all real step instances (ManifestStep → OptionsResolveStep → ConanEnrichStep →
DockerResolveStep → ArtifactoryValidationStep → FinalizeStep) with stubbed external I/O.
A failure here indicates a context-key rename or step interface change
that was invisible to individual unit tests.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.parser import ComponentParser
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.manifest_step import ManifestStep
from autodoc.parser.steps.finalize_step import FinalizeStep

from autodoc.parser.conan.models.conan_enrichment_result import ConanEnrichmentResult
from autodoc.parser.fetchers.models.fetch_result import FetchResult

_MIN_COMPONENTS: int = 1
_HTTP_OK: int = 200

_EMPTY_CONAN_RESULT = FetchResult(value=ConanEnrichmentResult(), warnings=[])


@pytest.fixture()
def parser_config() -> ParserConfigSchema:
    """Minimal valid ParserConfigSchema for integration tests."""
    return ParserConfigSchema(
        platform_version="2.0",
        platform_branch_name="develop",
        platform_ref_type="branch",
        username="testuser",
        tfs_token="test-tfs-pat-token",
        artifactory_token="test-art-token",
        tfs_collection_url="https://tfs.example.com",
        manifests_remotes_path="/platform/manifests",
        conan_config_url="https://art.example.com/conan-config.zip",
    )


@pytest.fixture()
def resources_dir() -> Path:
    """Path to real .properties manifest fixtures shared by unit tests."""
    return Path(__file__).parent / "resources" / "manifests"


def _make_parser_with_real_steps(
    config: ParserConfigSchema,
    data_dir: Path,
    resources_dir: Path,
) -> ComponentParser:
    """Build a ComponentParser that uses real step instances with stubbed I/O.

    The TFS client copies real .properties files from resources_dir;
    Artifactory always returns HTTP 200; ConanFetcher is patched to return
    a no-op result so no subprocess is spawned.
    """
    from tests.unit.parser.conftest import CopyingAllFakeTFSClient
    from autodoc.parser.clients.artifactory_client_protocol import IArtifactoryClient
    import requests

    class _AlwaysOkArtifactoryClient:
        """Stub: every HEAD request returns HTTP 200 OK."""

        def head(self, url: str) -> requests.Response:
            """Return a 200 response without making a real network request."""
            resp = requests.Response()
            resp.status_code = _HTTP_OK
            return resp

    tfs_client = CopyingAllFakeTFSClient(resources_dir)
    artifactory_client = _AlwaysOkArtifactoryClient()

    return ComponentParser(
        config=config,
        data_dir=data_dir,
        tfs_client=tfs_client,
        artifactory_client=artifactory_client,
    )


def test_full_pipeline_runs_without_raising(
    parser_config: ParserConfigSchema,
    resources_dir: Path,
    tmp_path: Path,
) -> None:
    """The full pipeline completes without raising and produces a ParsedResult.

    Wires all real step instances with stubbed external I/O. A crash here
    indicates a regression in step wiring, context key usage, or step interface.
    """
    parser = _make_parser_with_real_steps(parser_config, tmp_path, resources_dir)

    with patch(
        "autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch",
        return_value=_EMPTY_CONAN_RESULT,
    ):
        result: ParsedResult = parser.parse()

    assert result is not None
    assert isinstance(result, ParsedResult)


def test_manifest_step_populates_ctx_components(
    parser_config: ParserConfigSchema,
    resources_dir: Path,
    tmp_path: Path,
) -> None:
    """ManifestStep populates ctx.components with a non-empty list.

    Guards against context-key renames that silently empty the component list
    before downstream steps can consume it.
    """
    from tests.unit.parser.conftest import CopyingAllFakeTFSClient

    tfs_client = CopyingAllFakeTFSClient(resources_dir)
    ctx = PipelineContext(
        config=parser_config,
        tmp_dir=tmp_path / "tmp",
        tfs_client=tfs_client,
        artifactory_client=MagicMock(),
    )
    ManifestStep().execute(ctx)
    assert len(ctx.components) >= _MIN_COMPONENTS, (
        f"ManifestStep must populate at least {_MIN_COMPONENTS} component(s); "
        f"got {len(ctx.components)}"
    )


def test_finalize_step_output_length_matches_input(
    parser_config: ParserConfigSchema,
    resources_dir: Path,
    tmp_path: Path,
) -> None:
    """ctx.result.components count does not exceed the number of input components.

    Feeds the full pipeline with N components. After the pipeline completes,
    components may be filtered by ValidationStep but never artificially increased.
    """
    parser = _make_parser_with_real_steps(parser_config, tmp_path, resources_dir)

    with patch(
        "autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch",
        return_value=_EMPTY_CONAN_RESULT,
    ):
        result: ParsedResult = parser.parse()

    assert result is not None
    # Count components seen before finalization via the manifest resources.
    n_manifest_files: int = len(list(resources_dir.glob("*.properties")))
    assert (
        len(result.components) <= n_manifest_files
    ), "FinalizeStep must not create more components than ManifestStep parsed"
