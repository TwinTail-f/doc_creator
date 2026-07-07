"""Юнит-тесты для autodoc/parser/fetchers/conan_fetcher.py.

ConanFetcher orchestrates полный Conan enrichment pipeline:
environment setup → task building → parallel execution → result aggregation.
All external dependencies are mocked; no subprocess or network calls are made.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from autodoc.parser.conan.models.conan_enrichment_result import ConanEnrichmentResult
from autodoc.parser.fetchers.conan_fetcher import ConanFetcher
from autodoc.parser.fetchers.models.fetch_result import FetchResult

_CONAN_CONFIG_URL: str = "https://art.example.com/conan-config.zip"
_ARTIFACTORY_URL: str = "https://art.example.com/artifactory/conan2"
_PLATFORM_VERSION: str = "2.0"
_TIMEOUT_SEC: int = 60
_OVERRIDES_FILE_PATH: str = "/etc/autodoc/profile_overrides.json"
_CONAN_HOME_TEMPLATE: Path = Path("/tmp/conan_home_template")

_MODULE: str = "autodoc.parser.fetchers.conan_fetcher"


def _make_mock_ctx(
    mocker: MockerFixture,
    conan_config_url: str = _CONAN_CONFIG_URL,
    overrides_file: str | None = None,
) -> MagicMock:
    """Построить минимальный PipelineContext mock with the given conan_config_url.

    Provides sensible defaults for all attributes read by ConanFetcher.configure().
    """
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
    tasks: list[Any] | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Patch all external collaborators used inside ConanFetcher.fetch().

    Returns (mock_builder_cls, mock_env_cls, mock_runner_cls, mock_executor_cls, mock_agg_cls).
    Each class mock's return_value is pre-configured with sensible defaults so
    tests only need to override the attribute they care about.
    """
    if tasks is None:
        tasks = [mocker.MagicMock(name="task_0")]

    mock_builder_cls: MagicMock = mocker.patch(f"{_MODULE}.ConanTaskBuilder")
    mock_builder_cls.return_value.build.return_value = tasks

    mock_env_cls: MagicMock = mocker.patch(f"{_MODULE}.ConanEnvironmentManager")
    mock_env_cls.return_value.setup.return_value = _CONAN_HOME_TEMPLATE

    mock_runner_cls: MagicMock = mocker.patch(f"{_MODULE}.Conan2Runner")

    mock_executor_cls: MagicMock = mocker.patch(f"{_MODULE}.ParallelExecutor")
    mock_executor_cls.return_value.execute.return_value = [mocker.MagicMock() for _ in tasks]

    mocker.patch(f"{_MODULE}.Conan2ResultParser")
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
# T4A.1.1 — raises when conan_config_url is empty
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_conan_fetcher_raises_if_conan_config_url_not_set(
    mocker: MockerFixture,
) -> None:
    """configure() + fetch() raises RuntimeError when conan_config_url is empty.

    Without a config URL ConanFetcher cannot set up the Conan environment,
    so it must fail loudly rather than silently returning empty results.
    """
    ctx = _make_mock_ctx(mocker, conan_config_url="")

    fetcher = ConanFetcher()
    fetcher.configure(ctx)

    with pytest.raises(RuntimeError, match="conan_config_url"):
        fetcher.fetch([])


# ---------------------------------------------------------------------------
# T4A.1.2 — short-circuit on empty component list
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_conan_fetcher_returns_empty_on_empty_component_list(
    mocker: MockerFixture,
) -> None:
    """fetch() with zero components returns an empty result without calling the runner.

    Short-circuit path: no tasks → no subprocess calls → FetchResult with empty value.
    """
    mock_builder_cls: MagicMock = mocker.patch(f"{_MODULE}.ConanTaskBuilder")
    mock_builder_cls.return_value.build.return_value = []

    mock_executor_cls: MagicMock = mocker.patch(f"{_MODULE}.ParallelExecutor")

    ctx = _make_mock_ctx(mocker)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)

    result: FetchResult[ConanEnrichmentResult] = fetcher.fetch([])

    assert isinstance(result, FetchResult)
    assert isinstance(result.value, ConanEnrichmentResult)
    assert result.warnings == []
    mock_executor_cls.return_value.execute.assert_not_called()


