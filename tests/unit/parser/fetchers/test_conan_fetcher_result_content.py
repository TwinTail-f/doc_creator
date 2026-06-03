"""GAP 1 — ConanFetcher: real ConanEnrichmentResult content tests (1.1–1.4).

These tests verify that release_data, profile_data, errors, and task counters
survive intact through ConanFetcher.fetch() — scenarios invisible to the
orchestration-only tests in test_conan_fetcher.py which mock the whole result.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from autodoc.parser.conan.models.conan_enrichment_result import (
    ConanEnrichmentResult,
    ReleaseConanData,
    ProfileConanData,
)
from autodoc.models.conan_variant import ProfileBuild, ConanVariant
from autodoc.models.options import TotalOptionsSet, DefaultOptionsSet
from autodoc.parser.fetchers.conan_fetcher import ConanFetcher
from autodoc.parser.fetchers.models.fetch_result import FetchResult

_MODULE = "autodoc.parser.fetchers.conan_fetcher"
_CONAN_CONFIG_URL = "https://art.example.com/conan-config.zip"
_ARTIFACTORY_URL = "https://art.example.com/artifactory/conan2"

_TIMEOUT_SEC: int = 60
_PLATFORM_VERSION: str = "2.0"
_CONAN_HOME_TEMPLATE: Path = Path("/tmp/conan_home_template")


# ---------------------------------------------------------------------------
# Helpers — copied verbatim from test_conan_fetcher.py (not importable)
# ---------------------------------------------------------------------------


def _make_mock_ctx(
    mocker: MockerFixture,
    conan_config_url: str = _CONAN_CONFIG_URL,
    overrides_file: str | None = None,
) -> MagicMock:
    """Построить минимальный PipelineContext mock with the given conan_config_url."""
    ctx: MagicMock = mocker.MagicMock()
    ctx.config.conan_command_timeout = _TIMEOUT_SEC
    ctx.config.platform_base_version = _PLATFORM_VERSION
    ctx.config.artifactory_components_conan2_url = _ARTIFACTORY_URL
    ctx.config.conan_config_url = conan_config_url
    ctx.config.username = "testuser"
    ctx.config.artifactory_token = "test-art-token"
    ctx.config.profile_settings_overrides_file = overrides_file
    return ctx


def _patch_full_fetch_pipeline(
    mocker: MockerFixture,
    tasks: list | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Patch all external collaborators used inside ConanFetcher.fetch().

    Returns (mock_builder_cls, mock_env_cls, mock_runner_cls, mock_executor_cls, mock_agg_cls).
    """
    if tasks is None:
        tasks = [mocker.MagicMock(name="task_0")]

    mock_builder_cls: MagicMock = mocker.patch(f"{_MODULE}.ConanTaskBuilder")
    mock_builder_cls.return_value.build.return_value = tasks

    mock_env_cls: MagicMock = mocker.patch(f"{_MODULE}.ConanEnvironmentManager")
    mock_env_cls.return_value.setup.return_value = _CONAN_HOME_TEMPLATE

    mock_runner_cls: MagicMock = mocker.patch(f"{_MODULE}.Conan2Runner")

    mock_executor_cls: MagicMock = mocker.patch(f"{_MODULE}.ParallelExecutor")
    mock_executor_cls.return_value.execute.return_value = [
        mocker.MagicMock() for _ in tasks
    ]

    mocker.patch(f"{_MODULE}.ConanResultParser")
    mock_agg_cls: MagicMock = mocker.patch(f"{_MODULE}.ConanResultAggregator")
    mock_agg_cls.return_value.aggregate.return_value = ConanEnrichmentResult()
    mock_agg_cls.return_value.build_execution_report.return_value = []

    return (
        mock_builder_cls,
        mock_env_cls,
        mock_runner_cls,
        mock_executor_cls,
        mock_agg_cls,
    )


