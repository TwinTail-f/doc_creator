"""Шаг пайплайна: обогащение компонентов данными Conan graph info."""

from autodoc.infrastructure.logger import logger
from autodoc.models.conan_result import ConanEnrichmentResult
from autodoc.parser.enrichment.data_enricher import DataEnricher
from autodoc.parser.fetchers.base import IFetcher
from autodoc.parser.fetchers.conan_fetcher import ConanFetcher
from autodoc.parser.steps.base import BaseParseStep
from autodoc.parser.pipeline.context import PipelineContext


class ConanEnrichStep(BaseParseStep):
    """
    Шаг 3: Запускает conan graph info и применяет результаты к моделям.

    Следует тому же двухфазовому протоколу, что и остальные шаги пайплайна:

        fetcher.configure(ctx)
        result = fetcher.fetch(ctx.components)
        DataEnricher.apply_conan_results(ctx.components, result.value, profile_definitions=ctx.profile_definitions)

    Зависимость от ``ConanFetcher`` внедряется через конструктор — шаг
    легко тестируется с подставным фетчером без запуска Conan.
    """

    name = "Обогащение данными Conan graph info"
    is_critical = False

    def __init__(
        self,
        fetcher: IFetcher[ConanEnrichmentResult] | None = None,
    ) -> None:
        """
        Args:
            fetcher: Фетчер данных Conan. Если не передан — используется
                     ``ConanFetcher`` по умолчанию.
        """
        self._fetcher = fetcher or ConanFetcher()

    def execute(self, ctx: PipelineContext) -> None:
        """
        Собирает данные Conan и применяет их к компонентам.

        Конфигурирует фетчер из контекста, запускает сбор данных,
        передаёт результат в ``DataEnricher`` и сохраняет лог ошибок
        в ``ctx.intermediate`` для диагностики.

        Args:
            ctx: Контекст пайплайна с заполненными компонентами и конфигурацией.
        """
        self._fetcher.configure(ctx)
        result = self._fetcher.fetch(ctx.components)

        if result.warnings:
            for w in result.warnings:
                logger.warning(w)

        DataEnricher.apply_conan_results(
            ctx.components, result.value, profile_definitions=ctx.profile_definitions
        )
        ctx.intermediate["conan_report"] = result.value.errors
