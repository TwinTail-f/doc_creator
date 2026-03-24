"""
Шаг пайплайна: сбор Docker-ссылок и их применение к профилям сборки.
"""
from autodoc.parser.enrichment.data_enricher import DataEnricher
from autodoc.parser.resolvers.docker_resolver import DockerResolver
from autodoc.parser.steps.base import BaseParseStep, PipelineContext


class DockerResolveStep(BaseParseStep):
    """
    Шаг 4: Собирает Docker-образы и сразу применяет их к ProfileBuild.

    2.3 apply_docker_links вызывается здесь — обогащение происходит
    в шаге, который за него отвечает.

    3.15 Ссылки больше не записываются в ctx.docker_links (поле удалено).
    Для диагностики/save_intermediate данные доступны через
    ctx.intermediate['docker_links'].
    """

    name = 'Сбор Docker-ссылок профилей'
    is_critical = False

    def execute(self, ctx: PipelineContext) -> None:
        resolver = DockerResolver(ctx.config)
        docker_links = resolver.fetch(
            urls=ctx.config.profiles_urls or [],
            target_platform=ctx.config.platform_version,
        )
        DataEnricher.apply_docker_links(ctx.components, docker_links)
        # 3.15 для save_intermediate и диагностики
        ctx.intermediate['docker_links'] = docker_links
