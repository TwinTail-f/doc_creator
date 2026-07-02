"""Трансформер для профиль-центричного вида документации."""

from typing import Any

from autodoc.common.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.converters.base_release_converter import BaseReleaseConverter


class ProfileCentricConverter(BaseReleaseConverter):
    """
    Трансформер для профиль-центричного вида.

    Перестраивает иерархию ``Компонент → Релиз → Профиль``
    в ``Профиль → Канал → Компонент`` для удобного анализа по профилям.
    Поле ``passport_link`` каждого компонента заполняется реальной ссылкой
    в ``ProfileCentricStrategy`` через ``PassportPageRegistry.inject_links_for_profiles()``
    после публикации паспортов.
    """

    def _collect_profile_meta(
        self,
        data: ParsedResult,
        pd_map: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """
        Собирает метаданные профилей из не-header-only релизов.

        Проходит по всем компонентам и релизам, собирая настройки (conan_settings)
        и docker_image для каждого уникального имени профиля.

        Args:
            data: Данные парсера.
            pd_map: Словарь ``{profile_name: ProfileDefinition}``.

        Returns:
            Словарь ``{profile_name: {'settings': dict, 'docker_url': str}}``.
        """
        profile_meta: dict[str, dict[str, Any]] = {}
        for comp in data.components:
            for rel in comp.releases:
                if comp.is_header_only:
                    continue
                for pb in rel.profile_builds:
                    if pb.profile_name not in profile_meta:
                        settings, docker_url = self._resolve_profile_meta(pd_map, pb.profile_name)
                        profile_meta[pb.profile_name] = {
                            "settings": settings,
                            "docker_url": docker_url,
                        }
        return profile_meta

    def _build_profile_entry(
        self,
        profile_name: str,
        profile_meta: dict[str, dict[str, Any]],
        data: ParsedResult,
    ) -> dict[str, Any]:
        """
        Строит запись одного профиля для view-model профиль-центричного вида.

        Для каждого компонента и релиза с данным профилем формирует список
        компонентов, сгруппированных по каналам.

        Args:
            profile_name: Имя профиля.
            profile_meta: Агрегированные метаданные профилей (из ``_collect_profile_meta``).
            data: Данные парсера.

        Returns:
            Словарь с ключами ``profile_name``, ``os``, ``arch``, ``compiler``,
            ``compiler_version``, ``docker_url``, ``channels``.
        """
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
                is_relevant_for_profile = comp.is_header_only or has_profile_build
                if not is_relevant_for_profile:
                    continue
                if rel.channel not in entry["channels"]:
                    entry["channels"][rel.channel] = []
                entry["channels"][rel.channel].append(
                    {
                        "name": comp.name,
                        "version": rel.version,
                        "passport_link": None,
                        "reference": rel.conan_reference or "—",
                        "url": rel.artifactory_url or "—",
                    }
                )

        for channel in entry["channels"]:
            entry["channels"][channel].sort(key=lambda x: x["name"])

        return entry

    def transform(self, data: ParsedResult) -> dict[str, Any]:
        """
        Возвращает профиль-центричный вид данных.

        Собирает метаданные профилей, затем для каждого профиля строит список
        компонентов, сгруппированных по каналам.

        Args:
            data: Данные парсера.

        Returns:
            Словарь с профилями как верхним уровнем иерархии.
        """
        logger.debug("Трансформация в профиль-центричный вид")

        pd_map: dict[str, Any] = self._build_profile_definition_map(data)
        profile_meta = self._collect_profile_meta(data, pd_map)

        profiles: list[dict[str, Any]] = [
            self._build_profile_entry(profile_name, profile_meta, data)
            for profile_name in sorted(profile_meta)
        ]

        return {
            **self._base_view_model(data),
            "profiles": profiles,
        }
