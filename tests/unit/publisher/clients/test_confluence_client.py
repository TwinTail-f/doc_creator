"""
Tests for autodoc.publisher.clients.confluence_client.ConfluenceClient.

Testing strategy:
- The HTTP session is mocked via mocker.patch on create_retryable_session.
- The mock_session object returned provides controllable get/post/put responses.
- minimal_confluence_config fixture comes from tests/conftest.py.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import PublishError
from autodoc.publisher.clients.confluence_client import ConfluenceClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPACE: str = "TEST"
PAGE_TITLE: str = "Test Page"
PAGE_BODY: str = "<p>Content</p>"
PAGE_ID: str = "123456"
PARENT_ID: str = "root-001"

_API_BASE: str = "https://confluence.example.com/rest/api"

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def confluence_client(minimal_confluence_config: dict, mocker: Any) -> ConfluenceClient:
    """ConfluenceClient with a fully mocked HTTP session."""
    config = ConfluenceConfigSchema(**minimal_confluence_config)
    mock_session = mocker.MagicMock()
    mocker.patch(
        "autodoc.publisher.clients.confluence_client.create_retryable_session",
        return_value=mock_session,
    )
    client = ConfluenceClient(config)
    client._mock_session = mock_session  # type: ignore[attr-defined]
    return client


def _make_response(json_data: Any, status_code: int = 200) -> MagicMock:
    """Build a mock response with controllable json() and raise_for_status()."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            f"HTTP {status_code}",
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# find_page tests
# ---------------------------------------------------------------------------


