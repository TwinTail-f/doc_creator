"""
Tests for autodoc.publisher.clients.confluence_client.ConfluenceClient.

Testing strategy:
- ConfluenceClient delegates all HTTP calls to a ConfluenceTransport instance
  (self._transport). ConfluenceTransport itself is fully mocked via
  mocker.patch on the ConfluenceTransport class import in confluence_client,
  so no real HTTP session or network calls are involved.
- The mock_transport object provides controllable search_content / get_content /
  create_content / update_content responses (raw JSON dicts, matching the
  ConfluenceTransport public contract).
- minimal_confluence_config fixture comes from tests/conftest.py.
"""

from __future__ import annotations

from typing import Any

import pytest

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfluenceError, PublishError
from autodoc.publisher.clients.confluence_client import ConfluenceClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPACE: str = "TEST"
PAGE_TITLE: str = "Test Page"
PAGE_BODY: str = "<p>Content</p>"
PAGE_ID: str = "123456"
PARENT_ID: str = "root-001"

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def confluence_client(minimal_confluence_config: dict, mocker: Any) -> ConfluenceClient:
    """ConfluenceClient with a fully mocked ConfluenceTransport."""
    config = ConfluenceConfigSchema(**minimal_confluence_config)
    mock_transport = mocker.MagicMock()
    mocker.patch(
        "autodoc.publisher.clients.confluence_client.ConfluenceTransport",
        return_value=mock_transport,
    )
    client = ConfluenceClient(config)
    client._mock_transport = mock_transport  # type: ignore[attr-defined]
    return client


@pytest.fixture
def confluence_client_move_policy(minimal_confluence_config: dict, mocker: Any) -> ConfluenceClient:
    """ConfluenceClient configured with title_conflict_policy='move' via the public config.

    Built the same way production code builds it (through ConfluenceConfigSchema),
    rather than mutating the private _title_conflict_policy attribute directly,
    so the test exercises the real config-driven code path.
    """
    cfg = dict(minimal_confluence_config)
    cfg["title_conflict_policy"] = "move"
    config = ConfluenceConfigSchema(**cfg)
    mock_transport = mocker.MagicMock()
    mocker.patch(
        "autodoc.publisher.clients.confluence_client.ConfluenceTransport",
        return_value=mock_transport,
    )
    client = ConfluenceClient(config)
    client._mock_transport = mock_transport  # type: ignore[attr-defined]
    return client


# ---------------------------------------------------------------------------
# find_page tests
# ---------------------------------------------------------------------------


