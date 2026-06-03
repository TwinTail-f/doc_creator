"""
Фетчер опций Conan: скачивает options.json из репозиториев компонентов.
Разбор JSON делегируется OptionsParser.
"""

from typing import Any

import requests

from autodoc.exceptions import NetworkError
from autodoc.common.logger import logger
from autodoc.common.parallel_executor import ParallelExecutor
from autodoc.models.component import Component
from autodoc.models.types import OptionsMap
from autodoc.parser.parsers.options_parser import OptionsParser
from autodoc.parser.fetchers.base_tfs_fetcher import BaseTFSFetcher
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.pipeline.context import PipelineContext

_OPTIONS_MAX_WORKERS: int = 64
_OPTIONS_LOG_INTERVAL: int = 50
_RELEASE_BRANCH_PREFIX: str = "release_"


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
        """Инициализирует фетчер; перед вызовом ``fetch()`` необходимо вызвать ``configure(ctx)``."""
        super().__init__()
        self._base_url: str = ""
        self._branch_overrides: dict[str, str] = {}
        self._executor = ParallelExecutor(
            max_workers=_OPTIONS_MAX_WORKERS,
            log_progress_interval=_OPTIONS_LOG_INTERVAL,
        )

    def _configure(self, ctx: PipelineContext) -> None:
        """
        Инициализирует фетчер из контекста пайплайна.

        Получает ``TFSClient`` из контекста, сохраняет базовый URL
        и словарь переопределений веток для специфичных компонентов.

        Args:
            ctx: Контекст пайплайна с заполненной конфигурацией и клиентами.
        """
        self._tfs = ctx.tfs_client
        self._base_url = ctx.config.tfs_collection_url
        self._branch_overrides = ctx.config.component_branch_overrides

    def _get_branch(self, comp_name: str, version: str) -> str:
        """
        Возвращает имя ветки TFS для заданного компонента и версии.

        Если компонент присутствует в ``_branch_overrides``, подставляет версию
        в шаблон из конфига. Иначе использует универсальный шаблон
        ``release_{version}``.

        Args:
            comp_name: Имя компонента (ключ в словаре переопределений).
            version: Строка версии релиза (например ``"3.34.1"``).

        Returns:
            Имя ветки TFS (например ``"release_3.34.1"`` или
            ``"release_3.34.1_ext"``).
        """
        template = self._branch_overrides.get(comp_name)
        if template:
            return template.format(version=version)
        return f"{_RELEASE_BRANCH_PREFIX}{version}"

    def _fetch(self, components: list[Component]) -> FetchResult[OptionsMap]:
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

        warnings: list[str] = []

        # Собираем уникальные пары (repo_name, branch) в порядке появления;
        # ключ cache_key нужен для сопоставления с параллельными результатами.
        unique_keys: list[str] = []
        unique_repo_branches: list[tuple[str, str, str]] = []
        seen: set[str] = set()

        for comp in components:
            repo_name = comp.git_repo
            git_project = comp.git_project
            if not repo_name:
                warnings.append(f"{comp.name} без git_repo, пропуск")
                continue
            for release in comp.releases:
                branch = self._get_branch(comp.name, release.version)
                cache_key = f"{git_project}_{repo_name}_{branch}"
                if cache_key not in seen:
                    seen.add(cache_key)
                    unique_keys.append(cache_key)
                    unique_repo_branches.append((git_project, repo_name, branch))

        # Скачиваем все уникальные комбинации repo/branch параллельно.
        raw_results = self._executor.execute(
            lambda triple: self._fetch_options_for_repo(*triple),
            unique_repo_branches,
            task_label="репозиториев",
        )

        options_cache: dict[str, dict[str, Any]] = {
            key: repo_data for key, repo_data in zip(unique_keys, raw_results)
        }

        # Строим карту результатов из заполненного кэша — без повторных сетевых запросов.
        result: OptionsMap = {}
        for comp in components:
            if not comp.git_repo:
                continue
            for release in comp.releases:
                branch = self._get_branch(comp.name, release.version)
                cache_key = f"{comp.git_project}_{comp.git_repo}_{branch}"
                chosen = OptionsParser.pick_options(
                    options_cache[cache_key], release.channel
                )
                result[(comp.name, release.version, release.channel)] = chosen

        logger.info(f"Завершён. Собрано опций для {len(result)} релизов.")
        return FetchResult(value=result, warnings=warnings)

    def _fetch_options_for_repo(
        self, git_project: str, repo_name: str, branch: str
    ) -> dict[str, Any]:
        """
        Скачивает все options.json для репозитория и возвращает структуру данных.

        Args:
            git_project: Имя проекта TFS/Git (например DEP_Components или PRG_Quant).
            repo_name: Имя git-репозитория компонента.
            branch: Ветка, соответствующая версии релиза.

        Returns:
            Словарь с ключами ``'global'`` и ``'channels'``.
        """
        repo_data: dict[str, Any] = {"global": {}, "channels": {}}
        items_url = (
            f"{self._base_url}/{git_project}/_apis/git/repositories/{repo_name}/items"
        )

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
        repo_data: dict[str, Any],
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