class TestFindPage:
    """Tests for ConfluenceClient.find_page()."""

    def test_find_page_returns_none_when_not_found(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """find_page returns None when the API returns an empty results list."""
        confluence_client._mock_session.get.return_value = _make_response(
            {"results": []}
        )
        result = confluence_client.find_page(PAGE_TITLE, space=SPACE)
        assert result is None

    def test_find_page_returns_page_dict_when_found(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """find_page returns the first element of results when the page exists."""
        page_data = {"id": PAGE_ID, "title": PAGE_TITLE}
        confluence_client._mock_session.get.return_value = _make_response(
            {"results": [page_data]}
        )
        result = confluence_client.find_page(PAGE_TITLE, space=SPACE)
        assert result is not None
        assert result["id"] == PAGE_ID
        assert result["title"] == PAGE_TITLE


# ---------------------------------------------------------------------------
# get_page_body tests
# ---------------------------------------------------------------------------


class TestGetPageBody:
    """Tests for ConfluenceClient.get_page_body()."""

    def test_get_page_body_returns_empty_string_when_page_not_found(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """get_page_body returns '' when the page does not exist."""
        confluence_client._mock_session.get.return_value = _make_response(
            {"results": []}
        )
        result = confluence_client.get_page_body(space=SPACE, title=PAGE_TITLE)
        assert result == ""

    def test_get_page_body_returns_body_when_page_exists(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """get_page_body returns the storage value when the page exists."""
        page_data = {
            "id": PAGE_ID,
            "title": PAGE_TITLE,
            "body": {"storage": {"value": "<p>html</p>"}},
        }
        confluence_client._mock_session.get.return_value = _make_response(
            {"results": [page_data]}
        )
        result = confluence_client.get_page_body(space=SPACE, title=PAGE_TITLE)
        assert result == "<p>html</p>"


# ---------------------------------------------------------------------------
# publish_page tests
# ---------------------------------------------------------------------------


class TestPublishPage:
    """Tests for ConfluenceClient.publish_page()."""

    def _setup_not_found_then_created(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """Configure the mock so find_page returns None and create_page succeeds."""
        find_resp = _make_response({"results": []})
        create_resp = _make_response({"id": PAGE_ID})
        confluence_client._mock_session.get.return_value = find_resp
        confluence_client._mock_session.post.return_value = create_resp

    def _setup_existing_page(self, confluence_client: ConfluenceClient) -> None:
        """Configure the mock so find_page returns an existing page and update succeeds."""
        existing = {
            "id": PAGE_ID,
            "title": PAGE_TITLE,
            "version": {"number": 3},
            "ancestors": [{"id": PARENT_ID}],
        }
        find_resp = _make_response({"results": [existing]})
        update_resp = _make_response({"id": PAGE_ID})
        confluence_client._mock_session.get.return_value = find_resp
        confluence_client._mock_session.put.return_value = update_resp

    def test_publish_page_creates_new_page_when_not_exists(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """When the page doesn't exist, a POST request is made."""
        self._setup_not_found_then_created(confluence_client)
        confluence_client.publish_page(
            space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE, body_html=PAGE_BODY
        )
        confluence_client._mock_session.post.assert_called_once()

    def test_publish_page_updates_existing_page_when_exists(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """When the page exists, a PUT request is made."""
        self._setup_existing_page(confluence_client)
        confluence_client.publish_page(
            space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE, body_html=PAGE_BODY
        )
        confluence_client._mock_session.put.assert_called_once()

    def test_publish_page_returns_dict_with_id_version_status(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """publish_page returns a dict containing id, version, and status keys."""
        self._setup_not_found_then_created(confluence_client)
        result = confluence_client.publish_page(
            space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE, body_html=PAGE_BODY
        )
        assert "id" in result
        assert "version" in result
        assert "status" in result

    def test_publish_page_raises_publish_error_on_http_error(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """publish_page raises PublishError when the HTTP request fails."""
        confluence_client._mock_session.get.return_value = _make_response(
            {"error": "forbidden"}, status_code=403
        )
        with pytest.raises(PublishError):
            confluence_client.publish_page(
                space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE, body_html=PAGE_BODY
            )


# ---------------------------------------------------------------------------
# get_or_create_page tests
# ---------------------------------------------------------------------------


class TestGetOrCreatePage:
    """Tests for ConfluenceClient.get_or_create_page()."""

    def test_get_or_create_page_returns_id_if_page_exists(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """Returns the existing page's ID without issuing a POST request."""
        existing = {
            "id": PAGE_ID,
            "title": PAGE_TITLE,
            "ancestors": [{"id": PARENT_ID}],
        }
        confluence_client._mock_session.get.return_value = _make_response(
            {"results": [existing]}
        )
        result = confluence_client.get_or_create_page(
            space=SPACE, title=PAGE_TITLE, parent_id=PARENT_ID
        )
        assert result == PAGE_ID
        confluence_client._mock_session.post.assert_not_called()

    def test_get_or_create_page_creates_and_returns_id_if_not_exists(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """Creates the page and returns the new ID when the page doesn't exist."""
        confluence_client._mock_session.get.return_value = _make_response(
            {"results": []}
        )
        confluence_client._mock_session.post.return_value = _make_response(
            {"id": PAGE_ID}
        )
        result = confluence_client.get_or_create_page(
            space=SPACE, title=PAGE_TITLE, parent_id=PARENT_ID
        )
        assert result == PAGE_ID
        confluence_client._mock_session.post.assert_called_once()


# ---------------------------------------------------------------------------
# Phase 5 — timeout forwarding test
# ---------------------------------------------------------------------------


class TestTimeoutForwarding:
    """Tests that confluence_request_timeout reaches the HTTP session."""

    def test_confluence_client_passes_timeout_to_session(
        self, minimal_confluence_config: dict, mocker: Any
    ) -> None:
        """ConfluenceClient forwards confluence_request_timeout to create_retryable_session."""
        custom_timeout = 99
        cfg = dict(minimal_confluence_config)
        cfg["confluence_request_timeout"] = custom_timeout
        config = ConfluenceConfigSchema(**cfg)

        mock_create = mocker.patch(
            "autodoc.publisher.clients.confluence_client.create_retryable_session",
            return_value=mocker.MagicMock(),
        )
        ConfluenceClient(config)
        _, kwargs = mock_create.call_args
        assert kwargs.get("timeout") == custom_timeout


# ---------------------------------------------------------------------------
# T3.6 — Protocol compliance
# ---------------------------------------------------------------------------


def test_confluence_client_satisfies_protocol(
    minimal_confluence_config: dict, mocker
) -> None:
    """ConfluenceClient must satisfy IConfluenceClient at runtime."""
    from autodoc.publisher.clients.confluence_client import ConfluenceClient
    from autodoc.publisher.clients.confluence_client_protocol import IConfluenceClient
    from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema

    mocker.patch(
        "autodoc.publisher.clients.confluence_client.create_retryable_session",
        return_value=mocker.MagicMock(),
    )
    config = ConfluenceConfigSchema(**minimal_confluence_config)
    client = ConfluenceClient(config=config)
    assert isinstance(client, IConfluenceClient)
