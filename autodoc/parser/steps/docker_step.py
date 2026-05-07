"""
Шаг пайплайна: сбор Docker-ссылок и их применение к профилям сборки.
"""

from autodoc.infrastructure.logger import logger
from autodoc.parser.enrichment.data_enricher import DataEnricher
from autodoc.parser.fetchers.docker_fetcher import DockerLinksMap, DockerFetcher
from autodoc.interfaces.i_fetcher import IFetcher
from autodoc.interfaces.base_parse_step import BaseParseStep
from autodoc.parser.pipeline.context import PipelineContext


class DockerResolveStep(BaseParseStep):
    """
    Шаг 4: Собирает Docker-образы и сразу применяет их к ProfileBuild.
    """

    name = "Сбор Docker-ссылок профилей"
    is_critical = False

    def __init__(self, fetcher: IFetcher[DockerLinksMap] | None = None) -> None:
        """
        Args:
            fetcher: Фетчер Docker-ссылок. Если не передан — используется
                     ``DockerFetcher`` по умолчанию.
        """
        self._fetcher = fetcher or DockerFetcher()

    def execute(self, ctx: PipelineContext) -> None:
        """
        Собирает Docker-ссылки профилей и применяет их к ProfileBuild.

        Конфигурирует DockerFetcher, загружает ссылки по URL профилей из
        конфигурации, передаёт результат в DataEnricher и сохраняет карту
        в ctx.intermediate для диагностики и save_intermediate.

        Args:
            ctx: Контекст пайплайна с заполненными компонентами и конфигурацией.
        """
        self._fetcher.configure(ctx)
        result = self._fetcher.fetch(
            urls=ctx.config.profiles_urls or [],
            target_platform=ctx.config.platform_version,
        )
        if result.warnings:
            for w in result.warnings:
                logger.warning(w)
        docker_links = result.value
        DataEnricher.apply_docker_links(
            ctx.components, docker_links, profile_definitions=ctx.profile_definitions
        )
        ctx.intermediate["docker_links"] = docker_links
