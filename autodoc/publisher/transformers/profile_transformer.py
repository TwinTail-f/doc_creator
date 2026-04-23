"""Трансформер для профиль-центричного вида документации."""

from typing import Any

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.transformers.release_transformer import BaseReleaseTransformer


class ProfileCentricTransformer(BaseReleaseTransformer):
    """
    Трансформер для профиль-центричного вида.

    Перестраивает иерархию ``Компонент → Релиз → Профиль``
    в ``Профиль → Канал → Компонент`` для удобного анализа по профилям.
    Поле ``passport_link`` каждого компонента устанавливается через
    ``PassportLinkMixin._passport_link()`` и может быть заменено реальной
    ссылкой в ``ProfileCentricStrategy`` через
    ``PassportPageRegistry.inject_links_for_profiles()`` — идентично тому,
    как ``ReleasePageStrategy`` делает это для стандартного вида через
    ``PassportPageRegistry.inject_links()``.
    """

    def transform(self, data: ParsedResult) -> dict[str, Any]:
        """
        Возвращает профиль-центричный вид данных.

        Собирает агрегированные настройки сборки (conan_settings) и Docker-образ
        по каждому профилю, затем для каждого профиля выстраивает список
        компонентов, сгруппированных по каналам.

        Args:
            data: Данные парсера.

        Returns:
            Словарь с профилями как верхним уровнем иерархии.
        """
        logger.debug("Трансформация в профиль-центричный вид")

        pd_map: dict[str, Any] = {pd.profile_name: pd for pd in data.profile_definitions}

        # Собираем метаданные профилей из profile_definitions; компоненты перебираем
        # только для того, чтобы определить, какие профили реально присутствуют
        # в не-header-only релизах.
        profile_meta: dict[str, dict[str, Any]] = {}
        for comp in data.components:
            for rel in comp.releases:
                if rel.is_header_only:
                    continue
                for pb in rel.profile_builds:
                    if pb.profile_name not in profile_meta:
                        pd = pd_map.get(pb.profile_name)
                        profile_meta[pb.profile_name] = {
                            "settings": dict(pd.conan_settings) if pd else {},
                            "docker_url": pd.docker_image if pd else "",
                        }

        profiles: list[dict[str, Any]] = []
        for profile_name in sorted(profile_meta):
            settings = profile_meta[profile_name]["settings"]
            entry: dict[str, Any] = {
                "profile_name": profile_name,
                "os": settings.get("os", "Unknown"),
                "arch": settings.get("arch", "—"),
                "compiler": settings.get("compiler", "—"),
                "compiler_version": settings.get("compiler.version", "—"),
                "docker_url": profile_meta[profile_name]["docker_url"],
                "channels": {},
            }

            for comp in data.components:
                for rel in comp.releases:
                    has_profile_build = any(
                        pb.profile_name == profile_name for pb in rel.profile_builds
                    )
                    if not rel.is_header_only and not has_profile_build:
                        continue
                    if rel.channel not in entry["channels"]:
                        entry["channels"][rel.channel] = []
                    entry["channels"][rel.channel].append(
                        {
                            "name": comp.name,
                            "version": rel.version,
                            "passport_link": self._passport_link(
                                comp.name, rel.version
                            ),
                            "reference": rel.conan_reference or "—",
                            "url": rel.artifactory_url or "—",
                        }
                    )

            for channel in entry["channels"]:
                entry["channels"][channel].sort(key=lambda x: x["name"])

            profiles.append(entry)

        return {
            "platform_version": data.platform_version,
            "include_passport_links": self._include_passport_links,
            "profiles": profiles,
        }
