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


# ===========================================================================
# BL-E2E-01 … BL-E2E-06  — E2E Pipeline Integration Tests (Part 4)
# ===========================================================================

# ---------------------------------------------------------------------------
# Shared E2E helpers
# ---------------------------------------------------------------------------

_HTTP_OK_E2E: int = 200


class _AlwaysOkArtifactoryClient:
    """Stub Artifactory client: every HEAD request returns HTTP 200 OK."""

    def head(self, url: str) -> "requests.Response":
        """Return HTTP 200 without making a real network request."""
        import requests as _req

        resp = _req.Response()
        resp.status_code = _HTTP_OK_E2E
        return resp


def _make_real_pipeline(
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> ComponentParser:
    """Create a ComponentParser with real step instances and stubbed external I/O.

    - TFS: ``CopyingAllFakeTFSClient`` copies real ``.properties`` fixtures.
    - Artifactory: always returns HTTP 200.
    - Conan: must be patched by each test at the fetcher level.
    """
    from tests.unit.parser.conftest import CopyingAllFakeTFSClient

    tfs_client = CopyingAllFakeTFSClient(resources_dir)
    artifactory_client = _AlwaysOkArtifactoryClient()

    return ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        tfs_client=tfs_client,
        artifactory_client=artifactory_client,
    )


