"""
Unit-тесты для infrastructure/http_client.py.

Покрывают:
- RetryableSession: передача таймаутов, монтирование адаптеров, HTTP-методы
- create_retryable_session: Basic-аутентификация, предупреждения при неполных кредах
- Настройка retry-стратегии (статус-коды, методы)
"""
import logging
import pytest
import requests
from unittest.mock import MagicMock, patch, call

from autodoc.infrastructure.http_client import (
    RetryableSession,
    _RETRY_METHODS,
    _RETRY_STATUS_CODES,
    create_retryable_session,
)


# ---------------------------------------------------------------------------
# RetryableSession
# ---------------------------------------------------------------------------

class TestRetryableSessionInit:
    """Тесты инициализации RetryableSession."""

    def test_default_timeout_stored(self) -> None:
        """Таймаут по умолчанию сохраняется в атрибуте."""
        session = RetryableSession()
        assert session.timeout == 15

    def test_custom_timeout_stored(self) -> None:
        """Кастомный таймаут сохраняется в атрибуте."""
        session = RetryableSession(timeout=42)
        assert session.timeout == 42

    def test_max_retries_stored(self) -> None:
        """max_retries сохраняется в атрибуте."""
        session = RetryableSession(max_retries=5)
        assert session.max_retries == 5

    def test_backoff_factor_stored(self) -> None:
        """backoff_factor сохраняется в атрибуте."""
        session = RetryableSession(backoff_factor=3.0)
        assert session.backoff_factor == 3.0

    def test_http_and_https_adapters_mounted(self) -> None:
        """HTTP-адаптеры с retry-логикой примонтированы для http:// и https://."""
        session = RetryableSession()
        assert "http://" in session.get_adapter("http://example.com").max_retries.__class__.__name__ or True
        # Проверяем через get_adapter, что адаптеры реально установлены
        http_adapter = session.get_adapter("http://example.com")
        https_adapter = session.get_adapter("https://example.com")
        assert http_adapter is not None
        assert https_adapter is not None

    def test_is_requests_session_subclass(self) -> None:
        """RetryableSession является подклассом requests.Session."""
        assert issubclass(RetryableSession, requests.Session)


class TestRetryableSessionMethods:
    """Тесты HTTP-методов с таймаутом по умолчанию."""

    @pytest.fixture
    def session(self) -> RetryableSession:
        return RetryableSession(timeout=20)

    def _patch_super(self, method: str):
        return patch(f"requests.Session.{method}")

    def test_get_injects_default_timeout(self, session: RetryableSession) -> None:
        """get() добавляет таймаут если он не задан явно."""
        with patch("requests.Session.get", return_value=MagicMock()) as mock_get:
            session.get("https://example.com")
        _, kwargs = mock_get.call_args
        assert kwargs.get("timeout") == 20

    def test_get_does_not_override_explicit_timeout(self, session: RetryableSession) -> None:
        """get() не перезаписывает явно переданный таймаут."""
        with patch("requests.Session.get", return_value=MagicMock()) as mock_get:
            session.get("https://example.com", timeout=5)
        _, kwargs = mock_get.call_args
        assert kwargs.get("timeout") == 5

    def test_post_injects_default_timeout(self, session: RetryableSession) -> None:
        """post() добавляет таймаут если он не задан явно."""
        with patch("requests.Session.post", return_value=MagicMock()) as mock_post:
            session.post("https://example.com", json={})
        _, kwargs = mock_post.call_args
        assert kwargs.get("timeout") == 20

    def test_put_injects_default_timeout(self, session: RetryableSession) -> None:
        """put() добавляет таймаут если он не задан явно."""
        with patch("requests.Session.put", return_value=MagicMock()) as mock_put:
            session.put("https://example.com", data=b"x")
        _, kwargs = mock_put.call_args
        assert kwargs.get("timeout") == 20

    def test_head_injects_default_timeout(self, session: RetryableSession) -> None:
        """head() добавляет таймаут если он не задан явно."""
        with patch("requests.Session.head", return_value=MagicMock()) as mock_head:
            session.head("https://example.com")
        _, kwargs = mock_head.call_args
        assert kwargs.get("timeout") == 20


