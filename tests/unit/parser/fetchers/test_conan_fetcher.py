"""Юнит-тесты для autodoc/parser/fetchers/conan_fetcher.py.

ConanFetcher оркестрирует полный пайплайн обогащения Conan: установка
окружения → построение задач → параллельное выполнение → агрегация
результатов.
"""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from autodoc.parser.conan.models.conan_enrichment_result import ConanEnrichmentResult
from autodoc.parser.fetchers.conan_fetcher import ConanFetcher
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from tests.unit.parser.fetchers.conftest import _make_mock_ctx, _patch_full_fetch_pipeline

_OVERRIDES_FILE_PATH: str = "/etc/autodoc/profile_overrides.json"

_MODULE: str = "autodoc.parser.fetchers.conan_fetcher"


@pytest.mark.business_logic
def test_conan_fetcher_raises_if_conan_config_url_not_set(
    mocker: MockerFixture,
) -> None:
    """configure() + fetch() выбрасывает RuntimeError, когда conan_config_url пуст."""
    ctx = _make_mock_ctx(mocker, conan_config_url="")

    fetcher = ConanFetcher()
    fetcher.configure(ctx)

    with pytest.raises(RuntimeError, match="conan_config_url"):
        fetcher.fetch([])


@pytest.mark.business_logic
def test_conan_fetcher_returns_empty_on_empty_component_list(
    mocker: MockerFixture,
) -> None:
    """fetch() с пустым списком компонентов возвращает пустой результат, не вызывая runner."""
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


@pytest.mark.infrastructure
def test_conan_fetcher_cleanup_called_on_setup_failure(
    mocker: MockerFixture,
) -> None:
    """env_manager.cleanup() вызывается в блоке finally, даже если setup() выбросил исключение."""
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


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "overrides_file",
    [
        pytest.param(_OVERRIDES_FILE_PATH, id="overrides-file-configured"),
        pytest.param(None, id="overrides-file-absent"),
    ],
)
def test_conan_fetcher_overrides_loaded_only_when_file_configured(
    mocker: MockerFixture,
    overrides_file: str | None,
) -> None:
    """ProfileSettingsOverrides.from_file() вызывается только когда задан файл переопределений."""
    mock_from_file = mocker.patch(
        f"{_MODULE}.ProfileSettingsOverrides.from_file",
        return_value=mocker.MagicMock(is_empty=lambda: True),
    )

    ctx = _make_mock_ctx(mocker, overrides_file=overrides_file)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)

    if overrides_file:
        mock_from_file.assert_called_once_with(overrides_file)
    else:
        mock_from_file.assert_not_called()


@pytest.mark.business_logic
def test_conan_fetcher_parallel_executor_receives_task_list(
    mocker: MockerFixture,
) -> None:
    """ParallelExecutor.execute() вызывается со списком задач, построенным ConanTaskBuilder."""
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


@pytest.mark.business_logic
def test_conan_fetcher_aggregation_errors_in_result(
    mocker: MockerFixture,
) -> None:
    """Ошибки из ConanResultAggregator появляются в значении возвращённого FetchResult."""
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


@pytest.mark.business_logic
def test_conan_fetcher_forwards_exact_range_components_to_task_builder(
    mocker: MockerFixture,
) -> None:
    """exact_range_components из конфигурации доходит до ConanTaskBuilder.build() без изменений."""
    (
        mock_builder_cls,
        _mock_env_cls,
        _mock_runner_cls,
        _mock_executor_cls,
        _mock_agg_cls,
    ) = _patch_full_fetch_pipeline(mocker)

    ctx = _make_mock_ctx(mocker)
    ctx.config.exact_range_components = ["stunnel", "openssh"]

    fetcher = ConanFetcher()
    fetcher.configure(ctx)
    fetcher.fetch([mocker.MagicMock(name="component")])

    build_call = mock_builder_cls.return_value.build.call_args
    assert build_call.kwargs["exact_range_components"] == ["stunnel", "openssh"]


@pytest.mark.business_logic
def test_conan_fetcher_forwards_loaded_overrides_to_task_builder(
    mocker: MockerFixture,
) -> None:
    """Загруженные profile_overrides передаются в ConanTaskBuilder.build() при вызове fetch()."""
    sentinel_overrides = mocker.MagicMock(is_empty=lambda: False)
    mocker.patch(
        f"{_MODULE}.ProfileSettingsOverrides.from_file",
        return_value=sentinel_overrides,
    )

    (
        mock_builder_cls,
        _mock_env_cls,
        _mock_runner_cls,
        _mock_executor_cls,
        _mock_agg_cls,
    ) = _patch_full_fetch_pipeline(mocker)

    ctx = _make_mock_ctx(mocker, overrides_file=_OVERRIDES_FILE_PATH)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)
    fetcher.fetch([mocker.MagicMock(name="component")])

    build_call = mock_builder_cls.return_value.build.call_args
    assert build_call.kwargs["profile_overrides"] is sentinel_overrides
