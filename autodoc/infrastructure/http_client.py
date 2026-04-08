"""
HTTP утилиты с поддержкой retry-логики и exponential backoff.
"""

import http

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from autodoc.infrastructure.logger import logger

# Именованные статус-коды вместо магических чисел
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

    Таймаут задаётся при инициализации и применяется ко всем запросам
    через переопределённый метод ``request()``.

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

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Все HTTP-методы проходят сюда — таймаут подставляется один раз."""
        timeout = kwargs.pop("timeout", self._timeout)
        return super().request(method, url, timeout=timeout, **kwargs)


def create_retryable_session(
    username: str | None = None,
    token: str | None = None,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    timeout: int = 15,
) -> RetryableSession:
    """
    Создаёт ``RetryableSession`` с опциональной Basic-аутентификацией.

    Поддерживает два режима:

    * **Basic auth** — передать ``username`` и ``token``.
    * **PAT-only** — передать только ``token``; username подставляется
      как пустая строка, что корректно для Azure DevOps / TFS
      и Confluence Data Center, где PAT не привязан к конкретному пользователю.

    Args:
        username: Имя пользователя для Basic auth. Опционально при PAT-auth.
        token: Токен / пароль / PAT для Basic auth.
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
        logger.debug(f"Настроена Basic-аутентификация для {username!r}")
    elif token:
        # PAT-аутентификация: username не требуется (Azure DevOps / TFS, Confluence DC и др.)
        session.auth = (_PAT_DEFAULT_USERNAME, token)
        logger.debug("Настроена PAT-аутентификация (username не задан)")
    elif username:
        logger.warning(
            f"Передан только username {username!r} без token — аутентификация не настроена"
        )

    return session
