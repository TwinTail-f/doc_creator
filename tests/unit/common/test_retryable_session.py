"""Модульные тесты для autodoc/common/retryable_session.py.

RetryableSession оборачивает сеанс HTTP с автоматической логикой повторных попыток
для временных ошибок сервера с экспоненциальной задержкой.
"""

import base64
import io
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
import requests
import responses
import urllib3
from pytest_mock import MockerFixture
from urllib3.connectionpool import HTTPConnectionPool

from autodoc.common.retryable_session import (
    _RETRY_STATUS_CODES,
    RetryableSession,
    create_bearer_session,
    create_pat_session,
    create_retryable_session,
)

_TIMEOUT_SEC: int = 10
_HTTP_TOO_MANY: int = 429
_HTTP_OK: int = 200
_MAX_RETRIES: int = 3
_BACKOFF_FACTOR: float = 2.0
_TEST_URL: str = "https://example.com/api"


def _fake_transport(mocker: MockerFixture, statuses: Iterator[int]) -> MagicMock:
    """Подменяет ``HTTPConnectionPool._make_request`` фальшивым транспортом.

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
@pytest.mark.parametrize("retryable_status", _RETRY_STATUS_CODES)
def test_retryable_session_retries_on_every_configured_status(
    mocker: MockerFixture, retryable_status: int
) -> None:
    """После одного ответа с любым статусом из ``_RETRY_STATUS_CODES`` сессия
    автоматически повторяет запрос и возвращает результат второй, успешной
    попытки.

    Параметризовано по самому ``_RETRY_STATUS_CODES``, чтобы тест реально покрывал
    все коды, которые модуль считает временными и ДОСТОЙНЫМИ повтора — 408/429/500/502/503/504.
    """
    mock_transport = _fake_transport(mocker, iter([retryable_status, _HTTP_OK]))
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
def test_retryable_session_backs_off_between_retries(mocker: MockerFixture) -> None:
    """Пауза между повторными попытками растёт от повтора к повтору."""
    mock_sleep = mocker.patch("time.sleep")
    # urllib3 не спит перед самым первым повтором (backoff=0 при одном подряд
    # сбое), поэтому нужны три неудачи подряд, чтобы получить два ненулевых,
    # растущих интервала ожидания.
    _fake_transport(mocker, iter([_HTTP_TOO_MANY, _HTTP_TOO_MANY, _HTTP_TOO_MANY, _HTTP_OK]))
    session = RetryableSession(max_retries=_MAX_RETRIES, backoff_factor=_BACKOFF_FACTOR)

    response = session.get(_TEST_URL)

    assert response.status_code == _HTTP_OK
    assert mock_sleep.call_count == 2
    first_delay, second_delay = (call.args[0] for call in mock_sleep.call_args_list)
    assert second_delay > first_delay


@pytest.mark.infrastructure
def test_retryable_session_timeout_forwarded_to_request(
    mocker: MockerFixture,
) -> None:
    """RetryableSession.request() внедряет свой _timeout в каждый вызов super().request()."""
    mock_super_request: MagicMock = mocker.patch.object(
        requests.Session, "request", return_value=MagicMock(status_code=_HTTP_OK)
    )

    session = RetryableSession(timeout=_TIMEOUT_SEC)
    session.get(_TEST_URL)

    mock_super_request.assert_called_once()
    call_kwargs = mock_super_request.call_args.kwargs
    assert call_kwargs.get("timeout") == _TIMEOUT_SEC


@pytest.mark.business_logic
@responses.activate
def test_create_bearer_session_sends_bearer_authorization_header() -> None:
    """create_bearer_session(token=...) фактически отправляет заголовок
    'Authorization: Bearer <token>' в исходящем запросе — это единственный
    наблюдаемый эффект настройки Bearer-аутентификации."""
    responses.add(responses.GET, _TEST_URL, json={"ok": True}, status=200)
    session = create_bearer_session(token="my-pat-token")

    session.get(_TEST_URL)

    assert responses.calls[0].request.headers["Authorization"] == "Bearer my-pat-token"


@pytest.mark.business_logic
@responses.activate
def test_create_bearer_session_no_token_sends_no_authorization_header() -> None:
    """create_bearer_session(token=None) не добавляет заголовок Authorization."""
    responses.add(responses.GET, _TEST_URL, json={"ok": True}, status=200)
    session = create_bearer_session(token=None)

    session.get(_TEST_URL)

    assert "Authorization" not in responses.calls[0].request.headers


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "bearer, delegate_target, sentinel_name",
    [
        pytest.param(True, "create_bearer_session", "bearer_session", id="bearer-true"),
        pytest.param(False, "create_pat_session", "pat_session", id="bearer-false"),
    ],
)
def test_create_retryable_session_delegates_to_matching_auth_builder(
    mocker: MockerFixture, bearer: bool, delegate_target: str, sentinel_name: str
) -> None:
    """create_retryable_session(bearer=...) не собирает сессию сама, а делегирует
    её создание create_bearer_session()/create_pat_session() (в зависимости
    от ``bearer``)
    """
    sentinel = getattr(mocker.sentinel, sentinel_name)
    mock_delegate = mocker.patch(
        f"autodoc.common.retryable_session.{delegate_target}", return_value=sentinel
    )

    result = create_retryable_session(
        token="my-pat-token", bearer=bearer, max_retries=5, backoff_factor=2.0, timeout=20
    )

    mock_delegate.assert_called_once_with(
        token="my-pat-token", max_retries=5, backoff_factor=2.0, timeout=20
    )
    assert result is sentinel


@pytest.mark.business_logic
@responses.activate
def test_create_pat_session_sends_basic_auth_with_empty_username() -> None:
    """create_pat_session(token=...) настраивает Basic-аутентификацию с пустым
    именем пользователя и токеном в качестве пароля (PAT-паттерн)."""

    responses.add(responses.GET, _TEST_URL, json={"ok": True}, status=200)
    session = create_pat_session(token="my-pat-token")

    session.get(_TEST_URL)

    auth_header = responses.calls[0].request.headers["Authorization"]
    decoded = base64.b64decode(auth_header.removeprefix("Basic ")).decode()
    assert decoded == ":my-pat-token"
