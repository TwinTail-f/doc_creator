"""
Клиент для взаимодействия с REST API TFS.

Живёт в ``infrastructure/`` — используется fetcher-классами парсера
(``ManifestFetcher``, ``DockerFetcher``, ``OptionsFetcher``).
"""

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from autodoc.config.schemas import ParserConfigSchema

import requests

from autodoc.exceptions import ConfigError, NetworkError
from autodoc.infrastructure.http_client import create_retryable_session
from autodoc.infrastructure.logger import logger


class RecursionLevel(str, Enum):
    """Допустимые уровни рекурсии для TFS Items API."""

    ONE_LEVEL = 'OneLevel'
    FULL = 'Full'


class TFSClient:
    """
    Клиент для выполнения запросов к TFS с автоматической retry-логикой.

    Использует ``RetryableSession`` из ``http_client`` — собственный retry-код
    не дублируется.

    Attributes:
        session: HTTP-сессия с настроенной аутентификацией и retry-логикой.
    """

    _API_VERSION = '7.1'
    _instance: ClassVar['TFSClient | None'] = None

    def __init__(
        self,
        username: str,
        token: str,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        timeout: int = 15,
    ) -> None:
        """
        Инициализирует TFS-клиент.

        Args:
            username: Имя пользователя TFS.
            token: Personal Access Token (PAT).
            max_retries: Максимальное количество retry-попыток.
            backoff_factor: Множитель для exponential backoff.
            timeout: Таймаут HTTP-запросов в секундах.

        Raises:
            ConfigError: Если учётные данные не переданы.
        """
        if not (username and token):
            raise ConfigError(
                'TFSClient: учётные данные не переданы. '
                'Укажите tfs_username и tfs_token в конфигурации.'
            )

        self.session = create_retryable_session(
            username=username,
            token=token,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            timeout=timeout,
        )
        self.session.params = {'api-version': self._API_VERSION}

    @classmethod
    def initialize(cls, config: 'ParserConfigSchema') -> None:
        """Инициализирует синглтон из конфигурации. Повторный вызов — no-op."""
        if cls._instance is None:
            cls._instance = cls._from_config(config)

    @classmethod
    def get_instance(cls) -> 'TFSClient':
        """Возвращает текущий экземпляр синглтона.

        Raises:
            RuntimeError: Если ``initialize()`` не был вызван.
        """
        if cls._instance is None:
            raise RuntimeError('TFSClient not initialized — call initialize() first')
        return cls._instance

    @classmethod
    def shutdown(cls) -> None:
        """Закрывает сессию и сбрасывает синглтон."""
        if cls._instance is not None:
            cls._instance.session.close()
            cls._instance = None

    @classmethod
    def reset(cls) -> None:
        """Для тестов только. Сбрасывает синглтон без закрытия сессии."""
        cls._instance = None

    @classmethod
    def _from_config(cls, config: 'ParserConfigSchema') -> 'TFSClient':
        """
        Создаёт ``TFSClient`` из конфигурации парсера (приватный фабричный метод).

        Args:
            config: Валидированная конфигурация парсера.

        Returns:
            Настроенный экземпляр ``TFSClient``.
        """
        return cls(
            username=config.tfs_username,
            token=config.tfs_token,
            max_retries=config.max_retries,
            backoff_factor=config.retry_backoff_factor,
            timeout=config.tfs_request_timeout,
        )

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
    ) -> None:
        """
        Скачивает все ``.properties``-файлы из директории TFS в локальную папку.

        Args:
            items_url: API URL для запроса элементов репозитория.
            remote_path: Путь к директории внутри репозитория (scopePath).
            branch: Название ветки.
            output_dir: Локальный путь для сохранения файлов.

        Raises:
            NetworkError: Если не удалось получить список файлов.
        """
        params = {
            'scopePath': remote_path,
            'versionDescriptor.version': branch,
            'recursionLevel': RecursionLevel.ONE_LEVEL.value,
        }

        logger.info('запрос списка файлов из %s (ветка: %s)', items_url, branch)

        try:
            response = self.session.get(items_url, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise NetworkError(
                'TFSClient.download_properties: ошибка при получении списка файлов: %s' % e
            ) from e

        items = response.json().get('value', [])
        logger.info('найдено %d элементов, начинаем скачивание…', len(items))

        out_dir = Path(output_dir)
        downloaded_count = 0

        for item in items:
            path_str: str = item.get('path', '')
            if item.get('isFolder') or not path_str.endswith('.properties'):
                continue

            file_name = Path(path_str).name
            try:
                file_response = self.get_file_content(items_url, path_str, branch)
                file_response.raise_for_status()
                (out_dir / file_name).write_text(file_response.text, encoding='utf-8')
                downloaded_count += 1
            except requests.exceptions.RequestException as e:
                logger.warning('не удалось скачать %s: %s. Пропускаем.', file_name, e)

        logger.info('успешно скачано %d файлов.', downloaded_count)

    def get_file_content(
        self,
        items_url: str,
        path: str,
        branch: str,
    ) -> requests.Response:
        """
        Получает содержимое файла из TFS.

        Args:
            items_url: Базовый API URL для items репозитория.
            path: Полный путь к файлу в репозитории.
            branch: Название ветки.

        Returns:
            Ответ сервера с содержимым файла.

        Raises:
            NetworkError: Если запрос не удался.
        """
        params = {
            'path': path,
            'versionDescriptor.version': branch,
        }
        try:
            return self.session.get(items_url, params=params)
        except requests.exceptions.RequestException as e:
            raise NetworkError(
                'TFSClient.get_file_content: ошибка запроса файла %s: %s' % (path, e)
            ) from e

    def get_items(
        self,
        items_url: str,
        branch: str,
        recursion: RecursionLevel = RecursionLevel.FULL,
    ) -> list[dict[str, Any]]:
        """
        Получает список элементов (файлов и папок) репозитория.

        Args:
            items_url: Базовый API URL для items.
            branch: Название ветки.
            recursion: Уровень рекурсии обхода репозитория.

        Returns:
            Список словарей с описанием элементов репозитория.

        Raises:
            NetworkError: Если запрос не удался.
        """
        params = {
            'recursionLevel': recursion.value,
            'versionDescriptor.version': branch,
        }
        try:
            response = self.session.get(items_url, params=params)
            response.raise_for_status()
            return response.json().get('value', [])
        except requests.exceptions.RequestException as e:
            raise NetworkError(
                'TFSClient.get_items: ошибка запроса структуры репозитория '
                '(url=%s, branch=%s): %s' % (items_url, branch, e)
            ) from e
