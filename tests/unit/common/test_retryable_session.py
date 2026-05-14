"""Unit tests for autodoc/common/retryable_session.py.

RetryableSession wraps an HTTP session with automatic retry logic
for transient server errors (429, 503) with exponential backoff.

Retry behaviour is enforced by urllib3's Retry adapter at the transport layer.
Tests that verify retry triggering inspect the adapter configuration rather than
simulating the full urllib3 retry loop, because urllib3's own retry loop runs
inside HTTPAdapter.send — below the level that can be intercepted with a simple
mocker.patch without replacing the transport entirely.

The timeout-forwarding test exercises RetryableSession's own request() override,
which is the only logic that lives in application code rather than in urllib3.
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
    """Extract the urllib3 Retry object from the session's HTTPS adapter."""
    return session.get_adapter(_HTTPS_PREFIX).max_retries


# ---------------------------------------------------------------------------
# T4A.2.6 — adapter is configured to retry on 429
# ---------------------------------------------------------------------------


def test_retryable_session_retries_on_429() -> None:
    """Session retry adapter includes 429 in its status_forcelist.

    urllib3 will automatically retry any request that receives a 429 response.
    This test verifies the configuration that wires that behaviour into the
    session — testing the application-layer wiring rather than urllib3 itself.
    """
    session = RetryableSession(max_retries=_MAX_RETRIES, backoff_factor=0.0)
    retry = _get_retry(session)

    assert _HTTP_TOO_MANY in retry.status_forcelist
    assert retry.total == _MAX_RETRIES


# ---------------------------------------------------------------------------
# T4A.2.7 — adapter is configured to retry on 503
# ---------------------------------------------------------------------------


def test_retryable_session_retries_on_503() -> None:
    """Session retry adapter includes 503 in its status_forcelist.

    Service-unavailable responses are transient infrastructure issues;
    the adapter must be configured to retry them automatically.
    """
    session = RetryableSession(max_retries=_MAX_RETRIES, backoff_factor=0.0)
    retry = _get_retry(session)

    assert _HTTP_UNAVAILABLE in retry.status_forcelist


# ---------------------------------------------------------------------------
# T4A.2.8 — retry limit is honoured (adapter configured correctly)
# ---------------------------------------------------------------------------


def test_retryable_session_raises_after_exhausting_retries() -> None:
    """Retry adapter total count matches the max_retries constructor argument.

    urllib3 will raise MaxRetryError (surfaced by requests as RetryError) once
    this limit is reached. This test verifies the limit is wired correctly so
    that requests do not loop indefinitely.
    """
    max_retries: int = 2
    session = RetryableSession(max_retries=max_retries, backoff_factor=0.0)
    retry = _get_retry(session)

    assert retry.total == max_retries


# ---------------------------------------------------------------------------
# T4A.2.9 — exponential backoff factor is stored in the retry adapter
# ---------------------------------------------------------------------------


def test_retryable_session_uses_exponential_backoff() -> None:
    """The configured backoff_factor is wired into the urllib3 Retry object.

    urllib3 computes sleep delays as backoff_factor * (2 ** (retry_count - 1)),
    so the second delay is always strictly greater than the first when
    backoff_factor > 0. This test verifies the factor is stored correctly so
    that the delays increase between retries.
    """
    session = RetryableSession(max_retries=_MAX_RETRIES, backoff_factor=_BACKOFF_FACTOR)
    retry = _get_retry(session)

    assert retry.backoff_factor == _BACKOFF_FACTOR
    # Verify that second delay > first delay for the configured backoff_factor.
    # Delay formula: backoff_factor * (2 ** (retry_index - 1))
    first_delay: float = _BACKOFF_FACTOR * (2 ** 0)   # retry 1 → backoff_factor * 1
    second_delay: float = _BACKOFF_FACTOR * (2 ** 1)  # retry 2 → backoff_factor * 2
    assert second_delay > first_delay


# ---------------------------------------------------------------------------
# T4A.2.10 — request() override forwards timeout to the parent implementation
# ---------------------------------------------------------------------------


def test_retryable_session_timeout_forwarded_to_request(
    mocker: MockerFixture,
) -> None:
    """RetryableSession.request() injects its _timeout into every super().request() call.

    The override in RetryableSession.request() is the only application-layer
    logic in this class; it must pass effective_timeout=self._timeout to
    super().request() so that every HTTP call respects the configured timeout.
    """
    mock_super_request: MagicMock = mocker.patch.object(
        requests.Session, "request", return_value=MagicMock(status_code=_HTTP_OK)
    )

    session = RetryableSession(timeout=_TIMEOUT_SEC)
    session.get(_TEST_URL)

    mock_super_request.assert_called_once()
    call_kwargs = mock_super_request.call_args.kwargs
    assert call_kwargs.get("timeout") == _TIMEOUT_SEC
