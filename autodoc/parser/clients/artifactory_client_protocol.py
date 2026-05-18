"""
Протокол (структурный интерфейс) для Artifactory-клиента.
"""

from typing import Protocol, runtime_checkable

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
