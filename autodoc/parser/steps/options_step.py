"""Шаг пайплайна: сбор опций Conan для компонентов."""

from autodoc.infrastructure.logger import logger
from autodoc.parser.enrichment.data_enricher import DataEnricher
from autodoc.parser.fetchers.options_fetcher import OptionsMap, OptionsFetcher
from autodoc.parser.fetchers.base import IFetcher
from autodoc.parser.steps.base import BaseParseStep, PipelineContext


class OptionsResolveStep(BaseParseStep):
    """Шаг 2: Скачивает options.json и применяет опции к компонентам."""

    name = "Сбор опций Conan (options.json)"
    is_critical = False

    def __init__(self, fetcher: "IFetcher[OptionsMap] | None" = None) -> None:
        """
        Args:
            fetcher: Фетчер опций Conan. Если не передан — используется
                     ``OptionsFetcher`` по умолчанию.
        """
        self._fetcher = fetcher or OptionsFetcher()

    def execute(self, ctx: PipelineContext) -> None:
        """
        Скачивает options.json и применяет опции Conan к компонентам.

        Конфигурирует OptionsFetcher из контекста, выполняет загрузку,
        передаёт результат в DataEnricher и сохраняет карту опций
        в ctx.intermediate для диагностики.

        Args:
            ctx: Контекст пайплайна с заполненными компонентами.
        """
        self._fetcher.configure(ctx)
        result = self._fetcher.fetch(ctx.components)
        if result.warnings:
            for w in result.warnings:
                logger.warning(w)
        options_map = result.value
        DataEnricher.apply_options(ctx.components, options_map)
        ctx.intermediate["options_map"] = options_map