class TestFindPage:
    """Tests for ConfluenceClient.find_page()."""

    @pytest.mark.infrastructure
    def test_find_page_returns_none_when_not_found(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """find_page returns None when the transport returns an empty results list."""
        confluence_client._mock_transport.search_content.return_value = []
        result = confluence_client.find_page(PAGE_TITLE, space=SPACE)
        assert result is None

    @pytest.mark.infrastructure
    def test_find_page_returns_page_dict_when_found(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """find_page returns a ConfluencePage built from the first result when the page exists."""
        page_data = {"id": PAGE_ID, "title": PAGE_TITLE}
        confluence_client._mock_transport.search_content.return_value = [page_data]
        result = confluence_client.find_page(PAGE_TITLE, space=SPACE)
        assert result is not None
        assert result.id == PAGE_ID
        assert result.title == PAGE_TITLE


# ---------------------------------------------------------------------------
# get_page_body tests
# ---------------------------------------------------------------------------


class TestGetPageBody:
    """Tests for ConfluenceClient.get_page_body()."""

    @pytest.mark.infrastructure
    def test_get_page_body_returns_empty_string_when_page_not_found(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """get_page_body returns '' when the page does not exist."""
        confluence_client._mock_transport.search_content.return_value = []
        result = confluence_client.get_page_body(space=SPACE, title=PAGE_TITLE)
        assert result == ""

    @pytest.mark.infrastructure
    def test_get_page_body_returns_body_when_page_exists(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """get_page_body returns the storage value when the page exists."""
        page_data = {
            "id": PAGE_ID,
            "title": PAGE_TITLE,
            "body": {"storage": {"value": "<p>html</p>"}},
        }
        confluence_client._mock_transport.search_content.return_value = [page_data]
        result = confluence_client.get_page_body(space=SPACE, title=PAGE_TITLE)
        assert result == "<p>html</p>"


# ---------------------------------------------------------------------------
# publish_page tests
# ---------------------------------------------------------------------------


class TestPublishPage:
    """Tests for ConfluenceClient.publish_page()."""

    def _setup_not_found_then_created(self, confluence_client: ConfluenceClient) -> None:
        """Configure the mock so find_page returns None and create_page succeeds."""
        confluence_client._mock_transport.search_content.return_value = []
        confluence_client._mock_transport.create_content.return_value = {"id": PAGE_ID}

    def _setup_existing_page(self, confluence_client: ConfluenceClient) -> None:
        """Configure the mock so find_page returns an existing page and update succeeds."""
        existing = {
            "id": PAGE_ID,
            "title": PAGE_TITLE,
            "version": {"number": 3},
            "ancestors": [{"id": PARENT_ID}],
        }
        confluence_client._mock_transport.search_content.return_value = [existing]
        confluence_client._mock_transport.update_content.return_value = {"id": PAGE_ID}

    @pytest.mark.infrastructure
    def test_publish_page_creates_new_page_when_not_exists(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """When the page doesn't exist, create_content is called."""
        self._setup_not_found_then_created(confluence_client)
        confluence_client.publish_page(
            space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE, body_html=PAGE_BODY
        )
        confluence_client._mock_transport.create_content.assert_called_once()

    @pytest.mark.infrastructure
    def test_publish_page_updates_existing_page_when_exists(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """When the page exists, update_content is called."""
        self._setup_existing_page(confluence_client)
        confluence_client.publish_page(
            space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE, body_html=PAGE_BODY
        )
        confluence_client._mock_transport.update_content.assert_called_once()

    @pytest.mark.contract
    def test_publish_page_returns_dict_with_id_version_status(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """publish_page returns a PageResult exposing id, version, and status."""
        self._setup_not_found_then_created(confluence_client)
        result = confluence_client.publish_page(
            space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE, body_html=PAGE_BODY
        )
        assert result.id == PAGE_ID
        assert result.version == 1
        assert result.status == "created"

    @pytest.mark.infrastructure
    def test_publish_page_raises_publish_error_on_http_error(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """publish_page raises PublishError when the transport reports an HTTP error."""
        confluence_client._mock_transport.search_content.side_effect = ConfluenceError(
            "HTTP 403"
        )
        with pytest.raises(PublishError):
            confluence_client.publish_page(
                space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE, body_html=PAGE_BODY
            )

    @pytest.mark.business_logic
    def test_publish_page_calls_put_even_when_page_under_wrong_parent(
        self,
        confluence_client_move_policy: ConfluenceClient,
    ) -> None:
        """publish_page issues update_content even when found page's ancestor differs (title_conflict_policy='move')."""
        WRONG_PARENT = "wrong-parent-999"

        existing_page = {
            "id": PAGE_ID,
            "title": PAGE_TITLE,
            "version": {"number": 4},
            "ancestors": [{"id": WRONG_PARENT}],
        }
        confluence_client_move_policy._mock_transport.search_content.return_value = [existing_page]
        confluence_client_move_policy._mock_transport.update_content.return_value = {"id": PAGE_ID}

        confluence_client_move_policy.publish_page(
            space=SPACE,
            parent_id=PARENT_ID,  # different from WRONG_PARENT
            title=PAGE_TITLE,
            body_html=PAGE_BODY,
        )

        confluence_client_move_policy._mock_transport.update_content.assert_called_once()

    @pytest.mark.business_logic
    def test_publish_page_put_payload_contains_correct_parent_id(
        self,
        confluence_client_move_policy: ConfluenceClient,
    ) -> None:
        """update_content payload ancestors[0].id equals the requested parent_id, not the old one."""
        OLD_PARENT = "old-parent-111"
        NEW_PARENT = "new-parent-222"

        existing_page = {
            "id": PAGE_ID,
            "title": PAGE_TITLE,
            "version": {"number": 2},
            "ancestors": [{"id": OLD_PARENT}],
        }
        confluence_client_move_policy._mock_transport.search_content.return_value = [existing_page]
        confluence_client_move_policy._mock_transport.update_content.return_value = {"id": PAGE_ID}

        confluence_client_move_policy.publish_page(
            space=SPACE,
            parent_id=NEW_PARENT,
            title=PAGE_TITLE,
            body_html=PAGE_BODY,
        )

        update_call = confluence_client_move_policy._mock_transport.update_content.call_args
        payload = update_call.args[1]
        # _build_payload always sets: payload["ancestors"] = [{"id": parent_id}]
        ancestors = payload.get("ancestors", [])
        assert any(
            a["id"] == NEW_PARENT for a in ancestors
        ), f"Expected parent_id={NEW_PARENT!r} in ancestors, got: {ancestors}"

    @pytest.mark.business_logic
    def test_publish_page_version_incremented_on_reparent(
        self,
        confluence_client_move_policy: ConfluenceClient,
    ) -> None:
        """Version number increments correctly (current+1) even when page is moved to new parent."""
        existing_page = {
            "id": PAGE_ID,
            "title": PAGE_TITLE,
            "version": {"number": 7},
            "ancestors": [{"id": "some-other-parent"}],
        }
        confluence_client_move_policy._mock_transport.search_content.return_value = [existing_page]
        confluence_client_move_policy._mock_transport.update_content.return_value = {"id": PAGE_ID}

        result = confluence_client_move_policy.publish_page(
            space=SPACE,
            parent_id=PARENT_ID,
            title=PAGE_TITLE,
            body_html=PAGE_BODY,
        )

        assert result.version == 8  # 7 + 1
        assert result.status == "updated"


# ---------------------------------------------------------------------------
# resolve_existing_page_id tests
#
# (Replaces the former ConfluenceClient.get_or_create_page(), which no longer
# exists: "get or create" orchestration now lives in
# HierarchyManager._get_or_create_page_id(), combining
# ConfluenceClient.resolve_existing_page_id() with ConfluenceClient.create_page().)
# ---------------------------------------------------------------------------


class TestGetOrCreatePage:
    """Tests for ConfluenceClient.resolve_existing_page_id() and create_page()."""

    @pytest.mark.infrastructure
    def test_get_or_create_page_returns_id_if_page_exists(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """resolve_existing_page_id returns the existing page's ID without creating anything."""
        existing = {
            "id": PAGE_ID,
            "title": PAGE_TITLE,
            "version": {"number": 1},
            "ancestors": [{"id": PARENT_ID}],
        }
        confluence_client._mock_transport.search_content.return_value = [existing]
        result = confluence_client.resolve_existing_page_id(
            space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE
        )
        assert result == PAGE_ID
        confluence_client._mock_transport.create_content.assert_not_called()

    @pytest.mark.infrastructure
    def test_get_or_create_page_creates_and_returns_id_if_not_exists(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """When no page is found, resolve_existing_page_id returns None and create_page must be called explicitly."""
        confluence_client._mock_transport.search_content.return_value = []
        result = confluence_client.resolve_existing_page_id(
            space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE
        )
        assert result is None

        confluence_client._mock_transport.create_content.return_value = {"id": PAGE_ID}
        created = confluence_client.create_page(
            space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE, body_html=PAGE_BODY
        )
        assert created.id == PAGE_ID
        confluence_client._mock_transport.create_content.assert_called_once()


# ---------------------------------------------------------------------------
# Phase 5 — timeout forwarding test
# ---------------------------------------------------------------------------


class TestTimeoutForwarding:
    """Tests that confluence_request_timeout reaches the underlying HTTP session."""

    @pytest.mark.infrastructure
    def test_confluence_client_passes_timeout_to_session(
        self, minimal_confluence_config: dict, mocker: Any
    ) -> None:
        """ConfluenceClient forwards confluence_request_timeout to create_bearer_session via ConfluenceTransport."""
        custom_timeout = 99
        cfg = dict(minimal_confluence_config)
        cfg["confluence_request_timeout"] = custom_timeout
        config = ConfluenceConfigSchema(**cfg)

        mock_create = mocker.patch(
            "autodoc.publisher.clients.confluence_transport.create_bearer_session",
            return_value=mocker.MagicMock(),
        )
        ConfluenceClient(config)
        _, kwargs = mock_create.call_args
        assert kwargs.get("timeout") == custom_timeout
