"""
Парсер манифестов компонентов: разбор .properties-файлов в доменные модели.
Не имеет доступа к TFS и не выполняет сетевых вызовов.
"""

from dataclasses import dataclass, field
from pathlib import Path

from autodoc.infrastructure.logger import logger
from autodoc.infrastructure.parallel_executor import ParallelExecutor
from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.utils.properties_reader import read_properties

_MANIFEST_MAX_WORKERS: int = 32
_MANIFEST_LOG_INTERVAL: int = 50
_PLATFORM_BASE_VERSION: str = "2.0" #временный хардкод для фильтрации релизов по платформе, будет убран с добавлением функционала для парсинга 1.6 и иных


@dataclass
class _FileParseResult:
    """Результат разбора одного .properties-файла. Используется только внутри ManifestParser."""

    component: Component | None = None
    warnings: list[str] = field(default_factory=list)
    is_excluded: bool = False


class ManifestParser:
    """Преобразует список .properties-файлов в список Component."""

    def __init__(self, target_platform: str, tfs_dep_components_url: str = "") -> None:
        """
        Инициализирует парсер для указанной целевой платформы.

        Args:
            target_platform: Версия платформы (например '2.0'), используется
                             для фильтрации релизов манифестов.
            tfs_dep_components_url: Базовый URL проекта DEP_Components в TFS
                                    (например ``https://tfs.company.com/tfs/...``)
                                    без завершающего слэша.
                                    Если передан — формирует полные ссылки на
                                    репозиторий в поле ``git_url`` каждого Release.
        """
        self._target_platform = _PLATFORM_BASE_VERSION
        self._tfs_dep_components_url: str = tfs_dep_components_url.rstrip("/")
        self._executor = ParallelExecutor(
            max_workers=_MANIFEST_MAX_WORKERS,
            log_progress_interval=_MANIFEST_LOG_INTERVAL,
        )

    def parse(
        self,
        files: list[Path],
        excluded: list[str],
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
            lambda filepath: self._parse_single_file(filepath, excluded),
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
            f"обработано {parsed_count} компонентов, исключено {excluded_count}"
        )
        return components, warnings

    def _parse_single_file(
        self,
        filepath: Path,
        excluded: list[str],
    ) -> _FileParseResult:
        """
        Разбирает один .properties-файл.

        Обрабатывает ошибки чтения и валидации внутри метода, чтобы
        одна неудача не прерывала обработку остальных файлов.

        Args:
            filepath: Путь к .properties-файлу.
            excluded: Список имён компонентов, которые нужно исключить.

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

        if name in excluded:
            logger.debug(f"Компонент {name} исключён")
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
                if self._tfs_dep_components_url and git_repo:
                    full_git_url = (
                        f"{self._tfs_dep_components_url}/_git/{git_repo}"
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

    def _get_profiles_string(self, props: dict[str, str], c_ver: str, p_ver: str) -> str:
        """Извлекает строку со списком профилей для заданной комбинации версий."""
        key_profiles = f"profiles-{c_ver}-{p_ver}"
        return props.get(key_profiles, "")