# ---------------------------------------------------------------------------
# T4A.1.3 — cleanup always called, even when setup raises
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_conan_fetcher_cleanup_called_on_setup_failure(
    mocker: MockerFixture,
) -> None:
    """env_manager.cleanup() is called in the finally block even when setup() raises.

    Resource safety: the temp Conan environment directory must be cleaned up
    regardless of whether setup succeeds or fails.
    """
    non_empty_task: MagicMock = mocker.MagicMock(name="task_0")
    mock_builder_cls: MagicMock = mocker.patch(f"{_MODULE}.ConanTaskBuilder")
    mock_builder_cls.return_value.build.return_value = [non_empty_task]

    mock_manager: MagicMock = mocker.MagicMock()
    mock_manager.setup.side_effect = RuntimeError("setup failed")
    mocker.patch(f"{_MODULE}.ConanEnvironmentManager", return_value=mock_manager)

    ctx = _make_mock_ctx(mocker)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)

    with pytest.raises(RuntimeError, match="setup failed"):
        fetcher.fetch([mocker.MagicMock(name="component")])

    mock_manager.cleanup.assert_called_once()


# ---------------------------------------------------------------------------
# T4A.1.4 — ProfileSettingsOverrides.from_file called when file is configured
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_conan_fetcher_overrides_loaded_when_file_configured(
    mocker: MockerFixture,
) -> None:
    """ProfileSettingsOverrides.from_file() is called when the overrides file is set.

    The overrides branch is entered only when profile_settings_overrides_file is
    present in config; this test confirms the correct path is forwarded to from_file.
    """
    mock_from_file = mocker.patch(
        f"{_MODULE}.ProfileSettingsOverrides.from_file",
        return_value=mocker.MagicMock(is_empty=lambda: True),
    )

    ctx = _make_mock_ctx(mocker, overrides_file=_OVERRIDES_FILE_PATH)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)

    mock_from_file.assert_called_once_with(_OVERRIDES_FILE_PATH)


# ---------------------------------------------------------------------------
# T4A.1.5 — ParallelExecutor receives the task list from ConanTaskBuilder
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_conan_fetcher_parallel_executor_receives_task_list(
    mocker: MockerFixture,
) -> None:
    """ParallelExecutor.execute() is called with the tasks built by ConanTaskBuilder.

    Verifies the orchestration wiring: builder output → executor input.
    A broken wire here would silently skip all Conan enrichment.
    """
    mock_task_1: MagicMock = mocker.MagicMock(name="task_1")
    mock_task_2: MagicMock = mocker.MagicMock(name="task_2")
    expected_tasks: list[MagicMock] = [mock_task_1, mock_task_2]

    (
        _mock_builder_cls,
        _mock_env_cls,
        _mock_runner_cls,
        mock_executor_cls,
        _mock_agg_cls,
    ) = _patch_full_fetch_pipeline(mocker, tasks=expected_tasks)

    mock_executor_cls.return_value.execute.return_value = [
        mocker.MagicMock(),
        mocker.MagicMock(),
    ]

    ctx = _make_mock_ctx(mocker)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)
    fetcher.fetch([mocker.MagicMock(name="component")])

    execute_call = mock_executor_cls.return_value.execute.call_args
    actual_tasks = execute_call.args[1]
    assert list(actual_tasks) == expected_tasks


# ---------------------------------------------------------------------------
# T4A.1.6 — aggregation errors appear in the returned FetchResult
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_conan_fetcher_aggregation_errors_in_result(
    mocker: MockerFixture,
) -> None:
    """Errors from ConanResultAggregator appear in the returned FetchResult value.

    ConanFetcher returns FetchResult(value=ConanEnrichmentResult). Enrichment
    errors are stored in result.value.errors (not in FetchResult.warnings).
    This test verifies that aggregator errors are not silently dropped.
    """
    (
        _mock_builder_cls,
        _mock_env_cls,
        _mock_runner_cls,
        _mock_executor_cls,
        mock_agg_cls,
    ) = _patch_full_fetch_pipeline(mocker)

    expected_errors: dict = {
        "openssl": {"1.0.0": {"stable": {"hw-linux-x86_64-gcc10_2": ["graph info failed"]}}}
    }
    enrichment_result_with_errors = ConanEnrichmentResult(errors=expected_errors)
    mock_agg_cls.return_value.aggregate.return_value = enrichment_result_with_errors

    ctx = _make_mock_ctx(mocker)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)
    result: FetchResult[ConanEnrichmentResult] = fetcher.fetch([mocker.MagicMock(name="component")])

    assert result.value.errors == expected_errors
