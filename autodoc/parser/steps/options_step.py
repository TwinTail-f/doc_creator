"""Шаг пайплайна: сбор опций Conan для компонентов."""
from autodoc.infrastructure.logger import logger
from autodoc.parser.enrichment.data_enricher import DataEnricher
from autodoc.parser.fetchers.options_fetcher import OptionsMap, OptionsFetcher
from autodoc.parser.steps.base import BaseParseStep, IFetcher, PipelineContext


class OptionsResolveStep(BaseParseStep):
    """Шаг 2: Скачивает options.json и применяет опции к компонентам."""

    name = 'Сбор опций Conan (options.json)'
    is_critical = False

    def __init__(self, fetcher: 'IFetcher[OptionsMap] | None' = None) -> None:
        self._fetcher = fetcher or OptionsFetcher()

    def execute(self, ctx: PipelineContext) -> None:
        self._fetcher.configure(ctx)
        result = self._fetcher.fetch(ctx.components)
        if result.warnings:
            for w in result.warnings:
                logger.warning(w)
        options_map = result.value
        DataEnricher.apply_options(ctx.components, options_map)
        ctx.intermediate['options_map'] = options_map