# ---------------------------------------------------------------------------
# Test 1.1 — release_data key and base_ref preserved
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.integration
def test_fetch_result_release_data_has_correct_key_and_base_ref(
    mocker: MockerFixture,
) -> None:
    """FetchResult.value.release_data key=(name,version,channel) and base_ref are preserved."""
    expected_key = ("patchelf", "0.18.0", "tech")
    release_entry = ReleaseConanData(
        base_ref="patchelf/0.18.0@platform-2.0/tech",
        rrev="deadbeef",
        full_version="0.18.0",
        default_options=[],
        total_options=[],
        patches=[],
        dependencies=[],
        artifactory_url="https://art.example.com/patchelf",
    )
    fake_result = ConanEnrichmentResult(
        release_data={expected_key: release_entry},
        profile_data={},
        errors={},
    )

    _, _, _, _, mock_agg_cls = _patch_full_fetch_pipeline(mocker)
    mock_agg_cls.return_value.aggregate.return_value = fake_result

    ctx = _make_mock_ctx(mocker)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)
    result: FetchResult[ConanEnrichmentResult] = fetcher.fetch([mocker.MagicMock()])

    assert isinstance(result.value, ConanEnrichmentResult)
    assert expected_key in result.value.release_data
    assert (
        result.value.release_data[expected_key].base_ref
        == "patchelf/0.18.0@platform-2.0/tech"
    )


# ---------------------------------------------------------------------------
# Test 1.2 — profile_data keyed by object identity
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.integration
def test_fetch_result_profile_data_keyed_by_object_identity(
    mocker: MockerFixture,
) -> None:
    """profile_data dict key is id(pb); the ProfileConanData entry is preserved."""
    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    profile_entry = ProfileConanData(
        conan_settings={"os": "Linux", "arch": "x86_64", "compiler": "gcc"},
        exists=True,
        variants=[],
    )
    fake_result = ConanEnrichmentResult(
        release_data={},
        profile_data={id(pb): profile_entry},
        errors={},
    )

    _, _, _, _, mock_agg_cls = _patch_full_fetch_pipeline(mocker)
    mock_agg_cls.return_value.aggregate.return_value = fake_result

    ctx = _make_mock_ctx(mocker)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)
    result: FetchResult[ConanEnrichmentResult] = fetcher.fetch([mocker.MagicMock()])

    assert id(pb) in result.value.profile_data
    assert result.value.profile_data[id(pb)].conan_settings["os"] == "Linux"
    assert result.value.profile_data[id(pb)].exists is True


# ---------------------------------------------------------------------------
# Test 1.3 — nested errors structure preserved
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_fetch_result_nested_errors_structure_preserved(
    mocker: MockerFixture,
) -> None:
    """Nested {comp: {ver: {ch: {profile: [msgs]}}}} errors dict is not flattened or lost."""
    expected_errors = {
        "stunnel": {
            "5.71": {
                "tech": {
                    "hw-linux-x86_64-gcc10_2": [
                        "version range error: openssl/[>=1.0.0]"
                    ]
                }
            }
        }
    }
    fake_result = ConanEnrichmentResult(errors=expected_errors)

    _, _, _, _, mock_agg_cls = _patch_full_fetch_pipeline(mocker)
    mock_agg_cls.return_value.aggregate.return_value = fake_result

    ctx = _make_mock_ctx(mocker)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)
    result: FetchResult[ConanEnrichmentResult] = fetcher.fetch([mocker.MagicMock()])

    assert result.value.errors == expected_errors
    error_msg = result.value.errors["stunnel"]["5.71"]["tech"][
        "hw-linux-x86_64-gcc10_2"
    ][0]
    assert "version range" in error_msg


# ---------------------------------------------------------------------------
# Test 1.4 — task counters reflected in result
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_fetch_task_counters_reflected_in_result(
    mocker: MockerFixture,
) -> None:
    """Aggregator task counters (total/succeeded/failed) are present in FetchResult.value."""
    fake_result = ConanEnrichmentResult(
        total_tasks=3,
        succeeded=2,
        failed=1,
    )

    _, _, _, _, mock_agg_cls = _patch_full_fetch_pipeline(mocker)
    mock_agg_cls.return_value.aggregate.return_value = fake_result

    ctx = _make_mock_ctx(mocker)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)
    result: FetchResult[ConanEnrichmentResult] = fetcher.fetch([mocker.MagicMock()])

    assert result.value.total_tasks == 3
    assert result.value.succeeded == 2
    assert result.value.failed == 1
