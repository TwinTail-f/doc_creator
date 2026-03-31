"""
Фетчер Docker-образов: извлекает ссылки из YAML-файлов профилей сборки.
Разбор YAML делегируется DockerParser.
"""
from urllib.parse import parse_qs, urlparse

import requests
import yaml

from autodoc.infrastructure.logger import logger
from autodoc.parser.parsers.docker_parser import DockerLinksMap as DockerLinksMap  # noqa: F401
from autodoc.parser.parsers.docker_parser import DockerParser
from autodoc.parser.fetchers.base import BaseTFSFetcher, FetchResult
from autodoc.parser.steps.base import PipelineContext
from autodoc.parser.clients.tfs_client import TFSClient


class DockerFetcher(BaseTFSFetcher[DockerLinksMap]):
    """
    Скачивает YAML-файлы профилей из TFS и делегирует разбор DockerParser.

    Двухфазовый: сначала ``configure(ctx)``, потом ``fetch(urls, target_platform)``.
    """

    def configure(self, ctx: PipelineContext) -> None:
        """
        Инициализирует фетчер из контекста пайплайна.

        Получает синглтон ``TFSClient`` и сохраняет параметры конфигурации.

        Args:
            ctx: Контекст пайплайна с заполненной конфигурацией.
        """
        self._tfs = TFSClient(ctx.config)
        self._profiles_urls = ctx.config.profiles_urls or []
        self._platform_version = ctx.config.platform_version

    def fetch(self, urls: list[str], target_platform: str) -> 'FetchResult[DockerLinksMap]':
        """
        Скачивает YAML-файлы профилей и собирает маппинг Docker-образов.

        Args:
            urls: Список URL TFS к YAML-файлам профилей.
            target_platform: Целевая платформа (используется как ветка по умолчанию).

        Returns:
            ``FetchResult`` с маппингом ``имя_профиля → docker_image_url``.
        """
        docker_links: DockerLinksMap = {}

        for url in urls:
            parsed = urlparse(url)
            if '/_git/' not in parsed.path:
                logger.debug('DockerFetcher: пропуск URL без /_git/: %s', url)
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
                        'DockerFetcher: файл недоступен (HTTP %d) — %s', res.status_code, url
                    )
                    continue
                content = yaml.safe_load(res.text) or {}
            except (requests.exceptions.RequestException, yaml.YAMLError) as e:
                logger.warning('DockerFetcher: ошибка получения/парсинга %s: %s', url, e)
                continue

            DockerParser.extract_from_yaml(content, docker_links)

        return FetchResult(value=docker_links)
