"""
HTTP утилиты с поддержкой retry-логики и exponential backoff.
"""
import http

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from autodoc.infrastructure.logger import logger

# 1.1 Именованные статус-коды вместо магических чисел
_RETRY_STATUS_CODES: frozenset = frozenset({
    http.HTTPStatus.REQUEST_TIMEOUT.value,        # 408
    http.HTTPStatus.TOO_MANY_REQUESTS.value,      # 429
    http.HTTPStatus.INTERNAL_SERVER_ERROR.value,  # 500
    http.HTTPStatus.BAD_GATEWAY.value,            # 502
    http.HTTPStatus.SERVICE_UNAVAILABLE.value,    # 503
    http.HTTPStatus.GATEWAY_TIMEOUT.value,        # 504
})

# 1.1 frozenset: порядок не важен, дубликаты недопустимы, неизменяемо
_RETRY_METHODS: frozenset = frozenset({
    "HEAD", "GET", "DELETE", "OPTIONS", "PUT", "POST",
})

class RetryableSession(requests.Session):
    """
    HTTP-сессия с автоматической retry-логикой и exponential backoff.

    По умолчанию повторяет попытки при статусах из ``_RETRY_STATUS_CODES``.

    Example::

        session = RetryableSession(max_retries=3, backoff_factor=2.0)
        response = session.get(url)
    """

    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        timeout: int = 15,
    ) -> None:
        """
        Args:
            max_retries: Максимальное количество повторных попыток.
            backoff_factor: Множитель для exponential backoff.
            timeout: Таймаут каждого запроса в секундах.
        """
        super().__init__()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=_RETRY_STATUS_CODES,
            allowed_methods=_RETRY_METHODS,
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.mount("http://", adapter)
        self.mount("https://", adapter)

    def get(self, url: str, **kwargs) -> requests.Response:
        """GET-запрос с таймаутом по умолчанию."""
        kwargs.setdefault("timeout", self.timeout)
        return super().get(url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """POST-запрос с таймаутом по умолчанию."""
        kwargs.setdefault("timeout", self.timeout)
        return super().post(url, **kwargs)

    def put(self, url: str, **kwargs) -> requests.Response:
        """PUT-запрос с таймаутом по умолчанию."""
        kwargs.setdefault("timeout", self.timeout)
        return super().put(url, **kwargs)

    def head(self, url: str, **kwargs) -> requests.Response:
        """HEAD-запрос с таймаутом по умолчанию."""
        kwargs.setdefault("timeout", self.timeout)
        return super().head(url, **kwargs)

def create_retryable_session(
    username: str | None = None,
    token: str | None = None,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    timeout: int = 15,
) -> RetryableSession:
    """
    Создаёт ``RetryableSession`` с опциональной Basic-аутентификацией.

    Args:
        username: Имя пользователя для Basic auth.
        token: Токен/пароль для Basic auth.
        max_retries: Максимальное количество retry-попыток.
        backoff_factor: Множитель для exponential backoff.
        timeout: Таймаут запроса в секундах.

    Returns:
        Настроенная сессия с retry-логикой.
    """
    session = RetryableSession(
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        timeout=timeout,
    )

    if username and token:
        session.auth = (username, token)
        logger.debug("настроена Basic-аутентификация для %r", username)
    elif username or token:
        logger.warning(
            "передан только username или только token. "
            "Для Basic auth нужны оба значения."
        )

    return session
