"""
Клиент для HTTP HEAD-проверки ссылок в Artifactory.

Создаётся один раз в ``ComponentParser.parse()`` и передаётся в
``PipelineContext``. Шаги пайплайна получают экземпляр через
``ctx.artifactory_client``.
"""

import requests

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.common.retryable_session import create_pat_session
from autodoc.common.logger import logger


class ArtifactoryClient:
    """
    HTTP-клиент для проверки доступности ссылок в Artifactory.

    Создаётся через ``ArtifactoryClient(config)`` и внедряется в
    ``PipelineContext``. Не хранит глобального состояния — каждый
    экземпляр независим.

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

    def check_url(self, url: str) -> requests.Response:
        """
        Проверяет доступность URL с помощью HTTP HEAD-запроса.

        Args:
            url: URL для проверки.

        Returns:
            HTTP-ответ сервера.
        """
        logger.debug(f"HEAD {url}")
        return self.session.head(url, allow_redirects=True)
