"""Общие тестовые хелперы для юнит-тестов autodoc/parser/fetchers/.

Содержит функции, используемые более чем одним тестовым модулем в этом
пакете (test_conan_fetcher.py и test_conan_fetcher_result_content.py).
Это не conftest.py: здесь нет pytest-фикстур, поэтому хелперы явно
импортируются теми модулями, которым они нужны.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from pytest_mock import MockerFixture

from autodoc.parser.conan.models.conan_enrichment_result import ConanEnrichmentResult

_CONAN_CONFIG_URL: str = "https://art.example.com/conan-config.zip"
_ARTIFACTORY_URL: str = "https://art.example.com/artifactory/conan2"
_PLATFORM_VERSION: str = "2.0"
_TIMEOUT_SEC: int = 60
_CONAN_HOME_TEMPLATE: Path = Path("/tmp/conan_home_template")

_MODULE: str = "autodoc.parser.fetchers.conan_fetcher"


def make_mock_ctx(
    mocker: MockerFixture,
    conan_config_url: str = _CONAN_CONFIG_URL,
    overrides_file: str | None = None,
) -> MagicMock:
    """Строит минимальный mock PipelineContext с заданным conan_config_url.

    Задаёт разумные значения по умолчанию для всех атрибутов, которые
    читает ``ConanFetcher.configure()``.

    Args:
        mocker: Фикстура pytest-mock для создания mock-объекта.
        conan_config_url: URL zip-архива конфигурации Conan в Artifactory.
        overrides_file: Путь к файлу переопределений настроек профилей
            (``None``, если не задан).

    Returns:
        Mock-объект ``PipelineContext`` с заполненным ``config``.
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


def patch_full_fetch_pipeline(
    mocker: MockerFixture,
    tasks: list[Any] | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Патчит всех внешних коллабораторов, используемых внутри ConanFetcher.fetch().

    Каждый mock класса заранее настроен разумными значениями по умолчанию,
    так что тестам достаточно переопределить только нужный им атрибут.

    Args:
        mocker: Фикстура pytest-mock.
        tasks: Список задач, которые должен вернуть ``ConanTaskBuilder.build()``.
            Если не передан — используется список из одной mock-задачи.

    Returns:
        Кортеж ``(mock_builder_cls, mock_env_cls, mock_runner_cls,
        mock_executor_cls, mock_agg_cls)`` — mock-классы коллабораторов.
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
