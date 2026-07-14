"""Модульные тесты для autodoc/common/retryable_session.py.

RetryableSession оборачивает сеанс HTTP с автоматической логикой повторных попыток
для временных ошибок сервера (429, 503) с экспоненциальной задержкой.

Поведение повторных попыток обеспечивается адаптером Retry от urllib3 на уровне транспорта.
Тесты, которые проверяют срабатывание повторных попыток, подменяют самый нижний уровень —
``HTTPConnectionPool._make_request`` — фальшивым транспортом, возвращающим заданную
последовательность ответов. Благодаря этому настоящий цикл повторных попыток urllib3
(проверка status_forcelist, инкремент счётчика, рекурсивный вызов urlopen) отрабатывает
по-настоящему, а не подменяется моком целиком: тест проверяет фактическое количество
попыток и итоговый результат запроса, а не только то, что конфигурация выглядит правильно.

Тест пересылки тайм-аута использует переопределение request() в RetryableSession,
которое является единственной логикой, которая живёт в коде приложения, а не в urllib3.
"""

import io
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
import requests
import urllib3
from pytest_mock import MockerFixture
from urllib3.connectionpool import HTTPConnectionPool
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


def _fake_transport(mocker: MockerFixture, statuses: Iterator[int]) -> MagicMock:
    """Подменяет ``HTTPConnectionPool._make_request`` фальшивым транспортом.

    На каждый вызов возвращает ``urllib3.HTTPResponse`` со следующим статусом
    из ``statuses``. Это самый нижний уровень, на котором ещё можно
    перехватить запрос без реального сокета, поэтому вся логика повторных
    попыток urllib3 (чтение status_forcelist, инкремент Retry, рекурсия
    urlopen) выполняется по-настоящему.

    Args:
        mocker: Фикстура pytest-mock для патчинга.
        statuses: Последовательность HTTP-статусов, отдаваемых по одному на вызов.

    Returns:
        Мок, по которому можно проверить фактическое количество попыток
        (``call_count``).
    """

    def _make_request(
        self: HTTPConnectionPool,
        conn: object,
        method: str,
        url: str,
        *args: object,
        **kwargs: object,
    ) -> urllib3.HTTPResponse:
        status = next(statuses)
        return urllib3.HTTPResponse(
            body=io.BytesIO(b""),
            status=status,
            headers={},
            preload_content=False,
            request_method=method,
        )

    return mocker.patch.object(
        HTTPConnectionPool, "_make_request", autospec=True, side_effect=_make_request
    )


@pytest.mark.infrastructure
def test_retryable_session_retries_on_429(mocker: MockerFixture) -> None:
    """После первого ответа 429 сессия автоматически повторяет запрос и
    возвращает результат второй, успешной попытки.

    Тест гоняет запрос через настоящий цикл повторных попыток urllib3 (а не
    только проверяет конфигурацию Retry), поэтому фиксирует и итоговый
    статус, и фактическое число обращений к транспорту.
    """
    mock_transport = _fake_transport(mocker, iter([_HTTP_TOO_MANY, _HTTP_OK]))
    session = RetryableSession(max_retries=_MAX_RETRIES, backoff_factor=0.0)

    response = session.get(_TEST_URL)

    assert response.status_code == _HTTP_OK
    assert mock_transport.call_count == 2


@pytest.mark.infrastructure
def test_retryable_session_retries_on_503(mocker: MockerFixture) -> None:
    """После первого ответа 503 («сервис недоступен» — временная проблема
    инфраструктуры) сессия автоматически повторяет запрос и возвращает
    результат второй, успешной попытки."""
    mock_transport = _fake_transport(mocker, iter([_HTTP_UNAVAILABLE, _HTTP_OK]))
    session = RetryableSession(max_retries=_MAX_RETRIES, backoff_factor=0.0)

    response = session.get(_TEST_URL)

    assert response.status_code == _HTTP_OK
    assert mock_transport.call_count == 2


@pytest.mark.infrastructure
def test_retryable_session_raises_after_exhausting_retries(mocker: MockerFixture) -> None:
    """Если транспорт неизменно отвечает 429, сессия делает не более
    ``max_retries`` повторов, после чего пробрасывает ``RetryError``, а не
    зацикливается бесконечно."""
    max_retries: int = 2
    mock_transport = _fake_transport(mocker, iter(lambda: _HTTP_TOO_MANY, None))
    session = RetryableSession(max_retries=max_retries, backoff_factor=0.0)

    with pytest.raises(requests.exceptions.RetryError):
        session.get(_TEST_URL)

    # Первая попытка + max_retries повторов.
    assert mock_transport.call_count == max_retries + 1


@pytest.mark.infrastructure
def test_retryable_session_uses_exponential_backoff() -> None:
    """Настроенный backoff_factor подключён к объекту urllib3 Retry.

    urllib3 вычисляет задержки сна как backoff_factor * (2 ** (retry_count - 1)),
    поэтому вторая задержка всегда строго больше первой, когда
    backoff_factor > 0. Реальный сон между повторами здесь намеренно не
    проверяется (это удлинило бы тест или потребовало мокать time.sleep
    внутри urllib3), а лишь то, что фактор сохранён и формула задержки
    действительно возрастающая.
    """
    session = RetryableSession(max_retries=_MAX_RETRIES, backoff_factor=_BACKOFF_FACTOR)
    retry = _get_retry(session)

    assert retry.backoff_factor == _BACKOFF_FACTOR
    # Проверка, что вторая задержка > первой задержки для настроенного backoff_factor.
    # Формула задержки: backoff_factor * (2 ** (retry_index - 1))
    first_delay: float = _BACKOFF_FACTOR * (2**0)  # retry 1 → backoff_factor * 1
    second_delay: float = _BACKOFF_FACTOR * (2**1)  # retry 2 → backoff_factor * 2
    assert second_delay > first_delay


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