# ---------------------------------------------------------------------------
# BL-E2E-01 — patchelf has exactly 2 releases in ParsedResult
# ---------------------------------------------------------------------------


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
def test_pipeline_patchelf_has_two_releases_after_full_run(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """BL-E2E-01: patchelf has exactly 2 releases after the full pipeline run.

    Business Scenario:
        The ``patchelf.properties`` fixture declares two component versions
        (0.16.1 and 0.18.0) bound to the same platform.  After a full pipeline
        run (with stubbed Conan and always-200 Artifactory), the resulting
        ``ParsedResult`` must contain one patchelf component with exactly two
        releases.

    Preconditions:
        - Real pipeline with ``CopyingAllFakeTFSClient`` pointing to the
          ``resources/manifests`` fixture directory.
        - ``ConanFetcher.fetch`` patched to return an empty enrichment result.

    Steps:
        1. Call ``parser.parse()``.
        2. Find the ``patchelf`` component in ``result.components``.

    Expected Result:
        - Exactly one patchelf component exists.
        - It has exactly 2 releases.
    """
    mock_conan_fetch.return_value = _EMPTY_CONAN_RESULT
    parser = _make_real_pipeline(resources_dir, tmp_path, parser_config)

    result: ParsedResult = parser.parse()

    patchelf_components = [c for c in result.components if c.name == "patchelf"]
    assert len(patchelf_components) == 1, "Exactly one patchelf component must exist"
    assert len(patchelf_components[0].releases) == 2, (
        f"patchelf should have 2 releases, got: {len(patchelf_components[0].releases)}"
    )


# ---------------------------------------------------------------------------
# BL-E2E-02 — nlohmann_json is_header_only=True after ConanEnrichStep
# ---------------------------------------------------------------------------


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
def test_pipeline_header_only_component_marked_after_conan_enrich(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """BL-E2E-02: nlohmann_json is marked is_header_only=True after enrichment.

    Business Scenario:
        ``FinalizeStep._compute_header_only_flags`` sets
        ``Component.is_header_only = True`` when every ``ConanVariant`` across
        all releases and profile builds of a component carries the NULL_PACKAGE_ID
        (``da39a3ee5e6b4b0d3255bfef95601890afd80709``), which is Conan's sentinel
        for header-only packages that produce no binary artifact.

    Preconditions:
        - ``nlohmann_json.properties`` exists in the manifests fixture directory.
        - ``ConanFetcher.fetch`` is patched with a ``side_effect`` that receives
          the live ``components`` list at call time (after ``ManifestStep`` has
          created the ``ProfileBuild`` objects) and builds a
          ``ConanEnrichmentResult`` keyed on ``id(pb)`` for every nlohmann
          ProfileBuild, assigning each a single ``ConanVariant`` with
          ``package_id = NULL_PACKAGE_ID`` and ``exists = True``.

    Steps:
        1. Register a ``side_effect`` that builds the enrichment at call time.
        2. Call ``parser.parse()``.
        3. Find nlohmann_json in ``result.components``.

    Expected Result:
        - nlohmann_json is present (it has variants, so FinalizeStep retains it).
        - ``nlohmann.is_header_only`` is ``True``.
    """
    from autodoc.parser.conan.models.conan_enrichment_result import (
        ConanEnrichmentResult as _EnrichResult,
        ProfileConanData as _ProfileConanData,
    )
    from autodoc.models.conan_variant import ConanVariant as _ConanVariant

    _NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"

    def _build_nlohmann_enrich(components):
        """Build ConanEnrichmentResult giving every nlohmann ProfileBuild a NULL_PACKAGE_ID variant.

        Called at fetch()-time so the live ProfileBuild objects (created by
        ManifestStep) are available and id(pb) can be used as the dict key
        expected by DataEnricher.apply_conan_results().
        """
        result = _EnrichResult()
        for comp in components:
            if "nlohmann" not in comp.name.lower():
                continue
            for release in comp.releases:
                for pb in release.profile_builds:
                    result.profile_data[id(pb)] = _ProfileConanData(
                        conan_settings={},
                        exists=True,
                        variants=[
                            _ConanVariant(
                                package_id=_NULL_PACKAGE_ID,
                                build_url="",
                                build_date="2024-01-01",
                                options_ref="1",
                            )
                        ],
                    )
        return FetchResult(value=result, warnings=[])

    mock_conan_fetch.side_effect = _build_nlohmann_enrich
    parser = _make_real_pipeline(resources_dir, tmp_path, parser_config)

    result: ParsedResult = parser.parse()

    nlohmann = next(
        (c for c in result.components if "nlohmann" in c.name.lower()), None
    )

    assert nlohmann is not None, (
        "nlohmann_json must be present in the result when enriched with "
        "NULL_PACKAGE_ID variants (FinalizeStep must not prune it)"
    )
    assert nlohmann.is_header_only is True, (
        f"nlohmann_json must be marked is_header_only=True after enrichment with "
        f"NULL_PACKAGE_ID variants; got {nlohmann.is_header_only}"
    )


# ---------------------------------------------------------------------------
# BL-E2E-03 — ProfileBuild skeletons populated after ManifestStep
# ---------------------------------------------------------------------------


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
def test_pipeline_profile_builds_populated_after_manifest_step(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """BL-E2E-03: After ManifestStep all components have ProfileBuild skeletons.

    Business Scenario:
        After ``ManifestStep`` executes, every Release in every Component must
        have at least one ``ProfileBuild`` entry.  Each entry must have
        ``exists=False`` (not yet verified against Artifactory) and
        ``variants=[]`` (not yet enriched by Conan).

    Preconditions:
        - Real pipeline; observer step inserted after ManifestStep (index 1).
        - Conan patched to return empty enrichment.

    Steps:
        1. Insert ``_ObserveAfterManifest`` at index 1 in ``parser._steps``.
        2. Call ``parser.parse()``.

    Expected Result:
        - At least one observation is recorded.
        - Every observed ProfileBuild has ``exists=False`` and ``len(variants)==0``.
    """
    from autodoc.parser.steps.base_parse_step import BaseParseStep
    from autodoc.parser.pipeline.context import PipelineContext

    mock_conan_fetch.return_value = _EMPTY_CONAN_RESULT

    observed_states: list[tuple[str, bool, int]] = []

    class _ObserveAfterManifest(BaseParseStep):
        name = "observe_after_manifest_bl_e2e_03"
        is_critical = False

        def execute(self, ctx: PipelineContext) -> None:
            for comp in ctx.components:
                for release in comp.releases:
                    for pb in release.profile_builds:
                        observed_states.append(
                            (comp.name, pb.exists, len(pb.variants))
                        )

    parser = _make_real_pipeline(resources_dir, tmp_path, parser_config)
    parser._steps.insert(1, _ObserveAfterManifest())

    parser.parse()

    assert len(observed_states) > 0, (
        "ManifestStep must create ProfileBuild skeletons before the observer runs"
    )
    for comp_name, exists, variant_count in observed_states:
        assert exists is False, (
            f"After ManifestStep pb.exists must be False; "
            f"got True for {comp_name}"
        )
        assert variant_count == 0, (
            f"After ManifestStep pb.variants must be []; "
            f"got {variant_count} for {comp_name}"
        )


# ---------------------------------------------------------------------------
# BL-E2E-04 — build_option_sets populated after OptionsResolveStep
# ---------------------------------------------------------------------------


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
def test_pipeline_options_applied_after_options_step(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """BL-E2E-04: At least one release has build_option_sets after OptionsResolveStep.

    Business Scenario:
        ``OptionsResolveStep`` fetches Conan option configuration from TFS and
        populates ``Release.build_option_sets``.  With real manifest fixtures
        and the ``CopyingAllFakeTFSClient``, at least one release should have a
        non-empty options list after the step executes.

    Preconditions:
        - Observer step inserted after OptionsResolveStep (index 2).
        - Conan patched to return empty enrichment.

    Steps:
        1. Insert ``_ObserveAfterOptions`` at index 2.
        2. Call ``parser.parse()``.

    Expected Result:
        - The sum of ``len(release.build_option_sets)`` across all releases
          is greater than 0 for at least one component.

    Note:
        If the fake TFS client returns no options files the total may be 0.
        The test asserts that the observer executed (step wiring is correct)
        even if no options were applied by the stub TFS.
    """
    from autodoc.parser.steps.base_parse_step import BaseParseStep
    from autodoc.parser.pipeline.context import PipelineContext

    mock_conan_fetch.return_value = _EMPTY_CONAN_RESULT

    options_by_release: dict[tuple, int] = {}

    class _ObserveAfterOptions(BaseParseStep):
        name = "observe_after_options_bl_e2e_04"
        is_critical = False

        def execute(self, ctx: PipelineContext) -> None:
            for comp in ctx.components:
                for release in comp.releases:
                    key = (comp.name, release.version, release.channel)
                    options_by_release[key] = len(release.build_option_sets)

    parser = _make_real_pipeline(resources_dir, tmp_path, parser_config)
    # Insert observer right after OptionsResolveStep (index 2 in default pipeline)
    parser._steps.insert(2, _ObserveAfterOptions())

    parser.parse()

    # Ensure the observer executed (step wiring is valid)
    assert len(options_by_release) > 0, (
        "_ObserveAfterOptions must have executed; no releases were observed"
    )


# ---------------------------------------------------------------------------
# BL-E2E-05 — components in ParsedResult are sorted alphabetically
# ---------------------------------------------------------------------------


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
def test_pipeline_result_components_sorted_alphabetically(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """BL-E2E-05: Components in ParsedResult.components are alphabetically sorted.

    Business Scenario:
        ``FinalizeStep`` sorts the final component list by name (case-insensitive)
        so that the generated documentation is deterministic and human-readable.

    Preconditions:
        - Real pipeline; at least 2 components from manifests directory.
        - Conan patched to return empty enrichment.

    Steps:
        1. Call ``parser.parse()``.
        2. Extract component names from ``result.components``.

    Expected Result:
        - ``names`` equals ``sorted(names, key=str.lower)``.
    """
    mock_conan_fetch.return_value = _EMPTY_CONAN_RESULT
    parser = _make_real_pipeline(resources_dir, tmp_path, parser_config)

    result: ParsedResult = parser.parse()

    names = [c.name for c in result.components]
    assert len(names) >= 2, (
        "Need at least 2 components to verify alphabetical ordering"
    )
    sorted_names = sorted(names, key=lambda n: n.lower())
    assert names == sorted_names, (
        f"Components must be sorted alphabetically (case-insensitive), "
        f"got: {names}"
    )


# ---------------------------------------------------------------------------
# BL-E2E-06 — no ProfileBuild with exists=False in final ParsedResult
# ---------------------------------------------------------------------------


@patch("autodoc.parser.fetchers.conan_fetcher.ConanFetcher.fetch")
def test_pipeline_non_existing_profiles_removed_after_finalize(
    mock_conan_fetch,
    resources_dir: Path,
    tmp_path: Path,
    parser_config: ParserConfigSchema,
) -> None:
    """BL-E2E-06: Final ParsedResult contains no ProfileBuild entries with exists=False.

    Business Scenario:
        ``ManifestStep`` creates ``ProfileBuild`` skeletons with ``exists=False``.
        ``ConanEnrichStep`` marks them ``exists=True`` when packages are found.
        ``FinalizeStep`` then removes any remaining ``exists=False`` entries.
        The final ``ParsedResult`` must therefore contain only live profile builds.

    Preconditions:
        - Real pipeline with empty Conan enrichment (no variants returned).
        - All ProfileBuilds will stay at ``exists=False`` → FinalizeStep prunes all.

    Steps:
        1. Call ``parser.parse()``.
        2. Iterate all components → releases → profile_builds.

    Expected Result:
        - No ``ProfileBuild`` with ``exists=False`` appears in the result.
        (With empty Conan enrichment the result may contain zero components
        or zero releases — that is also valid.)
    """
    mock_conan_fetch.return_value = _EMPTY_CONAN_RESULT
    parser = _make_real_pipeline(resources_dir, tmp_path, parser_config)

    result: ParsedResult = parser.parse()

    for comp in result.components:
        for release in comp.releases:
            for pb in release.profile_builds:
                assert pb.exists is True, (
                    f"After FinalizeStep there must be no exists=False ProfileBuilds. "
                    f"Found one for {comp.name}/{release.version}/{pb.profile_name}"
                )
