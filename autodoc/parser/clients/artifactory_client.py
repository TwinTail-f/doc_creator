"""
Клиент для HTTP HEAD-проверки ссылок в Artifactory.

Синглтон реализован через метакласс ``Singleton``:
первый вызов ``ArtifactoryClient(config)`` создаёт экземпляр,
последующие вызовы возвращают тот же объект.
"""
import warnings

import requests
import urllib3

from autodoc.config.schemas import ParserConfigSchema
from autodoc.infrastructure.http_client import create_retryable_session
from autodoc.infrastructure.logger import logger
from autodoc.infrastructure.singleton import Singleton

_HEAD_TIMEOUT: int = 10
_MAX_RETRIES: int = 1


class ArtifactoryClient(metaclass=Singleton):
    """
    HTTP-клиент для проверки доступности ссылок в Artifactory.

    Синглтон — первый вызов ``ArtifactoryClient(config)`` создаёт экземпляр,
    последующие вызовы возвращают тот же объект без повторной инициализации.

    Отключает SSL-верификацию и подавляет ``InsecureRequestWarning``
    только внутри ``head()`` — не глобально.

    Attributes:
        session: HTTP-сессия с настроенной аутентификацией и retry-логикой.
    """

    def __init__(self, config: ParserConfigSchema) -> None:
        """
        Инициализирует Artifactory-клиент из конфигурации парсера.

        Вызывается только при первом создании синглтона. При повторных вызовах
        ``ArtifactoryClient(config)`` метакласс возвращает существующий экземпляр,
        не вызывая ``__init__`` повторно.

        Args:
            config: Валидированная конфигурация парсера с учётными данными Artifactory.
        """
        self.session = create_retryable_session(
            username=config.artifactory_username,
            token=config.artifactory_password,
            max_retries=_MAX_RETRIES,
            timeout=_HEAD_TIMEOUT,
        )
        self.session.verify = False

    @classmethod
    def reset(cls) -> None:
        """
        Удаляет экземпляр из реестра синглтонов без закрытия сессии.

        Предназначен только для использования в тестах.
        """
        Singleton._instances.pop(cls, None)

    def head(self, url: str) -> requests.Response:
        """
        Выполняет HTTP HEAD запрос с подавлением InsecureRequestWarning.

        SSL-предупреждение подавляется только внутри этого метода —
        не на уровне всего процесса.

        Args:
            url: URL для проверки.

        Returns:
            HTTP-ответ.
        """
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', urllib3.exceptions.InsecureRequestWarning)
            return self.session.head(url, allow_redirects=True, timeout=_HEAD_TIMEOUT)
