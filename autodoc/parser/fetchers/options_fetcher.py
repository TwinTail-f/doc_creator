"""
Фетчер опций Conan: скачивает options.json из репозиториев компонентов.
Разбор JSON делегируется OptionsParser.
"""
from autodoc.exceptions import NetworkError
from autodoc.infrastructure.logger import logger
from autodoc.models.component import Component
from autodoc.parser.parsers.options_parser import OptionsParser
from autodoc.parser.fetchers.base import BaseTFSFetcher, FetchResult
from autodoc.parser.steps.base import PipelineContext
from autodoc.parser.clients.tfs_client import TFSClient

OptionsMap = dict[tuple[str, str, str], dict[str, str]]


class OptionsFetcher(BaseTFSFetcher[OptionsMap]):
    """
    Скачивает options.json из TFS и делегирует разбор OptionsParser.

    Двухфазовый: сначала ``configure(ctx)``, потом ``fetch(components)``.
    Не мутирует входные модели — возвращает OptionsMap.
    """

    def configure(self, ctx: PipelineContext) -> None:
        """
        Инициализирует фетчер из контекста пайплайна.

        Получает синглтон ``TFSClient`` и сохраняет базовый URL.

        Args:
            ctx: Контекст пайплайна с заполненной конфигурацией.
        """
        self._tfs = TFSClient(ctx.config)
        self._base_url = ctx.config.tfs_dep_components_url.rstrip("/")

    def fetch(self, components: list[Component]) -> FetchResult[OptionsMap]:
        """
        Собирает опции Conan для всех релизов компонентов.

        Args:
            components: Список компонентов для обогащения.

        Returns:
            ``FetchResult`` с маппингом ``(comp_name, version, channel) → options``.
        """
        logger.info("OptionsFetcher: начинаем сбор options.json…")

        options_cache: dict[str, dict] = {}
        result: OptionsMap = {}
        fetch_warnings: list[str] = []

        for comp in components:
            repo_name = comp.git_repo
            if not repo_name:
                fetch_warnings.append("\"%s\" без git_repo, пропуск" % comp.name)
                continue

            for release in comp.releases:
                branch = "release_%s" % release.version
                cache_key = "%s_%s" % (repo_name, branch)

                if cache_key not in options_cache:
                    options_cache[cache_key] = self._fetch_options_for_repo(repo_name, branch)

                chosen = OptionsParser.pick_options(options_cache[cache_key], release.channel)
                result[(comp.name, release.version, release.channel)] = chosen

        logger.info("OptionsFetcher: завершён. Собрано опций для %d релизов.", len(result))
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
        items_url = "%s/_apis/git/repositories/%s/items" % (self._base_url, repo_name)

        try:
            items = self._tfs.get_items(items_url, branch)
        except NetworkError as e:
            logger.warning(
                "OptionsFetcher: пропуск репо \"%s\" (ветка \"%s\"): %s", repo_name, branch, e
            )
            return repo_data

        options_paths = [
            item["path"] for item in items
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
            if response.status_code != 200:
                return
        except (NetworkError, OSError) as e:
            logger.warning("OptionsFetcher: ошибка скачивания %s: %s", opt_path, e)
            return

        channel_name, cleaned = OptionsParser.parse_file(response.text, opt_path, ci_prefix)
        if not cleaned:
            return

        if channel_name:
            repo_data["channels"][channel_name] = cleaned
        else:
            repo_data["global"] = cleaned
