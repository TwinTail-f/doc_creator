"""
Единственная точка мутации доменных моделей в пайплайне парсера.
"""

from typing import Any

from autodoc.models.component import (
    ConanInputOptions,
    Component,
    OptionDefinition,
    OptionSet,
    ProfileDefinition,
)
from autodoc.models.conan_result import ConanEnrichmentResult
from autodoc.parser.fetchers.options_fetcher import OptionsMap


def _parse_option_str(option_str: str) -> dict[str, Any]:
    """Convert 'shared=True, fPIC=False' string to {'shared': 'True', 'fPIC': 'False'}."""
    result: dict[str, Any] = {}
    if not option_str:
        return result
    for part in option_str.split(","):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            # strip package prefix (e.g. "mylib:shared=True" → key "shared")
            key = k.strip().split(":")[-1].strip()
            result[key] = v.strip()
    return result


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
                        ConanInputOptions(id=k, options=v) for k, v in opts.items()
                    ]
                    release.option_sets = [
                        OptionSet(id=k, options=_parse_option_str(v)) for k, v in opts.items()
                    ]

    @staticmethod
    def apply_docker_links(
        components: list[Component],
        docker_links: dict[str, str],
        profile_definitions: list[ProfileDefinition] | None = None,
    ) -> None:
        """
        Fills docker_image into ProfileDefinition entries.
        If profile_definitions is provided, upserts by profile_name.

        Args:
            components: Список компонентов для обогащения.
            docker_links: Маппинг ``имя_профиля → docker_image_url``.
            profile_definitions: Mutable list of ProfileDefinition to upsert into.
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

        ``ReleaseConanData.default_options`` и ``ProfileConanData.variants`` уже
        хранят типизированные объекты (``OptionDefinition``, ``ConanVariant``),
        поэтому прямое присваивание не требует дополнительной конверсии.

        Args:
            components: Список компонентов для обогащения.
            result: ``ConanEnrichmentResult`` из ``ConanFetcher.fetch()``.
            profile_definitions: Mutable list of ProfileDefinition to upsert conan_settings into.
        """
        pd_map: dict[str, ProfileDefinition] = {}
        if profile_definitions is not None:
            pd_map = {pd.profile_name: pd for pd in profile_definitions}

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
                        pb.exists = pb_data.exists
                        pb.variants = pb_data.variants
                        # conan_settings now lives in ProfileDefinition
                        if profile_definitions is not None:
                            pname = pb.profile_name
                            if pname not in pd_map:
                                entry = ProfileDefinition(
                                    profile_name=pname,
                                    conan_settings=pb_data.conan_settings,
                                )
                                pd_map[pname] = entry
                                profile_definitions.append(entry)
                            else:
                                if pb_data.conan_settings:  # только если есть что писать (защита от header only)
                                    pd_map[pname].conan_settings = pb_data.conan_settings
