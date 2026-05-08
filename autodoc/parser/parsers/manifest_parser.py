"""
Парсер манифестов компонентов: разбор .properties-файлов в доменные модели.
Не имеет доступа к TFS и не выполняет сетевых вызовов.
"""

from dataclasses import dataclass, field
from pathlib import Path

from autodoc.common.logger import logger
from autodoc.common.parallel_executor import ParallelExecutor
from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.utils.properties_reader import read_properties

_MANIFEST_MAX_WORKERS: int = 32
_MANIFEST_LOG_INTERVAL: int = 50


@dataclass
class _FileParseResult:
    """Результат разбора одного .properties-файла. Используется только внутри ManifestParser."""

    component: Component | None = None
    warnings: list[str] = field(default_factory=list)
    is_excluded: bool = False


class ManifestParser:
    """Преобразует список .properties-файлов в список Component."""

    def __init__(self, target_platform: str, tfs_collection_url: str = "") -> None:
        """
        Инициализирует парсер для указанной целевой платформы.

        Args:
            target_platform: Версия платформы (например '2.0'), используется
                             для фильтрации релизов манифестов.
            tfs_collection_url: Базовый URL коллекции TFS
                                 формирует полные ссылки на
                                 репозиторий в поле ``git_url`` каждого Release,
                                 с учётом ``tfs_git_project`` из манифеста.
        """
        self._target_platform = target_platform
        self._tfs_collection_url: str = tfs_collection_url.rstrip("/")
        self._executor = ParallelExecutor(
            max_workers=_MANIFEST_MAX_WORKERS,
            log_progress_interval=_MANIFEST_LOG_INTERVAL,
        )

    def parse(
        self,
        files: list[Path],
        component_names: list[str],
        filter_mode: str,
    ) -> tuple[list[Component], list[str]]:
        """
        Разбирает список файлов манифестов в многопоточном режиме.

        Файлы обрабатываются параллельно через ``ParallelExecutor``.
        Порядок компонентов в результате не гарантирован —
        ``FinalizeStep`` сортирует их по имени.

        Returns:
            (components, warnings) — список компонентов и список предупреждений.
        """
        file_results = self._executor.execute(
            lambda filepath: self._parse_single_file(
                filepath, component_names, filter_mode
            ),
            files,
            task_label="манифестов",
        )

        components: list[Component] = []
        warnings: list[str] = []
        parsed_count = 0
        excluded_count = 0

        for result in file_results:
            if result is None:
                continue
            warnings.extend(result.warnings)
            if result.is_excluded:
                excluded_count += 1
            elif result.component is not None:
                components.append(result.component)
                parsed_count += 1

        logger.info(
            f"обработано {parsed_count} компонентов, "
            f"отфильтровано (режим '{filter_mode}'): {excluded_count}"
        )
        return components, warnings

    def _parse_single_file(
        self,
        filepath: Path,
        component_names: list[str],
        filter_mode: str,
    ) -> _FileParseResult:
        """
        Разбирает один .properties-файл.

        Обрабатывает ошибки чтения и валидации внутри метода, чтобы
        одна неудача не прерывала обработку остальных файлов.

        Args:
            filepath: Путь к .properties-файлу.
            component_names: Список имён компонентов для фильтрации.
            filter_mode: Режим фильтрации («exclude» или «include»).

        Returns:
            ``_FileParseResult`` с компонентом, предупреждениями или флагом исключения.
        """
        if not filepath.is_file():
            msg = f"файл не найден или недоступен: {filepath.name}"
            logger.warning(msg)
            return _FileParseResult(warnings=[msg])

        try:
            props = read_properties(filepath)
        except OSError as e:
            msg = f"не удалось прочитать {filepath.name}: {e}"
            logger.warning(msg)
            return _FileParseResult(warnings=[msg])

        name = props.get("name", "")
        if not name:
            logger.debug(f'Пропуск {filepath.name} — отсутствует поле "name"')
            return _FileParseResult()

        if filter_mode == "exclude":
            if name in component_names:
                logger.debug(f"Компонент {name} исключён (режим exclude)")
                return _FileParseResult(is_excluded=True)
        elif filter_mode == "include":
            if component_names and name not in component_names:
                logger.debug(
                    f"Компонент {name} пропущен — не в белом списке (режим include)"
                )
                return _FileParseResult(is_excluded=True)

        releases = self._build_releases(props)
        if not releases:
            return _FileParseResult()

        component = Component(
            name=name,
            description=props.get("description", ""),
            git_project=props.get("tfs_git_project", ""),
            git_repo=props.get("git_repo_name", ""),
            releases=releases,
        )
        return _FileParseResult(component=component)

    def _build_releases(self, props: dict[str, str]) -> list[Release]:
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
                git_repo_part = f"{git_project}/_git/{git_repo}" if git_repo else ""
                if self._tfs_collection_url and git_project and git_repo:
                    full_git_url = (
                        f"{self._tfs_collection_url}/{git_project}/_git/{git_repo}"
                        f"?path=%2F&version=GBrelease_{c_ver}"
                    )
                elif git_repo_part:
                    full_git_url = git_repo_part
                else:
                    full_git_url = ""
                releases.append(
                    Release(
                        version=c_ver,
                        platform=target_platform,
                        channel=channel,
                        git_url=full_git_url,
                        profile_builds=[
                            ProfileBuild(profile_name=prof) for prof in profile_list
                        ],
                    )
                )

        return releases

    def _get_profiles_string(
        self, props: dict[str, str], c_ver: str, p_ver: str
    ) -> str:
        """Извлекает строку со списком профилей для заданной комбинации версий."""
        key_profiles = f"profiles-{c_ver}-{p_ver}"
        return props.get(key_profiles, "")
