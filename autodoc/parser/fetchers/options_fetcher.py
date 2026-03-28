"""
Фетчер опций Conan: скачивает options.json из репозиториев компонентов.
"""
import json

from autodoc.exceptions import NetworkError
from autodoc.infrastructure.logger import logger
from autodoc.models.component import Component
from autodoc.parser.steps.base import BaseTFSFetcher, FetchResult, PipelineContext

# Тип: (имя_компонента, версия, канал) → {id_набора: строка_опций}
OptionsMap = dict[tuple[str, str, str], dict[str, str]]

_CI_PRIORITY = ('/ci-2.0/', '/ci-1.6/')


class OptionsFetcher(BaseTFSFetcher[OptionsMap]):
    """
    Скачивает ``options.json`` из репозиториев компонентов и возвращает маппинг опций.

    Двухфазовый: сначала configure(ctx), потом fetch(components).
    **Не мутирует** входные модели — возвращает ``OptionsMap``.
    """

    def configure(self, ctx: PipelineContext) -> None:
        """Сохраняет base_url из ctx.config."""
        from autodoc.parser.tfs_client import TFSClient
        self._tfs = TFSClient.get_instance()
        self._base_url = ctx.config.tfs_dep_components_url.rstrip('/')
        self._configured = True

    def fetch(self, components: list[Component]) -> FetchResult[OptionsMap]:
        """Типизированная точка входа — делегирует в _guarded_fetch."""
        return self._guarded_fetch(components)

    def _do_fetch(self, components: list[Component]) -> FetchResult[OptionsMap]:
        """
        Собирает опции Conan для всех релизов компонентов.

        Args:
            components: Список компонентов для обработки.

        Returns:
            FetchResult с маппингом ``(comp_name, version, channel) → {id: option_string}``.
        """
        logger.info('начинаем сбор options.json…')

        options_cache: dict[str, dict] = {}
        result: OptionsMap = {}
        fetch_warnings: list[str] = []

        for comp in components:
            repo_name = comp.git_repo
            if not repo_name:
                fetch_warnings.append('"%s" без git_repo, пропуск' % comp.name)
                continue

            for release in comp.releases:
                branch = 'release_%s' % release.version
                cache_key = '%s_%s' % (repo_name, branch)

                if cache_key not in options_cache:
                    options_cache[cache_key] = self._fetch_options_for_repo(repo_name, branch)

                chosen = self._pick_options(options_cache[cache_key], release.channel)
                result[(comp.name, release.version, release.channel)] = chosen

        logger.info('завершён. Собрано опций для %d релизов.', len(result))
        return FetchResult(value=result, warnings=fetch_warnings)

    # ------------------------------------------------------------------
    # Приватные методы
    # ------------------------------------------------------------------

    def _fetch_options_for_repo(self, repo_name: str, branch: str) -> dict:
        repo_data: dict = {'global': {}, 'channels': {}}
        items_url = '%s/_apis/git/repositories/%s/items' % (self._base_url, repo_name)

        try:
            items = self._tfs.get_items(items_url, branch)
        except NetworkError as e:
            logger.warning('пропуск репо "%s" (ветка "%s"): %s', repo_name, branch, e)
            return repo_data

        options_paths = [
            item['path'] for item in items
            if not item.get('isFolder')
            and item['path'].endswith('options.json')
            and '/conan/' in item['path']
        ]

        target_ci = self._select_ci_prefix(options_paths)
        if not target_ci:
            return repo_data

        for opt_path in options_paths:
            if target_ci not in opt_path:
                continue
            self._load_single_options_file(items_url, opt_path, branch, target_ci, repo_data)

        return repo_data

    def _load_single_options_file(
        self,
        items_url: str,
        opt_path: str,
        branch: str,
        ci_prefix: str,
        repo_data: dict,
    ) -> None:
        try:
            response = self._tfs.get_file_content(items_url, opt_path, branch)
            if response.status_code != 200:
                return
            parsed: dict = json.loads(response.text)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning('ошибка чтения %s: %s', opt_path, e)
            return

        cleaned: dict[str, str] = {
            str(k): (v.strip() if isinstance(v, str) else '')
            for k, v in parsed.items()
            if isinstance(v, (str, type(None)))
        }

        tail = opt_path.split(ci_prefix)[1]
        parts = tail.split('/')
        channel_name = parts[0] if len(parts) > 1 else None

        if channel_name:
            repo_data['channels'][channel_name] = cleaned
        else:
            repo_data['global'] = cleaned

    @staticmethod
    def _select_ci_prefix(options_paths: list[str]) -> str:
        for prefix in _CI_PRIORITY:
            if any(prefix in p for p in options_paths):
                return prefix
        return ''

    @staticmethod
    def _pick_options(repo_data: dict, channel: str) -> dict[str, str]:
        channels = repo_data.get('channels', {})
        if channel and channel in channels:
            return channels[channel]
        global_opts = repo_data.get('global', {})
        if global_opts:
            return global_opts
        return {'1': ''}

