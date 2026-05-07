"""Шаг пайплайна: загрузка и парсинг манифестов компонентов."""

from autodoc.common.logger import logger
from autodoc.models.component import Component
from autodoc.parser.fetchers.manifest_fetcher import ManifestFetcher
from autodoc.parser.fetchers.i_fetcher import IFetcher
from autodoc.parser.steps.base_parse_step import BaseParseStep
from autodoc.parser.pipeline.context import PipelineContext


class ManifestStep(BaseParseStep):
    """Шаг 1: Скачивает манифесты из TFS и парсит их в модели Component."""

    name = "Загрузка и парсинг манифестов"
    is_critical = True

    def __init__(self, fetcher: IFetcher[list[Component]] | None = None) -> None:
        """
        Args:
            fetcher: Фетчер манифестов. Если не передан — используется
                     ``ManifestFetcher`` по умолчанию.
        """
        self._fetcher = fetcher or ManifestFetcher()

    def execute(self, ctx: PipelineContext) -> None:
        """
        Скачивает манифесты из TFS и разбирает их в модели Component.

        Конфигурирует фетчер из контекста, запускает загрузку, логирует
        предупреждения и записывает компоненты в ctx.components.

        Args:
            ctx: Контекст пайплайна с заполненной конфигурацией и tmp_dir.
        """
        self._fetcher.configure(ctx)
        result = self._fetcher.fetch(
            tmp_dir=ctx.tmp_dir,
            excluded=ctx.config.excluded_components or [],
        )
        if result.warnings:
            for w in result.warnings:
                logger.warning(w)
        ctx.components = result.value
