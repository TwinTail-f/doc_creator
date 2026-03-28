"""
Клиент для HTTP HEAD-проверки ссылок в Artifactory.

Синглтон — инициализируется один раз через ``initialize(config)``,
затем используется через ``get_instance()``.
"""
import warnings
from typing import TYPE_CHECKING, ClassVar

import requests
import urllib3

from autodoc.infrastructure.http_client import create_retryable_session
from autodoc.infrastructure.logger import logger

if TYPE_CHECKING:
    from autodoc.config.schemas import ParserConfigSchema

_HEAD_TIMEOUT = 10


class ArtifactoryClient:
    """
    HTTP-клиент для проверки доступности ссылок в Artifactory.

    Отключает SSL-верификацию и подавляет предупреждения ``InsecureRequestWarning``
    только внутри ``head()`` — не глобально.

    Attributes:
        session: HTTP-сессия с настроенной аутентификацией и retry-логикой.
    """

    _instance: ClassVar['ArtifactoryClient | None'] = None

    def __init__(
        self,
        username: str,
        password: str,
        max_retries: int = 1,
        timeout: int = _HEAD_TIMEOUT,
        verify_ssl: bool = False,
    ) -> None:
        self.session = create_retryable_session(
            username=username,
            token=password,
            max_retries=max_retries,
            timeout=timeout,
        )
        self.session.verify = verify_ssl

    @classmethod
    def initialize(cls, config: 'ParserConfigSchema') -> None:
        """Инициализирует синглтон из конфигурации. Повторный вызов — no-op."""
        if cls._instance is None:
            cls._instance = cls(
                username=config.artifactory_username,
                password=config.artifactory_password,
            )

    @classmethod
    def get_instance(cls) -> 'ArtifactoryClient':
        """Возвращает текущий экземпляр синглтона.

        Raises:
            RuntimeError: Если ``initialize()`` не был вызван.
        """
        if cls._instance is None:
            raise RuntimeError('ArtifactoryClient not initialized — call initialize() first')
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

    def head(self, url: str) -> requests.Response:
        """
        Выполняет HTTP HEAD запрос с подавлением InsecureRequestWarning.

        Args:
            url: URL для проверки.

        Returns:
            HTTP-ответ.
        """
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', urllib3.exceptions.InsecureRequestWarning)
            return self.session.head(url, allow_redirects=True, timeout=_HEAD_TIMEOUT)
