"""
Клиент для взаимодействия с REST API TFS.

Живёт в ``parser/`` — используется fetcher-классами парсера
(``ManifestFetcher``, ``DockerFetcher``, ``OptionsFetcher``).

Создаётся один раз в ``ComponentParser.parse()`` и передаётся в
``PipelineContext``. Фетчеры получают экземпляр через ``ctx.tfs_client``.
"""

from pathlib import Path
from typing import Any

import requests

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import NetworkError
from autodoc.common.retryable_session import create_retryable_session
from autodoc.common.logger import logger
from autodoc.parser.clients.tfs_client_enums import RecursionLevel, VersionType


class TFSClient:
    """
    Клиент для выполнения запросов к TFS с автоматической retry-логикой.

    Создаётся через ``TFSClient(config)`` и внедряется в ``PipelineContext``.
    Не хранит глобального состояния — каждый экземпляр независим.

    Аутентификация: PAT-токен через Basic auth. Username опционален —
    Azure DevOps принимает любое (в том числе пустое) значение.

    Attributes:
        session: HTTP-сессия с настроенной аутентификацией и retry-логикой.
    """

    _API_VERSION: str = "7.1"

    def __init__(self, config: ParserConfigSchema) -> None:
        """
        Инициализирует TFS-клиент из конфигурации парсера.

        Args:
            config: Валидированная конфигурация парсера с учётными данными TFS.
        """
        self.session = create_retryable_session(
            token=config.tfs_token,
            max_retries=config.max_retries,
            backoff_factor=config.retry_backoff_factor,
            timeout=config.tfs_request_timeout,
        )
        self.session.params = {"api-version": self._API_VERSION}

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
        version_type: VersionType = VersionType.BRANCH,
    ) -> None:
        """
        Скачивает все ``.properties``-файлы из директории TFS в локальную папку.

        Args:
            items_url: API URL для запроса элементов репозитория.
            remote_path: Путь к директории внутри репозитория (scopePath).
            branch: Название ветки или тега.
            output_dir: Локальный путь для сохранения файлов.
            version_type: Тип версии (branch, tag, commit). По умолчанию branch.

        Raises:
            NetworkError: Если не удалось получить список файлов.
        """
        params = {
            "scopePath": remote_path,
            "versionDescriptor.version": branch,
            "versionDescriptor.versionType": version_type.value,
            "recursionLevel": RecursionLevel.ONE_LEVEL.value,
        }

        logger.info(
            f"Запрос списка файлов из {items_url} ({version_type.value}: {branch})"
        )

        try:
            response = self.session.get(items_url, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Ошибка при получении списка файлов: {e}") from e

        items = response.json().get("value", [])
        logger.info(f"Найдено {len(items)} элементов, начинаем скачивание…")

        out_dir = Path(output_dir)
        downloaded_count = 0

        for item in items:
            path_str: str = item.get("path", "")
            if item.get("isFolder") or not path_str.endswith(".properties"):
                continue

            file_name = Path(path_str).name
            try:
                file_response = self.get_file_content(
                    items_url, path_str, branch, version_type
                )
                file_response.raise_for_status()
                (out_dir / file_name).write_text(file_response.text, encoding="utf-8")
                downloaded_count += 1
            except (requests.exceptions.RequestException, NetworkError) as e:
                logger.warning(f"Не удалось скачать {file_name}: {e}. Пропускаем.")

        logger.info(f"Успешно скачано {downloaded_count} файлов.")

    def get_file_content(
        self,
        items_url: str,
        path: str,
        branch: str,
        version_type: VersionType = VersionType.BRANCH,
    ) -> requests.Response:
        """
        Получает содержимое файла из TFS.

        Args:
            items_url: Базовый API URL для items репозитория.
            path: Полный путь к файлу в репозитории.
            branch: Название ветки или тега.
            version_type: Тип версии (branch, tag, commit). По умолчанию branch.

        Returns:
            Ответ сервера с содержимым файла.

        Raises:
            NetworkError: Если запрос не удался.
        """
        params = {
            "path": path,
            "versionDescriptor.version": branch,
            "versionDescriptor.versionType": version_type.value,
        }
        try:
            return self.session.get(items_url, params=params)
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Ошибка запроса файла {path}: {e}") from e

    def get_items(
        self,
        items_url: str,
        branch: str,
        recursion: RecursionLevel = RecursionLevel.FULL,
        version_type: VersionType = VersionType.BRANCH,
    ) -> list[dict[str, Any]]:
        """
        Получает список элементов (файлов и папок) репозитория.

        Args:
            items_url: Базовый API URL для items.
            branch: Название ветки или тега.
            recursion: Уровень рекурсии обхода репозитория.
            version_type: Тип версии (branch, tag, commit). По умолчанию branch.

        Returns:
            Список словарей с описанием элементов репозитория.

        Raises:
            NetworkError: Если запрос не удался.
        """
        params = {
            "recursionLevel": recursion.value,
            "versionDescriptor.version": branch,
            "versionDescriptor.versionType": version_type.value,
        }
        try:
            response = self.session.get(items_url, params=params)
            response.raise_for_status()
            return response.json().get("value", [])
        except requests.exceptions.RequestException as e:
            raise NetworkError(
                f"Ошибка запроса структуры репозитория (url={items_url}, branch={branch}): {e}"
            ) from e
