"""Шаг пайплайна: обогащение компонентов данными Conan graph info."""
from autodoc.parser.conan.conan_manager import ConanManager
from autodoc.parser.enrichment.data_enricher import DataEnricher
from autodoc.parser.steps.base import BaseParseStep, PipelineContext

class ConanEnrichStep(BaseParseStep):
    """
    Шаг 3: Запускает conan graph info и применяет результаты к моделям.
    """

    name = "Обогащение данными Conan graph info"
    is_critical = False

    def execute(self, ctx: PipelineContext) -> None:
        """
        Запускает conan graph info и применяет результаты к компонентам.

        Делегирует выполнение ConanManager, затем передаёт
        ConanEnrichmentResult в DataEnricher для мутации моделей.

        Args:
            ctx: Контекст пайплайна с заполненными компонентами и конфигурацией.
        """
        manager = ConanManager(ctx.config)
        manager.clean_cache()
        conan_result = manager.enrich_components(
            components=ctx.components,
            target_platform=ctx.config.platform_version,
            artifactory_base_url=ctx.config.artifactory_components_conan2_url or "",
        )
        DataEnricher.apply_conan_results(ctx.components, conan_result)
        ctx.intermediate["conan_report"] = conan_result.errors
