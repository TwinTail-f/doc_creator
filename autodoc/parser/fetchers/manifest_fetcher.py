"""
Парсер манифестов компонентов: скачивание из TFS и сборка доменных моделей.
"""
from pathlib import Path
from typing import List

from autodoc.config.schemas import ParserConfigSchema
from autodoc.exceptions import NetworkError, ParsingError
from autodoc.infrastructure.logger import logger
from autodoc.infrastructure.tfs_client import TFSClient
from autodoc.models.component import Component, ProfileBuild, Release, SvaceReport
from autodoc.parser.fetchers.properties_reader import read_properties

_MANIFESTS_REPO = 'platform'


class ManifestParser:
    """
    Скачивает манифесты компонентов из TFS и парсит их в доменные модели.

    Принимает конфиг, сам создаёт ``TFSClient`` — наружу клиент не передаётся.
    """

    def __init__(self, config: ParserConfigSchema) -> None:
        """
        Args:
            config: Конфигурация парсера. ``TFSClient`` создаётся внутри из config.
        """
        self._config = config
        self._tfs = TFSClient.from_config(config)

    def fetch(self, tmp_dir: Path, excluded: List[str]) -> List[Component]:
        """
        Скачивает ``.properties``-файлы из TFS и парсит их в список ``Component``.

        Args:
            tmp_dir: Локальная директория для скачанных файлов.
            excluded: Имена компонентов, которые нужно пропустить.

        Returns:
            Список типизированных моделей ``Component``.

        Raises:
            NetworkError: Если скачивание завершилось с ошибкой.
            ParsingError: Если в директории не найдено ни одного ``.properties``-файла.
        """
        tmp_dir.mkdir(parents=True, exist_ok=True)

        base_url = self._config.tfs_dep_components_url.rstrip('/')
        items_url = '%s/_apis/git/repositories/%s/items' % (base_url, _MANIFESTS_REPO)

        self._tfs.download_properties(
            items_url=items_url,
            remote_path=self._config.manifests_remotes_path,
            branch=self._config.platform_branch_name,
            output_dir=str(tmp_dir),
        )

        properties_files = list(tmp_dir.glob('*.properties'))
        if not properties_files:
            raise ParsingError(
                'ManifestParser: в директории %s не найдено .properties-файлов '
                'после скачивания из TFS.' % tmp_dir
            )

        return self._parse_files(properties_files, excluded)

    # ------------------------------------------------------------------
    # Приватные методы
    # ------------------------------------------------------------------

    def _parse_files(self, files: List[Path], excluded: List[str]) -> List[Component]:
        """
        Парсит список ``.properties``-файлов манифестов в модели ``Component``.

        Пропускает файлы, в которых отсутствует поле ``name``, а также
        компоненты, чьё имя входит в список ``excluded``.

        Args:
            files: Список путей к ``.properties``-файлам.
            excluded: Имена компонентов, которые следует пропустить.

        Returns:
            Список типизированных моделей ``Component``.
        """
        target_platform = self._config.platform_version
        components: List[Component] = []
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

            # 1.3 git_project/git_repo берём из манифеста — записываем только в Component
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

    def _build_releases(self, props: dict, target_platform: str) -> List[Release]:
        """
        Строит список ``Release`` из словаря свойств манифеста.

        Фильтрует версии платформы, не относящиеся к ``target_platform``.
        Для каждой подходящей пары (компонент, платформа) создаёт ``Release``
        с набором ``ProfileBuild``.

        Args:
            props: Словарь свойств, прочитанный из ``.properties``-файла.
            target_platform: Целевая версия платформы (например ``2.0``).

        Returns:
            Список объектов ``Release``. Может быть пустым, если ни одна версия
            не соответствует целевой платформе.
        """
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
        releases: List[Release] = []

        for p_ver in plat_versions:
            if not (p_ver.startswith('%s-' % target_platform) or p_ver == target_platform):
                continue

            for c_ver in comp_versions:
                profiles_str = self._get_profiles_string(props, c_ver, p_ver)
                if not profiles_str:
                    continue

                channel = p_ver.split('-')[1] if '-' in p_ver else ''
                profile_list = [p.strip() for p in profiles_str.split(',') if p.strip()]
                svace_profile = props.get('svace-profiles-%s-%s' % (c_ver, target_platform), '')

                releases.append(Release(
                    version=c_ver,
                    platform=target_platform,
                    channel=channel,
                    git_url='%s/_git/%s' % (git_project, git_repo) if git_repo else '',
                    # 1.3 git_project/git_repo не пишем в Release — они на уровне Component
                    svace_report=SvaceReport(profile=svace_profile),
                    profile_builds=[
                        ProfileBuild(profile_name=prof)
                        for prof in profile_list
                    ],
                ))

        return releases

    @staticmethod
    def _get_profiles_string(props: dict, c_ver: str, p_ver: str) -> str:
        """
        Извлекает строку со списком профилей сборки для заданной комбинации версий.

        Сначала ищет ключ ``integration-profiles-develop-{c_ver}-{p_ver}``,
        затем — ``profiles-{c_ver}-{p_ver}``.

        Args:
            props: Словарь свойств манифеста.
            c_ver: Версия компонента.
            p_ver: Версия платформы (включая канал, например ``2.0-stable``).

        Returns:
            Строка с именами профилей через запятую или пустая строка.
        """
        key_develop = 'integration-profiles-develop-%s-%s' % (c_ver, p_ver)
        key_profiles = 'profiles-%s-%s' % (c_ver, p_ver)
        return props.get(key_develop, props.get(key_profiles, ''))
