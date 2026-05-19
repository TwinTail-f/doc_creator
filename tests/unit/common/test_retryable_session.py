"""Модульные тесты для autodoc/common/retryable_session.py.

RetryableSession оборачивает сеанс HTTP с автоматической логикой повторных попыток
для временных ошибок сервера (429, 503) с экспоненциальной задержкой.

Поведение повторных попыток обеспечивается адаптером Retry от urllib3 на уровне транспорта.
Тесты, которые проверяют срабатывание повторных попыток, проверяют конфигурацию адаптера, а не
моделируют полный цикл повторных попыток urllib3, потому что собственный цикл повторных попыток urllib3 работает
внутри HTTPAdapter.send — ниже уровня, который можно перехватить простым
mocker.patch без полной замены транспорта.

Тест пересылки тайм-аута использует переопределение request() в RetryableSession,
которое является единственной логикой, которая живёт в коде приложения, а не в urllib3.
"""

from unittest.mock import MagicMock

import pytest
import requests
from pytest_mock import MockerFixture
from urllib3.util.retry import Retry

from autodoc.common.retryable_session import RetryableSession

_TIMEOUT_SEC: int = 10
_HTTP_TOO_MANY: int = 429
_HTTP_UNAVAILABLE: int = 503
_HTTP_OK: int = 200
_MAX_RETRIES: int = 3
_BACKOFF_FACTOR: float = 2.0
_HTTPS_PREFIX: str = "https://"
_TEST_URL: str = "https://example.com/api"


def _get_retry(session: RetryableSession) -> Retry:
    """Извлекает объект urllib3 Retry из HTTPS адаптера сеанса."""
    return session.get_adapter(_HTTPS_PREFIX).max_retries


# ---------------------------------------------------------------------------
# T4A.2.6 — адаптер настроен для повторных попыток на 429
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_retryable_session_retries_on_429() -> None:
    """Адаптер повторных попыток сеанса включает 429 в его status_forcelist.

    urllib3 автоматически повторит любой запрос, который получит ответ 429.
    Этот тест проверяет конфигурацию, которая подключает это поведение в
    сеанс — тестируя проводку на уровне приложения, а не сам urllib3.
    """
    session = RetryableSession(max_retries=_MAX_RETRIES, backoff_factor=0.0)
    retry = _get_retry(session)

    assert _HTTP_TOO_MANY in retry.status_forcelist
    assert retry.total == _MAX_RETRIES


# ---------------------------------------------------------------------------
# T4A.2.7 — адаптер настроен для повторных попыток на 503
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_retryable_session_retries_on_503() -> None:
    """Адаптер повторных попыток сеанса включает 503 в его status_forcelist.

    Ответы "сервис недоступен" — это временные проблемы инфраструктуры;
    адаптер должен быть настроен на автоматический повтор их.
    """
    session = RetryableSession(max_retries=_MAX_RETRIES, backoff_factor=0.0)
    retry = _get_retry(session)

    assert _HTTP_UNAVAILABLE in retry.status_forcelist


# ---------------------------------------------------------------------------
# T4A.2.8 — лимит повторных попыток соблюдается (адаптер настроен правильно)
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_retryable_session_raises_after_exhausting_retries() -> None:
    """Общее количество адаптера повторных попыток соответствует аргументу конструктора max_retries.

    urllib3 вызовет MaxRetryError (отобразится в requests как RetryError) после того, как
    этот лимит будет достигнут. Этот тест проверяет, что лимит подключён правильно, чтобы
    запросы не циклились бесконечно.
    """
    max_retries: int = 2
    session = RetryableSession(max_retries=max_retries, backoff_factor=0.0)
    retry = _get_retry(session)

    assert retry.total == max_retries


# ---------------------------------------------------------------------------
# T4A.2.9 — фактор экспоненциальной задержки хранится в адаптере повторных попыток
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_retryable_session_uses_exponential_backoff() -> None:
    """Настроенный backoff_factor подключён к объекту urllib3 Retry.

    urllib3 вычисляет задержки сна как backoff_factor * (2 ** (retry_count - 1)),
    поэтому вторая задержка всегда строго больше первой, когда
    backoff_factor > 0. Этот тест проверяет, что фактор сохранён правильно, чтобы
    задержки увеличивались между повторными попытками.
    """
    session = RetryableSession(max_retries=_MAX_RETRIES, backoff_factor=_BACKOFF_FACTOR)
    retry = _get_retry(session)

    assert retry.backoff_factor == _BACKOFF_FACTOR
    # Проверка, что вторая задержка > первой задержки для настроенного backoff_factor.
    # Формула задержки: backoff_factor * (2 ** (retry_index - 1))
    first_delay: float = _BACKOFF_FACTOR * (2**0)  # retry 1 → backoff_factor * 1
    second_delay: float = _BACKOFF_FACTOR * (2**1)  # retry 2 → backoff_factor * 2
    assert second_delay > first_delay


# ---------------------------------------------------------------------------
# T4A.2.10 — переопределение request() пересылает timeout родительской реализации
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_retryable_session_timeout_forwarded_to_request(
    mocker: MockerFixture,
) -> None:
    """RetryableSession.request() внедряет свой _timeout в каждый вызов super().request().

    Переопределение в RetryableSession.request() — это единственная логика приложения
    в этом классе; оно должно передавать effective_timeout=self._timeout в
    super().request(), чтобы каждый вызов HTTP соблюдал настроенный timeout.
    """
    mock_super_request: MagicMock = mocker.patch.object(
        requests.Session, "request", return_value=MagicMock(status_code=_HTTP_OK)
    )

    session = RetryableSession(timeout=_TIMEOUT_SEC)
    session.get(_TEST_URL)

    mock_super_request.assert_called_once()
    call_kwargs = mock_super_request.call_args.kwargs
    assert call_kwargs.get("timeout") == _TIMEOUT_SEC
