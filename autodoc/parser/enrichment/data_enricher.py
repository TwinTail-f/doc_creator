"""
Единственная точка мутации доменных моделей в пайплайне парсера.
"""

from autodoc.models.component import (
    ConanInputOptions,
    Component,
    ProfileDefinition,
)
from autodoc.models.conan_result import ConanEnrichmentResult
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
        Записывает входные опции Conan (ConanInputOptions) в каждый ``Release``.

        Заполняет ``build_option_sets`` — список ``ConanInputOptions``
        (шаг 2, входные данные до выполнения conan graph info).
        ``TotalOptionsSet`` будет заполнен позднее в ``apply_conan_results``
        из фактических resolved-опций conan graph info.

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
                        ConanInputOptions(id=k, options=v) for k, v in opts.items()
                    ]

    @staticmethod
    def apply_docker_links(
        components: list[Component],
        docker_links: dict[str, str],
        profile_definitions: list[ProfileDefinition] | None = None,
    ) -> None:
        """
        Заполняет поле docker_image в записях ProfileDefinition.
        Если profile_definitions передан — выполняет upsert по profile_name.

        Args:
            components: Список компонентов для обогащения.
            docker_links: Маппинг ``имя_профиля → docker_image_url``.
            profile_definitions: Изменяемый список ProfileDefinition для upsert.
        """
        pd_map: dict[str, ProfileDefinition] = {}
        if profile_definitions is not None:
            pd_map = {pd.profile_name: pd for pd in profile_definitions}

        for comp in components:
            for release in comp.releases:
                for pb in release.profile_builds:
                    pname = pb.profile_name
                    docker_url = docker_links.get(pname, "")
                    if profile_definitions is not None:
                        if pname not in pd_map:
                            entry = ProfileDefinition(profile_name=pname, docker_image=docker_url)
                            pd_map[pname] = entry
                            profile_definitions.append(entry)
                        else:
                            pd_map[pname].docker_image = docker_url

    @staticmethod
    def apply_conan_results(
        components: list[Component],
        result: ConanEnrichmentResult,
        profile_definitions: list[ProfileDefinition] | None = None,
    ) -> None:
        """
        Применяет результаты Conan graph info к моделям ``Release`` и ``ProfileBuild``.

        ``ReleaseConanData.default_options`` хранит типизированные объекты
        ``DefaultOptionsSet`` (из поля ``default_options`` в JSON).
        ``ReleaseConanData.total_options`` хранит типизированные объекты
        ``TotalOptionsSet`` (из поля ``options`` в JSON — resolved-опции).
        ``ProfileConanData.variants`` хранит типизированные объекты ``ConanVariant``.

        Args:
            components: Список компонентов для обогащения.
            result: ``ConanEnrichmentResult`` из ``ConanFetcher.fetch()``.
            profile_definitions: Изменяемый список ProfileDefinition для upsert conan_settings.
        """
        # Строим карту один раз до всех циклов
        pd_map: dict[str, ProfileDefinition] = (
            {pd.profile_name: pd for pd in profile_definitions}
            if profile_definitions is not None else {}
        )

        for comp in components:
            for release in comp.releases:
                release_key = (comp.name, release.version, release.channel)
                rel_data = result.release_data.get(release_key)
                if rel_data:
                    release.conan_reference = rel_data.base_ref
                    release.artifactory_url = rel_data.artifactory_url
                    # DefaultOptionsSet: из поля "default_options" в conan graph info
                    release.default_options = rel_data.default_options
                    # TotalOptionsSet: из поля "options" в conan graph info
                    release.total_option_sets = rel_data.total_options
                    release.patches = rel_data.patches
                    release.dependencies = rel_data.dependencies

                for pb in release.profile_builds:
                    pb_data = result.profile_data.get(id(pb))
                    if pb_data:
                        pb.exists = pb_data.exists
                        pb.variants = pb_data.variants
                        if profile_definitions is not None:
                            pname = pb.profile_name
                            if pname not in pd_map:
                                entry = ProfileDefinition(
                                    profile_name=pname,
                                    conan_settings=pb_data.conan_settings,
                                )
                                pd_map[pname] = entry
                                profile_definitions.append(entry)
                            elif pb_data.conan_settings:  # не затираем непустые данные пустыми
                                pd_map[pname].conan_settings = pb_data.conan_settings
