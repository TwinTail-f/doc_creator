"""Шаг пайплайна: загрузка и парсинг манифестов компонентов."""
from autodoc.parser.fetchers.manifest_fetcher import ManifestParser
from autodoc.parser.steps.base import BaseParseStep, PipelineContext


class ManifestStep(BaseParseStep):
    """Шаг 1: Скачивает манифесты из TFS и парсит их в модели Component."""

    name = 'Загрузка и парсинг манифестов'
    is_critical = True

    def execute(self, ctx: PipelineContext) -> None:
        parser = ManifestParser(ctx.config)
        ctx.components = parser.fetch(
            tmp_dir=ctx.tmp_dir,
            excluded=ctx.config.excluded_components or [],
        )
