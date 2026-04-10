"""
Парсер манифестов компонентов: разбор .properties-файлов в доменные модели.
Не имеет доступа к TFS и не выполняет сетевых вызовов.
"""

from pathlib import Path

from autodoc.infrastructure.logger import logger
from autodoc.models.component import Component, ProfileBuild, Release
from autodoc.parser.fetchers.properties_reader import read_properties


class ManifestParser:
    """Преобразует список .properties-файлов в список Component."""

    def __init__(self, target_platform: str) -> None:
        """
        Инициализирует парсер для указанной целевой платформы.

        Args:
            target_platform: Версия платформы (например '2.0'), используется
                             для фильтрации релизов манифестов.
        """
        self._target_platform = target_platform

    def parse(
        self,
        files: list[Path],
        excluded: list[str],
    ) -> tuple[list[Component], list[str]]:
        """
        Разбирает список файлов манифестов.

        Returns:
            (components, warnings) — список компонентов и список предупреждений.
        """
        target_platform = self._target_platform
        components: list[Component] = []
        warnings: list[str] = []
        parsed_count = 0
        excluded_count = 0

        for filepath in files:
            # Проверяем доступность файла до обращения к нему.
            if not filepath.is_file():
                msg = f"файл не найден или недоступен: {filepath.name}"
                logger.warning(msg)
                warnings.append(msg)
                continue

            try:
                props = read_properties(filepath)
            except OSError as e:
                msg = f"не удалось прочитать {filepath.name}: {e}"
                logger.warning(msg)
                warnings.append(msg)
                continue

            name = props.get("name", "")
            if not name:
                logger.debug(f'Пропуск {filepath.name} — отсутствует поле "name"')
                continue

            if name in excluded:
                logger.debug(f"Компонент {name} исключён")
                excluded_count += 1
                continue

            releases = self._build_releases(props)
            if not releases:
                continue

            components.append(
                Component(
                    name=name,
                    description=props.get("description", ""),
                    git_project=props.get("tfs_git_project", ""),
                    git_repo=props.get("git_repo_name", ""),
                    releases=releases,
                )
            )
            parsed_count += 1

        logger.info(
            f"обработано {parsed_count} компонентов, исключено {excluded_count}"
        )
        return components, warnings

    def _build_releases(self, props: dict) -> list[Release]:
        """Строит список Release из словаря свойств манифеста."""
        target_platform = self._target_platform
        comp_versions = [
            v.strip()
            for v in props.get("versions.component", "").split(",")
            if v.strip()
        ]
        plat_versions = [
            v.strip()
            for v in props.get("versions.platform", "").split(",")
            if v.strip()
        ]
        git_project = props.get("tfs_git_project", "")
        git_repo = props.get("git_repo_name", "")
        releases: list[Release] = []

        for p_ver in plat_versions:
            if not (
                p_ver.startswith(f"{target_platform}-") or p_ver == target_platform
            ):
                continue
            for c_ver in comp_versions:
                profiles_str = self._get_profiles_string(props, c_ver, p_ver)
                if not profiles_str:
                    continue
                channel = p_ver.split("-")[1] if "-" in p_ver else ""
                profile_list = [p.strip() for p in profiles_str.split(",") if p.strip()]
                releases.append(
                    Release(
                        version=c_ver,
                        platform=target_platform,
                        channel=channel,
                        git_url=f"{git_project}/_git/{git_repo}" if git_repo else "",
                        profile_builds=[
                            ProfileBuild(profile_name=prof) for prof in profile_list
                        ],
                    )
                )

        return releases

    @staticmethod
    def _get_profiles_string(props: dict, c_ver: str, p_ver: str) -> str:
        """Извлекает строку со списком профилей для заданной комбинации версий."""
        key_develop = f"integration-profiles-develop-{c_ver}-{p_ver}"
        key_profiles = f"profiles-{c_ver}-{p_ver}"
        return props.get(key_develop, props.get(key_profiles, ""))
