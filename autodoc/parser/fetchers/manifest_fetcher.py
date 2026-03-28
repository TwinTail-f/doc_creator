"""
Фетчер манифестов компонентов: скачивание из TFS и сборка доменных моделей.
"""
from pathlib import Path

from autodoc.exceptions import NetworkError, ParsingError
from autodoc.infrastructure.logger import logger
from autodoc.models.component import Component, ProfileBuild, Release
from autodoc.parser.fetchers.properties_reader import read_properties
from autodoc.parser.steps.base import BaseTFSFetcher, FetchResult, PipelineContext

_MANIFESTS_REPO = 'platform'


class ManifestFetcher(BaseTFSFetcher[list[Component]]):
    """
    Скачивает манифесты компонентов из TFS и парсит их в доменные модели.

    Двухфазовый: сначала configure(ctx), потом fetch(tmp_dir, excluded).
    """

    def configure(self, ctx: PipelineContext) -> None:
        """Сохраняет нужные данные из ctx.config."""
        from autodoc.parser.tfs_client import TFSClient
        self._tfs = TFSClient.get_instance()
        self._base_url = ctx.config.tfs_dep_components_url.rstrip('/')
        self._manifests_remotes_path = ctx.config.manifests_remotes_path
        self._platform_branch_name = ctx.config.platform_branch_name
        self._platform_version = ctx.config.platform_version
        self._configured = True

    def fetch(self, tmp_dir: Path, excluded: list[str]) -> FetchResult[list[Component]]:
        """Типизированная точка входа — делегирует в _guarded_fetch."""
        return self._guarded_fetch(tmp_dir=tmp_dir, excluded=excluded)

    def _do_fetch(self, tmp_dir: Path, excluded: list[str]) -> FetchResult[list[Component]]:
        """
        Скачивает ``.properties``-файлы из TFS и парсит их в список ``Component``.

        Args:
            tmp_dir: Локальная директория для скачанных файлов.
            excluded: Имена компонентов, которые нужно пропустить.

        Returns:
            FetchResult со списком Component.

        Raises:
            NetworkError: Если скачивание завершилось с ошибкой.
            ParsingError: Если в директории не найдено ни одного .properties-файла.
        """
        tmp_dir.mkdir(parents=True, exist_ok=True)

        items_url = '%s/_apis/git/repositories/%s/items' % (self._base_url, _MANIFESTS_REPO)

        self._tfs.download_properties(
            items_url=items_url,
            remote_path=self._manifests_remotes_path,
            branch=self._platform_branch_name,
            output_dir=str(tmp_dir),
        )

        properties_files = list(tmp_dir.glob('*.properties'))
        if not properties_files:
            raise ParsingError(
                'ManifestFetcher: в директории %s не найдено .properties-файлов '
                'после скачивания из TFS.' % tmp_dir
            )

        components = self._parse_files(properties_files, excluded)
        return FetchResult(value=components)

    # ------------------------------------------------------------------
    # Приватные методы
    # ------------------------------------------------------------------

    def _parse_files(self, files: list[Path], excluded: list[str]) -> list[Component]:
        """
        Парсит список ``.properties``-файлов манифестов в модели ``Component``.
        """
        target_platform = self._platform_version
        components: list[Component] = []
        parsed_count = 0
        excluded_count = 0

        for filepath in files:
            try:
                props = read_properties(filepath)
            except OSError as e:
                logger.warning('не удалось прочитать %s: %s', filepath.name, e)
                continue

            name = props.get('name', '')
            if not name:
                logger.debug('пропуск %s — отсутствует поле "name"', filepath.name)
                continue

            if name in excluded:
                logger.debug('компонент "%s" исключён', name)
                excluded_count += 1
                continue

            releases = self._build_releases(props, target_platform)
            if not releases:
                continue

            components.append(Component(
                name=name,
                description=props.get('description', ''),
                git_project=props.get('tfs_git_project', ''),
                git_repo=props.get('git_repo_name', ''),
                releases=releases,
            ))
            parsed_count += 1

        logger.info('обработано %d компонентов, исключено %d', parsed_count, excluded_count)
        return components

    def _build_releases(self, props: dict, target_platform: str) -> list[Release]:
        """Строит список ``Release`` из словаря свойств манифеста."""
        comp_versions = [
            v.strip()
            for v in props.get('versions.component', '').split(',')
            if v.strip()
        ]
        plat_versions = [
            v.strip()
            for v in props.get('versions.platform', '').split(',')
            if v.strip()
        ]

        git_project = props.get('tfs_git_project', '')
        git_repo = props.get('git_repo_name', '')
        releases: list[Release] = []

        for p_ver in plat_versions:
            if not (p_ver.startswith('%s-' % target_platform) or p_ver == target_platform):
                continue

            for c_ver in comp_versions:
                profiles_str = self._get_profiles_string(props, c_ver, p_ver)
                if not profiles_str:
                    continue

                channel = p_ver.split('-')[1] if '-' in p_ver else ''
                profile_list = [p.strip() for p in profiles_str.split(',') if p.strip()]

                releases.append(Release(
                    version=c_ver,
                    platform=target_platform,
                    channel=channel,
                    git_url='%s/_git/%s' % (git_project, git_repo) if git_repo else '',
                    profile_builds=[
                        ProfileBuild(profile_name=prof)
                        for prof in profile_list
                    ],
                ))

        return releases

    @staticmethod
    def _get_profiles_string(props: dict, c_ver: str, p_ver: str) -> str:
        """Извлекает строку со списком профилей сборки для заданной комбинации версий."""
        key_develop = 'integration-profiles-develop-%s-%s' % (c_ver, p_ver)
        key_profiles = 'profiles-%s-%s' % (c_ver, p_ver)
        return props.get(key_develop, props.get(key_profiles, ''))

