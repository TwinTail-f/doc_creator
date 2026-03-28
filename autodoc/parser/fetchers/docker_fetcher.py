"""
Фетчер Docker-образов: извлекает ссылки из YAML-файлов профилей сборки.
"""
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
import yaml

from autodoc.infrastructure.logger import logger
from autodoc.parser.steps.base import BaseTFSFetcher, FetchResult, PipelineContext

# Тип: имя_профиля → docker_image_url
DockerLinksMap = dict[str, str]


class DockerFetcher(BaseTFSFetcher[DockerLinksMap]):
    """
    Извлекает Docker-образы из YAML-файлов профилей сборки.

    Двухфазовый: сначала configure(ctx), потом fetch(urls, target_platform).
    """

    def configure(self, ctx: PipelineContext) -> None:
        """Сохраняет нужные данные из ctx.config."""
        from autodoc.parser.tfs_client import TFSClient
        self._tfs = TFSClient.get_instance()
        self._profiles_urls = ctx.config.profiles_urls or []
        self._platform_version = ctx.config.platform_version
        self._configured = True

    def fetch(self, urls: list[str], target_platform: str) -> 'FetchResult[DockerLinksMap]':
        """Типизированная точка входа — делегирует в _guarded_fetch."""
        return self._guarded_fetch(urls=urls, target_platform=target_platform)

    def _do_fetch(self, urls: list[str], target_platform: str) -> 'FetchResult[DockerLinksMap]':
        """
        Парсит YAML-файлы профилей по переданным URL и собирает маппинг имён профилей
        на Docker-образы.
        """
        docker_links: DockerLinksMap = {}

        for url in urls:
            parsed = urlparse(url)
            if '/_git/' not in parsed.path:
                logger.debug('пропуск URL без /_git/: %s', url)
                continue

            base_path, repo = parsed.path.split('/_git/', 1)
            base_api_url = '%s://%s%s' % (parsed.scheme, parsed.netloc, base_path)

            query = parse_qs(parsed.query)
            yaml_path = query.get('path', [''])[0]
            branch_raw = query.get('version', [''])[0]
            branch = (
                branch_raw[2:] if branch_raw.startswith('GB')
                else (branch_raw or target_platform)
            )

            items_url = '%s/_apis/git/repositories/%s/items' % (base_api_url, repo)

            try:
                res = self._tfs.get_file_content(items_url, yaml_path, branch)
                if res.status_code != requests.codes.ok:
                    logger.warning(
                        'файл недоступен (HTTP %d) — %s', res.status_code, url
                    )
                    continue
                content = yaml.safe_load(res.text) or {}
            except (requests.exceptions.RequestException, yaml.YAMLError) as e:
                logger.warning('ошибка получения/парсинга %s: %s', url, e)
                continue

            self._extract_from_yaml(content, docker_links)

        return FetchResult(value=docker_links)

    # ------------------------------------------------------------------
    # Приватные методы
    # ------------------------------------------------------------------

    def _extract_from_yaml(self, content: dict, docker_links: DockerLinksMap) -> None:
        """Обходит раздел archs: YAML-профиля и заполняет маппинг docker_links."""
        archs = content.get('archs', {})
        for key, val in archs.items():
            if key == 'common' or not isinstance(val, dict):
                continue

            docker_img = self._extract_docker_image(val)
            if not docker_img:
                continue

            self._add_aliases(key, docker_img, docker_links)

            prof_host = val.get('profile_host')
            if isinstance(prof_host, str):
                self._add_aliases(prof_host, docker_img, docker_links)
            elif isinstance(prof_host, list):
                for ph in prof_host:
                    self._add_aliases(ph, docker_img, docker_links)

    @staticmethod
    def _extract_docker_image(arch_val: dict) -> str:
        """Извлекает URL Docker-образа из словаря значений одной архитектуры."""
        docker_val = arch_val.get('docker')
        if isinstance(docker_val, str):
            return docker_val
        if isinstance(docker_val, dict):
            return docker_val.get('image', '')
        return ''

    @staticmethod
    def _add_aliases(name: str, docker_img: str, docker_links: DockerLinksMap) -> None:
        """Добавляет имя профиля и все его псевдонимы в маппинг Docker-образов."""
        if not name:
            return
        path_obj = Path(name)
        docker_links[name] = docker_img
        docker_links[path_obj.name] = docker_img
        docker_links[path_obj.stem] = docker_img
        if path_obj.parent != Path('.'):
            docker_links['%s/%s' % (path_obj.parent, path_obj.stem)] = docker_img
