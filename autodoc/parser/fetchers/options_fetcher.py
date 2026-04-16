"""
Фетчер опций Conan: скачивает options.json из репозиториев компонентов.
Разбор JSON делегируется OptionsParser.
"""

import requests
from autodoc.exceptions import NetworkError
from autodoc.infrastructure.logger import logger
from autodoc.infrastructure.parallel_executor import ParallelExecutor
from autodoc.models.component import Component
from autodoc.parser.parsers.options_parser import OptionsParser
from autodoc.parser.fetchers.base import BaseTFSFetcher, FetchResult
from autodoc.parser.pipeline.context import PipelineContext

OptionsMap = dict[tuple[str, str, str], dict[str, str]]

_OPTIONS_MAX_WORKERS: int = 32
_OPTIONS_LOG_INTERVAL: int = 50


class OptionsFetcher(BaseTFSFetcher[OptionsMap]):
    """
    Скачивает options.json из TFS и делегирует разбор OptionsParser.

    Двухфазовый: сначала ``configure(ctx)``, потом ``fetch(components)``.
    Уникальные комбинации репозиторий/ветка скачиваются параллельно через
    ``ParallelExecutor``; итоговый маппинг собирается в один проход после
    завершения всех задач.
    Не мутирует входные модели — возвращает OptionsMap.
    """

    def __init__(self) -> None:
        """Initialises the fetcher; call ``configure(ctx)`` before ``fetch()``."""
        super().__init__()
        self._base_url: str = ""
        self._executor = ParallelExecutor(
            max_workers=_OPTIONS_MAX_WORKERS,
            log_progress_interval=_OPTIONS_LOG_INTERVAL,
        )

    def configure(self, ctx: PipelineContext) -> None:
        """
        Инициализирует фетчер из контекста пайплайна.

        Получает ``TFSClient`` из контекста и сохраняет базовый URL.

        Args:
            ctx: Контекст пайплайна с заполненной конфигурацией и клиентами.
        """
        self._tfs = ctx.tfs_client
        self._base_url = ctx.config.tfs_dep_components_url.rstrip("/")

    def fetch(self, components: list[Component]) -> FetchResult[OptionsMap]:
        """
        Собирает опции Conan для всех релизов компонентов.

        Уникальные пары ``(repo_name, branch)`` определяются за один проход,
        затем скачиваются параллельно через ``ParallelExecutor``. Итоговый
        маппинг строится последовательно из заполненного кэша — без повторных
        сетевых запросов.

        Args:
            components: Список компонентов для обогащения.

        Returns:
            ``FetchResult`` с маппингом ``(comp_name, version, channel) → options``.
        """
        logger.info("Начинаем сбор options.json…")

        fetch_warnings: list[str] = []

        # Collect unique (repo_name, branch) pairs in encounter order,
        # keyed by cache_key so the parallel results can be zipped back.
        unique_keys: list[str] = []
        unique_pairs: list[tuple[str, str]] = []
        seen: set[str] = set()

        for comp in components:
            repo_name = comp.git_repo
            if not repo_name:
                fetch_warnings.append(f"{comp.name} без git_repo, пропуск")
                continue
            for release in comp.releases:
                branch = f"release_{release.version}"
                cache_key = f"{repo_name}_{branch}"
                if cache_key not in seen:
                    seen.add(cache_key)
                    unique_keys.append(cache_key)
                    unique_pairs.append((repo_name, branch))

        # Fetch all unique repo/branch combinations in parallel.
        raw_results = self._executor.execute(
            lambda pair: self._fetch_options_for_repo(pair[0], pair[1]),
            unique_pairs,
            task_label="репозиториев",
        )

        _empty: dict = {"global": {}, "channels": {}}
        options_cache: dict[str, dict] = {
            key: (repo_data if repo_data is not None else _empty)
            for key, repo_data in zip(unique_keys, raw_results)
        }

        # Build the result map using the populated cache — no more network calls.
        result: OptionsMap = {}
        for comp in components:
            if not comp.git_repo:
                continue
            for release in comp.releases:
                branch = f"release_{release.version}"
                cache_key = f"{comp.git_repo}_{branch}"
                chosen = OptionsParser.pick_options(
                    options_cache[cache_key], release.channel
                )
                result[(comp.name, release.version, release.channel)] = chosen

        logger.info(f"Завершён. Собрано опций для {len(result)} релизов.")
        return FetchResult(value=result, warnings=fetch_warnings)

    def _fetch_options_for_repo(self, repo_name: str, branch: str) -> dict:
        """
        Скачивает все options.json для репозитория и возвращает структуру данных.

        Args:
            repo_name: Имя git-репозитория компонента.
            branch: Ветка, соответствующая версии релиза.

        Returns:
            Словарь с ключами ``'global'`` и ``'channels'``.
        """
        repo_data: dict = {"global": {}, "channels": {}}
        items_url = f"{self._base_url}/_apis/git/repositories/{repo_name}/items"

        try:
            items = self._tfs.get_items(items_url, branch)
        except NetworkError as e:
            logger.warning(f"Пропуск репо {repo_name} (ветка {branch}): {e}")
            return repo_data

        options_paths = [
            item["path"]
            for item in items
            if not item.get("isFolder")
            and item["path"].endswith("options.json")
            and "/conan/" in item["path"]
        ]

        target_ci = OptionsParser.select_ci_prefix(options_paths)
        if not target_ci:
            return repo_data

        for opt_path in options_paths:
            if target_ci not in opt_path:
                continue
            self._load_single_options_file(
                items_url, opt_path, branch, target_ci, repo_data
            )

        return repo_data

    def _load_single_options_file(
        self,
        items_url: str,
        opt_path: str,
        branch: str,
        ci_prefix: str,
        repo_data: dict,
    ) -> None:
        """
        Скачивает один options.json и сохраняет разобранный результат в repo_data.

        Args:
            items_url: API URL для items репозитория.
            opt_path: Путь к файлу options.json в репозитории.
            branch: Ветка для скачивания.
            ci_prefix: Префикс CI-директории (например ``'/ci-2.0/'``).
            repo_data: Изменяемый словарь для накопления результатов.
        """
        try:
            response = self._tfs.get_file_content(items_url, opt_path, branch)
        except NetworkError as e:
            logger.warning(f"Ошибка скачивания {opt_path}: {e}")
            return

        if response.status_code != requests.codes.ok:
            logger.debug(f"HTTP {response.status_code} для {opt_path}, пропуск")
            return

        channel_name, cleaned = OptionsParser.parse_file(
            response.text, opt_path, ci_prefix
        )
        if not cleaned:
            return

        if channel_name:
            repo_data["channels"][channel_name] = cleaned
        else:
            repo_data["global"] = cleaned