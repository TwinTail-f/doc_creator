"""
Клиент для взаимодействия с REST API TFS.

Живёт в ``parser/`` — используется только парсером
(``ManifestParser``, ``OptionsResolver``, ``DockerResolver``).
"""
from enum import Enum
from pathlib import Path
from typing import Any

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
        # 3.2 sys.exit заменён на ConfigError — корректная обработка ошибок конфигурации
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

        logger.info('TFSClient: запрос списка файлов из %s (ветка: %s)', items_url, branch)

        try:
            response = self.session.get(items_url, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise NetworkError(
                'TFSClient.download_properties: ошибка при получении списка файлов: %s' % e
            ) from e

        items = response.json().get('value', [])
        logger.info('TFSClient: найдено %d элементов, начинаем скачивание…', len(items))

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
                logger.warning('TFSClient: не удалось скачать %s: %s. Пропускаем.', file_name, e)

        logger.info('TFSClient: успешно скачано %d файлов.', downloaded_count)

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
