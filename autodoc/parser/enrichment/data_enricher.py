"""
Единственная точка мутации доменных моделей в пайплайне парсера.
"""

from autodoc.models.component import BuildOptionSet, Component, ConanVariant
from autodoc.models.conan_result import (
    ConanEnrichmentResult,
)  # 3.12 прямой импорт без отсрочки
from autodoc.parser.fetchers.options_fetcher import OptionsMap


class DataEnricher:
    """
    Применяет результаты шагов пайплайна к моделям компонентов.

    Все методы — статические. Единственное место явной мутации доменных
    объектов (``Release``, ``ProfileBuild``) во всём пайплайне.
    """

    @staticmethod
    def apply_options(
        components: list[Component],
        options_map: OptionsMap,
    ) -> None:
        """
        Записывает опции Conan в приватный атрибут каждого ``Release``.

        Args:
            components: Список компонентов для обогащения.
            options_map: Маппинг ``(comp_name, version, channel) → options``.
        """
        for comp in components:
            for release in comp.releases:
                key: tuple[str, str, str] = (
                    comp.name,
                    release.version,
                    release.channel,
                )
                opts = options_map.get(key)
                if opts is not None:
                    release._build_option_sets_internal = opts
                    release.build_option_sets = [
                        BuildOptionSet(id=k, options=v) for k, v in opts.items()
                    ]

    @staticmethod
    def apply_docker_links(
        components: list[Component],
        docker_links: dict[str, str],
    ) -> None:
        """
        Заполняет ``docker_image`` для каждого ``ProfileBuild``.

        Args:
            components: Список компонентов для обогащения.
            docker_links: Маппинг ``имя_профиля → docker_image_url``.
        """
        for comp in components:
            for release in comp.releases:
                for pb in release.profile_builds:
                    pb.docker_image = docker_links.get(pb.profile_name, "")

    @staticmethod
    def apply_conan_results(
        components: list[Component],
        result: ConanEnrichmentResult,
    ) -> None:
        """
        Применяет результаты Conan graph info к моделям ``Release`` и ``ProfileBuild``.

        Args:
            components: Список компонентов для обогащения.
            result: ``ConanEnrichmentResult`` из ``ConanManager.enrich_components()``.
        """
        for comp in components:
            for release in comp.releases:
                release_key = (comp.name, release.version, release.channel)
                rel_data = result.release_data.get(release_key)
                if rel_data:
                    release.conan_reference = rel_data.base_ref
                    release.artifactory_url = rel_data.artifactory_url
                    release.default_options = rel_data.default_options
                    release.patches = rel_data.patches
                    release.dependencies = rel_data.dependencies

                for pb in release.profile_builds:
                    pb_data = result.profile_data.get(id(pb))
                    if pb_data:
                        pb.conan_settings = pb_data.conan_settings
                        pb.exists = pb_data.exists
                        pb.variants = [ConanVariant(**v) for v in pb_data.variants]
