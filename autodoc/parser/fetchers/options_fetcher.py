"""
Фетчер опций Conan: скачивает options.json из репозиториев компонентов.
"""
import json
from typing import Dict, List, Tuple

from autodoc.config.schemas import ParserConfigSchema
from autodoc.exceptions import NetworkError
from autodoc.infrastructure.logger import logger
from autodoc.infrastructure.tfs_client import TFSClient
from autodoc.models.component import Component

# Тип: (имя_компонента, версия, канал) → {id_набора: строка_опций}
OptionsMap = Dict[Tuple[str, str, str], Dict[str, str]]

_CI_PRIORITY = ('/ci-2.0/', '/ci-1.6/')


class OptionsFetcher:
    """
    Скачивает ``options.json`` из репозиториев компонентов и возвращает маппинг опций.

    Принимает конфиг, сам создаёт ``TFSClient`` — наружу клиент не передаётся.
    **Не мутирует** входные модели — возвращает ``OptionsMap``.
    """

    def __init__(self, config: ParserConfigSchema) -> None:
        """
        Args:
            config: Конфигурация парсера. ``TFSClient`` создаётся внутри из config.
        """
        self._tfs = TFSClient.from_config(config)
        self._base_url = config.tfs_dep_components_url.rstrip('/')

    def fetch(self, components: List[Component]) -> OptionsMap:
        """
        Собирает опции Conan для всех релизов компонентов.

        Для каждого релиза ищет ``options.json`` в ветке ``release_{version}``
        репозитория компонента. Кеширует структуру репозитория.

        Args:
            components: Список компонентов для обработки.

        Returns:
            Словарь ``(comp_name, version, channel) → {id: option_string}``.
            Не мутирует входные объекты.
        """
        logger.info('начинаем сбор options.json…')

        options_cache: Dict[str, Dict] = {}
        result: OptionsMap = {}

        for comp in components:
            # 1.3 git_repo берём из Component, а не из Release
            repo_name = comp.git_repo
            if not repo_name:
                logger.debug('"%s" без git_repo, пропуск', comp.name)
                continue

            for release in comp.releases:
                branch = 'release_%s' % release.version
                cache_key = '%s_%s' % (repo_name, branch)

                if cache_key not in options_cache:
                    options_cache[cache_key] = self._fetch_options_for_repo(repo_name, branch)

                chosen = self._pick_options(options_cache[cache_key], release.channel)
                result[(comp.name, release.version, release.channel)] = chosen

        logger.info('завершён. Собрано опций для %d релизов.', len(result))
        return result

    # ------------------------------------------------------------------
    # Приватные методы
    # ------------------------------------------------------------------

    def _fetch_options_for_repo(self, repo_name: str, branch: str) -> Dict:
        """
        Загружает все файлы ``options.json`` из указанной ветки репозитория.

        Args:
            repo_name: Имя репозитория компонента в TFS.
            branch: Ветка, из которой скачиваются опции (например ``release_1.0.0``).

        Returns:
            Словарь с ключами ``global`` и ``channels``, содержащий найденные опции.
        """
        repo_data: Dict = {'global': {}, 'channels': {}}
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
        repo_data: Dict,
    ) -> None:
        """
        Скачивает один файл ``options.json`` и сохраняет результат в ``repo_data``.

        При сетевых или JSON-ошибках пишет предупреждение в лог и возвращает
        управление без исключения.

        Args:
            items_url: API URL для запроса элементов репозитория.
            opt_path: Путь к файлу ``options.json`` внутри репозитория.
            branch: Название ветки.
            ci_prefix: Выбранный CI-префикс (например ``/ci-2.0/``).
            repo_data: Словарь-накопитель, в который записываются найденные опции.
        """
        try:
            response = self._tfs.get_file_content(items_url, opt_path, branch)
            if response.status_code != 200:
                return
            parsed: Dict = json.loads(response.text)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning('ошибка чтения %s: %s', opt_path, e)
            return

        cleaned: Dict[str, str] = {
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
    def _select_ci_prefix(options_paths: List[str]) -> str:
        """
        Выбирает CI-префикс с наивысшим приоритетом из списка доступных путей.

        Проверяет наличие префиксов в порядке приоритета: ``/ci-2.0/`` перед
        ``/ci-1.6/``. Возвращает пустую строку, если ни один не найден.

        Args:
            options_paths: Список путей к файлам в репозитории.

        Returns:
            Строка CI-префикса или пустая строка, если подходящий не найден.
        """
        for prefix in _CI_PRIORITY:
            if any(prefix in p for p in options_paths):
                return prefix
        return ''

    @staticmethod
    def _pick_options(repo_data: Dict, channel: str) -> Dict[str, str]:
        """
        Выбирает подходящий словарь опций для указанного канала.

        Сначала ищет опции для конкретного канала, затем — глобальные.
        Если ничего не найдено, возвращает заглушку ``{'1': ''}``.

        Args:
            repo_data: Словарь с ключами ``global`` и ``channels``.
            channel: Имя канала (например ``stable``).

        Returns:
            Словарь опций ``{id: строка_опций}``.
        """
        channels = repo_data.get('channels', {})
        if channel and channel in channels:
            return channels[channel]
        global_opts = repo_data.get('global', {})
        if global_opts:
            return global_opts
        return {'1': ''}


# Обратная совместимость: старое имя оставлено для переходного периода
OptionsResolver = OptionsFetcher
