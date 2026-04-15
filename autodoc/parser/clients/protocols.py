"""
Абстрактные интерфейсы (Protocol) для инфраструктурных зависимостей парсера.

Использование ``typing.Protocol`` (структурная типизация) означает, что ни
``TFSClient``, ни ``ArtifactoryClient`` не требуют изменений в коде —
они удовлетворяют этим интерфейсам неявно.

Шаги пайплайна и ``PipelineContext`` зависят от этих Protocol-ов, а не от
конкретных инфраструктурных классов.
"""

from typing import Any, Protocol, runtime_checkable

import requests


@runtime_checkable
class IArtifactoryClient(Protocol):
    """
    Интерфейс для проверки доступности артефактов в Artifactory.

    Охватывает только метод ``head()``, используемый в ``ArtifactoryValidationStep``.
    ``ArtifactoryClient`` удовлетворяет этому интерфейсу структурно.
    """

    def head(self, url: str) -> requests.Response:
        """Выполняет HTTP HEAD-запрос и возвращает ответ."""
        ...


@runtime_checkable
class ITFSClient(Protocol):
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
        ...

    def get_file_content(
        self,
        items_url: str,
        path: str,
        branch: str,
        version_type: Any = None,
    ) -> requests.Response:
        """Получает содержимое одного файла из TFS."""
        ...

    def get_items(
        self,
        items_url: str,
        branch: str,
        recursion: Any = None,
        version_type: Any = None,
    ) -> list[dict[str, Any]]:
        """Возвращает список элементов (файлов и папок) репозитория TFS."""
        ...
