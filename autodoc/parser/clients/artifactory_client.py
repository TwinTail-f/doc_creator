"""
Клиент для HTTP HEAD-проверки ссылок в Artifactory.

Создаётся один раз в ``ComponentParser.parse()`` и передаётся в
``PipelineContext``. Шаги пайплайна получают экземпляр через
``ctx.artifactory_client``.
"""
import warnings

import requests
import urllib3

from autodoc.config.schemas import ParserConfigSchema
from autodoc.infrastructure.http_client import create_retryable_session
from autodoc.infrastructure.logger import logger

_HEAD_TIMEOUT: int = 10
_MAX_RETRIES: int = 1


class ArtifactoryClient:
    """
    HTTP-клиент для проверки доступности ссылок в Artifactory.

    Создаётся через ``ArtifactoryClient(config)`` и внедряется в
    ``PipelineContext``. Не хранит глобального состояния — каждый
    экземпляр независим.

    Отключает SSL-верификацию и подавляет ``InsecureRequestWarning``
    только внутри ``head()`` — не глобально.

    Attributes:
        session: HTTP-сессия с настроенной аутентификацией и retry-логикой.
    """

    def __init__(self, config: ParserConfigSchema) -> None:
        """
        Инициализирует Artifactory-клиент из конфигурации парсера.

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
            warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
            return self.session.head(url, allow_redirects=True, timeout=_HEAD_TIMEOUT)
