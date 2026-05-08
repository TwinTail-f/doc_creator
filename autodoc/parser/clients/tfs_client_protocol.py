"""
Протокол (structural interface) для TFS-клиента.
"""

from typing import Any, Protocol

import requests


class TFSClientProtocol(Protocol):
    """
    Интерфейс для чтения файлов и листинга директорий из TFS.

    Охватывает три публичных метода, используемых классами-фетчерами.
    ``TFSClient`` удовлетворяет этому интерфейсу структурно.
    """

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
        version_type: Any = None,
    ) -> None:
        """Скачивает все ``.properties``-файлы из директории TFS."""

    def get_file_content(
        self,
        items_url: str,
        path: str,
        branch: str,
        version_type: Any = None,
    ) -> requests.Response:
        """Получает содержимое одного файла из TFS."""

    def get_items(
        self,
        items_url: str,
        branch: str,
        recursion: Any = None,
        version_type: Any = None,
    ) -> list[dict[str, Any]]:
        """Возвращает список элементов (файлов и папок) репозитория TFS."""