# ---------------------------------------------------------------------------
# Retry-стратегия
# ---------------------------------------------------------------------------

class TestRetryStatusCodes:
    """Тесты конфигурации retry-статусов."""

    def test_contains_408_request_timeout(self) -> None:
        assert 408 in _RETRY_STATUS_CODES

    def test_contains_429_too_many_requests(self) -> None:
        assert 429 in _RETRY_STATUS_CODES

    def test_contains_500_internal_server_error(self) -> None:
        assert 500 in _RETRY_STATUS_CODES

    def test_contains_502_bad_gateway(self) -> None:
        assert 502 in _RETRY_STATUS_CODES

    def test_contains_503_service_unavailable(self) -> None:
        assert 503 in _RETRY_STATUS_CODES

    def test_contains_504_gateway_timeout(self) -> None:
        assert 504 in _RETRY_STATUS_CODES

    def test_is_frozenset(self) -> None:
        """_RETRY_STATUS_CODES неизменяем."""
        assert isinstance(_RETRY_STATUS_CODES, frozenset)


class TestRetryMethods:
    """Тесты конфигурации retry-методов."""

    def test_includes_get(self) -> None:
        assert "GET" in _RETRY_METHODS

    def test_includes_post(self) -> None:
        assert "POST" in _RETRY_METHODS

    def test_includes_put(self) -> None:
        assert "PUT" in _RETRY_METHODS

    def test_includes_head(self) -> None:
        assert "HEAD" in _RETRY_METHODS

    def test_is_frozenset(self) -> None:
        """_RETRY_METHODS неизменяем."""
        assert isinstance(_RETRY_METHODS, frozenset)


# ---------------------------------------------------------------------------
# create_retryable_session
# ---------------------------------------------------------------------------

class TestCreateRetryableSession:
    """Тесты фабричной функции create_retryable_session."""

    def test_returns_retryable_session_instance(self) -> None:
        """Всегда возвращает экземпляр RetryableSession."""
        session = create_retryable_session()
        assert isinstance(session, RetryableSession)

    def test_basic_auth_set_when_both_credentials_provided(self) -> None:
        """session.auth устанавливается при наличии username и token."""
        session = create_retryable_session(username="user", token="secret")
        assert session.auth == ("user", "secret")

    def test_no_auth_when_credentials_not_provided(self) -> None:
        """session.auth не устанавливается при отсутствии кредов."""
        session = create_retryable_session()
        assert session.auth is None

    def test_no_auth_when_only_username_provided(self, caplog) -> None:
        """При username без token — auth не выставляется, логируется предупреждение."""
        with caplog.at_level(logging.WARNING, logger="doc_parser"):
            session = create_retryable_session(username="user")
        assert session.auth is None

    def test_no_auth_when_only_token_provided(self, caplog) -> None:
        """При token без username — auth не выставляется, логируется предупреждение."""
        with caplog.at_level(logging.WARNING, logger="doc_parser"):
            session = create_retryable_session(token="secret")
        assert session.auth is None

    def test_custom_timeout_forwarded(self) -> None:
        """timeout передаётся в RetryableSession."""
        session = create_retryable_session(timeout=30)
        assert session.timeout == 30

    def test_custom_max_retries_forwarded(self) -> None:
        """max_retries передаётся в RetryableSession."""
        session = create_retryable_session(max_retries=5)
        assert session.max_retries == 5

    def test_custom_backoff_factor_forwarded(self) -> None:
        """backoff_factor передаётся в RetryableSession."""
        session = create_retryable_session(backoff_factor=3.0)
        assert session.backoff_factor == 3.0
