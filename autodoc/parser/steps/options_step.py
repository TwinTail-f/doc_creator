"""Шаг пайплайна: сбор опций Conan для компонентов."""
from autodoc.parser.enrichment.data_enricher import DataEnricher
from autodoc.parser.resolvers.options_resolver import OptionsResolver
from autodoc.parser.steps.base import BaseParseStep, PipelineContext


class OptionsResolveStep(BaseParseStep):
    """Шаг 2: Скачивает options.json и применяет опции к компонентам."""

    name = 'Сбор опций Conan (options.json)'
    is_critical = False

    def execute(self, ctx: PipelineContext) -> None:
        resolver = OptionsResolver(ctx.config)
        options_map = resolver.fetch(ctx.components)
        DataEnricher.apply_options(ctx.components, options_map)
        ctx.intermediate['options_map'] = options_map
