"""
Фетчер данных Conan graph info.

Реализует ``IFetcher[ConanEnrichmentResult]``, выстраивая тот же
двухфазовый протокол, что используется остальными шагами пайплайна:

    ConanFetcher.configure(ctx)          # извлечение параметров из контекста
    ConanFetcher.fetch(components)       # сбор данных → FetchResult[ConanEnrichmentResult]

Внутренняя разбивка на слои:
- ``ConanEnvironmentManager`` — однократная установка конфигурации из Artifactory;
- ``ConanTaskBuilder``        — формирование задач из моделей компонентов;
- ``Conan2Runner``            — запуск subprocess ``conan graph info``;
- ``ParallelExecutor``        — параллельное выполнение задач;
- ``ConanResultParser``       — парсинг одного JSON-ответа;
- ``ConanResultAggregator``   — агрегация N результатов → ``ConanEnrichmentResult``.
"""



from autodoc.infrastructure.logger import logger
from autodoc.infrastructure.parallel_executor import ParallelExecutor
from autodoc.models.component import Component
from autodoc.models.conan_result import ConanEnrichmentResult
from autodoc.parser.conan.conan_runner import Conan2Runner, ConanEnvironmentManager
from autodoc.parser.conan.result_aggregator import ConanResultAggregator
from autodoc.parser.conan.result_parser import ConanResultParser
from autodoc.parser.conan.task_builder import ConanTaskBuilder
from autodoc.parser.fetchers.base import FetchResult, IFetcher
from autodoc.parser.pipeline.context import PipelineContext

_DEFAULT_MAX_WORKERS: int = 64
_LOG_PROGRESS_INTERVAL: int = 50


class ConanFetcher(IFetcher[ConanEnrichmentResult]):
    """
    Фетчер данных ``conan graph info``.

    Следует двухфазовому протоколу ``IFetcher``:

    1. ``configure(ctx)`` — извлекает таймаут, платформу, URL Artifactory
       и URL конфигурации Conan из конфигурации пайплайна.
    2. ``fetch(components)`` — однократно устанавливает конфигурацию Conan
       из Artifactory в изолированную директорию-шаблон, строит задачи,
       запускает их параллельно (каждый вызов копирует шаблон в свой tmp),
       агрегирует результаты и очищает все временные директории.
    """

    def __init__(self) -> None:
        """Initialises the fetcher; call ``configure(ctx)`` before ``fetch()``."""
        self._timeout: int = 0
        self._platform_version: str = ""
        self._artifactory_base_url: str = ""
        self._conan_config_url: str = ""

    def configure(self, ctx: PipelineContext) -> None:
        """
        Инициализирует фетчер из контекста пайплайна.

        Args:
            ctx: Контекст пайплайна с валидированной конфигурацией.
        """
        self._timeout = ctx.config.conan_command_timeout
        self._platform_version = ctx.config.platform_version
        self._artifactory_base_url = (
            ctx.config.artifactory_components_conan2_url or ""
        ).rstrip("/")
        self._conan_config_url = (ctx.config.conan_config_url or "").strip()

    def fetch(
        self,
        components: list[Component],
    ) -> FetchResult[ConanEnrichmentResult]:
        """
        Выполняет ``conan graph info`` для всех компонентов и агрегирует результаты.

        Этапы:
        1. Установка конфигурации Conan из Artifactory в директорию-шаблон
           (``ConanEnvironmentManager.setup()``).
        2. Очистка кэша пакетов Conan в шаблоне.
        3. Построение задач из моделей компонентов.
        4. Параллельный запуск задач через ``ParallelExecutor``.
           Каждый вызов ``Conan2Runner.run()`` копирует шаблон в отдельный tmp
           и удаляет его по завершении.
        5. Агрегация сырых результатов в ``ConanEnrichmentResult``.
        6. Удаление директории-шаблона (``ConanEnvironmentManager.cleanup()``).

        Args:
            components: Список компонентов с заполненными ``_build_option_sets_internal``.

        Returns:
            ``FetchResult`` с ``ConanEnrichmentResult``. Поле ``warnings`` не
            используется — ошибки фиксируются в ``result.errors`` и
            ``result.execution_report``.

        Raises:
            RuntimeError: Если установка конфигурации Conan завершилась с ошибкой.
        """
        if not self._conan_config_url:
            raise RuntimeError(
                "ConanFetcher: conan_config_url не задан в конфигурации. "
                "Укажите URL zip-архива конфигурации Conan в Artifactory."
            )

        task_builder = ConanTaskBuilder()
        tasks = task_builder.build(
            components, self._platform_version, self._artifactory_base_url
        )

        if not tasks:
            logger.info("Нет задач для выполнения.")
            return FetchResult(value=ConanEnrichmentResult())

        env_manager = ConanEnvironmentManager(config_url=self._conan_config_url)
        try:
            conan_home_template = env_manager.setup()

            runner = Conan2Runner(
                timeout=self._timeout,
                conan_home_template=conan_home_template,
            )
            runner.clean_cache()

            logger.info(
                f"Сформировано {len(tasks)} задач, запуск в {_DEFAULT_MAX_WORKERS} потоках…"
            )

            executor = ParallelExecutor(
                max_workers=_DEFAULT_MAX_WORKERS,
                log_progress_interval=_LOG_PROGRESS_INTERVAL,
            )
            raw_results = executor.execute(
                runner.run,
                tasks,
                task_label="задач Conan",
            )

            aggregator = ConanResultAggregator(ConanResultParser())
            result = aggregator.aggregate(
                tasks, raw_results, self._artifactory_base_url, self._platform_version
            )
            result.execution_report = aggregator.build_execution_report(
                tasks, raw_results
            )

        finally:
            env_manager.cleanup()

        return FetchResult(value=result)
