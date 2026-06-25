"""
Клиент для HTTP HEAD-проверки ссылок в Artifactory.

Создаётся один раз в ``ComponentParser.parse()`` и передаётся в
``PipelineContext``. Шаги пайплайна получают экземпляр через
``ctx.artifactory_client``.
"""

import warnings

import requests
import urllib3

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.common.retryable_session import create_pat_session
from autodoc.common.logger import logger


class ArtifactoryClient:
    """
    HTTP-клиент для проверки доступности ссылок в Artifactory.

    Создаётся через ``ArtifactoryClient(config)`` и внедряется в
    ``PipelineContext``. Не хранит глобального состояния — каждый
    экземпляр независим.

    SSL-верификация отключена на уровне сессии (не только внутри ``head()``),
    поскольку Artifactory в корпоративной сети использует самоподписанные
    сертификаты. ``InsecureRequestWarning`` подавляется локально внутри
    ``head()``, чтобы не засорять лог при массовых проверках.

    Attributes:
        session: HTTP-сессия с настроенной аутентификацией и retry-логикой.
    """

    def __init__(self, config: ParserConfigSchema) -> None:
        """
        Инициализирует Artifactory-клиент из конфигурации парсера.

        Args:
            config: Валидированная конфигурация парсера с PAT-токеном Artifactory.
        """
        self.session = create_pat_session(
            token=config.artifactory_token,
            max_retries=config.max_retries,
            backoff_factor=config.retry_backoff_factor,
        )
        self.session.verify = False

    def head(self, url: str) -> requests.Response:
        """
        Выполняет HTTP HEAD-запрос к указанному URL.

        Args:
            url: URL для проверки.

        Returns:
            HTTP-ответ сервера.
        """
        logger.debug(f"HEAD {url}")
        with warnings.catch_warnings():
            # InsecureRequestWarning подавляется локально, а не на уровне всего процесса,
            # чтобы не засорять лог при массовых проверках.
            warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
            return self.session.head(url, allow_redirects=True)
