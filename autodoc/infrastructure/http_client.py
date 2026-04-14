"""
HTTP утилиты с поддержкой retry-логики и exponential backoff.
"""

import http

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from autodoc.infrastructure.logger import logger

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
        return super().request(method, url, timeout=self._timeout, **kwargs)


def create_retryable_session(    timeout: int = 15,
    token: str | None = None,
    bearer: bool = False,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
) -> RetryableSession:
    """
    Создаёт ``RetryableSession`` с опциональной аутентификацией.

    Поддерживает два режима:

    * **Bearer** — передать ``token`` и ``bearer=True``; токен подставляется
      в заголовок ``Authorization: Bearer <token>``. Используется для
      Confluence Data Center PAT-аутентификации.
    * **PAT-only** — передать только ``token``; username подставляется
      как пустая строка, что корректно для Azure DevOps / TFS,
      где PAT не привязан к конкретному пользователю.

    Args:
        token: Токен / PAT.
        bearer: Если ``True`` — использовать Bearer-аутентификацию вместо Basic.
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

    if bearer and token:
        session.headers["Authorization"] = f"Bearer {token}"
        logger.debug("Настроена Bearer-аутентификация")
    elif token:
        # PAT-аутентификация: username опционален (Azure DevOps / TFS и др.)
        session.auth = (_PAT_DEFAULT_USERNAME, token)
        logger.debug("Настроена PAT-аутентификация (username не задан)")

    return session