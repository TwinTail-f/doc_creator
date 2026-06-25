"""
HTTP утилиты с поддержкой retry-логики и exponential backoff.
"""

import http

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from autodoc.common.logger import logger

_RETRY_STATUS_CODES: tuple[int, ...] = (
    http.HTTPStatus.REQUEST_TIMEOUT.value,  # 408
    http.HTTPStatus.TOO_MANY_REQUESTS.value,  # 429
    http.HTTPStatus.INTERNAL_SERVER_ERROR.value,  # 500
    http.HTTPStatus.BAD_GATEWAY.value,  # 502
    http.HTTPStatus.SERVICE_UNAVAILABLE.value,  # 503
    http.HTTPStatus.GATEWAY_TIMEOUT.value,  # 504
)

_RETRY_METHODS: tuple[str, ...] = (
    "HEAD",
    "GET",
    "DELETE",
    "OPTIONS",
    "PUT",
    "POST",
)

_PAT_DEFAULT_USERNAME: str = ""


class RetryableSession(requests.Session):
    """
    HTTP-сессия с автоматической retry-логикой и exponential backoff.

    Таймаут задаётся при инициализации и применяется ко всем запросам.

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
        self._timeout = timeout

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=_RETRY_STATUS_CODES,
            allowed_methods=_RETRY_METHODS,
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.mount("https://", adapter)

    def request(
        self, method: str, url: str, *, timeout: int | None = None, **kwargs: object
    ) -> requests.Response:
        """Все HTTP-методы проходят сюда — таймаут подставляется один раз."""
        effective_timeout = timeout or self._timeout
        return super().request(method, url, timeout=effective_timeout, **kwargs)


def create_bearer_session(
    token: str | None = None,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    timeout: int = 15,
) -> RetryableSession:
    """
    Создаёт ``RetryableSession`` с Bearer-аутентификацией.

    Используется для Confluence Data Center PAT-аутентификации.

    Args:
        token: Bearer-токен. Если ``None`` — заголовок Authorization не устанавливается.
        max_retries: Максимальное количество retry-попыток.
        backoff_factor: Множитель для exponential backoff.
        timeout: Таймаут запроса в секундах.

    Returns:
        Настроенная сессия с retry-логикой и Bearer-аутентификацией.
    """
    session = RetryableSession(
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        timeout=timeout,
    )
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
        logger.debug("Настроена Bearer-аутентификация")
    return session


def create_pat_session(
    token: str | None = None,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    timeout: int = 15,
) -> RetryableSession:
    """
    Создаёт ``RetryableSession`` с PAT / Basic-аутентификацией.

    Args:
        token: Personal Access Token. Если ``None`` — аутентификация не устанавливается.
        max_retries: Максимальное количество retry-попыток.
        backoff_factor: Множитель для exponential backoff.
        timeout: Таймаут запроса в секундах.

    Returns:
        Настроенная сессия с retry-логикой и PAT-аутентификацией.
    """
    session = RetryableSession(
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        timeout=timeout,
    )
    if token:
        session.auth = (_PAT_DEFAULT_USERNAME, token)
        logger.debug("Настроена PAT-аутентификация (username не задан)")
    return session


def create_retryable_session(
    timeout: int = 15,
    token: str | None = None,
    bearer: bool = False,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
) -> RetryableSession:
    """
    Создаёт ``RetryableSession`` с опциональной аутентификацией.

    .. deprecated::
        Используйте ``create_bearer_session()`` или ``create_pat_session()`` напрямую.
        Этот враппер будет удалён в одном из следующих релизов.

    Args:
        timeout: Таймаут запроса в секундах.
        token: Токен / PAT.
        bearer: Если ``True`` — используется Bearer-аутентификация, иначе — PAT/Basic.
        max_retries: Максимальное количество retry-попыток.
        backoff_factor: Множитель для exponential backoff.

    Returns:
        Настроенная сессия с retry-логикой.
    """
    if bearer and token:
        return create_bearer_session(
            token=token,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            timeout=timeout,
        )
    return create_pat_session(
        token=token,
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        timeout=timeout,
    )
